import io
import json
import hashlib
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app import atualizacoes, configuracao


class AtualizacoesTests(unittest.TestCase):
    def test_versoes_numericas_e_beta(self):
        chave = atualizacoes.chave_versao
        self.assertLess(chave("v0.5.9"), chave("v0.5.10"))
        self.assertLess(chave("v0.6.0b1"), chave("v0.6.0"))
        self.assertIsNone(chave("release/qualquer"))

    def test_escolhe_maior_release_publicada_e_valida_url(self):
        releases = [
            {"tag_name": "v0.7.0", "html_url": "https://github.com/Raphazoc/assistente_ia/releases/tag/v0.7.0", "draft": True},
            {"tag_name": "v0.6.0b1", "html_url": "https://github.com/Raphazoc/assistente_ia/releases/tag/v0.6.0b1", "prerelease": True, "body": "Novidades",
             "assets": [{"name": "AssistenteIA-Setup.exe", "digest": "sha256:" + "a" * 64}]},
            {"tag_name": "v0.6.0", "html_url": "https://evil.example/release", "body": "Ignorar"},
            {"tag_name": "v0.5.2", "html_url": "https://github.com/Raphazoc/assistente_ia/releases/tag/v0.5.2"},
        ]
        resposta = io.BytesIO(json.dumps(releases).encode("utf-8"))
        abrir = Mock(return_value=resposta)
        resultado = atualizacoes.consultar("0.5.3", abrir=abrir)
        self.assertEqual(resultado["versao"], "v0.6.0b1")
        self.assertEqual(resultado["notas"], "Novidades")
        self.assertTrue(resultado["beta"])
        self.assertEqual(resultado["sha256"], "a" * 64)
        self.assertEqual(abrir.call_args.kwargs["timeout"], 5)

    def test_sem_novidades_e_resposta_invalida(self):
        def abrir(*_args, **_kwargs):
            return io.BytesIO(b'[{"tag_name":"v0.5.2","html_url":"https://github.com/Raphazoc/assistente_ia/releases/tag/v0.5.2"}]')
        self.assertIsNone(atualizacoes.consultar("0.5.3", abrir=abrir))
        with self.assertRaisesRegex(ValueError, "Resposta inesperada"):
            atualizacoes.consultar("0.5.3", abrir=lambda *_a, **_k: io.BytesIO(b'{}'))

    def test_preferencia_de_verificacao_validada(self):
        self.assertTrue(configuracao.validar({})["verificar_atualizacoes"])
        self.assertFalse(configuracao.validar({"verificar_atualizacoes": False})["verificar_atualizacoes"])
        with self.assertRaisesRegex(ValueError, "verificar_atualizacoes"):
            configuracao.validar({"verificar_atualizacoes": "não"})

    def test_cancelar_consulta_nao_abre_rede(self):
        cancelar = threading.Event()
        cancelar.set()
        abrir = Mock()
        with self.assertRaises(atualizacoes.VerificacaoCancelada):
            atualizacoes.consultar(abrir=abrir, cancelar=cancelar)
        abrir.assert_not_called()

    def test_ultima_verificacao_persistida_sem_dados_privados(self):
        with tempfile.TemporaryDirectory() as pasta, \
                patch.object(atualizacoes, "ARQUIVO_ESTADO", Path(pasta) / "ultima.json"):
            estado = atualizacoes.salvar_ultima_verificacao("disponivel", {"versao": "v0.6.0"})
            self.assertEqual(atualizacoes.carregar_ultima_verificacao(), estado)
            conteudo = atualizacoes.ARQUIVO_ESTADO.read_text(encoding="utf-8")
            self.assertNotIn("chave", conteudo)
            self.assertNotIn("conversa", conteudo)
            atualizacoes.ARQUIVO_ESTADO.write_text(json.dumps({"status": "disponivel",
                "versao": "v9.0.0", "verificado_em": "X" * 500}), encoding="utf-8")
            self.assertIsNone(atualizacoes.carregar_ultima_verificacao())

    def test_instalador_exige_digest_assinatura_e_versao_mais_nova(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "AssistenteIA-Setup.exe"
            arquivo.write_bytes(b"instalador de teste")
            release = {"versao": "v9.0.0", "sha256": hashlib.sha256(arquivo.read_bytes()).hexdigest()}
            verificar = Mock(return_value=True)
            self.assertTrue(atualizacoes.verificar_instalador(arquivo, release, verificar))
            verificar.assert_called_once_with(arquivo)
            with self.assertRaisesRegex(ValueError, "downgrade"):
                atualizacoes.verificar_instalador(arquivo, {**release, "versao": "v0.1.0"}, verificar)
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                atualizacoes.verificar_instalador(arquivo, {**release, "sha256": "0" * 64}, verificar)
            with self.assertRaisesRegex(ValueError, "Authenticode"):
                atualizacoes.verificar_instalador(arquivo, release, Mock(return_value=False))
