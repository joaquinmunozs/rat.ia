# -*- coding: utf-8 -*-
"""Base propia de Hector2: cada mensaje que pasó por el filtro, la confianza
por canal, y el estado del ritmo adaptativo por tópico.

POR QUÉ UNA BASE APARTE DE `precios.db`
------------------------------------------------------------------------------
Viven en procesos distintos con ciclos de vida distintos: `precios.db` es de
Héctor, corre en GitHub Actions, vive como artifact de 2 días + un respaldo
diario. `hector2.db` es de este bot, corre 24/7 en Railway con disco propio.
Mezclarlas ataría el ciclo de vida de una al de la otra sin necesidad — Hector2
solo NECESITA leer `precios.db` (de solo lectura, ver `descargar_base_hector.py`),
nunca escribirle.

ESTE ES EL DATO QUE HACE QUE EL PROYECTO EVOLUCIONE, NO SOLO FILTRE
------------------------------------------------------------------------------
Un filtro que solo decide sí/no y no registra nada no aprende. Cada mensaje que
pasa por acá queda anotado con su veredicto y las señales que lo llevaron ahí.
Con eso se puede, más adelante: auditar si el filtro quedó muy duro o muy
blando, calcular qué canales del aliado valen la pena de verdad
(`confianza_canal`), y ajustar el ritmo sin adivinar.
"""
import json
import os
import sqlite3
import time

def _ruta_por_defecto():
    """(Claude, 25-ago-2026) EL DISCO PERSISTENTE GANA, SIEMPRE.

    BUG REAL: `HECTOR2_DB` no está seteada en Railway, así que esta base
    caía junto al código dentro del contenedor -- que es efímero. Cada
    deploy borraba TODO el historial de mensajes y toda la confianza por
    canal acumulada, y el ritmo adaptativo volvía a arrancar de cero sin
    que nadie se enterara (no falla, simplemente olvida).

    Justo el dato que Joaquín pidió acumular para tener una histórica real
    era el que se estaba perdiendo. Ahora, si Railway montó un volumen
    (`RAILWAY_VOLUME_MOUNT_PATH`, hoy `/data`), la base vive ahí por
    defecto. `HECTOR2_DB` sigue mandando si alguien la setea a mano.
    """
    explicita = os.environ.get("HECTOR2_DB")
    if explicita:
        return explicita
    volumen = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
    if volumen and os.path.isdir(volumen):
        return os.path.join(volumen, "hector2.db")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "hector2.db")


RUTA = _ruta_por_defecto()

ESQUEMA = """
CREATE TABLE IF NOT EXISTS mensajes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    canal           TEXT NOT NULL,
    tienda          TEXT,
    url             TEXT,
    caida_declarada REAL,
    caida_real      REAL,
    fuente          TEXT,      -- base_propia / verificado_en_vivo / sin_dato
    veredicto       TEXT NOT NULL,   -- confirmado / sin_verificar / descartado
    motivo          TEXT,
    topico_original TEXT,
    topico_final    TEXT,
    texto_muestra   TEXT,      -- primeros ~200 chars, para poder auditar
    creado_en       INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS mensajes_canal_idx ON mensajes (canal, creado_en);
CREATE INDEX IF NOT EXISTS mensajes_topico_idx ON mensajes (topico_final, creado_en);

CREATE TABLE IF NOT EXISTS canales_confianza (
    canal        TEXT PRIMARY KEY,
    confirmados  INTEGER NOT NULL DEFAULT 0,
    sin_verificar INTEGER NOT NULL DEFAULT 0,
    descartados  INTEGER NOT NULL DEFAULT 0,
    actualizado_en INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ritmo_topico (
    topico          TEXT PRIMARY KEY,
    umbral          REAL NOT NULL,   -- 0..1, dial de exigencia (ver hector2_filtro.puntaje)
    actualizado_en  INTEGER NOT NULL
);

-- ── EL ARCHIVO DE ANUNCIOS (Claude, 25-ago-2026) ────────────────────────
--
-- `mensajes` de arriba guarda la DECISIÓN (pasó/no pasó, y por qué) con una
-- muestra de 200 caracteres. Sirve para auditar el filtro, no para saber a
-- qué precio se anunció algo hace tres semanas.
--
-- Esto guarda el ANUNCIO: todo lo que se publicó, venga de Héctor o del
-- aliado, con el texto completo y los números que lo sostenían. Pedido
-- explícito de Joaquín: poder mirar hacia atrás y decidir si un aviso
-- estuvo bien o mal, en vez de discutirlo de memoria.
CREATE TABLE IF NOT EXISTS anuncios (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    origen          TEXT NOT NULL,   -- 'hector' (propio) / 'aliado' (reenvío)
    canal           TEXT,            -- canal de origen, si vino del aliado
    tienda          TEXT,
    url             TEXT,
    nombre          TEXT,
    precio          INTEGER,         -- el precio anunciado
    referencia      INTEGER,         -- contra qué se midió la caída
    caida           REAL,            -- 0..1, la que se publicó
    caida_declarada REAL,            -- la que decía el aliado, si difiere
    historico       TEXT,            -- JSON [[precio, epoch], ...] del sondeo propio
    veredicto       TEXT,
    topico          TEXT,
    enviado         INTEGER NOT NULL DEFAULT 0,
    texto           TEXT,            -- el mensaje COMPLETO tal como se mandó
    creado_en       INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS anuncios_url_idx ON anuncios (url, creado_en);
CREATE INDEX IF NOT EXISTS anuncios_fecha_idx ON anuncios (creado_en);

-- ── LA HISTÓRICA REAL ───────────────────────────────────────────────────
--
-- Una fila por precio OBSERVADO, no por anuncio. Es lo que con el tiempo
-- convierte a Hector2 en algo que puede contradecir al aliado con datos
-- propios en vez de sólo desconfiar: cada mensaje que llega deja registrado
-- "esta URL costaba esto en esta fecha", incluso para tiendas que no están
-- en el catálogo de Héctor y que por eso nunca van a tener historial ahí.
--
-- UNIQUE(url, precio, visto_en) para que reprocesar la misma tanda no
-- duplique observaciones -- el mismo hallazgo llega hasta 3 veces cuando el
-- aliado lo publica en varios canales a la vez.
CREATE TABLE IF NOT EXISTS precios_vistos (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    url        TEXT NOT NULL,
    tienda     TEXT,
    precio     INTEGER NOT NULL,
    fuente     TEXT NOT NULL,   -- declarado_aliado / verificado_en_vivo / base_propia
    visto_en   INTEGER NOT NULL,
    UNIQUE (url, precio, visto_en)
);
CREATE INDEX IF NOT EXISTS precios_vistos_url_idx ON precios_vistos (url, visto_en);
"""


def abrir(ruta=None):
    # check_same_thread=False: en reenviar_ofertas.py esta conexion se usa
    # tanto desde el hilo del event loop (registrar_mensaje, umbral_actual)
    # como desde el hilo de asyncio.to_thread que corre evaluar_mensaje
    # (confianza_canal). El llamador serializa el acceso con un lock; esto
    # solo baja la barrera de sqlite3 para permitirlo.
    con = sqlite3.connect(ruta or RUTA, timeout=30, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    con.execute("PRAGMA journal_mode=WAL")
    return con


def registrar_mensaje(con, *, canal, tienda, url, caida_declarada, caida_real,
                       fuente, veredicto, motivo, topico_original, topico_final,
                       texto_muestra, ahora=None):
    ahora = int(ahora if ahora is not None else time.time())
    con.execute(
        "INSERT INTO mensajes (canal, tienda, url, caida_declarada, caida_real, "
        "fuente, veredicto, motivo, topico_original, topico_final, texto_muestra, "
        "creado_en) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (canal, tienda, url, caida_declarada, caida_real, fuente, veredicto,
         motivo, topico_original, topico_final, (texto_muestra or "")[:200], ahora))
    _actualizar_confianza(con, canal, veredicto, ahora)
    con.commit()


def registrar_anuncio(con, *, origen, canal=None, tienda=None, url=None,
                       nombre=None, precio=None, referencia=None, caida=None,
                       caida_declarada=None, historico=None, veredicto=None,
                       topico=None, enviado=True, texto=None, ahora=None):
    """(Claude, 25-ago-2026) Deja constancia de un anuncio, propio o del aliado.

    `historico` es la lista [(precio, epoch), ...] del sondeo propio; se
    guarda como JSON para poder reconstruir el aviso tal cual salió, aunque
    la base de Héctor ya haya rotado esos tramos fuera de su ventana de 30
    días.
    """
    ahora = int(ahora if ahora is not None else time.time())
    con.execute(
        "INSERT INTO anuncios (origen, canal, tienda, url, nombre, precio, "
        "referencia, caida, caida_declarada, historico, veredicto, topico, "
        "enviado, texto, creado_en) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (origen, canal, tienda, url, nombre,
         int(precio) if precio else None,
         int(referencia) if referencia else None,
         caida, caida_declarada,
         json.dumps(historico or [], separators=(",", ":")),
         veredicto, str(topico) if topico is not None else None,
         1 if enviado else 0, texto, ahora))
    con.commit()


def registrar_precio_visto(con, url, precio, fuente, tienda=None, visto_en=None):
    """Una observación de precio para la histórica propia.

    Silenciosa ante duplicados: el mismo hallazgo llega varias veces cuando
    el aliado lo publica en dos o tres canales a la vez, y eso no es un error
    que valga la pena reportar -- es el funcionamiento normal.
    """
    if not url or not precio:
        return False
    visto_en = int(visto_en if visto_en is not None else time.time())
    try:
        con.execute(
            "INSERT OR IGNORE INTO precios_vistos (url, tienda, precio, fuente, "
            "visto_en) VALUES (?,?,?,?,?)",
            (url, tienda, int(precio), fuente, visto_en))
        con.commit()
        return True
    except sqlite3.Error:
        return False


def historico_propio(con, url, limite=4):
    """Lo que NOSOTROS vimos costar esta ficha, de más reciente a más antiguo.

    Es el respaldo para las tiendas que no están en el catálogo de Héctor:
    ahí `baseprecios` no tiene nada que decir, pero estas observaciones se
    acumulan igual desde el primer mensaje que llega.
    """
    filas = con.execute(
        "SELECT precio, MAX(visto_en) AS visto_en FROM precios_vistos "
        "WHERE url=? GROUP BY precio ORDER BY visto_en DESC LIMIT ?",
        (url, limite)).fetchall()
    return [(f["precio"], f["visto_en"]) for f in filas]


def _actualizar_confianza(con, canal, veredicto, ahora):
    columna = {"confirmado": "confirmados", "sin_verificar": "sin_verificar",
               "descartado": "descartados"}.get(veredicto)
    if not columna:
        return
    con.execute(
        "INSERT INTO canales_confianza (canal, %s, actualizado_en) VALUES (?, 1, ?) "
        "ON CONFLICT(canal) DO UPDATE SET %s = %s + 1, actualizado_en = excluded.actualizado_en"
        % (columna, columna, columna),
        (canal, ahora))


def confianza_canal(con, canal):
    """Fracción de mensajes NO descartados, de los que ya se pudieron evaluar
    contra algo (confirmados + descartados; `sin_verificar` no cuenta para
    ninguno de los dos lados porque no hubo con qué comprobarlo).

    Devuelve None si el canal no tiene evidencia todavía -- un canal nuevo no
    debería heredar ni la confianza ni la sospecha de otro.
    """
    f = con.execute(
        "SELECT confirmados, descartados FROM canales_confianza WHERE canal=?",
        (canal,)).fetchone()
    if not f:
        return None
    total = f["confirmados"] + f["descartados"]
    if total < 5:
        # Muy poca evidencia para confiar en el número -- mismo criterio que
        # baseprecios usa para no creerle a una mediana con pocas lecturas.
        return None
    return f["confirmados"] / total


# ── RITMO ADAPTATIVO: ni mudo, ni saturado ─────────────────────────────────
#
# Mismo patrón que `_ControlRitmo` en vigilante.py (AIMD: sube despacio, baja
# rápido), aplicado a un dial de exigencia por tópico en vez de a peticiones
# por segundo. La lección que ya costó cara ahí (falabella atrapada en su
# piso por una asimetría entre subir y bajar) se evita a propósito: los pasos
# son simétricos acá.
#
# `umbral` es el puntaje mínimo (0..1, ver hector2_filtro.puntaje) que un
# mensaje necesita para pasar. 1.0 = solo lo perfecto pasa (mudo). 0.0 = pasa
# cualquier cosa (saturado). Arranca en un punto medio y se ajusta solo mirando
# cuánto se mandó en las últimas 24h contra el objetivo del tópico.
UMBRAL_INICIAL = 0.55
UMBRAL_MIN = 0.15   # ni con el tópico muerto se manda basura sin ningún filtro
UMBRAL_MAX = 0.90   # ni con el tópico saturado se exige perfección imposible
PASO = 0.05


def umbral_actual(con, topico):
    f = con.execute("SELECT umbral FROM ritmo_topico WHERE topico=?",
                     (topico,)).fetchone()
    return f["umbral"] if f else UMBRAL_INICIAL


def ajustar_umbral(con, topico, enviados_24h, piso_objetivo, techo_objetivo, ahora=None):
    """Un escalón por llamada, hacia el rango objetivo. Se llama una vez por
    tanda de decisión (no en cada mensaje), para no perseguir ruido de corto
    plazo -- igual que `_ControlRitmo` espera una ventana antes de mover el
    ritmo, acá se espera a mirar el conteo del día completo.
    """
    ahora = int(ahora if ahora is not None else time.time())
    actual = umbral_actual(con, topico)
    if enviados_24h < piso_objetivo:
        nuevo = max(UMBRAL_MIN, actual - PASO)   # menos exigente: que pase más
    elif enviados_24h > techo_objetivo:
        nuevo = min(UMBRAL_MAX, actual + PASO)   # más exigente: que pase menos
    else:
        nuevo = actual
    con.execute(
        "INSERT INTO ritmo_topico (topico, umbral, actualizado_en) VALUES (?,?,?) "
        "ON CONFLICT(topico) DO UPDATE SET umbral=excluded.umbral, "
        "actualizado_en=excluded.actualizado_en",
        (topico, nuevo, ahora))
    con.commit()
    return nuevo


def contar_enviados_24h(con, topico, ahora=None):
    ahora = int(ahora if ahora is not None else time.time())
    f = con.execute(
        "SELECT COUNT(*) AS n FROM mensajes WHERE topico_final=? AND "
        "veredicto != 'descartado' AND creado_en >= ?",
        (topico, ahora - 86400)).fetchone()
    return f["n"] if f else 0
