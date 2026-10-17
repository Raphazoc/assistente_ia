import queue
import threading
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from app import aplicativo
from app import internet, servicos


class AplicativoTests(unittest.TestCase):
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
