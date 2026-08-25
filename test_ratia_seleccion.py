# -*- coding: utf-8 -*-
"""(Claude, 25-ago-2026) La regla de Joaquín para qué sube a Instagram:

  OFERTAS  -- máx. 2/día. Novedoso/viral/tecnológico/hogar Y >=50% dcto.
             Se publican 1-2h después de aparecer en Telegram. Corte 23:30.
  ERRORES  -- caída >= 85% (el mismo umbral que ya separa "Ofertas 70%" de
             "Errores de precio" en el propio Telegram). Se publican 30 min
             después de aparecer, a cualquier hora.
"""
import sys
import time
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

sys.stdout.reconfigure(encoding="utf-8")

import ratia_seleccion as s

TZ = ZoneInfo("America/Santiago")


def _epoch(y, m, d, h, mi=0):
    return int(datetime(y, m, d, h, mi, tzinfo=TZ).timestamp())


def _fila(url="https://tienda.cl/p/1", tienda="falabella.com",
          nombre="Notebook HP Ryzen 5", precio=299_990, referencia=699_990,
          caida=0.57, primera_vez_vista=None, fuente="hector"):
    return dict(url=url, tienda=tienda, nombre=nombre, precio=precio,
               referencia=referencia, caida=caida, fuente=fuente,
               primera_vez_vista=primera_vez_vista or _epoch(2026, 8, 25, 15, 0))


class TestClasificacionYUmbral(unittest.TestCase):
    def test_bajo_85_es_oferta_sobre_85_es_error(self):
        self.assertEqual(s.clasificar(0.84), "oferta")
        self.assertEqual(s.clasificar(0.85), "error")
        self.assertEqual(s.clasificar(0.99), "error")

    def test_usa_el_mismo_umbral_que_el_telegram(self):
        import baseprecios
        self.assertEqual(s.clasificar(baseprecios.UMBRAL_ERROR_GRAVE - 0.001),
                         "oferta")
        self.assertEqual(s.clasificar(baseprecios.UMBRAL_ERROR_GRAVE), "error")


class TestCalificaParaOfertas(unittest.TestCase):
    """Las DOS condiciones, no una: categoría Y >=50%."""

    def test_notebook_al_57_califica(self):
        c = s.Candidato(**{**_candidato_base(), "caida": 0.57,
                          "nombre": "Notebook HP Ryzen 5", "tipo": "oferta"})
        ok, motivo = s.calificado_para_ig(c)
        self.assertTrue(ok, motivo)

    def test_categoria_correcta_pero_bajo_50_no_pasa(self):
        c = s.Candidato(**{**_candidato_base(), "caida": 0.40,
                          "nombre": "Notebook HP", "tipo": "oferta"})
        ok, motivo = s.calificado_para_ig(c)
        self.assertFalse(ok)
        self.assertIn("50", motivo)

    def test_50_o_mas_pero_categoria_ajena_no_pasa(self):
        # Zapatillas: -60%, ninguna categoría deseable. La regla es Y, no O.
        c = s.Candidato(**{**_candidato_base(), "caida": 0.60,
                          "nombre": "Zapatillas urbanas talla 42", "tipo": "oferta"})
        ok, motivo = s.calificado_para_ig(c)
        self.assertFalse(ok)
        self.assertIn("tecnológico", motivo)

    def test_hogar_califica_igual_que_tecnologico(self):
        c = s.Candidato(**{**_candidato_base(), "caida": 0.55,
                          "nombre": "Refrigerador Side by Side 500L", "tipo": "oferta"})
        ok, _m = s.calificado_para_ig(c)
        self.assertTrue(ok)

    def test_producto_viral_sin_ser_electronico_o_hogar_califica(self):
        # El caso que Joaquín dio de ejemplo (Starlink): "imán" de reventa,
        # no encaja limpio en electrónica de catálogo pero sí en IMANES.
        c = s.Candidato(**{**_candidato_base(), "caida": 0.55,
                          "nombre": "Starlink Mini Kit Internet Satelital", "tipo": "oferta"})
        ok, _m = s.calificado_para_ig(c)
        self.assertTrue(ok)


class TestCalificaParaErrores(unittest.TestCase):
    def test_84_no_es_error_aunque_sea_electronico(self):
        c = s.Candidato(**{**_candidato_base(), "caida": 0.84,
                          "nombre": "Notebook", "tipo": "error"})
        ok, motivo = s.calificado_para_ig(c)
        self.assertFalse(ok)

    def test_85_es_error_SIN_exigir_categoria(self):
        # A diferencia de ofertas, un error NO necesita ser tecnológico ni
        # hogar -- un error de precio en cualquier cosa vale la pena.
        c = s.Candidato(**{**_candidato_base(), "caida": 0.90,
                          "nombre": "Detergente líquido 3L", "tipo": "error"})
        ok, _m = s.calificado_para_ig(c)
        self.assertTrue(ok)


class TestTiempos(unittest.TestCase):
    """1-2h para ofertas, 30 min para errores, contados desde que se avisó
    en el Telegram."""

    def test_oferta_elegible_a_la_hora_no_antes(self):
        vista = _epoch(2026, 8, 25, 15, 0)
        c = s.Candidato(**{**_candidato_base(), "primera_vez_vista": vista,
                          "tipo": "oferta"})
        self.assertEqual(c.elegible_en, vista + 3600)

    def test_error_elegible_a_los_30_minutos(self):
        vista = _epoch(2026, 8, 25, 15, 0)
        c = s.Candidato(**{**_candidato_base(), "primera_vez_vista": vista,
                          "tipo": "error"})
        self.assertEqual(c.elegible_en, vista + 1800)

    def test_no_se_publica_antes_de_ser_elegible(self):
        vista = _epoch(2026, 8, 25, 15, 0)
        c = s.Candidato(**{**_candidato_base(), "primera_vez_vista": vista,
                          "tipo": "oferta", "caida": 0.55})
        c.puntaje = s.puntaje_oferta(c)
        # 40 min después: todavía no pasó la hora.
        listos = s.listos_para_publicar([c], vista + 40 * 60, {})
        self.assertEqual(listos, [])

    def test_se_publica_dentro_de_la_ventana(self):
        vista = _epoch(2026, 8, 25, 15, 0)
        c = s.Candidato(**{**_candidato_base(), "primera_vez_vista": vista,
                          "tipo": "oferta", "caida": 0.55})
        c.puntaje = s.puntaje_oferta(c)
        listos = s.listos_para_publicar([c], vista + 90 * 60, {})
        self.assertEqual(listos, [c])

    def test_oferta_vieja_de_mas_de_6h_ya_no_se_publica(self):
        vista = _epoch(2026, 8, 25, 8, 0)
        c = s.Candidato(**{**_candidato_base(), "primera_vez_vista": vista,
                          "tipo": "oferta", "caida": 0.55})
        c.puntaje = s.puntaje_oferta(c)
        listos = s.listos_para_publicar([c], vista + 7 * 3600, {})
        self.assertEqual(listos, [])

    def test_error_vencido_a_las_2h_no_se_publica(self):
        vista = _epoch(2026, 8, 25, 8, 0)
        c = s.Candidato(**{**_candidato_base(), "primera_vez_vista": vista,
                          "tipo": "error", "caida": 0.90})
        listos = s.listos_para_publicar([c], vista + 3 * 3600, {})
        self.assertEqual(listos, [])


class TestCorteYCupo(unittest.TestCase):
    def test_nada_de_ofertas_despues_de_las_2330(self):
        vista = _epoch(2026, 8, 25, 18, 0)
        ahora = _epoch(2026, 8, 25, 23, 45)  # después del corte
        c = s.Candidato(**{**_candidato_base(), "primera_vez_vista": vista,
                          "tipo": "oferta", "caida": 0.55})
        c.puntaje = s.puntaje_oferta(c)
        listos = s.listos_para_publicar([c], ahora, {})
        self.assertEqual(listos, [])

    def test_errores_SI_se_publican_despues_del_corte(self):
        # El corte de 23:30 es explícitamente sólo para ofertas -- un error
        # de precio no tiene por qué esperar a mañana.
        vista = _epoch(2026, 8, 25, 23, 20)
        ahora = _epoch(2026, 8, 25, 23, 55)
        c = s.Candidato(**{**_candidato_base(), "primera_vez_vista": vista,
                          "tipo": "error", "caida": 0.90})
        listos = s.listos_para_publicar([c], ahora, {})
        self.assertEqual(listos, [c])

    def test_tope_de_2_ofertas_al_dia(self):
        vista = _epoch(2026, 8, 25, 12, 0)
        ahora = _epoch(2026, 8, 25, 15, 0)
        candidatos = []
        for i in range(4):
            c = s.Candidato(**{**_candidato_base(), "url": f"https://t.cl/{i}",
                              "primera_vez_vista": vista, "tipo": "oferta",
                              "caida": 0.55})
            c.puntaje = s.puntaje_oferta(c)
            candidatos.append(c)
        # Ya se publicó 1 oferta hoy: sólo debería entrar 1 más (tope 2).
        listos = s.listos_para_publicar(candidatos, ahora, {"oferta": 1})
        self.assertEqual(len(listos), 1)

    def test_las_mejores_ofertas_ganan_el_cupo(self):
        vista = _epoch(2026, 8, 25, 12, 0)
        ahora = _epoch(2026, 8, 25, 15, 0)
        floja = s.Candidato(**{**_candidato_base(), "url": "https://t.cl/floja",
                              "primera_vez_vista": vista, "tipo": "oferta",
                              "caida": 0.50, "precio": 90_000, "referencia": 180_000})
        buena = s.Candidato(**{**_candidato_base(), "url": "https://t.cl/buena",
                              "primera_vez_vista": vista, "tipo": "oferta",
                              "caida": 0.75, "precio": 90_000, "referencia": 360_000,
                              "nombre": "iPhone 15 128GB"})
        for c in (floja, buena):
            c.puntaje = s.puntaje_oferta(c)
        listos = s.listos_para_publicar([floja, buena], ahora, {})
        self.assertEqual(len(listos), 2)  # tope 2, entran las 2
        # ahora con cupo de 1: debe ganar la buena.
        listos1 = s.listos_para_publicar([floja, buena], ahora, {"oferta": 1})
        self.assertEqual(listos1, [buena])

    def test_los_errores_no_tienen_tope_de_2_son_su_propio_cupo(self):
        vista = _epoch(2026, 8, 25, 15, 0)
        ahora = _epoch(2026, 8, 25, 15, 35)
        errores = []
        for i in range(3):
            c = s.Candidato(**{**_candidato_base(), "url": f"https://t.cl/e{i}",
                              "primera_vez_vista": vista, "tipo": "error",
                              "caida": 0.90})
            errores.append(c)
        listos = s.listos_para_publicar(errores, ahora, {"oferta": 2})
        self.assertEqual(len(listos), 3)

    def test_el_error_mas_urgente_va_primero_si_falta_cupo(self):
        ahora = _epoch(2026, 8, 25, 16, 0)
        viejo = s.Candidato(**{**_candidato_base(), "url": "https://t.cl/viejo",
                              "primera_vez_vista": ahora - 40 * 60, "tipo": "error",
                              "caida": 0.90})
        nuevo = s.Candidato(**{**_candidato_base(), "url": "https://t.cl/nuevo",
                              "primera_vez_vista": ahora - 31 * 60, "tipo": "error",
                              "caida": 0.99})
        listos = s.listos_para_publicar([nuevo, viejo], ahora, {"error": 5})
        self.assertEqual(listos, [viejo])  # sólo cabe 1, gana el más viejo


class TestEvaluarCandidatos(unittest.TestCase):
    """De principio a fin: filas crudas -> candidatos calificados."""

    def test_filtra_los_que_no_califican_y_clasifica_los_que_si(self):
        filas = [
            _fila(url="https://t.cl/1", nombre="Notebook HP", caida=0.57),   # oferta ok
            _fila(url="https://t.cl/2", nombre="Notebook HP", caida=0.30),   # bajo 50%
            _fila(url="https://t.cl/3", nombre="Polera básica", caida=0.60), # sin categoría
            _fila(url="https://t.cl/4", nombre="Auriculares Sony", caida=0.90),  # error
        ]
        resultado = s.evaluar_candidatos(filas)
        urls = {c.url for c in resultado}
        self.assertEqual(urls, {"https://t.cl/1", "https://t.cl/4"})
        tipos = {c.url: c.tipo for c in resultado}
        self.assertEqual(tipos["https://t.cl/1"], "oferta")
        self.assertEqual(tipos["https://t.cl/4"], "error")


def _candidato_base():
    return dict(url="https://tienda.cl/p/1", tipo="oferta", fuente="hector",
               tienda="falabella.com", nombre="Notebook HP Ryzen 5",
               precio=299_990, referencia=699_990, caida=0.57,
               primera_vez_vista=_epoch(2026, 8, 25, 15, 0))


if __name__ == "__main__":
    unittest.main(verbosity=1)
