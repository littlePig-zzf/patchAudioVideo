#!/bin/bash
# 随机音视频拼接工具 - 启动脚本

cd "$(dirname "$0")"

# 检查 FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️  警告: 未检测到 FFmpeg"
    echo "请安装 FFmpeg: brew install ffmpeg"
    echo ""
    read -p "按回车键继续..."
fi

# 启动应用
if [ -f "dist/随机音视频拼接工具.app/Contents/MacOS/随机音视频拼接工具" ]; then
    echo "🚀 启动应用..."
    open "dist/随机音视频拼接工具.app"
elif [ -f "random_av_stitcher.py" ]; then
    echo "🚀 从源码启动..."
    python3 random_av_stitcher.py
else
    echo "❌ 错误: 找不到应用文件"
    echo "请先运行打包脚本或确保在正确的目录"
    read -p "按回车键退出..."
fi
