import json
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app import aplicativo, configuracao, diagnostico, diagnostico_inicial, internet, primeira_execucao, main, voz, fala, servicos, versao


class ConfiguracaoTests(unittest.TestCase):
    def test_versao_exibida_corresponde_ao_instalador(self):
        script = Path(__file__).resolve().parents[1] / "installer" / "AssistenteIA.iss"
        self.assertIn(f"AppVersion={versao.VERSAO}", script.read_text(encoding="utf-8"))

    def test_configuracao_inicial_e_validacao_de_campos(self):
        with tempfile.TemporaryDirectory() as pasta, \
             patch.object(configuracao, "CONFIGURACAO", Path(pasta) / "geral.json"):
            self.assertFalse(configuracao.carregar()["configurado"])
            dados = {**configuracao.PADRAO, "modelo": "outro:7b", "configurado": True}
            configuracao.salvar(dados)
            self.assertEqual(configuracao.carregar()["modelo"], "outro:7b")
            self.assertNotIn("chave", configuracao.CONFIGURACAO.read_text(encoding="utf-8"))
            configuracao.CONFIGURACAO.write_text(json.dumps({"modelo": "\nruim"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "modelo"):
                configuracao.carregar()
            with self.assertRaisesRegex(ValueError, "idioma"):
                configuracao.validar({"idioma": ["pt-BR"]})
            configuracao.CONFIGURACAO.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "config_geral.json|geral.json"):
                configuracao.carregar()

    def test_diagnostico_sem_ollama_indica_ausencia_sem_travar(self):
        with patch.object(diagnostico_inicial, "_obter_json", side_effect=ConnectionRefusedError()), \
             patch.object(diagnostico_inicial.shutil, "which", return_value=None), \
             patch.object(diagnostico, "eventos_recentes", return_value=[]), \
             patch.object(diagnostico_inicial.sd, "query_devices", return_value=[]):
            resultado = diagnostico_inicial.verificar()
        self.assertFalse(resultado["ollama_instalado"])
        self.assertFalse(resultado["ollama_ativo"])
        self.assertEqual(resultado["modelos"], [])
        self.assertEqual(resultado["erro_ollama"], "ConnectionRefusedError")
        self.assertIn("versao_app", resultado)
        self.assertIn("eventos_recentes", resultado)

    def test_caminho_do_diagnostico_oculta_nome_da_conta(self):
        caminho = Path.home() / "assistente_ia" / "memoria.db"
        publico = diagnostico_inicial.caminho_publico(caminho)
        self.assertTrue(publico.startswith("%USERPROFILE%"))
        self.assertNotIn(str(Path.home()), publico)

    def test_modelos_e_idioma_escolhidos_sao_aplicados_ao_motor(self):
        dados = {**configuracao.PADRAO, "modelo": "outro:7b",
                 "modelo_memoria": "vetores:1b", "idioma": "en-US", "limite_historico": 75}
        with patch.object(main, "MODELO", main.MODELO), \
             patch.object(main, "MODELO_MEMORIA", main.MODELO_MEMORIA), \
             patch.object(main, "LIMITE_HISTORICO", main.LIMITE_HISTORICO), \
             patch.object(main, "IDIOMA", main.IDIOMA), \
             patch.object(voz, "IDIOMA_RECONHECIMENTO", voz.IDIOMA_RECONHECIMENTO), \
             patch.object(fala, "VOZ_ONLINE", fala.VOZ_ONLINE):
            configuracao.aplicar(dados)
            self.assertEqual((main.MODELO, main.MODELO_MEMORIA), ("outro:7b", "vetores:1b"))
            self.assertEqual(main.LIMITE_HISTORICO, 75)
            self.assertEqual((main.IDIOMA, voz.IDIOMA_RECONHECIMENTO), ("en-US", "en"))

    def test_primeira_execucao_nao_inicia_motor_antes_de_configurar(self):
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Ambiente sem interface gráfica")
        raiz.withdraw()
        with patch.object(aplicativo, "preparar_arquivos_usuario"), \
             patch.object(configuracao, "carregar", return_value=configuracao.PADRAO.copy()), \
             patch.object(aplicativo.MotorDesktop, "iniciar") as iniciar, \
             patch.object(primeira_execucao, "AssistenteConfiguracao") as assistente:
            janela = aplicativo.JanelaAssistente(raiz, iniciar_motor=True)
            try:
                self.assertFalse(janela.motor_iniciado)
                self.assertIn("configuração inicial", janela.estado["text"])
                raiz.after(150, raiz.quit)
                raiz.mainloop()
                assistente.assert_called_once()
                iniciar.assert_not_called()
            finally:
                janela.fechar()

    def test_assistente_exige_modelos_instalados_para_continuar(self):
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Ambiente sem interface gráfica")
        raiz.withdraw()
        with tempfile.TemporaryDirectory() as pasta, \
             patch.object(configuracao, "CONFIGURACAO", Path(pasta) / "geral.json"), \
             patch.object(internet, "CONFIGURACAO", Path(pasta) / "internet.json"), \
             patch.object(servicos, "CONFIGURACAO", Path(pasta) / "servicos.json"), \
             patch.object(servicos, "obter_chave", return_value=""), \
             patch.object(diagnostico_inicial, "verificar"):
            salvar = Mock()
            assistente = primeira_execucao.AssistenteConfiguracao(raiz, salvar)
            try:
                sem_ollama = {"ollama_instalado": False, "ollama_ativo": False,
                              "ollama_versao": "", "modelos": [], "microfone": False,
                              "alto_falante": False, "python": "3.13", "erro_ollama": "ConnectionRefusedError"}
                assistente._mostrar_resultado(sem_ollama)
                with patch.object(primeira_execucao.messagebox, "showerror") as erro:
                    assistente.salvar()
                erro.assert_called_once()
                salvar.assert_not_called()
                pronto = {**sem_ollama, "ollama_instalado": True, "ollama_ativo": True,
                          "modelos": ["qwen3:8b", "qwen3-embedding:0.6b"]}
                assistente._mostrar_resultado(pronto)
                assistente.salvar()
                salvar.assert_called_once()
                self.assertTrue(configuracao.carregar()["configurado"])
            finally:
                if assistente.janela.winfo_exists():
                    assistente.janela.destroy()
                raiz.destroy()

    def test_configuracoes_validam_antes_de_guardar_chaves(self):
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Ambiente sem interface gráfica")
        raiz.withdraw()
        with tempfile.TemporaryDirectory() as pasta, \
             patch.object(configuracao, "CONFIGURACAO", Path(pasta) / "geral.json"), \
             patch.object(servicos, "CONFIGURACAO", Path(pasta) / "servicos.json"), \
             patch.object(internet, "CONFIGURACAO", Path(pasta) / "internet.json"), \
             patch.object(servicos, "obter_chave", return_value=""), \
             patch.object(servicos, "salvar_chave") as guardar, \
             patch.object(diagnostico_inicial, "verificar"):
            salvar = Mock()
            assistente = primeira_execucao.AssistenteConfiguracao(raiz, salvar)
            try:
                assistente._mostrar_resultado({
                    "ollama_instalado": True, "ollama_ativo": True, "ollama_versao": "1.0",
                    "modelos": ["qwen3:8b", "qwen3-embedding:0.6b"],
                    "microfone": True, "alto_falante": True, "python": "3.13", "erro_ollama": "",
                })
                assistente.buscador.set("brave")
                assistente.chave_brave.insert(0, "chave-de-teste")
                assistente.voz.set("elevenlabs")
                assistente.voice_id.set("id inválido")
                with patch.object(primeira_execucao.messagebox, "showerror") as erro:
                    assistente.salvar()
                    erro.assert_called_once()
                    guardar.assert_not_called()
                    self.assertFalse(configuracao.CONFIGURACAO.exists())
                    assistente.voice_id.set("voz_teste")
                    assistente.salvar()
                    self.assertEqual(erro.call_count, 2)
                self.assertTrue(assistente.janela.winfo_exists())
                guardar.assert_not_called()
                assistente.chave_elevenlabs.insert(0, "outra-chave-de-teste")
                assistente.salvar()
                self.assertEqual(guardar.call_count, 2)
                self.assertEqual(servicos.carregar()["buscador"], "brave")
                self.assertTrue(configuracao.carregar()["configurado"])
                self.assertNotIn("chave-de-teste", servicos.CONFIGURACAO.read_text(encoding="utf-8"))
                salvar.assert_called_once()
            finally:
                if assistente.janela.winfo_exists():
                    assistente.janela.destroy()
                raiz.destroy()

    def test_preferencias_podem_ser_salvas_com_ollama_temporariamente_fora(self):
        try:
            raiz = tk.Tk()
        except tk.TclError:
            self.skipTest("Ambiente sem interface gráfica")
        raiz.withdraw()
        with tempfile.TemporaryDirectory() as pasta, \
             patch.object(configuracao, "CONFIGURACAO", Path(pasta) / "geral.json"), \
             patch.object(servicos, "CONFIGURACAO", Path(pasta) / "servicos.json"), \
             patch.object(internet, "CONFIGURACAO", Path(pasta) / "internet.json"), \
             patch.object(servicos, "obter_chave", return_value=""), \
             patch.object(diagnostico_inicial, "verificar"):
            configuracao.salvar({**configuracao.PADRAO, "configurado": True})
            salvar = Mock()
            assistente = primeira_execucao.AssistenteConfiguracao(raiz, salvar, primeira=False)
            try:
                assistente.idioma.set("en-US")
                assistente.pesquisa.set(False)
                assistente.salvar()
                self.assertEqual(configuracao.carregar()["idioma"], "en-US")
                self.assertFalse(internet.habilitada())
                salvar.assert_called_once()
            finally:
                if assistente.janela.winfo_exists():
                    assistente.janela.destroy()
                raiz.destroy()
