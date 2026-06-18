"""Tkinter-based launcher for AuditBee.

Provides a GUI for non-technical users to select LLM provider,
check/download the embedding model, and start the backend server.

This module is intentionally standalone -- it does NOT import from
app.core, app.services, or any other app module to avoid circular
dependencies and slow startup. It operates directly on the .env file.
"""

import contextlib
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox, ttk

# ---------------------------------------------------------------------------
# Provider configuration -- canonical source: backend/app/core/providers.py
# This dict is intentionally duplicated because the launcher is standalone
# (no app.* imports). When adding a new provider, update providers.py FIRST.
# ---------------------------------------------------------------------------

PROVIDERS: dict[str, dict[str, str]] = {
    "mimo": {"label": "Mimo (推荐)"},
    "deepseek": {"label": "DeepSeek"},
    "qwen": {"label": "通义千问 (Qwen)"},
    "glm": {"label": "智谱 (GLM)"},
    "openai": {"label": "OpenAI"},
    "anthropic": {"label": "Anthropic (Claude)"},
    "siliconflow": {"label": "SiliconFlow"},
    "openrouter": {"label": "OpenRouter"},
}

PROVIDER_KEYS: list[str] = list(PROVIDERS.keys())
PROVIDER_LABELS: list[str] = [PROVIDERS[k]["label"] for k in PROVIDER_KEYS]

# Model download config
MODEL_ID = "BAAI/bge-large-zh-v1.5"
MODEL_CHECK_FILE = "pytorch_model.bin"
MODEL_CHECK_FILE_SAFETENSORS = "model.safetensors"

# Theme colors
PRIMARY = "#D97757"
BG = "#FAFAF8"
FG = "#1a1a1a"
SUCCESS = "#52c41a"
ERROR = "#ff4d4f"
BORDER = "#E8E5E0"

# ---------------------------------------------------------------------------
# Path helpers (mirrors backend/app/core/paths.py logic)
# ---------------------------------------------------------------------------


def _get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(os.path.dirname(sys.executable))
    return Path(__file__).resolve().parent.parent.parent


def _resolve_env_path() -> Path:
    return _get_app_dir() / "config" / ".env"


def _resolve_model_dir() -> Path:
    if getattr(sys, "frozen", False):
        bundled = Path(os.path.dirname(sys.executable)) / "_internal" / "model"
        if bundled.is_dir() and (
            (bundled / MODEL_CHECK_FILE).exists() or (bundled / MODEL_CHECK_FILE_SAFETENSORS).exists()
        ):
            return bundled
    return _get_app_dir() / "model"


# ---------------------------------------------------------------------------
# .env file I/O (mirrors backend/app/api/config.py _update_env_file)
# ---------------------------------------------------------------------------


def _read_env(path: Path) -> dict[str, str]:
    """Parse .env file into a dict. Keys are uppercased."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def _atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Atomically write text to a file using write-to-temp-then-rename."""
    import tempfile

    tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding=encoding) as f:
            f.write(content)
        if sys.platform == "win32" and path.exists():
            path.unlink()
        os.rename(tmp_path, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def write_env(path: Path, updates: dict[str, str]) -> None:
    """Update specific keys in .env file, preserving comments and order."""
    lines: list[str] = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()

    updated_keys: set[str] = set()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                lines[i] = f"{key}={updates[key]}"
                updated_keys.add(key)

    # Append keys not found in file
    for key, value in updates.items():
        if key not in updated_keys:
            lines.append(f"{key}={value}")

    _atomic_write_text(path, "\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Model download
# ---------------------------------------------------------------------------


def _check_model_downloaded(model_dir: Path) -> bool:
    return model_dir.is_dir() and (
        (model_dir / MODEL_CHECK_FILE).exists() or (model_dir / MODEL_CHECK_FILE_SAFETENSORS).exists()
    )


def _download_model(
    model_dir: Path,
    status_cb,
    done_cb,
) -> None:
    """Download embedding model in a background thread."""

    def _worker():
        try:
            try:
                from modelscope import snapshot_download
            except ImportError:
                if getattr(sys, "frozen", False):
                    done_cb(False, "modelscope 未安装。打包模式不支持自动安装，请先手动安装: pip install modelscope")
                    return
                status_cb("正在安装 modelscope 依赖...")
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "modelscope"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                from modelscope import snapshot_download

            status_cb("正在下载模型 (~1.3 GB)，请耐心等待...")
            snapshot_download(MODEL_ID, local_dir=str(model_dir))
            done_cb(True, "模型下载完成")
        except Exception as e:
            done_cb(False, f"下载失败: {e}")

    threading.Thread(target=_worker, daemon=True).start()


# ---------------------------------------------------------------------------
# GUI Launcher
# ---------------------------------------------------------------------------


class _LauncherWindow:
    """Tkinter launcher window. Call show() to run the event loop."""

    def __init__(self):
        self.result: dict[str, str] | None = None
        self._downloading = False

        self.root = tk.Tk()
        self.root.title("AuditBee 启动器")
        self.root.geometry("480x460")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        # Center window
        self.root.update_idletasks()
        w, h = 480, 460
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        self._load_existing_config()
        self._build_ui()

    def _load_existing_config(self):
        """Read existing .env to pre-fill form."""
        env = _read_env(_resolve_env_path())
        provider_env = env.get("AGENT_LLM_PROVIDER", "mimo")
        self._initial_provider = provider_env if provider_env in PROVIDERS else "mimo"

    def _build_ui(self):
        pad = {"padx": 20, "pady": (0, 0)}
        title_font = tkfont.Font(family="Microsoft YaHei", size=16, weight="bold")
        section_font = tkfont.Font(family="Microsoft YaHei", size=10, weight="bold")
        normal_font = tkfont.Font(family="Microsoft YaHei", size=10)
        small_font = tkfont.Font(family="Microsoft YaHei", size=9)

        # Title
        tk.Label(
            self.root,
            text="AuditBee 启动器",
            font=title_font,
            bg=BG,
            fg=PRIMARY,
        ).pack(pady=(20, 5))
        tk.Label(
            self.root,
            text="选择大模型供应商并检查嵌入模型",
            font=small_font,
            bg=BG,
            fg="#6B7280",
        ).pack(pady=(0, 15))

        # --- LLM Provider Section ---
        tk.Label(
            self.root,
            text="大模型配置",
            font=section_font,
            bg=BG,
            fg=FG,
        ).pack(**pad, anchor="w")

        sep1 = tk.Frame(self.root, height=1, bg=BORDER)
        sep1.pack(fill="x", padx=20, pady=(2, 10))

        # Provider selector
        row_provider = tk.Frame(self.root, bg=BG)
        row_provider.pack(fill="x", padx=20, pady=(0, 8))
        tk.Label(row_provider, text="供应商:", font=normal_font, bg=BG, fg=FG, width=8, anchor="w").pack(side="left")
        self.provider_var = tk.StringVar(value=PROVIDERS[self._initial_provider]["label"])
        provider_combo = ttk.Combobox(
            row_provider,
            textvariable=self.provider_var,
            values=PROVIDER_LABELS,
            state="readonly",
            width=28,
        )
        provider_combo.pack(side="left", padx=(5, 0))

        tk.Label(
            self.root,
            text="API Key 和模型参数请在启动后进入「设置」页面配置",
            font=small_font,
            bg=BG,
            fg="#6B7280",
        ).pack(padx=20, anchor="w", pady=(0, 5))

        # --- Model Download Section ---
        tk.Label(
            self.root,
            text="嵌入模型（可选）",
            font=section_font,
            bg=BG,
            fg=FG,
        ).pack(padx=20, anchor="w", pady=(15, 0))

        sep2 = tk.Frame(self.root, height=1, bg=BORDER)
        sep2.pack(fill="x", padx=20, pady=(2, 10))

        model_dir = _resolve_model_dir()
        self._model_downloaded = _check_model_downloaded(model_dir)
        self._model_bundled = "_internal" in str(model_dir)

        tk.Label(
            self.root,
            text=f"模型: {MODEL_ID}\n大小: ~1.3 GB（知识图谱功能需要）",
            font=small_font,
            bg=BG,
            fg="#6B7280",
            justify="left",
        ).pack(padx=20, anchor="w")

        if self._model_bundled:
            status_text = "状态: 已打包（随程序分发）"
        elif self._model_downloaded:
            status_text = "状态: 已下载"
        else:
            status_text = "状态: 未下载"
        self.model_status_var = tk.StringVar(value=status_text)
        self.model_status_label = tk.Label(
            self.root,
            textvariable=self.model_status_var,
            font=small_font,
            bg=BG,
            fg=SUCCESS if self._model_downloaded else "#6B7280",
        )
        self.model_status_label.pack(padx=20, anchor="w", pady=(4, 4))

        if not self._model_bundled:
            row_model = tk.Frame(self.root, bg=BG)
            row_model.pack(fill="x", padx=20, pady=(0, 5))
            tk.Label(row_model, text="", width=8, bg=BG).pack(side="left")

            self.download_btn = tk.Button(
                row_model,
                text="下载模型",
                font=normal_font,
                command=self._on_download_model,
                relief="flat",
                bg="#E8E5E0",
                fg=FG,
                cursor="hand2",
            )
            self.download_btn.pack(side="left", padx=(5, 10))

            self.skip_btn = tk.Button(
                row_model,
                text="跳过",
                font=small_font,
                command=self._on_skip_model,
                relief="flat",
                bg=BG,
                fg="#6B7280",
                cursor="hand2",
            )
            self.skip_btn.pack(side="left")

        # Download progress bar
        self.progress_frame = tk.Frame(self.root, bg=BG)
        self.progress_frame.pack(fill="x", padx=20, pady=(5, 0))
        self.progress_var = tk.StringVar(value="")
        self.progress_label = tk.Label(
            self.progress_frame,
            textvariable=self.progress_var,
            font=small_font,
            bg=BG,
            fg="#6B7280",
        )
        self.progress_label.pack(anchor="w")
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            mode="indeterminate",
            length=300,
        )
        self.progress_bar.pack(fill="x", pady=(2, 0))
        self.progress_frame.pack_forget()  # Hidden initially

        # Spacer
        tk.Frame(self.root, bg=BG, height=10).pack()

        # --- Start Button ---
        self.start_btn = tk.Button(
            self.root,
            text="启动 AuditBee",
            font=tkfont.Font(family="Microsoft YaHei", size=12, weight="bold"),
            bg=PRIMARY,
            fg="white",
            relief="flat",
            cursor="hand2",
            command=self._on_start,
            width=25,
            height=2,
        )
        self.start_btn.pack(pady=(10, 5))

        # Footer hint
        tk.Label(
            self.root,
            text="启动后请在「设置」页面配置 API Key",
            font=small_font,
            bg=BG,
            fg="#6B7280",
        ).pack(pady=(0, 15))

    def _get_selected_provider(self) -> str:
        label = self.provider_var.get()
        for key, cfg in PROVIDERS.items():
            if cfg["label"] == label:
                return key
        return "mimo"

    # -- Model download --

    def _on_download_model(self):
        if self._downloading:
            return
        self._downloading = True
        self.download_btn.configure(state="disabled")
        self.skip_btn.configure(state="disabled")

        # Show progress
        self.progress_frame.pack(fill="x", padx=20, pady=(5, 0))
        self.progress_bar.start(15)
        self.progress_var.set("准备下载...")
        self.model_status_var.set("状态: 下载中...")
        self.model_status_label.configure(fg="#6B7280")

        model_dir = _resolve_model_dir()

        def status_cb(msg):
            self.root.after(0, lambda: self.progress_var.set(msg))

        def done_cb(ok, msg):
            def _update():
                self._downloading = False
                self.progress_bar.stop()
                self.download_btn.configure(state="normal")
                self.skip_btn.configure(state="normal")
                if ok:
                    self._model_downloaded = True
                    self.model_status_var.set("状态: 已下载")
                    self.model_status_label.configure(fg=SUCCESS)
                    self.progress_var.set("")
                    self.progress_frame.pack_forget()
                    messagebox.showinfo("下载完成", msg)
                else:
                    self.model_status_var.set("状态: 下载失败")
                    self.model_status_label.configure(fg=ERROR)
                    self.progress_var.set(msg)
                    messagebox.showerror("下载失败", msg)

            self.root.after(0, _update)

        _download_model(model_dir, status_cb, done_cb)

    def _on_skip_model(self):
        self.progress_frame.pack_forget()

    # -- Start --

    def _on_start(self):
        """Save config and show 'starting service' progress."""
        self.result = {
            "provider": self._get_selected_provider(),
        }
        # Disable start button and show progress
        self.start_btn.configure(state="disabled", text="正在启动服务...")
        self.progress_frame.pack(fill="x", padx=20, pady=(5, 0))
        self.progress_bar.start(15)
        self.progress_var.set("正在启动后端服务，请稍候...")
        # Start uvicorn in background thread
        threading.Thread(target=self._start_server, daemon=True).start()

    def _start_server(self):
        """Start uvicorn and wait for it to be ready, then open browser."""
        import subprocess
        import urllib.request

        port = int(os.getenv("AUDITBEE_PORT", "8000"))
        url = f"http://localhost:{port}"

        # Wait for server to be ready (up to 60s)
        for i in range(60):
            try:
                urllib.request.urlopen(f"{url}/api/health", timeout=2)
                # Server is ready
                self.root.after(0, lambda: self.progress_var.set("服务已就绪，正在打开浏览器..."))
                # Open browser
                try:
                    if sys.platform == "win32":
                        subprocess.Popen(
                            ["cmd", "/c", "start", url],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            shell=True,
                        )
                    else:
                        import webbrowser
                        webbrowser.open(url)
                except Exception:
                    pass
                # Close launcher after a short delay
                self.root.after(1000, self._close_launcher)
                return
            except Exception:
                self.root.after(0, lambda i=i: self.progress_var.set(f"正在等待服务启动... ({i+1}/60)"))
                time.sleep(1)
        # Timeout
        self.root.after(0, lambda: self.progress_var.set("服务启动超时，请手动打开浏览器"))
        self.root.after(0, lambda: self.start_btn.configure(state="normal", text="启动 AuditBee"))
        self.root.after(0, lambda: self.progress_bar.stop())

    def _close_launcher(self):
        """Close the launcher window."""
        self.root.quit()
        self.root.destroy()

    def _on_close(self):
        """Window closed without clicking Start."""
        self.result = None
        self.root.quit()
        self.root.destroy()

    def show(self) -> dict[str, str] | None:
        """Run the launcher window. Returns config dict or None if closed."""
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()
        return self.result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def show_launcher() -> dict[str, str] | None:
    """Show the tkinter launcher and return user config.

    Returns:
        {"provider": str} on success, or None if the
        user closed the window without clicking Start.
    """
    win = _LauncherWindow()
    return win.show()
