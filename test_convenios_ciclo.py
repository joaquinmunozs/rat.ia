# -*- coding: utf-8 -*-
"""(Claude, 25-ago-2026) El ciclo de republicación de convenios: Telegram
recuerda cada semana, Instagram sólo avisa "nuevo" y "última semana" --
nunca la misma pieza repetida. Reglas aprobadas explícitamente por Joaquín.
"""
import sys
import unittest
from datetime import date, timedelta

sys.stdout.reconfigure(encoding="utf-8")

import convenios_ciclo as cc


def _estado(**over):
    base = dict(primera_vista=date(2026, 8, 1))
    base.update(over)
    return cc.EstadoConvenio(**base)


class TestImportaParaInstagram(unittest.TestCase):
    def test_bajo_30_no_importa_aunque_sea_marca_conocida(self):
        self.assertFalse(cc.importa_para_instagram(25, "McDonald's", True))

    def test_marca_importante_con_30_basta_sin_verificacion(self):
        self.assertTrue(cc.importa_para_instagram(30, "Copec", False))

    def test_marca_desconocida_necesita_ademas_verificado_reciente(self):
        self.assertFalse(cc.importa_para_instagram(40, "Ferretería Don Juan", False))
        self.assertTrue(cc.importa_para_instagram(40, "Ferretería Don Juan", True))

    def test_no_importa_case_sensitive(self):
        self.assertTrue(cc.importa_para_instagram(35, "COPEC", False))
        self.assertTrue(cc.importa_para_instagram(35, "mcdonald's", False))


class TestConvenioNuevo(unittest.TestCase):
    def test_nuevo_siempre_va_a_telegram(self):
        acc = cc.decidir_acciones(
            es_nuevo=True, descuento=20, comercio="Tienda Random",
            verificado_recientemente=False, vigencia_hasta=None,
            es_recurrente=False, estado=_estado(), ahora=date(2026, 8, 25))
        self.assertIn("telegram_nuevo", acc)
        self.assertNotIn("instagram_nuevo", acc)

    def test_nuevo_importante_va_a_los_dos(self):
        acc = cc.decidir_acciones(
            es_nuevo=True, descuento=40, comercio="Copec",
            verificado_recientemente=True, vigencia_hasta=date(2026, 9, 30),
            es_recurrente=False, estado=_estado(), ahora=date(2026, 8, 25))
        self.assertEqual(set(acc), {"telegram_nuevo", "instagram_nuevo"})


class TestRecordatorioTelegram(unittest.TestCase):
    def test_no_toca_antes_de_los_7_dias(self):
        acc = cc.decidir_acciones(
            es_nuevo=False, descuento=20, comercio="X", verificado_recientemente=False,
            vigencia_hasta=date(2026, 10, 1), es_recurrente=False,
            estado=_estado(primera_vista=date(2026, 8, 20)),
            ahora=date(2026, 8, 25))  # 5 días
        self.assertEqual(acc, [])

    def test_recuerda_a_los_7_dias(self):
        acc = cc.decidir_acciones(
            es_nuevo=False, descuento=20, comercio="X", verificado_recientemente=False,
            vigencia_hasta=date(2026, 10, 1), es_recurrente=False,
            estado=_estado(primera_vista=date(2026, 8, 18)),
            ahora=date(2026, 8, 25))  # 7 días
        self.assertIn("telegram_recordatorio", acc)

    def test_recurrente_espera_30_dias_no_7(self):
        estado = _estado(primera_vista=date(2026, 8, 18))
        acc = cc.decidir_acciones(
            es_nuevo=False, descuento=20, comercio="X", verificado_recientemente=False,
            vigencia_hasta=None, es_recurrente=True, estado=estado,
            ahora=date(2026, 8, 25))  # 7 días -- no alcanza para uno recurrente
        self.assertEqual(acc, [])

    def test_recurrente_recuerda_a_los_30_dias(self):
        estado = _estado(primera_vista=date(2026, 7, 20))
        acc = cc.decidir_acciones(
            es_nuevo=False, descuento=20, comercio="X", verificado_recientemente=False,
            vigencia_hasta=None, es_recurrente=True, estado=estado,
            ahora=date(2026, 8, 19))  # 30 días
        self.assertIn("telegram_recordatorio", acc)

    def test_cuenta_desde_el_ultimo_recordatorio_no_desde_el_inicio(self):
        estado = _estado(primera_vista=date(2026, 7, 1),
                         ultimo_recordatorio_telegram=date(2026, 8, 20))
        acc = cc.decidir_acciones(
            es_nuevo=False, descuento=20, comercio="X", verificado_recientemente=False,
            vigencia_hasta=date(2026, 12, 1), es_recurrente=False, estado=estado,
            ahora=date(2026, 8, 24))  # 4 días desde el ultimo, aunque hayan
                                      # pasado semanas desde el inicio
        self.assertEqual(acc, [])


class TestUltimaSemana(unittest.TestCase):
    def test_telegram_avisa_ultima_vez_en_la_ventana_de_7_dias(self):
        estado = _estado(primera_vista=date(2026, 8, 1))
        acc = cc.decidir_acciones(
            es_nuevo=False, descuento=20, comercio="X", verificado_recientemente=False,
            vigencia_hasta=date(2026, 8, 30), es_recurrente=False, estado=estado,
            ahora=date(2026, 8, 25))  # 5 días para vencer, y ya toca recordar
        self.assertIn("telegram_ultima_vez", acc)
        self.assertNotIn("telegram_recordatorio", acc)

    def test_instagram_avisa_ultima_semana_solo_si_salio_antes_en_ig(self):
        estado = _estado(primera_vista=date(2026, 8, 1), publicado_en_instagram=True)
        acc = cc.decidir_acciones(
            es_nuevo=False, descuento=40, comercio="Copec", verificado_recientemente=True,
            vigencia_hasta=date(2026, 8, 28), es_recurrente=False, estado=estado,
            ahora=date(2026, 8, 25))
        self.assertIn("instagram_ultima_semana", acc)

    def test_instagram_no_avisa_si_nunca_salio_en_ig(self):
        estado = _estado(primera_vista=date(2026, 8, 1), publicado_en_instagram=False)
        acc = cc.decidir_acciones(
            es_nuevo=False, descuento=40, comercio="Copec", verificado_recientemente=True,
            vigencia_hasta=date(2026, 8, 28), es_recurrente=False, estado=estado,
            ahora=date(2026, 8, 25))
        self.assertNotIn("instagram_ultima_semana", acc)

    def test_instagram_no_repite_el_aviso_de_ultima_semana(self):
        estado = _estado(primera_vista=date(2026, 8, 1), publicado_en_instagram=True,
                         aviso_ultima_semana_ig_enviado=True)
        acc = cc.decidir_acciones(
            es_nuevo=False, descuento=40, comercio="Copec", verificado_recientemente=True,
            vigencia_hasta=date(2026, 8, 28), es_recurrente=False, estado=estado,
            ahora=date(2026, 8, 26))
        self.assertNotIn("instagram_ultima_semana", acc)


class TestVencido(unittest.TestCase):
    def test_convenio_vencido_no_genera_ninguna_accion(self):
        estado = _estado(primera_vista=date(2026, 7, 1))
        acc = cc.decidir_acciones(
            es_nuevo=False, descuento=40, comercio="Copec", verificado_recientemente=True,
            vigencia_hasta=date(2026, 8, 20), es_recurrente=False, estado=estado,
            ahora=date(2026, 8, 25))
        self.assertEqual(acc, [])

    def test_recien_detectado_pero_ya_vencido_no_publica(self):
        # Puede pasar si el monitor estuvo caído y la pagina ya avanzo.
        acc = cc.decidir_acciones(
            es_nuevo=True, descuento=50, comercio="Copec", verificado_recientemente=True,
            vigencia_hasta=date(2026, 8, 20), es_recurrente=False, estado=_estado(),
            ahora=date(2026, 8, 25))
        self.assertEqual(acc, [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
