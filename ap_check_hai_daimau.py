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
        left_container.pack(side="left", fill="y", expand=False, padx=5, pady=5)

        # 1. Khung ảnh chính (Live Video / Kết quả)
        left_frame = tk.LabelFrame(left_container, text=" ẢNH KẾT QUẢ ĐO ", font=("Arial", 10, "bold"))
        left_frame.pack(side="top", fill="y", expand=False, pady=(0, 5))

        self.panel_main = tk.Label(left_frame, bd=1, relief="solid")
        self.panel_main.pack(padx=5, pady=5)

        # 2. Khung ảnh Cạnh Đen Trắng
        mid_frame = tk.LabelFrame(left_container, text=" BẢN ĐỒ CẠNH ĐEN TRẮNG ", font=("Arial", 10, "bold"))
        mid_frame.pack(side="bottom", fill="both", expand=True, pady=(5, 0))

        self.panel_edge = tk.Label(mid_frame, bd=1, relief="solid")
        self.panel_edge.pack(padx=5, pady=5)

        # 3. Khung hiển thị ảnh kết quả tổng (chứa cả 6 nhãn tai)
        right_frame = tk.LabelFrame(content_frame, text=" CHI TIẾT CONNECTOR ", font=("Arial", 10, "bold"), padx=10, pady=10)
        right_frame.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        # Lưu lại right_frame để lấy kích thước tự động điều chỉnh ảnh
        self.right_frame = right_frame 

        # Tạo DUY NHẤT 1 Label to để hiển thị bức ảnh kết quả hoàn chỉnh
        self.lbl_full_result = tk.Label(right_frame)
        self.lbl_full_result.pack(fill="both", expand=True)

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

    def detect_connector_pose(self):
        """
        Hàm riêng chuyên phát hiện Tâm (cx, cy) và Phân loại Góc lệch (0 deg hoặc 30 deg) của Connector.
        Chỉ phân loại vào 2 trường hợp hệ góc BASE chuẩn.
        """     
        if self.cap is None or not self.cap.isOpened():
            print("[ERROR] Camera chưa kết nối!")
            return None, None, None, None, None

        list_cx = []
        list_cy = []
        list_r_in = []
        list_sin = []
        list_cos = []
        last_frame = None

        # Khai báo 2 Hệ góc cố định duy nhất
        BASE_SET_0  = [0, 60, 120, 180, 240, 300]   # Trường hợp 1: Hệ 0 độ
        BASE_SET_30 = [30, 90, 150, 210, 270, 330] # Trường hợp 2: Hệ 30 độ

        for _ in range(5):
            ret, frame = self.cap.read()
            if not ret or frame is None:
                continue
                
            last_frame = frame.copy()

            # Tiền xử lý ảnh
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (3, 3), 0)

            # 1. TÌM VÒNG TRÒN CYAN (INNER CIRCLE) TÌM TÂM
            circles = cv2.HoughCircles(
                blurred, cv2.HOUGH_GRADIENT, dp=1.2, minDist=100,
                param1=100, param2=25, minRadius=290, maxRadius=350
            )

            if circles is not None:
                circles = np.uint16(np.around(circles))
                cx, cy, r_in = circles[0][0]
                r_out = r_in + 100
                img_h, img_w = frame.shape[:2]

                # 2. TÍNH SOBEL GRADIENT TÌM CẠNH
                grad_x = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
                grad_y = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
                magnitude = cv2.magnitude(grad_x, grad_y)
                magnitude = cv2.normalize(magnitude, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

                # 3. HÀM PHỤ: CẢM BIẾN TỔNG ĐỘ NỔI BẬT R TẠI CÁC GÓC CỦA NGUYÊN HỆ GÓC
                def calc_system_score(base_angles_list):
                    total_score = 0
                    for base_a in base_angles_list:
                        max_r_at_angle = 0
                        # Quét dải nhỏ +-3 độ xung quanh góc base để bù sai số cơ khí nhỏ
                        for da in range(-3, 4):
                            a = (base_a + da) % 360
                            rad = math.radians(a)
                            cos_a, sin_a = math.cos(rad), math.sin(rad)

                            for r in range(r_in + 10, r_out - 2):
                                px = int(cx + r * cos_a)
                                py = int(cy + r * sin_a)
                                if 0 <= px < img_w and 0 <= py < img_h:
                                    if magnitude[py, px] > 30:
                                        if r > max_r_at_angle:
                                            max_r_at_angle = r
                        total_score += max_r_at_angle
                    return total_score

                # 4. CHẤM ĐIỂM BÌNH CHỌN HỆ 0 ĐỘ VS HỆ 30 ĐỘ
                score_0  = calc_system_score(BASE_SET_0)
                score_30 = calc_system_score(BASE_SET_30)

                # Chọn Hệ góc có tổng điểm cao nhất
                if score_0 >= score_30:
                    angle_offset = 0.0
                else:
                    angle_offset = 30.0

                # Lưu dữ liệu frame này vào danh sách
                list_cx.append(float(cx))
                list_cy.append(float(cy))
                list_r_in.append(float(r_in))
                
                # Đổi góc sang Sin/Cos để tính trung bình vector góc
                rad_offset = math.radians(angle_offset)
                list_sin.append(math.sin(rad_offset))
                list_cos.append(math.cos(rad_offset))

            self.root.update()

        # --- TÍNH GIÁ TRỊ TRUNG BÌNH CỦA CÁC FRAMES ---
        if len(list_cx) == 0:
            print("[WARNING] Không tìm thấy Connector!")
            return None, None, None, None, last_frame

        avg_cx = float(np.mean(list_cx))
        avg_cy = float(np.mean(list_cy))
        avg_r_in = float(np.mean(list_r_in))

        # Trung bình góc bằng lượng giác
        avg_sin = np.mean(list_sin)
        avg_cos = np.mean(list_cos)
        avg_angle_offset = float(math.degrees(math.atan2(avg_sin, avg_cos)))

        # Làm tròn về đúng 0.0 hoặc 30.0 tuyệt đối cho đầu ra
        avg_angle_offset = 0.0 if abs(avg_angle_offset) < 15.0 else 30.0

        return avg_cx, avg_cy, avg_r_in, avg_angle_offset, last_frame
    
    def process_image(self, img,cx=None, cy=None, angle_offset=0.0,r_input=None):
        """Giữ nguyên 100% Thuật toán gốc của bạn"""
        if img is None or cx is None or cy is None or r_input is None:
            return None, None, "Không có dữ liệu ảnh!", []
        # Ép kiểu dữ liệu an toàn
        cx, cy, r_input = int(cx), int(cy), int(r_input)
        r_input1=int(r_input*1.11)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        diameter_in = r_input * 2
        ear_max_height = 100 
        r_out = r_input + ear_max_height

        # Vẽ vòng Cyan và vòng Vàng
        cv2.circle(img, (cx, cy), r_input, (255, 255, 0), 2)       # Cyan
        cv2.circle(img, (cx, cy), r_out, (0, 255, 255), 2)     # Vàng
        
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
        
        cv2.circle(edge_map_display, (cx, cy), r_input, (255, 255, 0), 1)
        cv2.circle(edge_map_display, (cx, cy), r_out, (0, 255, 255), 1)
        cv2.putText(edge_map_display, f"R:{r_input}px", (cx - 40, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # 4. 6 GÓC ROI CỐ ĐỊNH
        #FIXED_ANGLES = [-35, 40, 90, 145, 210, 270] 
        # --- BƯỚC NÂNG CẤP CÔNG NGHIỆP: TỰ ĐỘNG TÌM GÓC XOAY CONNECTOR ---
        BASE_ANGLES = [0, 60, 120, 180, 240, 300] # Mảng góc mốc chuẩn 360/6
        

        # 3. Tạo mảng FIXED_ANGLES ĐỘNG thích ứng với góc xoay thực tế của Connector
        DYNAMIC_FIXED_ANGLES = [(ang + angle_offset) for ang in BASE_ANGLES]

        sector_angle = 12 # góc quét là sector_angle*2 vừa đủ chứa tai

        distances = []
        ear_crop_images = []
        ear_data_draw = []

        for mid_angle in DYNAMIC_FIXED_ANGLES:
            a_start = mid_angle - sector_angle
            a_end = mid_angle + sector_angle
            # 1. QUÉT CÁC TIA: LẤY TẤT CẢ ĐIỂM CẠNH THỎA MÃN (KHÔNG DÙNG argmax NỮA)
            valid_edge_points = []
            for angle in np.linspace(a_start, a_end, 30):
                rad = math.radians(angle)
                cos_a, sin_a = math.cos(rad), math.sin(rad)
            
                for r in range(r_input1, r_out):# 1.12 LÀ BẰNG 75% MIN( lỌC NHIỄU ) for r in range(r_input + 15, r_out - 3):
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

                    best_dist_for_ear = r_found - r_input
                    best_p_start = (int(cx + r_input * cos_a), int(cy + r_input * sin_a))
                    best_p_end = (px, py)

                    # Bây giờ vẽ lên inspect_frame thoải mái không sợ lỗi!
                    # cv2.line(img, p_first, p_last, (0, 0, 255), 2, cv2.LINE_AA)
                    cv2.line(edge_map_display, p_first, p_last, (0, 255, 0), 2)
            distances.append(best_dist_for_ear)
            ear_data_draw.append((best_p_start, best_p_end))

            rad_m = math.radians(mid_angle)
            rx = int(cx + (r_input + ear_max_height / 2) * math.cos(rad_m))
            ry = int(cy + (r_input + ear_max_height / 2) * math.sin(rad_m))
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

            if dist <= 60 or dist < 0.70 * max_d:
                color = (0, 0, 255)
                status = "NG"
                is_ng = True
            else:
                color = (0, 255, 0)
                status = "OK"

            # if dist > 0:
            #     cv2.arrowedLine(img, p_start, p_end, color, 2, tipLength=0.25)
            #     cv2.circle(img, p_end, 3, (0, 0, 255), -1)

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
        self.lbl_result.config(text="CHEKING... ", fg="green")
        # 2. XÓA MÀN HÌNH CŨ -> ĐƯA VỀ NỀN XANH GEMINI (BGR: 30, 20, 15)
        gemini_bg_bgr = (245, 230, 195)
        blank_canvas = np.full((900, 900, 3), gemini_bg_bgr, dtype=np.uint8)
        blank_pil = Image.fromarray(cv2.cvtColor(blank_canvas, cv2.COLOR_BGR2RGB))
        blank_tk = ImageTk.PhotoImage(blank_pil)

        self.lbl_full_result.config(image=blank_tk)
        self.lbl_full_result.image = blank_tk
        # 3. Ép Tkinter cập nhật giao diện ngay lập tức
        self.root.update()
        avg_cx, avg_cy, avg_r_in, avg_angle_offset, last_frame = self.detect_connector_pose()
        if avg_cx is None or last_frame is None:
            messagebox.showwarning("Cảnh báo", "Không tìm thấy Connector!")
            self.lbl_result.config(text="NOT CONECTOR", fg="red")
            # Mở lại nút bấm sau khi chụp xong
            self.btn_inspect.config(state="normal", text="🔍 KIỂM TRA CONNECTOR")
            return

        NUM_SAMPLES = 8
        all_distances = [[] for _ in range(6)] # Mảng lưu 10 khoảng cách của 6 tai
        last_clean_frame = None

        # 1. BẮT ĐẦU VÒNG LẶP CHỤP 10 FRAMES LIÊN TIẾP
        for sample_idx in range(NUM_SAMPLES):
            ret, frame = self.cap.read()
            if not ret or frame is None:
                continue

            last_clean_frame = frame.copy()

            # Chạy thuật toán xử lý ảnh trên frame hiện tại
            processed_img, edge_img, status, ear_data = self.process_image(frame,cx=avg_cx,cy=avg_cy,r_input=avg_r_in,angle_offset=avg_angle_offset)

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
        processed_img, edge_img, status, ear_data = self.process_image(last_clean_frame,avg_cx,cy=avg_cy,r_input=avg_r_in,angle_offset=avg_angle_offset)

        if processed_img is None:
            return

        # 4. ĐÁNH GIÁ LẠI TRẠNG THÁI OK/NG DỰA TRÊN KHOẢNG CÁCH TRUNG BÌNH
        max_avg_d = max(avg_distances) if max(avg_distances) > 0 else 1.0
        is_ng = False
        final_ear_data = []

        for i in range(6):
            avg_d = avg_distances[i]
            crop_img, _, _, _ = ear_data[i] if i < len(ear_data) else (None, "", "", (0,0,0))
            avg_r_in
            # Điều kiện đánh giá OK/NG dựa trên trung bình
            if (avg_d <= (avg_r_in*4/21)) or avg_d < 0.70 * max_avg_d:
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
        h_img, w_img = processed_img.shape[:2]
        crop_margin = 450
        # Ép kiểu tâm sang số nguyên int
        cx_int, cy_int = int(avg_cx), int(avg_cy)

        margin =int(crop_margin)
        x1, x2 = max(0, cx_int - margin), min(w_img, cx_int + margin)
        y1, y2 = max(0, cy_int - margin), min(h_img, cy_int + margin)

        main_crop = processed_img[y1:y2, x1:x2]
        edge_crop = edge_img[y1:y2, x1:x2] if edge_img is not None else None
        display_size = (500, 500)

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


        full_result_img = last_clean_frame

        if full_result_img is not None and full_result_img.size > 0:
            # --- 1. VẼ THÔNG SỐ 6 TAI LÊN ẢNH GỐC TẠI TỌA ĐỘ CỰC ---
            if 'avg_cx' in locals() and 'avg_cy' in locals() and 'avg_r_in' in locals():
                # Danh sách 6 góc tương ứng với 6 tai (thay bằng biến góc thực tế nếu có avg_angle_offset)
                BASE_ANGLES2 = [0, 60, 120, 180, 240, 300]
                DYNAMIC_FIXED_ANGLES2 = [(ang + avg_angle_offset) for ang in BASE_ANGLES2]
                # Bán kính đặt chữ (nằm sát phía ngoài viền tai)
                R_text = int(avg_r_in - 45)

                for i, (crop_img, avg_area_str, ear_status, color) in enumerate(final_ear_data):
                    # Tính chuyển đổi px -> um (chia 2)
                    try:
                        val_px = float(str(avg_area_str).replace("px", "").strip())
                        val_um = val_px*1.575/avg_r_in;
                        if(val_um>0):
                            display_val = f"{val_um:.3f} mm"
                        else:    
                            display_val = f"Không tìm thấy..."
                    except ValueError:
                        display_val = f"Không tìm thấy..."
                    if(val_px>0):
                        # Xác định chuỗi hiển thị và màu sắc (BGR: Xanh lá cho OK, Đỏ cho NG)
                        text_str = f"{display_val} ({ear_status})"
                    else:
                        text_str = f"{display_val}"
                    bgr_color = (0, 0, 255) if ear_status == "NG" else (0, 255, 0)

                    # Tính tọa độ (x, y) của từng tai trên ảnh full
                    angle_deg = DYNAMIC_FIXED_ANGLES2[i]
                    rad = math.radians(-angle_deg)
                    
                    # Trừ sin do trục Y của OpenCV hướng xuống
                    cx_ear = int(avg_cx + R_text * math.cos(rad))
                    cy_ear = int(avg_cy - R_text * math.sin(rad))

                    # Dịch tâm chữ một chút để căn giữa văn bản
                    (t_w, t_h), _ = cv2.getTextSize(text_str, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                    text_x = int(cx_ear - t_w / 2)
                    text_y = int(cy_ear + t_h / 2)

                    # Vẽ chữ OK/NG và giá trị um lên ảnh gốc
                    cv2.putText(
                        full_result_img,
                        text_str,
                        (text_x, text_y),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        bgr_color,
                        2,
                        cv2.LINE_AA
                    )
                    # VẼ ĐƯỜNG VẠCH MÀU ĐỎ 25PX VUÔNG GÓC VỚI TIA QUÉT (TẠI ĐỈNH MÉP TAI)
                    # -------------------------------------------------------------
                    # 1. Tọa độ đỉnh mép tai (bán kính R_in + val_px)
                    if(val_px>0):
                        r_outer = avg_r_in + val_px
                        x_top = avg_cx + r_outer * math.cos(rad)
                        y_top = avg_cy - r_outer * math.sin(rad)

                        # 2. Vector vuông góc với tia quét tại đỉnh mép tai
                        perp_rad = rad + math.pi / 2.0

                        # 3. Tọa độ 2 đầu đoạn thẳng 25px ôm theo mép tai
                        x_perp1 = int(x_top + 25 * math.cos(perp_rad))
                        y_perp1 = int(y_top - 25 * math.sin(perp_rad))

                        x_perp2 = int(x_top - 25 * math.cos(perp_rad))
                        y_perp2 = int(y_top + 25 * math.sin(perp_rad))

                        # 4. Vẽ đường vạch màu đỏ nằm trên mép tai
                        cv2.line(
                            full_result_img,
                            (x_perp1, y_perp1),
                            (x_perp2, y_perp2),
                            (0, 0, 255),  # Màu đỏ (BGR)
                            2,            # Độ dày nét vẽ
                            cv2.LINE_AA
                        )
# -------------------------------------------------------------
                    # A. TỌA ĐỘ TÂM ĐIỂM TAI (ĐỈNH MÉP TAI)
                    # -------------------------------------------------------------
                    BOX_HALF_SIZE = 100
                    r_outer = avg_r_in-10
                    x_ear_top = int(avg_cx + r_outer * math.cos(rad))
                    y_ear_top = int(avg_cy - r_outer * math.sin(rad))

                    # -------------------------------------------------------------
                    # B. VẼ Ô VUÔNG CÓ TÂM TRÙNG VỚI ĐIỂM TAI (X_EAR_TOP, Y_EAR_TOP)
                    # -------------------------------------------------------------
                    box_x1 = x_ear_top - BOX_HALF_SIZE
                    box_y1 = y_ear_top - BOX_HALF_SIZE
                    box_x2 = x_ear_top + BOX_HALF_SIZE
                    box_y2 = y_ear_top + BOX_HALF_SIZE

                    # Vẽ ô vuông màu theo trạng thái OK/NG
                    cv2.rectangle(
                        full_result_img,
                        (box_x1, box_y1),
                        (box_x2, box_y2),
                        bgr_color,
                        2
                    )
                # --- 2. CẮT VÙNG CONNECTOR THEO TÂM VÀ BÁN KÍNH ---
                R_crop = int(avg_r_in + 110)
                h_img, w_img = full_result_img.shape[:2]

                x1 = max(0, int(avg_cx - R_crop))
                y1 = max(0, int(avg_cy - R_crop))
                x2 = min(w_img, int(avg_cx + R_crop))
                y2 = min(h_img, int(avg_cy + R_crop))

                crop_img = full_result_img[y1:y2, x1:x2]
            else:
                crop_img = full_result_img

            # --- 3. ĐỆM CANVAS NỀN ĐEN ĐỂ HIỂN THỊ CHỐNG GIẬT KHUNG (SIZE 900x900) ---
            target_w, target_h = 900, 900
            ch, cw = crop_img.shape[:2]
            
            # Tính tỉ lệ resize giữ nguyên dáng Connector
            scale = min(target_w / cw, target_h / ch)
            new_w, new_h = int(cw * scale), int(ch * scale)
            resized_crop = cv2.resize(crop_img, (new_w, new_h), interpolation=cv2.INTER_AREA)

            # Đặt hình vuông vừa vặn vào giữa frame 900x900
            # Tạo nền màu xanh Gemini thay vì np.zeros (nền đen)
            GEMINI_BG = (245, 230, 195) # BGR cho tone xanh đen mờ / Gemini Dark
            canvas = np.full((target_h, target_w, 3), GEMINI_BG, dtype=np.uint8)
            off_x = (target_w - new_w) // 2
            off_y = (target_h - new_h) // 2
            canvas[off_y:off_y + new_h, off_x:off_x + new_w] = resized_crop

            # --- 4. CHUYỂN ĐỔI VÀ ĐƯA LÊN TKINTER ---
            img_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(img_rgb)
            img_tk = ImageTk.PhotoImage(img_pil)

            self.lbl_full_result.config(image=img_tk)
            self.lbl_full_result.image = img_tk
        else:
            print("[WARNING] full_result_img bị None hoặc rỗng, không thể hiển thị!")
    def __del__(self):
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()

if __name__ == "__main__":
    root = tk.Tk()
    app = PCBCheckerApp(root)
    root.mainloop()