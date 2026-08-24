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


# Dominios que casi seguro son de imágenes/CDN del propio aliado, no del
# producto -- verificado contra ejemplos reales en los logs de Railway
# (ej. "img2.ofertasshark.cl"). Es una lista chica y con "startswith" a
# propósito: mejor perder algún dominio raro de imagen que descartar por
# error el link real del producto.
_PREFIJOS_NO_PRODUCTO = ("img.", "img1.", "img2.", "cdn.", "static.", "media.")


def detectar_producto(urls):
    """De todos los links del mensaje, cuál es el del producto.

    Prioridad: un dominio que YA está en el catálogo de 44 tiendas de Héctor
    (ahí se sabe además el rubro, gratis). Si ninguno calza, se toma el
    primer link que no parezca una imagen del propio aliado -- sin tienda
    conocida, así que solo sirve para verificación en vivo, no para cruzar
    contra la base.
    """
    candidatos = []
    for u in urls:
        dom = _dominio_de(u)
        if not dom:
            continue
        if dom in _DOMINIOS_HECTOR:
            return dom, u, _DOMINIOS_HECTOR[dom]
        if not dom.startswith(_PREFIJOS_NO_PRODUCTO):
            candidatos.append(u)
    if candidatos:
        return None, candidatos[0], None
    return None, None, None


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


def es_irrelevante(texto, rubro):
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
    por error."""
    con = sqlite3.connect("file:%s?mode=ro" % ruta, uri=True, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def _existe_en_base(con_hector, url):
    f = con_hector.execute("SELECT 1 FROM precios WHERE url=? LIMIT 1", (url,)).fetchone()
    return f is not None


def cruzar_con_base_hector(con_hector, url, tienda, nombre, precio_declarado, ahora=None):
    """Le pregunta a la lógica YA VALIDADA de Héctor si esta caída es real.

    Devuelve (veredicto, caida_real, motivo) o None si la URL no está en la
    base de Héctor en absoluto (ahí no hay evidencia ni a favor ni en contra,
    y el llamador debe intentar verificación en vivo en cambio).
    """
    if not _existe_en_base(con_hector, url):
        return None
    det = baseprecios.evaluar(con_hector, url, precio_declarado, ahora=ahora,
                               nombre=nombre, tienda=tienda)
    if det:
        return "confirmado", det["caida"], (
            "confirmado contra la base propia: %.0f%% real (%s)"
            % (det["caida"] * 100, det.get("tipo", "")))
    return "descartado", None, (
        "existe en la base propia pero NO califica como caída real contra su "
        "historial (referencia real distinta a la declarada)")


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

    irrelevante, motivo_irrelevante = es_irrelevante(texto, rubro)
    if irrelevante:
        return {"veredicto": "descartado", "motivo": motivo_irrelevante,
                "fuente": "categoria", "tienda": tienda, "url": url,
                "caida_declarada": pct_declarado, "caida_real": None,
                "puntaje": 0.0}

    caida_real = None
    fuente = "sin_dato"
    veredicto, motivo = "sin_verificar", "sin URL de producto reconocible"

    if url and con_hector is not None and precio_declarado:
        resultado = cruzar_con_base_hector(con_hector, url, tienda, None,
                                           precio_declarado, ahora=ahora)
        if resultado is not None:
            veredicto, caida_real, motivo = resultado
            fuente = "base_propia"

    if url and fuente == "sin_dato" and verificar_vivo and precio_declarado:
        v = verificar_en_vivo(tienda, url, precio_declarado,
                              bajar_fn=bajar_fn, extraer_fn=extraer_fn)
        fuente = "verificado_en_vivo"
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

    conf = confianza_canal_fn(canal) if confianza_canal_fn else None
    return {"veredicto": veredicto, "motivo": motivo, "fuente": fuente,
            "tienda": tienda, "url": url, "caida_declarada": pct_declarado,
            "caida_real": caida_real, "puntaje": puntaje(veredicto, conf)}
