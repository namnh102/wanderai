"""Versioned scientific benchmark prompt and deterministic REC-A-CORE-V2 catalog builder (W06-INSTRUMENT-01A / 01D).

Does NOT mutate TRAVEL_PLANNER_V1 in apps/ai-service/app/prompts/planner_prompt.py.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.schemas.planner_benchmark import (
    CANONICAL_BENCHMARK_INTERESTS,
    EXPECTED_PRIMARY_CATALOG_COUNTS,
    PRIMARY_BENCHMARK_DESTINATIONS,
    BenchmarkCatalogPOI,
    BenchmarkScenarioInput,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CATALOG_PATH = REPO_ROOT / "data" / "curated" / "gomate_places_freeze_v2.json"

BENCHMARK_PROMPT_VERSION_01A = "TRAVEL_PLANNER_BENCHMARK_V1"
BENCHMARK_PROMPT_VERSION = "TRAVEL_PLANNER_BENCHMARK_V2"

CANONICAL_INTEREST_LABELS_VI: Dict[str, str] = {
    "food_cuisine": "Ẩm thực & Đặc sản địa phương (food_cuisine)",
    "culture_history": "Văn hóa & Di tích lịch sử (culture_history)",
    "nature_outdoor": "Thiên nhiên & Hoạt động ngoài trời (nature_outdoor)",
    "coffee_culture": "Văn hóa cà phê & Không gian thư giãn (coffee_culture)",
    "beach_island": "Biển & Đảo (beach_island)",
    "shopping_local": "Mua sắm & Chợ truyền thống (shopping_local)",
    "nightlife_entertainment": "Giải trí & Hoạt động về đêm (nightlife_entertainment)",
}

TRAVEL_PLANNER_BENCHMARK_V1 = """Bạn là hệ thống lập lịch trình du lịch của GoMate đang chạy ở chế độ kiểm định khoa học (BENCHMARK MODE — {prompt_version}).
Nhiệm vụ của bạn là tạo lịch trình chi tiết từng ngày bằng JSON hợp lệ dựa trên ngữ cảnh kịch bản và DANH MỤC ĐỊA ĐIỂM ĐƯỢC PHÉP (REC-A-CORE-V2 CATALOG) dưới đây.

THÔNG TIN KỊCH BẢN (SCENARIO CONTEXT):
- Mã kịch bản (scenario_id): {scenario_id}
- Điểm đến (destination): {destination} (destination_slug: {destination_slug})
- Số ngày: {days} ngày (từ {start_date} đến {end_date})
- Tổng ngân sách trần (budget ceiling): {budget_formatted} {currency}
- Phong cách du lịch (travel_style): {travel_style}
- Sở thích chuẩn hóa (canonical_interests): {canonical_interests_json} ({canonical_interests_vi})
- Chính sách lặp lại địa điểm (allow_revisit_place_ids): {allow_revisit_policy}
{additional_notes}

QUY TẮC BẮT BUỘC (SCIENTIFIC BENCHMARK RULES):
A. PHÂN LOẠI HOẠT ĐỘNG (activity_kind) — CHỈ ĐƯỢC DÙNG 1 TRONG 2 GIÁ TRỊ:
   1. "POI_VISIT":
      - Dùng cho mọi hoạt động tham quan, ăn uống, cà phê, mua sắm, vui chơi, nghỉ ngơi tại một địa điểm vật lý cụ thể.
      - BẮT BUỘC có:
        "activity_kind": "POI_VISIT"
        "place_id": "<sao chép CHÍNH XÁC từng ký tự place_id từ DANH MỤC ĐƯỢC PHÉP bên dưới>"
        "place_name": "<tên name tương ứng của địa điểm đó trong danh mục>"
      - TUYỆT ĐỐI KHÔNG tự bịa ra place_id hoặc địa điểm nằm ngoài danh mục được cung cấp.
   2. "TRANSIT_ONLY":
      - CHỈ dùng cho hoạt động di chuyển thuần túy giữa các điểm tham quan.
      - BẮT BUỘC có:
        "activity_kind": "TRANSIT_ONLY"
        "place_id": null
        "place_name": null
      - TUYỆT ĐỐI KHÔNG dùng "TRANSIT_ONLY" cho điểm tham quan, nhà hàng, quán cà phê, bảo tàng, công viên, hay bất kỳ địa điểm có tên cụ thể nào.

B. KHÔNG LẶP LẠI ĐỊA ĐIỂM (NO DUPLICATE POI):
   - Không được lặp lại cùng một "place_id" quá một lần trong toàn bộ lịch trình (trừ khi allow_revisit_place_ids = true).

C. THỜI GIAN & CẤU TRÚC NGÀY (SCHEDULE & DAY STRUCTURE):
   - Mảng "days" phải có đúng {days} ngày (day_number từ 1 đến {days}).
   - Mỗi hoạt động phải có "start_time" và "end_time" đúng định dạng 24 giờ "HH:MM" (ví dụ: "08:00", "10:30"), thỏa mãn start_time < end_time.
   - Trong cùng một ngày, các khung giờ [start_time, end_time) không được chồng chéo nhau.

D. NGÂN SÁCH ƯỚC LƯỢNG (ESTIMATED BUDGET):
   - Mỗi hoạt động có "estimated_cost" (số nguyên >= 0, đơn vị {currency}).
   - Tổng "estimated_cost" của toàn bộ các hoạt động trong lịch trình phải <= tổng ngân sách trần ({budget_formatted} {currency}).

E. ĐỊNH DẠNG ĐẦU RA (JSON ONLY):
   - Chỉ trả về DUY NHẤT một đối tượng JSON hợp lệ (không kèm markdown ```json hay văn bản giải thích ngoài JSON):
{{
  "destination": "{destination}",
  "total_days": {days},
  "overview": "Mô tả tổng quan ngắn gọn về lịch trình.",
  "best_time_to_visit": "Thông tin thời điểm phù hợp.",
  "general_tips": [
    "Lưu ý thực tế 1",
    "Lưu ý thực tế 2"
  ],
  "days": [
    {{
      "day_number": 1,
      "date": "{start_date}",
      "title": "Chủ đề ngày 1",
      "items": [
        {{
          "order_index": 1,
          "start_time": "08:00",
          "end_time": "09:30",
          "activity_kind": "POI_VISIT",
          "activity": "Tham quan và trải nghiệm tại địa điểm",
          "place_name": "<name từ danh mục>",
          "place_id": "<place_id chính xác từ danh mục>",
          "notes": "Ghi chú ngắn gọn",
          "estimated_cost": 50000,
          "transport_mode": "motorbike"
        }},
        {{
          "order_index": 2,
          "start_time": "09:30",
          "end_time": "10:00",
          "activity_kind": "TRANSIT_ONLY",
          "activity": "Di chuyển sang địa điểm tiếp theo",
          "place_name": null,
          "place_id": null,
          "notes": "Di chuyển nội đô",
          "estimated_cost": 30000,
          "transport_mode": "taxi"
        }}
      ]
    }}
  ]
}}

DANH MỤC ĐỊA ĐIỂM ĐƯỢC PHÉP CHO {destination_slug} (ALLOWED REC-A-CORE-V2 POI CATALOG — {catalog_count} POIs, SORTED BY place_id):
{catalog_json}
"""

TRAVEL_PLANNER_BENCHMARK_V2 = """Bạn là hệ thống lập lịch trình du lịch của GoMate đang chạy ở chế độ kiểm định khoa học (BENCHMARK MODE — {prompt_version}).
Nhiệm vụ của bạn là tạo lịch trình chi tiết từng ngày bằng JSON hợp lệ dựa trên ngữ cảnh kịch bản và DANH MỤC ĐỊA ĐIỂM ĐƯỢC PHÉP (REC-A-CORE-V2 CATALOG) dưới đây.

THÔNG TIN KỊCH BẢN (SCENARIO CONTEXT):
- Mã kịch bản (scenario_id): {scenario_id}
- Điểm đến (destination): {destination} (destination_slug: {destination_slug})
- Số ngày: {days} ngày (từ {start_date} đến {end_date})
- Tổng ngân sách trần (budget ceiling): {budget_formatted} {currency}
- Phong cách du lịch (travel_style): {travel_style}
- Sở thích chuẩn hóa (canonical_interests): {canonical_interests_json} ({canonical_interests_vi})
- Chính sách lặp lại địa điểm (allow_revisit_place_ids): {allow_revisit_policy}
{additional_notes}

QUY TẮC BẮT BUỘC (SCIENTIFIC BENCHMARK RULES):
A. PHÂN LOẠI HOẠT ĐỘNG (activity_kind) — CHỈ ĐƯỢC DÙNG 1 TRONG 2 GIÁ TRỊ:
   1. "POI_VISIT":
      - Dùng cho mọi hoạt động tham quan, ăn uống, cà phê, mua sắm, vui chơi, nghỉ ngơi tại một địa điểm vật lý cụ thể.
      - BẮT BUỘC có:
        "activity_kind": "POI_VISIT"
        "place_id": "<sao chép CHÍNH XÁC từng ký tự place_id từ DANH MỤC ĐƯỢC PHÉP bên dưới>"
        "place_name": "<tên name tương ứng của địa điểm đó trong danh mục>"
      - TUYỆT ĐỐI KHÔNG tự bịa ra place_id hoặc địa điểm nằm ngoài danh mục được cung cấp.
   2. "TRANSIT_ONLY":
      - CHỈ dùng cho hoạt động di chuyển thuần túy giữa các điểm tham quan.
      - BẮT BUỘC có:
        "activity_kind": "TRANSIT_ONLY"
        "place_id": null
        "place_name": null
      - TUYỆT ĐỐI KHÔNG dùng "TRANSIT_ONLY" cho điểm tham quan, nhà hàng, quán cà phê, bảo tàng, công viên, hay bất kỳ địa điểm có tên cụ thể nào.

B. KHÔNG LẶP LẠI ĐỊA ĐIỂM (NO DUPLICATE POI):
   - Không được lặp lại cùng một "place_id" quá một lần trong toàn bộ lịch trình (trừ khi allow_revisit_place_ids = true).

C. THỜI GIAN & CẤU TRÚC NGÀY (SCHEDULE & DAY STRUCTURE):
   - Mảng "days" phải có đúng {days} ngày (day_number từ 1 đến {days}).
   - YÊU CẦU TỐI THIỂU MỖI NGÀY (min_poi_visits_per_day = 2): Mỗi ngày trong lịch trình BẮT BUỘC có ít nhất 2 hoạt động có "activity_kind": "POI_VISIT".
   - CHỈ các hoạt động có "activity_kind" == "POI_VISIT" mới được tính vào số lượng tối thiểu 2 địa điểm/ngày này; "TRANSIT_ONLY" KHÔNG được tính vào số lượng tối thiểu này.
   - Một ngày chỉ có 1 "POI_VISIT" kèm theo bất kỳ số lượng "TRANSIT_ONLY" nào đều bị tính là VI PHẠM cấu trúc ngày (non-compliant). Quy tắc tối thiểu 2 "POI_VISIT"/ngày này áp dụng ĐỘC LẬP cho TỪNG ngày trong lịch trình.
   - Mỗi hoạt động phải có "start_time" và "end_time" đúng định dạng 24 giờ "HH:MM" (ví dụ: "08:00", "10:30"), thỏa mãn start_time < end_time.
   - Trong cùng một ngày, các khung giờ [start_time, end_time) không được chồng chéo nhau.

D. NGÂN SÁCH ƯỚC LƯỢNG (ESTIMATED BUDGET):
   - Mỗi hoạt động có "estimated_cost" (số nguyên >= 0, đơn vị {currency}).
   - Tổng "estimated_cost" của toàn bộ các hoạt động trong lịch trình phải <= tổng ngân sách trần ({budget_formatted} {currency}).

E. ĐỊNH DẠNG ĐẦU RA (JSON ONLY):
   - Chỉ trả về DUY NHẤT một đối tượng JSON hợp lệ (không kèm markdown ```json hay văn bản giải thích ngoài JSON):
{{
  "destination": "{destination}",
  "total_days": {days},
  "overview": "Mô tả tổng quan ngắn gọn về lịch trình.",
  "best_time_to_visit": "Thông tin thời điểm phù hợp.",
  "general_tips": [
    "Lưu ý thực tế 1",
    "Lưu ý thực tế 2"
  ],
  "days": [
    {{
      "day_number": 1,
      "date": "{start_date}",
      "title": "Chủ đề ngày 1",
      "items": [
        {{
          "order_index": 1,
          "start_time": "08:00",
          "end_time": "09:30",
          "activity_kind": "POI_VISIT",
          "activity": "Tham quan và trải nghiệm tại địa điểm thứ nhất",
          "place_name": "<name địa điểm 1 từ danh mục>",
          "place_id": "<place_id địa điểm 1 chính xác từ danh mục>",
          "notes": "Ghi chú ngắn gọn cho địa điểm 1",
          "estimated_cost": 50000,
          "transport_mode": "motorbike"
        }},
        {{
          "order_index": 2,
          "start_time": "09:30",
          "end_time": "10:00",
          "activity_kind": "TRANSIT_ONLY",
          "activity": "Di chuyển sang địa điểm tiếp theo",
          "place_name": null,
          "place_id": null,
          "notes": "Di chuyển nội đô",
          "estimated_cost": 30000,
          "transport_mode": "taxi"
        }},
        {{
          "order_index": 3,
          "start_time": "10:00",
          "end_time": "11:30",
          "activity_kind": "POI_VISIT",
          "activity": "Tham quan và trải nghiệm tại địa điểm thứ hai",
          "place_name": "<name địa điểm 2 từ danh mục>",
          "place_id": "<place_id địa điểm 2 chính xác từ danh mục>",
          "notes": "Ghi chú ngắn gọn cho địa điểm 2",
          "estimated_cost": 60000,
          "transport_mode": "taxi"
        }}
      ]
    }}
  ]
}}

DANH MỤC ĐỊA ĐIỂM ĐƯỢC PHÉP CHO {destination_slug} (ALLOWED REC-A-CORE-V2 POI CATALOG — {catalog_count} POIs, SORTED BY place_id):
{catalog_json}
"""


def build_destination_catalog_context(
    destination_slug: str,
    catalog_path: Optional[Path] = None,
) -> List[BenchmarkCatalogPOI]:
    """Deterministically build the REC-A-CORE-V2 catalog context for a primary destination.

    Rejects unknown or non-primary destinations.
    Orders deterministically by canonical place_id ascending.
    """
    slug = (destination_slug or "").strip()
    if slug not in PRIMARY_BENCHMARK_DESTINATIONS:
        raise ValueError(
            f"Destination '{destination_slug}' is not an allowed primary benchmark destination. "
            f"Allowed: {sorted(PRIMARY_BENCHMARK_DESTINATIONS.keys())}"
        )

    target_path = catalog_path or DEFAULT_CATALOG_PATH
    if not target_path.exists():
        raise FileNotFoundError(f"Frozen POI catalog not found at {target_path}")

    raw_places: List[Dict[str, Any]] = json.loads(target_path.read_text(encoding="utf-8"))
    filtered = [
        p
        for p in raw_places
        if p.get("is_rec_a_core_v2") is True and p.get("destination_slug") == slug
    ]

    # Deterministic sort by canonical place_id ascending
    filtered_sorted = sorted(filtered, key=lambda p: str(p["place_id"]))

    expected_count = EXPECTED_PRIMARY_CATALOG_COUNTS[slug]
    if len(filtered_sorted) != expected_count:
        raise ValueError(
            f"Catalog integrity mismatch for '{slug}': expected {expected_count} REC-A-CORE-V2 POIs, "
            f"found {len(filtered_sorted)}."
        )

    return [
        BenchmarkCatalogPOI(
            place_id=str(p["place_id"]),
            name=str(p["name"]),
            category=str(p["category"]),
            destination_slug=str(p["destination_slug"]),
            lat=float(p["latitude"]) if p.get("latitude") is not None else None,
            lng=float(p["longitude"]) if p.get("longitude") is not None else None,
            opening_hours=str(p["opening_hours"]) if p.get("opening_hours") is not None else None,
        )
        for p in filtered_sorted
    ]


def validate_canonical_interests_list(interests: List[str]) -> List[str]:
    """Validate that all interest strings belong to the canonical 7-interest taxonomy."""
    if not interests:
        raise ValueError("Interests list must not be empty.")
    invalid = [i for i in interests if i not in CANONICAL_BENCHMARK_INTERESTS]
    if invalid:
        raise ValueError(
            f"Non-canonical interest keys rejected: {invalid}. "
            f"Allowed canonical taxonomy: {list(CANONICAL_BENCHMARK_INTERESTS)}"
        )
    return list(interests)


def build_benchmark_planner_prompt(
    scenario: BenchmarkScenarioInput,
    catalog_pois: Optional[List[BenchmarkCatalogPOI]] = None,
    catalog_path: Optional[Path] = None,
) -> str:
    """Build the versioned TRAVEL_PLANNER_BENCHMARK_V2 prompt with deterministic catalog context."""
    validate_canonical_interests_list(scenario.interests)

    pois = (
        catalog_pois
        if catalog_pois is not None
        else build_destination_catalog_context(scenario.destination_slug, catalog_path=catalog_path)
    )
    if not pois:
        raise ValueError(f"Empty catalog context for destination_slug={scenario.destination_slug!r}")

    catalog_serializable = [poi.model_dump() for poi in pois]
    catalog_json = json.dumps(catalog_serializable, ensure_ascii=False, indent=2)

    interests_vi = ", ".join(CANONICAL_INTEREST_LABELS_VI[i] for i in scenario.interests)
    interests_json = json.dumps(scenario.interests, ensure_ascii=False)
    budget_formatted = f"{scenario.budget:,.0f}" if scenario.budget is not None else "Không giới hạn"
    allow_revisit_policy = (
        "true (cho phép lặp lại place_id nếu cần)"
        if scenario.allow_revisit_place_ids
        else "false (TUYỆT ĐỐI KHÔNG lặp lại cùng một place_id trong lịch trình)"
    )
    additional_notes = f"- Ghi chú kịch bản (notes): {scenario.notes}" if scenario.notes else ""

    return TRAVEL_PLANNER_BENCHMARK_V2.format(
        prompt_version=BENCHMARK_PROMPT_VERSION,
        scenario_id=scenario.scenario_id,
        destination=scenario.destination,
        destination_slug=scenario.destination_slug,
        days=scenario.days,
        start_date=scenario.start_date,
        end_date=scenario.end_date,
        budget_formatted=budget_formatted,
        currency=scenario.currency,
        travel_style=scenario.travel_style,
        canonical_interests_json=interests_json,
        canonical_interests_vi=interests_vi,
        allow_revisit_policy=allow_revisit_policy,
        additional_notes=additional_notes,
        catalog_count=len(pois),
        catalog_json=catalog_json,
    )
