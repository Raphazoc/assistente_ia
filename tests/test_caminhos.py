"""Desktop, terminal e comandos de manutenção devem apontar para a mesma memória."""

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import banco, caminhos, main


class CaminhosTests(unittest.TestCase):
    def test_banco_padrao_do_motor_usa_o_helper(self):
        self.assertEqual(main.BANCO, caminhos.caminho_banco())

    def test_pasta_windows_respeita_localappdata(self):
        if os.name != "nt":
            self.skipTest("Caminho LOCALAPPDATA é específico do Windows")
        with tempfile.TemporaryDirectory() as temporario, patch.dict(os.environ, {"LOCALAPPDATA": temporario}):
            esperado = Path(temporario) / "AssistenteIA" / "memoria.db"
            self.assertEqual(caminhos.caminho_banco(), esperado)

    def test_cli_lista_backups_da_pasta_do_desktop(self):
        with tempfile.TemporaryDirectory() as temporario:
            caminho = Path(temporario) / "AssistenteIA" / "memoria.db"
            saida = io.StringIO()
            with patch.object(caminhos, "caminho_banco", return_value=caminho), \
                    patch.object(sys, "argv", ["banco", "listar"]), contextlib.redirect_stdout(saida):
                banco.main()
            self.assertIn("Nenhum backup", saida.getvalue())

