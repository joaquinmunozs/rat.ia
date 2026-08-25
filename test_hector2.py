# -*- coding: utf-8 -*-
"""Pruebas de Hector2: el filtro (hector2_filtro.py) y su base (hector2_db.py).

Corre con `python -m unittest test_hector2.py -v`. Sin red y sin depender de
mensajes reales del aliado -- los casos de red (verificar_en_vivo) usan
funciones inyectadas, nunca `descubrir.bajar` de verdad.
"""
import os
import sqlite3
import tempfile
import time
import unittest

import baseprecios
import hector2_db
import hector2_filtro as f


# ── extraer_urls / detectar_producto ───────────────────────────────────────

class TestDeteccionProducto(unittest.TestCase):
    def test_extrae_todos_los_href(self):
        texto = '<a href="https://a.cl/1">x</a> otro <a href="https://b.cl/2">y</a>'
        self.assertEqual(f.extraer_urls(texto), ["https://a.cl/1", "https://b.cl/2"])

    def test_prefiere_tienda_conocida_de_hector(self):
        texto = ('<a href="https://img2.ofertasshark.cl/xyz.jpg">foto</a> '
                 '<a href="https://www.paris.cl/producto/123">ver</a>')
        tienda, url, rubro = f.detectar_producto(f.extraer_urls(texto))
        self.assertEqual(tienda, "paris.cl")
        self.assertIn("paris.cl", url)
        self.assertEqual(rubro, "retail")

    def test_sin_tienda_conocida_usa_el_primer_link_no_imagen(self):
        texto = ('<a href="https://img.ofertasshark.cl/xyz.jpg">foto</a> '
                 '<a href="https://tienda-random.cl/producto/9">ver</a>')
        tienda, url, rubro = f.detectar_producto(f.extraer_urls(texto))
        self.assertIsNone(tienda)
        self.assertIn("tienda-random.cl", url)

    def test_sin_ningun_link_util_devuelve_none(self):
        texto = '<a href="https://img.ofertasshark.cl/xyz.jpg">foto</a>'
        tienda, url, rubro = f.detectar_producto(f.extraer_urls(texto))
        self.assertIsNone(url)


class TestExtraccionNumeros(unittest.TestCase):
    def test_porcentaje_un_decimal(self):
        self.assertAlmostEqual(f.extraer_porcentaje("bajó (98,9%)"), 0.989)

    def test_porcentaje_dos_decimales_coma(self):
        # El bug real que ya mordió a reenviar_ofertas.py: el aliado a veces
        # manda dos decimales.
        self.assertAlmostEqual(f.extraer_porcentaje("(95,38%)"), 0.9538)

    def test_porcentaje_dos_decimales_punto(self):
        self.assertAlmostEqual(f.extraer_porcentaje("(39.34%)"), 0.3934)

    def test_sin_porcentaje_da_none(self):
        self.assertIsNone(f.extraer_porcentaje("sin numeros aca"))

    def test_precio_con_puntos_de_miles(self):
        self.assertEqual(f.extraer_precios("antes $237.990 ahora $89.990"),
                          [237990, 89990])

    def test_precio_sin_signo_no_se_confunde(self):
        self.assertEqual(f.extraer_precios("stock: 12 unidades"), [])


class TestRuido(unittest.TestCase):
    def test_tienda_de_libros_es_irrelevante(self):
        ok, motivo = f.es_irrelevante("Cien Años de Soledad -50%", "libros")
        self.assertTrue(ok)

    def test_libro_por_nombre_aunque_la_tienda_no_se_conozca(self):
        ok, motivo = f.es_irrelevante("Libro Los 7 Habitos de la Gente Altamente Efectiva", None)
        self.assertTrue(ok)

    def test_giftcard_es_irrelevante(self):
        ok, _ = f.es_irrelevante("Gift Card Steam 20 USD -30%", None)
        self.assertTrue(ok)

    def test_accesorio_barato_es_irrelevante(self):
        ok, motivo = f.es_irrelevante("Funda de silicona para iPhone 15 -70%", None)
        self.assertTrue(ok)
        self.assertIn("accesorio", motivo)

    def test_producto_normal_no_es_irrelevante(self):
        ok, _ = f.es_irrelevante("Notebook Lenovo IdeaPad 15.6\" -55%", None)
        self.assertFalse(ok)

    def test_seguro_de_vidrio_no_es_seguro_financiero(self):
        # El regex de "seguro" no debe comerse "vidrio de seguridad templado".
        ok, _ = f.es_irrelevante("Puerta de vidrio de seguridad templado", None)
        self.assertFalse(ok)


# ── puntaje ──────────────────────────────────────────────────────────────

class TestPuntaje(unittest.TestCase):
    def test_confirmado_puntua_alto(self):
        self.assertEqual(f.puntaje("confirmado"), 0.95)

    def test_descartado_puntua_cero(self):
        self.assertEqual(f.puntaje("descartado"), 0.0)

    def test_sin_verificar_sube_con_confianza_del_canal(self):
        bajo = f.puntaje("sin_verificar", confianza_canal=0.1)
        alto = f.puntaje("sin_verificar", confianza_canal=0.9)
        self.assertLess(bajo, alto)

    def test_sin_verificar_nunca_supera_a_confirmado(self):
        self.assertLess(f.puntaje("sin_verificar", confianza_canal=1.0), f.puntaje("confirmado"))


# ── cruzar_con_base_hector: contra una base real de baseprecios.py ────────

class TestCruceConBaseHector(unittest.TestCase):
    def setUp(self):
        # Se usa baseprecios.abrir() de verdad (no solo el ESQUEMA base) para
        # que corran también las migraciones que agregan columnas como
        # `visto_hasta` -- si no, la base de prueba queda más vieja que la
        # real y las pruebas mienten.
        self.tmp = tempfile.mktemp(suffix=".db")
        self._ruta_original = baseprecios.RUTA
        baseprecios.RUTA = self.tmp
        self.con = baseprecios.abrir()
        self.ahora = int(time.time())

    def tearDown(self):
        self.con.close()
        baseprecios.RUTA = self._ruta_original
        for sufijo in ("", "-wal", "-shm"):
            try:
                os.remove(self.tmp + sufijo)
            except OSError:
                pass

    def _sembrar(self, url, precio, hace_dias):
        cuando = self.ahora - int(hace_dias * 86400)
        baseprecios.guardar(self.con, "prueba.cl", url, "Producto de prueba",
                            precio, cuando=cuando)

    def test_url_desconocida_devuelve_none(self):
        r = f.cruzar_con_base_hector(self.con, "https://nueva.cl/x", "nueva.cl",
                                     None, 9990, ahora=self.ahora)
        self.assertIsNone(r)

    def test_el_jugo_en_caja_se_descarta(self):
        # Siempre costó $400, con 8 dias de historial real detras.
        self._sembrar("https://prueba.cl/jugo", 400, hace_dias=8)
        veredicto, caida, motivo, _ref = f.cruzar_con_base_hector(
            self.con, "https://prueba.cl/jugo", "prueba.cl", "Jugo en caja",
            400, ahora=self.ahora)
        self.assertEqual(veredicto, "descartado")

    def test_caida_real_se_confirma(self):
        self._sembrar("https://prueba.cl/notebook", 500_000, hace_dias=8)
        veredicto, caida, motivo, _ref = f.cruzar_con_base_hector(
            self.con, "https://prueba.cl/notebook", "prueba.cl", "Notebook",
            150_000, ahora=self.ahora)
        self.assertEqual(veredicto, "confirmado")
        self.assertAlmostEqual(caida, 0.70, places=2)


# ── evaluar_mensaje: integración con verificación en vivo simulada ────────

class TestEvaluarMensaje(unittest.TestCase):
    def test_verificacion_en_vivo_coincide_confirma(self):
        texto = '<a href="https://tienda-nueva.cl/p/1">Notebook</a> $150.000 (-70%)'
        bajar = lambda url, **kw: "<html>simulado</html>"
        extraer = lambda html: {"nombre": "Notebook", "precio": 150_000, "hay_stock": True}
        r = f.evaluar_mensaje(texto, "canal-prueba", con_hector=None,
                              bajar_fn=bajar, extraer_fn=extraer)
        self.assertEqual(r["veredicto"], "confirmado")
        self.assertEqual(r["fuente"], "verificado_en_vivo")

    def test_verificacion_en_vivo_no_coincide_descarta(self):
        texto = '<a href="https://tienda-nueva.cl/p/1">Notebook</a> $150.000 (-70%)'
        bajar = lambda url, **kw: "<html>simulado</html>"
        extraer = lambda html: {"nombre": "Notebook", "precio": 490_000, "hay_stock": True}
        r = f.evaluar_mensaje(texto, "canal-prueba", con_hector=None,
                              bajar_fn=bajar, extraer_fn=extraer)
        self.assertEqual(r["veredicto"], "descartado")

    def test_libro_se_descarta_sin_llegar_a_verificar_nada(self):
        llamado = []
        bajar = lambda url, **kw: llamado.append(1) or "<html></html>"
        texto = '<a href="https://buscalibre.cl/libro/1">Libro X</a> $9.990 (-50%)'
        r = f.evaluar_mensaje(texto, "canal-prueba", bajar_fn=bajar)
        self.assertEqual(r["veredicto"], "descartado")
        self.assertEqual(llamado, [], "no debería intentar verificar un libro")


# ── hector2_db ──────────────────────────────────────────────────────────

class TestUsoDesdeOtroHilo(unittest.TestCase):
    """Regresión del bug real del 23-ago: evaluar_mensaje corre dentro de
    asyncio.to_thread, así que las conexiones se abren en un hilo y se usan
    en otro. sqlite3 lo rechaza salvo check_same_thread=False."""

    def test_con_hector_se_puede_usar_desde_otro_hilo(self):
        tmp = tempfile.mktemp(suffix=".db")
        con_setup = sqlite3.connect(tmp)
        con_setup.executescript(baseprecios.ESQUEMA)
        con_setup.close()
        con = f.abrir_solo_lectura(tmp)
        try:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as ex:
                fut = ex.submit(lambda: con.execute("SELECT COUNT(*) FROM precios").fetchone())
                fut.result()  # no debe levantar ProgrammingError
        finally:
            con.close()
            for sufijo in ("", "-wal", "-shm"):
                try:
                    os.remove(tmp + sufijo)
                except OSError:
                    pass

    def test_con_h2_se_puede_usar_desde_otro_hilo(self):
        tmp = tempfile.mktemp(suffix=".db")
        con = hector2_db.abrir(tmp)
        try:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as ex:
                fut = ex.submit(lambda: hector2_db.confianza_canal(con, "canal-x"))
                fut.result()
        finally:
            con.close()
            for sufijo in ("", "-wal", "-shm"):
                try:
                    os.remove(tmp + sufijo)
                except OSError:
                    pass


class TestHector2Db(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mktemp(suffix=".db")
        self.con = hector2_db.abrir(self.tmp)

    def tearDown(self):
        self.con.close()
        for sufijo in ("", "-wal", "-shm"):
            try:
                os.remove(self.tmp + sufijo)
            except OSError:
                pass

    def test_confianza_canal_nuevo_es_none(self):
        self.assertIsNone(hector2_db.confianza_canal(self.con, "canal-x"))

    def test_confianza_necesita_evidencia_minima(self):
        for _ in range(3):
            hector2_db.registrar_mensaje(
                self.con, canal="c1", tienda="paris.cl", url="https://paris.cl/1",
                caida_declarada=0.5, caida_real=0.5, fuente="base_propia",
                veredicto="confirmado", motivo="x", topico_original="4",
                topico_final="4", texto_muestra="texto")
        self.assertIsNone(hector2_db.confianza_canal(self.con, "c1"))

    def test_confianza_se_calcula_con_evidencia_suficiente(self):
        for _ in range(4):
            hector2_db.registrar_mensaje(
                self.con, canal="c1", tienda="paris.cl", url="https://paris.cl/1",
                caida_declarada=0.5, caida_real=0.5, fuente="base_propia",
                veredicto="confirmado", motivo="x", topico_original="4",
                topico_final="4", texto_muestra="texto")
        hector2_db.registrar_mensaje(
            self.con, canal="c1", tienda=None, url="https://x.cl/1",
            caida_declarada=0.9, caida_real=None, fuente="categoria",
            veredicto="descartado", motivo="x", topico_original="4",
            topico_final="4", texto_muestra="texto")
        self.assertAlmostEqual(hector2_db.confianza_canal(self.con, "c1"), 4 / 5)

    def test_umbral_baja_cuando_falta_volumen(self):
        inicial = hector2_db.umbral_actual(self.con, "4")
        nuevo = hector2_db.ajustar_umbral(self.con, "4", enviados_24h=0,
                                          piso_objetivo=3, techo_objetivo=8)
        self.assertLess(nuevo, inicial)

    def test_umbral_sube_cuando_hay_saturacion(self):
        inicial = hector2_db.umbral_actual(self.con, "4")
        nuevo = hector2_db.ajustar_umbral(self.con, "4", enviados_24h=20,
                                          piso_objetivo=3, techo_objetivo=8)
        self.assertGreater(nuevo, inicial)

    def test_umbral_no_se_mueve_dentro_del_rango(self):
        inicial = hector2_db.umbral_actual(self.con, "4")
        nuevo = hector2_db.ajustar_umbral(self.con, "4", enviados_24h=5,
                                          piso_objetivo=3, techo_objetivo=8)
        self.assertEqual(nuevo, inicial)

    def test_umbral_no_pasa_el_piso_minimo(self):
        for _ in range(30):
            hector2_db.ajustar_umbral(self.con, "4", enviados_24h=0,
                                      piso_objetivo=3, techo_objetivo=8)
        self.assertGreaterEqual(hector2_db.umbral_actual(self.con, "4"),
                                hector2_db.UMBRAL_MIN)

    def test_umbral_no_pasa_el_techo_maximo(self):
        for _ in range(30):
            hector2_db.ajustar_umbral(self.con, "4", enviados_24h=999,
                                      piso_objetivo=3, techo_objetivo=8)
        self.assertLessEqual(hector2_db.umbral_actual(self.con, "4"),
                             hector2_db.UMBRAL_MAX)

    def test_contar_enviados_no_cuenta_descartados(self):
        hector2_db.registrar_mensaje(
            self.con, canal="c1", tienda=None, url=None, caida_declarada=None,
            caida_real=None, fuente="categoria", veredicto="descartado",
            motivo="x", topico_original="4", topico_final="4", texto_muestra="t")
        self.assertEqual(hector2_db.contar_enviados_24h(self.con, "4"), 0)

    def test_contar_enviados_cuenta_confirmados_y_sin_verificar(self):
        for v in ("confirmado", "sin_verificar"):
            hector2_db.registrar_mensaje(
                self.con, canal="c1", tienda=None, url=None, caida_declarada=None,
                caida_real=None, fuente="categoria", veredicto=v, motivo="x",
                topico_original="4", topico_final="4", texto_muestra="t")
        self.assertEqual(hector2_db.contar_enviados_24h(self.con, "4"), 2)


if __name__ == "__main__":
    unittest.main()
