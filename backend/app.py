import base64
import hashlib
import json
import mimetypes
import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from avatar_storage import AvatarStorageError, create_avatar_storage
from nail_knowledge import KNOWLEDGE_VERSION, build_plan, match_style, normalize_profile, style_knowledge

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
DB_PATH = Path(os.environ.get("DATABASE_PATH", Path(__file__).resolve().parent / "meijia.db")).expanduser().resolve()
PORT = int(os.environ.get("PORT", "8080"))
UPLOADS = Path(os.environ.get("MEDIA_ROOT", FRONTEND / "uploads")).expanduser().resolve()
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*").strip() or "*"
MAX_REQUEST_BYTES = 8 * 1024 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024
SESSION_DAYS = 30
_avatar_storage = None


def avatar_storage():
    global _avatar_storage
    if _avatar_storage is None:
        _avatar_storage = create_avatar_storage(UPLOADS)
    return _avatar_storage


def avatar_url(avatar_key):
    return avatar_storage().public_url(avatar_key or "")

def load_comprehensive_styles():
    """从JSON文件加载全面款式数据（包含真实照片引用）"""
    import json as j
    style_file = ROOT / "frontend" / "assets" / "comprehensive_styles.json"
    if style_file.exists():
        data = j.loads(style_file.read_text(encoding="utf-8"))
        styles = []
        for item in data.get("items", []):
            styles.append((
                item["title"], item["category"], ",".join(item["tags"]), item["scene"],
                ",".join(item["skin_tones"]), ",".join(item["nail_shapes"]), item["price"],
                item.get("image_url", "assets/photos/real_001.jpg"),
                item["color_a"], item["color_b"],
                item.get("skin_brightness", 3), item.get("hand_shape_fit", 3),
                item.get("daily_convenience", 3), item.get("maintenance_ease", 3),
                item.get("style_match", 3), item.get("gender_suitability", "all"),
            ))
        return styles
    return []


def load_community_posts():
    seed_file = FRONTEND / "assets" / "community" / "community_posts.json"
    if not seed_file.exists():
        return []
    try:
        payload = json.loads(seed_file.read_text(encoding="utf-8"))
        return payload.get("items", []) if isinstance(payload, dict) else []
    except (OSError, json.JSONDecodeError):
        return []


COMMUNITY_SEED = load_community_posts()

CURATED_STYLE_IMAGE_TITLES = {
    "经典白法式",
    "彩色法式边",
    "V形法式",
    "双色法式",
}

STYLE_SEED = load_comprehensive_styles() or [
    # 兜底：如果JSON文件不存在，使用基础款式
    ("樱粉奶油法式", "法式", "短甲友好,温柔,通勤", "通勤", "暖黄皮,自然肤色", "圆甲,方圆甲", "79-159", "assets/photos/real_001.jpg", "#f9c8d8", "#fff5f7", 4, 3, 5, 4, 4, "female"),
    ("玫瑰猫眼", "猫眼", "显白,高级感,约会", "约会", "冷白皮,自然肤色", "杏仁甲,方圆甲", "129-239", "assets/photos/photo_002.svg", "#c95a88", "#f5c2d8", 5, 5, 3, 3, 5),
    ("奶茶裸粉", "裸色", "高级感,日常,通勤", "日常", "暖黄皮,小麦色", "短甲,方圆甲", "89-169", "assets/photos/photo_003.svg", "#c58f82", "#f5ded5", 3, 3, 5, 5, 3),
    ("莓果镜面", "镜面", "甜酷,聚会,显白", "聚会", "冷白皮,自然肤色", "长甲,杏仁甲", "139-269", "assets/photos/photo_004.svg", "#8c2758", "#f2aec7", 5, 4, 2, 2, 4),
    ("珍珠蝴蝶结", "甜美", "氛围感,约会,浪漫", "约会", "冷白皮,自然肤色", "杏仁甲,长甲", "149-289", "assets/photos/photo_005.svg", "#f6cadc", "#ffffff", 4, 5, 2, 2, 5),
    ("微醺渐变", "渐变", "温柔,婚礼,浪漫", "婚礼", "自然肤色,暖黄皮", "方圆甲,杏仁甲", "119-219", "assets/photos/photo_006.svg", "#e9a8bb", "#fff7f8", 4, 4, 3, 3, 4),
    ("黑樱茶歇", "轻奢", "显手白,宴会,高级感", "宴会", "冷白皮,自然肤色", "长甲,方甲", "159-299", "assets/photos/photo_007.svg", "#352031", "#c490a5", 5, 4, 2, 2, 5),
    ("蓝莓星闪", "闪钻", "清冷,节日,显白", "节日", "冷白皮", "杏仁甲,长甲", "169-319", "assets/photos/photo_008.svg", "#8f9fe5", "#e9edff", 5, 5, 2, 2, 5),
    # 扩展款式（42款，覆盖更多风格和场景）
    ("蜜桃乌龙", "渐变", "温柔,日常,显白", "日常", "暖黄皮,自然肤色", "圆甲,方圆甲,短甲", "89-169", "assets/photos/photo_001.svg", "#ffab91", "#ffe0b2", 4, 3, 5, 4, 3),
    ("星空紫罗兰", "闪钻", "清冷,节日,高级感", "聚会", "冷白皮,自然肤色", "长甲,杏仁甲", "159-289", "assets/photos/photo_008.svg", "#7c4dff", "#b388ff", 5, 4, 2, 2, 5),
    ("奶油杏子", "裸色", "高级感,通勤,低调", "日常", "暖黄皮,自然肤色,小麦色", "短甲,方圆甲", "79-149", "assets/photos/photo_003.svg", "#d7ccc8", "#faf0e6", 2, 3, 5, 5, 2),
    ("粉雾海盐", "渐变", "温柔,约会,浪漫", "约会", "冷白皮,自然肤色", "杏仁甲,方圆甲", "109-199", "assets/photos/photo_006.svg", "#ce93d8", "#f3e5f5", 4, 4, 3, 3, 4),
    ("摩卡拿铁", "纯色", "高级感,通勤,显白", "通勤", "暖黄皮,小麦色", "短甲,方圆甲,圆甲", "69-129", "assets/photos/photo_003.svg", "#8d6e63", "#d7ccc8", 3, 3, 5, 5, 2),
    ("金箔琥珀", "轻奢", "显手白,宴会,贵气", "宴会", "暖黄皮,自然肤色", "长甲,杏仁甲", "179-329", "assets/photos/photo_007.svg", "#ff8f00", "#ffcc80", 4, 4, 2, 2, 4),
    ("薰衣草梦境", "渐变", "浪漫,婚礼,清冷", "婚礼", "冷白皮", "杏仁甲,长甲", "139-259", "assets/photos/photo_006.svg", "#b39ddb", "#ede7f6", 4, 5, 2, 2, 5),
    ("莓果奶昔", "纯色", "甜酷,约会,显白", "约会", "冷白皮,自然肤色", "方圆甲,短甲", "89-159", "assets/photos/photo_004.svg", "#e91e63", "#f48fb1", 5, 4, 3, 3, 4),
    ("抹茶慕斯", "纯色", "低调,日常,文艺", "日常", "暖黄皮,自然肤色", "方圆甲,短甲", "69-129", "assets/photos/photo_001.svg", "#81c784", "#c8e6c9", 2, 3, 4, 4, 2),
    ("橙花气泡", "法式", "活力,聚会,夏日", "聚会", "自然肤色,暖黄皮", "圆甲,方圆甲", "89-169", "assets/photos/photo_001.svg", "#ff7043", "#ffe0b2", 3, 3, 3, 3, 3),
    ("银河碎钻", "闪钻", "清冷,节日,派对", "节日", "冷白皮", "长甲,杏仁甲", "189-349", "assets/photos/photo_008.svg", "#263238", "#546e7a", 5, 5, 1, 1, 5),
    ("焦糖布丁", "纯色", "温柔,通勤,秋日", "通勤", "暖黄皮,小麦色,自然肤色", "方圆甲,短甲", "79-139", "assets/photos/photo_003.svg", "#bf8040", "#e6c9a8", 3, 3, 4, 4, 3),
    ("樱花马卡龙", "甜美", "氛围感,约会,春日", "约会", "冷白皮,自然肤色", "圆甲,方圆甲,短甲", "99-189", "assets/photos/photo_005.svg", "#f8bbd0", "#fce4ec", 4, 4, 3, 3, 5),
    ("大理石灰", "轻奢", "高级感,通勤,低调", "通勤", "冷白皮,自然肤色", "方甲,杏仁甲,长甲", "129-239", "assets/photos/photo_007.svg", "#90a4ae", "#cfd8dc", 3, 4, 4, 3, 3),
    ("珊瑚橘粉", "纯色", "活力,夏日,显白", "日常", "自然肤色,暖黄皮", "方圆甲,短甲", "79-149", "assets/photos/photo_001.svg", "#ff6e6e", "#ffab91", 4, 3, 4, 4, 3),
    ("暗夜丝绒", "镜面", "甜酷,宴会,高级感", "宴会", "冷白皮", "长甲,方甲", "169-319", "assets/photos/photo_004.svg", "#4a148c", "#9c27b0", 5, 4, 1, 1, 5),
    ("香槟玫瑰", "渐变", "婚礼,约会,浪漫", "婚礼", "自然肤色,暖黄皮", "杏仁甲,长甲", "139-259", "assets/photos/photo_006.svg", "#d4a574", "#f5e1d5", 3, 4, 2, 2, 4),
    ("薄荷冰沙", "纯色", "清冷,夏日,文艺", "日常", "冷白皮,自然肤色", "短甲,方圆甲", "69-129", "assets/photos/photo_001.svg", "#4db6ac", "#b2dfdb", 3, 3, 4, 4, 3),
    ("干枯玫瑰", "纯色", "温柔,通勤,高级感", "通勤", "暖黄皮,自然肤色,小麦色", "方圆甲,杏仁甲", "89-159", "assets/photos/photo_003.svg", "#bc8f8f", "#e8c4b8", 4, 4, 4, 4, 3),
    ("极光白", "镜面", "清冷,节日,高级感", "节日", "冷白皮", "长甲,杏仁甲", "159-299", "assets/photos/photo_004.svg", "#e0e0e0", "#fafafa", 5, 5, 2, 2, 5),
    ("草莓奶霜", "甜美", "氛围感,约会,春日", "约会", "冷白皮,自然肤色", "圆甲,杏仁甲", "109-199", "assets/photos/photo_005.svg", "#ef5350", "#ffcdd2", 5, 4, 3, 3, 5),
    ("肉桂奶茶", "裸色", "高级感,通勤,秋日", "日常", "暖黄皮,小麦色", "短甲,方圆甲", "79-139", "assets/photos/photo_003.svg", "#a1887f", "#d7ccc8", 2, 3, 5, 5, 2),
    ("紫藤花语", "渐变", "浪漫,春日,约会", "约会", "冷白皮,自然肤色", "杏仁甲,长甲", "129-239", "assets/photos/photo_006.svg", "#9575cd", "#d1c4e9", 4, 4, 2, 2, 4),
    ("海盐焦糖", "纯色", "温柔,通勤,高级感", "通勤", "暖黄皮,自然肤色", "方圆甲,杏仁甲", "89-159", "assets/photos/photo_001.svg", "#8d6e63", "#c9a88c", 3, 3, 5, 4, 3),
    ("烟熏玫瑰", "轻奢", "显白,宴会,高级感", "宴会", "冷白皮,自然肤色", "长甲,方甲", "149-279", "assets/photos/photo_007.svg", "#5d2e46", "#9e5c76", 5, 4, 2, 2, 4),
    ("蜜糖粉晶", "闪钻", "甜美,约会,浪漫", "约会", "冷白皮,自然肤色", "杏仁甲,长甲", "139-269", "assets/photos/photo_008.svg", "#ff80ab", "#fce4ec", 5, 4, 2, 2, 5),
    ("可可摩卡", "纯色", "通勤,低调,秋日", "通勤", "暖黄皮,小麦色,自然肤色", "短甲,方圆甲", "69-119", "assets/photos/photo_003.svg", "#6d4c41", "#bcaaa4", 2, 2, 5, 5, 2),
    ("极光紫", "猫眼", "清冷,节日,高级感", "节日", "冷白皮", "长甲,杏仁甲", "169-319", "assets/photos/photo_002.svg", "#673ab7", "#ce93d8", 5, 5, 1, 1, 5),
    ("奶茶豆沙", "纯色", "温柔,通勤,日常", "日常", "暖黄皮,自然肤色,小麦色", "方圆甲,短甲,圆甲", "79-139", "assets/photos/photo_003.svg", "#c59b8a", "#e8c4b8", 3, 4, 5, 5, 3),
    ("雾蓝梦境", "渐变", "清冷,文艺,日常", "日常", "冷白皮,自然肤色", "方圆甲,杏仁甲", "99-189", "assets/photos/photo_006.svg", "#5c6bc0", "#c5cae9", 4, 4, 3, 3, 4),
    ("蜜桔汽水", "纯色", "活力,夏日,聚会", "聚会", "自然肤色,暖黄皮", "圆甲,短甲", "69-129", "assets/photos/photo_001.svg", "#ff8a65", "#ffccbc", 3, 3, 3, 3, 3),
    ("丝绒红酒", "纯色", "显白,宴会,高级感", "宴会", "冷白皮,自然肤色", "长甲,方甲,杏仁甲", "119-219", "assets/photos/photo_004.svg", "#8e0000", "#c62828", 5, 4, 1, 1, 4),
    ("杏仁奶油", "裸色", "高级感,通勤,日常", "日常", "暖黄皮,自然肤色", "短甲,方圆甲", "69-129", "assets/photos/photo_003.svg", "#e6d5c3", "#faf3ec", 2, 2, 5, 5, 2),
    ("甜橙气泡", "法式", "活力,夏日,约会", "约会", "自然肤色,暖黄皮", "方圆甲,圆甲", "89-169", "assets/photos/photo_001.svg", "#ff9800", "#ffe0b2", 3, 3, 3, 3, 3),
    ("极夜星空", "闪钻", "清冷,派对,节日", "节日", "冷白皮", "长甲,杏仁甲", "189-359", "assets/photos/photo_008.svg", "#0d1b2a", "#1b3a5c", 5, 5, 1, 1, 5),
    ("蔷薇粉晶", "甜美", "氛围感,约会,春日", "约会", "冷白皮,自然肤色", "杏仁甲,圆甲", "109-199", "assets/photos/photo_005.svg", "#f48fb1", "#fce4ec", 5, 4, 3, 3, 5),
    ("冰岛迷雾", "渐变", "清冷,文艺,通勤", "通勤", "冷白皮,自然肤色", "方圆甲,杏仁甲", "99-189", "assets/photos/photo_006.svg", "#78909c", "#cfd8dc", 3, 3, 4, 4, 3),
    ("枫糖浆果", "纯色", "显白,秋日,约会", "约会", "暖黄皮,自然肤色", "方圆甲,杏仁甲", "99-179", "assets/photos/photo_004.svg", "#8b2252", "#d45d79", 5, 4, 3, 3, 4),
    ("月光贝壳", "镜面", "清冷,高级感,约会", "约会", "冷白皮,自然肤色", "杏仁甲,长甲", "139-259", "assets/photos/photo_004.svg", "#f8e8e0", "#fce4ec", 4, 5, 2, 2, 5),
    ("燕麦拿铁", "裸色", "通勤,低调,日常", "日常", "暖黄皮,小麦色,自然肤色", "短甲,方圆甲", "69-119", "assets/photos/photo_003.svg", "#bfa08a", "#e6d5c3", 2, 2, 5, 5, 2),
    ("荧光珊瑚", "纯色", "活力,夏日,派对", "聚会", "自然肤色,小麦色", "短甲,圆甲", "79-149", "assets/photos/photo_001.svg", "#ff5252", "#ff8a80", 4, 2, 3, 3, 2),
    ("紫水晶", "猫眼", "清冷,高级感,宴会", "宴会", "冷白皮", "长甲,杏仁甲", "159-299", "assets/photos/photo_002.svg", "#6a1b9a", "#ab47bc", 5, 5, 1, 1, 5),
    ("暖茶拿铁", "裸色", "温柔,通勤,日常", "日常", "暖黄皮,小麦色", "短甲,方圆甲,圆甲", "69-119", "assets/photos/photo_003.svg", "#a67c6d", "#dfc5b8", 2, 3, 5, 5, 2),
    ("碎冰蓝", "渐变", "清冷,夏日,文艺", "日常", "冷白皮,自然肤色", "方圆甲,杏仁甲", "99-189", "assets/photos/photo_006.svg", "#4fc3f7", "#b3e5fc", 4, 3, 4, 4, 3),
    ("暗红丝绒", "轻奢", "显白,宴会,贵气", "宴会", "冷白皮,自然肤色", "长甲,方甲", "169-319", "assets/photos/photo_007.svg", "#7b1a1a", "#b71c1c", 5, 4, 1, 1, 4),
    ("桃气满满", "甜美", "活力,约会,夏日", "约会", "自然肤色,冷白皮", "圆甲,杏仁甲,短甲", "89-169", "assets/photos/photo_005.svg", "#ff6b8a", "#ffcdd2", 4, 4, 3, 3, 4),
    ("祖母绿", "纯色", "高级感,宴会,贵气", "宴会", "冷白皮", "长甲,方甲", "149-279", "assets/photos/photo_007.svg", "#1b5e20", "#4caf50", 4, 4, 1, 1, 4),
    ("暖阳金桔", "纯色", "活力,夏日,日常", "日常", "暖黄皮,自然肤色", "短甲,方圆甲", "69-129", "assets/photos/photo_001.svg", "#ffa726", "#ffe0b2", 3, 2, 4, 4, 2),
    ("伯爵玫瑰", "轻奢", "显白,高级感,约会", "约会", "冷白皮,自然肤色", "长甲,杏仁甲,方甲", "139-259", "assets/photos/photo_007.svg", "#8c3a5a", "#c96d8a", 5, 5, 2, 2, 5),
    ("冰透粉", "渐变", "温柔,通勤,日常", "日常", "冷白皮,自然肤色,暖黄皮", "方圆甲,短甲,圆甲", "79-149", "assets/photos/photo_006.svg", "#ffcdd2", "#fff", 4, 3, 5, 5, 4),
]


def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            gender TEXT DEFAULT 'female',
            profile_json TEXT DEFAULT '{}',
            avatar_key TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
        CREATE TABLE IF NOT EXISTS styles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            tags TEXT NOT NULL,
            scene TEXT NOT NULL,
            skin_tones TEXT NOT NULL,
            nail_shapes TEXT NOT NULL,
            price TEXT NOT NULL,
            image_url TEXT NOT NULL,
            color_a TEXT NOT NULL,
            color_b TEXT NOT NULL,
            skin_brightness INTEGER DEFAULT 3,
            hand_shape_fit INTEGER DEFAULT 3,
            daily_convenience INTEGER DEFAULT 3,
            maintenance_ease INTEGER DEFAULT 3,
            style_match INTEGER DEFAULT 3,
            gender_suitability TEXT DEFAULT 'all',
            likes INTEGER DEFAULT 0,
            source TEXT DEFAULT '平台款式库',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS stores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            phone TEXT DEFAULT '',
            rating REAL DEFAULT 4.5,
            price_start TEXT DEFAULT '¥99 起',
            lat REAL DEFAULT 0,
            lng REAL DEFAULT 0,
            photos TEXT DEFAULT '[]',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS post_likes (
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (user_id, post_id)
        );
        CREATE TABLE IF NOT EXISTS share_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            target_type TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            platform TEXT DEFAULT 'link',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            body TEXT DEFAULT '',
            image_data TEXT NOT NULL,
            likes INTEGER DEFAULT 0,
            display_name TEXT DEFAULT '',
            category TEXT DEFAULT '??',
            tags TEXT DEFAULT '',
            featured INTEGER DEFAULT 0,
            editorial INTEGER DEFAULT 0,
            source_name TEXT DEFAULT '',
            source_url TEXT DEFAULT '',
            source_license TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER NOT NULL,
            style_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (user_id, style_id)
        );
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            style_id INTEGER NOT NULL,
            store_name TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            note TEXT DEFAULT '',
            status TEXT DEFAULT '待确认',
            created_at TEXT NOT NULL
        );
        """
    )
    user_columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "avatar_key" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN avatar_key TEXT DEFAULT ''")
    post_columns = {row[1] for row in conn.execute("PRAGMA table_info(posts)").fetchall()}
    for column_name, definition in (
        ("display_name", "display_name TEXT DEFAULT ''"),
        ("category", "category TEXT DEFAULT '??'"),
        ("tags", "tags TEXT DEFAULT ''"),
        ("featured", "featured INTEGER DEFAULT 0"),
        ("editorial", "editorial INTEGER DEFAULT 0"),
        ("source_name", "source_name TEXT DEFAULT ''"),
        ("source_url", "source_url TEXT DEFAULT ''"),
        ("source_license", "source_license TEXT DEFAULT ''"),
    ):
        if column_name not in post_columns:
            conn.execute(f"ALTER TABLE posts ADD COLUMN {definition}")
    style_columns = {row[1] for row in conn.execute("PRAGMA table_info(styles)").fetchall()}
    if "knowledge_json" not in style_columns:
        conn.execute("ALTER TABLE styles ADD COLUMN knowledge_json TEXT DEFAULT '{}'")
    if conn.execute("SELECT COUNT(*) FROM styles").fetchone()[0] == 0:
        now = datetime.now().isoformat(timespec="seconds")
        seed = STYLE_SEED
        if seed:
            conn.executemany(
                """INSERT INTO styles
                (title,category,tags,scene,skin_tones,nail_shapes,price,image_url,color_a,color_b,
                 skin_brightness,hand_shape_fit,daily_convenience,maintenance_ease,style_match,gender_suitability,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [(s[0],s[1],s[2],s[3],s[4],s[5],s[6],s[7],s[8],s[9],
                  s[10] if len(s)>10 else 3, s[11] if len(s)>11 else 3,
                  s[12] if len(s)>12 else 3, s[13] if len(s)>13 else 3,
                  s[14] if len(s)>14 else 3, s[15] if len(s)>15 else "all",
                  now) for s in seed],
            )
    curated_style_images = [
        (style[7], style[0])
        for style in STYLE_SEED
        if style[0] in CURATED_STYLE_IMAGE_TITLES
    ]
    if curated_style_images:
        conn.executemany(
            "UPDATE styles SET image_url=? WHERE title=?",
            curated_style_images,
        )
    for row in conn.execute("SELECT * FROM styles").fetchall():
        knowledge = style_knowledge(dict(row))
        encoded = json.dumps(knowledge, ensure_ascii=False, sort_keys=True)
        if row["knowledge_json"] != encoded:
            conn.execute("UPDATE styles SET knowledge_json=? WHERE id=?", (encoded, row["id"]))
    if conn.execute("SELECT COUNT(*) FROM stores").fetchone()[0] == 0:
        now = datetime.now().isoformat(timespec="seconds")
        stores_seed = [
            ("花漾美甲·中心店", "北京市朝阳区建国路88号", "北京", "010-88886666", 4.9, "¥99 起", 39.915, 116.465),
            ("Luna Nail Studio", "上海市静安区南京西路1266号", "上海", "021-66668888", 4.8, "¥129 起", 31.232, 121.469),
            ("粉雾美学工作室", "广州市天河区体育西路111号", "广州", "020-33336666", 4.7, "¥89 起", 23.128, 113.327),
            ("樱花美甲社", "杭州市西湖区文三路268号", "杭州", "0571-88889999", 4.6, "¥79 起", 30.265, 120.139),
            ("指尖星辰美甲馆", "成都市锦江区春熙路55号", "成都", "028-77776666", 4.8, "¥109 起", 30.658, 104.074),
            ("蝶舞美甲工坊", "深圳市南山区科技园路22号", "深圳", "0755-55556666", 4.7, "¥99 起", 22.543, 113.956),
        ]
        conn.executemany(
            "INSERT INTO stores(name,address,city,phone,rating,price_start,lat,lng,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            [(a, b, c, d, e, f, g, h, now) for a, b, c, d, e, f, g, h in stores_seed],
        )
    if conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0] == 0 and COMMUNITY_SEED:
        now = datetime.now()
        conn.executemany(
            """INSERT INTO posts
            (user_id,title,body,image_data,likes,display_name,category,tags,featured,editorial,
             source_name,source_url,source_license,created_at)
            VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [(
                str(item.get("title", "Community inspiration"))[:100],
                str(item.get("body", ""))[:2000],
                str(item.get("image_data", ""))[:500],
                max(0, int(item.get("likes", 0))),
                str(item.get("display_name", "Community editor"))[:60],
                str(item.get("category", "Inspiration"))[:30],
                ",".join(str(tag)[:30] for tag in item.get("tags", [])[:8]),
                1 if item.get("featured") else 0,
                1 if item.get("editorial", True) else 0,
                str(item.get("source_name", ""))[:200],
                str(item.get("source_url", ""))[:800],
                str(item.get("source_license", ""))[:100],
                (now - timedelta(hours=index * 11)).isoformat(timespec="seconds"),
            ) for index, item in enumerate(COMMUNITY_SEED)],
        )
    conn.commit()
    conn.close()


def row_json(row):
    if row is None:
        return None
    data = dict(row)
    for key in ("tags", "skin_tones", "nail_shapes"):
        data[key] = [x for x in data.get(key, "").split(",") if x]
    if "knowledge_json" in data:
        try:
            data["knowledge"] = json.loads(data.get("knowledge_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            data["knowledge"] = style_knowledge(data)
        data.pop("knowledge_json", None)
    # 添加评分维度
    for key in ("skin_brightness", "hand_shape_fit", "daily_convenience", "maintenance_ease", "style_match"):
        try:
            data[key] = int(data.get(key, 3))
        except (ValueError, TypeError):
            data[key] = 3
    return data


def user_json(user):
    if user is None:
        return None
    try:
        profile = json.loads(user["profile_json"] or "{}")
    except (TypeError, json.JSONDecodeError):
        profile = {}
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "gender": user["gender"],
        "profile": profile,
        "avatar_url": avatar_url(user["avatar_key"]),
    }


def hash_password(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000).hex()


class APIError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(conn, user_id):
    token = secrets.token_urlsafe(32)
    now = datetime.now()
    conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now.isoformat(timespec="seconds"),))
    conn.execute(
        "INSERT INTO sessions(token_hash,user_id,expires_at,created_at) VALUES (?,?,?,?)",
        (token_hash(token), user_id, (now + timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds"), now.isoformat(timespec="seconds")),
    )
    return token


def save_uploaded_image(data_url):
    if not isinstance(data_url, str) or not data_url.startswith("data:image/"):
        raise APIError("\u8bf7\u4e0a\u4f20\u6709\u6548\u7684\u56fe\u7247", 400)
    try:
        header, encoded = data_url.split(",", 1)
        mime = header[5:].split(";", 1)[0].lower()
        ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(mime)
        if not ext:
            raise APIError("\u4ec5\u652f\u6301 JPG\u3001PNG \u6216 WebP \u56fe\u7247", 415)
        raw = base64.b64decode(encoded, validate=True)
    except APIError:
        raise
    except (ValueError, base64.binascii.Error):
        raise APIError("\u56fe\u7247\u6570\u636e\u65e0\u6cd5\u89e3\u6790", 400)
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise APIError("\u56fe\u7247\u5927\u5c0f\u4e0d\u80fd\u8d85\u8fc7 5MB", 413)
    UPLOADS.mkdir(parents=True, exist_ok=True)
    filename = f"post_{secrets.token_hex(16)}{ext}"
    (UPLOADS / filename).write_bytes(raw)
    return f"/uploads/{filename}"


def remove_uploaded_image(image_url):
    if not isinstance(image_url, str) or not image_url.startswith("/uploads/"):
        return
    candidate = (UPLOADS / Path(image_url).name).resolve()
    if candidate.parent == UPLOADS.resolve() and candidate.exists():
        candidate.unlink()


class Handler(BaseHTTPRequestHandler):
    server_version = "MeijiaDapeishi/1.0"

    def _headers(self, status=200, content_type="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", CORS_ORIGIN)
        if CORS_ORIGIN != "*":
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Admin-Token")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.end_headers()

    def _json(self, payload, status=200):
        self._headers(status)
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise APIError("Invalid Content-Length", 400)
        if length < 0:
            raise APIError("Invalid Content-Length", 400)
        if length > MAX_REQUEST_BYTES:
            raise APIError("\u8bf7\u6c42\u5185\u5bb9\u8fc7\u5927", 413)
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise APIError("\u8bf7\u6c42\u4f53\u5fc5\u987b\u662f\u6709\u6548 JSON", 400)
        if not isinstance(payload, dict):
            raise APIError("\u8bf7\u6c42\u4f53\u5fc5\u987b\u662f JSON \u5bf9\u8c61", 400)
        return payload

    def _bearer_token(self):
        value = self.headers.get("Authorization", "")
        if value.startswith("Bearer "):
            return value[7:].strip()
        return ""

    def _current_user(self, conn):
        token = self._bearer_token()
        if not token:
            return None
        return conn.execute(
            """SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id
            WHERE sessions.token_hash=? AND sessions.expires_at>?""",
            (token_hash(token), datetime.now().isoformat(timespec="seconds")),
        ).fetchone()

    def _require_user(self, conn):
        user = self._current_user(conn)
        if user is None:
            self._json({"error": "\u8bf7\u5148\u767b\u5f55\u6216\u91cd\u65b0\u767b\u5f55"}, 401)
        return user

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self._json({"error": "Not found"}, 404)
            return
        try:
            self.api_delete(parsed.path)
        except APIError as exc:
            self._json({"error": str(exc)}, exc.status)
        except (ValueError, TypeError):
            self._json({"error": "\u8bf7\u6c42\u53c2\u6570\u65e0\u6548"}, 400)
        except sqlite3.Error:
            self._json({"error": "\u6570\u636e\u5e93\u64cd\u4f5c\u5931\u8d25"}, 500)

    def do_OPTIONS(self):
        self._headers(204)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/"):
            try:
                self.api_get(path)
            except APIError as exc:
                self._json({"error": str(exc)}, exc.status)
            except (ValueError, TypeError):
                self._json({"error": "\u8bf7\u6c42\u53c2\u6570\u65e0\u6548"}, 400)
            except sqlite3.Error:
                self._json({"error": "\u6570\u636e\u5e93\u64cd\u4f5c\u5931\u8d25"}, 500)
            return
        self.serve_static(path)

    def do_POST(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self._json({"error": "Not found"}, 404)
            return
        try:
            self.api_post(parsed.path)
        except APIError as exc:
            self._json({"error": str(exc)}, exc.status)
        except (ValueError, TypeError):
            self._json({"error": "\u8bf7\u6c42\u53c2\u6570\u65e0\u6548"}, 400)
        except sqlite3.Error:
            self._json({"error": "\u6570\u636e\u5e93\u64cd\u4f5c\u5931\u8d25"}, 500)

    def api_get(self, path):
        conn = db()
        try:
            query = urlparse(self.path).query
            params = {k: v[0] for k, v in parse_qs(query).items()} if query else {}
            if path == "/api/health":
                conn.execute("SELECT 1").fetchone()
                self._json({"ok": True, "service": "bloom"})
            elif path == "/api/styles":
                gender = params.get("gender", "")
                if gender in ("male", "female"):
                    rows = conn.execute("SELECT * FROM styles WHERE gender_suitability IN (?, 'all') ORDER BY likes DESC,id", (gender,)).fetchall()
                else:
                    rows = conn.execute("SELECT * FROM styles ORDER BY likes DESC,id").fetchall()
                self._json({"styles": [row_json(row) for row in rows]})
            elif path == "/api/stores":
                rows = conn.execute("SELECT * FROM stores ORDER BY rating DESC").fetchall()
                self._json({"stores": [dict(row) for row in rows]})
            elif path == "/api/community/posts":
                rows = conn.execute("""SELECT posts.*,COALESCE(NULLIF(posts.display_name,''),users.name,'\u642d\u914d\u5e08\u7528\u6237') user_name,
                    users.avatar_key user_avatar_key
                    FROM posts LEFT JOIN users ON users.id=posts.user_id ORDER BY posts.featured DESC,posts.id DESC""").fetchall()
                posts = []
                for row in rows:
                    item = dict(row)
                    item["user_avatar_url"] = avatar_url(item.pop("user_avatar_key", ""))
                    item["tags"] = [tag for tag in (item.get("tags") or "").split(",") if tag]
                    item["featured"] = bool(item.get("featured"))
                    item["editorial"] = bool(item.get("editorial"))
                    item["comment_count"] = conn.execute("SELECT COUNT(*) FROM comments WHERE post_id=?", (row["id"],)).fetchone()[0]
                    posts.append(item)
                self._json({"posts": posts})
            elif path.startswith("/api/community/posts/") and path.endswith("/comments"):
                post_id = int(path.split("/")[4])
                rows = conn.execute("""SELECT comments.*,COALESCE(users.name,'\u642d\u914d\u5e08\u7528\u6237') user_name,
                    users.avatar_key user_avatar_key
                    FROM comments LEFT JOIN users ON users.id=comments.user_id
                    WHERE comments.post_id=? ORDER BY comments.id""", (post_id,)).fetchall()
                comments = []
                for row in rows:
                    item = dict(row)
                    item["user_avatar_url"] = avatar_url(item.pop("user_avatar_key", ""))
                    comments.append(item)
                self._json({"comments": comments})
            elif path.startswith("/api/users/") and path.endswith("/favorites"):
                requested_id = int(path.split("/")[3])
                user = self._require_user(conn)
                if user is None:
                    return
                if requested_id != user["id"]:
                    self._json({"error": "Forbidden"}, 403)
                    return
                rows = conn.execute("""SELECT styles.* FROM favorites JOIN styles ON styles.id=favorites.style_id
                    WHERE favorites.user_id=? ORDER BY favorites.created_at DESC""", (user["id"],)).fetchall()
                self._json({"styles": [row_json(row) for row in rows]})
            elif path.startswith("/api/users/") and path.endswith("/appointments"):
                requested_id = int(path.split("/")[3])
                user = self._require_user(conn)
                if user is None:
                    return
                if requested_id != user["id"]:
                    self._json({"error": "Forbidden"}, 403)
                    return
                rows = conn.execute("""SELECT appointments.*,styles.title style_title FROM appointments
                    JOIN styles ON styles.id=appointments.style_id WHERE user_id=? ORDER BY appointments.id DESC""", (user["id"],)).fetchall()
                self._json({"appointments": [dict(row) for row in rows]})
            elif path == "/api/search":
                term = params.get("q", "").strip().lower()
                results = []
                if term:
                    for row in conn.execute("SELECT * FROM styles ORDER BY likes DESC").fetchall():
                        style = row_json(row)
                        text = f"{style['title']} {style['category']} {' '.join(style['tags'])} {style['scene']} {' '.join(style['skin_tones'])} {' '.join(style['nail_shapes'])}".lower()
                        score = (50 if term in style["title"].lower() else 0)
                        score += 40 if term in style["category"].lower() else 0
                        score += 30 if any(term in tag.lower() for tag in style["tags"]) else 0
                        score += 20 if term in style["scene"].lower() else 0
                        score += 15 if term in text else 0
                        if score:
                            style["match_score"] = score
                            results.append(style)
                    results.sort(key=lambda item: (-item["match_score"], -item.get("likes", 0)))
                douyin = f"https://www.douyin.com/search/{quote(term + ' ' + chr(0x7f8e) + chr(0x7532))}?type=general" if term else ""
                self._json({"results": results[:30], "douyin_url": douyin})
            elif path == "/api/featured":
                rows = conn.execute("SELECT * FROM styles ORDER BY likes DESC,id LIMIT 8").fetchall()
                self._json({"styles": [row_json(row) for row in rows]})
            elif path == "/api/trending":
                rows = conn.execute("SELECT * FROM styles ORDER BY likes DESC,id LIMIT 20").fetchall()
                self._json({"styles": [row_json(row) for row in rows]})
            else:
                self._json({"error": "Not found"}, 404)
        finally:
            conn.close()

    def api_post(self, path):
        data = self._body()
        conn = db()
        try:
            if path == "/api/auth/register":
                name = str(data.get("name", "")).strip()
                email = str(data.get("email", "")).strip().lower()
                password = str(data.get("password", ""))
                gender = str(data.get("gender", "female")).strip()
                if gender not in ("male", "female"):
                    gender = "female"
                if len(name) < 2 or "@" not in email or len(password) < 8:
                    raise APIError("\u8bf7\u8f93\u5165\u6709\u6548\u6635\u79f0\u3001\u90ae\u7bb1\u548c\u81f3\u5c11 8 \u4f4d\u5bc6\u7801", 400)
                salt = secrets.token_hex(12)
                avatar_key = ""
                if data.get("avatar_data"):
                    try:
                        avatar_key = avatar_storage().put_data_url(str(data["avatar_data"]))
                    except AvatarStorageError as exc:
                        raise APIError(str(exc), 400)
                try:
                    cur = conn.execute("INSERT INTO users(name,email,password_hash,salt,gender,avatar_key,created_at) VALUES (?,?,?,?,?,?,?)", (name,email,hash_password(password,salt),salt,gender,avatar_key,datetime.now().isoformat(timespec="seconds")))
                except sqlite3.Error as exc:
                    if avatar_key:
                        avatar_storage().delete(avatar_key)
                    if isinstance(exc, sqlite3.IntegrityError):
                        raise APIError("\u8be5\u90ae\u7bb1\u5df2\u7ecf\u6ce8\u518c", 409)
                    raise
                token = create_session(conn, cur.lastrowid)
                conn.commit()
                user = conn.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
                self._json({"token": token, "user": user_json(user)})
            elif path == "/api/auth/login":
                email = str(data.get("email", "")).strip().lower()
                password = str(data.get("password", ""))
                user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
                if not user or not secrets.compare_digest(hash_password(password,user["salt"]), user["password_hash"]):
                    raise APIError("\u90ae\u7bb1\u6216\u5bc6\u7801\u4e0d\u6b63\u786e", 401)
                token = create_session(conn, user["id"])
                conn.commit()
                self._json({"token": token, "user": user_json(user)})
            elif path == "/api/auth/logout":
                token = self._bearer_token()
                if token:
                    conn.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(token),))
                    conn.commit()
                self._json({"ok": True})
            elif path == "/api/profile":
                user = self._require_user(conn)
                if user is None:
                    return
                profile = data.get("profile", {})
                if not isinstance(profile, dict):
                    raise APIError("Invalid profile", 400)
                allowed_keys = (
                    "skin_tone", "hand_shape", "nail_shape", "scene", "style", "gender",
                    "onboarding_status", "tutorial_hand_type", "tutorial_nail_shape",
                    "color_preference", "style_preference", "decoration_preference",
                    "target_length", "maintenance_preference", "decoration_level", "budget_range",
                )
                try:
                    existing = json.loads(user["profile_json"] or "{}")
                except (TypeError, json.JSONDecodeError):
                    existing = {}
                if not isinstance(existing, dict):
                    existing = {}
                updates = {}
                for key in allowed_keys:
                    if key not in profile:
                        continue
                    value = profile[key]
                    if not isinstance(value, str) or len(value) > 64:
                        raise APIError("Invalid profile field", 400)
                    updates[key] = value
                if "nail_conditions" in profile:
                    conditions = profile["nail_conditions"]
                    if not isinstance(conditions, list) or len(conditions) > 3 or any(not isinstance(item, str) or len(item) > 16 for item in conditions):
                        raise APIError("Invalid profile field", 400)
                    updates["nail_conditions"] = conditions
                if "safety_flag" in profile:
                    if not isinstance(profile["safety_flag"], bool):
                        raise APIError("Invalid profile field", 400)
                    updates["safety_flag"] = profile["safety_flag"]
                if "onboarding_status" in updates and updates["onboarding_status"] not in ("skipped", "completed"):
                    raise APIError("Invalid onboarding status", 400)
                merged_profile = {**existing, **updates}
                conn.execute("UPDATE users SET profile_json=? WHERE id=?", (json.dumps(merged_profile,ensure_ascii=False),user["id"]))
                conn.commit()
                updated = conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
                self._json({"ok":True,"profile":merged_profile,"user":user_json(updated)})
            elif path == "/api/recommendations":
                profile_input = data.get("profile", {})
                if not isinstance(profile_input, dict):
                    raise APIError("Invalid profile", 400)
                rows = [row_json(row) for row in conn.execute("SELECT * FROM styles ORDER BY likes DESC,id").fetchall()]
                plan = build_plan(rows, profile_input)
                user = self._current_user(conn)
                if user is None:
                    self._json({"plan": plan, "saved": False})
                    return
                try:
                    existing = json.loads(user["profile_json"] or "{}")
                except (TypeError, json.JSONDecodeError):
                    existing = {}
                if not isinstance(existing, dict):
                    existing = {}
                stored_profile = normalize_profile(profile_input)
                stored_profile["latest_recommendation_plan"] = plan
                stored_profile["knowledge_version"] = KNOWLEDGE_VERSION
                merged_profile = {**existing, **stored_profile}
                conn.execute("UPDATE users SET profile_json=? WHERE id=?", (json.dumps(merged_profile, ensure_ascii=False), user["id"]))
                conn.commit()
                updated = conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
                self._json({"plan": plan, "saved": True, "user": user_json(updated)})
            elif path == "/api/profile/avatar":
                user = self._require_user(conn)
                if user is None:
                    return
                try:
                    new_avatar_key = avatar_storage().put_data_url(str(data.get("avatar_data", "")))
                except AvatarStorageError as exc:
                    raise APIError(str(exc), 400)
                old_avatar_key = user["avatar_key"] or ""
                try:
                    conn.execute("UPDATE users SET avatar_key=? WHERE id=?", (new_avatar_key, user["id"]))
                    conn.commit()
                except sqlite3.Error:
                    avatar_storage().delete(new_avatar_key)
                    raise
                avatar_storage().delete(old_avatar_key)
                updated = conn.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
                self._json({"ok": True, "user": user_json(updated)})
            elif path == "/api/analyze-hand":
                profile = data.get("profile") or {}
                skin = profile.get("skin_tone", "\u81ea\u7136\u80a4\u8272")
                hand = profile.get("hand_shape", "\u7ea4\u957f\u578b")
                nail = profile.get("nail_shape", "\u65b9\u5706\u7532")
                scene = profile.get("scene", "\u65e5\u5e38")
                style = "\u6e29\u67d4\u663e\u767d"
                if skin in ("\u51b7\u767d\u76ae","\u81ea\u7136\u80a4\u8272"):
                    style = "\u6e05\u900f\u51b7\u611f"
                elif skin in ("\u6696\u9ec4\u76ae","\u5c0f\u9ea6\u8272"):
                    style = "\u5976\u8336\u663e\u767d"
                self._json({"profile":{"skin_tone":skin,"hand_shape":hand,"nail_shape":nail,"scene":scene,"style":style},"tips":["\u77ed\u7532\u4f18\u5148\u9009\u62e9\u65b9\u5706\u7532\u6216\u77ed\u674f\u4ec1\u7532","\u4f4e\u9971\u548c\u7c89\u68d5\u8272\u66f4\u9002\u5408\u65e5\u5e38\u901a\u52e4","\u8bd5\u6234\u7ed3\u679c\u4ec5\u4f5c\u642d\u914d\u53c2\u8003"]})
            elif path == "/api/match":
                style_id = int(data.get("style_id",0))
                profile = data.get("profile") or {}
                style = conn.execute("SELECT * FROM styles WHERE id=?",(style_id,)).fetchone()
                if style is None:
                    raise APIError("\u6b3e\u5f0f\u4e0d\u5b58\u5728",404)
                result = match_style(row_json(style), profile)
                limits = {"skin": 28, "hand_shape": 20, "scene_length": 15, "style_finish": 12, "maintenance_decoration": 10, "budget": 10, "popularity": 5}
                labels = {"skin": "肤色与色彩", "hand_shape": "手型与甲型", "scene_length": "场景与长度", "style_finish": "风格与质感", "maintenance_decoration": "维护与饰品", "budget": "预算匹配", "popularity": "款式热度"}
                dimensions = {key: max(1, min(5, round(value / limits[key] * 5))) for key, value in result["components"].items()}
                self._json({"score":result["score"],"dimensions":dimensions,"dimension_labels":labels,"reasons":result["reasons"],"cautions":result["cautions"],"knowledge":result.get("knowledge", {}),"style":row_json(style)})
            elif path == "/api/favorites":
                user = self._require_user(conn)
                if user is None:
                    return
                style_id = int(data.get("style_id",0))
                if conn.execute("SELECT 1 FROM styles WHERE id=?",(style_id,)).fetchone() is None:
                    raise APIError("\u6b3e\u5f0f\u4e0d\u5b58\u5728",404)
                conn.execute("INSERT OR IGNORE INTO favorites(user_id,style_id,created_at) VALUES (?,?,?)",(user["id"],style_id,datetime.now().isoformat(timespec="seconds")))
                conn.commit()
                self._json({"ok":True})
            elif path == "/api/community/posts":
                user = self._require_user(conn)
                if user is None:
                    return
                title = str(data.get("title","")).strip()[:100] or "\u6211\u7684\u65b0\u7f8e\u7532"
                body = str(data.get("body",""))[:2000]
                category = str(data.get("category", "\u6652\u5355")).strip()[:30] or "\u6652\u5355"
                raw_tags = data.get("tags", [])
                tags = ",".join(str(tag).strip()[:30] for tag in raw_tags[:8] if str(tag).strip()) if isinstance(raw_tags, list) else str(raw_tags)[:200]
                image_url = save_uploaded_image(str(data.get("image_data","")))
                try:
                    conn.execute("INSERT INTO posts(user_id,title,body,image_data,category,tags,created_at) VALUES (?,?,?,?,?,?,?)",(user["id"],title,body,image_url,category,tags,datetime.now().isoformat(timespec="seconds")))
                    conn.commit()
                except Exception:
                    remove_uploaded_image(image_url)
                    raise
                self._json({"ok":True,"image_url":image_url})
            elif path == "/api/appointments":
                user = self._require_user(conn)
                if user is None:
                    return
                style_id = int(data.get("style_id",0))
                if conn.execute("SELECT 1 FROM styles WHERE id=?",(style_id,)).fetchone() is None:
                    raise APIError("\u6b3e\u5f0f\u4e0d\u5b58\u5728",404)
                store_name = str(data.get("store_name","")).strip()[:100]
                date = str(data.get("date","")).strip()[:20]
                time_value = str(data.get("time","")).strip()[:20]
                note = str(data.get("note",""))[:500]
                if not store_name or not date or not time_value:
                    raise APIError("\u8bf7\u5b8c\u6574\u586b\u5199\u95e8\u5e97\u3001\u65e5\u671f\u548c\u65f6\u95f4",400)
                conn.execute("INSERT INTO appointments(user_id,style_id,store_name,date,time,note,created_at) VALUES (?,?,?,?,?,?,?)",(user["id"],style_id,store_name,date,time_value,note,datetime.now().isoformat(timespec="seconds")))
                conn.commit()
                self._json({"ok":True})
            elif path == "/api/admin/import":
                expected = os.environ.get("ADMIN_TOKEN","")
                provided = self.headers.get("X-Admin-Token","")
                if not expected or not secrets.compare_digest(expected,provided):
                    self._json({"error":"Forbidden"},403)
                    return
                items = data.get("items",[])
                if not isinstance(items,list) or len(items)>500:
                    raise APIError("Invalid import payload",400)
                imported=0
                for item in items:
                    conn.execute("""INSERT INTO styles(title,category,tags,scene,skin_tones,nail_shapes,price,image_url,color_a,color_b,source,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",(str(item.get("title","Imported style"))[:100],str(item.get("category","Community"))[:50],",".join(item.get("tags",[])),str(item.get("scene","Daily"))[:50],",".join(item.get("skin_tones",["Natural"])),",".join(item.get("nail_shapes",["Squoval"])),str(item.get("price","TBD"))[:50],str(item.get("image_url","assets/photos/real_001.jpg"))[:500],str(item.get("color_a","#f5c4d7"))[:20],str(item.get("color_b","#fff6f8"))[:20],str(item.get("source","Authorized import"))[:100],datetime.now().isoformat(timespec="seconds")))
                    imported+=1
                conn.commit()
                self._json({"ok":True,"imported":imported})
            elif path == "/api/community/comments":
                user = self._require_user(conn)
                if user is None:
                    return
                post_id = int(data.get("post_id",0))
                content = str(data.get("content","")).strip()[:500]
                if not content:
                    raise APIError("\u8bc4\u8bba\u5185\u5bb9\u4e0d\u80fd\u4e3a\u7a7a",400)
                if conn.execute("SELECT 1 FROM posts WHERE id=?",(post_id,)).fetchone() is None:
                    raise APIError("\u5e16\u5b50\u4e0d\u5b58\u5728",404)
                conn.execute("INSERT INTO comments(user_id,post_id,content,created_at) VALUES (?,?,?,?)",(user["id"],post_id,content,datetime.now().isoformat(timespec="seconds")))
                conn.commit()
                self._json({"ok":True})
            elif path == "/api/community/posts/like":
                user = self._require_user(conn)
                if user is None:
                    return
                post_id = int(data.get("post_id",0))
                if conn.execute("SELECT 1 FROM posts WHERE id=?",(post_id,)).fetchone() is None:
                    raise APIError("\u5e16\u5b50\u4e0d\u5b58\u5728",404)
                cur = conn.execute("INSERT OR IGNORE INTO post_likes(user_id,post_id,created_at) VALUES (?,?,?)",(user["id"],post_id,datetime.now().isoformat(timespec="seconds")))
                if cur.rowcount:
                    conn.execute("UPDATE posts SET likes=likes+1 WHERE id=?",(post_id,))
                conn.commit()
                self._json({"ok":True,"added":bool(cur.rowcount)})
            elif path == "/api/share":
                user = self._current_user(conn)
                target_type = str(data.get("target_type","style"))[:30]
                target_id = int(data.get("target_id",0))
                platform = str(data.get("platform","link"))[:30]
                conn.execute("INSERT INTO share_records(user_id,target_type,target_id,platform,created_at) VALUES (?,?,?,?,?)",(user["id"] if user else None,target_type,target_id,platform,datetime.now().isoformat(timespec="seconds")))
                conn.commit()
                self._json({"ok":True})
            else:
                self._json({"error":"Not found"},404)
        finally:
            conn.close()

    def api_delete(self, path):
        conn = db()
        try:
            user = self._require_user(conn)
            if user is None:
                return
            if path == "/api/favorites":
                data = self._body()
                style_id = int(data.get("style_id", 0))
                conn.execute("DELETE FROM favorites WHERE user_id=? AND style_id=?", (user["id"], style_id))
                conn.commit()
                self._json({"ok": True})
            elif path.startswith("/api/community/posts/") and path.endswith("/delete"):
                post_id = int(path.split("/")[4])
                post = conn.execute("SELECT user_id,image_data FROM posts WHERE id=?", (post_id,)).fetchone()
                if post is None:
                    raise APIError("\u5e16\u5b50\u4e0d\u5b58\u5728", 404)
                if post["user_id"] != user["id"]:
                    self._json({"error": "Forbidden"}, 403)
                    return
                conn.execute("DELETE FROM posts WHERE id=?", (post_id,))
                conn.execute("DELETE FROM comments WHERE post_id=?", (post_id,))
                conn.execute("DELETE FROM post_likes WHERE post_id=?", (post_id,))
                conn.commit()
                remove_uploaded_image(post["image_data"])
                self._json({"ok": True})
            elif path.startswith("/api/appointments/") and path.endswith("/cancel"):
                appointment_id = int(path.split("/")[3])
                cur = conn.execute("UPDATE appointments SET status='\u5df2\u53d6\u6d88' WHERE id=? AND user_id=?", (appointment_id, user["id"]))
                if cur.rowcount == 0:
                    raise APIError("\u9884\u7ea6\u4e0d\u5b58\u5728", 404)
                conn.commit()
                self._json({"ok": True})
            else:
                self._json({"error": "Not found"}, 404)
        finally:
            conn.close()

    def serve_static(self, path):
        if path.startswith("/uploads/"):
            root = UPLOADS
            clean = path.removeprefix("/uploads/")
        else:
            root = FRONTEND
            clean = path.lstrip("/") or "index.html"
        target = (root / clean).resolve()
        if root not in target.parents and target != root:
            self._json({"error": "Forbidden"}, 403)
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            if "." not in Path(clean).name:
                target = FRONTEND / "index.html"
            else:
                self._json({"error": "Not found"}, 404)
                return
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self._headers(200, content_type)
        self.wfile.write(target.read_bytes())

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    UPLOADS.mkdir(parents=True, exist_ok=True)
    avatar_storage()
    init_db()
    print(f"美甲搭配师 running at http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
