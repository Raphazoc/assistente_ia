"""Cenários de inicialização e recuperação com componentes reais e rede simulada."""

import contextlib
import io
import os
import queue
import sqlite3
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

from ollama import ResponseError

from app import aplicativo, ativacao, configuracao, diagnostico, diagnostico_inicial
from app import fala, internet, main, memoria, servicos


class IntegracaoTests(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory()
        self.pasta = Path(self.temporario.name)
        self.patches = [
            patch.object(main, "BANCO", self.pasta / "memoria.db"),
            patch.object(diagnostico, "PASTA_LOGS", self.pasta / "logs"),
            patch.object(internet, "CONFIGURACAO", self.pasta / "internet.json"),
        ]
        for ajuste in self.patches:
            ajuste.start()
        internet.definir_habilitada(True)

    def tearDown(self):
        diagnostico.encerrar()
        for ajuste in reversed(self.patches):
            ajuste.stop()
        self.temporario.cleanup()

    def _banco_sem_memoria(self):
        conexao = main.iniciar_banco()
        memoria.definir_habilitada(conexao, False)
        return conexao

    def test_instalacao_simulada_copia_recursos_e_preserva_dados_na_reabertura(self):
        pacote = self.pasta / "pacote"
        recursos = pacote / "resources"
        recursos.mkdir(parents=True)
        for nome in ("config_voz.json", "config_internet.json", "config_servicos.json", "config_geral.json"):
            origem = Path(__file__).resolve().parents[1] / "resources" / nome
            (recursos / nome).write_bytes(origem.read_bytes())
        (recursos / "vozes").mkdir()
        (recursos / "vozes" / "pt_BR-faber-medium.onnx").write_bytes(b"modelo de teste")
        usuario = self.pasta / "usuario"
        usuario.mkdir()
        local = self.pasta / "local"
        with contextlib.ExitStack() as ajustes:
            ajustes.enter_context(patch.dict(os.environ, {"LOCALAPPDATA": str(local)}))
            ajustes.enter_context(patch.object(aplicativo.Path, "home", return_value=usuario))
            ajustes.enter_context(patch.object(aplicativo, "__file__", str(self.pasta / "instalado" / "app" / "aplicativo.py")))
            ajustes.enter_context(patch.object(aplicativo.sys, "_MEIPASS", str(pacote), create=True))
            ajustes.enter_context(patch.object(aplicativo.sys, "frozen", True, create=True))
            for modulo, atributo in ((main, "BANCO"), (main, "PASTA_PROJETO"),
                                     (ativacao, "CONFIGURACAO"), (internet, "CONFIGURACAO"),
                                     (servicos, "CONFIGURACAO"), (configuracao, "CONFIGURACAO"),
                                     (diagnostico, "PASTA_LOGS"), (fala, "MODELO_VOZ")):
                ajustes.enter_context(patch.object(modulo, atributo, getattr(modulo, atributo)))
            dados, trabalho = aplicativo.preparar_arquivos_usuario()
            self.assertEqual(dados, local / "AssistenteIA")
            self.assertEqual(trabalho, usuario / "Documents" / "AssistenteIA")
            self.assertFalse(configuracao.carregar()["configurado"])
            self.assertEqual(fala.MODELO_VOZ, recursos / "vozes" / "pt_BR-faber-medium.onnx")
            with contextlib.closing(main.iniciar_banco()) as conexao:
                conexao.execute("INSERT INTO mensagens(papel,conteudo) VALUES ('user','dado persistente')")
                conexao.commit()
            internet.definir_habilitada(False)
            aplicativo.preparar_arquivos_usuario()
            self.assertFalse(internet.habilitada())
            with contextlib.closing(main.iniciar_banco()) as conexao:
                self.assertEqual(conexao.execute("SELECT conteudo FROM mensagens").fetchone()[0], "dado persistente")

    def test_banco_corrompido_e_preservado_e_pode_ser_substituido_apos_fechar(self):
        original = b"banco corrompido - conteudo privado"
        main.BANCO.write_bytes(original)
        with self.assertRaises(sqlite3.DatabaseError):
            main.iniciar_banco()
        self.assertEqual(main.BANCO.read_bytes(), original)
        main.BANCO.unlink()  # Falha de abertura não deve deixar o arquivo preso no Windows.
        with contextlib.closing(main.iniciar_banco()) as conexao:
            self.assertIn("mensagens", {r[0] for r in conexao.execute("SELECT name FROM sqlite_master")})

    def test_falha_inicial_do_banco_emite_orientacao_sem_dados_privados(self):
        motor = aplicativo.MotorDesktop(queue.Queue())
        with (
            patch.object(aplicativo, "preparar_arquivos_usuario"),
            patch.object(main, "iniciar_banco", side_effect=sqlite3.DatabaseError("segredo pessoal")),
        ):
            motor._rodar()
        eventos = list(motor.eventos.queue)
        falhas = [evento[1] for evento in eventos if evento[0] == "fatal"]
        self.assertEqual(len(falhas), 1)
        self.assertIn("memória local", falhas[0])
        self.assertNotIn("segredo pessoal", falhas[0])

    def test_modelo_ausente_gera_erro_amigavel_e_proxima_pergunta_funciona(self):
        with contextlib.closing(self._banco_sem_memoria()) as conexao:
            motor = aplicativo.MotorDesktop(queue.Queue())
            historico = []
            with (
                patch.object(main, "atender_acao", return_value=None),
                patch.object(main, "preparar_pesquisa", return_value=None),
                patch.object(main, "chat", side_effect=[
                    ResponseError("mensagem privada", status_code=404),
                    {"message": {"content": "Resposta recuperada."}},
                ]),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                motor._responder(conexao, historico, "texto", "Primeira pergunta")
                motor._responder(conexao, historico, "texto", "Segunda pergunta")
            eventos = list(motor.eventos.queue)
            erros = [evento[3] for evento in eventos if evento[:3] == ("mensagem", "texto", "Erro")]
            respostas = [evento[3] for evento in eventos if evento[:3] == ("mensagem", "texto", "IA")]
            self.assertEqual(len(erros), 1)
            self.assertIn("modelo escolhido está ausente", erros[0])
            self.assertNotIn("mensagem privada", erros[0])
            self.assertEqual(respostas, ["Resposta recuperada."])
            self.assertEqual(conexao.execute("SELECT papel FROM mensagens ORDER BY id").fetchall(),
                             [("user",), ("user",), ("assistant",)])

    def test_pesquisa_sem_rede_informa_limite_e_preserva_resposta_local(self):
        with contextlib.closing(self._banco_sem_memoria()) as conexao:
            motor = aplicativo.MotorDesktop(queue.Queue())
            historico = []
            plano = {"pesquisar": True, "motivo": "Verificar fonte atual",
                     "consultas": ["documentação oficial do Python"]}
            with (
                patch.object(main, "atender_acao", return_value=None),
                patch.object(main, "gerar_json_pesquisa", return_value=plano),
                patch.object(motor, "_autorizar_pesquisa", return_value=True) as autorizar,
                patch.object(internet, "buscar_web", side_effect=OSError("falha com segredo")) as buscar,
                patch.object(main, "chat", return_value={"message": {"content": "Resposta local, sem dado atual."}}),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                motor._responder(conexao, historico, "texto", "Pesquise Python")
            autorizar.assert_called_once()
            buscar.assert_called_once_with("documentação oficial do Python")
            resposta = conexao.execute("SELECT conteudo FROM mensagens WHERE papel='assistant'").fetchone()[0]
            self.assertIn("Sem pesquisa online:", resposta)
            self.assertIn("Resposta local", resposta)
            self.assertNotIn("Fontes consultadas:", resposta)
            self.assertNotIn("segredo", resposta)

    def test_falha_da_api_mantem_fontes_do_buscador_alternativo_no_historico(self):
        with contextlib.closing(self._banco_sem_memoria()) as conexao:
            motor = aplicativo.MotorDesktop(queue.Queue())
            fonte = internet.Fonte("Python oficial", "https://www.python.org/doc/",
                                   "Documentação oficial.", provedor="DuckDuckGo")
            def estruturar(_sistema, _dados, schema):
                if schema is internet.SCHEMA_PLANO:
                    return {"pesquisar": True, "motivo": "Verificar Python",
                            "consultas": ["documentação oficial Python"]}
                return {"permitidos": [0]}
            with (
                patch.object(main, "atender_acao", return_value=None),
                patch.object(main, "gerar_json_pesquisa", side_effect=estruturar),
                patch.object(motor, "_autorizar_pesquisa", return_value=True),
                patch.object(servicos, "carregar", return_value={"buscador": "brave"}),
                patch.object(internet, "buscar_brave", side_effect=HTTPError("https://api.search.brave.com", 429, "limite", {}, None)),
                patch.object(internet, "buscar_duckduckgo", return_value=[fonte]) as alternativa,
                patch.object(internet, "baixar_html", side_effect=internet.LeituraIndisponivel("HTTP 403")),
                patch.object(main, "chat", return_value={"message": {"content": "A documentação confirma [1]."}}),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                motor._responder(conexao, [], "texto", "Pesquise documentação Python")
            alternativa.assert_called_once_with("documentação oficial Python")
            resposta = conexao.execute("SELECT conteudo FROM mensagens WHERE papel='assistant'").fetchone()[0]
            self.assertIn("Buscador alternativo: DuckDuckGo", resposta)
            self.assertIn("[Python oficial](https://www.python.org/doc/)", resposta)
            self.assertIn("resumo do buscador", resposta)

    def test_primeira_abertura_sem_ollama_mantem_motor_parado(self):
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Ambiente sem interface gráfica")
        raiz.withdraw()
        with (
            patch.object(aplicativo, "preparar_arquivos_usuario"),
            patch.object(configuracao, "carregar", return_value=configuracao.PADRAO.copy()),
            patch.object(aplicativo.MotorDesktop, "iniciar") as iniciar,
            patch.object(diagnostico_inicial, "verificar", return_value={
                "ollama_instalado": False, "ollama_ativo": False, "ollama_versao": "",
                "modelos": [], "microfone": False, "alto_falante": False,
                "python": "3.13", "erro_ollama": "ConnectionRefusedError",
            }),
            patch.object(servicos, "obter_chave", return_value=""),
        ):
            janela = aplicativo.JanelaAssistente(raiz, iniciar_motor=True)
            try:
                def aguardar_diagnostico():
                    if janela.assistente is not None and janela.assistente.resultado is not None:
                        raiz.quit()
                    else:
                        raiz.after(40, aguardar_diagnostico)
                raiz.after(40, aguardar_diagnostico)
                raiz.after(3000, raiz.quit)
                raiz.mainloop()
                self.assertFalse(janela.motor_iniciado)
                iniciar.assert_not_called()
                self.assertIsNotNone(janela.assistente)
                self.assertIn("Primeira execução", janela.assistente.janela.title())
                self.assertIn("indisponível", janela.assistente.diagnostico.get("1.0", "end"))
            finally:
                janela.fechar()

    def test_configuracao_invalida_abre_correcao_sem_iniciar_conversa(self):
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Ambiente sem interface gráfica")
        raiz.withdraw()
        arquivo = self.pasta / "config_geral.json"
        arquivo.write_text('{"modelo": "modelo\nquebrado"}', encoding="utf-8")
        with (
            patch.object(aplicativo, "preparar_arquivos_usuario"),
            patch.object(configuracao, "CONFIGURACAO", arquivo),
            patch.object(aplicativo.MotorDesktop, "iniciar") as iniciar,
            patch.object(diagnostico_inicial, "verificar", return_value={
                "ollama_instalado": False, "ollama_ativo": False, "ollama_versao": "",
                "modelos": [], "microfone": False, "alto_falante": False,
                "python": "3.13", "erro_ollama": "ConnectionRefusedError",
            }),
            patch.object(servicos, "obter_chave", return_value=""),
        ):
            janela = aplicativo.JanelaAssistente(raiz, iniciar_motor=True)
            try:
                raiz.after(220, raiz.quit)
                raiz.mainloop()
                iniciar.assert_not_called()
                self.assertIsNotNone(janela.assistente)
                self.assertIn("config_geral.json", janela.estado["text"])
            finally:
                janela.fechar()


if __name__ == "__main__":
    unittest.main()
