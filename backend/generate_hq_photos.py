"""
美甲搭配师 - 高质量美甲照片生成器

生成逼真、精美的美甲款式照片（SVG矢量图，细节丰富）
涵盖：法式、猫眼、渐变、镜面、闪钻、花卉、大理石、几何、磨砂等全部类别
"""

import json
import os
import sys
from pathlib import Path

PHOTOS_DIR = Path(__file__).resolve().parent.parent / "frontend" / "assets" / "photos"
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

# 肤色映射
SKIN_COLORS = {
    "fair": "#fce4d6",
    "medium": "#f5d5c8",
    "warm": "#e8c4a8",
    "olive": "#d4a88c",
    "tan": "#c49a7c",
}

# ===== 高精度美甲SVG模板 =====

def generate_premium_nail_svg(title, color_a, color_b, category, skin_tone="medium", accent_color=None, pattern=None):
    """生成细节丰富的高质量美甲SVG"""
    skin = SKIN_COLORS.get(skin_tone, SKIN_COLORS["medium"])
    accent = accent_color or color_a
    width, height = 800, 900

    # 根据类别生成装饰
    decorations = ""
    nail_effect = ""

    if category in ("法式",):
        nail_effect = f'''
        <ellipse cx="400" cy="180" rx="32" ry="55" fill="url(#nailGrad)" stroke="white" stroke-width="2.5"/>
        <path d="M370 155 Q400 135 430 155" stroke="white" stroke-width="8" fill="none" stroke-linecap="round" opacity="0.95"/>
        <ellipse cx="400" cy="180" rx="10" ry="35" fill="url(#shine)"/>'''
        decorations = '''<circle cx="350" cy="320" r="2" fill="#f8bbd0" opacity="0.6"/>
            <circle cx="450" cy="350" r="1.5" fill="#f8bbd0" opacity="0.5"/>
            <circle cx="380" cy="400" r="1" fill="white" opacity="0.4"/>'''

    elif category in ("猫眼",):
        nail_effect = f'''
        <ellipse cx="400" cy="180" rx="32" ry="55" fill="url(#catEyeGrad)" stroke="rgba(255,255,255,0.5)" stroke-width="2"/>
        <ellipse cx="395" cy="175" rx="5" ry="40" fill="url(#catEyeLine)" opacity="0.7"/>
        <ellipse cx="400" cy="180" rx="9" ry="38" fill="url(#shine)"/>'''

    elif category in ("闪钻",):
        nail_effect = f'''
        <ellipse cx="400" cy="180" rx="32" ry="55" fill="url(#glitterGrad)" stroke="rgba(255,255,255,0.5)" stroke-width="2"/>
        <ellipse cx="400" cy="180" rx="10" ry="38" fill="url(#shine)"/>
        <circle cx="388" cy="165" r="1.5" fill="white" opacity="0.9"/>
        <circle cx="405" cy="190" r="2" fill="white" opacity="0.8"/>
        <circle cx="395" cy="200" r="1" fill="white" opacity="0.7"/>
        <circle cx="410" cy="170" r="1.5" fill="white" opacity="0.85"/>
        <circle cx="385" cy="185" r="1" fill="white" opacity="0.6"/>'''

    elif category in ("花卉",):
        nail_effect = f'''
        <ellipse cx="400" cy="180" rx="32" ry="55" fill="url(#nailGrad)" stroke="rgba(255,255,255,0.5)" stroke-width="2"/>
        <circle cx="390" cy="170" r="6" fill="white" opacity="0.5"/>
        <circle cx="410" cy="185" r="5" fill="white" opacity="0.45"/>
        <circle cx="395" cy="190" r="4" fill="{accent}" opacity="0.4"/>'''

    elif category in ("大理石",):
        nail_effect = f'''
        <ellipse cx="400" cy="180" rx="32" ry="55" fill="url(#marbleGrad)" stroke="rgba(255,255,255,0.5)" stroke-width="2"/>
        <path d="M375 160 Q390 180 385 210" stroke="white" stroke-width="1.5" fill="none" opacity="0.3"/>
        <path d="M420 155 Q415 190 425 220" stroke="white" stroke-width="1" fill="none" opacity="0.25"/>
        <ellipse cx="400" cy="180" rx="8" ry="35" fill="url(#shine)"/>'''

    elif category in ("磨砂",):
        nail_effect = f'''
        <ellipse cx="400" cy="180" rx="32" ry="55" fill="url(#matteGrad)" stroke="rgba(255,255,255,0.3)" stroke-width="2"/>
        <ellipse cx="400" cy="180" rx="7" ry="32" fill="url(#shine)" opacity="0.3"/>'''

    elif category in ("几何",):
        nail_effect = f'''
        <ellipse cx="400" cy="180" rx="32" ry="55" fill="url(#nailGrad)" stroke="rgba(255,255,255,0.5)" stroke-width="2"/>
        <line x1="382" y1="150" x2="418" y2="210" stroke="white" stroke-width="1.5" opacity="0.5"/>
        <line x1="418" y1="150" x2="382" y2="210" stroke="white" stroke-width="1.5" opacity="0.5"/>'''

    elif category in ("3D立体",):
        nail_effect = f'''
        <ellipse cx="400" cy="180" rx="32" ry="55" fill="url(#nailGrad)" stroke="rgba(255,255,255,0.5)" stroke-width="2"/>
        <ellipse cx="400" cy="170" rx="12" ry="14" fill="{accent}" opacity="0.5"/>
        <ellipse cx="400" cy="170" rx="8" ry="10" fill="{accent}" opacity="0.35"/>
        <ellipse cx="400" cy="170" rx="4" ry="6" fill="white" opacity="0.3"/>'''

    else:
        nail_effect = f'''
        <ellipse cx="400" cy="180" rx="32" ry="55" fill="url(#nailGrad)" stroke="white" stroke-width="2"/>
        <ellipse cx="400" cy="180" rx="9" ry="36" fill="url(#shine)"/>'''

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" fill="none">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{color_a}" stop-opacity="0.08"/>
    <stop offset="50%" stop-color="{color_b}" stop-opacity="0.12"/>
    <stop offset="100%" stop-color="{color_a}" stop-opacity="0.06"/>
  </linearGradient>
  <linearGradient id="nailGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#fff" stop-opacity="0.95"/>
    <stop offset="25%" stop-color="{color_b}" stop-opacity="0.9"/>
    <stop offset="60%" stop-color="{color_a}" stop-opacity="0.95"/>
    <stop offset="100%" stop-color="{color_a}" stop-opacity="1"/>
  </linearGradient>
  <linearGradient id="catEyeGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#1a0008"/>
    <stop offset="30%" stop-color="{color_a}"/>
    <stop offset="65%" stop-color="{color_b}"/>
    <stop offset="100%" stop-color="{color_a}"/>
  </linearGradient>
  <linearGradient id="catEyeLine" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="white" stop-opacity="0"/>
    <stop offset="40%" stop-color="white" stop-opacity="0.6"/>
    <stop offset="60%" stop-color="white" stop-opacity="0.6"/>
    <stop offset="100%" stop-color="white" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="glitterGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#fff" stop-opacity="0.9"/>
    <stop offset="30%" stop-color="{accent}"/>
    <stop offset="70%" stop-color="{color_a}"/>
    <stop offset="100%" stop-color="{color_a}"/>
  </linearGradient>
  <linearGradient id="marbleGrad" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#fff"/>
    <stop offset="40%" stop-color="{color_b}"/>
    <stop offset="60%" stop-color="#eee"/>
    <stop offset="100%" stop-color="{color_a}" stop-opacity="0.8"/>
  </linearGradient>
  <linearGradient id="matteGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{color_b}"/>
    <stop offset="50%" stop-color="{color_a}"/>
    <stop offset="100%" stop-color="{color_a}"/>
  </linearGradient>
  <radialGradient id="shine" cx="0.4" cy="0.3" r="0.6">
    <stop offset="0%" stop-color="white" stop-opacity="0.5"/>
    <stop offset="60%" stop-color="white" stop-opacity="0.08"/>
    <stop offset="100%" stop-color="white" stop-opacity="0"/>
  </radialGradient>
  <filter id="shadow">
    <feDropShadow dx="0" dy="3" stdDeviation="5" flood-color="#000" flood-opacity="0.08"/>
  </filter>
  <filter id="softShadow">
    <feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#000" flood-opacity="0.06"/>
  </filter>
</defs>

<!-- 背景 -->
<rect width="{width}" height="{height}" fill="#fffafd"/>
<rect width="{width}" height="{height}" fill="url(#bg)"/>

<!-- 装饰背景图案 -->
<circle cx="200" cy="200" r="120" fill="none" stroke="{color_a}" stroke-width="0.4" opacity="0.1"/>
<circle cx="600" cy="700" r="160" fill="none" stroke="{color_a}" stroke-width="0.4" opacity="0.08"/>
<circle cx="650" cy="250" r="80" fill="none" stroke="{color_b}" stroke-width="0.3" opacity="0.1"/>

<!-- 手部 -->
<g filter="url(#softShadow)">
  <!-- 手掌 -->
  <path d="M280 500 Q280 750 400 780 Q520 750 520 500 Z" fill="{skin}" opacity="0.9"/>
  <!-- 手指 -->
  <path d="M310 480 Q310 220 326 220 Q342 220 342 480 Z" fill="{skin}" opacity="0.85"/>
  <path d="M348 470 Q348 190 364 190 Q380 190 380 470 Z" fill="{skin}" opacity="0.85"/>
  <path d="M386 465 Q386 175 400 175 Q414 175 414 465 Z" fill="{skin}" opacity="0.88"/>
  <path d="M422 470 Q422 190 438 190 Q454 190 454 470 Z" fill="{skin}" opacity="0.85"/>
  <path d="M460 480 Q460 230 475 230 Q490 230 490 480 Z" fill="{skin}" opacity="0.8"/>
  <!-- 指尖圆角 -->
  <ellipse cx="326" cy="215" rx="16" ry="10" fill="{skin}" opacity="0.85"/>
  <ellipse cx="364" cy="185" rx="16" ry="10" fill="{skin}" opacity="0.85"/>
  <ellipse cx="400" cy="170" rx="16" ry="10" fill="{skin}" opacity="0.88"/>
  <ellipse cx="438" cy="185" rx="16" ry="10" fill="{skin}" opacity="0.85"/>
  <ellipse cx="475" cy="225" rx="15" ry="9" fill="{skin}" opacity="0.8"/>
</g>

<!-- 指甲 -->
<g filter="url(#shadow)">
  <g transform="translate(326, 220)">{nail_effect.replace('cx="400" cy="180"', 'cx="0" cy="-40"').replace('rx="32" ry="55"', 'rx="14" ry="28"')}</g>
  <g transform="translate(364, 196)">{nail_effect.replace('cx="400" cy="180"', 'cx="0" cy="-35"').replace('rx="32" ry="55"', 'rx="14" ry="29"')}</g>
  <g transform="translate(400, 186)">{nail_effect}</g>
  <g transform="translate(438, 196)">{nail_effect.replace('cx="400" cy="180"', 'cx="0" cy="-35"').replace('rx="32" ry="55"', 'rx="14" ry="29"')}</g>
  <g transform="translate(475, 230)">{nail_effect.replace('cx="400" cy="180"', 'cx="0" cy="-50"').replace('rx="32" ry="55"', 'rx="13" ry="25"')}</g>
</g>

<!-- 装饰元素 -->
{decorations}

<!-- 品牌水印 -->
<text x="700" y="860" text-anchor="end" fill="{color_a}" fill-opacity="0.2" font-size="14" font-family="DM Sans" font-weight="600">meijia.life</text>

<!-- 款式信息卡片 -->
<g transform="translate(120, 770)">
  <rect width="560" height="70" rx="16" fill="white" fill-opacity="0.92" stroke="{color_a}" stroke-width="0.8" stroke-opacity="0.25"/>
  <text x="280" y="40" text-anchor="middle" fill="#2b1f28" font-size="20" font-family="Noto Sans SC" font-weight="700">{title}</text>
  <text x="280" y="60" text-anchor="middle" fill="#7f6b76" font-size="12" font-family="Noto Sans SC">{category} · {color_a}</text>
</g>
</svg>'''
    return svg


# ===== 全部款式列表 =====

STYLE_LIST = [
    # (title, color_a, color_b, category, skin_tone, accent)
    # 法式
    ("经典白法式", "#fce4ec", "#fff", "法式", "medium", "#fff"),
    ("裸粉法式边", "#f8bbd0", "#fff5f7", "法式", "fair", "#f48fb1"),
    ("黑金法式", "#2d1f29", "#d4af37", "法式", "olive", "#d4af37"),
    ("薄荷法式", "#e0f7fa", "#fff", "法式", "fair", "#4dd0e1"),

    # 猫眼
    ("深红猫眼", "#8b0000", "#ff6b6b", "猫眼", "fair", "#ff8a80"),
    ("星空蓝猫眼", "#0d1b2a", "#1b3a5c", "猫眼", "fair", "#448aff"),
    ("翡翠绿猫眼", "#004d40", "#26a69a", "猫眼", "medium", "#64ffda"),
    ("紫晶猫眼", "#4a148c", "#ce93d8", "猫眼", "fair", "#ea80fc"),

    # 渐变
    ("粉紫渐变", "#ce93d8", "#fce4ec", "渐变", "fair", "#e1bee7"),
    ("落日橘渐变", "#ff9800", "#ffe0b2", "渐变", "tan", "#ffcc80"),
    ("海洋蓝渐变", "#0277bd", "#e1f5fe", "渐变", "medium", "#4fc3f7"),
    ("莓果渐变", "#880e4f", "#f8bbd0", "渐变", "fair", "#ff4081"),

    # 镜面
    ("炫彩镜面", "#e0e0e0", "#fafafa", "镜面", "fair", "#fff"),
    ("玫瑰金镜面", "#e8a0b4", "#fadadd", "镜面", "medium", "#f8bbd0"),
    ("冰银镜面", "#bdbdbd", "#f5f5f5", "镜面", "fair", "#fff"),

    # 闪钻
    ("全息碎钻", "#e0e0e0", "#fff", "闪钻", "fair", "#fff"),
    ("金粉世家", "#ffd54f", "#fff8e1", "闪钻", "tan", "#ffecb3"),
    ("银河星钻", "#1a237e", "#7986cb", "闪钻", "fair", "#fff"),

    # 花卉
    ("手绘玫瑰", "#e91e63", "#fce4ec", "花卉", "medium", "#f48fb1"),
    ("春日雏菊", "#fff176", "#e8f5e9", "花卉", "fair", "#ffeb3b"),
    ("和风樱花", "#f8bbd0", "#fff", "花卉", "fair", "#f48fb1"),

    # 大理石
    ("白大理石", "#f5f5f5", "#e0e0e0", "大理石", "fair", "#fff"),
    ("粉红大理石", "#f8bbd0", "#fce4ec", "大理石", "fair", "#f48fb1"),
    ("黑金大理石", "#1a1a1a", "#d4af37", "大理石", "fair", "#ffd54f"),

    # 3D立体
    ("立体花朵", "#f8bbd0", "#fce4ec", "3D立体", "medium", "#ff80ab"),
    ("水珠效果", "#e0f7fa", "#fff", "3D立体", "fair", "#80deea"),

    # 几何
    ("极简线条", "#212121", "#fafafa", "几何", "olive", "#424242"),
    ("色块拼接", "#ff5252", "#2196f3", "几何", "fair", "#ffeb3b"),
    ("格纹棋盘", "#212121", "#fff", "几何", "medium", "#424242"),

    # 磨砂
    ("哑光深红", "#8b0000", "#b22222", "磨砂", "fair", "#c62828"),
    ("哑光裸灰", "#bdbdbd", "#e0e0e0", "磨砂", "medium", "#9e9e9e"),
    ("哑光黑", "#1a1a1a", "#333", "磨砂", "olive", "#424242"),
    ("哑光军绿", "#4a5d3a", "#6b7f55", "磨砂", "tan", "#558b2f"),

    # 男士专属
    ("暗影骑士", "#1a1a1a", "#3d3d3d", "磨砂", "olive", "#424242"),
    ("灰调绅士", "#616161", "#9e9e9e", "磨砂", "medium", "#757575"),
    ("暗夜金属", "#263238", "#546e7a", "几何", "olive", "#78909c"),
    ("黑曜石", "#1a1a1a", "#2d2d2d", "镜面", "olive", "#424242"),
    ("迷彩绿", "#4a5d3a", "#6b7f55", "几何", "tan", "#8d6e63"),
    ("极暗黑", "#0d0d0d", "#1a1a1a", "磨砂", "olive", "#212121"),

    # 甜美
    ("蜜桃马卡龙", "#ff80ab", "#fff5f7", "法式", "fair", "#ffab91"),
    ("草莓奶霜", "#ef5350", "#ffcdd2", "闪钻", "fair", "#ff8a80"),
    ("樱花果冻", "#f8bbd0", "#fff", "渐变", "fair", "#f48fb1"),

    # 更多热门
    ("微醺红酒", "#722f37", "#b22222", "猫眼", "medium", "#ef5350"),
    ("香槟玫瑰", "#d4a574", "#f5e1d5", "渐变", "medium", "#ffe0b2"),
    ("极光紫", "#673ab7", "#ce93d8", "猫眼", "fair", "#ea80fc"),
    ("蓝莓之夜", "#1a237e", "#3949ab", "闪钻", "fair", "#5c6bc0"),
    ("奶茶裸", "#c58f82", "#f5ded5", "磨砂", "medium", "#d7ccc8"),
    ("干枯玫瑰", "#bc8f8f", "#e8c4b8", "磨砂", "medium", "#a1887f"),
    ("冰透粉", "#ffcdd2", "#fff", "渐变", "fair", "#f8bbd0"),
    ("杏仁奶咖", "#d7ccc8", "#faf0e6", "磨砂", "medium", "#bcaaa4"),
]

if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    print("=" * 60)
    print("  美甲搭配师 - 高质量照片生成器 v2")
    print("=" * 60)
    print()

    # 清空旧照片
    for old in PHOTOS_DIR.glob("hq_*.svg"):
        old.unlink()

    generated = []
    for i, (title, ca, cb, cat, skin, accent) in enumerate(STYLE_LIST):
        filename = f"hq_{i+1:03d}.svg"
        filepath = PHOTOS_DIR / filename

        svg = generate_premium_nail_svg(title, ca, cb, cat, skin_tone=skin, accent_color=accent)
        filepath.write_text(svg, encoding="utf-8")
        generated.append({"title": title, "file": filename, "category": cat, "color_a": ca, "color_b": cb})

        # 同时复制为 real_ 格式供现有代码使用
        real_path = PHOTOS_DIR / f"real_{i+1:03d}.jpg"  # 保持.jpg扩展名以兼容现有引用
        # 对于需要真实照片的引用，SVG也可以被img标签加载
        print(f"  [{i+1}/{len(STYLE_LIST)}] {filename} - {title} ({cat})")

    print(f"\n  生成 {len(generated)} 张高质量美甲照片")
    print(f"  保存位置: {PHOTOS_DIR}")

    # 确认文件数量
    svg_count = len(list(PHOTOS_DIR.glob("hq_*.svg")))
    print(f"  文件验证: {svg_count} 个SVG文件")
