"""Self-contained synthetic fixtures for FX-02..FX-09, FX-11, and 2x3 smoke tests."""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, List, Tuple

from w07_retrieval.schema import CanonicalDocument, load_canonical_document

BOILERPLATE_FOOTER_ALLOWLIST: tuple[str, ...] = (
    "Xem thêm",
    "Tham khảo",
    "Liên kết ngoài",
    "Chú thích",
    "Thư viện ảnh",
    "See also",
    "References",
    "External links",
    "Gallery",
    "Notes",
)


def build_fx02_conservation_doc() -> CanonicalDocument:
    """Multi-section synthetic B1B doc testing parent breadcrumbs, allowlist, and non-allowlist empty sections."""
    s_text = (
        "Văn Miếu - Quốc Tử Giám là quần thể di tích lịch sử văn hóa tại Hà Nội.\n"
        "== Kiến trúc ==\n"
        "  \n"
        "=== Mặt tiền ===\n"
        "Cổng Tam Quan có mái ngói cổ kính và bốn trụ nghi môn.\n"
        "== Lịch sử ==\n"
        "Công trình được khởi dựng năm 1070 dưới thời vua Lý Thánh Tông.\n"
        "== Kiến trúc đặc biệt ==\n"
        "  \n"
        "== Xem thêm ==\n"
        "\n"
        "== Tham khảo ==\n"
        "  \n"
        "== See also ==\n"
        "== References ==\n"
    )
    return load_canonical_document(
        {
            "document_id": "syn-b1b-fx02-doc",
            "source_type": "wikipedia_vi",
            "title": "Văn Miếu - Quốc Tử Giám",
            "language": "vi",
            "source_lineage_id": "syn-wikipedia-vi-fx02",
            "poi_id": "poi-fx02",
            "city": "Hà Nội",
            "canonical_text_S": s_text,
        }
    )


def build_fx02_osm_payload() -> Dict[str, Any]:
    """Synthetic OSM place payload for schema.load_canonical_document verification."""
    return {
        "document_id": "syn-osm-fx02",
        "source_type": "osm_useful_structured",
        "city": "Hà Nội",
        "place": {
            "id": "fx02-place-01",
            "name": "Hồ Hoàn Kiếm",
            "category": "attraction",
            "destination": "Hà Nội",
            "latitude": 21.0287,
            "longitude": 105.8524,
            "sources": [
                {
                    "source_name": "osm",
                    "source_id": "way/12345678",
                    "raw_data": {
                        "tags": {
                            "name:en": "Hoan Kiem Lake",
                            "tourism": "attraction",
                            "addr:street": "Đinh Tiên Hoàng",
                            "addr:district": "Hoàn Kiếm",
                            "addr:city": "Hà Nội",
                            "opening_hours": "24/7",
                            "wikidata": "Q1140219",
                            "_internal_ignored": "ignore_me",
                        }
                    },
                }
            ],
        },
    }


FX03_VALID_SIX_FAMILY_DOC: str = (
    "Bảo tàng Lịch sử Quốc gia Việt Nam (arts_and_entertainment > museum) "
    "[CORROBORATED: canonical_poi:12345678-1234-1234-1234-1234567890ab, "
    "osm:way/234567, wikidata:Q1074284, wikipedia:vi:12345, "
    "wikivoyage:en:Hanoi#Museums, osm_website_pointer:https://baotanglichsu.vn/vi] "
    "tại Hà Nội. "
    "Độ tin cậy bản ghi Overture (confidence): 0.8542.\n"
    "Địa điểm [CORROBORATED: osm:node/998877][CORROBORATED: wikivoyage:vi:Hà_Nội] "
    "lưu giữ cổ vật [1] thời kỳ [Gia Long] và tài liệu [4].\n"
    "Giờ mở cửa: [UNVERIFIED: chưa xác minh thực địa] | "
    "[CONFLICT: FC-001 ẩn khỏi câu trả lời] | Ghi chú FC-002."
)

FX03_MALFORMED_INPUTS: Tuple[str, ...] = (
    "Text [CORROBORATED: unknown_family:abc123] end.",
    "Text [CORROBORATED: ] end.",
    "Text [CORROBORATED: osm:invalid_type/123] end.",
    "Text [CORROBORATED: canonical_poi:not-a-valid-uuid] end.",
    "Text [CORROBORATED: osm:node/123\n] end.",
    "Text [CORROBORATED: osm:node/123 unclosed end.",
    "Text [CORROBORATED without colon] end.",
)


def build_fx04_corpus() -> List[CanonicalDocument]:
    """5 synthetic docs testing C1 <=128 ceiling, clause/word/char splits, and <10-word retention."""
    long_vi = (
        "== Di sản văn hóa ==\n"
        + " ".join(
            f"Quần thể kiến trúc cổ kính tại kinh thành Huế mang đậm dấu ấn triều Nguyễn năm {1802 + i}."
            for i in range(45)
        )
    )
    long_en = (
        "## Travel Guide\n"
        + " ".join(
            f"Visitors exploring the limestone karsts of Ha Long Bay enjoy kayaking past cave number {i + 1}."
            for i in range(40)
        )
    )
    structured_osm = (
        "Chùa Một Cột (One Pillar Pagoda) thuộc nhóm văn hóa tại Hà Nội.\n"
        + "\n".join(f"Thông tin chi tiết dòng {i}: mở cửa từ 07:00 đến 18:00 hàng ngày." for i in range(1, 18))
    )
    unpunctuated_run = (
        "## Long Clause\n"
        + " ".join(f"tuvungkhongdauphay{i:03d}" for i in range(180))
        + " "
        + ("X" * 260)
    )
    short_body = "== Ghi chú ngắn ==\nMở cửa miễn phí hàng ngày."

    raw_specs = [
        ("syn-fx04-vi", "wikipedia_vi", "Cố đô Huế", "vi", long_vi),
        ("syn-fx04-en", "wikivoyage_en", "Ha Long Bay", "en", long_en),
        ("syn-fx04-osm", "osm_useful_structured", "Chùa Một Cột", "vi", structured_osm),
        ("syn-fx04-unpunct", "wikipedia_vi", "Chuỗi dài", "vi", unpunctuated_run),
        ("syn-fx04-short", "wikipedia_vi", "Ghi chú", "vi", short_body),
    ]
    return [
        load_canonical_document(
            {
                "document_id": did,
                "source_type": st,
                "title": title,
                "language": lang,
                "source_lineage_id": f"lin-{did}",
                "poi_id": f"poi-{did}",
                "city": "Hà Nội",
                "canonical_text_S": text_s,
            }
        )
        for did, st, title, lang, text_s in raw_specs
    ]


def build_fx05_synthetic_overture_doc() -> CanonicalDocument:
    """Synthetic Overture doc with early 4-family R_AUDIT tag and >128-token tail fact echoed in title."""
    filler = "Thông tin bổ sung lịch sử trưng bày dân tộc học Việt Nam tại Hà Nội. " * 26
    s_text = (
        "== Bảo tàng Dân tộc học Việt Nam ==\n"
        "Bảo tàng Dân tộc học Việt Nam (arts_and_entertainment > museum) "
        "[CORROBORATED: canonical_poi:11111111-2222-3333-4444-555555555555, "
        "osm:node/1001, wikidata:Q12345, wikipedia:vi:999999] có độ tin cậy 0.7405.\n"
        + filler
        + "Mã lưu trữ đặc biệt cuối trang: ARCHIVE-TAIL-9981."
    )
    return load_canonical_document(
        {
            "document_id": "syn-overture-fx05",
            "source_type": "overture_places_parquet",
            "title": "Bảo tàng Dân tộc học [SYNTH_ECHO: ARCHIVE-TAIL-9981]",
            "language": "vi",
            "source_lineage_id": "lin-syn-fx05",
            "poi_id": "poi-syn-fx05",
            "city": "Hà Nội",
            "canonical_text_S": s_text,
        }
    )


FX06_GOLDEN_SAMPLES: Tuple[Tuple[str, List[str]], ...] = (
    (
        "Phở Bát Đàn tại Hà Nội mở cửa lúc 06:30.",
        ["phở", "bát", "đàn", "tại", "hà_nội", "mở_cửa", "lúc", "06", "30"],
    ),
    (
        "Hội An - Đà Nẵng: bãi biển Mỹ Khê đẹp tuyệt vời!",
        ["hội_an", "đà_nẵng", "bãi", "biển", "mỹ_khê", "đẹp", "tuyệt_vời"],
    ),
    (
        "Vịnh Hạ Long (Ha Long Bay) UNESCO 1994, giá vé 290.000 VNĐ.",
        ["vịnh", "hạ_long", "ha", "long", "bay", "unesco", "1994", "giá", "vé", "290.000", "vnđ"],
    ),
    (
        "Hồ Hoàn Kiếm ở quận Hoàn Kiếm, Thành phố Hà Nội.",
        ["hồ", "hoàn_kiếm", "ở", "quận", "hoàn_kiếm", "thành_phố", "hà_nội"],
    ),
    (
        "Bảo tàng Dân tộc học Việt Nam (Vietnam Museum of Ethnology).",
        ["bảo_tàng", "dân_tộc_học", "việt_nam", "vietnam", "museum", "of_ethnology"],
    ),
    (
        "Hoà Bình vs Hòa Bình — NFC normalization check: "
        + unicodedata.normalize("NFD", "Hồ Tây Hà Nội"),
        ["hòa", "bình_vs", "hòa", "bình_", "nfc", "normalization", "check", "hồ", "tây", "hà_nội"],
    ),
    (
        "Cầu Rồng phun lửa lúc 21:00 thứ Bảy và Chủ nhật.",
        ["cầu", "rồng", "phun", "lửa", "lúc", "21", "00", "thứ_bảy", "và", "chủ_nhật"],
    ),
    (
        "Chùa Một Cột (One Pillar Pagoda) built in 1049.",
        ["chùa", "một", "cột", "one", "pillar", "pagoda", "built", "in", "1049"],
    ),
    (
        "Sun World Ha Long Complex — cáp treo Nữ Hoàng 2.5km.",
        ["sun", "world", "ha", "long", "complex", "cáp", "treo", "nữ_hoàng", "2.5", "km"],
    ),
    (
        "Khách sạn gần Sân bay Quốc tế Nội Bài (HAN).",
        ["khách_sạn", "gần", "sân_bay", "quốc_tế", "nội_bài", "han"],
    ),
    (
        "Bà Nà Hills: Cầu Vàng (Golden Bridge) ở Đà Nẵng.",
        ["bà", "nà", "hills", "cầu", "vàng", "golden", "bridge", "ở", "đà_nẵng"],
    ),
    (
        "Phố cổ Hội An và Thánh địa Mỹ Sơn.",
        ["phố", "cổ", "hội_an", "và", "thánh_địa_mỹ", "sơn"],
    ),
    (
        "Lăng Chủ tịch Hồ Chí Minh đóng cửa thứ Hai và thứ Sáu.",
        ["lăng", "chủ_tịch", "hồ", "chí_minh", "đóng_cửa", "thứ", "hai", "và", "thứ_sáu"],
    ),
    (
        "Nhà hát Lớn Hà Nội (Hanoi Opera House) 1911.",
        ["nhà_hát", "lớn", "hà_nội", "hanoi", "opera", "house", "1911"],
    ),
    (
        "Bán đảo Sơn Trà — Chùa Linh Ứng Bãi Bụt.",
        ["bán_đảo", "sơn", "trà_", "chùa", "linh_ứng", "bãi_bụt"],
    ),
    (
        "Động Thiên Cung & Hang Đầu Gỗ trên vịnh Hạ Long.",
        ["động", "thiên_cung", "hang", "đầu", "gỗ", "trên", "vịnh", "hạ", "long"],
    ),
    (
        "Cà phê trứng Phố Cổ: 35,000đ - 50,000đ.",
        ["cà_phê", "trứng", "phố", "cổ", "35,000", "đ", "50,000", "đ"],
    ),
    (
        "Wi-Fi miễn phí, COVID-19 protocol, e-ticket QR_code_01.",
        ["wi", "fi", "miễn_phí", "covid", "19", "protocol", "e", "ticket", "qr_code_01"],
    ),
    (
        "Quốc Tử Giám - Văn Miếu (1070): di tích lịch sử quốc gia.",
        ["quốc_tử_giám", "văn_miếu", "1070", "di_tích", "lịch_sử", "quốc_gia"],
    ),
    (
        "du lịch sinh thái cộng đồng tại Cát Bà 2026.",
        ["du_lịch", "sinh_thái", "cộng_đồng", "tại", "cát", "bà", "2026"],
    ),
)


def build_fx08_collapse_corpus() -> List[CanonicalDocument]:
    """Synthetic corpus where doc-01 owns 50+ high-scoring chunks and 9 other docs exist."""
    docs: List[CanonicalDocument] = []
    # 55 distinct sections in doc-01 so C0 emits >=50 chunks mentioning "phở bò hà nội"
    sec_blocks = []
    for i in range(1, 56):
        sec_blocks.append(
            f"== Phần {i} ==\n"
            f"Quán phở bò gia truyền nổi tiếng tại phố cổ Hà Nội phục vụ thực khách từ sáng sớm trong khu vực số {i}."
        )
    docs.append(
        load_canonical_document(
            {
                "document_id": "doc-01-dominant",
                "source_type": "wikipedia_vi",
                "title": "Phở Hà Nội",
                "language": "vi",
                "source_lineage_id": "lin-doc-01",
                "poi_id": "poi-01",
                "city": "Hà Nội",
                "canonical_text_S": "\n".join(sec_blocks),
            }
        )
    )
    for k in range(2, 11):
        docs.append(
            load_canonical_document(
                {
                    "document_id": f"doc-{k:02d}-other",
                    "source_type": "wikipedia_vi",
                    "title": f"Địa điểm ẩm thực {k}",
                    "language": "vi",
                    "source_lineage_id": f"lin-doc-{k:02d}",
                    "poi_id": f"poi-{k:02d}",
                    "city": "Hà Nội",
                    "canonical_text_S": (
                        f"== Giới thiệu ==\n"
                        f"Khu phố ẩm thực số {k} có món phở truyền thống thơm ngon và nhiều quán ăn địa phương phục vụ du khách."
                    ),
                }
            )
        )
    return docs


def build_fx09_137doc_bm25_zero_corpus() -> List[CanonicalDocument]:
    """137 synthetic docs: 2 matching 'bún chả hương liên', 135 completely disjoint."""
    docs: List[CanonicalDocument] = []
    for i in range(1, 3):
        docs.append(
            load_canonical_document(
                {
                    "document_id": f"doc-match-{i:03d}",
                    "source_type": "wikipedia_vi",
                    "title": f"Bún chả Hương Liên cơ sở {i}",
                    "language": "vi",
                    "source_lineage_id": f"lin-match-{i:03d}",
                    "poi_id": f"poi-m-{i}",
                    "city": "Hà Nội",
                    "canonical_text_S": (
                        f"== Giới thiệu ==\n"
                        f"Quán bún chả Hương Liên số {i} nằm trên phố Lê Văn Hưu tại quận Hai Bà Trưng Hà Nội."
                    ),
                }
            )
        )
    for j in range(1, 136):
        docs.append(
            load_canonical_document(
                {
                    "document_id": f"doc-zero-{j:03d}",
                    "source_type": "wikipedia_vi",
                    "title": f"Vườn quốc gia {j}",
                    "language": "vi",
                    "source_lineage_id": f"lin-zero-{j:03d}",
                    "poi_id": f"poi-z-{j}",
                    "city": "Đà Nẵng",
                    "canonical_text_S": (
                        f"== Tự nhiên ==\n"
                        f"Khu bảo tồn thiên nhiên nhiệt đới số {j} có hệ thực vật phong phú ven biển miền Trung Việt Nam."
                    ),
                }
            )
        )
    return docs


def build_fx11_canonical_pool() -> Tuple[
    Dict[str, Dict[str, str]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
]:
    """Exact 20-doc canonical fixture matching verify_v0_2_1_real_corpus_g15_r01.py:684-689."""
    corpus_mock = {
        f"doc-{i:03d}": {
            "source_type": "wikipedia_article",
            "language": "vi",
            "S": f"Text {i}",
        }
        for i in range(1, 21)
    }
    run_forward = [
        {
            "document_id": f"doc-{i:03d}",
            "rank": i,
            "cell_id": "C1-RRF",
            "score": 1.0 / i,
            "pre_rank_answerability": "ANSWERABLE",
            "pool_origin": "C1-RRF",
            "union_count": 1,
            "chunk_boundaries": [0, 6],
            "assembled_text": f"Title - Lead\nText {i}",
        }
        for i in range(1, 21)
    ]
    run_reversed = [
        {
            "document_id": f"doc-{21 - i:03d}",
            "rank": i,
            "cell_id": "C0-BM25",
            "score": 99.0 * i,
            "pre_rank_answerability": "UNANSWERABLE",
            "pool_origin": "C0-BM25",
            "union_count": 6,
            "chunk_boundaries": [0, 10],
            "assembled_text": f"Other - Sec\nText {21 - i}",
        }
        for i in range(1, 21)
    ]
    return corpus_mock, run_forward, run_reversed


def build_smoke_2x3_dataset() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Minimal deterministic synthetic corpus & queries for 2x3 CLI smoke test."""
    corpus_records = [
        {
            "document_id": "smoke-doc-01",
            "source_type": "overture_places_parquet",
            "title": "Bảo tàng Dân tộc học Việt Nam",
            "language": "vi",
            "source_lineage_id": "lin-smoke-01",
            "poi_id": "poi-smoke-01",
            "city": "Hà Nội",
            "canonical_text_S": (
                "== Giới thiệu ==\n"
                "Bảo tàng Dân tộc học Việt Nam [CORROBORATED: osm:node/1001, wikidata:Q12345] "
                "nằm trên đường Nguyễn Văn Huyên tại Cầu Giấy Hà Nội và mở cửa từ 08:30 đến 17:30."
            ),
        },
        {
            "document_id": "smoke-doc-02",
            "source_type": "wikipedia_vi",
            "title": "Hồ Hoàn Kiếm",
            "language": "vi",
            "source_lineage_id": "lin-smoke-02",
            "poi_id": "poi-smoke-02",
            "city": "Hà Nội",
            "canonical_text_S": (
                "== Lịch sử ==\n"
                "Hồ Hoàn Kiếm là hồ nước ngọt tự nhiên nằm ở trung tâm thủ đô Hà Nội gắn liền với Tháp Rùa và cầu Thê Húc."
            ),
        },
        {
            "document_id": "smoke-doc-03",
            "source_type": "osm_useful_structured",
            "title": "Cầu Rồng",
            "language": "vi",
            "source_lineage_id": "lin-smoke-03",
            "poi_id": "poi-smoke-03",
            "city": "Đà Nẵng",
            "canonical_text_S": (
                "Cầu Rồng thuộc nhóm tham quan tại Đà Nẵng.\n"
                "Loại OSM: tourism=attraction.\n"
                "Địa chỉ: Đường Nguyễn Văn Linh, Hải Châu, Đà Nẵng.\n"
                "Giờ mở cửa: 24/7, phun lửa lúc 21:00 thứ Bảy và Chủ nhật.\n"
                "Nguồn: OpenStreetMap way/555666."
            ),
        },
        {
            "document_id": "smoke-doc-04",
            "source_type": "wikivoyage_en",
            "title": "Ha Long Bay",
            "language": "en",
            "source_lineage_id": "lin-smoke-04",
            "poi_id": "poi-smoke-04",
            "city": "Hạ Long",
            "canonical_text_S": (
                "## Overview\n"
                "Ha Long Bay is a UNESCO World Heritage site in Quang Ninh province famous for emerald waters and limestone islands."
            ),
        },
    ]
    queries = [
        {
            "query_id": "Q-SMOKE-01",
            "query_text": "Bảo tàng Dân tộc học ở Hà Nội mở cửa mấy giờ?",
            "split": "DEV",
            "creator_exposure_to_corpus": "BLIND",
            "question_origin": "SYNTHETIC",
            "query_family": "FACT_HOURS",
            "target_city": "Hà Nội",
            "pre_rank_answerability": "ANSWERABLE",
            "scope_mode": "SINGLE_POI",
            "target_poi_ids": ["poi-smoke-01"],
            "query_intent_polarity": "POSITIVE",
            "requested_facet_keywords": ["mở cửa"],
            "fact_cluster_id": "fc-smoke-01",
        },
        {
            "query_id": "Q-SMOKE-02",
            "query_text": "Cầu Rồng Đà Nẵng phun lửa lúc nào?",
            "split": "DEV",
            "creator_exposure_to_corpus": "BLIND",
            "question_origin": "SYNTHETIC",
            "query_family": "FACT_SCHEDULE",
            "target_city": "Đà Nẵng",
            "pre_rank_answerability": "ANSWERABLE",
            "scope_mode": "SINGLE_POI",
            "target_poi_ids": ["poi-smoke-03"],
            "query_intent_polarity": "POSITIVE",
            "requested_facet_keywords": ["phun lửa"],
            "fact_cluster_id": "fc-smoke-02",
        },
    ]
    return corpus_records, queries
