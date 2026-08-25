# -*- coding: utf-8 -*-
"""Rat.IA · cuándo un convenio banco-comercio se publica, recuerda, o
avisa que se acaba — en Telegram y en Instagram, con reglas DISTINTAS.

LA DECISIÓN DE JOAQUÍN (25-ago-2026), Y POR QUÉ LOS DOS CANALES SE TRATAN
DISTINTO
------------------------------------------------------------------------------
Pidió: "si duran más de 1 semana deben ir publicándose semanalmente hasta
el fin de la vigencia". Eso tiene sentido pleno en Telegram —es un canal
de avisos, quien sigue el tópico de un banco quiere el recordatorio— pero
repetir la MISMA pieza cada semana en Instagram cuesta alcance real:
Instagram penaliza el contenido repetido y la audiencia silencia cuentas
que insisten con lo mismo.

Se le presentó la alternativa a Joaquín y la aprobó explícitamente:

    TELEGRAM   -- recuerda cada 7 días (o cada 30 si el convenio es
                  recurrente sin fecha de término) hasta que vence.
    INSTAGRAM  -- publica UNA vez al detectarlo. Si dura semanas, sólo
                  vuelve a aparecer en su ÚLTIMA SEMANA antes de vencer,
                  con un aviso de urgencia real ("¡última semana!"), nunca
                  la misma pieza repetida.

QUÉ ES "IMPORTANTE" PARA INSTAGRAM
------------------------------------------------------------------------------
Joaquín pidió explícito "alianzas realmente importantes... descuentos
grandes", no cualquier promo de 5%. La vara: descuento ≥30% Y (una marca
reconocida de las que nombró, o el propio "Verificado hoy" de Pangui como
señal de que el dato es fresco). Telegram no tiene ese filtro -- ahí entra
todo lo que se detecta, es un canal de avisos por tópico, no una vitrina.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

Accion = Literal[
    "telegram_nuevo", "telegram_recordatorio", "telegram_ultima_vez",
    "instagram_nuevo", "instagram_ultima_semana",
]

UMBRAL_DESCUENTO_IG = 30
RECORDATORIO_TELEGRAM_DIAS = 7
RECORDATORIO_TELEGRAM_RECURRENTE_DIAS = 30
VENTANA_ULTIMA_SEMANA_DIAS = 7

# ── TOPES POR PASADA, Y POR QUÉ NO SON OPCIONALES ────────────────────────
#
# El primer ensayo real contra las 16 páginas devolvió **1.347 convenios**
# con acción pendiente. Sin tope, la primera corrida con `--confirmar`
# habría mandado 1.347 mensajes de golpe a Telegram: el grupo silenciado
# en minutos, y Telegram cortando por límite de envíos mucho antes de
# terminar.
#
# No es un caso de borde: es el arranque NORMAL de un monitor que ve todo
# el catálogo por primera vez y lo considera "nuevo". El goteo también
# resuelve el arranque en frío -- el resto no se pierde, entra en las
# pasadas siguientes, priorizado por descuento.
TOPE_TELEGRAM_POR_PASADA = 25
TOPE_INSTAGRAM_POR_DIA = 2

# Las marcas/comercios que Joaquín nombró explícitamente como el objetivo
# ("alianzas realmente importantes"). Un convenio de una marca de esta
# lista basta con el piso de 30% para calificar; una marca fuera de la
# lista necesita además el "Verificado hoy" de Pangui como segunda señal
# de que vale la pena publicarlo sin ojos humanos encima.
MARCAS_IMPORTANTES = {
    "mcdonald's", "mcdonalds", "kfc", "wendy's", "wendys", "copec", "shell",
    "dr. simi", "dr simi", "rappi", "turbus", "flixbus",
    "farmacias cruz verde", "cruz verde", "salcobrand", "farmacias ahumada",
}


@dataclass
class EstadoConvenio:
    """Lo que ya se sabe de este convenio de pasadas anteriores -- viene de
    la tabla `convenios` en hector2_db. `None` en cualquier campo de fecha
    significa "todavía no se hizo esa acción nunca"."""
    primera_vista: date
    ultimo_recordatorio_telegram: date | None = None
    publicado_en_instagram: bool = False
    aviso_ultima_semana_ig_enviado: bool = False


def importa_para_instagram(descuento: int, comercio: str,
                           verificado_recientemente: bool) -> bool:
    if descuento < UMBRAL_DESCUENTO_IG:
        return False
    if comercio.strip().lower() in MARCAS_IMPORTANTES:
        return True
    return verificado_recientemente


def _en_ultima_semana(vigencia_hasta: date | None, ahora: date) -> bool:
    if not vigencia_hasta:
        return False
    return 0 <= (vigencia_hasta - ahora).days <= VENTANA_ULTIMA_SEMANA_DIAS


def _vencido(vigencia_hasta: date | None, ahora: date) -> bool:
    return bool(vigencia_hasta and vigencia_hasta < ahora)


def decidir_acciones(*, es_nuevo: bool, descuento: int, comercio: str,
                     verificado_recientemente: bool,
                     vigencia_hasta: date | None, es_recurrente: bool,
                     estado: EstadoConvenio, ahora: date) -> list[Accion]:
    """Qué hacer con este convenio EN ESTA PASADA. Puede ser más de una
    acción (ej. un convenio nuevo que además ya nace en su última semana),
    o ninguna (ya se avisó todo lo que correspondía, o venció)."""
    if _vencido(vigencia_hasta, ahora):
        return []

    acciones: list[Accion] = []

    if es_nuevo:
        acciones.append("telegram_nuevo")
        if importa_para_instagram(descuento, comercio, verificado_recientemente):
            acciones.append("instagram_nuevo")
        # Un convenio puede detectarse por primera vez ya sobre el final de
        # su vigencia (por ejemplo, si el monitor arranca a mitad de
        # camino) -- en ese caso el aviso de Instagram de "nuevo" y el de
        # "última semana" serían literalmente el mismo momento, así que NO
        # se duplica: el de arriba ya cubre esa publicación.
        return acciones

    # Ya se conocía. ¿Toca recordatorio de Telegram?
    paso_desde_recordatorio = RECORDATORIO_TELEGRAM_RECURRENTE_DIAS if es_recurrente \
        else RECORDATORIO_TELEGRAM_DIAS
    ultimo = estado.ultimo_recordatorio_telegram or estado.primera_vista
    if (ahora - ultimo).days >= paso_desde_recordatorio:
        if _en_ultima_semana(vigencia_hasta, ahora):
            acciones.append("telegram_ultima_vez")
        else:
            acciones.append("telegram_recordatorio")

    # ¿Toca el aviso de "última semana" en Instagram? Sólo si esta pieza
    # importaba lo suficiente para haber salido en Instagram alguna vez, y
    # sólo una vez por convenio -- nunca cada semana de la última semana.
    if (estado.publicado_en_instagram and not estado.aviso_ultima_semana_ig_enviado
            and _en_ultima_semana(vigencia_hasta, ahora)):
        acciones.append("instagram_ultima_semana")

    return acciones


def aplicar_topes(pendientes, ya_publicados_ig_hoy: int = 0):
    """De todo lo que tiene acción pendiente, qué se ejecuta EN ESTA PASADA.

    `pendientes` es [(convenio, [acciones]), ...] tal como lo arma el
    monitor. Devuelve la misma forma, recortada y priorizada:

      · Instagram: máximo `TOPE_INSTAGRAM_POR_DIA` al día, los de MAYOR
        descuento primero -- es una vitrina, entra lo mejor.
      · Telegram: máximo `TOPE_TELEGRAM_POR_PASADA`, también por descuento.
        Lo que no entra no se pierde: como no se marca en la base, la
        pasada siguiente lo vuelve a considerar.

    Se prioriza por descuento y no por orden de llegada a propósito: en el
    arranque en frío, "orden de llegada" es simplemente el orden del
    catálogo, que no significa nada para quien lee el canal.
    """
    ordenados = sorted(pendientes, key=lambda p: -p[0].descuento)

    cupo_ig = max(0, TOPE_INSTAGRAM_POR_DIA - ya_publicados_ig_hoy)
    enviados_tg = 0
    salida = []

    for conv, acciones in ordenados:
        acciones_ig = [a for a in acciones if a.startswith("instagram_")]
        acciones_tg = [a for a in acciones if a.startswith("telegram_")]

        permitidas = []
        if acciones_ig and cupo_ig > 0:
            permitidas += acciones_ig
            cupo_ig -= 1
        if acciones_tg and enviados_tg < TOPE_TELEGRAM_POR_PASADA:
            permitidas += acciones_tg
            enviados_tg += 1

        if permitidas:
            salida.append((conv, permitidas))
    return salida
