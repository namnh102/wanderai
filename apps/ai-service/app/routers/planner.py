"""AI Trip Planner — Generates structured itineraries using TripContext and Gemini."""
import json
import logging
import math
import os
import re
import time
import uuid
from typing import Optional, Union

from fastapi import APIRouter, HTTPException, Request, Response
from google import genai
from google.genai import types

from app.config import settings
from app.prompts.planner_prompt import build_planner_prompt
from app.routers import chat as chat_router
from app.schemas.planner import (
    BudgetAnalysis,
    ItineraryDay,
    ItineraryItem,
    PlannerModelAttemptTelemetry,
    PlannerTimingTelemetry,
    PlanRequest,
    PlanResponse,
    ScheduleViolation,
    TripContextRequest,
)

router = APIRouter(prefix="/planner", tags=["Trip Planner"])

_client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None
logger = logging.getLogger(__name__)

_STRICT_HHMM_RE = re.compile(r"^(\d{2}):(\d{2})$")


def _clean_json_response(raw: str) -> str:
    """Extract clean JSON string from raw LLM output."""
    raw = raw.strip()
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                raw = part
                break
    raw = raw.strip()

    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start >= 0 and end > start:
        raw = raw[start:end]

    # Remove invalid trailing commas before closing braces/brackets
    raw = re.sub(r",\s*}", "}", raw)
    raw = re.sub(r",\s*]", "]", raw)
    return raw


def _parse_optional_cost(itm: dict) -> tuple[Optional[int], str]:
    """Parse item cost without coercing null/missing/non-numeric values to 0."""
    if "estimated_cost" in itm:
        raw_val = itm.get("estimated_cost")
    elif "cost" in itm:
        raw_val = itm.get("cost")
    else:
        return None, "UNKNOWN"

    if raw_val is None or isinstance(raw_val, bool):
        return None, "UNKNOWN"

    if isinstance(raw_val, (int, float)):
        if math.isnan(raw_val) or math.isinf(raw_val):
            return None, "UNKNOWN"
        return max(0, int(raw_val)), "KNOWN"

    if isinstance(raw_val, str):
        stripped = raw_val.strip()
        if not stripped:
            return None, "UNKNOWN"
        try:
            parsed = float(stripped)
        except ValueError:
            return None, "UNKNOWN"
        if math.isnan(parsed) or math.isinf(parsed):
            return None, "UNKNOWN"
        return max(0, int(parsed)), "KNOWN"

    return None, "UNKNOWN"


def _normalize_optional_str(val: object) -> Optional[str]:
    if not isinstance(val, str):
        return None
    trimmed = val.strip()
    return trimmed if trimmed else None


def _parse_hhmm_minutes(val: Optional[str]) -> Optional[int]:
    if val is None:
        return None
    m = _STRICT_HHMM_RE.match(val.strip())
    if not m:
        return None
    hh = int(m.group(1))
    mm = int(m.group(2))
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        return None
    return hh * 60 + mm


def _format_minutes_hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _detect_day_schedule_violations(
    day_num: int,
    items: list[ItineraryItem],
) -> list[ScheduleViolation]:
    """Detect invalid time intervals and overlapping activities within a day."""
    summary_violations: list[ScheduleViolation] = []
    valid_intervals: list[tuple[int, ItineraryItem, int, int]] = []

    for idx, item in enumerate(items):
        start_raw = item.start_time
        end_raw = item.end_time
        start_min = _parse_hhmm_minutes(start_raw) if start_raw is not None else None
        end_min = _parse_hhmm_minutes(end_raw) if end_raw is not None else None

        if (start_raw is not None and start_min is None) or (
            end_raw is not None and end_min is None
        ):
            v = ScheduleViolation(
                code="TIME_INTERVAL_INVALID",
                reason_code="MALFORMED_HHMM",
                day_number=day_num,
                order_index=item.order_index,
                activity=item.activity,
                place_name=item.place_name,
                start_time=start_raw,
                end_time=end_raw,
                message=(
                    f"Ngày {day_num} • Mục #{item.order_index} \"{item.activity}\": "
                    f"định dạng giờ không hợp lệ ({start_raw or '?'} - {end_raw or '?'})."
                ),
            )
            item.violations.append(v)
            summary_violations.append(v)
            continue

        if start_min is not None and end_min is not None:
            if end_min <= start_min:
                v = ScheduleViolation(
                    code="TIME_INTERVAL_INVALID",
                    reason_code="END_NOT_AFTER_START",
                    day_number=day_num,
                    order_index=item.order_index,
                    activity=item.activity,
                    place_name=item.place_name,
                    start_time=start_raw,
                    end_time=end_raw,
                    message=(
                        f"Ngày {day_num} • Mục #{item.order_index} \"{item.activity}\": "
                        f"giờ kết thúc ({end_raw}) phải sau giờ bắt đầu ({start_raw})."
                    ),
                )
                item.violations.append(v)
                summary_violations.append(v)
                continue
            valid_intervals.append((idx, item, start_min, end_min))

    for i in range(len(valid_intervals)):
        _, item_a, start_a, end_a = valid_intervals[i]
        for j in range(i + 1, len(valid_intervals)):
            _, item_b, start_b, end_b = valid_intervals[j]
            ov_start = max(start_a, start_b)
            ov_end = min(end_a, end_b)
            if ov_start < ov_end:
                ov_str = f"{_format_minutes_hhmm(ov_start)} - {_format_minutes_hhmm(ov_end)}"
                v_a = ScheduleViolation(
                    code="SCHEDULE_OVERLAP",
                    reason_code="OVERLAPPING_TIME_WINDOW",
                    day_number=day_num,
                    order_index=item_a.order_index,
                    conflicting_order_index=item_b.order_index,
                    activity=item_a.activity,
                    place_name=item_a.place_name,
                    start_time=item_a.start_time,
                    end_time=item_a.end_time,
                    message=(
                        f"Chồng giờ khoảng {ov_str} với mục #{item_b.order_index} "
                        f"\"{item_b.activity}\" ({item_b.start_time} - {item_b.end_time})."
                    ),
                )
                v_b = ScheduleViolation(
                    code="SCHEDULE_OVERLAP",
                    reason_code="OVERLAPPING_TIME_WINDOW",
                    day_number=day_num,
                    order_index=item_b.order_index,
                    conflicting_order_index=item_a.order_index,
                    activity=item_b.activity,
                    place_name=item_b.place_name,
                    start_time=item_b.start_time,
                    end_time=item_b.end_time,
                    message=(
                        f"Chồng giờ khoảng {ov_str} với mục #{item_a.order_index} "
                        f"\"{item_a.activity}\" ({item_a.start_time} - {item_a.end_time})."
                    ),
                )
                item_a.violations.append(v_a)
                item_b.violations.append(v_b)
                summary_violations.append(
                    ScheduleViolation(
                        code="SCHEDULE_OVERLAP",
                        reason_code="OVERLAPPING_TIME_WINDOW",
                        day_number=day_num,
                        order_index=item_b.order_index,
                        conflicting_order_index=item_a.order_index,
                        activity=item_b.activity,
                        place_name=item_b.place_name,
                        start_time=item_b.start_time,
                        end_time=item_b.end_time,
                        message=(
                            f"Ngày {day_num}: Mục #{item_a.order_index} \"{item_a.activity}\" "
                            f"({item_a.start_time} - {item_a.end_time}) và mục #{item_b.order_index} "
                            f"\"{item_b.activity}\" ({item_b.start_time} - {item_b.end_time}) "
                            f"bị chồng giờ ({ov_str})."
                        ),
                    )
                )

    return summary_violations


def _get_max_planner_attempts() -> int:
    return 1 if os.getenv("PYTEST_CURRENT_TEST") else 3


def _sleep_for_retry(seconds: float) -> float:
    t0 = time.perf_counter()
    time.sleep(seconds)
    return round((time.perf_counter() - t0) * 1000, 2)


@router.post("", response_model=PlanResponse)
async def create_plan(
    req: Union[TripContextRequest, PlanRequest],
    http_request: Request,
    http_response: Response,
):
    """Tạo lịch trình du lịch AI chi tiết theo từng ngày từ TripContext."""
    t_fastapi_start = time.perf_counter()
    header_req_id = (http_request.headers.get("X-Request-Id") or "").strip()
    body_req_id = (getattr(req, "request_id", None) or "").strip()
    request_id = header_req_id or body_req_id or str(uuid.uuid4())
    http_response.headers["X-Request-Id"] = request_id

    if isinstance(req, TripContextRequest):
        destination = req.destination
        days = req.days
        start_date = req.start_date
        end_date = req.end_date
        budget = req.budget
        currency = req.currency or "VND"
        travel_style = req.travel_style
        interests = req.interests
        notes = req.notes
        trip_id = req.trip_id
    else:
        destination = req.destination
        days = req.days
        start_date = req.start_date
        end_date = None
        budget = int(req.budget) if req.budget is not None else None
        currency = "VND"
        travel_style = req.style
        interests = req.interests
        notes = None
        trip_id = None

    if days < 1 or days > 14:
        raise HTTPException(status_code=400, detail="Số ngày chuyến đi phải từ 1 đến 14")

    grounding_ctx: Optional[str] = None
    rag_retrieval_ms = 0.0
    if notes and _client is not None and "PYTEST_CURRENT_TEST" not in os.environ:
        t_rag_start = time.perf_counter()
        try:
            raw_grounding = await chat_router.retrieve_grounding(f"{destination} {notes}")
            norm_grounding = chat_router._normalize_retrieval_result(raw_grounding)
            if norm_grounding.status == "ok" and norm_grounding.context:
                grounding_ctx = norm_grounding.context
        except Exception:
            grounding_ctx = None
        finally:
            rag_retrieval_ms = round((time.perf_counter() - t_rag_start) * 1000, 2)

    prompt = build_planner_prompt(
        destination=destination,
        days=days,
        start_date=start_date,
        end_date=end_date,
        budget=budget,
        currency=currency,
        travel_style=travel_style,
        interests=interests,
        notes=notes,
        grounding_context=grounding_ctx,
    )

    model_attempts: list[PlannerModelAttemptTelemetry] = []
    retry_count = 0
    retry_wait_ms = 0.0

    try:
        raw_text = ""
        if _client:
            planner_thinking_cfg = (
                types.ThinkingConfig(thinking_level="MINIMAL")
                if str(settings.PLANNER_MODEL or "").startswith("gemini-3")
                else None
            )
            max_attempts = _get_max_planner_attempts()
            response = None
            for _attempt in range(max_attempts):
                started_offset_ms = round((time.perf_counter() - t_fastapi_start) * 1000, 2)
                t_call_start = time.perf_counter()
                try:
                    response = _client.models.generate_content(
                        model=settings.PLANNER_MODEL,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.7,
                            max_output_tokens=settings.PLANNER_MAX_OUTPUT_TOKENS,
                            response_mime_type="application/json",
                            thinking_config=planner_thinking_cfg,
                            http_options=types.HttpOptions(timeout=settings.PLANNER_TIMEOUT_MS),
                        ),
                    )
                    call_dur_ms = round((time.perf_counter() - t_call_start) * 1000, 2)
                    model_attempts.append(
                        PlannerModelAttemptTelemetry(
                            attempt=_attempt + 1,
                            started_offset_ms=started_offset_ms,
                            duration_ms=call_dur_ms,
                            status="ok",
                        )
                    )
                    break
                except Exception as call_exc:
                    call_dur_ms = round((time.perf_counter() - t_call_start) * 1000, 2)
                    up_msg = str(call_exc).upper()
                    is_503 = "503" in up_msg or "UNAVAILABLE" in up_msg
                    model_attempts.append(
                        PlannerModelAttemptTelemetry(
                            attempt=_attempt + 1,
                            started_offset_ms=started_offset_ms,
                            duration_ms=call_dur_ms,
                            status="error_503" if is_503 else "error",
                            error_code="PROVIDER_503_UNAVAILABLE" if is_503 else type(call_exc).__name__,
                        )
                    )
                    if is_503 and (_attempt + 1) < max_attempts:
                        backoff_sec = 2.0 * (_attempt + 1)
                        logger.warning(
                            "[C4_PLANNER_RETRY] request_id=%s model=%s attempt=%d/%d duration_ms=%.2f backoff_s=%.1f",
                            request_id,
                            settings.PLANNER_MODEL,
                            _attempt + 1,
                            max_attempts,
                            call_dur_ms,
                            backoff_sec,
                        )
                        slept_ms = _sleep_for_retry(backoff_sec)
                        retry_count += 1
                        retry_wait_ms = round(retry_wait_ms + slept_ms, 2)
                        continue
                    raise
            raw_text = response.text or ""
            finish = None
            try:
                finish = response.candidates[0].finish_reason
            except Exception:
                finish = None
            if finish is not None and "MAX_TOKENS" in str(finish):
                logger.error("Planner output truncated (MAX_TOKENS) model=%s", settings.PLANNER_MODEL)
                raise HTTPException(
                    status_code=502,
                    detail="AI tra ve ket qua khong day du. Vui long thu lai.",
                )
        else:
            # Fallback mock for testing when no Gemini key is present
            raw_text = json.dumps({
                "destination": destination,
                "total_days": days,
                "overview": f"Hành trình khám phá {destination} {days} ngày tuyệt vời.",
                "best_time_to_visit": "Quanh năm",
                "general_tips": ["Mang theo trang phục thoải mái"],
                "days": [
                    {
                        "day_number": i + 1,
                        "title": f"Ngày {i + 1}: Trải nghiệm {destination}",
                        "items": [
                            {
                                "order_index": 1,
                                "start_time": "08:30",
                                "end_time": "11:00",
                                "activity": f"Tham quan điểm nổi bật {destination}",
                                "place_name": destination,
                                "notes": "Điểm tham quan tiêu biểu",
                                "estimated_cost": 50000,
                                "transport_mode": "taxi",
                            }
                        ],
                    }
                    for i in range(days)
                ],
            })

        t_post_ai_start = time.perf_counter()
        cleaned_json = _clean_json_response(raw_text)
        data = json.loads(cleaned_json)

        raw_days = data.get("days", data.get("itinerary", []))
        itinerary_days: list[ItineraryDay] = []
        known_cost_total = 0
        total_unknown_cost_items = 0
        total_items_count = 0
        all_schedule_violations: list[ScheduleViolation] = []

        for idx, day_data in enumerate(raw_days):
            day_num = int(day_data.get("day_number", day_data.get("day", idx + 1)))
            day_title = str(day_data.get("title", f"Ngày {day_num}"))
            day_date = _normalize_optional_str(day_data.get("date"))

            items: list[ItineraryItem] = []
            day_cost = 0
            day_unknown_count = 0

            raw_items = day_data.get("items", day_data.get("activities", []))
            for item_idx, itm in enumerate(raw_items):
                if not isinstance(itm, dict):
                    continue
                total_items_count += 1
                item_cost, item_cost_status = _parse_optional_cost(itm)
                if item_cost is not None:
                    day_cost += item_cost
                else:
                    day_unknown_count += 1

                raw_order = itm.get("order_index")
                order_idx = int(raw_order) if isinstance(raw_order, (int, float)) and not isinstance(raw_order, bool) else (item_idx + 1)

                items.append(
                    ItineraryItem(
                        order_index=order_idx,
                        start_time=_normalize_optional_str(itm.get("start_time", itm.get("time"))),
                        end_time=_normalize_optional_str(itm.get("end_time")),
                        activity=str(itm.get("activity", itm.get("name", "")) or f"Hoạt động {item_idx + 1}"),
                        place_name=_normalize_optional_str(itm.get("place_name", itm.get("address"))),
                        notes=_normalize_optional_str(itm.get("notes", itm.get("tip"))),
                        estimated_cost=item_cost,
                        cost_status=item_cost_status,
                        transport_mode=_normalize_optional_str(itm.get("transport_mode", itm.get("type"))),
                    )
                )

            day_violations = _detect_day_schedule_violations(day_num, items)
            all_schedule_violations.extend(day_violations)

            known_cost_total += day_cost
            total_unknown_cost_items += day_unknown_count
            itinerary_days.append(
                ItineraryDay(
                    day_number=day_num,
                    date=day_date,
                    title=day_title,
                    items=items,
                    day_cost=day_cost,
                    unknown_cost_item_count=day_unknown_count,
                )
            )

        if total_unknown_cost_items == 0:
            overall_cost_status = "COMPLETE"
        elif total_unknown_cost_items == total_items_count:
            overall_cost_status = "ALL_UNKNOWN"
        else:
            overall_cost_status = "PARTIAL_UNKNOWN"

        has_positive_budget = budget is not None and budget > 0
        is_over = bool(has_positive_budget and known_cost_total > budget)
        has_sufficient_basis = bool(has_positive_budget and total_unknown_cost_items == 0)

        variance: Optional[int]
        if has_positive_budget:
            if is_over or has_sufficient_basis:
                variance = budget - known_cost_total
            else:
                # Never fabricate surplus when one or more items have unknown prices.
                variance = None
        else:
            variance = 0 if total_unknown_cost_items == 0 else None

        budget_analysis = BudgetAnalysis(
            total_budget=budget,
            estimated_cost=known_cost_total,
            known_cost_total=known_cost_total,
            unknown_cost_item_count=total_unknown_cost_items,
            cost_status=overall_cost_status,
            has_sufficient_budget_basis=has_sufficient_basis,
            currency=currency,
            is_over_budget=is_over,
            variance=variance,
        )

        post_ai_schedule_validation_ms = round(
            (time.perf_counter() - t_post_ai_start) * 1000, 2
        )
        fastapi_total_ms = round((time.perf_counter() - t_fastapi_start) * 1000, 2)
        model_total_ms = round(sum(a.duration_ms for a in model_attempts), 2)
        timing_telemetry = PlannerTimingTelemetry(
            request_id=request_id,
            fastapi_total_ms=fastapi_total_ms,
            rag_retrieval_ms=rag_retrieval_ms,
            model_attempts=model_attempts,
            model_total_ms=model_total_ms,
            retry_count=retry_count,
            retry_wait_ms=retry_wait_ms,
            post_ai_schedule_validation_ms=post_ai_schedule_validation_ms,
        )
        logger.info(
            "[C4_PLANNER_TIMING] %s",
            json.dumps(timing_telemetry.model_dump(), ensure_ascii=False),
        )

        return PlanResponse(
            plan_id=trip_id or str(uuid.uuid4()),
            destination=destination,
            total_days=len(itinerary_days),
            overview=str(data.get("overview", f"Lịch trình khám phá {destination}")),
            best_time_to_visit=str(data.get("best_time_to_visit", "Thời điểm lý tưởng trong năm")),
            general_tips=list(data.get("general_tips", [])),
            budget_analysis=budget_analysis,
            schedule_violations=all_schedule_violations,
            has_schedule_violations=len(all_schedule_violations) > 0,
            timing_telemetry=timing_telemetry,
            days=itinerary_days,
        )

    except json.JSONDecodeError as e:
        logger.error("Planner returned invalid JSON: %s", e)
        raise HTTPException(
            status_code=502,
            detail="AI trả về định dạng không hợp lệ. Vui lòng thử lại.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Planner provider/processing failure: %s", type(e).__name__)
        raise HTTPException(
            status_code=502,
            detail="Nhà cung cấp AI không phản hồi. Vui lòng thử lại sau.",
        )
