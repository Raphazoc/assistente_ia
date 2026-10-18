"""Consulta apenas metadados de releases públicas do projeto."""

import json
import hashlib
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from . import caminhos
from .versao import VERSAO


API_RELEASES = "https://api.github.com/repos/Raphazoc/assistente_ia/releases?per_page=20"
PAGINA_RELEASES = "https://github.com/Raphazoc/assistente_ia/releases/"
VERSAO_VALIDA = re.compile(r"^v?(\d+)\.(\d+)(?:\.(\d+))?(?:(a|b|rc)(\d+))?$", re.I)
ARQUIVO_ESTADO = caminhos.pasta_dados() / "ultima_verificacao.json"
NOME_INSTALADOR = "AssistenteIA-Setup.exe"


class VerificacaoCancelada(Exception):
    """A pessoa cancelou uma consulta pendente."""


def _checar_cancelamento(cancelar):
    if cancelar is not None and cancelar.is_set():
        raise VerificacaoCancelada()


def chave_versao(texto):
    """Ordena versões numéricas e pré-versões sem comparar strings lexicograficamente."""
    encontrado = VERSAO_VALIDA.fullmatch(texto.strip()) if isinstance(texto, str) else None
    if not encontrado:
        return None
    maior, menor, correcao, fase, numero = encontrado.groups()
    ordem = {None: 3, "rc": 2, "b": 1, "a": 0}
    return int(maior), int(menor), int(correcao or 0), ordem[fase.lower() if fase else None], int(numero or 0)


def consultar(versao_atual=VERSAO, abrir=urlopen, cancelar=None):
    """Retorna a release mais nova ou None; falhas são mostradas ao usuário pela interface."""
    atual = chave_versao(versao_atual)
    if atual is None:
        raise ValueError("A versão instalada não é válida.")
    _checar_cancelamento(cancelar)
    pedido = Request(API_RELEASES, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "AssistenteIA/" + versao_atual,
    })
    with abrir(pedido, timeout=5) as resposta:
        bruto = resposta.read(1_000_001)
    if len(bruto) > 1_000_000:
        raise ValueError("Resposta do GitHub acima do limite.")
    dados = json.loads(bruto)
    _checar_cancelamento(cancelar)
    if not isinstance(dados, list):
        raise ValueError("Resposta inesperada do GitHub.")
    candidatas = []
    for release in dados:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        tag = release.get("tag_name")
        chave = chave_versao(tag)
        url = release.get("html_url")
        if chave is None or not isinstance(url, str) or not url.startswith(PAGINA_RELEASES):
            continue
        if chave > atual:
            digest = ""
            for ativo in release.get("assets") or []:
                if isinstance(ativo, dict) and ativo.get("name") == NOME_INSTALADOR:
                    valor = ativo.get("digest", "")
                    if isinstance(valor, str) and re.fullmatch(r"sha256:[0-9a-fA-F]{64}", valor):
                        digest = valor[7:].lower()
            beta = bool(release.get("prerelease") or chave[3] < 3)
            candidatas.append((chave, tag, url, release.get("body", ""), beta, digest))
    if not candidatas:
        return None
    _, tag, url, notas, beta, digest = max(candidatas, key=lambda item: item[0])
    return {"versao": tag, "url": url, "notas": notas[:3000] if isinstance(notas, str) else "",
            "beta": beta, "sha256": digest}


def salvar_ultima_verificacao(status, release=None):
    """Persiste somente metadados públicos, nunca conversas ou credenciais."""
    if status not in {"atualizada", "disponivel", "falha", "cancelada"}:
        raise ValueError("Estado de atualização inválido.")
    dados = {"status": status, "versao": release["versao"] if release else "",
             "verificado_em": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    ARQUIVO_ESTADO.parent.mkdir(parents=True, exist_ok=True)
    temporario = ARQUIVO_ESTADO.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False) + "\n", encoding="utf-8")
    temporario.replace(ARQUIVO_ESTADO)
    return dados


def carregar_ultima_verificacao():
    try:
        dados = json.loads(ARQUIVO_ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(dados, dict) or dados.get("status") not in {"atualizada", "disponivel", "falha", "cancelada"}:
        return None
    if not isinstance(dados.get("verificado_em"), str) or not isinstance(dados.get("versao"), str):
        return None
    if len(dados["verificado_em"]) > 40 or len(dados["versao"]) > 30:
        return None
    try:
        datetime.fromisoformat(dados["verificado_em"])
    except ValueError:
        return None
    if dados["versao"] and chave_versao(dados["versao"]) is None:
        return None
    return dados


def verificar_instalador(arquivo, release, verificar_assinatura=None):
    """Confere digest da release e Authenticode; não executa o instalador."""
    atual, nova = chave_versao(VERSAO), chave_versao(release.get("versao"))
    if nova is None or nova <= atual:
        raise ValueError("Esta versão é igual ou anterior à instalada; downgrade recusado.")
    esperado = release.get("sha256", "")
    if not isinstance(esperado, str) or not re.fullmatch(r"[0-9a-f]{64}", esperado):
        raise ValueError("A release não publicou um SHA-256 verificável para o instalador.")
    caminho = Path(arquivo)
    if not caminho.is_file() or caminho.is_symlink() or caminho.name != NOME_INSTALADOR:
        raise ValueError("Selecione o instalador AssistenteIA-Setup.exe baixado da release.")
    digest = hashlib.sha256()
    with caminho.open("rb") as entrada:
        for bloco in iter(lambda: entrada.read(1024 * 1024), b""):
            digest.update(bloco)
    if digest.hexdigest() != esperado:
        raise ValueError("O SHA-256 do instalador não corresponde à release.")
    assinatura = verificar_assinatura or _assinatura_windows
    if not assinatura(caminho):
        raise ValueError("A assinatura Authenticode do instalador é inválida.")
    return True


def _assinatura_windows(caminho):
    if os.name != "nt":
        return False
    script = "$s=Get-AuthenticodeSignature -LiteralPath $env:ASSISTENTE_ARQUIVO_VERIFICAR; if($s.Status -eq 'Valid' -and $s.TimeStamperCertificate){exit 0}else{exit 1}"
    ambiente = {**os.environ, "ASSISTENTE_ARQUIVO_VERIFICAR": str(caminho.resolve())}
    try:
        resultado = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                                   env=ambiente, capture_output=True, timeout=12, check=False,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return resultado.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
