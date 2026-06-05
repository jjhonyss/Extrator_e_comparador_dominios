import unittest
from unittest.mock import patch

from app import RuntimeConfigError, validate_runtime_settings


class RuntimeValidationTests(unittest.TestCase):
    def test_validate_runtime_settings_rejects_invalid_port(self):
        with patch.dict("app.CONFIG", {"PORT": 70000}, clear=False):
            with self.assertRaises(RuntimeConfigError):
                validate_runtime_settings()

    def test_validate_runtime_settings_rejects_invalid_upload_size(self):
        with patch.dict("app.CONFIG", {"MAX_FILE_SIZE": 0}, clear=False):
            with self.assertRaises(RuntimeConfigError):
                validate_runtime_settings()


if __name__ == "__main__":
    unittest.main()
