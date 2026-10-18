"""Chamadas locais ao Ollama com retry limitado e diagnóstico sem conteúdo."""

import time

import httpx
from ollama import ResponseError


class OllamaService:
    def __init__(self, registrar, pausa=time.sleep):
        self.registrar = registrar
        self.pausa = pausa

    def consultar(self, funcao, evento, **argumentos):
        inicio = time.monotonic()
        for tentativa in range(2):
            try:
                resposta = funcao(**argumentos)
                self.registrar(evento + ".ok", duracao_ms=(time.monotonic() - inicio) * 1000)
                return resposta
            except (httpx.TransportError, ResponseError) as erro:
                self.registrar(evento + ".falha", duracao_ms=(time.monotonic() - inicio) * 1000, erro=erro)
                recuperavel = (
                    isinstance(erro, (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadError, httpx.RemoteProtocolError))
                    or isinstance(erro, ResponseError) and (erro.status_code >= 500 or erro.status_code == 429)
                )
                if tentativa == 0 and recuperavel:
                    self.pausa(0.4)
                    continue
                raise RuntimeError(
                    "Ollama indisponível ou modelo não encontrado. Verifique se o Ollama está aberto e se os modelos estão instalados."
                ) from None
