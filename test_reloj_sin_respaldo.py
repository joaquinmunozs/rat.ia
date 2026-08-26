# -*- coding: utf-8 -*-
"""(Claude, 25-ago-2026) El reloj Curren que Joaquin reporto en el topico
"Ofertas 70%", y el agujero que destapo.

EL SINTOMA
    "Curren Reloj Kree1904 Quartz Hombre Talla Unica
     $46.990 -> $14.091 (70.0%)
     Precio historico: $14.091  25/08
     sondeo propio de los ultimos 30 dias"

El mismo mensaje anunciaba -70% Y mostraba nuestro propio sondeo diciendo
que el reloj cuesta $14.091. Es el mismo defecto de la toalla Cannon Home
(ver `test_toalla_falsa.py`), que `f85c5ef` ya habia arreglado -- pero ese
arreglo nunca llego a produccion, y ademas dejaba una segunda puerta
abierta.

LA SEGUNDA PUERTA
    `precios_vistos` guarda el `precio_declarado` del aliado, y el aliado
    publica el mismo hallazgo en 2-3 canales a la vez (bitacora del 20-ago).
    Bastaba UNA observacion mayor -- aunque fuera de hace un minuto, o de
    hace 200 dias -- para que ese numero se convirtiera en "nuestra"
    referencia. O sea: el ancla inflada del aliado volvia a entrar por la
    puerta de atras.

LA VARA
    La misma que `baseprecios.evaluar` le exige a Hector: 5 observaciones y
    7 dias, dentro de la ventana de 30. Decision de Joaquin (25-ago), sobre
    la alternativa mas blanda de 2 observaciones en dias distintos.
"""
import os
import sys
import tempfile
import time
import unittest

sys.stdout.reconfigure(encoding="utf-8")

import baseprecios
import hector2_db
import reenviar_ofertas as R

# Tienda fuera del catalogo de Hector: es el caso en que la referencia se
# deriva del sondeo propio, que es justo donde estaba el agujero.
URL = "https://cannonhome.cl/curren-reloj-kree1904.html"
DIA = 86400


class _ConBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.con = hector2_db.abrir(self.tmp.name)
        self.ahora = int(time.time())

    def tearDown(self):
        self.con.close()
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def _reloj(self, **over):
        # Los numeros REALES del aviso que salio publicado.
        base = dict(url=URL, nombre="Curren Reloj Kree1904 Quartz Hombre Talla Unica",
                    tienda=None, precio_declarado=14091, precio_real=None,
                    referencia=None, referencia_declarada=46990,
                    caida_real=None, historico=[], imagen="")
        base.update(over)
        return base

    def _ver(self, precio, hace_dias):
        hector2_db.registrar_precio_visto(
            self.con, URL, precio, "declarado_aliado",
            visto_en=self.ahora - int(hace_dias * DIA))


class TestUnaObservacionNoEsUnaReferencia(_ConBase):
    def test_una_sola_observacion_no_es_referencia(self):
        # El caso C de la reproduccion: publicaba -70,0% contra $46.990.
        self._ver(46990, 2)
        self.assertIsNone(R._armar_aviso(self._reloj(), self.con))

    def test_el_ancla_del_aliado_no_entra_por_la_puerta_de_atras(self):
        # El caso E: el aliado publica en dos canales con un minuto de
        # diferencia y el primero se volvia "nuestra" referencia.
        self._ver(46990, 1.0 / 1440)
        self.assertIsNone(R._armar_aviso(self._reloj(), self.con))

    def test_cinco_observaciones_apretadas_en_tres_dias_no_alcanzan(self):
        # Cantidad sin tiempo no es historia: son cinco veces el mismo dia.
        for d in (3, 3, 2, 1, 0):
            self._ver(46990, d)
        self.assertIsNone(R._armar_aviso(self._reloj(), self.con))

    def test_cuatro_observaciones_bien_repartidas_tampoco(self):
        # Tiempo sin cantidad tampoco: le falta una para la vara de Hector.
        for d in (20, 14, 8, 2):
            self._ver(46990, d)
        self.assertIsNone(R._armar_aviso(self._reloj(), self.con))

    def test_con_respaldo_de_verdad_SI_se_publica(self):
        # LA CONTRAPARTE. Sin esta prueba, "no publicar nunca" pasaria
        # todas las demas.
        for d in (10, 8, 6, 4, 2):
            self._ver(46990, d)
        armado = R._armar_aviso(self._reloj(), self.con)
        self.assertIsNotNone(armado)
        _texto, caida, precio, referencia, _h = armado
        self.assertEqual(precio, 14091)
        self.assertEqual(referencia, 46990)
        self.assertAlmostEqual(caida, 1 - 14091 / 46990, places=4)

    def test_la_vara_es_la_de_hector_no_una_propia(self):
        # Un numero, un solo lugar: si alguien cambia baseprecios, esto
        # cambia con el. Es lo que evita que Hector2 derive su propia vara.
        self.assertEqual(baseprecios.MIN_OBSERVACIONES, 5)
        self.assertEqual(baseprecios.DIAS_MINIMOS_HISTORIAL, 7)


class TestLaVentanaDeTreintaDias(_ConBase):
    def test_una_observacion_de_hace_200_dias_no_se_usa(self):
        # El caso D. El mensaje dice "sondeo propio de los ultimos 30 dias"
        # y la consulta no tenia ninguna condicion de fecha.
        self._ver(46990, 200)
        self.assertIsNone(R._armar_aviso(self._reloj(), self.con))

    def test_historico_propio_no_devuelve_lo_de_fuera_de_la_ventana(self):
        self._ver(46990, 200)
        self._ver(30000, 5)
        visto = hector2_db.historico_propio(
            self.con, URL, dias=baseprecios.VENTANA_HISTORIAL_DIAS,
            ahora=self.ahora)
        self.assertEqual([p for p, _ in visto], [30000])

    def test_el_sondeo_que_se_publica_respalda_lo_que_el_mensaje_afirma(self):
        # Cinco observaciones dentro de la ventana y una vieja fuera: la
        # vieja no puede aparecer en un mensaje que dice "ultimos 30 dias".
        for d in (10, 8, 6, 4, 2):
            self._ver(46990, d)
        self._ver(99999, 120)
        armado = R._armar_aviso(self._reloj(), self.con)
        self.assertIsNotNone(armado)
        texto, _c, _p, referencia, hist = armado
        self.assertEqual(referencia, 46990)
        self.assertNotIn("99.999", texto)
        self.assertTrue(all(p != 99999 for p, _ in hist))


class TestRespaldoPropio(_ConBase):
    def test_cuenta_observaciones_y_dias_dentro_de_la_ventana(self):
        for d in (10, 8, 6, 4, 2):
            self._ver(46990 + int(d), d)
        obs, dias = hector2_db.respaldo_propio(
            self.con, URL, dias=baseprecios.VENTANA_HISTORIAL_DIAS,
            ahora=self.ahora)
        self.assertEqual(obs, 5)
        self.assertAlmostEqual(dias, 8.0, places=1)

    def test_no_cuenta_lo_de_fuera_de_la_ventana(self):
        self._ver(46990, 200)
        obs, dias = hector2_db.respaldo_propio(
            self.con, URL, dias=baseprecios.VENTANA_HISTORIAL_DIAS,
            ahora=self.ahora)
        self.assertEqual(obs, 0)
        self.assertEqual(dias, 0.0)

    def test_sin_nada_devuelve_cero_y_no_revienta(self):
        obs, dias = hector2_db.respaldo_propio(self.con, URL, ahora=self.ahora)
        self.assertEqual((obs, dias), (0, 0.0))

    def test_cuenta_filas_no_precios_distintos(self):
        # `historico_propio` agrupa POR PRECIO; `respaldo_propio` NO debe
        # hacerlo, o cinco lecturas del mismo precio contarian como una.
        for d in (10, 9, 8, 7, 6):
            self._ver(46990, d)
        obs, _dias = hector2_db.respaldo_propio(
            self.con, URL, dias=baseprecios.VENTANA_HISTORIAL_DIAS,
            ahora=self.ahora)
        self.assertEqual(obs, 5)
        visto = hector2_db.historico_propio(
            self.con, URL, dias=baseprecios.VENTANA_HISTORIAL_DIAS,
            ahora=self.ahora)
        self.assertEqual(len(visto), 1)


if __name__ == "__main__":
    unittest.main(verbosity=1)
