# -*- coding: utf-8 -*-
"""Trae la base de precios REAL de Héctor para que Hector2 pueda cruzar contra
ella, en vez de creerle al "antes" que declara el aliado.

DE DÓNDE SALE
------------------------------------------------------------------------------
`hector.yml` sube `precios.db` consolidada como Release de GitHub
(`respaldo-base`, ver el paso "Respaldo diario persistente"), no solo como
artifact de Actions -- los artifacts expiran a los 2 días y no son
descargables sin token; el Release es público y permanente. Rat.IA (`rat.ia`)
es un repo público a propósito, así que el asset se baja con una GET plana,
sin autenticación.

NO SE ESCRIBE NUNCA
------------------------------------------------------------------------------
Esta es una copia de SOLO LECTURA para cruzar precios. Se abre siempre con
`file:...?mode=ro` (ver hector2_filtro.abrir_solo_lectura) -- ni por accidente
un bug acá podría corromper el historial real de Héctor, porque ni siquiera
tiene el permiso del sistema operativo para escribir en el archivo.
"""
import os
import time
import urllib.request

REPO = os.environ.get("HECTOR2_REPO_BASE", "joaquinmunozs/rat.ia")
TAG = "respaldo-base"
ASSET = "precios.db"
URL = "https://github.com/%s/releases/download/%s/%s" % (REPO, TAG, ASSET)

RUTA_LOCAL = os.environ.get("HECTOR2_BASE_HECTOR", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "precios-hector-solo-lectura.db"))

# Cada cuánto se refresca. El respaldo de Héctor se actualiza una vez al día
# (el primer `schedule` del día); refrescar cada 4h alcanza de sobra y no le
# pega a GitHub por nada -- son ~40 MB una vez cada 4h, no por mensaje.
INTERVALO_SEG = int(os.environ.get("HECTOR2_REFRESCO_SEG", 4 * 3600))


def hace_falta_refrescar(ruta=RUTA_LOCAL, intervalo=INTERVALO_SEG):
    if not os.path.exists(ruta):
        return True
    return (time.time() - os.path.getmtime(ruta)) >= intervalo


def descargar(ruta=RUTA_LOCAL, url=URL, tiempo=120):
    """Baja a un archivo temporal y recién al final reemplaza el definitivo --
    si se corta a mitad de descarga, la copia vieja (que sí sirve) no queda
    pisada por un archivo a medio escribir."""
    tmp = ruta + ".tmp"
    req = urllib.request.Request(url, headers={"User-Agent": "hector2-vigia-precios"})
    with urllib.request.urlopen(req, timeout=tiempo) as r, open(tmp, "wb") as f:
        while True:
            bloque = r.read(1024 * 256)
            if not bloque:
                break
            f.write(bloque)
    os.replace(tmp, ruta)
    return ruta


def asegurar(ruta=RUTA_LOCAL, forzar=False):
    """Descarga solo si hace falta. Devuelve (ruta, se_descargo). Si la
    descarga falla y ya había una copia previa, se seguía usando ESA -- una
    base un día vieja sigue siendo mucho mejor que no tener con qué cruzar."""
    if not forzar and not hace_falta_refrescar(ruta):
        return ruta, False
    try:
        descargar(ruta)
        return ruta, True
    except Exception as e:                                   # noqa: BLE001
        if os.path.exists(ruta):
            print("[descargar_base_hector] no se pudo refrescar (%s); "
                  "se sigue usando la copia existente" % str(e)[:150])
            return ruta, False
        print("[descargar_base_hector] no hay base de Héctor y la descarga "
              "falló (%s): Hector2 corre sin cruce hasta la próxima" % str(e)[:150])
        return None, False


if __name__ == "__main__":
    ruta, nueva = asegurar(forzar=True)
    print("base de Héctor en %s (recién descargada: %s)" % (ruta, nueva))
