# Hướng dẫn API — Nền tảng Pháp lý

Tài liệu này mô tả REST API của Nền tảng Pháp lý.

**Base URL:** `http://localhost:8080/api`

**Xác thực:** Tất cả endpoint trừ `/health`, `/ready`, `/live` và `/v1/auth/login` đều yêu cầu token Bearer trong header `Authorization`.

**Content-Type:** `application/json` cho tất cả request và response.

---

## Định dạng Response

Mọi response API đều theo định dạng chuẩn:

```json
{
  "request_id": "uuid",
  "timestamp": "2026-08-07T10:00:00+00:00",
  "status": 200,
  "success": true,
  "data": { ... },
  "error": null,
  "warnings": []
}
```

Khi có lỗi:

```json
{
  "request_id": "uuid",
  "timestamp": "2026-08-07T10:00:00+00:00",
  "status": 400,
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Thông báo lỗi.",
    "category": "VALIDATION",
    "correlation_id": "uuid",
    "retryable": false
  }
}
```

---

## Xác thực

### POST /v1/auth/login

Đăng nhập và nhận token Bearer.

**Request:**
```json
{
  "user_id": "admin",
  "password": "admin"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "token": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "admin",
    "token_type": "Bearer"
  }
}
```

> **Lưu ý:** MVP chấp nhận bất kỳ tên đăng nhập và mật khẩu nào.

### POST /v1/auth/logout

Hủy phiên đăng nhập hiện tại.

### GET /v1/auth/me

Lấy thông tin người dùng hiện tại.

---

## Sức khỏe

### GET /health

Kiểm tra sức khỏe tổng thể. Không cần xác thực.

### GET /ready

Kiểm tra sẵn sàng.

### GET /live

Kiểm tra tiến trình còn sống.

---

## Kho tài liệu (Vaults)

### GET /v1/vaults

Danh sách kho tài liệu.

### POST /v1/vaults

Tạo kho tài liệu mới.

### GET /v1/vaults/{id}

Xem chi tiết kho.

### PATCH /v1/vaults/{id}

Cập nhật kho.

### DELETE /v1/vaults/{id}

Lưu trữ kho (chỉ đọc).

---

## Tài liệu (Documents)

### POST /v1/documents

Tạo bản ghi tài liệu.

### GET /v1/documents

Danh sách tài liệu.

### GET /v1/documents/{id}

Xem chi tiết tài liệu.

### GET /v1/documents/{id}/status

Trạng thái xử lý tài liệu.

### DELETE /v1/documents/{id}

Xóa tài liệu vĩnh viễn.

---

## Tải lên (Uploads)

### POST /v1/uploads

Tải lên file và đăng ký tài liệu.

### GET /v1/uploads/{id}

Kiểm tra trạng thái tải lên.

---

## Tìm kiếm

### POST /v1/search

Tìm kiếm Hybrid (kết hợp từ khóa và ngữ nghĩa).

### POST /v1/search/semantic

Tìm kiếm ngữ nghĩa.

### POST /v1/search/keyword

Tìm kiếm từ khóa.

### POST /v1/search/hybrid

Tìm kiếm Hybrid (tương đương POST /v1/search).

---

## Hỏi đáp

### POST /v1/answers

Đặt câu hỏi và nhận câu trả lời dựa trên bằng chứng.

---

## Quản trị

### GET /v1/jobs

Danh sách công việc xử lý tài liệu.

### GET /v1/system

Thông tin hệ thống.

### POST /v1/reindex

Xây dựng lại chỉ mục tìm kiếm.

### POST /v1/reembed

Kích hoạt re-embedding.

### POST /v1/reparse

Kích hoạt re-parsing.

---

## Bảng Route API

| Method | Path | Xác thực | Mô tả |
|--------|------|----------|-------|
| GET | /health | Không | Kiểm tra sức khỏe |
| GET | /ready | Không | Kiểm tra sẵn sàng |
| GET | /live | Không | Kiểm tra tiến trình |
| POST | /v1/auth/login | Không | Đăng nhập |
| POST | /v1/auth/logout | Có | Đăng xuất |
| GET | /v1/auth/me | Có | Thông tin người dùng |
| GET | /v1/vaults | Có | Danh sách kho |
| POST | /v1/vaults | Có | Tạo kho |
| GET | /v1/vaults/{id} | Có | Xem kho |
| PATCH | /v1/vaults/{id} | Có | Cập nhật kho |
| DELETE | /v1/vaults/{id} | Có | Lưu trữ kho |
| POST | /v1/documents | Có | Tạo tài liệu |
| GET | /v1/documents | Có | Danh sách tài liệu |
| GET | /v1/documents/{id} | Có | Xem tài liệu |
| GET | /v1/documents/{id}/status | Có | Trạng thái tài liệu |
| DELETE | /v1/documents/{id} | Có | Xóa tài liệu |
| POST | /v1/uploads | Có | Tải lên file |
| GET | /v1/uploads/{id} | Có | Trạng thái tải lên |
| POST | /v1/search | Có | Tìm kiếm Hybrid |
| POST | /v1/search/semantic | Có | Tìm kiếm ngữ nghĩa |
| POST | /v1/search/keyword | Có | Tìm kiếm từ khóa |
| POST | /v1/search/hybrid | Có | Tìm kiếm Hybrid |
| POST | /v1/answers | Có | Đặt câu hỏi |
| GET | /v1/jobs | Có | Danh sách công việc |
| GET | /v1/system | Có | Thông tin hệ thống |
| POST | /v1/reindex | Có | Xây dựng chỉ mục |
| POST | /v1/reembed | Có | Re-embed |
| POST | /v1/reparse | Có | Re-parse |