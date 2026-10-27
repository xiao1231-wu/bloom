import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen

import app


class RuntimeConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.original_db_path = app.DB_PATH
        self.original_uploads = app.UPLOADS
        self.original_cors_origin = app.CORS_ORIGIN
        self.original_avatar_storage = app._avatar_storage
        app.DB_PATH = root / "data" / "meijia.db"
        app.UPLOADS = root / "media"
        app.CORS_ORIGIN = "https://bloom.example.test"
        app._avatar_storage = None
        app.UPLOADS.mkdir(parents=True)
        app.init_db()

    def tearDown(self):
        app.DB_PATH = self.original_db_path
        app.UPLOADS = self.original_uploads
        app.CORS_ORIGIN = self.original_cors_origin
        app._avatar_storage = self.original_avatar_storage
        self.temporary_directory.cleanup()

    def test_fresh_database_contains_seed_content_without_users(self):
        conn = sqlite3.connect(app.DB_PATH)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)
            self.assertGreater(conn.execute("SELECT COUNT(*) FROM styles").fetchone()[0], 0)
            self.assertGreater(conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0], 0)
        finally:
            conn.close()

    def test_health_and_persistent_upload_routes(self):
        probe = app.UPLOADS / "probe.txt"
        probe.write_text("persistent media", encoding="utf-8")
        server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(f"{base_url}/api/health") as response:
                payload = json.load(response)
                self.assertEqual(payload, {"ok": True, "service": "bloom"})
                self.assertEqual(response.headers["Access-Control-Allow-Origin"], app.CORS_ORIGIN)
            with urlopen(f"{base_url}/uploads/probe.txt") as response:
                self.assertEqual(response.read(), b"persistent media")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
