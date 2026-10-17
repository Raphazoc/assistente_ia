import queue
import sqlite3
import unittest
from unittest.mock import patch

import httpx

from app import aplicativo, erros


class ErrosTests(unittest.TestCase):
    def test_mensagens_orientam_sem_reproduzir_segredos(self):
        casos = (
            (httpx.ConnectError("api_key=segredo123"), "conversa", "Ollama"),
            (sqlite3.DatabaseError("conteudo_privado"), "inicio", "memória local"),
            (OSError("microfone secreto"), "microfone", "microfone"),
            (RuntimeError("token=segredo123"), "conversa", "Diagnóstico"),
        )
        for excecao, contexto, esperado in casos:
            with self.subTest(contexto=contexto, tipo=type(excecao).__name__):
                mensagem = erros.orientar(excecao, contexto)
                self.assertIn(esperado, mensagem)
                self.assertNotIn("segredo123", mensagem)
                self.assertNotIn("conteudo_privado", mensagem)

    def test_falha_de_resposta_nao_expoe_excecao_na_interface(self):
        eventos = queue.Queue()
        motor = aplicativo.MotorDesktop(eventos)
        segredo = "minha-chave-privada-123"
        with patch.object(aplicativo.memoria, "tratar_comando", return_value=None), \
             patch.object(aplicativo.main, "salvar_mensagem", return_value=1), \
             patch.object(aplicativo.main, "atender_acao", side_effect=RuntimeError(segredo)), \
             patch.object(aplicativo.diagnostico, "registrar"):
            motor._responder(object(), [], "texto", "pergunta de teste")
        mensagens = []
        while not eventos.empty():
            evento = eventos.get_nowait()
            if evento[0] == "mensagem" and evento[2] == "Erro":
                mensagens.append(evento[3])
        self.assertEqual(len(mensagens), 1)
        self.assertNotIn(segredo, mensagens[0])

    def test_falha_de_inicio_emite_orientacao_segura_para_interface(self):
        eventos = queue.Queue()
        motor = aplicativo.MotorDesktop(eventos)
        with patch.object(aplicativo, "preparar_arquivos_usuario", side_effect=OSError("senha123")), \
             patch.object(aplicativo.diagnostico, "registrar") as registrar:
            motor._rodar()
        tipo, mensagem = eventos.get_nowait()
        self.assertEqual(tipo, "fatal")
        self.assertIn("Diagnóstico", mensagem)
        self.assertNotIn("senha123", mensagem)
        registrar.assert_called_once()
        self.assertEqual(registrar.call_args.args[0], "conversa.inicializacao_falhou")


if __name__ == "__main__":
    unittest.main()
