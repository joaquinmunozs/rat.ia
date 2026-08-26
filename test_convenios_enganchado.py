# -*- coding: utf-8 -*-
"""(Claude, 26-ago-2026) El monitor de convenios enganchado al proceso que ya
corre 24/7 -- mismo patrón que `test_selector_enganchado.py` para
`ratia_ig_selector`, pero para `convenios_monitor`.

Pedido de Joaquín: ponerse al día con las promos bancarias de agosto, 1 por
día en Instagram. Estas pruebas protegen lo mismo que las del selector: que
nada se publique sin que alguien lo haya habilitado a mano, y que la primera
pasada corra AL ARRANCAR (no recién después de `intervalo`) -- a diferencia
de `_tarea_selector_instagram`, acá no vale esperar horas para la primera
pasada cuando el pedido es "empezar ahora".
"""
import asyncio
import os
import sys
import unittest

sys.stdout.reconfigure(encoding="utf-8")

import reenviar_ofertas as R


class _ConVariable(unittest.TestCase):
    def setUp(self):
        self._previo = os.environ.get("CONVENIOS_IG_AUTO")

    def tearDown(self):
        if self._previo is None:
            os.environ.pop("CONVENIOS_IG_AUTO", None)
        else:
            os.environ["CONVENIOS_IG_AUTO"] = self._previo

    def _poner(self, valor):
        if valor is None:
            os.environ.pop("CONVENIOS_IG_AUTO", None)
        else:
            os.environ["CONVENIOS_IG_AUTO"] = valor


class TestLaTareaNoArrancaSola(_ConVariable):
    def test_sin_la_variable_la_tarea_termina_de_inmediato(self):
        self._poner(None)

        async def correr():
            await asyncio.wait_for(R._tarea_convenios(), timeout=1)

        asyncio.run(correr())

    def test_la_variable_vacia_tampoco_arranca(self):
        self._poner("   ")

        async def correr():
            await asyncio.wait_for(R._tarea_convenios(), timeout=1)

        asyncio.run(correr())


class TestElModoSeLeeBien(_ConVariable):
    def test_los_tres_escalones(self):
        for valor, esperado in ((None, ""), ("", ""), ("ensayo", "ensayo"),
                                ("1", "1"), ("ENSAYO", "ensayo"),
                                ("  1  ", "1")):
            self._poner(valor)
            self.assertEqual(R._convenios_modo(), esperado, repr(valor))

    def test_un_valor_raro_no_publica(self):
        for valor in ("si", "true", "yes", "publicar", "0"):
            self._poner(valor)
            self.assertNotEqual(R._convenios_modo(), "1", valor)


class TestLaPasadaAbreConexionPropia(_ConVariable):
    def test_abre_y_cierra_la_suya_y_pasa_confirmar(self):
        abiertas, cerradas, visto = [], [], {}

        class _Con:
            def __init__(self, nombre):
                self.nombre = nombre
                abiertas.append(nombre)

            def close(self):
                cerradas.append(self.nombre)

        import convenios_monitor

        original_abrir = R.hector2_db.abrir
        original_pasada = convenios_monitor.una_pasada
        R.hector2_db.abrir = lambda *a, **k: _Con("h2")

        def _pasada(con, confirmar=False, log=None):
            visto["confirmar"] = confirmar
            return []

        convenios_monitor.una_pasada = _pasada
        try:
            R._pasada_convenios(confirmar=True)
        finally:
            R.hector2_db.abrir = original_abrir
            convenios_monitor.una_pasada = original_pasada

        self.assertEqual(abiertas, ["h2"])
        self.assertEqual(cerradas, ["h2"])
        self.assertTrue(visto["confirmar"])

    def test_la_conexion_se_cierra_aunque_la_pasada_reviente(self):
        cerradas = []

        class _Con:
            def close(self):
                cerradas.append("h2")

        import convenios_monitor

        original_abrir = R.hector2_db.abrir
        original_pasada = convenios_monitor.una_pasada
        R.hector2_db.abrir = lambda *a, **k: _Con()

        def _explota(*a, **k):
            raise RuntimeError("pangui no responde")

        convenios_monitor.una_pasada = _explota
        try:
            with self.assertRaises(RuntimeError):
                R._pasada_convenios(confirmar=False)
        finally:
            R.hector2_db.abrir = original_abrir
            convenios_monitor.una_pasada = original_pasada

        self.assertEqual(cerradas, ["h2"])


class TestPrimeraPasadaCorreAlArrancar(_ConVariable):
    """A diferencia del selector de retail (10 min antes de la primera
    pasada), acá el pedido es "empezar ahora" -- esperar horas la primera
    vez habría dejado el 26-ago sin su promo del día."""

    def test_no_espera_el_intervalo_para_la_primera_pasada(self):
        self._poner("ensayo")
        llamadas = []
        original = R._pasada_convenios
        R._pasada_convenios = lambda confirmar: llamadas.append(confirmar)
        try:
            async def correr():
                tarea = asyncio.ensure_future(
                    R._tarea_convenios(intervalo=10))
                await asyncio.sleep(0.05)
                tarea.cancel()

            asyncio.run(correr())
        finally:
            R._pasada_convenios = original

        self.assertEqual(llamadas, [False], "debió correr una vez de inmediato, en ensayo")


class TestUnaPasadaRotaNoMataLaTarea(_ConVariable):
    def test_el_bucle_sigue_despues_de_un_fallo(self):
        self._poner("ensayo")
        llamadas = []

        def _explota(confirmar):
            llamadas.append(confirmar)
            raise RuntimeError("pangui caído")

        original = R._pasada_convenios
        R._pasada_convenios = _explota
        try:
            async def correr():
                tarea = asyncio.ensure_future(
                    R._tarea_convenios(intervalo=0.01))
                await asyncio.sleep(0.15)
                viva = not tarea.done()
                tarea.cancel()
                return viva

            viva = asyncio.run(correr())
        finally:
            R._pasada_convenios = original

        self.assertGreater(len(llamadas), 1, "no reintentó después del fallo")
        self.assertTrue(viva, "la tarea murió con la primera pasada rota")


if __name__ == "__main__":
    unittest.main(verbosity=1)
