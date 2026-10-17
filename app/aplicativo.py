"""Janela Windows da assistente, com escrita e áudio em áreas independentes."""

import os
import queue
import shutil
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import scrolledtext

from . import acoes
from . import ativacao
from . import diagnostico
from . import internet
from . import main
from . import memoria
from . import resumos


NOME_APP = "AssistenteIA"
COR_FUNDO = "#101820"
COR_CARTAO = "#1b2935"
COR_TEXTO = "#ecf2f5"
COR_SUAVE = "#a8bec9"
COR_DESTAQUE = "#56c7ba"
COR_AUDIO = "#b5a0f3"
COR_PESQUISA = "#f5c66b"
COR_ERRO = "#f58f8f"
COR_ENTRADA = "#13212c"


def preparar_arquivos_usuario():
    """Mantém banco, configurações e logs fora da pasta instalada."""
    dados = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / NOME_APP
    dados.mkdir(parents=True, exist_ok=True)
    origem = Path(__file__).resolve().parent.parent
    recursos = Path(getattr(sys, "_MEIPASS", origem)) / "resources"
    legado = origem / "memoria.db"
    if not legado.exists() and getattr(sys, "frozen", False):
        legado = Path.home() / "assistente_ia" / "memoria.db"
    destino = dados / "memoria.db"
    if not destino.exists() and legado.is_file():
        shutil.copy2(legado, destino)
    for nome in ("config_voz.json", "config_internet.json"):
        arquivo = dados / nome
        modelo = recursos / nome
        if not arquivo.exists() and modelo.is_file():
            shutil.copy2(modelo, arquivo)
    pasta_trabalho = Path.home() / "Documents" / NOME_APP
    pasta_trabalho.mkdir(parents=True, exist_ok=True)
    main.BANCO = destino
    main.PASTA_PROJETO = pasta_trabalho
    ativacao.CONFIGURACAO = dados / "config_voz.json"
    internet.CONFIGURACAO = dados / "config_internet.json"
    diagnostico.PASTA_LOGS = dados / "logs"
    from . import fala
    fala.MODELO_VOZ = recursos / "vozes" / "pt_BR-faber-medium.onnx"
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    return dados, pasta_trabalho


class _ControleFala:
    """Combina o cancelamento da interface com o monitor de interrupção."""

    def __init__(self, monitor, parar):
        self.monitor = monitor
        self.parar = parar

    def verificar(self):
        """Interrompe a fala quando a janela ou o monitor solicitar."""
        from .controles import InterromperFala
        if self.parar.is_set():
            raise InterromperFala()
        self.monitor.verificar()


class MotorDesktop:
    """Executa Ollama, SQLite e microfone fora da thread do Tk."""

    def __init__(self, eventos):
        self.eventos = eventos
        self.pedidos = queue.Queue()
        self.cancelar_captura = threading.Event()
        self.parar_fala = threading.Event()
        self.microfone_ativo = threading.Event()
        self.encerrando = threading.Event()
        self.monitor_ativo = None
        self.confirmacao = None
        self.confirmacao_trava = threading.Lock()
        self.thread = threading.Thread(target=self._rodar, name="motor-assistente", daemon=True)

    def iniciar(self):
        """Inicia a thread que processa pedidos fora da thread do Tk."""
        self.thread.start()

    def enviar_texto(self, texto):
        """Enfileira texto digitado e cancela uma captura ou fala anterior."""
        self.cancelar_captura.set()
        self.parar_fala.set()
        self.pedidos.put(("texto", texto))

    def ativar_microfone(self):
        """Solicita que o motor retome a captura de voz."""
        self.microfone_ativo.set()
        self.cancelar_captura.clear()
        self.parar_fala.set()
        self.pedidos.put(("acordar", ""))

    def desativar_microfone(self):
        """Cancela a captura e a escuta de interrupções por voz."""
        self.microfone_ativo.clear()
        self.cancelar_captura.set()
        if self.monitor_ativo is not None:
            self.monitor_ativo.finalizar.set()

    def interromper_fala(self):
        self.parar_fala.set()

    def fechar(self):
        """Sinaliza o encerramento e libera confirmações ou operações pendentes."""
        self.encerrando.set()
        self.desativar_microfone()
        self.parar_fala.set()
        with self.confirmacao_trava:
            if self.confirmacao:
                self.confirmacao["aceita"] = False
                self.confirmacao["evento"].set()
        self.pedidos.put(("fechar", ""))

    def responder_confirmacao(self, aceita):
        """Entrega ao motor a decisão tomada nos botões de confirmação."""
        with self.confirmacao_trava:
            if self.confirmacao:
                self.confirmacao["aceita"] = bool(aceita)
                self.confirmacao["evento"].set()

    def _emitir(self, tipo, *dados):
        if not self.encerrando.is_set():
            self.eventos.put((tipo, *dados))

    def _confirmar(self, titulo, descricao):
        resposta = {"evento": threading.Event(), "aceita": False}
        with self.confirmacao_trava:
            self.confirmacao = resposta
        self._emitir("confirmar", titulo, descricao)
        resposta["evento"].wait()
        with self.confirmacao_trava:
            self.confirmacao = None
        self._emitir("limpar_confirmacao")
        return resposta["aceita"] and not self.encerrando.is_set()

    def _autorizar_pesquisa(self, plano):
        consultas = "\n".join("• " + consulta for consulta in plano.consultas)
        return self._confirmar("Autorizar pesquisa na internet?", plano.motivo + "\n" + consultas)

    def _autorizar_acao(self, plano):
        return self._confirmar("Executar ação no computador?", acoes.descricao(plano))

    def _falar(self, resposta):
        from . import fala
        self.parar_fala.clear()
        self._emitir("estado_audio", "A IA está falando…")
        with ativacao.MonitorInterrupcao(resposta, habilitado=self.microfone_ativo.is_set()) as monitor:
            self.monitor_ativo = monitor
            try:
                fala.falar(resposta, controle=_ControleFala(monitor, self.parar_fala))
            finally:
                self.monitor_ativo = None
        self._emitir("estado_audio", "Voltando a ouvir…" if self.microfone_ativo.is_set() else "Microfone desligado")
        if monitor.comando and not self.encerrando.is_set():
            self.pedidos.put(("audio", monitor.comando))

    def _responder(self, conexao, historico, origem, pergunta):
        """Processa uma pergunta, incluindo memória, ações, pesquisa e resposta."""
        pergunta = pergunta.strip()
        if not pergunta:
            return
        if origem == "audio":
            pergunta = ativacao.preparar_pedido_falado(
                pergunta, ativacao.carregar_configuracao()["palavra_ativacao"]
            )
            if not pergunta:
                return
        self._emitir("mensagem", origem, "Você", pergunta)
        comando = main.normalizar_comando(pergunta)
        if comando in {"sair", "encerrar", "desligar assistente"}:
            self._emitir("fechar")
            return
        if comando in {"modo texto", "texto", "modo voz", "voz"}:
            self._emitir("mensagem", origem, "IA", "As áreas de Escrita e Áudio já estão disponíveis lado a lado.")
            return
        try:
            resposta = memoria.tratar_comando(conexao, pergunta)
        except ValueError as erro:
            resposta = f"Não foi possível alterar a memória: {erro}"
        if resposta is not None:
            historico.clear()
            self._emitir("mensagem", origem, "IA", resposta)
            if origem == "audio":
                try:
                    self._falar(resposta)
                except Exception as erro:
                    diagnostico.registrar("voz.reproducao_falhou", erro=erro)
                    self._emitir("estado_audio", "Falha na saída de voz; resposta disponível na tela")
            return
        self._emitir("estado", "Pensando…")
        identificador = main.salvar_mensagem(conexao, "user", pergunta)
        try:
            resposta = main.atender_acao(
                pergunta, modo_voz=(origem == "audio"), confirmar=self._autorizar_acao,
                mostrar=lambda texto: self._emitir("mensagem", origem, "Arquivo", texto),
            )
            if resposta is None:
                pesquisa = main.preparar_pesquisa(
                    pergunta, historico, modo_voz=(origem == "audio"),
                    pedir_autorizacao=self._autorizar_pesquisa,
                )
                resposta = main.obter_resposta(
                    conexao, historico, pergunta, modo_voz=(origem == "audio"), pesquisa=pesquisa,
                )
        except Exception as erro:
            diagnostico.registrar("conversa.resposta_falhou", erro=erro)
            self._emitir("mensagem", origem, "Erro", str(erro))
            self._emitir("estado", "Pronto")
            return
        resposta_id = main.salvar_mensagem(conexao, "assistant", resposta)
        historico.extend((
            {"role": "user", "content": pergunta, "id": identificador},
            {"role": "assistant", "content": resposta, "id": resposta_id},
        ))
        del historico[:-main.LIMITE_HISTORICO]
        self._emitir("mensagem", origem, "IA", resposta)
        self._emitir("estado", "Pronto")
        if origem == "audio" and not self.encerrando.is_set() and self.pedidos.empty():
            try:
                self._falar(resposta)
            except Exception as erro:
                diagnostico.registrar("voz.reproducao_falhou", erro=erro)
                self._emitir("estado_audio", "Falha na saída de voz; resposta disponível na tela")
        try:
            main.indexar_nova_mensagem(conexao, identificador, pergunta)
            resumos.resumir_pendentes(conexao)
            main.banco.backup_automatico(conexao, main.BANCO)
        except Exception as erro:
            diagnostico.registrar("memoria.indexacao_falhou", erro=erro)

    def _rodar(self):
        conexao = None
        try:
            preparar_arquivos_usuario()
            self._emitir("estado", "Preparando memória…")
            conexao = main.iniciar_banco()
            memoria.processar_pendentes(conexao)
            resumos.resumir_pendentes(conexao)
            try:
                main.indexar_memorias_antigas(conexao)
            except Exception as erro:
                diagnostico.registrar("memoria.indexacao_falhou", erro=erro)
            historico = []
            self._emitir("pronto")
            while not self.encerrando.is_set():
                try:
                    origem, texto = self.pedidos.get(timeout=0.1 if self.microfone_ativo.is_set() else None)
                except queue.Empty:
                    origem, texto = "capturar", ""
                if origem == "fechar":
                    break
                if origem == "acordar":
                    continue
                if origem == "capturar":
                    if not self.microfone_ativo.is_set():
                        continue
                    self.cancelar_captura.clear()
                    self._emitir("estado_audio", "Ouvindo · fale no seu ritmo")
                    try:
                        from .voz import ouvir
                        texto = ouvir(
                            cancelar=self.cancelar_captura, teclado=False, aguardar_fala=True,
                            ao_capturar=lambda: self._emitir("estado_audio", "Transcrevendo sua fala…"),
                        )
                    except Exception as erro:
                        diagnostico.registrar("microfone.captura_falhou", erro=erro)
                        self.desativar_microfone()
                        self._emitir("microfone_ativo", False)
                        self._emitir("estado_audio", f"Microfone indisponível: {erro}")
                        continue
                    if not texto or self.cancelar_captura.is_set():
                        continue
                    self._emitir("estado_audio", "Frase capturada · preparando resposta")
                    origem = "audio"
                self._responder(conexao, historico, origem, texto)
        except Exception as erro:
            self._emitir("fatal", str(erro))
        finally:
            if conexao is not None:
                conexao.close()


class JanelaAssistente:
    def __init__(self, raiz=None, iniciar_motor=True):
        self.raiz = raiz or tk.Tk()
        self.raiz.title("Assistente IA")
        self.raiz.geometry("1120x700")
        self.raiz.minsize(700, 600)
        self.raiz.configure(bg=COR_FUNDO)
        self.eventos = queue.Queue()
        self.motor = MotorDesktop(self.eventos)
        self.microfone_ligado = False
        self.layout_empilhado = False
        self.pronto = False
        self._montar()
        self.raiz.bind("<Configure>", self._ajustar_layout)
        self.raiz.protocol("WM_DELETE_WINDOW", self.fechar)
        self.raiz.after(60, self._processar_eventos)
        if iniciar_motor:
            self.motor.iniciar()

    def _rotulo(self, pai, texto, tamanho=11, cor=COR_TEXTO, **opcoes):
        return tk.Label(
            pai, text=texto, bg=pai["bg"], fg=cor,
            font=("Segoe UI", tamanho), anchor="w", **opcoes,
        )

    def _botao(self, pai, texto, comando, destaque=False, cor=None):
        fundo = cor or (COR_DESTAQUE if destaque else "#304858")
        return tk.Button(
            pai, text=texto, command=comando, relief="flat", cursor="hand2",
            bg=fundo,
            fg=COR_FUNDO if destaque or cor else COR_TEXTO,
            activebackground=cor or ("#7de0d2" if destaque else "#415f70"),
            activeforeground=COR_FUNDO if destaque or cor else COR_TEXTO,
            disabledforeground=COR_SUAVE, font=("Segoe UI", 10, "bold"),
            padx=18, pady=9,
        )

    def _configurar_historico(self, widget):
        for papel, cor in (("usuario", COR_DESTAQUE), ("ia", COR_AUDIO),
                           ("arquivo", COR_PESQUISA), ("erro", COR_ERRO)):
            widget.tag_configure(papel, foreground=cor, font=("Segoe UI", 10, "bold"))
        widget.tag_configure("corpo", foreground=COR_TEXTO, spacing3=9)

    def _montar(self):
        self.raiz.grid_columnconfigure(0, weight=1, uniform="paineis")
        self.raiz.grid_columnconfigure(1, weight=1, uniform="paineis")
        self.raiz.grid_rowconfigure(2, weight=1)

        topo = tk.Frame(self.raiz, bg=COR_FUNDO)
        topo.grid(row=0, column=0, columnspan=2, sticky="ew", padx=22, pady=(18, 10))
        titulo = tk.Frame(topo, bg=COR_FUNDO)
        titulo.pack(side="left")
        self._rotulo(titulo, "Assistente IA", 21).pack(anchor="w")
        self._rotulo(titulo, "Escreva ou converse por voz, no seu ritmo.", 10, COR_SUAVE).pack(anchor="w")
        self.pesquisa = self._botao(topo, "Pesquisa: ligada", self.alternar_pesquisa, cor=COR_PESQUISA)
        self.pesquisa.pack(side="right", padx=(12, 0))

        self.confirmacao = tk.Frame(self.raiz, bg="#29453e", padx=16, pady=12)
        self.confirmacao.grid(row=1, column=0, columnspan=2, sticky="ew", padx=22, pady=(0, 10))
        self.confirmacao.grid_columnconfigure(0, weight=1)
        self.titulo_confirmacao = self._rotulo(self.confirmacao, "", 11)
        self.titulo_confirmacao.grid(row=0, column=0, sticky="w")
        self.detalhes_confirmacao = self._rotulo(self.confirmacao, "", 10, COR_SUAVE, wraplength=760, justify="left")
        self.detalhes_confirmacao.grid(row=1, column=0, sticky="w", pady=(3, 0))
        botoes_confirmacao = tk.Frame(self.confirmacao, bg=self.confirmacao["bg"])
        botoes_confirmacao.grid(row=0, column=1, rowspan=2, padx=(18, 0))
        self._botao(botoes_confirmacao, "Cancelar", lambda: self._confirmar(False)).pack(side="left", padx=(0, 8))
        self._botao(botoes_confirmacao, "Confirmar", lambda: self._confirmar(True), True).pack(side="left")
        self.confirmacao.grid_remove()

        self.area_escrita = tk.Frame(self.raiz, bg=COR_CARTAO, padx=16, pady=16,
                                     highlightbackground="#315d60", highlightthickness=1)
        self.area_escrita.grid(row=2, column=0, sticky="nsew", padx=(22, 8), pady=(0, 14))
        self.area_escrita.grid_columnconfigure(0, weight=1)
        self.area_escrita.grid_rowconfigure(2, weight=1)
        self._rotulo(self.area_escrita, "ESCRITA", 15, COR_DESTAQUE).grid(row=0, column=0, sticky="w")
        self.descricao_escrita = self._rotulo(self.area_escrita, "Digite e acompanhe esta conversa aqui.", 10, COR_SUAVE)
        self.descricao_escrita.grid(
            row=1, column=0, sticky="w", pady=(2, 12)
        )
        self.historico_escrita = scrolledtext.ScrolledText(
            self.area_escrita, wrap="word", state="disabled", bg=COR_ENTRADA,
            fg=COR_TEXTO, insertbackground=COR_TEXTO, relief="flat",
            font=("Segoe UI", 10), padx=12, pady=12, width=1, height=4,
        )
        self.historico_escrita.grid(row=2, column=0, sticky="nsew")
        self._configurar_historico(self.historico_escrita)
        self.entrada = tk.Text(
            self.area_escrita, height=3, width=1, wrap="word", bg=COR_ENTRADA,
            fg=COR_TEXTO, insertbackground=COR_TEXTO, relief="flat",
            font=("Segoe UI", 11), padx=10, pady=8,
        )
        self.entrada.grid(row=3, column=0, sticky="ew", pady=(12, 8))
        self.entrada.bind("<Return>", self._enter)
        rodape_escrita = tk.Frame(self.area_escrita, bg=COR_CARTAO)
        rodape_escrita.grid(row=4, column=0, sticky="ew")
        self._rotulo(rodape_escrita, "Enter envia • Shift+Enter quebra linha", 9, COR_SUAVE).pack(side="left")
        self.enviar = self._botao(rodape_escrita, "Enviar", self.enviar_texto, True)
        self.enviar.pack(side="right")

        self.area_audio = tk.Frame(self.raiz, bg=COR_CARTAO, padx=16, pady=16,
                                   highlightbackground="#594f7c", highlightthickness=1)
        self.area_audio.grid(row=2, column=1, sticky="nsew", padx=(8, 22), pady=(0, 14))
        self.area_audio.grid_columnconfigure(0, weight=1)
        self.area_audio.grid_rowconfigure(4, weight=1)
        self._rotulo(self.area_audio, "ÁUDIO", 15, COR_AUDIO).grid(row=0, column=0, sticky="w")
        self.descricao_audio = self._rotulo(self.area_audio, "Ligue o microfone uma vez. Fale e faça uma pausa ao terminar.", 10, COR_SUAVE)
        self.descricao_audio.grid(
            row=1, column=0, sticky="w", pady=(2, 12)
        )
        self.estado_audio = self._rotulo(self.area_audio, "Microfone desligado", 11, COR_SUAVE)
        self.estado_audio.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        controles_audio = tk.Frame(self.area_audio, bg=COR_CARTAO)
        controles_audio.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        self.falar = self._botao(controles_audio, "Ativar microfone", self.alternar_microfone, cor=COR_AUDIO)
        self.falar.pack(side="left", padx=(0, 8))
        self.parar = self._botao(controles_audio, "Parar resposta", self.motor.interromper_fala)
        self.parar.pack(side="left")
        self.historico_audio = scrolledtext.ScrolledText(
            self.area_audio, wrap="word", state="disabled", bg=COR_ENTRADA,
            fg=COR_TEXTO, insertbackground=COR_TEXTO, relief="flat",
            font=("Segoe UI", 10), padx=12, pady=12, width=1, height=4,
        )
        self.historico_audio.grid(row=4, column=0, sticky="nsew")
        self._configurar_historico(self.historico_audio)

        self.estado = self._rotulo(self.raiz, "Iniciando…", 10, COR_SUAVE)
        self.estado.grid(row=4, column=0, columnspan=2, sticky="ew", padx=22, pady=(0, 13))
        self.falar.configure(state="disabled")
        self.enviar.configure(state="disabled")
        self.pesquisa.configure(state="disabled")

    def _enter(self, evento):
        if evento.state & 0x0001:
            return None
        self.enviar_texto()
        return "break"

    def enviar_texto(self):
        texto = self.entrada.get("1.0", "end-1c").strip()
        if texto and self.pronto:
            self.entrada.delete("1.0", "end")
            self.motor.enviar_texto(texto)
            self.estado.configure(text="Aguardando resposta…")

    def _ajustar_layout(self, evento):
        if evento.widget is not self.raiz:
            return
        empilhado = evento.width < 940 and evento.height >= 780
        if empilhado != self.layout_empilhado:
            self.layout_empilhado = empilhado
            self.raiz.grid_columnconfigure(0, weight=1, uniform="" if empilhado else "paineis")
            self.raiz.grid_columnconfigure(1, weight=0 if empilhado else 1,
                                           uniform="" if empilhado else "paineis")
            self.raiz.grid_rowconfigure(3, weight=1 if empilhado else 0)
            self.area_escrita.grid_configure(row=2, column=0, columnspan=2 if empilhado else 1,
                                             padx=(22, 22 if empilhado else 8),
                                             pady=(0, 10 if empilhado else 14))
            self.area_audio.grid_configure(row=3 if empilhado else 2, column=0 if empilhado else 1,
                                           columnspan=2 if empilhado else 1,
                                           padx=(22, 22) if empilhado else (8, 22),
                                           pady=(0, 14))
        largura_painel = evento.width - 80 if empilhado else (evento.width - 80) // 2
        self.descricao_escrita.configure(wraplength=max(230, largura_painel - 35))
        self.descricao_audio.configure(wraplength=max(230, largura_painel - 35))
        self.detalhes_confirmacao.configure(wraplength=max(250, evento.width - 340))

    def _mostrar_microfone(self, ativo):
        self.microfone_ligado = ativo
        self.falar.configure(text="Desligar microfone" if ativo else "Ativar microfone",
                             bg=COR_ERRO if ativo else COR_AUDIO)
        self.estado_audio.configure(text="Ouvindo · fale no seu ritmo" if ativo else "Microfone desligado",
                                     fg=COR_AUDIO if ativo else COR_SUAVE)

    def alternar_microfone(self):
        if not self.pronto:
            return
        if self.microfone_ligado:
            self.motor.desativar_microfone()
            self._mostrar_microfone(False)
        else:
            self.motor.ativar_microfone()
            self._mostrar_microfone(True)

    def _mostrar_pesquisa(self):
        ativa = internet.habilitada()
        self.pesquisa.configure(text="Pesquisa: ligada" if ativa else "Pesquisa: desligada",
                                bg=COR_PESQUISA if ativa else "#40505c",
                                fg=COR_FUNDO if ativa else COR_TEXTO)

    def alternar_pesquisa(self):
        if not self.pronto:
            return
        try:
            internet.definir_habilitada(not internet.habilitada())
            self._mostrar_pesquisa()
            self.estado.configure(text="Pesquisa online ligada; cada busca pede autorização."
                                  if internet.habilitada() else "Pesquisa online desligada.")
        except OSError as erro:
            self.estado.configure(text=f"Não foi possível salvar a preferência: {erro}", fg=COR_ERRO)

    def _confirmar(self, aceita):
        self.motor.responder_confirmacao(aceita)
        self.confirmacao.grid_remove()

    def _escrever(self, widget, autor, mensagem):
        papel = {"Você": "usuario", "IA": "ia", "Arquivo": "arquivo", "Erro": "erro"}.get(autor, "ia")
        widget.configure(state="normal")
        widget.insert("end", autor.upper() + "\n", papel)
        widget.insert("end", mensagem.strip() + "\n\n", "corpo")
        widget.configure(state="disabled")
        widget.see("end")

    def _processar_eventos(self):
        try:
            while True:
                evento = self.eventos.get_nowait()
                tipo, *dados = evento
                if tipo == "pronto":
                    self.pronto = True
                    self.estado.configure(text="Pronto")
                    self._mostrar_microfone(False)
                    self._mostrar_pesquisa()
                    self.falar.configure(state="normal")
                    self.enviar.configure(state="normal")
                    self.pesquisa.configure(state="normal")
                elif tipo == "mensagem":
                    origem, autor, mensagem = dados
                    destino = self.historico_audio if origem == "audio" else self.historico_escrita
                    self._escrever(destino, autor, mensagem)
                elif tipo == "estado":
                    self.estado.configure(text=dados[0])
                elif tipo == "estado_audio":
                    self.estado_audio.configure(text=dados[0], fg=COR_ERRO if "Falha" in dados[0] or "indisponível" in dados[0] else COR_AUDIO)
                elif tipo == "microfone_ativo":
                    self._mostrar_microfone(dados[0])
                elif tipo == "confirmar":
                    self.titulo_confirmacao.configure(text=dados[0])
                    self.detalhes_confirmacao.configure(text=dados[1])
                    self.confirmacao.grid()
                elif tipo == "limpar_confirmacao":
                    self.confirmacao.grid_remove()
                elif tipo == "fatal":
                    self.estado.configure(text="Falha ao iniciar: " + dados[0])
                    self.estado_audio.configure(text="Indisponível")
                elif tipo == "fechar":
                    self.fechar()
                    return
        except queue.Empty:
            pass
        self.raiz.after(60, self._processar_eventos)

    def fechar(self):
        self.motor.fechar()
        self.raiz.destroy()

    def executar(self):
        self.raiz.mainloop()


def executar():
    """Inicia a interface ou executa a verificação rápida do empacotamento."""
    if "--smoke-test" in sys.argv:
        janela = JanelaAssistente(iniciar_motor=False)
        janela.raiz.withdraw()
        janela.raiz.update_idletasks()
        assert janela.area_escrita.grid_info()["column"] == 0
        assert janela.area_audio.grid_info()["column"] == 1
        recursos = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "resources"
        assert (recursos / "vozes" / "pt_BR-faber-medium.onnx").is_file()
        janela.fechar()
    else:
        JanelaAssistente().executar()


if __name__ == "__main__":
    executar()
