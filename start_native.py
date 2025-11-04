#!/usr/bin/env python3
"""
启动 PySide6 桌面端应用。
"""

from ai_audio2note.gui.app import run_app


def main() -> None:
    """入口函数，启动桌面应用。"""
    print("🎵 正在启动 AI Audio2Note 桌面端...")
    run_app()


if __name__ == "__main__":
    main()
