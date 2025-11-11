# 应用图标

## 🎨 设计理念

本图标结合了音视频拼接工具的核心元素:

- **🎬 电影胶片**: 代表视频素材,采用经典的胶片孔设计
- **🎵 音频波形**: 代表背景音乐,使用渐变色波形条
- **🔀 随机拼接**: 中心的随机图标表示随机组合功能
- **🎨 渐变配色**: 紫色渐变背景(#667eea → #764ba2),现代感十足

## 📁 文件结构

```
icons/
├── icon.svg           # 源 SVG 文件 (1024x1024)
├── icon.icns          # macOS 应用图标
├── icon.iconset/      # macOS iconset (用于生成 icns)
│   ├── icon_16x16.png
│   ├── icon_16x16@2x.png
│   ├── icon_32x32.png
│   ├── icon_32x32@2x.png
│   ├── icon_128x128.png
│   ├── icon_128x128@2x.png
│   ├── icon_256x256.png
│   ├── icon_256x256@2x.png
│   ├── icon_512x512.png
│   └── icon_512x512@2x.png
└── png/               # 各种尺寸的 PNG 图标
    ├── icon_16x16.png
    ├── icon_32x32.png
    ├── icon_64x64.png
    ├── icon_128x128.png
    ├── icon_256x256.png
    ├── icon_512x512.png
    └── icon_1024x1024.png
```

## 🔧 使用方法

### macOS 应用打包

```bash
pyinstaller --icon="icons/icon.icns" your_script.py
```

或在 `.spec` 文件中:

```python
app = BUNDLE(
    exe,
    name='YourApp.app',
    icon='icons/icon.icns',
    ...
)
```

### 文档和网页

使用 `png/` 目录中的 PNG 图标:

```html
<img src="icons/png/icon_256x256.png" alt="App Icon">
```

## 🎨 重新生成图标

如果修改了 `icon.svg`,运行以下命令重新生成所有尺寸:

```bash
python3 generate_icons.py
```

需要安装依赖:

```bash
brew install librsvg
```

## 🌈 配色方案

- **主背景渐变**: `#667eea` → `#764ba2`
- **音频波形**: `#ffd89b` → `#19547b`
- **随机图标**: `#f093fb` → `#f5576c`
- **胶片边框**: 白色半透明 `rgba(255,255,255,0.95)`

## 📐 尺寸规格

| 尺寸 | 用途 |
|------|------|
| 16x16 | 小图标、通知图标 |
| 32x32 | 任务栏图标 |
| 64x64 | 对话框图标 |
| 128x128 | 中等图标 |
| 256x256 | Finder 图标 |
| 512x512 | Retina 显示 |
| 1024x1024 | 高分辨率显示 |

## ✏️ 修改图标

如需修改图标设计:

1. 编辑 `../icon.svg` (在项目根目录)
2. 运行 `python3 ../generate_icons.py` 重新生成
3. 查看 `png/icon_512x512.png` 预览效果

推荐使用:
- [Inkscape](https://inkscape.org/) (免费)
- [Figma](https://www.figma.com/) (在线)
- [Sketch](https://www.sketch.com/) (macOS)

## 📝 注意事项

- macOS 的 `.icns` 文件需要包含多种尺寸,以支持不同分辨率显示
- Retina 显示屏需要 `@2x` 版本的图标
- 图标设计应简洁清晰,在小尺寸下也能识别
- 建议使用矢量图(SVG)作为源文件,方便缩放
