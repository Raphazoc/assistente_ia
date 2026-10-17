import concurrent.futures
import contextlib
import io
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

import ativacao
import fala
import main
import memoria
import voz
from controles import InterromperFala, SolicitarMenu


class AtivacaoTests(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.config = patch.object(ativacao, "CONFIGURACAO", Path(self.pasta.name) / "config.json")
        self.config.start()

    def tearDown(self):
        self.config.stop()
        self.pasta.cleanup()

    def test_nome_personalizado_e_persistido_sem_mudar_outros_campos(self):
        ativacao.definir_palavra("Olá Sofia")
        config = ativacao.carregar_configuracao()
        self.assertEqual(config["palavra_ativacao"], "Olá Sofia")
        self.assertTrue(config["interromper_por_voz"])
        self.assertEqual(ativacao.extrair_chamada("Olá, Sofia! Qual é a previsão?", "Olá Sofia"), "Qual é a previsão?")

    def test_rejeita_nomes_invalidos(self):
        for nome in ("", "oi", "123", "menu", "pare", "a b c d e", "x" * 41):
            with self.subTest(nome=nome), self.assertRaises(ValueError):
                ativacao.definir_palavra(nome)

    def test_pedido_falado_direto_aceita_comandos_sem_nome(self):
        for texto in ("Explique Python", "sair", "modo texto", "menu"):
            self.assertEqual(ativacao.preparar_pedido_falado(texto, "Aurora"), texto)

    def test_nome_opcional_so_e_removido_com_separador(self):
        self.assertEqual(ativacao.preparar_pedido_falado("AURORA, explique Python.", "Aurora"), "explique Python.")
        self.assertEqual(ativacao.preparar_pedido_falado("Aurora, sair", "Aurora"), "sair")
        self.assertEqual(ativacao.preparar_pedido_falado("Aurora!", "Aurora"), "")
        self.assertEqual(ativacao.preparar_pedido_falado("Aurora boreal", "Aurora"), "Aurora boreal")
        self.assertEqual(ativacao.preparar_pedido_falado("Auroral é uma palavra", "Aurora"), "Auroral é uma palavra")

    def test_monitor_ignora_eco_e_conversa_sem_nome(self):
        monitor = ativacao.MonitorInterrupcao("Você pode dizer Aurora, pare para interromper.")
        for texto in ("Bom dia", "Aurora, pare"):
            monitor.processar(texto)
        self.assertFalse(monitor.interrompido.is_set())

    def test_monitor_para_e_pode_guardar_novo_pedido(self):
        monitor = ativacao.MonitorInterrupcao("Estou explicando programação.")
        monitor.processar("Aurora, pare.")
        self.assertTrue(monitor.interrompido.is_set())
        self.assertEqual(monitor.comando, "")
        monitor = ativacao.MonitorInterrupcao("Estou explicando programação.")
        monitor.processar("Aurora, agora explique matemática.")
        self.assertEqual(monitor.comando, "agora explique matemática.")

    def test_monitor_e_encerrado_e_libera_microfone(self):
        terminou = threading.Event()

        def capturar(**kwargs):
            kwargs["cancelar"].wait(timeout=2)
            terminou.set()
            return None

        with patch.object(voz, "capturar_audio", side_effect=capturar):
            with ativacao.MonitorInterrupcao("Olá") as monitor:
                pass
        self.assertTrue(monitor.finalizar.is_set())
        self.assertTrue(terminou.wait(timeout=1))

    def test_menu_altera_nome_e_retorna_para_escolha_de_modo(self):
        with (
            patch.object(main, "ler_texto", side_effect=["3", "Sofia", "2"]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(main.escolher_modo("texto"), "voz")
        self.assertEqual(ativacao.carregar_configuracao()["palavra_ativacao"], "Sofia")


class InterrupcaoAudioTests(unittest.TestCase):
    def test_interrupcao_aborta_buffer_antes_de_escrever_trecho_inteiro(self):
        stream = MagicMock()
        controle = MagicMock()
        controle.verificar.side_effect = [None, InterromperFala()]
        with self.assertRaises(InterromperFala):
            fala.escrever_audio(stream, b"\x00\x00" * 24000, 24000, controle)
        stream.abort.assert_called_once()
        self.assertEqual(stream.write.call_count, 1)
        self.assertLess(len(stream.write.call_args.args[0]), 24000 * 2)

    def test_esc_aborta_audio_e_solicita_menu(self):
        stream = MagicMock()
        with patch.object(fala, "tecla_durante_fala", return_value="menu"):
            with self.assertRaises(SolicitarMenu):
                fala.escrever_audio(stream, b"\x00\x00" * 480, 24000, None)
        stream.abort.assert_called_once()

    def test_interrompe_enquanto_aguarda_rede_sem_esperar_resultado(self):
        futuro = concurrent.futures.Future()
        controle = MagicMock()
        controle.verificar.side_effect = InterromperFala()
        with self.assertRaises(InterromperFala):
            fala.aguardar_audio(futuro, controle)
        self.assertFalse(futuro.done())

    def test_cancelamento_nao_aciona_voz_local_de_reserva(self):
        with (
            patch.object(fala, "_online_indisponivel_ate", 0),
            patch.object(fala, "falar_online", side_effect=InterromperFala()),
            patch.object(fala, "falar_local") as local,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            fala.falar("Olá.")
        local.assert_not_called()


class RuidoTests(unittest.TestCase):
    def test_filtro_atenua_dc_e_ruido_de_frequencia_baixa(self):
        filtro = voz.FiltroRuido()
        t = np.arange(16000) / 16000
        audio = (0.2 + 0.1 * np.sin(2 * np.pi * 20 * t)).astype(np.float32)
        filtrado = np.concatenate([filtro.processar(b) for b in np.array_split(audio, 32)])
        self.assertLess(np.sqrt(np.mean(filtrado[2000:] ** 2)), 0.03)

    def test_ruido_baixo_nao_passsa_mesmo_com_probabilidade_alta(self):
        filtro = voz.FiltroRuido()
        self.assertEqual(filtro.validar(np.full(512, 0.0001, dtype=np.float32), 0.9), 0)

    def test_impulsos_isolados_nao_iniciam_gravacao(self):
        gravador = voz.GravadorFrase()
        bloco = np.zeros(512, dtype=np.float32)
        for _ in range(20):
            gravador.processar(bloco, 0.95)
            gravador.processar(bloco, 0.0)
        self.assertFalse(gravador.iniciou)

    def test_transcricao_de_baixa_confianca_nao_ativa_assistente(self):
        segmentos = [
            SimpleNamespace(text="Aurora", avg_logprob=-1.5),
            SimpleNamespace(text="Aurora", no_speech_prob=0.9),
            SimpleNamespace(text="Aurora", compression_ratio=4),
        ]
        with patch.object(voz, "carregar_modelo") as modelo:
            modelo.return_value.transcribe.return_value = (iter(segmentos), None)
            self.assertEqual(voz.transcrever_audio(np.zeros(16000, dtype=np.float32)), "")

    def test_transcricao_normal_nao_induz_palavra_de_ativacao(self):
        with patch.object(voz, "carregar_modelo") as modelo:
            modelo.return_value.transcribe.return_value = (iter([]), None)
            voz.transcrever_audio(np.zeros(16000, dtype=np.float32))
            self.assertNotIn("hotwords", modelo.return_value.transcribe.call_args.kwargs)
            self.assertNotIn("initial_prompt", modelo.return_value.transcribe.call_args.kwargs)
            voz.transcrever_audio(np.zeros(16000, dtype=np.float32), modo_interrupcao=True)
            self.assertEqual(modelo.return_value.transcribe.call_args.kwargs["hotwords"], "Aurora")


class IntegracaoConversaTests(unittest.TestCase):
    def test_processa_fala_direta_e_novo_pedido_da_interrupcao_uma_vez(self):
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
            patch.object(main, "indexar_nova_mensagem"),
            patch.object(main, "carregar_historico", return_value=[]),
            patch.object(main, "ler_texto", return_value="2"),
            patch.object(main, "reconhecer_voz", side_effect=["primeiro pedido", "sair"]) as ouvir,
            patch.object(main, "obter_resposta", return_value="Uma resposta") as responder,
            patch.object(main, "salvar_mensagem", return_value=1) as salvar,
            patch.object(main, "reproduzir_resposta", side_effect=["segundo pedido", ""]),
            patch.object(ativacao, "carregar_configuracao", return_value=dict(ativacao.PADRAO)),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            main.main()
        self.assertEqual([c.args[2] for c in responder.call_args_list], ["primeiro pedido", "segundo pedido"])
        self.assertEqual(salvar.call_count, 4)
        self.assertEqual(ouvir.call_count, 2)


if __name__ == "__main__":
    unittest.main()
