# -*- coding: utf-8 -*-
"""Rat.IA · qué páginas de panguiapp.com se vigilan, y a qué tópico de
Telegram va cada una (un tópico por emisor, pedido de Joaquín 25-ago-2026).

Todas las URLs de abajo se confirmaron en vivo el 25-ago-2026 contra el
sitemap real de panguiapp.com (`/sitemap.xml`) -- no son adivinadas.

CÓMO SE ELIGIÓ: BANCO cuando el emisor es fijo, TIENDA cuando el comercio
es fijo
------------------------------------------------------------------------------
`/bancos/{slug}` lista TODOS los convenios de un emisor, con el comercio
variando oferta por oferta -- sirve para los emisores que Joaquín nombró
(BancoEstado, Banco de Chile, BCI, Santander, Cencosud Scotiabank, Mach,
Tenpo). `/tiendas/{slug}` lista los convenios de UN comercio con el emisor
variando -- sirve para las cadenas que nombró (McDonald's, KFC, Turbus,
Flixbus, las farmacias), porque esas no tienen página de "banco" propia.

VARIABLE DE ENTORNO DEL TÓPICO, MISMO PATRÓN QUE `VIGIA_TOPICO_*`
------------------------------------------------------------------------------
Cada fuente trae el nombre de la variable de entorno con el id del tópico
de Telegram, no el id en sí -- se configura en Railway, igual que los
tópicos de ofertas/errores. Si la variable no está seteada, ver
`convenios_monitor.py`: cae al tópico general, nunca se pierde en silencio.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FuentePangui:
    nombre: str            # el emisor o comercio, para logs y para el `emisor`/`comercio` fijo
    url: str
    tipo: str               # "banco" | "tienda"
    variable_topico: str    # variable de entorno con el id del tópico de Telegram


FUENTES_PANGUI = (
    # Bancos / billeteras -- un tópico por emisor, pedido explícito.
    FuentePangui("BancoEstado", "https://panguiapp.com/bancos/banco-estado",
                "banco", "CONVENIOS_TOPICO_BANCOESTADO"),
    FuentePangui("Banco de Chile", "https://panguiapp.com/bancos/banco-de-chile",
                "banco", "CONVENIOS_TOPICO_BANCO_CHILE"),
    FuentePangui("BCI", "https://panguiapp.com/bancos/bci",
                "banco", "CONVENIOS_TOPICO_BCI"),
    FuentePangui("Santander", "https://panguiapp.com/bancos/santander",
                "banco", "CONVENIOS_TOPICO_SANTANDER"),
    FuentePangui("CMR Falabella", "https://panguiapp.com/bancos/cmr-falabella",
                "banco", "CONVENIOS_TOPICO_CMR_FALABELLA"),
    FuentePangui("Cencosud Scotiabank",
                "https://panguiapp.com/bancos/cencosud-scotiabank",
                "banco", "CONVENIOS_TOPICO_CENCOSUD"),
    FuentePangui("Mach", "https://panguiapp.com/bancos/mach",
                "banco", "CONVENIOS_TOPICO_MACH"),
    FuentePangui("Tenpo", "https://panguiapp.com/bancos/tenpo",
                "banco", "CONVENIOS_TOPICO_TENPO"),

    # Comercios -- van al tópico "Promociones directas", pedido explícito
    # para los casos sin un banco específico detrás.
    FuentePangui("McDonald's", "https://panguiapp.com/tiendas/mcdonald-s",
                "tienda", "CONVENIOS_TOPICO_DIRECTAS"),
    FuentePangui("KFC", "https://panguiapp.com/tiendas/kfc",
                "tienda", "CONVENIOS_TOPICO_DIRECTAS"),
    FuentePangui("Wendy's", "https://panguiapp.com/tiendas/wendy-s",
                "tienda", "CONVENIOS_TOPICO_DIRECTAS"),
    FuentePangui("Turbus", "https://panguiapp.com/tiendas/turbus",
                "tienda", "CONVENIOS_TOPICO_DIRECTAS"),
    FuentePangui("Flixbus", "https://panguiapp.com/tiendas/flixbus",
                "tienda", "CONVENIOS_TOPICO_DIRECTAS"),
    FuentePangui("Farmacias Cruz Verde",
                "https://panguiapp.com/tiendas/farmacias-cruz-verde",
                "tienda", "CONVENIOS_TOPICO_DIRECTAS"),
    FuentePangui("Farmacias Salcobrand",
                "https://panguiapp.com/tiendas/farmacias-salcobrand",
                "tienda", "CONVENIOS_TOPICO_DIRECTAS"),
    FuentePangui("Farmacias Ahumada",
                "https://panguiapp.com/tiendas/farmacias-ahumada",
                "tienda", "CONVENIOS_TOPICO_DIRECTAS"),
)

# (Claude, 25-ago-2026) FUERA DE PANGUI -- pedido, sin extractor propio
# TODAVÍA. Cada una necesita su propio parser: no están en el catálogo de
# Pangui, así que `convenios_pangui.py` no les sirve.
#   · Dr. Simi           -- farmaciasdoctorsimi.cl / drsimi.cl. Promo fija
#                            (25% los lunes), cambia poco: el extractor
#                            sería mucho más simple que el de Pangui.
#   · RutPay              -- es de BancoEstado pero sus beneficios propios
#                            viven en rutpay.cl, no en la página de
#                            BancoEstado en Pangui.
#   · Mercado Pago        -- mercadopago.cl/c/descuentos. Sus promos son
#                            mayormente de eventos (Cyber/Black), no
#                            alianzas puntuales -- menor prioridad.
FUENTES_PENDIENTES = ("Dr. Simi", "RutPay", "Mercado Pago")
