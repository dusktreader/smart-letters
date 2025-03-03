from functools import wraps
from pathlib import Path

from smart_letters.exceptions import Abort


CACHE_DIR: Path = Path.home() / ".local/share/smart-letters"
BACKUP_DIR: Path = CACHE_DIR / "backup"


def init_cache(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            CACHE_DIR.mkdir(exist_ok=True, parents=True)
            BACKUP_DIR.mkdir(exist_ok=True)
            info_file = CACHE_DIR / "info.txt"
            info_file.write_text(
                """
                This directory is used by Smart Letters for its cache.

                The sub-directory, backup, is used for storing intermediate letters.
                Files are named by timestamp in this folder.
                """
            )
        except Exception:
            raise Abort(
                """
                Cache directory {cache_dir} doesn't exist, is not writable,
                or could not be created.

                Please check your home directory permissions and try again.
                """,
                subject="Non-writable cache dir",
                log_message="Non-writable cache dir",
            )
        return func(*args, **kwargs)

    return wrapper
