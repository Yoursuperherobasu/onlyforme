"""Debug logger that writes to a file for tracing tool resolution issues."""

import os
from datetime import datetime
from pathlib import Path

# Log file paths - use absolute path in langbuilder root
LOG_DIR = Path("E:/devteam_langbuilder/my_langbuilder/langbuilder/logs")
DEBUG_LOG_FILE = LOG_DIR / "tools_debug.log"
INFO_LOG_FILE = LOG_DIR / "info.log"

# Ensure log directory exists
LOG_DIR.mkdir(parents=True, exist_ok=True)

def _write_to_file(log_file: Path, message: str) -> None:
    """Write message to a log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    log_line = f"[{timestamp}] {message}\n"
    
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print(f"❌ Failed to write to log file {log_file}: {e}")

def debug_log(message: str, also_print: bool = True) -> None:
    """Write debug message to file and optionally print.
    
    Args:
        message: The debug message to log
        also_print: Whether to also print to stdout
    """
    _write_to_file(DEBUG_LOG_FILE, message)
    
    if also_print:
        print(message)

def info_log(message: str, also_print: bool = False) -> None:
    """Write info message to info log file.
    
    Args:
        message: The info message to log
        also_print: Whether to also print to stdout
    """
    _write_to_file(INFO_LOG_FILE, f"[INFO] {message}")
    
    if also_print:
        print(f"[INFO] {message}")

def error_log(message: str, also_print: bool = True) -> None:
    """Write error message to info log file.
    
    Args:
        message: The error message to log
        also_print: Whether to also print to stdout
    """
    _write_to_file(INFO_LOG_FILE, f"[ERROR] {message}")
    
    if also_print:
        print(f"[ERROR] {message}")

def clear_debug_log() -> None:
    """Clear the debug log file."""
    try:
        if DEBUG_LOG_FILE.exists():
            DEBUG_LOG_FILE.unlink()
        with open(DEBUG_LOG_FILE, "w", encoding="utf-8") as f:
            f.write(f"=== Debug Log Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
    except Exception as e:
        print(f"Failed to clear debug log: {e}")

def clear_info_log() -> None:
    """Clear the info log file."""
    try:
        if INFO_LOG_FILE.exists():
            INFO_LOG_FILE.unlink()
        with open(INFO_LOG_FILE, "w", encoding="utf-8") as f:
            f.write(f"=== Info Log Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
    except Exception as e:
        print(f"Failed to clear info log: {e}")

def get_log_paths() -> dict:
    """Get the paths to the log files."""
    return {
        "debug": str(DEBUG_LOG_FILE),
        "info": str(INFO_LOG_FILE),
        "log_dir": str(LOG_DIR)
    }

def get_log_path() -> str:
    """Get the path to the debug log file (for backward compatibility)."""
    return str(DEBUG_LOG_FILE)

