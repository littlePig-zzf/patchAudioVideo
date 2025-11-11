#!/bin/bash
# 打包脚本 - 随机音视频拼接工具

echo "开始打包随机音视频拼接工具..."

# 清理之前的构建
rm -rf build dist

# 使用 PyInstaller 打包
# --onefile: 打包成单个可执行文件
# --windowed: 不显示控制台窗口
# --name: 指定应用名称
# --clean: 清理缓存
pyinstaller --onefile \
    --windowed \
    --name "随机音视频拼接工具" \
    --icon="icons/icon.icns" \
    --clean \
    --noconfirm \
    --exclude-module torch \
    --exclude-module tensorboard \
    --exclude-module whisper \
    random_av_stitcher.py

if [ $? -eq 0 ]; then
    echo "✅ 打包成功！"
    echo "📦 可执行文件位置: dist/随机音视频拼接工具.app"
    echo ""
    echo "注意事项:"
    echo "1. 需要预先安装 FFmpeg: brew install ffmpeg"
    echo "2. 如需字幕功能,需安装 openai-whisper: pip install openai-whisper"
    echo "3. 双击 dist/随机音视频拼接工具.app 即可运行"
else
    echo "❌ 打包失败，请检查错误信息"
    exit 1
fi
