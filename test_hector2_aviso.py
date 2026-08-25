# -*- coding: utf-8 -*-
"""(Claude, 25-ago-2026) Lo que cambió el 25-ago en Hector2 y en el aviso.

Cubre cinco cosas que Joaquín pidió y una que apareció al medirlas:

  1. El aviso se REARMA con datos propios -- no llega el "DRank" del aliado
     ni el "sin verificar del todo".
  2. Amazon no se reenvía: no despacha a Chile.
  3. El precio histórico se muestra CON FECHA.
  4. Los tópicos se parten en 85% (Ofertas 70% / Errores de precio).
  5. Cada anuncio y cada precio observado quedan guardados.
  6. (el hallazgo) `simple.ripley.cl` tiene que reconocerse como `ripley.cl`:
     la comparación exacta de antes era la causa real de que el 100% de los
     mensajes saliera marcado "sin verificar".
"""
import os
import sqlite3
import sys
import tempfile
import time
import unittest

sys.stdout.reconfigure(encoding="utf-8")

import alertas
import baseprecios
import hector2_db
import hector2_filtro as f

DIA = 86400


class TestDominioPorSufijo(unittest.TestCase):
    """El bug que hacía que TODO saliera 'sin verificar'."""

    def test_subdominio_de_tienda_conocida_calza(self):
        self.assertEqual(f.tienda_de("simple.ripley.cl"), "ripley.cl")
        self.assertEqual(f.tienda_de("www.paris.cl"), "paris.cl")
        self.assertEqual(f.tienda_de("tienda.spdigital.cl"), "spdigital.cl")

    def test_dominio_exacto_sigue_calzando(self):
        self.assertEqual(f.tienda_de("ripley.cl"), "ripley.cl")

    def test_no_calza_por_pedazo_de_texto(self):
        # El corte es siempre en un punto: "noripley.cl" no es Ripley.
        self.assertIsNone(f.tienda_de("noripley.cl"))
        self.assertIsNone(f.tienda_de("ripley.cl.phishing.com"))

    def test_desconocida_es_none(self):
        self.assertIsNone(f.tienda_de("tiendarara.cl"))


class TestImagenesNoSonProductos(unittest.TestCase):
    def test_cdn_de_imagenes_de_ripley_no_es_el_producto(self):
        # Caso REAL de los logs de Railway: `rimage.ripley.cl` no empezaba
        # con ninguno de los prefijos viejos, se tomaba como link de
        # producto y se intentaba leer el precio de un JPG.
        urls = ["https://rimage.ripley.cl/home.ripley/Attachment/foto.jpg",
                "https://simple.ripley.cl/producto/notebook-hp-123"]
        tienda, url, _rubro = f.detectar_producto(urls)
        self.assertEqual(tienda, "ripley.cl")
        self.assertIn("/producto/", url)

    def test_imagen_del_aliado_se_ignora(self):
        urls = ["https://img2.ofertasshark.cl/AbC123",
                "https://www.falabella.com/falabella-cl/product/999/x"]
        tienda, url, _r = f.detectar_producto(urls)
        self.assertEqual(tienda, "falabella.com")

    def test_por_extension_aunque_el_host_sea_raro(self):
        urls = ["https://cosas.example.com/foto.webp",
                "https://www.paris.cl/producto-x.html"]
        tienda, _url, _r = f.detectar_producto(urls)
        self.assertEqual(tienda, "paris.cl")


class TestAmazon(unittest.TestCase):
    def test_amazon_se_descarta(self):
        for dom in ("amazon.com", "www.amazon.es", "amazon.cl", "amazon.com.mx"):
            self.assertTrue(f.esta_bloqueada(dom), dom)

    def test_no_bloquea_por_parecerse(self):
        self.assertFalse(f.esta_bloqueada("amazonas.cl"))
        self.assertFalse(f.esta_bloqueada("miamazon.example.com"))

    def test_mensaje_de_amazon_se_descarta_entero(self):
        texto = ('🔥 DRank Amazon Audífonos Sony\n$100.000 -> $20.000 (80%)\n'
                 '<a href="https://www.amazon.com/dp/B0ABC">PRODUCTO</a>')
        r = f.evaluar_mensaje(texto, "canal1", con_hector=None,
                              verificar_vivo=False)
        self.assertEqual(r["veredicto"], "descartado")
        self.assertIn("Amazon", r["motivo"])

    def test_se_puede_reactivar_por_variable(self):
        os.environ["HECTOR2_PERMITIR_AMAZON"] = "1"
        try:
            self.assertFalse(f.esta_bloqueada("amazon.com"))
        finally:
            del os.environ["HECTOR2_PERMITIR_AMAZON"]


class TestNombreSinRank(unittest.TestCase):
    def test_saca_el_drank(self):
        texto = "🔥 DRank  spdigital  Notebook Lenovo IdeaPad 3 🔍\n$500.000"
        self.assertNotIn("DRank", f.nombre_declarado(texto) or "")
        self.assertIn("Notebook Lenovo", f.nombre_declarado(texto))

    def test_saca_cualquier_rank(self):
        for r in ("SRank", "ARank", "BRank", "CRank", "drank"):
            texto = "%s falabella Zapatillas Nike Air\n$50.000" % r
            self.assertNotIn(r.lower(),
                             (f.nombre_declarado(texto) or "").lower())

    def test_no_devuelve_la_linea_de_precios(self):
        texto = "$1.000 -> $100 (90%)\nParlante JBL Charge 5 portatil"
        self.assertIn("Parlante", f.nombre_declarado(texto))

    def test_el_rank_detras_del_ancla_de_la_miniatura(self):
        # REGRESIÓN: el mensaje real arranca con un <a> que envuelve la
        # miniatura. Al sacar las etiquetas, su texto de ancla queda DELANTE
        # del rank, y un patrón anclado a "^" dejaba pasar el "DRank" entero
        # hasta el canal. Se detectó reconstruyendo el mensaje tal como llega
        # de Telethon, no leyendo el código.
        texto = ('<a href="https://rimage.ripley.cl/x/foto.jpg">​</a>'
                 '\U0001F525 DRank  Ripley  Notebook HP 15-fa123 \U0001F50D\n'
                 '$899.990 -> $89.990 (90,0%)')
        nombre = f.nombre_declarado(texto, "ripley.cl")
        self.assertNotIn("rank", nombre.lower())
        self.assertTrue(nombre.startswith("Notebook HP"), nombre)

    def test_no_repite_el_nombre_del_comercio(self):
        texto = "SRank  Ripley  Notebook HP 15-fa123 Ryzen"
        self.assertTrue(
            f.nombre_declarado(texto, "ripley.cl").startswith("Notebook"))


class TestPrecioHistoricoConFecha(unittest.TestCase):
    def test_el_aviso_muestra_la_fecha_de_cada_precio(self):
        ahora = int(time.time())
        det = {
            "url": "https://www.paris.cl/x",
            "nombre": "Notebook Acer Aspire 5",
            "precio": 200_000,
            "referencia": 800_000,
            "caida": 0.75,
            "con_historial": True,
            "historico": [800_000, 750_000],
            "historico_fechas": [(800_000, ahora - 3 * DIA),
                                 (750_000, ahora - 20 * DIA)],
            "habitual": None,
        }
        texto = alertas.armar_texto(det, "paris.cl")
        self.assertIn("Precio histórico", texto)
        self.assertIn(time.strftime("%d/%m", time.localtime(ahora - 3 * DIA)),
                      texto)
        self.assertIn(time.strftime("%d/%m", time.localtime(ahora - 20 * DIA)),
                      texto)
        self.assertIn("sondeo propio", texto)
        # Lo esencial que pidió Joaquín, todo junto:
        self.assertIn("paris.cl", texto)                 # el comercio
        self.assertIn("Notebook Acer Aspire 5", texto)   # el producto
        self.assertIn("$200.000", texto)                 # el precio actual
        self.assertIn("https://www.paris.cl/x", texto)   # el link

    def test_sin_fechas_sigue_funcionando_como_antes(self):
        det = {"url": "u", "nombre": "n", "precio": 100, "referencia": 1000,
               "caida": 0.9, "con_historial": True, "historico": [1000],
               "habitual": None}
        texto = alertas.armar_texto(det, "t")
        self.assertIn("$1.000", texto)


class TestTopicosPartidosEn85(unittest.TestCase):
    def setUp(self):
        self.previas = {k: os.environ.get(k) for k in (
            "VIGIA_TOPICO_ERRORES", "VIGIA_TOPICO_ERRORES_GRAVES",
            "VIGIA_TOPICO_OFERTAS70", "VIGIA_TOPICO_OFERTAS")}
        os.environ["VIGIA_TOPICO_ERRORES"] = "2"
        os.environ["VIGIA_TOPICO_ERRORES_GRAVES"] = "900"
        os.environ["VIGIA_TOPICO_OFERTAS70"] = "2"
        os.environ["VIGIA_TOPICO_OFERTAS"] = "4"

    def tearDown(self):
        for k, v in self.previas.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _destino(self, caida):
        det = {"tipo": baseprecios.ERROR if caida >= baseprecios.UMBRAL_ERROR
               else baseprecios.OFERTA,
               "caida": caida, "categoria": None}
        return alertas.destinos(det)

    def test_85_o_mas_va_a_errores_de_precio(self):
        self.assertIn("900", self._destino(0.93))
        self.assertIn("900", self._destino(0.85))

    def test_entre_70_y_85_va_a_ofertas_70(self):
        self.assertIn("2", self._destino(0.72))
        self.assertIn("2", self._destino(0.849))
        self.assertNotIn("900", self._destino(0.84))

    def test_bajo_70_no_cambia(self):
        self.assertIn("4", self._destino(0.55))

    def test_sin_la_variable_nueva_se_comporta_como_antes(self):
        # Mientras el tópico nuevo no exista en Railway, nada se pierde:
        # todo lo de 70%+ sigue cayendo en el tópico de siempre.
        del os.environ["VIGIA_TOPICO_ERRORES_GRAVES"]
        del os.environ["VIGIA_TOPICO_OFERTAS70"]
        self.assertIn("2", self._destino(0.93))
        self.assertIn("2", self._destino(0.72))


class TestArchivoDeAnuncios(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.con = hector2_db.abrir(self.tmp.name)

    def tearDown(self):
        self.con.close()
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_guarda_el_anuncio_completo(self):
        ahora = int(time.time())
        hector2_db.registrar_anuncio(
            self.con, origen="aliado", canal="-100123", tienda="ripley.cl",
            url="https://simple.ripley.cl/p/1", nombre="Notebook HP",
            precio=99_990, referencia=499_990, caida=0.80,
            caida_declarada=0.92,
            historico=[(499_990, ahora - 5 * DIA)], veredicto="confirmado",
            topico="2", enviado=True, texto="<b>Notebook HP</b>")
        fila = self.con.execute("SELECT * FROM anuncios").fetchone()
        self.assertEqual(fila["origen"], "aliado")
        self.assertEqual(fila["precio"], 99_990)
        self.assertEqual(fila["referencia"], 499_990)
        # La caída declarada por el aliado se guarda aparte de la real: es
        # exactamente la comparación que permite auditarlo con el tiempo.
        self.assertAlmostEqual(fila["caida"], 0.80)
        self.assertAlmostEqual(fila["caida_declarada"], 0.92)
        self.assertIn("499990", fila["historico"])

    def test_precios_vistos_construye_la_historica(self):
        ahora = int(time.time())
        u = "https://tiendarara.cl/p/1"
        hector2_db.registrar_precio_visto(self.con, u, 10_000,
                                          "declarado_aliado", visto_en=ahora - DIA)
        hector2_db.registrar_precio_visto(self.con, u, 8_000,
                                          "declarado_aliado", visto_en=ahora)
        hist = hector2_db.historico_propio(self.con, u)
        self.assertEqual([p for p, _ in hist], [8_000, 10_000])

    def test_el_mismo_hallazgo_en_tres_canales_no_duplica(self):
        ahora = int(time.time())
        u = "https://tiendarara.cl/p/2"
        for _ in range(3):
            hector2_db.registrar_precio_visto(self.con, u, 5_000,
                                              "declarado_aliado", visto_en=ahora)
        n = self.con.execute(
            "SELECT COUNT(*) AS n FROM precios_vistos WHERE url=?", (u,)
        ).fetchone()["n"]
        self.assertEqual(n, 1)

    def test_tiendas_fuera_del_catalogo_igual_acumulan_historia(self):
        # El punto del ejercicio: una tienda que Héctor no vigila nunca va a
        # tener historial en `precios`, pero acá sí lo junta sola.
        ahora = int(time.time())
        u = "https://noestaenhector.cl/p/9"
        for i, precio in enumerate((30_000, 25_000, 12_000)):
            hector2_db.registrar_precio_visto(
                self.con, u, precio, "declarado_aliado",
                visto_en=ahora - (3 - i) * DIA)
        self.assertEqual(len(hector2_db.historico_propio(self.con, u)), 3)


class TestElPrecioDeHoyNoEsSuPropiaReferencia(unittest.TestCase):
    """La trampa del orden: en `_al_llegar` la observación se guarda ANTES de
    armar el aviso, así que `historico_propio` ya devuelve el precio de hoy.
    Si ese valor entrara en la referencia, la caída daría 0% -- el mismo error
    que `baseprecios.evaluar` evita con su "llamar SIEMPRE antes de guardar".
    """

    def setUp(self):
        import reenviar_ofertas
        self.R = reenviar_ofertas
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.con = hector2_db.abrir(self.tmp.name)

    def tearDown(self):
        self.con.close()
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_no_se_referencia_a_si_mismo(self):
        u = "https://tiendarara.cl/p/7"
        ahora = int(time.time())
        hector2_db.registrar_precio_visto(self.con, u, 20_000,
                                          "declarado_aliado", visto_en=ahora - 9 * DIA)
        # Lo que hace el handler justo antes de armar el aviso:
        hector2_db.registrar_precio_visto(self.con, u, 5_000,
                                          "declarado_aliado", visto_en=ahora)
        r = {"url": u, "nombre": "Cosa", "tienda": None,
             "precio_declarado": 5_000, "precio_real": None,
             "referencia": None, "referencia_declarada": 99_999,
             "caida_real": None, "historico": []}
        _texto, caida, precio, referencia, _h = self.R._armar_aviso(r, self.con)
        self.assertEqual(precio, 5_000)
        # Gana la observación propia de $20.000, no el $99.999 del aliado
        # ni el propio $5.000 recién guardado.
        self.assertEqual(referencia, 20_000)
        self.assertAlmostEqual(caida, 0.75)

    def test_sin_sondeo_propio_lo_dice_en_el_mensaje(self):
        r = {"url": "https://tiendarara.cl/p/8", "nombre": "Otra cosa",
             "tienda": None, "precio_declarado": 5_000, "precio_real": None,
             "referencia": None, "referencia_declarada": 20_000,
             "caida_real": None, "historico": []}
        texto, _c, _p, ref, _h = self.R._armar_aviso(r, self.con)
        self.assertEqual(ref, 20_000)
        self.assertIn("declarada por la fuente", texto)


class TestBaseEnDiscoPersistente(unittest.TestCase):
    def test_usa_el_volumen_de_railway_si_existe(self):
        with tempfile.TemporaryDirectory() as d:
            previo_db = os.environ.pop("HECTOR2_DB", None)
            previo_vol = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
            os.environ["RAILWAY_VOLUME_MOUNT_PATH"] = d
            try:
                self.assertEqual(hector2_db._ruta_por_defecto(),
                                 os.path.join(d, "hector2.db"))
            finally:
                if previo_db is not None:
                    os.environ["HECTOR2_DB"] = previo_db
                if previo_vol is None:
                    os.environ.pop("RAILWAY_VOLUME_MOUNT_PATH", None)
                else:
                    os.environ["RAILWAY_VOLUME_MOUNT_PATH"] = previo_vol

    def test_hector2_db_explicita_manda(self):
        previo = os.environ.get("HECTOR2_DB")
        os.environ["HECTOR2_DB"] = "/tmp/elegida.db"
        try:
            self.assertEqual(hector2_db._ruta_por_defecto(), "/tmp/elegida.db")
        finally:
            if previo is None:
                os.environ.pop("HECTOR2_DB", None)
            else:
                os.environ["HECTOR2_DB"] = previo


class TestAlertasGuardaElTexto(unittest.TestCase):
    def test_anotar_alerta_archiva_nombre_topico_y_texto(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        previo = os.environ.get("VIGIA_DB")
        os.environ["VIGIA_DB"] = tmp.name
        try:
            import importlib
            importlib.reload(baseprecios)
            con = baseprecios.abrir()
            det = {"url": "https://www.paris.cl/x", "tipo": baseprecios.ERROR,
                   "precio": 1_000, "referencia": 10_000, "caida": 0.9,
                   "nombre": "Parlante JBL",
                   "historico_fechas": [(10_000, 1_700_000_000)]}
            baseprecios.anotar_alerta(con, det, tienda="paris.cl", topico="900",
                                       texto="<b>Parlante JBL</b>")
            con.commit()
            fila = con.execute("SELECT * FROM alertas").fetchone()
            self.assertEqual(fila["nombre"], "Parlante JBL")
            self.assertEqual(fila["tienda"], "paris.cl")
            self.assertEqual(fila["topico"], "900")
            self.assertIn("JBL", fila["texto"])
            self.assertIn("10000", fila["historico"])
            con.close()
        finally:
            if previo is None:
                os.environ.pop("VIGIA_DB", None)
            else:
                os.environ["VIGIA_DB"] = previo
            import importlib
            importlib.reload(baseprecios)
            try:
                os.unlink(tmp.name)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main(verbosity=1)
