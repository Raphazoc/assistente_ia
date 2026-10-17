"""Janela Windows da assistente, com escrita e áudio em áreas independentes."""

import os
import math
import queue
import re
import shutil
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import scrolledtext
from tkinter import messagebox
from pygments import lex
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.token import Token
from pygments.util import ClassNotFound

from . import acoes
from . import banco
from . import ativacao
from . import diagnostico
from . import erros
from . import internet
from . import main
from . import memoria
from . import memoria_ui
from . import resumos
from . import renderizacao
from . import servicos
from . import configuracao
from . import primeira_execucao


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
    for nome in ("config_voz.json", "config_internet.json", "config_servicos.json", "config_geral.json"):
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
    servicos.CONFIGURACAO = dados / "config_servicos.json"
    configuracao.CONFIGURACAO = dados / "config_geral.json"
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

    def enviar_texto(self, texto, nao_salvar=False):
        """Enfileira texto digitado e cancela uma captura ou fala anterior."""
        self.cancelar_captura.set()
        self.parar_fala.set()
        self.pedidos.put(("texto", (texto, bool(nao_salvar))))

    def gerenciar_memoria(self, acao, **dados):
        """Serializa leituras e alterações do banco na thread que já o possui."""
        self.cancelar_captura.set()
        self.pedidos.put(("gerenciar_memoria", (acao, dados)))

    def _gerenciar_memoria(self, conexao, acao, dados):
        apagou = False
        try:
            if acao == "guardar":
                memoria.guardar(conexao, dados["texto"], dados["assunto"], dados["projeto"],
                                dados["importancia"], tipo=dados["tipo"])
            elif acao == "editar":
                memoria.editar(conexao, dados["id"], dados["texto"], dados["assunto"],
                               dados["projeto"], dados["importancia"], dados["tipo"])
            elif acao == "excluir":
                memoria.excluir(conexao, dados["id"])
            elif acao == "habilitar":
                memoria.definir_habilitada(conexao, dados["ativa"])
                if dados["ativa"]:
                    memoria.processar_pendentes(conexao)
            elif acao == "nao_usar":
                memoria.nao_usar_troca(conexao, dados["id"])
            elif acao == "apagar_tudo":
                memoria.apagar_tudo(conexao)
                apagou = True
                self._emitir("memoria_zerada")
                if dados.get("incluir_backups"):
                    for copia in banco.listar_backups(main.BANCO):
                        copia.unlink()
                    pasta = banco.pasta_backups(main.BANCO)
                    if pasta.is_dir() and not pasta.is_symlink():
                        for temporario in pasta.glob("*.db.tmp"):
                            if banco.NOME_BACKUP.fullmatch(temporario.name[:-4]) and not temporario.is_symlink():
                                temporario.unlink()
                    legado = main.BANCO.resolve().parent / "backyp"
                    if legado.is_dir() and not legado.is_symlink():
                        for copia in legado.glob("memoria_antes_v2_*.db"):
                            if re.fullmatch(r"memoria_antes_v2_\d{8}_\d{6}_\d{6}_UTC\.db", copia.name) and not copia.is_symlink():
                                copia.unlink()
            elif acao != "listar":
                raise ValueError("Operação de memória desconhecida.")
            self._emitir("memoria_dados", memoria.painel(conexao))
        except ValueError as erro:
            self._emitir("memoria_erro", str(erro))
        except Exception as erro:
            diagnostico.registrar("memoria.gerenciamento_falhou", erro=erro)
            self._emitir("memoria_erro", "Não foi possível atualizar a memória. Consulte Configurações → Diagnóstico.")
            try:
                self._emitir("memoria_dados", memoria.painel(conexao))
            except Exception:
                pass
        return apagou

    def ativar_microfone(self):
        """Solicita que o motor retome a captura de voz."""
        from .voz import preparar_modelos
        preparar_modelos()
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
        provedor = "Brave Search (DuckDuckGo se falhar)" if servicos.carregar()["buscador"] == "brave" else "DuckDuckGo"
        return self._confirmar("Autorizar pesquisa na internet?", plano.motivo + "\nBuscador: " + provedor + "\n" + consultas)

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

    def _responder(self, conexao, historico, origem, pergunta, nao_salvar=False):
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
        self._emitir("mensagem", origem, "Você · não salvo" if nao_salvar else "Você", pergunta)
        comando = main.normalizar_comando(pergunta)
        if comando in {"sair", "encerrar", "desligar assistente"}:
            self._emitir("fechar")
            return
        if comando in {"modo texto", "texto", "modo voz", "voz"}:
            self._emitir("modo", "texto" if "texto" in comando else "voz")
            return
        resposta = None
        if not nao_salvar:
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
        identificador = None if nao_salvar else main.salvar_mensagem(conexao, "user", pergunta)
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
            self._emitir("mensagem", origem, "Erro", erros.orientar(erro))
            self._emitir("estado", "Pronto")
            return
        resposta_id = None if nao_salvar else main.salvar_mensagem(conexao, "assistant", resposta)
        if not nao_salvar:
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
        if identificador is not None:
            try:
                if memoria.habilitada(conexao):
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
            if memoria.habilitada(conexao):
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
                if origem == "gerenciar_memoria":
                    acao, dados = texto
                    if self._gerenciar_memoria(conexao, acao, dados):
                        historico.clear()
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
                            ao_nivel=lambda nivel: self._emitir("nivel_audio", nivel),
                        )
                    except Exception as erro:
                        diagnostico.registrar("microfone.captura_falhou", erro=erro)
                        self.desativar_microfone()
                        self._emitir("microfone_ativo", False)
                        self._emitir("estado_audio", erros.orientar(erro, "microfone"))
                        continue
                    if not texto or self.cancelar_captura.is_set():
                        continue
                    self._emitir("estado_audio", "Frase capturada · preparando resposta")
                    origem = "audio"
                if origem == "texto":
                    texto, nao_salvar = texto
                else:
                    nao_salvar = False
                self._responder(conexao, historico, origem, texto, nao_salvar=nao_salvar)
        except Exception as erro:
            diagnostico.registrar("conversa.inicializacao_falhou", erro=erro)
            self._emitir("fatal", erros.orientar(erro, "inicio"))
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
        self.microfone_mutado = False
        self.modo = "texto"
        self.nivel_audio = 0.0
        self.fase_onda = 0.0
        self.pronto = False
        self.motor_iniciado = False
        self.assistente = None
        self.janela_memoria = None
        self._fechada = False
        self._agendamentos = set()
        self._montar()
        self.raiz.bind("<Configure>", self._ajustar_layout)
        self.raiz.protocol("WM_DELETE_WINDOW", self.fechar)
        self._agendar(60, self._processar_eventos)
        if iniciar_motor:
            try:
                preparar_arquivos_usuario()
                dados = configuracao.carregar()
                if dados["configurado"]:
                    configuracao.aplicar(dados)
                    self.motor.iniciar()
                    self.motor_iniciado = True
                else:
                    self.estado.configure(text="Conclua a configuração inicial para começar.")
                    self._agendar(100, self.abrir_assistente_inicial)
            except (OSError, ValueError) as erro:
                mensagem = str(erro)
                self.estado.configure(text=f"Configuração inválida: {mensagem}", fg=COR_ERRO)
                self._agendar(100, lambda aviso=mensagem: self.abrir_assistente_inicial(aviso))

    def _agendar(self, atraso, funcao):
        referencia = {}
        def executar():
            self._agendamentos.discard(referencia["id"])
            if not self._fechada:
                funcao()
        referencia["id"] = self.raiz.after(atraso, executar)
        self._agendamentos.add(referencia["id"])

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
        widget.tag_configure("codigo", background="#0b1621", foreground="#dce8ee",
                             font=("Consolas", 10), lmargin1=16, lmargin2=16, rmargin=12)
        widget.tag_configure("codigo_cabecalho", background="#263b4a", foreground=COR_SUAVE,
                             font=("Segoe UI", 9, "bold"), lmargin1=16, lmargin2=16)
        widget.tag_configure("codigo_palavra", foreground="#c792ea")
        widget.tag_configure("codigo_nome", foreground="#82cfff")
        widget.tag_configure("codigo_texto", foreground="#a5e3a6")
        widget.tag_configure("codigo_numero", foreground="#f6c477")
        widget.tag_configure("codigo_comentario", foreground="#849daa")
        widget.tag_configure("inline_codigo", background="#2b4050", foreground="#8ee6de",
                             font=("Consolas", 10))

    @staticmethod
    def _tag_codigo(token):
        if token in Token.Comment:
            return "codigo_comentario"
        if token in Token.Keyword or token in Token.Operator.Word:
            return "codigo_palavra"
        if token in Token.Name.Function or token in Token.Name.Class or token in Token.Name.Builtin:
            return "codigo_nome"
        if token in Token.Literal.String:
            return "codigo_texto"
        if token in Token.Literal.Number:
            return "codigo_numero"
        return "codigo"

    @staticmethod
    def _inserir_prosa(widget, texto, links_permitidos=frozenset()):
        for trecho in re.split(r"(`[^`\n]+`)", texto):
            if trecho.startswith("`") and trecho.endswith("`") and len(trecho) > 2:
                widget.insert("end", trecho[1:-1], "inline_codigo")
            else:
                posicao = 0
                for link in re.finditer(r"\[([^\]\n]{1,180})\]\((https?://[^\s)]+)\)", trecho):
                    widget.insert("end", trecho[posicao:link.start()], "corpo")
                    url = link.group(2)
                    if url in links_permitidos:
                        tag = f"fonte_link_{len(widget.tag_names())}"
                        widget.tag_configure(tag, foreground=COR_DESTAQUE, underline=1)
                        widget.insert("end", link.group(1), tag)
                        widget.tag_bind(tag, "<Button-1>", lambda _evento, destino=url: webbrowser.open_new_tab(destino))
                    else:
                        widget.insert("end", link.group(0), "corpo")
                    posicao = link.end()
                widget.insert("end", trecho[posicao:], "corpo")

    def _inserir_codigo(self, widget, linguagem, codigo):
        etiqueta = linguagem.upper() if linguagem != "código" else "CÓDIGO"
        widget.insert("end", f"  {etiqueta}   ·   ", "codigo_cabecalho")
        tag_copiar = f"copiar_codigo_{len(widget.tag_names())}"
        widget.tag_configure(tag_copiar, background="#263b4a", foreground=COR_DESTAQUE,
                             font=("Segoe UI", 9, "bold"), underline=1)
        widget.insert("end", "Copiar código", tag_copiar)
        widget.tag_bind(tag_copiar, "<Button-1>", lambda _evento, bloco=codigo: self._copiar_codigo(bloco))
        widget.insert("end", "\n", "codigo_cabecalho")
        try:
            lexer = get_lexer_by_name(linguagem, stripall=False)
        except ClassNotFound:
            lexer = TextLexer(stripall=False)
        for token, trecho in lex(codigo + "\n", lexer):
            widget.insert("end", trecho, ("codigo", self._tag_codigo(token)))

    def _copiar_codigo(self, codigo):
        self.raiz.clipboard_clear()
        self.raiz.clipboard_append(codigo)
        self.estado.configure(text="Código copiado.", fg=COR_SUAVE)

    def _montar(self):
        self.raiz.grid_columnconfigure(0, weight=1, uniform="paineis")
        self.raiz.grid_columnconfigure(1, weight=1, uniform="paineis")
        self.raiz.grid_rowconfigure(3, weight=1)

        topo = tk.Frame(self.raiz, bg=COR_FUNDO)
        topo.grid(row=0, column=0, columnspan=2, sticky="ew", padx=22, pady=(18, 10))
        titulo = tk.Frame(topo, bg=COR_FUNDO)
        titulo.pack(side="left")
        self._rotulo(titulo, "✦  Assistente IA", 21).pack(anchor="w")
        self._rotulo(titulo, "Escreva ou converse por voz, no seu ritmo.", 10, COR_SUAVE).pack(anchor="w")
        self.pesquisa = self._botao(topo, "Pesquisa: ligada", self.alternar_pesquisa, cor=COR_PESQUISA)
        self.pesquisa.pack(side="right", padx=(12, 0))
        self.configurar = self._botao(topo, "Configurações", self.abrir_configuracoes)
        self.configurar.pack(side="right")
        self.gerenciar = self._botao(topo, "Memória", self.abrir_memorias)
        self.gerenciar.pack(side="right", padx=(0, 8))

        self.abas = tk.Frame(self.raiz, bg="#253342", highlightbackground="#40566e", highlightthickness=1)
        self.abas.grid(row=1, column=0, columnspan=2, sticky="ew", padx=22, pady=(0, 10))
        self.abas.grid_columnconfigure(0, weight=1, uniform="abas")
        self.abas.grid_columnconfigure(1, weight=1, uniform="abas")
        self.aba_texto = self._botao(self.abas, "Texto (Ativo)", lambda: self.selecionar_modo("texto"), cor="#465568")
        self.aba_voz = self._botao(self.abas, "Voz", lambda: self.selecionar_modo("voz"))
        self.aba_texto.configure(fg=COR_TEXTO)
        self.aba_texto.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        self.aba_voz.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        self.linha_texto = tk.Frame(self.abas, bg=COR_DESTAQUE, height=3)
        self.linha_voz = tk.Frame(self.abas, bg=COR_AUDIO, height=3)
        self.linha_texto.grid(row=1, column=0, sticky="ew", padx=4)

        self.confirmacao = tk.Frame(self.raiz, bg="#29453e", padx=16, pady=12)
        self.confirmacao.grid(row=2, column=0, columnspan=2, sticky="ew", padx=22, pady=(0, 10))
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
        self.area_escrita.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=22, pady=(0, 14))
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
        self.nao_salvar = tk.BooleanVar(value=False)
        tk.Checkbutton(rodape_escrita, text="Não salvar esta troca", variable=self.nao_salvar,
                       bg=COR_CARTAO, fg=COR_SUAVE, selectcolor=COR_ENTRADA,
                       activebackground=COR_CARTAO, activeforeground=COR_TEXTO,
                       font=("Segoe UI", 9)).pack(side="left", padx=(15, 0))
        self.enviar = self._botao(rodape_escrita, "Enviar", self.enviar_texto, True)
        self.enviar.pack(side="right")

        self.area_audio = tk.Frame(self.raiz, bg=COR_CARTAO, padx=16, pady=16,
                                   highlightbackground="#594f7c", highlightthickness=1)
        self.area_audio.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=22, pady=(0, 14))
        self.area_audio.grid_columnconfigure(0, weight=1)
        self.area_audio.grid_rowconfigure(3, weight=2)
        self.area_audio.grid_rowconfigure(5, weight=1)
        rotulo_audio = self._rotulo(self.area_audio, "ÁUDIO", 17, COR_AUDIO)
        rotulo_audio.configure(anchor="center")
        rotulo_audio.grid(row=0, column=0, sticky="ew")
        self.descricao_audio = self._rotulo(self.area_audio, "Fale e faça uma pausa ao terminar.", 10, COR_SUAVE)
        self.descricao_audio.configure(anchor="center")
        self.descricao_audio.grid(
            row=1, column=0, sticky="ew", pady=(2, 8)
        )
        self.estado_audio = self._rotulo(self.area_audio, "Microfone desligado", 11, COR_SUAVE)
        self.estado_audio.configure(anchor="center", font=("Segoe UI", 12, "bold"))
        self.estado_audio.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        self.onda = tk.Canvas(self.area_audio, bg=COR_CARTAO, highlightthickness=0, height=140)
        self.onda.grid(row=3, column=0, sticky="nsew", pady=(4, 8))
        controles_audio = tk.Frame(self.area_audio, bg=COR_CARTAO)
        controles_audio.grid(row=4, column=0, pady=(0, 14))
        self.falar = self._botao(controles_audio, "Ativar microfone", self.alternar_microfone, cor=COR_AUDIO)
        self.falar.pack(side="left", padx=(0, 8))
        self.parar = self._botao(controles_audio, "Parar resposta", self.motor.interromper_fala)
        self.parar.pack(side="left")
        self.historico_audio = scrolledtext.ScrolledText(
            self.area_audio, wrap="word", state="disabled", bg=COR_ENTRADA,
            fg=COR_TEXTO, insertbackground=COR_TEXTO, relief="flat",
            font=("Segoe UI", 10), padx=12, pady=12, width=1, height=4,
        )
        self.historico_audio.grid(row=5, column=0, sticky="nsew")
        self._configurar_historico(self.historico_audio)
        self.area_audio.grid_remove()

        self.estado = self._rotulo(self.raiz, "Iniciando…", 10, COR_SUAVE)
        self.estado.grid(row=4, column=0, columnspan=2, sticky="ew", padx=22, pady=(0, 13))
        self.falar.configure(state="disabled")
        self.enviar.configure(state="disabled")
        self.pesquisa.configure(state="disabled")
        self.gerenciar.configure(state="disabled")
        self._agendar(80, self._animar_onda)

    def _enter(self, evento):
        if evento.state & 0x0001:
            return None
        self.enviar_texto()
        return "break"

    def enviar_texto(self):
        texto = self.entrada.get("1.0", "end-1c").strip()
        if texto and self.pronto:
            self.entrada.delete("1.0", "end")
            nao_salvar = self.nao_salvar.get()
            self.nao_salvar.set(False)
            self.motor.enviar_texto(texto, nao_salvar=nao_salvar)
            self.estado.configure(text="Aguardando resposta…" + (" Esta troca não será salva." if nao_salvar else ""))

    def _ajustar_layout(self, evento):
        if evento.widget is not self.raiz:
            return
        self.descricao_escrita.configure(wraplength=max(300, evento.width - 90))
        self.descricao_audio.configure(wraplength=max(300, evento.width - 90))
        self.detalhes_confirmacao.configure(wraplength=max(250, evento.width - 340))

    def selecionar_modo(self, modo):
        if modo not in {"texto", "voz"} or modo == self.modo:
            return
        self.modo = modo
        if modo == "voz":
            self.area_escrita.grid_remove()
            self.area_audio.grid()
            self.aba_texto.configure(text="Texto", bg="#253342", fg=COR_SUAVE)
            self.aba_voz.configure(text="Voz (Ativa)", bg="#465568", fg=COR_TEXTO)
            self.linha_texto.grid_remove()
            self.linha_voz.grid(row=1, column=1, sticky="ew", padx=4)
            self._desenhar_onda()
            if self.pronto and not self.microfone_ligado and not self.microfone_mutado:
                self.motor.ativar_microfone()
                self._mostrar_microfone(True)
            elif self.microfone_mutado:
                self._mostrar_microfone(False)
        else:
            self.area_audio.grid_remove()
            self.area_escrita.grid()
            self.aba_texto.configure(text="Texto (Ativo)", bg="#465568", fg=COR_TEXTO)
            self.aba_voz.configure(text="Voz", bg="#253342", fg=COR_SUAVE)
            self.linha_voz.grid_remove()
            self.linha_texto.grid()
            if self.microfone_ligado:
                self.motor.desativar_microfone()
                self._mostrar_microfone(False)

    def _desenhar_onda(self):
        largura = self.onda.winfo_width()
        altura = self.onda.winfo_height()
        if largura <= 20 or altura <= 20:
            return
        self.onda.delete("all")
        centro = altura / 2
        self.onda.create_line(0, centro, largura, centro, fill="#50647e", width=2)
        energia = (38 + 64 * self.nivel_audio) if self.microfone_ligado else 2
        for indice, cor in enumerate(("#af4de4", "#7875e8", "#46c9e2")):
            pontos = []
            for x in range(0, largura + 8, 8):
                proporcao = min(x / largura, 1)
                envelope = math.sin(math.pi * proporcao) ** 2
                onda = math.sin(proporcao * (12 + indice * 3) * math.pi + self.fase_onda + indice)
                y = centro + energia * envelope * onda * (1 - indice * 0.18)
                pontos.extend((x, y))
            self.onda.create_line(*pontos, fill=cor, width=3, smooth=True)
        self.fase_onda += 0.16
        self.nivel_audio *= 0.88

    def _animar_onda(self):
        try:
            if self.modo == "voz":
                self._desenhar_onda()
            self._agendar(80, self._animar_onda)
        except tk.TclError:
            pass

    def _mostrar_microfone(self, ativo):
        self.microfone_ligado = ativo
        self.falar.configure(text="Mutar microfone" if ativo else "Ativar microfone",
                             bg="#34485a" if ativo else COR_AUDIO,
                             fg=COR_AUDIO if ativo else COR_FUNDO)
        self.estado_audio.configure(text="Microfone ativado e ouvindo…" if ativo else
                                     "Microfone mutado" if self.microfone_mutado else "Microfone desligado",
                                     fg=COR_AUDIO if ativo else COR_SUAVE)

    def alternar_microfone(self):
        if not self.pronto:
            return
        if self.microfone_ligado:
            self.microfone_mutado = True
            self.motor.desativar_microfone()
            self._mostrar_microfone(False)
        else:
            self.microfone_mutado = False
            self.motor.ativar_microfone()
            self._mostrar_microfone(True)

    def abrir_configuracoes(self):
        """Abre todas as preferências em uma única janela."""
        self.abrir_assistente_inicial()

    def abrir_memorias(self):
        if not self.pronto:
            return
        if self.janela_memoria is not None and self.janela_memoria.janela.winfo_exists():
            self.janela_memoria.janela.lift()
            return
        self.janela_memoria = memoria_ui.JanelaMemoria(self.raiz, self.motor.gerenciar_memoria)

    def abrir_assistente_inicial(self, erro=""):
        if self.assistente is not None and self.assistente.janela.winfo_exists():
            self.assistente.janela.lift()
            return
        self.assistente = primeira_execucao.AssistenteConfiguracao(
            self.raiz, self._configuracao_salva, primeira=not self.motor_iniciado,
            erro_configuracao=erro if isinstance(erro, str) else "",
        )

    def _configuracao_salva(self, dados):
        configuracao.aplicar(dados)
        self._mostrar_pesquisa()
        if self.motor_iniciado and not self.motor.thread.is_alive():
            self.motor = MotorDesktop(self.eventos)
            self.parar.configure(command=self.motor.interromper_fala)
            self.motor_iniciado = False
        if not self.motor_iniciado:
            self.motor.iniciar()
            self.motor_iniciado = True
            self.estado.configure(text="Iniciando assistente…", fg=COR_SUAVE)
        else:
            self.estado.configure(text="Configurações atualizadas.", fg=COR_SUAVE)

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
            diagnostico.registrar("configuracao.gravacao_falhou", erro=erro)
            self.estado.configure(text="Não foi possível salvar a pesquisa. Confira a pasta de dados em Configurações → Diagnóstico.", fg=COR_ERRO)

    def _confirmar(self, aceita):
        self.motor.responder_confirmacao(aceita)
        self.confirmacao.grid_remove()

    def _escrever(self, widget, autor, mensagem):
        papel = {"Você": "usuario", "Você · não salvo": "usuario", "IA": "ia", "Arquivo": "arquivo", "Erro": "erro"}.get(autor, "ia")
        links_permitidos = set()
        if autor == "IA" and "\nFontes consultadas:\n" in mensagem:
            fontes = mensagem.rsplit("\nFontes consultadas:\n", 1)[1]
            for link in re.finditer(r"(?m)^\d+\. \[[^\]\n]{1,150}\]\((https?://[^\s)]+)\)", fontes):
                try:
                    links_permitidos.add(internet.validar_url(link.group(1)))
                except ValueError:
                    pass
        widget.configure(state="normal")
        widget.insert("end", autor.upper() + "\n", papel)
        for tipo, linguagem, conteudo in renderizacao.fragmentos(mensagem.strip()):
            if tipo == "codigo":
                self._inserir_codigo(widget, linguagem, conteudo)
            else:
                self._inserir_prosa(widget, conteudo, links_permitidos)
        widget.insert("end", "\n\n", "corpo")
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
                    self.configurar.configure(state="normal")
                    self.gerenciar.configure(state="normal")
                    if self.modo == "voz" and not self.microfone_mutado:
                        self.motor.ativar_microfone()
                        self._mostrar_microfone(True)
                elif tipo == "mensagem":
                    origem, autor, mensagem = dados
                    destino = self.historico_audio if origem == "audio" else self.historico_escrita
                    self._escrever(destino, autor, mensagem)
                elif tipo == "estado":
                    self.estado.configure(text=dados[0])
                elif tipo == "estado_audio":
                    if not self.microfone_mutado or self.microfone_ligado:
                        self.estado_audio.configure(text=dados[0], fg=COR_ERRO if "Falha" in dados[0] or "indisponível" in dados[0] else COR_AUDIO)
                elif tipo == "microfone_ativo":
                    if not (self.microfone_mutado and dados[0]):
                        self._mostrar_microfone(dados[0])
                elif tipo == "nivel_audio":
                    if self.microfone_ligado:
                        self.nivel_audio = max(self.nivel_audio, dados[0])
                elif tipo == "modo":
                    self.selecionar_modo(dados[0])
                elif tipo == "confirmar":
                    self.titulo_confirmacao.configure(text=dados[0])
                    self.detalhes_confirmacao.configure(text=dados[1])
                    self.confirmacao.grid()
                elif tipo == "limpar_confirmacao":
                    self.confirmacao.grid_remove()
                elif tipo == "fatal":
                    self.pronto = False
                    self.enviar.configure(state="disabled")
                    self.falar.configure(state="disabled")
                    self.gerenciar.configure(state="disabled")
                    self.estado.configure(text=dados[0] if dados else erros.orientar(RuntimeError(), "inicio"), fg=COR_ERRO)
                    self.estado_audio.configure(text="Indisponível")
                elif tipo == "memoria_dados":
                    if self.janela_memoria is not None and self.janela_memoria.janela.winfo_exists():
                        self.janela_memoria.mostrar_dados(dados[0])
                elif tipo == "memoria_erro":
                    if self.janela_memoria is not None and self.janela_memoria.janela.winfo_exists():
                        self.janela_memoria.mostrar_erro(dados[0])
                elif tipo == "memoria_zerada":
                    for widget in (self.historico_escrita, self.historico_audio):
                        widget.configure(state="normal")
                        widget.delete("1.0", "end")
                        widget.configure(state="disabled")
                    self.estado.configure(text="Memória e histórico do banco ativo apagados.")
                elif tipo == "fechar":
                    self.fechar()
                    return
        except queue.Empty:
            pass
        self._agendar(60, self._processar_eventos)

    def fechar(self):
        if self._fechada:
            return
        self._fechada = True
        for identificador in self._agendamentos:
            try:
                self.raiz.after_cancel(identificador)
            except tk.TclError:
                pass
        self._agendamentos.clear()
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
        assert janela.area_escrita.winfo_manager() == "grid"
        assert janela.area_audio.winfo_manager() == ""
        janela.selecionar_modo("voz")
        assert janela.area_escrita.winfo_manager() == ""
        assert janela.area_audio.winfo_manager() == "grid"
        recursos = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "resources"
        assert (recursos / "vozes" / "pt_BR-faber-medium.onnx").is_file()
        assert (recursos / "config_geral.json").is_file()
        assert (recursos / "config_servicos.json").is_file()
        janela.fechar()
    else:
        JanelaAssistente().executar()


if __name__ == "__main__":
    executar()
