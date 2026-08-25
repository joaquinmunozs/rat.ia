# -*- coding: utf-8 -*-
import sys
import unittest
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")

import convenios_textos as t


class TestTextos(unittest.TestCase):
    def test_telegram_nuevo_trae_lo_esencial(self):
        txt = t.telegram_nuevo("BancoEstado", "Copec", 30, "Ahorra en bencina",
                               "viernes", date(2026, 9, 30), False,
                               "https://panguiapp.com/bancos/banco-estado")
        self.assertIn("BancoEstado", txt)
        self.assertIn("Copec", txt)
        self.assertIn("30%", txt)
        self.assertIn("viernes", txt)
        self.assertIn("30-09-2026", txt)
        self.assertIn("panguiapp.com", txt)

    def test_recurrente_no_muestra_fecha_fija(self):
        txt = t.telegram_nuevo("Mach", "KFC", 20, "t", "martes", None, True, "u")
        self.assertIn("Sin fecha de término", txt)
        self.assertNotIn("Vigente hasta", txt)

    def test_no_escapa_nada_raro_con_caracteres_html(self):
        txt = t.telegram_nuevo("Banco & Co", "Tienda <Test>", 10, "t", None,
                               None, False, "u")
        self.assertIn("&amp;", txt)
        self.assertIn("&lt;Test&gt;", txt)

    def test_recordatorio_dice_sigue_vigente(self):
        txt = t.telegram_recordatorio("BCI", "Wendy's", 25, date(2026, 10, 1),
                                      False, "u")
        self.assertIn("Recordatorio", txt)
        self.assertIn("25%", txt)

    def test_ultima_vez_avisa_urgencia(self):
        txt = t.telegram_ultima_vez("Santander", "Shell", 15, date(2026, 8, 30), "u")
        self.assertIn("Última semana", txt)

    def test_instagram_nuevo_sin_link_de_pangui(self):
        txt = t.instagram_nuevo("Copec", "BancoEstado", 30, "Ahorra en bencina",
                                "viernes", date(2026, 9, 30), False)
        self.assertNotIn("panguiapp.com", txt)
        self.assertIn("30%", txt)

    def test_instagram_ultima_semana(self):
        txt = t.instagram_ultima_semana("Copec", "BancoEstado", 30, date(2026, 8, 30))
        self.assertIn("Última semana", txt)
        self.assertIn("30%", txt)


if __name__ == "__main__":
    unittest.main(verbosity=1)
