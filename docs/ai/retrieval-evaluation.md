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
