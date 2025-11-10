"""Random audio/video stitching tool with a Tkinter GUI.

This script lets users pick target duration, media folders, and an output
destination, then randomly stitches background music and video segments
so the final export matches the background music length.
"""

from __future__ import annotations

import json
import random
import subprocess
import threading
import time
import uuid
import urllib.request
import zipfile
import shutil
from dataclasses import dataclass
import re
import textwrap
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

try:
    from pydub import AudioSegment
except ImportError as exc:  # pragma: no cover - dependency hint
    raise SystemExit(
        "Missing dependency 'pydub'. Install it with: pip install pydub"
    ) from exc

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv"}
TRANSCRIPT_EXTENSIONS = {".srt", ".ass"}
AUDIO_EXPORT_NAME = "bgm_final.mp3"
VIDEO_EXPORT_TEMPLATE = "final_video_{length_tag}.mp4"
CONFIG_PATH = Path.home() / ".random_av_stitcher.json"
FONT_CACHE_DIR = Path.home() / ".random_av_stitcher_fonts"
ZY_OLIVER_FONT_URL = "https://dl.dafont.com/dl/?f=oliver"
MAX_SUBTITLE_CHARS = 40
ASS_PLAY_RES_X = 1920
ASS_PLAY_RES_Y = 1080
ASS_MARGIN_V = 120


@dataclass
class AudioBuildResult:
    segment: AudioSegment
    used_files: List[Path]
    clip_segments: List[Tuple[Path, float]]  # (path, duration_sec)
    duration_ms: int
    export_path: Path


@dataclass
class VideoBuildResult:
    used_files: List[str]
    export_path: Path


@dataclass
class GenerationParams:
    target_minutes: float
    first_video: Optional[Path]
    main_dir: Path
    opening_dir: Optional[Path]
    opening_count: int
    music_dir: Path
    first_music: Optional[Path]
    output_dir: Path
    video_count: int
    speed_multiplier: float
    keep_original_audio: bool
    audio_speed_multiplier: float
    sort_audio_by_name: bool
    subtitles_enabled: bool
    subtitle_dir: Optional[Path]
    subtitle_font: str
    subtitle_font_size: int
    subtitle_language: Optional[str]


class RandomAVStitcherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("随机音视频拼接工具")
        self.geometry("900x750")
        self.resizable(True, True)

        # Configure modern color scheme
        self.bg_color = "#f5f6fa"
        self.card_color = "#ffffff"
        self.accent_color = "#3498db"
        self.text_color = "#2c3e50"
        self.border_color = "#dcdde1"

        self.configure(bg=self.bg_color)

        self.target_minutes_var = tk.StringVar(value="8")
        self.first_video_file_var = tk.StringVar()
        self.main_video_dir_var = tk.StringVar()
        self.opening_video_dir_var = tk.StringVar()
        self.opening_count_var = tk.StringVar(value="8")
        self.music_dir_var = tk.StringVar()
        self.first_music_file_var = tk.StringVar()
        self.output_dir_var = tk.StringVar()
        self.video_count_var = tk.StringVar(value="1")
        self.video_speed_var = tk.StringVar(value="1.0")
        self.audio_speed_var = tk.StringVar(value="1.0")
        self.keep_original_audio_var = tk.BooleanVar(value=False)
        self.sort_audio_by_name_var = tk.BooleanVar(value=False)
        self.enable_subtitles_var = tk.BooleanVar(value=False)
        self.subtitle_dir_var = tk.StringVar()
        self.subtitle_font_var = tk.StringVar(value="ZY Oliver")
        self.subtitle_font_size_var = tk.StringVar(value="64")
        self.subtitle_language_var = tk.StringVar(value="")

        self._worker_thread: Optional[threading.Thread] = None
        self._whisper_model = None

        self._load_last_settings()
        self._build_ui()

    def _build_ui(self) -> None:
        # Create a canvas with scrollbar for the entire form
        canvas = tk.Canvas(self, bg=self.bg_color, highlightthickness=0)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=canvas.yview)

        # Create outer container to center the content
        outer_frame = tk.Frame(canvas, bg=self.bg_color)

        # Create centered content frame with max width
        scrollable_frame = tk.Frame(outer_frame, padx=30, pady=30, bg=self.bg_color)

        # Pack the content frame with centered position
        scrollable_frame.pack(expand=True)

        outer_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=outer_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Update canvas window width to match canvas width
        def on_canvas_configure(event):
            canvas.itemconfig(canvas.find_all()[0], width=event.width)

        canvas.bind("<Configure>", on_canvas_configure)

        canvas.pack(side="left", fill=tk.BOTH, expand=True)
        scrollbar.pack(side="right", fill="y")

        # Enable mouse wheel and trackpad scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_trackpad(event):
            canvas.yview_scroll(int(-1 * event.delta), "units")

        # Bind mouse wheel (Windows/Linux)
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        # Bind trackpad scrolling (macOS)
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))
        # Bind two-finger scroll on macOS
        self.bind_all("<MouseWheel>", _on_trackpad)

        main_frame = scrollable_frame
        row = 0

        # Basic Settings Section
        basic_section = self._create_section_frame(main_frame, "基本设置")
        basic_section.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 15))
        row += 1

        row = self._add_labeled_entry(
            main_frame,
            row,
            label="目标时长（分钟）",
            textvariable=self.target_minutes_var,
        )
        row = self._add_labeled_entry(
            main_frame,
            row,
            label="生成视频数量",
            textvariable=self.video_count_var,
        )
        row = self._add_labeled_entry(
            main_frame,
            row,
            label="视频速度倍数",
            textvariable=self.video_speed_var,
        )
        row = self._add_labeled_entry(
            main_frame,
            row,
            label="音频速度倍数",
            textvariable=self.audio_speed_var,
        )

        # Add checkboxes in one row
        checkbox_frame = tk.Frame(main_frame, bg=self.bg_color)
        checkbox_frame.grid(row=row, column=0, columnspan=3, sticky="w", pady=10)

        keep_audio_check = tk.Checkbutton(
            checkbox_frame,
            text="保留原声",
            variable=self.keep_original_audio_var,
            bg=self.bg_color,
            activebackground=self.bg_color,
            font=("Arial", 11),
        )
        keep_audio_check.pack(side=tk.LEFT, padx=(0, 25))

        audio_order_check = tk.Checkbutton(
            checkbox_frame,
            text="按名称拼接音乐",
            variable=self.sort_audio_by_name_var,
            bg=self.bg_color,
            activebackground=self.bg_color,
            font=("Arial", 11),
        )
        audio_order_check.pack(side=tk.LEFT, padx=(0, 25))

        subtitle_check = tk.Checkbutton(
            checkbox_frame,
            text="启用字幕",
            variable=self.enable_subtitles_var,
            bg=self.bg_color,
            activebackground=self.bg_color,
            font=("Arial", 11),
        )
        subtitle_check.pack(side=tk.LEFT)
        row += 1

        # Subtitle Settings Section
        subtitle_section = self._create_section_frame(main_frame, "字幕设置")
        subtitle_section.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(15, 15))
        row += 1

        row = self._add_path_picker(
            main_frame,
            row,
            label="字幕 SRT 文件夹（启用字幕必填）",
            textvariable=self.subtitle_dir_var,
            is_dir=True,
        )
        row = self._add_labeled_entry(
            main_frame,
            row,
            label="字幕字体",
            textvariable=self.subtitle_font_var,
        )
        row = self._add_labeled_entry(
            main_frame,
            row,
            label="字幕字号（像素）",
            textvariable=self.subtitle_font_size_var,
        )
        row = self._add_labeled_entry(
            main_frame,
            row,
            label="字幕识别语言（留空自动）",
            textvariable=self.subtitle_language_var,
        )

        # Video Settings Section
        video_section = self._create_section_frame(main_frame, "视频设置")
        video_section.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(15, 15))
        row += 1

        row = self._add_path_picker(
            main_frame,
            row,
            label="指定第一个视频（可选）",
            textvariable=self.first_video_file_var,
            is_dir=False,
            filetypes=[("Video files", "*.mp4 *.mov *.mkv"), ("All files", "*.*")],
        )
        row = self._add_path_picker(
            main_frame,
            row,
            label="主体视频文件夹",
            textvariable=self.main_video_dir_var,
            is_dir=True,
        )
        row = self._add_path_picker(
            main_frame,
            row,
            label="开头素材文件夹（可选）",
            textvariable=self.opening_video_dir_var,
            is_dir=True,
        )
        row = self._add_labeled_entry(
            main_frame,
            row,
            label="从开头素材拼接数量",
            textvariable=self.opening_count_var,
        )

        # Audio Settings Section
        audio_section = self._create_section_frame(main_frame, "音频设置")
        audio_section.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(15, 15))
        row += 1

        row = self._add_path_picker(
            main_frame,
            row,
            label="音乐文件夹",
            textvariable=self.music_dir_var,
            is_dir=True,
        )
        row = self._add_path_picker(
            main_frame,
            row,
            label="指定第一首音乐（可选）",
            textvariable=self.first_music_file_var,
            is_dir=False,
            filetypes=[("Audio files", "*.mp3 *.wav *.flac"), ("All files", "*.*")],
        )
        row = self._add_path_picker(
            main_frame,
            row,
            label="输出文件夹",
            textvariable=self.output_dir_var,
            is_dir=True,
        )

        # Output Section
        output_section = self._create_section_frame(main_frame, "输出路径")
        output_section.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(15, 15))
        row += 1

        # Start button with improved styling using Frame for better color control
        button_container = tk.Frame(main_frame, bg=self.bg_color)
        button_container.grid(row=row, column=0, columnspan=3, pady=(20, 15))

        # Create button frame with colored background
        self.start_button_frame = tk.Frame(
            button_container,
            bg=self.accent_color,
            relief=tk.RAISED,
            borderwidth=2,
            cursor="hand2",
        )
        self.start_button_frame.pack()

        # Button label
        self.start_button_label = tk.Label(
            self.start_button_frame,
            text="开始生成",
            bg=self.accent_color,
            fg="white",
            font=("Arial", 12, "bold"),
            padx=60,
            pady=15,
            cursor="hand2",
        )
        self.start_button_label.pack()

        # Bind click event
        def on_button_click(e):
            self._on_start_clicked()

        self.start_button_frame.bind("<Button-1>", on_button_click)
        self.start_button_label.bind("<Button-1>", on_button_click)

        # Add hover effect
        def on_enter(e):
            self.start_button_frame.config(bg="#2c7db5")
            self.start_button_label.config(bg="#2c7db5")

        def on_leave(e):
            self.start_button_frame.config(bg=self.accent_color)
            self.start_button_label.config(bg=self.accent_color)

        self.start_button_frame.bind("<Enter>", on_enter)
        self.start_button_label.bind("<Enter>", on_enter)
        self.start_button_frame.bind("<Leave>", on_leave)
        self.start_button_label.bind("<Leave>", on_leave)

        row += 1

        # Log section
        log_section = self._create_section_frame(main_frame, "运行日志")
        log_section.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(15, 10))
        row += 1

        self.log_text = scrolledtext.ScrolledText(
            main_frame,
            width=80,
            height=14,
            state=tk.DISABLED,
            bg="#f8f9fa",
            fg=self.text_color,
            font=("Consolas", 10),
            relief=tk.FLAT,
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=self.border_color,
            wrap=tk.WORD,
        )
        self.log_text.grid(row=row, column=0, columnspan=3, sticky="nsew")
        main_frame.grid_rowconfigure(row, weight=1)

        # Enable trackpad scrolling for log text area and prevent event propagation
        def _on_log_trackpad(event):
            # Get the first and last visible line to check if we can scroll
            first_visible = float(self.log_text.yview()[0])
            last_visible = float(self.log_text.yview()[1])

            # Calculate scroll direction
            if event.delta > 0:  # Scrolling up
                if first_visible > 0:  # Can scroll up
                    self.log_text.yview_scroll(int(-1 * event.delta), "units")
                    return "break"  # Prevent propagation
            else:  # Scrolling down
                if last_visible < 1.0:  # Can scroll down
                    self.log_text.yview_scroll(int(-1 * event.delta), "units")
                    return "break"  # Prevent propagation

            # If log can't scroll in that direction, allow propagation
            return None

        def _on_log_button_scroll(event, direction):
            # Get the first and last visible line
            first_visible = float(self.log_text.yview()[0])
            last_visible = float(self.log_text.yview()[1])

            if direction == "up" and first_visible > 0:
                self.log_text.yview_scroll(-1, "units")
                return "break"
            elif direction == "down" and last_visible < 1.0:
                self.log_text.yview_scroll(1, "units")
                return "break"

            return None

        # Bind scrolling events to the log text widget
        self.log_text.bind("<MouseWheel>", _on_log_trackpad)
        self.log_text.bind("<Button-4>", lambda e: _on_log_button_scroll(e, "up"))
        self.log_text.bind("<Button-5>", lambda e: _on_log_button_scroll(e, "down"))

        # Handle focus to ensure scrolling works when mouse enters
        def _on_log_enter(event):
            self.log_text.focus_set()

        def _on_log_leave(event):
            self.focus_set()

        self.log_text.bind("<Enter>", _on_log_enter)
        self.log_text.bind("<Leave>", _on_log_leave)

    def _load_last_settings(self) -> None:
        settings = _load_settings()
        mapping = {
            "target_minutes": self.target_minutes_var,
            "first_video_file": self.first_video_file_var,
            "main_video_dir": self.main_video_dir_var,
            "opening_video_dir": self.opening_video_dir_var,
            "opening_count": self.opening_count_var,
            "music_dir": self.music_dir_var,
            "first_music_file": self.first_music_file_var,
            "output_dir": self.output_dir_var,
            "video_count": self.video_count_var,
            "video_speed": self.video_speed_var,
            "audio_speed": self.audio_speed_var,
            "subtitle_dir": self.subtitle_dir_var,
            "subtitle_font": self.subtitle_font_var,
            "subtitle_font_size": self.subtitle_font_size_var,
            "subtitle_language": self.subtitle_language_var,
        }
        for key, var in mapping.items():
            value = settings.get(key)
            if isinstance(value, str) and value:
                var.set(value)

        # Load boolean setting
        keep_audio = settings.get("keep_original_audio")
        if isinstance(keep_audio, bool):
            self.keep_original_audio_var.set(keep_audio)
        audio_order = settings.get("sort_audio_by_name")
        if isinstance(audio_order, bool):
            self.sort_audio_by_name_var.set(audio_order)
        enable_subtitles = settings.get("enable_subtitles")
        if isinstance(enable_subtitles, bool):
            self.enable_subtitles_var.set(enable_subtitles)
        subtitle_language = settings.get("subtitle_language")
        if isinstance(subtitle_language, str):
            self.subtitle_language_var.set(subtitle_language)

    def _save_last_settings(self) -> None:
        data = {
            "target_minutes": self.target_minutes_var.get(),
            "first_video_file": self.first_video_file_var.get(),
            "main_video_dir": self.main_video_dir_var.get(),
            "opening_video_dir": self.opening_video_dir_var.get(),
            "opening_count": self.opening_count_var.get(),
            "music_dir": self.music_dir_var.get(),
            "first_music_file": self.first_music_file_var.get(),
            "output_dir": self.output_dir_var.get(),
            "video_count": self.video_count_var.get(),
            "video_speed": self.video_speed_var.get(),
            "keep_original_audio": self.keep_original_audio_var.get(),
            "audio_speed": self.audio_speed_var.get(),
            "sort_audio_by_name": self.sort_audio_by_name_var.get(),
            "enable_subtitles": self.enable_subtitles_var.get(),
            "subtitle_dir": self.subtitle_dir_var.get(),
            "subtitle_font": self.subtitle_font_var.get(),
            "subtitle_font_size": self.subtitle_font_size_var.get(),
            "subtitle_language": self.subtitle_language_var.get(),
        }
        _save_settings(data)

    def _create_section_frame(self, parent: tk.Widget, title: str) -> tk.Frame:
        """Create a section title frame with modern styling"""
        section = tk.Frame(parent, bg=self.bg_color)

        title_label = tk.Label(
            section,
            text=title,
            font=("Arial", 13, "bold"),
            fg=self.accent_color,
            bg=self.bg_color,
        )
        title_label.pack(side=tk.LEFT)

        # Add separator line
        separator = tk.Frame(section, height=2, bg=self.border_color)
        separator.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(15, 0))

        return section

    def _add_labeled_entry(
        self,
        parent: tk.Widget,
        row: int,
        *,
        label: str,
        textvariable: tk.StringVar,
    ) -> int:
        label_widget = tk.Label(
            parent,
            text=label,
            bg=self.bg_color,
            fg=self.text_color,
            font=("Arial", 11),
        )
        label_widget.grid(
            row=row,
            column=0,
            sticky="w",
            padx=(0, 15),
            pady=8,
        )

        entry = tk.Entry(
            parent,
            textvariable=textvariable,
            font=("Arial", 11),
            relief=tk.SOLID,
            borderwidth=1,
            bg=self.card_color,
            highlightthickness=1,
            highlightbackground=self.border_color,
            highlightcolor=self.accent_color,
        )
        entry.grid(row=row, column=1, sticky="we", pady=8, ipady=4)

        parent.grid_columnconfigure(1, weight=1)
        return row + 1

    def _add_path_picker(
        self,
        parent: tk.Widget,
        row: int,
        *,
        label: str,
        textvariable: tk.StringVar,
        is_dir: bool,
        filetypes: Optional[Sequence[Tuple[str, str]]] = None,
    ) -> int:
        label_widget = tk.Label(
            parent,
            text=label,
            bg=self.bg_color,
            fg=self.text_color,
            font=("Arial", 11),
        )
        label_widget.grid(
            row=row,
            column=0,
            sticky="w",
            padx=(0, 15),
            pady=8,
        )

        entry = tk.Entry(
            parent,
            textvariable=textvariable,
            font=("Arial", 11),
            relief=tk.SOLID,
            borderwidth=1,
            bg=self.card_color,
            highlightthickness=1,
            highlightbackground=self.border_color,
            highlightcolor=self.accent_color,
        )
        entry.grid(row=row, column=1, sticky="we", pady=8, ipady=4)

        def _browse() -> None:
            if is_dir:
                selection = filedialog.askdirectory()
            else:
                selection = filedialog.askopenfilename(filetypes=filetypes)
            if selection:
                textvariable.set(selection)

        browse_btn = tk.Button(
            parent,
            text="浏览…",
            command=_browse,
            width=10,
            bg=self.card_color,
            fg=self.accent_color,
            font=("Arial", 10, "bold"),
            relief=tk.SOLID,
            borderwidth=1,
            cursor="hand2",
            highlightthickness=0,
            activebackground=self.accent_color,
            activeforeground="white",
        )
        browse_btn.grid(row=row, column=2, padx=(12, 0), pady=8)

        # Add hover effect for browse button
        browse_btn.bind("<Enter>", lambda e: browse_btn.config(bg=self.accent_color, fg="white"))
        browse_btn.bind("<Leave>", lambda e: browse_btn.config(bg=self.card_color, fg=self.accent_color))

        return row + 1

    def _append_log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")

        def _do_append() -> None:
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)

        self.after(0, _do_append)

    def _set_start_button_state(self, enabled: bool) -> None:
        def _update() -> None:
            if enabled:
                # Enable button
                self.start_button_label.config(text="开始生成", fg="white")
                self.start_button_frame.bind("<Button-1>", lambda e: self._on_start_clicked())
                self.start_button_label.bind("<Button-1>", lambda e: self._on_start_clicked())
            else:
                # Disable button
                self.start_button_label.config(text="处理中...", fg="#cccccc")
                self.start_button_frame.unbind("<Button-1>")
                self.start_button_label.unbind("<Button-1>")

        self.after(0, _update)

    def _show_message(self, kind: str, title: str, message: str) -> None:
        def _display() -> None:
            show_func = getattr(messagebox, kind, messagebox.showinfo)
            show_func(title, message)

        self.after(0, _display)

    def _on_start_clicked(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            messagebox.showinfo("任务正在进行", "请等待当前生成任务完成。")
            return

        try:
            params = self._collect_parameters()
        except ValueError as exc:
            messagebox.showerror("输入有误", str(exc))
            return

        self._save_last_settings()

        self._append_log("开始生成，准备处理音频和视频…")
        self._set_start_button_state(False)

        self._worker_thread = threading.Thread(
            target=self._run_generation,
            args=(params,),
            daemon=True,
        )
        self._worker_thread.start()

    def _collect_parameters(self) -> GenerationParams:
        try:
            target_minutes = float(self.target_minutes_var.get())
        except ValueError as exc:
            raise ValueError("目标时长需要是数字（例如 8 或 8.5）。") from exc

        if target_minutes <= 0:
            raise ValueError("目标时长需要大于 0。")

        try:
            video_count = int(self.video_count_var.get())
        except ValueError as exc:
            raise ValueError("生成视频数量需要是正整数。") from exc

        if video_count <= 0:
            raise ValueError("生成视频数量需要是正整数。")

        try:
            speed_multiplier = float(self.video_speed_var.get())
        except ValueError as exc:
            raise ValueError("视频速度倍数需要是数字（例如 1 或 1.5）。") from exc

        if speed_multiplier <= 0:
            raise ValueError("视频速度倍数需要大于 0。")

        try:
            audio_speed_multiplier = float(self.audio_speed_var.get())
        except ValueError as exc:
            raise ValueError("音频速度倍数需要是数字（例如 1 或 1.25）。") from exc

        if audio_speed_multiplier <= 0:
            raise ValueError("音频速度倍数需要大于 0。")

        try:
            opening_count = int(self.opening_count_var.get())
        except ValueError as exc:
            raise ValueError("从开头素材拼接数量需要是正整数。") from exc

        if opening_count < 0:
            raise ValueError("从开头素材拼接数量不能为负数。")

        first_video_path = self._validate_optional_file(
            self.first_video_file_var.get(), "指定第一个视频", VIDEO_EXTENSIONS
        )
        main_dir = self._validate_required_directory(self.main_video_dir_var.get(), "主体视频文件夹")
        opening_dir = self._validate_optional_directory(
            self.opening_video_dir_var.get(), "开头素材文件夹"
        )
        music_dir = self._validate_required_directory(self.music_dir_var.get(), "音乐文件夹")
        output_dir = self._validate_required_directory(self.output_dir_var.get(), "输出文件夹")
        first_music_path = self._validate_optional_file(
            self.first_music_file_var.get(), "指定第一首音乐", AUDIO_EXTENSIONS
        )
        subtitle_dir = self._validate_optional_directory(
            self.subtitle_dir_var.get(), "字幕 SRT 文件夹"
        )
        if self.enable_subtitles_var.get() and subtitle_dir is None:
            raise ValueError("启用字幕时必须提供字幕 SRT 文件夹。")

        subtitle_font = self.subtitle_font_var.get().strip() or "ZY Oliver"
        try:
            subtitle_font_size = int(self.subtitle_font_size_var.get())
        except ValueError as exc:
            raise ValueError("字幕字号需要是正整数，例如 64。") from exc

        if subtitle_font_size <= 0:
            raise ValueError("字幕字号需要大于 0。")

        return GenerationParams(
            target_minutes=target_minutes,
            first_video=first_video_path,
            main_dir=main_dir,
            opening_dir=opening_dir,
            opening_count=opening_count,
            music_dir=music_dir,
            first_music=first_music_path,
            output_dir=output_dir,
            video_count=video_count,
            speed_multiplier=speed_multiplier,
            keep_original_audio=self.keep_original_audio_var.get(),
            audio_speed_multiplier=audio_speed_multiplier,
            sort_audio_by_name=self.sort_audio_by_name_var.get(),
            subtitles_enabled=self.enable_subtitles_var.get(),
            subtitle_dir=subtitle_dir,
            subtitle_font=subtitle_font,
            subtitle_font_size=subtitle_font_size,
            subtitle_language=self.subtitle_language_var.get().strip() or None,
        )

    def _validate_required_directory(self, path_str: str, label: str) -> Path:
        path = Path(path_str).expanduser()
        if not path_str:
            raise ValueError(f"{label} 为必填项。")
        if not path.exists() or not path.is_dir():
            raise ValueError(f"{label} 不存在或不是文件夹：{path}")
        return path

    def _validate_optional_directory(self, path_str: str, label: str) -> Optional[Path]:
        if not path_str:
            return None
        path = Path(path_str).expanduser()
        if not path.exists() or not path.is_dir():
            raise ValueError(f"{label} 不存在或不是文件夹：{path}")
        return path

    def _validate_optional_file(
        self, path_str: str, label: str, allowed_extensions: set
    ) -> Optional[Path]:
        if not path_str:
            return None
        path = Path(path_str).expanduser()
        if not path.exists() or not path.is_file():
            raise ValueError(f"{label}不存在：{path}")
        if path.suffix.lower() not in allowed_extensions:
            raise ValueError(f"{label}文件格式不受支持：{path.suffix}")
        return path

    def _run_generation(self, params: GenerationParams) -> None:
        results: List[dict] = []
        try:
            for index in range(1, params.video_count + 1):
                run_label = f"第 {index}/{params.video_count} 条"
                self._append_log(f"{run_label}：开始生成。")
                result = self._generate_single_output(params, index, params.video_count)
                results.append(result)
                self._append_log(f"{run_label}：生成完成。")
        except Exception as exc:  # pragma: no cover - user feedback
            self._append_log(f"生成失败：{exc}")
            self._show_message("showerror", "生成失败", str(exc))
        else:
            for idx, result in enumerate(results, start=1):
                prefix = f"第 {idx}/{params.video_count} 条"
                video_path = result["video"].export_path
                self._append_log(f"{prefix}：成品视频 {video_path}")
                self._append_log(
                    f"{prefix}：视频时长 {result['audio'].duration_ms / 1000:.2f} 秒"
                )
            self._show_message("showinfo", "完成", f"已生成 {len(results)} 条视频。")
        finally:
            self._set_start_button_state(True)

    def _generate_single_output(
        self,
        params: GenerationParams,
        run_index: int,
        total_count: int,
    ) -> dict:
        run_label = f"第 {run_index}/{total_count} 条"
        log_prefix = f"[{run_label}] "

        target_ms = int(params.target_minutes * 60 * 1000)
        self._append_log(f"{log_prefix}目标时长：{params.target_minutes} 分钟（{target_ms} 毫秒）")

        music_paths = list_files_with_extensions(params.music_dir, AUDIO_EXTENSIONS)
        if not music_paths:
            raise ValueError("音乐文件夹中未找到任何音频文件，请检查文件格式。")
        self._append_log(f"{log_prefix}找到 {len(music_paths)} 个音乐文件。")

        output_dir = params.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        audio_filename = build_audio_filename(run_index, total_count)
        audio_export_path = output_dir / audio_filename

        audio_result = self._build_audio_playlist(
            target_ms=target_ms,
            music_paths=music_paths,
            first_music=params.first_music,
            export_path=audio_export_path,
            log_prefix=log_prefix,
            audio_speed_multiplier=params.audio_speed_multiplier,
            sort_audio_by_name=params.sort_audio_by_name,
        )

        main_paths = list_files_with_extensions(params.main_dir, VIDEO_EXTENSIONS)
        if not main_paths:
            raise ValueError("主体视频文件夹中未找到任何视频文件，请检查文件格式。")
        self._append_log(f"{log_prefix}主体视频素材：{len(main_paths)} 个。")

        opening_paths = []
        if params.opening_dir:
            opening_paths = list_files_with_extensions(params.opening_dir, VIDEO_EXTENSIONS)
            if opening_paths:
                self._append_log(f"{log_prefix}开头素材：{len(opening_paths)} 个。")
            else:
                self._append_log(f"{log_prefix}警告：开头素材文件夹中未找到视频文件。")

        length_tag = format_duration_tag(audio_result.duration_ms)
        video_filename = build_video_filename(length_tag, run_index, total_count)
        video_export_path = output_dir / video_filename

        subtitle_path = None
        font_file = None
        if params.subtitles_enabled:
            if params.subtitle_dir is None:
                raise ValueError("启用字幕时必须提供字幕 SRT 文件夹。")
            # Download ZY Oliver font if needed
            if params.subtitle_font == "ZY Oliver":
                self._append_log(f"{log_prefix}字幕：正在准备 ZY Oliver 字体...")
                font_file = download_zy_oliver_font()
                if font_file:
                    self._append_log(f"{log_prefix}字幕：已获取字体文件 {font_file.name}")
                else:
                    self._append_log(f"{log_prefix}字幕：警告 - 无法下载字体，将使用系统默认字体")

            subtitle_path = self._build_subtitle_track(
                audio_result=audio_result,
                subtitle_dir=params.subtitle_dir,
                clip_segments=audio_result.clip_segments,
                video_export_path=video_export_path,
                font_name=params.subtitle_font,
                font_size=params.subtitle_font_size,
                subtitle_language=params.subtitle_language,
                log_prefix=log_prefix,
            )

        video_result = self._build_video_sequence(
            audio_duration_ms=audio_result.duration_ms,
            first_video=params.first_video,
            main_paths=main_paths,
            opening_paths=opening_paths,
            opening_count=params.opening_count,
            export_path=video_export_path,
            audio_path=audio_export_path,
            speed_multiplier=params.speed_multiplier,
            keep_original_audio=params.keep_original_audio,
            subtitle_path=subtitle_path,
            font_file=font_file,
            log_prefix=log_prefix,
        )

        self._append_log(f"{log_prefix}使用的音乐文件：")
        for idx, path in enumerate(audio_result.used_files, start=1):
            self._append_log(f"{log_prefix}  {idx}. {path}")

        self._append_log(f"{log_prefix}使用的视频文件：")
        for idx, entry in enumerate(video_result.used_files, start=1):
            self._append_log(f"{log_prefix}  {idx}. {entry}")

        return {"audio": audio_result, "video": video_result}

    def _build_audio_playlist(
        self,
        *,
        target_ms: int,
        music_paths: Sequence[Path],
        first_music: Optional[Path],
        export_path: Path,
        log_prefix: str,
        audio_speed_multiplier: float,
        sort_audio_by_name: bool,
    ) -> AudioBuildResult:
        if audio_speed_multiplier <= 0:
            raise ValueError("音频速度倍数需要大于 0。")

        effective_target_ms = max(1, int(round(target_ms * audio_speed_multiplier)))

        # Copy list so we can shuffle without mutating original
        all_tracks = list(music_paths)
        if sort_audio_by_name:
            self._append_log(f"{log_prefix}音乐拼接顺序：按文件名排列。")
        else:
            random.shuffle(all_tracks)
            self._append_log(f"{log_prefix}音乐拼接顺序：随机。")

        used_files: List[Path] = []
        clip_segments: List[Tuple[Path, float]] = []
        total_duration = 0
        reencode_required = False

        combined = AudioSegment.silent(duration=0)
        if abs(audio_speed_multiplier - 1.0) > 1e-3:
            reencode_required = True

        # Track used to ensure no immediate repetition
        last_two_tracks: List[Path] = []

        def finalize_audio() -> AudioBuildResult:
            final_segment = combined
            duration_scale = 1.0
            if abs(audio_speed_multiplier - 1.0) > 1e-3:
                self._append_log(
                    f"{log_prefix}音频整体倍速：{audio_speed_multiplier:.2f}x（目标时长以倍速后结果为准）"
                )
                final_segment = apply_audio_speed(final_segment, audio_speed_multiplier)
                duration_scale = 1.0 / audio_speed_multiplier

            scaled_segments = [
                (path, duration * duration_scale) for path, duration in clip_segments
            ]

            export_path.parent.mkdir(parents=True, exist_ok=True)

            if (
                not reencode_required
                and len(used_files) == 1
                and abs(audio_speed_multiplier - 1.0) <= 1e-3
            ):
                source = used_files[0]
                try:
                    shutil.copyfile(source, export_path)
                    actual_duration = probe_audio_duration(source) or len(final_segment) / 1000.0
                    scaled_segments = [(source, actual_duration)]
                    duration_ms = int(round(actual_duration * 1000))
                    self._append_log(f"{log_prefix}音频：直接复用源文件（未重新转码）。")
                    return AudioBuildResult(
                        segment=final_segment,
                        used_files=used_files.copy(),
                        clip_segments=scaled_segments,
                        duration_ms=duration_ms,
                        export_path=export_path,
                    )
                except OSError as exc:
                    self._append_log(
                        f"{log_prefix}音频：复制源文件失败，改为重新编码：{exc}"
                    )

            # Export with higher quality and bitrate to preserve volume
            final_segment.export(
                export_path,
                format="mp3",
                bitrate="320k",
                parameters=["-q:a", "0"]  # Highest quality
            )
            self._append_log(f"{log_prefix}音频导出完成：{export_path}")
            return AudioBuildResult(
                segment=final_segment,
                used_files=used_files.copy(),
                clip_segments=scaled_segments,
                duration_ms=len(final_segment),
                export_path=export_path,
            )

        # Add first music if specified
        if first_music:
            if first_music not in all_tracks:
                self._append_log(f"{log_prefix}指定的第一首音乐不在音乐文件夹中，将仍以第一首方式加入。")
            self._append_log(f"{log_prefix}拼接音乐：{first_music.name}")
            segment = AudioSegment.from_file(first_music)
            combined += segment
            total_duration = len(combined)
            used_files.append(first_music)
            if len(used_files) > 1:
                reencode_required = True
            clip_duration = probe_audio_duration(first_music) or len(segment) / 1000.0
            clip_segments.append((first_music, clip_duration))
            last_two_tracks.append(first_music)

            if total_duration >= effective_target_ms:
                return finalize_audio()

        # Continue adding tracks until target duration is reached
        track_pool = all_tracks.copy()
        pool_index = 0

        while total_duration < effective_target_ms:
            # Refresh pool if exhausted
            if pool_index >= len(track_pool):
                pool_index = 0
                if not sort_audio_by_name:
                    random.shuffle(track_pool)

            track_path = track_pool[pool_index]

            # Skip if in last two tracks (avoid immediate repetition)
            if track_path in last_two_tracks:
                pool_index += 1
                # If we've checked all tracks and all are in last_two, allow repetition
                if pool_index >= len(track_pool):
                    pool_index = 0
                    last_two_tracks.clear()
                continue

            self._append_log(f"{log_prefix}拼接音乐：{track_path.name}")
            segment = AudioSegment.from_file(track_path)
            combined += segment
            total_duration = len(combined)
            used_files.append(track_path)
            if len(used_files) > 1:
                reencode_required = True
            clip_duration = probe_audio_duration(track_path) or len(segment) / 1000.0
            clip_segments.append((track_path, clip_duration))

            # Update last two tracks
            last_two_tracks.append(track_path)
            if len(last_two_tracks) > 2:
                last_two_tracks.pop(0)

            pool_index += 1

        return finalize_audio()

    def _build_subtitle_track(
        self,
        *,
        audio_result: AudioBuildResult,
        subtitle_dir: Optional[Path],
        clip_segments: Sequence[Tuple[Path, float]],
        video_export_path: Path,
        font_name: str,
        font_size: int,
        subtitle_language: Optional[str],
        log_prefix: str,
    ) -> Optional[Path]:
        self._append_log(f"{log_prefix}字幕：准备生成…")

        if subtitle_dir is not None:
            try:
                segments = stitch_subtitles_from_clips(
                    subtitle_dir=subtitle_dir,
                    clip_segments=clip_segments,
                    max_chars=MAX_SUBTITLE_CHARS,
                )
            except FileNotFoundError as exc:
                raise ValueError(str(exc)) from exc
            except ValueError as exc:
                self._append_log(f"{log_prefix}字幕：警告 - {exc}")
                segments = None
        else:
            segments = None

        if segments is None:
            self._append_log(f"{log_prefix}字幕：没有可用的 SRT，尝试 Whisper 自动识别。")
            whisper_segments = self._transcribe_audio_segments(
                audio_result.export_path,
                language=subtitle_language,
                log_prefix=log_prefix,
            )
            if whisper_segments:
                self._append_log(
                    f"{log_prefix}字幕：Whisper 自动识别 {len(whisper_segments)} 条片段。"
                )
                segments = whisper_segments

        if not segments:
            self._append_log(f"{log_prefix}字幕：没有可用的文本内容，跳过字幕生成。")
            return None

        subtitle_path = video_export_path.with_suffix(".ass")
        self._append_log(f"{log_prefix}字幕：正在写入文件 {subtitle_path}")

        try:
            write_ass_file(
                segments,
                font_name=font_name,
                font_size=font_size,
                output_path=subtitle_path,
            )
            self._append_log(f"{log_prefix}字幕文件已生成：{subtitle_path.name}")
            return subtitle_path
        except Exception as e:
            self._append_log(f"{log_prefix}字幕：警告 - 写入字幕文件失败：{e}")
            return None

    def _transcribe_audio_segments(
        self,
        audio_path: Path,
        *,
        language: Optional[str],
        log_prefix: str,
    ) -> List[Tuple[float, float, str]]:
        language = (language or "").strip() or None
        lang_info = language or "自动"
        self._append_log(f"{log_prefix}字幕：正在调用 Whisper 识别（语言：{lang_info}）…")
        try:
            import whisper
        except ImportError:
            self._append_log(
                f"{log_prefix}字幕：警告 - 未安装 openai-whisper，跳过字幕生成。"
            )
            self._append_log(
                f"{log_prefix}字幕：提示 - 可运行 'pip install openai-whisper' 安装后自动识别字幕。"
            )
            return []

        if self._whisper_model is None:
            self._append_log(f"{log_prefix}字幕：正在加载 Whisper base 模型（一次性操作）…")
            try:
                self._whisper_model = whisper.load_model("base")
            except Exception as load_exc:
                self._append_log(f"{log_prefix}字幕：警告 - 加载 Whisper 模型失败：{load_exc}")
                self._append_log(f"{log_prefix}字幕：跳过字幕生成。")
                return []

        try:
            transcribe_kwargs = {
                "audio": str(audio_path),
                "verbose": False,
            }
            if language:
                transcribe_kwargs["language"] = language
            result = self._whisper_model.transcribe(**transcribe_kwargs)
        except Exception as exc:
            self._append_log(f"{log_prefix}字幕：警告 - Whisper 识别失败：{exc}")
            self._append_log(f"{log_prefix}字幕：跳过字幕生成。")
            return []

        raw_segments: List[Tuple[float, float, str]] = []
        for seg in result.get("segments", []):
            text = seg.get("text", "").strip()
            if not text:
                continue
            start = max(0.0, float(seg.get("start", 0.0)))
            end = max(start + 0.01, float(seg.get("end", start + 0.5)))
            raw_segments.append((start, end, text))

        return refine_segments_for_length(raw_segments, MAX_SUBTITLE_CHARS)

    def _build_video_sequence(
        self,
        *,
        audio_duration_ms: int,
        first_video: Optional[Path],
        main_paths: Sequence[Path],
        opening_paths: Sequence[Path],
        opening_count: int,
        export_path: Path,
        audio_path: Path,
        speed_multiplier: float,
        keep_original_audio: bool,
        subtitle_path: Optional[Path],
        font_file: Optional[Path],
        log_prefix: str,
    ) -> VideoBuildResult:
        if speed_multiplier <= 0:
            raise ValueError("视频速度倍数需要大于 0。")

        audio_duration_sec = audio_duration_ms / 1000.0
        remaining = audio_duration_sec
        segments: List[Tuple[Path, Optional[float]]] = []
        used_files: List[str] = []

        # Copy list so we can shuffle without mutating original
        all_videos = list(main_paths)
        random.shuffle(all_videos)

        if not all_videos:
            raise ValueError("未提供主体视频素材。")

        # Track last two videos to avoid immediate repetition
        last_two_videos: List[Path] = []

        # Track opening video count
        opening_used_count = 0

        # Add first video if specified
        if first_video:
            if first_video not in all_videos:
                self._append_log(f"{log_prefix}指定的第一个视频不在主体视频文件夹中，将仍以第一个方式加入。")

            self._append_log(f"{log_prefix}拼接视频：{first_video.name}")
            duration = probe_video_duration(first_video)
            if duration <= 0:
                raise ValueError(f"无法获取视频时长，请检查文件：{first_video}")

            adjusted = duration / speed_multiplier

            if adjusted <= remaining + 1e-3:
                segments.append((first_video, None))
                used_files.append(str(first_video))
                remaining = max(0.0, remaining - adjusted)
                last_two_videos.append(first_video)
            else:
                original_needed = min(duration, remaining * speed_multiplier)
                segments.append((first_video, original_needed))
                used_files.append(
                    f"{first_video}（截取前 {original_needed:.2f} 秒 → 输出 {remaining:.2f} 秒）"
                )
                remaining = 0.0

            if remaining <= 0:
                if not segments:
                    raise ValueError("未能拼接任何视频，请确认素材文件可用。")

                temp_video_path = export_path.parent / f"__temp_concat_{uuid.uuid4().hex}.mp4"
                self._append_log(f"{log_prefix}正在使用 ffmpeg 拼接视频片段…")
                progress_state = {"last_percent": -10}

                def progress_callback(fraction: float) -> None:
                    percent = min(100, int(round(fraction * 100)))
                    if percent >= progress_state["last_percent"] + 10 or percent == 100:
                        progress_state["last_percent"] = percent
                        self._append_log(f"{log_prefix}ffmpeg 拼接进度：{percent}%")

                concat_videos_with_ffmpeg(
                    segments,
                    temp_video_path,
                    speed_multiplier=speed_multiplier,
                    keep_original_audio=keep_original_audio,
                    progress_callback=progress_callback,
                    expected_duration=audio_duration_sec,
                )

                self._append_log(f"{log_prefix}正在合并音频与视频…")
                merge_video_and_audio(
                    temp_video_path, audio_path, export_path, keep_original_audio
                )

                # Clean up temporary files
                try:
                    temp_video_path.unlink()
                except OSError:
                    pass

                try:
                    audio_path.unlink()
                    self._append_log(f"{log_prefix}已清理临时音频文件")
                except OSError:
                    pass

                return VideoBuildResult(
                    used_files=used_files,
                    export_path=export_path,
                )

        # Continue adding videos until target duration is reached
        # Prepare opening videos pool if available
        opening_pool = []
        if opening_paths and opening_count > 0:
            opening_pool = list(opening_paths)
            random.shuffle(opening_pool)
            self._append_log(f"{log_prefix}将使用开头素材拼接前 {opening_count} 个视频片段。")

        video_pool = all_videos.copy()
        pool_index = 0

        while remaining > 0:
            # Decide which pool to use based on opening count
            if opening_used_count < opening_count and opening_pool:
                # Use opening pool for first N videos
                if opening_used_count >= len(opening_pool):
                    # If opening pool is exhausted, reshuffle and start over
                    random.shuffle(opening_pool)
                    opening_used_count = 0

                path = opening_pool[opening_used_count]
                opening_used_count += 1
                self._append_log(f"{log_prefix}拼接视频（开头素材）：{path.name}")
            else:
                # Use main video pool
                # Refresh pool if exhausted
                if pool_index >= len(video_pool):
                    pool_index = 0
                    random.shuffle(video_pool)

                path = video_pool[pool_index]

                # Skip if in last two videos (avoid immediate repetition)
                if path in last_two_videos:
                    pool_index += 1
                    # If we've checked all videos and all are in last_two, allow repetition
                    if pool_index >= len(video_pool):
                        pool_index = 0
                        last_two_videos.clear()
                    continue

                self._append_log(f"{log_prefix}拼接视频：{path.name}")
                pool_index += 1

            duration = probe_video_duration(path)
            if duration <= 0:
                raise ValueError(f"无法获取视频时长，请检查文件：{path}")

            adjusted = duration / speed_multiplier

            if adjusted <= remaining + 1e-3:
                segments.append((path, None))
                used_files.append(str(path))
                remaining = max(0.0, remaining - adjusted)

                # Update last two videos (only for main pool)
                if opening_used_count > opening_count or not opening_pool:
                    last_two_videos.append(path)
                    if len(last_two_videos) > 2:
                        last_two_videos.pop(0)
            else:
                original_needed = min(duration, remaining * speed_multiplier)
                segments.append((path, original_needed))
                used_files.append(
                    f"{path}（截取前 {original_needed:.2f} 秒 → 输出 {remaining:.2f} 秒）"
                )
                remaining = 0.0
                break

        if not segments:
            raise ValueError("未能拼接任何视频，请确认素材文件可用。")

        temp_video_path = export_path.parent / f"__temp_concat_{uuid.uuid4().hex}.mp4"

        self._append_log(f"{log_prefix}正在使用 ffmpeg 拼接视频片段…")
        progress_state = {"last_percent": -10}

        def progress_callback(fraction: float) -> None:
            percent = min(100, int(round(fraction * 100)))
            if percent >= progress_state["last_percent"] + 10 or percent == 100:
                progress_state["last_percent"] = percent
                self._append_log(f"{log_prefix}ffmpeg 拼接进度：{percent}%")

        concat_videos_with_ffmpeg(
            segments,
            temp_video_path,
            speed_multiplier=speed_multiplier,
            keep_original_audio=keep_original_audio,
            progress_callback=progress_callback,
            expected_duration=audio_duration_sec,
        )

        merged_video_path = (
            export_path
            if subtitle_path is None
            else export_path.parent / f"__temp_merged_{uuid.uuid4().hex}.mp4"
        )

        self._append_log(f"{log_prefix}正在合并音频与视频…")
        merge_video_and_audio(
            temp_video_path, audio_path, merged_video_path, keep_original_audio
        )

        if subtitle_path:
            self._append_log(f"{log_prefix}正在烧录字幕…")
            burn_subtitles_onto_video(
                merged_video_path, subtitle_path, export_path, font_file
            )
            try:
                merged_video_path.unlink()
            except OSError:
                pass

            # Clean up subtitle file after burning
            try:
                subtitle_path.unlink()
                self._append_log(f"{log_prefix}已清理字幕文件")
            except OSError:
                pass

        # Clean up temporary files
        try:
            temp_video_path.unlink()
        except OSError:
            pass

        try:
            audio_path.unlink()
            self._append_log(f"{log_prefix}已清理临时音频文件")
        except OSError:
            pass

        return VideoBuildResult(
            used_files=used_files,
            export_path=export_path,
        )


def list_files_with_extensions(directory: Path, extensions: Iterable[str]) -> List[Path]:
    ext_set = {ext.lower() for ext in extensions}
    return [
        path
        for path in sorted(directory.iterdir())
        if path.is_file() and path.suffix.lower() in ext_set
    ]


def apply_audio_speed(segment: AudioSegment, speed_multiplier: float) -> AudioSegment:
    if abs(speed_multiplier - 1.0) <= 1e-3:
        return segment

    base_rate = segment.frame_rate or 44100
    new_rate = max(1, int(base_rate * speed_multiplier))
    sped = segment._spawn(segment.raw_data, overrides={"frame_rate": new_rate})
    return sped.set_frame_rate(base_rate)


def load_segments_from_transcript_file(
    path: Path,
    *,
    audio_duration_sec: float,
    max_chars: int,
) -> List[Tuple[float, float, str]]:
    suffix = path.suffix.lower()
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"无法读取字幕文本文件：{exc}") from exc

    if not content.strip():
        return []

    if suffix == ".srt":
        segments = parse_srt_segments(content)
        return reflow_segment_texts(segments, max_chars)
    if suffix == ".ass":
        segments = parse_ass_segments(content)
        return reflow_segment_texts(segments, max_chars)

    # Treat as plain text; evenly distribute over audio duration.
    segments = build_segments_from_plain_text(
        content,
        total_duration_sec=audio_duration_sec,
        max_chars=max_chars,
    )
    segments = clamp_segments_to_duration(segments, audio_duration_sec)
    return reflow_segment_texts(segments, max_chars)


def find_matching_subtitle(subtitle_dir: Path, audio_path: Path) -> Path:
    base = audio_path.stem
    preferred_exts = [".srt", ".ass"]
    for ext in preferred_exts:
        candidate = subtitle_dir / f"{base}{ext}"
        if candidate.exists() and candidate.is_file():
            return candidate

    lower_base = base.lower()
    for entry in subtitle_dir.iterdir():
        if entry.is_file() and entry.suffix.lower() in TRANSCRIPT_EXTENSIONS:
            if entry.stem.lower() == lower_base:
                return entry

    raise FileNotFoundError(
        f"在字幕文件夹 {subtitle_dir} 中找不到与音频文件 {audio_path.name} 同名的 SRT/ASS 文件。"
    )


def stitch_subtitles_from_clips(
    *,
    subtitle_dir: Path,
    clip_segments: Sequence[Tuple[Path, float]],
    max_chars: int,
) -> List[Tuple[float, float, str]]:
    if not clip_segments:
        raise ValueError("没有可用的音频片段，无法拼接字幕。")

    stitched: List[Tuple[float, float, str]] = []
    offset = 0.0
    for clip_path, duration in clip_segments:
        if duration < 0:
            duration = 0.0
        subtitle_file = find_matching_subtitle(subtitle_dir, clip_path)
        segments = load_segments_from_transcript_file(
            subtitle_file,
            audio_duration_sec=duration,
            max_chars=max_chars,
        )

        max_caption_end = max((seg[1] for seg in segments), default=0.0)
        clip_caption_span = max(duration, max_caption_end)

        for start, end, text in segments:
            adjusted_start = offset + start
            adjusted_end = offset + end
            if adjusted_end - adjusted_start < 0.01:
                adjusted_end = adjusted_start + 0.01
            stitched.append((adjusted_start, adjusted_end, text))
        if clip_caption_span > 0:
            offset += clip_caption_span
        else:
            offset += max_caption_end

    return stitched


def parse_srt_segments(content: str) -> List[Tuple[float, float, str]]:
    blocks = re.split(r"\r?\n\r?\n+", content.strip())
    segments: List[Tuple[float, float, str]] = []
    for block in blocks:
        lines = [line.strip("\ufeff") for line in block.strip().splitlines() if line.strip()]
        if not lines:
            continue
        # Skip numeric index line
        if re.fullmatch(r"\d+", lines[0]):
            lines = lines[1:]
        if not lines:
            continue
        timing_line = lines[0]
        timing_match = re.match(
            r"(?P<start>\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})\s*-->\s*(?P<end>\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})",
            timing_line,
        )
        if not timing_match:
            continue
        start = parse_srt_timestamp(timing_match.group("start"))
        end = parse_srt_timestamp(timing_match.group("end"))
        if start is None or end is None:
            continue
        text = "\n".join(lines[1:]).strip()
        if not text:
            continue
        segments.append((start, end, text))
    return segments


def parse_ass_segments(content: str) -> List[Tuple[float, float, str]]:
    lines = content.splitlines()
    in_events = False
    format_fields: List[str] = []
    default_format = [
        "layer",
        "start",
        "end",
        "style",
        "name",
        "marginl",
        "marginr",
        "marginv",
        "effect",
        "text",
    ]
    segments: List[Tuple[float, float, str]] = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("[events]"):
            in_events = True
            continue
        if lower.startswith("[") and not lower.startswith("[events]"):
            in_events = False
            continue
        if not in_events:
            continue
        if lower.startswith("format:"):
            format_fields = [field.strip().lower() for field in line[7:].split(",")]
            continue
        if lower.startswith("dialogue:"):
            if not format_fields:
                format_fields = default_format.copy()
            data = line[len("dialogue:"):].lstrip()
            parts = data.split(",", len(format_fields) - 1)
            if len(parts) < len(format_fields):
                continue
            mapping = dict(zip(format_fields, parts))
            start = parse_ass_timestamp(mapping.get("start", "0:00:00.00"))
            end = parse_ass_timestamp(mapping.get("end", "0:00:00.00"))
            if start is None or end is None:
                continue
            text = mapping.get("text", "")
            if not text:
                continue
            clean_text = re.sub(r"{[^}]*}", "", text)
            clean_text = clean_text.replace("\\N", "\n").replace("\\n", "\n").strip()
            if not clean_text:
                continue
            segments.append((start, end, clean_text))
    return segments


def clamp_segments_to_duration(
    segments: Sequence[Tuple[float, float, str]],
    total_duration_sec: float,
) -> List[Tuple[float, float, str]]:
    if total_duration_sec <= 0:
        total_duration_sec = 0.01

    clamped: List[Tuple[float, float, str]] = []
    for start, end, text in segments:
        clean_text = text.strip()
        if not clean_text:
            continue
        safe_start = max(0.0, min(start, total_duration_sec))
        safe_end = max(safe_start + 0.01, min(end, total_duration_sec))
        if safe_end <= safe_start:
            continue
        clamped.append((safe_start, safe_end, clean_text))

    clamped.sort(key=lambda item: item[0])
    return clamped


def reflow_segment_texts(
    segments: Sequence[Tuple[float, float, str]],
    max_chars: int,
) -> List[Tuple[float, float, str]]:
    if max_chars <= 0:
        return list(segments)

    reflowed: List[Tuple[float, float, str]] = []
    for start, end, text in segments:
        raw_lines = text.replace("\r", "\n").split("\n")
        wrapped_lines: List[str] = []
        for raw_line in raw_lines:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            wrapped_lines.extend(_wrap_line_preserving_words(raw_line, max_chars))
        combined = "\n".join(line.strip() for line in wrapped_lines if line.strip())
        if not combined:
            combined = text.strip()
        if not combined:
            continue
        reflowed.append((start, end, combined))
    return reflowed


def parse_srt_timestamp(value: str) -> Optional[float]:
    value = value.strip().replace(",", ".")
    try:
        hours_str, minutes_str, seconds_str = value.split(":")
        hours = int(hours_str)
        minutes = int(minutes_str)
        seconds = float(seconds_str)
    except (ValueError, TypeError):
        return None
    return max(0.0, hours * 3600 + minutes * 60 + seconds)


def parse_ass_timestamp(value: str) -> Optional[float]:
    parts = value.strip().split(":")
    if len(parts) != 3:
        return None
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
    except (ValueError, TypeError):
        return None
    return max(0.0, hours * 3600 + minutes * 60 + seconds)


def build_segments_from_plain_text(
    text: str,
    total_duration_sec: float,
    max_chars: int,
) -> List[Tuple[float, float, str]]:
    phrases = split_into_short_phrases(text, max_chars)
    if not phrases:
        return []

    total_duration_sec = max(0.01, total_duration_sec)
    per_segment = total_duration_sec / len(phrases)
    start = 0.0
    segments: List[Tuple[float, float, str]] = []

    for phrase in phrases:
        end = min(total_duration_sec, start + per_segment)
        if end - start < 0.05:
            end = min(total_duration_sec, start + 0.05)
        segments.append((start, end, phrase))
        start = end

    # Ensure final subtitle reaches音频尾部
    if segments:
        last_start, _, last_text = segments[-1]
        segments[-1] = (last_start, total_duration_sec, last_text)

    return segments


def split_into_short_phrases(text: str, max_chars: int) -> List[str]:
    normalized = text.replace("\r", "\n")
    phrases: List[str] = []
    blocks = re.split(r"[\n]+", normalized)
    for block in blocks:
        chunk = block.strip()
        if not chunk:
            continue
        sentences = re.split(r"(?<=[。！？!?…])\s*", chunk)
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            phrases.extend(_wrap_line_preserving_words(sentence, max_chars))
    return [phrase for phrase in phrases if phrase]


def refine_segments_for_length(
    segments: Sequence[Tuple[float, float, str]],
    max_chars: int,
) -> List[Tuple[float, float, str]]:
    refined: List[Tuple[float, float, str]] = []
    for start, end, text in segments:
        start = max(0.0, start)
        end = max(start + 0.05, end)
        wrapped_lines = _wrap_text_for_timed_segment(text, max_chars)
        if not wrapped_lines:
            continue
        refined.append((start, end, "\n".join(wrapped_lines)))
    return refined


def _wrap_text_for_timed_segment(text: str, max_chars: int) -> List[str]:
    normalized = text.replace("\r", "\n")
    lines: List[str] = []
    for block in normalized.split("\n"):
        chunk = block.strip()
        if not chunk:
            continue
        lines.extend(_wrap_line_preserving_words(chunk, max_chars))
    return lines


def _wrap_line_preserving_words(text: str, max_chars: int) -> List[str]:
    text = text.strip()
    if not text:
        return []
    if max_chars <= 0 or len(text) <= max_chars:
        return [text]

    looks_english = bool(re.search(r"[A-Za-z]", text))
    contains_space = " " in text

    if looks_english and contains_space:
        # Use textwrap for English text with spaces
        # This preserves word boundaries
        wrapper = textwrap.TextWrapper(
            width=max(1, max_chars),
            break_long_words=False,
            break_on_hyphens=False,
        )
        try:
            wrapped = wrapper.wrap(text)
            if wrapped:
                return wrapped
        except Exception:
            # If textwrap fails, fall back to splitting by spaces
            pass

        # Manual word-boundary splitting for safety
        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            word_length = len(word)
            # If adding this word exceeds max_chars, start new line
            if current_line and current_length + 1 + word_length > max_chars:
                lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_length
            else:
                current_line.append(word)
                current_length += word_length + (1 if current_line else 0)

        if current_line:
            lines.append(" ".join(current_line))

        return lines if lines else [text]

    # For Chinese or text without spaces, split by characters
    return [
        text[i : i + max_chars].strip()
        for i in range(0, len(text), max_chars)
        if text[i : i + max_chars].strip()
    ]


def write_ass_file(
    segments: Sequence[Tuple[float, float, str]],
    *,
    font_name: str,
    font_size: int,
    output_path: Path,
) -> None:
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {ASS_PLAY_RES_X}\n"
        f"PlayResY: {ASS_PLAY_RES_Y}\n"
        "ScaledBorderAndShadow: yes\n"
        "WrapStyle: 2\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font_name},{font_size},&H0000FFFF,&H0000FFFF,"
        f"&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,50,50,{ASS_MARGIN_V},1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = [header]
    for start, end, text in segments:
        start_ts = format_ass_timestamp(start)
        end_ts = format_ass_timestamp(end)
        clean_text = escape_ass_text(text)
        lines.append(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{clean_text}")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def format_ass_timestamp(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centiseconds = int(round((seconds - int(seconds)) * 100))
    if centiseconds >= 100:
        centiseconds -= 100
        secs += 1
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def escape_ass_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", r"\N")
    )


def format_duration_tag(duration_ms: int) -> str:
    total_seconds = int(duration_ms / 1000)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}m{seconds:02d}s"


def build_audio_filename(index: int, total: int) -> str:
    if total <= 1:
        return AUDIO_EXPORT_NAME
    width = max(2, len(str(total)))
    return f"bgm_final_{index:0{width}d}.mp3"


def build_video_filename(length_tag: str, index: int, total: int) -> str:
    if total <= 1:
        return VIDEO_EXPORT_TEMPLATE.format(length_tag=length_tag)
    width = max(2, len(str(total)))
    return f"final_video_{length_tag}_{index:0{width}d}.mp4"


def probe_video_duration(path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        result = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("未找到 ffprobe，请确认已安装 FFmpeg 并位于 PATH 中。") from exc

    if result.returncode != 0:
        return 0.0

    try:
        return float(result.stdout.strip())
    except (TypeError, ValueError):
        return 0.0


def probe_audio_duration(path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        result = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        return 0.0

    if result.returncode != 0:
        return 0.0

    try:
        return float(result.stdout.strip())
    except (TypeError, ValueError):
        return 0.0


def concat_videos_with_ffmpeg(
    segments: Sequence[Tuple[Path, Optional[float]]],
    output_path: Path,
    *,
    speed_multiplier: float,
    keep_original_audio: bool,
    progress_callback: Optional[Callable[[float], None]],
    expected_duration: Optional[float],
) -> None:
    if not segments:
        raise ValueError("没有可供拼接的视频片段。")

    if keep_original_audio:
        # When keeping original audio, use a simpler two-pass approach
        # First concatenate videos with their audio, then handle speed adjustment
        temp_concat_list = output_path.parent / f"__temp_list_{uuid.uuid4().hex}.txt"

        try:
            # Build concat demuxer file list
            with open(temp_concat_list, "w", encoding="utf-8") as f:
                for path, duration in segments:
                    # Escape single quotes in path
                    escaped_path = str(path).replace("'", "'\\''")
                    f.write(f"file '{escaped_path}'\n")
                    if duration is not None:
                        f.write(f"duration {duration:.6f}\n")

            cmd: List[str] = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(temp_concat_list)]

            # Apply speed adjustment if needed
            if abs(speed_multiplier - 1.0) > 1e-3:
                video_factor = 1.0 / speed_multiplier
                filter_complex = f"[0:v]setpts={video_factor:.6f}*PTS[outv]"

                # Handle audio tempo adjustment
                tempo = speed_multiplier
                audio_chain = "[0:a]"
                if tempo > 2.0:
                    # Chain multiple atempo filters for values > 2.0
                    while tempo > 2.0:
                        audio_chain += "atempo=2.0,"
                        tempo /= 2.0
                    audio_chain += f"atempo={tempo:.6f}[outa]"
                elif tempo < 0.5:
                    # Chain multiple atempo filters for values < 0.5
                    while tempo < 0.5:
                        audio_chain += "atempo=0.5,"
                        tempo /= 0.5
                    audio_chain += f"atempo={tempo:.6f}[outa]"
                else:
                    audio_chain += f"atempo={tempo:.6f}[outa]"

                filter_complex += ";" + audio_chain

                cmd.extend(["-filter_complex", filter_complex, "-map", "[outv]", "-map", "[outa]"])
            else:
                cmd.extend(["-c:v", "copy", "-c:a", "copy"])

            cmd.extend([
                "-c:v", "libx264",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                str(output_path)
            ])

            run_ffmpeg_command(
                cmd,
                progress_callback=progress_callback,
                expected_duration=expected_duration,
            )
        finally:
            # Clean up temp file
            try:
                temp_concat_list.unlink()
            except OSError:
                pass
    else:
        # Original logic for no audio
        cmd: List[str] = ["ffmpeg", "-y"]
        filter_inputs_v: List[str] = []
        filter_steps: List[str] = []

        for idx, (path, duration) in enumerate(segments):
            if duration is not None:
                cmd.extend(["-t", f"{duration:.6f}", "-i", str(path)])
            else:
                cmd.extend(["-i", str(path)])

            # Video processing
            input_label_v = f"[{idx}:v]"
            if abs(speed_multiplier - 1.0) > 1e-3:
                output_label_v = f"[v{idx}]"
                factor = 1.0 / speed_multiplier
                filter_steps.append(f"{input_label_v}setpts={factor:.6f}*PTS{output_label_v}")
                filter_inputs_v.append(output_label_v)
            else:
                filter_inputs_v.append(input_label_v)

        # Build concat filter (video only)
        concat_line = "".join(filter_inputs_v) + f"concat=n={len(segments)}:v=1:a=0[outv]"

        if filter_steps:
            filter_complex = ";".join(filter_steps + [concat_line])
        else:
            filter_complex = concat_line

        cmd.extend(["-filter_complex", filter_complex, "-map", "[outv]"])
        cmd.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-pix_fmt",
                "yuv420p",
                str(output_path),
            ]
        )

        run_ffmpeg_command(
            cmd,
            progress_callback=progress_callback,
            expected_duration=expected_duration,
        )


def merge_video_and_audio(
    video_path: Path, audio_path: Path, output_path: Path, keep_original_audio: bool
) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
    ]

    if keep_original_audio:
        # Mix original video audio with background music
        # Background music at 1.5x volume (weight=1.5)
        # Video audio at original volume (weight=1)
        # normalize=0 prevents automatic volume reduction
        cmd.extend(
            [
                "-filter_complex",
                "[0:a][1:a]amix=inputs=2:duration=shortest:dropout_transition=2:weights=1 1.5:normalize=0[aout]",
                "-map",
                "0:v:0",
                "-map",
                "[aout]",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "320k",
                "-shortest",
            ]
        )
    else:
        # Only use background music - preserve original volume
        cmd.extend(
            [
                "-c:v",
                "copy",
                "-filter:a",
                "volume=1.0",  # Preserve original volume
                "-c:a",
                "aac",
                "-b:a",
                "320k",  # Higher bitrate to preserve quality
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-shortest",
            ]
        )

    cmd.append(str(output_path))
    run_ffmpeg_command(cmd)


def burn_subtitles_onto_video(
    input_video: Path,
    subtitle_path: Path,
    output_video: Path,
    font_file: Optional[Path] = None,
) -> None:
    # Build the subtitle filter
    filter_arg = f"subtitles='{escape_subtitle_filter_path(subtitle_path)}'"

    # If a font file is provided, add fontsdir parameter
    if font_file and font_file.exists():
        font_dir = escape_subtitle_filter_path(font_file.parent)
        filter_arg = f"subtitles='{escape_subtitle_filter_path(subtitle_path)}':fontsdir='{font_dir}'"

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_video),
        "-vf",
        filter_arg,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        str(output_video),
    ]
    run_ffmpeg_command(cmd)


def escape_subtitle_filter_path(path: Path) -> str:
    escaped = str(path)
    escaped = escaped.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return escaped


def run_ffmpeg_command(
    cmd: Sequence[str],
    *,
    progress_callback: Optional[Callable[[float], None]] = None,
    expected_duration: Optional[float] = None,
) -> None:
    cmd_list = list(cmd)
    try:
        if progress_callback and expected_duration and expected_duration > 0:
            cmd_list = cmd_list + ["-progress", "pipe:1", "-nostats"]
            process = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert process.stdout is not None
            assert process.stderr is not None
            last_fraction = -0.1
            try:
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    line = line.strip()
                    if line.startswith("out_time_ms="):
                        try:
                            out_ms = int(line.split("=", 1)[1])
                        except ValueError:
                            continue
                        fraction = min(out_ms / 1_000_000 / expected_duration, 1.0)
                        if fraction - last_fraction >= 0.05:
                            last_fraction = fraction
                            progress_callback(fraction)
                    elif line == "progress=end":
                        progress_callback(1.0)
            finally:
                stdout_tail = process.stdout.read()
                if stdout_tail:
                    pass
                stderr = process.stderr.read()
                returncode = process.wait()
        else:
            result = subprocess.run(
                cmd_list,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            returncode = result.returncode
            stderr = result.stderr
    except FileNotFoundError as exc:
        raise RuntimeError("未找到 ffmpeg，请确认已安装并位于 PATH 中。") from exc

    if returncode != 0:
        stderr = (stderr or "").strip()
        message = stderr.splitlines()[-1] if stderr else "ffmpeg 命令执行失败。"
        raise RuntimeError(message)


def _load_settings() -> dict:
    try:
        raw = CONFIG_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError:
        return {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    return data if isinstance(data, dict) else {}


def _save_settings(data: dict) -> None:
    try:
        CONFIG_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def download_zy_oliver_font() -> Optional[Path]:
    """Download ZY Oliver font and return the path to the TTF file.

    Returns None if download fails.
    """
    try:
        FONT_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Check if font already exists
        existing_fonts = list(FONT_CACHE_DIR.glob("*.ttf")) + list(FONT_CACHE_DIR.glob("*.otf"))
        if existing_fonts:
            return existing_fonts[0]

        zip_path = FONT_CACHE_DIR / "zy_oliver.zip"

        # Download the font zip file with timeout
        req = urllib.request.Request(
            ZY_OLIVER_FONT_URL,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            with open(zip_path, 'wb') as out_file:
                out_file.write(response.read())

        # Extract the zip file
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(FONT_CACHE_DIR)

        # Clean up zip file
        try:
            zip_path.unlink()
        except OSError:
            pass

        # Find the TTF/OTF file
        font_files = list(FONT_CACHE_DIR.glob("*.ttf")) + list(FONT_CACHE_DIR.glob("*.otf"))
        if font_files:
            return font_files[0]

        return None
    except Exception as e:
        # If download fails, try to clean up
        try:
            if 'zip_path' in locals() and zip_path.exists():
                zip_path.unlink()
        except OSError:
            pass
        return None


def main() -> None:
    app = RandomAVStitcherApp()
    app.mainloop()


if __name__ == "__main__":
    main()
