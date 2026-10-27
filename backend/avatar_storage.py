"""Avatar storage with local and S3-compatible backends."""

import base64
import os
import secrets
from dataclasses import dataclass
from pathlib import Path


MAX_AVATAR_BYTES = 2 * 1024 * 1024
ALLOWED_IMAGES = {
    "image/jpeg": (".jpg", b"\xff\xd8\xff"),
    "image/png": (".png", b"\x89PNG\r\n\x1a\n"),
}


class AvatarStorageError(Exception):
    pass


def decode_avatar_data(data_url: str) -> tuple[str, str, bytes]:
    """Decode and validate a JPEG, PNG, or WebP data URL."""
    if not isinstance(data_url, str) or not data_url.startswith("data:image/"):
        raise AvatarStorageError("请上传有效的头像图片")
    try:
        header, encoded = data_url.split(",", 1)
        mime = header[5:].split(";", 1)[0].lower()
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error):
        raise AvatarStorageError("头像图片数据无法解析")

    if not raw or len(raw) > MAX_AVATAR_BYTES:
        raise AvatarStorageError("头像图片不能超过 2MB")

    if mime in ALLOWED_IMAGES:
        extension, signature = ALLOWED_IMAGES[mime]
        if not raw.startswith(signature):
            raise AvatarStorageError("头像图片格式与内容不一致")
    elif mime == "image/webp":
        extension = ".webp"
        if len(raw) < 12 or raw[:4] != b"RIFF" or raw[8:12] != b"WEBP":
            raise AvatarStorageError("头像图片格式与内容不一致")
    else:
        raise AvatarStorageError("仅支持 JPG、PNG 或 WebP 头像")
    return mime, extension, raw


@dataclass
class AvatarStorage:
    media_root: Path
    environment: str
    bucket: str
    public_base_url: str
    backend: str = "auto"

    def __post_init__(self):
        backend = self.backend.strip().lower() or "auto"
        if backend not in ("auto", "local", "s3"):
            raise AvatarStorageError("AVATAR_STORAGE 仅支持 local 或 s3")
        self.use_s3 = backend == "s3" or (backend == "auto" and bool(self.bucket))
        if self.use_s3 and not self.bucket:
            raise AvatarStorageError("S3 头像存储缺少配置：S3_BUCKET")
        if self.use_s3:
            self._configure_s3()
        else:
            self.local_root = self.media_root / "avatars"
            self.local_root.mkdir(parents=True, exist_ok=True)

    def _configure_s3(self):
        required = ("S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY", "S3_REGION", "AVATAR_PUBLIC_BASE_URL")
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            raise AvatarStorageError(f"S3 头像存储缺少配置：{', '.join(missing)}")
        try:
            import boto3
        except ImportError as exc:
            raise AvatarStorageError("未安装 boto3，无法使用 S3 头像存储") from exc
        self.public_base_url = self.public_base_url.rstrip("/")
        self.s3 = boto3.client(
            "s3",
            endpoint_url=os.environ.get("S3_ENDPOINT_URL") or None,
            region_name=os.environ.get("S3_REGION") or None,
            aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
        )

    def put_data_url(self, data_url: str) -> str:
        mime, extension, raw = decode_avatar_data(data_url)
        key = f"avatars/{secrets.token_hex(20)}{extension}"
        try:
            if self.use_s3:
                self.s3.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=raw,
                    ContentType=mime,
                    CacheControl="public, max-age=31536000, immutable",
                )
            else:
                target = (self.media_root / key).resolve()
                if target.parent != self.local_root.resolve():
                    raise AvatarStorageError("头像存储路径无效")
                target.write_bytes(raw)
        except AvatarStorageError:
            raise
        except Exception as exc:
            raise AvatarStorageError("头像上传失败，请稍后重试") from exc
        return key

    def public_url(self, key: str) -> str:
        if not key:
            return ""
        if self.use_s3:
            return f"{self.public_base_url}/{key}"
        return f"/uploads/{key}"

    def delete(self, key: str):
        if not key:
            return
        try:
            if self.use_s3:
                self.s3.delete_object(Bucket=self.bucket, Key=key)
            else:
                target = (self.media_root / Path(key)).resolve()
                if target.parent == self.local_root.resolve() and target.exists():
                    target.unlink()
        except Exception:
            # Database updates have already succeeded when this is called. A later cleanup can retry.
            return


def create_avatar_storage(media_root: Path) -> AvatarStorage:
    return AvatarStorage(
        media_root=media_root,
        environment=os.environ.get("APP_ENV", "development").lower(),
        bucket=os.environ.get("S3_BUCKET", "").strip(),
        public_base_url=os.environ.get("AVATAR_PUBLIC_BASE_URL", "").strip(),
        backend=os.environ.get("AVATAR_STORAGE", "auto"),
    )
