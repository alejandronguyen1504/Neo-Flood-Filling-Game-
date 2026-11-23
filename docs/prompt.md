Hãy đóng vai Senior Software Engineer & Algorithm Visualization Mentor để cùng mình nâng cấp repo `neo-flood-fill` từ bài tập nghiên cứu thành một dự án **LinkedIn Portfolio** hoàn chỉnh, chuẩn kỹ thuật và có giao diện tương tác ấn tượng.

### Bối cảnh hiện tại
- Spec gốc nằm ở `docs/NCT-NEO-FloodFill.pdf` và `docs/Gantt Chart Flood fill research.pdf`.
- Code hiện tại nằm trong `Neo_Flood_Filling.ipynb`, môi trường `.venv` (Python 3.13 + pygame) và `requirements.txt` đã được thiết lập.

### Mục tiêu nâng cấp (thực hiện theo từng Phase, xác nhận trước khi sang Phase mới)

#### Phase 1 — Tái cấu trúc kiến trúc & Sửa lỗi cốt lõi
1. Tách code khỏi notebook thành cấu trúc module rõ ràng:
   - `src/neo_flood_fill/grid.py` (cấu trúc lưới, helper, hỗ trợ nhiều màu vùng độc lập)
   - `src/neo_flood_fill/algorithms.py` (Recursive DFS, Iterative DFS, Queue BFS, Scanline Flood Fill, BFS/A* Shortest Path — cả dạng sync lẫn generator step-by-step, hỗ trợ 4-way & 8-way connectivity)
   - `src/neo_flood_fill/console_demo.py` (CLI demo step-by-step sạch sẽ)
   - `src/neo_flood_fill/visualizer.py` (Pygame app)
   - `main.py` (entry point chạy ngay bằng `python main.py`)
2. Sửa toàn bộ bug đã biết:
   - Thêm guard `target_color == fill_color` cho tất cả biến thể Flood Fill.
   - Sửa phương pháp benchmark bộ nhớ & kiểm định O(N) cho chính xác về mặt CS (phân biệt call-stack depth vs peak frontier vs heap allocation).
3. Chuyển 44+ unit tests sang `pytest` trong `tests/`, đảm bảo 100% pass, thêm edge cases (lưới rỗng, đường chéo, nhiều vùng màu, không có đường đi).

#### Phase 2 — Nâng cấp Pygame Visualizer thành Interactive Algorithm Studio
1. Đáp ứng đủ và vượt spec gốc:
   - Chế độ **Region Flood Fill** thực sự: chọn màu từ Color Picker, click vào bất kỳ vùng kín nào để xem thuật toán loang màu real-time (hỗ trợ nhiều vùng khác màu nhau như Paint Bucket).
   - Chế độ **Shortest Pathfinding**: chọn Start/End và so sánh trực quan BFS vs DFS (hoặc A*).
   - Hỗ trợ chọn thuật toán ngay trên UI (Recursive DFS / Iterative DFS / BFS / Scanline) và bật/tắt 4-way vs 8-way.
2. Cải thiện UX/UI:
   - Click & giữ kéo chuột để vẽ tường / xóa mượt mà; hover highlight ô dưới con trỏ.
   - Sidebar có nút bấm trực quan + phím tắt, thanh chỉnh tốc độ animation, Pause/Resume/Step, Undo/Reset.
   - 1-click **Maze / Random Obstacles / Multi-Room Preset** để demo nhanh.
   - HUD hiển thị live metrics (Cells visited, Peak frontier/stack, Path length, Time ms) và banner cảnh báo trên UI (vd: "No path found", trùng màu Wall/Path).
   - Hỗ trợ font cross-platform (macOS/Windows/Linux) và chạy ổn định ngoài notebook không crash kernel.

#### Phase 3 — Research Notebook, Benchmarks & Showcase cho LinkedIn
1. Cập nhật `Neo_Flood_Filling.ipynb` gọn gàng, import trực tiếp từ `src/` (không duplicate code), bổ sung biểu đồ `matplotlib` so sánh Runtime & Space/Frontier giữa DFS, BFS và Scanline trên nhiều địa hình lưới (open grid, maze, spiral).
2. Thêm GitHub Actions workflow chạy `pytest` tự động khi push/PR.
3. Viết lại `README.md` chuẩn Portfolio: kiến trúc hệ thống, hướng dẫn cài đặt & chạy (`python main.py`), bảng so sánh thuật toán kèm kết quả benchmark, chỗ gắn ảnh/GIF demo, và mục Role/Contributions.
4. Viết sẵn 1 bài đăng LinkedIn ngắn gọn + bullet points kỹ thuật cho mục Projects trên LinkedIn dựa trên những gì đã xây dựng.

### Cách làm việc
- Trước khi viết code, hãy đề xuất **Implementation Plan** chi tiết cho **Phase 1** (cấu trúc thư mục, thiết kế API, danh sách test) và hỏi mình các quyết định thiết kế quan trọng (ví dụ: có thêm A* hoặc xuất bản web demo qua `pygbag` hay không).
- Sau mỗi Phase, chạy test/verify đầy đủ rồi tóm tắt kết quả trước khi chuyển sang Phase tiếp theo.

### Ngôn ngữ: @
- Khi giao tiếp giữa user và agent: Tiếng việt 
- Liên quan đến docs, commit, repo, code, những gì liên quan đên dự án: Tiếng Anh [/grill-me](slashCommand;grill-me) 