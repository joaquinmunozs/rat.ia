# -*- coding: utf-8 -*-
"""Rat.IA · una pasada del selector de Instagram.

QUÉ HACE, EN ORDEN
==============================================================================
  1. Lee lo que se avisó en el Telegram de Rat.IA en las últimas horas —
     los hallazgos propios de Héctor (`alertas` en precios.db) y los
     reenvíos verificados del aliado (`anuncios` en hector2.db).
  2. Registra cada uno como candidato la PRIMERA vez que lo ve (si ya
     estaba, no lo toca — ver `hector2_db.registrar_candidato`).
  3. Vence los candidatos que se pasaron de su ventana sin publicarse.
  4. De los que siguen pendientes, filtra los que califican para Instagram
     (`ratia_seleccion.evaluar_candidatos`) y decide cuáles se publican EN
     ESTA PASADA (`ratia_seleccion.listos_para_publicar`).
  5. Para cada uno: arma la pieza y el caption (`ratia_publicar`).

CÓMO SE CORRE
==============================================================================
    python ratia_ig_selector.py              # una pasada, sin publicar
    python ratia_ig_selector.py --confirmar  # una pasada, publica de verdad

Pensado para correr cada 10-15 min (cron de Railway, GitHub Actions, o un
`asyncio` loop igual al de `reenviar_ofertas.py` — todavía no está enganchado
a ninguno de los dos; ver el estado en la bitácora del 25-ago).

⚠️ NO PUBLICA SOLO POR DEFECTO
==============================================================================
Mismo principio que `ratia_publicar.publicar_oferta`: sin `--confirmar`, esta
pasada arma todo y lo deja marcado como listo, pero no llama a Blotato. Un
selector automático que publica solo, sin que nadie lo haya visto andar en
producción al menos una vez, es exactamente el tipo de incidente que ya se
evitó una vez con esa misma regla.

QUÉ FALTA PARA QUE PUBLIQUE DE VERDAD
==============================================================================
  · BLOTATO_API_KEY + la cuenta de Instagram de Rat.IA conectada en Blotato.
  · KIE_API_KEY (ya la usa Bárbara; se puede reusar la misma cuenta).
  · La foto real del producto -- hoy `foto` llega vacía porque nada en el
    pipeline guarda la URL de imagen junto con el candidato. Se resuelve
    bajando `og:image` de la ficha (`descubrir.bajar` + el mismo patrón que
    ya usa `hector2_filtro.imagen_de`), pendiente de conectar acá.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import baseprecios
import descargar_base_hector
import hector2_db
import hector2_filtro
import ratia_publicar
import ratia_seleccion as sel

LOOKBACK_SEG = 8 * 60 * 60  # cuánto atrás mirar el Telegram cada pasada


def _candidatos_crudos(con_precios, con_h2, ahora):
    desde = ahora - LOOKBACK_SEG
    return (baseprecios.alertas_recientes(con_precios, desde)
            + hector2_db.anuncios_recientes(con_h2, desde))


def registrar_nuevos(con_h2, filas, ahora):
    for f in filas:
        if not f.get("url") or not f.get("precio"):
            continue
        hector2_db.registrar_candidato(
            con_h2, url=f["url"], tipo=sel.clasificar(float(f.get("caida") or 0)),
            fuente=f.get("fuente", ""), tienda=f.get("tienda"),
            nombre=f.get("nombre"), precio=f.get("precio"),
            referencia=f.get("referencia"), caida=f.get("caida"),
            primera_vez_vista=f["primera_vez_vista"], ahora=ahora)


def una_pasada(con_precios, con_h2, confirmar=False, ahora=None, log=print):
    ahora = ahora if ahora is not None else time.time()

    crudos = _candidatos_crudos(con_precios, con_h2, ahora)
    registrar_nuevos(con_h2, crudos, ahora)
    hector2_db.vencer_candidatos(
        con_h2, ahora, sel.VENCE_OFERTA_SEG, sel.VENCE_ERROR_SEG)

    pendientes = hector2_db.candidatos_pendientes(con_h2, ahora - LOOKBACK_SEG)
    calificados = sel.evaluar_candidatos(pendientes, ahora=ahora)

    medianoche = sel.medianoche_chile_epoch(ahora)
    hoy = hector2_db.publicados_hoy(con_h2, medianoche)

    listos = sel.listos_para_publicar(calificados, ahora, hoy)
    if not listos:
        log("[ratia-ig] nada listo para publicar en esta pasada "
            "(%d candidatos pendientes, %d calificados)."
            % (len(pendientes), len(calificados)))
        return []

    resultados = []
    for c in listos:
        log("[ratia-ig] %s | %s | -%.0f%% | %s (%s)" % (
            c.tipo.upper(), c.tienda, c.caida * 100, c.nombre, c.url))
        r = ratia_publicar.publicar_oferta(
            nombre_producto=c.nombre or "", precio_antes=c.referencia,
            precio_ahora=c.precio, foto=_foto_de(c),
            cuenta_id=os.environ.get("RATIA_IG_CUENTA_ID", ""),
            tienda=c.tienda or "", tipo=c.tipo,
            confirmado=confirmar, log=log)
        resultados.append((c, r))
        if r.get("ok") and (confirmar and r.get("publicado")):
            hector2_db.marcar_publicado(
                con_h2, c.url, c.tipo,
                post_id=(r.get("submission") or {}).get("id"), ahora=ahora)
        elif not r.get("ok"):
            hector2_db.marcar_descartado(
                con_h2, c.url, c.tipo, r.get("motivo", "error desconocido"))
    return resultados


def _foto_de(c: sel.Candidato) -> str:
    """La URL de la foto real del producto, para pegarla en la pieza.

    (Claude, 25-ago-2026) TODAVÍA NO HAY UNA FUENTE CONECTADA -- ni `alertas`
    ni `anuncios` guardan la imagen junto con el candidato. Se puede resolver
    bajando la ficha (`descubrir.bajar(c.url)`) y leyendo `og:image`, mismo
    patrón que ya prueba `test_hector2_aviso` para los reenvíos del aliado.
    Queda explícito como pendiente en vez de hacerlo a medias: sin foto real,
    `ratia_pieza_ia.generar_pieza` ya se niega sola a inventar una."""
    return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--confirmar", action="store_true",
                    help="Publica de verdad. Sin esto, sólo arma y loguea.")
    args = ap.parse_args()

    # De solo lectura y a propósito: este selector nunca escribe en la base
    # de Héctor, sólo lee `alertas`. Usa la misma copia de respaldo que ya
    # descarga `reenviar_ofertas.py` -- así corre igual en este PC (donde
    # además existe la base viva) que dentro de Railway (donde sólo existe
    # esta copia).
    ruta_precios, _ = descargar_base_hector.asegurar()
    con_precios = hector2_filtro.abrir_solo_lectura(ruta_precios)
    con_h2 = hector2_db.abrir()

    resultados = una_pasada(con_precios, con_h2, confirmar=args.confirmar)
    con_precios.close()
    con_h2.close()
    return 0 if resultados is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
