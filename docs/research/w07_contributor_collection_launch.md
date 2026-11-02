# W07-A3 — Contributor Review Collection Launch Plan & Owner Action Pack (v1, Corrective 01)

- **Task ID:** `W07-A3` (`GOOGLE FORMS RUNTIME COMPATIBILITY CORRECTIVE 01`)
- **Authoritative Base:** `develop@82d2a0567f98c5e2ca368d2a2760e1029b709a56`
- **Previous Gate:** `W07-A3-CONTRIBUTOR-COLLECTION-LAUNCH-CHATGPT-AUDIT = HOLD-CORRECTIVE`
- **Next Gate:** `W07-A3-CONTRIBUTOR-COLLECTION-LAUNCH-CORRECTIVE-01-CHATGPT-AUDIT`
- **Bound W07-A2 Manifest SHA256:** `b4be35d96ff503c61986674a6b3eb37b993484c0dc121434772184a2b089ed2b`
- **Form Definition Artifact:** `data/evaluation/w07/w07_contributor_collection_form_definition_v1.json` (`9c17cfc51c41295c8338b40544324454a36a7276bb2339edd3a0b59c88c6de8a`)
- **Apps Script Generator (`tools/w07/create_w07_contributor_forms.gs`) Lifecycle Status:** `STATICALLY_VERIFIED_OWNER_RUNTIME_PREFLIGHT_REQUIRED` (`5e87dcf74d2bc4840792701bbd852c75781ef6ba938ac8c1eacad6d2a430be71`)
- **Required Owner Runtime Gate:** `OWNER_GOOGLE_FORMS_RUNTIME_PREFLIGHT`
- **Progress Tracker Artifact:** `data/evaluation/w07/w07_review_collection_progress_v1.json` (`a7eb47e50735a6f184f4ae717976b7a8bf7d1258a6d4763031c62fd691d38e70`)

---

## 1. Two-Gate Launch Architecture: Static Engineering Gate vs. Owner Runtime Gate

A passing Python CI proves static schema/importer/validator correctness, **not** live Google Apps Script or Google account runtime behavior. Real contributor collection is therefore governed by two sequential gates and begins **only after both pass**:

### 1.1 Static Engineering Gate (Repository / CI)
- Three city-specific Google Forms definitions (`Hà Nội = 20 POIs`, `Đà Nẵng = 20 POIs`, `Hạ Long = 20 POIs`) generated programmatically from `data/evaluation/w07/w07_review_target_60_pois_v1.json` with fail-closed manifest SHA256 binding (`b4be35d96ff503c61986674a6b3eb37b993484c0dc121434772184a2b089ed2b`).
- Optional Owner-only Google Apps Script utility (`tools/w07/create_w07_contributor_forms.gs`) statically verified to:
  - avoid deprecated `FormApp` login APIs;
  - configure `setCollectEmail(false)`, `setLimitOneResponsePerUser(false)`, and `setShowLinkToRespondAgain(true)`;
  - guard advanced responder publishing behind `form.supportsAdvancedResponderPermissions() == true` (`form.setPublished(true)`).
- Deterministic CSV importer (`scripts/import_w07_contributor_reviews_v1.py`), W07-A2 validator (`scripts/validate_w07_review_corpus_v1.py`), offline coverage/pilot tracker (`scripts/report_w07_review_collection_progress.py`), and offline unit tests passing in exact-head GitHub Actions CI.
- Generator lifecycle status at this stage remains:
  `STATICALLY_VERIFIED_OWNER_RUNTIME_PREFLIGHT_REQUIRED`.

### 1.2 Owner Runtime Gate (`OWNER_GOOGLE_FORMS_RUNTIME_PREFLIGHT`)
After PR `#81` is audited and merged into `develop` — and **before sharing any form links publicly with contributors** — the Project Owner must execute the 10-step runtime preflight in their actual Google account:

1. Run `createW07ContributorForms` from `tools/w07/create_w07_contributor_forms.gs` in https://script.google.com (or create the 3 forms via the Workspace fallback in Section 1.3).
2. Confirm all **3 city forms** (`Hà Nội`, `Đà Nẵng`, `Hạ Long`) were created and inspect the Execution Log (`form_title`, `form_id`, `google_form_id`, `edit_url`, `published_url`, `supportsAdvancedResponderPermissions`, `publish_action_taken`, `collect_email_configuration`, `limit_one_response_configuration`).
3. Open each form's `published_url` (responder URL) in an **incognito / private browser window**.
4. Confirm the form opens without mandatory Google account login where account policy permits.
5. Confirm contributor email address is **not** collected.
6. Confirm there is **no** name, phone number, email, social handle, address, or student/national ID question.
7. Confirm **exactly 20 POIs** appear in that city's dropdown (`1. Chọn địa điểm (POI) bạn đã trực tiếp đến trải nghiệm`).
8. Confirm the rating (`1–5`), review text, optional visit-period, and consent questions exist.
9. Confirm the consent checkbox question (`5. Cam kết tính xác thực và đồng thuận nghiên cứu học thuật`) is **required**.
10. Confirm `"Submit another response"` (`Gửi phản hồi khác`) is enabled and available.

- **Gate Requirement:** `OWNER_GOOGLE_FORMS_RUNTIME_PREFLIGHT = PASS` is required before distributing forms to real contributors.
- **Smoke-Test Isolation Rule:** No synthetic smoke response may ever enter `data/restricted/w07_reviews/w07_canonical_reviews_v1.jsonl`. If form-runtime smoke testing needs a test submission, use a clearly separate disposable TEST form or delete the test response in Google Forms before exporting CSVs.

### 1.3 Google Workspace Policy Fallback
If the Project Owner's organizational Google Workspace policy forces sign-in, email collection, or domain-restricted responder access:
- Do **not** attempt to bypass organizational policy.
- **Allowed Fallbacks:**
  1. Use a personal `@gmail.com` Google account where public anonymous responder access is permitted; **or**
  2. Manually create the three forms using the frozen specification in `data/evaluation/w07/w07_contributor_collection_form_definition_v1.json`.
- If any raw identity columns nevertheless appear in a downloaded CSV export, the raw CSV remains git-ignored inside `data/restricted/w07_reviews/raw_forms/` and `scripts/import_w07_contributor_reviews_v1.py` automatically strips all identity columns before constructing scientific records.

---

## 2. Pilot & Scientific Minimum Gates

- **Pilot Gate (`COLLECTION_PIPELINE_PILOT_READY`):**
  - `>= 30` accepted genuine reviews total;
  - `>= 10` accepted reviews in `Hà Nội`, `>= 10` in `Đà Nẵng`, `>= 10` in `Hạ Long`;
  - `>= 15` distinct canonical POIs covered;
  - valid consent (`consent_record_id`) for 100% of accepted rows;
  - `0` synthetic/LLM reviews;
  - `0` quarantined PII reviews counted in accepted reviews;
  - importer idempotency verified.
- **Pilot Reviews Count Toward Final Corpus:** Every pilot review that passes normal validation is retained in `data/restricted/w07_reviews/w07_canonical_reviews_v1.jsonl` and counts toward the final 300-review corpus.
- **Scientific Minimum Gate (`CORPUS_SCIENTIFIC_MINIMUM_READY`):** Remains strictly separate from `COLLECTION_PIPELINE_PILOT_READY` and requires all `60` canonical POIs covered with `>= 5` accepted reviews each (`>= 300` accepted reviews total, `100` minimum per city).

---

## 3. Targeted Recruitment Strategy & Practical Collection Scenarios

### 3.1 City-Familiarity Targeted Recruitment
Distribute the three city-specific forms to contributors based on the cities they have personally visited:
- **Group 1 — Hà Nội Form (`w07_form_hanoi_v1`):** Contributors who have lived in or visited Hà Nội.
- **Group 2 — Đà Nẵng Form (`w07_form_danang_v1`):** Contributors who have travelled to or lived in Đà Nẵng.
- **Group 3 — Hạ Long Form (`w07_form_halong_v1`):** Contributors who have travelled to Vịnh Hạ Long / Quảng Ninh.

> **Ethical & Scientific Rule:** Contributors must **only** review POIs they have personally visited or directly experienced. Never pressure a contributor into reviewing unknown places.

### 3.2 Practical Collection Scenarios (Reaching 300 Valid Reviews)
- **Scenario A (Broad Light Participation):** `~100 contributors × ~3 genuine POI reviews average = ~300 accepted reviews`.
- **Scenario B (Moderate Travel-Familiar Participation):** `~60 contributors × ~5 genuine POI reviews average = ~300 accepted reviews`.
- **Scenario C (Hybrid Targeted Contributors + Approved Public Source):** Targeted first-party contributors prioritized for under-covered POIs combined with any later explicitly approved, source-ID-bound public research dataset.

Completion is governed strictly by `data/evaluation/w07/w07_review_collection_progress_v1.json`, never by contributor headcount.

### 3.3 Active Sampling Priority Order (Preventing Popular-POI Skew)
Consult `exact_under_covered_pois` in `data/evaluation/w07/w07_review_collection_progress_v1.json` after each import batch and prioritize recruitment in this exact order:
1. **Priority 1 — POIs with `0` accepted reviews** (`PRIORITY_1_ZERO_REVIEWS`);
2. **Priority 2 — POIs with `1–4` accepted reviews** (`PRIORITY_2_BELOW_FIVE_REVIEWS`);
3. **Priority 3 — City deficits**;
4. **Priority 4 — Category-stratum deficits** (`attractions_culture = 21`, `restaurants_cafes_markets = 21`, `hotels = 6`, `nature_beach = 9`, `other_tourism = 3`).

Once a POI reaches **`5` accepted reviews**, the tracker marks it `STOP_ACTIVE_RECRUITMENT_MIN_5_MET`. Stop actively soliciting for that POI unless broader preferred corpus collection is desired.

---

## 4. Owner Action Pack (Step-by-Step Operational Guide)

No Python editing is required. Follow these 12 steps in order after PR `#81` is merged:

### Step 1 — Create the Three Google Forms & Run Owner Preflight (`OWNER_GOOGLE_FORMS_RUNTIME_PREFLIGHT`)
- **Option A (Automatic Setup via Google Apps Script):**
  1. Open https://script.google.com while signed into your personal Google account (or Workspace account).
  2. Click **New project**, replace `Code.gs` with the contents of `tools/w07/create_w07_contributor_forms.gs`, select `createW07ContributorForms`, and click **Run**.
  3. Inspect the Execution Log and run the 10-step `OWNER_GOOGLE_FORMS_RUNTIME_PREFLIGHT` checklist (Section 1.2) in an incognito browser window.
- **Option B (Workspace Policy / Manual Fallback):**
  - If Workspace policy restricts external responders or forces sign-in/email collection, switch to a personal Google account or create the three forms manually from `data/evaluation/w07/w07_contributor_collection_form_definition_v1.json`, then verify all 10 preflight items.

### Step 2 — Exact Form Titles
1. **Hà Nội (`w07_form_hanoi_v1`):** `[GoMate W07] Đánh giá địa điểm du lịch thực tế — Hà Nội (20 POI)`
2. **Đà Nẵng (`w07_form_danang_v1`):** `[GoMate W07] Đánh giá địa điểm du lịch thực tế — Đà Nẵng (20 POI)`
3. **Hạ Long (`w07_form_halong_v1`):** `[GoMate W07] Đánh giá địa điểm du lịch thực tế — Hạ Long (20 POI)`

### Step 3 — Exact Form Settings (Privacy-First)
- **Collect email addresses (`setCollectEmail(false)`):** `Do not collect` (`OFF`)
- **Limit to 1 response (`setLimitOneResponsePerUser(false)`):** `OFF`
- **Show link to submit another response (`setShowLinkToRespondAgain(true)`):** `ON`
- **Advanced responder publishing:** If `form.supportsAdvancedResponderPermissions() == true`, `form.setPublished(true)` is called automatically; in the Google Forms UI, verify responder access is open (`Anyone with the link`).
- Zero questions asking for real name, email, phone number, social handle, home address, or student ID.

### Step 4 — Form Link Placeholders (Record Your Live Links Locally After Preflight)
- **Hà Nội Form Responder URL:** `<PASTE_HANOI_GOOGLE_FORM_RESPONDER_URL_HERE>`
- **Đà Nẵng Form Responder URL:** `<PASTE_DANANG_GOOGLE_FORM_RESPONDER_URL_HERE>`
- **Hạ Long Form Responder URL:** `<PASTE_HALONG_GOOGLE_FORM_RESPONDER_URL_HERE>`

### Step 5 — How to Distribute (Only After `OWNER_GOOGLE_FORMS_RUNTIME_PREFLIGHT = PASS`)
- Share the city-specific responder link with contributors who have visited that city.
- Remind contributors:
  1. **1 submission = 1 review for 1 POI** they personally visited;
  2. Submit again using *"Submit another response"* for additional POIs they have experienced;
  3. Write in their own words (no copying from Google Maps/Tripadvisor/Booking/Agoda/Foody, no ChatGPT/Gemini/Claude, and no phone numbers or email addresses inside the review text).

### Step 6 — Where Downloaded CSV Exports Go
Save downloaded CSV exports to these exact git-ignored paths:
- Hà Nội CSV -> `data/restricted/w07_reviews/raw_forms/hanoi_responses.csv`
- Đà Nẵng CSV -> `data/restricted/w07_reviews/raw_forms/danang_responses.csv`
- Hạ Long CSV -> `data/restricted/w07_reviews/raw_forms/halong_responses.csv`

### Step 7 — Exact Import Command
```powershell
python scripts/import_w07_contributor_reviews_v1.py --import-raw-dir
```

### Step 8 — Exact Validation Command
```powershell
python scripts/validate_w07_review_corpus_v1.py --validate-jsonl data/restricted/w07_reviews/w07_canonical_reviews_v1.jsonl
```

### Step 9 — Exact Progress-Report Command
```powershell
python scripts/report_w07_review_collection_progress.py --write
```

### Step 10 — How to Interpret the Tracker (`data/evaluation/w07/w07_review_collection_progress_v1.json`)
- `summary_counts.accepted_review_count`: Total valid reviews currently in the restricted canonical corpus.
- `summary_counts.quarantined_pii_count`: Reviews rejected because `review_text` contained a phone number or email address (`QUARANTINE_PII_REVIEW_TEXT`).
- `pilot_gate_evaluation.COLLECTION_PIPELINE_PILOT_READY`: Turns `true` once all pilot thresholds are met.
- `scientific_minimum_evaluation.CORPUS_SCIENTIFIC_MINIMUM_READY`: Turns `true` only when all `60` POIs have `>= 5` accepted reviews (`>= 300` total).
- `exact_under_covered_pois`: Ordered list of POIs that still need reviews (`0` reviews -> `1–4` reviews -> city deficit -> stratum deficit).
- `poi_coverage_buckets.stop_active_recruitment_pois`: POIs that already have `>= 5` accepted reviews.

### Step 11 — Pilot Target (`COLLECTION_PIPELINE_PILOT_READY`)
- `>= 30` accepted reviews total (`>= 10` in `Hà Nội`, `>= 10` in `Đà Nẵng`, `>= 10` in `Hạ Long`, `>= 15` distinct target POIs, 100% valid consent, `0` synthetic/LLM reviews, `0` quarantined PII reviews counted).

### Step 12 — When to Return to ChatGPT
1. **Now (`W07-A3-CONTRIBUTOR-COLLECTION-LAUNCH-CORRECTIVE-01-CHATGPT-AUDIT`):** Return the Corrective 01 PR return package for audit before merging PR `#81` or distributing forms.
2. **After Merge & Preflight + Pilot Collection:** Once `OWNER_GOOGLE_FORMS_RUNTIME_PREFLIGHT = PASS` and `COLLECTION_PIPELINE_PILOT_READY = true`, return the updated progress report to ChatGPT before scaling to `300 / 60 / >=5`.
