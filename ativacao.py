import json
import re
import threading
import time
import unicodedata
from pathlib import Path

from controles import InterromperFala, SolicitarMenu, tecla_durante_fala


CONFIGURACAO = Path(__file__).resolve().parent / "config_voz.json"
PADRAO = {"palavra_ativacao": "Aurora", "interromper_por_voz": True}
COMANDOS_DIRETOS = {
    "menu", "sair", "encerrar", "desligar assistente", "texto", "modo texto",
    "mudar para texto", "trocar para texto", "usar texto", "voltar para texto",
    "quero digitar", "voz", "modo voz", "mudar para voz", "voltar para voz",
}


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto.casefold())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(re.findall(r"\w+", texto))


def carregar_configuracao():
    if not CONFIGURACAO.exists():
        return dict(PADRAO)
    dados = json.loads(CONFIGURACAO.read_text(encoding="utf-8"))
    return {**PADRAO, **dados}


def definir_palavra(palavra):
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


def extrair_chamada(texto, palavra):
    """Compara palavras completas no início, sem aproximações ou substrings."""
    tokens = list(re.finditer(r"\w+", texto))
    nome = normalizar(palavra).split()
    if not nome or len(tokens) < len(nome):
        return None
    if [normalizar(t.group()) for t in tokens[:len(nome)]] != nome:
        return None
    return texto[tokens[len(nome) - 1].end():].lstrip(" ,.:;!?-–—")


class EstadoAtivacao:
    def __init__(self):
        self.aguardando_ate = 0.0

    def processar(self, texto):
        palavra = carregar_configuracao()["palavra_ativacao"]
        comando = extrair_chamada(texto, palavra)
        if comando is not None:
            self.aguardando_ate = 0 if comando else time.monotonic() + 8
            if not comando:
                print("[ATIVAÇÃO] Estou ouvindo. Diga seu pedido nos próximos 8 segundos.")
            return comando
        if time.monotonic() < self.aguardando_ate:
            self.aguardando_ate = 0
            return texto
        return ""


class MonitorInterrupcao:
    """Escuta uma chamada durante a saída; o teclado é lido pela reprodução."""

    def __init__(self, texto_falado):
        self.texto_falado = normalizar(texto_falado)
        self.finalizar = threading.Event()
        self.interrompido = threading.Event()
        self.comando = ""
        self.thread = None

    def __enter__(self):
        if carregar_configuracao()["interromper_por_voz"]:
            self.thread = threading.Thread(target=self._escutar, daemon=True)
            self.thread.start()
        return self

    def __exit__(self, *args):
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
                texto = transcrever_audio(audio)
                if self.finalizar.is_set():
                    return
                self.processar(texto)
                if self.interrompido.is_set():
                    return
        except Exception as erro:
            if not self.finalizar.is_set():
                print(f"[VOZ] Interrupção por microfone indisponível; use Espaço ou Esc. {erro}")

    def processar(self, texto):
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
