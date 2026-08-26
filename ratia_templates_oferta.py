# -*- coding: utf-8 -*-
"""Rat.IA · la slide 1 del carrusel de oferta, compuesta sobre los templates
reales de Joaquín — con código, sin pasar por un modelo de imagen.

CÓMO ESTÁ ARMADO EL CARRUSEL (26-ago-2026, definido por Joaquín)
==============================================================================
Dos slides, y los templates rotan de forma consecutiva entre publicaciones:

    TEMPLATE 1 → slide 1 fondo NEGRO   + slide 2 fondo BLANCO
    TEMPLATE 2 → slide 1 fondo BLANCO  + slide 2 fondo NEGRO

La slide 2 es fija: se pega tal cual, nunca se regenera. La slide 1 es la que
lleva los datos del producto, donde el template trae los marcadores
`{NOMBRE PRODUCTO}`, `{¡PORCENTAJE DESCUENTO OFF!}`, `{PRODUCTO}`,
`{$PRECIO ANTIGUO}`, `{$PRECIOACTUAL}` y `{-PORCENTAJE DESCUENTO%}`.

POR QUÉ ESTO NO PASA POR gpt-image-2
==============================================================================
El argumento para generar la pieza con IA (24-ago) era que la versión
compuesta con Pillow quedaba fea: la tipografía dibujada a mano no se acercaba
a lo que hace un diseñador. **Ese argumento se cayó cuando Joaquín hizo el
diseño él mismo.** El template ya es de diseñador; lo único que falta es
escribir cuatro textos en posiciones conocidas, y eso el código lo hace exacto.

Lo que se gana:

  · El precio que sale es EXACTAMENTE el que entra. Un modelo de imagen puede
    escribir $89.900 donde iba $89.990, y en una oferta que se publica sola
    eso es un precio equivocado anunciado al público.
  · El círculo blanco de `{PRODUCTO}` deja de ser un riesgo. Es un hueco
    esperando a que algo lo llene, y un modelo de imagen SIEMPRE llena: el
    24-ago inventó un frasco entero con claims de producto ("prensado en
    frío", "100% natural") que no existían. Acá se pega la foto real y punto.
  · No gasta créditos ni espera 30-60 s por pieza.
  · No hace falta la verificación de precios con Anthropic, que existía sólo
    para atajar los errores del modelo.

Se conserva `ratia_pieza_ia.py` para comparar; la decisión de cuál usar es de
Joaquín.

LAS COORDENADAS SALEN DE MEDIR EL TEMPLATE, NO DE ESTIMARLAS
==============================================================================
Cada caja se midió por análisis de píxeles sobre el PNG real (buscando las
zonas blancas, lima y de texto). Si Joaquín cambia el template, se vuelven a
medir con el mismo método en vez de moverlas a ojo.
"""
from __future__ import annotations

import io
import os
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent
TEMPLATES = Path(os.environ.get("RATIA_TEMPLATES_DIR", AQUI / "assets" / "templates"))
FUENTES = Path(os.environ.get("RATIA_FUENTES_DIR", AQUI / "assets" / "fuentes"))

LADO = (1024, 1280)          # 4:5, el formato vertical de feed de Instagram
LIMA = (188, 213, 48)
ROJO_TACHADO = (200, 45, 45)

# ── Zonas de TEXTO, fijas: son las mismas en los dos templates ────────────
CAJA_TITULO = (57, 150, 967, 232)     # {NOMBRE PRODUCTO}
CAJA_OFF = (57, 232, 967, 405)        # {¡PORCENTAJE DESCUENTO OFF!}, hasta 2 líneas

# Las dos cajas se borran de una sola pasada y SIN HUECO entre ellas: cuando
# se tapaban por separado (232 y 240) quedaba una franja de 8 px sin pintar, y
# por ahí asomaba el borde superior del marcador `{¡PORCENTAJE` — visible en
# el template claro, donde el resto gris contrasta con el fondo.
ZONA_TEXTO_SUP = (CAJA_TITULO[0] - 6, CAJA_TITULO[1] - 12,
                  CAJA_TITULO[2], CAJA_OFF[3])

MARGEN_IZQ = 57

# ── Geometría de cada template, MEDIDA sobre el PNG real ─────────────────
#
# Los dos templates no son la misma imagen con los colores invertidos: la
# barra de precios y el cuadro del porcentaje no arrancan en la misma fila, y
# el lima tampoco es el mismo (#AAD804 vs #A4C70B). Con constantes
# compartidas, lo que calzaba en uno dejaba el marcador `{$PRECIO ANTIGUO}`
# asomando por arriba en el otro — pasó en la primera prueba.
#
# Los valores salen de medir columnas SIN TEXTO encima (x=70 para la barra,
# x=745 para el cuadro, x=512 para el círculo): muestrear donde hay letras
# devuelve el color de la letra, no el de la pieza.
#
# Si Joaquín cambia un template, se vuelven a medir con `medir_template()`
# más abajo, que imprime exactamente estos números.
GEOMETRIA = {
    1: {  # slide 1 sobre fondo NEGRO
        "circulo": (299, 470, 726, 897),
        "barra":   (56, 903, 708, 1145),
        "cuadro":  (712, 900, 962, 1152),
        "lima":    (170, 216, 4),
    },
    2: {  # slide 1 sobre fondo CLARO
        "circulo": (296, 472, 723, 899),
        "barra":   (50, 898, 707, 1158),
        "cuadro":  (711, 900, 965, 1161),
        "lima":    (164, 199, 11),
    },
}


def medir_template(ruta) -> dict:
    """Re-mide la geometría de un template. Se usa a mano cuando cambia el
    diseño, no en cada generación: los números viven en `GEOMETRIA` para que
    una pieza no dependa de que la detección acierte en caliente."""
    import numpy as np
    a = np.asarray(Image.open(ruta).convert("RGB")).astype(int)
    blanco = a.min(axis=2) > 250
    lima_m = ((a[:, :, 1] > 150) & (a[:, :, 2] < 120)
              & (a[:, :, 0] > 120) & (a[:, :, 0] < 220))

    def rango(mask, eje, fijo, desde, hasta):
        v = mask[:, fijo] if eje == "y" else mask[fijo]
        idx = np.nonzero(v[desde:hasta])[0] + desde
        return (int(idx.min()), int(idx.max())) if len(idx) else None

    by = rango(blanco, "y", 70, 860, a.shape[0] - 1)
    bx = rango(blanco, "x", (by[0] + by[1]) // 2, 0, 790)
    cy = rango(blanco, "y", 512, 430, 640)
    cx = rango(blanco, "x", cy[0] + 120, 200, 830)
    ly = rango(lima_m, "y", 745, 900, a.shape[0] - 1)
    lx = rango(lima_m, "x", (ly[0] + ly[1]) // 2, 700, a.shape[1] - 1)
    return {
        "circulo": (cx[0], cy[0], cx[1], cy[0] + (cx[1] - cx[0])),
        "barra": (bx[0], by[0], bx[1], by[1]),
        "cuadro": (lx[0], ly[0], lx[1], ly[1]),
        "lima": tuple(int(v) for v in a[ly[0] + 30, 745]),
    }


def _fuente(nombre: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FUENTES / nombre), size)


def plata(n: float) -> str:
    """$1.234.567 — el formato chileno, con punto de miles."""
    return "$" + format(int(round(n)), ",d").replace(",", ".")


def _ancho(draw, texto, fuente) -> int:
    b = draw.textbbox((0, 0), texto, font=fuente)
    return b[2] - b[0]


def _encajar(draw, texto, nombre_fuente, ancho_max, size_ini, size_min):
    """Baja el cuerpo hasta que el texto entre en `ancho_max`.

    Los nombres reales de producto de retail son mucho más largos que
    "AirPods Pro": sin esto, un nombre largo se sale del cuadro.
    """
    size = size_ini
    while size > size_min:
        f = _fuente(nombre_fuente, size)
        if _ancho(draw, texto, f) <= ancho_max:
            return f
        size -= 2
    return _fuente(nombre_fuente, size_min)


def _partir(draw, texto, fuente, ancho_max):
    """Corta el texto en líneas que quepan, sin partir palabras."""
    palabras, lineas, actual = texto.split(), [], ""
    for p in palabras:
        prueba = (actual + " " + p).strip()
        if _ancho(draw, prueba, fuente) <= ancho_max or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    return lineas


def _color_fondo(base: Image.Image) -> tuple:
    """El color plano del fondo, muestreado de una esquina que nunca tiene
    nada encima. Así el mismo código sirve para el template negro y el
    blanco sin mantener el valor a mano por template."""
    return base.convert("RGB").getpixel((12, 400))


def _tapar(draw, caja, color):
    """Borra un marcador del template pintando su caja del color de fondo."""
    draw.rectangle(list(caja), fill=color)


def _mascara_redonda(size, radio=None):
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    if radio is None:
        d.ellipse([0, 0, size[0] - 1, size[1] - 1], fill=255)
    else:
        d.rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radio, fill=255)
    return m


def _pegar_foto(base: Image.Image, foto_bytes: bytes, circulo, log=print) -> None:
    """La foto real del producto, dentro del círculo blanco.

    Va CONTENIDA (nunca recortada) y sobre blanco: las fotos de retail vienen
    con su propio fondo, y forzarlas a llenar el círculo cortaría el producto.
    El 24-ago se descartó el recorte automático con rembg justamente porque
    con cientos de fotos reales de tiendas distintas falla demasiado.
    """
    x0, y0, x1, y1 = circulo
    lado = x1 - x0
    try:
        foto = Image.open(io.BytesIO(foto_bytes)).convert("RGB")
    except Exception as e:                                    # noqa: BLE001
        log("[templates] no se pudo abrir la foto: %s" % e)
        return

    # Lienzo blanco del tamaño del círculo, con la foto centrada dentro.
    interior = int(lado * 0.78)     # deja aire para que no toque el borde
    fw, fh = foto.size
    escala = min(interior / fw, interior / fh)
    nueva = foto.resize((max(1, int(fw * escala)), max(1, int(fh * escala))), Image.LANCZOS)

    disco = Image.new("RGB", (lado, lado), (255, 255, 255))
    disco.paste(nueva, ((lado - nueva.width) // 2, (lado - nueva.height) // 2))
    base.paste(disco, (x0, y0), _mascara_redonda((lado, lado)))


def componer_slide1(template: int, nombre: str, precio_antes: float,
                    precio_ahora: float, foto_bytes: bytes | None = None,
                    log=print) -> Image.Image:
    """La slide 1 con los datos del producto. `template` es 1 o 2."""
    archivo = TEMPLATES / ("t%d_slide1.png" % template)
    base = Image.open(archivo).convert("RGB")
    if base.size != LADO:
        base = base.resize(LADO, Image.LANCZOS)

    cajas = GEOMETRIA[template]
    fondo = _color_fondo(base)
    # En el template negro el titular es blanco; en el claro, negro.
    oscuro = sum(fondo) < 300
    tinta = (255, 255, 255) if oscuro else (17, 17, 17)
    draw = ImageDraw.Draw(base)

    desc = max(0, round((1 - precio_ahora / precio_antes) * 100)) if precio_antes else 0

    # ── 1. Titular: el nombre del producto ───────────────────────────────
    # Se borra el bloque de arriba ENTERO (titular + "% OFF") de una vez.
    _tapar(draw, ZONA_TEXTO_SUP, fondo)
    ancho_util = CAJA_TITULO[2] - CAJA_TITULO[0]
    f_tit = _encajar(draw, nombre.upper(), "Poppins-ExtraBold.ttf", ancho_util, 58, 26)
    lineas = _partir(draw, nombre.upper(), f_tit, ancho_util)[:2]
    y = CAJA_TITULO[1]
    for ln in lineas:
        draw.text((MARGEN_IZQ, y), ln, font=f_tit, fill=tinta)
        y += f_tit.size + 6

    # ── 2. "¡XX% OFF!" en lima, grande ───────────────────────────────────
    texto_off = "¡%d%% OFF!" % desc
    f_off = _encajar(draw, texto_off, "Poppins-ExtraBold.ttf",
                     CAJA_OFF[2] - CAJA_OFF[0], 96, 48)
    y_off = max(y + 8, CAJA_OFF[1])
    draw.text((MARGEN_IZQ, y_off), texto_off, font=f_off, fill=cajas["lima"])

    # ── 3. La foto real, en el círculo ───────────────────────────────────
    if foto_bytes:
        _pegar_foto(base, foto_bytes, cajas["circulo"], log=log)
    else:
        # Sin foto se deja el círculo blanco liso: un hueco vacío es honesto,
        # un dibujo inventado no.
        x0, y0, x1, y1 = cajas["circulo"]
        base.paste(Image.new("RGB", (x1 - x0, y1 - y0), (255, 255, 255)),
                   (x0, y0), _mascara_redonda((x1 - x0, y1 - y0)))

    # ── 4. Barra de precios (antes tachado / ahora) ──────────────────────
    draw = ImageDraw.Draw(base)
    bx0, by0, bx1, by1 = cajas["barra"]
    # Se repinta la barra ENTERA como rectángulo redondeado del color de la
    # tarjeta: así desaparece el marcador `{$PRECIO ANTIGUO}` completo. La
    # primera versión repintaba sólo el interior y el marcador asomaba por
    # arriba en el template claro, donde la barra empieza 40 px más arriba.
    draw.rounded_rectangle([bx0, by0, bx1, by1], radius=38, fill=(255, 255, 255))

    f_antes = _fuente("Poppins-SemiBold.ttf", 34)
    f_ahora = _fuente("Poppins-ExtraBold.ttf", 60)
    gris = (110, 110, 110)
    x_txt = bx0 + 44

    y_antes = by0 + 26
    draw.text((x_txt, y_antes), "Antes: ", font=f_antes, fill=gris)
    wl = _ancho(draw, "Antes: ", f_antes)
    txt_antes = plata(precio_antes)
    draw.text((x_txt + wl, y_antes), txt_antes, font=f_antes, fill=gris)
    b = draw.textbbox((x_txt + wl, y_antes), txt_antes, font=f_antes)
    ymed = (b[1] + b[3]) // 2
    draw.line([(b[0] - 3, ymed), (b[2] + 3, ymed)], fill=ROJO_TACHADO, width=4)

    y_ahora = by0 + 88
    draw.text((x_txt, y_ahora), "Ahora: ", font=f_ahora, fill=(17, 17, 17))
    wl2 = _ancho(draw, "Ahora: ", f_ahora)
    ancho_libre = (bx1 - 30) - (x_txt + wl2)
    f_precio = _encajar(draw, plata(precio_ahora), "Poppins-ExtraBold.ttf",
                        ancho_libre, 60, 30)
    draw.text((x_txt + wl2, y_ahora), plata(precio_ahora), font=f_precio, fill=(17, 17, 17))

    # ── 5. Cuadro lima con el -XX% ───────────────────────────────────────
    cx0, cy0, cx1, cy1 = cajas["cuadro"]
    # Con el lima EXACTO de este template, no con la constante: los dos
    # templates usan verdes distintos y el parche se notaba.
    draw.rounded_rectangle([cx0, cy0, cx1, cy1], radius=30, fill=cajas["lima"])
    pct = "-%d%%" % desc
    f_pct = _encajar(draw, pct, "Poppins-ExtraBold.ttf", (cx1 - cx0) - 44, 62, 30)
    tb = draw.textbbox((0, 0), pct, font=f_pct)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    draw.text((cx0 + (cx1 - cx0 - tw) // 2 - tb[0],
               cy0 + (cy1 - cy0 - th) // 2 - tb[1]),
              pct, font=f_pct, fill=(17, 17, 17))

    return base


def slide2(template: int) -> Image.Image:
    """La slide fija. Se usa tal cual: nunca se regenera ni se le escribe."""
    im = Image.open(TEMPLATES / ("t%d_slide2.png" % template)).convert("RGB")
    return im if im.size == LADO else im.resize(LADO, Image.LANCZOS)


def carrusel(template: int, nombre: str, precio_antes: float, precio_ahora: float,
             foto_bytes: bytes | None = None, log=print) -> list[bytes]:
    """Las dos slides listas para publicar, en orden, como PNG."""
    out = []
    for im in (componer_slide1(template, nombre, precio_antes, precio_ahora,
                               foto_bytes, log=log),
               slide2(template)):
        buf = io.BytesIO()
        im.save(buf, "PNG")
        out.append(buf.getvalue())
    return out


def template_de_turno(publicados_antes: int) -> int:
    """Rotación consecutiva 1 → 2 → 1 → 2, pedida por Joaquín.

    Se deriva del CONTADOR de publicaciones, no de un azar ni de un estado
    guardado aparte: así dos procesos que publiquen a la vez no eligen el
    mismo template, y reconstruir cuál tocaba es mirar cuántas van.
    """
    return 1 if publicados_antes % 2 == 0 else 2
