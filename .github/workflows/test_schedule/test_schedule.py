import sys
import unittest
from types import ModuleType
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEDULE_SERVICE_ROOT = REPO_ROOT / "schedule_service"
if str(SCHEDULE_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SCHEDULE_SERVICE_ROOT))

fake_pika = ModuleType("pika")
fake_pika.URLParameters = object
fake_pika.BlockingConnection = object
fake_pika.BasicProperties = object
fake_pika.DeliveryMode = type("DeliveryMode", (), {"Persistent": object()})
sys.modules.setdefault("pika", fake_pika)


class ScheduleSmokeTests(unittest.TestCase):
    def test_imports(self):
        # Simple smoke test to ensure module imports in CI
        import app.services.rabbitmq_publisher as pub  # noqa: F401
        import app.services.rabbitmq_consumer as cons  # noqa: F401

        self.assertTrue(hasattr(pub, "__name__"))
        self.assertTrue(hasattr(cons, "__name__"))


if __name__ == "__main__":
    unittest.main()
