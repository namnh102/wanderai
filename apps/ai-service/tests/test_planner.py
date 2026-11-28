"""Tests for AI Trip Planner router & schemas."""
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

MOCK_LLM_OUTPUT = {
    "destination": "Đà Nẵng",
    "total_days": 2,
    "overview": "Hành trình 2 ngày tại Đà Nẵng đầy sôi động và thư thái.",
    "best_time_to_visit": "Tháng 4 đến tháng 8",
    "general_tips": [
        "Thuê xe máy để dễ đi lại",
        "Mang kem chống nắng"
    ],
    "days": [
        {
            "day_number": 1,
            "title": "Ngày 1: Biển Mỹ Khê & Sơn Trà",
            "items": [
                {
                    "order_index": 1,
                    "start_time": "08:00",
                    "end_time": "09:30",
                    "activity": "Ăn sáng mì Quảng ếch",
                    "place_name": "Mì Quảng Bếp Trang",
                    "notes": "Món ăn đặc sản",
                    "estimated_cost": 50000,
                    "transport_mode": "motorbike"
                },
                {
                    "order_index": 2,
                    "start_time": "10:00",
                    "end_time": "12:00",
                    "activity": "Viếng Chùa Linh Ứng",
                    "place_name": "Bán đảo Sơn Trà",
                    "notes": "Vào cửa tự do",
                    "estimated_cost": 0,
                    "transport_mode": "motorbike"
                }
            ]
        },
        {
            "day_number": 2,
            "title": "Ngày 2: Ngũ Hành Sơn & Phố cổ Hội An",
            "items": [
                {
                    "order_index": 1,
                    "start_time": "09:00",
                    "end_time": "11:30",
                    "activity": "Khám phá danh thắng Ngũ Hành Sơn",
                    "place_name": "Ngũ Hành Sơn",
                    "notes": "Vé tham quan 40k",
                    "estimated_cost": 40000,
                    "transport_mode": "taxi"
                }
            ]
        }
    ]
}


def test_planner_invalid_day_range():
    """Validates that days < 1 or days > 14 return 400 status."""
    res_zero = client.post("/planner", json={"destination": "Hà Nội", "days": 0})
    assert res_zero.status_code == 400

    res_too_many = client.post("/planner", json={"destination": "Hà Nội", "days": 15})
    assert res_too_many.status_code == 400


def test_planner_with_trip_context():
    """Tests generating a plan with full TripContext payload."""
    mock_response = MagicMock()
    mock_response.text = f"```json\n{json.dumps(MOCK_LLM_OUTPUT)}\n```"

    with patch("app.routers.planner._client") as mock_client:
        mock_client.models.generate_content.return_value = mock_response

        payload = {
            "trip_id": "test-trip-uuid-123",
            "destination": "Đà Nẵng",
            "days": 2,
            "start_date": "2026-10-15",
            "end_date": "2026-10-16",
            "budget": 2000000,
            "currency": "VND",
            "travel_style": "budget",
            "interests": ["beach", "food"],
            "notes": "Muốn ăn hải sản tươi ngon",
        }
        res = client.post("/planner", json=payload)
        assert res.status_code == 200
        data = res.json()

        assert data["plan_id"] == "test-trip-uuid-123"
        assert data["destination"] == "Đà Nẵng"
        assert data["total_days"] == 2
        assert len(data["days"]) == 2

        # Check day 1 items and deterministic arithmetic
        day1 = data["days"][0]
        assert day1["day_number"] == 1
        assert day1["day_cost"] == 50000  # 50,000 + 0
        assert len(day1["items"]) == 2

        # Check day 2
        day2 = data["days"][1]
        assert day2["day_number"] == 2
        assert day2["day_cost"] == 40000

        # Check budget analysis: 50,000 + 40,000 = 90,000
        analysis = data["budget_analysis"]
        assert analysis["total_budget"] == 2000000
        assert analysis["estimated_cost"] == 90000
        assert analysis["is_over_budget"] is False
        assert analysis["variance"] == 1910000


def test_planner_over_budget_detection():
    """Tests that budget calculation detects when itinerary exceeds user budget."""
    mock_response = MagicMock()
    mock_response.text = json.dumps(MOCK_LLM_OUTPUT)

    with patch("app.routers.planner._client") as mock_client:
        mock_client.models.generate_content.return_value = mock_response

        # Total estimated cost in mock is 90,000. Set budget to 50,000.
        payload = {
            "destination": "Đà Nẵng",
            "days": 2,
            "budget": 50000,
            "currency": "VND",
        }
        res = client.post("/planner", json=payload)
        assert res.status_code == 200
        data = res.json()

        analysis = data["budget_analysis"]
        assert analysis["estimated_cost"] == 90000
        assert analysis["is_over_budget"] is True
        assert analysis["variance"] == -40000


def test_planner_backward_compatibility():
    """Tests that legacy PlanRequest shape still functions."""
    mock_response = MagicMock()
    mock_response.text = json.dumps(MOCK_LLM_OUTPUT)

    with patch("app.routers.planner._client") as mock_client:
        mock_client.models.generate_content.return_value = mock_response

        payload = {
            "destination": "Đà Nẵng",
            "days": 2,
            "budget": 1000000,
            "style": "adventure",
            "interests": ["beach"],
        }
        res = client.post("/planner", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["destination"] == "Đà Nẵng"
        assert len(data["days"]) == 2


def test_evaluation_scenario_runner():
    """Validates that evaluation scenarios can be evaluated against mock itinerary."""
    import sys
    from pathlib import Path
    data_dir = Path(__file__).parent.parent.parent.parent / "data" / "evaluation" / "planner"
    sys.path.insert(0, str(data_dir))
    from evaluate_planner import evaluate_itinerary

    scenario_file = data_dir / "da_nang_4d.json"
    with open(scenario_file, "r", encoding="utf-8") as f:
        scenario = json.load(f)

    # Evaluate against mock response shaped data
    mock_resp = {
        "destination": "Đà Nẵng",
        "budget_analysis": {"estimated_cost": 90000},
        "days": [
            {
                "day_number": 1,
                "day_cost": 50000,
                "items": [
                    {"activity": "Tắm biển Mỹ Khê", "place_name": "Biển Mỹ Khê", "estimated_cost": 50000},
                    {"activity": "Dạo Cầu Rồng", "place_name": "Cầu Rồng", "estimated_cost": 0},
                    {"activity": "Thưởng thức mì Quảng", "place_name": "Hội An", "estimated_cost": 0},
                ]
            },
            {
                "day_number": 2,
                "day_cost": 40000,
                "items": [
                    {"activity": "Khám phá phố cổ Hội An", "place_name": "Hội An", "estimated_cost": 40000},
                    {"activity": "Nghỉ ngơi", "place_name": "Khách sạn", "estimated_cost": 0},
                    {"activity": "Ăn tối", "place_name": "Đà Nẵng", "estimated_cost": 0},
                ]
            },
            {
                "day_number": 3,
                "day_cost": 0,
                "items": [
                    {"activity": "Tham quan", "place_name": "Đà Nẵng", "estimated_cost": 0},
                    {"activity": "Nghỉ trưa", "place_name": "Đà Nẵng", "estimated_cost": 0},
                    {"activity": "Tắm biển", "place_name": "Mỹ Khê", "estimated_cost": 0},
                ]
            },
            {
                "day_number": 4,
                "day_cost": 0,
                "items": [
                    {"activity": "Mua sắm chợ Hàn", "place_name": "Chợ Hàn", "estimated_cost": 0},
                    {"activity": "Ăn trưa", "place_name": "Đà Nẵng", "estimated_cost": 0},
                    {"activity": "Tiễn sân bay", "place_name": "Sân bay", "estimated_cost": 0},
                ]
            }
        ]
    }

    eval_result = evaluate_itinerary(mock_resp, scenario)
    assert eval_result["success"] is True
    assert eval_result["calculated_total"] == 90000


def test_planner_null_and_missing_cost_no_502_and_suppresses_surplus():
    """Case C: null/missing estimated_cost returns 200 (not 502), preserves None, and suppresses surplus."""
    mock_output = {
        "destination": "Hạ Long",
        "total_days": 1,
        "overview": "Lịch trình có mục đã biết giá và mục thiếu giá.",
        "days": [
            {
                "day_number": 1,
                "date": "2026-11-23",
                "title": "Ngày 1: Hạ Long",
                "items": [
                    {
                        "order_index": 1,
                        "start_time": "08:30",
                        "end_time": "10:00",
                        "activity": "Cà phê tại Cafe ban mê",
                        "place_name": "Cafe ban mê",
                        "estimated_cost": None,
                    },
                    {
                        "order_index": 2,
                        "start_time": "10:30",
                        "end_time": "12:00",
                        "activity": "Tham quan Bảo tàng Quảng Ninh",
                        "place_name": "Bảo tàng Quảng Ninh",
                        # estimated_cost omitted
                    },
                    {
                        "order_index": 3,
                        "start_time": "14:00",
                        "end_time": "15:30",
                        "activity": "Gửi xe & nước uống",
                        "estimated_cost": 60000,
                    },
                ],
            }
        ],
    }
    mock_response = MagicMock()
    mock_response.text = json.dumps(mock_output, ensure_ascii=False)
    mock_response.candidates = []

    with patch("app.routers.planner._client") as mock_client:
        mock_client.models.generate_content.return_value = mock_response

        res = client.post(
            "/planner",
            json={
                "trip_id": "trip-case-c",
                "destination": "Hạ Long",
                "days": 1,
                "start_date": "2026-11-23",
                "end_date": "2026-11-23",
                "budget": 500000,
                "currency": "VND",
            },
        )
        assert res.status_code == 200
        body = res.json()
        day = body["days"][0]
        assert day["day_cost"] == 60000
        assert day["unknown_cost_item_count"] == 2
        assert day["items"][0]["estimated_cost"] is None
        assert day["items"][0]["cost_status"] == "UNKNOWN"
        assert day["items"][1]["estimated_cost"] is None
        assert day["items"][1]["cost_status"] == "UNKNOWN"
        assert day["items"][2]["estimated_cost"] == 60000
        assert day["items"][2]["cost_status"] == "KNOWN"

        ba = body["budget_analysis"]
        assert ba["known_cost_total"] == 60000
        assert ba["estimated_cost"] == 60000
        assert ba["unknown_cost_item_count"] == 2
        assert ba["cost_status"] == "PARTIAL_UNKNOWN"
        assert ba["has_sufficient_budget_basis"] is False
        assert ba["is_over_budget"] is False
        assert ba["variance"] is None  # Surplus suppressed when unknown costs exist


def test_planner_detects_overlapping_schedule_in_same_day():
    """Case B2: overlapping intervals in the same day are surfaced in schedule_violations."""
    mock_output = {
        "destination": "Hạ Long",
        "total_days": 1,
        "days": [
            {
                "day_number": 1,
                "date": "2026-11-23",
                "title": "Ngày 1: Chồng giờ",
                "items": [
                    {
                        "order_index": 1,
                        "start_time": "09:00",
                        "end_time": "11:00",
                        "activity": "Cà phê sáng tại Cafe ban mê",
                        "place_name": "Cafe ban mê",
                        "estimated_cost": 60000,
                    },
                    {
                        "order_index": 2,
                        "start_time": "10:30",
                        "end_time": "12:00",
                        "activity": "Mua sắm tại Chợ Cái Dăm",
                        "place_name": "Chợ Cái Dăm",
                        "estimated_cost": 100000,
                    },
                ],
            }
        ],
    }
    mock_response = MagicMock()
    mock_response.text = json.dumps(mock_output, ensure_ascii=False)
    mock_response.candidates = []

    with patch("app.routers.planner._client") as mock_client:
        mock_client.models.generate_content.return_value = mock_response
        res = client.post(
            "/planner",
            json={
                "trip_id": "trip-case-b2",
                "destination": "Hạ Long",
                "days": 1,
                "start_date": "2026-11-23",
                "end_date": "2026-11-23",
                "budget": 1000000,
                "currency": "VND",
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["has_schedule_violations"] is True
        assert len(body["schedule_violations"]) == 1
        assert body["schedule_violations"][0]["code"] == "SCHEDULE_OVERLAP"
        assert len(body["days"][0]["items"][0]["violations"]) == 1
        assert len(body["days"][0]["items"][1]["violations"]) == 1


def test_c4_itinerary_evaluator_handles_nullable_and_zero_costs():
    """Verify C4 product evaluator supports both unknown (`None`/omitted) and free (`0`) item costs."""
    from app.services.c4_itinerary_evaluator import evaluate_c4_itinerary

    scenario = {
        "scenario_id": "c4_nullable_and_free_check",
        "expected_constraints": {"min_days": 1, "max_days": 2, "min_items_per_day": 2},
    }

    # Case 1: Mix of explicit None, omitted cost, and known paid item -> PARTIAL_UNKNOWN, variance=None
    partial_unknown_resp = {
        "destination": "Hạ Long",
        "budget_analysis": {
            "total_budget": 500000,
            "estimated_cost": 60000,
            "known_cost_total": 60000,
            "unknown_cost_item_count": 2,
            "cost_status": "PARTIAL_UNKNOWN",
            "has_sufficient_budget_basis": False,
            "is_over_budget": False,
            "variance": None,
        },
        "days": [
            {
                "day_number": 1,
                "day_cost": 60000,
                "unknown_cost_item_count": 2,
                "items": [
                    {"activity": "Cafe", "place_name": "Cafe ban mê", "estimated_cost": None, "cost_status": "UNKNOWN"},
                    {"activity": "Bảo tàng", "place_name": "Bảo tàng Quảng Ninh", "cost_status": "UNKNOWN"},
                    {"activity": "Gửi xe", "estimated_cost": 60000, "cost_status": "KNOWN"},
                ],
            }
        ],
    }
    res_null = evaluate_c4_itinerary(partial_unknown_resp, scenario)
    assert res_null["success"] is True, res_null["failed_checks"]
    assert res_null["calculated_known_total"] == 60000
    assert res_null["calculated_unknown_count"] == 2
    assert res_null["cost_status"] == "PARTIAL_UNKNOWN"

    # Reject fabricated surplus when unknown costs exist
    bad_surplus_resp = {
        **partial_unknown_resp,
        "budget_analysis": {**partial_unknown_resp["budget_analysis"], "variance": 440000},
    }
    assert evaluate_c4_itinerary(bad_surplus_resp, scenario)["success"] is False

    # Case 2: Sourced free POIs (`estimated_cost = 0`) -> COMPLETE, valid surplus = 300000
    free_zero_resp = {
        "destination": "Đà Nẵng",
        "budget_analysis": {
            "total_budget": 300000,
            "estimated_cost": 0,
            "known_cost_total": 0,
            "unknown_cost_item_count": 0,
            "cost_status": "COMPLETE",
            "has_sufficient_budget_basis": True,
            "is_over_budget": False,
            "variance": 300000,
        },
        "days": [
            {
                "day_number": 1,
                "day_cost": 0,
                "unknown_cost_item_count": 0,
                "items": [
                    {"activity": "Tắm biển Mỹ Khê", "place_name": "Bãi biển Mỹ Khê", "estimated_cost": 0, "cost_status": "KNOWN"},
                    {"activity": "Xem Cầu Rồng", "place_name": "Cầu Rồng", "estimated_cost": 0, "cost_status": "KNOWN"},
                ],
            }
        ],
    }
    res_zero = evaluate_c4_itinerary(free_zero_resp, scenario)
    assert res_zero["success"] is True, res_zero["failed_checks"]
    assert res_zero["calculated_known_total"] == 0
    assert res_zero["calculated_unknown_count"] == 0
    assert res_zero["cost_status"] == "COMPLETE"


def test_planner_halong_demo_three_cost_types_regression():
    """Regression characterization for the 3 cost categories observed in live Hạ Long demo:
    1) Verified-source ticket: Bảo tàng Quảng Ninh (place_name matched in NestJS, 80.000đ)
    2) Unknown-price POI: Tháp Đồng Hồ Hạ Long (estimated_cost=None)
    3) AI-estimated unverified meal: Bún bề bề Hòn Gai (estimated_cost=120.000đ)
    """
    demo_output = {
        "destination": "Hạ Long",
        "total_days": 1,
        "days": [
            {
                "day_number": 1,
                "date": "2026-11-28",
                "title": "Khám phá Văn hóa & Lịch sử Hạ Long",
                "items": [
                    {
                        "order_index": 1,
                        "start_time": "08:00",
                        "end_time": "10:30",
                        "activity": "Tham quan Bảo tàng Quảng Ninh - Tìm hiểu lịch sử và văn hóa vùng đất mỏ",
                        "place_id": "8f2b5a69-1293-4efe-8fc5-3a74193edd0f",
                        "place_name": "Bảo tàng Quảng Ninh",
                        "notes": "Giá vé đã xác minh cho 2 người lớn là 80.000 VND (40.000 VND/người).",
                        "estimated_cost": 80000,
                        "transport_mode": "motorbike",
                    },
                    {
                        "order_index": 2,
                        "start_time": "10:30",
                        "end_time": "11:15",
                        "activity": "Check-in và tham quan Tháp Đồng Hồ Hạ Long",
                        "place_id": "65562a67-84ff-44a0-990d-31917a2a9bd0",
                        "place_name": "Tháp Đồng Hồ Hạ Long",
                        "notes": "Chi phí tham quan/gửi xe tại đây chưa có dữ liệu giá xác minh.",
                        "estimated_cost": None,
                        "transport_mode": "motorbike",
                    },
                    {
                        "order_index": 3,
                        "start_time": "11:15",
                        "end_time": "12:00",
                        "activity": "Thưởng thức bún bề bề/bún hải sản Hòn Gai",
                        "place_id": None,
                        "place_name": "Khu vực ẩm thực Hòn Gai",
                        "notes": "AI ước tính khoảng 50.000 - 60.000 VND/bát cho 2 người.",
                        "estimated_cost": 120000,
                        "transport_mode": "motorbike",
                    },
                ],
            }
        ],
    }
    mock_response = MagicMock()
    mock_response.text = json.dumps(demo_output, ensure_ascii=False)
    mock_response.candidates = []

    with patch("app.routers.planner._client") as mock_client:
        mock_client.models.generate_content.return_value = mock_response
        res = client.post(
            "/planner",
            json={
                "request_id": "req-halong-3cost-regression",
                "trip_id": "88888888-ba26-4c17-8888-000000000c41",
                "destination": "Hạ Long",
                "days": 1,
                "start_date": "2026-11-28",
                "end_date": "2026-11-28",
                "budget": 500000,
                "currency": "VND",
                "interests": ["museum"],
            },
        )
        assert res.status_code == 200
        body = res.json()
        items = body["days"][0]["items"]

        # Item 1: 80.000đ verified POI
        assert items[0]["place_name"] == "Bảo tàng Quảng Ninh"
        assert items[0]["estimated_cost"] == 80000
        assert items[0]["cost_status"] == "KNOWN"

        # Item 2: unknown-price POI -> null preserved, never coerced to 0
        assert items[1]["place_name"] == "Tháp Đồng Hồ Hạ Long"
        assert items[1]["estimated_cost"] is None
        assert items[1]["cost_status"] == "UNKNOWN"

        # Item 3: 120.000đ AI-estimated food item -> FastAPI marks numeric cost KNOWN (NestJS classifies provenance)
        assert items[2]["place_name"] == "Khu vực ẩm thực Hòn Gai"
        assert items[2]["estimated_cost"] == 120000
        assert items[2]["cost_status"] == "KNOWN"

        ba = body["budget_analysis"]
        assert ba["known_cost_total"] == 200000
        assert ba["unknown_cost_item_count"] == 1
        assert ba["cost_status"] == "PARTIAL_UNKNOWN"
        assert ba["has_sufficient_budget_basis"] is False
        assert ba["variance"] is None

