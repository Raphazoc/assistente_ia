import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from app import perfil_voz


class PerfilVozTests(unittest.TestCase):
    def test_cadastro_guarda_somente_vetor_e_filtra_outro_locutor(self):
        with tempfile.TemporaryDirectory() as pasta, \
                patch.object(perfil_voz.caminhos, "pasta_dados", return_value=Path(pasta)), \
                patch.object(perfil_voz, "preparar_modelo"), \
                patch.object(perfil_voz, "modelo_disponivel", return_value=True):
            vetor = np.zeros(256, dtype=np.float32)
            vetor[0] = 1
            outro = np.zeros(256, dtype=np.float32)
            outro[1] = 1
            with patch.object(perfil_voz, "_embedding", side_effect=[vetor, vetor]):
                perfil_voz.cadastrar(np.ones(20000), np.ones(20000))
            dados = json.loads(perfil_voz.caminho_perfil().read_text(encoding="utf-8"))
            self.assertEqual(set(dados), {"modelo", "vetor"})
            self.assertEqual(len(dados["vetor"]), 256)
            with patch.object(perfil_voz, "_embedding", return_value=vetor):
                self.assertTrue(perfil_voz.corresponde(np.ones(20000)))
            with patch.object(perfil_voz, "_embedding", return_value=outro):
                self.assertFalse(perfil_voz.corresponde(np.ones(20000)))
            perfil_voz.remover()
            self.assertFalse(perfil_voz.cadastrado())

    def test_perfil_corrompido_falha_em_modo_fechado(self):
        with tempfile.TemporaryDirectory() as pasta, \
                patch.object(perfil_voz.caminhos, "pasta_dados", return_value=Path(pasta)):
            perfil_voz.caminho_perfil().write_text('{"vetor": "inválido"}', encoding="utf-8")
            self.assertFalse(perfil_voz.corresponde(np.ones(20000)))

    def test_download_conferido_por_hash_sem_deixar_temporario(self):
        conteudo = b"modelo local de teste"
        with tempfile.TemporaryDirectory() as pasta, \
                patch.object(perfil_voz.caminhos, "pasta_dados", return_value=Path(pasta)), \
                patch.object(perfil_voz, "MODELO_SHA256", hashlib.sha256(conteudo).hexdigest()), \
                patch.object(perfil_voz.urllib.request, "urlopen", return_value=io.BytesIO(conteudo)):
            destino = perfil_voz.preparar_modelo()
            self.assertEqual(destino.read_bytes(), conteudo)
            self.assertEqual(list(destino.parent.iterdir()), [destino])

    def test_download_adulterado_e_recusado(self):
        with tempfile.TemporaryDirectory() as pasta, \
                patch.object(perfil_voz.caminhos, "pasta_dados", return_value=Path(pasta)), \
                patch.object(perfil_voz.urllib.request, "urlopen", return_value=io.BytesIO(b"errado")):
            with self.assertRaisesRegex(ValueError, "integridade"):
                perfil_voz.preparar_modelo()
            self.assertEqual(list((Path(pasta) / "modelos").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
