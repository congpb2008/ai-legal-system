# Bắt đầu nhanh

Hướng dẫn này giúp bạn khởi động server, đăng nhập và sử dụng nền tảng lần đầu tiên.

---

## Bước 1: Khởi động server

```bash
cd legal-platform
source .venv/bin/activate
legal-platform
```

Hoặc tương đương:

```bash
python -m legal_platform
```

Kết quả mong đợi:
```
Platform API listening on http://0.0.0.0:8080
  Health:  http://0.0.0.0:8080/health
  API v1:  http://0.0.0.0:8080/api/v1/...
```

Mở trình duyệt và truy cập: `http://localhost:8080`

> **Lưu ý:** Nhấn `Ctrl+C` để dừng server.

Để thay đổi host hoặc port:

```bash
legal-platform --host 127.0.0.1 --port 9000
```

Hoặc dùng biến môi trường:

```bash
LEGAL_PLATFORM_HOST=127.0.0.1 LEGAL_PLATFORM_PORT=9000 legal-platform
```

---

## Bước 2: Cấu hình AI lần đầu

Ở lần mở đầu tiên, nhập Base URL OpenAI-compatible (với Ollama thường là `http://localhost:11434/v1`), model sinh câu trả lời, API key nếu provider yêu cầu, timeout và ngân sách token. Nếu model suy luận dùng hết ngân sách mà không trả nội dung hiển thị, chọn mức suy luận **Tắt / none**; có thể giữ giới hạn đầu ra hợp lý như 4096 token. Nút **Kiểm tra kết nối** phải thành công trước khi hoàn tất.

Semantic search còn cần endpoint Ollama native cho embedding. Có thể cấu hình riêng bằng `LEGAL_PLATFORM_EMBEDDING_BASE_URL`, `LEGAL_PLATFORM_EMBEDDING_MODEL` và `LEGAL_PLATFORM_EMBEDDING_API_KEY`.

---

## Bước 3: Đăng nhập

1. Mở `http://localhost:8080` trong trình duyệt
2. Nhập tên đăng nhập và mật khẩu (bất kỳ giá trị nào cũng được)
3. Nhấn **Đăng nhập**

Ví dụ:
```
Tên đăng nhập: admin
Mật khẩu: admin
```

Sau khi đăng nhập, bạn sẽ thấy trang chủ với các chức năng chính.

---

## Bước 4: Tạo kho tài liệu

1. Nhấn **📁 Kho tài liệu** trên thanh sidebar
2. Nhấn **+ Tạo mới**
3. Nhập tên (ví dụ: "Tài liệu của tôi")
4. Nhập loại: `DEPARTMENT`
5. Kho tài liệu mới sẽ xuất hiện trong danh sách

## Bước 5: Tải lên tài liệu

1. Nhấn **📤 Tải lên** trên thanh sidebar
2. Chọn file PDF hoặc DOCX
3. Nhập tiêu đề (ví dụ: "Quy chế mua sắm máy chủ")
4. Nhập cơ quan ban hành (ví dụ: "Phòng CNTT")
5. Chọn kho tài liệu đã tạo
6. Nhấn **Tải lên**

Để tải nhiều file, dùng **Tải lên thư mục**. File khóa Microsoft Office bắt đầu bằng `~$` được bỏ qua và báo rõ trong tổng kết. Chờ trạng thái xử lý thành `READY`; trạng thái `FAILED` có lý do cụ thể trong chi tiết tài liệu/công việc.

---

## Bước 6: Tra cứu

1. Nhấn **🔍 Tra cứu** trên thanh sidebar
2. Chọn chế độ tìm kiếm:
   - **Hybrid** (khuyến nghị) — kết hợp từ khóa và ngữ nghĩa
   - **Semantic** — tìm theo ý nghĩa
   - **Keyword** — tìm theo từ khóa chính xác
3. Nhập câu hỏi (ví dụ: "quy định mua sắm máy chủ")
4. Nhấn **Tìm kiếm**

Kết quả hiển thị điểm số liên quan, trích dẫn và nội dung.

---

## Bước 7: Hỏi đáp

1. Nhấn **❓ Hỏi đáp** trên thanh sidebar
2. Nhập câu hỏi (ví dụ: "Quy định về mua sắm máy chủ là gì?")
3. Nhấn `Ctrl+Enter` hoặc **Gửi câu hỏi**

Câu trả lời bao gồm trạng thái, mức độ tin cậy, nội dung và trích dẫn. Mở trích dẫn rồi chọn **Xem nguồn** để đối chiếu node/trang, hoặc **Tải bản gốc**. Câu hỏi không có bằng chứng trả về `NO_EVIDENCE` và không tạo trích dẫn giả.

---

## Tiếp theo

- [Tải lên tài liệu](03-tai-lieu.md)
- [Tìm kiếm](04-tim-kiem.md)
- [Hỏi đáp](05-hoi-dap.md)
- [Quản lý tài liệu](06-quan-ly-tai-lieu.md)
