# Cấu hình

Hướng dẫn này giải thích các tùy chọn cấu hình hệ thống.

---

## Tổng quan

Nền tảng có trình cấu hình provider lần đầu và hỗ trợ biến môi trường cho server, dữ liệu bền vững và embedding.

---

## Cấu hình Server

### Cổng kết nối

Mặc định server lắng nghe tại `0.0.0.0:8080`. Để thay đổi khi khởi động:

```bash
legal-platform --host 127.0.0.1 --port 9000
```

Hoặc dùng biến môi trường:

```bash
LEGAL_PLATFORM_HOST=127.0.0.1 LEGAL_PLATFORM_PORT=9000 legal-platform
```

Nếu dùng trực tiếp `PlatformAPI` trong mã nguồn:

```python
from legal_platform.api.server import PlatformAPI

api = PlatformAPI(host='127.0.0.1', port=9000)
```

### Kích thước tải lên tối đa

Mặc định 100 MB. Để thay đổi:

```python
from legal_platform.modules.upload_service.service import UploadService

upload_service = UploadService(max_upload_bytes=500 * 1024 * 1024)  # 500 MB
```

---

## Cấu hình lưu trữ

### Cơ sở dữ liệu và file nguồn

Runtime chính dùng SQLite bền vững tại `$LEGAL_PLATFORM_DATA_DIR/db/legal_platform.db` và file nguồn tại `$LEGAL_PLATFORM_DATA_DIR/files`. Nếu không đặt biến, thư mục `storage/` của dự án được dùng. Không đổi root giữa các lần khởi động nếu muốn giữ corpus/index.

### File tải lên

Mặc định lưu trong thư mục tạm. Để thay đổi:

```python
from legal_platform.modules.upload_service.file_storage import LocalFileStorage

file_storage = LocalFileStorage(base_path='/đường/dẫn/đến/data/uploads')
```

---

## Cấu hình Reranker

| Tham số | Mặc định | Mô tả |
|---------|----------|-------|
| `max_evidence` | 8 | Số lượng bằng chứng tối đa |
| `min_score` | 0.2 | Ngưỡng điểm tối thiểu |
| `diversity_weight` | 0.0 | Tín hiệu lexical bổ sung (0–1) |
| `freshness_weight` | 0.1 | Trọng số mới (0–1) |
| `authority_weight` | 0.1 | Trọng số thẩm quyền (0–1) |

---

## Cấu hình Logging

Mặc định ghi log ở mức `INFO` ra stderr.

```python
from legal_platform.modules.observability.logger import StructuredLogger

logger = StructuredLogger("dịch-vụ", "mô-đun", level="WARN")
```

Các mức: `DEBUG`, `INFO`, `WARN`, `ERROR`

---

## Cảnh báo mặc định

| Quy tắc | Chỉ số | Ngưỡng | Mức |
|---------|--------|--------|-----|
| Độ trễ tìm kiếm | `retrieval.latency_ms` | > 2000ms | WARNING |
| Độ trễ tìm kiếm nghiêm trọng | `retrieval.latency_ms` | > 5000ms | CRITICAL |
| Độ trễ sinh câu trả lời | `generation.latency_ms` | > 5000ms | WARNING |
| Tỷ lệ lỗi OCR | `ocr.failure_count` | > 5 | WARNING |

---

## Biến môi trường chính

- `LEGAL_PLATFORM_HOST`, `LEGAL_PLATFORM_PORT`: địa chỉ/cổng HTTP.
- `LEGAL_PLATFORM_DATA_DIR`: root bền vững chứa DB, file nguồn và cấu hình provider.
- `LEGAL_PLATFORM_EMBEDDING_BASE_URL`: Ollama native base URL (không thêm `/v1`).
- `LEGAL_PLATFORM_EMBEDDING_MODEL`: model embedding, mặc định `bge-m3:567m-fp16`.
- `LEGAL_PLATFORM_EMBEDDING_API_KEY`: khóa tương thích nếu endpoint yêu cầu.
- `LEGAL_PLATFORM_EMBEDDING_TIMEOUT`: timeout embedding.

Provider sinh câu trả lời được lưu bởi trình setup (quyền file `0600`). Không ghi API key vào log hoặc commit.

## OCR tài liệu scan

DOCX và PDF có lớp text được trích xuất trực tiếp. PDF chỉ chứa ảnh cần Tesseract và dữ liệu ngôn ngữ tiếng Việt trên máy chạy server. Nếu thiếu, tài liệu ở trạng thái `FAILED` với lý do quan sát được; cài dependency rồi chạy Re-OCR cho đúng tài liệu trong trang Quản trị.

---

## Tiếp theo

- [Khắc phục sự cố](08-khac-phuc-su-co.md)
- [Câu hỏi thường gặp](09-cau-hoi-thuong-gap.md)
