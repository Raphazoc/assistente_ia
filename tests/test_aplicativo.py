import queue
import threading
import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app import aplicativo
from app import internet


class AplicativoTests(unittest.TestCase):
    def test_escrita_e_audio_ficam_em_colunas_separadas(self):
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
            self.assertEqual(janela.area_audio.grid_info()["column"], 1)
            self.assertEqual(janela.area_escrita.grid_info()["row"], janela.area_audio.grid_info()["row"])
            self.assertEqual(janela.area_escrita.winfo_manager(), "grid")
            self.assertEqual(janela.area_audio.winfo_manager(), "grid")
            janela._ajustar_layout(SimpleNamespace(widget=raiz, width=720, height=850))
            self.assertEqual(janela.area_audio.grid_info()["row"], 3)
            janela._ajustar_layout(SimpleNamespace(widget=raiz, width=1120, height=700))
            self.assertEqual(janela.area_audio.grid_info()["row"], 2)
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

    def test_microfone_permanece_ativo_apos_duas_frases(self):
        motor = aplicativo.MotorDesktop(queue.Queue())
        conexao = Mock()
        frases = []

        def responder(_conexao, _historico, origem, texto):
            frases.append((origem, texto))
            if len(frases) == 2:
                motor.fechar()

        with (
            patch.object(aplicativo, "preparar_arquivos_usuario"),
            patch.object(aplicativo.main, "iniciar_banco", return_value=conexao),
            patch.object(aplicativo.memoria, "processar_pendentes"),
            patch.object(aplicativo.resumos, "resumir_pendentes"),
            patch.object(aplicativo.main, "indexar_memorias_antigas"),
            patch.object(aplicativo.MotorDesktop, "_responder", side_effect=responder),
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


if __name__ == "__main__":
    unittest.main()
