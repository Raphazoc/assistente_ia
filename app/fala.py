import asyncio
import io
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from urllib.request import Request, urlopen

import emoji
import sounddevice as sd
from .controles import InterromperFala, SolicitarMenu, tecla_durante_fala
from . import diagnostico
from . import servicos


PASTA_PROJETO = Path(__file__).resolve().parent.parent
MODELO_VOZ = PASTA_PROJETO / "resources" / "vozes" / "pt_BR-faber-medium.onnx"

# A voz principal envia o texto a ser falado ao serviço online da Microsoft.
# Para uma voz feminina, use "pt-BR-FranciscaNeural".
VOZ_ONLINE = "pt-BR-AntonioNeural"
VELOCIDADE_ONLINE = "+3%"
TOM_ONLINE = "+0Hz"
USAR_VOZ_ONLINE = True
TAXA_AUDIO_ONLINE = 24000
MAX_CARACTERES_TRECHO = 450
INTERVALO_RECONEXAO = 60
_online_indisponivel_ate = 0.0


class FalhaVozOnline(Exception):
    """Guarda somente o texto que ainda não foi reproduzido."""

    def __init__(self, texto_pendente, erro):
        super().__init__(str(erro))
        self.texto_pendente = texto_pendente


@lru_cache(maxsize=1)
def carregar_voz():
    """Carrega uma única vez o modelo local usado como reserva de voz."""
    from piper import PiperVoice

    if not MODELO_VOZ.exists():
        raise FileNotFoundError(f"Modelo de voz não encontrado: {MODELO_VOZ}")
    print("Carregando voz local de reserva...")
    return PiperVoice.load(str(MODELO_VOZ))


def limpar_texto(texto):
    """Preserva a pontuação da fala e remove conteúdo que não deve ser lido."""
    texto = re.split(r"(?im)^\s*Fontes consultadas:\s*$", texto, maxsplit=1)[0]
    texto = re.sub(r"<think>.*?(?:</think>|$)", "", texto, flags=re.S)
    texto = re.sub(
        r"```.*?(?:```|$)",
        " O código está disponível na resposta em texto. ",
        texto,
        flags=re.S,
    )
    texto = emoji.replace_emoji(texto, replace="")
    texto = re.sub(r"\[(?:\d+(?:\s*[,;-]\s*\d+)*)\]\(https?://[^)]+\)", "", texto)
    texto = re.sub(r"!?\[([^\]]+)\]\([^)]+\)", r"\1", texto)
    texto = re.sub(r"\s*\[(?:\d+(?:\s*[,;-]\s*\d+)*)\](?!\()", "", texto)
    texto = re.sub(r"https?://\S+", "", texto)
    texto = re.sub(r"\s+([.!?,;:])", r"\1", texto)
    texto = re.sub(r"(?m)^\s*(?:#{1,6}\s+|[-*+>]\s+|\d+[.)]\s+)", "", texto)
    texto = re.sub(r"[*`#_]", "", texto)
    texto = re.sub(r"(?m)^\s*[-=]{3,}\s*$", "", texto)

    # Listas e títulos viram frases, em vez de emendar todas as linhas.
    linhas = []
    for linha in texto.splitlines():
        linha = " ".join(linha.split())
        if linha:
            if linha[-1] not in ".!?;:,":
                linha += "."
            linhas.append(linha)
    return " ".join(linhas)


def dividir_texto(texto):
    """Agrupa frases para preservar a entonação, com início de fala mais rápido."""
    trechos = []
    while len(texto) > MAX_CARACTERES_TRECHO:
        janela = texto[:MAX_CARACTERES_TRECHO + 1]
        pausas = list(re.finditer(r"[.!?;:,]\s+", janela))
        pausas = [p for p in pausas if p.end() >= MAX_CARACTERES_TRECHO // 2]
        corte = pausas[-1].end() if pausas else janela.rfind(" ")
        if corte <= 0:
            corte = texto.find(" ", MAX_CARACTERES_TRECHO)
            if corte < 0:
                break
        trechos.append(texto[:corte].strip())
        texto = texto[corte:].strip()
    if texto:
        trechos.append(texto)
    return trechos


def gerar_audio_online(texto):
    """Recebe MP3 e converte para PCM em memória, sem player externo."""
    import av
    import edge_tts

    comunicador = edge_tts.Communicate(
        texto,
        voice=VOZ_ONLINE,
        rate=VELOCIDADE_ONLINE,
        pitch=TOM_ONLINE,
        connect_timeout=4,
        receive_timeout=8,
    )
    async def receber_audio():
        partes = []
        async for evento in comunicador.stream():
            if evento["type"] == "audio":
                partes.append(evento["data"])
        return b"".join(partes)

    async def receber_com_prazo():
        return await asyncio.wait_for(receber_audio(), timeout=15)

    # A API assíncrona propaga erros de rede, permitindo usar a voz local.
    mp3 = asyncio.run(receber_com_prazo())
    if not mp3:
        raise RuntimeError("O serviço de voz não retornou áudio.")

    return decodificar_mp3(mp3)


def gerar_audio_elevenlabs(texto):
    """Solicita áudio à voz configurada na ElevenLabs."""
    opcoes = servicos.carregar()
    identificador = opcoes["voice_id"]
    chave = servicos.obter_chave("elevenlabs")
    if not identificador or not chave:
        raise ValueError("Configure a chave e o ID da voz ElevenLabs.")
    pedido = Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{identificador}?output_format=mp3_44100_128",
        data=json.dumps({"text": texto, "model_id": "eleven_multilingual_v2"}).encode("utf-8"),
        headers={"xi-api-key": chave, "Content-Type": "application/json", "Accept": "audio/mpeg"},
        method="POST",
    )
    with urlopen(pedido, timeout=15) as resposta:
        mp3 = resposta.read(6_000_001)
    if not mp3 or len(mp3) > 6_000_000:
        raise ValueError("A API de voz retornou áudio vazio ou acima do limite.")
    return decodificar_mp3(mp3)


def decodificar_mp3(mp3):
    """Converte MP3 recebido dos provedores em PCM para a saída de áudio."""

    conversor = av.AudioResampler(format="s16", layout="mono", rate=TAXA_AUDIO_ONLINE)
    partes = []
    with av.open(io.BytesIO(mp3), format="mp3") as arquivo:
        for quadro in arquivo.decode(audio=0):
            for convertido in conversor.resample(quadro):
                partes.append(convertido.to_ndarray().tobytes())
        for convertido in conversor.resample(None):
            partes.append(convertido.to_ndarray().tobytes())
    audio = b"".join(partes)
    if not audio:
        raise RuntimeError("O áudio recebido não pôde ser decodificado.")
    return audio


def verificar_interrupcao(controle):
    """Propaga comandos de menu ou cancelamento durante a reprodução."""
    if controle is not None:
        controle.verificar()
    else:
        tecla = tecla_durante_fala()
        if tecla == "menu":
            raise SolicitarMenu()
        if tecla == "parar":
            raise InterromperFala()


@contextmanager
def executor_audio():
    """Fornece um executor para preparar áudio sem bloquear a reprodução."""
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        yield executor
    finally:
        # Uma requisição em andamento pode terminar sem atrasar o menu/cancelamento.
        executor.shutdown(wait=False, cancel_futures=True)


def aguardar_audio(futuro, controle):
    """Aguarda áudio pronto enquanto continua aceitando interrupções."""
    while not futuro.done():
        verificar_interrupcao(controle)
        time.sleep(0.02)
    verificar_interrupcao(controle)
    return futuro.result()


def escrever_audio(saida, audio, taxa, controle):
    """Envia o áudio ao dispositivo em blocos curtos e canceláveis."""
    tamanho = max(2, int(taxa * 0.02) * 2)
    try:
        for inicio in range(0, len(audio), tamanho):
            verificar_interrupcao(controle)
            saida.write(audio[inicio:inicio + tamanho])
    except BaseException:
        saida.abort()  # Descarta também o áudio que já estava no buffer do dispositivo.
        raise


def falar_online(texto, controle=None, gerar=None):
    """Reproduz texto usando a voz online com preparação antecipada dos trechos."""
    trechos = dividir_texto(texto)
    if not trechos:
        return
    gerar = gerar or gerar_audio_online
    with executor_audio() as executor:
        proximo = executor.submit(gerar, trechos[0])
        # Só abre o dispositivo depois de obter o primeiro áudio válido.
        try:
            audio = aguardar_audio(proximo, controle)
        except (InterromperFala, SolicitarMenu):
            raise
        except Exception as erro:
            raise FalhaVozOnline(texto, erro) from erro

        with sd.RawOutputStream(
            samplerate=TAXA_AUDIO_ONLINE, channels=1, dtype="int16", latency="high"
        ) as saida:
            for indice, trecho in enumerate(trechos):
                if indice:
                    try:
                        audio = aguardar_audio(proximo, controle)
                    except (InterromperFala, SolicitarMenu):
                        saida.abort()
                        raise
                    except Exception as erro:
                        pendente = " ".join(trechos[indice:])
                        raise FalhaVozOnline(pendente, erro) from erro
                if indice + 1 < len(trechos):
                    # Gera o próximo trecho enquanto o atual está tocando.
                    proximo = executor.submit(gerar, trechos[indice + 1])
                escrever_audio(saida, audio, TAXA_AUDIO_ONLINE, controle)


def falar_local(texto, controle=None):
    """Reproduz texto pelo modelo local quando a voz online falha ou é desligada."""
    from piper import SynthesisConfig

    voz = carregar_voz()
    configuracao = SynthesisConfig(
        length_scale=0.94, noise_scale=0.7, noise_w_scale=0.8,
    )
    gerador = iter(voz.synthesize(texto, syn_config=configuracao))
    trecho = next(gerador, None)
    if trecho is None:
        return

    with executor_audio() as executor:
        with sd.RawOutputStream(
            samplerate=trecho.sample_rate,
            channels=trecho.sample_channels,
            dtype="int16",
            latency="high",
        ) as saida:
            while trecho is not None:
                proximo = executor.submit(next, gerador, None)
                escrever_audio(saida, trecho.audio_int16_bytes, trecho.sample_rate, controle)
                try:
                    trecho = aguardar_audio(proximo, controle)
                except (InterromperFala, SolicitarMenu):
                    saida.abort()
                    raise


def falar(texto, controle=None):
    """Escolhe a voz configurada e aplica a limpeza do texto antes de falar."""
    try:
        _falar(texto, controle)
    except InterromperFala:
        print("[VOZ] Fala interrompida.")


def _falar(texto, controle=None):
    """Executa a estratégia de voz e preserva o texto pendente em uma falha online."""
    global _online_indisponivel_ate

    texto = limpar_texto(texto)
    if not texto:
        return
    print("\nIA está falando...")
    if USAR_VOZ_ONLINE and time.monotonic() >= _online_indisponivel_ate:
        try:
            if servicos.carregar()["voz"] == "elevenlabs":
                falar_online(texto, controle=controle, gerar=gerar_audio_elevenlabs)
            elif controle is None:
                falar_online(texto)
            else:
                falar_online(texto, controle=controle)
            return
        except FalhaVozOnline as erro:
            _online_indisponivel_ate = time.monotonic() + INTERVALO_RECONEXAO
            diagnostico.registrar("voz.online_falhou", erro=erro.__cause__ or erro)
            print("[VOZ] Serviço online indisponível; usando voz local.")
            texto = erro.texto_pendente
    try:
        if controle is None:
            falar_local(texto)
        else:
            falar_local(texto, controle=controle)
    except Exception as erro:
        diagnostico.registrar("voz.local_falhou", erro=erro)
        raise


def main():
    falar(
        "Olá! Como foi o seu dia? Estou aqui para conversar com você. "
        "Podemos continuar o seu projeto com calma, uma etapa de cada vez."
    )


if __name__ == "__main__":
    main()
