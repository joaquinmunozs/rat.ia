# -*- coding: utf-8 -*-
"""(Claude, 25-ago-2026) Los dos bugs que reporto Joaquin en el topico de
errores de precio:

  1. "toallas que estaban en 120.000 (imposible) y hoy bajaron a 11000
     (ese siempre es precio normal)"
  2. "al apretar producto me lleva a una pagina roja que dice unauthorized"

Los datos son los REALES del anuncio que salio publicado (tabla `anuncios`
en produccion), no inventados.
"""
import os
import sys
import tempfile
import time
import unittest

sys.stdout.reconfigure(encoding="utf-8")

import hector2_db
import hector2_filtro as f
import reenviar_ofertas as R

# El link de imagen real del aviso de la toalla: lleva la URL del producto
# en base64 al final del path.
IMG_REAL = ("https://img2.ofertasshark.cl/NdV5iu9ZrniWKS6BjzS1xTqkE_LT3yOhEKCZsl_rqV8"
            "/rs:fit:800:800:1/f:jpg/"
            "aHR0cHM6Ly9jYW5ub25ob21lLmNsL3RvYWxsYS1kZS1iYW5vLWxvdy10d2lzdC13aGl0ZS5odG1s")
REDIRECTOR = "https://link.ofertasshark.cl/link/v2/redirect?e=BmsOnqVzH_msfxLZEey5"
URL_REAL = "https://cannonhome.cl/toalla-de-bano-low-twist-white.html"


class TestLinkQueSiAbre(unittest.TestCase):
    def test_rescata_la_url_real_del_base64_de_la_imagen(self):
        self.assertEqual(f.url_real_desde_imagen([IMG_REAL, REDIRECTOR]), URL_REAL)

    def test_prefiere_la_rescatada_sobre_el_redirector_roto(self):
        _t, url, _r = f.detectar_producto([IMG_REAL, REDIRECTOR])
        self.assertEqual(url, URL_REAL)

    def test_una_tienda_conocida_igual_le_gana_a_todo(self):
        tienda, url, _r = f.detectar_producto(
            [IMG_REAL, REDIRECTOR, "https://simple.ripley.cl/p/1"])
        self.assertEqual(tienda, "ripley.cl")

    def test_base64_ilegible_no_inventa_una_url(self):
        self.assertIsNone(f.url_real_desde_imagen(
            ["https://img2.ofertasshark.cl/x/f:jpg/no-es-base64-valido!!!"]))


class TestNoSePublicaSinReferenciaPropia(unittest.TestCase):
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

    def _toalla(self, **over):
        # Exactamente lo que traia el aviso real que salio mal.
        base = dict(url=URL_REAL, nombre="Cannon home Toalla De Baño Low Twist White",
                    tienda=None, precio_declarado=11990, precio_real=None,
                    referencia=None, referencia_declarada=139930,
                    caida_real=None, historico=[], imagen=IMG_REAL)
        base.update(over)
        return base

    def test_el_caso_real_de_la_toalla_ya_no_se_publica(self):
        # Nuestro sondeo dice que la toalla cuesta $11.990 -- el mismo precio
        # de "hoy". Eso es evidencia de que NO hay oferta.
        hector2_db.registrar_precio_visto(self.con, URL_REAL, 11990, "declarado_aliado")
        self.assertIsNone(R._armar_aviso(self._toalla(), self.con))

    def test_sin_ningun_dato_propio_tampoco_se_publica(self):
        # Antes caia al "antes" del aliado ($139.930) y publicaba un -91%
        # inventado. Ahora no publica nada.
        self.assertIsNone(R._armar_aviso(self._toalla(), self.con))

    def test_con_una_caida_REAL_si_se_publica(self):
        # La contraparte: si nuestro sondeo respalda la caida, sale.
        # (Claude, 25-ago) "Respaldar" pasó a ser la misma vara de Héctor:
        # 5 observaciones y 7 dias. Una sola ya no alcanza -- ver
        # `test_una_sola_observacion_no_es_referencia`.
        # Repartidas en 8 dias: cinco lecturas apretadas en el mismo dia
        # NO alcanzan, y eso esta fijado en `test_reloj_sin_respaldo`.
        ahora = int(time.time())
        for d in (12, 10, 8, 6, 4):
            hector2_db.registrar_precio_visto(self.con, URL_REAL, 40000,
                                              "declarado_aliado",
                                              visto_en=ahora - d * 86400)
        armado = R._armar_aviso(self._toalla(), self.con)
        self.assertIsNotNone(armado)
        texto, caida, precio, referencia, _h = armado
        self.assertEqual(referencia, 40000)   # el nuestro, NO los $139.930
        self.assertNotIn("139.930", texto)
        self.assertAlmostEqual(caida, 1 - 11990 / 40000, places=4)

    def test_nunca_se_publica_el_link_del_redirector(self):
        hector2_db.registrar_precio_visto(self.con, REDIRECTOR, 40000, "declarado_aliado")
        r = self._toalla(url=REDIRECTOR)
        self.assertIsNone(R._armar_aviso(r, self.con))


if __name__ == "__main__":
    unittest.main(verbosity=1)
