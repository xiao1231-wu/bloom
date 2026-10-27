"""
美甲搭配师 - 照片资源管理工具

功能：
1. 生成高质量美甲款式 SVG 照片
2. 从公开 URL 下载美甲图片
3. 批量导入图片到款式库
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

PHOTOS_DIR = Path(__file__).resolve().parent.parent / "frontend" / "assets" / "photos"

# ============================================================
# 高质量美甲 SVG 生成器
# ============================================================

def generate_nail_svg(title, color_a, color_b, category, style="elegant", width=600, height=700):
    """生成高质量美甲款式 SVG 图片"""

    # 根据风格选择装饰元素
    decorations = {
        "elegant": '''<circle cx="280" cy="220" r="18" fill="none" stroke="white" stroke-width="1.5" opacity="0.7"/>
            <line x1="260" y1="200" x2="300" y2="240" stroke="white" stroke-width="0.8" opacity="0.5"/>
            <line x1="300" y1="200" x2="260" y2="240" stroke="white" stroke-width="0.8" opacity="0.5"/>''',
        "sparkle": '''<polygon points="280,180 283,195 298,198 285,206 289,221 280,213 271,221 275,206 262,198 277,195" fill="white" opacity="0.8"/>
            <polygon points="180,300 182,308 190,310 183,315 185,323 180,318 175,323 177,315 170,310 178,308" fill="white" opacity="0.6"/>
            <circle cx="350" cy="250" r="2" fill="white" opacity="0.7"/>
            <circle cx="320" cy="180" r="3" fill="white" opacity="0.5"/>''',
        "floral": '''<g transform="translate(280,200)" opacity="0.7">
            <circle cx="0" cy="-5" r="6" fill="white"/><circle cx="-6" cy="2" r="6" fill="white"/>
            <circle cx="6" cy="2" r="6" fill="white"/><circle cx="-4" cy="8" r="6" fill="white"/>
            <circle cx="4" cy="8" r="6" fill="white"/><circle cx="0" cy="2" r="4" fill="#f8d8e2"/>
            </g>''',
        "geometric": '''<rect x="250" y="180" width="40" height="40" rx="2" fill="none" stroke="white" stroke-width="1.5" opacity="0.6" transform="rotate(15,270,200)"/>
            <rect x="260" y="190" width="20" height="20" rx="1" fill="white" opacity="0.3" transform="rotate(15,270,200)"/>
            <line x1="240" y1="230" x2="330" y2="230" stroke="white" stroke-width="0.8" opacity="0.4"/>
            <line x1="240" y1="240" x2="330" y2="240" stroke="white" stroke-width="0.8" opacity="0.4"/>''',
        "minimal": '''<circle cx="280" cy="210" r="25" fill="none" stroke="white" stroke-width="1" opacity="0.5"/>
            <circle cx="280" cy="210" r="12" fill="white" opacity="0.2"/>''',
    }

    deco = decorations.get(style, decorations["elegant"])

    # 根据分类选择风格
    style_map = {
        "法式": "elegant", "猫眼": "sparkle", "闪钻": "sparkle", "镜面": "sparkle",
        "甜美": "floral", "渐变": "elegant", "纯色": "minimal", "裸色": "minimal",
        "轻奢": "geometric", "男士": "geometric",
    }
    actual_style = decorations.get(style_map.get(category, style), decorations["elegant"])

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" fill="none">
    <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="{color_a}"/>
            <stop offset="50%" stop-color="{color_b}"/>
            <stop offset="100%" stop-color="{color_a}"/>
        </linearGradient>
        <linearGradient id="nail" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#fff" stop-opacity="0.9"/>
            <stop offset="30%" stop-color="{color_b}" stop-opacity="0.8"/>
            <stop offset="70%" stop-color="{color_a}" stop-opacity="0.9"/>
            <stop offset="100%" stop-color="{color_a}" stop-opacity="0.95"/>
        </linearGradient>
        <radialGradient id="shine">
            <stop offset="0%" stop-color="white" stop-opacity="0.6"/>
            <stop offset="100%" stop-color="white" stop-opacity="0"/>
        </radialGradient>
        <filter id="soft-shadow">
            <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000" flood-opacity="0.1"/>
        </filter>
    </defs>

    <!-- 背景 -->
    <rect width="{width}" height="{height}" fill="url(#bg)"/>

    <!-- 背景纹理圆 -->
    <circle cx="{width//2}" cy="{height//2}" r="{min(width,height)//2.5}" fill="none" stroke="white" stroke-width="0.5" opacity="0.08"/>
    <circle cx="{width//2}" cy="{height//2}" r="{min(width,height)//3.5}" fill="none" stroke="white" stroke-width="0.5" opacity="0.06"/>

    <!-- 装饰元素 -->
    {actual_style}

    <!-- 手部背景 -->
    <g filter="url(#soft-shadow)" opacity="0.55">
        <ellipse cx="{width//2}" cy="{height-100}" rx="140" ry="180" fill="#f5d5c8"/>
    </g>

    <!-- 手指 -->
    <g opacity="0.5">
        <rect x="{width//2-130}" y="80" width="32" height="220" rx="16" fill="#f5d5c8"/>
        <rect x="{width//2-85}" y="60" width="32" height="240" rx="16" fill="#f5d5c8"/>
        <rect x="{width//2-40}" y="55" width="32" height="245" rx="16" fill="#f5d5c8"/>
        <rect x="{width//2+5}" y="62" width="32" height="238" rx="16" fill="#f5d5c8"/>
        <rect x="{width//2+50}" y="85" width="30" height="215" rx="15" fill="#f5d5c8"/>
    </g>

    <!-- 指甲覆盖层 -->
    <g filter="url(#soft-shadow)">
        <ellipse cx="{width//2-114}" cy="90" rx="16" ry="24" fill="url(#nail)" stroke="white" stroke-width="1"/>
        <ellipse cx="{width//2-69}" cy="70" rx="16" ry="25" fill="url(#nail)" stroke="white" stroke-width="1"/>
        <ellipse cx="{width//2-24}" cy="65" rx="16" ry="25" fill="url(#nail)" stroke="white" stroke-width="1"/>
        <ellipse cx="{width//2+21}" cy="72" rx="16" ry="24" fill="url(#nail)" stroke="white" stroke-width="1"/>
        <ellipse cx="{width//2+65}" cy="95" rx="15" ry="22" fill="url(#nail)" stroke="white" stroke-width="1"/>
    </g>

    <!-- 指甲高光 -->
    <g opacity="0.3">
        <ellipse cx="{width//2-116}" cy="82" rx="5" ry="16" fill="url(#shine)"/>
        <ellipse cx="{width//2-71}" cy="62" rx="5" ry="18" fill="url(#shine)"/>
        <ellipse cx="{width//2-26}" cy="57" rx="5" ry="18" fill="url(#shine)"/>
        <ellipse cx="{width//2+19}" cy="64" rx="5" ry="17" fill="url(#shine)"/>
        <ellipse cx="{width//2+63}" cy="87" rx="4" ry="15" fill="url(#shine)"/>
    </g>

    <!-- 款式名称 -->
    <rect x="{width//2-90}" y="{height-65}" width="180" height="45" rx="22" fill="rgba(255,255,255,0.85)"/>
    <text x="{width//2}" y="{height-38}" text-anchor="middle" fill="#2b1f28" font-size="18" font-family="sans-serif" font-weight="700">{title}</text>

    <!-- 分类标签 -->
    <rect x="{width//2-40}" y="{height-18}" width="80" height="22" rx="11" fill="{color_a}" fill-opacity="0.8"/>
    <text x="{width//2}" y="{height-3}" text-anchor="middle" fill="white" font-size="11" font-family="sans-serif" font-weight="600">{category}</text>
</svg>'''
    return svg


def generate_all_photos():
    """为所有款式生成照片"""
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

    styles = [
        # 女性热款
        ("樱粉奶油法式", "#f9c8d8", "#fff5f7", "法式"),
        ("玫瑰猫眼", "#c95a88", "#f5c2d8", "猫眼"),
        ("奶茶裸粉", "#c58f82", "#f5ded5", "裸色"),
        ("莓果镜面", "#8c2758", "#f2aec7", "镜面"),
        ("珍珠蝴蝶结", "#f6cadc", "#ffffff", "甜美"),
        ("微醺渐变", "#e9a8bb", "#fff7f8", "渐变"),
        ("黑樱茶歇", "#352031", "#c490a5", "轻奢"),
        ("蓝莓星闪", "#8f9fe5", "#e9edff", "闪钻"),
        ("蜜桃乌龙", "#ffab91", "#ffe0b2", "渐变"),
        ("薰衣草梦境", "#b39ddb", "#ede7f6", "渐变"),
        ("莓果奶昔", "#e91e63", "#f48fb1", "纯色"),
        ("暗夜丝绒", "#4a148c", "#9c27b0", "镜面"),
        ("草莓奶霜", "#ef5350", "#ffcdd2", "甜美"),
        ("极光白", "#e0e0e0", "#fafafa", "镜面"),
        ("蔷薇粉晶", "#f48fb1", "#fce4ec", "甜美"),
        ("伯爵玫瑰", "#8c3a5a", "#c96d8a", "轻奢"),
        ("蜜糖粉晶", "#ff80ab", "#fce4ec", "闪钻"),
        ("丝绒红酒", "#8e0000", "#c62828", "纯色"),
        # 男士款
        ("哑光黑武士", "#1a1a1a", "#3d3d3d", "男士"),
        ("几何暗纹", "#263238", "#546e7a", "轻奢"),
        ("深灰大理石", "#37474f", "#78909c", "轻奢"),
        ("机车铆钉风", "#424242", "#757575", "镜面"),
        ("简约雾灰", "#9e9e9e", "#e0e0e0", "纯色"),
        ("赛博黑银", "#212121", "#9e9e9e", "镜面"),
        ("极简裸黑", "#2d2d2d", "#f5f5f5", "法式"),
        ("哑光墨绿", "#1b3a2d", "#4a6b5d", "纯色"),
        # 更多热门
        ("金箔琥珀", "#ff8f00", "#ffcc80", "轻奢"),
        ("银河碎钻", "#263238", "#546e7a", "闪钻"),
        ("极光紫", "#673ab7", "#ce93d8", "猫眼"),
        ("紫水晶", "#6a1b9a", "#ab47bc", "猫眼"),
        ("极夜星空", "#0d1b2a", "#1b3a5c", "闪钻"),
    ]

    generated = []
    for i, (title, ca, cb, cat) in enumerate(styles):
        filename = f"photo_{i+1:03d}.svg"
        filepath = PHOTOS_DIR / filename

        # 确定风格
        style = "elegant"
        if cat in ("闪钻", "猫眼", "镜面"):
            style = "sparkle"
        elif cat in ("甜美",):
            style = "floral"
        elif cat in ("男士", "轻奢"):
            style = "geometric"
        elif cat in ("纯色", "裸色"):
            style = "minimal"

        svg = generate_nail_svg(title, ca, cb, cat, style)
        filepath.write_text(svg, encoding="utf-8")
        generated.append({
            "title": title,
            "file": filename,
            "color_a": ca,
            "color_b": cb,
            "category": cat,
        })
        print(f"  ✅ {filename} - {title}")

    # 保存映射文件
    mapping_path = PHOTOS_DIR / "mapping.json"
    mapping_path.write_text(json.dumps(generated, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n📸 共生成 {len(generated)} 张美甲照片 → {PHOTOS_DIR}")
    return generated


# ============================================================
# 公开图片下载器
# ============================================================

def download_image(url, save_path):
    """从公开URL下载图片"""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "MeijiaDapeishi/1.0 (Image Collector)"
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            # 检查是否为图片
            content_type = resp.headers.get("Content-Type", "")
            if not content_type.startswith("image/"):
                return None
            Path(save_path).write_bytes(data)
            return save_path
    except Exception as e:
        print(f"  ⚠️ 下载失败: {url[:60]}... ({e})")
        return None


def batch_download_from_urls(urls_file):
    """从URL列表文件批量下载图片"""
    if not Path(urls_file).exists():
        print(f"❌ 文件不存在: {urls_file}")
        return []

    urls = Path(urls_file).read_text(encoding="utf-8").strip().split("\n")
    urls = [u.strip() for u in urls if u.strip() and not u.startswith("#")]

    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    downloaded = []

    for i, url in enumerate(urls):
        ext = ".jpg"
        if ".png" in url.lower():
            ext = ".png"
        elif ".webp" in url.lower():
            ext = ".webp"

        filename = f"downloaded_{i+1:04d}{ext}"
        save_path = PHOTOS_DIR / filename

        print(f"  [{i+1}/{len(urls)}] 下载: {url[:70]}...")
        result = download_image(url, save_path)
        if result:
            downloaded.append(str(save_path))
            print(f"    ✅ → {filename}")
        else:
            print(f"    ❌ 失败")

    return downloaded


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    print("=" * 60)
    print("  美甲搭配师 - 照片资源管理")
    print("=" * 60)
    print()

    if len(sys.argv) < 2:
        print("用法:")
        print("  python photo_manager.py generate    生成高质量美甲SVG照片")
        print("  python photo_manager.py download <urls.txt>  从URL列表下载图片")
        print("  python photo_manager.py download <image_url>  下载单张图片")
        print()
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "generate":
        print("🎨 生成美甲款式照片...")
        generate_all_photos()

    elif cmd == "download":
        if len(sys.argv) < 3:
            print("请提供URL或URL列表文件路径")
            sys.exit(1)

        target = sys.argv[2]
        if target.startswith("http"):
            # 单个URL
            PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
            ext = ".jpg"
            if ".png" in target.lower():
                ext = ".png"
            filename = f"downloaded_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
            result = download_image(target, PHOTOS_DIR / filename)
            if result:
                print(f"✅ 下载成功: {filename}")
            else:
                print("❌ 下载失败")
        else:
            # URL列表文件
            batch_download_from_urls(target)

    else:
        print(f"未知命令: {cmd}")
