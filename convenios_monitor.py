# -*- coding: utf-8 -*-
"""Rat.IA · una pasada del monitor de convenios banco-comercio.

QUÉ HACE, EN ORDEN
==============================================================================
  1. Baja cada página vigilada de panguiapp.com (`convenios_fuentes.py`).
  2. Extrae los convenios de cada una (`convenios_pangui.py`).
  3. Para cada convenio decide qué corresponde HOY: avisar como nuevo,
     recordar en Telegram, avisar "última semana", publicar en Instagram
     (`convenios_ciclo.py`).
  4. Ejecuta esas acciones: manda a Telegram al tópico del emisor, y arma
     la pieza de Instagram cuando toca (`convenios_pieza.py`).
  5. Deja todo registrado en la tabla `convenios` de hector2.db.

CÓMO SE CORRE
==============================================================================
    python convenios_monitor.py              # una pasada, SIN publicar
    python convenios_monitor.py --confirmar  # publica de verdad

Pensado para correr 2-4 veces al día. No hace falta más: los convenios
bancarios no cambian cada hora como un precio de retail — la propia
Pangui actualiza una vez al día ("Actualizado el 25 de agosto de 2026").

⚠️ NO PUBLICA SOLO POR DEFECTO
==============================================================================
Mismo principio que `ratia_publicar` y `ratia_ig_selector`: sin
`--confirmar`, arma todo y loguea, pero no manda nada. Acá pesa más que en
retail: un aviso equivocado lleva el nombre de un banco real.

DÓNDE VA CADA AVISO DE TELEGRAM
==============================================================================
Al tópico del emisor (`FuentePangui.variable_topico` → una variable de
entorno con el id real del tópico, seteada en Railway). Si esa variable no
está, cae a `VIGIA_TOPICO_OFERTAS` y se avisa en el log — nunca se pierde
un aviso en silencio por una variable sin setear.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import convenios_ciclo as ciclo
import convenios_fuentes as fuentes
import convenios_pangui as pangui
import convenios_pieza
import convenios_textos as textos
import descubrir
import hector2_db
import ratia_publicar


def _topico_de(fuente: fuentes.FuentePangui, log=print) -> str | None:
    tid = (os.environ.get(fuente.variable_topico) or "").strip()
    if tid:
        return tid
    respaldo = (os.environ.get("VIGIA_TOPICO_OFERTAS") or "").strip() or None
    log("[convenios] ⚠️  %s sin setear — %s cae al tópico general"
        % (fuente.variable_topico, fuente.nombre))
    return respaldo


def _fecha_iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _estado_desde_fila(fila, primera_vista_hoy: date) -> ciclo.EstadoConvenio:
    if not fila:
        return ciclo.EstadoConvenio(primera_vista=primera_vista_hoy)
    return ciclo.EstadoConvenio(
        primera_vista=date.fromisoformat(fila["primera_vista"]),
        ultimo_recordatorio_telegram=(
            date.fromisoformat(fila["ultimo_recordatorio_telegram"])
            if fila["ultimo_recordatorio_telegram"] else None),
        publicado_en_instagram=bool(fila["publicado_en_instagram"]),
        aviso_ultima_semana_ig_enviado=bool(fila["aviso_ultima_semana_ig_enviado"]),
    )


def procesar_fuente(con, fuente: fuentes.FuentePangui, *, ahora: date,
                    confirmar: bool, log=print) -> list[tuple]:
    """Baja y procesa UNA página. Devuelve [(convenio, [acciones]), ...]."""
    try:
        html = descubrir.bajar(fuente.url)
    except Exception as e:                                    # noqa: BLE001
        log("[convenios] ❌ %s: no se pudo bajar — %s" % (fuente.nombre, str(e)[:120]))
        return []

    if fuente.tipo == "banco":
        convenios = pangui.extraer_convenios(html, fuente.url, emisor=fuente.nombre)
    else:
        convenios = pangui.extraer_convenios(html, fuente.url, comercio=fuente.nombre)

    if not convenios:
        log("[convenios] %s: 0 convenios extraídos" % fuente.nombre)
        return []

    topico = _topico_de(fuente, log=log)
    ahora_iso, ahora_epoch = ahora.isoformat(), int(time.time())
    resultados = []

    for c in convenios:
        fila = hector2_db.obtener_convenio(con, c.clave)
        es_nuevo = fila is None
        if es_nuevo:
            hector2_db.registrar_convenio_nuevo(con, c, ahora_iso, ahora_epoch)

        acciones = ciclo.decidir_acciones(
            es_nuevo=es_nuevo, descuento=c.descuento, comercio=c.comercio,
            verificado_recientemente=c.verificado_recientemente,
            vigencia_hasta=c.vigencia_hasta, es_recurrente=c.es_recurrente,
            estado=_estado_desde_fila(fila, ahora), ahora=ahora)

        if not acciones:
            continue
        # Se acumula sin ejecutar: los topes se aplican sobre el TOTAL de
        # la pasada (`una_pasada`), no por página -- si no, cada una de las
        # 16 fuentes gastaría su propio cupo y el tope global no existiría.
        resultados.append((c, acciones, topico))

    return resultados


def _ejecutar(con, c, acciones, topico, ahora_iso, ahora_epoch, log=print):
    """Manda de verdad. Cada acción marca su propio campo en la base DESPUÉS
    de que el envío salió bien -- si Telegram falla, no se marca, y la
    próxima pasada lo reintenta en vez de darlo por avisado."""
    for accion in acciones:
        if accion == "telegram_nuevo":
            txt = textos.telegram_nuevo(
                c.emisor, c.comercio, c.descuento, c.titulo, c.dia_semana,
                c.vigencia_hasta, c.es_recurrente, c.url_fuente)
            ratia_publicar_telegram(txt, topico, log=log)

        elif accion == "telegram_recordatorio":
            txt = textos.telegram_recordatorio(
                c.emisor, c.comercio, c.descuento, c.vigencia_hasta,
                c.es_recurrente, c.url_fuente)
            if ratia_publicar_telegram(txt, topico, log=log):
                hector2_db.marcar_recordatorio_telegram(
                    con, c.clave, ahora_iso, ahora_epoch)

        elif accion == "telegram_ultima_vez":
            txt = textos.telegram_ultima_vez(
                c.emisor, c.comercio, c.descuento, c.vigencia_hasta, c.url_fuente)
            if ratia_publicar_telegram(txt, topico, log=log):
                hector2_db.marcar_recordatorio_telegram(
                    con, c.clave, ahora_iso, ahora_epoch)

        elif accion in ("instagram_nuevo", "instagram_ultima_semana"):
            _publicar_instagram(con, c, accion, ahora_epoch, log=log)


def ratia_publicar_telegram(texto: str, topico: str | None, log=print) -> bool:
    """Reusa el envío ya probado de `reenviar_ofertas` en vez de reimplementar
    el reintento ante 429 y el manejo de errores de Telegram."""
    import reenviar_ofertas
    try:
        reenviar_ofertas._enviar_a_ratia(texto, topico)
        return True
    except Exception as e:                                    # noqa: BLE001
        log("[convenios] ❌ Telegram falló: %s" % str(e)[:140])
        return False


def _publicar_instagram(con, c, accion, ahora_epoch, log=print):
    pieza = convenios_pieza.generar_pieza_convenio(
        emisor=c.emisor, comercio=c.comercio, descuento=c.descuento,
        dia_semana=c.dia_semana, canal=c.canal,
        vigencia_hasta=c.vigencia_hasta, es_recurrente=c.es_recurrente,
        log=log)
    if not pieza:
        # `generar_pieza_convenio` ya explicó por qué en el log. No se
        # publica y NO se marca -- la próxima pasada lo reintenta.
        return

    if accion == "instagram_nuevo":
        caption = textos.instagram_nuevo(
            c.emisor, c.comercio, c.descuento, c.titulo, c.dia_semana,
            c.vigencia_hasta, c.es_recurrente)
    else:
        caption = textos.instagram_ultima_semana(
            c.emisor, c.comercio, c.descuento, c.vigencia_hasta)

    cuenta = os.environ.get("RATIA_IG_CUENTA_ID", "")
    if not cuenta:
        log("[convenios] ⚠️  RATIA_IG_CUENTA_ID sin setear — pieza lista, sin publicar")
        return

    try:
        ratia_publicar.publicar_media(pieza, caption, cuenta, log=log)
    except Exception as e:                                    # noqa: BLE001
        log("[convenios] ❌ Instagram falló: %s" % str(e)[:140])
        return

    if accion == "instagram_nuevo":
        hector2_db.marcar_publicado_instagram(con, c.clave, ahora_epoch)
    else:
        hector2_db.marcar_aviso_ultima_semana_ig(con, c.clave, ahora_epoch)


def una_pasada(con, *, confirmar=False, ahora=None, log=print):
    ahora = ahora or date.today()
    ahora_iso, ahora_epoch = ahora.isoformat(), int(time.time())

    pendientes = []
    for fuente in fuentes.FUENTES_PANGUI:
        pendientes += procesar_fuente(con, fuente, ahora=ahora,
                                      confirmar=confirmar, log=log)
        time.sleep(1.5)   # cortesía con el sitio: 16 páginas, sin apuro

    if not pendientes:
        log("[convenios] nada que avisar en esta pasada.")
        return []

    ig_hoy = hector2_db.convenios_publicados_ig_hoy(con, ahora_iso)
    elegidos = ciclo.aplicar_topes(
        [(c, acc) for c, acc, _t in pendientes], ya_publicados_ig_hoy=ig_hoy)

    # El tópico se perdió al recortar (aplicar_topes no lo conoce): se
    # recupera por la clave, que es única.
    topico_por_clave = {c.clave: t for c, _acc, t in pendientes}

    log("[convenios] %d con acciones pendientes → %d en esta pasada "
        "(topes: %d Telegram, %d Instagram/día; ya publicados hoy en IG: %d)"
        % (len(pendientes), len(elegidos), ciclo.TOPE_TELEGRAM_POR_PASADA,
           ciclo.TOPE_INSTAGRAM_POR_DIA, ig_hoy))

    for c, acciones in elegidos:
        log("[convenios] %s · %s -%d%% → %s"
            % (c.emisor, c.comercio, c.descuento, ", ".join(acciones)))
        if confirmar:
            _ejecutar(con, c, acciones, topico_por_clave.get(c.clave),
                      ahora_iso, ahora_epoch, log=log)

    if not confirmar:
        log("[convenios] NO se publicó nada: falta --confirmar.")
    return elegidos


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--confirmar", action="store_true",
                    help="Publica de verdad. Sin esto, sólo arma y loguea.")
    ap.add_argument("--fuente", help="Correr sólo una fuente, por nombre.")
    args = ap.parse_args()

    con = hector2_db.abrir()
    if args.fuente:
        elegidas = [f for f in fuentes.FUENTES_PANGUI
                    if f.nombre.lower() == args.fuente.lower()]
        if not elegidas:
            print("No existe esa fuente. Disponibles: %s"
                  % ", ".join(f.nombre for f in fuentes.FUENTES_PANGUI))
            return 1
        for f in elegidas:
            procesar_fuente(con, f, ahora=date.today(), confirmar=args.confirmar)
    else:
        una_pasada(con, confirmar=args.confirmar)
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
