import base64
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from avatar_storage import AvatarStorage, AvatarStorageError, decode_avatar_data


JPEG_DATA_URL = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xffavatar-test").decode()


class FakeS3:
    def __init__(self):
        self.put_calls = []
        self.delete_calls = []

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)

    def delete_object(self, **kwargs):
        self.delete_calls.append(kwargs)


class AvatarStorageTests(unittest.TestCase):
    def test_local_storage_creates_public_url_and_deletes_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = AvatarStorage(Path(temporary_directory), "development", "", "")
            key = storage.put_data_url(JPEG_DATA_URL)
            self.assertTrue((Path(temporary_directory) / key).is_file())
            self.assertEqual(storage.public_url(key), f"/uploads/{key}")
            storage.delete(key)
            self.assertFalse((Path(temporary_directory) / key).exists())

    def test_production_can_explicitly_use_local_storage(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage = AvatarStorage(Path(temporary_directory), "production", "", "", "local")
            key = storage.put_data_url(JPEG_DATA_URL)
            self.assertTrue((Path(temporary_directory) / key).is_file())

    def test_s3_backend_requires_bucket(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(AvatarStorageError):
                AvatarStorage(Path(temporary_directory), "production", "", "", "s3")

    def test_s3_storage_uses_public_base_url_and_object_key(self):
        client = FakeS3()
        boto3_module = SimpleNamespace(client=lambda *args, **kwargs: client)
        settings = {
            "S3_ACCESS_KEY_ID": "test-key",
            "S3_SECRET_ACCESS_KEY": "test-secret",
            "S3_REGION": "test-region",
            "AVATAR_PUBLIC_BASE_URL": "https://cdn.example.test/media/",
        }
        with tempfile.TemporaryDirectory() as temporary_directory, patch.dict(os.environ, settings, clear=False), patch.dict(sys.modules, {"boto3": boto3_module}):
            storage = AvatarStorage(Path(temporary_directory), "production", "avatar-bucket", settings["AVATAR_PUBLIC_BASE_URL"])
            key = storage.put_data_url(JPEG_DATA_URL)
            self.assertEqual(storage.public_url(key), f"https://cdn.example.test/media/{key}")
            self.assertEqual(client.put_calls[0]["Bucket"], "avatar-bucket")
            self.assertEqual(client.put_calls[0]["Key"], key)
            storage.delete(key)
            self.assertEqual(client.delete_calls, [{"Bucket": "avatar-bucket", "Key": key}])

    def test_rejects_mime_without_matching_image_signature(self):
        bad_data_url = "data:image/png;base64," + base64.b64encode(b"not-a-png").decode()
        with self.assertRaises(AvatarStorageError):
            decode_avatar_data(bad_data_url)


if __name__ == "__main__":
    unittest.main()
