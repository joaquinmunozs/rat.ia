# -*- coding: utf-8 -*-
"""Rat.IA · el texto de cada aviso de convenio, para Telegram e Instagram.

Convenios bancarios NO llevan el mecanismo de "comenta y te mando el link
por DM" que sí tienen las ofertas de retail (`ratia_publicar.caption_oferta`):
ahí el link se oculta para forzar el comentario y capturar el correo, algo
que Joaquín pidió explícito para ESE flujo. Acá no lo pidió, y esconder el
comercio/banco de un convenio público no tiene el mismo sentido -- es
información de servicio, no un hallazgo que dependa de verificar en vivo
antes de mostrarlo. El link a la ficha de Pangui va directo en el texto.
"""
from __future__ import annotations

from datetime import date


def _vigencia_txt(vigencia_hasta: date | None, es_recurrente: bool) -> str:
    if es_recurrente:
        return "Sin fecha de término conocida — se revisa cada mes."
    if vigencia_hasta:
        return "Vigente hasta el %s." % vigencia_hasta.strftime("%d-%m-%Y")
    return ""


def _dia_txt(dia_semana: str | None) -> str:
    if not dia_semana:
        return ""
    if dia_semana == "días":
        return "Todos los días."
    return "Todos los %s." % dia_semana


def telegram_nuevo(emisor: str, comercio: str, descuento: int, titulo: str,
                   dia_semana: str | None, vigencia_hasta: date | None,
                   es_recurrente: bool, url_fuente: str) -> str:
    lineas = [
        "💳 <b>%s</b> · <i>%s</i>" % (_escapar(emisor), _escapar(comercio)),
        "<b>%d%% de descuento</b>" % descuento,
        _escapar(titulo),
        "",
    ]
    dia = _dia_txt(dia_semana)
    if dia:
        lineas.append(dia)
    vig = _vigencia_txt(vigencia_hasta, es_recurrente)
    if vig:
        lineas.append(vig)
    lineas += ["", '<a href="%s">Ver detalle</a>' % url_fuente]
    return "\n".join(lineas)


def telegram_recordatorio(emisor: str, comercio: str, descuento: int,
                          vigencia_hasta: date | None, es_recurrente: bool,
                          url_fuente: str) -> str:
    lineas = [
        "🔁 <b>Recordatorio</b> — %s · %s" % (_escapar(emisor), _escapar(comercio)),
        "Sigue vigente: <b>%d%% de descuento</b>." % descuento,
    ]
    vig = _vigencia_txt(vigencia_hasta, es_recurrente)
    if vig:
        lineas.append(vig)
    lineas += ["", '<a href="%s">Ver detalle</a>' % url_fuente]
    return "\n".join(lineas)


def telegram_ultima_vez(emisor: str, comercio: str, descuento: int,
                        vigencia_hasta: date | None, url_fuente: str) -> str:
    lineas = [
        "⏰ <b>Última semana</b> — %s · %s" % (_escapar(emisor), _escapar(comercio)),
        "<b>%d%% de descuento</b>, se acaba pronto." % descuento,
        _vigencia_txt(vigencia_hasta, es_recurrente=False),
        "",
        '<a href="%s">Ver detalle</a>' % url_fuente,
    ]
    return "\n".join(l for l in lineas if l)


def instagram_nuevo(emisor: str, comercio: str, descuento: int, titulo: str,
                    dia_semana: str | None, vigencia_hasta: date | None,
                    es_recurrente: bool) -> str:
    lineas = [
        "💳 %s + %s" % (comercio, emisor),
        "%d%% de descuento" % descuento,
        "",
        titulo,
    ]
    dia = _dia_txt(dia_semana)
    if dia:
        lineas.append(dia)
    vig = _vigencia_txt(vigencia_hasta, es_recurrente)
    if vig:
        lineas.append(vig)
    lineas += ["", "#convenios #descuentos #chile"]
    return "\n".join(lineas)


def instagram_ultima_semana(emisor: str, comercio: str, descuento: int,
                            vigencia_hasta: date | None) -> str:
    lineas = [
        "⏰ ¡Última semana!",
        "%s + %s — %d%% de descuento" % (comercio, emisor, descuento),
        _vigencia_txt(vigencia_hasta, es_recurrente=False),
        "",
        "#convenios #descuentos #chile",
    ]
    return "\n".join(l for l in lineas if l)


def _escapar(t: str) -> str:
    return (str(t or "").replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;"))
