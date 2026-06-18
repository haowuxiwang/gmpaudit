import argparse
import contextlib
import logging
import os
import shutil
import signal
import sys
import threading
import time
import webbrowser
from threading import Thread

logger = logging.getLogger(__name__)


def open_browser(port: int) -> None:
    """Open browser after uvicorn is ready, with retry."""

    def _open():
        import subprocess
        import urllib.request

        url = f"http://localhost:{port}"
        logger.info("open_browser: waiting for server at %s", url)
        # Wait for server to be ready (up to 30s)
        for i in range(30):
            try:
                urllib.request.urlopen(f"{url}/api/health", timeout=2)
                logger.info("open_browser: server ready after %d attempts", i + 1)
                break
            except Exception:
                time.sleep(1)
        else:
            logger.warning("open_browser: server not ready after 30 attempts")
        # Use subprocess to open browser, avoiding fileno() issues with _NullStream
        try:
            if sys.platform == "win32":
                logger.info("open_browser: opening with subprocess")
                subprocess.Popen(
                    ["cmd", "/c", "start", url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    shell=True,
                )
                logger.info("open_browser: subprocess succeeded")
            else:
                logger.info("open_browser: opening with webbrowser.open(%s)", url)
                webbrowser.open(url)
                logger.info("open_browser: webbrowser.open succeeded")
        except Exception as e:
            logger.exception("open_browser: failed to open browser: %s", e)
            # Fallback: try webbrowser regardless of platform
            with contextlib.suppress(Exception):
                webbrowser.open(url)

    Thread(target=_open, daemon=True).start()


def setup_signal_handlers() -> None:
    def _handler(signum, frame):
        logger.info("Received signal %s, shutting down gracefully...", signum)
        sys.exit(0)

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)
    if hasattr(signal, "SIGBREAK"):
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
    _is_frozen = getattr(sys, "frozen", False)
    if _is_frozen and sys.platform == "win32":
        # Replace stdout/stderr with a null stream before any print/logging.
        # This prevents Windows from allocating a visible console window.
        # Logs still go to file via RotatingFileHandler in main.py.
        sys.stdout = _NullStream()
        sys.stderr = _NullStream()

    # --- Global crash handler: write to crash.log before process exits ---
    import traceback as _traceback

    _app_dir = (
        os.path.dirname(sys.executable)
        if _is_frozen
        else os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    )

    def _excepthook(exc_type, exc_value, exc_tb):
        import datetime

        crash_log = os.path.join(_app_dir, "data", "logs", "crash.log")
        os.makedirs(os.path.dirname(crash_log), exist_ok=True)
        # Rotate crash.log if larger than 10MB (keep 3 backups)
        try:
            if os.path.exists(crash_log) and os.path.getsize(crash_log) > 10 * 1024 * 1024:
                for i in range(2, 0, -1):
                    src = f"{crash_log}.{i}"
                    dst = f"{crash_log}.{i + 1}"
                    if os.path.exists(src):
                        if i + 1 > 3:
                            os.remove(src)
                        else:
                            os.replace(src, dst)
                os.replace(crash_log, f"{crash_log}.1")
        except OSError:
            pass  # rotation is best-effort
        with open(crash_log, "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 60}\n")
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

    # --- Original startup logic (runs in background thread if launcher is used) ---
    from app.core import paths

    # Add bundled FFmpeg to PATH for torchcodec/sentence_transformers
    ffmpeg_dir = str(paths.TOOLS_DIR / "ffmpeg")
    if os.path.isdir(ffmpeg_dir):
        current_path = os.environ.get("PATH", "")
        if ffmpeg_dir not in current_path:
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + current_path

    import uvicorn

    # In frozen mode, ensure backend/ is on sys.path so uvicorn can resolve "app.main:app"
    from app.core import paths as _paths

    if _paths.FROZEN:
        _backend_dir = str(_paths.BUNDLE_DIR)
        if _backend_dir not in sys.path:
            sys.path.insert(0, _backend_dir)

    def _run_uvicorn():
        uvicorn.run(
            "app.main:app",
            host=args.host,
            port=args.port,
            log_level="info",
        )

    # --- Tkinter launcher (before browser opens) ---
    if not args.no_launcher:
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
                shutil.copyfile(example, paths.ENV_FILE)
                os.chmod(paths.ENV_FILE, 0o600)

        # Pass port to tkinter launcher via env var so it can poll the correct URL
        os.environ["AUDITBEE_PORT"] = str(args.port)

        # Start uvicorn in background BEFORE showing launcher
        # so the health endpoint is ready when launcher polls it
        server_thread = threading.Thread(target=_run_uvicorn, daemon=True)
        server_thread.start()

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
        # Browser is opened by the launcher after server is ready
        # No need to set args.open_browser here

        # Keep main thread alive so uvicorn thread stays running
        with contextlib.suppress(KeyboardInterrupt):
            server_thread.join()
    else:
        if args.open_browser:
            open_browser(args.port)
        _run_uvicorn()


if __name__ == "__main__":
    main()
