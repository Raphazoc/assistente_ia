import contextlib
import queue
import sqlite3
import tempfile
import threading
import tkinter as tk
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from app import aplicativo
from app import configuracao, internet, servicos, voz
from app.controles import InterromperFala


class AplicativoTests(unittest.TestCase):
    def test_fechar_durante_resposta_fecha_banco_na_thread_e_descarta_resposta(self):
        iniciou, liberar = threading.Event(), threading.Event()
        eventos = queue.Queue()
        motor = aplicativo.MotorDesktop(eventos)
        with tempfile.TemporaryDirectory() as pasta, \
                patch.object(aplicativo, "preparar_arquivos_usuario"), \
                patch.object(aplicativo.main, "BANCO", Path(pasta) / "memoria.db"), \
                patch.object(aplicativo.memoria, "habilitada", return_value=False), \
                patch.object(aplicativo.main, "indexar_memorias_antigas"), \
                patch.object(aplicativo.main, "atender_acao", return_value=None), \
                patch.object(aplicativo.main, "preparar_pesquisa", return_value=None), \
                patch.object(aplicativo.main, "obter_resposta") as responder:
            def demorar(*_args, **_kwargs):
                iniciou.set()
                liberar.wait(3)
                return "resposta tardia"
            responder.side_effect = demorar
            motor.iniciar()
            motor.enviar_texto("pergunta")
            self.assertTrue(iniciou.wait(3))
            motor.fechar()
            liberar.set()
            motor.thread.join(3)
            self.assertFalse(motor.thread.is_alive())
            with contextlib.closing(sqlite3.connect(Path(pasta) / "memoria.db")) as conexao:
                self.assertEqual(conexao.execute("SELECT papel FROM mensagens").fetchall(), [("user",)])
            self.assertFalse(any(evento[0] == "fatal" for evento in list(eventos.queue)))

    def test_parar_fala_sinaliza_cancelamento(self):
        motor = aplicativo.MotorDesktop(queue.Queue())
        monitor = Mock()
        controle = aplicativo._ControleFala(monitor, motor.parar_fala)
        motor.interromper_fala()
        with self.assertRaises(InterromperFala):
            controle.verificar()
        monitor.verificar.assert_not_called()

    def test_interromper_sintese_em_andamento(self):
        motor = aplicativo.MotorDesktop(queue.Queue())
        iniciou, liberar = threading.Event(), threading.Event()
        erros = []
        def falar(_texto, controle):
            iniciou.set()
            liberar.wait(2)
            controle.verificar()
        with patch.object(aplicativo.ativacao, "MonitorInterrupcao") as monitor, \
                patch("app.fala.falar", side_effect=falar):
            monitor.return_value.__enter__.return_value.comando = ""
            tarefa = threading.Thread(target=lambda: self._capturar_falha(motor, erros))
            tarefa.start()
            self.assertTrue(iniciou.wait(2))
            motor.interromper_fala()
            liberar.set()
            tarefa.join(2)
        self.assertFalse(tarefa.is_alive())
        self.assertEqual(len(erros), 1)
        self.assertIsInstance(erros[0], InterromperFala)

    @staticmethod
    def _capturar_falha(motor, erros):
        try:
            motor._falar("resposta")
        except Exception as erro:
            erros.append(erro)

    def test_gerenciamento_sqlite_fica_na_thread_do_motor(self):
        motor = aplicativo.MotorDesktop(queue.Queue())
        dono = []
        abrir_real = aplicativo.main.iniciar_banco
        with tempfile.TemporaryDirectory() as pasta, \
                patch.object(aplicativo, "preparar_arquivos_usuario"), \
                patch.object(aplicativo.main, "BANCO", Path(pasta) / "memoria.db"), \
                patch.object(aplicativo.memoria, "habilitada", return_value=False), \
                patch.object(aplicativo.main, "indexar_memorias_antigas"), \
                patch.object(aplicativo.main, "iniciar_banco") as abrir:
            def abrir_na_thread():
                dono.append(threading.get_ident())
                return abrir_real()
            abrir.side_effect = abrir_na_thread
            motor.iniciar()
            motor.gerenciar_memoria("listar")
            recebidos = []
            for _ in range(10):
                evento = motor.eventos.get(timeout=2)
                recebidos.append(evento[0])
                if evento[0] in {"memoria_dados", "memoria_erro", "fatal"}:
                    break
            motor.fechar()
            motor.thread.join(2)
        self.assertEqual(recebidos[-1], "memoria_dados")
        self.assertNotEqual(dono[0], threading.get_ident())
        self.assertFalse(motor.thread.is_alive())

    def test_eventos_tardios_nao_alteram_widgets_apos_fechamento(self):
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Ambiente sem interface gráfica")
        raiz.withdraw()
        janela = aplicativo.JanelaAssistente(raiz, iniciar_motor=False)
        janela.fechar()
        janela.eventos.put(("estado", "tardio"))
        janela._processar_eventos()
        self.assertEqual(janela.eventos.qsize(), 1)

    def test_cancelar_verificacao_ignora_resposta_tardia(self):
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Ambiente sem interface gráfica")
        raiz.withdraw()
        janela = aplicativo.JanelaAssistente(raiz, iniciar_motor=False)
        iniciou, liberar, terminou = threading.Event(), threading.Event(), threading.Event()
        def consultar(cancelar):
            iniciou.set()
            liberar.wait(2)
            terminou.set()
            return {"versao": "v9.0.0", "url": "https://github.com/Raphazoc/assistente_ia/releases/tag/v9.0.0",
                    "notas": "", "beta": True, "sha256": ""}
        try:
            with patch.object(aplicativo.atualizacoes, "consultar", side_effect=consultar), \
                    patch.object(aplicativo.atualizacoes, "salvar_ultima_verificacao", return_value={"status": "cancelada"}):
                janela.verificar_atualizacao()
                self.assertTrue(iniciou.wait(2))
                janela.cancelar_verificacao()
                liberar.set()
                self.assertTrue(terminou.wait(2))
                evento = janela.eventos.get(timeout=2)
                self.assertEqual(evento[0], "atualizacao")
                janela.eventos.put(evento)
                janela._processar_eventos()
                self.assertIsNone(janela.atualizacao)
                self.assertIn("cancelada", janela.estado["text"])
        finally:
            liberar.set()
            janela.fechar()

    def test_reativar_microfone_nao_descancela_captura_antiga(self):
        motor = aplicativo.MotorDesktop(queue.Queue())
        captura_antiga = motor.cancelar_captura
        motor.desativar_microfone()
        with patch.object(voz, "preparar_modelos"):
            motor.ativar_microfone()
        self.assertTrue(captura_antiga.is_set())
        self.assertTrue(motor.microfone_ativo.is_set())

    def test_escrita_e_audio_ficam_em_abas_separadas(self):
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Ambiente sem interface gráfica")
        raiz.withdraw()
        janela = aplicativo.JanelaAssistente(raiz, iniciar_motor=False)
        try:
            self.assertIs(janela.area_escrita.master, raiz)
            self.assertIs(janela.area_audio.master, raiz)
            self.assertEqual(janela.area_escrita.grid_info()["column"], 0)
            self.assertEqual(janela.area_escrita.winfo_manager(), "grid")
            self.assertEqual(janela.area_audio.winfo_manager(), "")
            janela.selecionar_modo("voz")
            self.assertEqual(janela.area_escrita.winfo_manager(), "")
            self.assertEqual(janela.area_audio.winfo_manager(), "grid")
            self.assertEqual(janela.area_audio.grid_info()["columnspan"], 2)
            janela.selecionar_modo("texto")
            self.assertEqual(janela.area_escrita.winfo_manager(), "grid")
            self.assertEqual(janela.area_audio.winfo_manager(), "")
        finally:
            janela.fechar()

    def test_confirmacao_bloqueia_motor_ate_resposta(self):
        eventos = queue.Queue()
        motor = aplicativo.MotorDesktop(eventos)
        resultado = []
        tarefa = threading.Thread(target=lambda: resultado.append(motor._confirmar("Teste", "Ação")))
        tarefa.start()
        self.assertEqual(eventos.get(timeout=1), ("confirmar", "Teste", "Ação"))
        self.assertTrue(tarefa.is_alive())
        motor.responder_confirmacao(False)
        tarefa.join(timeout=1)
        self.assertEqual(resultado, [False])

    def test_troca_de_aba_controla_escuta(self):
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Ambiente sem interface gráfica")
        raiz.withdraw()
        janela = aplicativo.JanelaAssistente(raiz, iniciar_motor=False)
        try:
            janela.pronto = True
            with patch.object(janela.motor, "ativar_microfone") as ativar, \
                 patch.object(janela.motor, "desativar_microfone") as desativar:
                janela.selecionar_modo("voz")
                self.assertTrue(janela.microfone_ligado)
                ativar.assert_called_once_with()
                janela.selecionar_modo("texto")
                self.assertFalse(janela.microfone_ligado)
                desativar.assert_called_once_with()
        finally:
            janela.fechar()

    def test_microfone_mutado_continua_mutado_apos_trocar_abas(self):
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Ambiente sem interface gráfica")
        raiz.withdraw()
        janela = aplicativo.JanelaAssistente(raiz, iniciar_motor=False)
        try:
            janela.pronto = True
            with patch.object(janela.motor, "ativar_microfone") as ativar, \
                 patch.object(janela.motor, "desativar_microfone") as desativar:
                janela.selecionar_modo("voz")
                janela.alternar_microfone()
                janela.selecionar_modo("texto")
                janela.selecionar_modo("voz")
                self.assertTrue(janela.microfone_mutado)
                self.assertFalse(janela.microfone_ligado)
                self.assertIn("mutado", janela.estado_audio["text"])
                ativar.assert_called_once_with()
                desativar.assert_called_once_with()
                janela.eventos.put(("estado_audio", "Ouvindo · fale no seu ritmo"))
                janela._processar_eventos()
                self.assertIn("mutado", janela.estado_audio["text"])
                janela.alternar_microfone()
                self.assertFalse(janela.microfone_mutado)
                self.assertTrue(janela.microfone_ligado)
                self.assertEqual(ativar.call_count, 2)
        finally:
            janela.fechar()

    def test_troca_de_microfone_reinicia_escuta_e_respeita_mudo(self):
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Ambiente sem interface gráfica")
        raiz.withdraw()
        janela = aplicativo.JanelaAssistente(raiz, iniciar_motor=False)
        try:
            janela.pronto = True
            janela.motor_iniciado = True
            dados = {**configuracao.PADRAO, "microfone": "USB · WASAPI",
                     "verificar_atualizacoes": False}
            with patch.object(voz, "MICROFONE_SELECIONADO", ""), \
                 patch.object(configuracao, "aplicar"), \
                 patch.object(janela.motor.thread, "is_alive", return_value=True), \
                 patch.object(janela.motor, "ativar_microfone") as ativar, \
                 patch.object(janela.motor, "desativar_microfone") as desativar, \
                 patch.object(janela, "_agendar") as agendar:
                janela.selecionar_modo("voz")
                ativar.reset_mock()
                janela._configuracao_salva(dados)
                desativar.assert_called_once_with()
                self.assertFalse(janela.microfone_ligado)
                agendar.assert_called_once()
                agendar.call_args.args[1]()
                ativar.assert_called_once_with()
                janela.alternar_microfone()
                ativar.reset_mock()
                agendar.reset_mock()
                janela._configuracao_salva(dados)
                self.assertTrue(janela.microfone_mutado)
                ativar.assert_not_called()
                agendar.assert_not_called()
        finally:
            janela.fechar()

    def test_configuracoes_unificadas_abrem_na_interface(self):
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Ambiente sem interface gráfica")
        raiz.withdraw()
        janela = aplicativo.JanelaAssistente(raiz, iniciar_motor=False)
        try:
            with patch.object(servicos, "obter_chave", return_value=""):
                janela.motor_iniciado = True
                janela.abrir_configuracoes()
                dialogos = [filho for filho in raiz.winfo_children() if isinstance(filho, tk.Toplevel)]
                self.assertEqual(len(dialogos), 1)
                self.assertEqual(dialogos[0].title(), "Configurações")
                self.assertEqual(len(janela.assistente.abas.tabs()), 4)
                janela.abrir_configuracoes()
                self.assertEqual(len([filho for filho in raiz.winfo_children() if isinstance(filho, tk.Toplevel)]), 1)
        finally:
            janela.fechar()

    def test_fontes_da_pesquisa_aparecem_com_link_abre_no_clique(self):
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Ambiente sem interface gráfica")
        raiz.withdraw()
        janela = aplicativo.JanelaAssistente(raiz, iniciar_motor=False)
        try:
            widget = janela.historico_escrita
            mensagem = ("Consultei a fonte [1].\n\nFontes consultadas:\n"
                        "Consulta em 2026-10-17T20:00:00+00:00.\n"
                        "1. [Documentação Python](https://www.python.org/doc/) · Brave Search")
            janela._escrever(widget, "IA", mensagem)
            self.assertIn("Documentação Python", widget.get("1.0", "end"))
            self.assertNotIn("[Documentação Python]", widget.get("1.0", "end"))
            tags = [tag for tag in widget.tag_names() if tag.startswith("fonte_link_")]
            self.assertEqual(len(tags), 1)
            self.assertTrue(widget.tag_bind(tags[0], "<Button-1>", None))
        finally:
            janela.fechar()

    def test_mensagens_aparecem_em_cartoes_nas_abas_corretas(self):
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Ambiente sem interface gráfica")
        raiz.withdraw()
        janela = aplicativo.JanelaAssistente(raiz, iniciar_motor=False)
        try:
            janela._escrever(janela.historico_escrita, "Você", "Pergunta por texto")
            janela._escrever(janela.historico_escrita, "IA", "Resposta por texto")
            janela._escrever(janela.historico_audio, "IA", "Resposta por voz")
            self.assertEqual(len([filho for filho in janela.cartoes_escrita.winfo_children()
                                  if filho.winfo_manager() == "grid"]), 2)
            self.assertEqual(len([filho for filho in janela.cartoes_audio.winfo_children()
                                  if filho.winfo_manager() == "grid"]), 1)
            self.assertEqual(janela.vazio_escrita.winfo_manager(), "")
            janela.selecionar_modo("voz")
            self.assertEqual(janela.area_audio.winfo_manager(), "grid")
            self.assertEqual(janela.area_escrita.winfo_manager(), "")
        finally:
            janela.fechar()

    def test_microfone_permanece_ativo_apos_duas_frases(self):
        motor = aplicativo.MotorDesktop(queue.Queue())
        conexao = Mock()
        frases = []

        def responder(_conexao, _historico, origem, texto, nao_salvar=False):
            frases.append((origem, texto))
            if len(frases) == 2:
                motor.fechar()

        with (
            patch.object(aplicativo, "preparar_arquivos_usuario"),
            patch.object(aplicativo.main, "iniciar_banco", return_value=conexao),
            patch.object(aplicativo.memoria, "processar_pendentes"),
            patch.object(aplicativo.memoria, "habilitada", return_value=True),
            patch.object(aplicativo.resumos, "resumir_pendentes"),
            patch.object(aplicativo.main, "indexar_memorias_antigas"),
            patch.object(aplicativo.MotorDesktop, "_responder", side_effect=responder),
            patch("app.voz.preparar_modelos"),
            patch("app.voz.ouvir", side_effect=["Primeira frase", "Segunda frase"]) as ouvir,
        ):
            motor.ativar_microfone()
            motor.iniciar()
            motor.thread.join(timeout=3)
        self.assertFalse(motor.thread.is_alive())
        self.assertEqual(frases, [("audio", "Primeira frase"), ("audio", "Segunda frase")])
        self.assertEqual(ouvir.call_count, 2)
        self.assertTrue(all(chamada.kwargs["aguardar_fala"] for chamada in ouvir.call_args_list))

    def test_botao_de_pesquisa_alterna_preferencia(self):
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Ambiente sem interface gráfica")
        raiz.withdraw()
        janela = aplicativo.JanelaAssistente(raiz, iniciar_motor=False)
        try:
            janela.pronto = True
            with patch.object(internet, "habilitada", side_effect=[True, False, False]), \
                 patch.object(internet, "definir_habilitada") as definir:
                janela.alternar_pesquisa()
            definir.assert_called_once_with(False)
            self.assertIn("desligada", janela.pesquisa["text"])
        finally:
            janela.fechar()

    def test_nao_salvar_vale_apenas_para_o_proximo_envio(self):
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Ambiente sem interface gráfica")
        raiz.withdraw()
        janela = aplicativo.JanelaAssistente(raiz, iniciar_motor=False)
        try:
            janela.pronto = True
            janela.entrada.insert("1.0", "Pergunta particular")
            janela.nao_salvar.set(True)
            with patch.object(janela.motor, "enviar_texto") as enviar:
                janela.enviar_texto()
            enviar.assert_called_once_with("Pergunta particular", nao_salvar=True)
            self.assertFalse(janela.nao_salvar.get())
        finally:
            janela.fechar()


if __name__ == "__main__":
    unittest.main()
