# W07-A4H — Assisted First-Party Review Collection Guide

## 0. Authority & Scope

- **Previous Gates:**
  - `W07-A3-CONTRIBUTOR-COLLECTION-LAUNCH-POSTMERGE-CHATGPT-AUDIT = PASS`
  - `W07-A3-OWNER-GOOGLE-FORMS-RUNTIME-PREFLIGHT-CHATGPT-AUDIT = PASS`
- **Authoritative Base:** `develop@61e58f0fed2539971584c49cd7a2dac159554ff7`
- **Next Gate:** `W07-A4H-ASSISTED-FIRST-PARTY-COLLECTION-PIPELINE-CHATGPT-AUDIT`
- **Frozen 60-POI Manifest (Single Authority):** `data/evaluation/w07/w07_review_target_60_pois_v1.json` (`b4be35d96ff503c61986674a6b3eb37b993484c0dc121434772184a2b089ed2b`)
- **Assisted Intake CSV Template:** `data/templates/w07_assisted_first_party_review_template_v1.csv`
- **Assisted Candidate Output JSONL (gitignored):** `data/restricted/w07_reviews/w07_assisted_candidate_reviews_v1.jsonl`
- **Optional Restricted Identity Map (gitignored):** `data/restricted/w07_reviews/contributors/contributor_identity_map.csv`
- **Optional Restricted Consent Evidence Folder (gitignored):** `data/restricted/w07_reviews/consent_evidence/`
- **Combined First-Party Progress Artifact:** `data/evaluation/w07/w07_first_party_collection_progress_v1.json`

---

## 1. Provenance Separation & No Fake Form Submissions

`ASSISTED_FIRST_PARTY_COLLECTION` is a legitimate parallel first-party channel alongside W07-A3 Google Forms (`DIRECT_GOOGLE_FORM`).

| Channel | `source` | `provenance` | Candidate JSONL |
| :--- | :--- | :--- | :--- |
| **Google Forms (W07-A3)** | `first_party_contributor_form_v1` | `FIRST_PARTY_ACADEMIC_CONTRIBUTOR_CONSENT_V1` | `data/restricted/w07_reviews/w07_canonical_reviews_v1.jsonl` |
| **Assisted Collection (W07-A4H)** | `assisted_first_party` | `FIRST_PARTY_ASSISTED_COLLECTION_CONSENT_V1` | `data/restricted/w07_reviews/w07_assisted_candidate_reviews_v1.jsonl` |

### Strict Operational Rules
1. **Contributor must have personally visited/directly experienced the POI.**
2. **Never submit assisted reviews into the Google Forms** pretending to originate from different browser sessions.
3. **Never invent, rewrite, paraphrase with AI (ChatGPT/Gemini/Claude), or multiply one review into several reviews.**
4. **Keep Google Forms candidate JSONL and Assisted candidate JSONL separate** (W07-A5 will perform controlled merge & deduplication).

---

## 2. Step-by-Step Owner Workflow (Zero Python Editing Required)

1. **Ask contributor which target POIs they genuinely visited** from the 60 canonical POIs in Hà Nội, Đà Nẵng, or Hạ Long (see Section 8 table below).
2. **Assign or reuse a pseudonymous `contributor_code`** (`W07C001`, `W07C002`, `W07C003`, ...). The same person **must** keep the same `contributor_code` across all POIs they review. One contributor may review multiple POIs they genuinely visited, but at most **one** review per `(contributor_code, poi_id)`.
3. **Ask for their integer rating (`1` to `5`)** for each visited POI.
4. **Collect their review verbatim** (via Zalo, Messenger, direct chat, in-person interview, or phone conversation).
5. **Ask for optional `visit_period`** (`YYYY-MM` like `2025-08` or `YYYY-Q1..Q4` like `2025-Q3`).
6. **Send the Vietnamese consent script** (Section 4 below).
7. **Obtain explicit written/digital consent** (`"Tôi đồng ý"` or `"Đồng ý"`). Never infer consent from silence.
8. **If collector transcribed an oral review**, send the exact final text back to the contributor (Section 5 below) and wait for their explicit final-text approval before setting `review_text_approved = true`.
9. **Enter one CSV row per POI** into your local copy `data/restricted/w07_reviews/raw_assisted/assisted_reviews.csv` (copied from `data/templates/w07_assisted_first_party_review_template_v1.csv`).
10. **Run the deterministic assisted importer:**
    ```bash
    python scripts/import_w07_assisted_reviews_v1.py --import-csv data/restricted/w07_reviews/raw_assisted/assisted_reviews.csv
    ```
11. **Run the W07-A2 corpus validator on the assisted candidate JSONL:**
    ```bash
    python scripts/validate_w07_review_corpus_v1.py --validate-jsonl data/restricted/w07_reviews/w07_assisted_candidate_reviews_v1.jsonl
    ```
12. **Update the combined first-party progress tracker:**
    ```bash
    python scripts/import_w07_assisted_reviews_v1.py --write-progress
    ```

---

## 3. Copy-Paste Vietnamese Recruitment Message

> “Bọn mình đang làm đồ án GoMate về gợi ý du lịch. Nếu bạn từng đi một trong các địa điểm trong danh sách, mình muốn xin đánh giá thật của bạn (1–5 điểm + vài câu cảm nhận). Nội dung sẽ ẩn danh và chỉ dùng cho đồ án/nghiên cứu. Chỉ đánh giá địa điểm bạn thực sự từng trải nghiệm.”

---

## 4. Copy-Paste Vietnamese Consent Script

> “Bạn xác nhận rằng bạn đã trực tiếp đến/trải nghiệm địa điểm này, nội dung đánh giá là ý kiến của chính bạn, không sao chép từ Google Maps/Tripadvisor/Booking/Agoda/Foody và không dùng AI (ChatGPT, Gemini, Claude). Việc tham gia là hoàn toàn tự nguyện và bạn đồng ý cho đồ án GoMate sử dụng nội dung này dưới dạng ẩn danh cho nghiên cứu, đánh giá và demo học thuật phi thương mại. Nếu đồng ý, bạn nhắn giúp mình: ‘Tôi đồng ý’ hoặc ‘Đồng ý’ nhé.”

---

## 5. Copy-Paste Final-Text Approval Script (Mandatory for Oral Transcription Modes)

When `capture_mode` is `COLLECTOR_TRANSCRIBED_VERBATIM` or `COLLECTOR_TRANSCRIBED_AND_CONTRIBUTOR_APPROVED`, send the transcribed wording back to the contributor before importing:

> “Mình vừa ghi lại nguyên văn đánh giá của bạn cho địa điểm [Tên POI] (Điểm: [1–5]/5) như sau:
> ‘[Nội dung đánh giá cuối cùng]’
> Bạn kiểm tra giúp mình xem nội dung đã đúng hoàn toàn ý của bạn chưa, và nhắn xác nhận ‘Tôi duyệt nội dung và đồng ý’ để mình lưu vào bộ dữ liệu nghiên cứu ẩn danh nhé.”

---

## 6. Supported Values Reference (`w07_assisted_first_party_review_template_v1.csv`)

| Column | Required | Allowed / Expected Values |
| :--- | :--- | :--- |
| `contributor_code` | **Yes** | Pseudonymous code `W07C001`, `W07C002`, ... (`^W07C\d{3,6}$`). Never put real name, email, or phone. |
| `poi_id` | **Yes** | Exact canonical UUID from the 60-POI manifest (do NOT use POI name). |
| `city` | **Yes** | `Hà Nội`, `Đà Nẵng`, or `Hạ Long` (must match `manifest[poi_id].city`). |
| `rating` | **Yes** | Integer `1`, `2`, `3`, `4`, or `5`. |
| `review_text` | **Yes** | Authentic review text (`>= 20` chars and `>= 5` words recommended; zero phone/email PII). |
| `visit_period` | Optional | `YYYY-MM` (e.g. `2025-08`) or `YYYY-Q1..Q4` (e.g. `2025-Q3`). |
| `collection_channel` | **Yes** | `ZALO`, `MESSENGER`, `DIRECT_CHAT`, `IN_PERSON_INTERVIEW`, or `PHONE_WITH_WRITTEN_CONFIRMATION`. |
| `capture_mode` | **Yes** | `CONTRIBUTOR_WRITTEN_VERBATIM`, `COLLECTOR_TRANSCRIBED_VERBATIM`, or `COLLECTOR_TRANSCRIBED_AND_CONTRIBUTOR_APPROVED`. (Forbidden modes `COLLECTOR_PARAPHRASED`, `AI_REWRITTEN`, `AI_GENERATED`, `COPIED_ONLINE_REVIEW` are rejected). |
| `review_text_approved` | **Yes** | `true` (may be implied for `CONTRIBUTOR_WRITTEN_VERBATIM` when `consent_confirmed=true`; **explicit `true` mandatory** for transcription modes, otherwise rejected with `REJECT_TEXT_NOT_CONTRIBUTOR_APPROVED`). |
| `consent_confirmed` | **Yes** | `true`, `Tôi đồng ý`, or `Đồng ý`. |
| `consent_timestamp` | **Yes** | ISO-8601 or `YYYY-MM-DD HH:MM:SS` timestamp when consent was given. |
| `consent_evidence_type` | **Yes** | `CHAT_WRITTEN_CONSENT`, `DIGITAL_TEXT_CONSENT`, or `IN_PERSON_WRITTEN_CONSENT`. (Verbal-only consent without written confirmation is rejected). |
| `consent_evidence_ref` | **Yes** | Local reference token (e.g. `zalo_thread_w07c001_20261102_01`). Hashed with SHA-256 into `consent_record_id`; never published in the scientific JSONL. |
| `collector_code` | **Yes** | Collector pseudonymous code (e.g. `OWNER_01`, `TEAM_01`). |
| `collected_at` | **Yes** | ISO-8601 or `YYYY-MM-DD HH:MM:SS` timestamp when recorded into the template. |

### Example Synthetic TEST FIXTURE Row (For Format Illustration Only — Do Not Import)

```csv
contributor_code,poi_id,city,rating,review_text,visit_period,collection_channel,capture_mode,review_text_approved,consent_confirmed,consent_timestamp,consent_evidence_type,consent_evidence_ref,collector_code,collected_at
W07C001,698ee756-6062-5f47-955b-bdf458682e57,Hà Nội,5,"TEST_FIXTURE_ONLY: Khu vực quảng trường Ba Đình rộng rãi, sạch sẽ, xếp hàng buổi sáng rất trật tự.",2025-10,ZALO,CONTRIBUTOR_WRITTEN_VERBATIM,true,Tôi đồng ý,2026-11-02T09:00:00Z,CHAT_WRITTEN_CONSENT,zalo_msg_w07c001_001,OWNER_01,2026-11-02T09:05:00Z
```

---

## 7. Optional Restricted Identity Map (Gitignored)

If the Project Owner needs to remember which real person corresponds to `W07C001`, `W07C002`, ..., store a local-only file at:

`data/restricted/w07_reviews/contributors/contributor_identity_map.csv`

- Covered by `data/restricted/*` in `.gitignore` and `data/restricted/.gitignore`.
- Must **never** be committed to Git, **never** enter the scientific corpus, and is **never** required by CI.

---

## 8. Canonical 60-POI Lookup Table (Bound to W07-A2 Manifest)

| # | City | Category Group | Raw Category | `poi_id` | Name | `osm_id` | `overture_id` | Min Reviews |
|---:|---|---|---|---|---|---|---|---:|
| 1 | Hà Nội | `attractions_culture` | `attraction` | `698ee756-6062-5f47-955b-bdf458682e57` | Lăng Chủ tịch Hồ Chí Minh | `way/37625751` | `null` | 5 |
| 2 | Hà Nội | `attractions_culture` | `culture` | `b799793b-fb40-5bc2-9e67-6af92caeabe9` | Hoàng thành Thăng Long | `relation/21425205` | `null` | 5 |
| 3 | Hà Nội | `attractions_culture` | `culture` | `0938eb59-ee1c-5879-a798-58b5fdd07bce` | Nhà tù Hỏa Lò | `way/340128580` | `null` | 5 |
| 4 | Hà Nội | `attractions_culture` | `culture` | `44115e3a-6094-5bcd-b53c-0e3a596b3aff` | Đền Ngọc Sơn | `way/178995262` | `null` | 5 |
| 5 | Hà Nội | `attractions_culture` | `culture` | `e3fe1f1a-f524-55cf-9d83-903e427d0ba4` | Chùa Trấn Quốc | `way/220302249` | `null` | 5 |
| 6 | Hà Nội | `attractions_culture` | `culture` | `f0d424bd-f722-540f-8964-5e6fd8875b56` | Bảo tàng Dân tộc học Việt Nam | `way/339936730` | `e55bab3c-c110-4ba6-a005-5c43986a6095` | 5 |
| 7 | Hà Nội | `attractions_culture` | `culture` | `cad64db8-cd74-58fe-ad94-329e0d8110e1` | Nhà thờ Lớn | `way/28912942` | `null` | 5 |
| 8 | Hà Nội | `restaurants_cafes_markets` | `restaurant` | `afb3793b-7227-4645-a68a-3647c7468638` | Sen Tây Hồ | `node/443000681` | `e8077687-eb1f-44ff-b544-9e7ae8ccdc1e` | 5 |
| 9 | Hà Nội | `restaurants_cafes_markets` | `restaurant` | `acb22336-1124-49d5-a279-6357c2b2b445` | Quán Ăn Ngon - Phan Bội Châu | `node/721836715` | `null` | 5 |
| 10 | Hà Nội | `restaurants_cafes_markets` | `restaurant` | `5350dd97-2f75-45fc-9fc1-1979b08670f7` | Pho 10 | `node/773601261` | `ff9a223f-952f-4d51-b7a9-b90998668554` | 5 |
| 11 | Hà Nội | `restaurants_cafes_markets` | `restaurant` | `b0641225-0f38-4bcc-9f4c-34f65fa50d45` | Cửa Hàng Bánh Tôm Hồ Tây | `node/310727632` | `null` | 5 |
| 12 | Hà Nội | `restaurants_cafes_markets` | `cafe` | `5bd45eb7-a691-4426-9691-a5a00f38d1ad` | Highlands Coffee | `node/442977691` | `e8f37b82-c15a-49d1-ad85-994b4b10f150` | 5 |
| 13 | Hà Nội | `restaurants_cafes_markets` | `cafe` | `4146f2b7-8289-4309-b7e6-60ba7de3470e` | Cà Phê Nola | `node/721836730` | `null` | 5 |
| 14 | Hà Nội | `restaurants_cafes_markets` | `cafe` | `a2fc15de-d609-4d4f-abf1-9779d57901a6` | Cà Phê Kafa | `node/423736651` | `null` | 5 |
| 15 | Hà Nội | `hotels` | `hotel` | `5e92e89d-8524-4792-862a-6dfce0994862` | Sheraton Hanoi | `node/922396410` | `80ceecb4-b812-4b29-a332-e22dc1a21fb8` | 5 |
| 16 | Hà Nội | `hotels` | `hotel` | `9a96e0a0-e040-4e16-a3f2-682ca373dd8e` | Somerset Grand Hanoi | `node/442033049` | `165cef5b-70ba-41d9-8314-4b54d979379d` | 5 |
| 17 | Hà Nội | `nature_beach` | `nature` | `766656bb-c7e0-555d-9963-d3132f0de086` | Công viên Thống Nhất | `way/37933849` | `null` | 5 |
| 18 | Hà Nội | `nature_beach` | `nature` | `1f9c2b46-e032-5cbc-a9dc-dc68c435c594` | Công viên Thủ Lệ | `way/28945667` | `null` | 5 |
| 19 | Hà Nội | `nature_beach` | `nature` | `a2037ceb-201f-5c45-a596-af795a399e60` | Công viên Lê-nin | `way/185540946` | `3421b671-b891-408e-943f-1278e1a46c94` | 5 |
| 20 | Hà Nội | `other_tourism` | `nightlife` | `9b08dfe9-6f97-4d4b-94f6-f3548efd696c` | Le Pub | `node/969250576` | `null` | 5 |
| 21 | Đà Nẵng | `attractions_culture` | `attraction` | `9974ff88-5418-5867-ae49-1b72e0f0861f` | Cầu Rồng | `way/694831926` | `null` | 5 |
| 22 | Đà Nẵng | `attractions_culture` | `attraction` | `6f758ad7-5685-57b5-9913-d28e15bdb7c5` | Ngũ Hành Sơn | `relation/8552348` | `null` | 5 |
| 23 | Đà Nẵng | `attractions_culture` | `culture` | `a24d48ff-59d6-5e53-af77-36448e60d1cc` | Bảo tàng Nghệ thuật Điêu khắc Chăm Đà Nẵng | `way/302872188` | `null` | 5 |
| 24 | Đà Nẵng | `attractions_culture` | `temple` | `5fc0994a-e578-4a25-b375-7f079e6dc3ba` | Chùa Linh Ứng | `way/1205388457` | `b9ad130e-8f19-4dcb-92a7-638573a3f62d` | 5 |
| 25 | Đà Nẵng | `attractions_culture` | `attraction` | `2f389152-5676-54be-b812-a1d561b7df15` | Cầu Sông Hàn | `node/7276380289` | `null` | 5 |
| 26 | Đà Nẵng | `attractions_culture` | `culture` | `cb6cce60-8270-5f43-b9f7-42de2d7d7da3` | Bảo tàng Đà Nẵng | `way/1368599361` | `null` | 5 |
| 27 | Đà Nẵng | `attractions_culture` | `attraction` | `a302989c-08f1-5ca2-8022-a84c1a424018` | Chợ Cồn | `way/204790989` | `null` | 5 |
| 28 | Đà Nẵng | `restaurants_cafes_markets` | `restaurant` | `62a874a9-13e2-44d2-95b5-30e980b98965` | Bánh Xèo Bà Dưỡng | `node/4541527689` | `c732f0d5-911d-4d9f-93b2-51c886f4fe0b` | 5 |
| 29 | Đà Nẵng | `restaurants_cafes_markets` | `restaurant` | `61639da8-996a-43df-b6d3-928b6bdd70b9` | My Quang Bà Mua | `node/7210857787` | `da92232b-8e79-4082-84b0-6a35263af4df` | 5 |
| 30 | Đà Nẵng | `restaurants_cafes_markets` | `restaurant` | `fd118580-b5da-467d-9873-0116ba435f37` | Nhà hàng hải sản Bé Anh | `node/5485483822` | `df8dc91d-1790-4600-a518-31bec995467a` | 5 |
| 31 | Đà Nẵng | `restaurants_cafes_markets` | `market` | `9a2ca486-437d-4044-8541-d34d911d4fb4` | Chợ Đêm Sơn Trà | `way/1556362196` | `a310c792-65d8-4115-9df6-ddf54babd1a8` | 5 |
| 32 | Đà Nẵng | `restaurants_cafes_markets` | `market` | `c2afbb07-aaf9-47c1-9877-d17e64422066` | Chợ Bắc Mỹ An | `way/118614280` | `4d3dbac0-aae6-4960-8b89-d06c52fe21f5` | 5 |
| 33 | Đà Nẵng | `restaurants_cafes_markets` | `market` | `7ff87c59-62f1-4509-95f4-e83796b9a35c` | Vincom Plaza | `way/693393717` | `67b0a6b0-f6e8-477d-8517-ef73c56752f7` | 5 |
| 34 | Đà Nẵng | `restaurants_cafes_markets` | `cafe` | `8ebf0429-fabb-4701-bbc1-cb2fea86d587` | Ca Phe 83 | `node/729406392` | `1b27afcb-daa1-4977-bcd5-cc5327c08c64` | 5 |
| 35 | Đà Nẵng | `hotels` | `hotel` | `4608034c-6c43-4d54-a542-ead8e23b1338` | InterContinental Danang Sun Peninsula Resort | `way/360113559` | `0d91068a-7ee8-4d97-ad32-a075a23d30fd` | 5 |
| 36 | Đà Nẵng | `hotels` | `hotel` | `a32ce1b4-126b-4544-b5ea-4a7edbab6a0a` | Furama Resort | `way/485212452` | `82f95e1f-7bf8-40df-a3ed-6f92a4a847f3` | 5 |
| 37 | Đà Nẵng | `nature_beach` | `beach` | `2f202acf-c2bb-526a-9803-aaca142ffdad` | Bãi biển Mỹ Khê | `relation/19000664` | `null` | 5 |
| 38 | Đà Nẵng | `nature_beach` | `beach` | `49d739b9-e868-5391-9f80-bf9bed803b0f` | Bãi tắm Non Nước | `way/1204900824` | `null` | 5 |
| 39 | Đà Nẵng | `nature_beach` | `nature` | `b5ea1253-6b6a-5f5a-b910-5ef18cd29c94` | Ban Co Peak | `node/1538334281` | `null` | 5 |
| 40 | Đà Nẵng | `other_tourism` | `entertainment` | `987f490f-b1c7-42cf-b92e-300d57fd8d5f` | Sun World Bà Nà Hills | `way/359114064` | `null` | 5 |
| 41 | Hạ Long | `attractions_culture` | `attraction` | `ade2140c-7945-4044-b99a-b1a028edce9e` | Vịnh Hạ Long | `node/2707025319` | `null` | 5 |
| 42 | Hạ Long | `attractions_culture` | `museum` | `8f2b5a69-1293-4efe-8fc5-3a74193edd0f` | Bảo tàng Quảng Ninh | `node/5395107122` | `bd078edf-ad58-4f6c-9016-adf65c90e5eb` | 5 |
| 43 | Hạ Long | `attractions_culture` | `attraction` | `9a979427-a0bb-421d-b75f-2a6ee79b120b` | Động Thiên Cung | `node/4730928605` | `null` | 5 |
| 44 | Hạ Long | `attractions_culture` | `attraction` | `9fbcb0b4-27bc-4482-a8e3-8be6e3c72677` | Hang Đầu Gỗ | `node/4730928606` | `null` | 5 |
| 45 | Hạ Long | `attractions_culture` | `attraction` | `77af14b6-85ac-4c91-873a-e7da27d555f4` | Hang Luồn Cave Entrance | `node/3560283504` | `null` | 5 |
| 46 | Hạ Long | `attractions_culture` | `attraction` | `88652ea2-61a6-4022-85e5-84a0eb48d3f9` | Hòn Đỉnh Hương | `node/10821152105` | `null` | 5 |
| 47 | Hạ Long | `attractions_culture` | `attraction` | `871a6ee7-1d46-49bb-957a-ff50260b1f3b` | Ha Long International Cruise Port | `node/7044140886` | `527ebd9f-445a-4059-a815-0d988c0925a2` | 5 |
| 48 | Hạ Long | `restaurants_cafes_markets` | `restaurant` | `b37d68ee-0cb3-49f0-a399-cac4c8e2732c` | Nhà hàng Hồng Hạnh 3 | `node/12998514201` | `92ed9717-ce41-4e8f-ab25-52e369cd88be` | 5 |
| 49 | Hạ Long | `restaurants_cafes_markets` | `restaurant` | `7d01af19-10bc-4679-8cfa-4396209dece4` | Nhà hàng Ngọc Phương Nam 1 | `node/12998531301` | `04dda4d2-9d22-4516-a651-73c774b61663` | 5 |
| 50 | Hạ Long | `restaurants_cafes_markets` | `restaurant` | `065f8492-2ab3-4ea0-ae8f-9cc6f8c18ae5` | Nhà hàng Buffet Sen Á Đông | `node/12998779901` | `0772c46b-7aa9-40a0-b403-78dec2591927` | 5 |
| 51 | Hạ Long | `restaurants_cafes_markets` | `market` | `96523873-1b85-4d2f-b85c-cb3f5593091b` | Chợ Cái Dăm | `way/674641659` | `9b6e3c9a-d263-4e5d-8ff7-7d7bddc1ffef` | 5 |
| 52 | Hạ Long | `restaurants_cafes_markets` | `market` | `6215446b-2fdd-4014-aacf-23de6e45e264` | Chợ Hạ Long II | `way/673558390` | `null` | 5 |
| 53 | Hạ Long | `restaurants_cafes_markets` | `cafe` | `b57b3f7d-9704-44b0-8139-19bea1998391` | Sữa chua trân châu Hạ Long cơ sở 00 | `node/13009250202` | `null` | 5 |
| 54 | Hạ Long | `restaurants_cafes_markets` | `cafe` | `85303289-9746-4a42-b0f0-a555ce2bfd0e` | Highlands Coffee | `node/13183486704` | `6039522b-f82a-4a1d-88f3-09beca7172ab` | 5 |
| 55 | Hạ Long | `hotels` | `hotel` | `75a3fbd1-a24e-43c6-820a-72f95ebc05c0` | Vinpearl Ha Long resort | `node/4330722989` | `9ed3a2e3-60a3-4df0-acd8-83185f57a281` | 5 |
| 56 | Hạ Long | `hotels` | `hotel` | `9740c851-5b06-432c-a243-071ad0906494` | Novotel Ha Long | `way/676720191` | `893209f5-1d13-479f-b7d7-6630b1f3fe57` | 5 |
| 57 | Hạ Long | `nature_beach` | `park` | `708ee182-c879-477c-b920-516e2c99b0a6` | Công viên Lán Bè | `way/673096986` | `null` | 5 |
| 58 | Hạ Long | `nature_beach` | `park` | `0931b06b-4563-4af0-a3a4-75f1ad8392ee` | Vườn hoa | `way/673096992` | `null` | 5 |
| 59 | Hạ Long | `nature_beach` | `park` | `8fe33554-7a07-4eb2-870f-8af643d8c728` | Vườn hoa Thị trấn Trới | `way/677419454` | `null` | 5 |
| 60 | Hạ Long | `other_tourism` | `entertainment` | `1a95430d-289d-4663-91b8-ae64ede4f9a4` | Sunworld | `relation/18623673` | `null` | 5 |
