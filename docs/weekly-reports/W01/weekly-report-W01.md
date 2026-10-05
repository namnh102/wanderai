# BÁO CÁO TIẾN ĐỘ TUẦN 1

## 1. Thông tin chung

| Mục | Nội dung |
|---|---|
| Đề tài | Xây dựng nền tảng du lịch thông minh dựa trên AI Agent, hệ thống gợi ý và kết nối bạn đồng hành |
| Nhóm | KH3 |
| Sinh viên | Ngô Hoàng Nam; Nguyễn Duy Khánh |
| GVHD | TS. Nguyễn Tất Thắng |
| Thời gian đồ án | 27/09/2026 – 31/12/2026 |
| Tuần báo cáo | W1: 27/09/2026 – 03/10/2026 |
| Mốc tham chiếu | Commit `2d15a64` (03/10/2026 15:28). Mọi commit từ 04/10/2026 bị loại khỏi báo cáo |
| Nguồn đề cương | Không có file đề cương trong repository (*proposal source not found in repository*); nội dung W1 lấy từ đề cương do nhóm cung cấp |

## 2. Mục tiêu tuần
Theo đề cương: chọn phạm vi thành phố, xác định nguồn POI và license, chốt MVP. Output: Data/source card, repository, POI pilot dataset.

## 3. Kế hoạch W1
(1) City scope; (2) POI sources + license; (3) MVP; (4) Data/source card; (5) Repository; (6) POI pilot dataset.

## 4. Công việc đã thực hiện
Trạng thái: **V** = VERIFIED, **P** = PARTIALLY VERIFIED, **N** = NOT VERIFIED.

### 4.1 Geographic Scope — N
Không tìm thấy quyết định chọn thành phố (ADR/decision log) trong W1 hay ở HEAD. Hiện trạng quan sát được: pipeline Overpass dùng 5 bounding box (Đà Nẵng, Hà Nội, Hội An, Nha Trang, Huế) — `data/pipelines/osm/config.py`, commit `ffe7b97` (01/10). Dữ liệu thực tế tập trung ở Đà Nẵng (55) và Hà Nội (50). Hạ Long: 0 POI. Phạm vi 5 box vượt giới hạn 1–2 thành phố của đề cương.

**Post-W1 Scope Clarification / Scope Change:** hướng "Hà Nội + Hạ Long" **không** có bằng chứng được quyết định trong W1 và cũng chưa có tài liệu ghi nhận trong repository. Đây là định hướng sau W1, cần ghi ADR khi chính thức hóa; không được tính là kết quả W1.

### 4.2 POI Sources — P
OpenStreetMap qua Overpass API được chọn và triển khai: `docs/data/data-sources.md`, `data/manifests/sources.yaml`, ADR-002 (`8592aea`, `b5e96db`, `ffe7b97`). Pipeline: collect → parse → entity resolution (`data/pipelines/`). Ngày snapshot khai báo 01/10/2026, file raw không có timestamp. Kiểm tra ngày 03/10 (`2d15a64`) cho thấy 11/110 bản ghi nguồn có OSM ID không có thật (do nhập tay vào file raw).

### 4.3 License — P
Tài liệu ghi OSM = ODbL 1.0 (attribution "© OpenStreetMap contributors", share-alike); Wikivoyage = CC BY-SA 3.0; Open-Meteo = CC BY 4.0 (`sources.yaml`). Chưa đối chiếu độc lập với trang license gốc trong task này. Dữ liệu review nội bộ: **LICENSE STATUS: NOT VERIFIED** (fixture tổng hợp; trích dẫn UIT-VSFC trước đó đã được rút lại ở `4944fae`).

### 4.4 MVP Scope — N
Không có ADR/issue/tài liệu nào khóa MVP trong W1. Có bằng chứng gián tiếp: stack kỹ thuật cố định trong `AGENTS.md` (`9b36f9d`). Theo ba năng lực của đề cương tại cuối W1: lập lịch AI — một phần (chạy được với mock, lỗi khi chạy thật ngày 03/10); gợi ý — chỉ có baseline MostPop; ghép bạn đồng hành — chưa có mã.

### 4.5 Pilot Dataset — V (tồn tại), P (chất lượng)
`data/curated/places_canonical.json`: 108 địa điểm, 110 bản ghi nguồn (đều `osm`), 6 category (cafe 55, hotel 25, restaurant 15, attraction 9, culture 3, beach 1), 13 trường. Đo ngày 05/10 trên bản lưu tại `2d15a64` (`evidence/dataset-summary.txt`): 0 thiếu tọa độ, 0 tọa độ ngoài lãnh thổ, 0 trùng; nhưng 108/108 rating là mặc định 4.5 (review_count 0), 66/108 địa chỉ là placeholder, 0 mô tả, không có opening hours; trường `city` dùng hai kiểu nhãn (`da_nang` / `Đà Nẵng`).

### 4.6 Repository / Project Management — P
Repository GitHub riêng `namnh102/wanderai` có `AGENTS.md`, `CONTRIBUTING.md` (29/09), nhánh theo tính năng, 31 commit trong cửa sổ W1 (20 không tính merge). **Không có Issue, PR, Milestone, tag** (`gh issue/pr list` rỗng) — chưa đạt yêu cầu mục 10 đề cương.

## 5. Kết quả đạt được
- **COMPLETED:** repository có quy tắc làm việc; pipeline OSM tái lập được; pilot dataset 108 POI tồn tại và truy vết được tới commit.
- **PARTIAL:** nguồn POI/license (đã ghi tài liệu, chưa kiểm tra độc lập, 11 ID sai); Data/source card (có `dataset-card.md` + `data-sources.md` gốc; thẻ hợp nhất là bản **RECONSTRUCTED**); quản lý dự án.
- **NOT COMPLETED:** Issue/PR/Milestone; cross-review giữa hai thành viên.
- **NOT VERIFIED:** quyết định city scope; khóa MVP; đóng góp của Nguyễn Duy Khánh.
- Công việc nằm trong khoảng 27/09–03/10 nhưng **ngoài kế hoạch W1** (không tính là kết quả W1): auth, AI chat, trip CRUD, AI planner, RAG/MostPop, màn hình bản đồ (`d02cee7`…`0997efa`).

## 6. Data / Source Card
Xem `evidence/data-source-card.md` (RECONSTRUCTED 05/10/2026) và các file gốc: `docs/data/data-sources.md`, `docs/data/dataset-card.md`, `data/manifests/sources.yaml`.

## 7. Planned — Done — Evidence — Problems — Next Week

| Planned | Done | Evidence | Problems | Next week |
|---|---|---|---|---|
| City scope | Không xác nhận (N) | `mvp-scope-evidence.md` | Không có ADR; 5 box > 1–2 thành phố | Ghi ADR scope |
| POI source | OSM/Overpass (P) | `sources.yaml`, `ffe7b97` | 11 ID không thật; snapshot không có timestamp | Làm sạch, ghi timestamp |
| License | Ghi tài liệu (P) | `data-sources.md` | Chưa đối chiếu độc lập; review license N | Rà soát license W1–W2 |
| MVP | Không xác nhận (N) | `mvp-scope-evidence.md` | Không có decision log | Khóa MVP bằng ADR |
| Data/source card | Có tài liệu gốc (P) | `dataset-card.md` | Thẻ hợp nhất là bản dựng lại | Cập nhật theo dữ liệu thật |
| Repository | Có (P) | `AGENTS.md`, git log | Không Issue/PR | Tạo Issue/Milestone, PR |
| POI pilot dataset | 108 POI (V/P) | `places_canonical.json`, `dataset-summary.txt` | Rating mặc định, địa chỉ placeholder | Ingest PostGIS, chuẩn hóa |

## 8. Vấn đề và cách xử lý
1. **License/provenance:** 11/108 địa điểm có OSM ID không có thật; báo cáo chất lượng 01/10 ghi "100% provenance" chưa chính xác. Phát hiện ở `2d15a64` (03/10), đã ghi vào `current-database-state.md`; chưa sửa dữ liệu trong W1.
2. **Dữ liệu không nhất quán:** nhãn `city` hai kiểu; rating mặc định 4.5; địa chỉ placeholder; thiếu opening hours.
3. **Scope rộng:** 5 thành phố, nhiều module phát triển sớm trước khi khóa MVP.
4. **Môi trường:** lỗi mã hóa Windows, null byte `.gitignore`, thiếu hỗ trợ `vector` của Prisma (`docs/daily-reports/2026-10-01.md`); ngày 03/10 OSM tile bị chặn trên mạng của nhóm (`2026-10-03.md`).
5. **Dữ liệu review:** chưa có tập review thật; truy cập VLSP 2018/ViMACSA chưa được cấp.

## 9. Contribution của thành viên

| Member | Work | Evidence | Quantified contribution |
|---|---|---|---|
| Ngô Hoàng Nam | Toàn bộ commit trong W1 (tài khoản `namnh102`) | `git-log-W01.txt` | 31 commit (20 non-merge); ánh xạ tài khoản ↔ thành viên là giả định theo tên tài khoản |
| Nguyễn Duy Khánh | — | — | Not fully traceable (0 commit/issue/PR) |

## 10. Evidence Package
`docs/weekly-reports/W01/`: `evidence/git-log-W01.txt`, `dataset-summary.txt`, `data-source-card.md`, `mvp-scope-evidence.md`, `contribution-evidence.md`, `links.md`.

| W1 Requirement | Status | Evidence | Confidence |
|---|---|---|---|
| 1. City scope | NOT VERIFIED | Không có ADR; chỉ có 5 box | HIGH (về việc thiếu bằng chứng) |
| 2. POI source | PARTIAL | `sources.yaml`, `ffe7b97` | MEDIUM |
| 3. License | PARTIAL | `data-sources.md` | MEDIUM |
| 4. MVP | NOT VERIFIED | Không có decision log | HIGH |
| 5. Data/source card | PARTIAL | `dataset-card.md` (gốc) + thẻ dựng lại | MEDIUM |
| 6. Repository | PARTIAL | git log; không Issue/PR | HIGH |
| 7. POI pilot dataset | COMPLETED (tồn tại) / PARTIAL (chất lượng) | `places_canonical.json` | HIGH |
| 8. Weekly evidence | PARTIAL | gói này; số liệu đo lại ngày 05/10 | MEDIUM |

## 11. W2 Plan (04/10/2026 – 10/10/2026, theo đề cương)
- PostGIS schema + POI ingestion + tích hợp bản đồ. Output: **Map demo**. Dataset mục tiêu: 1k+ POI nếu có.
- Việc bổ sung thuộc W1 còn tồn: ghi ADR city scope và MVP, tạo Issue/Milestone, sửa 11 ID không thật, ghi snapshot date.

## 12. Kết luận
Trong W1 nhóm đã có pipeline OSM, tài liệu nguồn dữ liệu và pilot dataset 108 POI truy vết được tới commit. Chưa có bằng chứng về quyết định city scope và khóa MVP, chưa có Issue/PR, và chưa truy vết được đóng góp của Nguyễn Duy Khánh. Chất lượng dữ liệu pilot còn hạn chế (11 nguồn không hợp lệ, rating mặc định, địa chỉ placeholder). Các công việc từ 04/10/2026 trở đi không được tính vào báo cáo này.
