"""Preferências de provedores; chaves ficam no cofre do sistema operacional."""

import json
from . import caminhos

CONFIGURACAO = caminhos.pasta_dados() / "config_servicos.json"
SERVICO_CREDENCIAIS = "AssistenteIA"
PADRAO = {"buscador": "duckduckgo", "voz": "edge", "voice_id": ""}
BUSCADORES = {"duckduckgo", "brave"}
VOZES = {"edge", "elevenlabs"}


def id_voz_valido(valor):
    return isinstance(valor, str) and len(valor) <= 80 and all(
        c.isascii() and (c.isalnum() or c in "_-") for c in valor
    )


def carregar():
    try:
        dados = json.loads(CONFIGURACAO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dados = {}
    if not isinstance(dados, dict):
        dados = {}
    return {
        "buscador": dados.get("buscador") if dados.get("buscador") in BUSCADORES else PADRAO["buscador"],
        "voz": dados.get("voz") if dados.get("voz") in VOZES else PADRAO["voz"],
        "voice_id": dados.get("voice_id", "") if id_voz_valido(dados.get("voice_id", "")) else "",
    }


def salvar(buscador, voz, voice_id=""):
    if buscador not in BUSCADORES or voz not in VOZES:
        raise ValueError("Provedor inválido.")
    voice_id = voice_id.strip()
    if not id_voz_valido(voice_id):
        raise ValueError("Identificador de voz inválido.")
    CONFIGURACAO.parent.mkdir(parents=True, exist_ok=True)
    temporario = CONFIGURACAO.with_suffix(".tmp")
    temporario.write_text(json.dumps({"buscador": buscador, "voz": voz, "voice_id": voice_id}, indent=2) + "\n", encoding="utf-8")
    temporario.replace(CONFIGURACAO)


def obter_chave(provedor):
    if provedor not in {"brave", "elevenlabs"}:
        raise ValueError("Provedor de API inválido.")
    import keyring
    return keyring.get_password(SERVICO_CREDENCIAIS, provedor) or ""


def salvar_chave(provedor, chave):
    if provedor not in {"brave", "elevenlabs"}:
        raise ValueError("Provedor de API inválido.")
    import keyring
    if chave:
        keyring.set_password(SERVICO_CREDENCIAIS, provedor, chave.strip())
    else:
        try:
            keyring.delete_password(SERVICO_CREDENCIAIS, provedor)
        except keyring.errors.PasswordDeleteError:
            pass
