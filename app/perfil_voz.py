"""Verificação local e opcional do locutor para interromper a fala."""

import hashlib
import json
import math
import os
import tempfile
import urllib.request
from functools import lru_cache

import numpy as np

from . import caminhos


MODELO_URL = ("https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34/"
              "resolve/main/voxceleb_resnet34.onnx")
MODELO_SHA256 = "9fea6516d7ad6bf0a76c7689f5a49b65d330fad6dde96c91bb4435ffbfe056a1"
LIMITE_BYTES = 30_000_000
TAXA = 16_000
LIMIAR = 0.60


def caminho_modelo():
    return caminhos.pasta_dados() / "modelos" / "voxceleb_resnet34.onnx"


def caminho_perfil():
    return caminhos.pasta_dados() / "perfil_voz.json"


def modelo_disponivel():
    arquivo = caminho_modelo()
    return arquivo.is_file() and _sha256(arquivo) == MODELO_SHA256


def _sha256(arquivo):
    digest = hashlib.sha256()
    with arquivo.open("rb") as entrada:
        for bloco in iter(lambda: entrada.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def preparar_modelo():
    """Baixa somente o modelo público, confere SHA-256 e grava atomicamente."""
    destino = caminho_modelo()
    if modelo_disponivel():
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = None
    try:
        with urllib.request.urlopen(MODELO_URL, timeout=30) as origem, tempfile.NamedTemporaryFile(
                dir=destino.parent, prefix="modelo_", suffix=".tmp", delete=False) as saida:
            temporario = saida.name
            digest = hashlib.sha256()
            total = 0
            while bloco := origem.read(1024 * 1024):
                total += len(bloco)
                if total > LIMITE_BYTES:
                    raise ValueError("O modelo de voz ultrapassou o tamanho esperado.")
                digest.update(bloco)
                saida.write(bloco)
        if digest.hexdigest() != MODELO_SHA256:
            raise ValueError("O modelo de voz não passou na verificação de integridade.")
        os.replace(temporario, destino)
        return destino
    finally:
        if temporario and os.path.exists(temporario):
            os.unlink(temporario)


@lru_cache(maxsize=1)
def _sessao(caminho):
    import onnxruntime as ort

    opcoes = ort.SessionOptions()
    opcoes.intra_op_num_threads = 2
    opcoes.inter_op_num_threads = 1
    return ort.InferenceSession(str(caminho), sess_options=opcoes,
                                providers=["CPUExecutionProvider"])


def _embedding(audio):
    """FBank Kaldi de 80 bandas, conforme a inferência oficial do WeSpeaker."""
    import kaldi_native_fbank as fbank

    amostras = np.asarray(audio, dtype=np.float32).reshape(-1)
    if not 1.2 * TAXA <= amostras.size <= 10 * TAXA:
        raise ValueError("Fale por pelo menos 1,2 segundo e no máximo 10 segundos.")
    if not np.all(np.isfinite(amostras)) or float(np.sqrt(np.mean(amostras ** 2))) < 0.002:
        raise ValueError("A gravação ficou silenciosa ou inválida. Fale mais perto do microfone.")
    opcoes = fbank.FbankOptions()
    opcoes.frame_opts.samp_freq = TAXA
    opcoes.frame_opts.dither = 0
    opcoes.frame_opts.window_type = "hamming"
    opcoes.mel_opts.num_bins = 80
    extrator = fbank.OnlineFbank(opcoes)
    extrator.accept_waveform(TAXA, (amostras * 32768).tolist())
    extrator.input_finished()
    recursos = np.stack([extrator.get_frame(i) for i in range(extrator.num_frames_ready)]).astype(np.float32)
    recursos -= recursos.mean(axis=0, keepdims=True)
    vetor = _sessao(caminho_modelo()).run(["embs"], {"feats": recursos[None]})[0][0]
    vetor = np.asarray(vetor, dtype=np.float32)
    norma = float(np.linalg.norm(vetor))
    if not math.isfinite(norma) or norma == 0:
        raise ValueError("Não foi possível calcular o perfil de voz.")
    return vetor / norma


def cadastrar(primeira, segunda):
    """Descarta gravações e persiste somente a média dos vetores de locutor."""
    preparar_modelo()
    a, b = _embedding(primeira), _embedding(segunda)
    if float(np.dot(a, b)) < 0.55:
        raise ValueError("As duas gravações não parecem ser da mesma voz. Tente novamente em local silencioso.")
    media = a + b
    media /= np.linalg.norm(media)
    destino = caminho_perfil()
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destino.parent,
                                         prefix="perfil_", suffix=".tmp", delete=False) as saida:
            temporario = saida.name
            json.dump({"modelo": MODELO_SHA256, "vetor": media.tolist()}, saida)
        os.replace(temporario, destino)
    finally:
        if temporario and os.path.exists(temporario):
            os.unlink(temporario)


def cadastrado():
    return caminho_perfil().is_file()


def remover():
    caminho_perfil().unlink(missing_ok=True)


def corresponde(audio):
    """Sem cadastro aceita fala reconhecida; com cadastro falha em modo fechado."""
    if not cadastrado():
        return True
    try:
        if caminho_perfil().stat().st_size > 16_384:
            return False
        dados = json.loads(caminho_perfil().read_text(encoding="utf-8"))
        vetor = np.asarray(dados["vetor"], dtype=np.float32)
        if (dados["modelo"] != MODELO_SHA256 or vetor.shape != (256,)
                or not np.all(np.isfinite(vetor))
                or not 0.9 <= float(np.linalg.norm(vetor)) <= 1.1):
            return False
        if not modelo_disponivel():
            return False
        return float(np.dot(_embedding(audio), vetor)) >= LIMIAR
    except (OSError, ValueError, KeyError, TypeError):
        return False
