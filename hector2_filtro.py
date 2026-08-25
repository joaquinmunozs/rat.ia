# -*- coding: utf-8 -*-
"""Hector2: valida lo que reenvía `reenviar_ofertas.py` antes de mandarlo.

POR QUÉ EXISTE
------------------------------------------------------------------------------
El aliado reenvía SU clasificación de "esto es un error/oferta de precio",
calculada contra SU "antes" -- que puede ser un precio de lista, un MSRP, o
cualquier cosa que no sea lo que ese producto costó de verdad. El caso real
que lo destapó: un jugo en caja que "bajó de $2.000 a $400" cuando siempre
costó $400. Es el mismo fraude de anclaje documentado por Consumer Reports
(2024): más de 30% de los "sale price" de grandes retailers en EE.UU. eran
iguales o más altos que el precio regular del mes anterior [1]. La FTC lo
trata como engañoso salvo que el ancla sea un precio real y documentado [2].

LA IDEA CENTRAL: NO INVENTAR UNA SEGUNDA VARA, REUSAR LA DE HÉCTOR
------------------------------------------------------------------------------
Héctor ya resolvió esto para su propio catálogo (`baseprecios.evaluar`: 70%+
error, 40%+ oferta, referencia = mínimo real de 30 días, no un "antes"
inventado). Si el producto del aliado ya está en la base de Héctor, este
módulo NO recalcula nada propio -- llama a `baseprecios.evaluar` con el precio
que el aliado declara y le cree lo que HÉCTOR diga, no lo que el aliado diga.

TRES NIVELES DE VEREDICTO, NUNCA SILENCIO SIN EXPLICACIÓN
------------------------------------------------------------------------------
    confirmado     el producto está en la base de Héctor y la caída se
                    sostiene contra su historial real, o se verificó en vivo
                    que el precio actual coincide con lo declarado.
    sin_verificar   no hay con qué cruzar (tienda fuera del catálogo de
                    Héctor, o la verificación en vivo no se pudo hacer) pero
                    tampoco hay evidencia de que esté mal. Pasa con más
                    exigencia que un confirmado (ver hector2_db.puntaje).
    descartado      evidencia directa de que está mal: no calificó contra la
                    base real, la verificación en vivo no coincidió, o es
                    ruido de categoría (libros, accesorios, etc.).

Referencias:
[1] Consumer Reports (2024), citado en cheaperly.ai/blog/how-to-spot-fake-discounts
[2] FTC guidance sobre reference pricing, citado en numberanalytics.com/blog/price-anchoring-deceptive-trade-practices
"""
import os
import re
import sqlite3
from urllib.parse import urlparse

import adaptadores
import baseprecios
import categorias
import descubrir
import extractor
import tiendas

_DOMINIOS_HECTOR = {t["dominio"]: t["rubro"] for t in tiendas.TIENDAS}

# Productos que NO son "algo que bajó de precio de verdad": libros/revistas,
# entradas, tarjetas de regalo, suscripciones, cursos, seguros. Ninguno de
# estos tiene un precio de mercado estable y comparable como sí lo tiene un
# electrodoméstico -- un "-60%" en un libro casi siempre es un precio de
# catálogo que nunca se cobró, y una tarjeta de regalo "con descuento" es
# directamente sospechosa.
RUIDO_IRRELEVANTE = re.compile(
    r"\b("
    r"libro[s]?\b|e-?book|revista[s]?\b|comic[s]?\b|manga\b|"
    r"entrada[s]?\b|ticket[s]?\b|evento\b|concierto\b|"
    r"tarjeta\s*de\s*regalo|gift\s*card|giftcard|"
    r"suscripci[oó]n|membres[íi]a|plan\s*(?:mensual|anual)\b|"
    r"curso[s]?\b|capacitaci[oó]n\b|"
    r"seguro[s]?\b(?!\s*de\s*vidrio)"     # "seguro" sí, pero "vidrio de seguridad" no
    r")\b", re.I)

_PORCENTAJE = re.compile(r"\(?\s*-?\s*(\d{1,3}(?:[.,]\d+)?)\s*%\s*\)?")
_PRECIO = re.compile(r"\$\s?([\d.,]{3,})")
_HREF = re.compile(r'href="([^"]+)"', re.I)


def extraer_urls(texto):
    return _HREF.findall(texto or "")


def _dominio_de(url):
    try:
        d = urlparse(url).netloc.lower()
    except ValueError:
        return ""
    return d[4:] if d.startswith("www.") else d


# Hosts de imágenes/CDN, no del producto -- verificado contra ejemplos reales
# en los logs de Railway ("img2.ofertasshark.cl", "rimage.ripley.cl").
#
# (Claude, 25-ago-2026) Pasó de una lista de prefijos literales a un patrón
# porque `rimage.ripley.cl` (el CDN de imágenes de Ripley) no empezaba con
# ninguno de los prefijos viejos y se colaba como si fuera el link del
# producto: se intentaba "verificar en vivo" una imagen JPG, no había precio
# legible, y el mensaje terminaba marcado `sin_verificar`. Ese era el caso
# más común en producción.
_HOST_IMAGEN = re.compile(
    r"^(?:img|imagen|image|images|rimage|cdn|static|media|assets|thumb|thumbs|s|i)"
    r"\d*\.", re.I)
_EXT_IMAGEN = re.compile(r"\.(?:jpe?g|png|webp|gif|avif|bmp|svg|ico)(?:[?#]|$)", re.I)

# (Claude, 25-ago-2026) Hosts de imagen que NO empiezan con un prefijo típico.
# El caso real: `cl-cenco-pim-resizer.ecomm.cencosud.com` (el redimensionador
# de Cencosud para Paris y Jumbo) no empieza con "img" ni termina en ".jpg",
# así que pasaba el filtro y podía terminar elegido como link del producto.
_HOST_IMAGEN_CONTIENE = re.compile(r"(?:resizer|pim-|-img|imgproxy|photos?)\.", re.I)

# Links que el aliado agrega como AYUDA, no como el producto: un "buscar en
# Google" y links a Telegram/WhatsApp. Si el mensaje no trae link de tienda,
# `detectar_producto` se quedaba con el primero que no fuera imagen — y ese
# era el buscador. Ese es literalmente el "al apretar PRODUCTO me lleva a
# otro lado" que reportó Joaquín: caía en una búsqueda de Google.
_NO_ES_PRODUCTO = re.compile(
    r"^(?:www\.)?(?:google\.[a-z.]+|bing\.com|duckduckgo\.com|t\.me|wa\.me|"
    r"api\.whatsapp\.com|facebook\.com|instagram\.com|youtube\.com)$", re.I)

# El redirector de afiliado del aliado. Funciona en un navegador (lleva al
# producto y le acredita la comisión), pero devuelve 403 a cualquier cliente
# que no sea un navegador real -- verificado el 25-ago con las cabeceras de
# Chrome de `descubrir.CABECERAS`, con y sin Referer. O sea: NO se puede
# resolver desde acá para saber a qué tienda apunta.
#
# Se usa igual como último recurso —es el link que el propio aliado publica y
# a un humano sí le sirve— pero NUNCA se prefiere sobre un link directo a
# tienda, y no se le puede cruzar contra la base de Héctor porque no hay forma
# de saber el dominio real.
_REDIRECTOR_ALIADO = re.compile(r"(?:^|\.)(?:link\.)?ofertasshark\.cl$", re.I)

# (Claude, 25-ago-2026) TIENDAS QUE NO SE REENVÍAN NUNCA.
#
# Amazon: TODAS las ofertas de Amazon que reenvía el aliado resultaron ser
# productos que no despachan a Chile -- Joaquín las revisó una por una y no
# sirvió ninguna. Un aviso que el suscriptor no puede comprar es peor que no
# avisar: gasta su atención y le enseña que el canal manda cosas inútiles.
#
# Se descarta el dominio entero en vez de verificar el envío producto por
# producto porque Amazon calcula la disponibilidad de despacho contra la
# dirección de la sesión, no contra la ficha pública: sin sesión chilena no
# hay forma honesta de saberlo desde acá, y adivinar sería volver al mismo
# problema. Si algún día conviene revisarlo, la variable de entorno
# HECTOR2_PERMITIR_AMAZON=1 lo reactiva sin tocar código.
_BLOQUEADAS = re.compile(r"(?:^|\.)amazon\.[a-z.]+$", re.I)


def esta_bloqueada(dominio):
    if os.environ.get("HECTOR2_PERMITIR_AMAZON") == "1":
        return False
    return bool(_BLOQUEADAS.search(dominio or ""))


def _es_imagen(url, dominio):
    return bool(_HOST_IMAGEN.match(dominio or "")
                or _HOST_IMAGEN_CONTIENE.search(dominio or "")
                or _EXT_IMAGEN.search(url or ""))


def tienda_de(dominio):
    """El dominio del catálogo de Héctor que le corresponde, o None.

    (Claude, 25-ago-2026) LA COMPARACIÓN ES POR SUFIJO, NO EXACTA -- y esto
    es lo que arreglaba el bug grande. `_DOMINIOS_HECTOR` guarda "ripley.cl",
    pero la ficha real vive en `simple.ripley.cl`; con la comparación exacta
    de antes NUNCA calzaba, así que no se cruzaba contra la base propia, se
    caía a "verificación en vivo" y terminaba en `sin_verificar`. Por eso el
    100% de los mensajes salía rotulado "sin verificar del todo".

    Se compara contra el dominio Y sus sufijos punto a punto, así
    `simple.ripley.cl` -> `ripley.cl` calza y `noripley.cl` no (porque el
    corte es siempre en un punto, no en cualquier posición del texto).
    """
    if not dominio:
        return None
    if dominio in _DOMINIOS_HECTOR:
        return dominio
    partes = dominio.split(".")
    for i in range(1, len(partes) - 1):
        cola = ".".join(partes[i:])
        if cola in _DOMINIOS_HECTOR:
            return cola
    return None


def imagen_de(urls):
    """La foto del producto que trae el mensaje, o None.

    (Claude, 25-ago-2026) Vuelve a existir porque al rearmar el aviso se
    perdió la vista previa en Telegram. El mensaje del aliado empieza con un
    `<a>` invisible a la imagen, y de ahí Telegram sacaba la miniatura; al
    construir el mensaje de cero sin ese link, los avisos empezaron a llegar
    sin foto. Reportado por Joaquín.
    """
    for u in urls:
        dom = _dominio_de(u)
        if dom and _es_imagen(u, dom):
            return u
    return None


def detectar_producto(urls):
    """De todos los links del mensaje, cuál es el del producto.

    (Claude, 25-ago-2026) LA PRIORIDAD ES EXPLÍCITA, Y ESE ERA EL BUG.
    Antes se tomaba "el primero que no fuera una imagen", y el aliado pone
    en sus mensajes, en este orden: la foto, un "buscar en Google", y recién
    después el link real. Sin tienda conocida se elegía el de Google — o sea
    que apretar PRODUCTO abría una búsqueda, no la ficha.

    Ahora, de mejor a peor:
      1. Un dominio del catálogo de Héctor (ahí se sabe el rubro gratis y se
         puede cruzar contra la base real).
      2. Cualquier otro link de tienda: no se puede cruzar, pero es la ficha.
      3. El redirector de afiliado del aliado, sólo si no hay nada mejor.
    Nunca un buscador, una red social ni una imagen.
    """
    otro_directo = None
    redirector = None
    for u in urls:
        dom = _dominio_de(u)
        if not dom or _es_imagen(u, dom) or _NO_ES_PRODUCTO.match(dom):
            continue
        conocida = tienda_de(dom)
        if conocida:
            return conocida, u, _DOMINIOS_HECTOR[conocida]
        if _REDIRECTOR_ALIADO.search(dom):
            redirector = redirector or u
            continue
        otro_directo = otro_directo or u
    return None, (otro_directo or redirector), None


# (Claude, 25-ago-2026) El aliado rotula sus mensajes con el mismo sistema de
# "rank" del que Rat.IA copió su formato (ver alertas.RANGOS), pero con más
# escalones: además de S/A/B usa C y D. Joaquín pidió explícitamente sacar el
# "DRank" de lo que llega al canal. No se saca con un reemplazo de texto: el
# mensaje se REARMA desde cero con los datos propios (ver
# reenviar_ofertas._armar_aviso), así que el rótulo del aliado no sobrevive.
# Este patrón existe sólo para poder leer el NOMBRE del producto de esa
# primera línea sin arrastrar el rank.
# El rank puede aparecer en cualquier parte de la línea, NO sólo al principio:
# el mensaje real arranca con un `<a>` que envuelve la miniatura, así que al
# quitar las etiquetas queda su texto de ancla delante del rank. Anclar el
# patrón a `^` dejaba pasar el "DRank" entero -- verificado con un mensaje
# reconstruido tal como llega de Telethon.
_RANK = re.compile(r"\b[SABCD]\s*rank\b[\s:·|-]*", re.I)
_ETIQUETAS_HTML = re.compile(r"<[^>]+>")
_EMOJI_SUELTO = re.compile(
    r"[\U0001F000-\U0001FAFF←-⇿⌀-➿️⬀-⯿"
    r"​-‍⁠﻿]")


def _sin_prefijo_de_tienda(nombre, tienda):
    """Saca el nombre del comercio cuando el aliado lo repite delante.

    Su formato es "RANK  tienda  producto", así que sin esto el aviso queda
    con la tienda dos veces: una en la línea de rank que arma Rat.IA y otra
    pegada al nombre del producto.
    """
    if not nombre or not tienda:
        return nombre
    base = tienda.split(".")[0]
    patron = re.compile(r"^\s*%s\b[\s:·|,-]*" % re.escape(base), re.I)
    return patron.sub("", nombre).strip() or nombre


def nombre_declarado(texto, tienda=None):
    """El nombre del producto según el mensaje del aliado.

    Es la primera línea con contenido, sin el rank, sin etiquetas HTML, sin
    emojis y sin el nombre del comercio repetido. Se usa sólo como respaldo:
    si la ficha real se pudo leer, gana el nombre de la tienda, que es el que
    el suscriptor va a ver al entrar.
    """
    for linea in (texto or "").split("\n"):
        limpia = _ETIQUETAS_HTML.sub(" ", linea)
        limpia = _EMOJI_SUELTO.sub(" ", limpia)
        limpia = _RANK.sub(" ", limpia)
        # Fichas sueltas de un carácter: lo que queda del ancla de la
        # miniatura y de los separadores del aliado.
        piezas = [p for p in limpia.split() if len(p) > 1 or p.isalnum()]
        limpia = " ".join(piezas).strip(" ·|-–—:,")
        limpia = _sin_prefijo_de_tienda(limpia, tienda)
        if len(limpia) >= 8 and not limpia.startswith("$"):
            return limpia[:120]
    return None


def extraer_porcentaje(texto):
    m = _PORCENTAJE.search(texto or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ".")) / 100.0
    except ValueError:
        return None


def extraer_precios(texto):
    """Todos los "$NNN" del mensaje, como enteros (sin puntos de miles)."""
    precios = []
    for m in _PRECIO.finditer(texto or ""):
        crudo = re.sub(r"[.,]", "", m.group(1))
        if crudo.isdigit():
            precios.append(int(crudo))
    return precios


def es_irrelevante(texto, rubro, url=None):
    # (Claude, 25-ago-2026) LIBRERÍAS: NUNCA. Pedido de Joaquín, "nunca más
    # avisaremos ofertas ni errores de precios con ellos".
    #
    # Se chequea por DOMINIO y no sólo por `rubro`, porque el rubro venía de
    # `_DOMINIOS_HECTOR` -- y esos dominios ya salieron de `tiendas.py` en el
    # mismo pedido, así que la rama de abajo dejó de dispararse sola. Sin
    # esto, un reenvío del aliado con un link a Antártica pasaría: no calza
    # con ninguna tienda conocida, y si el título no dice "libro" tampoco lo
    # atrapa `RUIDO_IRRELEVANTE`.
    if url and baseprecios.es_libreria(url):
        return True, "librería (no se avisan libros)"
    if rubro == "libros":
        return True, "tienda de libros (%s)" % rubro
    if RUIDO_IRRELEVANTE.search(texto or ""):
        m = RUIDO_IRRELEVANTE.search(texto)
        return True, 'categoría irrelevante ("%s")' % m.group(0)
    if categorias.RUIDO.search(texto or ""):
        m = categorias.RUIDO.search(texto)
        return True, 'accesorio/consumible ("%s")' % m.group(0)
    return False, None


def abrir_solo_lectura(ruta):
    """Conexión de solo lectura a la copia descargada de precios.db. Con
    `mode=ro`, SQLite rechaza cualquier escritura a nivel de driver -- no
    hace falta confiar en que el código de arriba nunca llame a un INSERT
    por error.

    `check_same_thread=False`: `evaluar_mensaje` corre dentro de
    `asyncio.to_thread` (ver reenviar_ofertas.py), así que esta conexión se
    usa desde un hilo distinto al que la abrió. El acceso concurrente real
    se serializa con un lock en el llamador -- esto solo baja la barrera de
    sqlite3, no reemplaza esa serialización."""
    con = sqlite3.connect("file:%s?mode=ro" % ruta, uri=True, timeout=10,
                          check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def _existe_en_base(con_hector, url):
    f = con_hector.execute("SELECT 1 FROM precios WHERE url=? LIMIT 1", (url,)).fetchone()
    return f is not None


def historial_propio(con_hector, url, ahora=None):
    """(Claude, 25-ago-2026) El sondeo de precios QUE HICIMOS NOSOTROS.

    Devuelve [(precio, epoch_desde), ...] de más reciente a más antiguo, o []
    si no tenemos nada de esa ficha.

    Existe porque el reclamo concreto de Joaquín contra el canal del aliado es
    que sus "precios históricos" a veces son de horas antes -- una barrida
    reciente disfrazada de historia. Nuestra ventana es de 30 días y cada
    tramo tiene su fecha, así que el mensaje puede mostrar de cuándo es cada
    número en vez de pedir que se le crea.
    """
    try:
        return baseprecios.historial(con_hector, url, ahora=ahora)[:4]
    except sqlite3.Error:
        return []


def cruzar_con_base_hector(con_hector, url, tienda, nombre, precio_declarado, ahora=None):
    """Le pregunta a la lógica YA VALIDADA de Héctor si esta caída es real.

    Devuelve (veredicto, caida_real, motivo, referencia) o None si la URL no
    está en la base de Héctor en absoluto (ahí no hay evidencia ni a favor ni
    en contra, y el llamador debe intentar verificación en vivo en cambio).

    `referencia` es el precio contra el que Héctor mide la caída -- el mínimo
    real de 30 días, no el "antes" que declara el aliado. Se devuelve para
    poder mostrarlo en el aviso: es la diferencia entre un descuento que se
    puede auditar y uno que hay que creer.
    """
    if not _existe_en_base(con_hector, url):
        return None
    det = baseprecios.evaluar(con_hector, url, precio_declarado, ahora=ahora,
                               nombre=nombre, tienda=tienda)
    if det:
        return "confirmado", det["caida"], (
            "confirmado contra la base propia: %.0f%% real (%s)"
            % (det["caida"] * 100, det.get("tipo", ""))), det.get("referencia")
    return "descartado", None, (
        "existe en la base propia pero NO califica como caída real contra su "
        "historial (referencia real distinta a la declarada)"), None


def verificar_en_vivo(tienda, url, precio_declarado, bajar_fn=None, extraer_fn=None):
    """Pide la ficha real y compara. Sin historial no se puede confirmar la
    MAGNITUD de la caída, pero sí se puede detectar que el precio declarado
    es directamente falso.

    `bajar_fn`/`extraer_fn` son inyectables para poder probar esto sin red.
    """
    bajar_fn = bajar_fn or descubrir.bajar
    extraer_fn = extraer_fn or extractor.extraer
    try:
        especial = adaptadores.para(tienda) if tienda else None
        if especial:
            d = especial(url, lambda u, c: bajar_fn(u, cabeceras=c))
        else:
            html = bajar_fn(url)
            d = extraer_fn(html)
        if not d or not d.get("precio"):
            return {"ok": False, "motivo": "sin precio legible"}
        precio_real = int(d["precio"])
        # 5% de margen: el precio pudo moverse un poco entre que el aliado
        # publicó y esta verificación corrió unos segundos/minutos después.
        coincide = precio_declarado and abs(precio_real - precio_declarado) <= max(
            500, precio_declarado * 0.05)
        return {"ok": True, "precio_real": precio_real, "coincide": bool(coincide),
                "nombre": d.get("nombre")}
    except Exception as e:                                    # noqa: BLE001
        return {"ok": False, "motivo": str(e)[:150]}


def puntaje(veredicto, confianza_canal=None):
    """0..1. Se compara contra `hector2_db.umbral_actual(topico)` para
    decidir si se manda. Un `sin_verificar` de un canal con buen historial
    puntúa más alto que uno de un canal sin evidencia todavía -- es el punto
    donde la confianza por canal (que se acumula sola con el tiempo) empieza
    a influir en las decisiones del día a día, no solo a quedar registrada.
    """
    if veredicto == "confirmado":
        return 0.95
    if veredicto == "descartado":
        return 0.0
    base = 0.35
    if confianza_canal is not None:
        base += 0.4 * confianza_canal
    return min(0.85, base)


def evaluar_mensaje(texto, canal, con_hector=None, verificar_vivo=True,
                     confianza_canal_fn=None, ahora=None,
                     bajar_fn=None, extraer_fn=None):
    """Orquesta todo lo de arriba. Devuelve un dict con todo lo que hace
    falta para decidir y para registrar en hector2_db, sin decidir todavía
    SI se manda -- eso depende del ritmo del tópico, que vive en hector2_db
    y no acá."""
    urls = extraer_urls(texto)
    tienda, url, rubro = detectar_producto(urls)
    pct_declarado = extraer_porcentaje(texto)
    precios = extraer_precios(texto)
    precio_declarado = min(precios) if precios else None
    nombre = nombre_declarado(texto, tienda)
    imagen = imagen_de(urls)

    def _salida(veredicto, motivo, fuente, **extra):
        conf = (confianza_canal_fn(canal)
                if (confianza_canal_fn and veredicto != "descartado") else None)
        d = {"veredicto": veredicto, "motivo": motivo, "fuente": fuente,
             "tienda": tienda, "url": url, "nombre": nombre,
             "imagen": imagen,
             "caida_declarada": pct_declarado, "caida_real": None,
             "precio_declarado": precio_declarado, "precio_real": None,
             # El "antes" que declara el aliado. Se guarda para poder
             # compararlo con nuestra referencia real (es exactamente el
             # número que a veces está inflado), NUNCA para publicarlo como
             # si fuera nuestro.
             "referencia_declarada": (max(precios) if len(precios) >= 2 else None),
             "referencia": None, "historico": [],
             "puntaje": puntaje(veredicto, conf)}
        d.update(extra)
        return d

    # Amazon primero: si no se puede comprar desde Chile, no importa que la
    # caída sea real -- no hay nada que verificar ni que reenviar.
    if esta_bloqueada(_dominio_de(url)) or any(
            esta_bloqueada(_dominio_de(u)) for u in urls):
        return _salida("descartado", "Amazon: no despacha a Chile", "bloqueada")

    irrelevante, motivo_irrelevante = es_irrelevante(texto, rubro, url)
    if irrelevante:
        return _salida("descartado", motivo_irrelevante, "categoria")

    caida_real = None
    referencia = None
    precio_real = None
    fuente = "sin_dato"
    veredicto, motivo = "sin_verificar", "sin URL de producto reconocible"

    if url and con_hector is not None and precio_declarado:
        resultado = cruzar_con_base_hector(con_hector, url, tienda, nombre,
                                           precio_declarado, ahora=ahora)
        if resultado is not None:
            veredicto, caida_real, motivo, referencia = resultado
            fuente = "base_propia"

    if url and fuente == "sin_dato" and verificar_vivo and precio_declarado:
        v = verificar_en_vivo(tienda, url, precio_declarado,
                              bajar_fn=bajar_fn, extraer_fn=extraer_fn)
        fuente = "verificado_en_vivo"
        precio_real = v.get("precio_real")
        if v.get("nombre"):
            nombre = v["nombre"]
        if not v["ok"]:
            veredicto = "sin_verificar"
            motivo = "no se pudo verificar en vivo: %s" % v["motivo"]
        elif v["coincide"]:
            veredicto = "confirmado" if (pct_declarado and pct_declarado >= 0.35) else "sin_verificar"
            motivo = "precio actual coincide con lo declarado (verificación en vivo)"
        else:
            veredicto = "descartado"
            motivo = ("precio actual real ($%s) NO coincide con lo declarado ($%s)"
                       % (v.get("precio_real"), precio_declarado))

    # El sondeo propio se adjunta SIEMPRE que exista, incluso cuando el
    # veredicto quedó en `sin_verificar`: es el dato que hace auditable el
    # aviso, y es justo lo que el mensaje del aliado no trae bien.
    historico = (historial_propio(con_hector, url, ahora=ahora)
                 if (url and con_hector is not None) else [])

    return _salida(veredicto, motivo, fuente, caida_real=caida_real,
                   precio_real=precio_real, referencia=referencia,
                   historico=historico)
