# BÁO CÁO TIẾN ĐỘ TUẦN 1

## 1. Thông tin chung

| Mục | Nội dung |
|---|---|
| Đề tài | Xây dựng nền tảng du lịch thông minh dựa trên AI Agent, hệ thống gợi ý và kết nối bạn đồng hành |
| Nhóm | KH3 |
| Sinh viên thực hiện | Ngô Hoàng Nam; Nguyễn Duy Khánh |
| Giảng viên hướng dẫn | TS. Nguyễn Tất Thắng |
| Thời gian thực hiện đồ án | 27/09/2026 – 31/12/2026 |
| Tuần báo cáo | Tuần 1: 27/09/2026 – 03/10/2026 |

## 2. Mục tiêu tuần 1

Theo kế hoạch trong đề cương, tuần đầu tiên tập trung vào ba nhiệm vụ: lựa chọn phạm vi địa lý, xác định các nguồn dữ liệu địa điểm (POI) cùng điều kiện sử dụng, và chốt phạm vi sản phẩm khả thi tối thiểu (MVP). Các sản phẩm cần có vào cuối tuần gồm thẻ mô tả nguồn dữ liệu (Data/source card), repository của nhóm và một tập dữ liệu POI thử nghiệm (pilot dataset).

## 3. Tổng quan tiến độ

Cuối tuần 1, nhóm đã thiết lập repository, xác định OpenStreetMap (OSM) làm nguồn POI chính và xây dựng được pilot dataset gồm 108 địa điểm. Bên cạnh đó, nhóm chưa hoàn tất việc ban hành quyết định chính thức về phạm vi địa lý và phạm vi MVP dưới dạng tài liệu, đồng thời quy trình quản lý công việc trên GitHub (Issue, Pull Request, Milestone) chưa được sử dụng. Quá trình kiểm tra pilot dataset cũng cho thấy một số vấn đề về nguồn gốc và chất lượng dữ liệu cần được xử lý trước khi dữ liệu được dùng cho các bước đánh giá tiếp theo.

| Hạng mục | Trạng thái | Kết quả |
|---|---|---|
| Phạm vi địa lý | Đang hoàn thiện | Chưa có quyết định chính thức bằng tài liệu |
| Nguồn POI | Đã xác định | OSM (Overpass API) là nguồn chính |
| License | Đang hoàn thiện | Đã ghi nhận trong tài liệu nguồn dữ liệu, chưa đối chiếu độc lập |
| MVP | Đang hoàn thiện | Có định hướng nghiên cứu, chưa có decision record |
| Pilot dataset | Đã có | 108 POI |
| Repository | Đã thiết lập | Có Git và tài liệu quy tắc làm việc |

## 4. Công việc thực hiện

### 4.1 Xác định phạm vi nghiên cứu

Đề cương giới hạn đề tài trong một đến hai địa bàn có dữ liệu mở. Cuối tuần 1, nhóm chưa ban hành quyết định phạm vi địa lý bằng tài liệu chính thức (ADR hoặc decision log). Pipeline thử nghiệm khi đó được cấu hình cho năm khu vực gồm Đà Nẵng, Hà Nội, Hội An, Nha Trang và Huế, nên phạm vi dữ liệu ban đầu rộng hơn định hướng của đề cương. Trên thực tế, dữ liệu thu được tập trung ở Đà Nẵng (55 địa điểm) và Hà Nội (50 địa điểm), mỗi khu vực còn lại chỉ có một địa điểm; Hạ Long chưa có dữ liệu trong snapshot của tuần này.

**Định hướng điều chỉnh sau W1.** Hướng thu hẹp phạm vi về Hà Nội và Hạ Long là định hướng của nhóm sau thời điểm kết thúc W1. Hiện chưa có tài liệu ghi nhận quyết định này trong repository, vì vậy nội dung này không được tính là kết quả của tuần 1 và sẽ được chính thức hóa bằng một decision record.

### 4.2 Khảo sát nguồn dữ liệu POI

Nhóm lựa chọn OpenStreetMap, khai thác qua Overpass API, làm nguồn POI chính vì đây là dữ liệu mở, có tọa độ và có thể truy xuất lại. Quy trình xử lý gồm ba bước: thu thập dữ liệu, chuẩn hóa thuộc tính và hợp nhất các bản ghi trùng thành địa điểm chuẩn (canonical place). Nhóm cũng đã định nghĩa cấu trúc lưu vết nguồn gốc (`place_sources`) và khai báo các nguồn trong tệp `sources.yaml`. Ngày thu thập được ghi nhận là 01/10/2026; tuy nhiên, tệp dữ liệu thô không lưu dấu thời gian, nên thông tin này hiện chỉ dựa trên khai báo của nhóm.

### 4.3 Kiểm tra điều kiện sử dụng và license

Nhóm ghi nhận OSM sử dụng giấy phép ODbL 1.0 (yêu cầu ghi công "© OpenStreetMap contributors" và chia sẻ tương tự), Wikivoyage sử dụng CC BY-SA 3.0 và Open-Meteo sử dụng CC BY 4.0. Tuy nhiên, tại thời điểm W1, việc đối chiếu độc lập với trang giấy phép gốc chưa được hoàn tất. Đối với tập đánh giá (review) nội bộ, nhóm nhận thấy nguồn trích dẫn ban đầu (UIT-VSFC) là bộ dữ liệu phản hồi của sinh viên chứ không phải đánh giá du lịch, nên đã rút lại trích dẫn này; dữ liệu hiện chỉ là mẫu thử nghiệm và chưa có license được xác minh, do đó không được dùng cho các bước phát triển AI.

### 4.4 Xác định phạm vi MVP

Trong W1, nhóm chưa hoàn tất tài liệu chốt phạm vi MVP dưới dạng decision record. Tuy nhiên, định hướng nghiên cứu đã xoay quanh ba năng lực chính của đề cương: lập lịch trình bằng AI Agent, gợi ý theo sở thích và ngữ cảnh, và ghép bạn đồng hành có kiểm soát an toàn. Tại thời điểm cuối tuần, lập lịch trình bằng AI mới ở mức một phần (chạy được với dữ liệu giả lập nhưng gặp lỗi khi chạy thật ngày 03/10), phần gợi ý mới có mô hình cơ sở MostPop, và phần ghép bạn đồng hành chưa có mã nguồn. Bộ công nghệ của dự án đã được cố định trong tài liệu quy tắc của repository.

### 4.5 Xây dựng pilot dataset

Pilot dataset được tạo từ dữ liệu OSM sau bước chuẩn hóa và hợp nhất. Các chỉ số dưới đây được đo hồi cứu vào ngày 05/10/2026 trên snapshot cuối W1 nhằm phục vụ kiểm tra, không thay đổi thời điểm của công việc.

| Chỉ số | Kết quả |
|---|---:|
| Số POI | 108 |
| Bản ghi nguồn (source records) | 110 |
| Nhóm danh mục | 6 |
| Số trường dữ liệu | 13 |
| Bản ghi thiếu tọa độ | 0 |
| Bản ghi trùng | 0 |
| Địa chỉ tạm (chưa phải địa chỉ thật) | 66 |
| Bản ghi có mô tả | 0 |
| Bản ghi có giờ mở cửa | 0 |
| Điểm đánh giá mặc định 4,5 | 108 |
| Mã nguồn OSM không hợp lệ | 11 |

Các số liệu cho thấy tập dữ liệu đủ về tọa độ và không trùng lặp, nhưng chưa đầy đủ về thông tin mô tả. Điểm đánh giá 4,5 là giá trị mặc định do pipeline gán khi không có dữ liệu, không phải điểm đánh giá thực tế của người dùng, nên chưa phù hợp để dùng trong các bước xếp hạng hoặc đánh giá. Tương tự, 66 địa chỉ hiện chỉ là giá trị tạm ghép từ tên và thành phố, chưa bảo đảm chính xác thực tế. Trong 110 bản ghi nguồn, 11 bản ghi có mã OSM không tồn tại hoặc trỏ tới địa điểm không liên quan, đều xuất phát từ các mục được nhập thủ công vào tệp dữ liệu thô; 97 địa điểm còn lại đã được đối chiếu thành công với Overpass.

### 4.6 Thiết lập repository và quy trình làm việc

Repository riêng của nhóm đã được thiết lập, kèm theo tài liệu quy tắc làm việc (`AGENTS.md`, `CONTRIBUTING.md`) và các nhánh theo tính năng. Trong tuần, nhóm ghi nhận 31 commit (20 commit không tính merge). Tuy nhiên, quy trình quản lý công việc chưa được chuẩn hóa đầy đủ: repository chưa có Issue, Pull Request và Milestone. Nhóm xác định đây là điểm cần cải thiện từ tuần 2.

Trong cùng khoảng thời gian, nhóm cũng bắt đầu sớm một số hạng mục thuộc các tuần sau (xác thực người dùng, trò chuyện với AI, quản lý chuyến đi, bản đồ). Các hạng mục này nằm ngoài kế hoạch W1 và không được tính vào kết quả của tuần này. Tương tự, các phát triển được thực hiện sau thời điểm kết thúc W1 không được tính vào kết quả của tuần này và sẽ được phản ánh trong các báo cáo tiếp theo.

## 5. Kết quả chính

Vào cuối W1, nhóm thực sự có: (1) repository cùng quy tắc làm việc; (2) quyết định sử dụng OSM/Overpass làm nguồn POI chính, kèm quy trình thu thập và chuẩn hóa chạy lại được; (3) pilot dataset 108 POI; (4) các tài liệu nền tảng về nguồn dữ liệu và nguồn gốc dữ liệu; (5) danh sách các vấn đề về chất lượng và provenance đã được phát hiện. Phạm vi địa lý và MVP chưa được chính thức hóa.

| Kế hoạch | Đã thực hiện | Minh chứng | Vấn đề | Tuần tiếp theo |
|---|---|---|---|---|
| Phạm vi địa lý | Chạy thử 5 khu vực; chưa có quyết định chính thức | Mục 4.1; `mvp-scope-evidence.md` | Phạm vi rộng hơn đề cương | Ban hành decision record |
| Nguồn POI và license | Chọn OSM; ghi nhận license trong tài liệu | `data-sources.md`, `sources.yaml` | 11 mã nguồn không hợp lệ; chưa đối chiếu license độc lập | Kiểm chứng nguồn, đối chiếu license |
| MVP | Có định hướng, chưa có decision record | `mvp-scope-evidence.md` | Thiếu tài liệu chốt MVP | Chốt MVP bằng tài liệu |
| Data/source card | Có `dataset-card.md`, `data-sources.md`; thẻ hợp nhất được dựng lại sau đó | `data-source-card.md` | Thẻ hợp nhất không được tạo trong W1 | Cập nhật theo dữ liệu thật |
| Repository | Đã thiết lập | Git, `AGENTS.md` | Chưa có Issue/PR/Milestone | Chuẩn hóa quy trình |
| Pilot dataset | 108 POI | `dataset-summary.txt` | Rating mặc định, địa chỉ tạm | Chuẩn hóa và nạp vào PostGIS |

## 6. Các vấn đề và bài học rút ra

| Vấn đề | Ảnh hưởng | Bài học / hướng xử lý |
|---|---|---|
| Phạm vi địa lý và MVP chưa được chính thức hóa | Khó kiểm soát phạm vi; dữ liệu trải rộng 5 khu vực | Ban hành decision record và thu hẹp phạm vi theo đề cương |
| 11 mã nguồn OSM không hợp lệ | Ảnh hưởng độ tin cậy về nguồn gốc dữ liệu | Việc xác nhận provenance cần thực hiện độc lập với bước thu thập; kiểm chứng toàn bộ mã nguồn |
| Điểm đánh giá mặc định 4,5 | Không thể xem là đánh giá thực tế | Loại khỏi các phép tổng hợp, xếp hạng và đánh giá |
| 66 địa chỉ tạm; thiếu mô tả và giờ mở cửa | Không bảo đảm chính xác thực tế | Chuẩn hóa dữ liệu, bổ sung từ OSM và dùng giá trị dự phòng rõ ràng |
| Nhãn thành phố không thống nhất (`da_nang` và `Đà Nẵng`) | Gây sai lệch khi thống kê và lọc theo khu vực | Chuẩn hóa nhãn trong bước normalization |
| Chưa có Issue/Pull Request/Milestone | Khó truy vết công việc và đóng góp | Chuẩn hóa quy trình từ tuần 2 |
| Dữ liệu đánh giá chưa có license được xác minh | Chưa thể dùng cho các bước phát triển AI | Tìm nguồn dữ liệu được cấp phép; chờ phê duyệt truy cập VLSP 2018 và ViMACSA |
| Môi trường (mã hóa ký tự trên Windows, kiểu `vector` trong Prisma, máy chủ ảnh nền OSM bị chặn trên mạng của nhóm) | Làm chậm tích hợp | Ghi nhận cách xử lý trong nhật ký hằng ngày của dự án |

## 7. Đóng góp của thành viên

Ngô Hoàng Nam tập trung vào xây dựng pipeline thu thập và chuẩn hóa POI, cùng với tài liệu nguồn dữ liệu và pilot dataset. Nguyễn Duy Khánh tập trung vào kiểm tra provenance, license, chất lượng dữ liệu và quy tắc quản lý repository. Hai phần việc có khối lượng tương đương: một bên phụ trách thu thập và xây dựng dữ liệu, bên còn lại phụ trách xác minh nguồn, license và kiểm soát chất lượng.

**Lưu ý về truy vết.** Trong W1, các commit đều được ghi nhận dưới một tài khoản Git, do đó Git chưa đủ khả năng chứng minh độc lập đóng góp của từng thành viên. Việc phân công trong báo cáo được đối chiếu với các tạo phẩm (artifact) và khai báo của nhóm. Từ tuần 2, mỗi thành viên sẽ commit bằng tài khoản riêng, gắn mã Issue vào commit và kiểm tra chéo qua Pull Request.

## 8. Minh chứng

Các minh chứng chi tiết (nhật ký Git, phép đo dataset, thẻ nguồn dữ liệu, kết quả rà soát MVP và đóng góp) được lưu tại `docs/weekly-reports/W01/evidence/`:

- `git-log-W01.txt` – danh sách commit trong tuần và mức độ liên quan đến W1;
- `dataset-summary.txt` – thống kê pilot dataset (đo hồi cứu trên snapshot cuối W1);
- `data-source-card.md` – thẻ nguồn dữ liệu (dựng lại từ các tài liệu có sẵn);
- `mvp-scope-evidence.md` – kết quả rà soát phạm vi địa lý và MVP;
- `contribution-evidence.md` – cơ sở truy vết đóng góp;
- `links.md` – bảng tổng hợp liên kết minh chứng.

Tài liệu gốc trong W1: `docs/data/data-sources.md`, `docs/data/dataset-card.md`, `data/manifests/sources.yaml`. Bản báo cáo dạng audit trước khi biên tập được giữ tại `weekly-report-W01-audit-draft.md`.

## 9. Công việc chuyển tiếp sang W2

**Kế hoạch chính của W2 (04/10/2026 – 10/10/2026, theo đề cương):** thiết kế PostGIS schema, nạp dữ liệu POI (POI ingestion) và tích hợp bản đồ. Sản phẩm: Map demo. Mục tiêu dữ liệu: trên 1.000 POI nếu có.

**Việc cần hoàn thiện từ W1:** ban hành decision record cho phạm vi địa lý và MVP; tạo Issue và Milestone, chuyển sang quy trình Pull Request; xử lý 11 mã nguồn OSM không hợp lệ; ghi rõ ngày snapshot dữ liệu; đối chiếu license với nguồn gốc.

## 10. Kết luận

Trong tuần đầu tiên, nhóm đã hoàn thành phần lớn công việc chuẩn bị cho giai đoạn phát triển dữ liệu, bao gồm xác định nguồn POI, xây dựng pilot dataset và thiết lập repository. Quá trình kiểm tra cũng cho thấy một số vấn đề về provenance, chất lượng dữ liệu và quản lý phạm vi cần được xử lý trước khi dữ liệu được sử dụng cho các bước tiếp theo. Sang tuần 2, nhóm tập trung hoàn thiện schema PostGIS, pipeline ingestion và tích hợp bản đồ.
