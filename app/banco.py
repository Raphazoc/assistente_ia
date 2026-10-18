"""Backup SQLite validado e restauração manual com cópia de segurança."""

import argparse
import hashlib
from contextlib import closing
import os
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from . import caminhos, diagnostico


INTERVALO_BACKUP = timedelta(hours=24)
RETENCAO_AUTOMATICA = 7
NOME_BACKUP = re.compile(r"^(?:automatico|manual|antes_restauro)_\d{8}T\d{6}Z_[0-9a-f]{8}\.db$")
NOME_LEGADO = re.compile(r"^memoria_antes_v2_\d{8}_\d{6}_\d{6}_UTC\.db$")


def pasta_backups(caminho_banco):
    """Retorna a pasta reservada às cópias do banco informado."""
    return Path(caminho_banco).resolve().parent / "backups"


def migrar_backyp(caminho_banco):
    """Arquiva cópias históricas de `backyp` sem criar novas cópias ali."""
    origem = Path(caminho_banco).resolve().parent / "backyp"
    if not origem.is_dir() or origem.is_symlink():
        return 0
    destino = pasta_backups(caminho_banco) / "legado"
    movidos = 0
    for antigo in origem.iterdir():
        if not NOME_LEGADO.fullmatch(antigo.name) or not antigo.is_file() or antigo.is_symlink():
            continue
        destino.mkdir(parents=True, exist_ok=True)
        novo = destino / antigo.name
        if novo.exists():
            continue
        temporario = destino / (antigo.name + ".tmp")
        try:
            shutil.copy2(antigo, temporario)
            def digest(arquivo):
                with arquivo.open("rb") as entrada:
                    return hashlib.file_digest(entrada, "sha256").digest()
            if digest(antigo) != digest(temporario):
                raise OSError("A cópia legada não passou na verificação de integridade.")
            temporario.replace(novo)
            antigo.unlink()
            movidos += 1
        finally:
            temporario.unlink(missing_ok=True)
    return movidos


def _conexao_corresponde(conexao, caminho_banco):
    arquivos = [r[2] for r in conexao.execute("PRAGMA database_list") if r[1] == "main"]
    return bool(arquivos and arquivos[0] and Path(arquivos[0]).resolve() == Path(caminho_banco).resolve())


def verificar_integridade(conexao, exigir_estrutura=False):
    """Confere a integridade SQLite e, opcionalmente, a estrutura esperada."""
    if conexao.execute("PRAGMA integrity_check").fetchone() != ("ok",):
        raise sqlite3.DatabaseError("O banco não passou na verificação de integridade.")
    if exigir_estrutura:
        tabelas = {r[0] for r in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"mensagens", "memorias"}.issubset(tabelas):
            raise sqlite3.DatabaseError("O backup não contém as tabelas esperadas.")


def _novo_nome(tipo):
    agora = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{tipo}_{agora}_{uuid4().hex[:8]}.db"


def criar_backup(conexao, caminho_banco, tipo="manual"):
    """Cria e valida uma cópia consistente do banco usando o backup SQLite."""
    if tipo not in {"automatico", "manual", "antes_restauro"}:
        raise ValueError("Tipo de backup inválido.")
    if not _conexao_corresponde(conexao, caminho_banco):
        raise ValueError("A conexão não corresponde ao banco informado.")
    verificar_integridade(conexao)
    pasta = pasta_backups(caminho_banco)
    pasta.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        pasta.chmod(0o700)
    destino = pasta / _novo_nome(tipo)
    temporario = pasta / (destino.name + ".tmp")
    try:
        with closing(sqlite3.connect(temporario)) as copia:
            conexao.backup(copia)
            verificar_integridade(copia, exigir_estrutura=True)
        if os.name != "nt":
            temporario.chmod(0o600)
        temporario.replace(destino)
    finally:
        temporario.unlink(missing_ok=True)
    diagnostico.registrar("banco.backup_criado")
    if tipo == "automatico":
        automaticos = sorted(pasta.glob("automatico_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        for antigo in automaticos[RETENCAO_AUTOMATICA:]:
            antigo.unlink()
    return destino


def backup_automatico(conexao, caminho_banco):
    """Cria no máximo uma cópia automática por dia de uso, após uma abertura válida."""
    if not _conexao_corresponde(conexao, caminho_banco):
        return None
    pasta = pasta_backups(caminho_banco)
    mais_recente = max(pasta.glob("automatico_*.db"), key=lambda p: p.stat().st_mtime, default=None) if pasta.exists() else None
    if mais_recente is not None:
        idade = datetime.now(timezone.utc) - datetime.fromtimestamp(mais_recente.stat().st_mtime, timezone.utc)
        if idade < INTERVALO_BACKUP:
            return None
    return criar_backup(conexao, caminho_banco, tipo="automatico")


def listar_backups(caminho_banco):
    """Lista somente backups locais com nomes e arquivos válidos."""
    pasta = pasta_backups(caminho_banco)
    return sorted((p for p in pasta.glob("*.db") if NOME_BACKUP.fullmatch(p.name) and not p.is_symlink()), reverse=True) if pasta.exists() else []


def restaurar(caminho_banco, nome_backup):
    """Restaura somente uma cópia da pasta local; o programa deve estar fechado."""
    if not NOME_BACKUP.fullmatch(nome_backup):
        raise ValueError("Informe apenas o nome de um backup listado.")
    caminho_banco = Path(caminho_banco).resolve()
    origem = pasta_backups(caminho_banco) / nome_backup
    if not origem.is_file() or origem.is_symlink():
        raise FileNotFoundError("Backup não encontrado.")
    with closing(sqlite3.connect(f"file:{origem.as_posix()}?mode=ro", uri=True)) as copia:
        verificar_integridade(copia, exigir_estrutura=True)
    if not caminho_banco.exists():
        raise FileNotFoundError("Banco atual não encontrado; restauração automática recusada.")
    if any(Path(str(caminho_banco) + sufixo).exists() for sufixo in ("-wal", "-shm")):
        raise RuntimeError("Feche o programa e finalize o diário SQLite antes de restaurar.")
    with closing(sqlite3.connect(caminho_banco, timeout=0.2)) as atual:
        if atual.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal":
            raise RuntimeError("Feche o banco em modo WAL antes de restaurar.")
        seguranca = criar_backup(atual, caminho_banco, tipo="antes_restauro")
    descritor, nome_temporario = tempfile.mkstemp(prefix=".restaurando_", suffix=".db", dir=caminho_banco.parent)
    os.close(descritor)
    temporario = Path(nome_temporario)
    try:
        shutil.copyfile(origem, temporario)
        with closing(sqlite3.connect(temporario)) as validacao:
            verificar_integridade(validacao, exigir_estrutura=True)
        temporario.replace(caminho_banco)
    finally:
        temporario.unlink(missing_ok=True)
    diagnostico.registrar("banco.restaurado")
    return seguranca


def main():
    """Executa a interface de linha de comando para backup e restauração."""
    argumentos = argparse.ArgumentParser(description="Backup e restauração local da memória SQLite")
    argumentos.add_argument("acao", choices=("listar", "backup", "restaurar"))
    argumentos.add_argument("nome", nargs="?", help="Nome retornado por 'listar'")
    opcoes = argumentos.parse_args()
    caminho = caminhos.caminho_banco()
    if opcoes.acao == "listar":
        copias = listar_backups(caminho)
        print("\n".join(p.name for p in copias) if copias else "Nenhum backup disponível.")
    elif opcoes.acao == "backup":
        if not caminho.is_file():
            argumentos.error("Banco não encontrado.")
        with closing(sqlite3.connect(f"file:{caminho.as_posix()}?mode=ro", uri=True)) as conexao:
            print("Backup criado:", criar_backup(conexao, caminho).name)
    else:
        if not opcoes.nome:
            argumentos.error("restaurar exige o nome exibido por 'listar'")
        seguranca = restaurar(caminho, opcoes.nome)
        print("Banco restaurado. Cópia anterior preservada:", seguranca.name)


if __name__ == "__main__":
    main()
