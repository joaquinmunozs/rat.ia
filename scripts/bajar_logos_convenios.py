# -*- coding: utf-8 -*-
"""Descarga logos reales (Wikimedia Commons) para los emisores/comercios
de convenios_fuentes.py, como PNG con transparencia. Uso único / manual --
no corre en producción. Ver convenios_pangui.py y convenios_pieza.py."""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = "condor-ai-ratia/1.0 (contacto@teamcondorcl.com)"
DEST = Path(__file__).resolve().parent.parent / "assets" / "logos_convenios"
DEST.mkdir(parents=True, exist_ok=True)

# slug -> (nombre de archivo EXACTO en Commons, ya elegido a mano revisando
# los resultados de búsqueda -- no autoselección, para no traer el logo de
# otra marca por accidente).
ARCHIVOS = {
    "banco_de_chile": "File:Banco de Chile Logotipo.svg",
    "bancoestado": "File:Logo BancoEstado.svg",
    "bci": "File:Bci Logotype.svg",
    "santander": "File:Banco Santander Logotipo.svg",
    "cmr_falabella": "File:CMR Falabella-Logo.svg",
    "scotiabank": "File:Scotiabank logo.svg",
    "mcdonalds": "File:McDonald's Golden Arches.svg",
    "kfc": "File:KFC logo wordmark.svg",
    "wendys": "File:Wendy's logo 2012.svg",
    "turbus": "File:TurBus.png",
    "flixbus": "File:Flixbus Meinfernbus Logo 2016.svg",
    "farmacias_cruz_verde": "File:Logotipo Cruz Verde.svg",
    "farmacias_ahumada": "File:Farmacias Ahumada Logo.svg",
}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def imageinfo_url(titulo, ancho=500):
    q = urllib.parse.quote(titulo)
    url = (f"https://commons.wikimedia.org/w/api.php?action=query&titles={q}"
           f"&prop=imageinfo&iiprop=url|mime&iiurlwidth={ancho}&format=json")
    data = json.loads(_get(url))
    paginas = data.get("query", {}).get("pages", {})
    for pid, pag in paginas.items():
        if pid == "-1":
            return None
        info = (pag.get("imageinfo") or [None])[0]
        if not info:
            return None
        return info.get("thumburl") or info.get("url")
    return None


def main():
    ok, faltan = [], []
    for slug, titulo in ARCHIVOS.items():
        destino = DEST / f"{slug}.png"
        try:
            url = imageinfo_url(titulo)
            if not url:
                faltan.append((slug, titulo, "no encontrado en Commons"))
                continue
            datos = _get(url)
            destino.write_bytes(datos)
            ok.append((slug, len(datos)))
            print("OK  %-20s <- %s (%d bytes)" % (slug, titulo, len(datos)))
        except Exception as e:                                # noqa: BLE001
            faltan.append((slug, titulo, str(e)[:120]))
            print("ERR %-20s %s" % (slug, str(e)[:120]))
        time.sleep(1)

    print("\n%d ok, %d faltan" % (len(ok), len(faltan)))
    for slug, titulo, motivo in faltan:
        print(" - %s (%s): %s" % (slug, titulo, motivo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
