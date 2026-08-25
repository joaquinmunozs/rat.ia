# -*- coding: utf-8 -*-
"""(Claude, 25-ago-2026) "nunca mas avisaremos ofertas ni errores de precios
con ellos" -- pedido de Joaquin sobre las librerias.

El corte tiene que aguantar por las DOS puertas: la propia de Hector
(`baseprecios.evaluar`, que usan la barrida y la lista caliente) y el
reenvio del aliado (`hector2_filtro`).
"""
import sys
import unittest

sys.stdout.reconfigure(encoding="utf-8")

import baseprecios
import hector2_filtro as f
import tiendas


class TestCatalogoSinLibrerias(unittest.TestCase):
    def test_ninguna_tienda_de_libros_en_el_catalogo(self):
        self.assertEqual([t for t in tiendas.TIENDAS if t["rubro"] == "libros"], [])

    def test_los_dos_dominios_salieron(self):
        doms = {t["dominio"] for t in tiendas.TIENDAS}
        self.assertNotIn("antartica.cl", doms)
        self.assertNotIn("buscalibre.cl", doms)


class TestEsLibreria(unittest.TestCase):
    def test_reconoce_los_dominios_y_sus_subdominios(self):
        for u in ("https://www.antartica.cl/libro-x",
                  "https://antartica.cl/y",
                  "https://tienda.antartica.cl/z",
                  "https://www.buscalibre.cl/p/1"):
            self.assertTrue(baseprecios.es_libreria(u), u)

    def test_no_confunde_por_parecido(self):
        # El corte es en un punto: "noantartica.cl" no es Antartica.
        for u in ("https://noantartica.cl/x",
                  "https://www.falabella.com/p/1",
                  "https://antartica.cl.phishing.com/x"):
            self.assertFalse(baseprecios.es_libreria(u), u)

    def test_url_vacia_o_rara_no_revienta(self):
        for u in (None, "", "no-es-una-url"):
            self.assertFalse(baseprecios.es_libreria(u))


class TestHector2NoReenviaLibros(unittest.TestCase):
    def test_link_de_libreria_se_descarta_aunque_el_titulo_no_diga_libro(self):
        # El caso que el filtro por `rubro` ya NO atrapa: los dominios
        # salieron del catalogo, asi que llegan como tienda desconocida.
        ok, motivo = f.es_irrelevante("Oferta increible 70%", None,
                                      "https://www.antartica.cl/x")
        self.assertTrue(ok)
        self.assertIn("librería", motivo)

    def test_una_tienda_normal_sigue_pasando(self):
        ok, _m = f.es_irrelevante("Notebook HP Ryzen", None,
                                  "https://www.falabella.com/p/1")
        self.assertFalse(ok)

    def test_el_filtro_por_titulo_sigue_vivo_para_otras_tiendas(self):
        # Un libro vendido en una tienda que no es libreria igual se
        # descarta: esa barrera no se toco.
        ok, _m = f.es_irrelevante("Libro Cien Anos de Soledad -50%", None,
                                  "https://www.falabella.com/p/1")
        self.assertTrue(ok)

    def test_mensaje_completo_de_libreria_se_descarta(self):
        texto = ('Super oferta\n$20.000 -> $5.000 (75%)\n'
                 '<a href="https://www.antartica.cl/algo">PRODUCTO</a>')
        r = f.evaluar_mensaje(texto, "canal1", con_hector=None, verificar_vivo=False)
        self.assertEqual(r["veredicto"], "descartado")


if __name__ == "__main__":
    unittest.main(verbosity=1)
