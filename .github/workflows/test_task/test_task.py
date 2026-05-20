import os
import sys
import unittest
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from types import ModuleType
from uuid import uuid4
from unittest.mock import patch


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

from app.models import Tarea  # noqa: E402
from app.services.due_warning import _as_utc  # noqa: E402
from app.services.due_warning import verificar_vencimientos_pendientes  # noqa: E402


class FakeResult:
    def __init__(self, items):
        self._items = list(items)

    def scalars(self):
        return self

    def all(self):
        return list(self._items)


class FakeDB:
    def __init__(self, tasks):
        self.tasks = tasks
        self.commits = 0
        self.closed = False

    def execute(self, query):
        return FakeResult(self.tasks)

    def commit(self):
        self.commits += 1

    def rollback(self):
        return None

    def close(self):
        self.closed = True


class TaskServiceTests(unittest.TestCase):
    def setUp(self):
        self.tasks: list[Tarea] = []

    def tearDown(self):
        self.tasks.clear()

    def test_as_utc_converts_naive_and_aware(self):
        naive = datetime(2026, 1, 1, 12, 0, 0)
        aware = datetime(2026, 1, 1, 6, 0, 0, tzinfo=timezone.utc)

        n = _as_utc(naive)
        a = _as_utc(aware)

        self.assertEqual(n.tzinfo, timezone.utc)
        self.assertEqual(a.tzinfo, timezone.utc)

    def test_verificar_vencimientos_pendientes_marks_warning_and_expired(self):
        ahora = datetime.now(timezone.utc)
        warning_task = Tarea(
            id_tarea=uuid4(),
            id_usuario="user-warning",
            titulo="Tarea warning",
            descripcion="Descripcion warning",
            completada=False,
            due_at=ahora + timedelta(minutes=10),
        )
        expired_task = Tarea(
            id_tarea=uuid4(),
            id_usuario="user-expired",
            titulo="Tarea expired",
            descripcion="Descripcion expired",
            completada=False,
            due_at=ahora - timedelta(minutes=1),
        )
        self.tasks.extend([warning_task, expired_task])

        fake_db = FakeDB(self.tasks)

        with (
            patch("app.services.due_warning.SessionLocal", return_value=fake_db),
            patch("app.services.due_warning.publicar_tarea_due_warning", return_value=True) as warning_pub,
            patch("app.services.due_warning.publicar_tarea_vencida", return_value=True) as expired_pub,
        ):
            verificar_vencimientos_pendientes()

        self.assertIsNotNone(warning_task.due_warning_sent_at)
        self.assertIsNotNone(expired_task.due_expired_sent_at)
        self.assertEqual(fake_db.commits, 1)
        self.assertTrue(fake_db.closed)
        warning_pub.assert_called_once()
        expired_pub.assert_called_once()


if __name__ == "__main__":
    unittest.main()
