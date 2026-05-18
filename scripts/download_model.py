"""Download the BAAI/bge-large-zh-v1.5 embedding model from ModelScope.

Usage:
    python scripts/download_model.py

The model (~1.3 GB) will be saved to the project's model/ directory.
If the model already exists, the script exits with a message.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
MODEL_DIR = PROJECT_ROOT / "model"
MODEL_ID = "BAAI/bge-large-zh-v1.5"


def main():
    if MODEL_DIR.is_dir() and (MODEL_DIR / "pytorch_model.bin").exists():
        print(f"Model already exists at {MODEL_DIR}")
        return

    try:
        from modelscope import snapshot_download
    except ImportError:
        print("Installing modelscope...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "modelscope"])
        from modelscope import snapshot_download

    print(f"Downloading {MODEL_ID} to {MODEL_DIR}...")
    print("This may take several minutes (~1.3 GB).")
    print()

    snapshot_download(
        MODEL_ID,
        local_dir=str(MODEL_DIR),
    )

    print()
    print(f"Model downloaded successfully to {MODEL_DIR}")


if __name__ == "__main__":
    main()
