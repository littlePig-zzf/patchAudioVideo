# 随机音视频拼接工具

一个功能强大的自动化视频制作工具，支持随机拼接音视频素材，并使用 Whisper AI 自动生成同步字幕。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## ✨ 主要功能

### 🎬 视频处理
- **随机拼接**：从素材库中随机选择视频片段进行拼接
- **指定开头**：可指定第一个视频和开头素材
- **速度调整**：支持视频速度倍数调整
- **智能去重**：避免相邻视频片段重复
- **开头素材管理**：前 N 个片段可单独使用开头素材

### 🎵 音频处理
- **音乐拼接**：支持随机或按名称顺序拼接背景音乐
- **时长匹配**：自动拼接到目标时长
- **速度调整**：支持音频速度调整（保持音调）
- **混音支持**：可保留原视频音频并与背景音乐混合
- **智能去重**：避免短时间内重复播放同一首歌

### 📝 字幕功能
- **AI 自动识别**：使用 OpenAI Whisper 自动识别语音内容
- **精确同步**：字幕与音频完美同步
- **文本替换**：可提供自定义文本，使用 Whisper 时间戳 + 用户文本
- **智能断句**：
  - 英文按单词断行，不截断单词
  - 中文按字符断行
- **自定义样式**：
  - 黄色粗体文字
  - 黑色描边（4 像素）
  - 阴影效果
  - 底部居中显示
- **自定义字体**：支持自动下载和应用 ZY Oliver 字体

### 📊 其他特性
- **批量生成**：一次生成多个不同组合的视频
- **可视化界面**：Tkinter GUI，支持触控板/鼠标滚动
- **进度显示**：实时显示处理进度
- **设置记忆**：自动保存上次的配置
- **智能容错**：字体下载失败、Whisper 未安装等情况下继续运行
- **自动清理**：生成完成后自动清理临时文件

## 📋 系统要求

- **Python**: 3.10 或更高版本
- **操作系统**: macOS / Linux / Windows
- **FFmpeg**: 必须安装并在系统 PATH 中

## 🚀 安装步骤

### 1. 克隆仓库

```bash
git clone https://github.com/littlePig-zzf/patchAudioVideo.git
cd patchAudioVideo
```

### 2. 安装依赖

```bash
# 安装 Python 依赖
pip install pydub openai-whisper

# 确保安装正确的 NumPy 版本
pip install "numpy<2"
```

### 3. 安装 FFmpeg

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Windows:**
从 [FFmpeg 官网](https://ffmpeg.org/download.html) 下载并添加到系统 PATH

## 📖 使用方法

### 启动程序

```bash
python3 random_av_stitcher.py
```

### 界面配置

1. **基础设置**
   - `目标时长（分钟）`：设置最终视频的时长
   - `生成视频数量`：一次生成多少个视频
   - `视频速度倍数`：视频播放速度（1.0 为原速）
   - `音频速度倍数`：音频播放速度（1.0 为原速）

2. **素材路径**
   - `主体视频文件夹`：存放主要视频素材的文件夹
   - `开头素材文件夹`（可选）：存放开头专用素材的文件夹
   - `音乐文件夹`：存放背景音乐的文件夹
   - `输出文件夹`：生成视频的保存位置

3. **字幕设置**
   - ✅ 勾选 `启用字幕`
   - `字幕文本文件`（可选）：提供自定义文本
   - `字幕字体`：默认 "ZY Oliver"
   - `字幕字号（像素）`：默认 64

4. **高级选项**
   - `保留原声`：保留原视频音频并与背景音乐混合
   - `按名称拼接音乐`：按文件名顺序拼接音乐，否则随机
   - `指定第一个视频`（可选）：固定使用某个视频作为开头
   - `指定第一首音乐`（可选）：固定使用某首音乐作为开头

### 点击"开始生成"

程序会自动：
1. 拼接背景音乐到目标时长
2. 随机选择视频片段并拼接
3. 使用 Whisper 识别音频生成字幕
4. 下载并应用字体（首次运行）
5. 将字幕烧录到视频中
6. 清理所有临时文件

### 输出文件

生成的视频文件命名格式：`final_video_XXmXXs.mp4`

例如：`final_video_06m42s.mp4` 表示时长为 6 分 42 秒的视频

## 🎨 字幕样式说明

### 无文本文件（纯 Whisper 识别）
- Whisper 自动识别音频内容
- 自动生成时间戳
- 适合：音质好、发音清晰的英文内容

### 有文本文件（Whisper 时间戳 + 用户文本）
- Whisper 识别音频获取精确时间戳
- 使用用户提供的文本内容
- 智能匹配文本到时间段
- 适合：避免识别错误、专业术语、方言等

## 📁 项目结构

```
patchAudioVideo/
├── random_av_stitcher.py    # 主程序
├── README.md                 # 项目说明
└── .random_av_stitcher.json # 配置文件（自动生成）
```

## 🔧 技术栈

- **GUI 框架**: Tkinter
- **音频处理**: pydub
- **视频处理**: FFmpeg
- **语音识别**: OpenAI Whisper
- **深度学习**: PyTorch (Whisper 依赖)

## 📝 支持的文件格式

### 输入格式
- **视频**: `.mp4`, `.mov`, `.mkv`
- **音频**: `.mp3`, `.wav`, `.flac`
- **字幕文本**: `.txt`, `.srt`, `.ass`

### 输出格式
- **视频**: `.mp4` (H.264 编码)
- **音频**: `.aac` (192k 码率)
- **字幕**: `.ass` (生成后自动删除)

## ⚠️ 常见问题

### 1. NumPy 版本错误
```
A module that was compiled using NumPy 1.x cannot be run in NumPy 2.x
```
**解决方案**:
```bash
pip install "numpy<2"
```

### 2. FFmpeg 未找到
```
未找到 ffmpeg，请确认已安装并位于 PATH 中
```
**解决方案**: 安装 FFmpeg 并确保在系统 PATH 中

### 3. Whisper 识别慢
```
FP16 is not supported on CPU; using FP32 instead
```
**说明**: 这是正常警告，CPU 模式下 Whisper 会稍慢，但功能正常。如需加速，可使用 NVIDIA GPU。

### 4. 字体下载失败
程序会自动回退到系统默认字体，不影响功能。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 👤 作者

littlePig-zzf

## 🙏 致谢

- [OpenAI Whisper](https://github.com/openai/whisper) - 语音识别
- [pydub](https://github.com/jiaaro/pydub) - 音频处理
- [FFmpeg](https://ffmpeg.org/) - 音视频处理

## 📮 联系方式

如有问题或建议，请通过 GitHub Issues 联系。
