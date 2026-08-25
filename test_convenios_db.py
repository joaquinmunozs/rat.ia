# -*- coding: utf-8 -*-
"""(Claude, 25-ago-2026) Persistencia de convenios en hector2_db."""
import os
import sys
import tempfile
import unittest
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")

import convenios_pangui as cp
import hector2_db


def _convenio(**over):
    base = dict(emisor="BancoEstado", comercio="Copec", categoria="Otros",
               descuento=20, titulo="t", canal=None, dia_semana="viernes",
               verificado_recientemente=True, dias_sin_verificar=None,
               vigencia_hasta=date(2026, 9, 1), texto="texto real",
               url_fuente="https://panguiapp.com/bancos/banco-estado")
    base.update(over)
    return cp.ConvenioPangui(**base)


class TestPersistenciaConvenios(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.con = hector2_db.abrir(self.tmp.name)

    def tearDown(self):
        self.con.close()
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_convenio_nuevo_no_existe_hasta_registrarlo(self):
        conv = _convenio()
        self.assertIsNone(hector2_db.obtener_convenio(self.con, conv.clave))
        hector2_db.registrar_convenio_nuevo(self.con, conv, "2026-08-25", 1000)
        fila = hector2_db.obtener_convenio(self.con, conv.clave)
        self.assertEqual(fila["emisor"], "BancoEstado")
        self.assertEqual(fila["primera_vista"], "2026-08-25")
        self.assertEqual(fila["publicado_en_instagram"], 0)

    def test_registrar_dos_veces_no_pisa_la_primera_vista(self):
        conv = _convenio()
        hector2_db.registrar_convenio_nuevo(self.con, conv, "2026-08-01", 1000)
        hector2_db.registrar_convenio_nuevo(self.con, conv, "2026-08-25", 2000)
        fila = hector2_db.obtener_convenio(self.con, conv.clave)
        self.assertEqual(fila["primera_vista"], "2026-08-01")

    def test_marcar_recordatorio_telegram(self):
        conv = _convenio()
        hector2_db.registrar_convenio_nuevo(self.con, conv, "2026-08-01", 1000)
        hector2_db.marcar_recordatorio_telegram(self.con, conv.clave, "2026-08-08", 2000)
        fila = hector2_db.obtener_convenio(self.con, conv.clave)
        self.assertEqual(fila["ultimo_recordatorio_telegram"], "2026-08-08")

    def test_marcar_publicado_instagram_y_ultima_semana(self):
        conv = _convenio()
        hector2_db.registrar_convenio_nuevo(self.con, conv, "2026-08-01", 1000)
        hector2_db.marcar_publicado_instagram(self.con, conv.clave, 2000)
        hector2_db.marcar_aviso_ultima_semana_ig(self.con, conv.clave, 3000)
        fila = hector2_db.obtener_convenio(self.con, conv.clave)
        self.assertEqual(fila["publicado_en_instagram"], 1)
        self.assertEqual(fila["aviso_ultima_semana_ig_enviado"], 1)

    def test_marcar_vencido(self):
        conv = _convenio()
        hector2_db.registrar_convenio_nuevo(self.con, conv, "2026-08-01", 1000)
        hector2_db.marcar_convenio_vencido(self.con, conv.clave, 2000)
        fila = hector2_db.obtener_convenio(self.con, conv.clave)
        self.assertEqual(fila["estado"], "vencido")

    def test_dos_convenios_distintos_no_se_pisan(self):
        a = _convenio(comercio="Copec")
        b = _convenio(comercio="McDonald's")
        hector2_db.registrar_convenio_nuevo(self.con, a, "2026-08-01", 1000)
        hector2_db.registrar_convenio_nuevo(self.con, b, "2026-08-02", 1000)
        self.assertIsNotNone(hector2_db.obtener_convenio(self.con, a.clave))
        self.assertIsNotNone(hector2_db.obtener_convenio(self.con, b.clave))
        self.assertNotEqual(a.clave, b.clave)


if __name__ == "__main__":
    unittest.main(verbosity=1)
