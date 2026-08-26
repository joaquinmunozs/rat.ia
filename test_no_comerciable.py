# -*- coding: utf-8 -*-
"""(Claude, 25-ago-2026) Gift cards, entradas y suscripciones: tampoco.

DE DONDE SALIO
==============================================================================
Verificando otro pendiente (hushpuppies.cl y vans.cl "descubren y miden 0%",
que resulto estar ya resuelto) aparecio esta ficha REAL en el catalogo:

    https://www.hushpuppies.cl/products/hpp-cinturon-hombre-hpmg-belt-bar-...
    JSON-LD: ProductGroup "Gift Card Cinturon Belt Bar Hush Puppies" $29.990

Una gift card no tiene precio: su precio ES su monto. Un cambio del monto por
defecto de la ficha se lee como una caida, y el suscriptor no puede aprovechar
nada -- comprar $10.000 en gift card cuesta $10.000.

Eso YA se filtraba en `hector2_filtro` (los reenvios del aliado) y NO del lado
de Hector. La misma asimetria que tenian los libros hasta el 25-ago.

EL BUG QUE APARECIO AL MUDAR EL PATRON
==============================================================================
El patron original traia `manga\\b` (por los comics) y `entrada[s]?\\b` (por
las entradas de concierto). Probado contra nombres reales de retail:

    "Polera Manga Larga Hombre Nike"      -> descartada por "Manga"
    "Mesa de Entrada Recibidor Madera"    -> descartada por "Entrada"

O sea que el filtro de ruido estaba borrando ropa y muebles. Copiarlo tal cual
a `baseprecios.evaluar` habria llevado ese descarte silencioso a TODO el
catalogo de Hector. Es la leccion #5 del 20-ago otra vez: "un regex de sanidad
puede descartar en silencio lo mas importante".
"""
import os
import sqlite3
import sys
import tempfile
import time
import unittest

sys.stdout.reconfigure(encoding="utf-8")

import baseprecios
import hector2_filtro

DIA = 86400


def _abrir_temporal(ruta):
    """Una base de prueba, SIN tocar `VIGIA_DB`.

    `baseprecios.abrir()` no acepta ruta: usa la global `RUTA`, que se fija
    al IMPORTARSE el modulo. El camino habitual en este repo es exportar
    `VIGIA_DB` antes del import (ver `probar_referencia.py`), y eso funciona
    en un script suelto pero NO en un archivo de pruebas: con
    `python -m unittest discover`, otro test ya importo `baseprecios` antes y
    la variable llega tarde. Comprobado -- el primer intento de este archivo
    hacia fallar el discover entero.

    Peor que fallar seria no fallar: sin el `assert` que traia, las pruebas
    habrian escrito sus filas en el `precios.db` real. Construir la conexion
    a mano saca el problema de raiz y no deja rastro en el entorno.
    """
    if os.path.exists(ruta):
        os.remove(ruta)
    con = sqlite3.connect(ruta)
    con.row_factory = sqlite3.Row
    con.executescript(baseprecios.ESQUEMA)
    baseprecios._migrar(con)
    return con


class TestNoSeDescartaCatalogoBueno(unittest.TestCase):
    """La mitad que importa: lo que NO se puede descartar."""

    ROPA_Y_MUEBLES = [
        "Polera Manga Larga Hombre Nike",
        "Camisa Manga Corta Lino Mujer",
        "Blusa manga globo",
        "Camiseta Hombre Sin Mangas",
        "Primera Capa Deportiva Hombre Manga Corta",
        "Polera Bebe Gatito Manga Larga",
        "Mesa de Entrada Recibidor Madera",
        "Puerta de Entrada Roble 90x200",
        "Zapatilla Authentic Negro Vans - 34.5",
        "Cortina Black Out Termica",
        # Ferreteria: "seguro" es una PIEZA, no una poliza. construmart.cl
        # mide el 100% de sus 9.886 fichas, asi que esto se habria notado.
        "Seguro de Puerta Infantil Pack 6",
        "Cerradura con Seguro Interior",
        "Casco Seguro Bicicleta Adulto",
        "Curso Agua Piscina Filtro",
        "Planchado Vapor Plancha Philips",
        "Revistero de Pared Metalico",
        "Ticketera Termica 80mm",
    ]

    def test_la_ropa_de_manga_larga_no_es_ruido(self):
        # Los seis primeros son nombres tomados de URLs reales del sitemap
        # de tricot.cl, no inventados.
        for nombre in self.ROPA_Y_MUEBLES:
            ruido, motivo = baseprecios.es_ruido(nombre)
            self.assertFalse(ruido, "%s se descarto por %r" % (nombre, motivo))

    def test_tampoco_en_el_filtro_del_aliado(self):
        # Los dos lados comparten el patron: si uno pasa, el otro tambien.
        for nombre in self.ROPA_Y_MUEBLES:
            ok, motivo = hector2_filtro.es_irrelevante(
                nombre, None, "https://www.falabella.com/p/1")
            self.assertFalse(ok, "%s se descarto por %r" % (nombre, motivo))


class TestSiSeDescartaLoQueNoEsProducto(unittest.TestCase):
    NO_COMERCIABLE = [
        ("Gift Card Cinturon Belt Bar Hush Puppies", "gift card"),
        ("Tarjeta de Regalo $50.000", "tarjeta de regalo"),
        ("Entradas Concierto Bad Bunny", "entradas"),
        ("Entrada al Estadio Nacional", "entrada"),
        ("Curso de Ingles Online", "curso de"),
        ("Suscripcion Anual Revista", "suscripcion"),
        ("Libro Cien Anos de Soledad", "libro"),
        ("Membresia Gimnasio Plan Anual", "membresia"),
        # La contraparte de los tres patrones acotados: la POLIZA y el
        # CURSO de verdad si tienen que caer.
        ("Seguro Automotriz Cobertura Total", "seguro automotriz"),
        ("Seguro de Vida Individual", "seguro de vida"),
        ("Curso Online de Excel", "curso online"),
        # Como nombra esto el retail chileno de verdad. Las tres primeras se
        # colaban con el patron heredado de `hector2_filtro`.
        ("Tarjeta Regalo Jumbo 20.000", "tarjeta regalo"),
        ("Vale Regalo Sodimac", "vale regalo"),
        ("eGift Card Cencosud", "egift card"),
        ("GiftCard Paris", "giftcard"),
    ]

    PRODUCTOS_DE_REGALO_QUE_SI_SE_VENDEN = [
        "Papel de Regalo Navideno 5m",
        "Bolsa de Regalo Kraft x10",
        "Caja de Regalo Carton",
        "Set de Regalo Perfume Mujer",
        "Mono de Regalo Autoadhesivo",
        # Una SIM prepago es un producto real: por eso NO se agrego
        # "tarjeta prepago" al patron.
        "Tarjeta Prepago Entel SIM",
        "Tarjeta Madre ASUS B550",
    ]

    def test_lo_que_solo_se_regala_no_es_una_gift_card(self):
        for nombre in self.PRODUCTOS_DE_REGALO_QUE_SI_SE_VENDEN:
            ruido, motivo = baseprecios.es_ruido(nombre)
            self.assertFalse(ruido, "%s se descarto por %r" % (nombre, motivo))

    def test_se_reconocen_y_dicen_por_que(self):
        for nombre, esperado in self.NO_COMERCIABLE:
            ruido, motivo = baseprecios.es_ruido(nombre)
            self.assertTrue(ruido, nombre)
            self.assertEqual(motivo, esperado, nombre)

    def test_sin_nombre_no_se_descarta_nada(self):
        # Sin nombre no se puede AFIRMAR que sea ruido. Descartar por las
        # dudas perderia fichas buenas.
        for nombre in (None, "", "   "):
            self.assertFalse(baseprecios.es_ruido(nombre)[0])


class TestElCorteVaDentroDeEvaluar(unittest.TestCase):
    """`evaluar` es la UNICA puerta por la que pasan la barrida (`vigia.py`)
    y la lista caliente (`vigilante.py`). Es la leccion del corte de libros:
    en cualquier otro lado queda una puerta abierta."""

    def setUp(self):
        self.ruta = os.path.join(tempfile.gettempdir(), "test_no_comerciable.db")
        self.con = _abrir_temporal(self.ruta)
        self.ahora = int(time.time())

    def tearDown(self):
        self.con.close()
        try:
            os.remove(self.ruta)
        except OSError:
            pass

    def _sembrar(self, url, nombre, precio, dias=30):
        for t in ("precios", "alertas"):
            self.con.execute("DELETE FROM %s WHERE url=?" % t, (url,))
        self.con.execute(
            "INSERT INTO precios (tienda, url, nombre, precio, visto_en, visto_hasta)"
            " VALUES (?,?,?,?,?,?)",
            ("hushpuppies.cl", url, nombre, precio,
             self.ahora - dias * DIA, self.ahora - 60))
        self.con.commit()

    def test_una_gift_card_con_caida_enorme_no_se_avisa(self):
        # El caso real, con una caida del 90% simulada encima.
        url = "https://www.hushpuppies.cl/products/hpp-cinturon-gift-card"
        nombre = "Gift Card Cinturon Belt Bar Hush Puppies"
        self._sembrar(url, nombre, 29_990)
        diag = {}
        det = baseprecios.evaluar(self.con, url, 2_999, ahora=self.ahora,
                                  nombre=nombre, tienda="hushpuppies.cl",
                                  diag=diag)
        self.assertIsNone(det)
        self.assertIn("no_comerciable:gift card", diag)

    def test_la_misma_caida_en_ropa_de_manga_larga_SI_se_avisa(self):
        # LA CONTRAPARTE. Sin esto, "descartar todo" pasaria la prueba de
        # arriba y nadie se enteraria hasta ver el canal mudo.
        url = "https://www.tricot.cl/camisa-hombre-lisa-manga-larga-104756.html"
        nombre = "Camisa Hombre Lisa Manga Larga"
        self._sembrar(url, nombre, 29_990)
        det = baseprecios.evaluar(self.con, url, 2_999, ahora=self.ahora,
                                  nombre=nombre, tienda="tricot.cl")
        self.assertIsNotNone(det)
        self.assertGreater(det["caida"], 0.85)

    def test_sin_nombre_el_corte_no_se_aplica(self):
        url = "https://www.hushpuppies.cl/products/sin-nombre"
        self._sembrar(url, "Zapato Cuero", 29_990)
        det = baseprecios.evaluar(self.con, url, 2_999, ahora=self.ahora,
                                  nombre=None, tienda="hushpuppies.cl")
        self.assertIsNotNone(det)


class TestUnSoloPatronParaLosDosLados(unittest.TestCase):
    def test_hector2_usa_exactamente_el_de_baseprecios(self):
        # Un numero, un solo lugar: dos copias del patron se habrian ido
        # separando, que es como empezo esta asimetria con los libros.
        self.assertIs(hector2_filtro.RUIDO_IRRELEVANTE,
                      baseprecios.RUIDO_NO_COMERCIABLE)


if __name__ == "__main__":
    unittest.main(verbosity=1)
