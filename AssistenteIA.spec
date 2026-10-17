"""Empacotamento Windows em pasta, preservando os modelos de voz como recursos."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all


raiz = Path.cwd()
dados = [
    (str(raiz / "vozes" / "pt_BR-faber-medium.onnx"), "vozes"),
    (str(raiz / "vozes" / "pt_BR-faber-medium.onnx.json"), "vozes"),
    (str(raiz / "config_voz.json"), "."),
    (str(raiz / "config_internet.json"), "."),
]
binarios = []
ocultos = []
for pacote in ("faster_whisper", "piper", "onnxruntime", "ctranslate2", "sounddevice", "av", "edge_tts"):
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
