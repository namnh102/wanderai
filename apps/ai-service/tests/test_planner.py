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
