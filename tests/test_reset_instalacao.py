"""A instalação limpa apenas a memória e impede a reimportação automática."""

import contextlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import aplicativo, ativacao, configuracao, diagnostico, fala, internet, main, servicos


class ResetInstalacaoTests(unittest.TestCase):
    def test_marcador_remove_banco_diarios_e_backups_mas_preserva_configuracao(self):
        with tempfile.TemporaryDirectory() as temporario:
            dados = Path(temporario) / "AssistenteIA"
            dados.mkdir()
            for nome in ("memoria.db", "memoria.db-wal", "memoria.db-shm",
                         "memoria.db-journal", "memoria_antes_v2_20261018_120000_123456_UTC.db"):
                (dados / nome).write_bytes(b"memoria antiga")
            (dados / "backups").mkdir()
            (dados / "backups" / "automatico_20261018T120000Z_12345678.db").write_bytes(b"backup")
            (dados / "config_geral.json").write_text("preferencias", encoding="utf-8")
            (dados / "reiniciar_memoria.flag").write_text("reset", encoding="utf-8")

            self.assertTrue(aplicativo._reiniciar_memoria_apos_instalacao(dados))
            self.assertFalse(any(dados.glob("memoria*.db*")))
            self.assertFalse((dados / "backups").exists())
            self.assertFalse((dados / "reiniciar_memoria.flag").exists())
            self.assertEqual((dados / "config_geral.json").read_text(encoding="utf-8"), "preferencias")
            self.assertFalse(aplicativo._reiniciar_memoria_apos_instalacao(dados))

    def test_sem_marcador_memoria_persiste_e_banco_legado_nao_volta(self):
        with tempfile.TemporaryDirectory() as temporario:
            base = Path(temporario)
            (base / "antigo" / "app").mkdir(parents=True)
            (base / "antigo" / "memoria.db").write_bytes(b"memoria legada")
            (base / "home").mkdir()
            local = base / "local"
            with contextlib.ExitStack() as ajustes:
                ajustes.enter_context(patch.dict(os.environ, {"LOCALAPPDATA": str(local)}))
                ajustes.enter_context(patch.object(aplicativo.Path, "home", return_value=base / "home"))
                ajustes.enter_context(patch.object(
                    aplicativo, "__file__", str(base / "antigo" / "app" / "aplicativo.py")))
                for modulo, atributo in ((main, "BANCO"), (main, "PASTA_PROJETO"),
                                         (ativacao, "CONFIGURACAO"), (internet, "CONFIGURACAO"),
                                         (servicos, "CONFIGURACAO"), (configuracao, "CONFIGURACAO"),
                                         (diagnostico, "PASTA_LOGS"), (fala, "MODELO_VOZ")):
                    ajustes.enter_context(patch.object(modulo, atributo, getattr(modulo, atributo)))
                dados, _ = aplicativo.preparar_arquivos_usuario()
                self.assertFalse((dados / "memoria.db").exists())
                (dados / "memoria.db").write_bytes(b"memoria nova")
                aplicativo.preparar_arquivos_usuario()
                self.assertEqual((dados / "memoria.db").read_bytes(), b"memoria nova")

    def test_marcador_permanece_se_backup_nao_puder_ser_removido(self):
        with tempfile.TemporaryDirectory() as temporario:
            dados = Path(temporario) / "AssistenteIA"
            dados.mkdir()
            (dados / "reiniciar_memoria.flag").write_text("reset", encoding="utf-8")
            (dados / "backups").write_text("pasta inválida", encoding="utf-8")
            with self.assertRaises(OSError):
                aplicativo._reiniciar_memoria_apos_instalacao(dados)
            self.assertTrue((dados / "reiniciar_memoria.flag").exists())


if __name__ == "__main__":
    unittest.main()
