"""
Minimal ProcessService: Only keeps video download functionality
"""

import os
import re
from pathlib import Path
from .audio_downloader import AudioDownloader


def sanitize_filename(name: str) -> str:
    """Sanitize filename to avoid invalid characters."""
    sanitized = re.sub(r'[<>:"/\\|?*\n\r\t]', "_", name).strip()
    return sanitized or "下载内容"


class ProcessService:
    """仅保留视频下载相关功能的服务类"""

    def __init__(self, download_dir: str | os.PathLike | None = None):
        base = Path(download_dir).expanduser() if download_dir else Path.cwd() / "temp"
        self.base_dir = base

    def process_video(self, url: str, page_number: int | None = None) -> dict:
        """
        下载视频（或音频，根据你的实际业务逻辑）
        Args:
            url: 视频页面 URL 或视频直链
            page_number: 可选分页参数，用于批量下载等场景
        Returns:
            dict: {
                "success": bool,
                "files": list[下载的文件路径],
                "session_folder": 下载文件所在目录,
                "video_title": 视频标题
            } 或者错误信息
        """
        try:
            base_path = self.base_dir
            print(f"ProcessService: 下载目录 = {base_path}")
            base_path.mkdir(parents=True, exist_ok=True)

            downloader = AudioDownloader(str(base_path))
            video_title = downloader.get_video_title(url)
            if not video_title:
                return {"success": False, "error": "无法获取视频标题"}

            safe_title = sanitize_filename(video_title)
            session_folder = base_path / safe_title
            print(f"创建会话文件夹: {session_folder}")
            session_folder.mkdir(parents=True, exist_ok=True)

            downloader = AudioDownloader(str(session_folder))
            downloader.download_audio(url, page_number)

            files = [str(path) for path in session_folder.iterdir() if path.is_file()]

            return {
                "success": True,
                "files": files,
                "session_folder": str(session_folder),
                "video_title": video_title
            }

        except Exception as e:
            return {"success": False, "error": str(e)}
