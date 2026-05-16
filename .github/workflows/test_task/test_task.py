import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
import os
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
TASK_SERVICE_ROOT = REPO_ROOT / "task_service"
if str(TASK_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(TASK_SERVICE_ROOT))

os.environ.setdefault("task_db_host", "localhost")
os.environ.setdefault("task_db_port", "5432")
os.environ.setdefault("task_db_user", "kairos")
os.environ.setdefault("task_db_password", "kairos")
os.environ.setdefault("task_db_name", "kairos")

fake_pika = ModuleType("pika")
fake_pika.URLParameters = object
fake_pika.BlockingConnection = object
fake_pika.BasicProperties = object
fake_pika.DeliveryMode = type("DeliveryMode", (), {"Persistent": object()})
sys.modules.setdefault("pika", fake_pika)


from app.services.due_warning import _as_utc


class TaskServiceTests(unittest.TestCase):
    def test_as_utc_converts_naive_and_aware(self):
        naive = datetime(2026, 1, 1, 12, 0, 0)
        aware = datetime(2026, 1, 1, 6, 0, 0, tzinfo=timezone.utc)

        n = _as_utc(naive)
        a = _as_utc(aware)

        self.assertEqual(n.tzinfo, timezone.utc)
        self.assertEqual(a.tzinfo, timezone.utc)


if __name__ == "__main__":
    unittest.main()
