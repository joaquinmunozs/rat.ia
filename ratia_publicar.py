# -*- coding: utf-8 -*-
"""Rat.IA · publicar una oferta en Instagram vía Blotato.

QUÉ HACE
==============================================================================
Toma una oferta ya verificada, arma la pieza con `ratia_pieza_ia`, sube la
imagen a Blotato y crea la publicación.

⚠️ NO PUBLICA SOLO POR DEFECTO
==============================================================================
`publicar_oferta(..., confirmado=False)` es lo predeterminado: prepara todo,
deja la pieza lista para revisar, y NO llama a Blotato. Hay que pasar
`confirmado=True` explícitamente.

No es burocracia: publicar en el Instagram real de Rat.IA es irreversible
frente al público (se puede borrar, pero ya lo vieron), y Joaquín pidió
explícitamente que se le avise ANTES del primer posteo real. Un default que
publica convierte cualquier prueba en un incidente.

POR QUÉ NO SE REESCRIBE EL CLIENTE DE BLOTATO
==============================================================================
`services/barbara/blotato.mjs` (repo condor-ai-monorepo) ya implementa la API
—subir media, crear post, consultar estado— y está probado. Acá se habla con
la misma API HTTP en Python porque Rat.IA es Python, pero el CONTRATO es el
mismo: si Blotato cambia algo, los dos lados se arreglan igual.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import ratia_pieza_ia

BLOTATO_BASE = "https://backend.blotato.com/v2"


class SinCredenciales(RuntimeError):
    pass


def _clave() -> str:
    k = (os.environ.get("BLOTATO_API_KEY") or "").strip()
    if not k:
        raise SinCredenciales("Falta BLOTATO_API_KEY en el entorno.")
    return k


def _pedir(ruta: str, cuerpo: dict | None = None, metodo: str = "GET") -> dict:
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(f"{BLOTATO_BASE}{ruta}", data=datos, method=metodo)
    req.add_header("blotato-api-key", _clave())
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"Blotato {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from None


def caption_oferta(nombre: str, tienda: str) -> str:
    """El texto del post para el carril de OFERTAS.

    (Claude, 25-ago-2026) Pedido explícito de Joaquín: SIN precio y SIN
    link. El precio ya está en la pieza (la imagen lo muestra grande); el
    link nunca va en la descripción -- Instagram penaliza el alcance de los
    posts con link saliente, y un link en el caption tampoco genera nada.

    El pedido es que la persona COMENTE (eso sí suma alcance) y reciba el
    link por DM -- ver `ratia_manychat.py`. El caption entonces sólo tiene
    que dar dos datos (dónde está, qué es) y el gancho para comentar.
    """
    return (
        f"🐀 {nombre}\n"
        f"📍 Disponible en {tienda}\n\n"
        "¿Te lo mando? Comenta \"OFERTA\" 👇 y te paso el link por DM.\n\n"
        "#ofertas #chile #descuentos"
    )


def caption_error(nombre: str, tienda: str) -> str:
    """El texto del post para el carril de ERRORES DE PRECIO.

    (Claude, 25-ago-2026) Mismo principio de "sin link en la descripción",
    pero el framing es distinto: acá SÍ se avisa que el DM va a pedir el
    correo antes del link -- decirlo de entrada evita que alguien comente,
    no reciba el link al toque, y piense que el bot está roto.

    Nunca "¡ÚLTIMAS HORAS!" ni presión inventada: Rat.IA no controla si la
    tienda corrige el precio en 2 minutos o en 2 horas, y prometer algo que
    no se puede cumplir es lo que hace que la cuenta deje de darle
    credibilidad a la palabra "error de precio".
    """
    return (
        f"🚨 ERROR DE PRECIO — {nombre}\n"
        f"📍 {tienda}\n\n"
        "Puede durar minutos o corregirse en cualquier momento — comenta "
        "\"ERROR\" 👇 y te lo mandamos al DM apenas dejes tu correo (así "
        "también te avisamos si vuelve a pasar).\n\n"
        "#errordeprecio #chile #ofertas"
    )


def publicar_oferta(nombre_producto: str, precio_antes: float, precio_ahora: float,
                    foto: str | bytes, cuenta_id: str, tienda: str,
                    tipo: str = "oferta", pagina_id: str | None = None,
                    plataforma: str = "instagram",
                    color: str = "negro", confirmado: bool = False,
                    log=print) -> dict:
    """Arma la pieza y (si `confirmado`) la publica.

    `tipo` decide el caption: "oferta" (sin correo, link directo por DM) o
    "error" (el DM pide correo antes del link) -- ver `caption_oferta` /
    `caption_error`. `ratia_seleccion.Candidato.tipo` ya viene en ese mismo
    vocabulario, así que el llamador real no tiene que traducir nada.

    Devuelve un dict con `pieza` (bytes), `caption` y, si se publicó,
    `submission`. Con `confirmado=False` devuelve todo listo pero
    `publicado: False` — para revisar antes de apretar el gatillo.
    """
    pieza = ratia_pieza_ia.generar_pieza(
        nombre_producto, precio_antes, precio_ahora, foto, color=color, log=log)
    if not pieza:
        # generar_pieza ya explicó por qué en el log. No se sigue: sin pieza
        # verificada no hay publicación posible.
        return {"ok": False, "publicado": False,
                "motivo": "no se pudo generar/verificar la pieza"}

    texto = (caption_error(nombre_producto, tienda) if tipo == "error"
             else caption_oferta(nombre_producto, tienda))

    if not confirmado:
        log("[ratia-pub] pieza lista. NO se publicó: falta confirmado=True.")
        return {"ok": True, "publicado": False, "pieza": pieza, "caption": texto}

    # Blotato recibe la imagen por URL, no por bytes. Se sube primero a su
    # propio almacenamiento y se usa la URL que devuelve.
    log("[ratia-pub] subiendo la pieza a Blotato…")
    import base64
    data_uri = "data:image/png;base64," + base64.b64encode(pieza).decode()
    media = _pedir("/media", {"url": data_uri}, metodo="POST")
    url_media = media.get("url") or media.get("mediaUrl")
    if not url_media:
        return {"ok": False, "publicado": False,
                "motivo": f"Blotato no devolvió URL de la media: {media}"}

    destino = {"targetType": plataforma}
    if pagina_id:
        destino["pageId"] = pagina_id

    payload = {"post": {
        "accountId": cuenta_id,
        "target": destino,
        "content": {"platform": plataforma, "text": texto, "mediaUrls": [url_media]},
    }}
    log(f"[ratia-pub] publicando en {plataforma}…")
    envio = _pedir("/posts", payload, metodo="POST")
    log(f"[ratia-pub] publicado: {envio}")
    return {"ok": True, "publicado": True, "pieza": pieza,
            "caption": texto, "submission": envio}
