"""Verificações de primeira execução, sem consultar serviços externos."""

import json
import os
import re
import shutil
import subprocess
import sys
import ctypes
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

import numpy as np
import sounddevice as sd


OLLAMA_LOCAL = "http://127.0.0.1:11434"
VERSAO_MINIMA_OLLAMA = (0, 6, 0)


def versao_compativel(texto):
    """Aceita a numeração estável do servidor; versões não reconhecidas ficam pendentes."""
    encontrado = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:$|[-+])", texto.strip())
    return tuple(map(int, encontrado.groups())) >= VERSAO_MINIMA_OLLAMA if encontrado else None


def memoria_ram_gb():
    if os.name == "nt":
        class EstadoMemoria(ctypes.Structure):
            _fields_ = [("tamanho", ctypes.c_ulong), ("carga", ctypes.c_ulong),
                        ("total_fisico", ctypes.c_ulonglong), ("livre_fisico", ctypes.c_ulonglong),
                        ("total_pagina", ctypes.c_ulonglong), ("livre_pagina", ctypes.c_ulonglong),
                        ("total_virtual", ctypes.c_ulonglong), ("livre_virtual", ctypes.c_ulonglong),
                        ("livre_estendido", ctypes.c_ulonglong)]
        estado = EstadoMemoria()
        estado.tamanho = ctypes.sizeof(estado)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado)):
            return round(estado.total_fisico / 1024 ** 3, 1)
    elif hasattr(os, "sysconf"):
        try:
            return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3, 1)
        except (OSError, ValueError):
            pass
    return None


def vram_nvidia_gb():
    """Consulta local e opcional; indisponível em PCs sem NVIDIA ou sem utilitário."""
    if not shutil.which("nvidia-smi"):
        return None
    try:
        resposta = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3, check=True,
        )
        valores = [int(linha.strip()) for linha in resposta.stdout[:1000].splitlines() if linha.strip().isdigit()]
        return round(max(valores) / 1024, 1) if valores else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


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
    from . import configuracao, diagnostico, fala, versao

    try:
        modelos_escolhidos = configuracao.carregar()
    except ValueError:
        modelos_escolhidos = configuracao.PADRAO
    resultado = {
        "versao_app": versao.VERSAO,
        "ollama_instalado": shutil.which("ollama") is not None,
        "ollama_ativo": False,
        "ollama_versao": "",
        "ollama_versao_compativel": None,
        "modelos": [],
        "modelo_conversa": modelos_escolhidos["modelo"],
        "modelo_memoria": modelos_escolhidos["modelo_memoria"],
        "modelo_conversa_disponivel": False,
        "modelo_memoria_disponivel": False,
        "ram_gb": memoria_ram_gb(),
        "vram_nvidia_gb": vram_nvidia_gb(),
        "microfone": False,
        "alto_falante": False,
        "python": sys.version.split()[0],
        "erro_ollama": "",
        "voz_local": fala.MODELO_VOZ.is_file(),
        "eventos_recentes": diagnostico.eventos_recentes(),
    }
    try:
        resultado["ollama_versao"] = str(_obter_json("/api/version").get("version", ""))
        resultado["ollama_versao_compativel"] = versao_compativel(resultado["ollama_versao"])
        dados = _obter_json("/api/tags")
        resultado["modelos"] = sorted({str(modelo.get("name", "")) for modelo in dados.get("models", [])
                                        if isinstance(modelo, dict) and modelo.get("name")})
        resultado["ollama_ativo"] = True
        resultado["modelo_conversa_disponivel"] = resultado["modelo_conversa"] in resultado["modelos"]
        resultado["modelo_memoria_disponivel"] = resultado["modelo_memoria"] in resultado["modelos"]
    except Exception as erro:
        resultado["erro_ollama"] = type(erro).__name__
    try:
        dispositivos = sd.query_devices()
        resultado["microfone"] = any(d.get("max_input_channels", 0) > 0 for d in dispositivos)
        resultado["alto_falante"] = any(d.get("max_output_channels", 0) > 0 for d in dispositivos)
    except Exception:
        pass
    return resultado


def testar_microfone(selecao=None):
    """Mede por dois segundos sem guardar a gravação."""
    from . import voz
    with sd.InputStream(samplerate=16000, channels=1, dtype="float32", blocksize=1024,
                        device=voz.resolver_microfone(selecao)) as entrada:
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
