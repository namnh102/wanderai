# W07-A3 — Contributor Review Collection Launch Plan & Owner Action Pack (v1)

- **Task ID:** `W07-A3`
- **Authoritative Base:** `develop@82d2a0567f98c5e2ca368d2a2760e1029b709a56`
- **Previous Gate:** `W07-A2-CANONICAL-REVIEW-CORPUS-INTAKE-POSTMERGE-CHATGPT-AUDIT = PASS`
- **Next Gate:** `W07-A3-CONTRIBUTOR-COLLECTION-LAUNCH-CHATGPT-AUDIT`
- **Bound W07-A2 Manifest SHA256:** `b4be35d96ff503c61986674a6b3eb37b993484c0dc121434772184a2b089ed2b`
- **Form Definition Artifact:** `data/evaluation/w07/w07_contributor_collection_form_definition_v1.json` (`9c17cfc51c41295c8338b40544324454a36a7276bb2339edd3a0b59c88c6de8a`)
- **Progress Tracker Artifact:** `data/evaluation/w07/w07_review_collection_progress_v1.json` (`a7eb47e50735a6f184f4ae717976b7a8bf7d1258a6d4763031c62fd691d38e70`)

---

## 1. Two-Stage Launch & Pilot Strategy

`W07-A3` separates contributor review collection into two operational stages so the pipeline is verified on real first-party submissions before scaling to the full 300-review corpus:

1. **Stage A — Launch Infrastructure (completed in this PR):**
   - Three city-specific Google Forms definitions (`Hà Nội = 20 POIs`, `Đà Nẵng = 20 POIs`, `Hạ Long = 20 POIs`) generated programmatically from `data/evaluation/w07/w07_review_target_60_pois_v1.json` with fail-closed manifest SHA256 binding (`b4be35d96ff503c61986674a6b3eb37b993484c0dc121434772184a2b089ed2b`).
   - Optional Owner-only Google Apps Script utility (`tools/w07/create_w07_contributor_forms.gs`) to create all three Google Forms automatically in the Owner's Google account without paid APIs or stored credentials.
   - Deterministic CSV importer (`scripts/import_w07_contributor_reviews_v1.py`) with identity-column stripping, canonical POI resolution, non-reversible `consent_record_id` generation, idempotent `review_id` generation, and W07-A2 validation.
   - Offline coverage and pilot-gate tracker (`scripts/report_w07_review_collection_progress.py`).
2. **Stage B — Pilot (`COLLECTION_PIPELINE_PILOT_READY`) -> Full Scientific Minimum (`CORPUS_SCIENTIFIC_MINIMUM_READY`):**
   - **Pilot Gate (`COLLECTION_PIPELINE_PILOT_READY`):**
     - `>= 30` accepted genuine reviews total;
     - `>= 10` accepted reviews in `Hà Nội`, `>= 10` in `Đà Nẵng`, `>= 10` in `Hạ Long`;
     - `>= 15` distinct canonical POIs covered;
     - valid consent (`consent_record_id`) for 100% of accepted rows;
     - `0` synthetic/LLM reviews;
     - `0` quarantined PII reviews counted in accepted reviews;
     - importer idempotency verified.
   - **Pilot Reviews Count Toward Final Corpus:** Pilot reviews are **not** throwaway data. Every pilot review that passes validation is stored in `data/restricted/w07_reviews/w07_canonical_reviews_v1.jsonl` and counts directly toward the final 300-review scientific minimum.
   - **Scientific Minimum Gate (`CORPUS_SCIENTIFIC_MINIMUM_READY`):** Remains strictly separate from `COLLECTION_PIPELINE_PILOT_READY` and requires all `60` canonical POIs covered with `>= 5` accepted reviews each (`>= 300` accepted reviews total, `100` minimum per city).

---

## 2. Targeted Recruitment Strategy & Practical Collection Scenarios

### 2.1 City-Familiarity Targeted Recruitment
Do **not** blast a single 60-POI form to random participants. Distribute the three city-specific forms to contributors based on the cities they have personally visited:
- **Group 1 — Hà Nội Form (`w07_form_hanoi_v1`):** Students, colleagues, friends, and travelers who have lived in or visited Hà Nội.
- **Group 2 — Đà Nẵng Form (`w07_form_danang_v1`):** Contributors who have travelled to or lived in Đà Nẵng.
- **Group 3 — Hạ Long Form (`w07_form_halong_v1`):** Contributors who have travelled to Vịnh Hạ Long / Quảng Ninh.

> **Ethical & Scientific Rule:** Contributors must **only** review POIs they have personally visited or directly experienced. Never pressure a contributor to meet a fixed per-person quota or review an unfamiliar place.

### 2.2 Practical Collection Scenarios (Reaching 300 Valid Reviews)
Do not assume every contributor can provide 10 valid reviews. Plan recruitment around realistic yield scenarios:
- **Scenario A (Broad Light Participation):** `~100 contributors × ~3 genuine POI reviews average = ~300 accepted reviews` (plus ~10–15% buffer for short/rejected entries).
- **Scenario B (Moderate Travel-Familiar Participation):** `~60 contributors × ~5 genuine POI reviews average = ~300 accepted reviews`.
- **Scenario C (Hybrid Targeted Contributors + Approved Public Source):** Targeted first-party contributors prioritized for under-covered POIs combined with any later explicitly approved, source-ID-bound public research dataset.

Completion is governed strictly by `data/evaluation/w07/w07_review_collection_progress_v1.json`, never by contributor headcount.

### 2.3 Active Sampling Priority Order (Preventing Popular-POI Skew)
During collection, consult `exact_under_covered_pois` in `data/evaluation/w07/w07_review_collection_progress_v1.json` after each import batch and direct recruitment in this exact order:
1. **Priority 1 — POIs with `0` accepted reviews** (`PRIORITY_1_ZERO_REVIEWS`);
2. **Priority 2 — POIs with `1–4` accepted reviews** (`PRIORITY_2_BELOW_FIVE_REVIEWS`);
3. **Priority 3 — City deficits** (cities furthest below `10` for pilot or `100` for scientific minimum);
4. **Priority 4 — Category-stratum deficits** (`attractions_culture = 21`, `restaurants_cafes_markets = 21`, `hotels = 6`, `nature_beach = 9`, `other_tourism = 3`).

Once a POI reaches **`5` accepted reviews**, the tracker marks it `STOP_ACTIVE_RECRUITMENT_MIN_5_MET`. Stop actively soliciting for that POI so popular landmarks do not accumulate 30 reviews while less-visited POIs remain at zero.

---

## 3. Owner Action Pack (Step-by-Step Operational Guide)

No Python editing is required. Follow these 12 steps in order:

### Step 1 — Create the Three Google Forms
- **Option A (Recommended Automatic Setup via Google Apps Script — 2 minutes):**
  1. Open https://script.google.com while signed into your Google account.
  2. Click **New project**, delete the default snippet in `Code.gs`, and paste the entire contents of `tools/w07/create_w07_contributor_forms.gs`.
  3. Select the function `createW07ContributorForms` in the toolbar and click **Run**.
  4. Approve the standard Google Forms permission prompt for your own account, then copy the three `published_url` links and `edit_url` links printed in the Execution Log.
- **Option B (Manual Setup):**
  - Create three Google Forms matching the exact titles, 20-POI dropdown lists, and 5 questions defined in `data/evaluation/w07/w07_contributor_collection_form_definition_v1.json`.

### Step 2 — Exact Form Titles
1. **Hà Nội (`w07_form_hanoi_v1`):** `[GoMate W07] Đánh giá địa điểm du lịch thực tế — Hà Nội (20 POI)`
2. **Đà Nẵng (`w07_form_danang_v1`):** `[GoMate W07] Đánh giá địa điểm du lịch thực tế — Đà Nẵng (20 POI)`
3. **Hạ Long (`w07_form_halong_v1`):** `[GoMate W07] Đánh giá địa điểm du lịch thực tế — Hạ Long (20 POI)`

### Step 3 — Exact Form Settings (Privacy-First)
Verify in each Google Form's **Settings** tab:
- **Responses -> Collect email addresses:** `Do not collect` (`OFF`)
- **Responses -> Limit to 1 response:** `OFF` (so a contributor can submit again for another POI they visited without signing in)
- **Presentation -> Show link to submit another response:** `ON`
- Do **not** add any field asking for real name, email, phone number, social handle, home address, or student ID.

### Step 4 — Form Link Placeholders (Record Your Live Links Locally)
- **Hà Nội Form Responder URL:** `<PASTE_HANOI_GOOGLE_FORM_RESPONDER_URL_HERE>`
- **Đà Nẵng Form Responder URL:** `<PASTE_DANANG_GOOGLE_FORM_RESPONDER_URL_HERE>`
- **Hạ Long Form Responder URL:** `<PASTE_HALONG_GOOGLE_FORM_RESPONDER_URL_HERE>`

### Step 5 — How to Distribute
- Share the city-specific responder link with contributors who have visited that city.
- Remind contributors:
  1. **1 submission = 1 review for 1 POI** they personally visited;
  2. Submit again using *"Submit another response"* for additional POIs they have experienced;
  3. Write in their own words (no copying from Google Maps/Tripadvisor/Booking/Agoda/Foody, no ChatGPT/Gemini/Claude, and no phone numbers or email addresses inside the review text).

### Step 6 — Where Downloaded CSV Exports Go
In Google Forms -> **Responses** -> click the three-dot menu -> **Download responses (.csv)** (or File -> Download -> CSV from the linked Google Sheet), and save them to these exact git-ignored paths:
- Hà Nội CSV -> `data/restricted/w07_reviews/raw_forms/hanoi_responses.csv`
- Đà Nẵng CSV -> `data/restricted/w07_reviews/raw_forms/danang_responses.csv`
- Hạ Long CSV -> `data/restricted/w07_reviews/raw_forms/halong_responses.csv`

*(Never commit files inside `data/restricted/`; `.gitignore` blocks them automatically.)*

### Step 7 — Exact Import Command
Run from repository root (`d:\Do_an\wanderai`):
```powershell
python scripts/import_w07_contributor_reviews_v1.py --import-raw-dir
```
- This command is **strictly idempotent**: running it multiple times on unchanged CSV exports will never duplicate reviews in `data/restricted/w07_reviews/w07_canonical_reviews_v1.jsonl`.

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
- `summary_counts.quarantined_pii_count`: Reviews rejected because `review_text` contained a phone number or email address (`QUARANTINE_PII_REVIEW_TEXT`). Ask the contributor to resubmit a clean original review if needed; never edit or redact their text yourself.
- `pilot_gate_evaluation.COLLECTION_PIPELINE_PILOT_READY`: Turns `true` once all pilot thresholds are met.
- `scientific_minimum_evaluation.CORPUS_SCIENTIFIC_MINIMUM_READY`: Turns `true` only when all `60` POIs have `>= 5` accepted reviews (`>= 300` total).
- `exact_under_covered_pois`: Ordered list of POIs that still need reviews, prioritized by `0` reviews first, then `1–4` reviews, then city and category deficits.
- `poi_coverage_buckets.stop_active_recruitment_pois`: POIs that already have `>= 5` accepted reviews (stop actively recruiting for these until all 60 POIs reach 5).

### Step 11 — Pilot Target (`COLLECTION_PIPELINE_PILOT_READY`)
Aim first to reach:
- `>= 30` accepted reviews total;
- `>= 10` accepted reviews in `Hà Nội`, `>= 10` in `Đà Nẵng`, `>= 10` in `Hạ Long`;
- `>= 15` distinct target POIs covered;
- `100%` valid consent, `0` synthetic/LLM reviews, `0` quarantined PII reviews counted.

### Step 12 — When to Return to ChatGPT
1. **Immediately now (Gate `W07-A3-CONTRIBUTOR-COLLECTION-LAUNCH-CHATGPT-AUDIT`):** Return the A3 launch infrastructure PR return package for audit and merge approval before or as collection begins.
2. **After Pilot Collection:** Once `COLLECTION_PIPELINE_PILOT_READY = true` in `data/evaluation/w07/w07_review_collection_progress_v1.json`, return the updated progress report to ChatGPT to audit the pilot before or during full scale-up to `300 / 60 / >=5`.
