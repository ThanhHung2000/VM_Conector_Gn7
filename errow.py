import cv2
import numpy as np
import math
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import gc  # Thêm thư viện dọn rác ở đầu file: import gc

class PCBCheckerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PCB Connector Inspection - Live Video & On-Demand Check")
        self.root.geometry("1400x850")
        # 1. BIẾN QUẢN LÝ CAMERA
        self.camera_index = 0
        self.cap = None
        self.is_camera_connected = False
        self.is_inspecting = False

        # # Khởi tạo Camera
        # SỬA THÀNH (Thêm cv2.CAP_DSHOW để chạy ổn định, không bị lỗi MSMF):
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        # Cài đặt camera về độ phân giải Full HD (1920x1080) hoặc HD (1280x720)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        if not self.cap.isOpened():
            messagebox.showerror("Lỗi Camera", "Không thể mở kết nối tới Camera!")

        # --- FRAME ĐIỀU KHIỂN TOP ---
        top_frame = tk.Frame(root)
        top_frame.pack(fill="x", pady=10)

        # Nút bấm bắt đầu kiểm tra
        self.btn_inspect = tk.Button(
            top_frame, text="🔍 KIỂM TRA CONNECTOR", command=self.inspect_current_frame, 
            font=("Arial", 12, "bold"), bg="#4CAF50", fg="white", padx=20, pady=5
        )
        self.btn_inspect.pack()

        self.lbl_result = tk.Label(top_frame, text="KẾT QUẢ: ĐANG LIVE CAMERA", font=("Arial", 13, "bold"), fg="gray")
        self.lbl_result.pack(pady=3)

        # --- KHUNG CHỨA HIỂN THỊ ÁNH ---
        content_frame = tk.Frame(root)
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # KHUNG BÊN TRÁI: Chứa 2 ảnh lớn xếp dọc (Ảnh chính ở trên, Ảnh cạnh ở dưới)
        left_container = tk.Frame(content_frame)
        left_container.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        # 1. Khung ảnh chính (Live Video / Kết quả)
        left_frame = tk.LabelFrame(left_container, text=" ẢNH KẾT QUẢ ĐO ", font=("Arial", 10, "bold"))
        left_frame.pack(side="top", fill="both", expand=True, pady=(0, 5))

        self.panel_main = tk.Label(left_frame, bd=1, relief="solid")
        self.panel_main.pack(padx=5, pady=5)

        # 2. Khung ảnh Cạnh Đen Trắng
        mid_frame = tk.LabelFrame(left_container, text=" BẢN ĐỒ CẠNH ĐEN TRẮNG ", font=("Arial", 10, "bold"))
        mid_frame.pack(side="bottom", fill="both", expand=True, pady=(5, 0))

        self.panel_edge = tk.Label(mid_frame, bd=1, relief="solid")
        self.panel_edge.pack(padx=5, pady=5)

        # 3. Khung chứa 6 ảnh tai nhỏ
        right_frame = tk.LabelFrame(content_frame, text=" CHI TIẾT 6 TAI CONNECTOR ", font=("Arial", 10, "bold"), padx=10, pady=10)
        right_frame.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        self.ear_panels = []
        self.ear_labels = []

        for i in range(6):
            r, c = divmod(i, 2)
            sub_frame = tk.Frame(right_frame, bd=1, relief="groove", padx=5, pady=5)
            sub_frame.grid(row=r, column=c, padx=5, pady=5)

            p = tk.Label(sub_frame)
            p.pack()
            l = tk.Label(sub_frame, text=f"Tai {i+1}: -", font=("Arial", 9, "bold"))
            l.pack()

            self.ear_panels.append(p)
            self.ear_labels.append(l)

        # Chạy luồng cập nhật video trực tiếp
        self.update_video_stream()

    def init_camera(self):
        """Hàm riêng chuyên khởi tạo / Reconnect Camera"""
        if self.cap is not None:
            self.cap.release() # Giải phóng tài nguyên cũ nếu có

        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW) # DSHOW giúp Windows nhận diện USB nhanh hơn
        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            self.is_camera_connected = True
            print("[OK] Đã kết nối thành công Camera!")
            self.lbl_result.config(text="KẾT QUẢ: ĐANG LIVE CAMERA", fg="gray")
        else:
            self.is_camera_connected = False
            print("[WARNING] Không thể kết nối Camera. Đang đợi cắm lại...")

    def update_video_stream(self):
        next_delay = 30  # Chờ 3s trước khi thử lại
        """Hiển thị luồng Live View giữ nguyên tỷ lệ camera (480x360 hoặc 640x480)"""
        if self.cap is not None and self.cap.isOpened():
            ret, frame = self.cap.read()    
            if ret:
                self.current_frame = frame.copy()
                self.is_camera_connected = True
                # Tự động tính toán kích thước giữ đúng tỷ lệ hình chữ nhật (Chiều rộng max 500px)
                h, w = frame.shape[:2]
                target_w = 520
                target_h = int(h * (target_w / w))

                img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img_pil = Image.fromarray(img_rgb).resize((target_w, target_h), Image.Resampling.LANCZOS)
                img_tk = ImageTk.PhotoImage(img_pil)
                self.panel_main.config(image=img_tk)
                self.panel_main.image = img_tk
            else:
                # Mất khung hình (Tuột cáp giữa chừng)
                self.handle_camera_loss()
                next_delay = 2000
                self.is_camera_connected = False
        # TH2: Mất kết nối -> Tiến hành Auto-Reconnect sau mỗi 2 giây
        else:
            # Hiển thị màn hình đen thông báo mất kết nối
            next_delay = 2000
            self.handle_camera_loss()
        self.root.after(next_delay, self.update_video_stream)
        # Ép Python dọn dẹp bộ nhớ rác định kỳ
        if not hasattr(self, 'frame_count'):
            self.frame_count = 0
        self.frame_count += 1
        if self.frame_count % 500 == 0:  # Cứ 100 frames dọn RAM 1 lần
            gc.collect()
    def handle_camera_loss(self):
        """Xử lý giao diện khi mất kết nối Camera: Xóa ảnh cũ, hiển thị màn hình đen"""
        self.is_camera_connected = False
        self.lbl_result.config(text="LỖI: MẤT KẾT NỐI CAMERA! ĐANG THỬ KẾT NỐI LẠI...", fg="red")
        # 1. Tính toán kích thước đen chính xác theo tỷ lệ HD (1920x1080) với target_w = 520
        # h = 1080, w = 1920 -> target_h = int(1080 * (520 / 1920)) = 292 px
        w_hd, h_hd = 1920, 1080
        target_w = 520
        target_h = int(h_hd * (target_w / w_hd))  # Kích thước chuẩn: 520x292       
        # 2. Tạo khung ảnh đen đúng kích thước (Height: 292, Width: 520, 3 channels RGB)
        black_frame = np.zeros((target_h, target_w, 3), dtype=np.uint8) 
        text = "CAMERA DISCONNECTED"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        thickness = 2
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        text_x = (target_w - text_size[0]) // 2
        text_y = (target_h + text_size[1]) // 2        
        # # 2. Thêm dòng chữ thông báo mất kết nối trực tiếp trên ảnh đen (Tùy chọn)
        # cv2.putText(black_frame, "CAMERA DISCONNECTED", (80, 260), 
        #             cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), cv2.LINE_AA)
        cv2.putText(black_frame, "CAMERA DISCONNECTED", (text_x, text_y), 
                    font, font_scale, (0, 0, 255), thickness, cv2.LINE_AA)
        # 3. Đẩy ảnh đen lên panel_main để xóa ngay ảnh cũ/ảnh vẽ đè
        img_pil = Image.fromarray(black_frame)
        img_tk = ImageTk.PhotoImage(img_pil)
        self.panel_main.config(image=img_tk)
        self.panel_main.image = img_tk

        # 4. Thử khởi tạo lại Camera
        self.init_camera()

    def detect_connector_pose(self, img):
        """
        Hàm riêng chuyên phát hiện Tâm (cx, cy) và Góc xoay (angle) của Connector.
        Không thực hiện cắt ROI hay đo đạc kích thước ở đây.
        """     
        if img is None:
            return None, None, "Không có dữ liệu ảnh!", []
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # 1. TÌM VÒNG TRÒN CYAN (INNER CIRCLE)
        circles = cv2.HoughCircles(
            blurred, cv2.HOUGH_GRADIENT, dp=1.2, minDist=100,
            param1=100, param2=25, minRadius=290, maxRadius=350
        )

        if circles is None:
            return img, None, "KHÔNG TÌM THẤY TÂM CONNECTOR!", []

        circles = np.uint16(np.around(circles))
        cx, cy, r_in = circles[0][0]

        diameter_in = r_in * 2
        ear_max_height = 100 
        r_out = r_in + ear_max_height

        # Vẽ vòng Cyan và vòng Vàng
        cv2.circle(img, (cx, cy), r_in, (255, 255, 0), 2)       # Cyan
        cv2.circle(img, (cx, cy), r_out, (0, 255, 255), 2)     # Vàng

        # Hiển thị chữ đường kính
        text_dia = f"Dia: {diameter_in}px"
        cv2.putText(img, text_dia, (cx - 40, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        # 2. TẠO TẤM MASK NỀN XANH PCB (HSV)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lower_green = np.array([35, 40, 40])
        upper_green = np.array([90, 255, 255])
        pcb_mask = cv2.inRange(hsv, lower_green, upper_green)

        # 3. TẠO BẢN ĐỒ CẠNH SẮC NÉT ĐEN TRẮNG (SOBEL GRADIENT)
        grad_x = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
        magnitude = cv2.magnitude(grad_x, grad_y)
        magnitude = cv2.normalize(magnitude, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        _, edge_map_bw = cv2.threshold(magnitude, 30, 255, cv2.THRESH_BINARY)
        edge_map_display = cv2.cvtColor(edge_map_bw, cv2.COLOR_GRAY2BGR)
        
        cv2.circle(edge_map_display, (cx, cy), r_in, (255, 255, 0), 1)
        cv2.circle(edge_map_display, (cx, cy), r_out, (0, 255, 255), 1)
        cv2.putText(edge_map_display, f"R:{r_in}px", (cx - 40, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # 4. 6 GÓC ROI CỐ ĐỊNH
        #FIXED_ANGLES = [-35, 40, 90, 145, 210, 270] 
        # --- BƯỚC NÂNG CẤP CÔNG NGHIỆP: TỰ ĐỘNG TÌM GÓC XOAY CONNECTOR ---
        BASE_ANGLES = [0, 60, 120, 180, 240, 300] # Mảng góc mốc chuẩn 360/6
        
        # 1. Quét toàn bộ 360 độ để tìm Tai Mốc (Tai có vươn cạnh rõ nhất)
        scan_step = 2 # Quét mỗi 2 độ một tia
        max_edge_r = 0
        found_key_angle = 0

        for a in range(0, 360, scan_step):
            rad = math.radians(a)
            cos_a, sin_a = math.cos(rad), math.sin(rad)
            
            # Quét từ r_in ra r_out tìm điểm cạnh Sobel
            for r in range(r_in + 10, r_out - 2):
                px = int(cx + r * cos_a)
                py = int(cy + r * sin_a)
                if 0 <= px < img.shape[1] and 0 <= py < img.shape[0]:
                    if magnitude[py, px] > 30: # Ngưỡng cạnh rõ
                        if r > max_edge_r:
                            max_edge_r = r
                            found_key_angle = a # Lưu lại góc của tai mốc tìm thấy

        # 2. Tính góc lệch Delta so với mốc 0 độ (hoặc góc mốc gần nhất)
        # Nắn góc lệch về khoảng [-30, 30] độ quanh vạch chuẩn gần nhất
        nearest_base = min(BASE_ANGLES, key=lambda x: abs((found_key_angle - x + 180) % 360 - 180))
        angle_offset = (found_key_angle - nearest_base + 180) % 360 - 180

        # 3. Tạo mảng FIXED_ANGLES ĐỘNG thích ứng với góc xoay thực tế của Connector
        DYNAMIC_FIXED_ANGLES = [(ang + angle_offset) for ang in BASE_ANGLES]

        return float(cx), float(cy), float(angle)
    
    def process_image(self, img):
        """Giữ nguyên 100% Thuật toán gốc của bạn"""
        if img is None:
            return None, None, "Không có dữ liệu ảnh!", []

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # 1. TÌM VÒNG TRÒN CYAN (INNER CIRCLE)
        circles = cv2.HoughCircles(
            blurred, cv2.HOUGH_GRADIENT, dp=1.2, minDist=100,
            param1=100, param2=25, minRadius=290, maxRadius=350
        )

        if circles is None:
            return img, None, "KHÔNG TÌM THẤY TÂM CONNECTOR!", []

        circles = np.uint16(np.around(circles))
        cx, cy, r_in = circles[0][0]

        diameter_in = r_in * 2
        ear_max_height = 100 
        r_out = r_in + ear_max_height

        # Vẽ vòng Cyan và vòng Vàng
        cv2.circle(img, (cx, cy), r_in, (255, 255, 0), 2)       # Cyan
        cv2.circle(img, (cx, cy), r_out, (0, 255, 255), 2)     # Vàng

        # Hiển thị chữ đường kính
        text_dia = f"Dia: {diameter_in}px"
        cv2.putText(img, text_dia, (cx - 40, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        # 2. TẠO TẤM MASK NỀN XANH PCB (HSV)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lower_green = np.array([35, 40, 40])
        upper_green = np.array([90, 255, 255])
        pcb_mask = cv2.inRange(hsv, lower_green, upper_green)

        # 3. TẠO BẢN ĐỒ CẠNH SẮC NÉT ĐEN TRẮNG (SOBEL GRADIENT)
        grad_x = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
        magnitude = cv2.magnitude(grad_x, grad_y)
        magnitude = cv2.normalize(magnitude, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        _, edge_map_bw = cv2.threshold(magnitude, 30, 255, cv2.THRESH_BINARY)
        edge_map_display = cv2.cvtColor(edge_map_bw, cv2.COLOR_GRAY2BGR)
        
        cv2.circle(edge_map_display, (cx, cy), r_in, (255, 255, 0), 1)
        cv2.circle(edge_map_display, (cx, cy), r_out, (0, 255, 255), 1)
        cv2.putText(edge_map_display, f"R:{r_in}px", (cx - 40, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # 4. 6 GÓC ROI CỐ ĐỊNH
        #FIXED_ANGLES = [-35, 40, 90, 145, 210, 270] 
        # --- BƯỚC NÂNG CẤP CÔNG NGHIỆP: TỰ ĐỘNG TÌM GÓC XOAY CONNECTOR ---
        BASE_ANGLES = [0, 60, 120, 180, 240, 300] # Mảng góc mốc chuẩn 360/6
        
        # 1. Quét toàn bộ 360 độ để tìm Tai Mốc (Tai có vươn cạnh rõ nhất)
        scan_step = 2 # Quét mỗi 2 độ một tia
        max_edge_r = 0
        found_key_angle = 0

        for a in range(0, 360, scan_step):
            rad = math.radians(a)
            cos_a, sin_a = math.cos(rad), math.sin(rad)
            
            # Quét từ r_in ra r_out tìm điểm cạnh Sobel
            for r in range(r_in + 10, r_out - 2):
                px = int(cx + r * cos_a)
                py = int(cy + r * sin_a)
                if 0 <= px < img.shape[1] and 0 <= py < img.shape[0]:
                    if magnitude[py, px] > 30: # Ngưỡng cạnh rõ
                        if r > max_edge_r:
                            max_edge_r = r
                            found_key_angle = a # Lưu lại góc của tai mốc tìm thấy

        # 2. Tính góc lệch Delta so với mốc 0 độ (hoặc góc mốc gần nhất)
        # Nắn góc lệch về khoảng [-30, 30] độ quanh vạch chuẩn gần nhất
        nearest_base = min(BASE_ANGLES, key=lambda x: abs((found_key_angle - x + 180) % 360 - 180))
        angle_offset = (found_key_angle - nearest_base + 180) % 360 - 180

        # 3. Tạo mảng FIXED_ANGLES ĐỘNG thích ứng với góc xoay thực tế của Connector
        DYNAMIC_FIXED_ANGLES = [(ang + angle_offset) for ang in BASE_ANGLES]

        sector_angle = 20 # góc quét là 30 vừa đủ chứa tai

        distances = []
        ear_crop_images = []
        ear_data_draw = []

        for mid_angle in DYNAMIC_FIXED_ANGLES:
            a_start = mid_angle - sector_angle / 2
            a_end = mid_angle + sector_angle / 2
            # 1. QUÉT CÁC TIA: LẤY TẤT CẢ ĐIỂM CẠNH THỎA MÃN (KHÔNG DÙNG argmax NỮA)
            valid_edge_points = []
            for angle in np.linspace(a_start, a_end, 60):
                rad = math.radians(angle)
                cos_a, sin_a = math.cos(rad), math.sin(rad)

                for r in range(r_in + 8, r_out - 3):
                    px = int(cx + r * cos_a)
                    py = int(cy + r * sin_a)
                    if 0 <= px < img.shape[1] and 0 <= py < img.shape[0]:
                        if magnitude[py, px] > 30: # Ngưỡng cạnh
                            gx, gy = grad_x[py, px], grad_y[py, px]
                            edge_angle = math.degrees(math.atan2(gy, gx))
                            angle_diff = abs(edge_angle - angle) % 180
                            if angle_diff > 90: angle_diff = 180 - angle_diff

                            # Lọc đúng cạnh tiếp tuyến
                            if angle_diff < 10:
                                valid_edge_points.append((px, py, r, cos_a, sin_a))

            # 2. PHÂN NHÓM THEO BÁN KÍNH VÀ CHỌN ĐOẠN CẠNH DÀI NHẤT (NẰM Ở NGOÀI)
            best_dist_for_ear = 0
            best_p_start, best_p_end = (cx, cy), (cx, cy)

            if len(valid_edge_points) >= 15:
                # Gom nhóm các điểm có bán kính r gần nhau (sai số 3px)
                from collections import defaultdict
                clusters = defaultdict(list)

                # Góc pháp tuyến định hướng của vùng tai hiện tại
                rad_mid = math.radians(mid_angle)
                cos_mid, sin_mid = math.cos(rad_mid), math.sin(rad_mid)
                cx_f, cy_f = float(cx), float(cy)
                for pt in valid_edge_points:
                    px, py = pt[0], pt[1]
                    # TÍNH KHOẢNG CÁCH VUÔNG GÓC (d) TỪ TÂM TỚI ĐƯỜNG THẲNG ĐI QUA POINT
                    # Công thức chiếu vector (px - cx, py - cy) lên vector pháp tuyến
                    d_val = (px - cx_f) * cos_mid + (py - cy_f) * sin_mid
                    # Gom nhóm các điểm thuộc CÙNG MỘT ĐƯỜNG THẲNG (có d chênh lệch <= 3px)
                    grouped = False
                    for k in clusters.keys():
                        if abs(d_val - k) <= 3:
                            clusters[k].append(pt)
                            grouped = True
                            break
                    if not grouped:
                        clusters[d_val].append(pt)
                # ƯU TIÊN 1: Tìm đường thẳng có NHIỀU ĐIỂM NHẤT (Cạnh dài nhất)
                # ƯU TIÊN 2: Chọn đường thẳng nằm XA TÂM NHẤT (d LỚN NHẤT)
                best_cluster = max(clusters.values(), key=lambda group: (
                    len(group), 
                    np.mean([(p[0] - cx_f) * cos_mid + (p[1] - cy_f) * sin_mid for p in group])
                ))
                if best_cluster:
                    # 1. Để lấy đúng 2 đầu mép tai của ĐƯỜNG THẲNG, ta sắp xếp theo thứ tự góc quét
                    best_cluster.sort(key=lambda item: item[3]) # Sắp xếp theo cos_a hoặc góc
                    
                    p_first = (best_cluster[0][0], best_cluster[0][1])   # Đầu mép thẳng
                    p_last = (best_cluster[-1][0], best_cluster[-1][1])   # Cuối mép thẳng

                    # 2. Điểm vuông góc chính giữa để đo khoảng cách tai
                    mid_idx = len(best_cluster) // 2
                    px, py, r_found, cos_a, sin_a = best_cluster[mid_idx]

                    best_dist_for_ear = r_found - r_in
                    best_p_start = (int(cx + r_in * cos_a), int(cy + r_in * sin_a))
                    best_p_end = (px, py)
                    # Bây giờ vẽ lên inspect_frame thoải mái không sợ lỗi!
                    cv2.line(img, p_first, p_last, (0, 0, 255), 2, cv2.LINE_AA)
                    cv2.line(edge_map_display, p_first, p_last, (0, 255, 0), 2)
            distances.append(best_dist_for_ear)
            ear_data_draw.append((best_p_start, best_p_end))

            rad_m = math.radians(mid_angle)
            rx = int(cx + (r_in + ear_max_height / 2) * math.cos(rad_m))
            ry = int(cy + (r_in + ear_max_height / 2) * math.sin(rad_m))
            crop_size = 130
            x1, x2 = max(0, rx - crop_size), min(img.shape[1], rx + crop_size)
            y1, y2 = max(0, ry - crop_size), min(img.shape[0], ry + crop_size)
            ear_crop_images.append(img[y1:y2, x1:x2].copy())

        # 5. HIỂN THỊ KẾT QUẢ VÀ ĐÁNH GIÁ OK/NG
        max_d = max(distances) if max(distances) > 0 else 1
        is_ng = False
        ear_data = []

        for i in range(6):
            dist = distances[i]
            p_start, p_end = ear_data_draw[i]

            if dist <= 60 or dist < 0.80 * max_d:
                color = (0, 0, 255)
                status = "NG"
                is_ng = True
            else:
                color = (0, 255, 0)
                status = "OK"

            if dist > 0:
                cv2.arrowedLine(img, p_start, p_end, color, 2, tipLength=0.25)
                cv2.circle(img, p_end, 3, (0, 0, 255), -1)

            ear_data.append((ear_crop_images[i], f"{dist}px", status, color))

        status_text = "RESULT: NOT GOOD (NG)" if is_ng else "RESULT: OK"
        return img, edge_map_display, status_text, ear_data

    def inspect_current_frame(self):
        """
        Kích hoạt kiểm tra: Chụp 10 frame liên tiếp -> Lấy trung bình kích thước 6 tai -> Hiển thị
        """
        if self.cap is None or not self.cap.isOpened():
            messagebox.showwarning("Cảnh báo", "Camera chưa được kết nối!")
            return

        # Vô hiệu hóa nút bấm tạm thời để người dùng không bấm dồn dập
        self.btn_inspect.config(state="disabled", text="⏳ ĐANG TÍNH TOÁN GIÁ TRỊ ...")
        self.root.update()

        NUM_SAMPLES = 5
        all_distances = [[] for _ in range(6)] # Mảng lưu 10 khoảng cách của 6 tai
        last_clean_frame = None

        # 1. BẮT ĐẦU VÒNG LẶP CHỤP 10 FRAMES LIÊN TIẾP
        for sample_idx in range(NUM_SAMPLES):
            ret, frame = self.cap.read()
            if not ret or frame is None:
                continue

            last_clean_frame = frame.copy()

            # Chạy thuật toán xử lý ảnh trên frame hiện tại
            processed_img, edge_img, status, ear_data = self.process_image(frame)

            # Lấy khoảng cách (px) từng tai từ ear_data
            for i in range(6):
                if i < len(ear_data):
                    # ear_data[i][1] có dạng "45.5px" -> ép kiểu float
                    try:
                        dist_val = float(ear_data[i][1].replace("px", ""))
                        all_distances[i].append(dist_val)
                    except ValueError:
                        all_distances[i].append(0.0)

            # Chờ 10ms để camera quét frame mới
            cv2.waitKey(10)

        # Mở lại nút bấm sau khi chụp xong
        self.btn_inspect.config(state="normal", text="🔍 KIỂM TRA CONNECTOR")

        if last_clean_frame is None:
            return

        # 2. TÍNH GIÁ TRỊ TRUNG BÌNH CỦA 6 TAI (BỎ 1 MAX, 1 MIN ĐỂ TRÁNH NHIỄU)
        avg_distances = []
        for i in range(6):
            dists = all_distances[i]
            if len(dists) >= 3:
                dists.sort()
                valid_dists = dists[1:-1] # Loại bỏ 1 Min và 1 Max
                avg_d = sum(valid_dists) / len(valid_dists)
            elif len(dists) > 0:
                avg_d = sum(dists) / len(dists)
            else:
                avg_d = 0.0
            final_px = math.ceil(avg_d)
            avg_distances.append(final_px)

        # 3. CHẠY LẠI PROCESS_IMAGE TRÊN LAST_FRAME ĐỂ LẤY VỊ TRÍ TỌA ĐỘ VẼ
        processed_img, edge_img, status, ear_data = self.process_image(last_clean_frame)

        if processed_img is None:
            return

        # 4. ĐÁNH GIÁ LẠI TRẠNG THÁI OK/NG DỰA TRÊN KHOẢNG CÁCH TRUNG BÌNH
        max_avg_d = max(avg_distances) if max(avg_distances) > 0 else 1.0
        is_ng = False
        final_ear_data = []

        for i in range(6):
            avg_d = avg_distances[i]
            crop_img, _, _, _ = ear_data[i] if i < len(ear_data) else (None, "", "", (0,0,0))

            # Điều kiện đánh giá OK/NG dựa trên trung bình
            if avg_d <= 60 or avg_d < 0.80 * max_avg_d:
                color = (0, 0, 255) # Đỏ
                ear_status = "NG"
                is_ng = True
            else:
                color = (0, 255, 0) # Xanh
                ear_status = "OK"

            final_ear_data.append((crop_img, f"{avg_d}px", ear_status, color))

        # Cập nhật nhãn kết quả chung
        if is_ng:
            self.lbl_result.config(text="RESULT: NOT GOOD (NG) ", fg="red")
        else:
            self.lbl_result.config(text="RESULT: OK ", fg="green")

        # 5. CẮT VÙNG PHÓNG TO CONNECTOR VÀ HIỂN THỊ LÊN UI (GIỮ NGUYÊN CODE CỦA BẠN)
        gray = cv2.cvtColor(processed_img, cv2.COLOR_BGR2GRAY)
        h_img, w_img = processed_img.shape[:2]

        circles = cv2.HoughCircles(
            cv2.GaussianBlur(gray, (5, 5), 0), cv2.HOUGH_GRADIENT, 
            dp=1.2, minDist=int(min(h_img, w_img) * 0.15), 
            param1=100, param2=25, 
            minRadius=int(min(h_img, w_img) * 0.10), 
            maxRadius=int(min(h_img, w_img) * 0.25)
        )

        if circles is not None:
            circles = np.uint16(np.around(circles))
            cx, cy, r = circles[0][0]
            crop_margin = 520
            cy_int, cx_int, margin = int(cy), int(cx), int(crop_margin)
            x1, x2 = max(0, cx_int - margin), min(w_img, cx_int + margin)
            y1, y2 = max(0, cy_int - margin), min(h_img, cy_int + margin)

            main_crop = processed_img[y1:y2, x1:x2]
            edge_crop = edge_img[y1:y2, x1:x2] if edge_img is not None else None
        else:
            main_crop = processed_img
            edge_crop = edge_img

        display_size = (520, 520)

        if main_crop is None or main_crop.size == 0:
            print("[WARNING] Ảnh main_crop bị rỗng! Bỏ qua frame này.")
            return

        # Hiển thị Ảnh Kết Quả Đo
        img_rgb = cv2.cvtColor(main_crop, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb).resize(display_size, Image.Resampling.LANCZOS)
        img_tk = ImageTk.PhotoImage(img_pil)
        self.panel_main.config(image=img_tk)
        self.panel_main.image = img_tk

        # Hiển thị Bản Đồ Cạnh Đen Trắng
        if edge_crop is not None:
            edge_rgb = cv2.cvtColor(edge_crop, cv2.COLOR_BGR2RGB)
            edge_pil = Image.fromarray(edge_rgb).resize(display_size, Image.Resampling.LANCZOS)
            edge_tk = ImageTk.PhotoImage(edge_pil)
            self.panel_edge.config(image=edge_tk)
            self.panel_edge.image = edge_tk

        # 6. CẬP NHẬT 6 ẢNH TAI NHỎ VỚI GIÁ TRỊ TRUNG BÌNH VỪA TÍNH
        for i, (crop_img, avg_area_str, ear_status, color) in enumerate(final_ear_data):
            if crop_img is not None and crop_img.size > 0:
                crop_rgb = cv2.cvtColor(crop_img, cv2.COLOR_BGR2RGB)
                crop_pil = Image.fromarray(crop_rgb).resize((230, 230), Image.Resampling.LANCZOS)
                crop_tk = ImageTk.PhotoImage(crop_pil)

                self.ear_panels[i].config(image=crop_tk)
                self.ear_panels[i].image = crop_tk

                fg_color = "red" if ear_status == "NG" else "green"
                self.ear_labels[i].config(text=f"Tai {i+1}: {avg_area_str} ({ear_status})", fg=fg_color)

    def __del__(self):
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()

if __name__ == "__main__":
    root = tk.Tk()
    app = PCBCheckerApp(root)
    root.mainloop()