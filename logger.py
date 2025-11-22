import logging
import sys
from datetime import datetime
from pathlib import Path

class PhotoSyncLogger:
    def __init__(self, log_dir="./data/logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create logger
        self.logger = logging.getLogger("PhotoSync")
        self.logger.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_format)
        
        # File handler
        log_file = self.log_dir / f"photosync_{datetime.now():%Y%m%d}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_format)
        
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
    
    def info(self, msg):
        self.logger.info(msg)
    
    def error(self, msg, exc_info=False):
        self.logger.error(msg, exc_info=exc_info)
    
    def warning(self, msg):
        self.logger.warning(msg)
    
    def debug(self, msg):
        self.logger.debug(msg)

# Global logger instance
logger = None

def get_logger():
    global logger
    if logger is None:
        logger = PhotoSyncLogger()
    return logger
