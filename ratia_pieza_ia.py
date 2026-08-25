# -*- coding: utf-8 -*-
"""Rat.IA · la pieza de oferta, generada con IA en vez de compuesta con PIL.

POR QUÉ SE CAMBIA (24-ago-2026, decisión de Joaquín)
==============================================================================
`plantillas_ratia.py` compone la pieza con Pillow: dibuja el texto encima de
una plantilla fija. Funciona, pero el resultado del 23-ago quedó feo — la
tipografía dibujada a mano no se acerca a lo que hace un diseñador, y cada
mejora exige más código de posicionamiento. `gpt-image-2` renderiza texto de
verdad bien (es su rasgo distintivo frente a los modelos anteriores) y por
Kie.ai cuesta centavos, así que sale más barato en tiempo y en plata.

LA FOTO DEL PRODUCTO SE PEGA, NO SE GENERA — Y NO ES NEGOCIABLE
==============================================================================
La IA hace el DISEÑO (fondo, tipografía, composición). La foto del producto
la pega Pillow encima, desde el archivo real.

POR QUÉ, con el caso que lo probó (24-ago-2026):
En la primera prueba se le pasó al modelo la URL de una foto de MercadoLibre
que resultó ser el placeholder de "imagen no encontrada". El modelo, en vez
de fallar, **inventó un frasco entero**: dibujó una botella ámbar con una
etiqueta que decía "ACEITE DE SEMILLA DE CALABAZA · PRENSADO EN FRÍO · 100%
NATURAL · 250 ML".

Nada de eso venía del producto real. Son afirmaciones de producto —cómo se
elabora, su pureza, su contenido— inventadas por un modelo y listas para
publicarse como publicidad. Ese frasco no existe.

Un modelo de imagen SIEMPRE devuelve algo: cuando no tiene el dato, lo
completa. Por eso `image-to-image` no alcanza como garantía, y por eso la
verificación de precios de más abajo tampoco basta: verifica los números,
no el producto. La única garantía real es que la foto no pase nunca por el
modelo.

⚠️ POR QUÉ SE VERIFICAN LOS PRECIOS ANTES DE PUBLICAR
==============================================================================
Esto es lo que hace que el cambio sea seguro y no un riesgo nuevo.

Un modelo de imagen, por bueno que sea con el texto, puede escribir $89.900
donde debía decir $89.990. En una pieza decorativa eso es un defecto; en una
oferta que se publica SOLA en Instagram es un precio equivocado anunciado al
público, y el que llega a comprar tiene razón en reclamar.

Por eso `generar_pieza()` no devuelve la imagen y ya: se la vuelve a mostrar
a un modelo que lee los números y confirma que sean EXACTAMENTE los que se le
pidieron. Si no calzan, reintenta. Si tras los reintentos siguen sin calzar,
devuelve `None` — y quien llame decide, pero nunca publica un precio que no
se pudo verificar.

Es el mismo principio que ya usa `revision.mjs` de Bárbara con los carruseles:
mirar la pieza terminada antes de mandarla, porque el modelo no avisa cuando
se equivoca.
"""
from __future__ import annotations

import base64
import io
import json
import os
import time
import urllib.error
import urllib.request

from PIL import Image, ImageDraw

KIE_BASE = "https://api.kie.ai/api/v1"
# Solo texto-a-imagen: la foto real NUNCA pasa por el modelo (ver encabezado).
MODELO_TXT2IMG = "gpt-image-2-text-to-image"

# Identidad de Rat.IA, la misma de las plantillas de PIL — así la pieza
# generada por IA y la compuesta a mano se ven de la misma marca.
LIMA_HEX = "#B9E606"
INTENTOS = 3


class SinCredenciales(RuntimeError):
    pass


def _clave() -> str:
    k = (os.environ.get("KIE_API_KEY") or "").strip()
    if not k:
        raise SinCredenciales("Falta KIE_API_KEY en el entorno.")
    return k


def _pedir(ruta: str, cuerpo: dict | None = None, metodo: str = "GET") -> dict:
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(f"{KIE_BASE}{ruta}", data=datos, method=metodo)
    req.add_header("Authorization", f"Bearer {_clave()}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", "replace")[:300]
        # 402 y 401 no se reintentan: no es un problema pasajero.
        raise RuntimeError(f"Kie {e.code}: {detalle}") from None


def _esperar(task_id: str, timeout_s: int = 300) -> dict:
    """La API de Kie es asíncrona: crea la tarea y hay que consultar el estado."""
    limite = time.time() + timeout_s
    ultimo = {}
    while time.time() < limite:
        r = _pedir(f"/jobs/recordInfo?taskId={task_id}")
        ultimo = r.get("data") or r
        estado = (ultimo.get("state") or "").lower()
        if estado in ("success", "fail"):
            return ultimo
        time.sleep(5)
    raise TimeoutError(f"La tarea {task_id} no terminó en {timeout_s}s "
                       f"(último estado: {ultimo.get('state')})")


def _url_resultado(estado: dict) -> str | None:
    rj = estado.get("resultJson")
    if isinstance(rj, str):
        try:
            rj = json.loads(rj)
        except Exception:
            rj = {}
    rj = rj or estado
    urls = rj.get("resultUrls") or rj.get("result_urls") or []
    return urls[0] if urls else rj.get("url")


def _plata(n: float) -> str:
    """$1.234.567 — el formato chileno, que es como lo lee el comprador."""
    return "$" + f"{int(round(n)):,}".replace(",", ".")


def _prompt(nombre: str, antes: float, ahora: float, color: str) -> str:
    """El prompt de diseño.

    Los precios van ENTRE COMILLAS y con la instrucción de copiarlos carácter
    por carácter: es la diferencia entre "escribe el precio" (el modelo lo
    reformatea a su gusto) y "escribe exactamente esto".

    Y se le pide EXPLÍCITAMENTE que NO dibuje el producto: solo la tarjeta
    vacía donde después se pega la foto real. Sin esa instrucción el modelo
    rellena el hueco con un frasco inventado — pasó en la primera prueba.
    """
    desc = max(0, round((1 - ahora / antes) * 100)) if antes else 0
    fondo = "negro puro (#0A0A0A)" if color == "negro" else "blanco puro (#FFFFFF)"
    texto = "blanco" if color == "negro" else "negro"
    return f"""Diseña una pieza cuadrada de Instagram para una oferta de precio, estilo
editorial moderno y limpio, calidad de agencia.

FONDO: {fondo}. Texto principal en {texto}. Color de acento: verde lima {LIMA_HEX}.

CONTENIDO EXACTO (copia cada texto carácter por carácter, sin reformatear,
sin traducir, sin cambiar ni un dígito ni un punto):
· Titular grande arriba a la izquierda: "{nombre}"
· Debajo, enorme y en verde lima: "¡{desc}% OFF!"
· Precio anterior, más chico y TACHADO con una línea: "{_plata(antes)}"
· Precio nuevo, grande y destacado: "{_plata(ahora)}"

IMPORTANTE - NO DIBUJES NINGÚN PRODUCTO. En la mitad derecha, deja una tarjeta
CUADRADA COMPLETAMENTE BLANCA Y VACÍA, con esquinas redondeadas y un marco
verde lima de unos 20px de grosor. Esa tarjeta tiene que quedar totalmente
lisa por dentro: sin frascos, sin botellas, sin cajas, sin sombras, sin
reflejos, sin texto, sin ningún objeto. Es un espacio reservado que se
rellena después con una fotografía real.

TIPOGRAFÍA: sans-serif geométrica pesada (tipo Poppins ExtraBold) para los
titulares. Los números de precio deben leerse perfectamente nítidos.

NO agregues ningún texto que no esté en la lista de arriba. Sin logos
inventados, sin marcas de agua, sin texto decorativo de relleno."""


def _bajar(url: str, timeout: int = 60) -> bytes:
    """Baja una imagen.

    El User-Agent NO es decorativo: el CDN de MercadoLibre responde 403 a las
    peticiones sin uno de navegador. Sin esto, la foto real nunca llega y la
    pieza se descarta entera — que es como se descubrió (tres intentos
    seguidos con `HTTP Error 403: Forbidden`).
    """
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
        "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _hueco_blanco(base: Image.Image) -> tuple[int, int, int, int] | None:
    """Encuentra la tarjeta blanca vacía que dejó el modelo.

    CÓMO, y por qué así: se recorre la MITAD DERECHA (donde el prompt pide la
    tarjeta) buscando el rectángulo continuo de píxeles casi blancos más
    grande. No se usa una posición fija porque el modelo la ubica distinto en
    cada corrida — fijarla haría que la foto cayera encima del texto la
    primera vez que decida moverla.

    Devuelve (x0, y0, x1, y1) o None si no hay una tarjeta reconocible, que
    es la señal de que esa generación no sirve y hay que reintentar.
    """
    w, h = base.size
    px = base.convert("RGB").load()
    # Muestreo cada 8 px: a 2048 de lado son ~65k lecturas en vez de 4M, y la
    # tarjeta mide cientos de píxeles — no se pierde por saltar de a 8.
    paso = 8
    blanco = lambda c: c[0] > 232 and c[1] > 232 and c[2] > 232

    mejor = None
    for y0 in range(0, h, paso * 4):
        if not blanco(px[min(w - 1, int(w * 0.62)), y0]):
            continue
        # Alto del bloque blanco en esta columna testigo
        y1 = y0
        while y1 + paso < h and blanco(px[min(w - 1, int(w * 0.62)), y1 + paso]):
            y1 += paso
        if y1 - y0 < h * 0.18:
            continue
        # Ancho, midiendo en la mitad vertical del bloque
        ym = (y0 + y1) // 2
        x0 = int(w * 0.62)
        while x0 - paso > 0 and blanco(px[x0 - paso, ym]):
            x0 -= paso
        x1 = int(w * 0.62)
        while x1 + paso < w - 1 and blanco(px[x1 + paso, ym]):
            x1 += paso
        area = (x1 - x0) * (y1 - y0)
        if (x1 - x0) > w * 0.18 and (not mejor or area > mejor[4]):
            mejor = (x0, y0, x1, y1, area)
    return mejor[:4] if mejor else None


def _pegar_foto(pieza_bytes: bytes, foto_bytes: bytes, log=print) -> bytes | None:
    """Pega la foto REAL dentro de la tarjeta blanca de la pieza generada.

    `contain`, nunca `cover`: recortar la foto de un producto puede cortarle
    la etiqueta o dejarlo irreconocible. Se prefiere que sobre fondo blanco
    antes que mostrar el producto a medias.
    """
    base = Image.open(io.BytesIO(pieza_bytes)).convert("RGB")
    hueco = _hueco_blanco(base)
    if not hueco:
        log("[ratia-ia] la pieza no trae una tarjeta blanca reconocible")
        return None

    x0, y0, x1, y1 = hueco
    # Margen interior: la foto no toca el marco lima.
    m = int(min(x1 - x0, y1 - y0) * 0.08)
    caja = (x1 - x0 - m * 2, y1 - y0 - m * 2)
    if caja[0] < 40 or caja[1] < 40:
        log("[ratia-ia] la tarjeta detectada es demasiado chica")
        return None

    foto = Image.open(io.BytesIO(foto_bytes)).convert("RGBA")
    foto.thumbnail(caja, Image.LANCZOS)
    fx = x0 + m + (caja[0] - foto.width) // 2
    fy = y0 + m + (caja[1] - foto.height) // 2

    # Se blanquea la tarjeta antes de pegar: si el modelo dejó una sombra o
    # un reflejo pese a la instrucción, queda tapado y no se cuela un objeto
    # a medio dibujar detrás de la foto real.
    ImageDraw.Draw(base).rectangle([x0 + 2, y0 + 2, x1 - 2, y1 - 2], fill=(255, 255, 255))
    base.paste(foto, (fx, fy), foto)

    salida = io.BytesIO()
    base.save(salida, format="PNG")
    return salida.getvalue()


def _verificar_precios(url_imagen: str, antes: float, ahora: float,
                       anthropic_key: str) -> tuple[bool, str]:
    """Le muestra la pieza terminada a un modelo y le pide leer los precios.

    Devuelve (ok, detalle). `ok=False` significa "no publicar": o los números
    salieron mal, o no se pudo comprobar. Las dos cosas terminan igual —
    publicar un precio sin verificar es el riesgo que este módulo existe para
    evitar.
    """
    try:
        crudo = url_imagen if isinstance(url_imagen, bytes) else _bajar(url_imagen)
        img_b64 = base64.b64encode(crudo).decode()
    except Exception as e:
        return False, f"no se pudo leer la pieza para verificar: {e}"

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
                    "Lee los precios que aparecen en esta imagen. Responde SOLO "
                    'un JSON: {"antes": "...", "ahora": "...", "descuento": "..."} '
                    "copiando el texto EXACTO tal como está escrito en la imagen "
                    "(incluyendo el signo $ y los puntos). Si algún dato no "
                    "aparece, pon null."},
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
    except Exception as e:
        return False, f"no se pudo verificar con el modelo: {e}"

    txt = "".join(b.get("text", "") for b in resp.get("content", []))
    ini, fin = txt.find("{"), txt.rfind("}")
    if ini < 0 or fin < 0:
        return False, f"la verificación no devolvió JSON: {txt[:120]}"
    try:
        leido = json.loads(txt[ini:fin + 1])
    except Exception:
        return False, f"JSON inválido en la verificación: {txt[:120]}"

    def normal(s):
        return "".join(ch for ch in str(s or "") if ch.isdigit())

    esperado_antes, esperado_ahora = normal(_plata(antes)), normal(_plata(ahora))
    real_antes, real_ahora = normal(leido.get("antes")), normal(leido.get("ahora"))

    if real_antes != esperado_antes or real_ahora != esperado_ahora:
        return False, (f"los precios de la pieza no calzan — "
                       f"esperado antes={_plata(antes)} ahora={_plata(ahora)}; "
                       f"la imagen dice antes={leido.get('antes')} "
                       f"ahora={leido.get('ahora')}")
    return True, "precios verificados"


def generar_pieza(nombre_producto: str, precio_antes: float, precio_ahora: float,
                  foto: str | bytes, color: str = "negro",
                  verificar: bool = True, log=print) -> bytes | None:
    """Genera la pieza terminada y la devuelve como PNG en bytes.

    `foto` es la URL o los bytes de la fotografía REAL del producto. Se pega
    con Pillow después de generar el diseño — nunca se le pasa al modelo.

    Devuelve `None` cuando la pieza no se pudo armar o verificar. Eso
    significa NO PUBLICAR: es preferible saltarse una oferta a publicar una
    con un precio o un producto que no se pudo comprobar.

    `verificar=False` solo para pruebas de diseño.
    """
    if color not in ("negro", "blanco"):
        raise ValueError("color tiene que ser 'negro' o 'blanco'")

    anthropic_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if verificar and not anthropic_key:
        raise SinCredenciales(
            "Falta ANTHROPIC_API_KEY: sin ella no se pueden verificar los "
            "precios, y publicar sin verificar no es una opción. Usá "
            "verificar=False solo para probar el diseño.")

    try:
        foto_bytes = foto if isinstance(foto, bytes) else _bajar(foto)
    except Exception as e:
        log(f"[ratia-ia] ERROR: no se pudo bajar la foto del producto: {e}")
        return None

    # Una foto que no abre como imagen suele ser un placeholder o un error
    # HTML disfrazado. Mejor detenerse acá que publicar una tarjeta vacía.
    try:
        Image.open(io.BytesIO(foto_bytes)).verify()
    except Exception:
        log("[ratia-ia] ERROR: la foto del producto no es una imagen valida")
        return None

    prompt = _prompt(nombre_producto, precio_antes, precio_ahora, color)

    for intento in range(1, INTENTOS + 1):
        creada = _pedir("/jobs/createTask", {
            "model": MODELO_TXT2IMG,
            "input": {"prompt": prompt, "aspect_ratio": "1:1", "resolution": "2K"},
        }, metodo="POST")
        task_id = (creada.get("data") or {}).get("taskId") or creada.get("taskId")
        if not task_id:
            log(f"[ratia-ia] intento {intento}: Kie no devolvió taskId — {creada}")
            continue

        estado = _esperar(task_id)
        if (estado.get("state") or "").lower() != "success":
            log(f"[ratia-ia] intento {intento} falló: "
                f"{estado.get('failMsg') or estado.get('errorMessage') or estado}")
            continue

        url = _url_resultado(estado)
        if not url:
            log(f"[ratia-ia] intento {intento}: terminó sin URL")
            continue

        try:
            pieza = _pegar_foto(_bajar(url), foto_bytes, log=log)
        except Exception as e:
            log(f"[ratia-ia] intento {intento}: no se pudo componer — {e}")
            continue
        if not pieza:
            continue  # sin tarjeta reconocible: se reintenta el diseño

        if not verificar:
            return pieza

        ok, detalle = _verificar_precios(pieza, precio_antes, precio_ahora, anthropic_key)
        if ok:
            log(f"[ratia-ia] pieza lista y verificada (intento {intento})")
            return pieza
        log(f"[ratia-ia] intento {intento} descartado: {detalle}")

    log("[ratia-ia] ERROR: no se logro una pieza correcta - NO se publica. "
        "Revisar a mano o usar las plantillas de plantillas_ratia.py.")
    return None
