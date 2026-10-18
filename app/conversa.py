"""Orquestra resposta comum entre terminal e desktop."""


class ConversationService:
    def __init__(self, acao, pesquisa, resposta):
        self.acao = acao
        self.pesquisa = pesquisa
        self.resposta = resposta

    def responder(self, conexao, historico, pergunta, modo_voz=False):
        resultado = self.acao(pergunta, modo_voz)
        if resultado is not None:
            return resultado
        plano = self.pesquisa(pergunta, historico, modo_voz)
        return self.resposta(conexao, historico, pergunta, modo_voz, plano)
