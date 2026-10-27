"""Export a fresh public copy without touching private originals.

Usage: python scripts/prepare_public_release.py NEW_DESTINATION
Export-time dependency: Pillow (not needed to run the exported application).
"""
import json
import re
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
RASTER = {".png", ".jpg", ".jpeg", ".webp"}


def placeholder(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (480, 600), "#f6eeea")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((160, 120, 320, 430), radius=75, fill="#c79691")
    draw.rounded_rectangle((172, 132, 308, 300), radius=55, fill="#ecd1cb")
    draw.text((175, 490), "DEMO PREVIEW", fill="#73514e")
    image.save(path)


def main():
    target = Path(sys.argv[1]).resolve()
    if target.exists() or target == ROOT or ROOT in target.parents:
        raise SystemExit("Destination must be a new directory outside the source project")
    target.mkdir(parents=True)
    # Deliberate allowlist: no internal docs, uploads, databases or deployment secrets.
    files = [ROOT / name for name in ("README.md", "LICENSE", ".gitignore", "requirements.txt")]
    files += list((ROOT / "backend").glob("*.py"))
    files += [p for p in (ROOT / "deploy").iterdir() if p.is_file() and
              (p.suffix in {".py", ".service", ".timer", ".conf", ".js"} or p.name == "bloom.env.example")]
    files += [ROOT / "frontend" / name for name in ("index.html", "app.js", "styles.css")]
    files += list((ROOT / "frontend" / "vendor").rglob("*"))
    files += [Path(__file__)]
    for source in files:
        if not source.is_file() or source.suffix == ".task":
            continue
        destination = target / source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    assets = ROOT / "frontend" / "assets"
    # Keep only application seed data; do not redistribute scraped post text/provenance.
    styles = json.loads((assets / "comprehensive_styles.json").read_text(encoding="utf-8"))
    dest_assets = target / "frontend" / "assets"
    dest_assets.mkdir(parents=True, exist_ok=True)
    (dest_assets / "comprehensive_styles.json").write_text(json.dumps(styles, ensure_ascii=False, indent=2), encoding="utf-8")
    posts = {"items": [{"title": "Demo nail inspiration", "body": "Original demo placeholder; no third-party photograph included.",
                         "image_data": "/assets/community/demo.png", "tags": ["demo"], "likes": 0}]}
    (dest_assets / "community").mkdir()
    (dest_assets / "community" / "community_posts.json").write_text(json.dumps(posts, indent=2), encoding="utf-8")
    # Generate original geometric previews in place of ALL source image assets.
    count = 0
    for source in assets.rglob("*"):
        if source.suffix.lower() in RASTER:
            placeholder(dest_assets / source.relative_to(assets))
            count += 1
        elif source.suffix.lower() == ".svg":
            destination = dest_assets / source.relative_to(assets)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 600"><rect width="480" height="600" fill="#f6eeea"/><rect x="160" y="120" width="160" height="310" rx="75" fill="#c79691"/><text x="145" y="490" fill="#73514e">DEMO PREVIEW</text></svg>', encoding="utf-8")
    placeholder(dest_assets / "community" / "demo.png")
    # Cover referenced-but-absent images too, including legacy style seeds.
    for source in [target / "frontend" / "app.js", target / "frontend" / "styles.css", target / "frontend" / "index.html", dest_assets / "comprehensive_styles.json", target / "backend" / "app.py"]:
        for reference in re.findall(r'assets/[A-Za-z0-9_./-]+\.(?:png|jpg|jpeg|webp)', source.read_text(encoding="utf-8")):
            destination = target / "frontend" / reference
            if not destination.exists():
                placeholder(destination)
    uploads = target / "frontend" / "uploads"
    uploads.mkdir()
    (uploads / ".gitkeep").touch()
    print(f"Public copy: {target}; replaced {count} raster assets. Private originals unchanged.")


if __name__ == "__main__":
    main()
