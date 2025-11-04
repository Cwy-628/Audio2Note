"""
PySide6-based desktop application for AI Audio2Note.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QThread, Qt, Signal, Slot, QTimer
from PySide6.QtGui import QDesktopServices, QColor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QComboBox,
    QFrame,
    QPlainTextEdit,
    QProgressBar,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QGraphicsDropShadowEffect,
    QScrollArea,
    QTextEdit,
)
from PySide6.QtCore import QUrl

from ai_audio2note.backend.services.process_service import ProcessService
from ai_audio2note.backend.services.transcription_service import TranscriptionService
from ai_audio2note.backend.services.chat_service import ChatService, ChatMessage, LLMError


DEFAULT_DOWNLOAD_DIR = Path.home() / "AI_Audio2Note_Downloads"
HISTORY_FILE = Path.home() / ".ai_audio2note_history.json"
SUPPORTED_DOMAINS = ("bilibili.com", "youtube.com", "youtu.be")


@dataclass
class HistoryItem:
    url: str
    title: str
    timestamp: str


class DownloadWorker(QThread):
    progress = Signal(str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, url: str, page_number: Optional[int], download_dir: Optional[str]):
        super().__init__()
        self.url = url
        self.page_number = page_number
        self.download_dir = download_dir

    def run(self) -> None:
        try:
            base_dir = self.download_dir or str(DEFAULT_DOWNLOAD_DIR)
            base_path = Path(base_dir).expanduser().resolve()
            base_path.mkdir(parents=True, exist_ok=True)

            self.progress.emit(f"下载目录: {base_path}")
            service = ProcessService(str(base_path))
            result = service.process_video(self.url, self.page_number)
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class TranscriptionWorker(QThread):
    progress = Signal(str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, audio_path: str, model_size: str):
        super().__init__()
        self.audio_path = audio_path
        self.model_size = model_size

    def run(self) -> None:
        try:
            service = TranscriptionService(model_size=self.model_size)
            text, info = service.transcribe_audio(
                self.audio_path,
                progress_callback=self.progress.emit,
            )
            self.finished.emit({"success": True, "text": text, "info": info})
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class ChatBatchWorker(QThread):
    progress = Signal(str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, api_key: str, model: str, text: str, instruction: str, chunk_size: int = 5000):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.text = text
        self.instruction = instruction
        self.chunk_size = max(1, chunk_size)

    def run(self) -> None:
        try:
            service = ChatService(api_key=self.api_key, model=self.model)
            chunks = [
                self.text[i : i + self.chunk_size]
                for i in range(0, len(self.text), self.chunk_size)
            ]
            if not chunks:
                raise ValueError("文本内容为空，无法处理")

            responses: list[ChatMessage] = []
            total = len(chunks)
            for idx, chunk in enumerate(chunks, start=1):
                prompt = (
                    f"{self.instruction}\n\n"
                    f"以下是第 {idx}/{total} 段文本内容，请按要求给出总结或分析：\n\n{chunk}"
                )
                reply = service.chat([], prompt)
                responses.append(ChatMessage(role="assistant", content=reply))
                self.progress.emit(f"已完成第 {idx}/{total} 段处理")

            markdown_sections = [
                f"## 第 {idx + 1} 段回复\n\n{msg.content}"
                for idx, msg in enumerate(responses)
            ]
            combined = "# 大模型回复汇总\n\n" + "\n\n".join(markdown_sections)
            self.finished.emit({"markdown": combined, "sections": markdown_sections})
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Audio2Note")
        self.resize(1180, 740)
        self.setMinimumSize(1180, 740)

        self.download_dir: Optional[str] = None
        self.last_session_path: Optional[str] = None
        self.history: List[HistoryItem] = []

        self.worker: Optional[DownloadWorker] = None
        self.transcribe_worker: Optional[TranscriptionWorker] = None
        self.transcribe_selected_file: Optional[str] = None
        self.transcription_result: Optional[str] = None

        self.chat_api_key: Optional[str] = None
        self.chat_history: List[ChatMessage] = []
        self.chat_service: Optional[ChatService] = None
        self.chat_batch_worker: Optional[ChatBatchWorker] = None
        self.chat_batch_markdown: Optional[str] = None

        self.sidebar_buttons: List[QPushButton] = []
        self.stacked_widget: Optional[QStackedWidget] = None

        self._build_ui()
        self._load_history()
        self._switch_page(0)

    # ------------------------------------------------------------------ UI BUILDERS
    def _build_ui(self) -> None:
        central = QWidget(self)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(24)

        sidebar = self._create_sidebar()
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self._create_download_page())
        self.stacked_widget.addWidget(self._create_transcription_page())
        self.stacked_widget.addWidget(self._create_chat_page())

        root_layout.addWidget(sidebar, 0)
        root_layout.addWidget(self.stacked_widget, 1)

        self.setCentralWidget(central)
        self._apply_styles()
        self._apply_shadows()

    def _create_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 24, 16, 24)
        layout.setSpacing(12)

        title = QLabel("Audio2Note")
        title.setObjectName("sidebarTitle")
        layout.addWidget(title)

        subtitle = QLabel("音频工作台")
        subtitle.setObjectName("sidebarSubtitle")
        layout.addWidget(subtitle)
        layout.addSpacing(12)

        pages = [
            ("下载音频", 0),
            ("音频转文字", 1),
            ("大模型助手", 2),
        ]
        for text, index in pages:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setProperty("kind", "sidebar")
            btn.clicked.connect(lambda _, i=index: self._switch_page(i))
            self.sidebar_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch(1)
        version = QLabel("v1.0 桌面版")
        version.setObjectName("sidebarVersion")
        version.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(version)

        return sidebar

    def _create_download_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(18)

        header_frame = QFrame()
        header_frame.setObjectName("headerFrame")
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(28, 28, 28, 28)
        header_layout.setSpacing(8)

        title = QLabel("下载音频 · 高保真提取")
        title.setObjectName("heroTitle")
        header_layout.addWidget(title)

        subtitle = QLabel("支持 Bilibili 与 YouTube 链接，自动提取 192kbps MP3")
        subtitle.setObjectName("heroSubtitle")
        header_layout.addWidget(subtitle)

        helper = QLabel("填写视频链接并选择存储位置，点击开始即可完成下载与转码。")
        helper.setObjectName("heroHelper")
        header_layout.addWidget(helper)

        page_layout.addWidget(header_frame)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(24)

        controls_card = QFrame()
        controls_card.setObjectName("card")
        controls_layout = QVBoxLayout(controls_card)
        controls_layout.setContentsMargins(24, 24, 24, 24)
        controls_layout.setSpacing(16)

        inputs_title = QLabel("下载设置")
        inputs_title.setObjectName("sectionTitle")
        controls_layout.addWidget(inputs_title)

        url_label = QLabel("视频链接")
        url_label.setObjectName("fieldLabel")
        controls_layout.addWidget(url_label)

        self.url_input = QLineEdit()
        self.url_input.setObjectName("urlInput")
        self.url_input.setPlaceholderText("例如：https://www.bilibili.com/video/BV1xxxx 或 https://youtu.be/xxxx")
        controls_layout.addWidget(self.url_input)

        url_hint = QLabel("支持 Bilibili、YouTube、Shorts 等公开链接")
        url_hint.setObjectName("helperText")
        controls_layout.addWidget(url_hint)
        controls_layout.addWidget(self._create_divider())

        page_row = QHBoxLayout()
        page_row.setSpacing(12)
        page_label = QLabel("分P编号")
        page_label.setObjectName("fieldLabel")
        page_row.addWidget(page_label)

        self.page_input = QSpinBox()
        self.page_input.setMinimum(0)
        self.page_input.setMaximum(9999)
        self.page_input.setSpecialValueText("所有分P")
        self.page_input.setValue(0)
        self.page_input.setEnabled(False)
        self.page_input.setObjectName("pageInput")
        page_row.addWidget(self.page_input, stretch=1)

        self.page_toggle_btn = QPushButton("启用分P")
        self.page_toggle_btn.setCheckable(True)
        self.page_toggle_btn.setProperty("kind", "ghost")
        self.page_toggle_btn.toggled.connect(self._toggle_page_input)
        page_row.addWidget(self.page_toggle_btn)
        controls_layout.addLayout(page_row)
        controls_layout.addWidget(self._create_divider())

        dir_title = QLabel("下载目录")
        dir_title.setObjectName("fieldLabel")
        controls_layout.addWidget(dir_title)

        self.dir_label = QLabel(str(DEFAULT_DOWNLOAD_DIR))
        self.dir_label.setObjectName("directoryLabel")
        controls_layout.addWidget(self.dir_label)

        dir_actions = QHBoxLayout()
        dir_actions.addStretch()
        self.choose_dir_btn = QPushButton("选择文件夹")
        self.choose_dir_btn.setProperty("kind", "secondary")
        self.choose_dir_btn.clicked.connect(self._pick_download_dir)
        dir_actions.addWidget(self.choose_dir_btn)
        controls_layout.addLayout(dir_actions)
        controls_layout.addWidget(self._create_divider())

        actions = QHBoxLayout()
        actions.setSpacing(12)

        self.start_btn = QPushButton("开始下载")
        self.start_btn.setProperty("kind", "primary")
        self.start_btn.clicked.connect(self._handle_download)
        self.start_btn.setMinimumHeight(46)
        actions.addWidget(self.start_btn, stretch=1)

        self.open_dir_btn = QPushButton("打开保存目录")
        self.open_dir_btn.setEnabled(False)
        self.open_dir_btn.setProperty("kind", "secondary")
        self.open_dir_btn.clicked.connect(self._open_last_session)
        self.open_dir_btn.setMinimumHeight(46)
        actions.addWidget(self.open_dir_btn, stretch=1)

        controls_layout.addLayout(actions)

        self.download_status_label = QLabel()
        self.download_status_label.setObjectName("statusLabel")
        controls_layout.addWidget(self.download_status_label)

        self.download_progress_bar = QProgressBar()
        self.download_progress_bar.setObjectName("progressBar")
        self.download_progress_bar.setVisible(False)
        controls_layout.addWidget(self.download_progress_bar)

        controls_layout.addStretch(1)

        output_card = QFrame()
        output_card.setObjectName("card")
        output_layout = QVBoxLayout(output_card)
        output_layout.setContentsMargins(24, 24, 24, 24)
        output_layout.setSpacing(16)

        log_title = QLabel("下载日志")
        log_title.setObjectName("sectionTitle")
        output_layout.addWidget(log_title)

        self.log_output = QPlainTextEdit()
        self.log_output.setObjectName("logOutput")
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("任务日志将在此显示")
        self.log_output.setMinimumHeight(180)
        output_layout.addWidget(self.log_output, stretch=1)

        output_layout.addWidget(self._create_divider())

        history_title = QLabel("下载历史")
        history_title.setObjectName("sectionTitle")
        output_layout.addWidget(history_title)

        history_hint = QLabel("双击历史记录可自动填充链接")
        history_hint.setObjectName("helperText")
        output_layout.addWidget(history_hint)

        self.history_list = QListWidget()
        self.history_list.setObjectName("historyList")
        self.history_list.itemDoubleClicked.connect(self._apply_history_item)
        output_layout.addWidget(self.history_list, stretch=1)

        content_layout.addWidget(controls_card, stretch=3)
        content_layout.addWidget(output_card, stretch=4)

        page_layout.addLayout(content_layout)
        return page

    def _create_transcription_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        header_frame = QFrame()
        header_frame.setObjectName("headerFrame")
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(28, 28, 28, 28)
        header_layout.setSpacing(8)

        title = QLabel("音频转文字 · 一键生成字幕稿")
        title.setObjectName("heroTitle")
        header_layout.addWidget(title)

        subtitle = QLabel("上传音频文件，使用 Whisper 模型离线转写为文本")
        subtitle.setObjectName("heroSubtitle")
        header_layout.addWidget(subtitle)

        helper = QLabel("支持 MP3、WAV、FLAC、M4A 等常见格式，生成 txt 文稿。")
        helper.setObjectName("heroHelper")
        header_layout.addWidget(helper)

        layout.addWidget(header_frame)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(24)

        settings_card = QFrame()
        settings_card.setObjectName("card")
        settings_card.setFixedWidth(360)
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(24, 24, 24, 24)
        settings_layout.setSpacing(16)

        settings_title = QLabel("转写设置")
        settings_title.setObjectName("sectionTitle")
        settings_layout.addWidget(settings_title)

        file_label = QLabel("音频文件")
        file_label.setObjectName("fieldLabel")
        settings_layout.addWidget(file_label)

        self.transcribe_file_view = QPlainTextEdit("尚未选择文件")
        self.transcribe_file_view.setObjectName("pathOutput")
        self.transcribe_file_view.setReadOnly(True)
        self.transcribe_file_view.setFixedHeight(60)
        self.transcribe_file_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.transcribe_file_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.transcribe_file_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        settings_layout.addWidget(self.transcribe_file_view)

        file_actions = QHBoxLayout()
        file_actions.addStretch()
        self.transcribe_pick_btn = QPushButton("选择音频文件")
        self.transcribe_pick_btn.setProperty("kind", "secondary")
        self.transcribe_pick_btn.clicked.connect(self._select_audio_file)
        file_actions.addWidget(self.transcribe_pick_btn)
        settings_layout.addLayout(file_actions)
        settings_layout.addWidget(self._create_divider())

        model_row = QHBoxLayout()
        model_row.setSpacing(12)
        model_label = QLabel("识别模型")
        model_label.setObjectName("fieldLabel")
        model_row.addWidget(model_label)

        self.model_select = QComboBox()
        self.model_select.addItem("Base (推荐)", "base")
        self.model_select.addItem("Small (更精准)", "small")
        self.model_select.addItem("Tiny (更快)", "tiny")
        self.model_select.setObjectName("modelSelect")
        model_row.addWidget(self.model_select, stretch=1)
        settings_layout.addLayout(model_row)

        settings_layout.addWidget(self._create_divider())

        transcribe_actions = QHBoxLayout()
        transcribe_actions.setSpacing(12)

        self.transcribe_start_btn = QPushButton("开始转写")
        self.transcribe_start_btn.setProperty("kind", "primary")
        self.transcribe_start_btn.setEnabled(False)
        self.transcribe_start_btn.clicked.connect(self._handle_transcription)
        self.transcribe_start_btn.setMinimumHeight(44)
        transcribe_actions.addWidget(self.transcribe_start_btn, stretch=1)

        settings_layout.addLayout(transcribe_actions)

        self.transcribe_status_label = QLabel("请先选择音频文件")
        self.transcribe_status_label.setObjectName("statusLabel")
        settings_layout.addWidget(self.transcribe_status_label)

        self.transcribe_progress_bar = QProgressBar()
        self.transcribe_progress_bar.setObjectName("progressBar")
        self.transcribe_progress_bar.setVisible(False)
        settings_layout.addWidget(self.transcribe_progress_bar)
        settings_layout.addStretch(1)

        result_card = QFrame()
        result_card.setObjectName("card")
        result_card.setMinimumWidth(420)
        result_card.setMaximumWidth(420)
        result_outer_layout = QVBoxLayout(result_card)
        result_outer_layout.setContentsMargins(0, 0, 0, 0)

        result_scroll = QScrollArea()
        result_scroll.setWidgetResizable(True)
        result_scroll.setFrameShape(QFrame.NoFrame)

        result_container = QWidget()
        result_layout = QVBoxLayout(result_container)
        result_layout.setContentsMargins(24, 24, 24, 24)
        result_layout.setSpacing(16)

        result_title = QLabel("转写结果")
        result_title.setObjectName("sectionTitle")
        result_layout.addWidget(result_title)

        self.transcribe_text_output = QPlainTextEdit()
        self.transcribe_text_output.setObjectName("logOutput")
        self.transcribe_text_output.setReadOnly(True)
        self.transcribe_text_output.setPlaceholderText("转写后的文本将在此显示")
        self.transcribe_text_output.setMinimumHeight(260)
        result_layout.addWidget(self.transcribe_text_output, stretch=1)

        save_actions = QHBoxLayout()
        save_actions.addStretch()
        self.transcribe_push_btn = QPushButton("推送到大模型助手")
        self.transcribe_push_btn.setProperty("kind", "secondary")
        self.transcribe_push_btn.setEnabled(False)
        self.transcribe_push_btn.clicked.connect(self._push_transcript_to_chat)
        self.transcribe_push_btn.setMinimumHeight(42)
        save_actions.addWidget(self.transcribe_push_btn)

        self.transcribe_save_btn = QPushButton("保存为 TXT")
        self.transcribe_save_btn.setProperty("kind", "secondary")
        self.transcribe_save_btn.setEnabled(False)
        self.transcribe_save_btn.clicked.connect(self._save_transcription)
        self.transcribe_save_btn.setMinimumHeight(42)
        save_actions.addWidget(self.transcribe_save_btn)
        result_layout.addLayout(save_actions)
        result_layout.addStretch(1)

        result_scroll.setWidget(result_container)
        result_outer_layout.addWidget(result_scroll)

        content_layout.addWidget(settings_card, stretch=3)
        content_layout.addWidget(result_card, stretch=4)
        layout.addLayout(content_layout)
        return page

    def _create_chat_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        header_frame = QFrame()
        header_frame.setObjectName("headerFrame")
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(28, 28, 28, 28)
        header_layout.setSpacing(8)

        title = QLabel("大模型助手 · DeepSeek")
        title.setObjectName("heroTitle")
        header_layout.addWidget(title)

        subtitle = QLabel("连接 DeepSeek Chat，与智能助手实时互动")
        subtitle.setObjectName("heroSubtitle")
        header_layout.addWidget(subtitle)

        helper = QLabel("首先填写 API Key，随后即可开始对话。")
        helper.setObjectName("heroHelper")
        header_layout.addWidget(helper)

        layout.addWidget(header_frame)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(24)

        config_card = QFrame()
        config_card.setObjectName("card")
        config_card.setFixedWidth(360)
        config_layout = QVBoxLayout(config_card)
        config_layout.setContentsMargins(24, 24, 24, 24)
        config_layout.setSpacing(16)

        config_title = QLabel("连接设置")
        config_title.setObjectName("sectionTitle")
        config_layout.addWidget(config_title)

        key_label = QLabel("DeepSeek API Key")
        key_label.setObjectName("fieldLabel")
        config_layout.addWidget(key_label)

        self.chat_api_input = QLineEdit()
        self.chat_api_input.setPlaceholderText("sk-...")
        config_layout.addWidget(self.chat_api_input)

        self.chat_model_select = QComboBox()
        self.chat_model_select.addItem("deepseek-chat", "deepseek-chat")
        self.chat_model_select.setObjectName("modelSelect")
        config_layout.addWidget(self.chat_model_select)

        connect_btn = QPushButton("保存设置")
        connect_btn.setProperty("kind", "secondary")
        connect_btn.clicked.connect(self._save_chat_credentials)
        config_layout.addWidget(connect_btn)

        instruction_label = QLabel("批处理指令")
        instruction_label.setObjectName("fieldLabel")
        config_layout.addWidget(instruction_label)

        self.chat_instruction_input = QTextEdit()
        self.chat_instruction_input.setObjectName("chatInput")
        self.chat_instruction_input.setPlaceholderText("示例：请将以下文本总结为结构化的 Markdown 笔记，突出重点和待办事项。")
        self.chat_instruction_input.setFixedHeight(110)
        self.chat_instruction_input.setPlainText("请将以下内容总结为结构化的 Markdown 笔记，其中包含关键信息、要点列表以及可执行的待办项。")
        config_layout.addWidget(self.chat_instruction_input)

        config_layout.addWidget(self._create_divider())

        recent_label = QLabel("提示：API Key 将缓存在本地，仅在当前设备使用。")
        recent_label.setObjectName("helperText")
        config_layout.addWidget(recent_label)
        config_layout.addStretch(1)

        chat_card = QFrame()
        chat_card.setObjectName("card")
        chat_layout = QVBoxLayout(chat_card)
        chat_layout.setContentsMargins(24, 24, 24, 24)
        chat_layout.setSpacing(16)

        conversation_label = QLabel("对话历史")
        conversation_label.setObjectName("sectionTitle")
        chat_layout.addWidget(conversation_label)

        self.chat_history_view = QPlainTextEdit()
        self.chat_history_view.setObjectName("logOutput")
        self.chat_history_view.setReadOnly(True)
        self.chat_history_view.setPlaceholderText("这里将显示与 DeepSeek 的对话")
        self.chat_history_view.setMinimumHeight(280)
        chat_layout.addWidget(self.chat_history_view, stretch=1)

        batch_actions = QHBoxLayout()
        batch_actions.setSpacing(12)
        batch_actions.addStretch()

        self.chat_run_batch_btn = QPushButton("处理转写文本")
        self.chat_run_batch_btn.setProperty("kind", "secondary")
        self.chat_run_batch_btn.clicked.connect(self._run_transcript_batch)
        self.chat_run_batch_btn.setMinimumHeight(40)
        batch_actions.addWidget(self.chat_run_batch_btn)

        self.chat_download_btn = QPushButton("下载 Markdown")
        self.chat_download_btn.setProperty("kind", "secondary")
        self.chat_download_btn.setEnabled(False)
        self.chat_download_btn.clicked.connect(self._download_chat_markdown)
        self.chat_download_btn.setMinimumHeight(40)
        batch_actions.addWidget(self.chat_download_btn)

        chat_layout.addLayout(batch_actions)

        self.chat_input = QTextEdit()
        self.chat_input.setObjectName("chatInput")
        self.chat_input.setPlaceholderText("请输入要发送给大模型的内容......")
        self.chat_input.setFixedHeight(110)
        chat_layout.addWidget(self.chat_input)

        chat_actions = QHBoxLayout()
        chat_actions.setSpacing(12)
        chat_actions.addStretch()

        self.chat_send_btn = QPushButton("发送")
        self.chat_send_btn.setProperty("kind", "primary")
        self.chat_send_btn.clicked.connect(self._handle_chat_send)
        self.chat_send_btn.setMinimumHeight(42)
        chat_actions.addWidget(self.chat_send_btn)

        chat_layout.addLayout(chat_actions)

        self.chat_status_label = QLabel("请先填写 API Key")
        self.chat_status_label.setObjectName("statusLabel")
        chat_layout.addWidget(self.chat_status_label)

        content_layout.addWidget(config_card, stretch=0)
        content_layout.addWidget(chat_card, stretch=1)

        layout.addLayout(content_layout)
        return page

    # ------------------------------------------------------------------ STYLING
    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background-color: #f4f6fb;
                color: #1f2937;
                font-family: 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif;
                font-size: 14px;
            }
            QFrame#sidebar {
                background-color: #ffffff;
                border-radius: 20px;
                border: 1px solid rgba(203, 213, 225, 0.7);
            }
            QLabel#sidebarTitle {
                font-size: 20px;
                font-weight: 700;
                color: #1d4ed8;
            }
            QLabel#sidebarSubtitle {
                font-size: 13px;
                color: #475569;
            }
            QLabel#sidebarVersion {
                font-size: 12px;
                color: #94a3b8;
            }
            QPushButton[kind="sidebar"] {
                padding: 12px 16px;
                border-radius: 12px;
                text-align: left;
                font-weight: 600;
                color: #1f2937;
                border: 1px solid transparent;
                background-color: transparent;
            }
            QPushButton[kind="sidebar"]:hover {
                background-color: #e0e7ff;
                border-color: rgba(99, 102, 241, 0.35);
            }
            QPushButton[kind="sidebar"]:checked {
                background-color: #3b82f6;
                color: #ffffff;
                border-color: rgba(59, 130, 246, 0.8);
            }
            QFrame#headerFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                            stop:0 #f8fbff, stop:1 #e8f0ff);
                border-radius: 20px;
                border: 1px solid rgba(59, 130, 246, 0.18);
            }
            QLabel#heroTitle {
                font-size: 28px;
                font-weight: 700;
                color: #1d4ed8;
            }
            QLabel#heroSubtitle {
                font-size: 16px;
                color: #2563eb;
                font-weight: 600;
            }
            QLabel#heroHelper {
                font-size: 13px;
                color: #475569;
            }
            QFrame#card {
                background-color: #ffffff;
                border-radius: 20px;
                border: 1px solid rgba(203, 213, 225, 0.7);
            }
            QLabel#sectionTitle {
                font-size: 16px;
                font-weight: 600;
                color: #1f2937;
            }
            QLabel#fieldLabel {
                font-size: 13px;
                font-weight: 600;
                color: #334155;
            }
            QLabel#helperText {
                font-size: 12px;
                color: #64748b;
            }
            QLabel#directoryLabel {
                padding: 10px 12px;
                border-radius: 12px;
                background-color: #f8fafc;
                border: 1px solid rgba(148, 163, 184, 0.45);
                color: #1e293b;
            }
            QLineEdit,
            QSpinBox,
            QComboBox {
                padding: 10px 12px;
                border-radius: 12px;
                border: 1px solid rgba(148, 163, 184, 0.5);
                background-color: #ffffff;
                color: #0f172a;
                selection-background-color: rgba(59, 130, 246, 0.25);
                selection-color: #0f172a;
            }
            QLineEdit:focus,
            QSpinBox:focus,
            QComboBox:focus {
                border-color: #3b82f6;
                background-color: #f8faff;
            }
            QComboBox::drop-down {
                border: none;
                width: 22px;
            }
            QPushButton {
                border-radius: 12px;
                padding: 12px 16px;
                font-weight: 600;
                border: 1px solid transparent;
                font-size: 15px;
            }
            QPushButton[kind="primary"] {
                background-color: #2563eb;
                color: #ffffff;
            }
            QPushButton[kind="primary"]:hover {
                background-color: #1d4ed8;
            }
            QPushButton[kind="primary"]:disabled {
                background-color: rgba(37, 99, 235, 0.35);
                color: rgba(255, 255, 255, 0.7);
            }
            QPushButton[kind="secondary"] {
                background-color: #f1f5ff;
                color: #1f2937;
                border: 1px solid rgba(99, 102, 241, 0.45);
            }
            QPushButton[kind="secondary"]:hover {
                background-color: #dbeafe;
            }
            QPushButton[kind="secondary"]:disabled {
                color: rgba(15, 23, 42, 0.45);
                background-color: rgba(224, 231, 255, 0.7);
            }
            QPushButton[kind="secondary"]:focus,
            QPushButton[kind="primary"]:focus,
            QPushButton[kind="ghost"]:focus,
            QPushButton[kind="sidebar"]:focus {
                outline: none;
            }
            QPushButton[kind="ghost"] {
                background-color: transparent;
                color: #475569;
                border: 1px dashed rgba(148, 163, 184, 0.6);
                padding: 10px 14px;
            }
            QPushButton[kind="ghost"]:hover {
                color: #1d4ed8;
                border-color: rgba(37, 99, 235, 0.6);
            }
            QPushButton[kind="ghost"]:checked {
                background-color: #dbeafe;
                color: #1d4ed8;
                border-style: solid;
                border-color: rgba(37, 99, 235, 0.6);
            }
            QPlainTextEdit#logOutput {
                background-color: #f8fafc;
                border-radius: 16px;
                border: 1px solid rgba(148, 163, 184, 0.35);
                padding: 12px;
                color: #0f172a;
            }
            QTextEdit#chatInput {
                border-radius: 16px;
                border: 1px solid rgba(148, 163, 184, 0.35);
                background-color: #f8fafc;
                padding: 12px;
                color: #0f172a;
            }
            QPlainTextEdit#pathOutput {
                background-color: #f8fafc;
                border-radius: 12px;
                border: 1px solid rgba(148, 163, 184, 0.45);
                padding: 8px 12px;
                color: #0f172a;
            }
            QListWidget#historyList {
                background-color: #f8fafc;
                border-radius: 16px;
                border: 1px solid rgba(148, 163, 184, 0.25);
                padding: 8px;
            }
            QListWidget#historyList::item {
                border-radius: 10px;
                padding: 10px;
                margin: 4px;
                color: #0f172a;
            }
            QListWidget#historyList::item:hover {
                background-color: rgba(191, 219, 254, 0.6);
            }
            QListWidget#historyList::item:selected {
                background-color: #bfdbfe;
                color: #1d4ed8;
            }
            QFrame#divider {
                background-color: rgba(148, 163, 184, 0.24);
                max-height: 1px;
                min-height: 1px;
            }
            QProgressBar#progressBar {
                height: 14px;
                border-radius: 10px;
                border: 1px solid rgba(148, 163, 184, 0.28);
                background-color: #e2e8f0;
                text-align: center;
                color: transparent;
            }
            QProgressBar#progressBar::chunk {
                border-radius: 8px;
                background-color: #3b82f6;
            }
            QLabel#statusLabel {
                padding: 10px 14px;
                border-radius: 12px;
                font-weight: 600;
                border: 1px solid transparent;
                color: #2563eb;
                background-color: rgba(37, 99, 235, 0.12);
            }
            QLabel#statusLabel[status="info"] {
                color: #2563eb;
                background-color: rgba(37, 99, 235, 0.12);
            }
            QLabel#statusLabel[status="success"] {
                color: #16a34a;
                background-color: rgba(74, 222, 128, 0.18);
            }
            QLabel#statusLabel[status="error"] {
                color: #dc2626;
                background-color: rgba(248, 113, 113, 0.2);
            }
            QLabel#statusLabel[status="loading"] {
                color: #ca8a04;
                background-color: rgba(250, 204, 21, 0.24);
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                background: transparent;
                width: 10px;
                height: 10px;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: rgba(148, 163, 184, 0.48);
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
                background: rgba(148, 163, 184, 0.7);
            }
            """
        )

    def _apply_shadows(self) -> None:
        for frame in self.findChildren(QFrame):
            name = frame.objectName()
            if name in {"card", "sidebar"}:
                effect = QGraphicsDropShadowEffect(frame)
                effect.setBlurRadius(24)
                effect.setColor(QColor(15, 23, 42, 60))
                effect.setOffset(0, 8)
                frame.setGraphicsEffect(effect)

    @staticmethod
    def _create_divider() -> QFrame:
        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Plain)
        divider.setFixedHeight(1)
        return divider

    # ------------------------------------------------------------------ NAVIGATION
    def _switch_page(self, index: int) -> None:
        if self.stacked_widget is None:
            return
        self.stacked_widget.setCurrentIndex(index)
        for idx, btn in enumerate(self.sidebar_buttons):
            btn.blockSignals(True)
            btn.setChecked(idx == index)
            btn.blockSignals(False)

    # ------------------------------------------------------------------ DOWNLOAD FLOW
    @Slot(bool)
    def _toggle_page_input(self, checked: bool) -> None:
        if checked:
            self.page_input.setEnabled(True)
            self.page_toggle_btn.setText("使用所有分P")
        else:
            self.page_input.setEnabled(False)
            self.page_toggle_btn.setText("启用分P")

    def _pick_download_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择下载目录")
        if directory:
            self.download_dir = directory
            self.dir_label.setText(directory)
            self._set_status("已更新下载目录", "success", self.download_status_label)

    def _handle_download(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            self._show_error("请输入视频链接")
            return
        if not self._is_supported_url(url):
            self._show_error("仅支持B站与YouTube视频链接")
            return

        page_number = None
        if self.page_input.isEnabled():
            value = int(self.page_input.value())
            page_number = value or None

        self.log_output.clear()
        self._append_log("开始处理任务...")
        self._set_download_loading_state(True, "正在下载，请稍候...")

        self.worker = DownloadWorker(url, page_number, self.download_dir)
        self.worker.progress.connect(self._append_log)
        self.worker.finished.connect(self._on_download_finished)
        self.worker.error.connect(self._on_worker_error)
        self.worker.start()

    def _set_download_loading_state(self, loading: bool, message: str = "") -> None:
        self.start_btn.setEnabled(not loading)
        self.choose_dir_btn.setEnabled(not loading)
        self.page_toggle_btn.setEnabled(not loading or self.page_toggle_btn.isChecked())
        self.download_progress_bar.setVisible(loading)
        if loading:
            self.download_progress_bar.setRange(0, 0)
            self._set_status(message or "正在处理...", "loading", self.download_status_label)
        else:
            self.download_progress_bar.setRange(0, 100)
            self.download_progress_bar.setValue(0)

    def _append_log(self, message: str) -> None:
        self.log_output.appendPlainText(message)

    def _on_download_finished(self, result: dict) -> None:
        self._set_download_loading_state(False, "任务已完成")
        self.worker = None

        if result.get("success"):
            files = result.get("files", [])
            session_folder = result.get("session_folder")
            self.last_session_path = session_folder
            self.open_dir_btn.setEnabled(bool(session_folder))

            summary_lines = [
                "下载完成！",
                f"视频标题：{result.get('video_title', '未知标题')}",
                f"保存目录：{session_folder}",
                "",
            ]

            if files:
                summary_lines.append("生成的文件：")
                summary_lines.extend(files)
            self._append_log("\n".join(summary_lines))

            self._set_status("下载完成 ✅", "success", self.download_status_label)
            self._save_history_entry(result)
        else:
            error_message = result.get("error", "未知错误")
            self._append_log(f"下载失败：{error_message}")
            self._show_error(f"下载失败：{error_message}")

    def _on_worker_error(self, message: str) -> None:
        self._set_download_loading_state(False)
        self.worker = None
        self._append_log(f"任务失败：{message}")
        self._show_error(f"任务失败：{message}")

    def _open_last_session(self) -> None:
        if not self.last_session_path:
            self._show_error("当前没有可打开的下载目录")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_session_path))

    def _apply_history_item(self, item: QListWidgetItem) -> None:
        url = item.data(Qt.ItemDataRole.UserRole)
        if url:
            self.url_input.setText(url)
            self._set_status("已从历史记录填充链接", "success", self.download_status_label)

    def _is_supported_url(self, url: str) -> bool:
        return any(domain in url for domain in SUPPORTED_DOMAINS)

    # ------------------------------------------------------------------ TRANSCRIPTION FLOW
    def _select_audio_file(self) -> None:
        filters = "音频文件 (*.mp3 *.wav *.m4a *.flac *.aac *.ogg);;所有文件 (*.*)"
        file_path, _ = QFileDialog.getOpenFileName(self, "选择音频文件", str(Path.home()), filters)
        if file_path:
            self.transcribe_selected_file = file_path
            self.transcribe_file_view.setPlainText(file_path)
            self.transcribe_start_btn.setEnabled(True)
            self._set_status("已选择音频文件", "success", self.transcribe_status_label)

    def _handle_transcription(self) -> None:
        if not self.transcribe_selected_file:
            self._set_status("请先选择音频文件", "error", self.transcribe_status_label)
            return
        audio_path = Path(self.transcribe_selected_file)
        if not audio_path.exists():
            self._set_status("音频文件不存在，请重新选择", "error", self.transcribe_status_label)
            return

        model_size = self.model_select.currentData()
        self.transcribe_text_output.clear()
        self.transcribe_save_btn.setEnabled(False)
        self._set_transcribe_loading_state(True, "正在转写，请稍候...")

        self.transcribe_worker = TranscriptionWorker(str(audio_path), model_size)
        self.transcribe_worker.progress.connect(
            lambda message: self._set_status(message, "loading", self.transcribe_status_label)
        )
        self.transcribe_worker.finished.connect(self._on_transcription_finished)
        self.transcribe_worker.error.connect(self._on_transcription_error)
        self.transcribe_worker.start()

    def _set_transcribe_loading_state(self, loading: bool, message: str = "") -> None:
        self.transcribe_start_btn.setEnabled(not loading)
        self.transcribe_pick_btn.setEnabled(not loading)
        self.model_select.setEnabled(not loading)
        self.transcribe_progress_bar.setVisible(loading)
        if loading:
            self.transcribe_progress_bar.setRange(0, 0)
            self._set_status(message or "正在处理...", "loading", self.transcribe_status_label)
        else:
            self.transcribe_progress_bar.setRange(0, 100)
            self.transcribe_progress_bar.setValue(0)

    def _on_transcription_finished(self, result: dict) -> None:
        self._set_transcribe_loading_state(False)
        self.transcribe_worker = None

        if result.get("success"):
            text = result.get("text", "")
            info = result.get("info", {})
            language = info.get("language", "")
            duration = info.get("duration", "")

            self.transcribe_text_output.setPlainText(text)
            self.transcription_result = text
            message = "转写完成 ✅"
            if language:
                message += f"（检测语言：{language}"
                if duration:
                    message += f"，音频时长：{duration}"
                message += "）"
            self._set_status(message, "success", self.transcribe_status_label)
            ready = bool(text.strip())
            self.transcribe_save_btn.setEnabled(ready)
            self.transcribe_push_btn.setEnabled(ready)
        else:
            error_message = result.get("error", "未知错误")
            self._set_status(f"转写失败：{error_message}", "error", self.transcribe_status_label)
            self.transcription_result = None
            self.transcribe_save_btn.setEnabled(False)
            self.transcribe_push_btn.setEnabled(False)

    def _on_transcription_error(self, message: str) -> None:
        self._set_transcribe_loading_state(False)
        self.transcribe_worker = None
        self._set_status(f"转写失败：{message}", "error", self.transcribe_status_label)

    def _save_transcription(self) -> None:
        text = self.transcribe_text_output.toPlainText().strip()
        if not text:
            self._set_status("没有可保存的文本", "error", self.transcribe_status_label)
            return

        default_dir = Path(self.transcribe_selected_file).parent if self.transcribe_selected_file else Path.home()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存转写结果",
            str(default_dir / "transcript.txt"),
            "文本文件 (*.txt);;所有文件 (*.*)",
        )
        if file_path:
            Path(file_path).write_text(text, encoding="utf-8")
            self._set_status(f"已保存到：{file_path}", "success", self.transcribe_status_label)

    # ------------------------------------------------------------------ CHAT FLOW

    def _push_transcript_to_chat(self) -> None:
        if not self.transcription_result or not self.transcription_result.strip():
            self._set_status("没有可推送的转写内容", "error", self.transcribe_status_label)
            return
        self._switch_page(2)
        QTimer.singleShot(150, lambda: self._start_chat_batch(self.transcription_result or ""))

    def _run_transcript_batch(self) -> None:
        if not self.transcription_result or not self.transcription_result.strip():
            self._set_status("请先完成音频转文字", "error", self.chat_status_label)
            return
        self._start_chat_batch(self.transcription_result)

    def _save_chat_credentials(self) -> None:
        api_key = self.chat_api_input.text().strip()
        model = self.chat_model_select.currentData()
        if not api_key:
            self._set_status("请填写有效的 API Key", "error", self.chat_status_label)
            return
        self.chat_api_key = api_key
        self.chat_service = ChatService(api_key=api_key, model=model)
        self._set_status("DeepSeek 已就绪，可以开始对话", "success", self.chat_status_label)

    def _start_chat_batch(self, text: str) -> None:
        if self.chat_batch_worker and self.chat_batch_worker.isRunning():
            self._set_status("已有批处理任务进行中，请稍候", "error", self.chat_status_label)
            return
        if not text.strip():
            self._set_status("转写内容为空，无法处理", "error", self.chat_status_label)
            return
        if not self.chat_api_key:
            self._set_status("请先保存 DeepSeek API Key", "error", self.chat_status_label)
            return
        instruction = self.chat_instruction_input.toPlainText().strip()
        if not instruction:
            instruction = "请将以下内容总结为结构化的 Markdown 笔记，其中包含关键信息、要点列表以及可执行的待办项。"

        self.chat_batch_markdown = None
        self.chat_download_btn.setEnabled(False)
        self.chat_run_batch_btn.setEnabled(False)
        self.chat_send_btn.setEnabled(False)
        self._set_status("正在批量处理转写文本...", "loading", self.chat_status_label)
        self.chat_history_view.appendPlainText("系统：开始批量处理转写文本...\n")

        self.chat_batch_worker = ChatBatchWorker(
            api_key=self.chat_api_key,
            model=self.chat_model_select.currentData(),
            text=text,
            instruction=instruction,
            chunk_size=5000,
        )
        self.chat_batch_worker.progress.connect(self._on_chat_batch_progress)
        self.chat_batch_worker.finished.connect(self._on_chat_batch_finished)
        self.chat_batch_worker.error.connect(self._on_chat_batch_error)
        self.chat_batch_worker.start()

    def _on_chat_batch_progress(self, message: str) -> None:
        self._set_status(message, "loading", self.chat_status_label)
        self.chat_history_view.appendPlainText(f"系统：{message}\n")

    def _on_chat_batch_finished(self, result: dict) -> None:
        self.chat_run_batch_btn.setEnabled(True)
        self.chat_send_btn.setEnabled(True)
        self.chat_batch_worker = None

        markdown = result.get("markdown", "")
        sections = result.get("sections", [])
        if sections:
            for section in sections:
                self.chat_history_view.appendPlainText(f"AI 批处理回复：\n{section}\n")

        self.chat_batch_markdown = markdown
        if markdown.strip():
            self.chat_download_btn.setEnabled(True)
        self._set_status("批处理完成 ✅", "success", self.chat_status_label)
        self.chat_history_view.appendPlainText("系统：批处理完成，已生成 Markdown 文档。\n")

    def _on_chat_batch_error(self, message: str) -> None:
        self.chat_run_batch_btn.setEnabled(True)
        self.chat_send_btn.setEnabled(True)
        self.chat_batch_worker = None
        self._set_status(f"批处理失败：{message}", "error", self.chat_status_label)
        self.chat_history_view.appendPlainText(f"系统：批处理失败，原因：{message}\n")
        self.chat_download_btn.setEnabled(bool(self.chat_batch_markdown and self.chat_batch_markdown.strip()))

    def _download_chat_markdown(self) -> None:
        if not self.chat_batch_markdown or not self.chat_batch_markdown.strip():
            self._set_status("暂无可下载的 Markdown", "error", self.chat_status_label)
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存模型回复",
            str(Path.home() / "llm_output.md"),
            "Markdown 文件 (*.md);;所有文件 (*.*)",
        )
        if file_path:
            Path(file_path).write_text(self.chat_batch_markdown, encoding="utf-8")
            self._set_status(f"已保存到：{file_path}", "success", self.chat_status_label)

    def _handle_chat_send(self) -> None:
        message = self.chat_input.toPlainText().strip()
        if not message:
            self._set_status("请输入要发送的内容", "error", self.chat_status_label)
            return
        if not self.chat_service:
            self._set_status("请先保存 API Key", "error", self.chat_status_label)
            return

        self.chat_send_btn.setEnabled(False)
        self._set_status("正在向大模型提问...", "loading", self.chat_status_label)

        def run_chat() -> None:
            try:
                response = self.chat_service.chat(self.chat_history, message)
                self.chat_history.append(ChatMessage(role="user", content=message))
                self.chat_history.append(ChatMessage(role="assistant", content=response))
                self._append_chat(f"用户：{message}\n\nAI：{response}\n{'-' * 24}\n")
                self.chat_input.clear()
                self._set_status("回复已返回", "success", self.chat_status_label)
            except Exception as exc:  # noqa: BLE001
                self._set_status(str(exc), "error", self.chat_status_label)
            finally:
                self.chat_send_btn.setEnabled(True)

        # 直接调用，不开线程（请求本身在 requests 中阻塞，界面仍可用）
        run_chat()

    def _append_chat(self, text: str) -> None:
        self.chat_history_view.appendPlainText(text)
        cursor = self.chat_history_view.textCursor()
        cursor.movePosition(cursor.End)
        self.chat_history_view.setTextCursor(cursor)

    # ------------------------------------------------------------------ HISTORY & STATUS
    def _show_error(self, message: str) -> None:
        self._set_status(message, "error", self.download_status_label)
        QMessageBox.critical(self, "错误", message)

    def _set_status(self, message: str, status: str = "info", target: Optional[QLabel] = None) -> None:
        label = target or self.download_status_label
        label.setText(message)
        label.setProperty("status", status)
        label.style().unpolish(label)
        label.style().polish(label)

    def _load_history(self) -> None:
        if not HISTORY_FILE.exists():
            self._refresh_history_list()
            return
        try:
            entries = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            self.history = [
                HistoryItem(**item)
                for item in entries
                if isinstance(item, dict) and {"url", "title", "timestamp"} <= item.keys()
            ]
            self._refresh_history_list()
        except Exception:  # noqa: BLE001
            self.history = []
            self._refresh_history_list()

    def _save_history_entry(self, result: dict) -> None:
        url = self.url_input.text().strip()
        title = result.get("video_title") or "未知标题"
        timestamp = result.get("timestamp")

        if not timestamp:
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        new_item = HistoryItem(url=url, title=title, timestamp=timestamp)
        self.history = [item for item in self.history if item.url != url]
        self.history.insert(0, new_item)
        self.history = self.history[:20]

        self._refresh_history_list()
        data = [item.__dict__ for item in self.history]
        HISTORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _refresh_history_list(self) -> None:
        self.history_list.clear()
        for item in self.history:
            display = f"{item.title} — {item.timestamp}"
            list_item = QListWidgetItem(display)
            list_item.setData(Qt.ItemDataRole.UserRole, item.url)
            self.history_list.addItem(list_item)

    # ------------------------------------------------------------------ LIFECYCLE
    def closeEvent(self, event) -> None:  # noqa: N802
        if self.worker and self.worker.isRunning():
            self.worker.progress.disconnect()
            self.worker.finished.disconnect()
            self.worker.error.disconnect()
            self.worker.quit()
            self.worker.wait(2000)
        if self.transcribe_worker and self.transcribe_worker.isRunning():
            self.transcribe_worker.progress.disconnect()
            self.transcribe_worker.finished.disconnect()
            self.transcribe_worker.error.disconnect()
            self.transcribe_worker.quit()
            self.transcribe_worker.wait(2000)
        if self.chat_batch_worker and self.chat_batch_worker.isRunning():
            self.chat_batch_worker.progress.disconnect()
            self.chat_batch_worker.finished.disconnect()
            self.chat_batch_worker.error.disconnect()
            self.chat_batch_worker.quit()
            self.chat_batch_worker.wait(2000)
        super().closeEvent(event)


def run_app() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


__all__ = ["run_app", "MainWindow"]
