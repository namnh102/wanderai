# BÁO CÁO TIẾN ĐỘ TUẦN 1

## 1. Thông tin chung

| Mục | Nội dung |
|---|---|
| Đề tài | Xây dựng nền tảng du lịch thông minh dựa trên AI Agent, hệ thống gợi ý và kết nối bạn đồng hành |
| Nhóm | KH3 |
| Sinh viên thực hiện | Ngô Hoàng Nam; Nguyễn Duy Khánh |
| Giảng viên hướng dẫn | TS. Nguyễn Tất Thắng |
| Thời gian thực hiện đồ án | 27/09/2026 – 31/12/2026 |
| Tuần báo cáo | Tuần 1 (W1): 27/09/2026 – 03/10/2026 |
| Mốc tham chiếu | Commit `2d15a64` (03/10/2026, 15:28). Các commit từ 04/10/2026 trở đi không được tính vào báo cáo này |
| Nguồn đề cương | Không có file đề cương trong repository (*proposal source not found in repository*). Nội dung kế hoạch W1 được lấy từ đề cương do nhóm cung cấp |

## 2. Mục tiêu tuần
Theo đề cương, W1 gồm ba nhiệm vụ: chọn phạm vi thành phố, xác định nguồn dữ liệu POI cùng license, và chốt phạm vi MVP. Sản phẩm cần nộp gồm Data/source card, repository và tập dữ liệu POI thử nghiệm (pilot dataset).

## 3. Kế hoạch W1
(1) Chọn phạm vi thành phố; (2) xác định nguồn POI và license; (3) chốt MVP; (4) lập Data/source card; (5) thiết lập repository; (6) xây dựng POI pilot dataset.

## 4. Công việc đã thực hiện
Quy ước trạng thái: **V** = đã xác minh (VERIFIED); **P** = xác minh một phần (PARTIALLY VERIFIED); **N** = chưa xác minh được (NOT VERIFIED).

### 4.1 Phạm vi địa lý (Geographic Scope) — N
Không tìm thấy quyết định chọn thành phố (ADR hoặc decision log) trong W1, kể cả ở nhánh hiện tại. Hiện trạng quan sát được: pipeline Overpass sử dụng 5 vùng bao (bounding box) gồm Đà Nẵng, Hà Nội, Hội An, Nha Trang và Huế (`data/pipelines/osm/config.py`, commit `ffe7b97`, ngày 01/10). Dữ liệu thực tế tập trung ở Đà Nẵng (55 địa điểm) và Hà Nội (50 địa điểm); Hạ Long không có địa điểm nào. Phạm vi 5 vùng vượt giới hạn 1–2 thành phố mà đề cương đề ra.

**Làm rõ phạm vi sau W1 (Post-W1 Scope Clarification):** hướng "Hà Nội + Hạ Long" không có bằng chứng được quyết định trong W1 và hiện chưa được ghi nhận trong repository. Đây là định hướng sau W1, cần được ghi thành ADR khi chính thức hóa và không được tính là kết quả của W1.

### 4.2 Nguồn dữ liệu POI — P
OpenStreetMap thông qua Overpass API được chọn làm nguồn POI chính (`docs/data/data-sources.md`, `data/manifests/sources.yaml`, ADR-002; các commit `8592aea`, `b5e96db`, `ffe7b97`). Quy trình xử lý gồm thu thập, phân tích cú pháp và hợp nhất thực thể (`data/pipelines/`). Ngày lấy dữ liệu được khai báo là 01/10/2026, tuy nhiên file dữ liệu thô không có dấu thời gian. Đợt rà soát ngày 03/10 (`2d15a64`) phát hiện 11/110 bản ghi nguồn có mã OSM không tồn tại do được nhập thủ công vào file dữ liệu thô.

### 4.3 License — P
Tài liệu của nhóm ghi nhận: OSM theo ODbL 1.0 (ghi công "© OpenStreetMap contributors", chia sẻ tương tự); Wikivoyage theo CC BY-SA 3.0; Open-Meteo theo CC BY 4.0 (`sources.yaml`). Báo cáo này chưa đối chiếu độc lập với trang license gốc. Với dữ liệu đánh giá (review) nội bộ, **trạng thái license: chưa xác minh (NOT VERIFIED)**; đây là dữ liệu mẫu tự tạo và nguồn UIT-VSFC được trích dẫn trước đó đã được nhóm rút lại ở commit `4944fae`.

### 4.4 Phạm vi MVP — N
Không có ADR, issue hay tài liệu nào chốt MVP trong W1. Bằng chứng gián tiếp duy nhất là bộ công nghệ được cố định trong `AGENTS.md` (`9b36f9d`). Đối chiếu với ba năng lực nghiên cứu của đề cương tại cuối W1: lập lịch trình bằng AI mới đạt một phần (chạy được với dữ liệu giả lập, nhưng lỗi khi chạy thật ngày 03/10); gợi ý mới có mô hình cơ sở MostPop; ghép bạn đồng hành chưa có mã nguồn.

### 4.5 Tập dữ liệu POI thử nghiệm (Pilot Dataset) — V (về sự tồn tại), P (về chất lượng)
`data/curated/places_canonical.json` gồm 108 địa điểm, 110 bản ghi nguồn (đều từ `osm`), 6 nhóm danh mục (cafe 55, hotel 25, restaurant 15, attraction 9, culture 3, beach 1) và 13 trường dữ liệu. Số liệu được đo lại ngày 05/10 trên bản lưu tại `2d15a64` (`evidence/dataset-summary.txt`): không thiếu tọa độ, không có tọa độ ngoài lãnh thổ Việt Nam, không có bản ghi trùng. Tuy nhiên, cả 108 địa điểm đều mang điểm đánh giá mặc định 4,5 (số lượt đánh giá bằng 0); 66/108 địa chỉ chỉ là giá trị tạm; không có mô tả và không có giờ mở cửa; trường `city` dùng hai kiểu nhãn khác nhau (`da_nang` và `Đà Nẵng`).

### 4.6 Repository và quản lý dự án — P
Nhóm có repository GitHub riêng `namnh102/wanderai`, tệp quy tắc `AGENTS.md` và `CONTRIBUTING.md` (29/09), các nhánh theo tính năng, và 31 commit trong khoảng thời gian W1 (20 commit không tính merge). Repository **không có Issue, Pull Request, Milestone hay tag** (`gh issue list` và `gh pr list` đều trả về rỗng), chưa đáp ứng yêu cầu quản lý công việc tại mục 10 của đề cương.

## 5. Kết quả đạt được
- **Hoàn thành:** repository có quy tắc làm việc; pipeline OSM chạy lại được; pilot dataset 108 POI tồn tại và truy vết được tới commit.
- **Hoàn thành một phần:** nguồn POI và license (đã có tài liệu nhưng chưa kiểm tra độc lập, còn 11 mã nguồn sai); Data/source card (có `dataset-card.md` và `data-sources.md` gốc, thẻ hợp nhất mới là bản **dựng lại**, đánh dấu RECONSTRUCTED); quản lý dự án.
- **Chưa hoàn thành:** Issue, Pull Request, Milestone; kiểm tra chéo mã nguồn giữa hai thành viên.
- **Chưa xác minh được:** quyết định phạm vi thành phố; việc chốt MVP; phần đóng góp của từng thành viên qua Git.
- Các công việc diễn ra trong khoảng 27/09–03/10 nhưng nằm ngoài kế hoạch W1 và không được tính là kết quả W1: xác thực người dùng, trò chuyện AI, quản lý chuyến đi, AI planner bản đầu, RAG và MostPop, màn hình bản đồ (từ `d02cee7` đến `0997efa`).

## 6. Data / Source Card
Xem `evidence/data-source-card.md` (bản dựng lại ngày 05/10/2026) và các tài liệu gốc: `docs/data/data-sources.md`, `docs/data/dataset-card.md`, `data/manifests/sources.yaml`.

## 7. Bảng Planned — Done — Evidence — Problems — Next Week

| Planned | Done | Evidence | Problems | Next week |
|---|---|---|---|---|
| Chọn phạm vi thành phố | Chưa xác minh (N) | `mvp-scope-evidence.md` | Không có ADR; 5 vùng vượt giới hạn 1–2 thành phố | Ghi ADR phạm vi |
| Nguồn POI | OSM/Overpass (P) | `sources.yaml`, `ffe7b97` | 11 mã nguồn sai; dữ liệu thô không có dấu thời gian | Làm sạch, ghi ngày snapshot |
| License | Đã ghi tài liệu (P) | `data-sources.md` | Chưa đối chiếu độc lập; license dữ liệu review chưa xác minh | Rà soát license W1–W2 |
| Chốt MVP | Chưa xác minh (N) | `mvp-scope-evidence.md` | Không có decision log | Chốt MVP bằng ADR |
| Data/source card | Có tài liệu gốc (P) | `dataset-card.md` | Thẻ hợp nhất là bản dựng lại | Cập nhật theo dữ liệu thật |
| Repository | Đã có (P) | `AGENTS.md`, git log | Không có Issue/PR | Tạo Issue, Milestone, PR |
| POI pilot dataset | 108 POI (V/P) | `places_canonical.json`, `dataset-summary.txt` | Điểm đánh giá mặc định, địa chỉ tạm | Nạp vào PostGIS, chuẩn hóa |

## 8. Vấn đề và cách xử lý
1. **License và nguồn gốc dữ liệu:** 11/108 địa điểm có mã OSM không tồn tại; báo cáo chất lượng ngày 01/10 ghi "100% có nguồn" là chưa chính xác. Vấn đề được phát hiện tại `2d15a64` (03/10) và ghi vào `current-database-state.md`; chưa được sửa trong W1.
2. **Dữ liệu thiếu nhất quán:** nhãn `city` hai kiểu; điểm đánh giá mặc định 4,5; địa chỉ tạm; thiếu giờ mở cửa.
3. **Phạm vi rộng:** dùng 5 thành phố và nhiều module được triển khai sớm trước khi chốt MVP.
4. **Môi trường:** lỗi mã hóa ký tự trên Windows, ký tự null trong `.gitignore`, Prisma không hỗ trợ kiểu `vector` (`docs/daily-reports/2026-10-01.md`); ngày 03/10 máy chủ ảnh nền OSM bị chặn trên mạng của nhóm (`2026-10-03.md`).
5. **Dữ liệu đánh giá:** chưa có tập đánh giá thật; quyền truy cập VLSP 2018 và ViMACSA chưa được cấp.

## 9. Đóng góp của thành viên

Phân công dưới đây do nhóm tự khai báo, chia theo hạng mục công việc của W1 và bám theo phân vai trong đề cương (Lead A: phân tích, thiết kế và một module kỹ thuật chính; Lead B: module kỹ thuật còn lại, tích hợp và kiểm thử). Do toàn bộ commit trong W1 được thực hiện từ một tài khoản Git duy nhất (`namnh102`), Git chưa thể hiện ranh giới đóng góp theo từng cá nhân; các tạo phẩm dưới đây có thể truy vết tới commit, nhưng việc gán cho từng người dựa trên khai báo của nhóm.

| Thành viên | Công việc W1 | Tạo phẩm / Evidence | Định lượng |
|---|---|---|---|
| Ngô Hoàng Nam | Lựa chọn nguồn POI và xây dựng pipeline OSM (thu thập, phân tích, hợp nhất thực thể); ADR-002 về dữ liệu thật; viết `data-sources.md`, `data-dictionary.md`; tạo pilot dataset 108 POI | `ffe7b97`, `8592aea`, `data/pipelines/osm/`, `data/pipelines/entity_resolution/`, `places_canonical.json` | 5 tạo phẩm chính; 2 commit đại diện |
| Nguyễn Duy Khánh | Rà soát license và nguồn gốc dữ liệu (`sources.yaml`, `review-provenance.json`, `dataset-role-matrix.md`); kiểm soát chất lượng và đối soát dữ liệu (`data-quality-report.md`, `current-database-state.md`, đợt kiểm tra hồi quy 03/10); quy tắc làm việc nhóm (`AGENTS.md`, `CONTRIBUTING.md`) | `b5e96db`, `4944fae`, `bec83d0`, `173a573`, `2d15a64`, `9b36f9d` | 6 tạo phẩm chính; 6 commit đại diện |

Hai phần việc có khối lượng tương đương: một bên phụ trách thu thập và xây dựng dữ liệu, bên còn lại phụ trách xác minh nguồn, license và kiểm soát chất lượng. **Lưu ý trung thực:** Git chỉ ghi nhận một tác giả (31 commit), chưa có Issue hay Pull Request, và chưa có kiểm tra chéo giữa hai thành viên. Nhóm cam kết từ W2 mỗi thành viên commit bằng tài khoản riêng, gắn mã Issue vào commit và kiểm tra chéo qua Pull Request để đóng góp định lượng được.

## 10. Gói bằng chứng (Evidence Package)
Thư mục `docs/weekly-reports/W01/`: `evidence/git-log-W01.txt`, `dataset-summary.txt`, `data-source-card.md`, `mvp-scope-evidence.md`, `contribution-evidence.md`, `links.md`.

| Yêu cầu W1 | Trạng thái | Bằng chứng | Độ tin cậy |
|---|---|---|---|
| 1. Phạm vi thành phố | Chưa xác minh | Không có ADR; chỉ có 5 vùng bao | Cao (về việc thiếu bằng chứng) |
| 2. Nguồn POI | Một phần | `sources.yaml`, `ffe7b97` | Trung bình |
| 3. License | Một phần | `data-sources.md` | Trung bình |
| 4. MVP | Chưa xác minh | Không có decision log | Cao |
| 5. Data/source card | Một phần | `dataset-card.md` (gốc) và thẻ dựng lại | Trung bình |
| 6. Repository | Một phần | git log; không có Issue/PR | Cao |
| 7. POI pilot dataset | Hoàn thành (tồn tại) / một phần (chất lượng) | `places_canonical.json` | Cao |
| 8. Weekly evidence | Một phần | Gói bằng chứng này; số liệu đo lại ngày 05/10 | Trung bình |

## 11. Kế hoạch W2 (04/10/2026 – 10/10/2026, theo đề cương)
- Xây dựng PostGIS schema, nạp dữ liệu POI và tích hợp bản đồ. Sản phẩm: **Map demo**. Mục tiêu dữ liệu: trên 1.000 POI nếu có.
- Việc còn tồn của W1: ghi ADR về phạm vi thành phố và MVP, tạo Issue/Milestone, sửa 11 mã OSM sai, ghi ngày snapshot.

## 12. Kết luận
Trong W1, nhóm đã xây dựng pipeline OSM, lập tài liệu nguồn dữ liệu và tạo pilot dataset gồm 108 POI có thể truy vết tới commit. Nhóm chưa có bằng chứng về quyết định phạm vi thành phố và việc chốt MVP, chưa có Issue/Pull Request, và Git chưa phân tách được đóng góp của từng thành viên. Chất lượng dữ liệu pilot còn hạn chế (11 mã nguồn không hợp lệ, điểm đánh giá mặc định, địa chỉ tạm). Các công việc từ 04/10/2026 trở đi không được tính vào báo cáo này.
