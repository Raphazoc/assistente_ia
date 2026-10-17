import contextlib
import io
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app import fala
from app import main


class FalaTests(unittest.TestCase):
    def setUp(self):
        self.saida = MagicMock()
        self.dispositivo = patch.object(fala.sd, "RawOutputStream")
        self.stream = self.dispositivo.start()
        self.stream.return_value.__enter__.return_value = self.saida
        self.silenciar = contextlib.redirect_stdout(io.StringIO())
        self.silenciar.__enter__()

    def tearDown(self):
        self.silenciar.__exit__(None, None, None)
        self.dispositivo.stop()

    def test_limpeza_preserva_pontuacao_e_nao_le_codigo_ou_pensamento(self):
        texto = (
            "<think>pensamento interno</think>\n"
            "## Vamos conversar\n"
            "- **Tudo bem?** 😊\n"
            "- Veja [o exemplo](https://example.com).\n"
            "```python\nprint('segredo')\n```"
        )
        limpo = fala.limpar_texto(texto)
        self.assertEqual(
            limpo,
            "Vamos conversar. Tudo bem? Veja o exemplo. "
            "O código está disponível na resposta em texto.",
        )

    def test_negrito_some_da_prosa_sem_alterar_codigo(self):
        texto = "Isso é **natural**.\n```python\nx = 2 ** 3\n```"
        self.assertEqual(main.remover_negrito(texto), "Isso é natural.\n```python\nx = 2 ** 3\n```")

    def test_fontes_permanecem_na_resposta_mas_nao_sao_narradas(self):
        resposta = (
            "A versão atual é esta [1]. Veja também [2](https://exemplo.org/nota).\n\n"
            "Fontes consultadas:\n"
            "[1] Documentação oficial — https://exemplo.org/docs\n"
            "[2] Nota de lançamento — https://exemplo.org/nota"
        )
        falado = fala.limpar_texto(resposta)
        self.assertEqual(falado, "A versão atual é esta. Veja também.")
        self.assertIn("Fontes consultadas:", resposta)
        self.assertNotIn("https://", falado)

    def test_elevenlabs_recebe_apenas_texto_limpo_e_id_configurado(self):
        resposta = MagicMock()
        resposta.read.return_value = b"mp3"
        contexto = MagicMock()
        contexto.__enter__.return_value = resposta
        with patch.object(fala.servicos, "carregar", return_value={"voz": "elevenlabs", "voice_id": "voz123"}), \
             patch.object(fala.servicos, "obter_chave", return_value="chave"), \
             patch.object(fala, "urlopen", return_value=contexto) as abrir, \
             patch.object(fala, "decodificar_mp3", return_value=b"pcm"):
            audio = fala.gerar_audio_elevenlabs(fala.limpar_texto("Resposta **natural**.\n\nFontes consultadas:\n1. fonte"))
        pedido = abrir.call_args.args[0]
        self.assertEqual(audio, b"pcm")
        self.assertIn("/voz123?", pedido.full_url)
        self.assertEqual(pedido.get_header("Xi-api-key"), "chave")
        self.assertIn('"text": "Resposta natural."', pedido.data.decode())
        self.assertNotIn("Fontes", pedido.data.decode())

    def test_seletor_de_voz_usa_elevenlabs_quando_configurada(self):
        with patch.object(fala.servicos, "carregar", return_value={"voz": "elevenlabs", "voice_id": "voz123"}), \
             patch.object(fala, "_online_indisponivel_ate", 0), \
             patch.object(fala, "falar_online") as online:
            fala.falar("Olá **amigo**.")
        self.assertEqual(online.call_args.args, ("Olá amigo.",))
        self.assertIs(online.call_args.kwargs["gerar"], fala.gerar_audio_elevenlabs)

    def test_divisao_preserva_texto_e_prioriza_pausas(self):
        texto = " ".join([
            "Podemos conversar com calma e continuar o projeto aos poucos."
        ] * 30)
        trechos = fala.dividir_texto(texto)
        self.assertEqual(" ".join(trechos), texto)
        self.assertTrue(all(len(t) <= fala.MAX_CARACTERES_TRECHO for t in trechos))
        self.assertTrue(all(t.endswith(".") for t in trechos))

    def test_audio_seguinte_e_gerado_enquanto_o_atual_toca(self):
        gerando_segundo = threading.Event()
        permitir_segundo = threading.Event()

        def gerar(texto):
            if texto == "Segundo.":
                gerando_segundo.set()
                if not permitir_segundo.wait(timeout=3):
                    raise RuntimeError("A reprodução não iniciou.")
                return b"\x02\x00"
            return b"\x01\x00"

        def escrever(audio):
            if audio == b"\x01\x00":
                try:
                    self.assertTrue(gerando_segundo.wait(timeout=3))
                finally:
                    permitir_segundo.set()

        self.saida.write.side_effect = escrever
        with (
            patch.object(fala, "dividir_texto", return_value=["Primeiro.", "Segundo."]),
            patch.object(fala, "gerar_audio_online", side_effect=gerar),
        ):
            fala.falar_online("Primeiro. Segundo.")

        self.assertEqual(self.saida.write.call_count, 2)
        self.stream.assert_called_once()

    def test_falha_depois_de_um_trecho_reproduz_so_o_restante_na_voz_local(self):
        with (
            patch.object(fala, "_online_indisponivel_ate", 0),
            patch.object(fala, "dividir_texto", return_value=["Primeiro.", "Segundo.", "Terceiro."]),
            patch.object(fala, "gerar_audio_online", side_effect=[b"\x01\x00", OSError("Sem rede")]),
            patch.object(fala, "falar_local") as local,
        ):
            fala.falar("Primeiro. Segundo. Terceiro.")
            local.assert_called_once_with("Segundo. Terceiro.")
            self.assertGreater(fala._online_indisponivel_ate, 0)

        self.saida.write.assert_called_once_with(b"\x01\x00")

    def test_falha_inicial_e_recuo_evitam_tentar_a_rede_em_toda_resposta(self):
        with (
            patch.object(fala, "_online_indisponivel_ate", 0),
            patch.object(fala, "falar_online", side_effect=fala.FalhaVozOnline("Olá.", OSError("Sem rede"))) as online,
            patch.object(fala, "falar_local") as local,
        ):
            fala.falar("Olá.")
            fala.falar("Vamos continuar.")
            online.assert_called_once()
            self.assertEqual(local.call_count, 2)
            local.assert_called_with("Vamos continuar.")

    def test_erro_da_api_assincrona_e_propagado_sem_travar(self):
        async def sem_rede():
            raise OSError("Sem rede")
            yield  # Faz a função se comportar como o gerador assíncrono da API.

        with patch("edge_tts.Communicate") as comunicador:
            comunicador.return_value.stream.side_effect = sem_rede
            with self.assertRaisesRegex(OSError, "Sem rede"):
                fala.gerar_audio_online("Olá.")

    def test_sem_texto_nao_acessa_rede_ou_dispositivo(self):
        with patch.object(fala, "falar_online") as online:
            fala.falar("😊 ** **")
        online.assert_not_called()
        self.stream.assert_not_called()

    def test_voz_local_tambem_usa_um_fluxo_continuo(self):
        trecho = SimpleNamespace(
            sample_rate=22050, sample_channels=1, audio_int16_bytes=b"\x01\x00"
        )
        voz = MagicMock()
        voz.synthesize.return_value = iter([trecho, trecho])
        with patch.object(fala, "carregar_voz", return_value=voz):
            fala.falar_local("Olá. Tudo bem?")
        self.stream.assert_called_once()
        self.assertEqual(self.saida.write.call_count, 2)

    def test_orientacao_de_conversa_e_aplicada_somente_no_modo_voz(self):
        for modo in [False, True]:
            with (
                patch.object(main, "buscar_memorias", return_value=[]),
                patch.object(main, "chat", return_value={"message": {"content": "Tudo bem!"}}) as chat,
            ):
                main.obter_resposta(None, [], "Olá", modo_voz=modo)
            contexto = chat.call_args.kwargs["messages"][0]["content"]
            self.assertEqual("Você está conversando por voz." in contexto, modo)


if __name__ == "__main__":
    unittest.main()
