## Định hướng chung
- **Mục tiêu**: Giữ phong cách desktop dark hiện tại nhưng làm cho trải nghiệm chat mượt, rõ ràng hơn, dễ mở rộng (thêm nhiều tính năng và loại message trong tương lai).

## Cải tiến cấu hình & môi trường
- **Đa ngôn ngữ (i18n)**:
  - Tách text UI (title, subtitle, placeholder, status label…) ra 1 file header constants hoặc JSON resource để sau này dễ chuyển đổi ngôn ngữ (vi/eng).

## Cải tiến về usability nhỏ nhưng hữu ích
- **Shortcut bổ sung**:
  - Ctrl+Enter gửi message (tùy chọn trong Settings)
  - Esc ngoài input → đóng app hoặc confirm exit
- **Copy nội dung**:
  - Double-click vào bubble để copy toàn bộ text (dùng clipboard API Win32)
  - Thêm icon copy nhỏ bên phải bubble khi hover
- **Tooltip metadata**:
  - Hiển thị tooltip với metadata (token usage, latency, model name) khi hover vào message

## Hướng mở rộng tính năng
- **Cải tiến sidebar**:
  - Thêm nút "Xoá lịch sử hiện tại" hoặc "Đóng session".
  - Thêm scroll cho sidebar nếu có nhiều conversations.
  - Thêm search/filter conversations trong sidebar.
- **Tích hợp tasks**:
  - Hiện `createTask/getTasks/updateTask` chưa dùng ở UI mới:
    - Thiết kế thêm tab "Tasks" hoặc một khu vực nhỏ hiển thị các task AI đang chạy/đã xong.
    - Cho phép click mở chi tiết task, update trạng thái ngay từ UI.

## Gợi ý thứ tự triển khai
- **Giai đoạn 2 (trải nghiệm tốt hơn)**:
  - Thêm copy bubble (double-click hoặc icon copy)
  - Tooltip metadata khi hover vào message
  - Cải thiện sidebar: search/filter conversations
- **Giai đoạn 3 (nâng cấp & mở rộng)**:
  - Lưu/load settings từ file config
  - Hiển thị tên model trong header
  - Tab Tasks để hiển thị và quản lý tasks
  - Đa ngôn ngữ (i18n) support
