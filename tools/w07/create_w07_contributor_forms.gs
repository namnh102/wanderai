/**
 * W07-A3 Optional Owner Utility: Google Forms Generator for GoMate / WanderAI
 *
 * Authority:
 *   Bound to W07-A2 Manifest SHA256: b4be35d96ff503c61986674a6b3eb37b993484c0dc121434772184a2b089ed2b
 *   Form Definition SHA256: 9c17cfc51c41295c8338b40544324454a36a7276bb2339edd3a0b59c88c6de8a
 *   Generator Lifecycle Status: STATICALLY_VERIFIED_OWNER_RUNTIME_PREFLIGHT_REQUIRED
 *   Required Owner Preflight Gate: OWNER_GOOGLE_FORMS_RUNTIME_PREFLIGHT
 *
 * IMPORTANT:
 *   - Owner utility ONLY. Never executed in CI.
 *   - Static Python CI verification does NOT replace Owner Google account runtime preflight.
 *   - Does NOT store credentials or call any paid API.
 *   - Creates 3 city-specific Google Forms (Hà Nội, Đà Nẵng, Hạ Long), each containing
 *     exactly 20 canonical POIs rendered as human-readable <POI name>.
 *   - Configures supported privacy-first settings:
 *       setCollectEmail(false)
 *       setLimitOneResponsePerUser(false)
 *       setShowLinkToRespondAgain(true)
 *   - Guards advanced responder publishing with supportsAdvancedResponderPermissions().
 *
 * Usage (in https://script.google.com):
 *   1. Create a new Apps Script project and paste this file into Code.gs.
 *   2. Select `createW07ContributorForms` and click Run.
 *   3. Inspect the Execution Log and complete the 10-step OWNER_GOOGLE_FORMS_RUNTIME_PREFLIGHT
 *      in an incognito/private browser before distributing any link to contributors.
 */

const W07_A2_MANIFEST_SHA256 = "b4be35d96ff503c61986674a6b3eb37b993484c0dc121434772184a2b089ed2b";
const W07_FORM_VERSION = "1.0.0";
const W07_GENERATOR_LIFECYCLE_STATUS = "STATICALLY_VERIFIED_OWNER_RUNTIME_PREFLIGHT_REQUIRED";
const W07_OWNER_RUNTIME_PREFLIGHT_GATE = "OWNER_GOOGLE_FORMS_RUNTIME_PREFLIGHT";
const W07_CONSENT_TEXT_VI = "Việc gửi đánh giá địa điểm là hoàn toàn tự nguyện phục vụ đồ án tốt nghiệp đại học (GoMate / WanderAI). Nội dung đánh giá sẽ được ẩn danh hoàn toàn (không lưu họ tên, số điện thoại, email hay tài khoản cá nhân trong bộ dữ liệu khoa học) và được sử dụng cho mục đích nghiên cứu, đánh giá thực nghiệm và trình diễn học thuật phi thương mại. Người đóng góp xác nhận không đưa thông tin cá nhân nhạy cảm vào nội dung, xác nhận bản thân đã trực tiếp đến/trải nghiệm địa điểm được chọn, tự viết đánh giá, không sao chép từ Google Maps, Tripadvisor, Booking, Agoda hay Foody, không dùng AI (ChatGPT, Gemini, Claude) để tạo hoặc viết lại nội dung, và đồng ý cấp quyền tái sử dụng học thuật phi thương mại cho dự án.";
const W07_CONSENT_TEXT_EN = "Submission of this place review is completely voluntary for an academic graduation project (GoMate / WanderAI). Your review will be strictly anonymized (no real name, phone number, email, or social handle will be stored in the scientific corpus) and may be used for research, benchmark evaluation, and academic demonstration. Please do not submit any sensitive personal information. By checking the consent box, you confirm that you have personally visited or directly experienced the selected place (and personally visited or directly experienced the selected POI), that the review is your own original writing (not copied from Google Maps, Tripadvisor, Booking, Agoda, or Foody, and not generated or paraphrased by an AI/LLM), and that you grant permission for academic, non-commercial project reuse.";
const W07_CONSENT_CHECKBOX_LABEL = "Tôi xác nhận đầy đủ 7 cam kết trên (đã trực tiếp đến địa điểm, tự viết 100%, không sao chép, không dùng AI, tự nguyện cấp quyền nghiên cứu học thuật ẩn danh) / I affirm all 7 statements above.";

const W07_CITY_FORMS = [
  {
    "form_id": "w07_form_hanoi_v1",
    "city": "Hà Nội",
    "title": "[GoMate W07] Đánh giá địa điểm du lịch thực tế — Hà Nội (20 POI)",
    "raw_csv_default_relpath": "data/restricted/w07_reviews/raw_forms/hanoi_responses.csv",
    "pois": [
      "Lăng Chủ tịch Hồ Chí Minh",
      "Hoàng thành Thăng Long",
      "Nhà tù Hỏa Lò",
      "Đền Ngọc Sơn",
      "Chùa Trấn Quốc",
      "Bảo tàng Dân tộc học Việt Nam",
      "Nhà thờ Lớn",
      "Sen Tây Hồ",
      "Quán Ăn Ngon - Phan Bội Châu",
      "Pho 10",
      "Cửa Hàng Bánh Tôm Hồ Tây",
      "Highlands Coffee",
      "Cà Phê Nola",
      "Cà Phê Kafa",
      "Sheraton Hanoi",
      "Somerset Grand Hanoi",
      "Công viên Thống Nhất",
      "Công viên Thủ Lệ",
      "Công viên Lê-nin",
      "Le Pub"
    ]
  },
  {
    "form_id": "w07_form_danang_v1",
    "city": "Đà Nẵng",
    "title": "[GoMate W07] Đánh giá địa điểm du lịch thực tế — Đà Nẵng (20 POI)",
    "raw_csv_default_relpath": "data/restricted/w07_reviews/raw_forms/danang_responses.csv",
    "pois": [
      "Cầu Rồng",
      "Ngũ Hành Sơn",
      "Bảo tàng Nghệ thuật Điêu khắc Chăm Đà Nẵng",
      "Chùa Linh Ứng",
      "Cầu Sông Hàn",
      "Bảo tàng Đà Nẵng",
      "Chợ Cồn",
      "Bánh Xèo Bà Dưỡng",
      "My Quang Bà Mua",
      "Nhà hàng hải sản Bé Anh",
      "Chợ Đêm Sơn Trà",
      "Chợ Bắc Mỹ An",
      "Vincom Plaza",
      "Ca Phe 83",
      "InterContinental Danang Sun Peninsula Resort",
      "Furama Resort",
      "Bãi biển Mỹ Khê",
      "Bãi tắm Non Nước",
      "Ban Co Peak",
      "Sun World Bà Nà Hills"
    ]
  },
  {
    "form_id": "w07_form_halong_v1",
    "city": "Hạ Long",
    "title": "[GoMate W07] Đánh giá địa điểm du lịch thực tế — Hạ Long (20 POI)",
    "raw_csv_default_relpath": "data/restricted/w07_reviews/raw_forms/halong_responses.csv",
    "pois": [
      "Vịnh Hạ Long",
      "Bảo tàng Quảng Ninh",
      "Động Thiên Cung",
      "Hang Đầu Gỗ",
      "Hang Luồn Cave Entrance",
      "Hòn Đỉnh Hương",
      "Ha Long International Cruise Port",
      "Nhà hàng Hồng Hạnh 3",
      "Nhà hàng Ngọc Phương Nam 1",
      "Nhà hàng Buffet Sen Á Đông",
      "Chợ Cái Dăm",
      "Chợ Hạ Long II",
      "Sữa chua trân châu Hạ Long cơ sở 00",
      "Highlands Coffee",
      "Vinpearl Ha Long resort",
      "Novotel Ha Long",
      "Công viên Lán Bè",
      "Vườn hoa",
      "Vườn hoa Thị trấn Trới",
      "Sunworld"
    ]
  }
];

function createW07ContributorForms() {
  const results = [];
  for (let i = 0; i < W07_CITY_FORMS.length; i++) {
    const spec = W07_CITY_FORMS[i];
    const form = FormApp.create(spec.title);
    form.setDescription(
      "Khảo sát thu thập đánh giá thực tế phục vụ nghiên cứu học thuật đồ án tốt nghiệp GoMate / WanderAI.\n\n" +
      "Mỗi lần gửi biểu mẫu tương ứng với 01 đánh giá cho 01 địa điểm (POI) tại " + spec.city + " mà bạn đã trực tiếp ghé thăm. " +
      "Bạn có thể gửi lại biểu mẫu nhiều lần cho các địa điểm khác mà bạn đã trải nghiệm.\n\n" +
      "Quyền riêng tư: Biểu mẫu KHÔNG thu thập họ tên, email, số điện thoại hay tài khoản cá nhân.\n" +
      "Manifest SHA256: " + W07_A2_MANIFEST_SHA256
    );
    form.setCollectEmail(false);
    form.setLimitOneResponsePerUser(false);
    form.setShowLinkToRespondAgain(true);

    // 1. Required POI selection dropdown (20 canonical POIs for this city)
    const poiItem = form.addListItem();
    poiItem
      .setTitle("1. Chọn địa điểm (POI) bạn đã trực tiếp đến trải nghiệm")
      .setHelpText("Chỉ chọn 1 địa điểm tại " + spec.city + " mà bạn đã thực sự ghé thăm.")
      .setChoiceValues(spec.pois)
      .setRequired(true);

    // 2. Required integer rating 1-5
    const ratingItem = form.addScaleItem();
    ratingItem
      .setTitle("2. Điểm đánh giá tổng thể (1 = Rất tệ, 5 = Rất tốt)")
      .setBounds(1, 5)
      .setLabels("Rất tệ", "Rất tốt")
      .setRequired(true);

    // 3. Required review_text
    const textItem = form.addParagraphTextItem();
    textItem
      .setTitle("3. Nội dung đánh giá thực tế của riêng bạn")
      .setHelpText(
        "Hãy viết cảm nhận cụ thể của chính bạn (khuyến nghị >= 20 ký tự, >= 5 từ). " +
        "Không sao chép từ Google Maps/Tripadvisor/Booking/Agoda/Foody, không dùng AI, " +
        "và KHÔNG ghi số điện thoại hay email vào nội dung."
      )
      .setRequired(true);

    // 4. Optional visit_period
    const visitItem = form.addTextItem();
    visitItem
      .setTitle("4. Thời điểm ghé thăm (Không bắt buộc)")
      .setHelpText("Định dạng gợi ý: YYYY-MM (ví dụ: 2025-08) hoặc YYYY-Q1..Q4 (ví dụ: 2025-Q3).")
      .setRequired(false);

    // 5. Required consent checkbox
    const consentItem = form.addCheckboxItem();
    consentItem
      .setTitle("5. Cam kết tính xác thực và đồng thuận nghiên cứu học thuật")
      .setHelpText(W07_CONSENT_TEXT_VI + "\n\n" + W07_CONSENT_TEXT_EN)
      .setChoices([consentItem.createChoice(W07_CONSENT_CHECKBOX_LABEL)])
      .setRequired(true);

    // Guard advanced responder publishing by supportsAdvancedResponderPermissions()
    const supportsAdvanced = (
      typeof form.supportsAdvancedResponderPermissions === "function" &&
      form.supportsAdvancedResponderPermissions() == true
    );
    let publishActionTaken = "NO_OP_ADVANCED_RESPONDER_PERMISSIONS_UNSUPPORTED";
    if (supportsAdvanced) {
      form.setPublished(true);
      publishActionTaken = "form.setPublished(true)";
    }

    const summary = {
      form_title: spec.title,
      form_id: spec.form_id,
      google_form_id: form.getId(),
      city: spec.city,
      poi_count: spec.pois.length,
      edit_url: form.getEditUrl(),
      published_url: form.getPublishedUrl(),
      supportsAdvancedResponderPermissions: supportsAdvanced,
      publish_action_taken: publishActionTaken,
      collect_email_configuration: false,
      limit_one_response_configuration: false,
      show_link_to_respond_again_configuration: true,
      raw_csv_target: spec.raw_csv_default_relpath
    };
    results.push(summary);
    Logger.log(JSON.stringify(summary, null, 2));
  }
  return results;
}
