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


class TestComercioRealEnPaginaDeBanco(unittest.TestCase):
    """(Claude, 26-ago-2026) En /bancos/{x} la cabecera repite el nombre del
    banco antes de la oferta real: "Banco de Chile 80% en Clínica Dental
    3Dent Más de 30 años...". Sin esto, `comercio` salía "Banco de Chile" --
    el mismo texto que `emisor`, publicado como "Banco de Chile + Banco de
    Chile" en una pieza real de Instagram. Los textos de abajo son EXACTOS,
    copiados de /bancos/banco-de-chile en vivo (no inventados)."""

    def test_saca_el_comercio_real_no_el_emisor_repetido(self):
        r = cp._comercio_real_pagina_banco(
            "Banco de Chile 80% en Clínica Dental 3Dent Más de 30 años "
            "cuidando sonrisas en Concepción.", "Banco de Chile")
        self.assertIsNotNone(r)
        comercio, resto = r
        self.assertEqual(comercio, "Clínica Dental 3Dent")
        self.assertTrue(resto.startswith("Clínica Dental 3Dent"))

    def test_no_se_come_una_apertura_de_marketing_capitalizada(self):
        # "Más" empieza con mayúscula por ser inicio de oración -- no es
        # parte del nombre del comercio, y antes del 26-ago se colaba.
        comercio = cp._acotar_nombre_comercio(
            "Clínica Dental 3Dent Más de 30 años cuidando sonrisas.")
        self.assertEqual(comercio, "Clínica Dental 3Dent")

    def test_conserva_conectores_dentro_del_nombre(self):
        comercio = cp._acotar_nombre_comercio(
            "Portal Ortodoncia de Chile Portal de Ortodoncia de Chile "
            "cuenta con sedes en Santiago.")
        self.assertEqual(comercio, "Portal Ortodoncia de Chile")

    def test_admite_un_digito_al_inicio_de_palabra(self):
        # "3Dent" no empieza con mayúscula (empieza con "3") -- sin admitir
        # dígitos, el nombre se cortaba en "Clínica Dental".
        comercio = cp._acotar_nombre_comercio("3Dent Más de 30 años.")
        self.assertEqual(comercio, "3Dent")

    def test_si_no_calza_el_patron_devuelve_none_no_revienta(self):
        # "Sobre el arancel de ONEDE..." no trae "{pct}% en" -- tiene que
        # caer con gracia al heurístico genérico, no lanzar ni devolver
        # basura.
        r = cp._comercio_real_pagina_banco(
            "Banco de Chile Sobre el arancel de ONEDENT.", "Banco de Chile")
        self.assertIsNone(r)

    def test_solo_aplica_cuando_la_cabecera_empieza_con_el_emisor(self):
        # Una página de TIENDA (`comercio` fijo) nunca debería llegar acá,
        # pero si algo la llamara igual, no debe inventar un match falso.
        r = cp._comercio_real_pagina_banco(
            "McDonald's 40% de descuento en la App.", "Banco de Chile")
        self.assertIsNone(r)

    def test_extraer_convenios_de_punta_a_punta_ya_no_duplica_el_emisor(self):
        html = (
            "<html><body>ofertas activas 1 ofertas activas · Actualizado "
            "hoy 80 % de descuento Salud Banco de Chile 80% en Clínica "
            "Dental 3Dent Más de 30 años cuidando sonrisas en Concepción. "
            "Verificado hoy Ver detalle</body></html>"
        )
        c = cp.extraer_convenios(html, "https://panguiapp.com/bancos/banco-de-chile",
                                 emisor="Banco de Chile")
        self.assertEqual(len(c), 1)
        self.assertEqual(c[0].comercio, "Clínica Dental 3Dent")
        self.assertNotEqual(c[0].comercio, c[0].emisor,
                            "el comercio no puede ser igual al emisor -- ese es el bug original")
        self.assertTrue(c[0].titulo.startswith("Clínica Dental 3Dent"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
