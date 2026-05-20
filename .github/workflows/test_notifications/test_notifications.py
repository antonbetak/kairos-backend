import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy.exc import IntegrityError


REPO_ROOT = Path(__file__).resolve().parents[3]
NOTIFICATIONS_SERVICE_ROOT = REPO_ROOT / "notifications_service"
if str(NOTIFICATIONS_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(NOTIFICATIONS_SERVICE_ROOT))

os.environ.setdefault("notifications_db_user", "kairos")
os.environ.setdefault("notifications_db_password", "kairos")
os.environ.setdefault("notifications_db_host", "localhost")
os.environ.setdefault("notifications_db_port", "5432")
os.environ.setdefault("notifications_db_name", "kairos")

from app.models import NotificacionUsuario  # noqa: E402
from app.services.notificaciones import crear_notificacion  # noqa: E402
from app.services.notificaciones import marcar_notificacion_leida  # noqa: E402
from app.services.notificaciones import marcar_todas_como_leidas  # noqa: E402


def _criterion_matches(item, criterion) -> bool:
    column_name = getattr(getattr(criterion, "left", None), "key", None)
    if not column_name:
        return True

    criterion_text = str(criterion).lower()
    if " is false" in criterion_text:
        expected = False
    elif " is true" in criterion_text:
        expected = True
    else:
        expected = getattr(getattr(criterion, "right", None), "value", None)
    operator = getattr(criterion, "operator", None)
    actual = getattr(item, column_name)

    if operator is None:
        return actual == expected

    try:
        return bool(operator(actual, expected))
    except Exception:
        return actual == expected


class FakeQuery:
    def __init__(self, items):
        self._items = list(items)

    def filter(self, criterion):
        self._items = [item for item in self._items if _criterion_matches(item, criterion)]
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._items)

    def first(self):
        return self._items[0] if self._items else None


class FakeDB:
    def __init__(self):
        self.persisted: list[NotificacionUsuario] = []
        self.pending: list[NotificacionUsuario] = []

    def add(self, obj):
        self.pending.append(obj)

    def commit(self):
        request_ids = {item.request_id for item in self.persisted if item.request_id is not None}
        for item in self.pending:
            if item.request_id is not None and item.request_id in request_ids:
                self.pending.clear()
                raise IntegrityError("duplicate request_id", None, None)
            if item.request_id is not None:
                request_ids.add(item.request_id)
        self.persisted.extend(self.pending)
        self.pending.clear()

    def rollback(self):
        self.pending.clear()

    def refresh(self, obj):
        return obj

    def query(self, model):
        if model is NotificacionUsuario:
            return FakeQuery(self.persisted)
        return FakeQuery([])


class NotificationsTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()

    def tearDown(self):
        self.db.persisted.clear()
        self.db.pending.clear()

    def _payload(self, titulo="Titulo", mensaje="Mensaje", tipo="tipo"):
        return SimpleNamespace(titulo=titulo, mensaje=mensaje, tipo=tipo)

    def test_crear_notificacion_persists_and_returns_object(self):
        request_id = uuid4()
        user_id = uuid4()

        notificacion = crear_notificacion(
            self.db,
            user_id,
            self._payload(),
            request_id=request_id,
        )

        self.assertEqual(len(self.db.persisted), 1)
        self.assertEqual(notificacion.id_usuario, user_id)
        self.assertEqual(notificacion.request_id, request_id)
        self.assertEqual(notificacion.titulo, "Titulo")

    def test_crear_notificacion_reuses_existing_on_duplicate_request_id(self):
        request_id = uuid4()
        user_id = uuid4()

        first = crear_notificacion(
            self.db,
            user_id,
            self._payload("Uno", "Mensaje uno", "tipo"),
            request_id=request_id,
        )
        second = crear_notificacion(
            self.db,
            user_id,
            self._payload("Dos", "Mensaje dos", "tipo"),
            request_id=request_id,
        )

        self.assertIs(first, second)
        self.assertEqual(len(self.db.persisted), 1)

    def test_marcar_notificacion_leida_sets_fields(self):
        notificacion = NotificacionUsuario(
            id_notificacion=uuid4(),
            id_usuario=uuid4(),
            titulo="Titulo",
            mensaje="Mensaje",
            tipo="tipo",
            leida=False,
        )
        self.db.persisted.append(notificacion)

        result = marcar_notificacion_leida(self.db, notificacion)
        self.assertTrue(result.leida)
        self.assertIsNotNone(result.fecha_lectura)

    def test_marcar_todas_como_leidas_marks_all(self):
        user_id = uuid4()
        n1 = NotificacionUsuario(
            id_notificacion=uuid4(),
            id_usuario=user_id,
            titulo="Uno",
            mensaje="Mensaje uno",
            tipo="tipo",
            leida=False,
        )
        n2 = NotificacionUsuario(
            id_notificacion=uuid4(),
            id_usuario=user_id,
            titulo="Dos",
            mensaje="Mensaje dos",
            tipo="tipo",
            leida=False,
        )
        self.db.persisted.extend([n1, n2])

        resultado = marcar_todas_como_leidas(self.db, user_id)
        self.assertEqual(len(resultado), 2)
        self.assertTrue(all(n.leida for n in resultado))
        self.assertTrue(all(n.fecha_lectura is not None for n in resultado))


if __name__ == "__main__":
    unittest.main()
