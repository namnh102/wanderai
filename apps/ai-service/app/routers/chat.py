"""Chat Router — AI chat voi Function Calling that su, fail-closed RAG/LLM va session isolation."""
import os
import re
from typing import Any, Dict, List, Optional
import uuid

os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.security.internal_auth import InternalPrincipal, require_internal_principal
from app.services.chat_llm import LLMProviderError, SessionOwnershipError, gemini_provider
from app.services.rag import RAGService, RetrievalResult, RetrievalStatus
from app.tools.calculate_budget import CalculateBudgetTool
from app.tools.get_weather import GetWeatherTool
from app.tools.search_places import SearchPlacesTool

router = APIRouter(prefix="/chat", tags=["Chat"])

# Production toolset excludes SearchHotelsTool because no verified hotel inventory is connected.
_TOOLS = [
    GetWeatherTool(),
    SearchPlacesTool(),
    CalculateBudgetTool(),
]


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None


class ToolCallLog(BaseModel):
    tool: str
    args: dict
    result: Any


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    tools_used: List[str] = []
    tool_calls: List[ToolCallLog] = []
    # Candidate source URLs retrieved from the RAG corpus (OpenStreetMap / Wikivoyage) for this query;
    # these represent retrieved context candidates, NOT claim-level verified answer citations (W07 G5=HOLD).
    sources: List[str] = []
    retrieval_status: RetrievalStatus = "ok"
    can_plan_trip: bool = False
    planning_context: Optional[Dict[str, Any]] = None


_rag_service: Optional[RAGService] = None


async def retrieve_grounding(message: str) -> RetrievalResult:
    """Retrieve verified knowledge with explicit tri-state status (ok | empty | error)."""
    global _rag_service
    try:
        if _rag_service is None:
            _rag_service = RAGService()
        return await _rag_service.retrieve_with_status(message, top_k=4)
    except Exception as e:  # noqa: BLE001
        return RetrievalResult(
            status="error",
            context="",
            chunks=[],
            sources=[],
            error_type=type(e).__name__,
        )


def _normalize_retrieval_result(raw: Any) -> RetrievalResult:
    """Normalize either RetrievalResult or legacy (context, sources) 2-tuple from test mocks."""
    if isinstance(raw, RetrievalResult):
        return raw
    if isinstance(raw, tuple) and len(raw) == 2:
        context, sources = raw
        src_list = list(sources or [])
        ctx_str = context or ""
        status: RetrievalStatus = "ok" if (ctx_str or src_list) else "empty"
        return RetrievalResult(
            status=status,
            context=ctx_str,
            chunks=[],
            sources=src_list,
        )
    return RetrievalResult(
        status="error",
        context="",
        chunks=[],
        sources=[],
        error_type="InvalidRetrievalResultType",
    )


NO_CONTEXT_INSTRUCTION = (
    "Không có dữ liệu truy xuất cho câu hỏi này. Chỉ nêu thông tin thực tế về địa điểm nếu có kết quả tool; "
    "không bịa giờ mở cửa, giá vé hay đánh giá. Nếu thiếu, nói rõ là chưa có thông tin trong dữ liệu hiện có."
)


C4_CHAT_BUDGET_INSTRUCTION = (
    "Quy tắc trình bày ngân sách (C4): Khi lập hoặc tư vấn lịch trình mà có bất kỳ địa điểm/khoản mục nào chưa biết giá "
    "hoặc chưa có thông tin giá xác minh trong dữ liệu, chỉ cộng các khoản đã biết giá và ghi rõ theo mẫu: "
    "\"Đã biết <tổng tiền đã biết>đ; còn khoản chưa xác minh\" (ví dụ: \"Đã biết 80.000đ; còn khoản chưa xác minh\"). "
    "Tuyệt đối KHÔNG lấy tổng ngân sách trừ đi phần đã biết để báo \"còn dư ...\" hay \"số tiền còn lại ...\" như số dư cuối cùng."
)

_VN_WORD_NUMBERS = {
    "một": 1,
    "mot": 1,
    "hai": 2,
    "ba": 3,
    "bốn": 4,
    "bon": 4,
    "tư": 4,
    "năm": 5,
    "nam": 5,
    "sáu": 6,
    "sau": 6,
    "bảy": 7,
    "bay": 7,
    "tám": 8,
    "tam": 8,
    "chín": 9,
    "chin": 9,
    "mười": 10,
    "muoi": 10,
}

_PLANNING_INTENT_RE = re.compile(
    r"(lập\s+(?:giúp\s+(?:tôi|mình)\s+)?(?:một\s+)?lịch|lịch\s*trình|lên\s+lịch|kế\s*hoạch\s*(?:đi|chuyến|tham\s*quan)|đi\s+.+\s+từ\s+\d{1,2}\s*(?:h|:|giờ))",
    re.IGNORECASE,
)


def _format_dot_vnd(amount: int) -> str:
    return f"{amount:,}".replace(",", ".")


def extract_planning_request_context(message: str, reply: str = "") -> tuple[bool, Optional[Dict[str, Any]]]:
    """Deterministically detect itinerary-planning intent and extract party size, time window, budget, and interests."""
    msg = (message or "").strip()
    if not msg:
        return False, None

    has_intent = bool(_PLANNING_INTENT_RE.search(msg))
    if not has_intent and reply:
        has_intent = bool(
            re.search(r"lịch\s*trình", reply, re.IGNORECASE)
            and re.search(r"\b\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\b", reply)
        )
    if not has_intent:
        return False, None

    lower = msg.lower()

    # 1. Party size & description (e.g., "Hai người lớn", "3 người")
    party_size: Optional[int] = None
    party_description: Optional[str] = None
    m_party_num = re.search(r"\b(\d{1,2})\s*(người\s*lớn|người|khách|bạn)\b", lower)
    if m_party_num:
        party_size = int(m_party_num.group(1))
        party_description = f"{party_size} {m_party_num.group(2).strip()}"
    else:
        for word, val in _VN_WORD_NUMBERS.items():
            m_word = re.search(rf"\b{word}\s+(người\s*lớn|người|khách)\b", lower)
            if m_word:
                party_size = val
                party_description = f"{val} {m_word.group(1).strip()}"
                break

    # 2. Time window (e.g., "từ 8h đến 12h", "từ 08:30 đến 12:00")
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    m_time = re.search(
        r"từ\s*(\d{1,2})(?:[:hgiờ\s]*(\d{2}))?\s*(?:h|giờ)?\s*(?:đến|tới|-)\s*(\d{1,2})(?:[:hgiờ\s]*(\d{2}))?\s*(?:h|giờ)?",
        lower,
    )
    if m_time:
        sh, sm, eh, em = (
            int(m_time.group(1)),
            int(m_time.group(2) or 0),
            int(m_time.group(3)),
            int(m_time.group(4) or 0),
        )
        if 0 <= sh <= 23 and 0 <= sm <= 59 and 0 <= eh <= 23 and 0 <= em <= 59:
            time_start = f"{sh:02d}:{sm:02d}"
            time_end = f"{eh:02d}:{em:02d}"

    # 3. Total budget in VND (e.g., "500.000 đồng", "500k", "1.5 triệu")
    total_budget: Optional[int] = None
    m_trieu = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:triệu|tr)\b", lower)
    m_vnd = re.search(r"(\d{1,3}(?:[.,]\d{3})+|\d{5,9})\s*(?:đồng|vnd|vnđ|đ)\b", lower)
    m_k = re.search(r"\b(\d{2,5})\s*k\b", lower)
    if m_trieu:
        total_budget = int(round(float(m_trieu.group(1).replace(",", ".")) * 1_000_000))
    elif m_vnd:
        digits = re.sub(r"[^\d]", "", m_vnd.group(1))
        if digits:
            total_budget = int(digits)
    elif m_k:
        total_budget = int(m_k.group(1)) * 1000

    # 4. Interests
    interests: List[str] = []
    interest_map = [
        (("bảo tàng", "museum"), "museum"),
        (("văn hóa", "lịch sử", "di tích", "chùa", "đền"), "culture"),
        (("biển", "bãi tắm", "đảo"), "beach"),
        (("ẩm thực", "ăn uống", "quán ăn", "đặc sản"), "food"),
        (("thiên nhiên", "núi", "hang động", "vịnh"), "nature"),
        (("chụp ảnh", "check-in", "sống ảo"), "photography"),
        (("chợ", "mua sắm"), "shopping"),
    ]
    for keywords, tag in interest_map:
        if any(kw in lower for kw in keywords) and tag not in interests:
            interests.append(tag)

    return True, {
        "raw_prompt": msg,
        "party_size": party_size,
        "party_description": party_description,
        "time_window_start": time_start,
        "time_window_end": time_end,
        "total_budget": total_budget,
        "interests": interests,
    }


def enforce_c4_chat_budget_presentation(reply: str, planning_ctx: Optional[Dict[str, Any]] = None) -> str:
    """Ensure chat itinerary replies never present misleading remaining surplus when prices are unknown."""
    if not reply:
        return reply

    has_unknown_price = bool(
        re.search(
            r"(chưa\s+biết\s+giá|chưa\s+có\s+(?:thông\s+tin|dữ\s+liệu)\s+giá|chưa\s+xác\s+minh)",
            reply,
            re.IGNORECASE,
        )
    )
    if not has_unknown_price:
        return reply

    surplus_line_re = re.compile(
        r"^[^\n]*(?:còn\s+dư|số\s+tiền\s+còn\s+(?:dư|lại)|tiền\s+dư|ngân\s+sách\s+còn\s+lại)[^\n]*\d[\d.,]*\s*(?:đồng|vnd|vnđ|đ)[^\n]*$",
        re.IGNORECASE | re.MULTILINE,
    )

    # Extract known total if explicitly stated or sum item totals when unambiguous
    known_amount: Optional[int] = None
    budget_val = (planning_ctx or {}).get("total_budget")
    m_surplus_num = surplus_line_re.search(reply)
    if m_surplus_num and isinstance(budget_val, int) and budget_val > 0:
        m_num = re.search(r"(\d{1,3}(?:[.,]\d{3})+|\d{4,9})\s*(?:đồng|vnd|vnđ|đ)", m_surplus_num.group(0), re.IGNORECASE)
        if m_num:
            surplus_digits = int(re.sub(r"[^\d]", "", m_num.group(1)))
            if 0 <= surplus_digits <= budget_val:
                known_amount = budget_val - surplus_digits

    if known_amount is None:
        m_known = re.search(
            r"(?:đã\s+biết|đã\s+xác\s+minh|tổng\s+tiền\s+vé|chi\s+phí\s+cho\s+\d+\s+người\s+lớn)[^\n:]*:\s*\**(\d{1,3}(?:[.,]\d{3})+|\d{4,9})\s*(?:đồng|vnd|vnđ|đ)",
            reply,
            re.IGNORECASE,
        )
        if m_known:
            known_amount = int(re.sub(r"[^\d]", "", m_known.group(1)))

    c4_line = (
        f"* **Tổng hợp chi phí (theo quy tắc C4):** Đã biết {_format_dot_vnd(known_amount)}đ; còn khoản chưa xác minh (chưa đủ căn cứ tính tiền dư cuối cùng)."
        if known_amount is not None
        else "* **Tổng hợp chi phí (theo quy tắc C4):** Còn khoản chưa xác minh giá nên chưa đủ căn cứ tính tiền dư cuối cùng."
    )

    cleaned = surplus_line_re.sub(c4_line, reply)
    if "còn khoản chưa xác minh" not in cleaned.lower() and known_amount is not None:
        cleaned = f"{cleaned.rstrip()}\n\n{c4_line}"
    return cleaned


def build_grounded_message(message: str, context: str) -> str:
    if not context:
        return f"{NO_CONTEXT_INSTRUCTION}\n\n{C4_CHAT_BUDGET_INSTRUCTION}\n\nCâu hỏi của người dùng: {message}"
    return (
        "Dữ liệu truy xuất từ nguồn mở (OpenStreetMap, Wikivoyage). Khi nói về các địa điểm/thông tin có trong dữ liệu này, "
        "chỉ dùng đúng dữ liệu bên dưới; không bịa thêm giờ mở cửa, giá vé hay thông tin không có trong dữ liệu.\n\n"
        f"{C4_CHAT_BUDGET_INSTRUCTION}\n\n"
        f"{context}\n\nCâu hỏi của người dùng: {message}"
    )


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    principal: InternalPrincipal = Depends(require_internal_principal),
):
    """Chat voi AI Wandy — yeu cau xac thuc noi bo, fail-closed khi RAG/LLM loi."""
    if request.user_id is not None and request.user_id != principal.user_id:
        raise HTTPException(
            status_code=403,
            detail="Request user_id does not match authenticated principal.",
        )

    normalized_req_sid = (request.session_id or "").strip()
    normalized_bound_sid = (principal.bound_session_id or "").strip()
    if normalized_req_sid != normalized_bound_sid:
        raise HTTPException(
            status_code=403,
            detail="Request session_id does not match signed assertion session binding.",
        )

    session_id = normalized_req_sid or str(uuid.uuid4())

    raw_grounding = await retrieve_grounding(request.message)
    grounding = _normalize_retrieval_result(raw_grounding)

    if grounding.status == "error":
        raise HTTPException(
            status_code=503,
            detail="Kho dữ liệu tri thức du lịch tạm thời không khả dụng. Vui lòng thử lại sau.",
        )

    context = grounding.context if grounding.status == "ok" else ""
    sources = list(grounding.sources) if grounding.status == "ok" else []

    try:
        result = await gemini_provider.chat_with_tools(
            message=build_grounded_message(request.message, context),
            tools=_TOOLS,
            session_id=session_id,
            user_id=principal.user_id,
        )
    except SessionOwnershipError as exc:
        raise HTTPException(
            status_code=403,
            detail="Không có quyền truy cập phiên trò chuyện này.",
        ) from exc
    except LLMProviderError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
        ) from exc

    raw_reply = result["response"]
    can_plan_trip, planning_context = extract_planning_request_context(
        request.message, raw_reply
    )
    reply = enforce_c4_chat_budget_presentation(raw_reply, planning_context)
    raw_tool_calls = result.get("tool_calls", [])

    tool_logs = [
        ToolCallLog(
            tool=tc["tool"],
            args=tc.get("args", {}),
            result=tc.get("result"),
        )
        for tc in raw_tool_calls
    ]
    tools_used = [tc["tool"] for tc in raw_tool_calls]

    return ChatResponse(
        reply=reply,
        session_id=session_id,
        tools_used=tools_used,
        tool_calls=tool_logs,
        sources=sources,
        retrieval_status=grounding.status,
        can_plan_trip=can_plan_trip,
        planning_context=planning_context,
    )


@router.delete("/{session_id}")
async def clear_chat(
    session_id: str,
    user_id: Optional[str] = Query(default=None),
    principal: InternalPrincipal = Depends(require_internal_principal),
):
    """Xoa lich su chat — chi cho phep chu so huu session xoa."""
    if user_id is not None and user_id != principal.user_id:
        raise HTTPException(
            status_code=403,
            detail="Query user_id does not match authenticated principal.",
        )
    normalized_path_sid = (session_id or "").strip()
    normalized_bound_sid = (principal.bound_session_id or "").strip()
    if not normalized_path_sid or normalized_bound_sid != normalized_path_sid:
        raise HTTPException(
            status_code=403,
            detail="Path session_id does not match signed assertion session binding.",
        )

    try:
        gemini_provider.clear_session(session_id, user_id=principal.user_id)
    except SessionOwnershipError as exc:
        raise HTTPException(
            status_code=403,
            detail="Không có quyền xóa phiên trò chuyện này.",
        ) from exc

    return {"message": "Chat history cleared"}
