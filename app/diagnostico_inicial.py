"""Verificações de primeira execução, sem consultar serviços externos."""

import json
import os
import shutil
import sys
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

import numpy as np
import sounddevice as sd


OLLAMA_LOCAL = "http://127.0.0.1:11434"


def caminho_publico(caminho):
    """Mostra locais úteis sem copiar o nome da conta do Windows."""
    texto = str(caminho)
    raizes = (
        (os.environ.get("LOCALAPPDATA", ""), "%LOCALAPPDATA%"),
        (str(Path.home()), "%USERPROFILE%"),
    )
    for raiz, nome in raizes:
        if raiz and (texto.casefold() == raiz.casefold() or
                     texto.casefold().startswith((raiz + os.sep).casefold())):
            return nome + texto[len(raiz):]
    return Path(texto).name


def _obter_json(caminho):
    with build_opener(ProxyHandler({})).open(OLLAMA_LOCAL + caminho, timeout=3) as resposta:
        bruto = resposta.read(1_000_001)
    if len(bruto) > 1_000_000:
        raise ValueError("Resposta do Ollama acima do limite.")
    return json.loads(bruto)


def verificar():
    """Retorna apenas estados técnicos, sem conversas ou credenciais."""
    from . import diagnostico, fala, versao
    resultado = {
        "versao_app": versao.VERSAO,
        "ollama_instalado": shutil.which("ollama") is not None,
        "ollama_ativo": False,
        "ollama_versao": "",
        "modelos": [],
        "microfone": False,
        "alto_falante": False,
        "python": sys.version.split()[0],
        "erro_ollama": "",
        "voz_local": fala.MODELO_VOZ.is_file(),
        "eventos_recentes": diagnostico.eventos_recentes(),
    }
    try:
        resultado["ollama_versao"] = str(_obter_json("/api/version").get("version", ""))
        dados = _obter_json("/api/tags")
        resultado["modelos"] = sorted({str(modelo.get("name", "")) for modelo in dados.get("models", [])
                                        if isinstance(modelo, dict) and modelo.get("name")})
        resultado["ollama_ativo"] = True
    except Exception as erro:
        resultado["erro_ollama"] = type(erro).__name__
    try:
        dispositivos = sd.query_devices()
        resultado["microfone"] = any(d.get("max_input_channels", 0) > 0 for d in dispositivos)
        resultado["alto_falante"] = any(d.get("max_output_channels", 0) > 0 for d in dispositivos)
    except Exception:
        pass
    return resultado


def testar_microfone():
    """Mede por dois segundos sem guardar a gravação."""
    with sd.InputStream(samplerate=16000, channels=1, dtype="float32", blocksize=1024) as entrada:
        niveis = []
        for _ in range(32):
            audio, _ = entrada.read(1024)
            niveis.append(float(np.sqrt(np.mean(audio * audio))))
    return max(niveis, default=0.0)


def testar_alto_falante():
    """Reproduz um tom curto no dispositivo padrão."""
    t = np.arange(0, int(0.35 * 22050)) / 22050
    tom = (0.15 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sd.play(tom, samplerate=22050)
    sd.wait()


def testar_voz():
    from . import fala
    fala.falar("Olá. Este é um teste da voz da assistente.")
