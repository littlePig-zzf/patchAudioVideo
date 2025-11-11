# 随机音视频拼接工具 - 打包说明

## 方案一:简单打包(推荐)

使用 PyInstaller 打包成单个可执行文件,不包含 whisper(字幕自动识别功能需要用户自行安装)。

### 步骤:

```bash
# 1. 安装打包依赖
pip install pyinstaller

# 2. 执行打包命令
pyinstaller --onefile \
    --windowed \
    --name "随机音视频拼接工具" \
    --clean \
    --exclude-module torch \
    --exclude-module tensorboard \
    --exclude-module whisper \
    random_av_stitcher.py

# 3. 打包完成后,可执行文件位于 dist 目录
```

### 使用说明:

- 打包后的应用大小约 20-30MB
- 需要预先安装 FFmpeg: `brew install ffmpeg`
- 如需字幕自动识别功能,需单独安装: `pip install openai-whisper`
- 字幕拼接功能(SRT/ASS)无需额外安装

---

## 方案二:完整打包

包含所有依赖(包括 whisper),体积较大(约 2-3GB)。

### 步骤:

```bash
# 1. 安装所有依赖
pip install -r requirements.txt
pip install openai-whisper

# 2. 执行打包命令
pyinstaller --onefile \
    --windowed \
    --name "随机音视频拼接工具完整版" \
    --clean \
    random_av_stitcher.py
```

### 优点:
- 开箱即用,包含字幕自动识别功能
- 无需单独安装 whisper

### 缺点:
- 文件体积很大(2-3GB)
- 打包时间长(10-30分钟)

---

## 方案三:使用虚拟环境运行(最轻量)

不打包,直接在 Python 环境中运行。

### 步骤:

```bash
# 1. 创建虚拟环境
python -m venv venv

# 2. 激活虚拟环境
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行程序
python random_av_stitcher.py
```

### 优点:
- 文件体积最小
- 更新方便
- 开发调试友好

---

## 系统要求

### 必需:
- Python 3.10 或更高版本
- FFmpeg (安装: `brew install ffmpeg`)
- pydub 库

### 可选:
- openai-whisper (字幕自动识别功能)
- 足够的磁盘空间(建议至少 5GB)

---

## 常见问题

### Q: 打包时间过长怎么办?
A: 使用方案一(简单打包),排除 torch 等大型依赖。

### Q: 打包后无法运行?
A: 检查是否安装了 FFmpeg,可以在终端运行 `ffmpeg -version` 验证。

### Q: 字幕功能无法使用?
A: 如使用简单打包,需要单独安装 whisper: `pip install openai-whisper`

### Q: 打包后文件太大?
A: 使用方案三,直接在 Python 环境中运行,无需打包。

---

## 推荐配置

**日常使用:**
- 方案三(虚拟环境运行) - 最灵活

**分享给他人:**
- 方案一(简单打包) - 体积小,启动快

**完全独立:**
- 方案二(完整打包) - 无需安装任何依赖
