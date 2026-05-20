import os
import sys
import unittest
from pathlib import Path
from types import ModuleType
from uuid import uuid4
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
STATS_SERVICE_ROOT = REPO_ROOT / "stats_service"
if str(STATS_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(STATS_SERVICE_ROOT))

os.environ.setdefault("stats_db_user", "kairos")
os.environ.setdefault("stats_db_password", "kairos")
os.environ.setdefault("stats_db_host", "localhost")
os.environ.setdefault("stats_db_port", "5432")
os.environ.setdefault("stats_db_name", "kairos")

fake_pika = ModuleType("pika")
fake_pika.URLParameters = object
fake_pika.BlockingConnection = object
fake_pika.BasicProperties = object
fake_pika.DeliveryMode = type("DeliveryMode", (), {"Persistent": object()})
sys.modules.setdefault("pika", fake_pika)

from app.models import EstadisticaUsuario  # noqa: E402
from app.models import LogroUsuario  # noqa: E402
from app.models import RachaUsuario  # noqa: E402
from app.services.estadisticas import desbloquear_logro_si_no_existe  # noqa: E402
from app.services.estadisticas import enviar_notificacion  # noqa: E402
from app.services.estadisticas import obtener_o_crear_estadistica_usuario  # noqa: E402
from app.services.estadisticas import registrar_tarea_completada  # noqa: E402
from app.services.estadisticas import registrar_tarea_creada  # noqa: E402


def _criterion_matches(item, criterion) -> bool:
    column_name = getattr(getattr(criterion, "left", None), "key", None)
    if not column_name:
        return True

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
        self.storage = {
            EstadisticaUsuario: [],
            RachaUsuario: [],
            LogroUsuario: [],
        }

    def add(self, obj):
        self.storage[type(obj)].append(obj)

    def commit(self):
        return None

    def flush(self):
        return None

    def refresh(self, obj):
        return obj

    def query(self, model):
        return FakeQuery(self.storage.get(model, []))


class StatsServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()

    def tearDown(self):
        for items in self.db.storage.values():
            items.clear()

    def test_enviar_notificacion_routes_correctly(self):
        user = uuid4()

        with (
            patch(
                "app.services.estadisticas.publicar_racha_actualizada",
                return_value=True,
            ) as racha_pub,
            patch(
                "app.services.estadisticas.publicar_notificacion_creada",
                return_value=True,
            ) as notif_pub,
            patch(
                "app.services.estadisticas.publicar_logro_desbloqueado",
                return_value=True,
            ) as logro_pub,
        ):
            self.assertTrue(
                enviar_notificacion(user, "T", "M", "racha", "racha.actualizada")
            )
            racha_pub.assert_called_once()

            self.assertTrue(
                enviar_notificacion(user, "T", "M", "tipo", "notificacion.creada")
            )
            notif_pub.assert_called_once()

            self.assertTrue(enviar_notificacion(user, "T", "M", "otro", "otro.routing"))
            logro_pub.assert_called_once()

    def test_obtener_o_crear_estadistica_creates_and_reuses(self):
        user = uuid4()

        created = obtener_o_crear_estadistica_usuario(self.db, user)
        reused = obtener_o_crear_estadistica_usuario(self.db, user)

        self.assertIs(created, reused)
        self.assertEqual(len(self.db.storage[EstadisticaUsuario]), 1)

    def test_registrar_tarea_creada_increments_counters(self):
        user = uuid4()
        estadistica = EstadisticaUsuario(id_usuario=user, tareas_creadas=0, tareas_completadas=0)
        self.db.storage[EstadisticaUsuario].append(estadistica)

        result = registrar_tarea_creada(self.db, user)

        self.assertEqual(result.tareas_creadas, 1)
        self.assertEqual(result.porcentaje_cumplimiento, 0)

    def test_registrar_tarea_completada_creates_rewards_and_notifications(self):
        user = uuid4()
        estadistica = EstadisticaUsuario(
            id_usuario=user,
            tareas_creadas=1,
            tareas_completadas=0,
            porcentaje_cumplimiento=0,
        )
        racha = RachaUsuario(
            id_usuario=user,
            tipo="tareas",
            racha_actual=2,
            mejor_racha=2,
        )
        self.db.storage[EstadisticaUsuario].append(estadistica)
        self.db.storage[RachaUsuario].append(racha)

        with (
            patch("app.services.estadisticas.publicar_racha_actualizada", return_value=True) as racha_pub,
            patch("app.services.estadisticas.publicar_notificacion_creada", return_value=True) as notif_pub,
            patch("app.services.estadisticas.publicar_logro_desbloqueado", return_value=True) as logro_pub,
        ):
            result = registrar_tarea_completada(self.db, user)

        self.assertEqual(result.tareas_completadas, 1)
        self.assertEqual(result.porcentaje_cumplimiento, 100)
        self.assertEqual(racha.racha_actual, 3)
        self.assertEqual(racha.mejor_racha, 3)
        self.assertTrue(racha_pub.called)
        self.assertTrue(notif_pub.called)
        self.assertGreaterEqual(logro_pub.call_count, 2)
        self.assertEqual(
            {logro.codigo for logro in self.db.storage[LogroUsuario]},
            {"primera_tarea", "racha_3_tareas"},
        )

    def test_desbloquear_logro_no_duplica(self):
        user = uuid4()

        with patch("app.services.estadisticas.publicar_logro_desbloqueado", return_value=True):
            first = desbloquear_logro_si_no_existe(
                self.db,
                user,
                "codigo-ci",
                "Titulo CI",
                "Descripcion CI",
            )
            second = desbloquear_logro_si_no_existe(
                self.db,
                user,
                "codigo-ci",
                "Titulo CI",
                "Descripcion CI",
            )

        self.assertIs(first, second)
        self.assertEqual(len(self.db.storage[LogroUsuario]), 1)


if __name__ == "__main__":
    unittest.main()
