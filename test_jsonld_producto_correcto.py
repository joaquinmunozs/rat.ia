# -*- coding: utf-8 -*-
"""El JSON-LD con varios productos: hay que leer EL de la ficha, no el primero.

EL BUG QUE ESTO CONGELA (24-ago-2026)
==============================================================================
`_de_jsonld` devolvía el primer `Product` con precio del bloque. Cuando una
ficha publica también sus "recomendados" en el mismo JSON-LD, ese primero
puede ser un producto ajeno: se termina midiendo el precio de otra cosa bajo
el nombre y la URL de esta.

Cómo se detectó (sin poder abrir la tienda, que bloquea el acceso): se
compararon los cambios de precio de una corrida real de `hector.yml`
(#32764015419). Lo normal es que casi todos los precios de origen sean
distintos — spdigital.cl tuvo 47 valores distintos en 49 cambios. `bata.cl`
tuvo 7 en 19, con el 63% arrancando del MISMO $22.990. Decenas de fichas
distintas informando el mismo precio es la firma de leer siempre el mismo
nodo. En la misma corrida salió un "$674 → $1.299" en una tienda de zapatos,
que tampoco es un precio real.

Por qué importa más allá de una tienda: un precio mal leído no queda en un
número feo, se convierte en una alerta falsa. El suscriptor entra, ve que la
oferta no existe, y deja de creerle al canal — el error caro que el propio
encabezado de `extractor.py` dice querer evitar.
"""
import json

import extractor


def _pagina(objetos):
    """HTML mínimo con un bloque JSON-LD. El relleno es para pasar el largo
    mínimo que exige `extraer` (una ficha real nunca pesa menos de 2 KB)."""
    return ("<html>" + "x" * 2100 +
            '<script type="application/ld+json">' +
            json.dumps(objetos) + "</script></html>")


RECOMENDADO = {
    "@type": "Product", "name": "Zapatilla recomendada",
    "url": "https://www.bata.cl/producto/recomendado-999",
    "offers": {"@type": "Offer", "price": "22990", "availability": "InStock"},
}
DE_LA_FICHA = {
    "@type": "Product", "name": "Bototo Cuero Hombre",
    "url": "https://www.bata.cl/producto/bototo-cuero-123",
    "offers": {"@type": "Offer", "price": "45990", "availability": "InStock"},
}


def test_elige_el_producto_de_la_ficha_y_no_el_primero():
    html = _pagina([RECOMENDADO, DE_LA_FICHA])
    r = extractor.extraer(html, "https://www.bata.cl/producto/bototo-cuero-123")
    assert r["precio"] == 45990
    assert r["nombre"] == "Bototo Cuero Hombre"


def test_sin_url_conserva_el_comportamiento_viejo():
    """Los llamadores que no pasan URL no deben cambiar de comportamiento."""
    html = _pagina([RECOMENDADO, DE_LA_FICHA])
    assert extractor.extraer(html)["precio"] == 22990


def test_url_que_no_calza_con_ninguno_no_rompe():
    """Si el JSON-LD no declara URLs, o ninguna calza, se sigue midiendo:
    quedarse sin precio sería peor que usar el criterio de siempre."""
    html = _pagina([RECOMENDADO, DE_LA_FICHA])
    assert extractor.extraer(html, "https://www.bata.cl/otra/cosa")["precio"] == 22990


def test_ficha_con_un_solo_producto_no_cambia():
    solo = {"@type": "Product", "name": "Unico",
            "url": "https://t.cl/p/1", "offers": {"price": "9990"}}
    html = _pagina(solo)
    assert extractor.extraer(html)["precio"] == 9990
    assert extractor.extraer(html, "https://t.cl/p/1")["precio"] == 9990


def test_variantes_del_mismo_producto_siguen_funcionando():
    """`hasVariant` son tallas/colores del MISMO producto (Shopify): eso ya
    andaba bien y no lo tiene que tocar el desempate por URL."""
    grupo = {
        "@type": "ProductGroup", "name": "Zapatilla",
        "url": "https://vans.cl/p/old-skool",
        "offers": None,
        "hasVariant": [
            {"@type": "Product", "name": "Old Skool 40",
             "offers": {"price": "59990", "availability": "InStock"}},
        ],
    }
    html = _pagina(grupo)
    assert extractor.extraer(html, "https://vans.cl/p/old-skool")["precio"] == 59990


def test_compara_ruta_sin_dominio_ni_query():
    """La URL guardada y la del JSON-LD suelen diferir en http/https, www o
    parámetros de campaña. Comparar la cadena cruda perdería la coincidencia
    justo cuando más se necesita."""
    ficha = dict(DE_LA_FICHA, url="http://bata.cl/producto/bototo-cuero-123/")
    html = _pagina([RECOMENDADO, ficha])
    r = extractor.extraer(
        html, "https://www.bata.cl/producto/bototo-cuero-123?utm_source=x")
    assert r["precio"] == 45990


# ── ESTAS PRUEBAS NO SE ESTABAN EJECUTANDO (Claude, 25-ago-2026) ────────────
#
# Están escritas como funciones sueltas al estilo pytest, y pytest no está
# instalado ni figura en `requirements.txt`. El proyecto corre sus pruebas con
# `python -m unittest <archivo>`, que sólo recoge métodos de `TestCase`:
# durante un día entero este archivo respondió "Ran 0 tests" -- que se lee
# igual que un éxito -- mientras las seis pruebas del arreglo del extractor
# nunca corrían. Es el mismo modo de falla del `if __name__` que había quedado
# a mitad de `test_hector2_aviso.py`: una prueba que no corre no avisa que no
# corre.
#
# Verificado a mano antes de enganchar: las seis pasan. Lo que faltaba era el
# enganche, no el arreglo del extractor.
#
# Se envuelven en vez de reescribirse para no tocar pruebas que ya funcionan.
import unittest as _unittest


class PruebasJsonLd(_unittest.TestCase):
    """Envoltorio para que `python -m unittest` recoja las funciones de arriba."""


for _nombre, _fn in sorted(globals().items()):
    if _nombre.startswith("test_") and callable(_fn):
        setattr(PruebasJsonLd, _nombre, (lambda f: lambda self: f())(_fn))
del _nombre, _fn


if __name__ == "__main__":
    _unittest.main(verbosity=1)
