import argparse
import logging
import os
import signal
import shutil
import sys
import time
import webbrowser
from threading import Thread

logger = logging.getLogger(__name__)


def open_browser(port: int, delay: float = 2.0) -> None:
    def _open():
        time.sleep(delay)
        webbrowser.open(f"http://localhost:{port}")
    Thread(target=_open, daemon=True).start()


def setup_signal_handlers() -> None:
    def _handler(signum, frame):
        logger.info("Received signal %s, shutting down gracefully...", signum)
        sys.exit(0)

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, _handler)


class _NullStream:
    """A no-op stream that absorbs all writes without errors.

    Used to replace stdout/stderr in frozen GUI mode so that
    uvicorn's logging (which calls isatty(), write(), etc.)
    does not crash when no console is attached.
    """
    def write(self, s):
        pass
    def flush(self):
        pass
    def isatty(self):
        return False
    def fileno(self):
        raise OSError("No console")
    def close(self):
        pass


def main() -> None:
    # --- Suppress console output in frozen GUI mode to prevent black window ---
    _is_frozen = getattr(sys, 'frozen', False)
    if _is_frozen and sys.platform == "win32":
        # Replace stdout/stderr with a null stream before any print/logging.
        # This prevents Windows from allocating a visible console window.
        # Logs still go to file via RotatingFileHandler in main.py.
        sys.stdout = _NullStream()
        sys.stderr = _NullStream()

    # --- Global crash handler: write to crash.log before process exits ---
    import traceback as _traceback
    _app_dir = os.path.dirname(sys.executable) if _is_frozen else os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    def _excepthook(exc_type, exc_value, exc_tb):
        crash_log = os.path.join(_app_dir, 'data', 'logs', 'crash.log')
        os.makedirs(os.path.dirname(crash_log), exist_ok=True)
        with open(crash_log, 'a', encoding='utf-8') as f:
            f.write(f"\n{'=' * 60}\n")
            import datetime
            f.write(f"Crash at {datetime.datetime.now()}\n")
            _traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
        _traceback.print_exception(exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook

    parser = argparse.ArgumentParser(description="AuditBee GMP Audit System")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--host", default="127.0.0.1", help="Server host (default: 127.0.0.1)")
    parser.add_argument("--open-browser", action="store_true", help="Open browser on startup")
    parser.add_argument("--data-dir", default=None, help="Custom data directory path")
    parser.add_argument("--no-launcher", action="store_true", help="Skip tkinter launcher GUI")
    args = parser.parse_args()

    setup_signal_handlers()

    # --- Handle --data-dir before any paths import (paths.py reads this env var at import time) ---
    if args.data_dir:
        os.environ["AUDITBEE_DATA_DIR"] = args.data_dir

    # --- Tkinter launcher (before backend starts) ---
    if not args.no_launcher:
        from app.core import paths
        paths.ensure_writable_dirs()

        # Pre-launcher file logging (before _configure_logging in main.py)
        _log_dir = str(paths.LOG_DIR)
        os.makedirs(_log_dir, exist_ok=True)
        if not logging.getLogger().handlers:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                handlers=[
                    logging.StreamHandler(),
                    logging.FileHandler(os.path.join(_log_dir, "launcher.log"), encoding="utf-8"),
                ],
            )

        # Ensure .env exists before launcher reads it
        if not paths.ENV_FILE.exists():
            example = paths.CONFIG_DIR / ".env.example"
            if example.exists():
                shutil.copy2(example, paths.ENV_FILE)

        try:
            from app.tkinter_launcher import show_launcher
            config = show_launcher()
        except Exception as exc:
            logger.exception("Launcher crashed: %s", exc)
            print(f"\n启动器异常: {exc}", file=sys.stderr)
            print(f"详细错误已写入 {os.path.join(_log_dir, 'crash.log')}", file=sys.stderr)
            print("可使用 --no-launcher 参数跳过启动器直接启动服务", file=sys.stderr)
            input("按 Enter 键退出...")
            sys.exit(1)

        if config is None:
            sys.exit(0)  # User closed window

        from app.tkinter_launcher import write_env
        write_env(paths.ENV_FILE, {"AGENT_LLM_PROVIDER": config["provider"]})
        args.open_browser = True  # Launcher mode auto-opens browser

    # --- Original startup logic ---
    from app.core import paths

    # Add bundled FFmpeg to PATH for torchcodec/sentence_transformers
    ffmpeg_dir = str(paths.TOOLS_DIR / "ffmpeg")
    if os.path.isdir(ffmpeg_dir):
        current_path = os.environ.get("PATH", "")
        if ffmpeg_dir not in current_path:
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + current_path

    if args.open_browser:
        open_browser(args.port)

    import uvicorn

    # In frozen mode, ensure backend/ is on sys.path so uvicorn can resolve "app.main:app"
    from app.core import paths as _paths
    if _paths.FROZEN:
        _backend_dir = str(_paths.BUNDLE_DIR)
        if _backend_dir not in sys.path:
            sys.path.insert(0, _backend_dir)

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
