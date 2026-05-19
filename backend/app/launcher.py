import argparse
import logging
import os
import signal
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


def main() -> None:
    parser = argparse.ArgumentParser(description="AuditBee GMP Audit System")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--host", default="0.0.0.0", help="Server host (default: 0.0.0.0)")
    parser.add_argument("--open-browser", action="store_true", help="Open browser on startup")
    parser.add_argument("--data-dir", default=None, help="Custom data directory path")
    args = parser.parse_args()

    setup_signal_handlers()

    # Add bundled FFmpeg to PATH for torchcodec/sentence_transformers
    import sys
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        bundle_dir = sys._MEIPASS
        ffmpeg_dir = os.path.join(bundle_dir, 'tools', 'ffmpeg')
    else:
        # Running from source
        ffmpeg_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'tools', 'ffmpeg')
    if os.path.isdir(ffmpeg_dir):
        current_path = os.environ.get("PATH", "")
        if ffmpeg_dir not in current_path:
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + current_path

    if args.data_dir:
        import os
        os.environ["AUDITBEE_DATA_DIR"] = args.data_dir

    if args.open_browser:
        open_browser(args.port)

    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
