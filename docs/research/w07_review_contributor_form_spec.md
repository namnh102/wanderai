# W07-A2 — Canonical 60-POI Contributor Review Form Specification & Intake Guide

## 0. Authority & Scope

- **Previous Gate:** `W07-A1-REVIEW-CORPUS-FEASIBILITY-POSTMERGE-CHATGPT-AUDIT = PASS`
- **Authoritative Base:** `develop@7a263ff289b79e198cfda94fea61e1c88dc86813`
- **Target 60-POI Manifest:** `data/evaluation/w07/w07_review_target_60_pois_v1.json` (SHA256: `1e7e59304c182cfe3f4a8518e18df2ab1dde3b9dee5850f081fc390f1d13cd8d`)
- **Restricted Primary Corpus Path (gitignored):** `data/restricted/w07_reviews/w07_canonical_reviews_v1.jsonl`
- **Restricted CSV Intake Template (gitignored):** `data/restricted/w07_reviews/w07_contributor_intake_template_v1.csv`
- **Primary Acquisition Strategy:** `HYBRID_TARGETED_COLLECTION`
- **Next Gate:** `W07-A2-CANONICAL-REVIEW-CORPUS-INTAKE-CHATGPT-AUDIT`

---

## 1. Consent Language (Academic Graduation Project)

### Vietnamese Consent Text (Displayed at Top of Form & Required Checkbox)

> Việc gửi đánh giá địa điểm là hoàn toàn tự nguyện phục vụ đồ án tốt nghiệp đại học (GoMate / WanderAI). Nội dung đánh giá sẽ được ẩn danh hoàn toàn (không lưu họ tên, số điện thoại, email hay tài khoản cá nhân trong bộ dữ liệu khoa học) và được sử dụng cho mục đích nghiên cứu, đánh giá thực nghiệm và trình diễn học thuật phi thương mại. Người đóng góp xác nhận không đưa thông tin cá nhân nhạy cảm vào nội dung, xác nhận đây là trải nghiệm/nhận xét thật do chính mình tự viết (không sao chép từ Google Maps/Tripadvisor và không dùng AI/LLM tạo sinh), và đồng ý cấp quyền tái sử dụng học thuật phi thương mại cho dự án.

### English Consent Text

> Submission of this place review is completely voluntary for an academic graduation project (GoMate / WanderAI). Your review will be strictly anonymized (no real name, phone number, email, or social handle will be stored in the scientific corpus) and may be used for research, benchmark evaluation, and academic demonstration. Please do not submit any sensitive personal information. By checking the consent box, you confirm that this review is your own original writing based on genuine experience/opinion (not copied from Google Maps/Tripadvisor and not generated or paraphrased by an LLM) and grant permission for academic, non-commercial project reuse.

---

## 2. Google Forms / Microsoft Forms / CSV Field Specification

Create a zero-cost Google Form, Microsoft Form, or shared spreadsheet with the following 6 fields:

| # | Form Field | Schema Field Mapping | Type & Validation | Required |
|---:|---|---|---|---|
| 1 | **Canonical Place (`poi_id`)** | `poi_id` + `city` | Dropdown of the 60 frozen POIs formatted as `[City] Name (Category) — poi_id` | **Yes** |
| 2 | **Your Genuine Review (`review_text`)** | `review_text` | Paragraph text (`>= 20` characters and `>= 5` words recommended; describe real experience: atmosphere, service, food/rooms, price, tips) | **Yes** |
| 3 | **Overall Rating (`1–5`)** | `rating` (`rating_scale_max = 5`) | Linear scale `1` to `5` (`1 = Poor`, `5 = Excellent`) | **Yes** |
| 4 | **Review Language** | `language` | Multiple choice: `vi` (Tiếng Việt), `en` (English), `mixed_vi_en` | **Yes** |
| 5 | **Visit Period (Optional)** | `visit_period` | Short text (`YYYY-MM` or `YYYY-Q1..Q4`, e.g. `2025-08`) | Optional |
| 6 | **Originality & Academic Reuse Consent** | `license_or_usage_class = OWNER_FIRST_PARTY_CONSENT` | Required checkbox confirming: (a) genuine personal experience/opinion, (b) not copied from Google/Tripadvisor, (c) not LLM-generated, (d) anonymized academic reuse permitted | **Yes** |

### Strict Authenticity & Privacy Rules
- **No platform copying:** Contributors must **never** copy or translate reviews from Google Maps, Tripadvisor, Booking.com, Agoda, or Foody.
- **No fabricated visits:** Contributors must only review places from the 60-POI list that they have genuinely visited or experienced.
- **Zero LLM generation (`LLM_GENERATED_PRIMARY_REVIEWS = 0`):** LLMs (ChatGPT, Gemini, Claude, etc.) must **never** be used to write, rewrite, or paraphrase reviews.
- **Strict Anonymization:** Do **not** collect phone numbers or sensitive personal data. If the form tool records a respondent identifier to prevent duplicate spam, convert it offline into `author_anonymous_id = contrib_<sha256_prefix>` before writing to `data/restricted/w07_reviews/w07_canonical_reviews_v1.jsonl`.

---

## 3. Primary Review JSONL Schema (`w07_canonical_reviews_v1.jsonl`)

Every accepted row in `data/restricted/w07_reviews/w07_canonical_reviews_v1.jsonl` must conform to this exact 17-field primary schema (plus 3 optional fields):

```json
{
  "review_id": "w07_rev_hn_0001",
  "poi_id": "698ee756-6062-5f47-955b-bdf458682e57",
  "upstream_place_id": "osm:way/37629144",
  "city": "Hà Nội",
  "source": "first_party_contributor_form_v1",
  "source_review_id": null,
  "rating": 5.0,
  "rating_scale_max": 5,
  "review_text": "Không gian quảng trường Ba Đình và khu vực Lăng Bác rất trang nghiêm, sạch sẽ, xếp hàng buổi sáng sớm khá nhanh và trật tự.",
  "language": "vi",
  "created_at": "2026-11-02",
  "collected_at": "2026-11-02T09:00:00Z",
  "source_ref": "gomate_w07_contributor_intake_v1#resp_0001",
  "provenance": "FIRST_PARTY_ACADEMIC_CONTRIBUTOR_CONSENT_V1",
  "license_or_usage_class": "OWNER_FIRST_PARTY_CONSENT",
  "mapping_method": "EXACT_PREBOUND_CANONICAL_POI",
  "mapping_confidence": 1.0,
  "author_anonymous_id": "contrib_9f86d081884c",
  "visit_period": "2025-10",
  "consent_record_id": "consent_2026_0001"
}
```

---

## 4. Frozen 60 Canonical POIs (`20` Hà Nội, `20` Đà Nẵng, `20` Hạ Long)

| # | City | Category Group | Raw Category | `poi_id` | Name | `osm_id` | `overture_id` | Min Reviews |
|---:|---|---|---|---|---|---|---|---:|
| 1 | Hà Nội | `attractions_culture` | `attraction` | `698ee756-6062-5f47-955b-bdf458682e57` | Lăng Chủ tịch Hồ Chí Minh | `way/37625751` | `null` | 5 |
| 2 | Hà Nội | `attractions_culture` | `culture` | `b799793b-fb40-5bc2-9e67-6af92caeabe9` | Hoàng thành Thăng Long | `relation/21425205` | `null` | 5 |
| 3 | Hà Nội | `attractions_culture` | `culture` | `0938eb59-ee1c-5879-a798-58b5fdd07bce` | Nhà tù Hỏa Lò | `way/340128580` | `null` | 5 |
| 4 | Hà Nội | `attractions_culture` | `culture` | `44115e3a-6094-5bcd-b53c-0e3a596b3aff` | Đền Ngọc Sơn | `way/178995262` | `null` | 5 |
| 5 | Hà Nội | `attractions_culture` | `culture` | `e3fe1f1a-f524-55cf-9d83-903e427d0ba4` | Chùa Trấn Quốc | `way/220302249` | `null` | 5 |
| 6 | Hà Nội | `attractions_culture` | `culture` | `f0d424bd-f722-540f-8964-5e6fd8875b56` | Bảo tàng Dân tộc học Việt Nam | `way/339936730` | `e55bab3c-c110-4ba6-a005-5c43986a6095` | 5 |
| 7 | Hà Nội | `restaurants_cafes_markets` | `restaurant` | `afb3793b-7227-4645-a68a-3647c7468638` | Sen Tây Hồ | `node/443000681` | `e8077687-eb1f-44ff-b544-9e7ae8ccdc1e` | 5 |
| 8 | Hà Nội | `restaurants_cafes_markets` | `restaurant` | `acb22336-1124-49d5-a279-6357c2b2b445` | Quán Ăn Ngon - Phan Bội Châu | `node/721836715` | `null` | 5 |
| 9 | Hà Nội | `restaurants_cafes_markets` | `restaurant` | `5350dd97-2f75-45fc-9fc1-1979b08670f7` | Pho 10 | `node/773601261` | `ff9a223f-952f-4d51-b7a9-b90998668554` | 5 |
| 10 | Hà Nội | `restaurants_cafes_markets` | `restaurant` | `b0641225-0f38-4bcc-9f4c-34f65fa50d45` | Cửa Hàng Bánh Tôm Hồ Tây | `node/310727632` | `null` | 5 |
| 11 | Hà Nội | `restaurants_cafes_markets` | `cafe` | `5bd45eb7-a691-4426-9691-a5a00f38d1ad` | Highlands Coffee | `node/442977691` | `e8f37b82-c15a-49d1-ad85-994b4b10f150` | 5 |
| 12 | Hà Nội | `restaurants_cafes_markets` | `cafe` | `4146f2b7-8289-4309-b7e6-60ba7de3470e` | Cà Phê Nola | `node/721836730` | `null` | 5 |
| 13 | Hà Nội | `hotels` | `hotel` | `5e92e89d-8524-4792-862a-6dfce0994862` | Sheraton Hanoi | `node/922396410` | `80ceecb4-b812-4b29-a332-e22dc1a21fb8` | 5 |
| 14 | Hà Nội | `hotels` | `hotel` | `9a96e0a0-e040-4e16-a3f2-682ca373dd8e` | Somerset Grand Hanoi | `node/442033049` | `165cef5b-70ba-41d9-8314-4b54d979379d` | 5 |
| 15 | Hà Nội | `hotels` | `hotel` | `ab78f751-d68d-4436-b42a-93587aa5a22a` | Khách Sạn Little Hanoi | `node/708488342` | `e464edc4-64e6-4031-99ed-ffab9463a841` | 5 |
| 16 | Hà Nội | `hotels` | `hotel` | `e5729e0c-08a4-41c4-ad37-ecbfaa244efc` | Khách Sạn Golden Sunrise | `node/1378877103` | `5c3d9a40-7172-46ea-8a83-d3080c62f505` | 5 |
| 17 | Hà Nội | `hotels` | `hotel` | `6377c9e4-6376-4070-97fa-799c1cb45838` | Royal Hotel | `node/1388478348` | `3982167b-3592-4f36-9eeb-42aff0f47cf9` | 5 |
| 18 | Hà Nội | `nature_beach` | `nature` | `766656bb-c7e0-555d-9963-d3132f0de086` | Công viên Thống Nhất | `way/37933849` | `null` | 5 |
| 19 | Hà Nội | `nature_beach` | `nature` | `1f9c2b46-e032-5cbc-a9dc-dc68c435c594` | Công viên Thủ Lệ | `way/28945667` | `null` | 5 |
| 20 | Hà Nội | `other_tourism` | `nightlife` | `9b08dfe9-6f97-4d4b-94f6-f3548efd696c` | Le Pub | `node/969250576` | `null` | 5 |
| 21 | Đà Nẵng | `attractions_culture` | `attraction` | `9974ff88-5418-5867-ae49-1b72e0f0861f` | Cầu Rồng | `way/694831926` | `null` | 5 |
| 22 | Đà Nẵng | `attractions_culture` | `attraction` | `6f758ad7-5685-57b5-9913-d28e15bdb7c5` | Ngũ Hành Sơn | `relation/8552348` | `null` | 5 |
| 23 | Đà Nẵng | `attractions_culture` | `culture` | `a24d48ff-59d6-5e53-af77-36448e60d1cc` | Bảo tàng Nghệ thuật Điêu khắc Chăm Đà Nẵng | `way/302872188` | `null` | 5 |
| 24 | Đà Nẵng | `attractions_culture` | `temple` | `5fc0994a-e578-4a25-b375-7f079e6dc3ba` | Chùa Linh Ứng | `way/1205388457` | `b9ad130e-8f19-4dcb-92a7-638573a3f62d` | 5 |
| 25 | Đà Nẵng | `attractions_culture` | `attraction` | `2f389152-5676-54be-b812-a1d561b7df15` | Cầu Sông Hàn | `node/7276380289` | `null` | 5 |
| 26 | Đà Nẵng | `attractions_culture` | `culture` | `cb6cce60-8270-5f43-b9f7-42de2d7d7da3` | Bảo tàng Đà Nẵng | `way/1368599361` | `null` | 5 |
| 27 | Đà Nẵng | `restaurants_cafes_markets` | `restaurant` | `62a874a9-13e2-44d2-95b5-30e980b98965` | Bánh Xèo Bà Dưỡng | `node/4541527689` | `c732f0d5-911d-4d9f-93b2-51c886f4fe0b` | 5 |
| 28 | Đà Nẵng | `restaurants_cafes_markets` | `restaurant` | `61639da8-996a-43df-b6d3-928b6bdd70b9` | My Quang Bà Mua | `node/7210857787` | `da92232b-8e79-4082-84b0-6a35263af4df` | 5 |
| 29 | Đà Nẵng | `restaurants_cafes_markets` | `restaurant` | `fd118580-b5da-467d-9873-0116ba435f37` | Nhà hàng hải sản Bé Anh | `node/5485483822` | `df8dc91d-1790-4600-a518-31bec995467a` | 5 |
| 30 | Đà Nẵng | `restaurants_cafes_markets` | `market` | `9a2ca486-437d-4044-8541-d34d911d4fb4` | Chợ Đêm Sơn Trà | `way/1556362196` | `a310c792-65d8-4115-9df6-ddf54babd1a8` | 5 |
| 31 | Đà Nẵng | `restaurants_cafes_markets` | `market` | `c2afbb07-aaf9-47c1-9877-d17e64422066` | Chợ Bắc Mỹ An | `way/118614280` | `4d3dbac0-aae6-4960-8b89-d06c52fe21f5` | 5 |
| 32 | Đà Nẵng | `restaurants_cafes_markets` | `cafe` | `8ebf0429-fabb-4701-bbc1-cb2fea86d587` | Ca Phe 83 | `node/729406392` | `1b27afcb-daa1-4977-bcd5-cc5327c08c64` | 5 |
| 33 | Đà Nẵng | `hotels` | `hotel` | `4608034c-6c43-4d54-a542-ead8e23b1338` | InterContinental Danang Sun Peninsula Resort | `way/360113559` | `0d91068a-7ee8-4d97-ad32-a075a23d30fd` | 5 |
| 34 | Đà Nẵng | `hotels` | `hotel` | `a32ce1b4-126b-4544-b5ea-4a7edbab6a0a` | Furama Resort | `way/485212452` | `82f95e1f-7bf8-40df-a3ed-6f92a4a847f3` | 5 |
| 35 | Đà Nẵng | `hotels` | `hotel` | `00fa371f-a082-49ed-977c-38ae5460849f` | Hilton Da Nang | `way/655921406` | `748873d9-5259-4815-a64d-5d6371e55594` | 5 |
| 36 | Đà Nẵng | `hotels` | `hotel` | `d7fface5-c0f4-4c9f-893a-5b9c66c74334` | Haian Beach Hotel & Spa | `way/693058159` | `e91bcd0e-3087-421c-af92-e78780926d6d` | 5 |
| 37 | Đà Nẵng | `hotels` | `hotel` | `19059ca2-6cee-4a42-bd3f-bd0c3fa65741` | Brilliant Hotel | `node/2987527833` | `6e439352-bac0-45ce-9df8-4b63b1c1c16c` | 5 |
| 38 | Đà Nẵng | `nature_beach` | `beach` | `2f202acf-c2bb-526a-9803-aaca142ffdad` | Bãi biển Mỹ Khê | `relation/19000664` | `null` | 5 |
| 39 | Đà Nẵng | `nature_beach` | `nature` | `b5ea1253-6b6a-5f5a-b910-5ef18cd29c94` | Ban Co Peak | `node/1538334281` | `null` | 5 |
| 40 | Đà Nẵng | `other_tourism` | `entertainment` | `987f490f-b1c7-42cf-b92e-300d57fd8d5f` | Sun World Bà Nà Hills | `way/359114064` | `null` | 5 |
| 41 | Hạ Long | `attractions_culture` | `attraction` | `ade2140c-7945-4044-b99a-b1a028edce9e` | Vịnh Hạ Long | `node/2707025319` | `null` | 5 |
| 42 | Hạ Long | `attractions_culture` | `museum` | `8f2b5a69-1293-4efe-8fc5-3a74193edd0f` | Bảo tàng Quảng Ninh | `node/5395107122` | `bd078edf-ad58-4f6c-9016-adf65c90e5eb` | 5 |
| 43 | Hạ Long | `attractions_culture` | `attraction` | `9a979427-a0bb-421d-b75f-2a6ee79b120b` | Động Thiên Cung | `node/4730928605` | `null` | 5 |
| 44 | Hạ Long | `attractions_culture` | `attraction` | `9fbcb0b4-27bc-4482-a8e3-8be6e3c72677` | Hang Đầu Gỗ | `node/4730928606` | `null` | 5 |
| 45 | Hạ Long | `attractions_culture` | `attraction` | `77af14b6-85ac-4c91-873a-e7da27d555f4` | Hang Luồn Cave Entrance | `node/3560283504` | `null` | 5 |
| 46 | Hạ Long | `attractions_culture` | `attraction` | `871a6ee7-1d46-49bb-957a-ff50260b1f3b` | Ha Long International Cruise Port | `node/7044140886` | `527ebd9f-445a-4059-a815-0d988c0925a2` | 5 |
| 47 | Hạ Long | `restaurants_cafes_markets` | `restaurant` | `b37d68ee-0cb3-49f0-a399-cac4c8e2732c` | Nhà hàng Hồng Hạnh 3 | `node/12998514201` | `92ed9717-ce41-4e8f-ab25-52e369cd88be` | 5 |
| 48 | Hạ Long | `restaurants_cafes_markets` | `restaurant` | `7d01af19-10bc-4679-8cfa-4396209dece4` | Nhà hàng Ngọc Phương Nam 1 | `node/12998531301` | `04dda4d2-9d22-4516-a651-73c774b61663` | 5 |
| 49 | Hạ Long | `restaurants_cafes_markets` | `restaurant` | `065f8492-2ab3-4ea0-ae8f-9cc6f8c18ae5` | Nhà hàng Buffet Sen Á Đông | `node/12998779901` | `0772c46b-7aa9-40a0-b403-78dec2591927` | 5 |
| 50 | Hạ Long | `restaurants_cafes_markets` | `market` | `96523873-1b85-4d2f-b85c-cb3f5593091b` | Chợ Cái Dăm | `way/674641659` | `9b6e3c9a-d263-4e5d-8ff7-7d7bddc1ffef` | 5 |
| 51 | Hạ Long | `restaurants_cafes_markets` | `market` | `6215446b-2fdd-4014-aacf-23de6e45e264` | Chợ Hạ Long II | `way/673558390` | `null` | 5 |
| 52 | Hạ Long | `restaurants_cafes_markets` | `cafe` | `b57b3f7d-9704-44b0-8139-19bea1998391` | Sữa chua trân châu Hạ Long cơ sở 00 | `node/13009250202` | `null` | 5 |
| 53 | Hạ Long | `hotels` | `hotel` | `75a3fbd1-a24e-43c6-820a-72f95ebc05c0` | Vinpearl Ha Long resort | `node/4330722989` | `9ed3a2e3-60a3-4df0-acd8-83185f57a281` | 5 |
| 54 | Hạ Long | `hotels` | `hotel` | `9740c851-5b06-432c-a243-071ad0906494` | Novotel Ha Long | `way/676720191` | `893209f5-1d13-479f-b7d7-6630b1f3fe57` | 5 |
| 55 | Hạ Long | `hotels` | `hotel` | `80b93f9b-1a08-4a9c-9786-6b98d80b30bd` | Khách sạn Mường Thanh Luxury Hạ Long Centre | `relation/19730970` | `null` | 5 |
| 56 | Hạ Long | `hotels` | `hotel` | `512e972a-e67b-42af-bb8c-e2bc4fe9c4d0` | Paradise Suites | `node/6956608362` | `88a0145c-aa3e-4b54-b3ba-f2b750c58a3a` | 5 |
| 57 | Hạ Long | `hotels` | `hotel` | `55119cbc-b173-43e8-a603-a79f6dc25ae7` | Halong Plaza Hotel | `node/3410529615` | `4288385a-a620-4628-9f3c-acba6f68fa15` | 5 |
| 58 | Hạ Long | `nature_beach` | `park` | `708ee182-c879-477c-b920-516e2c99b0a6` | Công viên Lán Bè | `way/673096986` | `null` | 5 |
| 59 | Hạ Long | `nature_beach` | `park` | `8fe33554-7a07-4eb2-870f-8af643d8c728` | Vườn hoa Thị trấn Trới | `way/677419454` | `null` | 5 |
| 60 | Hạ Long | `other_tourism` | `entertainment` | `1a95430d-289d-4663-91b8-ae64ede4f9a4` | Sunworld | `relation/18623673` | `null` | 5 |

---

## 5. Owner Action Pack (Low-Burden Collection Plan)

- **Current Status:** `COLLECTION_IN_PROGRESS` (`0 / 300` primary reviews collected; `CORPUS_SCIENTIFIC_MINIMUM_READY = false`).
- **Remaining Gap to Scientific Minimum:** `300` reviews across `60` canonical POIs (`>= 5` reviews/POI: `100` Hà Nội, `100` Đà Nẵng, `100` Hạ Long).
- **Recommended Low-Burden Distribution:**
  - Invite **30 to 50 contributors** (classmates, university students, local travelers).
  - Each contributor submits **6 to 10 genuine reviews** for POIs from the 60-POI table that they have personally visited in Hà Nội, Đà Nẵng, or Hạ Long.
  - Run offline validation after importing responses:
    ```bash
    python scripts/validate_w07_review_corpus_v1.py --validate-jsonl data/restricted/w07_reviews/w07_canonical_reviews_v1.jsonl
    ```
