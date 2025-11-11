#!/usr/bin/env python3
"""
生成应用图标 - 从 SVG 转换为多种尺寸的 PNG 和 ICNS
"""

import os
import subprocess
from pathlib import Path

# 图标尺寸
SIZES = [16, 32, 64, 128, 256, 512, 1024]

def check_dependencies():
    """检查必需的依赖"""
    try:
        subprocess.run(['rsvg-convert', '--version'],
                      capture_output=True, check=True)
        print("✅ rsvg-convert 已安装")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ 未找到 rsvg-convert")
        print("请安装: brew install librsvg")
        return False

    try:
        subprocess.run(['iconutil', '--version'],
                      capture_output=True, check=False)
        print("✅ iconutil 已安装 (macOS)")
    except FileNotFoundError:
        print("⚠️  iconutil 未找到 (仅 macOS 需要)")

    return True

def generate_png_icons(svg_path, output_dir):
    """从 SVG 生成多种尺寸的 PNG 图标"""
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    print(f"\n📦 生成 PNG 图标到: {output_dir}")

    for size in SIZES:
        output_file = output_dir / f"icon_{size}x{size}.png"

        cmd = [
            'rsvg-convert',
            '-w', str(size),
            '-h', str(size),
            '-o', str(output_file),
            str(svg_path)
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"  ✅ 生成 {size}x{size} 像素")
        except subprocess.CalledProcessError as e:
            print(f"  ❌ 生成 {size}x{size} 失败: {e}")
            return False

    return True

def generate_iconset(png_dir, iconset_dir):
    """创建 macOS .iconset 文件夹"""
    iconset_dir = Path(iconset_dir)
    iconset_dir.mkdir(exist_ok=True)

    print(f"\n📦 创建 iconset: {iconset_dir}")

    # macOS iconset 需要的尺寸和命名
    icon_mapping = {
        16: ['icon_16x16.png'],
        32: ['icon_16x16@2x.png', 'icon_32x32.png'],
        64: ['icon_32x32@2x.png'],
        128: ['icon_128x128.png'],
        256: ['icon_128x128@2x.png', 'icon_256x256.png'],
        512: ['icon_256x256@2x.png', 'icon_512x512.png'],
        1024: ['icon_512x512@2x.png'],
    }

    png_dir = Path(png_dir)

    for size, filenames in icon_mapping.items():
        source = png_dir / f"icon_{size}x{size}.png"
        if not source.exists():
            print(f"  ⚠️  缺少 {size}x{size} 图标")
            continue

        for filename in filenames:
            target = iconset_dir / filename
            try:
                import shutil
                shutil.copy(source, target)
                print(f"  ✅ 复制 {filename}")
            except Exception as e:
                print(f"  ❌ 复制 {filename} 失败: {e}")

    return True

def generate_icns(iconset_dir, output_file):
    """从 .iconset 生成 .icns 文件 (仅 macOS)"""
    if not Path(iconset_dir).exists():
        print(f"❌ iconset 目录不存在: {iconset_dir}")
        return False

    print(f"\n📦 生成 ICNS 文件: {output_file}")

    cmd = ['iconutil', '-c', 'icns', str(iconset_dir), '-o', str(output_file)]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"  ✅ 成功生成 {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ 生成 ICNS 失败: {e}")
        return False
    except FileNotFoundError:
        print("  ⚠️  iconutil 未找到 (仅 macOS 支持)")
        return False

def main():
    """主函数"""
    print("🎨 应用图标生成工具\n")

    # 检查依赖
    if not check_dependencies():
        print("\n❌ 缺少必需的依赖，请先安装")
        return

    # 文件路径
    svg_path = Path(__file__).parent / "icon.svg"
    icons_dir = Path(__file__).parent / "icons"
    png_dir = icons_dir / "png"
    iconset_dir = icons_dir / "icon.iconset"
    icns_file = icons_dir / "icon.icns"

    if not svg_path.exists():
        print(f"❌ SVG 文件不存在: {svg_path}")
        return

    # 创建目录
    icons_dir.mkdir(exist_ok=True)

    # 生成 PNG 图标
    if not generate_png_icons(svg_path, png_dir):
        print("\n❌ PNG 图标生成失败")
        return

    # 创建 iconset
    if not generate_iconset(png_dir, iconset_dir):
        print("\n❌ iconset 创建失败")
        return

    # 生成 ICNS (macOS)
    generate_icns(iconset_dir, icns_file)

    print("\n" + "="*60)
    print("✅ 图标生成完成!")
    print("="*60)
    print(f"\n📁 生成的文件:")
    print(f"  • PNG 图标: {png_dir}")
    print(f"  • iconset: {iconset_dir}")
    if icns_file.exists():
        print(f"  • ICNS 文件: {icns_file}")
    print(f"\n💡 使用方法:")
    print(f"  1. PNG 图标可用于网页、文档等")
    print(f"  2. ICNS 文件用于 macOS 应用打包")
    print(f"  3. 在打包时指定: --icon icons/icon.icns")

if __name__ == "__main__":
    main()
