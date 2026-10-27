"""
美甲搭配师 - 真实照片下载器 + 全面款式库

从 Pixabay 等免费图库下载真实美甲照片
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from datetime import datetime

PHOTOS_DIR = Path(__file__).resolve().parent.parent / "frontend" / "assets" / "photos"
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = "Mozilla/5.0 (compatible; MeijiaDapeishi/1.0; +https://meijia.local)"

# ============================================================
# Pixabay 公开图片URL列表（从搜索结果中提取的真实美甲照片）
# 这些是 Pixabay 上的免费图片，可直接下载
# ============================================================

PIXABAY_NAIL_PHOTOS = [
    # 各类美甲真实照片（Pixabay免费图片）
    "https://cdn.pixabay.com/photo/2017/06/20/05/43/nail-art-2421670_1280.jpg",
    "https://cdn.pixabay.com/photo/2018/05/23/15/04/nail-art-3425130_1280.jpg",
    "https://cdn.pixabay.com/photo/2019/02/18/13/34/nail-art-4004491_1280.jpg",
    "https://cdn.pixabay.com/photo/2016/11/29/04/58/nail-art-1867606_1280.jpg",
    "https://cdn.pixabay.com/photo/2017/08/10/14/39/nail-art-2628663_1280.jpg",
    "https://cdn.pixabay.com/photo/2020/05/13/16/30/nail-art-5164845_1280.jpg",
    "https://cdn.pixabay.com/photo/2018/01/30/14/20/nail-3118914_1280.jpg",
    "https://cdn.pixabay.com/photo/2019/07/13/19/15/nail-art-4335514_1280.jpg",
    "https://cdn.pixabay.com/photo/2021/08/04/13/05/nail-art-6521864_1280.jpg",
    "https://cdn.pixabay.com/photo/2022/03/15/09/08/nail-art-7069681_1280.jpg",
    # 法式美甲
    "https://cdn.pixabay.com/photo/2017/09/05/10/21/nail-art-2717448_1280.jpg",
    "https://cdn.pixabay.com/photo/2018/12/19/10/29/nail-art-3882814_1280.jpg",
    # 红色美甲
    "https://cdn.pixabay.com/photo/2023/05/30/13/45/nail-art-8028566_1280.jpg",
    "https://cdn.pixabay.com/photo/2016/09/10/14/09/nail-polish-1658174_1280.jpg",
    # 闪亮美甲
    "https://cdn.pixabay.com/photo/2017/08/10/14/37/nail-art-2628661_1280.jpg",
    "https://cdn.pixabay.com/photo/2018/08/13/09/31/nail-art-3602562_1280.jpg",
    # 花卉美甲
    "https://cdn.pixabay.com/photo/2017/08/10/14/47/nail-art-2628672_1280.jpg",
    "https://cdn.pixabay.com/photo/2019/06/06/15/28/nail-art-4256243_1280.jpg",
    # 更多风格
    "https://cdn.pixabay.com/photo/2020/01/23/10/35/nail-art-4787455_1280.jpg",
    "https://cdn.pixabay.com/photo/2021/11/10/09/40/nail-art-6783706_1280.jpg",
]


def download_image(url, filename=None, retries=3):
    """从URL下载图片"""
    if filename is None:
        ext = ".jpg"
        if ".png" in url.lower(): ext = ".png"
        filename = f"real_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{ext}"

    filepath = PHOTOS_DIR / filename

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                if len(data) < 1000:
                    continue
                filepath.write_bytes(data)
                print(f"  ✅ {filename} ({len(data)//1024}KB)")
                return str(filepath.relative_to(PHOTOS_DIR.parent))
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                print(f"  ❌ {filename}: {e}")
    return None


def download_all():
    """批量下载Pixabay图片"""
    print(f"📥 从 Pixabay 下载真实美甲照片 ({len(PIXABAY_NAIL_PHOTOS)} 张)...")
    print(f"   保存目录: {PHOTOS_DIR}\n")

    results = []
    for i, url in enumerate(PIXABAY_NAIL_PHOTOS):
        filename = f"real_{i+1:03d}.jpg"
        print(f"  [{i+1}/{len(PIXABAY_NAIL_PHOTOS)}] {filename}...", end=" ")
        path = download_image(url, filename)
        if path:
            results.append(path)
        time.sleep(0.3)  # 礼貌延迟

    # 保存下载记录
    record_path = PHOTOS_DIR / "download_record.json"
    record_path.write_text(json.dumps({
        "date": datetime.now().isoformat(),
        "downloaded": results,
        "total": len(results),
        "source": "Pixabay (free license)"
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n📸 成功下载 {len(results)}/{len(PIXABAY_NAIL_PHOTOS)} 张真实美甲照片")
    return results


def check_pixabay_api():
    """尝试使用 Pixabay API 获取更多图片（需要 API key）"""
    api_key = os.environ.get("PIXABAY_API_KEY", "")
    if not api_key:
        print("⚠️ 未设置 PIXABAY_API_KEY 环境变量，使用预设URL列表")
        return []

    print("🔑 使用 Pixabay API 搜索美甲照片...")
    queries = ["nail+art+manicure", "french+nails", "nail+design+glitter",
               "nail+art+flower", "ombre+nails", "nail+art+marble"]

    all_results = []
    for query in queries:
        url = f"https://pixabay.com/api/?key={api_key}&q={urllib.parse.quote(query)}&image_type=photo&per_page=20&lang=zh"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                for hit in data.get("hits", []):
                    all_results.append(hit["largeImageURL"])
            print(f"  搜索 '{query}' → {len(data.get('hits',[]))} 结果")
        except Exception as e:
            print(f"  API错误: {e}")
        time.sleep(1)

    # 下载API获取的图片
    print(f"\n📥 下载 API 结果 ({len(all_results)} 张)...")
    downloaded = []
    for i, url in enumerate(all_results[:50]):  # 最多50张
        filename = f"api_{i+1:03d}.jpg"
        path = download_image(url, filename)
        if path:
            downloaded.append(path)
        time.sleep(0.3)

    return downloaded


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    print("=" * 60)
    print("  美甲搭配师 - 真实照片下载器")
    print("=" * 60)
    print()

    # 先尝试API，再下载预设URL
    api_results = check_pixabay_api()
    url_results = download_all()

    total = len(api_results) + len(url_results)
    print(f"\n🎉 总计下载 {total} 张真实美甲照片 → {PHOTOS_DIR}")
