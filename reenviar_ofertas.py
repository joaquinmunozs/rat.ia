# -*- coding: utf-8 -*-
"""Reenvía al grupo de Rat.IA las ofertas/errores de precio del canal de un
aliado externo (contenido redistribuido con su autorización).

QUÉ HACE Y QUÉ NO
------------------------------------------------------------------------------
Escucha mensajes nuevos en los canales de origen (via cuenta de usuario real,
Telethon — no un bot, porque los bots no pueden "espiar" canales ajenos, solo
los que administran) y los reenvía al tópico de Rat.IA que corresponde, sin
marca de origen (a pedido): el mensaje llega con el formato normal de Rat.IA,
sin decir de qué canal salió.

NO hace nada con cookies, rastreo entre sitios, ni bots de "login" — eso se
descartó a propósito. Esto es un reenvío de texto, plano y simple.

EL RUTEO ES POR CANAL, NO POR EL % DEL TEXTO (20-ago-2026, rediseñado)
------------------------------------------------------------------------------
Cada canal del aliado YA está segmentado por su propio nombre: "Ofertas
Chile 50%" solo publica alrededor de ese piso, "80" son los errores más
grandes, "Tecno"/"Supermercado" son por categoría. Rutear tratando de leer
el % del TEXTO de cada mensaje (como hacía la v1 de este script) es más
frágil: si el formato de un mensaje no calza con el regex, se pierde el
mensaje aunque el canal mismo ya garantice que es un hallazgo válido.

Por eso el mapa canal → tópico es la fuente de verdad (variables
CANALES_ERRORES, CANALES_OFERTAS, CANALES_SUPERMERCADO, CANALES_TECNO,
CANALES_VUELOS, CANALES_HOGAR más abajo). Un canal YA CATEGORIZADO se
reenvía SIEMPRE, sin exigirle ningún formato al texto -- el canal mismo es
la garantía. El filtro de "(NN%)"/"$NNN" (`_parece_oferta`) solo se evalúa
para un canal que llegue en CANALES_ORIGEN pero no esté en NINGUNA lista de
categoría: ahí sí conviene ser cauto antes de reenviar algo a ciegas, y se
avisa en el log "canal sin categoría asignada" para arreglarlo a mano en
vez de mandarlo al tópico equivocado en silencio.

BUG REAL encontrado y corregido el 20-ago-2026: antes el filtro de % se le
exigía a TODOS los mensajes, categorizados o no, y el regex solo aceptaba
UN decimal ("98,9%"). El bot del aliado a veces manda DOS ("95,38%" en el
canal "80", "39.34%" con punto en COCHA) -- verificado leyendo mensajes
reales vía Telethon, no a ciegas. Resultado: se perdían en silencio
hallazgos reales del canal "80", el más importante, y el canal COCHA
(Vuelos) probablemente no había reenviado NADA nunca por el mismo motivo.
El regex ahora acepta cualquier cantidad de decimales, y de todos modos ya
no aplica a canales categorizados.

RUTEO POR CANAL DE ORIGEN (tal como quedaron los canales del aliado)
------------------------------------------------------------------------------
    Tecno                 -> 📱 Electrónicos         (CANALES_TECNO)
    Supermercado          -> 🛒 Supermercado         (CANALES_SUPERMERCADO)
    COCHA                 -> ✈️ Vuelos               (CANALES_VUELOS)
    (ninguno todavía)     -> 🏠 Hogar                (CANALES_HOGAR, por si
                             el aliado suma un canal de esa categoría después)

⚠️ CAMBIO DEL 25-ago-2026: los canales GENERALES del aliado ("75%", "80",
"50%", "60%") ya NO deciden el tópico. Su vara no es la nuestra: su "-80%"
suele estar medido contra un precio de lista que la tienda nunca cobró. Ahora
el destino sale de la caída REAL, calculada contra el mínimo de 30 días de la
base de Héctor (`_topico_por_caida`):

    caída 85% - 99%   -> 🚨 Errores de precio   (VIGIA_TOPICO_ERRORES_GRAVES)
    caída 70% - 85%   -> 🏷️ Ofertas 70%         (VIGIA_TOPICO_OFERTAS70)
    caída 40% - 70%   -> 🏷️ Ofertas reales      (VIGIA_TOPICO_OFERTAS)

Los canales de CATEGORÍA (Tecno, Supermercado, Vuelos, Hogar) siguen mandando
por canal: ahí el canal sabe algo —el rubro— que el porcentaje no dice.

EL AVISO SE REARMA, NO SE REENVÍA (25-ago-2026)
------------------------------------------------------------------------------
El texto del aliado ya no llega al canal. Se arma uno nuevo con el formato de
Rat.IA (`alertas.armar_texto`) y datos propios: comercio, producto, precio
actual, el sondeo histórico CON LA FECHA de cada precio, y el link. Motivos:

  · arrastraba el rank del aliado ("DRank"), que no es el nuestro;
  · arrastraba su "antes" inflado como si fuera una referencia real; y
  · lo encabezaba un "🔎 sin verificar del todo" que salía en el 100% de los
    mensajes. No era exceso de prudencia: `detectar_producto` no reconocía
    `simple.ripley.cl` como `ripley.cl` (comparaba el dominio exacto, no el
    sufijo), así que NUNCA llegaba a cruzar contra la base propia. Arreglado
    en `hector2_filtro.tienda_de`.

Amazon se descarta entero: todas sus ofertas resultaron ser productos que no
despachan a Chile (`hector2_filtro.esta_bloqueada`).
El canal "... Chat" NO es un canal de ofertas, es conversación: no debe
estar en CANALES_ORIGEN ni en ninguna categoría.

REQUIERE UNA SESIÓN DE USUARIO REAL, NO SE PUEDE AUTOMATIZAR DE UNA
------------------------------------------------------------------------------
Telethon necesita loguearse UNA VEZ como una cuenta de Telegram de verdad,
con el código que llega al teléfono. Eso no lo puede hacer un script solo —
hay que correr `python reenviar_ofertas.py --login` a mano, una sola vez,
y de ahí el archivo `.session` que se genera queda para todas las corridas
siguientes sin volver a pedir código.

Para canales PRIVADOS (a los que se entró por link de invitación, como el
"addlist" del aliado — el caso normal acá) no hay @usuario público, solo un
ID numérico interno. `listar_canales.py` lista todos los chats de la sesión
con su ID.

CORRE COMO PROCESO QUE NO SE APAGA, NO COMO CRON
------------------------------------------------------------------------------
Esto tiene que quedar escuchando todo el tiempo — no sirve un cron de
GitHub Actions de "correr y listo". Necesita un hostname que no se apague:
un VPS chico o un servicio tipo Railway/Fly.io (~$5 USD/mes). GitHub Actions
NO alcanza para esto (está pensado para trabajos que terminan, no para
quedarse escuchando).

    python reenviar_ofertas.py --login     # una sola vez, a mano
    python reenviar_ofertas.py             # queda escuchando

VARIABLES DE ENTORNO
------------------------------------------------------------------------------
    TG_API_ID, TG_API_HASH        de https://my.telegram.org/apps (cuenta que
                                   ya está unida a los canales de origen)
    CANALES_ORIGEN                 @usuario o ID de TODOS los canales a
                                   escuchar, separados por coma. SIN el canal
                                   "... Chat".
    CANALES_ERRORES                subconjunto de arriba -> VIGIA_TOPICO_ERRORES
    CANALES_OFERTAS                subconjunto de arriba -> VIGIA_TOPICO_OFERTAS
    CANALES_SUPERMERCADO           subconjunto de arriba -> VIGIA_TOPICO_SUPERMERCADO
    CANALES_TECNO                  subconjunto de arriba -> VIGIA_TOPICO_ELECTRONICOS
    CANALES_VUELOS                 subconjunto de arriba -> VIGIA_TOPICO_VUELOS
    CANALES_HOGAR                  subconjunto de arriba -> VIGIA_TOPICO_HOGAR
    TELEGRAM_BOT_TOKEN, VIGIA_CHAT_ID          los mismos que ya usa alertas.py
    VIGIA_TOPICO_ERRORES, VIGIA_TOPICO_OFERTAS, VIGIA_TOPICO_ELECTRONICOS,
    VIGIA_TOPICO_SUPERMERCADO, VIGIA_TOPICO_VUELOS, VIGIA_TOPICO_HOGAR
                                   IDs de tópico del grupo de Rat.IA
    VIGIA_TOPICO_OFERTAS70         caída 70-85%. Es el tópico VIEJO de errores,
                                   sólo renombrado, así que su id no cambió.
    VIGIA_TOPICO_ERRORES_GRAVES    caída 85%+. Tópico nuevo (25-ago-2026).
                                   Si falta, todo el 70%+ vuelve a caer junto
                                   en VIGIA_TOPICO_ERRORES como antes.
    RATIA_IG_AUTO                  el selector de Instagram dentro de este
                                   mismo proceso (25-ago-2026). Sin definir,
                                   la tarea NI ARRANCA y nada cambia.
                                   "ensayo" = corre y loguea qué publicaría,
                                   sin publicar. "1" = publica de verdad.
                                   Poner "ensayo" primero y mirar los logs no
                                   es una formalidad: es la única forma de ver
                                   qué elige antes de que Instagram lo vea.
    HECTOR2_DB                     dónde vive hector2.db. En Railway TIENE que
                                   apuntar al volumen (/data): sin eso, cada
                                   deploy borraba el historial entero.
    HECTOR2_BASE_HECTOR            ídem para la copia de solo lectura de la
                                   base de Héctor.
    HECTOR2_PERMITIR_AMAZON=1      reactiva Amazon, hoy descartado por no
                                   despachar a Chile.
    VIGIA_TOPICO_DUDOSOS           (Hector2) tópico donde caen los hallazgos
                                   que no se pudieron confirmar contra nada.
                                   Si no se define, esos mensajes se mandan
                                   igual a su tópico normal, marcados -- nunca
                                   se pierden en silencio por falta de config.

HECTOR2: EL FILTRO DE CONFIANZA (23-ago-2026)
------------------------------------------------------------------------------
Hasta acá este archivo era un relay puro: si el canal ya venía categorizado,
se reenviaba SIEMPRE, sin mirar si la caída declarada era real. El caso que lo
destapó: un jugo en caja que "el aliado" anunciaba bajando de $2.000 a $400,
cuando siempre costó $400 -- el mismo fraude de anclaje de precio que
Consumer Reports midió en más de 30% de las "ofertas" de grandes retailers
en 2024.

Antes de reenviar, `hector2_filtro.evaluar_mensaje` cruza el producto contra
la base REAL de Héctor (`descargar_base_hector.py`, un respaldo de solo
lectura) y, si no está ahí, intenta verificarlo en vivo. El resultado nunca es
un simple sí/no silencioso -- ver `hector2_db.py` para el ritmo adaptativo por
tópico (ni se satura el grupo, ni queda mudo) y `hector2_filtro.py` para el
porqué de cada señal.
"""
import argparse
import asyncio
import base64
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

try:
    from telethon import TelegramClient, events
    from telethon.extensions import html as tl_html
except ImportError:
    print("Falta telethon: pip install telethon")
    raise

import alertas
import baseprecios
import descargar_base_hector
import hector2_db
import hector2_filtro

# Objetivo de mensajes por día, por tópico -- lo que dispara el ajuste
# adaptativo de `hector2_db.ajustar_umbral`. Son un punto de partida, no un
# número medido: la guía de referencia para canales de Telegram no-noticiosos
# es 1-2 posts/día como base, 3 como máximo aceptable si el contenido vale la
# pena, y que 4+ ya deteriora el alcance (postmypost.io, floqal.com, 2026).
# Acá se ajustan un poco al alza porque son alertas que el suscriptor pidió
# explícitamente, no contenido genérico -- pero quedan pensados para
# CALIBRARSE con datos reales de las primeras semanas, no para quedarse fijos.
OBJETIVOS_RITMO = {
    "VIGIA_TOPICO_ERRORES": (1, 4),
    "VIGIA_TOPICO_OFERTAS": (3, 8),
    "VIGIA_TOPICO_ELECTRONICOS": (2, 6),
    "VIGIA_TOPICO_HOGAR": (2, 6),
    "VIGIA_TOPICO_SUPERMERCADO": (2, 6),
    "VIGIA_TOPICO_VUELOS": (1, 4),
}

# Estado compartido del proceso. Vive en un dict (no en variables sueltas)
# para que la tarea de refresco pueda reemplazar la conexión sin tener que
# declarar `global` en cada función que la usa.
_ESTADO = {"con_hector": None, "con_h2": None}

# BUG REAL (23-ago-2026): `evaluar_mensaje` corre dentro de
# `asyncio.to_thread` para no bloquear el event loop con la verificación en
# vivo (red), pero eso mueve las consultas a con_hector/con_h2 a un hilo
# distinto del que las abrió -- sqlite3 lo rechaza con
# "SQLite objects created in a thread can only be used in that same thread"
# en el primer mensaje real que llegó. `check_same_thread=False` (ver
# hector2_filtro.abrir_solo_lectura y hector2_db.abrir) le saca esa barrera
# a sqlite3, pero sqlite3 SIGUE sin ser seguro para uso concurrente desde
# varios hilos a la vez -- este lock es lo que de verdad lo hace seguro:
# nunca hay dos hilos tocando con_hector/con_h2 al mismo tiempo.
_DB_LOCK = asyncio.Lock()


def _reabrir_con_hector(ruta):
    anterior = _ESTADO.get("con_hector")
    _ESTADO["con_hector"] = hector2_filtro.abrir_solo_lectura(ruta)
    if anterior:
        try:
            anterior.close()
        except Exception:                                     # noqa: BLE001
            pass


async def _tarea_refresco_base(intervalo=None):
    """Vuelve a bajar precios.db de Héctor cada `intervalo` segundos, sin
    interrumpir el reenvío mientras tanto -- se descarga a un .tmp y se
    reemplaza recién al final (ver descargar_base_hector.descargar)."""
    intervalo = intervalo or descargar_base_hector.INTERVALO_SEG
    while True:
        await asyncio.sleep(intervalo)
        try:
            ruta, nueva = await asyncio.to_thread(descargar_base_hector.asegurar, forzar=True)
            if ruta and nueva:
                async with _DB_LOCK:
                    _reabrir_con_hector(ruta)
                print("[hector2] base de Héctor refrescada")
        except Exception as e:                                # noqa: BLE001
            print("[hector2] fallo refrescando la base: %s" % str(e)[:150])


# ── EL SELECTOR DE INSTAGRAM, EN EL MISMO PROCESO ───────────────────────────
#
# (Claude, 25-ago-2026) Cierra "engancharlo a algo que corra solo" de la
# bitácora del 25-ago (tarde). Va acá y no en un cron aparte porque este
# proceso ya está levantado 24/7 en Railway, ya mantiene la copia de
# `precios.db` fresca (`_tarea_refresco_base`) y ya tiene abierta la
# `hector2.db` de la que el selector saca sus candidatos. Un cron aparte
# tendría que rehacer las tres cosas.
#
# ── POR QUÉ POR DEFECTO NO HACE NADA ────────────────────────────────────────
# `RATIA_IG_AUTO` decide, y sin ella la tarea NI SIQUIERA ARRANCA: el
# comportamiento queda idéntico al de hoy. Los tres escalones:
#
#     (sin definir)  la tarea no existe. Nada cambia.
#     "ensayo"       corre las pasadas y loguea qué publicaría. NO publica.
#     "1"            publica de verdad.
#
# El escalón del medio es el que importa y por eso existe: deja mirar en los
# logs de Railway qué habría salido, durante días si hace falta, antes de que
# nada llegue a Instagram. Es la misma regla que ya traía `ratia_publicar` --
# "un selector automático que publica solo, sin que nadie lo haya visto correr
# en producción al menos una vez, es el tipo de incidente que ya se evitó una
# vez con esa misma regla" (bitácora del 25-ago).
RATIA_IG_INTERVALO_SEG = 600


def _ig_modo():
    """"" (apagado) | "ensayo" | "1"."""
    return (os.environ.get("RATIA_IG_AUTO") or "").strip().lower()


def _pasada_instagram(confirmar):
    """Una pasada del selector, con conexiones PROPIAS.

    No reusa `_ESTADO["con_hector"]` / `["con_h2"]` a propósito. Esas están
    serializadas con `_DB_LOCK`, y una pasada del selector baja fichas, llama
    a un modelo de imágenes y publica: tener el lock tomado todo ese rato
    dejaría el reenvío del aliado congelado durante minutos. Es el mismo error
    que el 11-ago mantenía el lock de escritura tomado durante descargas HTTP.
    `hector2.db` está en WAL, así que una segunda conexión convive sin
    problema, y la de Héctor se abre en modo `ro`.

    Import perezoso: si algo del selector no importa (una dependencia que
    falta en el contenedor, por ejemplo), el bot de reenvío -- que es lo que
    de verdad está en producción -- no se cae con él.
    """
    import ratia_ig_selector

    ruta_precios, _ = descargar_base_hector.asegurar()
    con_precios = hector2_filtro.abrir_solo_lectura(ruta_precios)
    con_h2 = hector2_db.abrir()
    try:
        return ratia_ig_selector.una_pasada(
            con_precios, con_h2, confirmar=confirmar,
            log=lambda m: print("[ratia-ig] %s" % m))
    finally:
        con_precios.close()
        con_h2.close()


async def _tarea_selector_instagram(intervalo=None):
    """Cada `intervalo`, mira si algo cumple su ventana y le toca salir.

    El intervalo no es el retraso de publicación: las ventanas reales (30 min
    para errores, 1-2 h para ofertas, corte 23:30) las decide
    `ratia_seleccion`, y esta tarea sólo pregunta seguido. 10 minutos da
    granularidad de sobra para una ventana de 30 y no gasta nada.
    """
    modo = _ig_modo()
    if not modo:
        return
    intervalo = intervalo or RATIA_IG_INTERVALO_SEG
    confirmar = (modo == "1")
    print("[ratia-ig] selector activo cada %ds -- %s"
          % (intervalo, "PUBLICA de verdad" if confirmar else "ENSAYO, no publica"))
    while True:
        await asyncio.sleep(intervalo)
        try:
            await asyncio.to_thread(_pasada_instagram, confirmar)
        except Exception as e:                                # noqa: BLE001
            # Una pasada que falla no puede matar la tarea: si muere, deja de
            # publicarse en Instagram y nadie se entera (el reenvío a Telegram
            # sigue andando, así que el servicio "se ve" sano).
            print("[ratia-ig] fallo la pasada: %s" % str(e)[:200])


async def _tarea_ajustar_ritmos(intervalo=3600):
    """Una vez por hora, no por mensaje -- perseguir ruido de corto plazo
    haría que el umbral bailara todo el día en vez de converger. Ver el
    docstring de `hector2_db.ajustar_umbral`."""
    con = _ESTADO["con_h2"]
    while True:
        await asyncio.sleep(intervalo)
        try:
            for variable, (piso, techo) in OBJETIVOS_RITMO.items():
                topico = (os.environ.get(variable) or "").strip()
                if not topico:
                    continue
                enviados = hector2_db.contar_enviados_24h(con, topico)
                hector2_db.ajustar_umbral(con, topico, enviados, piso, techo)
        except Exception as e:                                # noqa: BLE001
            print("[hector2] fallo ajustando ritmos: %s" % str(e)[:150])

# EL ARCHIVO .session ES LA CONTRASEÑA DE LA CUENTA DE TELEGRAM DEL ALIADO
# (23-ago-2026). No va al repo (ver .gitignore), así que cada deploy nuevo
# levanta un contenedor sin él -- y este servicio corre en Railway SIN un
# volumen persistente por defecto, así que "cada deploy nuevo" incluía
# literalmente cada redeploy del código, no solo el primero.
#
# EL INCIDENTE (23-ago-2026): reconectar este servicio de Railway del repo
# privado archivado al público (para que los cambios de código llegaran a
# producción) disparó un rebuild sin el .session, y el proceso quedó en
# crash-loop pidiendo login interactivo (`EOFError: EOF when reading a
# line`) porque el contenedor no tiene terminal. Se recuperó una copia local
# vieja del archivo (20-ago).
#
# `railway volume files upload` PARECE funcionar pero corrompe binarios: subió
# un .session de 36.864 bytes y el archivo que quedó en el volumen medía
# 28.672 -- verificado comparando checksums, dos veces, con --overwrite de por
# medio. No se investigó la causa exacta (¿el CLI, la capa MSYS de Git Bash en
# Windows?) porque hay un camino que sí es verificable byte a byte: guardarlo
# en variables de entorno (texto, sin ambigüedad de modo binario/texto) y que
# el propio proceso lo escriba a disco al arrancar. Verificado con sha256
# antes de confiar en esto.
SESION_DIR = os.environ.get("HECTOR2_SESION_DIR") or os.path.dirname(os.path.abspath(__file__))
SESION = os.path.join(SESION_DIR, "reenvio.session")
# TelegramClient abre el archivo de sesión AL CONSTRUIRSE, no al conectar --
# si el directorio no existe todavía (un volumen recién montado, o un
# HECTOR2_SESION_DIR que apunta a algo que nunca se creó), revienta ahí
# mismo con "unable to open database file", antes de que el bootstrap de
# variables de entorno tenga chance de correr. Se garantiza el directorio
# apenas se sabe cuál es, no como parte del camino de reconstrucción.
os.makedirs(SESION_DIR, exist_ok=True)


def _sesion_parece_utilizable(ruta):
    """Chequeo BARATO, no autoritativo: ¿el archivo abre como sqlite y tiene
    una fila con algo en `auth_key`? Sirve para no reconstruir de arriba
    cuando claramente no hace falta, pero NO prueba que el auth_key sea
    válido -- un archivo truncado a mitad de una página puede seguir dando
    una fila con bytes en esa columna. La prueba real es
    `_asegurar_sesion_autorizada`, que le pregunta al servidor."""
    if not os.path.exists(ruta):
        return False
    try:
        con = sqlite3.connect(ruta, timeout=5)
        fila = con.execute("SELECT auth_key FROM sessions LIMIT 1").fetchone()
        con.close()
        return bool(fila and fila[0])
    except Exception:                                         # noqa: BLE001
        return False


def _bootstrap_sesion_desde_env(forzar=False):
    """Reconstruye reenvio.session desde HECTOR2_SESION_B64_1, _2, ...

    `forzar=False` (default): solo escribe si `_sesion_parece_utilizable`
    dice que no hay nada usable -- barato, para el arranque normal.
    `forzar=True`: reescribe sin mirar el archivo actual. Se usa desde
    `_asegurar_sesion_autorizada` DESPUÉS de que el propio servidor de
    Telegram ya dijo que la sesión actual no es válida -- ahí no hace falta
    ninguna heurística local, hay una respuesta real.

    Devuelve True si terminó con algo escrito en disco (nuevo o preexistente).
    """
    if not forzar and _sesion_parece_utilizable(SESION):
        return True
    partes = []
    i = 1
    while True:
        v = os.environ.get("HECTOR2_SESION_B64_%d" % i)
        if not v:
            break
        partes.append(v)
        i += 1
    if not partes:
        return False
    try:
        datos = base64.b64decode("".join(partes))
        os.makedirs(SESION_DIR, exist_ok=True)
        with open(SESION, "wb") as f:
            f.write(datos)
        print("[hector2] sesion reconstruida desde variables de entorno "
              "(%d bytes, %d parte(s))" % (len(datos), len(partes)))
        return True
    except Exception as e:                                    # noqa: BLE001
        print("[hector2] no se pudo reconstruir la sesion desde env: %s" % str(e)[:150])
        return False


async def _asegurar_sesion_autorizada(crear_cliente):
    """La única prueba real de que la sesión sirve: preguntarle al servidor.
    Si no está autorizada (auth_key inválido, revocado, o el archivo estaba
    corrupto -- el caso real del 23-ago: `railway volume files upload`
    corrompió el binario en silencio, y una heurística de "¿parece una fila
    de sqlite?" no lo detectó), se reconstruye desde las variables de
    entorno UNA vez y se reintenta. Nunca cae al prompt interactivo de
    `client.start()`: un contenedor sin terminal solo puede reventar ahí.

    Recibe una FÁBRICA de cliente, no un cliente ya armado: Telethon carga
    la sesión en memoria al construir el objeto, así que reescribir el
    archivo en disco no le sirve de nada a un cliente que ya existe -- hace
    falta uno nuevo para que la relectura sea real. Devuelve el cliente
    utilizable (conectado y autorizado) o None."""
    async def _intentar():
        # Un archivo que ni siquiera es un sqlite válido revienta DENTRO de
        # crear_cliente() (Telethon corre una consulta al construirse, no
        # al conectar) -- eso también cuenta como "sesión no utilizable",
        # no solo un is_user_authorized() en falso.
        client = crear_cliente()
        await client.connect()
        if await client.is_user_authorized():
            return client
        await client.disconnect()
        return None

    try:
        client = await _intentar()
        if client is not None:
            return client
        print("[hector2] sesion existente no autorizada contra el servidor "
              "-- reconstruyendo desde variables de entorno")
    except Exception as e:                                    # noqa: BLE001
        print("[hector2] sesion existente ilegible (%s) -- "
              "reconstruyendo desde variables de entorno" % str(e)[:150])

    if not _bootstrap_sesion_desde_env(forzar=True):
        return None
    try:
        return await _intentar()
    except Exception as e:                                    # noqa: BLE001
        print("[hector2] la sesion reconstruida desde env tampoco sirve: %s"
              % str(e)[:150])
        return None

# Lo que el mensaje original trae para "loguearte"/unirte a MÁS canales del
# aliado — no tiene sentido en el mensaje reenviado, y es justo el tipo de
# instrucción (bots de login, links de invitación) que no queremos empujar
# a los suscriptores de Rat.IA. Se recorta por línea, no se descarta el
# mensaje entero: el precio y el link del producto sí importan.
_LINEAS_A_SACAR = re.compile(
    r"(añadir carpeta|únete a los grupos|t\.me/addlist|t\.me/\w*bot|"
    r"/login|configuraci[oó]n seg[uú]n tu dispositivo|evitar rastreo|"
    r"abrir enlaces en|navegador en app)", re.I)

# "(60%)", "(98,9%)", "(95,38%)", "(39.34%)" -- CUALQUIER cantidad de
# decimales y separador coma O punto (el bot del aliado usa los dos según
# el canal). Antes exigía exactamente UN decimal y perdía en silencio
# los mensajes con dos (ver docstring de _parece_oferta). Se usa SOLO
# como filtro de sanidad, no para decidir el tópico -- eso lo decide el
# canal, ver CATEGORIAS más abajo.
_PORCENTAJE = re.compile(r"\(\s*\d{1,3}(?:[.,]\d+)?\s*%\s*\)")

# "$237.990" -- respaldo del filtro de sanidad para el día que un mensaje
# real no traiga ningún "(NN%)" en absoluto (ej. un precio plano sin
# comparación porcentual).
_PRECIO = re.compile(r"\$\s?\d")

# Orden de prioridad: la primera variable que contenga al canal gana. Errores
# va primero a propósito -- si algún día un canal quedara mal clasificado en
# dos listas a la vez, es preferible que gane el más urgente.
CATEGORIAS = (
    ("CANALES_ERRORES", "VIGIA_TOPICO_ERRORES"),
    ("CANALES_SUPERMERCADO", "VIGIA_TOPICO_SUPERMERCADO"),
    ("CANALES_TECNO", "VIGIA_TOPICO_ELECTRONICOS"),
    ("CANALES_VUELOS", "VIGIA_TOPICO_VUELOS"),
    ("CANALES_HOGAR", "VIGIA_TOPICO_HOGAR"),
    ("CANALES_OFERTAS", "VIGIA_TOPICO_OFERTAS"),
)


def _limpiar(texto):
    lineas = [l for l in (texto or "").split("\n") if not _LINEAS_A_SACAR.search(l)]
    return "\n".join(lineas).strip()


def _parece_oferta(texto):
    """Filtro de sanidad para canales SIN categoría asignada (ver _topico):
    ¿el mensaje trae algún "(NN%)" o un precio en pesos? No decide el
    tópico, solo si vale la pena reenviarlo cuando no hay otra señal.

    BUG REAL encontrado y corregido el 20-ago-2026: el regex de % solo
    aceptaba UN decimal ("98,9%"), y el bot del aliado a veces manda DOS
    ("95,38%" en el canal "80", "39.34%" con punto en COCHA) -- eso hacía
    que se descartaran en silencio hallazgos reales del canal MÁS
    importante. Verificado con mensajes reales vía Telethon antes de
    tocar el regex, no a ciegas.

    Los canales que SÍ tienen categoría (todo lo que hoy está en
    CANALES_ORIGEN) ya NO pasan por acá -- ver _al_llegar: el canal mismo
    es la garantía de que es un hallazgo real, no el formato exacto del
    texto. Esta función queda como red de seguridad para el día que se
    sume un canal sin clasificar todavía."""
    return bool(_PORCENTAJE.search(texto or "") or _PRECIO.search(texto or ""))


def _en_lista(chat_id, chat_username, variable_env):
    valores = {v.strip().lower().lstrip("@") for v in
              (os.environ.get(variable_env) or "").split(",") if v.strip()}
    if str(chat_id) in valores:
        return True
    if chat_username and chat_username.lower() in valores:
        return True
    return False


def _topico(chat_id, chat_username):
    """A qué tópico va este canal, según CATEGORIAS. None si no está
    clasificado en ninguna lista -- ese caso se descarta con aviso."""
    for canales_var, topico_var in CATEGORIAS:
        if _en_lista(chat_id, chat_username, canales_var):
            return os.environ.get(topico_var)
    return None


# ── EL AVISO SE REARMA, NO SE REENVÍA (Claude, 25-ago-2026) ───────────────
#
# Hasta hoy el texto del aliado se reenviaba tal cual, y eso arrastraba dos
# cosas que Joaquín pidió sacar:
#
#   · el rótulo de rank del aliado ("DRank"), que no es el nuestro y no
#     significa nada para un suscriptor de Rat.IA; y
#   · el "🔎 sin verificar del todo" que encabezaba el mensaje. No era un
#     capricho del código: SALÍA EN EL 100% de los mensajes, porque
#     `detectar_producto` no reconocía `simple.ripley.cl` como `ripley.cl`
#     (comparación exacta en vez de por sufijo) y nunca llegaba a cruzar
#     contra la base propia. Corregido en hector2_filtro.tienda_de.
#
# Además arrastraba el problema de fondo: los "precios históricos" del aliado
# a veces son de horas antes. Ahora el mensaje se construye con el mismo
# formato que usa Héctor para sus propios hallazgos (`alertas.armar_texto`),
# con NUESTRO sondeo y la fecha de cada precio.
CATEGORIAS_PROPIAS = ("CANALES_SUPERMERCADO", "CANALES_TECNO",
                       "CANALES_VUELOS", "CANALES_HOGAR")


def _topico_por_caida(caida):
    """A qué tópico va, según la caída REAL -- no según el canal de origen.

    El canal del aliado dice "80" o "50%" según SU vara. La nuestra es la de
    `baseprecios`, y es la que decide: si su "-80%" es un -62% medido contra
    el mínimo real de 30 días, va a Ofertas reales y no al tópico de errores.
    """
    if caida is None:
        return None
    if caida >= baseprecios.UMBRAL_ERROR_GRAVE:
        return (os.environ.get("VIGIA_TOPICO_ERRORES_GRAVES")
                or os.environ.get("VIGIA_TOPICO_ERRORES"))
    if caida >= baseprecios.UMBRAL_ERROR:
        return (os.environ.get("VIGIA_TOPICO_OFERTAS70")
                or os.environ.get("VIGIA_TOPICO_ERRORES"))
    return os.environ.get("VIGIA_TOPICO_OFERTAS")


def _armar_aviso(r, con_h2, ahora=None):
    """El mensaje con datos propios, o None si no alcanza para armarlo.

    Devuelve (texto, caida, precio, referencia, historico). `caida` es la que
    manda para el ruteo, así que sale de la mejor evidencia disponible en
    este orden: la medida contra la base de Héctor, y sólo si no hay, la
    declarada por el aliado.
    """
    precio = r.get("precio_real") or r.get("precio_declarado")
    if not precio:
        return None

    # ── UN LINK QUE NO ABRE ES PEOR QUE NO PUBLICAR ───────────────────
    # (Claude, 25-ago-2026) El redirector del aliado
    # (`link.ofertasshark.cl/link/v2/redirect?e=...`) devuelve `unauthorized`
    # también en un navegador real -- Joaquín: "al apretar PRODUCTO me lleva
    # a una pagina roja que dice unauthorized". Ya se sabía que daba 403 a un
    # script; se lo había dejado como último recurso pensando que a una
    # persona sí le serviría. No le sirve.
    #
    # `hector2_filtro.detectar_producto` ya intenta rescatar la URL real del
    # base64 del link de la imagen antes de llegar acá. Si aun así lo único
    # que hay es el redirector, no se publica: el aviso completo depende de
    # que el suscriptor pueda llegar al producto.
    if hector2_filtro._REDIRECTOR_ALIADO.search(
            hector2_filtro._dominio_de(r.get("url")) or ""):
        return None

    caida = r.get("caida_real")
    referencia = r.get("referencia")

    # El sondeo propio primero (base de Héctor); si esa ficha no está en su
    # catálogo, lo que Hector2 haya ido observando por su cuenta.
    historico = list(r.get("historico") or [])
    de_hector2 = False
    if not historico and r.get("url"):
        historico = hector2_db.historico_propio(
            con_h2, r["url"], dias=baseprecios.VENTANA_HISTORIAL_DIAS,
            ahora=ahora)
        de_hector2 = True

    if referencia is None and historico:
        # ── UNA OBSERVACIÓN SUELTA NO ES UNA REFERENCIA ───────────────────
        # (Claude, 25-ago-2026) Cuando la referencia se deriva del sondeo
        # PROPIO de Hector2 se le exige lo mismo que `baseprecios.evaluar` le
        # exige a Héctor: 5 lecturas y 7 días. Antes no se le exigía nada, y
        # bastaba UNA observación mayor para publicar un porcentaje.
        #
        # Por qué importa más de lo que parece: `precios_vistos` guarda el
        # `precio_declarado` del aliado, y el aliado publica el mismo hallazgo
        # en 2-3 canales a la vez (bitácora del 20-ago). Si uno de esos
        # mensajes traía un precio más alto, al minuto siguiente ese número se
        # convertía en "nuestra" referencia. O sea: el ancla inflada del
        # aliado volvía a entrar por la puerta de atrás, justo después de que
        # `f85c5ef` la sacara por la puerta de adelante.
        #
        # Reproducido con el reloj Curren del 25-ago (los tres publicaban un
        # -70,0% contra $46.990):
        #     1 observación, 2 días de historia   -> publicaba
        #     1 observación de hace 200 días      -> publicaba
        #     1 observación de hace 1 minuto      -> publicaba
        #
        # Decisión de Joaquín: la misma vara que Héctor, no una más blanda.
        # Cuesta alcance en las tiendas fuera del catálogo -- son las que
        # menos sondeo propio acumulan -- y a cambio un porcentaje publicado
        # por Rat.IA siempre tiene respaldo detrás.
        if de_hector2:
            obs, dias = hector2_db.respaldo_propio(
                con_h2, r["url"], dias=baseprecios.VENTANA_HISTORIAL_DIAS,
                ahora=ahora)
            if (obs < baseprecios.MIN_OBSERVACIONES
                    or dias < baseprecios.DIAS_MINIMOS_HISTORIAL):
                return None

        # Mismo criterio que baseprecios: el MÍNIMO observado, no el máximo
        # ni la media. Es el número que aguanta que lo revisen.
        previos = [p for p, _ in historico if p > precio]
        if previos:
            referencia = min(previos)
        else:
            # ── TENEMOS SONDEO PROPIO Y NO MUESTRA NINGUNA CAÍDA ──────
            # (Claude, 25-ago-2026) Eso NO es "falta información": es
            # EVIDENCIA EN CONTRA. Si lo que vimos es igual o mayor que el
            # precio de hoy, este precio es el normal del producto y no hay
            # oferta que avisar.
            #
            # Caso real que lo destapó: una toalla Cannon Home. El aliado
            # declaraba "$139.930 → $11.990 (91,4%)" y salió al tópico de
            # ERRORES DE PRECIO... con nuestro propio sondeo impreso más
            # abajo en el MISMO mensaje diciendo "$11.990". El aviso se
            # contradecía solo. Joaquín: "toallas que estaban en 120.000
            # (imposible) y hoy bajaron a 11000 (ese siempre es precio
            # normal)".
            #
            # Antes esto caía al `referencia_declarada` de abajo y publicaba
            # el ancla inflada del aliado — exactamente el fraude que
            # Hector2 existe para filtrar.
            return None

    if referencia is None:
        # ── SIN NINGÚN DATO PROPIO: NO SE PUBLICA UN PORCENTAJE ───────
        # Antes acá se usaba `referencia_declarada` (el "antes" del aliado)
        # como último recurso. Se quitó: ese número es justo el que puede
        # estar inflado, y publicarlo como si fuera nuestro convierte a
        # Rat.IA en el mismo canal del que se quería diferenciar.
        #
        # Sin referencia verificable no hay caída que anunciar, así que no
        # hay aviso. Se pierde alcance; se conserva que un "-91%" de Rat.IA
        # signifique algo.
        return None

    if not referencia or referencia <= precio:
        return None

    if caida is None:
        caida = 1 - (precio / float(referencia))

    det = {
        "url": r.get("url"),
        "nombre": r.get("nombre"),
        "precio": int(precio),
        "referencia": int(referencia),
        "caida": caida,
        "historico_fechas": historico,
        "historico": [p for p, _ in historico],
        "con_historial": bool(historico),
        "habitual": None,
    }
    tienda = r.get("tienda") or _comercio_de(r.get("url"))
    texto = alertas.armar_texto(det, tienda)

    # LA MINIATURA (Claude, 25-ago-2026)
    # Telegram arma la vista previa con el PRIMER link del mensaje. El aviso
    # del aliado empezaba con un ancla invisible a la foto del producto, y de
    # ahí salía la imagen; al rearmar el mensaje de cero esa ancla se perdió y
    # los avisos empezaron a llegar sin foto. Se vuelve a poner delante, con
    # un carácter de ancho cero como texto para que no se vea nada.
    #
    # `disable_web_page_preview` ya viene en False en `_enviar_a_ratia`, así
    # que con esto alcanza: no hay que mandar la foto como adjunto ni gastar
    # una petición extra.
    imagen = r.get("imagen")
    if imagen:
        texto = '<a href="%s">​</a>%s' % (imagen, texto)
    # (Claude, 25-ago-2026) Acá vivía una nota de "referencia declarada por
    # la fuente", para los avisos armados con el "antes" del aliado. Quedó
    # inalcanzable: sin sondeo propio ya no se publica nada (ver arriba), así
    # que todo aviso que llega hasta acá tiene historial propio detrás.
    return texto, caida, int(precio), int(referencia), historico


def _comercio_de(url):
    """El nombre del comercio a partir del dominio, para las tiendas que no
    están en el catálogo de Héctor. "simple.ripley.cl" -> "ripley"."""
    if not url:
        return "tienda"
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except ValueError:
        return "tienda"
    partes = [p for p in host.split(".") if p not in ("www", "com", "cl", "net")]
    return partes[-1] if partes else "tienda"


def _enviar_a_ratia(texto, topico, intentos=3):
    """Manda el mensaje. Reintenta en 429 (límite de envíos de Telegram) --
    el aliado a veces publica el MISMO hallazgo en 2-3 de sus canales a la
    vez (verificado: un "Logitech Teclado Gamer" salió simultáneo en los
    canales 75%/80/Tecno), así que pueden llegar varios reenvíos casi
    juntos al mismo grupo. Sin reintento, el 429 se perdía en silencio."""
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = (os.environ.get("VIGIA_CHAT_ID") or "").strip()
    if not token or not chat:
        print("[sin telegram configurado] %s" % texto[:200])
        return
    cuerpo = {"chat_id": chat, "text": texto, "parse_mode": "HTML",
              "disable_web_page_preview": False}
    if topico:
        cuerpo["message_thread_id"] = int(topico)
    req = urllib.request.Request(
        "https://api.telegram.org/bot%s/sendMessage" % token,
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    for intento in range(intentos):
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
            if r.get("ok"):
                return
            print("telegram rechazó: %s" % str(r)[:200])
            return
        except urllib.error.HTTPError as e:
            if e.code == 429 and intento < intentos - 1:
                cuerpo_error = json.loads(e.read().decode())
                espera = (cuerpo_error.get("parameters") or {}).get("retry_after", 2)
                print("429 de Telegram, esperando %ss (intento %d/%d)..."
                      % (espera, intento + 1, intentos))
                time.sleep(espera)
                continue
            print("telegram falló: HTTP %s %s"
                  % (e.code, e.read().decode(errors="replace")[:150]))
            return
        except Exception as e:                                   # noqa: BLE001
            print("telegram falló: %s" % str(e)[:150])
            return


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--login", action="store_true",
                   help="solo hace el login interactivo y sale")
    a = p.parse_args()

    api_id = os.environ.get("TG_API_ID")
    api_hash = os.environ.get("TG_API_HASH")
    if not api_id or not api_hash:
        print("Faltan TG_API_ID / TG_API_HASH (sacarlos de my.telegram.org/apps)")
        return 1

    # Un canal PRIVADO (al que se entró por link de invitación, como el
    # "addlist" del aliado) no tiene @usuario público -- solo un ID numérico,
    # que `listar_canales.py` imprime. Se acepta cualquiera de los dos acá:
    # los valores que son puro dígitos (con o sin signo -) se pasan como int,
    # el resto se deja como string de @usuario.
    def _entidad(c):
        c = c.strip().lstrip("@")
        try:
            return int(c)
        except ValueError:
            return c

    canales = [_entidad(c) for c in (os.environ.get("CANALES_ORIGEN") or "").split(",") if c.strip()]
    if not canales and not a.login:
        print("Falta CANALES_ORIGEN (usernames o IDs separados por coma)")
        return 1

    if a.login:
        # Interactivo a propósito -- SOLO se corre a mano, una vez, desde una
        # terminal real. En producción (Railway) nunca se llega acá: un
        # contenedor sin terminal solo puede reventar en el prompt.
        client = TelegramClient(SESION, int(api_id), api_hash)
        client.start()
        print("Login OK. La sesión quedó guardada en %s" % SESION)
        return 0

    def _crear_cliente():
        return TelegramClient(SESION, int(api_id), api_hash)

    _bootstrap_sesion_desde_env()   # chequeo barato antes de tocar red
    client = asyncio.get_event_loop().run_until_complete(
        _asegurar_sesion_autorizada(_crear_cliente))
    if client is None:
        print("::error:: Hector2 no tiene una sesión de Telegram autorizada, "
              "ni en disco ni reconstruible desde HECTOR2_SESION_B64_* -- "
              "hay que correr 'python reenviar_ofertas.py --login' a mano y "
              "actualizar esas variables con el archivo nuevo.")
        return 1

    # Hector2: base propia (mensajes, confianza por canal, ritmo por tópico) y
    # copia de solo lectura de la base de Héctor para cruzar precios. Si la
    # descarga inicial falla (sin red, GitHub caído), el proceso sigue: todo
    # cae a "sin_verificar" -- degradado, no roto.
    _ESTADO["con_h2"] = hector2_db.abrir()
    ruta_hector, _ = descargar_base_hector.asegurar()
    if ruta_hector:
        _reabrir_con_hector(ruta_hector)
    else:
        print("[hector2] arranca sin base de Héctor -- todo pasa por "
              "verificación en vivo o queda sin_verificar")
    topico_dudosos = (os.environ.get("VIGIA_TOPICO_DUDOSOS") or "").strip() or None

    @client.on(events.NewMessage(chats=canales))
    async def _al_llegar(event):
        # `raw_text` es texto plano puro: pierde cualquier link "escondido"
        # bajo una palabra (ej. "PRODUCTO" clickeable hacia la ficha real,
        # que en el mensaje original es un text_link, no una URL visible).
        # `tl_html.unparse` reconstruye el mismo mensaje en HTML a partir del
        # texto + las entidades reales (`event.message.entities`), preservando
        # esos links -- se manda con parse_mode HTML, así llegan clickeables
        # también en Rat.IA. Verificado el 20-ago-2026 (bug reportado: los
        # links de producto no eran clickeables en el reenvío).
        texto = _limpiar(tl_html.unparse(event.message.message or "", event.message.entities))
        if not texto:
            return
        chat = await event.get_chat()
        username = getattr(chat, "username", None)
        topico = _topico(event.chat_id, username)
        canal_id = str(event.chat_id)

        # El canal manda: si ya tiene categoría asignada (CANALES_ERRORES,
        # CANALES_OFERTAS, etc.), es de confianza y se reenvía SIEMPRE, sin
        # exigirle un formato exacto al texto. El filtro de "% o precio"
        # queda solo para el canal que todavía no está clasificado en
        # ninguna lista -- ahí sí conviene ser cauto antes de reenviar algo
        # a ciegas. Antes se exigía el % SIEMPRE, y un formato de dos
        # decimales ("95,38%", "39.34%") hacía que se perdieran en
        # silencio hallazgos reales del canal "80" -- el más importante.
        if topico is None:
            if not _parece_oferta(texto):
                print("descartado (canal sin categoría y sin %% ni precio "
                      "legible): %s..." % texto[:60].replace("\n", " "))
                return
            print("⚠️  canal SIN categoría asignada (chat_id=%s, @%s) -- "
                  "revisar CANALES_* en las variables de entorno: %s..."
                  % (event.chat_id, username, texto[:50].replace("\n", " ")))
            return

        # ── HECTOR2: el canal ya no es garantía suficiente ──────────────
        # Todo lo que toca con_hector/con_h2 va bajo el mismo lock -- ver el
        # comentario de _DB_LOCK sobre por qué esto no es opcional.
        async with _DB_LOCK:
            con_h2 = _ESTADO["con_h2"]
            r = await asyncio.to_thread(
                hector2_filtro.evaluar_mensaje, texto, canal_id,
                _ESTADO["con_hector"], True,
                lambda c: hector2_db.confianza_canal(con_h2, c))

            # Toda observación de precio se guarda ANTES de decidir si el
            # aviso se manda -- incluso la de un mensaje que se va a
            # descartar. Un precio que vimos es un dato real de la histórica
            # aunque el anuncio que lo traía no sirviera, y es justo lo que
            # con el tiempo permite contradecir al aliado con números
            # propios en vez de sólo desconfiar de los suyos.
            if r.get("url") and r.get("precio_declarado"):
                hector2_db.registrar_precio_visto(
                    con_h2, r["url"], r["precio_declarado"],
                    "verificado_en_vivo" if r.get("precio_real") else "declarado_aliado",
                    tienda=r.get("tienda"))

            if r["veredicto"] == "descartado":
                hector2_db.registrar_mensaje(
                    con_h2, canal=canal_id, tienda=r["tienda"], url=r["url"],
                    caida_declarada=r["caida_declarada"], caida_real=r["caida_real"],
                    fuente=r["fuente"], veredicto="descartado", motivo=r["motivo"],
                    topico_original=str(topico), topico_final="", texto_muestra=texto)
                hector2_db.registrar_anuncio(
                    con_h2, origen="aliado", canal=canal_id, tienda=r["tienda"],
                    url=r["url"], nombre=r.get("nombre"),
                    precio=r.get("precio_declarado"),
                    caida_declarada=r["caida_declarada"], veredicto="descartado",
                    topico=None, enviado=False, texto=texto)
                print("🚫 descartado (%s): %s..." % (r["motivo"][:60],
                      texto[:50].replace("\n", " ")))
                return

            armado = _armar_aviso(r, con_h2)
            if armado is None:
                # Sin precio ni referencia no hay forma honesta de armar el
                # aviso con datos propios, y reenviar el del aliado sería
                # volver a arrastrar su rank y su "antes" inflado. Queda
                # registrado para poder revisar cuántos caen acá.
                hector2_db.registrar_anuncio(
                    con_h2, origen="aliado", canal=canal_id, tienda=r["tienda"],
                    url=r["url"], nombre=r.get("nombre"),
                    caida_declarada=r["caida_declarada"],
                    veredicto=r["veredicto"], topico=None, enviado=False,
                    texto=texto)
                print("⏭️  sin datos para armar el aviso: %s..."
                      % texto[:50].replace("\n", " "))
                return

            a_enviar, caida, precio, referencia, historico = armado

            # El tópico sale de la caída REAL, salvo en los canales que ya
            # son de una categoría (Supermercado, Tecno, Vuelos, Hogar): ahí
            # el canal sí sabe algo que el porcentaje no dice.
            es_categoria = any(_en_lista(event.chat_id, username, v)
                               for v in CATEGORIAS_PROPIAS)
            topico_final = topico if es_categoria else (
                _topico_por_caida(caida) or topico)

            umbral = hector2_db.umbral_actual(con_h2, str(topico_final))
            if r["puntaje"] < umbral and topico_dudosos:
                topico_final = topico_dudosos

            _enviar_a_ratia(a_enviar, topico_final)
            hector2_db.registrar_mensaje(
                con_h2, canal=canal_id, tienda=r["tienda"], url=r["url"],
                caida_declarada=r["caida_declarada"], caida_real=r["caida_real"],
                fuente=r["fuente"], veredicto=r["veredicto"], motivo=r["motivo"],
                topico_original=str(topico), topico_final=str(topico_final),
                texto_muestra=texto)
            hector2_db.registrar_anuncio(
                con_h2, origen="aliado", canal=canal_id, tienda=r["tienda"],
                url=r["url"], nombre=r.get("nombre"), precio=precio,
                referencia=referencia, caida=caida,
                caida_declarada=r["caida_declarada"], historico=historico,
                veredicto=r["veredicto"], topico=topico_final, enviado=True,
                texto=a_enviar)
            print("reenviado (topico %s, %.0f%%, %s): %s..." % (
                topico_final, (caida or 0) * 100, r["veredicto"],
                (r.get("nombre") or texto)[:50].replace("\n", " ")))

    print("Escuchando %d canal(es): %s" % (len(canales), ", ".join(str(c) for c in canales)))
    # NO se llama a client.start() acá -- ya está conectado y autorizado
    # desde _asegurar_sesion_autorizada(). Un segundo start() no rompería
    # nada (Telethon lo tolera), pero es el mismo camino que puede caer en
    # el prompt interactivo si algo cambió el estado entre medio; mejor que
    # ese camino no exista en el flujo normal.
    client.loop.create_task(_tarea_refresco_base())
    client.loop.create_task(_tarea_ajustar_ritmos())
    client.loop.create_task(_tarea_selector_instagram())
    client.run_until_disconnected()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
