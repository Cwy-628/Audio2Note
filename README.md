# Audio2Note 桌面版

Audio2Note 是一款面向内容创作者与学习者的桌面工具，可从 B 站与 YouTube 下载视频并自动提取高质量 MP3 音频，也能离线将音频快速转写为文本。新版前端重构为 PySide6 桌面应用，摆脱浏览器依赖，提供原生的文件选择与任务反馈体验。

## ✨ 核心特性

- 🖥️ **原生桌面体验**：基于 PySide6 打造，支持 Windows、macOS 与 Linux。
- 🎬 **多平台视频支持**：适配 Bilibili、YouTube（含短链、番剧、Shorts 等）。
- 🎵 **高质量音频提取**：集成 yt-dlp + FFmpeg，输出 192 kbps MP3。
- 🎤 **音频转文字**：内置 faster-whisper 引擎，离线生成 txt 文稿。
- 🤖 **大模型助手**：侧边栏内置 DeepSeek Chat，可与大模型实时对话。
- 📁 **灵活的保存策略**：原生文件夹选择器，自动按视频标题整理文件。
- 🧠 **智能下载历史**：自动记录下载任务，双击即可重新填充链接。
- ⚙️ **可扩展后端**：保留 FastAPI 服务，便于自动化或二次开发。

## 🛠️ 系统要求

- Python 3.8 或更高版本
- FFmpeg（用于转码）
- 推荐使用虚拟环境隔离依赖

> 桌面应用会自动检测常见位置（如 `/opt/homebrew/bin/ffmpeg`、`/usr/local/bin/ffmpeg`）。  
> 如安装在其他路径，可设置环境变量 `FFMPEG_PATH` 指向可执行文件，或使用 `install_ffmpeg.py` 下载。  
> 首次使用音频转文字功能时会自动下载 faster-whisper 模型，可提前联网完成模型缓存。

## 📦 安装与环境准备

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 如果尚未安装 FFmpeg，可执行辅助脚本（macOS / Linux 会调用 curl 或包管理器）
python install_ffmpeg.py
```

> Windows 用户可通过 [Chocolatey](https://chocolatey.org/) 安装：`choco install ffmpeg`  
> macOS 用户推荐使用 [Homebrew](https://brew.sh/) 安装：`brew install ffmpeg`

## 🚀 快速开始

```bash
python start_native.py
```

启动后即可看到桌面界面，无需再运行额外的浏览器或 Electron 应用。

## 🖥️ 桌面应用使用指南

桌面端提供侧边栏，可在「下载音频」「音频转文字」「大模型助手」之间一键切换。

### 下载音频

1. **输入视频链接**：支持 B 站 / YouTube 的标准、短链与番剧链接。
2. **可选分 P 下载**：点击“启用分P”并填写需要的分 P 编号，关闭则下载全部分 P。
3. **选择下载目录**：默认保存在 `~/AI_Audio2Note_Downloads`，也可以手动指定路径。
4. **开始下载**：点击“开始下载”后程序会在后台运行并实时输出日志。
5. **查看结果**：任务完成后可直接打开保存目录，也可从历史列表重新发起下载。

### 音频转文字

1. **选择音频文件**：支持 MP3 / WAV / FLAC / M4A / AAC 等常见格式。
2. **选择识别模型**：提供 Tiny / Base / Small 可选（Tiny 更快，Small 更精确）。
3. **开始转写**：点击「开始转写」，后台自动执行 faster-whisper 离线识别。
4. **保存结果**：转写完成后可直接复制，或保存为 `.txt` 文档。

> 提示：模型首次下载可能耗时数分钟，后续使用可离线运行。

### 大模型助手（DeepSeek）

1. **填写 API Key**：在设置卡片中粘贴 DeepSeek API Key（格式 `sk-...`）。
2. **选择模型**：目前默认提供 `deepseek-chat`。
3. **开始对话**：在输入框中编辑问题，点击发送即可与大模型互动。
4. **批量处理转写文本**：点击「处理转写文本」将最近的转写结果按 5000 字符切片，多轮自动发送给大模型，并将所有回复整合成 Markdown（可下载保存）。
5. **查看历史**：对话历史展示在右侧卡片，支持滚动查看。

### 支持的视频链接示例

- `https://www.bilibili.com/video/BV1xxxxx`
- `https://www.bilibili.com/bangumi/play/xxxxx`
- `https://www.youtube.com/watch?v=xxxxx`
- `https://youtu.be/xxxxx`
- `https://www.youtube.com/shorts/xxxxx`

## 📂 项目结构

```
AI_Audio2Note/
├── ai_audio2note/             # 核心源码
│   ├── __init__.py
│   ├── backend/               # FastAPI 与下载服务
│   │   ├── __init__.py
│   │   ├── api.py             # REST API 入口（可选）
│   │   └── services/          # 下载与处理逻辑
│   │       ├── audio_downloader.py
│   │       ├── process_service.py
│   │       └── transcription_service.py
│   │       └── chat_service.py
│   └── gui/                   # PySide6 桌面界面
│       ├── __init__.py
│       └── app.py             # 主窗口、侧边栏与多功能页
├── build_all.py               # 发行版构建脚本（按平台输出）
├── build_quick.py             # 调试用 onedir 构建
├── install_ffmpeg.py          # FFmpeg 安装助手
├── requirements.txt           # Python 依赖列表
└── start_native.py            # 桌面应用入口
```

## 🧰 构建与分发

### 一键构建发行版（单文件）

```bash
python build_all.py
```

- 输出目录：`dist/AI_Audio2Note_<平台>/`
- Windows：生成 `AI_Audio2Note.exe` 与批处理启动脚本
- macOS：生成 `AI_Audio2Note.app` 与 `.command` 启动脚本，可直接双击运行
- Linux：生成可执行文件与 `start_ai_audio2note.sh`
- 同步附带 `install_ffmpeg.py` 与最新 `README.md`

### 快速调试构建（onedir）

```bash
python build_quick.py
```

该命令会在 `dist/debug/` 下生成可直接运行的目录结构，便于调试资源文件。

## 🔧 进阶说明

- **服务复用**：桌面端直接使用 `ai_audio2note.backend.services.ProcessService`、`TranscriptionService` 与 `ChatService`，无需额外启动 API。若要提供 REST 接口，可运行 `python -m ai_audio2note.backend.api`。
- **自定义存储结构**：ProcessService 会以视频标题创建独立会话目录，避免文件覆盖；可在 GUI 中自定义根目录。
- **FFmpeg 检测**：应用会检查 `FFMPEG_PATH` 环境变量、Homebrew 常用目录以及 PyInstaller 打包路径；若未找到会提示安装路径。
- **历史记录**：数据存储于本地 `~/.ai_audio2note_history.json`，仅保存最近 20 条记录。
- **Whisper 模型**：`faster-whisper` 首次使用时会下载模型到缓存目录（默认 `~/.cache/huggingface`）。可提前联网拉取，或设置 `FasterWhisperModelsPath` 指定缓存位置。
- **DeepSeek API**：大模型助手会使用用户提供的 DeepSeek API Key，请妥善保管；如果需要其他模型，可在 UI 中扩展模型列表。

## 🐛 常见问题

- **FFmpeg 未找到**：确认已安装并在 PATH 中；若使用脚本安装，请重新打开终端。
- **下载失败**：
  - 检查网络环境或平台限制。
  - 确认链接公开可访问，未设置区域/年龄限制。
  - 更新 yt-dlp：`pip install --upgrade yt-dlp`
- **无法写入目录**：确保目标目录具有写权限，必要时以管理员/终端授权运行。
- **UI 无响应**：下载任务在后台线程执行，如需终止可直接关闭窗口；程序会安全结束后台线程。

## 🤝 贡献指南

1. Fork 仓库并创建分支
2. 完成功能开发或问题修复
3. 提交遵循规范的 Pull Request

欢迎提交 Issue 交流功能建议与使用反馈。

## 🙏 致谢

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — 强大的视频下载工具
- [FFmpeg](https://ffmpeg.org/) — 全能音视频处理框架
- [PySide6](https://doc.qt.io/qtforpython/) — Qt 官方 Python 绑定
- [FastAPI](https://fastapi.tiangolo.com/) — 现代化 Python Web 框架

---

**AI Audio2Note** — 让视频音频提取随时随地、触手可及！ 🎵
