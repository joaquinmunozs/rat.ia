# -*- coding: utf-8 -*-
"""(Claude, 25-ago-2026) La foto real del producto para la pieza de Instagram.

Cierra el pendiente de la bitacora del 25-ago (tarde): "`_foto_de()` en el
selector devuelve vacio -- falta bajar la ficha y leer `og:image`".

POR QUE NO SE LEE `og:image` A MANO
==============================================================================
`extractor.extraer` ya lo hace Y valida el resultado. La validacion no es de
adorno: spdigital.cl publica de verdad

    <meta property="og:image" content="https:undefined">

que tiene forma de URL y host inexistente. Leido a mano se guarda como si
fuera una foto y el carrusel falla recien al publicar, cuando Instagram no
puede bajarla.

LA REGLA DE FONDO
==============================================================================
Ante cualquier problema se devuelve "" y NO una foto aproximada. Sin foto,
`ratia_pieza_ia.generar_pieza` se niega sola a armar la pieza. Una pieza de
Instagram con la foto de otro producto es peor que no publicar: es la version
visual del mismo error que Hector2 existe para evitar.
"""
import sys
import unittest

sys.stdout.reconfigure(encoding="utf-8")

import ratia_ig_selector as S
import ratia_seleccion as sel


def _candidato(url="https://www.vans.cl/products/zapatilla-x"):
    return sel.Candidato(
        url=url, tipo="oferta", fuente="hector", tienda="vans.cl",
        nombre="Zapatilla Authentic Negro Vans",
        precio=29990, referencia=59990, caida=0.5,
        primera_vez_vista=0, puntaje=1.0)


class TestFotoDelProducto(unittest.TestCase):
    def test_saca_la_imagen_de_la_ficha(self):
        html = '<meta property="og:image" content="https://vans.cl/foto.jpg">'
        foto = S._foto_de(_candidato(),
                          bajar_fn=lambda u: html,
                          extraer_fn=lambda h, u: {"imagen": "https://vans.cl/foto.jpg"})
        self.assertEqual(foto, "https://vans.cl/foto.jpg")

    def test_pasa_la_url_del_candidato_a_las_dos_funciones(self):
        # Si se bajara otra URL, la foto seria de otro producto -- que es
        # exactamente el error que esto tiene que no cometer.
        vistas = {}

        def bajar(u):
            vistas["bajada"] = u
            return "<html>"

        def extraer(h, u):
            vistas["extraida"] = u
            return {"imagen": "https://x/f.jpg"}

        c = _candidato("https://www.paris.cl/p/9")
        S._foto_de(c, bajar_fn=bajar, extraer_fn=extraer)
        self.assertEqual(vistas["bajada"], "https://www.paris.cl/p/9")
        self.assertEqual(vistas["extraida"], "https://www.paris.cl/p/9")

    def test_sin_url_no_baja_nada(self):
        def bajar(u):
            raise AssertionError("no deberia bajar nada sin URL")

        self.assertEqual(S._foto_de(_candidato(""), bajar_fn=bajar), "")

    def test_ficha_que_no_baja_devuelve_vacio(self):
        self.assertEqual(S._foto_de(_candidato(), bajar_fn=lambda u: None), "")

    def test_un_error_de_red_no_tumba_la_pasada(self):
        # El resto de los candidatos tiene que seguir.
        def explota(u):
            raise OSError("connection reset")

        self.assertEqual(S._foto_de(_candidato(), bajar_fn=explota), "")

    def test_ficha_sin_imagen_devuelve_vacio(self):
        self.assertEqual(
            S._foto_de(_candidato(), bajar_fn=lambda u: "<html>",
                       extraer_fn=lambda h, u: {"precio": 1000}), "")

    def test_extraer_que_devuelve_None_no_revienta(self):
        self.assertEqual(
            S._foto_de(_candidato(), bajar_fn=lambda u: "<html>",
                       extraer_fn=lambda h, u: None), "")

    def test_nunca_devuelve_None_sino_cadena(self):
        # `ratia_publicar` espera una cadena; un None se colaria hasta la
        # llamada a Blotato.
        for extraer in (lambda h, u: None,
                        lambda h, u: {"imagen": None},
                        lambda h, u: {}):
            foto = S._foto_de(_candidato(), bajar_fn=lambda u: "<html>",
                              extraer_fn=extraer)
            self.assertIsInstance(foto, str)


if __name__ == "__main__":
    unittest.main(verbosity=1)
