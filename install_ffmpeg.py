#!/usr/bin/env python3
"""
FFmpeg 自动安装脚本
为没有代码基础的用户提供FFmpeg安装帮助
"""

import os
import sys
import platform
import subprocess
import webbrowser
from pathlib import Path

def check_ffmpeg():
    """检查FFmpeg是否已安装"""
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ FFmpeg 已安装")
            print(f"版本信息: {result.stdout.split('ffmpeg version')[1].split()[0]}")
            return True
    except FileNotFoundError:
        pass
    
    print("❌ FFmpeg 未安装")
    return False

def install_ffmpeg_windows():
    """Windows FFmpeg安装指导"""
    print("🪟 Windows FFmpeg 安装指导")
    print("=" * 50)
    
    print("方法1: 使用Chocolatey (推荐)")
    print("1. 打开PowerShell (管理员权限)")
    print("2. 运行: Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))")
    print("3. 运行: choco install ffmpeg")
    print()
    
    print("方法2: 手动安装")
    print("1. 访问: https://ffmpeg.org/download.html")
    print("2. 下载Windows版本")
    print("3. 解压到 C:\\ffmpeg")
    print("4. 添加 C:\\ffmpeg\\bin 到系统PATH")
    print()
    
    # 尝试自动打开下载页面
    try:
        webbrowser.open("https://ffmpeg.org/download.html")
        print("🌐 已自动打开FFmpeg下载页面")
    except:
        pass

def install_ffmpeg_mac():
    """macOS FFmpeg安装指导"""
    print("🍎 macOS FFmpeg 安装指导")
    print("=" * 50)
    
    print("方法1: 使用Homebrew (推荐)")
    print("1. 安装Homebrew (如果未安装):")
    print("   /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
    print("2. 安装FFmpeg:")
    print("   brew install ffmpeg")
    print()
    
    print("方法2: 使用MacPorts")
    print("1. 安装MacPorts: https://www.macports.org/install.php")
    print("2. 运行: sudo port install ffmpeg")
    print()
    
    # 检查是否有Homebrew
    try:
        result = subprocess.run(["brew", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ 检测到Homebrew，正在安装FFmpeg...")
            try:
                subprocess.run(["brew", "install", "ffmpeg"], check=True)
                print("✅ FFmpeg 安装成功！")
                return True
            except subprocess.CalledProcessError:
                print("❌ 自动安装失败，请手动安装")
        else:
            print("❌ 未检测到Homebrew")
    except FileNotFoundError:
        print("❌ 未检测到Homebrew")
    
    return False

def install_ffmpeg_linux():
    """Linux FFmpeg安装指导"""
    print("🐧 Linux FFmpeg 安装指导")
    print("=" * 50)
    
    print("Ubuntu/Debian:")
    print("sudo apt update")
    print("sudo apt install ffmpeg")
    print()
    
    print("CentOS/RHEL:")
    print("sudo yum install ffmpeg")
    print()
    
    print("Fedora:")
    print("sudo dnf install ffmpeg")
    print()
    
    print("Arch Linux:")
    print("sudo pacman -S ffmpeg")
    print()

def main():
    """主函数"""
    print("🎵 AI Audio2Note - FFmpeg 安装助手")
    print("=" * 50)
    
    # 检查FFmpeg是否已安装
    if check_ffmpeg():
        print("🎉 FFmpeg 已正确安装，可以正常使用AI Audio2Note！")
        return
    
    print("FFmpeg 是AI Audio2Note的必需依赖，用于音频处理。")
    print("请根据您的操作系统选择安装方法：")
    print()
    
    system = platform.system().lower()
    
    if system == "windows":
        install_ffmpeg_windows()
    elif system == "darwin":
        if not install_ffmpeg_mac():
            print("请按照上述指导手动安装FFmpeg")
    elif system == "linux":
        install_ffmpeg_linux()
    else:
        print(f"❌ 不支持的操作系统: {system}")
        return
    
    print("\n安装完成后，请重新运行此脚本验证安装。")
    print("或者直接启动AI Audio2Note测试功能。")

if __name__ == "__main__":
    main()
