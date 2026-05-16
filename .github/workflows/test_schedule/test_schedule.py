import unittest


class ScheduleSmokeTests(unittest.TestCase):
    def test_imports(self):
        # Simple smoke test to ensure module imports in CI
        import schedule_service.app.services.rabbitmq_publisher as pub  # noqa: F401
        import schedule_service.app.services.rabbitmq_consumer as cons  # noqa: F401

        self.assertTrue(hasattr(pub, "__name__"))
        self.assertTrue(hasattr(cons, "__name__"))


if __name__ == "__main__":
    unittest.main()
