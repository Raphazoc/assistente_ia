import queue
import sqlite3
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app import aplicativo, banco, main, memoria, memoria_ui, renderizacao


class MemoriaGerenciavelTests(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = Path(self.pasta.name) / "memoria.db"
        self.patch_banco = patch.object(main, "BANCO", self.caminho)
        self.patch_banco.start()
        self.conexao = main.iniciar_banco()

    def tearDown(self):
        self.conexao.close()
        self.patch_banco.stop()
        self.pasta.cleanup()

    def test_painel_separa_lembrancas_preferencias_historico_e_resumos(self):
        fato = memoria.guardar(self.conexao, "Meu nome é Ana.")
        preferencia = memoria.guardar(self.conexao, "Prefiro respostas curtas.")
        main.salvar_mensagem(self.conexao, "user", "Como vai?")
        painel = memoria.painel(self.conexao)
        tipos = {r["id"]: r["tipo"] for r in painel["lembrancas"]}
        self.assertEqual(tipos[fato], "fato")
        self.assertEqual(tipos[preferencia], "preferencia")
        self.assertEqual(painel["total_historico"], 1)
        memoria.editar(self.conexao, fato, "Meu nome é Ana Maria.", tipo="preferencia")
        self.assertEqual(next(r["tipo"] for r in memoria.painel(self.conexao)["lembrancas"] if r["id"] == fato), "preferencia")

    def test_desativar_memoria_mantem_historico_sem_recuperar_fatos(self):
        memoria.guardar(self.conexao, "Meu nome é Ana.")
        memoria.definir_habilitada(self.conexao, False)
        identificador = main.salvar_mensagem(self.conexao, "user", "Meu projeto se chama Secreto.")
        self.assertEqual(self.conexao.execute("SELECT ignorar_memoria FROM mensagens WHERE id=?", (identificador,)).fetchone(), (1,))
        self.assertEqual(memoria.recentes(self.conexao), [])
        self.assertEqual(memoria.preferencias_de_estilo(self.conexao), [])
        with patch.object(main, "buscar_memorias") as buscar, \
             patch.object(main, "chat", return_value={"message": {"content": "Resposta."}}) as chat:
            main.obter_resposta(self.conexao, [{"role": "user", "content": "Frase da sessão"}], "Pergunta?")
        buscar.assert_not_called()
        self.assertNotIn("Meu nome é Ana", chat.call_args.kwargs["messages"][0]["content"])
        self.assertIn("Frase da sessão", repr(chat.call_args.kwargs["messages"]))
        memoria.definir_habilitada(self.conexao, True)
        self.assertEqual(self.conexao.execute("SELECT ignorar_memoria FROM mensagens WHERE id=?", (identificador,)).fetchone(), (1,))

    def test_nao_usar_troca_remove_fontes_e_resumos_da_recuperacao(self):
        pergunta = main.salvar_mensagem(self.conexao, "user", "Meu nome é Ana.")
        resposta = main.salvar_mensagem(self.conexao, "assistant", "Olá, Ana.")
        with self.conexao:
            self.conexao.execute("INSERT INTO resumos_conversa(inicio_id,fim_id,conteudo) VALUES (?,?,?)",
                                 (pergunta, resposta, "Resumo antigo"))
        memoria.nao_usar_troca(self.conexao, pergunta)
        self.assertEqual(self.conexao.execute("SELECT ignorar_memoria FROM mensagens WHERE id=?", (pergunta,)).fetchone(), (1,))
        self.assertEqual(self.conexao.execute("SELECT ignorar_memoria FROM mensagens WHERE id=?", (resposta,)).fetchone(), (1,))
        self.assertEqual(memoria.painel(self.conexao)["total_lembrancas"], 0)
        self.assertEqual(self.conexao.execute("SELECT COUNT(*) FROM resumos_conversa").fetchone(), (0,))
        self.assertEqual(memoria.painel(self.conexao)["total_historico"], 2)

    def test_selecionar_resposta_tambem_retira_pergunta_da_memoria(self):
        pergunta = main.salvar_mensagem(self.conexao, "user", "Meu nome é Ana.")
        resposta = main.salvar_mensagem(self.conexao, "assistant", "Olá, Ana.")
        memoria.nao_usar_troca(self.conexao, resposta)
        estados = self.conexao.execute(
            "SELECT id,ignorar_memoria FROM mensagens WHERE id IN (?,?) ORDER BY id", (pergunta, resposta)
        ).fetchall()
        self.assertEqual(estados, [(pergunta, 1), (resposta, 1)])
        self.assertEqual(memoria.painel(self.conexao)["total_lembrancas"], 0)

    def test_apagar_tudo_limpa_banco_ativo(self):
        memoria.guardar(self.conexao, "Prefiro respostas curtas.")
        main.salvar_mensagem(self.conexao, "user", "Olá")
        memoria.apagar_tudo(self.conexao)
        painel = memoria.painel(self.conexao)
        self.assertEqual(painel["total_lembrancas"], 0)
        self.assertEqual(painel["total_historico"], 0)
        self.assertEqual(painel["resumos"], [])

    def test_migracao_classifica_preferencias_antigas(self):
        legado = sqlite3.connect(Path(self.pasta.name) / "legado.db")
        try:
            legado.execute("CREATE TABLE mensagens(id INTEGER PRIMARY KEY, papel TEXT, conteudo TEXT)")
            legado.execute("""CREATE TABLE memorias(
                id INTEGER PRIMARY KEY, conteudo TEXT NOT NULL, normalizado TEXT NOT NULL,
                assunto TEXT NOT NULL DEFAULT 'geral', projeto TEXT NOT NULL DEFAULT '',
                importancia INTEGER NOT NULL DEFAULT 3, chave TEXT, criada_em TEXT DEFAULT CURRENT_TIMESTAMP,
                atualizada_em TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(normalizado,assunto,projeto))""")
            legado.execute("INSERT INTO memorias(conteudo,normalizado) VALUES (?,?)",
                           ("Prefiro respostas curtas.", "prefiro respostas curtas"))
            memoria.iniciar_estrutura(legado)
            self.assertEqual(legado.execute("SELECT tipo FROM memorias").fetchone(), ("preferencia",))
        finally:
            legado.close()

    def test_envio_nao_salvo_nao_grava_nem_reutiliza_a_troca(self):
        motor = aplicativo.MotorDesktop(queue.Queue())
        historico = []
        with patch.object(main, "atender_acao", return_value=None), \
             patch.object(main, "preparar_pesquisa", return_value=None), \
             patch.object(main, "obter_resposta", return_value="Resposta privada."), \
             patch.object(main, "salvar_mensagem") as salvar:
            motor._responder(self.conexao, historico, "texto", "Pergunta privada.", nao_salvar=True)
        salvar.assert_not_called()
        self.assertEqual(historico, [])
        self.assertEqual(memoria.painel(self.conexao)["total_historico"], 0)

    def test_motor_gerencia_memoria_na_mesma_conexao(self):
        eventos = queue.Queue()
        motor = aplicativo.MotorDesktop(eventos)
        motor._gerenciar_memoria(self.conexao, "guardar", {
            "texto": "Prefiro exemplos.", "assunto": "geral", "projeto": "",
            "importancia": 4, "tipo": "preferencia",
        })
        tipo, dados = eventos.get_nowait()
        self.assertEqual(tipo, "memoria_dados")
        self.assertEqual(dados["lembrancas"][0]["tipo"], "preferencia")
        motor._gerenciar_memoria(self.conexao, "habilitar", {"ativa": False})
        self.assertFalse(eventos.get_nowait()[1]["ativa"])

    def test_apagar_tudo_pode_remover_backups_gerenciados(self):
        self.assertTrue(banco.listar_backups(self.caminho))
        eventos = queue.Queue()
        motor = aplicativo.MotorDesktop(eventos)
        memoria.guardar(self.conexao, "Meu nome é Ana.")
        self.assertTrue(motor._gerenciar_memoria(self.conexao, "apagar_tudo", {"incluir_backups": True}))
        self.assertEqual(eventos.get_nowait(), ("memoria_zerada",))
        self.assertEqual(eventos.get_nowait()[1]["total_lembrancas"], 0)
        self.assertEqual(banco.listar_backups(self.caminho), [])

    def test_janela_edita_lembranca_e_pede_confirmacao_para_apagar(self):
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Ambiente sem interface gráfica")
        raiz.withdraw()
        solicitar = Mock()
        janela = memoria_ui.JanelaMemoria(raiz, solicitar)
        try:
            janela.mostrar_dados(memoria.painel(self.conexao))
            janela._nova()
            janela.texto_lembranca.insert("1.0", "Prefiro exemplos curtos.")
            janela.tipo.set("preferencia")
            janela._salvar()
            self.assertEqual(solicitar.call_args.args[0], "guardar")
            self.assertEqual(solicitar.call_args.kwargs["tipo"], "preferencia")
            janela.incluir_backups.set(True)
            with patch.object(memoria_ui.messagebox, "askyesno", return_value=True):
                janela._apagar_tudo()
            self.assertEqual(solicitar.call_args.args[0], "apagar_tudo")
            self.assertTrue(solicitar.call_args.kwargs["incluir_backups"])
        finally:
            raiz.destroy()

    def test_botao_da_janela_principal_abre_gerenciador(self):
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Ambiente sem interface gráfica")
        raiz.withdraw()
        janela = aplicativo.JanelaAssistente(raiz, iniciar_motor=False)
        try:
            janela.pronto = True
            with patch.object(janela.motor, "gerenciar_memoria") as solicitar:
                janela.abrir_memorias()
            solicitar.assert_called_once_with("listar")
            janela.eventos.put(("memoria_dados", memoria.painel(self.conexao)))
            janela._processar_eventos()
            self.assertEqual(janela.janela_memoria.estado.cget("text").split()[0], "0")
        finally:
            janela.fechar()


class RenderizacaoTests(unittest.TestCase):
    def test_cercas_markdown_viram_blocos_de_codigo_sem_perder_indetacao(self):
        texto = "Exemplo:\n\n```python\nif True:\n    print('oi')\n```\nDepois."
        partes = renderizacao.fragmentos(texto)
        self.assertEqual([p[0] for p in partes], ["texto", "codigo", "texto"])
        self.assertEqual(partes[1], ("codigo", "python", "if True:\n    print('oi')"))
        self.assertNotIn("```", "".join(parte[2] for parte in partes))

    def test_duas_crases_e_codigo_sem_fechamento_tambem_sao_formatados(self):
        self.assertEqual(renderizacao.fragmentos("``python\nx = 1\n``")[0], ("codigo", "python", "x = 1"))
        self.assertEqual(renderizacao.fragmentos("```js\nconst x = 1;")[0], ("codigo", "js", "const x = 1;"))

    def test_widget_mostra_linguagem_e_copia_codigo(self):
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Ambiente sem interface gráfica")
        raiz.withdraw()
        janela = aplicativo.JanelaAssistente(raiz, iniciar_motor=False)
        try:
            janela._escrever(janela.historico_escrita, "IA", "Exemplo:\n```python\nprint('oi')\n```")
            exibido = janela.historico_escrita.get("1.0", "end-1c")
            self.assertIn("PYTHON", exibido)
            self.assertIn("Copiar código", exibido)
            self.assertNotIn("```", exibido)
            janela._copiar_codigo("print('oi')")
            self.assertEqual(raiz.clipboard_get(), "print('oi')")
        finally:
            janela.fechar()


if __name__ == "__main__":
    unittest.main()
