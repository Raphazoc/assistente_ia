"""Empacotamento Windows em pasta, preservando os modelos de voz como recursos."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all


raiz = Path.cwd()
dados = [
    (str(raiz / "resources" / "vozes" / "pt_BR-faber-medium.onnx"), "resources/vozes"),
    (str(raiz / "resources" / "vozes" / "pt_BR-faber-medium.onnx.json"), "resources/vozes"),
    (str(raiz / "resources" / "config_voz.json"), "resources"),
    (str(raiz / "resources" / "config_internet.json"), "resources"),
    (str(raiz / "resources" / "config_servicos.json"), "resources"),
    (str(raiz / "resources" / "config_geral.json"), "resources"),
    (str(raiz / "resources" / "assistente_ia.ico"), "resources"),
    (str(raiz / "resources" / "assistente_ia.png"), "resources"),
]
binarios = []
ocultos = []
for pacote in ("faster_whisper", "piper", "onnxruntime", "ctranslate2", "sounddevice", "av", "edge_tts", "keyring", "pygments", "customtkinter"):
    dados_pacote, binarios_pacote, ocultos_pacote = collect_all(pacote)
    dados.extend(dados_pacote)
    binarios.extend(binarios_pacote)
    ocultos.extend(ocultos_pacote)

analise = Analysis(
    [str(raiz / "aplicativo.py")],
    pathex=[str(raiz)],
    binaries=binarios,
    datas=dados,
    hiddenimports=ocultos,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
arquivo_python = PYZ(analise.pure)
executavel = EXE(
    arquivo_python,
    analise.scripts,
    [],
    exclude_binaries=True,
    name="AssistenteIA",
    icon=str(raiz / "resources" / "assistente_ia.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
COLLECT(
    executavel,
    analise.binaries,
    analise.datas,
    strip=False,
    upx=False,
    name="AssistenteIA",
)
