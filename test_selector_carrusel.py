# -*- coding: utf-8 -*-
"""Rat.IA · el selector de Instagram publica el carrusel de 2 slides, no 1
imagen suelta (26-ago-2026: reemplaza a `ratia_publicar.publicar_oferta`).

Cada prueba fija un comportamiento real que se verificó al conectar
`ratia_carrusel.armar()` a `ratia_ig_selector._armar_y_publicar_carrusel`.
Nada gasta créditos: `ratia_carrusel.armar` y `ratia_publicar.publicar_carrusel`
van con monkeypatch.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hector2_db
import ratia_carrusel
import ratia_ig_selector as S
import ratia_publicar
import ratia_seleccion as sel


def _candidato(**kw):
    base = dict(url="https://tienda.cl/prod", tipo="oferta", fuente="hector",
                tienda="Tienda", nombre="Producto X", precio=10000,
                referencia=20000, caida=0.5, primera_vez_vista=1000)
    base.update(kw)
    return sel.Candidato(**base)


class ArmaAntesDePublicar(unittest.TestCase):
    def setUp(self):
        self.con = hector2_db.abrir(":memory:")

    def test_sin_confirmar_arma_pero_no_llama_a_blotato(self):
        pieza = {"slides": [b"s1", b"s2"], "caption": "cap", "template": 1, "nombre_corto": "x"}
        with patch.object(ratia_carrusel, "armar", return_value=pieza) as m_armar, \
             patch.object(ratia_publicar, "publicar_carrusel") as m_pub:
            r = S._armar_y_publicar_carrusel(self.con, _candidato(), confirmar=False)
        m_armar.assert_called_once()
        m_pub.assert_not_called()
        self.assertTrue(r["ok"])
        self.assertFalse(r["publicado"])

    def test_confirmar_publica_el_carrusel_completo(self):
        pieza = {"slides": [b"s1", b"s2"], "caption": "cap", "template": 2, "nombre_corto": "x"}
        with patch.object(ratia_carrusel, "armar", return_value=pieza), \
             patch.object(ratia_publicar, "publicar_carrusel",
                          return_value={"id": "post123"}) as m_pub:
            r = S._armar_y_publicar_carrusel(self.con, _candidato(), confirmar=True)
        # Las DOS slides viajan juntas, no una imagen suelta.
        args = m_pub.call_args[0]
        self.assertEqual(args[0], [b"s1", b"s2"])
        self.assertEqual(args[1], "cap")
        self.assertTrue(r["ok"] and r["publicado"])
        self.assertEqual(r["submission"], {"id": "post123"})

    def test_si_armar_no_puede_no_se_intenta_publicar(self):
        # `armar` devuelve None cuando Kie no logra una pieza correcta -- eso
        # SIEMPRE significa no publicar, nunca reintentar acá mismo.
        with patch.object(ratia_carrusel, "armar", return_value=None), \
             patch.object(ratia_publicar, "publicar_carrusel") as m_pub:
            r = S._armar_y_publicar_carrusel(self.con, _candidato(), confirmar=True)
        m_pub.assert_not_called()
        self.assertFalse(r["ok"])
        self.assertIn("motivo", r)

    def test_un_fallo_de_blotato_no_revienta_la_pasada(self):
        pieza = {"slides": [b"s1", b"s2"], "caption": "cap", "template": 1, "nombre_corto": "x"}
        with patch.object(ratia_carrusel, "armar", return_value=pieza), \
             patch.object(ratia_publicar, "publicar_carrusel",
                          side_effect=RuntimeError("Blotato 500: boom")):
            r = S._armar_y_publicar_carrusel(self.con, _candidato(), confirmar=True)
        self.assertFalse(r["ok"])
        self.assertIn("Blotato", r["motivo"])


class TemplateDeTurnoUsaElContadorTotal(unittest.TestCase):
    """1,2,1,2 consecutivo -- pero sobre TOTAL publicados, no sobre los de hoy
    (el contador de hoy se reinicia a medianoche y repetiría template)."""

    def test_deriva_del_total_publicados(self):
        con = hector2_db.abrir(":memory:")
        self.assertEqual(hector2_db.total_publicados(con), 0)
        self.assertEqual(ratia_carrusel.template_de_turno(hector2_db.total_publicados(con)), 1)

        hector2_db.registrar_candidato(
            con, url="https://a.cl/1", tipo="oferta", fuente="hector",
            tienda="A", nombre="p1", precio=1, referencia=2, caida=0.5,
            primera_vez_vista=1, ahora=1)
        hector2_db.marcar_publicado(con, "https://a.cl/1", "oferta", post_id="p1", ahora=2)

        self.assertEqual(hector2_db.total_publicados(con), 1)
        self.assertEqual(ratia_carrusel.template_de_turno(hector2_db.total_publicados(con)), 2)


class PublicarCarruselSubeCadaSlide(unittest.TestCase):
    def test_sube_n_slides_y_publica_con_n_mediaurls(self):
        subidas = []

        def _pedir_falso(ruta, cuerpo=None, metodo="GET"):
            if ruta == "/media":
                subidas.append(cuerpo["url"])
                return {"url": "https://blotato.cdn/%d.png" % len(subidas)}
            if ruta == "/posts":
                return {"id": "post999", "cuerpo": cuerpo}
            raise AssertionError("ruta inesperada: %s" % ruta)

        with patch.dict(os.environ, {"BLOTATO_API_KEY": "k"}), \
             patch.object(ratia_publicar, "_pedir", side_effect=_pedir_falso):
            envio = ratia_publicar.publicar_carrusel(
                [b"slide1", b"slide2"], "el caption", cuenta_id="acc1")

        self.assertEqual(len(subidas), 2, "debe subir cada slide por separado")
        self.assertEqual(
            envio["cuerpo"]["post"]["content"]["mediaUrls"],
            ["https://blotato.cdn/1.png", "https://blotato.cdn/2.png"])
        self.assertEqual(envio["cuerpo"]["post"]["accountId"], "acc1")


if __name__ == "__main__":
    unittest.main()
