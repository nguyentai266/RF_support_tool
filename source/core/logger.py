import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logger(logger_name="log", log_filename="system.log"):
   
    if not os.path.exists('Log'):
        os.makedirs('Log')

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] --> %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        f'Log/{log_filename}', maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
    
    return logger
    
logger = setup_logger(logger_name="app", log_filename="app.log")
