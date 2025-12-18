# SenAI
Một chatbot tự học hỏi

## Cấu trúc dự án

- `backend/`: Backend Python (FastAPI)
- `frontend/`: Frontend C++ cho Windows

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