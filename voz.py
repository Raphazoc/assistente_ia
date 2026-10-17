
import math
import os
import sys
import threading
from collections import deque
from functools import lru_cache

import numpy as np
import sounddevice as sd
from controles import SolicitarMenu


TAXA_AMOSTRAGEM = 16000
AMOSTRAS_POR_BLOCO = 512  # Janela de 32 ms usada pelo Silero VAD v6.
SILENCIO_FINAL = 0.7
DURACAO_MINIMA_FALA = 0.12
DURACAO_MAXIMA_FALA = 30
TEMPO_ESPERA_INICIO = 10
MARGEM_INICIO = 0.25
LIMIAR_INICIO = 0.5
LIMIAR_CONTINUACAO = 0.35
_trava_transcricao = threading.Lock()


class FiltroRuido:
    """Filtro passa-faixa com estado e limiar adaptativo de energia do ambiente."""

    def __init__(self):
        self.x_anterior = self.alta_anterior = self.baixa_anterior = 0.0
        self.ruido = 0.0005

    def processar(self, bloco):
        alta = 1 / (1 + 2 * math.pi * 80 / TAXA_AMOSTRAGEM)
        baixa = 1 - math.exp(-2 * math.pi * 4500 / TAXA_AMOSTRAGEM)
        saida = np.empty_like(bloco)
        for indice, valor in enumerate(bloco):
            atual = alta * (self.alta_anterior + float(valor) - self.x_anterior)
            self.x_anterior, self.alta_anterior = float(valor), atual
            self.baixa_anterior += baixa * (atual - self.baixa_anterior)
            saida[indice] = self.baixa_anterior
        return saida

    def validar(self, bloco, probabilidade):
        energia = float(np.sqrt(np.mean(bloco * bloco)))
        if probabilidade < 0.2:
            self.ruido = 0.95 * self.ruido + 0.05 * energia
        return probabilidade if energia >= max(0.001, self.ruido * 1.8) else 0.0


@lru_cache(maxsize=1)
def carregar_modelo():
    from faster_whisper import WhisperModel

    print("Carregando reconhecimento de voz...")
    return WhisperModel("base", device="cpu", compute_type="int8")


class DetectorVoz:
    """Executa o Silero incluído no Whisper, preservando o estado entre blocos."""

    def __init__(self):
        from faster_whisper.vad import get_vad_model

        self.sessao = get_vad_model().session
        self.h = np.zeros((1, 1, 128), dtype=np.float32)
        self.c = np.zeros((1, 1, 128), dtype=np.float32)
        self.contexto = np.zeros(64, dtype=np.float32)

    def probabilidade(self, bloco):
        entrada = np.concatenate((self.contexto, bloco)).reshape(1, -1)
        probabilidades, self.h, self.c = self.sessao.run(
            None, {"input": entrada, "h": self.h, "c": self.c}
        )
        self.contexto = bloco[-64:].copy()
        return float(np.asarray(probabilidades).reshape(-1)[-1])


class GravadorFrase:
    """Encerra a frase por silêncio, sem impor seis segundos a cada gravação."""

    def __init__(self, limite_fala=None):
        self.duracao_bloco = AMOSTRAS_POR_BLOCO / TAXA_AMOSTRAGEM
        self.limite_fala = limite_fala
        self.candidatos = 0
        self.anteriores = deque(
            maxlen=max(1, math.ceil(MARGEM_INICIO / self.duracao_bloco))
        )
        self.blocos = []
        self.iniciou = False
        self.espera = 0
        self.silencio = 0
        self.fala = 0
        self.duracao = 0

    def processar(self, bloco, probabilidade):
        """Retorna True quando terminou a fala ou expirou a espera inicial."""
        limiar = LIMIAR_CONTINUACAO if self.iniciou else LIMIAR_INICIO
        tem_fala = probabilidade >= limiar
        if not self.iniciou:
            self.anteriores.append(bloco.copy())
            self.espera += 1
            self.candidatos = self.candidatos + 1 if tem_fala else 0
            if self.candidatos < 3:
                return self.espera * self.duracao_bloco >= TEMPO_ESPERA_INICIO
            self.iniciou = True
            self.fala = self.duracao = self.candidatos - 1
            self.blocos.extend(self.anteriores)
            self.anteriores.clear()
        else:
            self.blocos.append(bloco.copy())

        self.duracao += 1
        if tem_fala:
            self.fala += 1
            self.silencio = 0
        else:
            self.silencio += 1

        return (
            self.silencio * self.duracao_bloco >= SILENCIO_FINAL
            or self.duracao * self.duracao_bloco >= (
                self.limite_fala if self.limite_fala is not None else DURACAO_MAXIMA_FALA
            )
        )

    def audio(self):
        if self.fala * self.duracao_bloco < DURACAO_MINIMA_FALA:
            return np.empty(0, dtype=np.float32)
        return np.concatenate(self.blocos)


def atalho_menu_pressionado():
    """Lê Esc sem bloquear a captura no terminal do Windows, inclusive no VS Code."""
    if os.name != "nt" or not sys.stdin.isatty():
        return False
    import msvcrt

    while msvcrt.kbhit():
        tecla = msvcrt.getwch()
        if tecla in ("\x00", "\xe0"):
            msvcrt.getwch()  # Segunda parte de uma tecla especial, como as setas.
        elif tecla == "\x1b":
            return True
    return False


def capturar_audio(cancelar=None, teclado=True, anunciar=True, limite_fala=None):
    """Retorna None para abrir o menu, ou um vetor de áudio da frase."""
    if teclado and atalho_menu_pressionado():
        return None
    detector = DetectorVoz()
    gravador = GravadorFrase(limite_fala=limite_fala)
    filtro = FiltroRuido()
    if anunciar:
        print("\nPode falar. Faça uma pausa ao terminar. Esc = menu de modos.")

    with sd.InputStream(
        samplerate=TAXA_AMOSTRAGEM,
        channels=1,
        dtype="float32",
        blocksize=AMOSTRAS_POR_BLOCO,
    ) as microfone:
        while True:
            if (cancelar is not None and cancelar.is_set()) or (teclado and atalho_menu_pressionado()):
                return None
            bloco, perdeu_amostras = microfone.read(AMOSTRAS_POR_BLOCO)
            if perdeu_amostras:
                raise RuntimeError("A captura perdeu áudio. Tente falar novamente.")
            bloco = filtro.processar(bloco[:, 0])
            probabilidade = filtro.validar(bloco, detector.probabilidade(bloco))
            if gravador.processar(bloco, probabilidade):
                return gravador.audio()


def ouvir():
    audio = capturar_audio()
    if audio is None:
        raise SolicitarMenu()
    if not audio.size:
        return ""

    print("Processando sua fala...")
    return transcrever_audio(audio)


def transcrever_audio(audio):
    from ativacao import carregar_configuracao

    palavra = carregar_configuracao()["palavra_ativacao"]
    with _trava_transcricao:
        segmentos, _ = carregar_modelo().transcribe(
            audio, language="pt", vad_filter=True, beam_size=1,
            condition_on_previous_text=False, no_speech_threshold=0.5,
            hotwords=palavra,
            initial_prompt=(
                f"Assistente chamada {palavra}. {palavra}, pare. "
                f"{palavra}, modo texto. {palavra}, menu."
            ),
        )
        return " ".join(
            segmento.text.strip() for segmento in segmentos
            if getattr(segmento, "no_speech_prob", 0) < 0.5
            and getattr(segmento, "avg_logprob", 0) >= -0.8
            and getattr(segmento, "compression_ratio", 0) < 2.2
        ).strip()


def main():
    print("\nReconhecimento de voz iniciado. Esc para encerrar este teste.")
    while True:
        try:
            texto = ouvir()
            if texto.casefold() in ("texto", "sair"):
                break
            if texto:
                print(f"\nVocê disse: {texto}")
        except (KeyboardInterrupt, SolicitarMenu):
            break
        except Exception as erro:
            print(f"Erro no reconhecimento: {erro}")
            break


if __name__ == "__main__":
    main()
