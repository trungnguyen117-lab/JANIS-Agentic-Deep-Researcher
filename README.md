# Hướng dẫn sử dụng repo

## Bước 1: Điều kiện tiên quyết

Cài đặt [uv](https://docs.astral.sh/uv/) — trình quản lý môi trường nhanh cho Python.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Trên Windows, bạn có thể tải bản cài đặt trực tiếp từ trang chủ của UV.

---

## Bước 2: Clone repo

```bash
git clone hhttps://github.com/trungnguyen117-lab/JANIS-Agentic-Deep-Researcher.git
```

---

## Bước 3: Cấu hình môi trường

Đi tới từng thư mục `frontend` và `backend`, chỉnh sửa các biến môi trường trong file `.env` cho phù hợp:

```bash
cd frontend
# Mở và chỉnh sửa file .env
cd ../backend
# Mở và chỉnh sửa file .env
```

## Template mẫu trong .env.example

## Bước 4: Khởi chạy Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend sẽ chạy tại địa chỉ mặc định:
[http://localhost:3000](http://localhost:3000)

---

## Bước 5: Khởi chạy Backend

```bash
uv sync
cd backend
langgraph dev --allow-blocking
```
