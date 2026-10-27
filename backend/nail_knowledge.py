"""Versioned, explainable nail recommendation knowledge derived from the local manuals."""

from __future__ import annotations

import math
import re
from datetime import datetime


KNOWLEDGE_VERSION = "2026.09.25-v1"
SOURCES = ["美甲(3).docx", "美甲资料大全(1).docx", "美甲搭配资料说明手册(1).docx"]

HAND_TYPES = {
    "肉肉手": {"shapes": ["圆形", "椭圆形", "方圆形"], "avoid": ["尖形"], "note": "圆润边缘与短中长度能让手部线条更轻盈。"},
    "短粗手": {"shapes": ["椭圆形", "杏仁形", "方圆形"], "avoid": ["圆形", "方形"], "note": "纵向弧线更能拉长视觉比例，减少横向装饰。"},
    "骨节手": {"shapes": ["方形", "梯形", "方圆形"], "avoid": ["尖形"], "note": "适度直线结构能平衡骨节的棱角感。"},
    "修长手": {"shapes": ["椭圆形", "杏仁形", "尖形", "方圆形"], "avoid": [], "note": "比例协调，可优先按场景、颜色和风格选择。"},
    "圆锥手": {"shapes": ["方形", "方圆形", "梯形"], "avoid": ["尖形", "杏仁形"], "note": "平直前缘可平衡指尖过尖的感觉。"},
    "匀称手": {"shapes": ["圆形", "椭圆形", "杏仁形", "方形", "方圆形", "梯形", "尖形"], "avoid": [], "note": "甲型限制较少，可根据生活方式控制长度。"},
}

NAIL_SHAPES = {
    "圆形": "圆润安全，适合短甲与低维护日常。",
    "椭圆形": "柔和拉长手指，适配通勤和婚礼。",
    "杏仁形": "线条柔和且显手长，适合中长款。",
    "方形": "前缘利落，适合法式、极简与几何。",
    "方圆形": "稳定耐看，日常和通勤适配面广。",
    "梯形": "修饰宽甲床，适合潮流和艺术感设计。",
    "尖形": "视觉延长强，但更需要控制长度和维护。",
}

PALETTES = [
    ("C01", "冷裸粉", "#F5D8E2", ["冷白皮", "黄白皮"], ["冷粉", "清透浅色"]),
    ("C02", "玫瑰粉", "#E7B9C7", ["冷白皮", "黄白皮", "自然黄皮"], ["玫瑰", "清透浅色"]),
    ("C03", "冰透白", "#F2E6DF", ["冷白皮"], ["中性", "清透浅色"]),
    ("C04", "车厘子红", "#C93F63", ["黄白皮", "自然黄皮", "深肤色"], ["冷红", "显白暖色"]),
    ("C05", "复古酒红", "#7A1F3D", ["冷白皮", "自然黄皮", "深肤色"], ["深红", "显白暖色"]),
    ("C06", "莓果红", "#8F2D56", ["冷白皮", "黄白皮"], ["红紫", "显白暖色"]),
    ("C07", "宝蓝", "#2B3C78", ["冷白皮", "深肤色"], ["冷蓝", "冷感光泽"]),
    ("C08", "雾霾蓝", "#7890B8", ["黄白皮", "自然黄皮"], ["灰蓝", "冷感光泽"]),
    ("C09", "灰调芋紫", "#4A245F", ["冷白皮", "深肤色"], ["冷紫", "冷感光泽"]),
    ("C10", "芋泥紫", "#9A78A6", ["黄白皮", "自然黄皮"], ["灰紫", "冷感光泽"]),
    ("C11", "黑茶", "#8B574A", ["黄白皮", "自然黄皮"], ["茶棕", "低饱和裸色"]),
    ("C12", "焦糖棕", "#B77745", ["自然黄皮", "深肤色"], ["暖棕", "显白暖色"]),
    ("C13", "巧克力棕", "#6B3F2A", ["自然黄皮", "深肤色"], ["深棕", "显白暖色"]),
    ("C14", "奶茶裸", "#D9B6A7", ["黄白皮", "自然黄皮"], ["暖裸", "低饱和裸色"]),
    ("C15", "奶茶灰裸", "#BFA28F", ["自然黄皮"], ["灰裸", "低饱和裸色"]),
    ("C16", "灰粉裸", "#B8A6A0", ["冷白皮", "自然黄皮"], ["中性灰粉", "低饱和裸色"]),
    ("C17", "墨绿", "#1F4A3B", ["黄白皮", "深肤色"], ["深绿", "显白暖色"]),
    ("C18", "藏蓝", "#1D315A", ["自然黄皮", "深肤色"], ["深蓝", "冷感光泽"]),
    ("C19", "香槟金", "#C8A15A", ["黄白皮", "深肤色"], ["金属", "显白暖色"]),
    ("C20", "银灰", "#C5C9D6", ["冷白皮"], ["冷金属", "冷感光泽"]),
    ("C21", "蜜桃粉", "#F2A6B8", ["黄白皮", "自然黄皮"], ["暖粉", "清透浅色"]),
    ("C22", "珊瑚橘", "#E77854", ["自然黄皮", "深肤色"], ["暖橘", "显白暖色"]),
    ("C23", "雾灰", "#8B8F8D", ["冷白皮", "黄白皮", "自然黄皮", "深肤色"], ["中性灰", "低饱和裸色"]),
    ("C24", "柔黑", "#15151A", ["冷白皮", "黄白皮", "自然黄皮", "深肤色"], ["中性深色", "冷感光泽"]),
]
PALETTE_BY_ID = {item[0]: {"id": item[0], "name": item[1], "hex": item[2], "skin_tones": item[3], "families": item[4]} for item in PALETTES}

SCENE_GUIDES = {
    "日常": {"lengths": ["短", "中"], "note": "优先低饱和、低凸起与轻维护设计。"},
    "通勤": {"lengths": ["短", "中"], "note": "奶茶、灰裸、微法式更利落，避免强反光满甲。"},
    "约会": {"lengths": ["中"], "note": "玫瑰、莓果、猫眼与少量珍珠能增加精致感。"},
    "婚礼": {"lengths": ["中", "长"], "note": "冰透白、香槟与珍珠优先考虑服装和拍照协调。"},
    "聚会": {"lengths": ["中", "长"], "note": "酒红、镜面、碎钻更有氛围，先评估维护耐受。"},
    "节日": {"lengths": ["短", "中", "长"], "note": "可尝试高饱和和趣味质感，提前确认环境变化效果。"},
}

FAMILY_TERMS = {
    "基础纯色": ["纯色", "果冻", "裸色", "极简"],
    "法式": ["法式"],
    "渐变晕染": ["渐变", "晕染", "大理石", "扎染"],
    "特殊质感": ["猫眼", "镜面", "磨砂", "闪钻", "星空"],
    "手绘纹理": ["花卉", "几何", "蕾丝", "大理石"],
    "饰品装饰": ["3D立体", "链条", "铆钉", "闪钻", "甜美"],
}
FINISH_BY_CATEGORY = {
    "猫眼": "猫眼光带", "镜面": "镜面/极光", "磨砂": "磨砂雾面", "闪钻": "细闪碎钻",
    "星空": "细闪碎钻", "果冻": "果冻透色", "法式": "亮面法式", "渐变": "柔和渐变",
    "晕染": "水墨晕染", "大理石": "纹理晕染", "3D立体": "立体装饰", "链条": "金属饰件",
    "铆钉": "金属饰件", "蕾丝": "手绘纹理", "花卉": "手绘纹理", "几何": "几何线条",
    "扎染": "柔和晕染", "甜美": "亮面装饰", "琥珀": "透色纹理", "复古": "复古亮面", "极简": "简约亮面",
}
DECORATION_BY_CATEGORY = {
    "3D立体": ("突出", ["立体3D"], "高"), "链条": ("突出", ["金属"], "高"),
    "铆钉": ("适中", ["金属"], "中"), "闪钻": ("适中", ["薄片闪粉"], "中"),
    "星空": ("轻量", ["薄片闪粉"], "中"), "甜美": ("适中", ["珍珠"], "中"),
    "蕾丝": ("轻量", ["手绘纹理"], "中"), "花卉": ("轻量", ["手绘纹理"], "中"),
}

LEGACY_SKINS = {"自然肤色": "自然黄皮", "暖黄皮": "黄白皮", "小麦色": "深肤色"}
LEGACY_HANDS = {"圆润型": "肉肉手", "短指型": "短粗手", "骨感型": "骨节手", "纤长型": "修长手"}
LEGACY_SHAPES = {"圆甲": "圆形", "椭圆甲": "椭圆形", "杏仁甲": "杏仁形", "方甲": "方形", "方圆甲": "方圆形", "梯形甲": "梯形", "尖甲": "尖形"}
LEGACY_SCENES = {"宴会": "聚会", "夏季": "节日"}


def _normalize(value, allowed, legacy, fallback):
    value = str(value or "").strip()
    value = legacy.get(value, value)
    return value if value in allowed else fallback


def normalize_profile(raw):
    raw = raw if isinstance(raw, dict) else {}
    shape_raw = raw.get("nail_shape", "方圆形")
    inferred_length = "短" if shape_raw == "短甲" else "长" if shape_raw == "长甲" else "中"
    conditions = raw.get("nail_conditions", [])
    if isinstance(conditions, str):
        conditions = [conditions]
    conditions = [item for item in conditions if item in {"无明显困扰", "短甲", "软薄易断", "扁平", "扇形外扩"}][:3]
    if not conditions:
        conditions = ["无明显困扰"]
    return {
        "skin_tone": _normalize(raw.get("skin_tone"), {"冷白皮", "黄白皮", "自然黄皮", "深肤色"}, LEGACY_SKINS, "自然黄皮"),
        "hand_shape": _normalize(raw.get("hand_shape"), set(HAND_TYPES), LEGACY_HANDS, "修长手"),
        "nail_shape": _normalize(shape_raw, set(NAIL_SHAPES), LEGACY_SHAPES, "方圆形"),
        "scene": _normalize(raw.get("scene"), set(SCENE_GUIDES), LEGACY_SCENES, "日常"),
        "target_length": raw.get("target_length") if raw.get("target_length") in {"短", "中", "长"} else inferred_length,
        "nail_conditions": conditions,
        "maintenance_preference": raw.get("maintenance_preference") if raw.get("maintenance_preference") in {"低", "中", "高"} else "中",
        "decoration_level": raw.get("decoration_level") if raw.get("decoration_level") in {"无", "轻量", "适中", "突出"} else _legacy_decoration(raw.get("decoration_preference")),
        "budget_range": raw.get("budget_range") if raw.get("budget_range") in {"100以内", "100-160", "160-240", "240以上", "不限"} else "不限",
        "style_preference": str(raw.get("style_preference") or raw.get("style") or "").strip(),
        "color_preference": str(raw.get("color_preference") or "").strip(),
        "safety_flag": bool(raw.get("safety_flag", False)),
    }


def _legacy_decoration(value):
    return {"不加饰品": "无", "细闪薄片": "轻量", "珍珠金属": "适中", "钻饰": "适中", "3D 饰品": "突出"}.get(value, "轻量")


def _hex_rgb(value):
    value = str(value or "").lstrip("#")
    if len(value) == 3:
        value = "".join(char * 2 for char in value)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        return (245, 216, 226)
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def _nearest_palette_ids(*colors):
    candidates = []
    for color in colors:
        rgb = _hex_rgb(color)
        nearest = min(PALETTE_BY_ID.values(), key=lambda item: sum((a - b) ** 2 for a, b in zip(rgb, _hex_rgb(item["hex"]))))
        if nearest["id"] not in candidates:
            candidates.append(nearest["id"])
    return candidates[:2] or ["C02"]


def _split(value):
    return value if isinstance(value, list) else [item for item in str(value or "").split(",") if item]


def _normalize_style_shape(value):
    return LEGACY_SHAPES.get(value, value) if value not in {"短甲", "长甲"} else value


def _family_for(style):
    text = " ".join([str(style.get("category", "")), str(style.get("title", "")), *[str(item) for item in _split(style.get("tags"))]])
    for family, terms in FAMILY_TERMS.items():
        if any(term in text for term in terms):
            return family
    return "基础纯色"


def style_knowledge(style):
    category = str(style.get("category", ""))
    tags = _split(style.get("tags"))
    raw_shapes = _split(style.get("nail_shapes"))
    shapes = [_normalize_style_shape(item) for item in raw_shapes if _normalize_style_shape(item) in NAIL_SHAPES]
    lengths = ["短"] if "短甲" in raw_shapes else ["长"] if "长甲" in raw_shapes else ["中"]
    if "长甲" in raw_shapes and "短甲" in raw_shapes:
        lengths = ["短", "中", "长"]
    decoration, decoration_types, visual_weight = DECORATION_BY_CATEGORY.get(category, ("无", [], "低"))
    text = " ".join([str(style.get("title", "")), category, *tags])
    if any(term in text for term in ("珍珠", "蝴蝶结")) and decoration == "无":
        decoration, decoration_types, visual_weight = "适中", ["珍珠"], "中"
    if any(term in text for term in ("金箔", "碎钻", "星闪")) and decoration == "无":
        decoration, decoration_types, visual_weight = "轻量", ["薄片闪粉"], "低"
    maintenance = int(style.get("maintenance_ease") or 3)
    maintenance_level = "低" if maintenance >= 4 else "高" if maintenance <= 2 else "中"
    skins = [LEGACY_SKINS.get(item, item) for item in _split(style.get("skin_tones"))]
    scenes = [LEGACY_SCENES.get(item, item) for item in _split(style.get("scene"))]
    return {
        "version": KNOWLEDGE_VERSION,
        "sources": SOURCES,
        "style_family": _family_for(style),
        "color_ids": _nearest_palette_ids(style.get("color_a"), style.get("color_b")),
        "finish": FINISH_BY_CATEGORY.get(category, "亮面设计"),
        "decoration_level": decoration,
        "decoration_types": decoration_types,
        "visual_weight": visual_weight,
        "recommended_lengths": lengths,
        "maintenance_level": maintenance_level,
        "suitable_hand_shapes": list(HAND_TYPES),
        "cautious_hand_shapes": [],
        "suitable_nail_shapes": shapes or list(NAIL_SHAPES),
        "suitable_skin_tones": skins or list(PALETTE_BY_ID["C02"]["skin_tones"]),
        "suitable_scenes": [scene for scene in scenes if scene in SCENE_GUIDES] or ["日常"],
        "price_range": str(style.get("price", "")),
    }


def _price_floor(value):
    match = re.search(r"\d+", str(value or ""))
    return int(match.group()) if match else 0


def _budget_cap(value):
    return {"100以内": 100, "100-160": 160, "160-240": 240, "240以上": math.inf, "不限": math.inf}[value]


def _score_style(style, profile, max_likes):
    knowledge = style.get("knowledge") or style_knowledge(style)
    score = 0
    reasons = []
    colors = [PALETTE_BY_ID[color_id] for color_id in knowledge["color_ids"]]
    skin_match = profile["skin_tone"] in knowledge["suitable_skin_tones"]
    palette_match = any(profile["skin_tone"] in color["skin_tones"] for color in colors)
    score += 28 if skin_match else 18 if palette_match else 7
    if skin_match or palette_match:
        reasons.append("色彩方向与肤色参考相符，更容易呈现干净有气色的效果。")
    preferred_shapes = HAND_TYPES[profile["hand_shape"]]["shapes"]
    desired_shape_match = profile["nail_shape"] in knowledge["suitable_nail_shapes"]
    hand_shape_match = profile["nail_shape"] in preferred_shapes
    catalog_shape_match = bool(set(preferred_shapes) & set(knowledge["suitable_nail_shapes"]))
    score += (10 if desired_shape_match else 3) + (7 if hand_shape_match else 1) + (3 if catalog_shape_match else 0)
    if hand_shape_match:
        reasons.append(f"{profile['hand_shape']}更适合{profile['nail_shape']}的线条方向。")
    scene_match = profile["scene"] in knowledge["suitable_scenes"]
    length_match = profile["target_length"] in knowledge["recommended_lengths"]
    score += (10 if scene_match else 4) + (5 if length_match else 1)
    if scene_match:
        reasons.append(f"款式的视觉重量与{profile['scene']}场景更协调。")
    family_match = bool(profile["style_preference"] and any(term in knowledge["style_family"] for term in FAMILY_TERMS if term == profile["style_preference"]))
    if not family_match and profile["style_preference"]:
        family_match = profile["style_preference"] == knowledge["style_family"]
    color_match = bool(profile["color_preference"] and any(profile["color_preference"] in color["families"] for color in colors))
    finish_match = profile["style_preference"] == "特殊质感" and knowledge["style_family"] == "特殊质感"
    score += (7 if family_match else 2) + (3 if color_match else 1) + (2 if finish_match else 0)
    decoration = knowledge["decoration_level"]
    decoration_score = 5 if decoration == profile["decoration_level"] else 3 if {decoration, profile["decoration_level"]} <= {"无", "轻量"} or {decoration, profile["decoration_level"]} <= {"适中", "突出"} else 0
    maintenance_match = knowledge["maintenance_level"] == profile["maintenance_preference"]
    score += decoration_score + (5 if maintenance_match else 2)
    if maintenance_match:
        reasons.append("维护强度与你当前的日常耐受更接近。")
    floor = _price_floor(knowledge["price_range"])
    cap = _budget_cap(profile["budget_range"])
    in_budget = floor <= cap
    overage = 0 if in_budget or math.isinf(cap) else floor - cap
    score += 10 if in_budget else 0
    popularity = min(5, round((int(style.get("likes") or 0) / max(max_likes, 1)) * 5))
    score += popularity
    cautions = []
    if profile["nail_shape"] in HAND_TYPES[profile["hand_shape"]]["avoid"]:
        cautions.append(f"{profile['hand_shape']}使用{profile['nail_shape']}时，建议由美甲师现场确认长度与边缘比例。")
    if profile["target_length"] == "长" and any(item in profile["nail_conditions"] for item in ("短甲", "软薄易断")):
        cautions.append("当前甲况与目标长度存在受力风险，建议优先向美甲师咨询加固或降低长度。")
    if decoration in ("适中", "突出") and profile["maintenance_preference"] == "低":
        cautions.append("该款包含较明显装饰，做家务和穿脱衣物时需减少勾挂。")
    return {
        "style": style,
        "knowledge": knowledge,
        "score": min(100, int(score)),
        "reasons": reasons[:3] or ["款式与当前档案有基础适配，可结合色卡和现场甲况确认。"],
        "cautions": cautions,
        "in_budget": in_budget,
        "budget_overage": overage,
        "components": {"skin": 28 if skin_match else 18 if palette_match else 7, "hand_shape": (10 if desired_shape_match else 3) + (7 if hand_shape_match else 1) + (3 if catalog_shape_match else 0), "scene_length": (10 if scene_match else 4) + (5 if length_match else 1), "style_finish": (7 if family_match else 2) + (3 if color_match else 1) + (2 if finish_match else 0), "maintenance_decoration": decoration_score + (5 if maintenance_match else 2), "budget": 10 if in_budget else 0, "popularity": popularity},
    }


def _consultation(profile):
    conditions = set(profile["nail_conditions"])
    if "软薄易断" in conditions:
        return "可向美甲师咨询短中长度与本甲薄建构的可行性；实际胶量和受力须由现场甲况决定。"
    if "扁平" in conditions or "扇形外扩" in conditions:
        return "可向美甲师咨询高位建构或修饰线条的可行性；这属于现场工艺判断，不代表远程矫正结论。"
    if "短甲" in conditions and profile["target_length"] in ("中", "长"):
        return "可向美甲师咨询半贴、全贴或无甲片延长的适配性，并先确认甲片弧度和日常受力。"
    return "本甲状态无明显困扰时，仍建议在到店前确认甲面弧度、材料经历和实际可承受长度。"


def build_plan(styles, raw_profile):
    profile = normalize_profile(raw_profile)
    base = {"version": KNOWLEDGE_VERSION, "sources": SOURCES, "generated_at": datetime.now().isoformat(timespec="seconds"), "profile": profile}
    if profile["safety_flag"]:
        return {**base, "status": "safety_hold", "summary": "检测到甲面异常提示，已暂停普通美甲推荐。", "safety_notice": "如有疼痛、红肿、渗液、明显变色或破损，请先进行专业检查；平台不提供诊断或施工结论。", "items": [], "consultation": None, "care": []}
    max_likes = max((int(style.get("likes") or 0) for style in styles), default=1)
    ranked = [_score_style(style, profile, max_likes) for style in styles]
    ranked.sort(key=lambda item: (not item["in_budget"], -item["score"], item["budget_overage"], -int(item["style"].get("likes") or 0)))
    primary = ranked[0] if ranked else None
    colors = []
    for item in ranked[:3]:
        for color_id in item["knowledge"]["color_ids"]:
            if color_id not in colors:
                colors.append(color_id)
    if not colors:
        colors = ["C02", "C04"]
    suggested_shape = profile["nail_shape"] if profile["nail_shape"] in HAND_TYPES[profile["hand_shape"]]["shapes"] else HAND_TYPES[profile["hand_shape"]]["shapes"][0]
    care = ["避免用甲面撬硬物；接触清洁剂和长期泡水时建议戴手套。"]
    if profile["decoration_level"] in ("适中", "突出"):
        care.append("立体饰品和钻饰容易磕碰，洗头、穿脱衣物时注意减少勾挂。")
    if primary and primary["knowledge"]["maintenance_level"] == "高":
        care.append("该方向的维护要求较高，发现起翘、裂缝或疼痛时请及时回店处理。")
    return {
        **base,
        "status": "ready",
        "summary": f"为你优先选择{suggested_shape}与{profile['target_length']}长度方向，并按肤色、场景、维护和预算综合排序。",
        "recommendation": {
            "nail_shape": suggested_shape,
            "target_length": profile["target_length"],
            "colors": [PALETTE_BY_ID[color_id] for color_id in colors[:3]],
            "finish": primary["knowledge"]["finish"] if primary else "亮面设计",
            "decoration_level": profile["decoration_level"],
            "scene_note": SCENE_GUIDES[profile["scene"]]["note"],
        },
        "consultation": _consultation(profile),
        "care": care,
        "disclaimer": "搭配建议仅供参考，屏幕色差、甲面状态与实际工艺应以自然光试色和美甲师现场判断为准。",
        "items": ranked[:3],
    }


def match_style(style, raw_profile):
    profile = normalize_profile(raw_profile)
    if profile["safety_flag"]:
        return {"score": 0, "reasons": ["已暂停普通美甲匹配，请先处理甲面异常。"], "cautions": ["平台不提供诊断或施工结论。"], "components": {}}
    result = _score_style(style, profile, max(int(style.get("likes") or 0), 1))
    return {"score": result["score"], "reasons": result["reasons"], "cautions": result["cautions"], "components": result["components"], "knowledge": result["knowledge"]}
