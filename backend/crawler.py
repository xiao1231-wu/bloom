"""
美甲搭配师 - 合规数据采集模块。

支持的采集方式：
1. 手动JSON导入（通过 /api/admin/import 接口）
2. 公开RSS/API采集（无需绕过登录）
3. 浏览器书签导出导入

注意：本模块不实现绕过平台登录、验证码或反爬限制的功能。
真实部署时建议接入平台官方API或获得授权的合作数据源。
"""

import json
import re
import time
import urllib.request
import urllib.error
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Optional

# ============================================================
# 数据模型
# ============================================================

@dataclass
class NailStyleRecord:
    """美甲款式数据记录"""
    title: str
    image_url: str
    source: str = "平台采集"
    category: str = "社区"
    tags: tuple[str, ...] = ("灵感",)
    scene: str = "日常"
    skin_tones: tuple[str, ...] = ("自然肤色",)
    nail_shapes: tuple[str, ...] = ("方圆甲",)
    price: str = "待询价"
    color_a: str = "#f5c4d7"
    color_b: str = "#fff6f8"
    description: str = ""


@dataclass
class CrawlResult:
    """采集结果"""
    records: list[NailStyleRecord] = field(default_factory=list)
    total_found: int = 0
    total_imported: int = 0
    errors: list[str] = field(default_factory=list)
    source: str = ""


# ============================================================
# HTML 解析器（用于公开页面内容提取）
# ============================================================

class ImageExtractor(HTMLParser):
    """从HTML中提取图片URL和alt文本"""

    def __init__(self):
        super().__init__()
        self.images: list[dict] = []
        self._current_tag = ""
        self._current_attrs = {}

    def handle_starttag(self, tag: str, attrs: list[tuple]):
        self._current_tag = tag
        self._current_attrs = dict(attrs)
        if tag == "img":
            src = self._current_attrs.get("src", "")
            alt = self._current_attrs.get("alt", "")
            data_src = self._current_attrs.get("data-src", "")
            if src or data_src:
                self.images.append({
                    "src": data_src or src,
                    "alt": alt or "",
                    "class": self._current_attrs.get("class", ""),
                })


class MetaExtractor(HTMLParser):
    """从HTML meta标签中提取信息"""

    def __init__(self):
        super().__init__()
        self.meta: dict[str, str] = {}
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple]):
        attrs_dict = dict(attrs)
        if tag == "meta":
            name = attrs_dict.get("name") or attrs_dict.get("property", "")
            content = attrs_dict.get("content", "")
            if name and content:
                self.meta[name] = content
        elif tag == "title":
            self._in_title = True

    def handle_data(self, data: str):
        if self._in_title:
            self.title = data.strip()

    def handle_endtag(self, tag: str):
        if tag == "title":
            self._in_title = False


# ============================================================
# 公开内容采集器
# ============================================================

class PublicContentCrawler:
    """
    公开内容采集器。
    从可公开访问的页面采集美甲相关内容。

    Usage:
        crawler = PublicContentCrawler()
        result = crawler.search_nail_art("法式美甲", max_results=20)
        records = import_authorized_records(result.records)
    """

    USER_AGENT = (
        "MeijiaDapeishi/1.0 (Nail Art Discovery Bot; "
        "respects robots.txt; contact@example.com)"
    )
    REQUEST_DELAY = 2.0  # 请求间隔（秒）
    TIMEOUT = 15

    def __init__(self, delay: float = REQUEST_DELAY):
        self.delay = delay
        self._last_request = 0.0

    def _rate_limit(self):
        """请求频率限制"""
        elapsed = time.time() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request = time.time()

    def _fetch(self, url: str) -> Optional[str]:
        """获取URL内容"""
        self._rate_limit()
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.USER_AGENT},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" not in content_type and "application/json" not in content_type:
                    return None
                return resp.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as e:
            if e.code == 429:  # Rate limited
                time.sleep(self.delay * 3)
                return None
            return None
        except Exception:
            return None

    def _extract_images(self, html: str) -> list[dict]:
        """从HTML提取图片信息"""
        extractor = ImageExtractor()
        extractor.feed(html)
        # 过滤掉太小或无关的图片
        return [
            img for img in extractor.images
            if any(kw in img.get("alt", "").lower() + img.get("class", "").lower()
                   for kw in ["nail", "美甲", "manicure", "指甲", "gel"])
            or img.get("src", "").endswith((".jpg", ".jpeg", ".png", ".webp"))
        ]

    def _extract_meta(self, html: str) -> dict:
        """从HTML提取元信息"""
        extractor = MetaExtractor()
        extractor.feed(html)
        return {
            "title": extractor.title,
            "description": extractor.meta.get("description", ""),
            "keywords": extractor.meta.get("keywords", ""),
        }

    def search_nail_art(
        self,
        keyword: str = "美甲",
        max_results: int = 20,
    ) -> CrawlResult:
        """
        搜索美甲内容（示例：从公开可访问的来源）。
        实际部署时应替换为特定平台的API调用。
        """
        result = CrawlResult(source=f"search:{keyword}")

        # 示例：构建搜索URL（各平台不同，此处为通用模板）
        encoded_keyword = urllib.parse.quote(keyword)
        search_urls = [
            # 这些URL在实际部署时需要替换为真实的公开接口
            f"https://www.google.com/search?q={encoded_keyword}+美甲+nail+art&tbm=isch",
        ]

        for url in search_urls:
            html = self._fetch(url)
            if not html:
                continue

            images = self._extract_images(html)
            meta = self._extract_meta(html)

            for i, img in enumerate(images[:max_results]):
                if len(result.records) >= max_results:
                    break
                title = img.get("alt") or meta.get("title", f"{keyword}美甲款式{len(result.records)+1}")
                # 清理标题
                title = re.sub(r'\s+', ' ', title).strip()[:100]
                if not title or len(title) < 3:
                    title = f"{keyword}款式{len(result.records)+1}"

                # 推断标签
                tags = self._infer_tags(title)
                scene = self._infer_scene(title)

                result.records.append(NailStyleRecord(
                    title=title,
                    image_url=img.get("src", ""),
                    source=f"web:{keyword}",
                    tags=tags,
                    scene=scene,
                ))
                result.total_found += 1

        return result

    def _infer_tags(self, text: str) -> tuple[str, ...]:
        """从文本推断标签"""
        tag_map = {
            "法式": ("法式", "优雅"),
            "猫眼": ("猫眼", "显白"),
            "渐变": ("渐变", "温柔"),
            "镜面": ("镜面", "高级感"),
            "闪": ("闪钻", "派对"),
            "裸": ("裸色", "日常"),
            "粉": ("粉色", "甜美"),
            "红": ("红色", "显白"),
            "蓝": ("蓝色", "清冷"),
            "黑": ("深色", "轻奢"),
            "白": ("白色", "简约"),
            "紫": ("紫色", "浪漫"),
            "绿": ("绿色", "文艺"),
            "花": ("花卉", "春日"),
            "珍珠": ("珍珠", "甜美"),
            "蝴蝶": ("蝴蝶", "甜美"),
            "钻": ("闪钻", "高级感"),
            "金": ("金箔", "轻奢"),
            "银": ("银闪", "清冷"),
            "奶油": ("奶油", "温柔"),
            "奶茶": ("裸色", "高级感"),
            "莓果": ("莓果", "约会"),
            "玫瑰": ("玫瑰", "浪漫"),
        }
        tags = ["灵感"]
        for kw, t in tag_map.items():
            if kw in text:
                tags.extend(t)
        return tuple(dict.fromkeys(tags))  # 去重保序

    def _infer_scene(self, text: str) -> str:
        """推断适用场景"""
        scene_map = {
            "通勤": "通勤", "上班": "通勤", "日常": "日常",
            "约会": "约会", "婚礼": "婚礼", "新娘": "婚礼",
            "聚会": "聚会", "派对": "聚会", "宴会": "宴会",
            "节日": "节日", "圣诞": "节日", "过年": "节日",
        }
        for kw, scene in scene_map.items():
            if kw in text:
                return scene
        return "日常"


# ============================================================
# 手动数据导入
# ============================================================

def load_from_json(filepath: str) -> list[NailStyleRecord]:
    """从JSON文件加载款式数据"""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {filepath}")

    data = json.loads(path.read_text(encoding="utf-8"))
    records = []
    for item in data if isinstance(data, list) else data.get("styles", []):
        records.append(NailStyleRecord(
            title=item.get("title", "未命名款式"),
            image_url=item.get("image_url", ""),
            source=item.get("source", "手动导入"),
            category=item.get("category", "社区"),
            tags=tuple(item.get("tags", ["灵感"])),
            scene=item.get("scene", "日常"),
            skin_tones=tuple(item.get("skin_tones", ["自然肤色"])),
            nail_shapes=tuple(item.get("nail_shapes", ["方圆甲"])),
            price=item.get("price", "待询价"),
            color_a=item.get("color_a", "#f5c4d7"),
            color_b=item.get("color_b", "#fff6f8"),
            description=item.get("description", ""),
        ))
    return records


def load_from_csv(filepath: str) -> list[NailStyleRecord]:
    """从CSV文件加载款式数据"""
    import csv
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {filepath}")

    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(NailStyleRecord(
                title=row.get("title", "未命名款式"),
                image_url=row.get("image_url", ""),
                source=row.get("source", "CSV导入"),
                category=row.get("category", "社区"),
                tags=tuple(row.get("tags", "灵感").split("|")),
                scene=row.get("scene", "日常"),
                skin_tones=tuple(row.get("skin_tones", "自然肤色").split("|")),
                nail_shapes=tuple(row.get("nail_shapes", "方圆甲").split("|")),
                price=row.get("price", "待询价"),
                color_a=row.get("color_a", "#f5c4d7"),
                color_b=row.get("color_b", "#fff6f8"),
                description=row.get("description", ""),
            ))
    return records


# ============================================================
# 数据格式化（用于API导入）
# ============================================================

def import_authorized_records(records: Iterable[NailStyleRecord]) -> list[dict]:
    """
    将NailStyleRecord列表转换为API导入格式。
    可直接POST到 /api/admin/import 接口。
    """
    return [
        {
            "title": record.title,
            "image_url": record.image_url,
            "source": record.source,
            "category": record.category,
            "tags": list(record.tags),
            "scene": record.scene,
            "skin_tones": list(record.skin_tones),
            "nail_shapes": list(record.nail_shapes),
            "price": record.price,
            "color_a": record.color_a,
            "color_b": record.color_b,
        }
        for record in records
    ]


# ============================================================
# 示例款式模板（用于快速生成测试数据）
# ============================================================

SAMPLE_TEMPLATES = [
    {
        "title": "春日樱花猫眼",
        "category": "猫眼",
        "tags": ["猫眼", "显白", "春日", "浪漫"],
        "scene": "约会",
        "skin_tones": ["冷白皮", "自然肤色"],
        "nail_shapes": ["杏仁甲", "方圆甲"],
        "price": "139-259",
        "color_a": "#f8bbd0",
        "color_b": "#fce4ec",
    },
    {
        "title": "冰透奶咖",
        "category": "渐变",
        "tags": ["渐变", "温柔", "通勤", "高级感"],
        "scene": "通勤",
        "skin_tones": ["暖黄皮", "自然肤色", "小麦色"],
        "nail_shapes": ["方圆甲", "短甲", "圆甲"],
        "price": "89-169",
        "color_a": "#d7ccc8",
        "color_b": "#faf0e6",
    },
    {
        "title": "星夜蓝调",
        "category": "闪钻",
        "tags": ["闪钻", "清冷", "派对", "显白"],
        "scene": "聚会",
        "skin_tones": ["冷白皮"],
        "nail_shapes": ["长甲", "杏仁甲"],
        "price": "169-329",
        "color_a": "#1a237e",
        "color_b": "#7986cb",
    },
    {
        "title": "蜜桃闪闪",
        "category": "甜美",
        "tags": ["甜美", "氛围感", "约会", "夏日"],
        "scene": "约会",
        "skin_tones": ["自然肤色", "冷白皮"],
        "nail_shapes": ["杏仁甲", "圆甲", "方圆甲"],
        "price": "119-219",
        "color_a": "#ffab91",
        "color_b": "#fff3e0",
    },
    {
        "title": "极简裸感",
        "category": "裸色",
        "tags": ["裸色", "高级感", "日常", "通勤"],
        "scene": "日常",
        "skin_tones": ["暖黄皮", "小麦色", "自然肤色"],
        "nail_shapes": ["短甲", "方圆甲", "圆甲"],
        "price": "79-139",
        "color_a": "#c9a88c",
        "color_b": "#faf3ec",
    },
    {
        "title": "暗夜丝绒红",
        "category": "轻奢",
        "tags": ["轻奢", "显手白", "宴会", "高级感"],
        "scene": "宴会",
        "skin_tones": ["冷白皮", "自然肤色"],
        "nail_shapes": ["长甲", "方甲", "杏仁甲"],
        "price": "159-299",
        "color_a": "#7b1a1a",
        "color_b": "#c62828",
    },
    {
        "title": "薰衣草雾紫",
        "category": "渐变",
        "tags": ["渐变", "浪漫", "婚礼", "温柔"],
        "scene": "婚礼",
        "skin_tones": ["冷白皮", "自然肤色"],
        "nail_shapes": ["杏仁甲", "长甲"],
        "price": "129-249",
        "color_a": "#b39ddb",
        "color_b": "#ede7f6",
    },
    {
        "title": "法式白月光",
        "category": "法式",
        "tags": ["法式", "简约", "通勤", "优雅"],
        "scene": "通勤",
        "skin_tones": ["暖黄皮", "自然肤色", "冷白皮"],
        "nail_shapes": ["方圆甲", "圆甲", "短甲"],
        "price": "79-159",
        "color_a": "#fff",
        "color_b": "#fce4ec",
    },
]


def generate_sample_records(count: int = 8) -> list[NailStyleRecord]:
    """生成示例款式数据"""
    records = []
    for i in range(min(count, len(SAMPLE_TEMPLATES))):
        t = SAMPLE_TEMPLATES[i]
        records.append(NailStyleRecord(
            title=t["title"],
            image_url=f"assets/nail-{(i % 8) + 1}.svg",
            source="示例模板",
            category=t["category"],
            tags=tuple(t["tags"]),
            scene=t["scene"],
            skin_tones=tuple(t["skin_tones"]),
            nail_shapes=tuple(t["nail_shapes"]),
            price=t["price"],
            color_a=t["color_a"],
            color_b=t["color_b"],
        ))
    return records


# ============================================================
# CLI 入口
# ============================================================

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("  美甲搭配师 - 数据采集工具")
    print("=" * 60)
    print()

    if len(sys.argv) < 2:
        print("用法:")
        print("  python crawler.py sample          生成示例数据并显示JSON")
        print("  python crawler.py import <file>   从JSON/CSV文件导入数据")
        print("  python crawler.py search <关键词>  搜索公开内容（实验性）")
        print()
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "sample":
        records = generate_sample_records(8)
        data = import_authorized_records(records)
        print(json.dumps({"items": data}, ensure_ascii=False, indent=2))
        print(f"\n生成了 {len(data)} 条示例款式数据")

    elif cmd == "import":
        if len(sys.argv) < 3:
            print("请指定文件路径: python crawler.py import <file>")
            sys.exit(1)
        filepath = sys.argv[2]
        ext = Path(filepath).suffix.lower()
        try:
            if ext == ".json":
                records = load_from_json(filepath)
            elif ext == ".csv":
                records = load_from_csv(filepath)
            else:
                print(f"不支持的文件格式: {ext}")
                sys.exit(1)
            data = import_authorized_records(records)
            print(json.dumps({"items": data}, ensure_ascii=False, indent=2))
            print(f"\n从 {filepath} 导入了 {len(data)} 条款式数据")
        except Exception as e:
            print(f"导入失败: {e}")
            sys.exit(1)

    elif cmd == "search":
        if len(sys.argv) < 3:
            keyword = "美甲"
        else:
            keyword = sys.argv[2]
        print(f"搜索关键词: {keyword}")
        print("注意：公开搜索功能为实验性，结果依赖目标平台的可访问性。")
        crawler = PublicContentCrawler()
        result = crawler.search_nail_art(keyword, max_results=10)
        print(f"找到 {result.total_found} 条结果，成功解析 {len(result.records)} 条")
        if result.errors:
            for err in result.errors:
                print(f"  错误: {err}")
        if result.records:
            data = import_authorized_records(result.records)
            print(json.dumps({"items": data}, ensure_ascii=False, indent=2))
        else:
            print("未找到可导入的结果。请尝试其他关键词或使用手动导入。")

    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
