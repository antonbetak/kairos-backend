import json
import sys
import unittest
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEDULE_SERVICE_ROOT = REPO_ROOT / "schedule_service"
if str(SCHEDULE_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SCHEDULE_SERVICE_ROOT))


class FakeBasicProperties:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeDeliveryMode:
    Persistent = "persistent"


class FakeChannel:
    def __init__(self):
        self.exchange_declare_calls = []
        self.basic_publish_calls = []

    def exchange_declare(self, **kwargs):
        self.exchange_declare_calls.append(kwargs)

    def basic_publish(self, **kwargs):
        self.basic_publish_calls.append(kwargs)


class FakeConnection:
    def __init__(self, parameters):
        self.parameters = parameters
        self.channel_obj = FakeChannel()
        self.closed = False

    def channel(self):
        return self.channel_obj

    def close(self):
        self.closed = True


class FakeURLParameters:
    def __init__(self, url):
        self.url = url


fake_pika = ModuleType("pika")
fake_pika.URLParameters = FakeURLParameters
fake_pika.BlockingConnection = FakeConnection
fake_pika.BasicProperties = FakeBasicProperties
fake_pika.DeliveryMode = FakeDeliveryMode
sys.modules["pika"] = fake_pika

import app.services.rabbitmq_publisher as pub  # noqa: E402


class ScheduleServiceTests(unittest.TestCase):
    def setUp(self):
        self.connections = []

        def _connection_factory(parameters):
            connection = FakeConnection(parameters)
            self.connections.append(connection)
            return connection

        pub.pika.URLParameters = FakeURLParameters
        pub.pika.BlockingConnection = _connection_factory
        pub.pika.BasicProperties = FakeBasicProperties
        pub.pika.DeliveryMode = FakeDeliveryMode

    def tearDown(self):
        self.connections.clear()

    def _last_publish(self):
        self.assertTrue(self.connections)
        channel = self.connections[-1].channel_obj
        self.assertTrue(channel.basic_publish_calls)
        self.assertTrue(channel.exchange_declare_calls)
        return channel.basic_publish_calls[-1], channel.exchange_declare_calls[-1]

    def test_publicar_horario_creado_emits_expected_event(self):
        result = pub.publicar_horario_creado(
            id_usuario="user-1",
            id_bloque="block-1",
            request_id="request-1",
            titulo="Bloque CI",
            descripcion="Descripcion CI",
            fecha_inicio="2026-05-19T10:00:00Z",
            fecha_fin="2026-05-19T11:00:00Z",
            tipo="focus",
            status="planned",
            google_access_token="google-access",
            google_refresh_token="google-refresh",
        )

        self.assertTrue(result)
        publish_call, exchange_call = self._last_publish()
        payload = json.loads(publish_call["body"])
        self.assertEqual(exchange_call["exchange"], pub.EXCHANGE)
        self.assertEqual(payload["event_type"], "Schedule.Created")
        self.assertEqual(payload["id_usuario"], "user-1")
        self.assertEqual(payload["id_bloque"], "block-1")
        self.assertEqual(payload["request_id"], "request-1")
        self.assertEqual(payload["google_access_token"], "google-access")
        self.assertEqual(payload["google_refresh_token"], "google-refresh")

    def test_other_schedule_wrappers_emit_expected_routing_keys(self):
        self.assertTrue(
            pub.publicar_horario_error("user-1", "error inesperado", "block-2")
        )
        publish_call, _ = self._last_publish()
        payload = json.loads(publish_call["body"])
        self.assertEqual(payload["event_type"], "Schedule.Error")
        self.assertEqual(payload["error"], "error inesperado")

        self.assertTrue(
            pub.publicar_bloque_completado("user-1", "block-3", "Bloque", "focus")
        )
        publish_call, _ = self._last_publish()
        payload = json.loads(publish_call["body"])
        self.assertEqual(payload["event_type"], "bloque.completado")
        self.assertEqual(payload["status"], "completed")

        self.assertTrue(
            pub.publicar_aviso_tarea_vencida(
                "user-1",
                "task-1",
                "Tarea",
                "Tarea vencida",
                fecha_vencimiento="2026-05-19T09:45:00Z",
            )
        )
        publish_call, _ = self._last_publish()
        payload = json.loads(publish_call["body"])
        self.assertEqual(payload["event_type"], "Task.DueWarning")
        self.assertEqual(payload["id_tarea"], "task-1")
        self.assertEqual(payload["mensaje"], "Tarea vencida")


if __name__ == "__main__":
    unittest.main()
