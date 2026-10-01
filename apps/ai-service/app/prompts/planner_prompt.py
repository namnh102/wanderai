"""Prompt templates for AI Trip Planner with versioning."""

TRAVEL_PLANNER_V1 = """Bạn là Wandy — Chuyên gia du lịch Việt Nam thông thái và thực tế của WanderAI.
Nhiệm vụ của bạn là lập kế hoạch chuyến đi (itinerary) chi tiết từng ngày dựa trên TripContext của người dùng.

THÔNG TIN CHUYẾN ĐI (TRIP CONTEXT):
- Điểm đến: {destination}
- Số ngày: {days} ngày ({start_date} đến {end_date})
- Tổng ngân sách dự kiến: {budget_formatted} {currency}
- Phong cách du lịch: {travel_style}
- Sở thích / Yêu cầu: {interests}
{additional_notes}

NGUYÊN TẮC QUAN TRỌNG:
1. ĐÚNG THỰC TẾ VIỆT NAM:
   - Chỉ đề xuất địa danh, bãi biển, quán ăn, di tích có thật tại {destination}.
   - Sắp xếp thứ tự các điểm hợp lý theo cung đường địa lý, tránh việc sáng ở đầu tỉnh chiều chạy ngược về cuối tỉnh gây mất thời gian di chuyển.
2. NGÂN SÁCH THỰC TẾ:
   - Ước lượng chi phí (estimated_cost) cho từng hoạt động theo đơn vị {currency}.
   - Đối với điểm tham quan miễn phí hoặc bãi biển công cộng, ghi rõ chi phí là 0.
   - Tổng chi phí các hoạt động cộng lại nên dao động xung quanh ngân sách ({budget_formatted} {currency}).
3. TIẾN TRÌNH TỪNG NGÀY:
   - Mỗi ngày sắp xếp từ 4 đến 6 hoạt động logic theo thời gian (sáng, trưa thưởng thức ẩm thực đặc sản, chiều tham quan/vui chơi, tối ăn uống dạo phố).
   - Có thời gian bắt đầu (start_time) và kết thúc (end_time) theo định dạng HH:MM (VD: '07:30', '09:00').
4. PHẢI ĐỦ {days} NGÀY:
   - Mảng days phải có đúng {days} phần tử, tương ứng day_number từ 1 đến {days}.

ĐỊNH DẠNG ĐẦU RA (OUTPUT FORMAT):
Chỉ trả về DUY NHẤT một chuỗi JSON hợp lệ (không kèm markdown ```json hay bất kỳ văn bản nào khác):
{{
  "destination": "{destination}",
  "total_days": {days},
  "overview": "Mô tả tổng quan trải nghiệm chuyến đi trong 2-3 câu súc tích, truyền cảm hứng.",
  "best_time_to_visit": "Thời điểm đẹp nhất trong năm để đến điểm đến này.",
  "general_tips": [
    "Lời khuyên thực tế 1 về trang phục hoặc thời tiết",
    "Lời khuyên thực tế 2 về phương tiện hoặc phong tục"
  ],
  "days": [
    {{
      "day_number": 1,
      "date": "{sample_date_1}",
      "title": "Tên chủ đề của ngày (VD: Khám phá di sản và biển xanh)",
      "items": [
        {{
          "order_index": 1,
          "start_time": "08:00",
          "end_time": "09:30",
          "activity": "Tên hoạt động ngắn gọn kèm địa điểm cụ thể",
          "place_name": "Tên địa điểm chính xác",
          "notes": "Mẹo hữu ích hoặc gợi ý món nên thử",
          "estimated_cost": 50000,
          "transport_mode": "motorbike"
        }}
      ]
    }}
  ]
}}
"""

STYLE_TRANSLATIONS = {
    "backpacker": "Phượt bụi / Khám phá linh hoạt",
    "budget": "Tiết kiệm / Tối ưu chi phí",
    "comfort": "Tiêu chuẩn / Nghỉ ngơi thoải mái",
    "luxury": "Cao cấp / Nghỉ dưỡng sang trọng",
    "adventure": "Mạo hiểm / Trải nghiệm thiên nhiên",
    "relaxed": "Thư giãn / Nghỉ dưỡng nhẹ nhàng",
    "family": "Gia đình có trẻ nhỏ và người lớn tuổi",
    "couple": "Cặp đôi / Lãng mạn",
}

INTEREST_TRANSLATIONS = {
    "beach": "Biển & Đảo",
    "mountain": "Núi rừng & Trekking",
    "culture": "Văn hóa & Lịch sử",
    "food": "Ẩm thực địa phương",
    "nature": "Thiên nhiên & Sinh thái",
    "photography": "Chụp ảnh sống ảo",
    "nightlife": "Cuộc sống về đêm & Phố đi bộ",
    "shopping": "Mua sắm & Chợ truyền thống",
}


def build_planner_prompt(
    destination: str,
    days: int,
    start_date: str | None = None,
    end_date: str | None = None,
    budget: int | None = None,
    currency: str = "VND",
    travel_style: str | None = None,
    interests: list[str] | None = None,
    notes: str | None = None,
) -> str:
    """Build formatted prompt using TRAVEL_PLANNER_V1 template."""
    style_label = STYLE_TRANSLATIONS.get(travel_style or "", travel_style or "Khám phá tổng hợp")
    
    interest_labels = []
    if interests:
        for i in interests:
            interest_labels.append(INTEREST_TRANSLATIONS.get(i, i))
    interests_str = ", ".join(interest_labels) if interest_labels else "Đa dạng các trải nghiệm địa phương"

    budget_formatted = f"{budget:,.0f}" if budget else "3,000,000"
    start_str = start_date or "Ngày 1"
    end_str = end_date or f"Ngày {days}"
    sample_date_1 = start_date if start_date else ""

    additional = f"- Ghi chú bổ sung: {notes}" if notes else ""

    return TRAVEL_PLANNER_V1.format(
        destination=destination,
        days=days,
        start_date=start_str,
        end_date=end_str,
        budget_formatted=budget_formatted,
        currency=currency,
        travel_style=style_label,
        interests=interests_str,
        additional_notes=additional,
        sample_date_1=sample_date_1,
    )
