# auto delete logic
# auto delete file after 10 minutes


import threading
import time
from pathlib import Path


def cleanup_folder(folder_path, max_age_seconds=600):
    """
    Delete files in the folder that are older than max_age_seconds.
    """
    now = time.time()
    folder = Path(folder_path)
    if not folder.exists():
        return
    for file_path in folder.iterdir():
        if file_path.is_file():
            if now - file_path.stat().st_mtime > max_age_seconds:
                try:
                    file_path.unlink()
                    print(f"Auto-deleted old file: {file_path}")
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")


def start_cleanup_scheduler(folder_path, interval_seconds=600):
    """
    Start a periodic cleanup scheduler for the folder.
    """
    def cleanup_task():
        cleanup_folder(folder_path, interval_seconds)
        # Schedule next run
        timer = threading.Timer(interval_seconds, cleanup_task)
        timer.daemon = True
        timer.start()

    # Run first cleanup
    cleanup_task()
