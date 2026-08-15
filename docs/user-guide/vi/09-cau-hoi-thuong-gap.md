# Câu hỏi Thường gặp (FAQ)

---

## Tổng quan

### Nền tảng Pháp lý là gì?
Hệ thống AI giúp tổ chức quản lý và tra cứu tài liệu pháp lý. Chuyển đổi tài liệu thành kiến thức có cấu trúc và cung cấp câu trả lời dựa trên bằng chứng.

### Nền tảng này có thay thế luật sư không?
**Không.** Nền tảng là công cụ hỗ trợ nghiên cứu, không phải tư vấn pháp lý. Mọi quyết định pháp lý phải do con người đưa ra.

### Hỗ trợ ngôn ngữ nào?
Tối ưu cho **tiếng Việt**. Giao diện bằng tiếng Việt.

---

## Cài đặt

### Yêu cầu hệ thống?
Python 3.12+, RAM 2 GB (khuyến nghị 4 GB), ổ đĩa 500 MB.

### Có cần GPU không?
Không. MVP không yêu cầu GPU.

### Có cần internet không?
Không. Hệ thống chạy hoàn toàn ngoại tuyến.

---

## Sử dụng

### Làm sao khởi động server?
```bash
legal-platform
```

### Làm sao tải lên tài liệu?
Dùng giao diện web tại **📤 Tải lên** hoặc qua API. Xem [Tải lên Tài liệu](03-tai-lieu.md).

### Hỗ trợ định dạng nào?
PDF (`.pdf`) và Word (`.docx`).

### Giới hạn kích thước?
Tối đa 100 MB mỗi file.

### Làm sao tìm kiếm?
Dùng trang **🔍 Tra cứu**. Chọn chế độ Hybrid, Semantic hoặc Keyword.

### Làm sao hỏi đáp?
Dùng trang **❓ Hỏi đáp**. Nhập câu hỏi và nhấn Ctrl+Enter.

### Tại sao câu hỏi trả về NO_EVIDENCE?
Không tìm thấy tài liệu liên quan. Tải lên tài liệu hoặc diễn đạt lại câu hỏi.

---

## Tài liệu

### Tài liệu lưu ở đâu?
File tải lên lưu trên hệ thống file. Dữ liệu metadata lưu trong SQLite.

### Có thể xóa tài liệu không?
Có, nhưng vĩnh viễn. Dùng API: `DELETE /v1/documents/{id}`.

### Kho tài liệu là gì?
Nơi chứa tài liệu, cung cấp cách ly và kiểm soát truy cập.

### Di chuyển tài liệu giữa kho?
Chưa hỗ trợ trong MVP.

---

## Phân quyền

### Phân quyền hoạt động thế nào?
Mỗi kho có thành viên với vai trò (VIEWER, CONTRIBUTOR, MANAGER, OWNER).

### Thêm thành viên vào kho?
Hiện tại dùng API:
```bash
curl -X POST http://localhost:8080/api/v1/vaults/ID_KHO/members \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"user_id": "ten", "role": "VIEWER"}'
```

---

## Kỹ thuật

### Dùng cơ sở dữ liệu gì?
SQLite (mặc định trong bộ nhớ tạm).

### Có API không?
Có. REST API tại `/api/v1/`.

### Kiểm tra server hoạt động?
```bash
curl http://localhost:8080/api/health
```

### Xem log ở đâu?
Log ghi ra stderr dưới dạng JSON.

### Sao lưu dữ liệu?
Chưa tự động. Thiết lập lưu trữ bền vững và copy file cơ sở dữ liệu.

### Nâng cấp hệ thống?
Chưa có quy trình chính thức. Pull code mới và khởi động lại.

---

## Giới hạn MVP

### MVP chưa làm gì?
- Quy trình xử lý tài liệu tự động
- Lưu trữ bền vững mặc định
- Bộ nhớ hội thoại
- Truyền phát (streaming)
- Giới hạn tốc độ
- Xác thực đa yếu tố
- SSO / OAuth

### Khi nào có các tính năng này?
Được lên kế hoạch cho Milestone 5 (Enterprise) và Milestone 6 (Intelligence). Xem [Lộ trình](../../../tasks/019-roadmap.md).

---

## Khắc phục

### Server không khởi động
Kiểm tra cổng 8080 không bị chiếm.

### Tải lên thất bại
Kiểm tra định dạng (PDF/DOCX) và kích thước (< 100 MB).

### Tìm kiếm không có kết quả
Tải lên tài liệu trước, đảm bảo có quyền truy cập kho.

### Mất dữ liệu
Mặc định lưu trong bộ nhớ tạm. Thiết lập lưu trữ bền vững.

### Vẫn gặp vấn đề?
Xem [Khắc phục Sự cố](08-khac-phuc-su-co.md).