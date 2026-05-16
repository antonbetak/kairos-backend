import unittest
from types import SimpleNamespace


from notifications_service.app.services.notificaciones import (
    marcar_notificacion_leida,
    marcar_todas_como_leidas,
)


class NotificationsTests(unittest.TestCase):
    def test_marcar_notificacion_leida_sets_fields(self):
        notificacion = SimpleNamespace(leida=False, fecha_lectura=None)

        class DummyDB:
            def commit(self):
                pass

            def refresh(self, obj):
                pass

        db = DummyDB()

        result = marcar_notificacion_leida(db, notificacion)
        self.assertTrue(result.leida)
        self.assertIsNotNone(result.fecha_lectura)

    def test_marcar_todas_como_leidas_marks_all(self):
        n1 = SimpleNamespace(leida=False, fecha_lectura=None)
        n2 = SimpleNamespace(leida=False, fecha_lectura=None)

        class QueryMock:
            def __init__(self, data):
                self._data = data

            def filter(self, *args, **kwargs):
                return self

            def all(self):
                return self._data

        class DummyDB:
            def __init__(self, data):
                self._data = data

            def query(self, model):
                return QueryMock(self._data)

            def commit(self):
                pass

        db = DummyDB([n1, n2])

        marcar_todas_como_leidas(db, "user-id")
        self.assertTrue(all(n.leida for n in db._data))


if __name__ == "__main__":
    unittest.main()
