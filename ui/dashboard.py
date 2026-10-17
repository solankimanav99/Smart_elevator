"""
Smart Elevator Dashboard - Professional Industrial UI
"""
import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk
import threading
import time
import random
from datetime import datetime

from detection.detector import ObjectDetector
from hardware.serial_reader import SerialReader
from logic.safety import get_status
from db.database import ElevatorDB
from utils.config import *

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    MATPLOTLIB_OK = True
except:
    MATPLOTLIB_OK = False


class ElevatorDashboard:
    def __init__(self, root):
        self.root = root
        self.db = ElevatorDB()
        self.detector = ObjectDetector()
        self.serial_reader = SerialReader(
            callback=self._on_serial_weight,
            log_callback=self._add_log
        )

        # State
        self.current_weight = 0.0
        self.load_limit = DEFAULT_LOAD_LIMIT
        self.mode = "simulation"  # simulation | hardware | demo
        self.camera_active = False
        self.cap = None
        self.weight_history = []
        self.hw_weight = 0.0  # Latest hardware weight
        self.demo_running = False

        # Detection results
        self.det_object_count = 0
        self.det_objects_str = ""
        self.det_human = False

        self._build_ui()
        self._update_loop()

    # ── UI BUILDING ────────────────────────────────────────────────
    def _build_ui(self):
        BG = "#1a1a2e"
        CARD = "#16213e"
        ACCENT = "#0f3460"
        TEXT = "#e0e0e0"
        BRIGHT = "#ffffff"
        
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("Dark.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Card.TLabel", background=CARD, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=BG, foreground=BRIGHT, font=("Segoe UI", 16, "bold"))
        style.configure("Big.TLabel", background=CARD, foreground=BRIGHT, font=("Segoe UI", 22, "bold"))
        style.configure("Sub.TLabel", background=CARD, foreground="#aaaaaa", font=("Segoe UI", 9))
        style.configure("Metric.TLabel", background=CARD, foreground="#00e5ff", font=("Consolas", 14, "bold"))
        style.configure("MetricLabel.TLabel", background=CARD, foreground="#888888", font=("Segoe UI", 9))
        style.configure("Log.TLabel", background=CARD, foreground="#66bb6a", font=("Consolas", 8))
        style.configure("Dark.TButton", font=("Segoe UI", 9, "bold"))

        # Header
        header = ttk.Frame(self.root, style="Dark.TFrame")
        header.pack(fill="x", padx=10, pady=(8, 4))
        ttk.Label(header, text="⬡ SMART ELEVATOR OVERLOAD DETECTION SYSTEM",
                  style="Title.TLabel").pack(side="left")
        self.lbl_clock = ttk.Label(header, text="", style="Dark.TLabel")
        self.lbl_clock.pack(side="right")
        self._tick_clock()

        # Main container
        main = ttk.Frame(self.root, style="Dark.TFrame")
        main.pack(fill="both", expand=True, padx=10, pady=4)

        # LEFT COLUMN — Camera + Detection Info
        left = ttk.Frame(main, style="Dark.TFrame", width=480)
        left.pack(side="left", fill="both", expand=False, padx=(0, 6))
        left.pack_propagate(False)

        self._build_camera_panel(left, CARD)
        self._build_detection_panel(left, CARD)

        # CENTER COLUMN — Status + Metrics + Graph
        center = ttk.Frame(main, style="Dark.TFrame")
        center.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self._build_status_card(center, CARD)
        self._build_metrics_panel(center, CARD)
        self._build_graph_panel(center, CARD)

        # RIGHT COLUMN — Controls + Log
        right = ttk.Frame(main, style="Dark.TFrame", width=300)
        right.pack(side="left", fill="both", expand=False)
        right.pack_propagate(False)

        self._build_control_panel(right, CARD, ACCENT)
        self._build_log_panel(right, CARD)

    def _build_camera_panel(self, parent, bg):
        frame = ttk.LabelFrame(parent, text="  📷 CAMERA FEED  ", style="Card.TFrame")
        frame.pack(fill="x", pady=(0, 4))
        self.camera_canvas = tk.Canvas(frame, width=460, height=280, bg="#000000",
                                        highlightthickness=0)
        self.camera_canvas.pack(padx=6, pady=6)
        self.camera_canvas.create_text(230, 140, text="Camera Off",
                                        fill="#555555", font=("Segoe UI", 14))

    def _build_detection_panel(self, parent, bg):
        frame = ttk.LabelFrame(parent, text="  🔍 DETECTED OBJECTS  ", style="Card.TFrame")
        frame.pack(fill="both", expand=True, pady=(0, 4))
        
        row1 = ttk.Frame(frame, style="Card.TFrame")
        row1.pack(fill="x", padx=8, pady=(6, 2))
        ttk.Label(row1, text="Human Detected:", style="MetricLabel.TLabel").pack(side="left")
        self.lbl_human = ttk.Label(row1, text="No", style="Card.TLabel")
        self.lbl_human.pack(side="right")

        row2 = ttk.Frame(frame, style="Card.TFrame")
        row2.pack(fill="x", padx=8, pady=2)
        ttk.Label(row2, text="Total Objects:", style="MetricLabel.TLabel").pack(side="left")
        self.lbl_obj_count = ttk.Label(row2, text="0", style="Card.TLabel")
        self.lbl_obj_count.pack(side="right")

        self.det_text = tk.Text(frame, height=5, bg="#0d1b2a", fg="#00e5ff",
                                font=("Consolas", 9), relief="flat", state="disabled",
                                wrap="word")
        self.det_text.pack(fill="both", expand=True, padx=8, pady=(2, 6))

    def _build_status_card(self, parent, bg):
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.pack(fill="x", pady=(0, 4), ipady=12)
        
        ttk.Label(frame, text="SYSTEM STATUS", style="MetricLabel.TLabel").pack(pady=(8, 0))
        self.lbl_status = ttk.Label(frame, text="SAFE", style="Big.TLabel")
        self.lbl_status.pack()
        self.lbl_status_sub = ttk.Label(frame, text="Within safe load capacity", style="Sub.TLabel")
        self.lbl_status_sub.pack()
        
        # Progress bar for weight ratio
        self.progress_var = tk.DoubleVar(value=0)
        self.progress = ttk.Progressbar(frame, variable=self.progress_var,
                                         maximum=100, length=300, mode="determinate")
        self.progress.pack(pady=(8, 4))
        self.lbl_pct = ttk.Label(frame, text="0%", style="Card.TLabel")
        self.lbl_pct.pack()

    def _build_metrics_panel(self, parent, bg):
        frame = ttk.LabelFrame(parent, text="  📊 LIVE METRICS  ", style="Card.TFrame")
        frame.pack(fill="x", pady=(0, 4))

        metrics_grid = ttk.Frame(frame, style="Card.TFrame")
        metrics_grid.pack(fill="x", padx=10, pady=8)

        # Row 0 — Weight
        ttk.Label(metrics_grid, text="Current Weight", style="MetricLabel.TLabel").grid(
            row=0, column=0, sticky="w", pady=3)
        self.lbl_weight = ttk.Label(metrics_grid, text="0.00 kg", style="Metric.TLabel")
        self.lbl_weight.grid(row=0, column=1, sticky="e", pady=3, padx=(20, 0))

        # Row 1 — Limit
        ttk.Label(metrics_grid, text="Load Limit", style="MetricLabel.TLabel").grid(
            row=1, column=0, sticky="w", pady=3)
        self.lbl_limit = ttk.Label(metrics_grid, text=f"{DEFAULT_LOAD_LIMIT:.0f} kg",
                                    style="Metric.TLabel")
        self.lbl_limit.grid(row=1, column=1, sticky="e", pady=3, padx=(20, 0))

        # Row 2 — Mode
        ttk.Label(metrics_grid, text="Data Source", style="MetricLabel.TLabel").grid(
            row=2, column=0, sticky="w", pady=3)
        self.lbl_source = ttk.Label(metrics_grid, text="Simulation", style="Metric.TLabel")
        self.lbl_source.grid(row=2, column=1, sticky="e", pady=3, padx=(20, 0))

        # Row 3 — COM Port
        ttk.Label(metrics_grid, text="COM Port", style="MetricLabel.TLabel").grid(
            row=3, column=0, sticky="w", pady=3)
        self.lbl_com = ttk.Label(metrics_grid, text="—", style="Metric.TLabel")
        self.lbl_com.grid(row=3, column=1, sticky="e", pady=3, padx=(20, 0))

        # Row 4 — HW Status
        ttk.Label(metrics_grid, text="Hardware Status", style="MetricLabel.TLabel").grid(
            row=4, column=0, sticky="w", pady=3)
        self.lbl_hw_status = ttk.Label(metrics_grid, text="Disconnected",
                                        style="Metric.TLabel")
        self.lbl_hw_status.grid(row=4, column=1, sticky="e", pady=3, padx=(20, 0))

        metrics_grid.columnconfigure(1, weight=1)

    def _build_graph_panel(self, parent, bg):
        frame = ttk.LabelFrame(parent, text="  📈 LIVE WEIGHT TREND  ", style="Card.TFrame")
        frame.pack(fill="both", expand=True, pady=(0, 4))
        
        if MATPLOTLIB_OK:
            self.fig = Figure(figsize=(4, 2.2), dpi=90, facecolor="#16213e")
            self.ax = self.fig.add_subplot(111)
            self.ax.set_facecolor("#0d1b2a")
            self.ax.tick_params(colors="#888888", labelsize=7)
            self.ax.spines["bottom"].set_color("#333")
            self.ax.spines["left"].set_color("#333")
            self.ax.spines["top"].set_visible(False)
            self.ax.spines["right"].set_visible(False)
            self.ax.set_ylabel("Weight (kg)", color="#888888", fontsize=8)
            self.graph_canvas = FigureCanvasTkAgg(self.fig, frame)
            self.graph_canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)
        else:
            ttk.Label(frame, text="matplotlib not installed", style="Card.TLabel").pack(pady=20)

    def _build_control_panel(self, parent, bg, accent):
        frame = ttk.LabelFrame(parent, text="  ⚙ CONTROL PANEL  ", style="Card.TFrame")
        frame.pack(fill="x", pady=(0, 4))
        inner = ttk.Frame(frame, style="Card.TFrame")
        inner.pack(fill="x", padx=8, pady=6)

        # Mode selection
        ttk.Label(inner, text="Operating Mode", style="MetricLabel.TLabel").pack(anchor="w")
        self.mode_var = tk.StringVar(value="simulation")
        mode_frame = ttk.Frame(inner, style="Card.TFrame")
        mode_frame.pack(fill="x", pady=(2, 8))
        for val, txt in [("simulation", "Simulation"), ("hardware", "Hardware"), ("demo", "Demo")]:
            ttk.Radiobutton(mode_frame, text=txt, variable=self.mode_var, value=val,
                            command=self._on_mode_change).pack(side="left", padx=4)

        # Weight slider (simulation)
        ttk.Label(inner, text="Simulated Weight (kg)", style="MetricLabel.TLabel").pack(anchor="w")
        self.weight_slider = tk.Scale(inner, from_=0, to=800, orient="horizontal",
                                       bg="#16213e", fg="#00e5ff", troughcolor="#0d1b2a",
                                       highlightthickness=0, font=("Consolas", 9),
                                       command=self._on_slider)
        self.weight_slider.pack(fill="x", pady=(0, 6))

        # Load limit
        ttk.Label(inner, text="Load Limit (kg)", style="MetricLabel.TLabel").pack(anchor="w")
        self.limit_slider = tk.Scale(inner, from_=50, to=1000, orient="horizontal",
                                      bg="#16213e", fg="#ffaa00", troughcolor="#0d1b2a",
                                      highlightthickness=0, font=("Consolas", 9),
                                      command=self._on_limit_change)
        self.limit_slider.set(int(DEFAULT_LOAD_LIMIT))
        self.limit_slider.pack(fill="x", pady=(0, 8))

        # Camera button
        sep1 = ttk.Separator(inner)
        sep1.pack(fill="x", pady=4)
        ttk.Label(inner, text="Camera", style="MetricLabel.TLabel").pack(anchor="w")
        btn_row1 = ttk.Frame(inner, style="Card.TFrame")
        btn_row1.pack(fill="x", pady=2)
        self.btn_cam = tk.Button(btn_row1, text="▶ Start Camera", bg="#0f3460", fg="white",
                                  font=("Segoe UI", 9, "bold"), relief="flat",
                                  command=self._toggle_camera)
        self.btn_cam.pack(fill="x")

        # Hardware buttons
        ttk.Label(inner, text="Hardware", style="MetricLabel.TLabel").pack(anchor="w", pady=(6, 0))
        hw_row = ttk.Frame(inner, style="Card.TFrame")
        hw_row.pack(fill="x", pady=2)

        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(hw_row, textvariable=self.port_var, width=10, state="readonly")
        self.port_combo.pack(side="left", padx=(0, 4))
        
        tk.Button(hw_row, text="🔄", bg="#0f3460", fg="white", relief="flat",
                  command=self._refresh_ports, width=3).pack(side="left", padx=(0, 4))
        
        self.btn_hw = tk.Button(hw_row, text="Connect", bg="#2e7d32", fg="white",
                                 font=("Segoe UI", 9, "bold"), relief="flat",
                                 command=self._toggle_hardware)
        self.btn_hw.pack(side="left", fill="x", expand=True)

        # Database buttons
        ttk.Label(inner, text="Database", style="MetricLabel.TLabel").pack(anchor="w", pady=(6, 0))
        db_row = ttk.Frame(inner, style="Card.TFrame")
        db_row.pack(fill="x", pady=2)
        tk.Button(db_row, text="💾 Save", bg="#1565c0", fg="white",
                  font=("Segoe UI", 9, "bold"), relief="flat",
                  command=self._save_record).pack(side="left", fill="x", expand=True, padx=(0, 2))
        tk.Button(db_row, text="📋 View", bg="#0f3460", fg="white",
                  font=("Segoe UI", 9, "bold"), relief="flat",
                  command=self._view_records).pack(side="left", fill="x", expand=True, padx=(0, 2))
        tk.Button(db_row, text="🗑 Reset", bg="#c62828", fg="white",
                  font=("Segoe UI", 9, "bold"), relief="flat",
                  command=self._reset_all).pack(side="left", fill="x", expand=True)

        self._refresh_ports()

    def _build_log_panel(self, parent, bg):
        frame = ttk.LabelFrame(parent, text="  📝 EVENT LOG  ", style="Card.TFrame")
        frame.pack(fill="both", expand=True, pady=(0, 4))
        self.log_text = tk.Text(frame, height=8, bg="#0d1b2a", fg="#66bb6a",
                                 font=("Consolas", 8), relief="flat", state="disabled",
                                 wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)
        self._add_log("System initialized")

    # ── CALLBACKS & LOGIC ──────────────────────────────────────────
    def _tick_clock(self):
        self.lbl_clock.config(text=datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))
        self.root.after(1000, self._tick_clock)

    def _on_slider(self, val):
        if self.mode == "simulation":
            self.current_weight = float(val)

    def _on_limit_change(self, val):
        self.load_limit = float(val)
        self.lbl_limit.config(text=f"{self.load_limit:.0f} kg")

    def _on_mode_change(self):
        new_mode = self.mode_var.get()
        self.mode = new_mode
        self._add_log(f"Mode changed to {new_mode.upper()}")

        if new_mode == "hardware":
            self.lbl_source.config(text="Hardware")
            self.weight_slider.config(state="disabled")
        elif new_mode == "simulation":
            self.lbl_source.config(text="Simulation")
            self.weight_slider.config(state="normal")
            self.demo_running = False
        elif new_mode == "demo":
            self.lbl_source.config(text="Demo")
            self.weight_slider.config(state="disabled")
            self.demo_running = True

    def _on_serial_weight(self, weight):
        """Called from serial thread with new weight."""
        self.hw_weight = weight

    def _toggle_camera(self):
        if self.camera_active:
            self.camera_active = False
            if self.cap:
                self.cap.release()
                self.cap = None
            self.btn_cam.config(text="▶ Start Camera")
            self.camera_canvas.delete("all")
            self.camera_canvas.create_text(230, 140, text="Camera Off",
                                            fill="#555555", font=("Segoe UI", 14))
            self._add_log("Camera stopped")
        else:
            self.cap = cv2.VideoCapture(0)
            if self.cap.isOpened():
                self.camera_active = True
                self.btn_cam.config(text="⏹ Stop Camera")
                self._add_log("Camera started")
                self._camera_loop()
            else:
                self._add_log("Camera not found")
                self.cap = None

    def _camera_loop(self):
        if not self.camera_active or not self.cap:
            return
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.resize(frame, (460, 280))
            frame, results = self.detector.detect(frame)

            self.det_object_count = results["object_count"]
            self.det_objects_str = results["detected_objects"]
            self.det_human = results["human_detected"]

            # Update detection panel
            self.lbl_human.config(text="Yes ✓" if self.det_human else "No",
                                   foreground="#00ff00" if self.det_human else "#ff5555")
            self.lbl_obj_count.config(text=str(self.det_object_count))
            
            self.det_text.config(state="normal")
            self.det_text.delete("1.0", "end")
            if results["details"]:
                for d in results["details"]:
                    self.det_text.insert("end", f"  • {d['name']} × {d['count']}\n")
            else:
                self.det_text.insert("end", "  No objects detected")
            self.det_text.config(state="disabled")

            # Display frame
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            imgtk = ImageTk.PhotoImage(image=img)
            self.camera_canvas.create_image(0, 0, anchor="nw", image=imgtk)
            self.camera_canvas._img = imgtk

        self.root.after(33, self._camera_loop)

    def _toggle_hardware(self):
        if self.serial_reader.connected:
            self.serial_reader.disconnect()
            self.btn_hw.config(text="Connect", bg="#2e7d32")
            self.lbl_hw_status.config(text="Disconnected", foreground="#ff5555")
            self.lbl_com.config(text="—")
            if self.mode == "hardware":
                self.mode = "simulation"
                self.mode_var.set("simulation")
                self.lbl_source.config(text="Simulation")
                self.weight_slider.config(state="normal")
                self._add_log("Fallback to Simulation mode")
        else:
            port = self.port_var.get()
            if not port:
                self._add_log("No port selected")
                return
            if self.serial_reader.connect(port, DEFAULT_BAUD):
                self.btn_hw.config(text="Disconnect", bg="#c62828")
                self.lbl_hw_status.config(text="Connected", foreground="#00ff00")
                self.lbl_com.config(text=port)
            else:
                self.lbl_hw_status.config(text="Error", foreground="#ff5555")

    def _refresh_ports(self):
        ports = self.serial_reader.get_ports()
        self.port_combo["values"] = ports
        if ports:
            self.port_combo.current(0)
        self._add_log(f"Ports found: {ports if ports else 'None'}")

    def _save_record(self):
        status, _, _ = get_status(self.current_weight, self.load_limit, self.det_human)
        source = self.mode.capitalize()
        ts = self.db.save_record(
            self.current_weight, self.load_limit,
            self.det_object_count, self.det_objects_str,
            self.det_human, status, status, source
        )
        self._add_log(f"Record saved at {ts}")

    def _view_records(self):
        records = self.db.get_records(50)
        win = tk.Toplevel(self.root)
        win.title("📋 Elevator Records")
        win.geometry("650x450")
        win.configure(bg="#1a1a2e")

        cols = ("Time", "Weight (kg)", "Status", "Source")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=18)
        
        style = ttk.Style()
        style.configure("Treeview", background="#0d1b2a", foreground="#e0e0e0",
                         fieldbackground="#0d1b2a", font=("Consolas", 9), rowheight=24)
        style.configure("Treeview.Heading", background="#16213e", foreground="#00e5ff",
                         font=("Segoe UI", 10, "bold"))

        tree.heading("Time", text="Time")
        tree.heading("Weight (kg)", text="Weight (kg)")
        tree.heading("Status", text="Status")
        tree.heading("Source", text="Source")
        
        tree.column("Time", width=170, anchor="center")
        tree.column("Weight (kg)", width=120, anchor="center")
        tree.column("Status", width=120, anchor="center")
        tree.column("Source", width=120, anchor="center")

        scrollbar = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        for i, r in enumerate(records):
            tag = "latest" if i == 0 else ""
            tree.insert("", "end", values=r, tags=(tag,))
        
        tree.tag_configure("latest", background="#1b3a5c")

        tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        scrollbar.pack(side="right", fill="y", pady=8, padx=(0, 8))

        count_label = tk.Label(win, text=f"Total records: {self.db.get_record_count()}",
                                bg="#1a1a2e", fg="#888888", font=("Segoe UI", 9))
        count_label.pack(side="bottom", pady=4)

    def _reset_all(self):
        if messagebox.askyesno("Confirm Reset", "Delete ALL records and reset dashboard?"):
            self.db.clear_all()
            self.weight_history.clear()
            self.current_weight = 0.0
            self.weight_slider.set(0)
            self.det_object_count = 0
            self.det_objects_str = ""
            self.det_human = False
            self._update_graph()
            self._add_log("All data reset")

    def _add_log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        try:
            self.log_text.config(state="normal")
            self.log_text.insert("end", f"[{ts}] {msg}\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        except:
            pass

    # ── MAIN UPDATE LOOP ───────────────────────────────────────────
    def _update_loop(self):
        # Determine weight based on mode
        if self.mode == "hardware":
            if self.serial_reader.connected:
                self.current_weight = self.hw_weight
            else:
                # Auto-fallback
                self.mode = "simulation"
                self.mode_var.set("simulation")
                self.lbl_source.config(text="Simulation (fallback)")
                self.weight_slider.config(state="normal")
                self._add_log("Hardware lost — fallback to simulation")
        elif self.mode == "demo":
            self.current_weight = random.uniform(100, 600)
        # simulation mode uses slider value via _on_slider

        # Update weight display
        self.lbl_weight.config(text=f"{self.current_weight:.2f} kg")

        # Status
        status, subtitle, color = get_status(self.current_weight, self.load_limit, self.det_human)
        self.lbl_status.config(text=status, foreground=color)
        self.lbl_status_sub.config(text=subtitle)

        # Progress
        pct = min((self.current_weight / self.load_limit) * 100, 100) if self.load_limit > 0 else 0
        self.progress_var.set(pct)
        self.lbl_pct.config(text=f"{pct:.1f}%")

        # Overload alert to hardware
        if status in ("OVERLOAD", "HIGH RISK") and self.serial_reader.connected:
            self.serial_reader.send("OVERLOAD")

        # Graph
        self.weight_history.append(self.current_weight)
        if len(self.weight_history) > GRAPH_HISTORY:
            self.weight_history = self.weight_history[-GRAPH_HISTORY:]
        self._update_graph()

        self.root.after(UPDATE_INTERVAL_MS, self._update_loop)

    def _update_graph(self):
        if not MATPLOTLIB_OK:
            return
        self.ax.clear()
        self.ax.set_facecolor("#0d1b2a")
        self.ax.tick_params(colors="#888888", labelsize=7)
        self.ax.spines["bottom"].set_color("#333")
        self.ax.spines["left"].set_color("#333")
        self.ax.spines["top"].set_visible(False)
        self.ax.spines["right"].set_visible(False)
        self.ax.set_ylabel("kg", color="#888888", fontsize=8)

        if self.weight_history:
            x = list(range(len(self.weight_history)))
            self.ax.plot(x, self.weight_history, color="#00e5ff", linewidth=2.5, zorder=3)
            # Highlight latest point
            self.ax.scatter([x[-1]], [self.weight_history[-1]], color="#00ffaa",
                            s=60, zorder=4, edgecolors="white", linewidths=1.5)
            # Threshold line
            self.ax.axhline(y=self.load_limit, color="#ff4444", linestyle="--",
                            linewidth=1.2, label=f"Limit: {self.load_limit:.0f}")
            self.ax.legend(loc="upper left", fontsize=7, facecolor="#16213e",
                           edgecolor="#333", labelcolor="#cccccc")

        self.fig.tight_layout(pad=1)
        self.graph_canvas.draw_idle()

    def cleanup(self):
        self.camera_active = False
        self.demo_running = False
        if self.cap:
            self.cap.release()
        self.serial_reader.disconnect()
        self.db.close()
