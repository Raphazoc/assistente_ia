import contextlib
import io
import math
import sqlite3
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from app import main
from app import memoria
from app import voz


class GravadorFraseTests(unittest.TestCase):
    def setUp(self):
        self.bloco = np.zeros(voz.AMOSTRAS_POR_BLOCO, dtype=np.float32)
        self.gravador = voz.GravadorFrase()

    def falar(self, quantidade):
        for _ in range(quantidade):
            self.assertFalse(self.gravador.processar(self.bloco, 0.9))

    def test_encerra_apos_pausa_de_silencio_depois_da_fala(self):
        self.falar(10)
        blocos_silencio = math.ceil(voz.SILENCIO_FINAL / self.gravador.duracao_bloco)
        for _ in range(blocos_silencio - 1):
            self.assertFalse(self.gravador.processar(self.bloco, 0.0))
        self.assertTrue(self.gravador.processar(self.bloco, 0.0))
        self.assertLess(self.gravador.audio().size / voz.TAXA_AMOSTRAGEM, 2.0)

    def test_escuta_continua_espera_fala_sem_expirar(self):
        gravador = voz.GravadorFrase(aguardar_fala=True)
        total = math.ceil(voz.TEMPO_ESPERA_INICIO * 2 / gravador.duracao_bloco)
        for _ in range(total):
            self.assertFalse(gravador.processar(self.bloco, 0.0))
        self.assertEqual(gravador.audio().size, 0)

    def test_pausa_curta_nao_encerra_e_nova_fala_reinicia_contagem(self):
        self.falar(10)
        for _ in range(10):
            self.assertFalse(self.gravador.processar(self.bloco, 0.0))
        self.falar(3)
        self.assertEqual(self.gravador.silencio, 0)
        self.assertTrue(self.gravador.audio().size)

    def test_fala_continua_pode_ultrapassar_seis_segundos(self):
        self.falar(math.ceil(7 / self.gravador.duracao_bloco))
        self.assertGreater(self.gravador.audio().size / voz.TAXA_AMOSTRAGEM, 6)

    def test_limite_impede_gravacao_sem_fim(self):
        with patch.object(voz, "DURACAO_MAXIMA_FALA", 0.16):
            self.falar(4)
            self.assertTrue(self.gravador.processar(self.bloco, 0.9))

    def test_silencio_inicial_e_ruido_muito_curto_nao_geram_transcricao(self):
        total = math.ceil(voz.TEMPO_ESPERA_INICIO / self.gravador.duracao_bloco)
        for _ in range(total - 1):
            self.assertFalse(self.gravador.processar(self.bloco, 0.0))
        self.assertTrue(self.gravador.processar(self.bloco, 0.0))
        self.assertEqual(self.gravador.audio().size, 0)

        self.gravador = voz.GravadorFrase()
        self.falar(1)
        while not self.gravador.processar(self.bloco, 0.0):
            pass
        self.assertEqual(self.gravador.audio().size, 0)

    def test_margem_preserva_audio_antes_da_deteccao(self):
        for numero in range(10):
            bloco = np.full(voz.AMOSTRAS_POR_BLOCO, numero, dtype=np.float32)
            self.gravador.processar(bloco, 0.0)
        self.falar(4)
        self.assertEqual(self.gravador.audio()[0], 5)


class CapturaVozTests(unittest.TestCase):
    def setUp(self):
        self.silenciar = contextlib.redirect_stdout(io.StringIO())
        self.silenciar.__enter__()

    def tearDown(self):
        self.silenciar.__exit__(None, None, None)

    def test_esc_fecha_microfone_e_solicita_menu_sem_transcrever(self):
        with (
            patch.object(voz, "atalho_menu_pressionado", side_effect=[False, True]),
            patch.object(voz, "DetectorVoz"),
            patch.object(voz.sd, "InputStream") as stream,
            patch.object(voz, "carregar_modelo") as modelo,
        ):
            with self.assertRaises(voz.SolicitarMenu):
                voz.ouvir()
        stream.return_value.__exit__.assert_called_once()
        modelo.assert_not_called()

    def test_gravacao_e_encerrada_por_silencio_e_fecha_microfone(self):
        amostras = np.arange(voz.AMOSTRAS_POR_BLOCO) / voz.TAXA_AMOSTRAGEM
        bloco = (0.1 * np.sin(2 * np.pi * 200 * amostras)).astype(np.float32).reshape(-1, 1)
        silencios = math.ceil(voz.SILENCIO_FINAL * voz.TAXA_AMOSTRAGEM / voz.AMOSTRAS_POR_BLOCO)
        with (
            patch.object(voz, "atalho_menu_pressionado", return_value=False),
            patch.object(voz, "DetectorVoz") as detector,
            patch.object(voz.sd, "InputStream") as stream,
        ):
            detector.return_value.probabilidade.side_effect = [0.9] * 5 + [0.0] * silencios
            microfone = stream.return_value.__enter__.return_value
            microfone.read.return_value = (bloco, False)
            audio = voz.capturar_audio()
        self.assertEqual(microfone.read.call_count, 5 + silencios)
        self.assertGreater(audio.size, 0)
        stream.return_value.__exit__.assert_called_once()

    def test_microfone_escolhido_e_usado_na_captura(self):
        dispositivos = [
            {"name": "Caixas", "hostapi": 0, "max_input_channels": 0},
            {"name": "Microfone USB", "hostapi": 0, "max_input_channels": 1},
        ]
        with (patch.object(voz.sd, "query_devices", return_value=dispositivos),
              patch.object(voz.sd, "query_hostapis", return_value=[{"name": "WASAPI"}]),
              patch.object(voz.sd, "check_input_settings"),
              patch.object(voz, "MICROFONE_SELECIONADO", "Microfone USB · WASAPI"),
              patch.object(voz, "DetectorVoz"),
              patch.object(voz.sd, "InputStream") as stream):
            cancelar = threading.Event()
            cancelar.set()
            self.assertIsNone(voz.capturar_audio(cancelar=cancelar, teclado=False, anunciar=False))
            self.assertEqual(stream.call_args.kwargs["device"], 1)

    def test_microfone_removido_nao_troca_para_o_padrao(self):
        with (patch.object(voz.sd, "query_devices", return_value=[]),
              patch.object(voz.sd, "query_hostapis", return_value=[]),
              patch.object(voz, "MICROFONE_SELECIONADO", "Microfone USB · WASAPI"),
              patch.object(voz.sd, "InputStream") as stream):
            with self.assertRaisesRegex(RuntimeError, "não está disponível"):
                voz.resolver_microfone()
            stream.assert_not_called()

    def test_lista_recomendada_remove_alias_e_repeticoes_sem_perder_dispositivos(self):
        apis = [{"name": "MME"}, {"name": "Windows DirectSound"},
                {"name": "Windows WASAPI"}, {"name": "Windows WDM-KS"}]
        entradas = [
            {"name": "Mapeador de som da Microsoft - Input", "hostapi": 0, "max_input_channels": 2},
            {"name": "Microfone (WEBCAM)", "hostapi": 0, "max_input_channels": 1},
            {"name": "Microfone (L80)", "hostapi": 0, "max_input_channels": 1},
            {"name": "Driver de captura de som primário", "hostapi": 1, "max_input_channels": 2},
            {"name": "Microfone (WEBCAM)", "hostapi": 1, "max_input_channels": 1},
            {"name": "Microfone (WEBCAM)", "hostapi": 2, "max_input_channels": 1},
            {"name": "Microfone (L80)", "hostapi": 2, "max_input_channels": 1},
            {"name": "Microfone (HD Audio Mixed capture)", "hostapi": 3, "max_input_channels": 2},
        ]
        with patch.object(voz.sd, "query_devices", return_value=entradas), \
             patch.object(voz.sd, "query_hostapis", return_value=apis), \
             patch.object(voz.sd, "check_input_settings"), \
             patch.object(voz.sd, "default") as padrao:
            padrao.device = [1, 0]
            recomendados = voz.listar_microfones_recomendados()
            self.assertEqual(recomendados, [
                ("Microfone (WEBCAM) · Windows WASAPI", 5),
                ("Microfone (L80) · Windows WASAPI", 6),
            ])
            self.assertEqual(voz.nome_microfone_padrao(), "Microfone (WEBCAM) · MME")
            self.assertEqual(voz.resolver_microfone("Microfone (WEBCAM) · MME"), 1)

    def test_lista_recomendada_nao_oferece_api_incompativel_com_captura(self):
        entradas = [
            {"name": "Microfone USB", "hostapi": 0, "max_input_channels": 1},
            {"name": "Microfone USB", "hostapi": 1, "max_input_channels": 1},
        ]
        def verificar(**dados):
            if dados["device"] == 1:
                raise voz.sd.PortAudioError("Invalid sample rate")
        with patch.object(voz.sd, "query_devices", return_value=entradas), \
             patch.object(voz.sd, "query_hostapis", return_value=[{"name": "Windows DirectSound"},
                                                               {"name": "Windows WASAPI"}]), \
             patch.object(voz.sd, "check_input_settings", side_effect=verificar), \
             patch.object(voz.sd, "default") as padrao:
            padrao.device = [0, 0]
            self.assertEqual(voz.listar_microfones_recomendados(),
                             [("Microfone USB · Windows DirectSound", 0)])
            with self.assertRaisesRegex(RuntimeError, "16 kHz"):
                voz.resolver_microfone("Microfone USB · Windows WASAPI")

    def test_silencio_nao_e_enviado_ao_whisper(self):
        with (
            patch.object(voz, "capturar_audio", return_value=np.empty(0, dtype=np.float32)),
            patch.object(voz, "carregar_modelo") as modelo,
        ):
            self.assertEqual(voz.ouvir(), "")
        modelo.assert_not_called()

    def test_transcricao_usa_audio_detectado_e_junta_segmentos(self):
        audio = np.zeros(16000, dtype=np.float32)
        with (
            patch.object(voz, "capturar_audio", return_value=audio),
            patch.object(voz, "carregar_modelo") as carregar,
        ):
            carregar.return_value.transcribe.return_value = (
                iter([SimpleNamespace(text=" Modo "), SimpleNamespace(text=" texto. ")]),
                None,
            )
            self.assertEqual(voz.ouvir(), "Modo texto.")
        self.assertIs(carregar.return_value.transcribe.call_args.args[0], audio)

    def test_tecla_esc_e_detectada_sem_enter(self):
        teclado = SimpleNamespace(
            kbhit=MagicMock(return_value=True), getwch=MagicMock(return_value="\x1b")
        )
        with (
            patch.object(voz.sys.stdin, "isatty", return_value=True),
            patch.dict("sys.modules", {"msvcrt": teclado}),
        ):
            self.assertTrue(voz.atalho_menu_pressionado())
        teclado.getwch.assert_called_once()

    def test_silero_real_classifica_silencio_e_preserva_estado(self):
        detector = voz.DetectorVoz()
        bloco = np.zeros(voz.AMOSTRAS_POR_BLOCO, dtype=np.float32)
        probabilidades = [detector.probabilidade(bloco) for _ in range(10)]
        self.assertTrue(all(0 <= p < voz.LIMIAR_INICIO for p in probabilidades))


class TrocaModoTests(unittest.TestCase):
    def test_atalho_e_comandos_falados_trocam_modo_sem_consultar_ia(self):
        for comando in ("texto", "Modo texto!", "Mudar para texto."):
            with self.subTest(comando=comando):
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
                    patch.object(main, "reconhecer_voz", side_effect=["Aurora, " + comando, "Aurora, sair"]),
                    patch.object(main, "obter_resposta") as resposta,
                    patch.object(main, "ler_texto", side_effect=["2", "voz"]),
                    contextlib.redirect_stdout(io.StringIO()) as saida,
                ):
                    main.main()
                self.assertIn("Modo texto ativado.", saida.getvalue())
                self.assertIn("Modo microfone ativado.", saida.getvalue())
                resposta.assert_not_called()


class CancelamentoTranscricaoTests(unittest.TestCase):
    def test_cancelar_antes_de_transcrever_evita_modelo(self):
        cancelar = threading.Event()
        with patch.object(voz, "capturar_audio", return_value=np.ones(1600, dtype=np.float32)), \
                patch.object(voz, "transcrever_audio") as transcrever:
            self.assertEqual(voz.ouvir(cancelar=cancelar, ao_capturar=cancelar.set), "")
        transcrever.assert_not_called()

    def test_cancelar_durante_transcricao_descarta_texto(self):
        cancelar = threading.Event()
        def transcrever(_audio):
            cancelar.set()
            return "texto tardio"
        with patch.object(voz, "capturar_audio", return_value=np.ones(1600, dtype=np.float32)), \
                patch.object(voz, "transcrever_audio", side_effect=transcrever):
            self.assertEqual(voz.ouvir(cancelar=cancelar), "")


if __name__ == "__main__":
    unittest.main()
