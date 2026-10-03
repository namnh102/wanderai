"""Retrieval evaluation (frozen set + place-grounding checks).

Usage (from apps/ai-service):
    python -m app.rag.evaluate --label before --out ../../docs/audit/evidence/rag-eval-before.json

The frozen queries are copied verbatim from docs/ai/retrieval-evaluation.md and must not be edited to
improve scores.
"""

import argparse
import asyncio
import json
from datetime import datetime, timezone

from app.rag.retriever import RAGRetriever

FROZEN_QUERIES = [
    {"id": "RAG-EVAL-01", "query": "Đà Nẵng có món ăn đặc trưng nào?", "expected_topic": "culinary", "expected_title": "Da Nang"},
    {"id": "RAG-EVAL-02", "query": "Thời tiết Hà Nội vào mùa thu như thế nào?", "expected_topic": "climate", "expected_title": "Hanoi"},
    {"id": "RAG-EVAL-03", "query": "How to get to Ha Long Bay from Hanoi?", "expected_topic": "transport", "expected_title": "Ha Long Bay"},
    {"id": "RAG-EVAL-04", "query": "Lưu ý an toàn khi đi taxi ở Việt Nam", "expected_topic": "safety", "expected_title": "Vietnam"},
]

GROUNDING_CULTURE_HANOI = "Địa điểm nào thuộc Văn hóa ở Hà Nội?"


def opening_hours_query(name: str) -> str:
    return f"Giờ mở cửa của {name} là gì?"


async def run(top_k: int = 5):
    retriever = RAGRetriever()
    report = {"retrieved_at": datetime.now(timezone.utc).isoformat(), "model": retriever.embedder.model_name, "frozen": [], "grounding": []}
    for q in FROZEN_QUERIES:
        res = await retriever.search(query=q["query"], top_k=top_k, min_similarity=0.35)
        top_hit = next(
            (i + 1 for i, r in enumerate(res) if r["topic"] == q["expected_topic"] and r["title"] == q["expected_title"]), None
        )
        report["frozen"].append({
            **q,
            "expected_topic_and_title_rank": top_hit,
            "results": [
                {"rank": i + 1, "similarity": r["similarity"], "title": r["title"], "topic": r["topic"],
                 "source": r["source_name"], "section": r["section_heading"]}
                for i, r in enumerate(res)
            ],
        })
    await retriever.close()
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="run")
    ap.add_argument("--out")
    args = ap.parse_args()
    report = asyncio.run(run())
    report["label"] = args.label
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
    for q in report["frozen"]:
        print(q["id"], "expected-rank:", q["expected_topic_and_title_rank"],
              [(r["rank"], r["similarity"], r["source"], r["title"], r["topic"]) for r in q["results"]][:5])


if __name__ == "__main__":
    main()
