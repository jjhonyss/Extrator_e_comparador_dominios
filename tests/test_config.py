import importlib
import os
import unittest
from pathlib import Path
from unittest.mock import patch


class ConfigTests(unittest.TestCase):
    def test_config_uses_environment_overrides(self):
        env = {
            "DOMAIN_GUARD_HOST": "0.0.0.0",
            "DOMAIN_GUARD_PORT": "8080",
            "DOMAIN_GUARD_DATA_DIR": str(Path("C:/domain-guard-data")),
            "DOMAIN_GUARD_ENABLE_OCR": "false",
            "DOMAIN_GUARD_ALLOWED_EXTENSIONS": "txt,pdf,csv",
        }

        import config

        with patch.dict(os.environ, env, clear=False):
            reloaded = importlib.reload(config)
            overridden = dict(reloaded.CONFIG)

        importlib.reload(config)

        self.assertEqual(overridden["HOST"], "0.0.0.0")
        self.assertEqual(overridden["PORT"], 8080)
        self.assertEqual(overridden["UPLOAD_DIR"], Path("C:/domain-guard-data") / "uploads")
        self.assertFalse(overridden["ENABLE_OCR"])
        self.assertEqual(overridden["ALLOWED_EXTENSIONS"], {".txt", ".pdf", ".csv"})


if __name__ == "__main__":
    unittest.main()
