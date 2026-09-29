import cv2
import numpy as np
import math
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import gc  # Thêm thư viện dọn rác ở đầu file: import gc
import threading
import time
import sys
import os
from datetime import datetime
import json
from tkinter import simpledialog, messagebox
from tkinter import filedialog
import threading
CONFIG_FILE = "config.json"
NUM_SAMPLES = 1
NUM_SAMPLES_detect=1

# =========================================================================
# 1. HÀM TỰ ĐỘNG TẠO THƯ MỤC LƯU ẢNH VÀ LOG TẠI VỊ TRÍ FILE .EXE
# =========================================================================
def get_exe_dir():
    """Hàm lấy đường dẫn đến thư mục chứa file .exe (hoặc file .py)"""
    if getattr(sys, 'frozen', False):
        # Nếu đã đóng gói thành file .exe
        return os.path.dirname(sys.executable)
    else:
        # Nếu đang chạy trực tiếp bằng file .py
        return os.path.dirname(os.path.abspath(__file__))

# Lấy đường dẫn gốc
BASE_DIR = get_exe_dir()

# Tạo sẵn 2 thư mục cố định ngay bên cạnh file .exe
IMAGE_DIR = os.path.join(BASE_DIR, "Hinh_Anh_Kiem_Tra")
LOG_DIR = os.path.join(BASE_DIR, "File_Log")

# Tự động tạo thư mục trên máy tính nếu chưa có
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# File log nằm gọn trong thư mục File_Log
LOG_FILE_PATH = os.path.join(LOG_DIR, "inspection_log.txt")
def write_log(message):
    """Hàm ghi log kèm thời gian vào file log"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}\n"
    print(log_line, end="")
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
        f.write(log_line)
def get_best_camera_index():
    # Thử kiểm tra Camera 1 trước (thường là Cam USB cắm ngoài)
    cap1 = cv2.VideoCapture(1, cv2.CAP_DSHOW)
    if cap1.isOpened():
        cap1.release()
        return 1  # Ưu tiên lấy camera USB ngoài
    
    # Nếu không có Cam 1 thì quay về Cam 0 (Webcam có sẵn trên máy)
    return 0

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

        # Biến quản lý chế độ Auto & Thống kê
        self.is_auto_running = False
        self.total_count = tk.IntVar(value=0)
        self.ok_count = tk.IntVar(value=0)
        self.ng_count = tk.IntVar(value=0)
        self.total_execution_time =0
        self.total_count_run =0
        self.init_camera

        # --- BIẾN CẤU HÌNH BÁN KÍNH (KHỞI TẠO MẶC ĐỊNH) ---
        self.center_radius = tk.IntVar(value=300) # Bán kính đường tròn tìm tâm (Pixel)
        self.number_log = tk.IntVar(value=0) # Bán kính đường tròn tìm tâm (Pixel)
        self.spec_mm = tk.DoubleVar(value=0.3) # Bán kính đường tròn tìm tâm (Pixel)
        self.config_magnitude = tk.IntVar(value=30) # Mức ngưỡng - Threshold
        # Đọc cấu hình từ File nếu có
        self.load_config()
        # --- FRAME ĐIỀU KHIỂN TOP ---
        top_frame = tk.Frame(root)
        top_frame.pack(fill="x", pady=10)

        # Container chứa các nút bấm và thống kê
        btn_container = tk.Frame(top_frame)
        btn_container.pack()
        # Tạo nút bấm chạy hàm test_single_image
        self.btn_test_image = tk.Button(
            self.root, 
            text="📁 Chọn Ảnh Test", 
            command=self.test_single_image,
            font=("Arial", 11, "bold"),
            bg="#2196F3",
            fg="white"
        )
        self.btn_test_image.pack(pady=5)
        # Nút bấm bắt đầu kiểm tra
        self.btn_inspect = tk.Button(
            top_frame, text="🔍 KIỂM TRA CONNECTOR", command=self.inspect_current_frame, 
            font=("Arial", 12, "bold"), bg="#4CAF50", fg="white", padx=20, pady=5
        )
        self.btn_inspect.pack()
        # 2. Đăng ký phím Spacebar cho toàn bộ ứng dụng
        self.root.bind("<space>", self.inspect_current_frame)
        # Đăng ký sự kiện khi người dùng tắt ứng dụng -> Bắt buộc lưu JSON
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.lbl_result = tk.Label(top_frame, text="KẾT QUẢ: ĐANG LIVE CAMERA", font=("Arial", 20, "bold"), fg="gray")
        self.lbl_result.pack(pady=3)
        

        # --- KHUNG CHỨA HIỂN THỊ ÁNH ---
        content_frame = tk.Frame(root)
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # KHUNG BÊN TRÁI: Chứa 2 ảnh lớn xếp dọc (Ảnh chính ở trên, Ảnh cạnh ở dưới)
        left_container = tk.Frame(content_frame)
        left_container.pack(side="left", fill="y", expand=False, padx=5, pady=5)

        # 1. Khung ảnh chính (Live Video / Kết quả)
        left_frame = tk.LabelFrame(left_container, text=" ẢNH KẾT QUẢ ĐO ", font=("Arial", 10, "bold"))
        left_frame.pack(side="top", fill="x", expand=False, pady=(0, 5))

        # 2. Thêm khung chứa nút điều khiển phía trên/dưới ảnh
        top_cam_bar = tk.Frame(left_container)
        top_cam_bar.pack(fill="y", padx=5, pady=2)

        # Nút bấm Phóng to toàn màn hình
        self.btn_fullscreen = tk.Button(
            top_cam_bar, text="⛶ TOÀN MÀN HÌNH", command=self.open_fullscreen_live,
            font=("Arial", 9, "bold"), bg="#607D8B", fg="white", padx=10
        )
        self.btn_fullscreen.pack(side="right")
        self.panel_main = tk.Label(left_frame, bd=1, relief="solid")
        self.panel_main.pack(padx=5, pady=5)
        # Mẹo: Click đúp vào ảnh cũng sẽ bật Toàn màn hình
        self.panel_main.bind("<Double-Button-1>", lambda event: self.open_fullscreen_live())

        # Biến quản lý cửa sổ Fullscreen
        self.fullscreen_window = None
        self.panel_fullscreen = None
        # 2. Khung ảnh Cạnh Đen Trắng
        edge_frame = tk.LabelFrame(left_container, text=" BẢN ĐỒ CẠNH ĐEN TRẮNG ", font=("Arial", 10, "bold"))
        edge_frame.pack(side="bottom", fill="both", expand=True, pady=(5, 0))

        self.panel_edge = tk.Label(edge_frame, bd=1, relief="solid")
        self.panel_edge.pack(padx=5, pady=5)

        # 3. Khung hiển thị ảnh kết quả tổng (chứa cả 6 nhãn tai)
        mid_frame = tk.LabelFrame(content_frame, text=" CHI TIẾT CONNECTOR ", font=("Arial", 10, "bold"), padx=10, pady=10)
        mid_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        # Lưu lại mid_frame để lấy kích thước tự động điều chỉnh ảnh
        self.mid_frame = mid_frame 

        # Tạo DUY NHẤT 1 Label to để hiển thị bức ảnh kết quả hoàn chỉnh
        self.lbl_full_result = tk.Label(mid_frame)
        self.lbl_full_result.pack(fill="both", expand=True)

        # 4. Khung hiển thị ảnh kết quả tổng (chứa cả 6 nhãn tai)
        right_frame = tk.LabelFrame(content_frame, text=" THÔNG SỐ HIỂN THỊ ", font=("Arial", 10, "bold"), padx=10, pady=10)
        right_frame.pack(side="right", fill="y",expand=False, padx=5, pady=5)
        # 3.2. Khung thống kê tỉ suất & Điều khiển Auto
        auto_frame = tk.LabelFrame(right_frame, text=" CHẾ ĐỘ AUTO & THỐNG KÊ ", font=("Arial", 10, "bold"), padx=10, pady=10)
        auto_frame.pack(side="top", fill="x", pady=(5, 0))
        # Nhãn hiển thị thống kê chi tiết tỉ suất

        self.lbl_total = tk.Label(auto_frame, text=f"Tổng số lần chạy: {self.total_count.get()}", font=("Arial", 9, "bold"), anchor="w")
        self.lbl_total.pack(fill="x", pady=1)

        self.lbl_ok_ng = tk.Label(auto_frame, text=f"OK: {self.ok_count.get()}  |  NG: {self.ng_count.get()}", font=("Arial", 9, "bold"), fg="#2E7D32", anchor="w")
        self.lbl_ok_ng.pack(fill="x", pady=1)
        if(self.total_count.get()):
            self.lbl_rate = tk.Label(auto_frame, text=f"Tỉ lệ OK (Rate): {(self.ok_count.get() / self.total_count.get()) * 100:.1f}%", font=("Arial", 9, "bold"), fg="#1565C0", anchor="w")
        else:
            self.lbl_rate = tk.Label(auto_frame, text="Tỉ lệ OK (Rate): 0%", font=("Arial", 9, "bold"), fg="#1565C0", anchor="w")
        self.lbl_rate.pack(fill="x", pady=1)

        self.lbl_time = tk.Label(auto_frame, text="Thời gian TB: 0.0 ms", font=("Arial", 9, "bold"), fg="#E65100", anchor="w")
        self.lbl_time.pack(fill="x", pady=1)

# ==========================================
        # 3.1. THÔNG SỐ CẤU HÌNH (SPEC & BÁN KÍNH TÂM)
        # ==========================================
        cfg_frame = tk.LabelFrame(right_frame, text=" THÔNG SỐ CẤU HÌNH ", font=("Arial", 10, "bold"), padx=10, pady=8)
        cfg_frame.pack(side="top", fill="x", pady=5)

        # 1. SPEC (mm) - HIỂN THỊ DÒNG 0 (TRƯỚC)
        tk.Label(cfg_frame, text="Spec (mm):", font=("Arial", 9, "bold"), fg="#D32F2F").grid(row=0, column=0, sticky="w", pady=2)
        spn_spec = tk.Spinbox(
            cfg_frame, 
            from_=0.01, 
            to=10.0, 
            increment=0.01, 
            textvariable=self.spec_mm, 
            width=8, 
            font=("Arial", 9, "bold"),
            format="%.2f"
        )
        spn_spec.grid(row=0, column=1, padx=5, pady=2)

        # 2. BÁN KÍNH TÂM (px) - HIỂN THỊ DÒNG 1 (SAU)
        tk.Label(cfg_frame, text="Bán kính Tâm (px):", font=("Arial", 9)).grid(row=1, column=0, sticky="w", pady=2)
        spn_center_r = tk.Spinbox(
            cfg_frame, 
            from_=1, 
            to=1000, 
            textvariable=self.center_radius, 
            width=8, 
            font=("Arial", 9, "bold")
        )
        spn_center_r.grid(row=1, column=1, padx=5, pady=2)
        # 3. Mức ngưỡng - Threshold
        tk.Label(cfg_frame, text="Threshold:", font=("Arial", 9)).grid(row=2, column=0, sticky="w", pady=2)
        spn_threshold = tk.Spinbox(
            cfg_frame, 
            from_=1, 
            to=255, 
            textvariable=self.config_magnitude, 
            width=8, 
            font=("Arial", 9, "bold")
        )
        spn_threshold.grid(row=2, column=1, padx=5, pady=2)
        # 3. NÚT LƯU CẤU HÌNH - DÒNG 2 (DƯỚI CÙNG KHUNG)
        self.btn_save_config = tk.Button(
            cfg_frame, text="💾 LƯU CẤU HÌNH", command=self.save_config,
            font=("Arial", 9, "bold"), bg="#FF9800", fg="white", padx=10, pady=3
        )
        self.btn_save_config.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(5, 0))
            # Chạy luồng cập nhật video trực tiếp
        self.update_video_stream()


    def test_single_image(self):
        """Mở hộp thoại chọn file ảnh và chạy quy trình kiểm tra trên ảnh đó"""
        # 1. Hiển thị cửa sổ chọn file ảnh (chỉ lọc file PNG, JPG, BMP)
        file_path = filedialog.askopenfilename(
            title="Chọn ảnh để test kiểm tra",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp"), ("All Files", "*.*")]
        )
        
        # Nếu người dùng bấm Cancel (không chọn file) thì thoát
        if not file_path:
            return

        # 2. Đọc ảnh từ đường dẫn vừa chọn
        frame = cv2.imread(file_path)
        if frame is None:
            print(f"[LỖI] Không thể đọc được file ảnh: {file_path}")
            return

        # 3. Gọi trực tiếp hàm xử lý kiểm tra (Hàm xử lý ảnh hiện tại của bạn)
        # Giả sử hàm kiểm tra ảnh của bạn tên là process_image hoặc inspect_frame
        # Bạn truyền trực tiếp 'frame' vừa đọc vào để xử lý:
        self.inspect_current_frame(test_frame=frame, is_test=True)
    # --- HÀM LƯU BỘ THÔNG SỐ VÀO FILE CONFIG.JSON ---

    def save_config(self):
        ADMIN_PASSWORD = "1"
        # Hiện hộp thoại hỏi mật khẩu
        pwd = simpledialog.askstring("Xác thực kỹ sư", "Nhập mật khẩu để lưu cấu hình:", show='*')
        if pwd == ADMIN_PASSWORD:
            config_data = {
                "center_radius": self.center_radius.get(),
                "spec_mm": self.spec_mm.get(),
                "config_magnitude ": self.config_magnitude .get(),
            }
            try:
                with open(CONFIG_FILE, "w") as f:
                    json.dump(config_data, f, indent=4)
                messagebox.showinfo("Thông báo", "Đã lưu cài đặt cấu hình thành công!")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể lưu file cấu hình: {e}")
        elif pwd is not None: # Nếu nhập sai (và không bấm Cancel)
            messagebox.showerror("Lỗi mật khẩu", "Mật khẩu không đúng! Bạn không có quyền sửa cấu hình.")

    # --- HÀM ĐỌC BỘ THÔNG SỐ TỪ FILE CONFIG.JSON ---
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config_data = json.load(f)
                    self.center_radius.set(config_data.get("center_radius", 300))
                    self.spec_mm.set(config_data.get("spec_mm", 0.3))#spec_mm
                    self.config_magnitude .set(config_data.get("config_magnitude ", 30))#total_count

                    self.total_count .set(config_data.get("total_count", 0))
                    self.ok_count .set(config_data.get("ok_count", 0))
                    self.ng_count .set(config_data.get("ng_count", 0))                  
            except Exception as e:
                print(f"Lỗi khi đọc file config: {e}")

        config_data = {
            "center_radius": self.center_radius.get(),
            "spec_mm": self.spec_mm.get(),
            "config_magnitude ": self.config_magnitude .get(),
            "total_count ": self.total_count.get(),
            "ok_count ": self.ok_count.get(),
            "ng_count ": self.ng_count.get()
        }
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config_data, f, indent=4)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể lưu file cấu hình: {e}")
    # --- HÀM ĐỌC BỘ THÔNG SỐ TỪ FILE CONFIG.JSON ---
    def load_number(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config_data = json.load(f)
                    self.center_radius.set(config_data.get("center_radius", 300))
            except Exception as e:
                print(f"Lỗi khi đọc file config: {e}")               
    # --- CÁC HÀM XỬ LÝ CHẾ ĐỘ AUTO ---
    def start_auto(self):
        """Bắt đầu chạy tự động"""
        self.is_auto_running = True
        self.btn_start_auto.config(state="disabled")
        self.btn_stop_auto.config(state="normal")
        self.btn_inspect.config(state="disabled")
        self.run_auto_loop()

    def stop_auto(self):
        """Dừng chạy tự động"""
        self.is_auto_running = False
        self.btn_start_auto.config(state="normal")
        self.btn_stop_auto.config(state="disabled")
        self.btn_inspect.config(state="normal")


    def init_camera(self):
        """Hàm riêng chuyên khởi tạo / Reconnect Camera"""
        if self.cap is not None:
            self.cap.release() # Giải phóng tài nguyên cũ nếu có

        # Lúc khởi tạo camera trong ứng dụng:
        cam_index = get_best_camera_index()
        self.cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            # 3. Xóa bộ đệm Buffer (Chỉ giữ 1 frame mới nhất)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
            # Khóa giá trị Phơi sáng cố định (Chỉnh số này tùy theo độ sáng môi trường)
            self.cap.set(cv2.CAP_PROP_EXPOSURE, -6) 
            self.cap.set(cv2.CAP_PROP_GAIN, 0)
            # Tắt Tự động Cân bằng trắng (Auto White Balance)
            if hasattr(cv2, 'CAP_PROP_AUTO_WB'):
                self.cap.set(cv2.CAP_PROP_AUTO_WB, 0)
            self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0) # Tắt Auto Focus nếu có
            # Chỉ cho phép bộ đệm lưu tối đa 1 frame

            self.cap.set(cv2.CAP_PROP_EXPOSURE, -8)
           
            self.cap.set(cv2.CAP_PROP_BRIGHTNESS, 1) # Giảm độ sáng tổng thể

            self.is_camera_connected = True
            print("[OK] Đã kết nối thành công Camera!")
            self.lbl_result.config(text="KẾT QUẢ: ĐANG LIVE CAMERA", fg="gray")
        else:
            self.is_camera_connected = False
            print("[WARNING] Không thể kết nối Camera. Đang đợi cắm lại...")
        # Đọc bỏ 10 frame đầu để phần cứng Camera ổn định dòng điện & phơi sáng
        for _ in range(10):
            self.cap.grab()

    def update_video_stream(self):
        next_delay = 33  # ĐÚNG 33ms (~30 FPS)
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
                # --- B. TRUYỀN VIDEO LIVE SANG CỬA SỔ FULLSCREEN (Nếu đang mở) ---
                if hasattr(self, 'panel_fullscreen') and self.panel_fullscreen is not None:
                    # Lấy kích thước màn hình máy tính để phóng to vừa khít
                    screen_w = self.fullscreen_window.winfo_screenwidth()
                    screen_h = self.fullscreen_window.winfo_screenheight()

                    img_full = img_pil.resize((screen_w, screen_h))
                    img_full_tk = ImageTk.PhotoImage(image=img_full)

                    # Đẩy frame trực tiếp lên panel cửa sổ fullscreen
                    self.panel_fullscreen.config(image=img_full_tk)
                    self.panel_fullscreen.image = img_full_tk # Bắt buộc phải có dòng này để không bị mất ảnh
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
        # Ép Python dọn dẹp bộ nhớ rác định kỳ
        if not hasattr(self, 'frame_count'):
            self.frame_count = 0
        self.frame_count += 1
        if self.frame_count % 500 == 0:  # Cứ 500 frames dọn RAM 1 lần
            gc.collect()
        self.root.after(next_delay, self.update_video_stream)

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
    def open_fullscreen_live(self):
        """Mở cửa sổ hiển thị Live Camera toàn màn hình"""
        if self.fullscreen_window is not None and self.fullscreen_window.winfo_exists():
            return # Nếu đã mở rồi thì không mở thêm

        # 1. Tạo cửa sổ Toplevel
        self.fullscreen_window = tk.Toplevel(self.root)
        self.fullscreen_window.title("LIVE CAMERA - FULLSCREEN")
        
        # 2. Bật chế độ Fullscreen phủ kín màn hình
        self.fullscreen_window.attributes("-fullscreen", True)
        self.fullscreen_window.configure(bg="black")

        # 3. Thêm Label hiển thị ảnh chiếm trọn cửa sổ mới
        self.panel_fullscreen = tk.Label(self.fullscreen_window, bg="black")
        self.panel_fullscreen.pack(fill="both", expand=True)

        # 4. Thêm nút Thoát nhỏ ở góc trên bên phải
        btn_close = tk.Button(
            self.fullscreen_window, text="✕ THOÁT (ESC)", command=self.close_fullscreen_live,
            font=("Arial", 10, "bold"), bg="#f44336", fg="white", bd=0, padx=10, pady=5
        )
        # Đặt nút đè lên góc trên bên phải bằng place
        btn_close.place(relx=0.99, rely=0.01, anchor="ne")

        # 5. Bắt sự kiện ấn phím ESC hoặc Click đúp để thoát Fullscreen
        self.fullscreen_window.bind("<Escape>", lambda e: self.close_fullscreen_live())
        self.panel_fullscreen.bind("<Double-Button-1>", lambda e: self.close_fullscreen_live())

    def close_fullscreen_live(self):
        """Đóng cửa sổ toàn màn hình"""
        if self.fullscreen_window is not None:
            self.fullscreen_window.destroy()
            self.fullscreen_window = None
            self.panel_fullscreen = None
    def on_closing(self):
        """Khi đóng app: Giữ nguyên cấu hình cũ, chỉ cập nhật 3 số đếm sản lượng"""
        try:
            data = {}
            # Step 1: Đọc lại file cũ nếu có để giữ nguyên 3 thông số cấu hình
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            
    # 2. Rút giá trị int từ IntVar ra bằng .get() trước khi lưu JSON
            data["total_count"] = self.total_count.get() if isinstance(self.total_count, tk.IntVar) else self.total_count
            data["ok_count"] = self.ok_count.get() if isinstance(self.ok_count, tk.IntVar) else self.ok_count
            data["ng_count"] = self.ng_count.get() if isinstance(self.ng_count, tk.IntVar) else self.ng_count

            # 3. Ghi đè lại file JSON
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            # Step 3: Ghi đè lại file
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            print("Đã bảo lưu thành công 3 thông số sản lượng!")
        except Exception as e:
            print(f"Lỗi khi lưu sản lượng trước khi thoát: {e}")
        finally:
            self.root.destroy()
    def detect_connector_pose(self, frame):
        """
        Hàm phát hiện Tâm (cx, cy) và Góc lệch (0° hay 30°) của Connector.
        Xử lý trực tiếp 1 frame truyền vào.
        """     
        if frame is None:
            print("[ERROR] Frame truyền vào bị None!")
            return None, None, None, None, frame

        img_h, img_w = frame.shape[:2]

        # 1. TIỀN TÍNH TOÁN RADIAN CHẤM ĐIỂM HỆ GÓC
        BASE_SET_0  = [0, 60, 120, 180, 240, 300]   # Hệ 0 độ
        BASE_SET_30 = [30, 90, 150, 210, 270, 330] # Hệ 30 độ
        # 1. KHAI BÁO HỆ SỐ CO DÃN (CONRESIZE)
        # CONRESIZE = 2.0 -> Thu nhỏ 1/2 (50%)
        # CONRESIZE = 3.0 -> Thu nhỏ 1/3 (33.3%)
        CONRESIZE = 8.0  
        scale_factor = (1.0 / CONRESIZE)

        angles_0  = np.array([(b + da) % 360 for b in BASE_SET_0 for da in range(-3, 4)])
        angles_30 = np.array([(b + da) % 360 for b in BASE_SET_30 for da in range(-3, 4)])
        rads_0  = np.radians(angles_0)
        rads_30 = np.radians(angles_30)

        # 2. XỬ LÝ ẢNH THU NHỎ THEO TỶ LỆ CONRESIZE
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Resize theo scale_factor linh hoạt
        small_gray = cv2.resize(gray, (0, 0), fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_AREA)
        small_blurred = cv2.GaussianBlur(small_gray, (3, 3), 0)
        
        # Tự động tính ngưỡng Canny Otsu
        high_thresh, _ = cv2.threshold(small_blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        low_thresh = 0.5 * high_thresh
        edges = cv2.Canny(small_blurred, low_thresh, high_thresh)

        # 3. CHIA BÁN KÍNH MỤC TIÊU THEO CONRESIZE
        target_r = self.center_radius.get() / CONRESIZE
        small_min_r = int((self.center_radius.get() * 0.92) / CONRESIZE)
        small_max_r = int((self.center_radius.get() * 1.08) / CONRESIZE)

        # 4. CHẠY HOUGH CIRCLES TRÊN ẢNH CANNY THU NHỎ
        circles = cv2.HoughCircles(
            edges, 
            cv2.HOUGH_GRADIENT, 
            dp=1.0, 
            minDist=20,
            param1=100, 
            param2=20,
            minRadius=small_min_r, 
            maxRadius=small_max_r
        )
        
        best_circle = None
        if circles is not None:
            # Lấy ứng viên đường tròn xếp đầu tiên từ Hough
            circles = np.uint16(np.around(circles))
            best_circle = circles[0][0] # (cx_s, cy_s, r_s)

        # BẮT LỖI NẾU KHÔNG TÌM THẤY CONNECTOR (DỌN SẠCH CÁC DÒNG IF DƯ THỪA)
        if best_circle is None:
            print("[WARNING] Không tìm thấy Connector!")
            return None, None, None, None, frame
        # Tọa độ sơ bộ quy đổi lên ảnh gốc
        best_circle_small = circles[0][0]
        cx_coarse = float(best_circle_small[0] * CONRESIZE)
        cy_coarse = float(best_circle_small[1] * CONRESIZE)
        r_coarse  = float(best_circle_small[2] * CONRESIZE)

        # =========================================================================
        # BƯỚC 2: TÌM TÂM CHÍNH XÁC Tuyệt Đối (FINE SEARCH) TRÊN ROI ẢNH GỐC 100%
        # =========================================================================
        # Tạo khung ROI nhỏ bao quanh Connector (rộng hơn bán kính 20%)
        margin = int(r_coarse * 1.25)
        x1 = max(0, int(cx_coarse - margin))
        y1 = max(0, int(cy_coarse - margin))
        x2 = min(frame.shape[1], int(cx_coarse + margin))
        y2 = min(frame.shape[0], int(cy_coarse + margin))

        # Cắt ROI trên ảnh gốc Full HD
        roi_gray = gray[y1:y2, x1:x2]
        roi_blurred = cv2.GaussianBlur(roi_gray, (3, 3), 0)
        edges_roi = cv2.Canny(roi_blurred, 0.5 * high_thresh, high_thresh)

        # Chạy HoughCircles chính xác cao trong ROI
        fine_min_r = int(self.center_radius.get() * 0.92)
        fine_max_r = int(self.center_radius.get() * 1.08)

        fine_circles = cv2.HoughCircles(
            edges_roi, cv2.HOUGH_GRADIENT, dp=1.0, minDist=20,
            param1=100, param2=15, minRadius=fine_min_r, maxRadius=fine_max_r
        )

        if fine_circles is not None:
            # Lấy tâm chính xác trong không gian ROI
            cx_roi, cy_roi, r_in = fine_circles[0][0]
            # Quy đổi tọa độ ROI về tọa độ toàn bộ ảnh gốc
            cx = float(cx_roi + x1)
            cy = float(cy_roi + y1)
            r_in = float(r_in)
        else:
            # Nếu ROI không lọc được thì dùng tạm kết quả sơ bộ
            cx, cy, r_in = cx_coarse, cy_coarse, r_coarse

        r_out = int(r_in * 1.4)


        # 4. CẮT ROI XUNG QUANH CONNECTOR VÀ CHẠY SOBEL
        pad = r_out + 15
        x1, x2 = max(0, int(cx - pad)), min(img_w, int(cx + pad))
        y1, y2 = max(0, int(cy - pad)), min(img_h, int(cy + pad))

        roi_gray = gray[y1:y2, x1:x2]
        roi_blurred = cv2.GaussianBlur(roi_gray, (3, 3), 0)

        grad_x = cv2.Sobel(roi_blurred, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(roi_blurred, cv2.CV_32F, 0, 1, ksize=3)
        
        magnitude_roi = cv2.magnitude(grad_x, grad_y)
        magnitude_roi = cv2.normalize(magnitude_roi, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        cx_roi = cx - x1
        cy_roi = cy - y1
        roi_h, roi_w = magnitude_roi.shape

        # 5. CHẤM ĐIỂM HỆ GÓC TRÊN ROI (NUMPY VECTORIZATION)
        thresh_mag = self.config_magnitude.get()
        r_range = np.arange(int(r_in) + 10, int(r_out) - 2)

        def calc_system_score_roi(rads, base_count=6):
            if len(r_range) == 0:
                return 0

            # 1. Tạo lưới tọa độ Cực -> Tọa độ vuông
            R, RAD = np.meshgrid(r_range, rads)
            PX = np.round(cx_roi + R * np.cos(RAD)).astype(np.int32)
            PY = np.round(cy_roi + R * np.sin(RAD)).astype(np.int32)

            # 2. Lọc các điểm nằm ngoài phạm vi ROI
            valid_mask = (PX >= 0) & (PX < roi_w) & (PY >= 0) & (PY < roi_h)
            PX = np.clip(PX, 0, roi_w - 1)
            PY = np.clip(PY, 0, roi_h - 1)

            # 3. Lấy giá trị Cường độ Sobel
            mag_values = magnitude_roi[PY, PX]
            mag_values[~valid_mask] = 0

            # 4. Tạo Mask các điểm có biên độ cạnh vượt ngưỡng (loại nhiễu nền mờ)
            edge_mask = mag_values > thresh_mag

            # 5. Lấy độ mạnh của Gradient (Magnitude) làm điểm thay vì dùng Bán kính R
            # Giúp nhiễu ở xa không bị "ăn gian" điểm số R khổng lồ
            scores_matrix = np.where(edge_mask, mag_values, 0)

            # 6. Reshape về (6 chân, 7 góc quét lân cận, N bán kính)
            # score_reshaped shape: (base_count, 7, len(r_range))
            scores_reshaped = scores_matrix.reshape(base_count, 7, -1)

            # CÁCH CHẤM ĐIỂM CHỐNG NHIỄU:
            # Lấy trung bình top các điểm cạnh rõ nhất tại mỗi chân thay vì lấy MAX tuyệt đối
            # Tránh trường hợp 1 điểm nhiễu cực sáng kéo lệch toàn bộ hệ góc
            max_per_angle = scores_reshaped.max(axis=2) # Lấy biên mạnh nhất trên dải bán kính R
            top_base_scores = np.mean(max_per_angle, axis=1) # Trung bình 7 góc quét lân cận
            
            return float(np.sum(top_base_scores))

        score_0  = calc_system_score_roi(rads_0)
        score_30 = calc_system_score_roi(rads_30)

        angle_offset = 0.0 if score_0 >= score_30 else 30.0

        return cx, cy, r_in, angle_offset, frame
    def process_image(self, img,cx=None, cy=None,r_input=None, angle_offset=0.0):
        """Giữ nguyên 100% Thuật toán gốc của bạn"""
        if img is None or cx is None or cy is None or r_input is None:
            return None, None, "Không có dữ liệu ảnh!", []
        # Ép kiểu dữ liệu an toàn
        cx, cy, r_input = int(cx), int(cy), int(r_input)
        r_input1=int(r_input*1.1)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        ear_max_height = 100 
        r_out = int(r_input*1.3)
        # Vẽ vòng Cyan và vòng Vàng
        cv2.circle(img, (cx, cy), r_input, (255, 255, 0), 2)       # Cyan
        #cv2.circle(img, (cx, cy), r_out, (0, 255, 255), 2)     # Vàng
        
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

        _, edge_map_bw = cv2.threshold(magnitude, self.config_magnitude.get(), 255, cv2.THRESH_BINARY)
        # Chỉ lấy cạnh nằm NGOÀI nền xanh PCB (tức là cạnh của Connector/Kim loại)
        # edge_map_bw = cv2.bitwise_and(edge_map_bw, cv2.bitwise_not(pcb_mask))
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
        valid_edge_points_min=int((r_input/24))
        distances = []
        ear_crop_images = []
        ear_data_draw = []
        minimum_point = int(0.021*r_input)
        minimum_point = max(minimum_point, 5)
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
                        if magnitude[py, px] > self.config_magnitude.get(): # Ngưỡng cạnh
                            gx, gy = grad_x[py, px], grad_y[py, px]
                            edge_angle = math.degrees(math.atan2(gy, gx))
                            angle_diff = abs(edge_angle - angle) % 180
                            if angle_diff > 90: angle_diff = 180 - angle_diff

                            # Lọc đúng cạnh tiếp tuyến
                            if angle_diff < 20:# chọn số ngẫu nhiên
                                valid_edge_points.append((px, py, r, cos_a, sin_a))

            # 2. PHÂN NHÓM THEO BÁN KÍNH VÀ CHỌN ĐOẠN CẠNH DÀI NHẤT (NẰM Ở NGOÀI)
            best_dist_for_ear = 0
            best_p_start, best_p_end = (cx, cy), (cx, cy)
            if len(valid_edge_points) >=minimum_point: # (12 độ * 2pi*rin*10%/360 độ)
                # Gom nhóm các điểm có bán kính r gần nhau (sai số 5px)
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
                # # ƯU TIÊN 1: Tìm đường thẳng có NHIỀU ĐIỂM NHẤT (Cạnh dài nhất)
                # # ƯU TIÊN 2: Chọn đường thẳng nằm XA TÂM NHẤT (d LỚN NHẤT)
                # best_cluster = max(clusters.values(), key=lambda group: ( 
                #     np.mean([(p[0] - cx_f) * cos_mid + (p[1] - cy_f) * sin_mid for p in group], len(group))
                # ))
                # 1. Lọc ra danh sách (list) các cụm thỏa mãn độ dài tối thiểu
                valid_clusters = [g for g in clusters.values() if len(g) >= minimum_point]
                # ƯU TIÊN 1: Chọn đường thẳng nằm XA TÂM NHẤT (d LỚN NHẤT)
                # ƯU TIÊN 2: Tìm đường thẳng có NHIỀU ĐIỂM NHẤT (Cạnh dài nhất)
                # 2. Kiểm tra nếu list không rỗng mới tìm cụm xa nhất
                if valid_clusters:
                    best_cluster = max(valid_clusters, key=lambda group: (  # Bỏ .values()
                        np.mean([(p[0] - cx_f) * cos_mid + (p[1] - cy_f) * sin_mid for p in group]), # Ưu tiên 1: Xa tâm nhất
                        len(group)                                                                 # Ưu tiên 2: Nhiều điểm nhất
                    ))
                else:
                    best_cluster = None  # Bỏ qua nếu không có cụm nào đủ độ dài
                if best_cluster:
                    # 1. Để lấy đúng 2 đầu mép tai của ĐƯỜNG THẲNG, ta sắp xếp theo thứ tự góc quét
                    best_cluster.sort(key=lambda item: item[3]) # Sắp xếp theo cos_a hoặc góc
                    
                    p_first = np.array([best_cluster[0][0], best_cluster[0][1]])
                    p_last = np.array([best_cluster[-1][0], best_cluster[-1][1]])
                    # 2. Trung điểm tọa độ thực tế (X, Y) của mép ngoài
                    mid_pt = (p_first + p_last) / 2.0
                    px_mid, py_mid = mid_pt[0], mid_pt[1]
                    # 3. Tính khoảng cách chính xác từ tâm (cx_f, cy_f) đến trung điểm này
                    r_found_exact = np.hypot(px_mid - cx_f, py_mid - cy_f)
                    # 4. Góc chuẩn của trung điểm
                    angle_mid = np.arctan2(py_mid - cy_f, px_mid - cx_f)
                    # 5. Khoảng cách tai chuẩn
                    best_dist_for_ear = r_found_exact - r_input

                    # 2. Điểm vuông góc chính giữa để đo khoảng cách tai
                    mid_idx = len(best_cluster) // 2
                    px, py, r_found, cos_a, sin_a = best_cluster[mid_idx]

                    #best_dist_for_ear = r_found - r_input
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
            if ((dist*1.575/r_input) < self.spec_mm.get()) or (dist < 0.6 * max_d):#val_px*1.575/avg_r_in
                color = (0, 0, 255)
                status = "NG"
                is_ng = True
            else:
                color = (0, 255, 0)
                status = "OK"

            ear_data.append((ear_crop_images[i], f"{dist}px", status, color))

        status_text = "NG" if is_ng else "OK"
        return img, edge_map_display, status_text, ear_data
    def get_fresh_frame(self):
        """Lấy frame mới nhất tuyệt đối, loại bỏ frame cũ nằm trong bộ đệm USB"""
        if self.cap is None or not self.cap.isOpened():
            return None
            
        # Xả bỏ (grab) 3-5 frame tồn đọng trong RAM cực nhanh mà không giải mã JPEG
        for _ in range(3):
            self.cap.grab()
            
        # Lấy frame thực sự ở thời điểm hiện tại
        ret, frame = self.cap.retrieve()
        if ret:
            return frame
        return None
    def capture_stable_frame(self):
        """
        Chụp 3 frame liên tiếp và lấy trung bình để triệt tiêu 100% nhiễu hạt CMOS & nhấp nháy đèn.
        Trả về 1 frame nét và cố định độ sáng chuẩn Vision công nghiệp.
        """
        frames = []
        for _ in range(3):
            f = self.get_fresh_frame()
            if f is not None:
                frames.append(f.astype(np.float32))
                
        if len(frames) == 3:
            # Lấy trung bình cộng 3 tấm
            avg_frame = np.mean(frames, axis=0).astype(np.uint8)
            return avg_frame
        elif len(frames) > 0:
            return frames[0].astype(np.uint8)
        return None
    def inspect_current_frame(self,event=None,test_frame=None, is_test=False):

        if self.cap is None or not self.cap.isOpened():
            messagebox.showwarning("Cảnh báo", "Camera chưa được kết nối!")
            return
        # 1. BẮT ĐẦU ĐO THỜI GIAN
        start_time = time.time()
        # Vô hiệu hóa nút bấm tạm thời để người dùng không bấm dồn dập
        self.btn_inspect.config(state="disabled", text="⏳ ĐANG KIỂM TRA CONECTOR...")
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
        if is_test and test_frame is not None:
            frame = test_frame.copy()
        else:
            # ret, frame = self.cap.read()
            frame=self.get_fresh_frame()
            if frame  is  None:
                return
        last_clean_frame = frame.copy()
        anhgoc_show = frame.copy()
        avg_cx, avg_cy, avg_r_in, avg_angle_offset, last_frame = self.detect_connector_pose(frame)
        # elapsed_time = (time.time() - start_time) * 1000 # Quy đổi ra miligiây (ms)  
        if avg_cx is None or last_frame is None:
            messagebox.showwarning("Cảnh báo", "Không tìm thấy Connector!")
            self.lbl_result.config(text="NOT CONECTOR", fg="red")
            # Mở lại nút bấm sau khi chụp xong
            self.btn_inspect.config(state="normal", text="🔍 KIỂM TRA CONNECTOR")
            return
        all_distances = [[] for _ in range(6)] # Mảng lưu 10 khoảng cách của 6 tai
        last_clean_frame = None
        status_list = []
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

        # Mở lại nút bấm sau khi chụp xong
        self.btn_inspect.config(state="normal", text="🔍 KIỂM TRA CONNECTOR")

        if last_clean_frame is None:
            return

        # 2. TÍNH GIÁ TRỊ TRUNG BÌNH CỦA 6 TAI (BỎ 1 MAX, 1 MIN ĐỂ TRÁNH NHIỄU)
        avg_distances = []
        for i in range(6):
            dists = all_distances[i]
            if len(dists) >= 2:
                dists.sort()
                valid_dists = dists[1:] # Chỉ bỏ 1 phần tử nhỏ nhất (dists[0])
                avg_d = sum(valid_dists) / len(valid_dists)
            elif len(dists) == 1:
                avg_d = dists[0]
            else:
                avg_d = 0.0
            final_px = math.ceil(avg_d)
            avg_distances.append(final_px)

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
            if ((avg_d*1.575/avg_r_in) < self.spec_mm.get()) or avg_d < 0.6 * max_avg_d:#val_px*1.575/avg_r_in
                color = (0, 0, 255) # Đỏ
                ear_status = "NG"
                is_ng = True
            else:
                color = (0, 255, 0) # Xanh
                ear_status = "OK"

            final_ear_data.append((crop_img, f"{avg_d}px", ear_status, color))
        # Cập nhật nhãn kết quả chung
        Goods_good = False
        Result_status = "NG"
        if is_ng:
            self.lbl_result.config(text="RESULT: NOT GOOD (NG) ", fg="red")
        else:
            self.lbl_result.config(text="RESULT: OK ", fg="green")
            Goods_good = True
            Result_status = "OK"

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
        val_um_list = []
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
                        # Thêm giá trị vừa tính vào danh sách
                        val_um_list.append(val_um)
                        if(val_um>0):
                            display_val = f"{val_um:.4f} mm"
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

        elapsed_time = (time.time() - start_time) * 1000 # Quy đổi ra miligiây (ms)      
        # Nếu hàm inspect_current_frame của bạn trả về chuỗi "OK" hoặc "NG"
        self.total_count_run +=1
        self.total_count.set(self.total_count.get() + 1)
        if Goods_good==True:
            self.ok_count.set(self.ok_count.get() + 1)
        else:
            self.ng_count.set(self.ng_count.get() + 1)

        self.total_execution_time += elapsed_time
        self.avg_execution_time = self.total_execution_time / self.total_count_run
        ok_rate = (self.ok_count.get() / self.total_count.get()) * 100


        # Cập nhật thông số lên cột bên phải
        self.lbl_total.config(text=f"Tổng số lần chạy: {self.total_count.get()}")
        self.lbl_ok_ng.config(text=f"OK: {self.ok_count.get()}  |  NG: {self.ng_count.get()}")
        self.lbl_rate.config(text=f"Tỉ lệ OK (Rate): {ok_rate:.1f}%")
        self.lbl_time.config(text=f"Thời gian TB: {self.avg_execution_time:.1f} ms")

        # 2. KẾT THÚC ĐO THỜI GIAN LẦN CHẠY NÀY
        orig_filename = os.path.join(IMAGE_DIR, f"number={self.total_count.get()}_{Result_status}goc.jpg")
        drawn_filename = os.path.join(IMAGE_DIR, f"number={self.total_count.get()}_{Result_status}ve.jpg")
        # 2. Tự động lưu 2 ảnh vào thư mục 'Hinh_Anh_Kiem_Tra'
        if anhgoc_show is not None:
            cv2.imwrite(orig_filename, anhgoc_show)
        else:
            print("[WARNING] Không thể lưu ảnh vì anhgoc_show bị None!")
        cv2.imwrite(drawn_filename, full_result_img)
        # Làm tròn 2 chữ số cho toàn bộ mảng trước khi ghép chuỗi
        safe_list = val_um_list + [0.0] * (6 - len(val_um_list))
        ears_formatted = [f"{v:.2f}" for v in safe_list]
        log_msg = (
            f"number={self.total_count.get()}, Result: {Result_status}, "
            f"Tai0: {ears_formatted[0]}| "
            f"Tai1: {ears_formatted[1]}| "
            f"Tai2: {ears_formatted[2]}| "
            f"Tai3: {ears_formatted[3]}| "
            f"Tai4: {ears_formatted[4]}| "
            f"Tai5: {ears_formatted[5]}. "
        )
        write_log(log_msg)                   
        return ear_status
    def __del__(self):
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()

if __name__ == "__main__":
    root = tk.Tk()
    app = PCBCheckerApp(root)
    root.mainloop()