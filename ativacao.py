import json
import re
import threading
import unicodedata
from pathlib import Path

from controles import InterromperFala, SolicitarMenu, tecla_durante_fala
import diagnostico


CONFIGURACAO = Path(__file__).resolve().parent / "config_voz.json"
PADRAO = {"palavra_ativacao": "Aurora", "interromper_por_voz": True}
COMANDOS_DIRETOS = {
    "menu", "sair", "encerrar", "desligar assistente", "texto", "modo texto",
    "mudar para texto", "trocar para texto", "usar texto", "voltar para texto",
    "quero digitar", "voz", "modo voz", "mudar para voz", "voltar para voz",
}


def normalizar(texto):
    """Normaliza uma frase para reconhecer comandos sem acentos."""
    texto = unicodedata.normalize("NFKD", texto.casefold())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(re.findall(r"\w+", texto))


def carregar_configuracao():
    """Carrega a configuração da palavra de ativação usando valores padrão."""
    if not CONFIGURACAO.exists():
        return dict(PADRAO)
    dados = json.loads(CONFIGURACAO.read_text(encoding="utf-8"))
    return {**PADRAO, **dados}


def definir_palavra(palavra):
    """Valida e salva uma nova palavra ou expressão de ativação."""
    palavra = " ".join(palavra.split())
    if not re.fullmatch(r"[^\W\d_]+(?: [^\W\d_]+){0,3}", palavra) or not 3 <= len(palavra) <= 40:
        raise ValueError("Use de 3 a 40 letras, em uma palavra ou até quatro palavras.")
    if normalizar(palavra) in COMANDOS_DIRETOS or normalizar(palavra) in {"pare", "parar", "cancele"}:
        raise ValueError("Escolha um nome diferente dos comandos do programa.")
    dados = carregar_configuracao()
    dados["palavra_ativacao"] = palavra
    temporario = CONFIGURACAO.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporario.replace(CONFIGURACAO)


def extrair_chamada(texto, palavra, exigir_separador=False):
    """Compara palavras completas no início, sem aproximações ou substrings."""
    tokens = list(re.finditer(r"\w+", texto))
    nome = normalizar(palavra).split()
    if not nome or len(tokens) < len(nome):
        return None
    if [normalizar(t.group()) for t in tokens[:len(nome)]] != nome:
        return None
    restante = texto[tokens[len(nome) - 1].end():]
    if exigir_separador and restante.strip() and not re.match(r"^\s*[,.:;!?–—-]", restante):
        return None
    return restante.lstrip(" ,.:;!?-–—")


def preparar_pedido_falado(texto, palavra):
    """Aceita fala direta e remove um nome inicial apenas quando é uma chamada explícita."""
    chamada = extrair_chamada(texto, palavra, exigir_separador=True)
    return (texto if chamada is None else chamada).strip()


class MonitorInterrupcao:
    """Escuta uma chamada durante a saída; o teclado é lido pela reprodução."""

    def __init__(self, texto_falado, habilitado=True):
        self.texto_falado = normalizar(texto_falado)
        self.habilitado = habilitado
        self.finalizar = threading.Event()
        self.interrompido = threading.Event()
        self.comando = ""
        self.thread = None

    def __enter__(self):
        """Inicia a escuta de interrupções quando o recurso está habilitado."""
        if self.habilitado and carregar_configuracao()["interromper_por_voz"]:
            self.thread = threading.Thread(target=self._escutar, daemon=True)
            self.thread.start()
        return self

    def __exit__(self, *args):
        """Solicita o encerramento da escuta e aguarda sua finalização breve."""
        self.finalizar.set()
        if self.thread:
            self.thread.join(timeout=0.2)

    def _escutar(self):
        from voz import capturar_audio, transcrever_audio

        try:
            while not self.finalizar.is_set():
                audio = capturar_audio(cancelar=self.finalizar, teclado=False, anunciar=False, limite_fala=2.5)
                if self.finalizar.is_set():
                    return
                if audio is None or not audio.size:
                    continue
                texto = transcrever_audio(audio, modo_interrupcao=True)
                if self.finalizar.is_set():
                    return
                self.processar(texto)
                if self.interrompido.is_set():
                    return
        except Exception as erro:
            if not self.finalizar.is_set():
                diagnostico.registrar("microfone.interrupcao_falhou", erro=erro)
                print("[VOZ] Interrupção por microfone indisponível; use Espaço ou Esc.")

    def processar(self, texto):
        """Interpreta uma transcrição e registra comando de interrupção válido."""
        frase = normalizar(texto)
        if not frase or frase in self.texto_falado:
            return  # Não reage a uma transcrição que repete a própria resposta.
        comando = extrair_chamada(texto, carregar_configuracao()["palavra_ativacao"])
        if comando is None:
            return
        self.comando = "" if normalizar(comando) in {"pare", "parar", "cancele", "chega", "silencio"} else comando
        self.interrompido.set()

    def verificar(self):
        tecla = tecla_durante_fala()
        if tecla == "menu":
            raise SolicitarMenu()
        if tecla == "parar" or self.interrompido.is_set():
            raise InterromperFala()
