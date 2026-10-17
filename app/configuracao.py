"""Configuração principal validada, sem credenciais ou conteúdo de conversa."""

import json
import re
from pathlib import Path


CONFIGURACAO = Path(__file__).resolve().parent.parent / "resources" / "config_geral.json"
PADRAO = {
    "modelo": "qwen3:8b",
    "modelo_memoria": "qwen3-embedding:0.6b",
    "idioma": "pt-BR",
    "limite_historico": 100,
    "configurado": False,
}
IDIOMAS = {"pt-BR", "en-US"}
PADRAO_MODELO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./:-]{0,119}$")


def validar(dados):
    if not isinstance(dados, dict):
        raise ValueError("A configuração principal deve ser um objeto JSON.")
    desconhecidos = set(dados) - set(PADRAO)
    if desconhecidos:
        raise ValueError("Campos desconhecidos na configuração: " + ", ".join(sorted(desconhecidos)))
    resultado = {**PADRAO, **dados}
    for campo in ("modelo", "modelo_memoria"):
        if not isinstance(resultado[campo], str) or not PADRAO_MODELO.fullmatch(resultado[campo]):
            raise ValueError(f"Campo '{campo}' inválido: escolha um nome de modelo instalado no Ollama.")
    if not isinstance(resultado["idioma"], str) or resultado["idioma"] not in IDIOMAS:
        raise ValueError("Campo 'idioma' inválido: use pt-BR ou en-US.")
    if type(resultado["limite_historico"]) is not int or not 10 <= resultado["limite_historico"] <= 500:
        raise ValueError("Campo 'limite_historico' inválido: use um número de 10 a 500.")
    if type(resultado["configurado"]) is not bool:
        raise ValueError("Campo 'configurado' inválido: use true ou false.")
    return {chave: resultado[chave] for chave in PADRAO}


def carregar():
    try:
        dados = json.loads(CONFIGURACAO.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return PADRAO.copy()
    except (OSError, json.JSONDecodeError) as erro:
        raise ValueError(f"Não foi possível ler {CONFIGURACAO.name}: {erro}") from erro
    return validar(dados)


def salvar(dados):
    validos = validar(dados)
    CONFIGURACAO.parent.mkdir(parents=True, exist_ok=True)
    temporario = CONFIGURACAO.with_suffix(".tmp")
    temporario.write_text(json.dumps(validos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporario.replace(CONFIGURACAO)
    return validos


def aplicar(dados):
    """Atualiza o processo antes de iniciar o motor da conversa."""
    from . import main, voz, fala
    validos = validar(dados)
    main.MODELO = validos["modelo"]
    main.MODELO_MEMORIA = validos["modelo_memoria"]
    main.LIMITE_HISTORICO = validos["limite_historico"]
    main.IDIOMA = validos["idioma"]
    voz.IDIOMA_RECONHECIMENTO = "en" if validos["idioma"] == "en-US" else "pt"
    fala.VOZ_ONLINE = "en-US-GuyNeural" if validos["idioma"] == "en-US" else "pt-BR-AntonioNeural"
    return validos
