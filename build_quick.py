#!/usr/bin/env python3
"""
快速构建脚本：生成便于调试的 PyInstaller onedir 版本。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    project_root = Path(__file__).parent.resolve()
    dist_dir = project_root / "dist" / "debug"
    work_dir = project_root / "dist" / "debug_build"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--paths",
        ".",
        "--name",
        "AI_Audio2Note_Debug",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
        "--hidden-import",
        "ai_audio2note.backend.services.audio_downloader",
        "--hidden-import",
        "ai_audio2note.backend.services.process_service",
        "--hidden-import",
        "ai_audio2note.backend.services.transcription_service",
        "--hidden-import",
        "faster_whisper",
        "--hidden-import",
        "ai_audio2note.backend.services.chat_service",
        "--hidden-import",
        "requests",
        "start_native.py",
    ]

    print("🚀 开始快速构建 (onedir)...")
    subprocess.run(cmd, check=True, cwd=project_root)
    print(f"✅ 调试版本已生成，位置：{dist_dir}")


if __name__ == "__main__":
    main()
