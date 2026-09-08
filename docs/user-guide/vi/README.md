> Historical prototype documentation. For the implemented LAN release, use the [Windows quickstart](../../WINDOWS-QUICKSTART.md) and [maintainer guide](../../MAINTAINER-GUIDE.md). Account, setup, UI and deployment instructions below may be outdated.

# Hướng dẫn sử dụng Nền tảng Pháp lý

> Nền tảng pháp lý thông minh — chuyển đổi tài liệu pháp lý thành kiến thức có cấu trúc và cung cấp câu trả lời dựa trên bằng chứng, có thể truy xuất nguồn gốc.

---

## Tài liệu hướng dẫn

| # | Tài liệu | Mô tả |
|---|----------|-------|
| 01 | [Cài đặt](01-cai-dat.md) | Hướng dẫn cài đặt hệ thống |
| 02 | [Bắt đầu nhanh](02-bat-dau-nhanh.md) | Khởi động server và sử dụng cơ bản |
| 03 | [Tải lên tài liệu](03-tai-lieu.md) | Cách tải lên và quản lý tài liệu |
| 04 | [Tìm kiếm](04-tim-kiem.md) | Tra cứu thông tin pháp lý |
| 05 | [Hỏi đáp](05-hoi-dap.md) | Đặt câu hỏi và nhận câu trả lời |
| 06 | [Quản lý tài liệu](06-quan-ly-tai-lieu.md) | Quản lý kho tài liệu và quyền truy cập |
| 07 | [Cấu hình](07-cau-hinh.md) | Các tùy chọn cấu hình hệ thống |
| 08 | [Khắc phục sự cố](08-khac-phuc-su-co.md) | Giải quyết các vấn đề thường gặp |
| 09 | [Câu hỏi thường gặp](09-cau-hoi-thuong-gap.md) | FAQ |

---

## Tổng quan

Nền tảng Pháp lý là một hệ thống AI giúp tổ chức quản lý và tra cứu tài liệu pháp lý. Hệ thống:

- Chuyển đổi tài liệu pháp lý thành kiến thức có cấu trúc
- Tìm kiếm thông minh với kết hợp từ khóa và ngữ nghĩa
- Tạo câu trả lời dựa trên bằng chứng với trích dẫn có thể truy xuất
- Đảm bảo mọi thông tin đều có nguồn gốc rõ ràng

## Đối tượng sử dụng

Nền tảng được thiết kế cho:
- **Chuyên viên pháp chế** — tra cứu văn bản pháp luật
- **Chuyên viên tuân thủ** — kiểm tra quy định nội bộ
- **Quản lý tri thức** — tổ chức và quản lý tài liệu
- **Nhân viên phòng ban** — tra cứu chính sách, quy trình

## Bắt đầu

1. [Cài đặt hệ thống](01-cai-dat.md)
2. [Khởi động server và đăng nhập](02-bat-dau-nhanh.md)
3. [Tải lên tài liệu đầu tiên](03-tai-lieu.md)
4. [Tra cứu thông tin](04-tim-kiem.md)
5. [Đặt câu hỏi](05-hoi-dap.md)

## Lưu ý quan trọng

> ⚠️ Nền tảng này là công cụ hỗ trợ nghiên cứu, **không phải** tư vấn pháp lý. Mọi quyết định pháp lý cuối cùng phải do con người đưa ra.

> ⚠️ Phiên bản MVP hiện tại lưu trữ dữ liệu trong bộ nhớ tạm. Dữ liệu sẽ bị mất khi khởi động lại server. Vui lòng xem [Cấu hình](07-cau-hinh.md) để thiết lập lưu trữ bền vững.