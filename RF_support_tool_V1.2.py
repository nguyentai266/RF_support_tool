import os
import shutil
import tkinter as tk
from ftplib import FTP
from tkinter import filedialog, messagebox, ttk

import numpy as np
import pandas as pd

from core.parser import ParserLog


class RFAnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("RF Support Tool - V1.2.8")
        self.root.geometry("1700x1050")
        
        self.parser = ParserLog() 
        
        # Variables
        self.source_path = tk.StringVar(value="")
        self.output_path = tk.StringVar(value="") 
        
        # --- CẤU HÌNH FTP ---
        self.ftp_host = tk.StringVar(value="10.239.73.213")
        self.ftp_user = tk.StringVar(value="Mars")
        self.ftp_pass = tk.StringVar(value="GGFTP@22")
        self.ftp_dir = tk.StringVar(value="/.Enzo/log")
        
        self.item_search_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="GRR") 
        self.target_str = tk.StringVar(value="17.0")
        self.delta_str = tk.StringVar(value="0.5")
        
        self.df_summary = None
        self.last_mode_msg = ""

        self._setup_style()
        self._setup_ui()
        
        # --- ĐĂNG KÝ PHÍM TẮT ---
        self.root.bind('<Return>', lambda event: self._calculate_report())
        self.dut_tree.bind('<Control-a>', lambda e: self._select_all(self.dut_tree))
        self.dut_tree.bind('<Control-A>', lambda e: self._select_all(self.dut_tree))
        self.item_tree.bind('<Control-a>', lambda e: self._select_all(self.item_tree))
        self.item_tree.bind('<Control-A>', lambda e: self._select_all(self.item_tree))

    def _select_all(self, tree):
        """Chọn tất cả các dòng trong bảng"""
        tree.selection_set(tree.get_children())
        return "break"

    def _setup_style(self):
        """Cấu hình chuyên sâu để hiển thị vạch kẻ ô (Gridlines)"""
        style = ttk.Style()
        style.theme_use("clam") # Theme 'clam' hỗ trợ gridlines tốt nhất
        
        # Cấu hình màu sắc và độ cao hàng
        style.configure("Treeview", 
                        rowheight=25, 
                        font=("Arial", 9),
                        background="white",
                        fieldbackground="white",
                        foreground="black",
                        lightcolor="#cccccc", # Màu đường kẻ dọc
                        bordercolor="#cccccc") # Màu viền
        
        # Hiển thị vạch kẻ ô bằng cách thay đổi layout
        style.layout("Treeview", [
            ('Treeview.treearea', {'sticky': 'nswe'})
        ])
        
        # Cấu hình tiêu đề bảng có viền
        style.configure("Treeview.Heading", 
                        font=("Arial", 9, "bold"), 
                        background="#eeeeee",
                        relief="flat")
        
        style.map("Treeview", 
                  background=[('selected', '#0078d7')], 
                  foreground=[('selected', 'white')])

    def _setup_ui(self):
        # --- 1. TOP PANEL ---
        top_frame = tk.Frame(self.root, bg="#f8f9fa", padx=10, pady=10, bd=1, relief="ridge")
        top_frame.pack(side="top", fill="x")
        
        # Dòng 1 & 2: Paths
        for text, var in [("📁 Input Dir: ", self.source_path), ("📂 Output Dir:", self.output_path)]:
            row = tk.Frame(top_frame, bg="#f8f9fa")
            row.pack(fill="x", pady=2)
            tk.Label(row, text=text, bg="#f8f9fa", font=("Arial", 9, "bold"), width=12, anchor="w").pack(side="left")
            tk.Entry(row, textvariable=var, width=100).pack(side="left", padx=5)
            tk.Button(row, text="...", command=lambda v=var: self._browse_dir(v), bg="#6c757d", fg="white", width=5).pack(side="left")

        # Dòng 3: FTP Config
        ftp_row = tk.Frame(top_frame, bg="#f8f9fa")
        ftp_row.pack(fill="x", pady=5)
        tk.Label(ftp_row, text="🌐 FTP Host:", bg="#f8f9fa", font=("Arial", 9, "bold"), width=12, anchor="w").pack(side="left")
        tk.Entry(ftp_row, textvariable=self.ftp_host, width=20).pack(side="left", padx=5)
        tk.Label(ftp_row, text="User:", bg="#f8f9fa").pack(side="left", padx=2)
        tk.Entry(ftp_row, textvariable=self.ftp_user, width=15).pack(side="left", padx=5)
        tk.Label(ftp_row, text="Password:", bg="#f8f9fa").pack(side="left", padx=2)
        tk.Entry(ftp_row, textvariable=self.ftp_pass, show="*", width=15).pack(side="left", padx=5)
        tk.Label(ftp_row, text="Remote Dir:", bg="#f8f9fa").pack(side="left", padx=2)
        tk.Entry(ftp_row, textvariable=self.ftp_dir, width=60).pack(side="left", padx=5)

        # Dòng 4: Tools
        tool_row = tk.Frame(top_frame, bg="#f8f9fa")
        tool_row.pack(fill="x", pady=5)
        self.mode_combo = ttk.Combobox(tool_row, textvariable=self.mode_var, values=("DEBUG", "AUDIT", "GRR","CALIBRATION","PRODUCTION"), width=12, state="readonly")
        self.mode_combo.pack(side="left", padx=5)
        tk.Button(tool_row, text="LOAD DATA", command=self._load_data_logic, bg="#0078d7", fg="white", font=("Arial", 9, "bold"), width=12).pack(side="left", padx=10)
        
        tk.Button(tool_row, text="FTP upload ALL", command=self._upload_all_to_ftp, bg="#6f42c1", fg="white", width=15).pack(side="right", padx=5)
        tk.Button(tool_row, text="FTP upload Sorted", command=self._upload_to_ftp, bg="#17a2b8", fg="white", width=15).pack(side="right", padx=5)

        # --- 2. MAIN CONTENT ---
        paned = tk.PanedWindow(self.root, orient="horizontal", bg="#cccccc", sashwidth=4)
        paned.pack(expand=True, fill="both", padx=2, pady=2)

        # DUT List (Cột trái)
        left_frame = tk.Frame(paned, bg="white", padx=5, pady=5)
        paned.add(left_frame, width=220)
        self.dut_tree = ttk.Treeview(left_frame, columns=("ID", "P"), show="headings", selectmode="extended")
        self.dut_tree.heading("ID", text="DUT ID"); self.dut_tree.heading("P", text="PASS")
        self.dut_tree.column("ID", width=160); self.dut_tree.column("P", width=40, anchor="center")
        self.dut_tree.pack(expand=True, fill="both")
        self.dut_tree.bind("<<TreeviewSelect>>", self._on_dut_selection_change)

        # Item Table (Cột phải)
        right_frame = tk.Frame(paned, bg="white", padx=10, pady=5)
        paned.add(right_frame, width=1350)

        tk.Entry(right_frame, textvariable=self.item_search_var, bg="#e1f5fe").pack(fill="x", pady=5)
        self.item_search_var.trace_add("write", self._refresh_item_table)

        # Bảng Item chính - Kẻ ô Gridlines
        cols = ("Name", "Max", "Min", "Mean", "Gap", "Stdev")
        self.item_tree = ttk.Treeview(right_frame, columns=cols, show="headings", selectmode="extended")
        self.item_tree.heading("Name", text="Measurement Name", anchor="w")
        self.item_tree.column("Name", width=1000, anchor="w")
        for col in cols[1:]:
            self.item_tree.heading(col, text=col, anchor="center")
            self.item_tree.column(col, width=30, anchor="center")
        self.item_tree.pack(expand=True, fill="both")

        action_frame = tk.Frame(right_frame, bg="white", pady=10)
        action_frame.pack(fill="x")
        tk.Label(action_frame, text="Target:", font=("Arial", 9, "bold")).pack(side="left")
        tk.Entry(action_frame, textvariable=self.target_str, width=8).pack(side="left", padx=5)
        tk.Label(action_frame, text="Delta:", font=("Arial", 9, "bold")).pack(side="left")
        tk.Entry(action_frame, textvariable=self.delta_str, width=8).pack(side="left", padx=5)
        tk.Button(action_frame, text="RUN", command=self._calculate_report, bg="#28a745", fg="white", font=("Arial", 8, "bold"), width=15).pack(side="left", padx=10)
        tk.Button(action_frame, text="COPY", command=self._copy_pass_logs, bg="#ffc107", fg="black", font=("Arial", 8, "bold"), width=20).pack(side="left")

        self.result_text = tk.Text(right_frame, height=12, bg="#1a1a1a", fg="#00ff41", font=("Consolas", 10), padx=10, pady=10)
        self.result_text.pack(side="bottom", fill="x", pady=10)

    # --- LOGIC DỮ LIỆU ---
    def _get_filtered(self):
        items = [self.item_tree.item(i)['values'][0] for i in self.item_tree.selection()]
        if not items: return None
        
        selected_dut_items = self.dut_tree.selection()
        selected_dut_ids = [self.dut_tree.item(i)['values'][0] for i in selected_dut_items]
        
        df_base = self.df_summary if not selected_dut_ids else self.df_summary[self.df_summary['dut_id'].isin(selected_dut_ids)]
        
        try: delta = float(self.delta_str.get() or 0)
        except ValueError: return None

        final_mask = pd.Series([False] * len(df_base), index=df_base.index)

        # Logic Case 1: 1 DUT + 1 Item đơn lẻ -> Dùng Target nhập tay
        if len(selected_dut_ids) == 1 and len(items) == 1:
            try: target = float(self.target_str.get() or 0)
            except ValueError: return None
            self.last_mode_msg = f"Single Mode (Dut: {selected_dut_ids[0]} | Target: {target})"
            val_col = pd.to_numeric(df_base[items[0]], errors='coerce')
            final_mask = (val_col >= target - delta) & (val_col <= target + delta)
        
        # Logic Case 2: Nhiều Item (kể cả 1 DUT) HOẶC Nhiều DUT -> Dùng Mean Mode
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
                
                # Cập nhật kết quả vào mask tổng (dùng .loc để tránh cảnh báo Future)
                final_mask.loc[combined_item_mask.index] = combined_item_mask

        return df_base[final_mask]

    def _calculate_report(self):
        selected_items = self.item_tree.selection()
        num_items = len(selected_items)
        df_filtered = self._get_filtered()
        self.result_text.delete(1.0, tk.END)
        
        if self.df_summary is None:
            self.result_text.insert(tk.END, " Please load data first.\n")
            return

        self.result_text.insert(tk.END, f"--- RUN REPORT ---\n")
        self.result_text.insert(tk.END, f"{self.last_mode_msg})\n")
        self.result_text.insert(tk.END, f"Selected Items Count: {num_items}\n")
        self.result_text.insert(tk.END, f"Delta applied: ±{self.delta_str.get()}\n\n")

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

    # --- CÁC HÀM TIỆN ÍCH (GIỮ NGUYÊN) ---
    def _execute_ftp_transfer(self, df, label):
        host, user, pw, remote_dir = self.ftp_host.get(), self.ftp_user.get(), self.ftp_pass.get(), self.ftp_dir.get()
        try:
            self.result_text.insert(tk.END, f"🚀 Connecting to FTP {host}...\n")
            self.root.update_idletasks()
            with FTP(host) as ftp:
                ftp.login(user=user, passwd=pw)
                try: ftp.cwd(remote_dir)
                except: ftp.mkd(remote_dir); ftp.cwd(remote_dir)
                count = 0
                for path in df['log_path'].dropna().unique():
                    json_p = path.replace('.csv', '.json')
                    if os.path.exists(json_p):
                        with open(json_p, 'rb') as f: ftp.storbinary(f"STOR {os.path.basename(json_p)}", f)
                        with open(path, 'rb') as f: ftp.storbinary(f"STOR {os.path.basename(path)}", f)
                        count += 1
                self.result_text.insert(tk.END, f"FTP Successfuly: {count} files.\n")
                messagebox.showinfo("FTP", f"Uploaded {count} files")
        except Exception as e: messagebox.showerror("FTP Error", str(e))

    def _upload_all_to_ftp(self):
        if self.df_summary is None: return
        if messagebox.askyesno("Confirm FTP", f"Upload ALL ({len(self.df_summary)}) logs?"):
            self._execute_ftp_transfer(self.df_summary, "ALL")

    def _upload_to_ftp(self):
        df = self._get_filtered()
        if df is not None: self._execute_ftp_transfer(df, "SORTED")

    def _load_data_logic(self):
        path, run_mode = self.source_path.get(), self.mode_var.get()
        if not os.path.exists(path): return
        try:
            _, full_df = self.parser.summary_data(path, mode="rf") 
            if not full_df.empty:
                mode_pattern = f"_{run_mode}_"
                self.df_summary = full_df[
                    (full_df['log_path'].str.contains(mode_pattern, case=False, na=False)) & 
                    (full_df['result'].str.upper() == 'PASS')
                ].copy()
                self._refresh_dut_list(); self._refresh_item_table()
                self.result_text.delete(1.0, tk.END); self.result_text.insert(tk.END, f"Input success: {len(self.df_summary)} logs.\n")
        except Exception as e: messagebox.showerror("Error", str(e))

    def _refresh_item_table(self, *args):
        if self.df_summary is None: return
        for row in self.item_tree.get_children(): self.item_tree.delete(row)
        selected_duts = [self.dut_tree.item(i)['values'][0] for i in self.dut_tree.selection()]
        df = self.df_summary if not selected_duts else self.df_summary[self.df_summary['dut_id'].isin(selected_duts)]
        kw = self.item_search_var.get().lower()
        cols = [c for c in self.df_summary.columns if kw in c.lower() and c not in ["dut_id", "log_path", "result"]]
        for col in cols:
            nums = pd.to_numeric(df[col], errors='coerce').dropna()
            if not nums.empty:
                v_max, v_min = nums.max(), nums.min()
                self.item_tree.insert("", "end", values=(col, f"{v_max:.2f}", f"{v_min:.2f}", f"{nums.mean():.2f}", f"{v_max - v_min:.2f}", f"{nums.std():.2f}"))

    def _browse_dir(self, var):
        path = filedialog.askdirectory()
        if path: var.set(path)

    def _on_dut_selection_change(self, event): self._refresh_item_table()

    def _refresh_dut_list(self):
        for row in self.dut_tree.get_children(): self.dut_tree.delete(row)
        summary = self.df_summary.groupby('dut_id').size().reset_index(name='c')
        for _, r in summary.iterrows(): self.dut_tree.insert("", "end", values=(r['dut_id'], r['c']))

    def _copy_pass_logs(self):
        df = self._get_filtered()
        if df is None: return
        target = self.output_path.get()
        if target:
            os.makedirs(target,exist_ok=True)
        if not target or not os.path.exists(target):
            target = filedialog.askdirectory(title="Select Output Directory")
            if target: self.output_path.set(target)
            else: return
        count = 0
        for path in df['log_path'].dropna().unique():
            json_p = path.replace('.csv', '.json')
            if os.path.exists(json_p):
                shutil.copy(path, target); shutil.copy(json_p, target); count += 1
        messagebox.showinfo("Copy", f"Copied {count} logs")

if __name__ == "__main__":
    root = tk.Tk(); app = RFAnalyzerGUI(root); root.mainloop()