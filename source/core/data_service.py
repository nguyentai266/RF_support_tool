import os
import posixpath
from stat import S_ISDIR
import paramiko
from ftplib import FTP, error_perm, error_temp
from core.logger import logger as log
import datetime

class SFTPService:
    """Service xử lý kết nối, Upload/Download File & Folder qua SFTP."""
    def __init__(self):
        self.ssh: paramiko.SSHClient | None = None
        self.sftp: paramiko.SFTPClient | None = None
        self.is_connected = False

    def connect(self, 
                host: str, 
                port: int = 22, 
                username: str = "", 
                password: str = "", 
                timeout: int = 10) -> bool:
        """Kết nối tới SFTP Server."""
        try:
            log.info(f"Connecting to SFTP server {host}:{port}...")
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            self.ssh.connect(hostname=host, port=port, username=username, password=password, timeout=timeout)
            self.sftp = self.ssh.open_sftp()
            
            self.is_connected = True
            log.info("Connected SFTP successfully.")
            return True
        except Exception as e:
            log.error(f"Connection SFTP error: {e}")
            self.close()
            return False

    def listdir(self, remote_path: str = ".") -> list[dict]:
    
        if not self.is_connected or not self.sftp:
            log.error("SFTP not connected.")
            return []
        try:
            clean_path = posixpath.normpath(remote_path) if remote_path else "."
            items = []
            
            # listdir_attr() trả về các đối tượng chứa thuộc tính chi tiết
            for attr in self.sftp.listdir_attr(clean_path):
                if attr.filename in [".", ".."]:
                    continue
                
                # Format ngày tháng từ Unix timestamp (st_mtime)
                mtime_dt = datetime.datetime.fromtimestamp(attr.st_mtime)
                date_str = mtime_dt.strftime("%Y-%m-%d %H:%M:%S") if attr.st_mtime else "N/A"
                
                is_dir = S_ISDIR(attr.st_mode)
                
                items.append({
                    "name": attr.filename,
                    "is_dir": is_dir,
                    "size": 0 if is_dir else (attr.st_size or 0),
                    "date": date_str
                })
                
            return items
        except Exception as e:
            log.error(f"Error list remote dir '{remote_path}': {e}")
            return []

    def _ensure_remote_dir(self, remote_dir: str):
        """Tự động tạo cấu trúc thư mục đệ quy trên SFTP Server nếu chưa tồn tại."""
        if not self.sftp:
            return
        dirs = [d for d in remote_dir.split('/') if d]
        path = ""
        if remote_dir.startswith('/'):
            path = "/"
            
        for d in dirs:
            path = posixpath.join(path, d)
            try:
                self.sftp.stat(path)
            except FileNotFoundError:
                try:
                    self.sftp.mkdir(path)
                except Exception:
                    pass

    
    def upload_file(self, local_file: str, remote_path: str,callback=None) -> bool:
        """Upload 1 File từ local lên remote path."""
        if not self.is_connected or not self.sftp:
            log.error("SFTP not connected.")
            return False

        if not os.path.isfile(local_file):
            log.error(f"Local file does not exist: {local_file}")
            return False

        try:
            clean_remote = posixpath.normpath(remote_path)
            try:
                self.sftp.chdir(remote_path)
            except:
                self.sftp.mkdir(remote_path)
                self.sftp.chdir(remote_path)
            # Kiểm tra xem remote_path là Thư mục hay File
            is_dir = False
            try:
                stat = self.sftp.stat(clean_remote)
                is_dir = S_ISDIR(stat.st_mode) # type: ignore
            except FileNotFoundError:
                if remote_path.endswith('/'):
                    is_dir = True

            if is_dir:
                self._ensure_remote_dir(clean_remote)
                target_file = posixpath.join(clean_remote, os.path.basename(local_file))
            else:
                parent_dir = posixpath.dirname(clean_remote)
                if parent_dir:
                    self._ensure_remote_dir(parent_dir)
                target_file = clean_remote

            self.sftp.put(local_file, target_file,callback=callback if callable(callback) else None)
            log.info(f"SFTP Uploaded File: {local_file} -> {target_file}")
            return True
        except Exception as e:
            log.error(f"SFTP Uploading file error ({local_file}): {e}")
            return False

    def upload_directory(self, local_dir: str, remote_dir: str,callback=None) -> bool:
        """Upload TOÀN BỘ THƯ MỤC từ local lên SFTP Server (đệ quy)."""
        if not self.is_connected or not self.sftp:
            return False

        if not os.path.isdir(local_dir):
            log.error(f"Local directory does not exist: {local_dir}")
            return False

        try:
            folder_name = os.path.basename(os.path.normpath(local_dir))
            target_remote_base = posixpath.join(posixpath.normpath(remote_dir), folder_name)

            for root, _, files in os.walk(local_dir):
                rel_path = os.path.relpath(root, local_dir)
                remote_sub_dir = target_remote_base if rel_path == "." else posixpath.join(target_remote_base, rel_path.replace("\\", "/"))
                
                self._ensure_remote_dir(remote_sub_dir)

                for file in files:
                    local_file_path = os.path.join(root, file)
                    remote_file_path = posixpath.join(remote_sub_dir, file)
                    self.sftp.put(local_file_path, remote_file_path,callback=callback if callable(callback) else None)

            log.info(f"SFTP Uploaded Directory: {local_dir} -> {target_remote_base}")
            return True
        except Exception as e:
            log.error(f"SFTP Uploading directory error ({local_dir}): {e}")
            return False

    # --- 🔵 DOWNLOAD LOGIC ---
    def download_file(self, remote_file: str, local_path: str,callback = None) -> bool:
        """Download 1 File từ SFTP Server về Local."""
        if not self.is_connected or not self.sftp:
            log.error("SFTP not connected.")
            return False

        try:
            clean_remote = posixpath.normpath(remote_file)
            
            if os.path.isdir(local_path) or local_path.endswith(('/', '\\')):
                filename = posixpath.basename(clean_remote)
                target_local_file = os.path.join(local_path, filename)
            else:
                target_local_file = local_path

            os.makedirs(os.path.dirname(os.path.abspath(target_local_file)), exist_ok=True)

            self.sftp.get(clean_remote, target_local_file,callback=callback if callable(callback) else None)
            log.info(f"SFTP Downloaded File: {clean_remote} -> {target_local_file}")
            return True
        except Exception as e:
            log.error(f"SFTP Downloading file error ({remote_file}): {e}")
            return False

    def download_directory(self, remote_dir: str, local_dir: str,callback =None) -> bool:
        """Download TOÀN BỘ THƯ MỤC từ SFTP Server về Local (đệ quy)."""
        if not self.is_connected or not self.sftp:
            return False

        try:
            clean_remote = posixpath.normpath(remote_dir)
            folder_name = posixpath.basename(clean_remote)
            target_local_dir = os.path.join(local_dir, folder_name)
            os.makedirs(target_local_dir, exist_ok=True)

            for item in self.sftp.listdir_attr(clean_remote):
                item_remote_path = posixpath.join(clean_remote, item.filename)
                
                if S_ISDIR(item.st_mode):   # type: ignore
                    self.download_directory(item_remote_path, target_local_dir)
                else:
                    item_local_path = os.path.join(target_local_dir, item.filename)
                    self.sftp.get(item_remote_path, item_local_path,callback=callback if callable(callback) else None)

            log.info(f"SFTP Downloaded Directory: {clean_remote} -> {target_local_dir}")
            return True
        except Exception as e:
            log.error(f"SFTP Downloading directory error ({remote_dir}): {e}")
            return False

    def close(self):
        """Tắt kết nối an toàn."""
        self.is_connected = False
        if self.sftp:
            try:
                self.sftp.close()
            except Exception:
                pass
            self.sftp = None

        if self.ssh:
            try:
                self.ssh.close()
            except Exception:
                pass
            self.ssh = None
            
        log.info("Closed SFTP connection.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# =========================================================================
# 🛠️ CLASS QUẢN LÝ FTP SERVICE
# =========================================================================
class FTPService:
    """Service xử lý kết nối, Upload/Download File & Folder qua FTP."""

    def __init__(self, port: int = 21, timeout: int = 10):
        self.host = ""
        self.port = port
        self.timeout = timeout
        self.ftp: FTP | None = None
        self.is_connected = False

    def connect(self,host: str, username: str = "", password: str = "") -> bool:
        """Kết nối tới FTP Server."""
        try:
            self.ftp = FTP(host=host)
            log.info(f"Connecting to FTP Server {self.host}:{self.port}...")
            self.ftp.connect(host=self.host, port=self.port, timeout=self.timeout)
            self.ftp.login(user=username, passwd=password)
            self.is_connected = True
            log.info('Connected FTP server successfully.')
            return True
        except (error_perm, error_temp, Exception) as e:
            log.error(f"Connection FTP server error: {e}")
            self.is_connected = False
            self.close()
            return False



    def listdir(self, remote_dir: str = ".") -> list[dict]:
    
        if not self.is_connected or not self.ftp:
            return []
        try:
            clean_dir = posixpath.normpath(remote_dir) if remote_dir else "."
            items = []

            # Thử dùng mlsd() - Chuẩn FTP hiện đại (RFC 3659)
            try:
                for name, facts in self.ftp.mlsd(clean_dir):
                    if name in [".", ".."]:
                        continue
                    
                    is_dir = facts.get("type") in ["dir", "cdir", "pdir"]
                    size = 0 if is_dir else int(facts.get("size", 0))
                    
                    # facts.get("modify") dạng YYYYMMDDHHMMSS
                    raw_fact_date = facts.get("modify", "")
                    date_str = "N/A"
                    if len(raw_fact_date) >= 14:
                        try:
                            dt = datetime.datetime.strptime(raw_fact_date[:14], "%Y%m%d%H%M%S")
                            date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            pass

                    items.append({
                        "name": name,
                        "is_dir": is_dir,
                        "size": size,
                        "date": date_str
                    })
            except Exception:
                # Fallback nếu FTP server không hỗ trợ mlsd(): Dùng nlst() kết hợp lệnh SIZE/MDTM
                raw_names = self.ftp.nlst(clean_dir)
                for item_path in raw_names:
                    name = posixpath.basename(item_path.rstrip("/"))
                    if not name or name in [".", ".."]:
                        continue
                    
                    full_path = posixpath.join(clean_dir, name)
                    
                    # Kiểm tra dung lượng
                    size = 0
                    is_dir = False
                    try:
                        size = self.ftp.size(full_path) or 0
                    except Exception:
                        is_dir = True # Không lấy được SIZE thường là Folder

                    # Lấy ngày sửa đổi MDTM
                    date_str = "N/A"
                    try:
                        mdtm_resp = self.ftp.sendcmd(f"MDTM {full_path}")
                        if mdtm_resp.startswith("213 "):
                            raw_date = mdtm_resp[4:].strip()[:14]
                            dt = datetime.datetime.strptime(raw_date, "%Y%m%d%H%M%S")
                            date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        pass

                    items.append({
                        "name": name,
                        "is_dir": is_dir,
                        "size": 0 if is_dir else size,
                        "date": date_str
                    })

            return items
        except Exception as e:
            log.error(f"Can't read folder {remote_dir}: {e}")
            return []

    def _ensure_remote_dir(self, remote_dir: str):
        """Tự động tạo thư mục đệ quy trên FTP Server nếu chưa tồn tại."""
        if not self.ftp:
            return
        dirs = [d for d in remote_dir.split('/') if d]
        path = ""
        if remote_dir.startswith('/'):
            path = "/"

        for d in dirs:
            path = posixpath.join(path, d)
            try:
                self.ftp.cwd(path)
            except error_perm:
                try:
                    self.ftp.mkd(path)
                except Exception:
                    pass

    # --- 🟢 UPLOAD LOGIC ---
    def upload_file(self, local_file: str, remote_path: str, callback=None) -> bool:
        """Upload 1 File từ local lên FTP Server hỗ trợ Progress Callback."""
        if not self.is_connected or not self.ftp:
            log.info("FTP server not connected")
            return False

        if not os.path.isfile(local_file):
            log.info(f"File does not exist: {local_file}")
            return False

        try:
            clean_remote = posixpath.normpath(remote_path)
            
            # Kiểm tra xem remote_path là Thư mục hay File
            is_dir = False
            try:
                self.ftp.cwd(clean_remote)
                is_dir = True
            except error_perm:
                if remote_path.endswith('/'):
                    is_dir = True

            if is_dir:
                self._ensure_remote_dir(clean_remote)
                self.ftp.cwd(clean_remote)
                target_filename = os.path.basename(local_file)
            else:
                parent_dir = posixpath.dirname(clean_remote)
                if parent_dir:
                    self._ensure_remote_dir(parent_dir)
                    self.ftp.cwd(parent_dir)
                target_filename = posixpath.basename(clean_remote)

            total_bytes = os.path.getsize(local_file)
            transferred_bytes = 0

            # Wrapper callback chuyển đổi chunk -> total transferred
            def read_and_count(block):
                nonlocal transferred_bytes
                transferred_bytes += len(block)
                if callback and callable(callback):
                    callback(transferred_bytes, total_bytes)

            with open(local_file, "rb") as f:
                self.ftp.storbinary(f"STOR {target_filename}", f, blocksize=8192, callback=read_and_count)

            log.info(f"FTP Uploaded File: {local_file} -> {clean_remote}")
            return True
        except Exception as e:
            log.error(f"FTP Uploading file error ({local_file}): {e}")
            return False

    def upload_directory(self, local_dir: str, remote_dir: str, callback=None) -> bool:
        """Upload TOÀN BỘ THƯ MỤC từ local lên FTP Server (đệ quy) có Callback."""
        if not self.is_connected or not self.ftp:
            return False

        if not os.path.isdir(local_dir):
            log.error(f"Local directory does not exist: {local_dir}")
            return False

        try:
            folder_name = os.path.basename(os.path.normpath(local_dir))
            target_remote_base = posixpath.join(posixpath.normpath(remote_dir), folder_name)

            for root, _, files in os.walk(local_dir):
                rel_path = os.path.relpath(root, local_dir)
                remote_sub_dir = target_remote_base if rel_path == "." else posixpath.join(target_remote_base, rel_path.replace("\\", "/"))

                self._ensure_remote_dir(remote_sub_dir)
                self.ftp.cwd(remote_sub_dir)

                for file in files:
                    local_file_path = os.path.join(root, file)
                    self.upload_file(local_file_path, remote_sub_dir, callback=callback)

            log.info(f"FTP Uploaded Directory: {local_dir} -> {target_remote_base}")
            return True
        except Exception as e:
            log.error(f"FTP Uploading directory error ({local_dir}): {e}")
            return False

    # --- 🔵 DOWNLOAD LOGIC CÓ CALLBACK ---
    def download_file(self, remote_file: str, local_path: str, callback=None) -> bool:
        """Download 1 File từ FTP Server về Local hỗ trợ Progress Callback."""
        if not self.is_connected or not self.ftp:
            log.info("FTP server not connected")
            return False

        try:
            clean_remote_path = posixpath.normpath(remote_file)
            
            if os.path.isdir(local_path) or local_path.endswith(("/", "\\")):
                filename = posixpath.basename(clean_remote_path)
                local_file_target = os.path.join(local_path, filename)
            else:
                local_file_target = local_path

            os.makedirs(os.path.dirname(os.path.abspath(local_file_target)), exist_ok=True)

            # Lấy dung lượng file trên FTP Server
            total_bytes = 0
            try:
                total_bytes = self.ftp.size(clean_remote_path) or 0
            except Exception:
                total_bytes = 0

            transferred_bytes = 0

            with open(local_file_target, "wb") as f:
                def write_and_count(block):
                    nonlocal transferred_bytes
                    f.write(block)
                    transferred_bytes += len(block)
                    if callback and callable(callback):
                        callback(transferred_bytes, total_bytes)

                cmd = f"RETR {clean_remote_path}"
                self.ftp.retrbinary(cmd, write_and_count, blocksize=8192)

            log.info(f"FTP Downloaded File: {clean_remote_path} -> {local_file_target}")
            return True
        except Exception as e:
            log.error(f"FTP Downloading file error ({remote_file}): {e}")
            return False

    def download_directory(self, remote_dir: str, local_dir: str, callback=None) -> bool:
        """Download TOÀN BỘ THƯ MỤC từ FTP Server về Local (đệ quy) có Callback."""
        if not self.is_connected or not self.ftp:
            return False

        try:
            clean_remote_dir = posixpath.normpath(remote_dir)
            target_folder_name = posixpath.basename(clean_remote_dir)
            local_target_dir = os.path.join(local_dir, target_folder_name)
            os.makedirs(local_target_dir, exist_ok=True)

            items = self.ftp.nlst(clean_remote_dir)

            for item in items:
                item_name = posixpath.basename(item)
                if item_name in [".", ".."]:
                    continue

                full_remote_item = posixpath.join(clean_remote_dir, item_name)

                # Kiểm tra item là Folder hay File bằng cwd
                is_dir = False
                try:
                    current_pwd = self.ftp.pwd()
                    self.ftp.cwd(full_remote_item)
                    self.ftp.cwd(current_pwd)
                    is_dir = True
                except error_perm:
                    is_dir = False

                if is_dir:
                    self.download_directory(full_remote_item, local_target_dir, callback=callback)
                else:
                    self.download_file(full_remote_item, local_target_dir, callback=callback)

            log.info(f"FTP Downloaded Directory: {clean_remote_dir} -> {local_target_dir}")
            return True

        except Exception as e:
            log.error(f"FTP Downloading directory error ({remote_dir}): {e}")
            return False

    def close(self):
        """Tắt kết nối an toàn."""
        if self.ftp:
            try:
                self.ftp.quit()
            except Exception:
                self.ftp.close()
            finally:
                self.ftp = None
                self.is_connected = False
                log.info("Closed FTP connection.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()