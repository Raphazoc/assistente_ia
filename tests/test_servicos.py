import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import servicos


class ServicosTests(unittest.TestCase):
    def test_preferencias_nao_guardam_chaves_no_json(self):
        with tempfile.TemporaryDirectory() as pasta, \
             patch.object(servicos, "CONFIGURACAO", Path(pasta) / "servicos.json"), \
             patch("keyring.set_password") as guardar, \
             patch("keyring.get_password", return_value="segredo"):
            servicos.salvar_chave("brave", "segredo")
            servicos.salvar("brave", "elevenlabs", "voz123")
            self.assertEqual(servicos.obter_chave("brave"), "segredo")
            self.assertEqual(servicos.carregar(), {
                "buscador": "brave", "voz": "elevenlabs", "voice_id": "voz123"
            })
            self.assertNotIn("segredo", servicos.CONFIGURACAO.read_text(encoding="utf-8"))
            guardar.assert_called_once_with("AssistenteIA", "brave", "segredo")

    def test_identificador_malformado_nao_entra_na_url_de_voz(self):
        with tempfile.TemporaryDirectory() as pasta, \
             patch.object(servicos, "CONFIGURACAO", Path(pasta) / "servicos.json"):
            servicos.CONFIGURACAO.write_text(json.dumps({
                "buscador": "brave", "voz": "elevenlabs", "voice_id": "../outro?x=1"
            }), encoding="utf-8")
            self.assertEqual(servicos.carregar()["voice_id"], "")
            with self.assertRaises(ValueError):
                servicos.salvar("brave", "elevenlabs", "../outro")
