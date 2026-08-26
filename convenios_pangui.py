# -*- coding: utf-8 -*-
"""Rat.IA · convenios banco-comercio, extraídos de panguiapp.com.

PARA QUÉ EXISTE
------------------------------------------------------------------------------
Pedido de Joaquín (25-ago-2026): sumar a Instagram/Telegram una tercera
fuente de contenido, distinta de las caídas de precio de Héctor —
alianzas banco-comercio ("40% en Copec pagando con Lider Bci") y
promociones de cadenas (McDonald's, KFC, farmacias, buses…).

Ningún banco chileno ofrece un webhook para esto. `panguiapp.com` sí sirve:
es un agregador real, activo, con páginas por emisor (`/bancos/{slug}`) y
por comercio (`/tiendas/{slug}`), pre-renderizadas (Next.js, HTML real, no
depende de JS para verse), sin protección anti-bot, y `robots.txt` permite
explícitamente `/bancos/` y `/tiendas/` (sólo prohíbe `/tarjetas`,
`/guardadas`, `/perfil`, `/admin`, `/api`). Verificado en vivo el 25-ago,
no asumido.

CADA OFERTA TRAE SU PROPIA SEÑAL DE CONFIANZA
------------------------------------------------------------------------------
El sitio marca cada convenio como "Verificado hoy" o "Sin verificar hace N
días" — es la vara real para decidir qué se publica sin revisión humana
(pedido explícito de Joaquín: "publica sola si pasa la verificación").
`verificado_recientemente` en el resultado usa esa señal.

CÓMO SE EXTRAE, Y POR QUÉ ASÍ
------------------------------------------------------------------------------
La página trae los datos "de verdad" en un payload de streaming de Next.js
(React Server Components) que no es JSON plano fácil de aislar con
seguridad. En cambio, el TEXTO RENDERIZADO (quitando etiquetas) sigue
siempre el mismo patrón, verificado contra tres páginas reales de
categorías distintas (McDonald's, Farmacias Cruz Verde, Turbus — ver
`fixtures/pangui_*.html`):

    N % de descuento  CATEGORÍA  COMERCIO
    <título y texto libre de la oferta>
    [Presencial|Online|Todos los canales]
    Todos los <día(s)> | Todos los días
    Verificado hoy | Sin verificar hace N días
    [Cerca de ti]
    Ver detalle → [Hasta DD mes AAAA]

Cada oferta se separa de la siguiente por "N % de descuento" (el inicio) y
"Ver detalle" (el fin) — se confirmó contando: "N ofertas activas" en el
encabezado == N apariciones de cada marcador, en las tres páginas de
prueba.

POR QUÉ "COMERCIO" NO SE ADIVINA DEL TEXTO
------------------------------------------------------------------------------
El nombre del comercio aparece con capitalización distinta según quién lo
cargó en Pangui — "McDonald's" (mixto), "FARMACIAS CRUZ VERDE" (mayúscula
total), "TURBUS" (mayúscula total) — sin un patrón único que permita
aislarlo con un regex confiable. La solución real es no adivinarlo: quien
llama a `extraer_convenios` YA SABE qué página está vigilando (`comercio`
en una página `/tiendas/{x}`, `emisor` en una página `/bancos/{x}`, ambos
fijos de antemano en la config del monitor), así que se pasan como
parámetro. Lo que SÍ hace falta leer del texto es el que NO es fijo en esa
página: el emisor específico dentro de una ficha de comercio (puede
cambiar oferta por oferta -- ver `_EMISORES_CONOCIDOS`), o viceversa.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

MESES_ES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dic": 12,
}

_SCRIPT_O_ESTILO = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_ETIQUETA = re.compile(r"<[^>]+>")
_ESPACIOS = re.compile(r"\s+")

_INICIO_OFERTA = re.compile(r"(\d{1,3})\s*%\s*de descuento\b", re.I)

# Vocabulario cerrado (sale de las secciones reales del propio sitio:
# panguiapp.com/descuentos/{categoria}/...). Marca dónde termina la
# categoría en la cabecera de cada oferta -- lo que viene inmediatamente
# después, hasta el primer dígito, es el nombre del comercio tal como lo
# muestra Pangui (no siempre coincide con el `comercio` que pasó quien
# llama, por eso se guarda aparte como `comercio_pangui`).
_CATEGORIAS = ("Restaurante", "Viajes", "Salud", "Supermercado",
              "Entretenimiento", "Delivery", "Tecnología", "Tecnologia", "Otros")

_VERIFICADO_HOY = re.compile(r"\bVerificado hoy\b")
_SIN_VERIFICAR = re.compile(r"\bSin verificar hace (\d+) d[ií]as?\b")
_HASTA_FECHA = re.compile(
    r"Hasta\s+(\d{1,2})\s+([a-záéíóú]{3,4})\.?\s+(\d{4})", re.I)
# Ancla al final EXACTO de "→ Hasta DD mes AAAA" cuando aparece justo
# después de "Ver detalle" -- ver el comentario en `extraer_convenios`
# sobre por qué no se usa un colchón de caracteres fijo.
_COLA_HASTA = re.compile(
    r"\s*→?\s*Hasta\s+\d{1,2}\s+[a-záéíóú]{3,4}\.?\s+\d{4}", re.I)
_DIA_SEMANA = re.compile(
    r"Todos los (lunes|martes|mi[ée]rcoles|jueves|viernes|s[áa]bados|"
    r"domingos|d[ií]as)\b", re.I)
_CANAL = re.compile(r"\b(Presencial|Online|Todos los canales)\b")


def _texto_plano(html: str) -> str:
    """El HTML, sin scripts/estilos/etiquetas, con entidades comunes
    resueltas -- lo único que hace falta para leer el texto tal como lo ve
    un visitante."""
    limpio = _SCRIPT_O_ESTILO.sub(" ", html)
    limpio = _ETIQUETA.sub(" ", limpio)
    limpio = limpio.replace("&#x27;", "'").replace("&amp;", "&")
    limpio = limpio.replace("&aacute;", "á").replace("&eacute;", "é")
    limpio = limpio.replace("&iacute;", "í").replace("&oacute;", "ó")
    limpio = limpio.replace("&uacute;", "ú").replace("&ntilde;", "ñ")
    return _ESPACIOS.sub(" ", limpio).strip()


def _fecha_de(texto_hasta: str) -> date | None:
    m = _HASTA_FECHA.search(texto_hasta)
    if not m:
        return None
    dia, mes_txt, anio = m.groups()
    mes = MESES_ES.get(mes_txt.lower()[:4]) or MESES_ES.get(mes_txt.lower()[:3])
    if not mes:
        return None
    try:
        return date(int(anio), mes, int(dia))
    except ValueError:
        return None


def _categoria_y_resto(cabecera: str) -> tuple[str | None, str]:
    """Separa el prefijo de categoría (si viene) del resto de la cabecera.

    Antes esto y la extracción del comercio vivían en la misma función
    (`_categoria_y_comercio_pangui`) y el LLAMADOR volvía a cortar la
    cabecera ORIGINAL por el largo del comercio ya encontrado -- en una
    página con categoría (la mayoría), eso ignoraba los caracteres de la
    categoría y el `titulo` salía corrido ("Chile 80%..." en vez de
    "80%..."). Separarlas evita que ese bug pueda volver: el llamador ahora
    corta siempre desde `resto`, nunca desde `cabecera`."""
    for cat in _CATEGORIAS:
        if cabecera.startswith(cat):
            return cat, cabecera[len(cat):].strip()
    return None, cabecera


def _comercio_generico(resto: str) -> str:
    """Todo lo que sigue hasta el primer dígito -- sirve de respaldo cuando
    no aplica (o no calza) el patrón de página de banco. Funciona en los
    tres formatos reales observados (mixto, mayúscula total) porque no
    depende de la capitalización, sólo de dónde aparece el primer número."""
    m = re.match(r"^([^\d]{1,60}?)(?=\d|$)", resto)
    comercio = (m.group(1).strip() if m else resto[:40].strip())
    return comercio or resto[:40].strip()


_PCT_EN = re.compile(r"^\s*\d{1,3}\s*%\s*en\s+(.+)$", re.I)


def _comercio_real_pagina_banco(resto: str, emisor: str) -> tuple[str, str] | None:
    """En una página /bancos/{x}, la cabecera de CADA oferta repite el
    nombre del banco como etiqueta antes de decir la oferta real:
    'Banco de Chile 80% en Clínica Dental 3Dent Más de 30 años...'.

    Encontrado el 26-ago-2026 al revisar por qué una pieza de Instagram
    publicó "Banco de Chile + Banco de Chile" -- el comercio real ("Clínica
    Dental 3Dent") nunca se leía: `_comercio_generico` paraba en el primer
    dígito, que es el de la etiqueta repetida, no el del comercio real.
    Verificado contra las 772 ofertas reales de /bancos/banco-de-chile: la
    etiqueta aparece en el 100% de los casos.

    Devuelve (comercio_real, resto_para_titulo), o None si `resto` no
    calza ese patrón -- el llamador cae entonces a `_comercio_generico`,
    nunca revienta por esto.
    """
    bajo = resto.lower()
    if not bajo.startswith(emisor.strip().lower()):
        return None
    tras_emisor = resto[len(emisor):].strip()
    m = _PCT_EN.match(tras_emisor)
    if not m:
        return None
    despues_en = m.group(1)
    comercio_real = _acotar_nombre_comercio(despues_en)
    return comercio_real, despues_en


# Aperturas típicas de la frase de marketing que sigue al nombre del
# comercio ("Más de 30 años...", "Somos Esan...", "Ven a disfrutar...") --
# van en mayúscula por ser inicio de oración, así que el chequeo de
# "empieza con mayúscula" no basta para distinguirlas de un nombre propio.
_NO_ES_NOMBRE_COMERCIO = {
    "mas", "más", "con", "ven", "es", "somos", "en", "accede", "aprovecha",
    "descubre", "vive", "disfruta", "obten", "obtén", "consigue", "una",
    "un", "esta", "está", "nuestro", "nuestra", "el", "la",
}
_CONECTORES = ("de", "del", "la", "los", "las", "y")


def _acotar_nombre_comercio(texto: str) -> str:
    """Hasta 3 palabras 'reales' (mayúscula o dígito inicial, y que no sean
    un arranque de frase de marketing conocido) más los conectores que caen
    entre medio -- suficiente para "Clínica Dental 3Dent" o "Portal
    Ortodoncia de Chile" sin comerse la oración que sigue. No es perfecto
    (nombres de 4+ palabras se acortan), pero es un salto enorme respecto a
    devolver el nombre del banco repetido."""
    tomadas: list[str] = []
    reales = 0
    for palabra in texto.split():
        limpia = palabra.strip(",;:¡!¿?")
        if not limpia:
            continue
        bajo = limpia.lower()
        es_conector = bajo in _CONECTORES
        es_real = (limpia[0].isupper() or limpia[0].isdigit()) and bajo not in _NO_ES_NOMBRE_COMERCIO
        if not (es_conector or es_real):
            break
        if es_conector and not tomadas:
            break  # un conector no puede ser la primera palabra del nombre
        if es_real:
            if reales >= 3:
                break
            reales += 1
        tomadas.append(limpia)
    while tomadas and tomadas[-1].lower() in _CONECTORES:
        tomadas.pop()
    return " ".join(tomadas).rstrip(".") if tomadas else texto.split(".")[0][:60]


@dataclass
class ConvenioPangui:
    emisor: str            # el banco/tarjeta que da el descuento
    comercio: str
    categoria: str | None
    descuento: int          # %, entero
    titulo: str
    canal: str | None
    dia_semana: str | None  # "martes", "días" (=todos los días), o None
    verificado_recientemente: bool
    dias_sin_verificar: int | None
    vigencia_hasta: date | None
    texto: str               # el bloque completo, para el caption/registro
    url_fuente: str
    clave: str = field(init=False)

    def __post_init__(self):
        # Identifica la MISMA oferta entre pasadas -- no el texto completo
        # (que puede variar en detalles legales sin ser una oferta nueva),
        # sino emisor+comercio+descuento+título, que es lo que de verdad
        # cambia cuando el convenio es otro.
        self.clave = "|".join((self.emisor, self.comercio,
                               str(self.descuento), self.titulo))[:300]

    @property
    def es_recurrente(self) -> bool:
        """Sin fecha de término y con un día fijo: "todos los martes",
        indefinido. Estos no vencen -- se recuerdan cada 30 días en vez de
        cada semana (ver `convenios_ciclo.py`)."""
        return self.vigencia_hasta is None and bool(self.dia_semana)


# Nombres de emisor tal como los escribe Pangui en el cuerpo del texto,
# para reconocerlos dentro de una página de TIENDA (donde el emisor varía
# oferta por oferta). Se listan con el nombre "bonito" que se quiere
# mostrar en el aviso, no el slug de la URL.
_EMISORES_CONOCIDOS = {
    "bancoestado": "BancoEstado", "banco estado": "BancoEstado",
    "rutpay": "RutPay",
    "banco de chile": "Banco de Chile", "tarjetas de chile": "Banco de Chile",
    "lider bci": "BCI", "bci": "BCI",
    "santander": "Santander",
    "cmr falabella": "CMR Falabella",
    "cencosud scotiabank": "Cencosud Scotiabank", "scotiabank": "Scotiabank",
    "mach": "Mach", "tenpo": "Tenpo",
    "banco security": "Banco Security", "banco ripley": "Banco Ripley",
    "coopeuch": "Coopeuch", "caja los andes": "Caja Los Andes",
}


def _emisor_de_bloque(bloque: str) -> str | None:
    bajo = bloque.lower()
    for clave, bonito in _EMISORES_CONOCIDOS.items():
        if clave in bajo:
            return bonito
    return None


def extraer_convenios(html: str, url_fuente: str, *, comercio: str | None = None,
                      emisor: str | None = None) -> list[ConvenioPangui]:
    """Todas las ofertas de una página de Pangui (banco o tienda).

    Pasar `comercio` cuando se vigila una página `/tiendas/{x}` (el
    comercio es fijo, el emisor puede variar oferta por oferta y se
    detecta del texto). Pasar `emisor` cuando se vigila una página
    `/bancos/{x}` (al revés: el emisor es fijo, el comercio varía y se lee
    de la cabecera de cada oferta vía `_categoria_y_comercio_pangui`).
    """
    texto = _texto_plano(html)
    inicio = texto.find("ofertas activas")
    if inicio == -1:
        return []
    cuerpo = texto[inicio:]

    # El delimitador confiable es "Ver detalle" (uno por oferta, verificado
    # contra el conteo real de "N ofertas activas" en las tres páginas de
    # prueba) -- NO "% de descuento": esa frase se repite dentro de la
    # propia descripción de una oferta ("...con Tarjeta de Crédito 40% de
    # descuento en la App McDonald's solo con Tarjeta de Crédito..."), así
    # que usarla como delimitador partía una sola oferta en varias.
    #
    # Cada bloque va desde donde terminó el anterior hasta el FINAL EXACTO
    # de su propio "→ Hasta DD mes AAAA" si viene -- nunca un colchón fijo
    # de N caracteres: con un colchón fijo, una oferta sin fecha de término
    # (o con una cola corta) le como parte del encabezado a la oferta
    # siguiente, y esa siguiente queda sin su "% de descuento" -- se perdía
    # así la segunda oferta de Farmacias Cruz Verde en la página real.
    fin_marcador = [m.end() for m in re.finditer(r"Ver detalle", cuerpo)]
    bloques = []
    desde = 0
    for pos in fin_marcador:
        cola = _COLA_HASTA.match(cuerpo, pos)
        hasta = cola.end() if cola else pos
        bloques.append(cuerpo[desde:hasta])
        desde = hasta

    salida = []
    for bloque in bloques:
        m = _INICIO_OFERTA.search(bloque)
        if not m:
            continue
        desc = int(m.group(1))

        cabecera = bloque[m.end():].strip()
        categoria, resto_categoria = _categoria_y_resto(cabecera)

        # Página /bancos/{x}: intenta el patrón "{emisor} {pct}% en
        # {comercio real}" primero -- si no calza (o esto es una página
        # /tiendas/{x}, donde `comercio` ya viene fijo y esto ni se usa),
        # cae al heurístico genérico de siempre.
        real = _comercio_real_pagina_banco(resto_categoria, emisor) if emisor and not comercio else None
        if real:
            comercio_pangui, resto_para_titulo = real
        else:
            comercio_pangui = _comercio_generico(resto_categoria)
            resto_para_titulo = resto_categoria[len(comercio_pangui):].strip()

        dia_m = _DIA_SEMANA.search(bloque)
        canal_m = _CANAL.search(bloque)
        ver_hoy = bool(_VERIFICADO_HOY.search(bloque))
        sin_ver = _SIN_VERIFICAR.search(bloque)

        # El título es lo que sigue al comercio en la cabecera, hasta el
        # primer punto -- es la oración corta que resume la oferta
        # ("40% de descuento en la App McDonald's...").
        titulo = resto_para_titulo.split(".")[0].strip()[:140] or comercio_pangui

        salida.append(ConvenioPangui(
            emisor=emisor or _emisor_de_bloque(bloque) or "(varios)",
            comercio=comercio or comercio_pangui,
            categoria=categoria,
            descuento=desc,
            titulo=titulo,
            canal=canal_m.group(1) if canal_m else None,
            dia_semana=(dia_m.group(1).lower() if dia_m else None),
            verificado_recientemente=ver_hoy,
            dias_sin_verificar=int(sin_ver.group(1)) if sin_ver else None,
            vigencia_hasta=_fecha_de(bloque),
            texto=bloque.strip(),
            url_fuente=url_fuente,
        ))
    return salida
