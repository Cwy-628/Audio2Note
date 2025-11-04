#!/usr/bin/env python3
"""
跨平台构建脚本：使用 PyInstaller 为当前系统生成桌面端可执行文件。
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "AI_Audio2Note"


class DesktopBuilder:
    def __init__(self) -> None:
        self.project_root = Path(__file__).parent.resolve()
        self.dist_root = self.project_root / "dist"
        self.binary_dir = self.dist_root / "bin"
        self.work_dir = self.dist_root / "build"
        self.bundle_dir = self.dist_root / f"{APP_NAME}_{self.platform_label}"
        self._artifact_path: Path | None = None

    @property
    def system(self) -> str:
        return platform.system().lower()

    @property
    def platform_label(self) -> str:
        mapping = {"windows": "Windows", "darwin": "macOS", "linux": "Linux"}
        return mapping.get(self.system, platform.system())

    @property
    def executable_name(self) -> str:
        if self.system == "windows":
            return f"{APP_NAME}.exe"
        return APP_NAME

    def ensure_dependencies(self) -> None:
        try:
            import PyInstaller  # noqa: F401

            print("✅ PyInstaller 已安装")
        except ImportError:
            print("📦 未检测到 PyInstaller，正在安装...")
            subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    def clean_previous_builds(self) -> None:
        for path in (self.binary_dir, self.work_dir, self.bundle_dir):
            if path.exists():
                shutil.rmtree(path)
        self.binary_dir.mkdir(parents=True, exist_ok=True)
        self.bundle_dir.mkdir(parents=True, exist_ok=True)

    def build_binary(self) -> None:
        print("🔨 正在构建桌面端可执行文件...")
        cmd = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--name",
            APP_NAME,
            "--paths",
            ".",
            "--distpath",
            str(self.binary_dir),
            "--workpath",
            str(self.work_dir),
        ]

        hidden_imports = [
            "ai_audio2note.backend.services.audio_downloader",
            "ai_audio2note.backend.services.process_service",
            "ai_audio2note.backend.services.transcription_service",
            "faster_whisper",
            "ai_audio2note.backend.services.chat_service",
            "requests",
        ]
        for hidden in hidden_imports:
            cmd.extend(["--hidden-import", hidden])

        if self.system == "windows":
            cmd.extend(["--onefile", "--windowed"])
        elif self.system == "darwin":
            cmd.append("--windowed")
        else:
            cmd.append("--onefile")

        cmd.append("start_native.py")

        subprocess.run(cmd, check=True, cwd=self.project_root)
        artifact = self.expected_artifact()
        if not artifact.exists():
            raise FileNotFoundError(f"未找到构建产物: {artifact}")
        self._artifact_path = artifact
        print(f"✅ 可执行文件构建完成: {artifact}")

    def expected_artifact(self) -> Path:
        if self.system == "windows":
            return self.binary_dir / f"{APP_NAME}.exe"
        if self.system == "darwin":
            return self.binary_dir / f"{APP_NAME}.app"
        return self.binary_dir / APP_NAME

    def assemble_bundle(self) -> None:
        print("📦 正在整理分发包...")
        if not self._artifact_path:
            raise RuntimeError("请先构建可执行文件")

        destination = self.bundle_dir / self._artifact_path.name
        if self._artifact_path.is_dir():
            shutil.copytree(self._artifact_path, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(self._artifact_path, destination)

        # 附带重要脚本与文档
        self._copy_if_exists("install_ffmpeg.py")
        self._copy_if_exists("README.md")

        if self.system == "windows":
            self._create_windows_launcher()
        elif self.system == "darwin":
            self._create_mac_launcher(destination)
        else:
            self._create_linux_launcher()

        print(f"✅ 分发包已准备好: {self.bundle_dir}")

    def _copy_if_exists(self, filename: str) -> None:
        source = self.project_root / filename
        if source.exists():
            shutil.copy2(source, self.bundle_dir / source.name)

    def _create_windows_launcher(self) -> None:
        launcher = self.bundle_dir / "启动AI_Audio2Note.bat"
        launcher.write_text(
            f"""@echo off
setlocal
pushd %~dp0
echo 启动 AI Audio2Note...
start "" "{self.executable_name}"
popd
""",
            encoding="utf-8",
        )

    def _create_mac_launcher(self, app_path: Path) -> None:
        launcher = self.bundle_dir / "启动AI_Audio2Note.command"
        launcher.write_text(
            f"""#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
echo "启动 AI Audio2Note..."
open "$DIR/{app_path.name}"
""",
            encoding="utf-8",
        )
        launcher.chmod(0o755)

    def _create_linux_launcher(self) -> None:
        launcher = self.bundle_dir / "start_ai_audio2note.sh"
        launcher.write_text(
            f"""#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
echo "启动 AI Audio2Note..."
"$DIR/{APP_NAME}"
""",
            encoding="utf-8",
        )
        launcher.chmod(0o755)

    def build(self) -> None:
        print(f"🚀 开始构建 AI Audio2Note ({self.platform_label})")
        self.ensure_dependencies()
        self.clean_previous_builds()
        self.build_binary()
        self.assemble_bundle()
        print("🎉 构建完成！")
        print(f"📂 输出目录: {self.bundle_dir}")


def main() -> None:
    builder = DesktopBuilder()
    builder.build()


if __name__ == "__main__":
    main()
