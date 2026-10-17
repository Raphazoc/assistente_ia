"""Eventos técnicos locais, sem conteúdo de conversas ou mensagens de erro."""

import json
import logging
import os
import threading
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path


PASTA_LOGS = Path(__file__).resolve().parent.parent / "logs"
_logger = None
_trava = threading.RLock()
EVENTOS = {
    "acoes.executada", "acoes.falhou",
    "banco.backup_criado", "banco.backup_falhou", "banco.gravacao_falhou",
    "banco.manutencao_falhou", "banco.restaurado", "conversa.resposta_falhou",
    "internet.pesquisa_avaliada", "internet.pesquisa_cancelada",
    "memoria.indexacao_falhou", "microfone.captura_falhou",
    "memoria.busca_semantica_falhou",
    "microfone.frase_capturada", "microfone.interrupcao_falhou",
    "ollama.embedding.ok", "ollama.embedding.falha", "ollama.planejamento.ok",
    "ollama.planejamento.falha", "ollama.resposta.ok", "ollama.resposta.falha",
    "voz.reproducao_ok", "voz.reproducao_falhou", "voz.online_falhou",
    "voz.local_falhou", "whisper.gpu_carregada", "whisper.gpu_falhou",
    "whisper.cpu_carregada", "whisper.preparacao_falhou",
    "whisper.transcricao_ok", "whisper.transcricao_falhou", "whisper.gpu_fallback",
}


def _obter_logger():
    """Inicializa, de forma thread-safe, o arquivo rotativo de diagnóstico."""
    global _logger
    with _trava:
        if _logger is None:
            PASTA_LOGS.mkdir(parents=True, exist_ok=True)
            if os.name != "nt":
                PASTA_LOGS.chmod(0o700)
            logger = logging.getLogger("assistente.diagnostico")
            logger.setLevel(logging.INFO)
            logger.propagate = False
            handler = RotatingFileHandler(
                PASTA_LOGS / "assistente.log", maxBytes=2_000_000,
                backupCount=3, encoding="utf-8",
            )
            if os.name != "nt":
                (PASTA_LOGS / "assistente.log").chmod(0o600)
            logger.addHandler(handler)
            _logger = logger
        return _logger


def encerrar():
    """Fecha os manipuladores de log para permitir encerramento limpo."""
    global _logger
    with _trava:
        if _logger is not None:
            for handler in list(_logger.handlers):
                _logger.removeHandler(handler)
                handler.close()
            _logger = None


def registrar(evento, *, duracao_ms=None, erro=None, quantidade=None):
    """Somente códigos fixos, números e nome da exceção; nunca texto pessoal."""
    if evento not in EVENTOS:
        raise ValueError("Evento técnico não autorizado para registro.")
    registro = {
        "hora_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evento": evento,
    }
    if duracao_ms is not None:
        registro["duracao_ms"] = round(max(0, float(duracao_ms)), 1)
    if quantidade is not None:
        registro["quantidade"] = int(quantidade)
    if erro is not None:
        registro["tipo_erro"] = type(erro).__name__
    try:
        _obter_logger().info(json.dumps(registro, ensure_ascii=False))
    except OSError:
        pass  # Falha no log não interrompe conversa, voz ou gravação.
