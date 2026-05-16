import unittest
from datetime import datetime, timezone


from task_service.app.services.due_warning import _as_utc


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
