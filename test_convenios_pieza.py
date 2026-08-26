# -*- coding: utf-8 -*-
"""Rat.IA · el logo real de banco en la pieza de convenios (26-ago-2026).

Pedido de Joaquín viendo la primera pieza publicada: "no puede ser que las
publicaciones de bancos no incluyan el logo oficial". El modelo NUNCA dibuja
el logo (ver la regla en convenios_pieza.py, no se negocia); en cambio se
reserva un badge vacío y se pega el archivo real encima con Pillow. Estas
pruebas no gastan créditos: no llaman a Kie ni a Anthropic.
"""
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image

import convenios_pieza as cp


class LogoDe(unittest.TestCase):
    def test_encuentra_el_logo_de_un_banco_conocido(self):
        ruta = cp.logo_de("Banco de Chile")
        self.assertIsNotNone(ruta)
        self.assertTrue(ruta.exists(), "el archivo del logo no existe en disco")

    def test_no_distingue_mayusculas_ni_espacios_de_mas(self):
        self.assertEqual(cp.logo_de("banco de chile"), cp.logo_de("Banco de Chile"))
        self.assertEqual(cp.logo_de("  BCI  "), cp.logo_de("BCI"))

    def test_cencosud_scotiabank_y_scotiabank_comparten_el_mismo_logo(self):
        self.assertEqual(cp.logo_de("Cencosud Scotiabank"), cp.logo_de("Scotiabank"))

    def test_un_comercio_sin_logo_curado_devuelve_none_sin_reventar(self):
        # "Clínica Dental 3Dent" es cola larga -- no hay (ni va a haber)
        # logo curado para cada comercio posible.
        self.assertIsNone(cp.logo_de("Clínica Dental 3Dent"))
        self.assertIsNone(cp.logo_de(""))
        self.assertIsNone(cp.logo_de(None))


class PegarLogoBadge(unittest.TestCase):
    def _base(self, color=(10, 10, 10)):
        img = Image.new("RGB", (1024, 1024), color)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def test_devuelve_un_png_valido_del_mismo_tamano(self):
        ruta = cp.logo_de("Banco de Chile")
        salida = cp.pegar_logo_badge(self._base(), ruta)
        img = Image.open(io.BytesIO(salida))
        self.assertEqual(img.size, (1024, 1024))
        self.assertEqual(img.format, "PNG")

    def test_el_badge_queda_arriba_a_la_derecha(self):
        # Sobre fondo negro puro, el badge blanco tiene que dejar píxeles
        # claros cerca de la esquina superior derecha y NINGUNO cerca de
        # la esquina inferior izquierda (donde no se pegó nada).
        ruta = cp.logo_de("Banco de Chile")
        salida = cp.pegar_logo_badge(self._base(), ruta)
        img = Image.open(io.BytesIO(salida)).convert("RGB")
        w, h = img.size
        esquina_sup_der = img.crop((round(w * 0.75), 0, w, round(h * 0.20)))
        esquina_inf_izq = img.crop((0, round(h * 0.80), round(w * 0.20), h))
        self.assertGreater(max(esquina_sup_der.getextrema()[0][1],
                               esquina_sup_der.getextrema()[1][1]), 200,
                           "no hay nada claro donde debería estar el badge")
        self.assertLess(max(esquina_inf_izq.getextrema()[0][1],
                            esquina_inf_izq.getextrema()[1][1]), 50,
                        "el badge se pegó en el lugar equivocado")

    def test_funciona_igual_sobre_fondo_blanco(self):
        ruta = cp.logo_de("Banco de Chile")
        salida = cp.pegar_logo_badge(self._base((250, 250, 250)), ruta)
        img = Image.open(io.BytesIO(salida))
        self.assertEqual(img.size, (1024, 1024))


class SinLogoNoRevientaLaPieza(unittest.TestCase):
    def test_con_ruta_none_devuelve_la_pieza_intacta(self):
        original = b"no es un PNG de verdad, pero no debe abrirse"
        self.assertEqual(cp._con_logo_si_corresponde(original, None), original)

    def test_un_pegado_que_falla_no_tumba_la_pieza(self):
        pieza = b"tampoco esto es un PNG"
        ruta_falsa = Path(__file__)  # existe, pero Image.open() le va a fallar
        resultado = cp._con_logo_si_corresponde(pieza, ruta_falsa, log=lambda m: None)
        self.assertEqual(resultado, pieza, "sin logo pegado, tiene que devolver la pieza original")


class PromptReservaElBadgeSoloConLogo(unittest.TestCase):
    def test_con_logo_reserva_el_area(self):
        p = cp._prompt("Banco de Chile", "Clínica Dental 3Dent", 80,
                       "Todos los días", "Hasta el 30-06-2027", "negro",
                       con_logo=True)
        self.assertIn("RESERVED BADGE AREA", p)

    def test_sin_logo_no_menciona_ningun_badge(self):
        # Si no hay logo para pegar, reservar el área sería dejar un hueco
        # vacío sin sentido en la pieza -- el diseño se queda 100% tipográfico.
        p = cp._prompt("Coopeuch", "Clínica Dental 3Dent", 80,
                       "Todos los días", "Hasta el 30-06-2027", "negro",
                       con_logo=False)
        self.assertNotIn("RESERVED BADGE AREA", p)

    def test_la_regla_de_no_dibujar_logos_sigue_siempre_presente(self):
        # Con o sin badge, el modelo nunca puede dibujar un logo por su
        # cuenta -- eso es lo que este archivo existe para evitar.
        for con_logo in (True, False):
            p = cp._prompt("Banco de Chile", "X", 50, "cond", "vig", "negro",
                           con_logo=con_logo)
            self.assertIn("NO DIBUJES NINGÚN LOGO", p)


if __name__ == "__main__":
    unittest.main(verbosity=1)
