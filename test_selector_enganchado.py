# -*- coding: utf-8 -*-
"""(Claude, 25-ago-2026) El selector de Instagram enganchado al proceso que ya
corre 24/7.

Cierra "engancharlo a algo que corra solo" de la bitacora del 25-ago (tarde).

LO QUE ESTAS PRUEBAS PROTEGEN
==============================================================================
Que NADA se publique sin que alguien lo haya habilitado a mano. La regla ya
existia para `ratia_publicar` y esta escrita en la bitacora: "un selector
automatico que publica solo, sin que nadie lo haya visto correr en produccion
al menos una vez, es el tipo de incidente que ya se evito una vez con esa
misma regla".

Los tres escalones de `RATIA_IG_AUTO`:

    (sin definir)  la tarea no arranca. Identico al comportamiento de hoy.
    "ensayo"       corre y loguea que publicaria. NO publica.
    "1"            publica de verdad.

Un cuarto caso importa igual: un valor RARO ("si", "true", "yes") no puede
interpretarse como "publica". Ante la duda, no se publica.
"""
import asyncio
import os
import sys
import unittest

sys.stdout.reconfigure(encoding="utf-8")

import reenviar_ofertas as R


class _ConVariable(unittest.TestCase):
    def setUp(self):
        self._previo = os.environ.get("RATIA_IG_AUTO")

    def tearDown(self):
        if self._previo is None:
            os.environ.pop("RATIA_IG_AUTO", None)
        else:
            os.environ["RATIA_IG_AUTO"] = self._previo

    def _poner(self, valor):
        if valor is None:
            os.environ.pop("RATIA_IG_AUTO", None)
        else:
            os.environ["RATIA_IG_AUTO"] = valor


class TestLaTareaNoArrancaSola(_ConVariable):
    def test_sin_la_variable_la_tarea_termina_de_inmediato(self):
        # Sin definir, el comportamiento tiene que ser IDENTICO al de antes
        # de este cambio: la tarea no existe.
        self._poner(None)

        async def correr():
            # Si la tarea entrara al bucle, `wait_for` daria TimeoutError
            # en vez de terminar.
            await asyncio.wait_for(R._tarea_selector_instagram(), timeout=1)

        asyncio.run(correr())

    def test_la_variable_vacia_tampoco_arranca(self):
        self._poner("   ")

        async def correr():
            await asyncio.wait_for(R._tarea_selector_instagram(), timeout=1)

        asyncio.run(correr())


class TestElModoSeLeeBien(_ConVariable):
    def test_los_tres_escalones(self):
        for valor, esperado in ((None, ""), ("", ""), ("ensayo", "ensayo"),
                                ("1", "1"), ("ENSAYO", "ensayo"),
                                ("  1  ", "1")):
            self._poner(valor)
            self.assertEqual(R._ig_modo(), esperado, repr(valor))

    def test_un_valor_raro_no_publica(self):
        # "si"/"true"/"yes" arrancan la tarea pero en ENSAYO. La unica
        # cadena que publica es "1" -- ante la duda, no se publica.
        for valor in ("si", "true", "yes", "publicar", "0"):
            self._poner(valor)
            self.assertNotEqual(R._ig_modo(), "1", valor)


class TestLaPasadaAbreConexionesPropias(_ConVariable):
    """No puede reusar las del bot: estan serializadas con `_DB_LOCK`, y una
    pasada baja fichas, llama a un modelo de imagenes y publica. Tener el lock
    tomado todo ese rato dejaria el reenvio congelado -- el mismo error que el
    11-ago mantenia el lock de escritura tomado durante descargas HTTP."""

    def test_abre_y_cierra_las_suyas_y_pasa_confirmar(self):
        abiertas, cerradas, visto = [], [], {}

        class _Con:
            def __init__(self, nombre):
                self.nombre = nombre
                abiertas.append(nombre)

            def close(self):
                cerradas.append(self.nombre)

        import ratia_ig_selector

        originales = (R.descargar_base_hector.asegurar,
                      R.hector2_filtro.abrir_solo_lectura,
                      R.hector2_db.abrir,
                      ratia_ig_selector.una_pasada)
        R.descargar_base_hector.asegurar = lambda *a, **k: ("/tmp/p.db", False)
        R.hector2_filtro.abrir_solo_lectura = lambda ruta: _Con("precios")
        R.hector2_db.abrir = lambda *a, **k: _Con("h2")

        def _pasada(con_precios, con_h2, confirmar=False, log=None):
            visto["confirmar"] = confirmar
            return []

        ratia_ig_selector.una_pasada = _pasada
        try:
            R._pasada_instagram(confirmar=True)
        finally:
            (R.descargar_base_hector.asegurar,
             R.hector2_filtro.abrir_solo_lectura,
             R.hector2_db.abrir,
             ratia_ig_selector.una_pasada) = originales

        self.assertEqual(abiertas, ["precios", "h2"])
        self.assertEqual(sorted(cerradas), ["h2", "precios"])
        self.assertTrue(visto["confirmar"])

    def test_las_conexiones_se_cierran_aunque_la_pasada_reviente(self):
        cerradas = []

        class _Con:
            def __init__(self, nombre):
                self.nombre = nombre

            def close(self):
                cerradas.append(self.nombre)

        import ratia_ig_selector

        originales = (R.descargar_base_hector.asegurar,
                      R.hector2_filtro.abrir_solo_lectura,
                      R.hector2_db.abrir,
                      ratia_ig_selector.una_pasada)
        R.descargar_base_hector.asegurar = lambda *a, **k: ("/tmp/p.db", False)
        R.hector2_filtro.abrir_solo_lectura = lambda ruta: _Con("precios")
        R.hector2_db.abrir = lambda *a, **k: _Con("h2")

        def _explota(*a, **k):
            raise RuntimeError("kie no responde")

        ratia_ig_selector.una_pasada = _explota
        try:
            with self.assertRaises(RuntimeError):
                R._pasada_instagram(confirmar=False)
        finally:
            (R.descargar_base_hector.asegurar,
             R.hector2_filtro.abrir_solo_lectura,
             R.hector2_db.abrir,
             ratia_ig_selector.una_pasada) = originales

        # Una conexion filtrada por pasada, cada 10 minutos, termina en un
        # servicio que se queda sin descriptores a los dias.
        self.assertEqual(sorted(cerradas), ["h2", "precios"])


class TestUnaPasadaRotaNoMataLaTarea(_ConVariable):
    def test_el_bucle_sigue_despues_de_un_fallo(self):
        # Si la tarea muere, deja de publicarse en Instagram y NADIE se
        # entera: el reenvio a Telegram sigue andando y el servicio se ve
        # sano.
        self._poner("ensayo")
        llamadas = []

        def _explota(confirmar):
            llamadas.append(confirmar)
            raise RuntimeError("kie no responde")

        original = R._pasada_instagram
        R._pasada_instagram = _explota
        try:
            async def correr():
                tarea = asyncio.ensure_future(
                    R._tarea_selector_instagram(intervalo=0.01))
                await asyncio.sleep(0.15)
                viva = not tarea.done()
                tarea.cancel()
                return viva

            viva = asyncio.run(correr())
        finally:
            R._pasada_instagram = original

        self.assertGreater(len(llamadas), 1, "no reintento despues del fallo")
        self.assertTrue(viva, "la tarea murio con la primera pasada rota")


if __name__ == "__main__":
    unittest.main(verbosity=1)
