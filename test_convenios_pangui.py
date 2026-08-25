# -*- coding: utf-8 -*-
"""(Claude, 25-ago-2026) El extractor de convenios de panguiapp.com, contra
HTML REAL bajado en vivo (no HTML inventado a mano) -- ver fixtures/.
"""
import io
import sys
import unittest
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")

import convenios_pangui as cp


def _html(nombre):
    with io.open("fixtures/%s" % nombre, encoding="utf-8", errors="replace") as f:
        return f.read()


class TestMcDonalds(unittest.TestCase):
    def setUp(self):
        self.html = _html("pangui_mcdonalds.html")

    def test_encuentra_las_4_ofertas(self):
        c = cp.extraer_convenios(self.html, "https://panguiapp.com/tiendas/mcdonald-s",
                                 comercio="McDonald's")
        self.assertEqual(len(c), 4)

    def test_lee_el_descuento_y_el_comercio(self):
        c = cp.extraer_convenios(self.html, "u", comercio="McDonald's")
        self.assertTrue(all(x.comercio == "McDonald's" for x in c))
        self.assertEqual(c[0].descuento, 40)

    def test_reconoce_al_emisor_lider_bci_dentro_del_bloque(self):
        c = cp.extraer_convenios(self.html, "u", comercio="McDonald's")
        emisores = {x.emisor for x in c}
        self.assertIn("BCI", emisores)

    def test_lee_el_dia_de_la_semana(self):
        c = cp.extraer_convenios(self.html, "u", comercio="McDonald's")
        dias = {x.dia_semana for x in c}
        self.assertIn("martes", dias)

    def test_lee_la_fecha_de_vencimiento(self):
        c = cp.extraer_convenios(self.html, "u", comercio="McDonald's")
        con_fecha = [x for x in c if x.vigencia_hasta]
        self.assertTrue(con_fecha)
        self.assertIn(date(2026, 9, 3), {x.vigencia_hasta for x in con_fecha})
        self.assertIn(date(2026, 8, 31), {x.vigencia_hasta for x in con_fecha})

    def test_distingue_verificado_hoy_de_sin_verificar(self):
        c = cp.extraer_convenios(self.html, "u", comercio="McDonald's")
        estados = {x.verificado_recientemente for x in c}
        self.assertIn(True, estados)
        con_dias = [x for x in c if x.dias_sin_verificar]
        self.assertTrue(any(x.dias_sin_verificar == 21 for x in con_dias))

    def test_la_clave_identifica_la_oferta_no_el_texto_legal_completo(self):
        c = cp.extraer_convenios(self.html, "u", comercio="McDonald's")
        claves = [x.clave for x in c]
        self.assertEqual(len(claves), len(set(claves)))  # todas distintas


class TestCruzVerde(unittest.TestCase):
    def test_dos_ofertas_semanales_con_su_propia_vigencia(self):
        # Real, y no obvio: "todos los lunes" NO implica indefinido -- las
        # dos ofertas de esta página recurren semanalmente Y tienen fecha
        # de término. `es_recurrente` (sin fecha de fin) es el caso
        # aparte que cubre `TestEsRecurrente` con un caso sintético, no
        # el típico.
        html = _html("pangui_cruzverde.html")
        c = cp.extraer_convenios(html, "u", emisor="Banco de Chile")
        self.assertEqual(len(c), 2)
        self.assertEqual({x.dia_semana for x in c}, {"lunes", "días"})
        self.assertTrue(all(x.vigencia_hasta for x in c))
        self.assertFalse(any(x.es_recurrente for x in c))


class TestEsRecurrente(unittest.TestCase):
    def _convenio(self, **over):
        base = dict(emisor="BancoEstado", comercio="Copec", categoria="Otros",
                   descuento=20, titulo="t", canal=None, dia_semana="viernes",
                   verificado_recientemente=True, dias_sin_verificar=None,
                   vigencia_hasta=None, texto="t", url_fuente="u")
        base.update(over)
        return cp.ConvenioPangui(**base)

    def test_sin_fecha_de_fin_y_con_dia_fijo_es_recurrente(self):
        self.assertTrue(self._convenio(vigencia_hasta=None, dia_semana="viernes")
                        .es_recurrente)

    def test_con_fecha_de_fin_no_es_recurrente_aunque_tenga_dia_fijo(self):
        self.assertFalse(self._convenio(vigencia_hasta=date(2026, 12, 31),
                                        dia_semana="viernes").es_recurrente)

    def test_sin_dia_fijo_no_es_recurrente(self):
        self.assertFalse(self._convenio(vigencia_hasta=None, dia_semana=None)
                         .es_recurrente)


class TestTurbus(unittest.TestCase):
    def test_dos_ofertas_con_vigencias_distintas(self):
        html = _html("pangui_turbus.html")
        c = cp.extraer_convenios(html, "u", comercio="Turbus")
        self.assertEqual(len(c), 2)
        fechas = {x.vigencia_hasta for x in c if x.vigencia_hasta}
        # El badge corto de Pangui ("Hasta 1 ene 2027") no siempre coincide
        # al día exacto con la prosa de la oferta ("hasta el 31 de
        # diciembre de 2026") -- se confía en el badge, que es el dato
        # estructurado y consistente en todo el sitio, no en la prosa
        # libre de cada comercio.
        self.assertIn(date(2026, 8, 31), fechas)
        self.assertIn(date(2027, 1, 1), fechas)

    def test_la_de_enero_dura_mas_de_una_semana(self):
        html = _html("pangui_turbus.html")
        c = cp.extraer_convenios(html, "u", comercio="Turbus")
        larga = [x for x in c if x.vigencia_hasta == date(2027, 1, 1)][0]
        dias_restantes = (larga.vigencia_hasta - date(2026, 8, 25)).days
        self.assertGreater(dias_restantes, 7)


class TestSinOfertas(unittest.TestCase):
    def test_html_sin_seccion_de_ofertas_no_revienta(self):
        self.assertEqual(cp.extraer_convenios("<html><body>nada</body></html>",
                                              "u", emisor="X"), [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
