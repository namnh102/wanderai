# WanderAI RAG Retrieval Evaluation Report

**Document Version:** 1.0.0  
**Audit Date:** 2026-10-01  
**Auditor:** Technical Lead & AI Engineer (Antigravity)  
**Task Reference:** TASK 06.4 — Step A7: Retrieval Tests & Frozen Evaluation Set  

---

## 1. Frozen Evaluation Set & Objectives

To prevent hallucination and guarantee deterministic retrieval quality as WanderAI scales its knowledge base, a frozen evaluation suite tests semantic search accuracy across destination-specific domains:

| Query ID | Test Query | Language | Target Destination | Expected Topic | Ground Truth Anchor |
| :--- | :--- | :---: | :--- | :--- | :--- |
| `RAG-EVAL-01` | "Đà Nẵng có món ăn đặc trưng nào?" | Vietnamese | Da Nang | `culinary` | Mì Quảng, Bánh xèo, Bánh tráng cuốn thịt heo |
| `RAG-EVAL-02` | "Thời tiết Hà Nội vào mùa thu như thế nào?" | Vietnamese | Hanoi | `climate` | Autumn pleasant weather, October-November |
| `RAG-EVAL-03` | "How to get to Ha Long Bay from Hanoi?" | English | Ha Long Bay | `transport` | Bus, expressway, seaplane, shuttle |
| `RAG-EVAL-04` | "Lưu ý an toàn khi đi taxi ở Việt Nam" | Vietnamese | Vietnam | `safety` | Metered taxis, ride-hailing apps, airport scams |

---

## 2. Evaluation Results for `RAG-EVAL-01` (Da Nang Culinary)

* **Query:** `"Đà Nẵng có món ăn đặc trưng nào?"`
* **Embedding Model:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384-dim)
* **Search Metric:** Cosine similarity via PostgreSQL `pgvector` HNSW index
* **Parameters:** `top_k = 5`, `min_similarity = 0.35`

### Top Retrieved Chunks:

| Rank | Similarity | Document Title | Section Heading | Topic | Source & License | Verification Snippet |
| :---: | :---: | :--- | :--- | :--- | :--- | :--- |
| **1** | **0.6857** | Vietnam | Eat | `culinary` | Wikivoyage (CC BY-SA 3.0) | Traditional fish sauce, herbs, and culinary traditions across Vietnamese regions. |
| **2** | **0.6654** | **Da Nang** | **Eat** | **`culinary`** | **Wikivoyage (CC BY-SA 3.0)** | **"Seafood is popular, but Da Nang is best known for its Mì Quảng... Bánh xèo, Bánh tráng cuốn thịt heo..."** |
| **3** | **0.6133** | Nha Trang | Eat | `culinary` | Wikivoyage (CC BY-SA 3.0) | Regional coastal rice specialties (Bánh căn, Bánh hỏi, Bánh xèo). |
| **4** | **0.5853** | Vietnam | Eat | `culinary` | Wikivoyage (CC BY-SA 3.0) | Vietnamese culinary culture, meal customs, and street food. |
| **5** | **0.5765** | Vietnam | Dietary restrictions | `general` | Wikivoyage (CC BY-SA 3.0) | Vegetarian food (cơm chay) guidance across Vietnam. |

---

## 3. Evaluation Invariants & Quality Checks

1. **Top-K Retrieval Precision:**
   * **Passed.** Result #2 precisely matches Da Nang culinary specialties (`topic: culinary`, `title: Da Nang`).
2. **Metadata Integrity:**
   * **Passed.** 100% of retrieved records retain valid `source_name`, `source_url`, `license`, and `attribution` fields.
3. **Chunk Deduplication:**
   * **Passed.** 0 duplicate chunk IDs across all returned results.
4. **Deterministic Output:**
   * **Passed.** Repeated queries against the frozen embedding vector produce identical similarity scores ($1.0000$ consistency).

---

## 4. TASK 07.5 update (2026-10-04): OSM verified-place documents

Production corpus after TASK 07.5: **821 documents = 464 Wikivoyage + 357 OSM** (357/357 verified places covered; 164 documents in `document_quarantine`).

Frozen queries RAG-EVAL-01..04 are unchanged. Results BEFORE and AFTER the re-ingestion are identical:

| Query | Expected | Before | After |
| :--- | :--- | :---: | :---: |
| RAG-EVAL-01 | culinary / Da Nang | rank 2 (0.6654) | rank 2 (0.6654) |
| RAG-EVAL-02 | climate / Hanoi | rank 2 (0.6542) | rank 2 (0.6542) |
| RAG-EVAL-03 | transport / Ha Long Bay | rank 4 (0.7279) | rank 4 (0.7279) |
| RAG-EVAL-04 | safety / Vietnam | not in top 5 | not in top 5 (pre-existing gap, not changed) |

Deterministic grounding checks (no LLM; `tests/test_rag_osm_ingestion.py`, `tests/test_grounding_contract.py`):
- "Địa điểm văn hóa ở Hà Nội": returns an OSM `culture` document; every returned document is `osm` or `wikivoyage`, has a source URL, and each OSM document maps to a real `place_sources` row (`https://www.openstreetmap.org/{source_id}`, ODbL 1.0).
- "Giờ mở cửa Bảo tàng Hồ Chí Minh": the matching OSM documents are returned (ranks 1-3 in the 07.5 probe) and contain `Giờ mở cửa:` only when the OSM tag exists.
- No synthetic/mock/unsourced document is returned by the production retriever.

These are retrieval checks, not an LLM-quality or hallucination-rate evaluation.

### Chat grounding contract (TASK 07.5 & 07.5.1)

`POST /chat` and NestJS `POST /ai/chat` return `data.sources: string[]` (source URLs of retrieved documents; `[]` when nothing was retrieved). Retrieved context is prepended to the user message with a "do not invent" instruction; the system prompt permits place facts only from retrieved context or tool results and mandates the exact fallbacks "Chưa có thông tin giá trong dữ liệu hiện có.", "Chưa có thông tin giờ mở cửa trong dữ liệu hiện có.", "Chưa có đánh giá.".

### TASK 07.5.1 Update (2026-10-04): End-to-End Propagation & Source UI

- **Runtime Path:** Flutter Mobile → NestJS (`POST /ai/chat`) → FastAPI (`POST /chat`) → `retrieve_grounding()` → `RAGService.search_with_sources()` → `sources: string[]` → Gemini prompt context → NestJS wrapper (`data.sources`) → Flutter (`ChatResponse.sources`) → `ChatMessage.sources` → `AiChatScreen` source chips.
- **Flutter Source UI:** Displays a visually secondary "Nguồn tham khảo:" section within assistant bubbles containing compact chips formatted as `OpenStreetMap (way/...)` or `Wikivoyage: ...`. Clicking a chip opens the source URL externally via `url_launcher`.
- **Empty / Non-assistant behavior:** When `sources` is empty or message is from user, no source section or empty box is rendered.
- **Live Gemini Verification Status:** **PENDING** due to provider quota `HTTP 429 RESOURCE_EXHAUSTED`. Verified via mock-grounding tests and opt-in smoke test `CHAT_LIVE_TEST=1 pytest tests/test_chat_live.py`.
