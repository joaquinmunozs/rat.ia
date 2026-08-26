# -*- coding: utf-8 -*-
"""Rat.IA · el carrusel de 2 slides de una oferta, listo para publicar.

CÓMO ESTÁ ARMADO (26-ago-2026, definido por Joaquín)
==============================================================================
Dos slides, con los templates rotando de forma consecutiva entre publicaciones:

    TEMPLATE 1 → slide 1 fondo NEGRO   + slide 2 fondo BLANCO
    TEMPLATE 2 → slide 1 fondo CLARO   + slide 2 fondo NEGRO

  · slide 1 — lleva los datos del producto. Es la única que pasa por
    gpt-image-2: se le manda el template de Joaquín y reemplaza los
    marcadores `{NOMBRE PRODUCTO}`, `{¡PORCENTAJE DESCUENTO OFF!}`,
    `{$PRECIO ANTIGUO}`, `{$PRECIOACTUAL}` y `{-PORCENTAJE DESCUENTO%}`.
  · slide 2 — fija. Se pega tal cual, nunca se regenera ni se le escribe nada.

DOS COSAS QUE COSTARON UNA TARDE, PARA NO REPETIRLAS
==============================================================================
1. **El campo se llama `input_urls`, NO `image_urls`.** Con el nombre
   equivocado la API acepta el request, ignora el campo desconocido y genera
   la imagen DESDE CERO con sólo el prompt. El resultado se ve plausible y es
   otra marca: en la prueba del 26-ago inventó un logo ("OfertasReales") y
   cambió la paleta a azul y amarillo. Si un día las piezas dejan de
   parecerse al template, esto es lo primero que hay que mirar.

2. **`resolution="1K"` es MEJOR que "2K", no peor.** Con 1K devuelve
   1122×1402 (ratio 0.8003 = 4:5 exacto, el formato de feed de Instagram) y
   cuesta 6 créditos. Con 2K devuelve 1792×2304, que es ratio 0.7778 — NO es
   4:5, Instagram lo recorta — y cuesta 10. Y como Instagram recomprime todo
   igual, la resolución extra se pierde. Pedir `aspect_ratio="4:5"` explícito
   no ayuda: al 26-ago la API responde 422 "temporarily unavailable" para 4:5
   y 5:4, así que se pide `auto` y es 1K quien da el ratio correcto.

EL PROMPT ES CORTO A PROPÓSITO
==============================================================================
La primera versión le describía el diseño entero (fondo, starburst, colores,
tipografías). Eso invita al modelo a RE-CREAR en vez de editar. La versión
que funciona sólo lista los reemplazos: el diseño ya está en la imagen que se
le manda, no hay que contárselo.

LA FOTO DEL PRODUCTO NO PASA POR EL MODELO — NUNCA
==============================================================================
El círculo blanco vuelve vacío del modelo y la foto real se pega con Pillow.
Un modelo de imagen SIEMPRE llena un hueco: el 24-ago inventó un frasco
entero con claims de producto ("prensado en frío", "100% natural") que no
existían. Esa regla no se negocia — ver `ratia_pieza_ia.py`.
"""
from __future__ import annotations

import base64
import io
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

import ratia_texto

AQUI = Path(__file__).resolve().parent
TEMPLATES = Path(os.environ.get("RATIA_TEMPLATES_DIR", AQUI / "assets" / "templates"))

KIE = "https://api.kie.ai/api/v1"
MODELO_EDICION = "gpt-image-2-image-to-image"
# 1K da 4:5 exacto y cuesta 6 créditos; 2K da 0.7778 y cuesta 10. Ver arriba.
RESOLUCION = "1K"
CREDITOS_POR_PIEZA = 6

LADO = (1122, 1402)      # lo que devuelve el modelo en 1K


class SinCredenciales(RuntimeError):
    pass


def _clave_kie() -> str:
    k = (os.environ.get("KIE_API_KEY") or "").strip()
    if not k:
        raise SinCredenciales("Falta KIE_API_KEY en el entorno.")
    return k


def _pedir(ruta: str, cuerpo: dict | None = None, metodo: str = "GET") -> dict:
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(KIE + ruta, data=datos, method=metodo)
    req.add_header("Authorization", "Bearer " + _clave_kie())
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError("Kie %s: %s"
                           % (e.code, e.read().decode("utf-8", "replace")[:300])) from None


def _esperar(task_id: str, timeout_s: int = 300) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        d = _pedir("/jobs/recordInfo?taskId=" + task_id)
        data = d.get("data") or {}
        if (data.get("state") or "").lower() in ("success", "fail", "failed", "error"):
            return data
        time.sleep(5)
    return {"state": "timeout"}


def _url_resultado(estado: dict) -> str | None:
    r = estado.get("resultJson") or estado.get("result") or ""
    if isinstance(r, str) and r.strip().startswith("{"):
        try:
            r = json.loads(r)
        except Exception:                                     # noqa: BLE001
            return None
    if isinstance(r, dict):
        for k in ("resultUrls", "urls", "images"):
            v = r.get(k)
            if isinstance(v, list) and v:
                return v[0] if isinstance(v[0], str) else (v[0] or {}).get("url")
    return None


def _bajar(url: str, timeout: int = 90) -> bytes:
    # User-Agent de navegador: varios CDN (incluido el de MercadoLibre)
    # responden 403 al de urllib por defecto.
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _subir_a_blotato(datos: bytes) -> str:
    """gpt-image-2 necesita la imagen de entrada por URL pública. Se usa
    Blotato, que ya está en el stack para publicar y devuelve una URL."""
    k = (os.environ.get("BLOTATO_API_KEY") or "").strip()
    if not k:
        raise SinCredenciales("Falta BLOTATO_API_KEY (se usa para subir el template).")
    uri = "data:image/png;base64," + base64.b64encode(datos).decode()
    req = urllib.request.Request("https://backend.blotato.com/v2/media",
                                 data=json.dumps({"url": uri}).encode(), method="POST")
    req.add_header("blotato-api-key", k)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read() or b"{}")
    u = d.get("url") or d.get("mediaUrl")
    if not u:
        raise RuntimeError("Blotato no devolvió URL del template: %s" % d)
    return u


def _plata(n) -> str:
    return "$" + format(int(round(float(n))), ",d").replace(",", ".")


PROMPT = """Replace only the placeholder texts in this image. Keep everything else pixel-identical: same background, same colours, same shapes, same fonts, same layout, same logo.

- "{{NOMBRE PRODUCTO}}" -> "{nombre}"
- "{{¡PORCENTAJE DESCUENTO OFF!}}" -> "¡{desc}% OFF!"
- "{{$PRECIO ANTIGUO}}" -> "{antes}"
- "{{$PRECIOACTUAL}}" -> "{ahora}"
- "{{-PORCENTAJE DESCUENTO%}}" -> "-{desc}%"
- "{{PRODUCTO}}" -> delete it, leave the white circle empty

Copy each replacement exactly, digit by digit. Do not add or redesign anything."""


def template_de_turno(publicados_antes: int) -> int:
    """Rotación consecutiva 1 → 2 → 1 → 2.

    Se deriva del CONTADOR de publicaciones y no de un estado guardado
    aparte: así reconstruir cuál tocaba es mirar cuántas van, y dos procesos
    que publiquen a la vez no eligen el mismo.
    """
    return 1 if publicados_antes % 2 == 0 else 2


def _circulo_de(base: Image.Image):
    """Dónde quedó el círculo blanco del producto en la pieza generada.

    Se mide en la pieza REAL y no con una constante: el modelo reencuadra un
    poco en cada corrida (medido el 26-ago: 11,6% de píxeles distintos entre
    dos generaciones idénticas), así que una caja fija pegaría la foto corrida.

    CÓMO SE DISTINGUE DEL RESTO DEL BLANCO — dos intentos fallidos primero:

      1. "el tramo blanco más ancho" eligió la BARRA DE PRECIOS, que también
         es blanca y es más ancha. La foto terminó pegada encima del precio.
      2. filtrar por proporción no alcanzó: el círculo TOCA la barra, los dos
         son blancos, y el recorrido vertical los une en una sola mancha, así
         que el alto medido salía siempre de más.

    Lo que sí funciona: el círculo es el único blanco RODEADO DE LIMA — está
    dentro del starburst. La barra tiene fondo (negro o gris) encima. Así que
    se comprueba el color unos píxeles arriba del borde superior del tramo.
    """
    import numpy as np
    a = np.asarray(base.convert("RGB")).astype(int)
    h, w, _ = a.shape
    blanco = a.min(axis=2) > 244
    # Lima por su forma, no por un hex exacto: mucho más verde que azul.
    # Tolera las dos variantes de template y el reencuadre del modelo.
    lima = ((a[:, :, 1] > 140) & (a[:, :, 2] < 130)
            & (a[:, :, 0] > 110) & (a[:, :, 0] < 225))

    mejor = None
    for y in range(int(h * 0.22), int(h * 0.78), 3):
        fila = blanco[y]
        cx = w // 2
        if not fila[cx]:
            continue
        x0 = x1 = cx
        while x0 > 0 and fila[x0 - 1]:
            x0 -= 1
        while x1 < w - 1 and fila[x1 + 1]:
            x1 += 1
        ancho = x1 - x0
        if not (w * 0.20 <= ancho <= w * 0.85):
            continue

        # ¿Hay lima a los LADOS, en esta misma fila? El starburst rodea el
        # círculo, así que a la izquierda de x0 y a la derecha de x1 hay lima.
        # La barra de precios no: a sus lados está el fondo de la pieza.
        #
        # Mirar hacia ARRIBA no sirve — el círculo está pegado sobre la barra
        # y las dos son blancas, así que el recorrido vertical sale por el
        # tope del círculo y encuentra lima igual, dando por bueno el tramo
        # unido (ancho 720 donde el círculo mide 532).
        def hay_lima(x_desde, paso):
            for d in range(4, 60, 4):
                x = x_desde + paso * d
                if 0 <= x < w and lima[y, x]:
                    return True
            return False
        if not (hay_lima(x0, -1) and hay_lima(x1, +1)):
            continue

        if mejor is None or ancho > mejor[0]:
            mejor = (ancho, x0, x1, y)

    if not mejor:
        # Sin círculo reconocible no se pega nada: una foto puesta "a ver si
        # pega" arruina la pieza en silencio.
        return None

    # El alto se DEDUCE del ancho: en un círculo la fila más ancha pasa por el
    # centro, y ese ancho es el diámetro. Medirlo a pie une el círculo con la
    # barra que tiene pegada abajo.
    ancho, x0, x1, y_centro = mejor
    r = ancho // 2
    return (x0, max(0, y_centro - r), x1, min(h - 1, y_centro + r))


def _mascara_circular(size):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).ellipse([0, 0, size[0] - 1, size[1] - 1], fill=255)
    return m


def pegar_foto(pieza: bytes, foto: bytes, log=print) -> bytes:
    """La foto real del producto, dentro del círculo blanco de la pieza.

    Va CONTENIDA (nunca recortada) sobre blanco: las fotos de retail traen su
    propio fondo y forzarlas a llenar el círculo cortaría el producto. El
    24-ago se descartó el recorte automático con rembg porque con cientos de
    fotos reales de tiendas distintas falla demasiado.
    """
    base = Image.open(io.BytesIO(pieza)).convert("RGB")
    caja = _circulo_de(base)
    if not caja:
        log("[carrusel] no se encontró el círculo: la pieza va sin foto")
        return pieza
    x0, y0, x1, y1 = caja
    lado = min(x1 - x0, y1 - y0)
    if lado < 80:
        log("[carrusel] el círculo salió muy chico (%dpx): la pieza va sin foto" % lado)
        return pieza

    try:
        prod = Image.open(io.BytesIO(foto)).convert("RGB")
    except Exception as e:                                    # noqa: BLE001
        log("[carrusel] no se pudo abrir la foto del producto: %s" % e)
        return pieza

    interior = int(lado * 0.74)      # aire para que no toque el borde
    fw, fh = prod.size
    escala = min(interior / fw, interior / fh)
    nueva = prod.resize((max(1, int(fw * escala)), max(1, int(fh * escala))), Image.LANCZOS)

    disco = Image.new("RGB", (lado, lado), (255, 255, 255))
    disco.paste(nueva, ((lado - nueva.width) // 2, (lado - nueva.height) // 2))
    base.paste(disco, (x0, y0), _mascara_circular((lado, lado)))

    buf = io.BytesIO()
    base.save(buf, "PNG")
    return buf.getvalue()


def generar_slide1(template: int, nombre: str, precio_antes: float,
                   precio_ahora: float, foto: bytes | None = None,
                   intentos: int = 2, log=print) -> bytes | None:
    """La slide 1 con los datos del producto, con la foto real ya pegada."""
    ruta = TEMPLATES / ("t%d_slide1.png" % template)
    if not ruta.exists():
        raise FileNotFoundError("falta el template %s" % ruta)

    desc = max(0, round((1 - precio_ahora / precio_antes) * 100)) if precio_antes else 0
    prompt = PROMPT.format(nombre=nombre, desc=desc,
                           antes=_plata(precio_antes), ahora=_plata(precio_ahora))
    url_tpl = _subir_a_blotato(ruta.read_bytes())

    for intento in range(1, intentos + 1):
        creada = _pedir("/jobs/createTask", {
            "model": MODELO_EDICION,
            # `input_urls`, NO `image_urls` — ver el encabezado del módulo.
            "input": {"prompt": prompt, "input_urls": [url_tpl],
                      "aspect_ratio": "auto", "resolution": RESOLUCION},
        }, metodo="POST")
        tid = (creada.get("data") or {}).get("taskId") or creada.get("taskId")
        if not tid:
            log("[carrusel] intento %d: Kie no devolvió taskId — %s" % (intento, creada))
            continue

        est = _esperar(tid)
        if (est.get("state") or "").lower() != "success":
            log("[carrusel] intento %d falló: %s"
                % (intento, str(est.get("failMsg") or est.get("errorMessage") or est)[:160]))
            continue

        u = _url_resultado(est)
        if not u:
            log("[carrusel] intento %d: terminó sin URL" % intento)
            continue

        pieza = _bajar(u)
        return pegar_foto(pieza, foto, log=log) if foto else pieza

    log("[carrusel] no se pudo generar la slide 1 después de %d intentos" % intentos)
    return None


def slide2(template: int) -> bytes:
    """La slide fija, tal cual. Nunca se regenera."""
    return (TEMPLATES / ("t%d_slide2.png" % template)).read_bytes()


def armar(template: int, titulo: str, tienda: str, precio_antes: float,
          precio_ahora: float, foto: bytes | None = None,
          tipo: str = "oferta", log=print) -> dict | None:
    """Todo lo que hace falta para publicar: las 2 slides y el caption.

    Devuelve None si la slide 1 no se pudo generar — sin pieza no se publica.
    """
    nombre = ratia_texto.nombre_corto(titulo, log=log)
    log("[carrusel] titular: %r" % nombre)

    s1 = generar_slide1(template, nombre, precio_antes, precio_ahora, foto, log=log)
    if not s1:
        return None

    return {
        "slides": [s1, slide2(template)],
        "caption": ratia_texto.caption(nombre, tienda, precio_antes,
                                       precio_ahora, tipo, log=log),
        "template": template,
        "nombre_corto": nombre,
    }
