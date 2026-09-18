# Thư viện pháp lý — hướng dẫn nhanh

Từ phiên bản **0.2.4**, giao diện trình duyệt và cửa sổ máy chủ mặc định dùng **tiếng Việt**. Bạn vẫn có thể chọn **English** tại mục **Ngôn ngữ / Language**.

## Chọn ngôn ngữ

- **Trong trình duyệt:** mục Ngôn ngữ / Language nằm phía trên trang, kể cả trước khi đăng nhập. Lựa chọn được nhớ trên trình duyệt này cho địa chỉ thư viện hiện tại, qua các lần tải lại và đăng xuất. Trình duyệt hoặc địa chỉ khác mặc định dùng tiếng Việt. Đây không phải cài đặt đồng bộ theo tài khoản.
- Đổi ngôn ngữ sẽ tải lại trang. Nếu có nội dung chưa lưu hoặc tệp đang chọn, hệ thống hỏi trước khi đổi. Không thể đổi khi một lô tài liệu đang tải lên.
- **Trong cửa sổ máy chủ Windows:** chọn ngôn ngữ ở đầu cửa sổ. Nhãn và trạng thái được cập nhật ngay, không dừng máy chủ. Lựa chọn này độc lập với ngôn ngữ của trình duyệt.

Ngôn ngữ chỉ áp dụng cho giao diện, thông báo thông dụng và nhãn nguồn khi xuất câu trả lời. Tên người dùng, tên tài liệu, tệp gốc, nội dung trích dẫn, địa chỉ API và tên mô hình không được dịch. Thông báo kỹ thuật chưa có bản dịch được giữ nguyên để phục vụ kiểm tra lỗi. Hộp chọn tệp của Windows và thông báo kiểm tra biểu mẫu của trình duyệt có thể dùng ngôn ngữ hệ điều hành/trình duyệt.

## Cài đặt và sử dụng lần đầu

1. Giải nén toàn bộ tệp **Legal-Library-0.2.4-Windows-x64.zip**. Giữ thư mục `_internal` cạnh **LegalLibrary.exe**.
2. Mở **LegalLibrary.exe**, chọn **Thư mục dữ liệu thư viện** trên ổ đĩa cục bộ và giữ **Dùng HTTPS**. Cổng mặc định là **8443**.
3. Chọn **Khởi động máy chủ**, rồi **Mở thư viện**. Nhờ quản trị viên CNTT thiết lập tin cậy chứng chỉ HTTPS cho các máy sử dụng thư viện; nút **Chứng chỉ HTTPS…** cho phép xuất chứng chỉ công khai.
4. Dùng mã thiết lập hiển thị trong cửa sổ máy chủ để **Tạo quản trị viên** trên trang web. Mật khẩu cần ít nhất 12 ký tự.
5. Vào **Bộ sưu tập → Tạo bộ sưu tập**. Chọn **Tải tài liệu lên** để thêm PDF hoặc DOCX và chờ trạng thái **Sẵn sàng**.
6. Mở **Hỏi đáp tài liệu**, chọn bộ sưu tập và đặt câu hỏi. Dùng **Kiểm tra nguồn** và **Tải bản gốc xuống** để đối chiếu đoạn trích trước khi sử dụng.

## Chia sẻ với đồng nghiệp

Trên máy chủ, chọn **Cho phép truy cập LAN…** để mở cổng thư viện trong mạng riêng; Windows yêu cầu quyền quản trị viên. Gửi đồng nghiệp địa chỉ như `https://192.168.1.20:8443`, thay IP bằng địa chỉ hiển thị trên máy chủ của bạn. Máy chủ cần luôn bật và kết nối mạng.

Trong **Người dùng**, tạo lời mời hoặc phê duyệt tài khoản đang chờ. Trong **Chia sẻ** của bộ sưu tập, cấp quyền đọc, đóng góp hoặc quản lý. Có tài khoản không đồng nghĩa với được xem mọi tài liệu.

## Đọc bản quét và dùng Ollama trên máy khác

Trong **Cài đặt máy chủ → Đọc PDF dạng quét (OCR)**, chọn Tesseract, mô hình thị giác không cần Tesseract, hoặc Tesseract với mô hình thị giác dự phòng. Nhập địa chỉ, tên mô hình hỗ trợ ảnh và khóa API nếu cần; đồng ý gửi ảnh trang quét, chọn **Kiểm tra OCR**, rồi **Lưu cài đặt OCR**. Với tài liệu bị lỗi, mở **Chi tiết → Xử lý lại**. OCR thị giác có thể đọc sai hoặc tạo thêm nội dung; hãy đối chiếu với bản gốc.

Nếu Ollama chạy trên PC khác, dùng địa chỉ của PC đó, ví dụ `http://192.168.1.50:11434/v1`, và bật **Cho phép nhà cung cấp này trên mạng nội bộ** ở phần AI hoặc OCR tương ứng. Trên PC chạy Ollama, cấu hình `OLLAMA_HOST` để nhận kết nối LAN, khởi động lại Ollama và cho phép cổng qua tường lửa trong phạm vi tin cậy. `localhost` chỉ máy đang chạy thư viện, không phải PC khác. Xem [hướng dẫn OCR và Ollama chi tiết bằng tiếng Anh](OCR-AND-OLLAMA.md).

## Nâng cấp và sao lưu

Trước khi nâng cấp, chọn **Sao lưu thư viện…**, giữ mật khẩu sao lưu an toàn và dừng máy chủ/dịch vụ. Giải nén ứng dụng mới vào thư mục chương trình riêng, giữ nguyên thư mục dữ liệu và chọn lại thư mục đó. Phiên bản 0.2.4 không yêu cầu chuyển đổi cơ sở dữ liệu. Nếu chạy dạng dịch vụ Windows, làm theo [các bước nâng cấp dịch vụ](WINDOWS-QUICKSTART.md).

Không chia sẻ khóa API, mật khẩu hoặc `tls/server.key`. Dùng **Khôi phục bản sao lưu…** vào một thư mục trống khi cần phục hồi. Bản sao lưu chứa cài đặt OCR cần phiên bản 0.2.3 trở lên để khôi phục. Ngôn ngữ trình duyệt và cửa sổ máy chủ là tùy chọn thiết bị, không nằm trong bản sao lưu thư viện.
