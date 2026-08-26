# -*- coding: utf-8 -*-
"""Rat.IA · la pieza de Instagram para un convenio banco-comercio.

POR QUÉ NO SE REUSA `ratia_pieza_ia.generar_pieza`
==============================================================================
Esa arma una pieza de OFERTA DE RETAIL: su diseño gira en torno a un
"antes → ahora" y a la FOTO REAL del producto, que se pega con Pillow
sobre una tarjeta blanca vacía porque el modelo no puede inventar un
producto que existe.

Un convenio no tiene nada de eso:
  · no hay "antes/ahora" -- hay un porcentaje y una condición
    ("40% todos los martes pagando con Lider Bci");
  · no hay una foto de producto que pegar;
  · lo que importa es la RELACIÓN entre dos marcas (comercio + banco),
    el día y la vigencia.

Forzar el molde de retail acá daría una pieza con un hueco de foto vacío y
un "antes" inventado -- peor que no publicar.

⚠️ LOS LOGOS NO SE DIBUJAN, Y ES LA REGLA MÁS IMPORTANTE DE ESTE ARCHIVO
==============================================================================
Se le pide EXPLÍCITAMENTE al modelo que NO dibuje el logo de McDonald's,
de Copec ni de ningún banco. Un modelo de imagen siempre devuelve algo:
si le pides el logo de un banco, dibuja algo *parecido* -- y publicar una
versión deformada de la marca registrada de un banco real, en una cuenta
que además afirma un descuento suyo, es un problema distinto y más caro
que un precio mal escrito.

La pieza es puramente tipográfica: los NOMBRES en texto, el porcentaje
enorme, la condición y la vigencia. Es además el estilo que mejor le sale
a `gpt-image-2` (renderiza texto de verdad bien) y el que más se parece a
la identidad ya existente de Rat.IA.

LA VERIFICACIÓN, IGUAL QUE EN RETAIL PERO SOBRE OTROS DATOS
==============================================================================
Joaquín pidió "publica sola si pasa la verificación". Acá lo que se
verifica no son dos precios sino: el PORCENTAJE, el COMERCIO y el BANCO.
Si el modelo escribió "45%" donde debía decir "40%", o cambió el nombre
del banco, la pieza se descarta y se reintenta. Sin `ANTHROPIC_API_KEY` no
se publica nada: `verificar=False` es sólo para probar el diseño.
"""
from __future__ import annotations

import base64
import io
import json
import os
import urllib.request
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw

import ratia_pieza_ia as base

INTENTOS = 3
LIMA_HEX = base.LIMA_HEX if hasattr(base, "LIMA_HEX") else "#B9E606"

# ── Logo real del EMISOR (26-ago-2026) ──────────────────────────────────────
#
# Joaquín, viendo la primera pieza real publicada: "no puede ser que las
# publicaciones de bancos no incluyan el logo oficial". El modelo NUNCA
# dibuja el logo (ver la regla más abajo, no se negocia -- pedirle a
# gpt-image-2 que dibuje el isotipo de un banco real da una versión
# deformada, que es peor que no ponerlo). En cambio se reserva un badge
# vacío y se pega el archivo REAL encima con Pillow -- mismo patrón que
# el logo/personaje de Bárbara y la foto de producto de Rat.IA retail.
#
# Sólo el EMISOR (el banco/billetera): son ~15 marcas fijas, reusables en
# TODOS los convenios. El `comercio` es casi siempre de cola larga
# ("Clínica Dental 3Dent") -- sin una fuente confiable por cada uno, pegar
# un logo ahí es que gastaría más esfuerzo del que vale.
LOGOS_DIR = Path(__file__).resolve().parent / "assets" / "logos_convenios"
_LOGO_SLUG = {
    "banco de chile": "banco_de_chile",
    "bancoestado": "bancoestado",
    "banco estado": "bancoestado",
    "bci": "bci",
    "lider bci": "bci",
    "santander": "santander",
    "cmr falabella": "cmr_falabella",
    "cencosud scotiabank": "scotiabank",
    "scotiabank": "scotiabank",
    "mcdonald's": "mcdonalds",
    "mcdonalds": "mcdonalds",
    "kfc": "kfc",
    "wendy's": "wendys",
    "wendys": "wendys",
    "turbus": "turbus",
    "flixbus": "flixbus",
    "farmacias cruz verde": "farmacias_cruz_verde",
    "farmacias ahumada": "farmacias_ahumada",
}


def logo_de(nombre: str) -> Path | None:
    """La ruta al logo real de `nombre` (emisor), o None si no hay uno
    curado -- en ese caso la pieza sigue siendo sólo tipográfica, como
    antes del 26-ago-2026. Nunca revienta por un nombre desconocido."""
    slug = _LOGO_SLUG.get((nombre or "").strip().lower())
    if not slug:
        return None
    ruta = LOGOS_DIR / f"{slug}.png"
    return ruta if ruta.exists() else None


def pegar_logo_badge(pieza: bytes, ruta_logo: Path) -> bytes:
    """Pega el logo real en una tarjeta blanca redondeada, arriba a la
    derecha -- una tarjeta blanca funciona sobre CUALQUIER color de fondo
    (bancos como Banco de Chile son texto azul oscuro sobre transparente:
    ilegible pegado directo sobre negro)."""
    base_img = Image.open(io.BytesIO(pieza)).convert("RGBA")
    w, h = base_img.size
    logo = Image.open(ruta_logo).convert("RGBA")

    card_w = round(w * 0.30)
    pad = round(card_w * 0.14)
    logo_w = card_w - pad * 2
    ratio = logo_w / logo.width
    logo_h = round(logo.height * ratio)
    max_logo_h = round(card_w * 0.42)
    if logo_h > max_logo_h:
        ratio = max_logo_h / logo.height
        logo_w = round(logo.width * ratio)
        logo_h = max_logo_h
    logo = logo.resize((max(1, logo_w), max(1, logo_h)), Image.LANCZOS)

    card_h = logo_h + pad * 2
    card = Image.new("RGBA", (card_w, card_h), (255, 255, 255, 255))
    mascara = Image.new("L", (card_w, card_h), 0)
    ImageDraw.Draw(mascara).rounded_rectangle(
        [0, 0, card_w - 1, card_h - 1], radius=round(card_h * 0.18), fill=255)
    card.putalpha(mascara)
    card.alpha_composite(logo, ((card_w - logo_w) // 2, (card_h - logo_h) // 2))

    margen = round(w * 0.06)
    salida = base_img.copy()
    salida.alpha_composite(card, (w - card_w - margen, margen))
    buf = io.BytesIO()
    salida.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


_ZONA_LOGO = """RESERVED BADGE AREA — top-right corner, about 30% of the frame's width and
14% of its height: this area must look EXACTLY like the rest of the
background — same colour, same texture, continuous with everything around
it. Do NOT draw a box, card, panel, chip, text or icon there. A real brand
logo file gets placed on top of this untouched area afterward — any visible
shape or colour shift there is a mistake."""


def _prompt(emisor: str, comercio: str, descuento: int, condicion: str,
            vigencia: str, color: str, con_logo: bool) -> str:
    fondo = "negro puro (#0A0A0A)" if color == "negro" else "blanco puro (#FFFFFF)"
    texto = "blanco" if color == "negro" else "negro"
    return f"""Diseña una pieza cuadrada de Instagram para anunciar un convenio de
descuento entre un banco y un comercio. Estilo editorial moderno, limpio,
tipográfico, calidad de agencia.

FONDO: {fondo}. Texto principal en {texto}. Color de acento: verde lima {LIMA_HEX}.

CONTENIDO EXACTO (copia cada texto carácter por carácter, sin reformatear,
sin traducir, sin cambiar ni un dígito):
· Arriba, mediano: "{comercio}"
· Debajo, más chico y en verde lima: "con {emisor}"
· En el centro, ENORME, ocupando el mayor espacio de la pieza: "{descuento}%"
· Bajo el porcentaje, mediano: "DE DESCUENTO"
· Más abajo, chico: "{condicion}"
· Al pie, muy chico y discreto: "{vigencia}"
{"" if not con_logo else chr(10) + _ZONA_LOGO + chr(10)}
REGLA CRÍTICA — NO DIBUJES NINGÚN LOGO NI ISOTIPO.
No dibujes el logo de {comercio}, ni el de {emisor}, ni de ninguna marca,
banco o tarjeta. Nada de arcos dorados, aislados de bencinera, tarjetas de
crédito dibujadas, escudos ni emblemas. Los nombres de las marcas van
ÚNICAMENTE como TEXTO tipográfico, escritos tal cual arriba.

La composición es puramente tipográfica y geométrica: se permiten formas
abstractas simples (círculos, franjas, bloques de color) como decoración,
nunca figuras que representen una marca o un producto.

TIPOGRAFÍA: sans-serif geométrica pesada (tipo Poppins ExtraBold) para el
porcentaje y los titulares. El "{descuento}%" tiene que leerse perfectamente
nítido y ser lo primero que se ve.

NO agregues ningún texto que no esté en la lista de arriba. Sin marcas de
agua, sin texto decorativo de relleno, sin condiciones legales inventadas."""


def _verificar_datos(pieza: bytes, emisor: str, comercio: str, descuento: int,
                     anthropic_key: str) -> tuple[bool, str]:
    """Le muestra la pieza a un modelo y le pide leer los tres datos que
    NO pueden salir mal: el porcentaje, el comercio y el banco.

    Devuelve (ok, detalle). `ok=False` siempre significa NO PUBLICAR --
    tanto si los datos salieron mal como si no se pudo comprobar.
    """
    try:
        img_b64 = base64.b64encode(pieza).decode()
    except Exception as e:                                    # noqa: BLE001
        return False, "no se pudo leer la pieza para verificar: %s" % e

    cuerpo = {
        "model": "claude-sonnet-5",
        "max_tokens": 300,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64",
                                             "media_type": "image/png",
                                             "data": img_b64}},
                {"type": "text", "text":
                    "Lee esta imagen. Responde SOLO un JSON: "
                    '{"descuento": "...", "comercio": "...", "banco": "...", '
                    '"hay_logos": true/false} '
                    "copiando el texto EXACTO tal como está escrito. En "
                    '"hay_logos" pon true si ves CUALQUIER logo, isotipo o '
                    "emblema de una marca real dibujado (no cuenta el texto "
                    "con el nombre). Si un dato no aparece, pon null."},
            ],
        }],
    }
    req = urllib.request.Request("https://api.anthropic.com/v1/messages",
                                 data=json.dumps(cuerpo).encode(), method="POST")
    req.add_header("x-api-key", anthropic_key)
    req.add_header("anthropic-version", "2023-06-01")
    req.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            resp = json.loads(r.read())
    except Exception as e:                                    # noqa: BLE001
        return False, "no se pudo verificar con el modelo: %s" % e

    txt = "".join(b.get("text", "") for b in resp.get("content", []))
    ini, fin = txt.find("{"), txt.rfind("}")
    if ini < 0 or fin < 0:
        return False, "la verificación no devolvió JSON: %s" % txt[:120]
    try:
        leido = json.loads(txt[ini:fin + 1])
    except Exception:                                         # noqa: BLE001
        return False, "JSON inválido en la verificación: %s" % txt[:120]

    if leido.get("hay_logos") is True:
        return False, ("la pieza trae un logo dibujado -- se descarta (ver la "
                       "regla de logos en el encabezado del módulo)")

    solo_digitos = "".join(ch for ch in str(leido.get("descuento") or "")
                           if ch.isdigit())
    if solo_digitos != str(descuento):
        return False, ("el descuento de la pieza no calza -- esperado %d%%, "
                       "la imagen dice %s" % (descuento, leido.get("descuento")))

    def parecido(a, b):
        """Comparación laxa a propósito: el modelo puede escribir el nombre
        en mayúsculas o sin el apóstrofo ("MCDONALDS" vs "McDonald's") sin
        que eso sea un error real. Lo que importa es que no haya escrito
        OTRA marca."""
        na = "".join(ch.lower() for ch in str(a or "") if ch.isalnum())
        nb = "".join(ch.lower() for ch in str(b or "") if ch.isalnum())
        return bool(na) and bool(nb) and (na in nb or nb in na)

    if not parecido(leido.get("comercio"), comercio):
        return False, ("el comercio de la pieza no calza -- esperado %r, "
                       "la imagen dice %r" % (comercio, leido.get("comercio")))
    if not parecido(leido.get("banco"), emisor):
        return False, ("el banco de la pieza no calza -- esperado %r, "
                       "la imagen dice %r" % (emisor, leido.get("banco")))
    return True, "datos verificados"


def condicion_texto(dia_semana: str | None, canal: str | None) -> str:
    """La línea de condición, en el orden en que se lee natural."""
    partes = []
    if dia_semana == "días":
        partes.append("Todos los días")
    elif dia_semana:
        partes.append("Todos los %s" % dia_semana)
    if canal and canal.lower() != "todos los canales":
        partes.append(canal)
    return " · ".join(partes)


def vigencia_texto(vigencia_hasta: date | None, es_recurrente: bool) -> str:
    if es_recurrente or not vigencia_hasta:
        return "Vigencia sujeta a cambios"
    return "Hasta el %s" % vigencia_hasta.strftime("%d-%m-%Y")


def _con_logo_si_corresponde(pieza: bytes, ruta_logo: Path | None, log=print) -> bytes:
    """Pega el logo real si hay uno curado para este emisor. Si el pegado
    falla por lo que sea (archivo corrupto, etc.), se publica la pieza
    IGUAL sin logo -- un logo es una mejora, no puede tumbar una pieza ya
    verificada y lista."""
    if not ruta_logo:
        return pieza
    try:
        return pegar_logo_badge(pieza, ruta_logo)
    except Exception as e:                                    # noqa: BLE001
        log("[convenios-pieza] no se pudo pegar el logo (%s), se publica sin él: %s"
            % (ruta_logo.name, str(e)[:150]))
        return pieza


def generar_pieza_convenio(emisor: str, comercio: str, descuento: int,
                            dia_semana: str | None = None,
                            canal: str | None = None,
                            vigencia_hasta: date | None = None,
                            es_recurrente: bool = False,
                            color: str = "negro", verificar: bool = True,
                            log=print) -> bytes | None:
    """La pieza terminada como PNG en bytes, o `None` si no se pudo armar
    o verificar -- y `None` SIEMPRE significa no publicar."""
    if color not in ("negro", "blanco"):
        raise ValueError("color tiene que ser 'negro' o 'blanco'")

    anthropic_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if verificar and not anthropic_key:
        raise base.SinCredenciales(
            "Falta ANTHROPIC_API_KEY: sin ella no se puede verificar que la "
            "pieza diga el descuento y las marcas correctas, y publicar el "
            "nombre de un banco sin verificar no es una opción.")

    ruta_logo = logo_de(emisor)
    prompt = _prompt(emisor, comercio, descuento,
                     condicion_texto(dia_semana, canal),
                     vigencia_texto(vigencia_hasta, es_recurrente), color,
                     con_logo=ruta_logo is not None)

    for intento in range(1, INTENTOS + 1):
        creada = base._pedir("/jobs/createTask", {
            "model": base.MODELO_TXT2IMG,
            "input": {"prompt": prompt, "aspect_ratio": "1:1", "resolution": "2K"},
        }, metodo="POST")
        task_id = (creada.get("data") or {}).get("taskId") or creada.get("taskId")
        if not task_id:
            log("[convenios-pieza] intento %d: Kie no devolvió taskId — %s"
                % (intento, creada))
            continue

        estado = base._esperar(task_id)
        if (estado.get("state") or "").lower() != "success":
            log("[convenios-pieza] intento %d falló: %s"
                % (intento, estado.get("failMsg") or estado.get("errorMessage")))
            continue

        url = base._url_resultado(estado)
        if not url:
            log("[convenios-pieza] intento %d: terminó sin URL" % intento)
            continue

        try:
            pieza = base._bajar(url)
        except Exception as e:                                # noqa: BLE001
            log("[convenios-pieza] intento %d: no se pudo bajar — %s" % (intento, e))
            continue

        if not verificar:
            return _con_logo_si_corresponde(pieza, ruta_logo, log)

        ok, detalle = _verificar_datos(pieza, emisor, comercio, descuento,
                                       anthropic_key)
        if ok:
            log("[convenios-pieza] pieza lista y verificada (intento %d)" % intento)
            # El logo real se pega DESPUÉS de verificar -- `_verificar_datos`
            # comprueba que el MODELO no haya dibujado ningún logo
            # (`hay_logos`); pegar el archivo real antes confundiría esa
            # verificación con un falso positivo.
            return _con_logo_si_corresponde(pieza, ruta_logo, log)
        log("[convenios-pieza] intento %d descartado: %s" % (intento, detalle))

    log("[convenios-pieza] ERROR: no se logró una pieza correcta — NO se publica.")
    return None
