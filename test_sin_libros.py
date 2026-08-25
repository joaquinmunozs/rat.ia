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




class TestMatrizDelWorkflowSincronizada(unittest.TestCase):
    """La matriz de `hector.yml` repite los dominios a mano. `tiendas.py`
    aborta con SystemExit si HECTOR_TIENDAS nombra uno que no existe, asi
    que una desincronizacion no da un aviso: revienta el shard entero.

    Paso de verdad el 25-ago: al sacar buscalibre.cl y antartica.cl de
    `tiendas.py`, los shards 0 y 3 quedaron rotos hasta que se saco tambien
    de la matriz.
    """

    def _matriz(self):
        import re
        with open(".github/workflows/hector.yml", encoding="utf-8") as f:
            texto = f.read()
        return [m.group(1) for m in re.finditer(r'tiendas:\s*"([^"]+)"', texto)]

    def test_todos_los_dominios_de_la_matriz_existen_en_tiendas_py(self):
        conocidas = {t["dominio"] for t in tiendas.TIENDAS}
        for i, lista in enumerate(self._matriz()):
            for dom in [d.strip() for d in lista.split(",") if d.strip()]:
                self.assertIn(dom, conocidas,
                              "shard %d nombra '%s', que no esta en tiendas.py "
                              "-- ese shard reventaria entero" % (i, dom))

    def test_la_matriz_cubre_todas_las_tiendas_sin_repetir(self):
        de_la_matriz = []
        for lista in self._matriz():
            de_la_matriz += [d.strip() for d in lista.split(",") if d.strip()]
        self.assertEqual(len(de_la_matriz), len(set(de_la_matriz)),
                         "hay un dominio repetido en dos shards")
        self.assertEqual(set(de_la_matriz), {t["dominio"] for t in tiendas.TIENDAS},
                         "la matriz y tiendas.py no cubren el mismo conjunto")

    def test_ninguna_libreria_quedo_en_la_matriz(self):
        for lista in self._matriz():
            self.assertNotIn("antartica.cl", lista)
            self.assertNotIn("buscalibre.cl", lista)


if __name__ == "__main__":
    unittest.main(verbosity=1)
