"""Mensagens de recuperação para a interface, sem detalhes privados de exceções."""

import sqlite3

import httpx
from ollama import ResponseError


def orientar(erro, contexto="conversa"):
    """Traduz falhas técnicas para ações úteis sem reproduzir o texto da exceção."""
    if isinstance(erro, (sqlite3.Error,)):
        return ("A memória local não pôde ser acessada. Confira o espaço em disco "
                "e abra Configurações → Diagnóstico para localizar o banco e os backups.")
    if isinstance(erro, PermissionError):
        return ("O Windows negou acesso a um arquivo da assistente. Confira as permissões "
                "da pasta de dados em Configurações → Diagnóstico.")
    if contexto == "microfone":
        if isinstance(erro, RuntimeError) and str(erro).startswith("O microfone escolhido não está disponível"):
            return ("O microfone escolhido foi desconectado ou mudou. "
                    "Escolha outro em Configurações → Voz e teste novamente.")
        return ("Não consegui ouvir pelo microfone. Confira o dispositivo padrão e a permissão "
                "de microfone do Windows; depois teste em Configurações → Voz.")
    if contexto == "voz":
        return ("Não consegui reproduzir a voz. A resposta continua na tela. "
                "Teste o alto-falante e a voz em Configurações → Voz.")
    if isinstance(erro, (httpx.TransportError, ResponseError)) or (
        isinstance(erro, RuntimeError) and str(erro).startswith("Ollama indisponível")
    ):
        return ("Não consegui falar com o Ollama ou o modelo escolhido está ausente. "
                "Abra o Ollama e verifique os modelos em Configurações → Diagnóstico.")
    if contexto == "inicio":
        return ("A assistente não conseguiu iniciar. Abra Configurações → Diagnóstico "
                "para verificar o Ollama, o banco e os dispositivos.")
    return ("Não consegui concluir esse pedido. Tente novamente e consulte "
            "Configurações → Diagnóstico se o problema continuar.")
