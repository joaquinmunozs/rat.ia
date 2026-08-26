# -*- coding: utf-8 -*-
"""Pruebas del carrusel de ofertas (26-ago-2026).

Cada una fija un bug REAL que apareció construyéndolo, no un caso inventado.
Ninguna gasta créditos ni llama a una API: las que necesitan una pieza usan
las que quedaron guardadas en `assets/muestras/`.
"""
import io
import os
import sys
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ratia_carrusel as C
import ratia_texto as T

MUESTRAS = Path(__file__).resolve().parent / "assets" / "muestras"


class RotacionDeTemplate(unittest.TestCase):
    """Joaquín la pidió CONSECUTIVA: 1, 2, 1, 2 — no al azar."""

    def test_alterna_y_arranca_en_1(self):
        self.assertEqual([C.template_de_turno(n) for n in range(6)],
                         [1, 2, 1, 2, 1, 2])

    def test_es_funcion_del_contador_no_de_un_estado(self):
        # Dos procesos con el mismo contador eligen el mismo template, y
        # reconstruir cuál tocaba es mirar cuántas van.
        self.assertEqual(C.template_de_turno(10), C.template_de_turno(10))


class NombreCorto(unittest.TestCase):
    """El respaldo sin IA: tiene que servir aunque la API esté caída."""

    def test_acorta_el_titulo_de_retail(self):
        r = T._nombre_corto_sin_ia(
            "Audífonos Inalámbricos Bluetooth 5.3 con Cancelación de Ruido")
        self.assertLessEqual(len(r.split()), 5)
        self.assertIn("Audífonos", r)

    def test_saca_medidas_y_codigos(self):
        r = T._nombre_corto_sin_ia("Aceite de Oliva 500ml X3 Extra Virgen")
        self.assertNotIn("500ml", r)
        self.assertNotIn("X3", r)

    def test_un_titulo_ya_corto_no_se_toca(self):
        # Sin llamar a la API: ya cumple, se devuelve igual.
        self.assertEqual(T.nombre_corto("Cafetera Oster"), "Cafetera Oster")

    def test_nunca_devuelve_vacio(self):
        # Un título hecho sólo de relleno igual tiene que dar algo.
        self.assertTrue(T._nombre_corto_sin_ia("de la con para sin"))


class Caption(unittest.TestCase):
    """Lo que Joaquín pidió el 26-ago: comercio sí, DM y link no."""

    def setUp(self):
        self.txt = T._caption_sin_ia("Audífonos Bluetooth", "Falabella",
                                     89990, 26990, "oferta")

    def test_nombra_el_comercio(self):
        self.assertIn("Falabella", self.txt)

    def test_no_pide_comentar_ni_manda_al_dm(self):
        bajo = self.txt.lower()
        for prohibido in ("dm", "comenta", "link", "http", "bio"):
            self.assertNotIn(prohibido, bajo,
                             "el caption no puede mencionar %r" % prohibido)

    def test_lleva_el_precio_en_formato_chileno(self):
        self.assertIn("$26.990", self.txt)

    def test_el_error_de_precio_se_anuncia_distinto(self):
        err = T._caption_sin_ia("Smart TV", "Ripley", 449990, 44999, "error")
        self.assertIn("rror", err)                 # "Error de precio"
        self.assertIn("#errordeprecio", err)


class DeteccionDelCirculo(unittest.TestCase):
    """El bug que pegó la foto encima del precio."""

    def _pieza(self, nombre):
        ruta = MUESTRAS / nombre
        if not ruta.exists():
            self.skipTest("falta la muestra %s" % nombre)
        return Image.open(ruta)

    def test_encuentra_el_circulo_y_no_la_barra(self):
        """La barra de precios es blanca Y MÁS ANCHA que el círculo.

        Buscar "el blanco más ancho" la elegía a ella y la foto terminaba
        sobre el precio. El círculo ocupa ~40-45% del ancho de la pieza; la
        barra, bastante más.
        """
        for nombre in ("oferta_1k.png", "oferta_2k.png"):
            with self.subTest(pieza=nombre):
                im = self._pieza(nombre)
                caja = C._circulo_de(im)
                self.assertIsNotNone(caja, "no encontró el círculo en %s" % nombre)
                ancho = caja[2] - caja[0]
                proporcion = ancho / im.size[0]
                self.assertTrue(0.35 <= proporcion <= 0.50,
                                "el círculo de %s salió al %.0f%% del ancho — "
                                "probablemente agarró la barra de precios"
                                % (nombre, proporcion * 100))

    def test_la_caja_es_cuadrada(self):
        """Es un círculo: alto y ancho tienen que coincidir. Medir el alto a
        pie lo unía con la barra que tiene pegada abajo."""
        im = self._pieza("oferta_1k.png")
        x0, y0, x1, y1 = C._circulo_de(im)
        self.assertAlmostEqual((x1 - x0), (y1 - y0), delta=3)

    def test_sin_circulo_devuelve_None_y_no_pega_nada(self):
        """Una imagen sin círculo no puede terminar con la foto puesta en
        cualquier parte: es mejor una pieza sin foto que una arruinada."""
        plana = Image.new("RGB", (1122, 1402), (10, 10, 10))
        self.assertIsNone(C._circulo_de(plana))

        buf = io.BytesIO()
        plana.save(buf, "PNG")
        original = buf.getvalue()
        foto = io.BytesIO()
        Image.new("RGB", (200, 200), (255, 0, 0)).save(foto, "PNG")
        salida = C.pegar_foto(original, foto.getvalue(), log=lambda *_: None)
        self.assertEqual(salida, original, "sin círculo, la pieza vuelve intacta")


class PegadoDeLaFoto(unittest.TestCase):
    def test_la_foto_queda_dentro_del_circulo(self):
        ruta = MUESTRAS / "oferta_1k.png"
        if not ruta.exists():
            self.skipTest("falta la muestra")
        original = ruta.read_bytes()
        caja = C._circulo_de(Image.open(ruta))

        roja = io.BytesIO()
        Image.new("RGB", (400, 400), (255, 0, 0)).save(roja, "PNG")
        salida = C.pegar_foto(original, roja.getvalue(), log=lambda *_: None)

        im = Image.open(io.BytesIO(salida)).convert("RGB")
        cx = (caja[0] + caja[2]) // 2
        cy = (caja[1] + caja[3]) // 2
        r, g, b = im.getpixel((cx, cy))
        self.assertTrue(r > 200 and g < 80 and b < 80,
                        "el centro del círculo tendría que ser la foto, es %s"
                        % ((r, g, b),))

        # Y la barra de precios NO puede haber quedado pintada.
        h = im.size[1]
        rb, gb, bb = im.getpixel((im.size[0] // 4, int(h * 0.83)))
        self.assertFalse(rb > 200 and gb < 80 and bb < 80,
                         "la foto invadió la barra de precios")


class ConfiguracionDeCosto(unittest.TestCase):
    """1K no es "peor calidad": es más barato Y da el ratio correcto."""

    def test_se_pide_1k(self):
        self.assertEqual(C.RESOLUCION, "1K")
        self.assertEqual(C.CREDITOS_POR_PIEZA, 6)

    def test_el_campo_de_la_imagen_es_input_urls(self):
        """Con `image_urls` la API ignora el template y genera desde cero —
        el bug que inventó el logo 'OfertasReales'."""
        fuente = Path(C.__file__).read_text(encoding="utf-8")
        self.assertIn('"input_urls"', fuente)
        self.assertNotIn('"image_urls"', fuente)

    def test_el_prompt_no_describe_el_diseno(self):
        """Describirle el diseño lo invita a re-crearlo. El prompt sólo
        enumera reemplazos."""
        for palabra in ("starburst", "background colour", "lime green"):
            self.assertNotIn(palabra.lower(), C.PROMPT.lower())


class CostoMensual(unittest.TestCase):
    def test_haiku_sale_centavos(self):
        c = T.costo_mensual_estimado(118)
        self.assertLess(c["usd"], 1.0, "los textos no deberían costar ni un dólar")
        self.assertEqual(c["piezas"], 118)

    def test_escala_lineal(self):
        self.assertAlmostEqual(T.costo_mensual_estimado(200)["usd"],
                               T.costo_mensual_estimado(100)["usd"] * 2, places=3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
