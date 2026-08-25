# -*- coding: utf-8 -*-
"""Saca de la base TODAS las fichas de librerías y las deja descartadas.

    python limpiar_libros.py              # SIMULACIÓN
    python limpiar_libros.py --confirmar  # ejecuta de verdad

PEDIDO (25-ago-2026, Joaquín): "quites todos los libros de hector 2 y hector
en el grupo telegram y nunca mas avisaremos ofertas ni errores de precios
con ellos".

POR QUÉ NO ALCANZA CON SACARLOS DE `tiendas.py`
------------------------------------------------------------------------------
Quitar el dominio de la lista evita que la barrida los VUELVA A LEER, pero
las fichas ya guardadas siguen en `precios` con su historial. El vigilante
no consulta `tiendas.py` para decidir a quién avisar: recorre lo que hay en
la base. Sin este paso, Héctor seguiría mandando ofertas de libros durante
semanas con los precios que ya tenía cargados.

POR QUÉ `olvidar_url` Y NO UN DELETE A SECAS
------------------------------------------------------------------------------
`baseprecios.olvidar_url` borra la ficha de `precios`, `linea_base` y
`fallos` Y ADEMÁS la anota en `descartadas`. Esa constancia es la parte que
importa: sin ella, el descubrimiento del lunes siguiente volvería a meter
las mismas 56.500 fichas de Antártica y todo esto habría durado una semana.

EL BORRADO ES IRREVERSIBLE
------------------------------------------------------------------------------
Se pierde el historial de precios de esas fichas. Es lo pedido —"nunca
más"— y no hay forma de "pausar" una ficha en esta base como sí la hay en
MercadoLibre. Por eso el modo por defecto es SIMULACIÓN y hay que pasar
`--confirmar` a propósito.
"""
import argparse
import sys
from collections import Counter
from urllib.parse import urlparse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import baseprecios

# Los dominios que se sacaron de `tiendas.py` en el mismo pedido, más los
# que puedan haber quedado de descubrimientos viejos. Se listan explícitos
# en vez de leerlos de `tiendas.py`: justamente ya NO están ahí, y el punto
# es limpiar lo que quedó huérfano.
DOMINIOS_LIBROS = ("buscalibre.cl", "antartica.cl")


def _dominio(url):
    try:
        d = (urlparse(url).netloc or "").lower()
    except ValueError:
        return ""
    return d[4:] if d.startswith("www.") else d


def _es_libreria(url):
    d = _dominio(url)
    return any(d == x or d.endswith("." + x) for x in DOMINIOS_LIBROS)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--confirmar", action="store_true",
                    help="Borra de verdad. Sin esto, sólo cuenta.")
    args = ap.parse_args()

    con = baseprecios.abrir()

    urls = [f[0] for f in con.execute("SELECT DISTINCT url FROM precios").fetchall()]
    objetivo = [u for u in urls if _es_libreria(u)]

    print("URLs en la base: %d" % len(urls))
    print("De librerías:    %d" % len(objetivo))
    if objetivo:
        c = Counter(_dominio(u) for u in objetivo)
        for dom, n in c.most_common():
            print("   %-18s %d" % (dom, n))

    # Alertas ya emitidas de esas fichas: no se borran (son historial de lo
    # que SÍ se avisó en su momento), pero se cuentan para el reporte.
    alertas_libros = sum(
        1 for f in con.execute("SELECT url FROM alertas").fetchall()
        if _es_libreria(f[0]))
    print("Alertas históricas de librerías (no se tocan): %d" % alertas_libros)
    print()

    if not objetivo:
        print("Nada que limpiar.")
        con.close()
        return 0

    if not args.confirmar:
        print("SIMULACIÓN — no se borró nada. Corré con --confirmar.")
        con.close()
        return 0

    for n, url in enumerate(objetivo, 1):
        baseprecios.olvidar_url(con, url)
        if n % 5000 == 0:
            con.commit()
            print("   %d/%d borradas" % (n, len(objetivo)))
    con.commit()

    quedan = [f[0] for f in con.execute("SELECT DISTINCT url FROM precios").fetchall()
              if _es_libreria(f[0])]
    print()
    print("RESULTADO: %d borradas · quedan %d fichas de librería en la base"
          % (len(objetivo), len(quedan)))
    con.close()
    return 0 if not quedan else 1


if __name__ == "__main__":
    raise SystemExit(main())
