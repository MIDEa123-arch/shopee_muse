# Gợi ý commerce v2 — 17/10/2026

Đây là mô tả cho catalog tiếng Việt đang chạy. Các quy tắc và báo cáo 17 điều kiện của bản trước không thay thế báo cáo hiện tại [retail_audit.json](retail_audit.json).

## Các lỗi đã tìm và cách sửa

1. Tab ngành hàng trang chủ từng bỏ qua khoảng nghỉ sau mua. Nay trang chủ, ưu đãi, gợi ý tự động trong thanh tìm kiếm, tương tự ở chi tiết, giỏ, mua kèm và sau mua đều áp dụng cùng bộ lọc sở hữu. Đồ bền vừa mua được nghỉ gợi ý cùng loại 30 ngày; mẫu đã mua và các bản sao màu/ID bị loại. Tìm kiếm chủ động và Mua lại vẫn tìm được hàng.
2. Lấy top 240 dòng phổ biến trước rồi lọc loại hàng làm ứng viên bị chiếm bởi bản sao màu. Nay duyệt tuần tự tối đa 50.000 dòng, giữ đại diện theo model và dải giá. Không nạp 2 triệu dòng vào RAM.
3. Ảnh minh họa trùng từng bị coi là cùng sản phẩm, làm bốn model chuột còn một thẻ. Nay chỉ gộp model, không gộp hai model khác nhau vì chung ảnh. Giữ khác biệt đời máy/dung lượng thật; bỏ thông số sinh ngẫu nhiên và màu chưa xác thực khỏi tên hiển thị.
4. Đơn mua từng chỉ lấy món đầu tiên của đơn mới nhất và không theo tab/đơn đang xem. Nay dùng `order_id` có kiểm tra chủ sở hữu, toàn bộ món của đơn và tên/giá snapshot. Có nút **Xem gợi ý mua kèm** ở từng đơn; tab đơn hủy không mượn ngữ cảnh của đơn khác. Phản hồi chậm bị chặn nếu đã đổi ngữ cảnh.
5. Ảnh sai loại trong snapshot đơn cũ được sửa khi hiển thị theo tên snapshot. Ảnh lưu gốc vẫn giữ trong DB và trường `snapshot_image_url`; không viết lại tên/giá/shop của đơn.
6. Gợi ý lỗi mạng không chuyển sang danh sách phổ biến bất kỳ. Các khu vực có trạng thái lỗi/thử lại hoặc thông báo hết lựa chọn phù hợp.

## Dữ liệu và giới hạn model

Script [build_vietnamese_catalog.py](../scripts/build_vietnamese_catalog.py) chọn ngành hàng, template, thông số, màu và ảnh ngẫu nhiên rồi gán lên đặc trưng ID Taobao. Vì vậy tên Việt hiện tại **không có mapping ngữ nghĩa đã xác minh với SCL gốc**. Gán lại vài ID hoặc thêm dòng màu không làm checkpoint tự hiểu sản phẩm Việt.

Snapshot trước bổ sung và sửa phân loại có 155 model tên khác nhau trong 48 nhóm cũ, gồm chỉ bốn model chuột, dù bảng có 2 triệu dòng. Đã bổ sung 11 mẫu nhỏ có tên/ảnh/nguồn rõ ràng: ba chuột Logitech, bảy phụ kiện chăm sóc/bảo quản giày Crep Protect và một mẫu cầu lông. Nguồn tại [curated_retail.json](../app/recommender/curated_retail.json) và [manifest ảnh](../static/images/merchandise/sources.json). Giá, kho, thanh toán vẫn mô phỏng; không phải báo giá thị trường hay phục hồi metadata Taobao.

Snapshot sau bổ sung có 166 model trong 59 nhóm phân loại đã sửa, gồm bảy model chuột. Tìm kiếm và gợi ý cùng xét tối đa 50.000 dòng đầu; các mẫu bổ sung gần ID 50.000 không bị giới hạn tìm kiếm cũ 25.000 dòng che mất. Sản phẩm chưa có đánh giá hiện đúng trạng thái này; không hiện 0 sao hoặc huy hiệu giảm 0%.

Bổ sung dùng các dòng demo trùng chưa được tham chiếu, không đổi ID 64-bit hoặc trường đặc trưng gốc. Script bảo vệ dòng có trong đơn, giỏ, wishlist, đánh giá, lịch sử và các gợi ý gần đây; giữ đại diện cũ của từng model; lưu JSON trước thay đổi tại `data/backups/retail-curation-*.json`. Không thay checkpoint hoặc huấn luyện lại. Mapping ngữ nghĩa vẫn được ghi là chưa xác minh.

## Luồng đang chạy

Tất cả vị trí commerce dùng [retail.py](../app/recommender/retail.py): lấy đại diện model/giá → loại mẫu đã sở hữu và ngữ cảnh không hợp lệ → kiểm tra loại/phụ kiện/thông số → chấm tối đa 320 ứng viên bằng checkpoint → xếp theo nhu cầu và điểm model → gộp model.

Cách tách recall, filter, rank và re-rank tham khảo tài liệu chính thức [Alibaba PAI-Rec](https://www.alibabacloud.com/help/en/pai/use-cases/recommended-solutions-overview), [cấu hình theo từng vị trí](https://www.alibabacloud.com/help/en/pai/engine-configuration-case), [chính sách tránh lọc cạn ứng viên](https://www.alibabacloud.com/help/en/airec/airec/user-guide/recommendation-policies). Checkpoint dùng implementation [MUSE của Alibaba](https://github.com/alimama-tech/MUSE).

Thông số mặc định của **lớp commerce**, không phải trọng số học của MUSE:

- Tín hiệu mua/giỏ/thích/xem: 5/4/3/2, giảm theo thứ tự sự kiện `1/(1+0.3k)`. Mua chuyển nhu cầu sang đồ bổ trợ; không tiếp tục đẩy cùng loại đồ bền vừa mua.
- Xếp hiển thị: 65% phù hợp ngữ cảnh/giá/nhu cầu sử dụng, 30% thứ hạng checkpoint trong tập hợp lệ, 5% sao mẫu. Đây là mặc định bảo thủ cho metadata chưa xác minh, chưa được tối ưu bằng nhãn người mua.
- P(click)/cosine từng ID giữ nguyên, được trả riêng với `ranking_score`. Hai điểm checkpoint bằng nhau nhận cùng mức đóng góp, không bị tách thứ hạng tùy ý.
- Tương tự ưu tiên giá 0,5–2 lần. Nếu thiếu lựa chọn, giữ thêm model cùng loại ở phân khúc khác, ghi rõ **Tầm giá khác** trên thẻ và `broader_price` trong metadata; không lấp ngành hàng khác.
- Mua kèm theo loại/khả năng dùng cùng và giới hạn giá. Cáp Lightning không gợi ý cho Android/iPhone 15 trở lên; iPhone cổng Lightning không nhận cáp USB-C thuần. Ốp phải đúng model. Sạc laptop không chỉ dựa vào watt: cần bằng chứng chuẩn sạc PD trong tên đáng tin cậy; không dùng thông số sinh trong ngoặc. Chưa phải cơ sở dữ liệu chứng nhận tương thích mọi thiết bị.
- Đồ thể thao không được mua kèm điện tử chỉ vì điểm click cao. Giày có phụ kiện chăm sóc/bảo quản, vợt có cầu/bag/bình nước/giày thể thao. Không ghép dây giày cho mẫu ghi rõ không dây/slip-on.

## Input/output để tự kiểm tra

| Input/thao tác | Output phải thấy | Dấu hiệu lỗi |
|---|---|---|
| Đã mua Laptop Inspiron 3520; về trang chủ rồi chọn tab Laptop | Không có laptop khác tự động chen lại; có thể có chuột, phím, màn hình phù hợp | Tab bỏ qua khoảng nghỉ sau mua |
| Mở chi tiết chuột MX Master 3S | Sáu model chuột khác sau khi cài assortment bổ sung; không lặp màu/model và không còn bị giới hạn vì ảnh trùng | Chỉ một thẻ dù còn nhiều model cùng loại hợp lệ |
| Mở bàn phím, điện thoại hoặc laptop | Tối đa sáu lựa chọn cùng loại, ưu tiên nhu cầu và khoảng giá; phụ kiện nằm riêng ở mua kèm | Tai nghe bị gọi là bàn phím, hoặc điện thoại nằm trong tương tự laptop |
| Đơn vợt cầu lông Yonex, chọn đúng đơn ở Đơn mua | Cầu lông, bao vợt, bình nước, giày thể thao hợp lệ; tối thiểu sáu lựa chọn trong snapshot đã bổ sung | Laptop, sạc, tai nghe hoặc đồ điện tử |
| Đơn giày Nike Court Vision Low | Tối thiểu sáu đồ chăm sóc/bảo quản giày như lót, dây, bộ vệ sinh, túi, khử mùi, bình nước | Mua thêm laptop/điện thoại hoặc lặp giày vừa mua |
| Có đơn giày cũ và laptop mới; bấm mua kèm ở đơn giày | Header và danh sách theo đúng đơn giày, không dùng đơn laptop mới nhất | Tên đơn một nơi, sản phẩm theo đơn khác |
| Một đơn có hai loại hàng | Xét bổ trợ cho mọi món trong chính đơn đó | Chỉ xét món đầu tiên |
| Chuyển tab Đã hủy | Không hiển thị gợi ý đi kèm một đơn khác ở phần trống | Vẫn dùng đơn mới nhất bên ngoài tab |
| Chọn hàng thể thao, bỏ chọn điện thoại trong giỏ | Mua kèm chỉ dựa trên món đã chọn | Điện thoại bỏ chọn vẫn kéo gợi ý điện tử vào |
| Lấy `order_id` của khách khác | API trả 404, không lộ hàng/context của khách kia | Có thể đọc gợi ý theo đơn người khác |
| Tài khoản đã mua laptop; mở thanh tìm kiếm khi chưa gõ | Không có laptop đã bị khoảng nghỉ loại | Dropdown/ưu đãi dùng bộ lọc khác trang chủ |
| Chủ động gõ laptop hoặc Mua lại | Vẫn xem/tìm lại được sản phẩm; đây là thao tác tìm kiếm chủ động | Bộ lọc gợi ý xóa hàng khỏi catalog |
| Tắt Lab | Không có ID kỹ thuật, MUSE, vector hoặc P(click) trên thẻ mua sắm | Kỹ thuật chiếm giao diện khách |
| Bật Lab | Có ngữ cảnh, đơn, số mẫu hợp lệ/đã trả và điểm gốc để đối chiếu | Mượn 64% AUC làm % phù hợp cho danh mục Việt |
| Mất mạng ở mua kèm; sau đó thử lại | Thông báo lỗi; tương tự vẫn dùng được; retry phục hồi | Spinner vô hạn hoặc lấp bằng hàng phổ biến sai loại |

API dùng để đối chiếu trong Lab:

```text
/api/recommendations?touchpoint=home&category_id=1
/api/recommendations?touchpoint=similar&product_id=157&limit=6
/api/recommendations?touchpoint=orders&order_id=<đơn-của-bạn>&limit=12
/api/recommendations?touchpoint=post_purchase&order_id=<đơn-của-bạn>&limit=12
/api/recommendations?touchpoint=cart&limit=12
/api/recommendations/deals?limit=6
/api/recommendations/bundle?focus_product_id=157
/api/search/suggestions?q=
```

Xem `meta.focus_product_ids`, `focus_names`, `order_id`, `purchase_policy`, `retrieval`, `model_used`, `score_type`, `semantic_mapping_verified`. Những trường này phục vụ kiểm tra, không hiện thành thuật ngữ quảng cáo ở màn mua sắm.

## Phân biệt với danh sách “40 đặc trưng”

MUSE thực nhận sáu trường hồ sơ ẩn danh `129_1`, `130_1`–`130_5`, lịch sử item/category `150_2_180`/`151_2_180` tối đa 1.000 và các trường item `205`, `206`, `213`, `214`, SCL 128D qua maps. Chưa xác minh `130_2` nghĩa là hạn mức chi tiêu hay `213`/`214` là thành phố/tỉnh cụ thể. Đổi tên, tuổi, ví, hạng hội viên trên form không tự cập nhật các vector hồ sơ đã nhập.

Tên/loại/giá/nhu cầu sử dụng, sở hữu, ảnh, shop, vận chuyển, điểm chạm và trọng số hành vi là lớp commerce/nghiệp vụ. P(click), cosine, attention là kết quả/tính toán nội bộ, không phải các input độc lập thêm vào checkpoint. Forward không đọc NLP tên tiếng Việt. Vì vậy không thể kết luận “40 trường đều đã được AI học”.

## Chạy tiết kiệm RAM

Test nhỏ tự tạo SQLite, không copy database chính hoặc load model:

```bash
PYTHONPATH=.:tests .venv/bin/python -m unittest test_retail_context test_merchandise test_catalog -v
```

PowerShell:

```powershell
$env:PYTHONPATH = ".;tests"
.\.venv\Scripts\python.exe -m unittest test_retail_context test_merchandise test_catalog -v
```

Cài 11 mẫu bổ sung khi đã có catalog tiếng Việt; script mặc định dry-run, bản đang chạy đã được áp dụng:

```bash
.venv/bin/python -m scripts.install_retail_curated
.venv/bin/python -m scripts.install_retail_curated --apply
```

Sau bổ sung, restart server để bỏ cache danh mục. Trên Windows thay `.venv/bin/python` bằng `.\.venv\Scripts\python.exe`. Xem [WINDOWS.md](WINDOWS.md); Git không chứa DB/checkpoint nhiều GB.

Đối chiếu checkpoint thật và toàn bộ loại hàng, chạy tuần tự một tiến trình model, có giới hạn RAM; script chỉ đọc, không tạo log/đơn/giỏ/hành vi:

Dừng server đang chạy trước audit để không nạp model hai lần. Với dịch vụ Linux hiện tại dùng `systemctl --user stop lumi-commerce.service`, chạy audit dưới đây, sau đó bật lại bằng `./start_server.sh`. Trên Windows dừng cửa sổ server bằng Ctrl+C, chạy audit rồi mở lại script Windows.

```bash
systemd-run --user --scope -p MemoryMax=1500M -p MemorySwapMax=64M \
  .venv/bin/python -m scripts.audit_retail --output docs/retail_audit.json
```

Giao diện trên server đang chạy, không tạo đơn/giỏ/hành vi (có session demo tạm và log tải gợi ý):

```bash
systemd-run --user --scope -p MemoryMax=1000M -p MemorySwapMax=64M \
  /usr/bin/env PYTHONPATH=. TEST_BASE_URL=http://127.0.0.1:8000 \
  .venv/bin/python tests/browser_merchandise.py
```

Không chạy toàn bộ `unittest discover` trên DB 4,6 GB: các suite native/storefront cũ có thao tác copy DB. Test integration sử dụng fixture nhỏ đã kiểm tra, thao tác mua/hủy chỉ diễn ra trong DB thử.

**Số ca kiểm tra đạt là kiểm chứng chức năng, không phải phần trăm gợi ý đúng hoặc bằng chứng CTR tăng.** AUC khoảng 64% là chỉ số ranking trên dữ liệu Taobao gốc. Để đo chất lượng catalog này cần metadata gốc khớp model hoặc nhãn phản hồi người dùng trên chính catalog và tập đánh giá giữ riêng. Không thể giải quyết khoảng lệch dữ liệu đó bằng chỉnh một ngưỡng điểm.

## Kết quả kiểm tra ngày 17/10/2026

- 76 test về commerce, phân loại, ngữ cảnh, catalog và tính chỉ số đã đạt; bộ 38 test liên quan trực tiếp được chạy lại sau sửa giới hạn tìm kiếm, đạt toàn bộ. Fixture integration nhỏ, không copy DB chính 4,6 GB. Đỉnh RAM suite đầy đủ 234,6 MB, suite nhỏ 48,1 MB.
- Audit checkpoint thật: 249 điều kiện đạt, 0 lỗi; duyệt đại diện cả 59 loại. Đỉnh RAM 209,6 MB; không ghi đơn, giỏ, hành vi hoặc log gợi ý.
- Trình duyệt thật: 11 nhóm luồng đạt trên desktop/mobile, không lỗi JavaScript. Đối chiếu ID thẻ với API, sáu chuột tương tự, đơn giày tám món liên quan, xử lý lỗi/thử lại, đổi đơn/tab, mua xong và Lab. Đỉnh RAM 392,9 MB.
- Thanh tìm kiếm: 14 tình huống đạt, gồm bấm ngoài, Escape, đổi focus, phản hồi chậm và gửi tìm kiếm; đỉnh RAM 272,8 MB.
- Các lượt trên không dùng swap. Một server CPU, một worker, không huấn luyện lại. Demo công khai trả HTTP 200 và `model_ready=true` sau cập nhật.

Một số loại chỉ có một model thật sự khác nhau nên phần tương tự vẫn có thể trống. Không thêm sản phẩm sai loại chỉ để đủ sáu thẻ; báo cáo coverage ghi rõ số lượng từng loại.
