import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class MemoriaPersistenteTests(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.banco = Path(self.pasta.name) / "memoria.db"
        self.configuracao = patch.object(main, "BANCO", self.banco)
        self.configuracao.start()
        self.conexao = main.iniciar_banco()

    def tearDown(self):
        self.conexao.close()
        self.configuracao.stop()
        self.pasta.cleanup()

    def salvar(self, papel, conteudo):
        with self.conexao:
            cursor = self.conexao.execute(
                "INSERT INTO mensagens (papel, conteudo) VALUES (?, ?)",
                (papel, conteudo),
            )
        return cursor.lastrowid

    def test_reinicio_recupera_assuntos_sem_repetir_negativas_antigas(self):
        self.salvar("user", "Estou criando uma IA com Python e SQLite.")
        negativa = "Infelizmente, não tenho memória de conversas anteriores."
        self.salvar("assistant", negativa)
        self.conexao.close()

        # Simula outra execução, que deve ler o mesmo arquivo em disco.
        self.conexao = sqlite3.connect(self.banco)
        with (
            patch.object(main, "indexar_memorias_antigas"),
            patch.object(main, "indexar_nova_mensagem"),
            patch.object(main, "embed", return_value={"embeddings": [[1, 0]]}),
            patch.object(main, "chat", return_value={
                "message": {"content": "Falamos sobre sua IA em Python."}
            }) as chat,
            patch.object(main, "ler_texto", side_effect=[
                "1", "Sobre o que conversamos?", "sair"
            ]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            main.main()

        mensagens = chat.call_args.kwargs["messages"]
        self.assertEqual([m["role"] for m in mensagens], ["system", "user"])
        self.assertIn("Estou criando uma IA com Python e SQLite.", mensagens[0]["content"])
        self.assertNotIn(negativa, mensagens[0]["content"])
        self.assertEqual(mensagens[-1]["content"], "Sobre o que conversamos?")

    def test_busca_semantica_recupera_fato_fora_das_conversas_recentes(self):
        identificador = self.salvar("user", "Meu projeto antigo se chama Aurora.")
        with self.conexao:
            self.conexao.execute(
                "INSERT INTO vetores_memoria VALUES (?, ?, ?)",
                (identificador, main.MODELO_MEMORIA, json.dumps([1, 0])),
            )
        for numero in range(main.LIMITE_HISTORICO + 2):
            self.salvar("user", f"Assunto recente {numero}.")

        with (
            patch.object(main, "embed", return_value={"embeddings": [[1, 0]]}),
            patch.object(main, "chat", return_value={
                "message": {"content": "Aurora"}
            }) as chat,
        ):
            main.obter_resposta(self.conexao, [], "Qual é o nome do meu projeto antigo?")

        contexto = chat.call_args.kwargs["messages"][0]["content"]
        self.assertIn("Outras conversas relacionadas", contexto)
        self.assertIn("Meu projeto antigo se chama Aurora.", contexto)
        self.assertIn(f"Assunto recente {main.LIMITE_HISTORICO + 1}.", contexto)

    def test_falha_nos_embeddings_mantem_memoria_recente(self):
        self.salvar("user", "Meu código de teste é violeta 123.")
        with (
            patch.object(main, "embed", side_effect=RuntimeError("Offline")),
            patch.object(main, "chat", return_value={
                "message": {"content": "violeta 123"}
            }) as chat,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            resposta = main.obter_resposta(self.conexao, [], "Qual é meu código?")

        self.assertEqual(resposta, "violeta 123")
        self.assertIn(
            "Meu código de teste é violeta 123.",
            chat.call_args.kwargs["messages"][0]["content"],
        )

    def test_falha_na_indexacao_nao_impede_inicializacao(self):
        self.salvar("user", "Conversa que ainda não foi indexada.")
        saida = io.StringIO()
        with (
            patch.object(main, "indexar_memorias_antigas", side_effect=RuntimeError("Offline")),
            patch.object(main, "ler_texto", side_effect=["1", "sair"]),
            contextlib.redirect_stdout(saida),
        ):
            main.main()

        self.assertIn("IA iniciada com sucesso!", saida.getvalue())
        self.assertIn("Indexação semântica pendente", saida.getvalue())
        self.assertNotIn("Memória semântica ativada.", saida.getvalue())

    def test_resposta_longa_nao_esvazia_historico_da_sessao(self):
        historico = [
            {"role": "user", "content": "Explique o assunto."},
            {"role": "assistant", "content": "x" * (main.MAX_CARACTERES_HISTORICO + 1)},
            {"role": "user", "content": "Continue."},
        ]
        preparado = main.preparar_historico(historico)

        self.assertEqual(preparado[-1], historico[-1])
        self.assertEqual(preparado[0]["role"], "assistant")
        self.assertEqual(
            sum(len(m["content"]) for m in preparado),
            main.MAX_CARACTERES_HISTORICO,
        )
        self.assertEqual(len(historico[1]["content"]), main.MAX_CARACTERES_HISTORICO + 1)

    def test_banco_vazio_e_tratado_sem_inventar_registros(self):
        with (
            patch.object(main, "embed", return_value={"embeddings": [[1, 0]]}),
            patch.object(main, "chat", return_value={
                "message": {"content": "Ainda não há registros."}
            }) as chat,
        ):
            main.obter_resposta(self.conexao, [], "O que conversamos?")

        self.assertIn(
            "Ainda não há conversas anteriores salvas no SQLite.",
            chat.call_args.kwargs["messages"][0]["content"],
        )

    def test_fato_do_usuario_e_salvo_mesmo_quando_a_resposta_falha(self):
        with (
            patch.object(main, "indexar_memorias_antigas"),
            patch.object(main, "chat", side_effect=RuntimeError("Modelo offline")),
            patch.object(main, "ler_texto", side_effect=["1", "Meu nome é Elisa.", "sair"]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            main.main()
        self.assertEqual(
            self.conexao.execute("SELECT conteudo FROM memorias").fetchone()[0], "Meu nome é Elisa."
        )
        self.assertEqual(self.conexao.execute("SELECT COUNT(*) FROM mensagens").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
