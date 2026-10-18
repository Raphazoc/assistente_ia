"""Coordena confirmação e execução; autorização não vem do modelo."""

from . import acoes


class ActionCoordinator:
    def __init__(self, raiz, gerar_json, confirmar, registrar):
        self.raiz = raiz
        self.gerar_json = gerar_json
        self.confirmar = confirmar
        self.registrar = registrar

    def atender(self, pergunta, mostrar=None):
        if not acoes.parece_pedido_de_acao(pergunta):
            return None
        plano = acoes.planejar(pergunta, self.raiz, self.gerar_json)
        if plano is None:
            return None
        if not self.confirmar(plano):
            return "Ação cancelada; nada foi executado."
        resultado = acoes.executar(plano, self.raiz, self.gerar_json, mostrar=mostrar)
        self.registrar("acoes.executada")
        return resultado
