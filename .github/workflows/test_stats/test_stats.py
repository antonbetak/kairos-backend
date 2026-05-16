import unittest
from uuid import UUID, uuid4
from types import SimpleNamespace
from unittest.mock import patch


from stats_service.app.services.estadisticas import (
    enviar_notificacion,
    registrar_tarea_creada,
)


class StatsServiceTests(unittest.TestCase):
    def test_enviar_notificacion_routes_correctly(self):
        user = uuid4()

        with patch(
            "stats_service.app.services.estadisticas.publicar_racha_actualizada",
            return_value=True,
        ) as racha_pub, patch(
            "stats_service.app.services.estadisticas.publicar_notificacion_creada",
            return_value=True,
        ) as notif_pub, patch(
            "stats_service.app.services.estadisticas.publicar_logro_desbloqueado",
            return_value=True,
        ) as logro_pub:
            self.assertTrue(
                enviar_notificacion(user, "T", "M", "racha", "racha.actualizada")
            )
            racha_pub.assert_called_once()

            self.assertTrue(
                enviar_notificacion(user, "T", "M", "tipo", "notificacion.creada")
            )
            notif_pub.assert_called_once()

            self.assertTrue(
                enviar_notificacion(user, "T", "M", "otro", "otro.routing")
            )
            logro_pub.assert_called_once()

    def test_registrar_tarea_creada_increments_counters(self):
        user = uuid4()

        estadistica = SimpleNamespace(
            tareas_creadas=0,
            tareas_completadas=0,
            porcentaje_cumplimiento=0,
            fecha_actualizacion=None,
        )

        class DummyDB:
            def commit(self):
                pass

            def refresh(self, obj):
                pass

        db = DummyDB()

        with patch(
            "stats_service.app.services.estadisticas.obtener_o_crear_estadistica_usuario",
            return_value=estadistica,
        ):
            result = registrar_tarea_creada(db, user)

        self.assertEqual(result.tareas_creadas, 1)


if __name__ == "__main__":
    unittest.main()
