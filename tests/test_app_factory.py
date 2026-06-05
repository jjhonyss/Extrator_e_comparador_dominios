import importlib.util
import unittest


class AppFactoryTests(unittest.TestCase):
    def test_create_app_sets_upload_limit(self):
        if importlib.util.find_spec("flask") is None:
            self.skipTest("Flask nao instalado no interpretador atual")

        from app import app, create_app

        created = create_app()
        self.assertEqual(created.config["MAX_CONTENT_LENGTH"], app.config["MAX_CONTENT_LENGTH"])


if __name__ == "__main__":
    unittest.main()
