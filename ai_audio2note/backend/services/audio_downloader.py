"""
视记 - 音频下载工具模块

功能：
- 使用 yt-dlp 从 B站 和 YouTube 下载视频并提取为 MP3 音频文件
- 支持平台：B站 (bilibili.com)、YouTube (youtube.com)
- 分P选择和URL验证

安全特性：
- URL域名白名单验证
- 文件路径安全处理
- 错误处理和异常管理

作者：视记开发团队
版本：1.0.0
"""

import os
import shutil
import sys
from pathlib import Path
from typing import Optional

import yt_dlp


def _find_ffmpeg() -> Optional[str]:
    """Locate ffmpeg binary across common installation paths."""
    candidates: list[Optional[str]] = []

    env_path = os.environ.get("FFMPEG_PATH")
    if env_path:
        candidates.append(env_path)

    candidates.append(shutil.which("ffmpeg"))

    # Common Homebrew paths on macOS
    candidates.extend(
        [
            "/opt/homebrew/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            "/usr/bin/ffmpeg",
        ]
    )

    # Relative to current executable (PyInstaller bundle scenario)
    exec_dir = Path(sys.executable).resolve().parent
    candidates.append(str(exec_dir / "ffmpeg"))

    # Look inside PyInstaller temporary directory
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        candidates.append(str(Path(bundle_dir) / "ffmpeg"))

    for path in candidates:
        if path and Path(path).is_file():
            return path
    return None


class AudioDownloader:
    """
    视记音频下载器类

    支持从 B站 和 YouTube 平台下载视频并提取为 MP3 音频文件
    提供分P选择、URL验证、错误处理等功能
    """

    def __init__(self, session_folder: str | None = None):
        """
        初始化视记音频下载器

        配置 yt-dlp 下载选项，包括输出格式、音频质量等
        自动创建 temp 目录用于保存下载的文件

        Args:
            session_folder (str, optional): 会话文件夹路径
        """
        # 设置输出目录
        if session_folder:
            self.output_dir = session_folder
            self.temp_dir = session_folder
        else:
            self.temp_dir = "temp"
            self.output_dir = self.temp_dir

        # 确保输出目录存在
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)

        ffmpeg_path = _find_ffmpeg()
        if ffmpeg_path:
            ffmpeg_dir = str(Path(ffmpeg_path).parent)
            current_path = os.environ.get("PATH", "")
            if ffmpeg_dir not in current_path.split(os.pathsep):
                os.environ["PATH"] = os.pathsep.join([ffmpeg_dir, current_path])

        self.ydl_opts = {
            # 输出目录：保存到指定文件夹
            'outtmpl': os.path.join(self.output_dir, '%(title)s.%(ext)s'),

            # 选择最佳音频质量进行下载
            'format': 'bestaudio/best',

            # 后处理器配置：提取音频并转换为 MP3
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',  # 使用 FFmpeg 提取音频
                'preferredcodec': 'mp3',  # 音频编码格式为 MP3
                'preferredquality': '192',  # 音频质量 192 kbps
            }],

            # 添加超时设置
            'socket_timeout': 30,
            'retries': 3,
        }

        if ffmpeg_path:
            self.ydl_opts["ffmpeg_location"] = ffmpeg_path
        else:
            raise RuntimeError(
                "未检测到 FFmpeg。请先安装 FFmpeg（例如通过 brew install ffmpeg），"
                "或设置环境变量 FFMPEG_PATH 指向可执行文件。"
            )

    def download_audio(self, url: str, page_number: Optional[int] = None) -> bool:
        """
        下载视频并提取为 MP3 音频文件

        Args:
            url (str): 视频 URL 地址
                - B站: https://www.bilibili.com/video/...
                - YouTube: https://www.youtube.com/watch?v=...
            page_number (int, optional): 分P编号（从1开始）
                - None: 下载所有分P
                - 数字: 下载指定分P

        Returns:
            bool: 下载成功返回 True，失败返回 False
        """
        # 验证 URL 是否支持
        if not self._is_supported_url(url):
            raise ValueError(
                "不支持的平台。目前仅支持 B站(bilibili.com) 和 YouTube(youtube.com/ youtu.be) 链接。"
            )

        # 复制配置选项
        ydl_opts = self.ydl_opts.copy()

        # 如果指定了分P编号，则只下载该分P
        if page_number is not None:
            ydl_opts['playlist_items'] = f'{page_number}:{page_number}'

        try:
            # 清理URL，移除不必要的参数
            clean_url = self._clean_url(url)
            print(f"🎵 开始下载音频: {clean_url}")
            print("📥 正在获取视频信息...")

            # 创建 yt-dlp 下载器实例
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                print("🔍 正在提取视频信息...")
                # 先获取视频信息，不直接下载
                info = ydl.extract_info(clean_url, download=False)
                print(f"📋 视频信息: {info.get('title', 'Unknown')}")
                
                print("📥 开始下载...")
                # 执行下载
                ydl.download([clean_url])

                print("✅ 音频下载完成！")
                return True

        except Exception as e:
            raise RuntimeError(
                f"下载失败: {str(e)}。请确认网络连接、FFmpeg 安装以及链接有效性。"
            ) from e

    def get_video_title(self, url: str) -> Optional[str]:
        """
        获取视频标题

        Args:
            url (str): 视频 URL 地址

        Returns:
            Optional[str]: 视频标题，获取失败返回 None
        """
        try:
            # 清理URL，移除不必要的参数
            clean_url = self._clean_url(url)
            print(f"清理后的URL: {clean_url}")

            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(clean_url, download=False)
                return info.get('title') or '未知标题'
        except Exception as e:
            raise RuntimeError(f"获取视频标题失败: {str(e)}") from e
    
    def _clean_url(self, url: str) -> str:
        """
        清理URL，移除不必要的参数
        
        Args:
            url (str): 原始URL
            
        Returns:
            str: 清理后的URL
        """
        import urllib.parse
        
        # 解析URL
        parsed = urllib.parse.urlparse(url)
        
        # 对于B站链接，只移除追踪参数，保留必要的参数
        if 'bilibili.com' in parsed.netloc:
            query_params = urllib.parse.parse_qs(parsed.query)
            # 只移除追踪和统计相关的参数，保留p（分P）、t（时间戳）等重要参数
            tracking_params = ['spm_id_from', 'vd_source', 'unique_k', 'spm_id', 'from_spmid', 'from']
            for param in tracking_params:
                query_params.pop(param, None)
            
            # 重新构建URL
            new_query = urllib.parse.urlencode(query_params, doseq=True)
            clean_url = urllib.parse.urlunparse((
                parsed.scheme, parsed.netloc, parsed.path,
                parsed.params, new_query, parsed.fragment
            ))
            return clean_url
        
        # 对于YouTube链接，也进行适当的清理
        elif 'youtube.com' in parsed.netloc or 'youtu.be' in parsed.netloc:
            query_params = urllib.parse.parse_qs(parsed.query)
            # 移除追踪参数，保留v（视频ID）等重要参数
            tracking_params = ['feature', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term']
            for param in tracking_params:
                query_params.pop(param, None)
            
            # 重新构建URL
            new_query = urllib.parse.urlencode(query_params, doseq=True)
            clean_url = urllib.parse.urlunparse((
                parsed.scheme, parsed.netloc, parsed.path,
                parsed.params, new_query, parsed.fragment
            ))
            return clean_url
        
        return url

    def _is_supported_url(self, url: str) -> bool:
        """
        检查 URL 是否支持（内部方法）

        Args:
            url (str): 视频 URL

        Returns:
            bool: 支持返回 True，不支持返回 False
        """
        import re
        
        # 更精确的URL模式匹配
        bilibili_patterns = [
            r'https?://(?:www\.)?bilibili\.com/video/[A-Za-z0-9]+',
            r'https?://(?:www\.)?bilibili\.com/bangumi/play/[A-Za-z0-9]+',
            r'https?://(?:www\.)?bilibili\.com/cheese/play/[A-Za-z0-9]+'
        ]
        
        youtube_patterns = [
            r'https?://(?:www\.)?youtube\.com/watch\?v=[A-Za-z0-9_-]+',
            r'https?://(?:www\.)?youtube\.com/embed/[A-Za-z0-9_-]+',
            r'https?://(?:www\.)?youtube\.com/v/[A-Za-z0-9_-]+',
            r'https?://youtu\.be/[A-Za-z0-9_-]+',
            r'https?://(?:www\.)?youtube\.com/shorts/[A-Za-z0-9_-]+',
            r'https?://(?:m\.)?youtube\.com/watch\?v=[A-Za-z0-9_-]+'
        ]
        
        url_lower = url.lower().strip()
        
        # 检查B站链接
        for pattern in bilibili_patterns:
            if re.match(pattern, url_lower):
                return True
        
        # 检查YouTube链接
        for pattern in youtube_patterns:
            if re.match(pattern, url_lower):
                return True
        
        return False
