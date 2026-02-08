import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(log_name="running_app",log_dir="AppLogs",level=logging.INFO):
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"{log_name}.log")

    logger = logging.getLogger()   # root logger
    logger.setLevel(level)

    if logger.handlers:
        return logger  # tránh add handler nhiều lần

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] "
        "- %(message)s",datefmt="%Y-%m-%d %H:%M:%S"
    )

    # ---- File handler (ghi ra file) ----
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,   # 5MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    # ---- Console handler (tuỳ chọn) ----
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger