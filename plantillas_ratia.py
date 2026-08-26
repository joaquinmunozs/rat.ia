# -*- coding: utf-8 -*-
"""Rat.IA · compone la pieza de una oferta sobre las plantillas reales de
Joaquín, sin IA -- solo código (Pillow).

CÓMO ESTÁ ARMADO EL CARRUSEL (24-ago-2026, definido por Joaquín)
------------------------------------------------------------------------------
2 slides, alternando color cada publicación (una vez blanca, la siguiente
negra):
    slide 1 (placeholder)   se autocompleta acá: foto del producto, precio
                            antes/después, % de descuento.
    slide 2 (predeterminada) fija, tal cual la entregó Joaquín -- no se toca.

SEGUNDA VUELTA (24-ago-2026): SIN RECORTE DE FONDO, LETRAS MÁS GRANDES
------------------------------------------------------------------------------
La primera versión recortaba el producto (rembg) y lo hacía flotar sobre el
sticker/starburst de la plantilla. Joaquín lo frenó por dos motivos reales:
  1. El recorte automático se ve mal en varios casos y es poco confiable --
     con cientos de fotos reales de tiendas distintas, muchas van a fallar
     (fondos con textura, reflejos, productos transparentes, etc.).
  2. El texto se sentía tímido -- quería títulos y precios que realmente
     paren el scroll.

Ahora: el starburst de la plantilla se TAPA (se repinta con el color de
fondo plano) y en su lugar se dibuja una tarjeta blanca, chica, con
esquinas redondeadas, donde entra la foto COMPLETA sin tocar (contain-fit,
nunca recortada) -- funciona con cualquier foto de producto, sin depender
de que un modelo de segmentación la lea bien. El espacio que libera el
sticker más chico se lo lleva el titular y el "¡XX% OFF!", mucho más
grandes que en la primera versión.

Las coordenadas base salen de medir en píxeles las plantillas reales
(`template negro/blanco, 1 placeholder.jpeg`, 1254×1254). La tipografía es
una aproximación (Poppins ExtraBold) -- se ajusta con la prueba real, no
pretende ser un match exacto de la fuente original.
"""
from __future__ import annotations

import io
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_TEMPLATES = Path(os.environ.get(
    "RATIA_TEMPLATES_DIR",
    r"C:\Users\HP Pavilion\Downloads"))
BASE_FUENTES = Path(os.environ.get(
    "RATIA_FUENTES_DIR",
    r"C:\Users\HPPAVI~1\AppData\Local\Temp\claude\C--Users-HP-Pavilion\4ca2169b-27ca-42ca-995b-fca375bacd2b\scratchpad\fuentes"))
BASE_ASSETS = Path(os.environ.get(
    "RATIA_ASSETS_DIR",
    r"C:\Users\HPPAVI~1\AppData\Local\Temp\claude\C--Users-HP-Pavilion\4ca2169b-27ca-42ca-995b-fca375bacd2b\scratchpad"))

LADO = 1254

# ── Coordenadas medidas en píxeles contra las plantillas reales ───────────
# Medido por separado en las plantillas negra Y blanca -- el sticker NO
# queda exactamente en el mismo lugar en las dos (blanca: 219,318-1070,945;
# negra: 239,343-1036,953). Usar la unión de ambas + margen en
# `_tapar_starburst` evita que queden puntas del sticker asomando en una
# de las dos plantillas (pasó de verdad: quedaban visibles en la blanca).
#
# El techo se subió a 150 (en vez de pegarlo justo al borde medido del
# sticker, 318): la tarjeta con marco es más alta que el sticker chico
# original y su Y depende del texto de arriba -- con un nombre de producto
# corto (fuente al tamaño mínimo) la tarjeta podía terminar arrancando por
# encima de la zona tapada, dejando algún pico del sticker viejo asomando.
# Con margen de sobra no importa qué tan corto sea el título.
STARBURST = (219, 150, 1070, 953)          # zona del sticker -- se tapa entera
BARRA_BLANCA = (117, 955, 910, 1186)       # antes/ahora
CUADRO_DESCUENTO = (885, 955, 1141, 1186)  # -XX%
ICONO_POS = (1093, 1128)                   # esquina del icono standalone
ICONO_ANCHO = 108

MARGEN_IZQ = 78
HEADLINE_Y = 96           # tope del bloque de titulo (nombre producto)
SUBHEADLINE_GAP = 8        # separacion entre nombre y "¡XX% OFF!"

# La tarjeta de la foto: chica y cuadrada a propósito (pedido explícito de
# Joaquín, "un pequeño cuadrado con el producto completo"), centrada en el
# hueco que deja el sticker tapado. GAP_TARJETA es el respiro después del
# bloque de titular; el tamaño de letra más grande de abajo empuja este
# bloque hacia abajo solo, así que la tarjeta no tiene una Y fija.
LADO_TARJETA = 500
GAP_TARJETA = 40
PAD_TARJETA = 26           # margen interno entre el borde de la tarjeta y la foto
RADIO_TARJETA = 30
RADIO_FOTO = 16             # esquinas de la foto misma, adentro de la tarjeta

# SEGUNDA CORRECCIÓN (24-ago-2026): "se ve mal el contraste de la imagen del
# producto con la imagen de fondo". El problema real: una tarjeta BLANCA
# sobre la plantilla BLANCA casi no se distingue -- solo la sombra gris la
# separaba del fondo, y encima cualquier foto de producto con SU propio
# fondo (cielo azul, mesón gris, lo que sea) queda flotando sin ninguna
# relación visual con la marca. La arregla un marco lima sólido alrededor
# de la tarjeta: da contraste garantizado contra CUALQUIER fondo (negro o
# blanco) y ata la pieza al color de marca en vez de a lo que traiga la foto.
MARCO_LIMA = 22

COLORES = {
    "negro": {"texto_titulo": (255, 255, 255), "icono": "icono_blanco.png"},
    "blanco": {"texto_titulo": (10, 10, 10), "icono": "icono_negro.png"},
}
LIMA = (185, 230, 6)
ROJO_TACHADO = (196, 40, 40)
BLANCO_TARJETA = (255, 255, 255)
SOMBRA_MARCO = (0, 0, 0, 90)


def _fuente(nombre, size):
    return ImageFont.truetype(str(BASE_FUENTES / nombre), size)


def _texto_ancho(draw, texto, fuente):
    b = draw.textbbox((0, 0), texto, font=fuente)
    return b[2] - b[0]


def _ajustar_tamano(draw, texto, fuente_nombre, ancho_max, size_inicial, size_min=28):
    """Baja el tamaño de a poco hasta que el texto entre en `ancho_max`.
    Los nombres reales de producto son mucho más largos que "AirPods Pro 2"
    -- sin esto, un nombre largo se saldría del cuadro."""
    size = size_inicial
    while size > size_min:
        f = _fuente(fuente_nombre, size)
        if _texto_ancho(draw, texto, f) <= ancho_max:
            return f
        size -= 2
    return _fuente(fuente_nombre, size_min)


def _color_de_fondo(base: Image.Image) -> tuple:
    """El color plano de fondo de esta plantilla (negro puro o blanco),
    muestreado de una esquina que nunca tiene ningún elemento encima --
    así no hace falta mantener el valor exacto a mano por plantilla."""
    return base.convert("RGB").getpixel((20, 20))


def _tapar_starburst(base: Image.Image) -> None:
    """Repinta toda la zona del sticker con el color de fondo plano. Es
    más simple que recortar la silueta jagged del starburst -- y como la
    tarjeta nueva es más chica que el sticker original, un rectángulo de
    sobra cubre cualquier punta que quedara asomando."""
    color = _color_de_fondo(base)
    draw = ImageDraw.Draw(base)
    x0, y0, x1, y1 = STARBURST
    draw.rectangle([x0 - 16, y0 - 16, x1 + 16, y1 + 16], fill=color)


def _rounded_mask(size: tuple, radius: int) -> Image.Image:
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1],
                                        radius=radius, fill=255)
    return m


def _tarjeta_producto(base: Image.Image, foto_bytes: bytes, cy_centro: int) -> None:
    """Tarjeta blanca chica y cuadrada, con marco lima (contraste
    garantizado contra cualquier fondo) y la foto COMPLETA adentro
    (contain-fit, nunca recortada, nunca corrida por un modelo de
    segmentación) -- funciona igual con cualquier foto real de tienda,
    tenga o no fondo limpio."""
    x0 = (LADO - LADO_TARJETA) // 2
    y0 = cy_centro - LADO_TARJETA // 2
    x1, y1 = x0 + LADO_TARJETA, y0 + LADO_TARJETA
    mx0, my0, mx1, my1 = x0 - MARCO_LIMA, y0 - MARCO_LIMA, x1 + MARCO_LIMA, y1 + MARCO_LIMA
    radio_marco = RADIO_TARJETA + MARCO_LIMA // 2

    # Sombra debajo del marco (no de la tarjeta blanca) -- así se ve como UN
    # solo objeto con volumen, no dos capas sueltas.
    sombra = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle(
        [mx0 + 8, my0 + 14, mx1 + 8, my1 + 14], radius=radio_marco, fill=SOMBRA_MARCO)
    base.alpha_composite(sombra)

    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle([mx0, my0, mx1, my1], radius=radio_marco, fill=LIMA)
    draw.rounded_rectangle([x0, y0, x1, y1], radius=RADIO_TARJETA, fill=BLANCO_TARJETA)

    try:
        foto = Image.open(io.BytesIO(foto_bytes)).convert("RGB")
    except Exception as e:                                    # noqa: BLE001
        print(f"[plantillas_ratia] no se pudo abrir la foto del producto: {e}")
        return

    interior = LADO_TARJETA - PAD_TARJETA * 2
    fw, fh = foto.size
    escala = min(interior / fw, interior / fh)
    nueva = foto.resize((max(1, int(fw * escala)), max(1, int(fh * escala))),
                        Image.LANCZOS)
    px = x0 + PAD_TARJETA + (interior - nueva.width) // 2
    py = y0 + PAD_TARJETA + (interior - nueva.height) // 2
    mascara = _rounded_mask(nueva.size, RADIO_FOTO)
    base.paste(nueva, (px, py), mascara)


def _tachar(draw, xy, texto, fuente, color_texto):
    x, y = xy
    draw.text((x, y), texto, font=fuente, fill=color_texto)
    b = draw.textbbox((x, y), texto, font=fuente)
    ymed = (b[1] + b[3]) // 2
    draw.line([(b[0] - 2, ymed), (b[2] + 2, ymed)], fill=ROJO_TACHADO, width=4)


def _plata(n):
    return "$" + format(int(round(n)), ",d").replace(",", ".")


def componer_slide1(color: str, nombre_producto: str, precio_antes: float,
                    precio_ahora: float, foto_bytes: bytes) -> Image.Image:
    """El slide que se autocompleta. `color` es 'negro' o 'blanco'."""
    cfg = COLORES[color]
    ruta_base = BASE_TEMPLATES / f"template {color}, 1 placeholder.jpeg"
    base = Image.open(ruta_base).convert("RGBA")

    _tapar_starburst(base)
    draw = ImageDraw.Draw(base)

    # ── Titular: nombre del producto + "¡XX% OFF!" -- grandes a propósito,
    # es lo que tiene que parar el scroll. ───────────────────────────────
    descuento = max(0, round((1 - precio_ahora / precio_antes) * 100)) if precio_antes else 0
    ancho_max_titulo = LADO - MARGEN_IZQ - 60

    f_titulo = _ajustar_tamano(draw, nombre_producto, "Poppins-ExtraBold.ttf",
                               ancho_max_titulo, 134, size_min=58)
    draw.text((MARGEN_IZQ, HEADLINE_Y), nombre_producto, font=f_titulo,
              fill=cfg["texto_titulo"])
    alto_titulo = draw.textbbox((MARGEN_IZQ, HEADLINE_Y), nombre_producto,
                                font=f_titulo)[3]

    texto_off = f"¡{descuento}% OFF!"
    ancho_max_off = LADO - MARGEN_IZQ - 60
    f_off = _ajustar_tamano(draw, texto_off, "Poppins-ExtraBold.ttf",
                            ancho_max_off, 156, size_min=80)
    y_off = alto_titulo + SUBHEADLINE_GAP
    draw.text((MARGEN_IZQ, y_off), texto_off, font=f_off, fill=LIMA)
    alto_off = draw.textbbox((MARGEN_IZQ, y_off), texto_off, font=f_off)[3]

    # ── Tarjeta del producto -- su Y depende de dónde terminó el titular,
    # así nunca se pisan sin importar cuán largo sea el nombre. ─────────
    cy_tarjeta = alto_off + GAP_TARJETA + LADO_TARJETA // 2
    _tarjeta_producto(base, foto_bytes, cy_tarjeta)
    draw = ImageDraw.Draw(base)  # la tarjeta compone sobre `base`; se re-crea el draw

    # ── Barra de precio (antes / ahora) ─────────────────────────────────
    bx0, by0, bx1, by1 = BARRA_BLANCA
    pad_izq = 46
    color_precio = (20, 20, 20)  # la barra siempre es clara en ambas plantillas
    color_gris = (100, 100, 100)

    f_antes = _fuente("Poppins-SemiBold.ttf", 50)
    y_antes = by0 + 18
    draw.text((bx0 + pad_izq, y_antes), "Antes: ", font=f_antes, fill=color_gris)
    ancho_label = _texto_ancho(draw, "Antes: ", f_antes)
    _tachar(draw, (bx0 + pad_izq + ancho_label, y_antes), _plata(precio_antes),
            f_antes, color_gris)

    f_ahora = _fuente("Poppins-ExtraBold.ttf", 92)
    y_ahora = by0 + 80
    draw.text((bx0 + pad_izq, y_ahora), "Ahora: ", font=f_ahora, fill=color_precio)
    ancho_label2 = _texto_ancho(draw, "Ahora: ", f_ahora)
    draw.text((bx0 + pad_izq + ancho_label2, y_ahora), _plata(precio_ahora),
              font=f_ahora, fill=color_precio)

    # ── -XX% en el cuadro lima ───────────────────────────────────────────
    cx0, cy0, cx1, cy1 = CUADRO_DESCUENTO
    texto_pct = f"-{descuento}%"
    f_pct = _ajustar_tamano(draw, texto_pct, "Poppins-ExtraBold.ttf",
                            (cx1 - cx0) - 24, 84, size_min=48)
    tb = draw.textbbox((0, 0), texto_pct, font=f_pct)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    draw.text((cx0 + (cx1 - cx0 - tw) // 2 - tb[0],
              cy0 + (cy1 - cy0 - th) // 2 - tb[1]),
              texto_pct, font=f_pct, fill=(15, 15, 15))

    # ── Ícono Rat.IA, esquina ────────────────────────────────────────────
    icono = Image.open(BASE_ASSETS / cfg["icono"]).convert("RGBA")
    escala_icono = ICONO_ANCHO / icono.width
    icono = icono.resize((ICONO_ANCHO, int(icono.height * escala_icono)), Image.LANCZOS)
    base.alpha_composite(icono, ICONO_POS)

    return base.convert("RGB")


def slide2_predeterminada(color: str) -> Image.Image:
    """El slide fijo -- se usa tal cual, sin tocar."""
    ruta = BASE_TEMPLATES / f"template {color}, 2 predeterminada.jpeg"
    return Image.open(ruta).convert("RGB")
