import contextlib
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app import acoes
from app import internet
from app import main


class AcoesTests(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.raiz = Path(self.pasta.name)

    def tearDown(self):
        self.pasta.cleanup()

    def test_so_planeja_pedido_de_acao_direto(self):
        modelo = Mock()
        self.assertIsNone(acoes.planejar("Como abro o Bloco de Notas?", self.raiz, modelo))
        self.assertIsNone(acoes.planejar("Bom dia", self.raiz, modelo))
        modelo.assert_not_called()
        self.assertTrue(acoes.parece_pedido_de_acao("Pode abrir a calculadora?"))

    def test_programa_fora_da_lista_e_rejeitado_antes_da_confirmacao(self):
        modelo = Mock(return_value={"acao": "abrir_programa", "alvo": "powershell", "destino": ""})
        with self.assertRaises(ValueError):
            acoes.planejar("Abra o PowerShell", self.raiz, modelo)

    def test_caminho_fora_do_projeto_e_arquivo_protegido_sao_rejeitados(self):
        with self.assertRaises(ValueError):
            acoes.validar(acoes.PlanoAcao("ler_arquivo", str(self.raiz.parent / "segredo.txt")), self.raiz)
        (self.raiz / "main.py").write_text("print('oi')", encoding="utf-8")
        with self.assertRaises(ValueError):
            acoes.validar(acoes.PlanoAcao("mover_arquivo", "main.py", "backup.py"), self.raiz)
        (self.raiz / ".git").mkdir()
        with self.assertRaises(ValueError):
            acoes.validar(acoes.PlanoAcao("listar_pasta", ".git"), self.raiz)

    def test_mover_arquivo_exige_destino_livre(self):
        (self.raiz / "nota.txt").write_text("teste", encoding="utf-8")
        (self.raiz / "existente.txt").write_text("outro", encoding="utf-8")
        with self.assertRaises(ValueError):
            acoes.validar(acoes.PlanoAcao("mover_arquivo", "nota.txt", "existente.txt"), self.raiz)
        plano = acoes.validar(acoes.PlanoAcao("mover_arquivo", "nota.txt", "novo.txt"), self.raiz)
        acoes.executar(plano, self.raiz, Mock())
        self.assertFalse((self.raiz / "nota.txt").exists())
        self.assertEqual((self.raiz / "novo.txt").read_text(encoding="utf-8"), "teste")

    def test_leitura_nao_envia_conteudo_ao_modelo_ou_a_voz(self):
        (self.raiz / "nota.txt").write_text("conteúdo privado", encoding="utf-8")
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            resultado = acoes.executar(acoes.PlanoAcao("ler_arquivo", "nota.txt"), self.raiz, Mock())
        self.assertIn("conteúdo privado", saida.getvalue())
        self.assertNotIn("conteúdo privado", resultado)

    def test_listagem_fica_no_terminal(self):
        (self.raiz / "nota.txt").write_text("teste", encoding="utf-8")
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            resultado = acoes.executar(acoes.PlanoAcao("listar_pasta", "."), self.raiz, Mock())
        self.assertIn("nota.txt", saida.getvalue())
        self.assertNotIn("nota.txt", resultado)

    def test_recusa_nao_executa_acao_ou_acessa_rede(self):
        modelo = Mock(return_value={"acao": "abrir_site", "alvo": "https://www.python.org/", "destino": ""})
        with (
            patch.object(main, "gerar_json_pesquisa", side_effect=modelo),
            patch.object(main, "autorizar_acao", return_value=False),
            patch.object(internet, "baixar_html") as baixar,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertIn("cancelada", main.atender_acao("Abra https://www.python.org/"))
        baixar.assert_not_called()

    def test_site_exige_classificacao_antes_de_abrir_navegador(self):
        plano = acoes.PlanoAcao("abrir_site", "https://www.python.org/")
        html = b"<main>" + b"Guia publico de programacao Python. " * 10 + b"</main>"
        with (
            patch.object(internet, "baixar_html", return_value=(plano.alvo, html)),
            patch.object(internet, "filtrar_fontes", return_value=[]) as filtrar,
            patch.object(acoes.webbrowser, "open") as abrir,
        ):
            with self.assertRaises(ValueError):
                acoes.executar(plano, self.raiz, Mock())
        filtrar.assert_called_once()
        abrir.assert_not_called()

    def test_confirmacao_por_voz_exige_frase_exata(self):
        plano = acoes.PlanoAcao("abrir_programa", "calculadora")
        with (
            patch.object(main, "reconhecer_voz", side_effect=["confirmo qualquer coisa", "Confirmo!"]),
            patch("app.fala.falar"),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertFalse(main.autorizar_acao(plano, modo_voz=True))
            self.assertTrue(main.autorizar_acao(plano, modo_voz=True))

    def test_fluxo_completo_de_acao_nao_chama_pesquisa_ou_resposta_comum(self):
        banco = self.raiz / "memoria.db"
        plano = {"acao": "listar_pasta", "alvo": ".", "destino": ""}
        with (
            patch.object(main, "BANCO", banco),
            patch.object(main, "indexar_memorias_antigas"),
            patch.object(main, "indexar_nova_mensagem"),
            patch.object(main, "gerar_json_pesquisa", return_value=plano),
            patch.object(main, "ler_texto", side_effect=["1", "Liste a pasta .", "sair"]),
            patch.object(main, "autorizar_acao", return_value=True),
            patch.object(acoes, "executar", return_value="Pasta listada."),
            patch.object(main, "preparar_pesquisa") as pesquisa,
            patch.object(main, "obter_resposta") as responder,
            contextlib.redirect_stdout(io.StringIO()) as saida,
        ):
            main.main()
        pesquisa.assert_not_called()
        responder.assert_not_called()
        self.assertIn("Pasta listada.", saida.getvalue())
        with contextlib.closing(sqlite3.connect(banco)) as conexao:
            self.assertEqual(conexao.execute("SELECT papel FROM mensagens ORDER BY id").fetchall(), [("user",), ("assistant",)])


if __name__ == "__main__":
    unittest.main()
