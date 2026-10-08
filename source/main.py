import glob
import itertools
import os
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from core.data_service import SFTPService, FTPService
import numpy as np
import pandas as pd
from core.logger import logger as log
from core.load_config import load_yaml
from core.parser import ParserLog
import ctypes
import sys
from core import report_tool
from core.toolkits import ClientView

class RFAnalyzerGUI:
    def __init__(self, root):
        self.config = load_yaml()
        
        self.version = self.config["version"]
        self.root = root
        self.root.title(f"RF Support Tool - {self.version}")
        self.root.geometry(self.config["size"])
        
        # Variables
        self.source_path = tk.StringVar(value="")
        self.output_path = tk.StringVar(value="") 
        
        # --- CẤU HÌNH FTP ---
        self.ftp_host = tk.StringVar(value=self.config["ftp_host"])
        self.ftp_user = tk.StringVar(value=self.config["ftp_user"])
        self.ftp_pass = tk.StringVar(value=self.config["ftp_password"])
        self.ftp_port = tk.StringVar(value=self.config["ftp_port"])
        self.ftp_dir = tk.StringVar(value=self.config["ftp_remote"])
        
        self.item_search_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="GRR")
        self.mode_export_val = tk.StringVar(value="loop")
        self.target_str = tk.StringVar(value="17.0")
        self.delta_str = tk.StringVar(value="0.5")
        
        # 🟢 BIẾN CHỌN CHẾ ĐỘ LỌC (NORMAL / ADVANCE)
        self.scan_mode_var = tk.StringVar(value="normal")  # 'normal' hoặc 'advance'
        self.station_id_var = tk.StringVar(value="ALL")
        self.sample_count_var = tk.StringVar(value="5")
        
        # Tập hợp lưu các item đã được tick chọn
        self.selected_item_names = set()
        
        self.df_summary = None
        self.df_checked_result = None
        self.last_mode_msg = ""
        self.dut_sort_desc = True
        self._setup_style()
        self._setup_ui()
        
        # --- ĐĂNG KÝ PHÍM TẮT ---
        self.root.bind('<Return>', lambda event: self._execute_scan())
        self.dut_tree.bind('<Control-a>', lambda e: self._select_all(self.dut_tree))
        self.dut_tree.bind('<Control-A>', lambda e: self._select_all(self.dut_tree))
        self.item_tree.bind('<Control-a>', lambda e: self._select_all(self.item_tree))
        self.item_tree.bind('<Control-A>', lambda e: self._select_all(self.item_tree))
        self.item_tree.bind("<<TreeviewSelect>>", self._auto_fill_target)
        
        # Sự kiện Click vào Checkbox trên bảng Item
        self.item_tree.bind("<Button-1>", self._on_item_tree_click)
        
        self.parser = ParserLog()

    def _select_all(self, tree):
        tree.selection_set(tree.get_children())
        return "break"

    def _setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        style.configure("Treeview", 
                        rowheight=28, 
                        font=("Arial", 9),
                        background="white",
                        fieldbackground="white",
                        foreground="black",
                        relief="solid")
        
        style.layout("Treeview", [('Treeview.treearea', {'sticky': 'nswe'})])
        
        style.configure("Treeview.Heading", 
                        font=("Arial", 9, "bold"), 
                        background="#0ddff2",
                        relief="flat")
        
        style.map("Treeview", 
                  background=[('selected', '#0078d7')], 
                  foreground=[('selected', 'white')])

    def _setup_ui(self):
        # --- 1. TOP PANEL ---
        top_frame = tk.Frame(self.root, bg="#f8f9fa", padx=10, pady=8, bd=1, relief="ridge")
        top_frame.pack(side="top", fill="x")
        
        row = tk.Frame(top_frame, bg="#f8f9fa")
        row.pack(fill="x", pady=2)
        tk.Label(row, text="Input Dir", bg="#f8f9fa", font=("Arial", 9, "bold"), width=12, anchor="w").pack(side="left")
        tk.Entry(row, textvariable=self.source_path, width=100, background="#e6e5e0").pack(side="left", padx=5)
        self.source_path.trace_add("write", self._load_data_logic)
        tk.Button(row, text="...", command=lambda v=self.source_path: self._browse_dir(v), bg="#6c757d", fg="white", width=5).pack(side="left")
        
        row = tk.Frame(top_frame, bg="#f8f9fa")
        row.pack(fill="x", pady=2)
        tk.Label(row, text="Output Dir", bg="#f8f9fa", font=("Arial", 9, "bold"), width=12, anchor="w").pack(side="left")
        tk.Entry(row, textvariable=self.output_path, width=100, background="#e6e5e0").pack(side="left", padx=5)
        tk.Button(row, text="...", command=lambda v=self.output_path: self._browse_dir(v), bg="#6c757d", fg="white", width=5).pack(side="left")

        # Dòng 3: FTP Config
        ftp_row = tk.Frame(top_frame, bg="#f8f9fa")
        ftp_row.pack(fill="x", pady=4)
        tk.Label(ftp_row, text="Host:", bg="#f8f9fa", font=("Arial", 9, "bold"), width=12, anchor="w").pack(side="left")
        tk.Entry(ftp_row, textvariable=self.ftp_host, font=("Arial", 9), background="#e6e5e0", width=20).pack(side="left", padx=5)
        tk.Label(ftp_row, text="User:", bg="#f8f9fa", font=("Arial", 9, "bold")).pack(side="left", padx=2)
        tk.Entry(ftp_row, textvariable=self.ftp_user, width=15, font=("Arial", 9), background="#e6e5e0").pack(side="left", padx=5)
        tk.Label(ftp_row, text="Password:", bg="#f8f9fa", font=("Arial", 9, "bold")).pack(side="left", padx=2)
        tk.Entry(ftp_row, textvariable=self.ftp_pass, show="*", width=15, font=("Arial", 9), background="#e6e5e0").pack(side="left", padx=5)
        tk.Label(ftp_row, text="Port:", bg="#f8f9fa", font=("Arial", 9, "bold")).pack(side="left", padx=2)
        tk.Entry(ftp_row, textvariable=self.ftp_port, width=5, font=("Arial", 9), background="#e6e5e0").pack(side="left", padx=5)
        tk.Label(ftp_row, text="Remote:", bg="#f8f9fa", font=("Arial", 9, "bold")).pack(side="left", padx=2)
        tk.Entry(ftp_row, textvariable=self.ftp_dir, width=40, font=("Arial", 9), background="#e6e5e0").pack(side="left", padx=5)

        # Dòng 4: Tools & Modes
        tool_row = tk.Frame(top_frame, bg="#f8f9fa")
        tool_row.pack(fill="x", pady=4)
        self.mode_combo = ttk.Combobox(tool_row, textvariable=self.mode_var, values=("DEBUG", "AUDIT", "GRR", "CALIBRATION", "PRODUCTION"), width=13, state="readonly")
        self.mode_combo.pack(side="left", padx=5)
        self.mode_combo.bind("<<ComboboxSelected>>", self._load_data_logic)
        tk.Button(tool_row, text="LOAD DATA", command=self._load_data_logic, bg="#0078d7", fg="white", font=("Arial", 9, "bold"), width=13).pack(side="left", padx=10)
        
        modes = [("Loop", "loop"), ("Correlation", "correl"), ("GRR", "grr"), ("Other", "station")]
        for text, mode_val in modes:
            ttk.Radiobutton(tool_row, text=text, variable=self.mode_export_val, value=mode_val, width=10).pack(side="left", padx=3)
         
        self.export_btn = tk.Button(tool_row, text="Export Report", command=self.handle_export, bg="#00d700", fg="black", font=("Arial", 9, "bold"), width=14)
        self.export_btn.pack(side="left", padx=5)
        
        tk.Button(tool_row, text="Upload ALL", command=self._upload_all_to_ftp, bg="#6f42c1", fg="white", font=("Arial", 9, "bold"), width=13).pack(side="right", padx=3)
        tk.Button(tool_row, text="Upload Sorted", command=self._upload_to_ftp, bg="#17a2b8", fg="white", font=("Arial", 9, "bold"), width=13).pack(side="right", padx=3)
        tk.Button(tool_row, text="Open Client", command=self.open_client_view, bg="#c4d808", fg="black", font=("Arial", 9, "bold"), width=13).pack(side="right", padx=3)
        
        # --- 2. MAIN CONTENT ---
        paned = tk.PanedWindow(self.root, orient="horizontal", bg="#cccccc", sashwidth=4)
        paned.pack(expand=True, fill="both", padx=2, pady=2)

        # DUT List (Cột trái)
        left_frame = tk.Frame(paned, bg="white", padx=5, pady=5)
        paned.add(left_frame, width=250)
        self.dut_tree = ttk.Treeview(left_frame, columns=("ID", "P"), show="headings", selectmode="extended")
        self.dut_tree.heading("ID", text="DUT ID")
        self.dut_tree.heading("P", text="PASS",command=lambda: self._sort_dut_tree("P"),anchor="w")
        self.dut_tree.column("ID", width=160); self.dut_tree.column("P", width=40, anchor="center")
        '''scrollbar = ttk.Scrollbar(self.dut_tree, orient="vertical", command=self.dut_tree.yview)
        self.dut_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")'''
        self.dut_tree.pack(expand=True, fill="both")
        
        self.dut_tree.bind("<<TreeviewSelect>>", self._on_dut_selection_change)
        
        # Item Table (Cột phải)
        right_frame = tk.Frame(paned, bg="#D0EDF3", padx=10, pady=2)
        paned.add(right_frame, width=1350)

        # Thanh tìm kiếm + Nút Select All / Clear All
        search_bar_frame = tk.Frame(right_frame, bg="#D0EDF3")
        search_bar_frame.pack(fill="x", pady=5)

        tk.Button(search_bar_frame, text="✔ Select All", command=self._select_all_items_cb, bg="#17a2b8", fg="white", font=("Arial", 8, "bold")).pack(side="left", padx=2)
        tk.Button(search_bar_frame, text="   Clear All", command=self._clear_all_items_cb, bg="#6c757d", fg="white", font=("Arial", 8, "bold")).pack(side="left", padx=2)
        tk.Entry(search_bar_frame, textvariable=self.item_search_var, bg="#e1f5fe").pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.item_search_var.trace_add("write", self._refresh_item_table)

        # Bảng Item chính - Có cột Checkbox 'sel'
        cols = ("sel", "Name", "Max", "Min", "Mean", "Gap", "Stdev")
        self.item_tree = ttk.Treeview(right_frame, columns=cols, show="headings", selectmode="extended")
        
        self.item_tree.heading("sel", text="✔", anchor="w")
        self.item_tree.heading("Name", text="Measurement Name", anchor="w")
        self.item_tree.column("sel", width=10, anchor="w")
        self.item_tree.column("Name", width=950, anchor="w")
        scrollbar_item = ttk.Scrollbar(self.item_tree, orient="vertical", command=self.item_tree.yview)
        self.item_tree.configure(yscrollcommand=scrollbar_item.set)
        scrollbar_item.pack(side="right", fill="y")

        for col in cols[2:]:
            self.item_tree.heading(col, text=col, anchor="center")
            self.item_tree.column(col, width=30, anchor="center")
            
        self.item_tree.pack(expand=True, fill="both")

        # --- 3. BOTTOM PANEL (CONSOLE + KHU VỰC SCAN CONTROL CÂN ĐỐI) ---
        bottom_container = tk.Frame(right_frame, bg="#D0EDF3")
        bottom_container.pack(fill="x", pady=(5, 0))

        # 🟢 KHU VỰC SCAN CONTROL (MỞ RỘNG VÀ ĐƯA SCAN/COPY DATA LÊN ĐẦU)
        filter_box = tk.LabelFrame(bottom_container, text="Scanning Control Panel", bg="#D0EDF3", fg="#003366", font=("Arial", 9, "bold"), padx=12, pady=6)
        filter_box.pack(side="left", fill="both", padx=(0, 10))

        # DÒNG 1: CHỌN CHẾ ĐỘ SCAN (NORMAL vs ADVANCE)
        mode_radio_row = tk.Frame(filter_box, bg="#D0EDF3")
        mode_radio_row.pack(fill="x", pady=(2, 4))
        tk.Label(mode_radio_row, text="Mode:", font=("Arial", 9, "bold"), bg="#D0EDF3", width=10, anchor="w").pack(side="left")
        ttk.Radiobutton(mode_radio_row, text="Normal",variable=self.scan_mode_var, value="normal").pack(side="left", padx=5)
        ttk.Radiobutton(mode_radio_row, text="Advance", variable=self.scan_mode_var, value="advance").pack(side="left", padx=5)

        # DÒNG 2: NÚT SCAN VÀ COPY DATA LÊN TRÊN CÙNG
        btn_top_row = tk.Frame(filter_box, bg="#D0EDF3")
        btn_top_row.pack(fill="x", pady=5)

    
        # DÒNG 4: PARAMS ADVANCE (Station ID Combo Rộng Rãi & Logs Count)
        adv_row = tk.Frame(filter_box, bg="#D0EDF3")
        adv_row.pack(fill="x", pady=5)
        tk.Label(adv_row, text="Station ID:", font=("Arial", 9, "bold"), bg="#D0EDF3", width=10, anchor="w").pack(side="left")
        
        # 🟢 MỞ RỘNG Ô COMBOBOX ĐỂ HIỂN THỊ TOÀN BỘ STATION ID
        self.station_combo = ttk.Combobox(adv_row, textvariable=self.station_id_var, values=["ALL"], width=45, state="readonly")
        self.station_combo.pack(side="left", fill="x", expand=True, padx=3,pady=5)
        self.station_combo.bind("<<ComboboxSelected>>", self._on_station_selected)

        norm_row = tk.Frame(filter_box, bg="#D0EDF3")
        norm_row.pack(fill="x",pady=5)
        tk.Label(norm_row, text="Target:", font=("Arial", 9, "bold"), bg="#D0EDF3", width=10, anchor="w").pack(side="left")
        tk.Entry(norm_row, textvariable=self.target_str, width=8).pack(side="left", padx=(2, 10))
        tk.Label(norm_row, text="Delta:", font=("Arial", 9, "bold"), bg="#D0EDF3", width=6, anchor="w").pack(side="left")
        tk.Entry(norm_row, textvariable=self.delta_str, width=8).pack(side="left")
        sc_row = tk.Frame(filter_box, bg="#D0EDF3")
        sc_row.pack(fill="x", pady=5)
        tk.Label(sc_row, text="Logs/Dut:", font=("Arial", 9, "bold"), bg="#D0EDF3", width=10, anchor="w").pack(side="left")
        tk.Entry(sc_row, textvariable=self.sample_count_var, width=8, font=("Arial", 9, "bold")).pack(side="left", padx=2)
       

        # DÒNG 5: NÚT UPLOAD DƯỚI CÙNG
        btn_upload_row = tk.Frame(filter_box, bg="#D0EDF3")
        btn_upload_row.pack(fill="x", pady=(6, 2))

        btn_scan = tk.Button(btn_upload_row, text="SCAN", command=self._execute_scan, bg="#ffc107", fg="black", font=("Arial", 9, "bold"), width=16)
        btn_scan.pack(side="left", padx=(0, 4), expand=True, fill="x")

        btn_copy = tk.Button(btn_upload_row, text="COPY DATA", command=self._execute_copy_data, bg="#20c997", fg="white", font=("Arial", 9, "bold"), width=16)
        btn_copy.pack(side="left", padx=(4, 0), expand=True, fill="x")
        

        # Console Log hiển thị bên phải
        self.result_text = tk.Text(bottom_container, height=12, width=60, bg="#1a1a1a", fg="#00ff41", font=("Consolas", 10), padx=10)
        self.result_text.pack(side="right", fill="both", expand=True)

    # -----------------------------------------------------------------
    # 🟢 QUẢN LÝ SỰ KIỆN CLICK CHECKBOX CHO ITEM TREEVIEW
    # -----------------------------------------------------------------
    def _sort_dut_tree(self, col):
        """Sắp xếp danh sách DUT Treeview theo cột ID hoặc PASS."""
        items = [(self.dut_tree.item(k)["values"], k) for k in self.dut_tree.get_children("")]
        
        if not items:
            return

        # Đảo chiều sắp xếp sau mỗi lần click
        self.dut_sort_desc = not getattr(self, 'dut_sort_desc', False)

        if col == "P":
            # Sắp xếp theo số lượng PASS (chuyển về kiểu int để so sánh chính xác)
            items.sort(key=lambda x: int(x[0][1]), reverse=self.dut_sort_desc)
            suffix = " ▼" if self.dut_sort_desc else " ▲"
            self.dut_tree.heading("P", text=f"PASS{suffix}")
            self.dut_tree.heading("ID", text="DUT ID")
        else:
            # Sắp xếp theo chuỗi DUT ID
            items.sort(key=lambda x: str(x[0][0]), reverse=self.dut_sort_desc)
            suffix = " ▼" if self.dut_sort_desc else " ▲"
            self.dut_tree.heading("ID", text=f"DUT ID{suffix}")
            self.dut_tree.heading("P", text="PASS")

        # Cập nhật lại thứ tự dòng trên Treeview
        for index, (values, k) in enumerate(items):
            self.dut_tree.move(k, "", index)
    def _on_item_tree_click(self, event):
        region = self.item_tree.identify_region(event.x, event.y)
        if region in ("cell", "tree"):
            column = self.item_tree.identify_column(event.x)
            if column == "#1":
                item_id = self.item_tree.identify_row(event.y)
                if item_id:
                    vals = list(self.item_tree.item(item_id, "values"))
                    item_name = vals[1]
                    if item_name in self.selected_item_names:
                        self.selected_item_names.remove(item_name)
                        vals[0] = " "
                    else:
                        self.selected_item_names.add(item_name)
                        vals[0] = "✔"
                    self.item_tree.item(item_id, values=vals)

    def _select_all_items_cb(self):
        """Tick chọn TẤT CẢ các Item đang hiển thị trong Treeview (kể cả khi đang filter)."""
        for item_id in self.item_tree.get_children():
            vals = list(self.item_tree.item(item_id, "values"))
            if len(vals) > 1:
                item_name = vals[1]
                self.selected_item_names.add(item_name)
                vals[0] = "✔"
                self.item_tree.item(item_id, values=vals)

    def _clear_all_items_cb(self):
        """Bỏ tick các Item đang hiển thị trong Treeview (hoặc toàn bộ)."""
        for item_id in self.item_tree.get_children():
            vals = list(self.item_tree.item(item_id, "values"))
            if len(vals) > 1:
                item_name = vals[1]
                if item_name in self.selected_item_names:
                    self.selected_item_names.remove(item_name)
                vals[0] = " "
                self.item_tree.item(item_id, values=vals)

    def _get_chosen_items(self):
        """Lấy danh sách Item được chọn và chỉ giữ lại những Item thực sự có trong DataFrame."""
        chosen = []
        if self.selected_item_names:
            chosen = list(self.selected_item_names)
        else:
            chosen = [self.item_tree.item(i)['values'][1] for i in self.item_tree.selection() if len(self.item_tree.item(i)['values']) > 1]
            
        # 🟢 LỌC AN TOÀN: Chỉ trả về các item có tồn tại trong cột của df_summary
        if self.df_summary is not None:
            chosen = [item for item in chosen if item in self.df_summary.columns]
            
        return chosen

    def open_client_view(self):
        # 1. Kiểm tra nếu cửa sổ đã tồn tại và chưa bị đóng thì chỉ cần active lại
        if hasattr(self, 'client_view') and self.client_view.winfo_exists():
            self.client_view.lift()
            self.client_view.focus_force()
            return

        # 2. Tạo cửa sổ Toplevel mới
        self.client_view = tk.Toplevel(self.root)
        self.client_view.geometry("1500x800")
        ClientView(self.client_view)

        # 🟢 CHẶN TƯƠNG TÁC CỬA SỔ CHÍNH (MODAL)
        self.client_view.transient(self.root)   # Gắn chặt vào cửa sổ chính
        #self.client_view.grab_set()            # Khóa mọi sự kiện click vào cửa sổ chính
        self.client_view.focus_force()         # Đưa tiêu điểm vào cửa sổ phụ

    def handle_export(self):
        log_path = self.source_path.get().strip()
        mode = self.mode_export_val.get()
        
        if not log_path or not os.path.exists(log_path):
            messagebox.showerror("Error", "Input can not empty to running")
            return
            
        if mode == 'grr':
            file_path = filedialog.asksaveasfilename(
                title="Input filename to export GRR csv",
                filetypes=[("CSV Files", "*.csv")],
                defaultextension=".csv"
            )
        else:
            file_path = filedialog.asksaveasfilename(
                title=f"Input filename to export {mode.upper()}",
                filetypes=[("Excel Files", "*.xlsx")],
                defaultextension=".xlsx"
            )
            
        if not file_path:
            return
        
        try:
            self.export_btn.config(state="disabled")
            self.root.update_idletasks()
            
            if mode == 'grr':
                t = threading.Thread(target=lambda: report_tool.grr(path=log_path, filename=file_path))
                t.start()
            elif mode in ['loop', 'correl', 'station']:
                t = threading.Thread(target=lambda: report_tool.crr_and_loop(path=log_path, filename=file_path, mode=mode))
                t.start()
            messagebox.showinfo("Success", f"Export OK!\nSaved path: {file_path}")
        except Exception as e:
            messagebox.showerror("System Error", f"Data Process Error:\n{str(e)}")
        finally:
            self.export_btn.config(state="normal")
    
    def _get_filtered(self):
        items = self._get_chosen_items()
        if not items: return None
        
        selected_dut_items = self.dut_tree.selection()
        selected_dut_ids = [self.dut_tree.item(i)['values'][0] for i in selected_dut_items]
        
        df_base = self.df_summary if not selected_dut_ids else self.df_summary[self.df_summary['dut_id'].isin(selected_dut_ids)]
        
        selected_station = self.station_id_var.get()
        if selected_station and selected_station != "ALL" and "station_id" in df_base.columns:
            df_base = df_base[df_base['station_id'] == selected_station]

        try: delta = float(self.delta_str.get() or 0)
        except ValueError: return None

        final_mask = pd.Series([False] * len(df_base), index=df_base.index)

        if len(selected_dut_ids) == 1 and len(items) == 1:
            try: target = float(self.target_str.get() or 0)
            except ValueError: return None
            self.last_mode_msg = f"Single Mode (Dut: {selected_dut_ids[0]} | Target: {target})"
            val_col = pd.to_numeric(df_base[items[0]], errors='coerce')
            final_mask = (val_col >= target - delta) & (val_col <= target + delta)
        else:
            self.last_mode_msg = "Multi Mode (Auto)"
            for dut_id in df_base['dut_id'].unique():
                dut_mask = df_base['dut_id'] == dut_id
                df_dut = df_base[dut_mask]
                
                combined_item_mask = pd.Series([True] * len(df_dut), index=df_dut.index)
                for item_name in items:
                    val_col = pd.to_numeric(df_dut[item_name], errors='coerce')
                    item_mean = val_col.mean()
                    if pd.isna(item_mean): continue
                    item_filter = (val_col >= item_mean - delta) & (val_col <= item_mean + delta)
                    combined_item_mask &= item_filter
                
                final_mask.loc[combined_item_mask.index] = combined_item_mask

        return df_base[final_mask]

    # -----------------------------------------------------------------
    # 🟢 HÀM SCAN VÀ COPY ĐIỀU HƯỚNG THEO NORMAL VS ADVANCE
    # -----------------------------------------------------------------
    def _execute_scan(self):
        """Kích hoạt quét dữ liệu tự động dựa theo Radiobutton đang chọn."""
        if self.scan_mode_var.get() == "normal":
            self._calculate_report()
        else:
            self._execute_smart_check()

    def _execute_copy_data(self):
        """Kích hoạt sao chép dữ liệu dựa theo Radiobutton đang chọn."""
        if self.scan_mode_var.get() == "normal":
            self._copy_pass_logs()
        else:
            self._copy_checked_logs()

    def _calculate_report(self):
        """Logic lọc Normal (theo Target & Delta)."""
        selected_items = self._get_chosen_items()
        num_items = len(selected_items)
        df_filtered = self._get_filtered()
        self.result_text.delete(1.0, tk.END)
        
        if self.df_summary is None:
            self.result_text.insert(tk.END, " Please load data first.\n")
            return

        self.result_text.insert(tk.END, f"[NORMAL SCAN REPORT]\n")
        self.result_text.insert(tk.END, f"Station ID: {self.station_id_var.get()}\n")
        self.result_text.insert(tk.END, f"{self.last_mode_msg}\n")
        self.result_text.insert(tk.END, f"Selected Items Count: {num_items}\n")
        self.result_text.insert(tk.END, f"Delta Apply: ± {self.delta_str.get()}\n\n")

        selected_dut_ids = [self.dut_tree.item(i)['values'][0] for i in self.dut_tree.selection()]
        duts_to_report = selected_dut_ids if selected_dut_ids else self.df_summary['dut_id'].unique()

        self.result_text.insert(tk.END, f"{'DUT ID':<20} | {'OK':<12}\n")
        self.result_text.insert(tk.END, "-" * 35 + "\n")

        total_ok = 0
        if df_filtered is not None:
            for dut in duts_to_report:
                count = len(df_filtered[df_filtered['dut_id'] == dut])
                self.result_text.insert(tk.END, f"{dut:<20} | {count:<12}\n")
                total_ok += count
            self.result_text.insert(tk.END, "-" * 35 + "\n")
            self.result_text.insert(tk.END, f"TOTAL: {total_ok} logs found\n")
            self.result_text.see(tk.END)
        else:
            self.result_text.insert(tk.END, " No items selected for filtering.\n")

    def _execute_smart_check(self):
        """Logic lọc Advance (Smart Gap & Station ID Filter)."""
        if self.df_summary is None or self.df_summary.empty:
            messagebox.showwarning("Warning", "Please load data first !!!")
            return

        selected_items = self._get_chosen_items()
        if not selected_items:
            messagebox.showwarning("Warning", "Please seclecte minimum a item to run analyze!!!")
            return

        try:
            target_count = int(self.sample_count_var.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Input interger pls !!")
            return

        mode = self.mode_export_val.get()
        station_selected = self.station_id_var.get()

        df_base = self.df_summary.copy()
        if station_selected != "ALL" and "station_id" in df_base.columns:
            df_base = df_base[df_base['station_id'] == station_selected]

        selected_duts = [self.dut_tree.item(i)['values'][0] for i in self.dut_tree.selection()]
        if selected_duts:
            df_base = df_base[df_base['dut_id'].isin(selected_duts)]

        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, f"=== ADVANCE SCAN ({mode.upper()} MODE) ===\n")
        self.result_text.insert(tk.END, f"Target logs to get: {target_count}\n")
        self.result_text.insert(tk.END, f"Station: {station_selected}\n")
        self.result_text.insert(tk.END, f"Items selected: {len(selected_items)}\n\n")

        selected_indices = []
        warning_msgs = []

        if mode in ['loop', 'grr', 'station']:
            for dut_id, df_group in df_base.groupby('dut_id'):
                n_avail = len(df_group)
                if n_avail < target_count:
                    warning_msgs.append(f"{dut_id} | Miss log (idle {n_avail}/{target_count} logs) -> Take all {n_avail} logs.")
                    selected_indices.extend(df_group.index)
                    continue

                best_comb = None
                min_sum_gap = float('inf')

                all_combos = list(itertools.combinations(df_group.index, target_count))
                if len(all_combos) > 2000:
                    all_combos = all_combos[:2000]

                for comb in all_combos:
                    sub_df = df_group.loc[list(comb)]
                    total_gap = 0
                    for item in selected_items:
                        vals = pd.to_numeric(sub_df[item], errors='coerce').dropna()
                        if not vals.empty:
                            total_gap += (vals.max() - vals.min())

                    if total_gap < min_sum_gap:
                        min_sum_gap = total_gap
                        best_comb = comb

                if best_comb is not None:
                    selected_indices.extend(best_comb)
                    sub_df_best = df_group.loc[list(best_comb)]
                    
                    max_item_gap = 0
                    bad_items = []
                    for item in selected_items:
                        vals = pd.to_numeric(sub_df_best[item], errors='coerce').dropna()
                        if not vals.empty:
                            gap = vals.max() - vals.min()
                            if gap > max_item_gap: max_item_gap = gap
                            if gap >= 1.0:
                                bad_items.append(f"{item} (Gap={gap:.2f})")

                    if max_item_gap >= 1.0:
                        warning_msgs.append(f"{dut_id} | Gap < 1! [Max Gap = {max_item_gap:.3f}] - Items Error: {', '.join(bad_items[:2])}")
                        self.result_text.insert(tk.END, f"{dut_id} | Sorting {target_count} logs - Max Gap: {max_item_gap:.3f} (Gap > 1.0)\n")
                    else:
                        self.result_text.insert(tk.END, f"{dut_id} | Sorting {target_count} logs successfuly (Max Gap: {max_item_gap:.3f} OK)\n")

        elif mode == 'correl':
            if "station_id" not in df_base.columns:
                messagebox.showerror("Error", "Missing column 'station_id'!")
                return

            stations = df_base['station_id'].unique()
            for dut_id, df_dut in df_base.groupby('dut_id'):
                st_tested = df_dut['station_id'].unique()
                if len(st_tested) < len(stations):
                    warning_msgs.append(f"{dut_id} | Miss station test! (Have {len(st_tested)}/{len(stations)} station)")

                dut_selected_idx = []
                for st in st_tested:
                    st_df = df_dut[df_dut['station_id'] == st]
                    dut_selected_idx.append(st_df.index[0])

                selected_indices.extend(dut_selected_idx)
                sub_df_correl = df_dut.loc[dut_selected_idx]
                
                max_correl_gap = 0
                for item in selected_items:
                    st_means = sub_df_correl.groupby('station_id')[item].apply(lambda x: pd.to_numeric(x, errors='coerce').mean())
                    if not st_means.empty:
                        gap = st_means.max() - st_means.min()
                        if gap > max_correl_gap: max_correl_gap = gap

                if max_correl_gap >= 1.0:
                    warning_msgs.append(f"{dut_id} | Cross-Station Gap = {max_correl_gap:.3f} (Gap > 1.0)!")
                    self.result_text.insert(tk.END, f"{dut_id} | Correlation Gap = {max_correl_gap:.3f} (Gap > 1.0)\n")
                else:
                    self.result_text.insert(tk.END, f"{dut_id} | Correlation Gap = {max_correl_gap:.3f} OK\n")

        if selected_indices:
            self.df_checked_result = self.df_summary.loc[selected_indices]
        else:
            self.df_checked_result = None

        if warning_msgs:
            #self.result_text.insert(tk.END, "\n=== DANH SÁCH CẢNH BÁO (VẪN CHO PHÉP COPY / UPLOAD) ===\n")
            for w in warning_msgs:
                self.result_text.insert(tk.END, w + "\n")
            self.result_text.see(tk.END)
            #messagebox.showwarning("Cảnh Báo Kiểm Tra", f"Đã trích xuất {len(selected_indices)} logs thành công!\nPhát hiện {len(warning_msgs)} cảnh báo Gap >= 1 (Xem chi tiết ở ô Console bên dưới).\n\nBạn vẫn có thể bấm COPY DATA để lấy dữ liệu!")
        else:
            #self.result_text.insert(tk.END, f"\n🎉 TẤT CẢ DỮ LIỆU ĐẠT CHUẨN! Đã trích xuất {len(selected_indices)} logs hợp lệ.\n")
            self.result_text.see(tk.END)
            #messagebox.showinfo("Thành Công", f"Đã trích xuất {len(selected_indices)} logs hoàn hảo!")

    def _copy_checked_logs(self):
        """Sao chép các log đã lọc thuộc mode Advance."""
        if self.df_checked_result is None or self.df_checked_result.empty:
            messagebox.showwarning("Warning", "Don't have any data scanning in advance mode! Click 'SCAN' first.")
            return

        target = self.output_path.get()
        if not target or not os.path.exists(target):
            target = filedialog.askdirectory(title="Select folder to copy logs")
            if target: self.output_path.set(target)
            else: return

        os.makedirs(target, exist_ok=True)
        count_json, count_csv = 0, 0

        for path in self.df_checked_result['log_path'].dropna().unique():
            json_p = path.replace('.csv', '.json')
            if os.path.exists(json_p):
                shutil.copy(json_p, target)
                count_json += 1
            if os.path.exists(path):
                shutil.copy(path, target)
                count_csv += 1

        messagebox.showinfo("Copy Complete", f"Copy completed {len(self.df_checked_result)} logs!\n\nCSV: {count_csv} files\nJSON: {count_json} files")

    def _upload_to_ftp(self):
        """Upload dữ liệu dựa theo mode Normal/Advance đang chọn."""
        df_target = self.df_checked_result if self.scan_mode_var.get() == "advance" else self._get_filtered()

        if df_target is None or df_target.empty:
            messagebox.showwarning("Warning", "Don't have any data to upload! Click 'SCAN' first.")
            return

        if messagebox.askyesno("Confirm Transfer", f"Upload {len(df_target)} Sorted Logs lên Remote Server?"):
            self._execute_transfer(df_target, "SORTED")

    def _upload_all_to_ftp(self):
        if self.df_summary is None: return
        if messagebox.askyesno("Confirm Transfer", f"Upload ALL {len(self.df_summary)} logs ?"):
            self._execute_transfer(self.df_summary, "ALL")

    def _on_station_selected(self, event=None):
        self._refresh_dut_list()
        self._refresh_item_table()

    def _auto_fill_target(self, event=None):
        selected_duts = self.dut_tree.selection()
        selected_items = self._get_chosen_items()

        if len(selected_duts) == 1 and len(selected_items) == 1:
            dut_id = self.dut_tree.item(selected_duts[0])['values'][0]
            item_name = selected_items[0]

            if self.df_summary is not None:
                df_dut = self.df_summary[self.df_summary['dut_id'] == dut_id]
                val_col = pd.to_numeric(df_dut[item_name], errors='coerce').dropna()
                
                if not val_col.empty:
                    mean_val = val_col.mean()
                    self.target_str.set(f"{mean_val:.3f}")

    def _execute_transfer(self, df, label):
        host, user, pw, port, remote_dir = self.ftp_host.get(), self.ftp_user.get(), self.ftp_pass.get(), self.ftp_port.get(), self.ftp_dir.get()
        try:
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, f"[Transfer Progress - {label}]\n")
             
            self.root.update_idletasks()
            transfer = None
            if int(port) == 21:
                transfer = FTPService()
                if transfer.connect(host=host, username=user, password=pw):
                    self.result_text.insert(tk.END, f"Connected OK to FTP: ftp://{user}@{host}{remote_dir}\n\n")
            else: 
                transfer = SFTPService()
                if transfer.connect(host=host, username=user, password=pw):
                    self.result_text.insert(tk.END, f"Connected OK to SFTP: sftp://{user}@{host}{remote_dir}\n\n")
            
            total_files = len(df['log_path'].dropna().unique())
            def exec():
                count_json = 0
                count_csv = 0
                for idx, path in enumerate(df['log_path'].dropna().unique()):
                    percent = (idx / total_files) * 100
                    json_p = path.replace('.csv', '.json')
                    if os.path.exists(json_p):
                        if transfer.upload_file(local_file=json_p, remote_path=remote_dir):
                            count_json += 1
                    if os.path.exists(path):
                        if transfer.upload_file(local_file=path, remote_path=remote_dir):
                            count_csv += 1
                    if idx > 1:
                        self.result_text.delete("end-2c linestart", "end-1c")
                    
                        progress_msg = f"⏳ Uploading... [{percent:5.1f}%] ({idx}/{total_files} logs)"
                        self.result_text.insert(tk.END, progress_msg + "\n")
                        self.result_text.see(tk.END)
                        self.root.update_idletasks()
                self.result_text.delete("end-2c linestart", "end-1c")
                summary_msg = f"\nUpload Successfully!\n------------------------------\nJSON: {count_json} logs.\nCSV: {count_csv} logs.\n"
                self.result_text.insert(tk.END, summary_msg)
                self.result_text.see(tk.END)
                messagebox.showinfo("Transfer", f"Upload Successfully\n\nJSON: {count_json} logs\n CSV: {count_csv} logs\n")
            if transfer:
                t = threading.Thread(target=exec)
                t.start()
        except Exception as e: 
            messagebox.showerror("Transfer Error", str(e))

    def _load_data_logic(self, *args):
        path, run_mode = self.source_path.get(), self.mode_var.get()
        if not os.path.exists(path): return
        try:
            _, full_df = self.parser.summary_data(path) 
            if not full_df.empty:
                mode_pattern = f"_{run_mode}_"
                self.df_summary = full_df[
                    (full_df['log_path'].str.contains(mode_pattern, case=False, na=False)) & 
                    (full_df['outcome'].str.upper() == 'PASS')
                ].copy()
                
                self.selected_item_names.clear()

                if 'station_id' not in self.df_summary.columns:
                    self.df_summary['station_id'] = self.df_summary['log_path'].apply(
                        lambda p: os.path.basename(p).split('_')[0] if '_' in os.path.basename(p) else "ST01"
                    )

                stations = ["ALL"] + sorted(list(self.df_summary['station_id'].dropna().astype(str).unique()))
                self.station_combo['values'] = stations
                self.station_id_var.set("ALL")

                self._refresh_dut_list()
                self._refresh_item_table()
                self.result_text.delete(1.0, tk.END)
                self.result_text.insert(tk.END, f"Input: {len(self.df_summary)} logs loaded successfully.\n")
        except Exception as e: 
            messagebox.showerror("Error", str(e))
            log.error(e)

    def _refresh_item_table(self, *args):
        if self.df_summary is None: return
        for row in self.item_tree.get_children(): self.item_tree.delete(row)
        
        selected_duts = [self.dut_tree.item(i)['values'][0] for i in self.dut_tree.selection()]
        df = self.df_summary if not selected_duts else self.df_summary[self.df_summary['dut_id'].isin(selected_duts)]
        
        st_id = self.station_id_var.get()
        if st_id != "ALL" and "station_id" in df.columns:
            df = df[df['station_id'] == st_id]

        kw = self.item_search_var.get().lower()
        cols = [c for c in self.df_summary.columns if kw in c.lower() and c not in ["dut_id", "station_id", "log_path", "outcome"]]
        
        for col in cols:
            nums = pd.to_numeric(df[col], errors='coerce').dropna()
            if not nums.empty:
                v_max, v_min = nums.max(), nums.min()
                is_selected = "✔" if col in self.selected_item_names else ""
                self.item_tree.insert("", "end", values=(is_selected, col, f"{v_max:.2f}", f"{v_min:.2f}", f"{nums.mean():.2f}", f"{v_max - v_min:.2f}", f"{nums.std():.2f}"))
            
    def _browse_dir(self, var):
        path = filedialog.askdirectory()
        if path: var.set(path)

    def _on_dut_selection_change(self, event): 
        self._refresh_item_table()

    def _refresh_dut_list(self):
        for row in self.dut_tree.get_children(): 
            self.dut_tree.delete(row)
        
        df = self.df_summary
        st_id = self.station_id_var.get()
        if df is not None and st_id != "ALL" and "station_id" in df.columns:
            df = df[df['station_id'] == st_id]

        if df is not None and not df.empty:
            summary = df.groupby('dut_id').size().reset_index(name='c')
            
            # 🟢 Sắp xếp mặc định số lượng PASS từ lớn đến nhỏ (ascending=False)
            summary = summary.sort_values(by='c', ascending=False)
            
            for _, r in summary.iterrows(): 
                self.dut_tree.insert("", "end", values=(r['dut_id'], r['c']))
            
            # Đặt mũi tên chỉ báo giảm dần cho cột PASS
            self.dut_tree.heading("P", text="PASS ▼")
            self.dut_sort_desc = True

    
    def _copy_pass_logs(self):
        """Sao chép logs lọc Normal."""
        df = self._get_filtered()
        if df is None: return
        target = self.output_path.get()
        if target:
            os.makedirs(target, exist_ok=True)
        if not target or not os.path.exists(target):
            target = filedialog.askdirectory(title="Select Output Directory")
            if target: self.output_path.set(target)
            else: return
        count_json = 0
        count_csv = 0
        for path in df['log_path'].dropna().unique():
            json_p = path.replace('.csv', '.json')
            if os.path.exists(json_p):
                shutil.copy(json_p, target)
                count_json += 1
            if os.path.exists(path):
                shutil.copy(path, target)
                count_csv += 1
        messagebox.showinfo("Copy", f"Copy Completed (Normal Mode)\n\nJSON: {count_json} logs\nCSV: {count_csv} logs\n")

if __name__ == "__main__":
    app_mutex_name = "Global\\RF_SUPPORT_TOOL_2026"

    mutex = ctypes.windll.kernel32.CreateMutexW(None, True, app_mutex_name)
    last_error = ctypes.windll.kernel32.GetLastError()
    if last_error == 183:
        root_warning = tk.Tk()
        root_warning.withdraw() 
        messagebox.showwarning("Notify", "App is opened!")
        root_warning.destroy()
        sys.exit(0)
    

    log.info('Start Application')
    root = tk.Tk()
    icon_path = "icon.ico"
    if os.path.exists(icon_path):
        root.iconbitmap(icon_path) 
    app = RFAnalyzerGUI(root) 
    root.mainloop()