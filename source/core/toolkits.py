
import json
import os
import posixpath
from stat import S_ISDIR
import subprocess

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import win32com.client
from core.data_service import FTPService, SFTPService
from core.logger import logger as log
import platform
HISTORY_FILE = "connection_history.json"


class ClientView(ttk.Frame):
    """Giao diện quản lý file Remote (FTP/SFTP) tích hợp Quickconnect History & Tự động kết nối khi chọn tài khoản."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.ftp_service_cls = FTPService()
        self.sftp_service_cls = SFTPService()
        self.current_os = platform.system()
        self.service = None
        self.current_remote_dir = "/"
        self.all_items = []
        self.history_list = self._load_history()

        self.pack(fill="both", expand=True, padx=10, pady=10)

        # Biến bindings Tkinter
        self.host_var = tk.StringVar(value="10.239.73.213")
        self.port_var = tk.StringVar(value="22")
        self.user_var = tk.StringVar(value="Images")
        self.pass_var = tk.StringVar(value="DMSTE@SFTP189")
        self.protocol_var = tk.StringVar(value="SFTP")

        self.path_var = tk.StringVar(value="/")
        self.search_var = tk.StringVar()

        # Build Giao diện
        self._build_top_connection_bar()
        self._build_navigation_bar()
        self._build_file_treeview()
        self._build_bottom_action_bar()

        self.search_var.trace_add("write", self._on_search_change)

        # Đăng ký sự kiện tắt cửa sổ
        if isinstance(self.parent, (tk.Toplevel, tk.Tk)):
            self.parent.protocol("WM_DELETE_WINDOW", self._on_close_window)

    def _on_close_window(self):
        """Xử lý khi nhấn nút X tắt cửa sổ: Đóng toàn bộ kết nối và hủy cửa sổ."""
        try:
            if self.service and getattr(self.service, "is_connected", False):
                log.info("Closing ClientView...")
                self.service.close()
                self.service = None
        except Exception as e:
            log.error(f"Error: {e}")
        finally:
            if isinstance(self.parent, (tk.Toplevel, tk.Tk)):
                self.parent.destroy()

    # -----------------------------------------------------------------
    # 💾 HOẠT ĐỘNG QUẢN LÝ FILE LỊCH SỬ (JSON)
    # -----------------------------------------------------------------
    def _load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                log.error(f"Read file history error: {e}")
                return []
        return []

    def _save_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.history_list, f, indent=4, ensure_ascii=False)
        except Exception as e:
            log.error(f"Save file history error: {e}")

    def _add_to_history(self, host, port, user, passwd, proto):
        prefix = "sftp://" if proto == "SFTP" else ""
        label = f"{prefix}{user}@{host}" if user else f"{prefix}{host}"

        new_entry = {
            "label": label,
            "host": host,
            "port": port,
            "user": user,
            "pass": passwd,
            "proto": proto
        }

        self.history_list = [item for item in self.history_list if item.get("label") != label]
        self.history_list.insert(0, new_entry)
        self.history_list = self.history_list[:15]
        self._save_history()

    # -----------------------------------------------------------------
    # 1. THANH KẾT NỐI QUICKCONNECT KÈM DROPDOWN MENU
    # -----------------------------------------------------------------
    def _build_top_connection_bar(self):
        conn_frame = ttk.LabelFrame(self, text=" Connection Settings ", padding=(8, 5))
        conn_frame.pack(fill="x", pady=(0, 10))

        # Protocol
        ttk.Label(conn_frame, text="Protocol:").grid(row=0, column=0, padx=2, sticky="w")
        proto_combo = ttk.Combobox(conn_frame, textvariable=self.protocol_var, values=["FTP", "SFTP"], width=6, state="readonly")
        proto_combo.grid(row=0, column=1, padx=(0, 6))
        proto_combo.bind("<<ComboboxSelected>>", self._on_protocol_change)

        # Host
        ttk.Label(conn_frame, text="Host:").grid(row=0, column=2, padx=2, sticky="w")
        ttk.Entry(conn_frame, textvariable=self.host_var, width=14).grid(row=0, column=3, padx=(0, 6))

        # Username
        ttk.Label(conn_frame, text="Username:").grid(row=0, column=4, padx=2, sticky="w")
        ttk.Entry(conn_frame, textvariable=self.user_var, width=11).grid(row=0, column=5, padx=(0, 6))

        # Password
        ttk.Label(conn_frame, text="Password:").grid(row=0, column=6, padx=2, sticky="w")
        ttk.Entry(conn_frame, textvariable=self.pass_var, show="*", width=11).grid(row=0, column=7, padx=(0, 6))

        # Port
        ttk.Label(conn_frame, text="Port:").grid(row=0, column=8, padx=2, sticky="w")
        ttk.Entry(conn_frame, textvariable=self.port_var, width=5).grid(row=0, column=9, padx=(0, 8))

        # Nút Quickconnect
        self.btn_connect = ttk.Button(conn_frame, text="Quickconnect", command=self._toggle_connection)
        self.btn_connect.grid(row=0, column=10, padx=(0, 2))

        # NÚT TAM GIÁC (▼) BẬT DROPDOWN LỊCH SỬ KẾT NỐI
        self.btn_history = ttk.Button(conn_frame, text="▼", width=3, command=self._show_history_menu)
        self.btn_history.grid(row=0, column=11, padx=2)

    def _show_history_menu(self):
        menu = tk.Menu(self, tearoff=0)

        menu.add_command(label="Clear quickconnect bar", command=self._clear_quickconnect_bar)
        menu.add_command(label="Clear history", command=self._clear_history)
        menu.add_separator()

        if not self.history_list:
            menu.add_command(label="(No history)", state="disabled")
        else:
            for item in self.history_list:
                menu.add_command(
                    label=item.get("label", ""),
                    command=lambda data=item: self._apply_history_item(data)
                )

        x = self.btn_history.winfo_rootx()
        y = self.btn_history.winfo_rooty() + self.btn_history.winfo_height()
        menu.post(x, y)

    def _apply_history_item(self, item):
        """Điền tự động thông tin tài khoản và TỰ ĐỘNG KẾT NỐI NGAY."""
        # 1. Ngắt kết nối hiện tại nếu đang kết nối
        if self.service and getattr(self.service, "is_connected", False):
            try:
                self.service.close()
            except Exception:
                pass
            self.service = None
            self.btn_connect.config(text="Quickconnect")
            self.status_lbl.config(text="Status: Disconnected")
            self._clear_tree()

        # 2. Cập nhật các thông số tài khoản mới
        self.host_var.set(item.get("host", ""))
        self.port_var.set(str(item.get("port", "21")))
        self.user_var.set(item.get("user", ""))
        self.pass_var.set(item.get("pass", ""))
        self.protocol_var.set(item.get("proto", "FTP"))

        # 3. 🟢 TỰ ĐỘNG KẾT NỐI TỚI TÀI KHOẢN MỚI NÀY
        self._toggle_connection()

    def _clear_quickconnect_bar(self):
        self.host_var.set("")
        self.port_var.set("21")
        self.user_var.set("")
        self.pass_var.set("")

    def _clear_history(self):
        self.history_list = []
        if os.path.exists(HISTORY_FILE):
            try:
                os.remove(HISTORY_FILE)
            except Exception as e:
                log.error(f"Clear file history error: {e}")
        messagebox.showinfo("History Cleared", "Clear all")

    # -----------------------------------------------------------------
    # 2. THANH ĐIỀU HƯỚNG & Ô TÌM KIẾM (PATH & SEARCH BAR)
    # -----------------------------------------------------------------
    def _build_navigation_bar(self):
        nav_frame = ttk.Frame(self)
        nav_frame.pack(fill="x", pady=(0, 8))

        self.btn_up = ttk.Button(nav_frame, text="⬆ Up", width=5, command=self._navigate_up)
        self.btn_up.pack(side="left", padx=(0, 4))

        self.btn_refresh = ttk.Button(nav_frame, text="🔄", width=3, command=self.refresh_directory)
        self.btn_refresh.pack(side="left", padx=(0, 10))

        ttk.Label(nav_frame, text="Path:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
        path_entry = ttk.Entry(nav_frame, textvariable=self.path_var)
        path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        path_entry.bind("<Return>", lambda e: self._change_directory(self.path_var.get()))

        ttk.Label(nav_frame, text="🔍 Search:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
        search_entry = ttk.Entry(nav_frame, textvariable=self.search_var, width=20)
        search_entry.pack(side="left")

    # -----------------------------------------------------------------
    # 3. TREEVIEW BẢNG FILE / THƯ MỤC
    # -----------------------------------------------------------------
    def _build_file_treeview(self):
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True)

        # 🟢 Thêm cột 'date'
        columns = ("name", "type", "size", "date")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("name", text="Filename / Folder Name", anchor="w")
        self.tree.heading("type", text="Type", anchor="center")
        self.tree.heading("size", text="Size", anchor="center")
        self.tree.heading("date", text="Date Modified", anchor="center")

        self.tree.column("name", width=600, stretch=True)
        self.tree.column("type", width=30, anchor="center")
        self.tree.column("size", width=30, anchor="center")
        self.tree.column("date", width=50, anchor="center")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self._on_double_click)

    # -----------------------------------------------------------------
    # 4. ACTION BAR (NÚT DOWNLOAD, UPLOAD KÈM THANH TIẾN ĐỘ PROGRESS BAR)
    # -----------------------------------------------------------------
    def _build_bottom_action_bar(self):
        action_frame = ttk.Frame(self)
        action_frame.pack(fill="x", pady=(8, 0))

        # Status Text
        self.status_lbl = ttk.Label(action_frame, text="Status: Disconnected", font=("Segoe UI", 8))
        self.status_lbl.pack(side="left", padx=(0, 10))

        # THANH PROGESS BAR TIẾN ĐỘ CHẠY REALTIME
        self.progress_bar = ttk.Progressbar(action_frame, orient="horizontal", mode="determinate", length=180)
        self.progress_bar.pack(side="left", padx=5)
        self.progress_bar.pack_forget()

        self.btn_download = ttk.Button(action_frame, text="⬇ Download", command=self._download_selected)
        self.btn_download.pack(side="right", padx=3)

        self.btn_upload = ttk.Button(action_frame, text="⬆ Upload", command=self._upload_file)
        #self.btn_upload.pack(side="right", padx=3)

    # -----------------------------------------------------------------
    # 🟢 CALLBACK HÀM CẬP NHẬT PROGRESS BAR REALTIME
    # -----------------------------------------------------------------
    def _progress_callback(self, transferred, total, label="Transferring"):
        """Hàm cập nhật phần trăm tiến độ truyền dữ liệu an toàn từ Thread phụ."""
        if total > 0:
            percent = (transferred / total) * 100
            
            trans_mb = transferred / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            
            status_text = f"⏳ {label}: {percent:.1f}% ({trans_mb:.2f}MB / {total_mb:.2f}MB)"

            def update_gui():
                if self.winfo_exists():
                    self.progress_bar['value'] = percent
                    self.status_lbl.config(text=status_text)

            self.after(0, update_gui)

    def _reset_progress(self):
        """Khôi phục trạng thái thanh Progress Bar."""
        def reset():
            if self.winfo_exists():
                self.progress_bar['value'] = 0
                self.progress_bar.pack_forget()
        self.after(0, reset)

    # -----------------------------------------------------------------
    # ⚙️ LOGIC KẾT NỐI & XỬ LÝ DỮ LIỆU
    # -----------------------------------------------------------------
    def _on_protocol_change(self, event=None):
        proto = self.protocol_var.get()
        if proto == "FTP":
            self.port_var.set("21")
        else:
            self.port_var.set("22")

    def _toggle_connection(self):
        if self.service and getattr(self.service, "is_connected", False):
            self.service.close()
            self.service = None
            self.btn_connect.config(text="Quickconnect")
            self.status_lbl.config(text="Status: Disconnected")
            self._clear_tree()
            return

        host = self.host_var.get().strip()
        port = int(self.port_var.get().strip())
        user = self.user_var.get().strip()
        passwd = self.pass_var.get()
        proto = self.protocol_var.get()

        if not host:
            messagebox.showwarning("Warning", "Input IP!")
            return

        self.status_lbl.config(text=f"Connecting to {host}:{port} via {proto}...")
        self.btn_connect.config(state="disabled")

        def run_connect():
            if proto == "FTP":
                self.service = self.ftp_service_cls
            else:
                self.service = self.sftp_service_cls

            success = self.service.connect(host=host, username=user, password=passwd) if proto == "SFTP" else self.service.connect(host=host, username=user, password=passwd)

            def update_ui():
                if not self.winfo_exists():
                    return
                self.btn_connect.config(state="normal")
                if success:
                    self.btn_connect.config(text="🔴 Disconnect")
                    self.status_lbl.config(text=f"✅ Connected to {host} ({proto})")
                    self._add_to_history(host, port, user, passwd, proto)
                    self.current_remote_dir = "/"
                    self.refresh_directory()
                else:
                    self.status_lbl.config(text="❌ Connection failed!")
                    messagebox.showerror("Error", f"Can't connect to {proto} Server!")

            self.after(0, update_ui)

        threading.Thread(target=run_connect, daemon=True).start()

    def refresh_directory(self):
        if not self.service or not getattr(self.service, "is_connected", False):
            return

        self.status_lbl.config(text=f"⏳ Reading directory '{self.current_remote_dir}'...")
        self._set_controls_state("disabled")

        def run_refresh():
            items_result = []
            try:
                clean_dir = posixpath.normpath(self.current_remote_dir)
                
                # 🟢 Gọi trực tiếp hàm listdir() trả về danh sách Dictionary chuẩn
                items_result = self.service.listdir(clean_dir)

            except Exception as e:
                log.error(f"Error reading directory: {e}")

            def update_ui():
                if not self.winfo_exists():
                    return
                self.all_items = items_result
                self._render_tree_items(self.all_items)
                self.path_var.set(self.current_remote_dir)
                self.status_lbl.config(text=f"✅ Loaded {len(self.all_items)} items.")
                self._set_controls_state("normal")

            self.after(0, update_ui)

        threading.Thread(target=run_refresh, daemon=True).start()

    def _render_tree_items(self, items):
        self._clear_tree()
        for item in items:
            # 🟢 Truy cập dữ liệu Dictionary an toàn
            name = item.get("name", "")
            is_dir = item.get("is_dir", False)
            size_bytes = item.get("size", 0)
            date_str = item.get("date", "N/A")

            if is_dir:
                display_name = f"📁 {name}"
                file_type = "Folder"
                file_size = "--"
            else:
                display_name = f"📄 {name}"
                file_type = name.split('.')[-1].upper() if '.' in name else "File"
                
                # Format dung lượng file đẹp mắt
                if size_bytes > 1024 * 1024:
                    file_size = f"{size_bytes / (1024 * 1024):.2f} MB"
                elif size_bytes > 1024:
                    file_size = f"{size_bytes / 1024:.1f} KB"
                else:
                    file_size = f"{size_bytes} B"

            # Đẩy dữ liệu vào Treeview (Tags giữ nguyên 'dir' hoặc 'file' để hỗ trợ double-click)
            self.tree.insert("", "end", values=(display_name, file_type, file_size, date_str), tags=(name, "dir" if is_dir else "file"))

            '''def update_ui():
                if not self.winfo_exists():
                    return
                self.all_items = items_result
                self._render_tree_items(self.all_items)
                self.path_var.set(self.current_remote_dir)
                self.status_lbl.config(text=f"✅ Loaded {len(self.all_items)} items.")
                self._set_controls_state("normal")

            self.after(0, update_ui)

        threading.Thread(target=run_refresh, daemon=True).start()'''

    def __render_tree_items(self, items):
        self._clear_tree()
        for item in items:
            name = item["name"]
            is_dir = item["is_dir"]
            
            # Format hiển thị dung lượng
            if is_dir:
                display_name = f"📁 {name}"
                file_type = "Folder"
                file_size = "--"
            else:
                display_name = f"📄 {name}"
                file_type = name.split('.')[-1].upper() if '.' in name else "File"
                size_bytes = item["size"]
                file_size = f"{size_bytes / (1024*1024):.2f} MB" if size_bytes > 1024*1024 else f"{size_bytes / 1024:.1f} KB"

            date_str = item.get("date", "N/A")

            # Insert dòng vào Treeview (nếu thêm cột Date)
            self.tree.insert("", "end", values=(display_name, file_type, file_size, date_str), tags=(name, "dir" if is_dir else "file"))

    def _clear_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _set_controls_state(self, state_str):
        if not self.winfo_exists():
            return
        self.btn_up.config(state=state_str)
        self.btn_refresh.config(state=state_str)
        self.btn_download.config(state=state_str)
        self.btn_upload.config(state=state_str)

    # -----------------------------------------------------------------
    # 🔍 TÌM KIẾM LIVE & ĐIỀU HƯỚNG
    # -----------------------------------------------------------------
    def _on_search_change(self, *args):
        query = self.search_var.get().strip().lower()
        if not query:
            self._render_tree_items(self.all_items)
            return

        filtered = [item for item in self.all_items if query in item[0].lower()]
        self._render_tree_items(filtered)

    def _on_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        selected = self.tree.selection()
        if not selected:
            return

        item_tags = self.tree.item(selected[0], "tags")
        if not item_tags:
            return

        raw_name = item_tags[0]
        is_dir = "dir" in item_tags

        if is_dir:
            new_dir = posixpath.normpath(posixpath.join(self.current_remote_dir, raw_name))
            self._change_directory(new_dir)

    def _change_directory(self, target_dir):
        self.current_remote_dir = target_dir
        self.search_var.set("")
        self.refresh_directory()

    def _navigate_up(self):
        if self.current_remote_dir in ["/", ""]:
            return
        parent_dir = posixpath.dirname(self.current_remote_dir)
        self._change_directory(parent_dir)

    # -----------------------------------------------------------------
    # 📥 DOWNLOAD VỚI THANH CHẠY % (THREADED)
    # -----------------------------------------------------------------
    def _download_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Selecte target folder")
            return

        item_tags = self.tree.item(selected[0], "tags")
        raw_name = item_tags[0]
        is_dir = "dir" in item_tags

        save_dir = filedialog.askdirectory(title="Folder save local")
        if not save_dir:
            return

        remote_target = posixpath.normpath(posixpath.join(self.current_remote_dir, raw_name))
        self._set_controls_state("disabled")

        self.progress_bar.pack(side="left", padx=5)
        self.progress_bar['value'] = 0

        def run_download():
            cb = lambda transferred, total: self._progress_callback(transferred, total, label=f"Downloading '{raw_name}'")
            
            if is_dir:
                success = self.service.download_directory(remote_target, save_dir, callback=cb) if hasattr(self.service, "download_directory") else False
            else:
                success = self.service.download_file(remote_target, save_dir, callback=cb) if hasattr(self.service, "download_file") else False

            def finish():
                if not self.winfo_exists():
                    return
                self._set_controls_state("normal")
                self._reset_progress()
                if success:
                    self.status_lbl.config(text=f"✅ Download completed: {raw_name}")
                    #messagebox.showinfo("Success", f"Đã tải thành công '{raw_name}'!")
                else:
                    self.status_lbl.config(text=f"❌ Download failed: {raw_name}")
                    #messagebox.showerror("Error", f"Tải về thất bại cho '{raw_name}'!")

            self.after(0, finish)

        threading.Thread(target=run_download, daemon=True).start()

    # -----------------------------------------------------------------
    # 📤 UPLOAD VỚI THANH CHẠY % (THREADED)
    # -----------------------------------------------------------------
    def _upload_file(self):
        local_file = ""
        if self.current_os == "Windows":
            try:
                dialog = win32com.client.Dispatch("Shell.Application")
                folder = dialog.BrowseForFolder(0, "Selecte file or folder to Upload", 0x4000, 0)
                if not folder:
                    return
                local_file = folder.Self.Path
            except Exception:
                return None
        if self.current_os == "Linux":
            try:
        # Gọi zenity của Linux
                cmd = ["zenity", "--file-selection", "--title=Selecte file or folder to Upload"]
                local_file = subprocess.check_output(cmd, text=True).strip()
                return local_file
            except Exception:
                return None

        if not local_file or not os.path.exists(local_file):
            return

        filename = os.path.basename(local_file)
        self._set_controls_state("disabled")

        self.progress_bar.pack(side="left", padx=5)
        self.progress_bar['value'] = 0

        def run_upload():
            cb = lambda transferred, total: self._progress_callback(transferred, total, label=f"Uploading '{filename}'")

            if os.path.isdir(local_file):
                success = self.service.upload_directory(local_file, self.current_remote_dir, callback=cb) if hasattr(self.service, "upload_directory") else False
            else:
                success = self.service.upload_file(local_file, self.current_remote_dir, callback=cb) if hasattr(self.service, "upload_file") else False

            def finish():
                if not self.winfo_exists():
                    return
                self._set_controls_state("normal")
                self._reset_progress()
                if success:
                    self.status_lbl.config(text=f"✅ Upload completed: {filename}")
                    #messagebox.showinfo("Success", f"Upload '{filename}' thành công!")
                    self.refresh_directory()
                else:
                    self.status_lbl.config(text=f"❌ Upload failed: {filename}")
                    #messagebox.showerror("Error", f"Upload '{filename}' thất bại!")

            self.after(0, finish)

        threading.Thread(target=run_upload, daemon=True).start()