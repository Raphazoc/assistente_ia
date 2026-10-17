import contextlib
import io
import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app import controles
from app import main
from app import memoria


class MenuTests(unittest.TestCase):
    def test_esc_na_digitacao_solicita_menu_sem_enter(self):
        teclado = SimpleNamespace(getwch=MagicMock(side_effect=["o", "i", "\x1b"]))
        with (
            patch.object(controles.sys.stdin, "isatty", return_value=True),
            patch.dict("sys.modules", {"msvcrt": teclado}),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            with self.assertRaises(controles.SolicitarMenu):
                controles.ler_texto("Você: ")

    def test_digitacao_aceita_acentos_e_corrige_com_backspace(self):
        teclado = SimpleNamespace(getwch=MagicMock(side_effect=list("olx\bá\r")))
        with (
            patch.object(controles.sys.stdin, "isatty", return_value=True),
            patch.dict("sys.modules", {"msvcrt": teclado}),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(controles.ler_texto("Você: "), "olá")

    def test_menu_valida_opcao_e_permite_manter_modo_atual(self):
        with (
            patch.object(main, "ler_texto", side_effect=["inválido", "0"]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(main.escolher_modo("voz"), "voz")

    def test_esc_no_menu_cancela_sem_alterar_modo(self):
        with (
            patch.object(main, "ler_texto", side_effect=controles.SolicitarMenu),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(main.escolher_modo("texto"), "texto")

    def executar_troca(self, entradas, capturas):
        conexao = sqlite3.connect(":memory:")
        conexao.execute(
            "CREATE TABLE mensagens (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "papel TEXT, conteudo TEXT, data TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        conexao.execute(
            "CREATE TABLE vetores_memoria (mensagem_id INTEGER, modelo TEXT, "
            "vetor TEXT, PRIMARY KEY (mensagem_id, modelo))"
        )
        memoria.iniciar_estrutura(conexao)
        with (
            patch.object(main, "iniciar_banco", return_value=conexao),
            patch.object(main, "indexar_memorias_antigas"),
            patch.object(main, "preparar_pesquisa", return_value=None),
            patch.object(main, "aquecer_voz"),
            patch.object(main, "carregar_historico", return_value=[]),
            patch.object(main, "ler_texto", side_effect=entradas),
            patch.object(main, "reconhecer_voz", side_effect=capturas) as reconhecer,
            patch.object(main, "obter_resposta") as responder,
            patch.object(main, "salvar_mensagem") as salvar,
            contextlib.redirect_stdout(io.StringIO()) as saida,
        ):
            main.main()
        responder.assert_not_called()
        salvar.assert_not_called()
        return saida.getvalue(), reconhecer.call_count

    def test_esc_no_audio_abre_menu_e_troca_para_digitacao(self):
        saida, chamadas = self.executar_troca(
            ["2", "1", "sair"], [controles.SolicitarMenu()]
        )
        self.assertIn("Modo texto ativado.", saida)
        self.assertEqual(saida.count("MODO DE CONVERSA"), 2)
        self.assertEqual(chamadas, 1)

    def test_esc_na_digitacao_abre_menu_e_troca_para_audio(self):
        saida, chamadas = self.executar_troca(
            ["1", controles.SolicitarMenu(), "2"], ["Aurora, sair"]
        )
        self.assertIn("Modo microfone ativado.", saida)
        self.assertEqual(chamadas, 1)

    def test_menu_pode_retornar_ao_audio_sem_trocar(self):
        saida, chamadas = self.executar_troca(
            ["2", "0"], [controles.SolicitarMenu(), "Aurora, sair"]
        )
        self.assertNotIn("Modo texto ativado.", saida)
        self.assertEqual(chamadas, 2)

    def test_opcao_sair_fecha_a_ia_antes_de_iniciar_conversa(self):
        saida, chamadas = self.executar_troca(["6"], [])
        self.assertIn("6 - Sair (fechar a IA)", saida)
        self.assertIn("IA encerrada.", saida)
        self.assertEqual(chamadas, 0)

    def test_opcao_sair_funciona_apos_esc_no_modo_voz(self):
        saida, chamadas = self.executar_troca(
            ["2", "6"], [controles.SolicitarMenu()]
        )
        self.assertIn("Até a próxima!", saida)
        self.assertIn("IA encerrada.", saida)
        self.assertEqual(chamadas, 1)


if __name__ == "__main__":
    unittest.main()
