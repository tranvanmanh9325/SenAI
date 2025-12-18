# SenAI
Một chatbot tự học hỏi

## Cấu trúc dự án

- `backend/`: Backend Python (FastAPI) - API server với PostgreSQL
- `frontend/`: Frontend C++ cho Windows - Ứng dụng GUI kết nối với backend

## Tính năng

### Frontend (C++ Windows App)
- **Chat với AI**: Gửi tin nhắn và nhận phản hồi từ AI Agent
- **Quản lý Tasks**: Tạo và xem danh sách tasks
- **Kết nối Backend**: Giao tiếp với FastAPI backend qua HTTP requests
- **Giao diện GUI**: Ứng dụng Windows với Win32 API

### Backend (FastAPI)
- RESTful API với PostgreSQL database
- Endpoints cho conversations và tasks
- CORS enabled để hỗ trợ frontend

## Hướng dẫn Build và Chạy Frontend (C++)

### Yêu cầu hệ thống

- **Windows 10/11**
- **CMake** (phiên bản 3.10 trở lên)
- **MinGW** hoặc **Visual Studio** với C++ compiler
- **Git** (để clone dependencies nếu cần)

### Kiểm tra cài đặt

Kiểm tra xem bạn đã cài đặt các công cụ cần thiết:

```powershell
cmake --version
g++ --version
```

### Build ứng dụng

1. **Mở PowerShell** và di chuyển đến thư mục frontend:

```powershell
cd D:\GitHub\SenAI\frontend
```

2. **Tạo thư mục build** (nếu chưa có):

```powershell
if (-not (Test-Path build)) { New-Item -ItemType Directory -Path build }
```

3. **Di chuyển vào thư mục build** và cấu hình CMake:

```powershell
cd build
cmake .. -G "MinGW Makefiles"
```

**Lưu ý**: Nếu bạn dùng Visual Studio, thay `"MinGW Makefiles"` bằng `"Visual Studio 17 2022"` hoặc generator phù hợp.

4. **Build project**:

```powershell
cmake --build .
```

Sau khi build thành công, file executable sẽ được tạo tại: `build/bin/SenAIFrontend.exe`

### Chạy ứng dụng

Có 2 cách để chạy ứng dụng:

**Cách 1**: Từ thư mục build:

```powershell
cd D:\GitHub\SenAI\frontend\build
.\bin\SenAIFrontend.exe
```

**Cách 2**: Từ thư mục bin:

```powershell
cd D:\GitHub\SenAI\frontend\build\bin
.\SenAIFrontend.exe
```

**Cách 3**: Double-click vào file `SenAIFrontend.exe` trong Windows Explorer.

### Sử dụng ứng dụng

**Lưu ý**: Đảm bảo backend đang chạy trước khi mở frontend!

1. **Khởi động Backend** (xem hướng dẫn bên dưới)
2. **Mở Frontend**: Chạy `SenAIFrontend.exe`
3. **Chat với AI**:
   - Nhập tin nhắn vào ô chat bên trái
   - Nhấn nút "Gửi" hoặc Enter
   - Xem lịch sử chat và phản hồi từ AI
4. **Quản lý Tasks**:
   - Nhập tên task và mô tả (tùy chọn) vào ô bên phải
   - Nhấn "Tạo Task" để tạo task mới
   - Nhấn "Làm mới Tasks" để xem danh sách tasks mới nhất

### Build lại sau khi thay đổi code

Nếu bạn đã thay đổi code, chỉ cần chạy lại lệnh build:

```powershell
cd D:\GitHub\SenAI\frontend\build
cmake --build .
```

### Xóa build và build lại từ đầu

Nếu gặp vấn đề với build, bạn có thể xóa thư mục build và build lại:

```powershell
cd D:\GitHub\SenAI\frontend
Remove-Item -Recurse -Force build
mkdir build
cd build
cmake .. -G "MinGW Makefiles"
cmake --build .
```

## Hướng dẫn Backend (Python)

### Yêu cầu

- Python 3.8+
- pip

### Cài đặt và chạy

1. **Di chuyển đến thư mục backend**:

```powershell
cd D:\GitHub\SenAI\backend
```

2. **Tạo virtual environment** (nếu chưa có):

```powershell
python -m venv venv
```

3. **Kích hoạt virtual environment**:

```powershell
.\venv\Scripts\Activate.ps1
```

4. **Cài đặt dependencies**:

```powershell
pip install -r requirements.txt
```

5. **Chạy server**:

```powershell
uvicorn app:app --reload
```

Server sẽ chạy tại `http://localhost:8000`

### API Endpoints

Backend cung cấp các endpoints sau:

- `GET /` - Health check cơ bản
- `GET /health` - Health check với database
- `POST /conversations` - Tạo conversation mới (chat với AI)
- `GET /conversations` - Lấy danh sách conversations
- `POST /tasks` - Tạo task mới
- `GET /tasks` - Lấy danh sách tasks
- `GET /tasks/{task_id}` - Lấy task cụ thể
- `PUT /tasks/{task_id}` - Cập nhật task

### Cấu hình Database

Backend sử dụng PostgreSQL. Cấu hình trong file `.env` hoặc biến môi trường:

```
DB_HOST=192.168.0.106
DB_PORT=5432
DB_NAME=ai_system
DB_USER=postgres
DB_PASSWORD=your_password
```

## Kết nối Frontend và Backend

1. **Khởi động Backend** trước:
   ```powershell
   cd backend
   .\venv\Scripts\Activate.ps1
   uvicorn app:app --reload
   ```

2. **Khởi động Frontend**:
   ```powershell
   cd frontend\build\bin
   .\SenAIFrontend.exe
   ```

3. Frontend sẽ tự động kết nối đến `http://localhost:8000`

**Lưu ý**: Nếu backend chạy trên port khác hoặc địa chỉ khác, bạn cần sửa trong code `HttpClient.cpp` (dòng khởi tạo `HttpClient`).