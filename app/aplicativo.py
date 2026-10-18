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
from datetime import datetime
from pathlib import Path
from tkinter import scrolledtext
from tkinter import filedialog, messagebox
import customtkinter as ctk
from pygments import lex
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.token import Token
from pygments.util import ClassNotFound

from . import acoes
from . import atualizacoes
from . import banco
from . import caminhos
from . import ativacao
from . import diagnostico
from . import erros
from . import internet
from . import icones
from . import icone_app
from . import main
from . import memoria
from . import memoria_ui
from . import resumos
from . import renderizacao
from . import servicos
from . import configuracao
from .conversa import ConversationService
from . import primeira_execucao
from . import voz


NOME_APP = "AssistenteIA"
COR_FUNDO = "#0b1424"
COR_CARTAO = "#12223a"
COR_TEXTO = "#f3f6ff"
COR_SUAVE = "#a8bad2"
COR_DESTAQUE = "#4bd8d0"
COR_AUDIO = "#ad91ff"
COR_PESQUISA = "#efc477"
COR_ERRO = "#ff849c"
COR_ENTRADA = "#172b47"
COR_BOTAO = "#1c3150"
COR_BORDA = "#2b4366"
ctk.set_appearance_mode("dark")


class _BotaoArredondado(ctk.CTkButton):
    """Aceita as opções de cor usadas pelos controles existentes da janela."""

    def __getitem__(self, chave):
        return self.cget(chave)

    def configure(self, require_redraw=False, **kwargs):
        if "bg" in kwargs:
            kwargs["fg_color"] = kwargs.pop("bg")
        if "fg" in kwargs:
            kwargs["text_color"] = kwargs.pop("fg")
        kwargs.pop("padx", None)
        kwargs.pop("pady", None)
        return super().configure(require_redraw=require_redraw, **kwargs)


def _reiniciar_memoria_apos_instalacao(dados):
    """Consome a marca criada pelo instalador antes de abrir qualquer conexão SQLite."""
    marcador = dados / "reiniciar_memoria.flag"
    if not marcador.exists() and not marcador.is_symlink():
        return False
    if marcador.is_symlink() or not marcador.is_file():
        raise OSError("Marcador de reinicialização da memória inválido.")
    for nome in ("memoria.db", "memoria.db-wal", "memoria.db-shm", "memoria.db-journal"):
        arquivo = dados / nome
        if arquivo.is_dir():
            raise OSError(f"Não foi possível remover {nome}: é uma pasta.")
        arquivo.unlink(missing_ok=True)
    for arquivo in dados.glob("memoria_antes_v2_*.db"):
        if re.fullmatch(r"memoria_antes_v2_\d{8}_\d{6}_\d{6}_UTC\.db", arquivo.name):
            if arquivo.is_dir():
                raise OSError(f"Não foi possível remover {arquivo.name}: é uma pasta.")
            arquivo.unlink()
    pasta = dados / "backups"
    if pasta.exists() or pasta.is_symlink():
        if pasta.is_symlink() or pasta.resolve().parent != dados.resolve() or not pasta.is_dir():
            raise OSError("Pasta de backups da memória inválida.")
        shutil.rmtree(pasta)
    marcador.unlink()
    return True


def preparar_arquivos_usuario():
    """Mantém configurações fora da instalação e zera a memória marcada pelo instalador."""
    dados = caminhos.pasta_dados()
    dados.mkdir(parents=True, exist_ok=True)
    _reiniciar_memoria_apos_instalacao(dados)
    origem = Path(__file__).resolve().parent.parent
    recursos = Path(getattr(sys, "_MEIPASS", origem)) / "resources"
    destino = caminhos.caminho_banco()
    for nome in ("config_voz.json", "config_internet.json", "config_servicos.json", "config_geral.json"):
        arquivo = dados / nome
        modelo = recursos / nome
        if not arquivo.exists() and modelo.is_file():
            shutil.copy2(modelo, arquivo)
    pasta_trabalho = caminhos.pasta_trabalho()
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
                            if banco.NOME_LEGADO.fullmatch(copia.name) and not copia.is_symlink():
                                copia.unlink()
                    arquivados = banco.pasta_backups(main.BANCO) / "legado"
                    if arquivados.is_dir() and not arquivados.is_symlink():
                        for copia in arquivados.glob("memoria_antes_v2_*.db"):
                            if banco.NOME_LEGADO.fullmatch(copia.name) and not copia.is_symlink():
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
            servico = ConversationService(
                lambda texto, voz: main.atender_acao(
                    texto, modo_voz=voz, confirmar=self._autorizar_acao,
                    mostrar=lambda conteudo: self._emitir("mensagem", origem, "Arquivo", conteudo)),
                lambda texto, h, voz: main.preparar_pesquisa(
                    texto, h, modo_voz=voz, pedir_autorizacao=self._autorizar_pesquisa),
                lambda con, h, texto, voz, pesquisa: main.obter_resposta(
                    con, h, texto, modo_voz=voz, pesquisa=pesquisa),
            )
            resposta = servico.responder(conexao, historico, pergunta, modo_voz=(origem == "audio"))
        except Exception as erro:
            diagnostico.registrar("conversa.resposta_falhou", erro=erro)
            self._emitir("mensagem", origem, "Erro", erros.orientar(erro))
            self._emitir("estado", "Pronto")
            return
        if self.encerrando.is_set():
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
                    cancelar_atual = threading.Event()
                    self.cancelar_captura = cancelar_atual
                    if not self.microfone_ativo.is_set():
                        cancelar_atual.set()
                        continue
                    self._emitir("estado_audio", "Ouvindo · fale no seu ritmo")
                    try:
                        from .voz import ouvir
                        texto = ouvir(
                            cancelar=cancelar_atual, teclado=False, aguardar_fala=True,
                            ao_capturar=lambda: self._emitir("estado_audio", "Transcrevendo sua fala…"),
                            ao_nivel=lambda nivel: self._emitir("nivel_audio", nivel),
                        )
                    except Exception as erro:
                        diagnostico.registrar("microfone.captura_falhou", erro=erro)
                        self.desativar_microfone()
                        self._emitir("microfone_ativo", False)
                        self._emitir("estado_audio", erros.orientar(erro, "microfone"))
                        continue
                    if not texto or cancelar_atual.is_set():
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
        icone_app.aplicar(self.raiz, padrao=True)
        self.raiz.geometry("1180x820")
        self.raiz.minsize(850, 680)
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
        self.atualizacao = None
        self.ultima_verificacao = atualizacoes.carregar_ultima_verificacao()
        self.verificacao_iniciada = False
        self.verificacao_em_andamento = False
        self.cancelar_atualizacao = threading.Event()
        self._verificacao_id = 0
        self._fechada = False
        self._agendamentos = set()
        self._montar()
        if self.ultima_verificacao:
            data = self.ultima_verificacao["verificado_em"][:10]
            estado = {"atualizada": "sem novidade", "disponivel": "nova versão",
                      "falha": "falhou", "cancelada": "cancelada"}[self.ultima_verificacao["status"]]
            self.botao_atualizacao.configure(text=f"Versão · {estado} em {data}")
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
        if not self._janela_ativa():
            return
        referencia = {}
        def executar():
            self._agendamentos.discard(referencia["id"])
            if self._janela_ativa():
                funcao()
        referencia["id"] = self.raiz.after(atraso, executar)
        self._agendamentos.add(referencia["id"])

    def _janela_ativa(self):
        try:
            return not self._fechada and bool(self.raiz.winfo_exists())
        except tk.TclError:
            return False

    def _rotulo(self, pai, texto, tamanho=11, cor=COR_TEXTO, **opcoes):
        return tk.Label(
            pai, text=texto, bg=pai["bg"], fg=cor,
            font=("Segoe UI", tamanho), anchor="w", **opcoes,
        )

    def _botao(self, pai, texto, comando, destaque=False, cor=None, icone=None, icone_cor=None):
        fundo = cor or (COR_DESTAQUE if destaque else COR_BOTAO)
        return _BotaoArredondado(
            pai, text=texto, command=comando, cursor="hand2", height=42,
            corner_radius=11, fg_color=fundo,
            text_color=COR_FUNDO if destaque or cor else COR_TEXTO,
            hover_color=cor or ("#78e8e0" if destaque else "#304d70"),
            text_color_disabled=COR_SUAVE, font=("Segoe UI", 10, "bold"),
            image=icones.obter(icone, icone_cor or (COR_FUNDO if destaque or cor else COR_DESTAQUE))
            if icone else None,
        )

    def _configurar_historico(self, widget):
        for papel, cor in (("usuario", COR_DESTAQUE), ("ia", COR_AUDIO),
                           ("arquivo", COR_PESQUISA), ("erro", COR_ERRO)):
            widget.tag_configure(papel, foreground=cor, font=("Segoe UI", 10, "bold"))
        widget.tag_configure("corpo", foreground=COR_TEXTO, spacing3=6,
                             font=("Segoe UI", 11))
        widget.tag_configure("separador", foreground=COR_BORDA, spacing1=7, spacing3=10)
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
        if hasattr(widget, "vbar"):
            widget.vbar.configure(bg=COR_BOTAO, troughcolor=COR_ENTRADA,
                                  activebackground=COR_DESTAQUE, bd=0,
                                  highlightthickness=0)

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
        topo.grid(row=0, column=0, columnspan=2, sticky="ew", padx=28, pady=(24, 20))
        titulo = tk.Frame(topo, bg=COR_FUNDO)
        titulo.pack(side="left")
        marca = tk.Frame(titulo, bg=COR_FUNDO)
        marca.pack(anchor="w")
        self.marca_icone = icone_app.imagem_cabecalho(54)
        ctk.CTkLabel(marca, text="", image=self.marca_icone, width=54, height=54).pack(
            side="left", padx=(0, 10))
        self._rotulo(marca, "Assistente IA", 22).pack(side="left")
        self._rotulo(titulo, "Converse do seu jeito", 10, COR_SUAVE).pack(anchor="w", padx=64)
        acoes_topo = tk.Frame(topo, bg=COR_FUNDO)
        acoes_topo.pack(side="right")
        self.gerenciar = self._botao(acoes_topo, "Memória", self.abrir_memorias, icone="memory")
        self.gerenciar.configure(font=("Segoe UI", 12, "bold"), height=46)
        self.gerenciar.pack(side="right")
        self.configurar = self._botao(acoes_topo, "Configurações", self.abrir_configuracoes, icone="settings")
        self.configurar.configure(font=("Segoe UI", 12, "bold"), height=46)
        self.configurar.pack(side="right", padx=(0, 8))
        self.pesquisa = self._botao(acoes_topo, "Pesquisa: ligada", self.alternar_pesquisa, icone="search")
        self.pesquisa.configure(font=("Segoe UI", 12, "bold"), height=46)
        self.pesquisa.pack(side="right", padx=(0, 8))

        self.abas = tk.Frame(self.raiz, bg=COR_FUNDO)
        self.abas.grid(row=1, column=0, columnspan=2, sticky="ew", padx=28, pady=(0, 12))
        self.grupo_abas = tk.Frame(self.abas, bg=COR_FUNDO)
        self.grupo_abas.pack(anchor="center")
        self.aba_texto = self._botao(self.grupo_abas, "Texto", lambda: self.selecionar_modo("texto"), icone="text")
        self.aba_voz = self._botao(self.grupo_abas, "Voz", lambda: self.selecionar_modo("voz"), icone="voice")
        self.aba_texto.configure(font=("Segoe UI", 13, "bold"), height=52, width=215)
        self.aba_voz.configure(font=("Segoe UI", 13, "bold"), height=52, width=215)
        self.aba_texto.configure(bg="#1d3b57")
        self.aba_texto.configure(fg=COR_TEXTO)
        self.aba_texto.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=(0, 4))
        self.aba_voz.grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=(0, 4))
        self.linha_texto = tk.Frame(self.grupo_abas, bg=COR_DESTAQUE, height=3)
        self.linha_voz = tk.Frame(self.grupo_abas, bg=COR_BORDA, height=3)
        self.linha_texto.grid(row=1, column=0, sticky="ew")
        self.linha_voz.grid(row=1, column=1, sticky="ew")

        self.confirmacao = tk.Frame(self.raiz, bg="#1c3d46", padx=18, pady=13,
                                   highlightbackground=COR_DESTAQUE, highlightthickness=1)
        self.confirmacao.grid(row=2, column=0, columnspan=2, sticky="ew", padx=28, pady=(0, 12))
        self.confirmacao.grid_columnconfigure(0, weight=1)
        self.titulo_confirmacao = self._rotulo(self.confirmacao, "", 11)
        self.titulo_confirmacao.grid(row=0, column=0, sticky="w")
        self.detalhes_confirmacao = self._rotulo(self.confirmacao, "", 10, COR_SUAVE, wraplength=760, justify="left")
        self.detalhes_confirmacao.grid(row=1, column=0, sticky="w", pady=(3, 0))
        botoes_confirmacao = tk.Frame(self.confirmacao, bg=self.confirmacao["bg"])
        botoes_confirmacao.grid(row=0, column=1, rowspan=2, padx=(18, 0))
        self._botao(botoes_confirmacao, "Cancelar", lambda: self._confirmar(False), icone="close").pack(side="left", padx=(0, 8))
        self._botao(botoes_confirmacao, "Confirmar", lambda: self._confirmar(True), True, icone="check").pack(side="left")
        self.confirmacao.grid_remove()

        self.area_escrita = tk.Frame(self.raiz, bg=COR_FUNDO)
        self.area_escrita.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=28, pady=(0, 12))
        self.area_escrita.grid_columnconfigure(0, weight=1)
        self.area_escrita.grid_rowconfigure(0, weight=1)
        painel_escrita = ctk.CTkFrame(self.area_escrita, fg_color=COR_CARTAO,
                                      border_color=COR_BORDA, border_width=1, corner_radius=20)
        painel_escrita.grid(row=0, column=0, sticky="nsew")
        painel_escrita.grid_columnconfigure(0, weight=1)
        painel_escrita.grid_rowconfigure(0, weight=1)
        conteudo_escrita = tk.Frame(painel_escrita, bg=COR_CARTAO)
        conteudo_escrita.grid(row=0, column=0, sticky="nsew", padx=17, pady=16)
        conteudo_escrita.grid_columnconfigure(0, weight=1)
        conteudo_escrita.grid_rowconfigure(0, weight=1)
        conversa = ctk.CTkFrame(conteudo_escrita, fg_color="#101e34", corner_radius=15,
                                border_color=COR_BORDA, border_width=1)
        conversa.grid(row=0, column=0, sticky="nsew")
        conversa.grid_columnconfigure(0, weight=1)
        conversa.grid_rowconfigure(0, weight=1)
        self.cartoes_escrita = ctk.CTkScrollableFrame(
            conversa, fg_color="transparent", corner_radius=0,
            scrollbar_button_color="#355076", scrollbar_button_hover_color=COR_DESTAQUE)
        self.cartoes_escrita.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.cartoes_escrita.grid_columnconfigure(0, weight=1)
        self.vazio_escrita = ctk.CTkLabel(self.cartoes_escrita,
            text="Comece a conversa escrevendo uma mensagem abaixo.",
            text_color=COR_SUAVE, font=("Segoe UI", 13))
        self.vazio_escrita.grid(row=0, column=0, pady=34)
        self.historico_escrita = scrolledtext.ScrolledText(
            conteudo_escrita, wrap="word", state="disabled", bg=COR_ENTRADA,
            fg=COR_TEXTO, insertbackground=COR_TEXTO, relief="flat",
            font=("Segoe UI", 11), padx=22, pady=20, width=1, height=4,
        )
        self._configurar_historico(self.historico_escrita)
        self._cartoes_historico = {
            self.historico_escrita: (self.cartoes_escrita, self.vazio_escrita),
        }
        rodape_escrita = tk.Frame(conteudo_escrita, bg=COR_CARTAO)
        rodape_escrita.grid(row=1, column=0, sticky="ew", pady=(13, 0))
        self.nao_salvar = tk.BooleanVar(value=False)
        tk.Checkbutton(rodape_escrita, text="Não salvar esta troca", variable=self.nao_salvar,
                       bg=COR_CARTAO, fg=COR_SUAVE, selectcolor=COR_ENTRADA,
                       activebackground=COR_CARTAO, activeforeground=COR_TEXTO,
                       font=("Segoe UI", 9)).pack(side="left")
        self._rotulo(rodape_escrita, "Enter envia  ·  Shift+Enter quebra linha", 9, COR_SUAVE).pack(side="right")
        compositor = tk.Frame(conteudo_escrita, bg=COR_CARTAO)
        compositor.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        compositor.grid_columnconfigure(0, weight=1)
        campo_entrada = ctk.CTkFrame(compositor, fg_color=COR_ENTRADA,
            border_color=COR_BORDA, border_width=1, corner_radius=14)
        campo_entrada.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.entrada = tk.Text(
            campo_entrada, height=2, width=1, wrap="word", bg=COR_ENTRADA,
            fg=COR_TEXTO, insertbackground=COR_TEXTO, relief="flat",
            font=("Segoe UI", 11), padx=12, pady=9,
        )
        self.entrada.pack(fill="both", expand=True, padx=7, pady=7)
        self.entrada.bind("<Return>", self._enter)
        self.enviar = self._botao(compositor, "Enviar", self.enviar_texto, True, icone="send")
        self.enviar.configure(font=("Segoe UI", 16, "bold"), height=66, width=160)
        self.enviar.grid(row=0, column=1, sticky="ns")

        self.area_audio = tk.Frame(self.raiz, bg=COR_FUNDO)
        self.area_audio.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=28, pady=(0, 12))
        self.area_audio.grid_columnconfigure(0, weight=1)
        self.area_audio.grid_rowconfigure(0, weight=1)
        painel_audio = ctk.CTkFrame(self.area_audio, fg_color=COR_CARTAO,
                                   border_color=COR_BORDA, border_width=1, corner_radius=20)
        painel_audio.grid(row=0, column=0, sticky="nsew")
        painel_audio.grid_columnconfigure(0, weight=1)
        painel_audio.grid_rowconfigure(0, weight=1)
        conteudo_audio = tk.Frame(painel_audio, bg=COR_CARTAO)
        conteudo_audio.grid(row=0, column=0, sticky="nsew", padx=22, pady=18)
        conteudo_audio.grid_columnconfigure(0, weight=1)
        conteudo_audio.grid_rowconfigure(6, weight=1, minsize=125)
        simbolo = ctk.CTkFrame(conteudo_audio, width=78, height=78, corner_radius=39,
                               fg_color="#1c2b56", border_color=COR_AUDIO, border_width=2)
        simbolo.grid_propagate(False)
        ctk.CTkLabel(simbolo, text="", image=icones.obter("voice", COR_AUDIO, 34),
                     width=44, height=44).place(relx=0.5, rely=0.5, anchor="center")
        simbolo.grid(row=0, column=0, pady=(2, 4))
        self.estado_audio = self._rotulo(conteudo_audio, "Microfone desligado", 19, COR_SUAVE)
        self.estado_audio.configure(anchor="center", font=("Segoe UI", 19, "bold"))
        self.estado_audio.grid(row=1, column=0, sticky="ew")
        self.descricao_audio = self._rotulo(conteudo_audio, "Fale naturalmente e faça uma pausa ao terminar.", 10, COR_SUAVE)
        self.descricao_audio.configure(anchor="center")
        self.descricao_audio.grid(
            row=2, column=0, sticky="ew", pady=(5, 6)
        )
        self.onda = tk.Canvas(conteudo_audio, bg=COR_CARTAO, highlightthickness=0, height=62)
        self.onda.grid(row=3, column=0, sticky="nsew", pady=(2, 4))
        controles_audio = tk.Frame(conteudo_audio, bg=COR_CARTAO)
        controles_audio.grid(row=4, column=0, pady=(0, 9))
        self.falar = self._botao(controles_audio, "Ativar microfone", self.alternar_microfone,
                                cor=COR_AUDIO, icone="voice")
        self.falar.configure(width=210, height=42)
        self.falar.pack(side="left", padx=(0, 12))
        self.parar = self._botao(controles_audio, "Parar resposta", self.motor.interromper_fala,
                                icone="stop", icone_cor=COR_ERRO)
        self.parar.configure(fg=COR_ERRO)
        self.parar.configure(width=210, height=42, border_width=1, border_color=COR_ERRO)
        self.parar.pack(side="left")
        cabecalho_transcricao = tk.Frame(conteudo_audio, bg=COR_CARTAO)
        cabecalho_transcricao.grid(row=5, column=0, sticky="ew", pady=(0, 8))
        self._rotulo(cabecalho_transcricao, "CONVERSA POR VOZ", 10, COR_AUDIO).pack(side="left")
        self._rotulo(cabecalho_transcricao, "Transcrição em tempo real", 9, COR_SUAVE).pack(side="right")
        conversa_audio = ctk.CTkFrame(conteudo_audio, fg_color="#101e34", corner_radius=15,
                                      border_color=COR_BORDA, border_width=1)
        conversa_audio.grid(row=6, column=0, sticky="nsew")
        conversa_audio.grid_columnconfigure(0, weight=1)
        conversa_audio.grid_rowconfigure(0, weight=1)
        self.cartoes_audio = ctk.CTkScrollableFrame(
            conversa_audio, fg_color="transparent", corner_radius=0,
            scrollbar_button_color="#355076", scrollbar_button_hover_color=COR_AUDIO)
        self.cartoes_audio.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.cartoes_audio.grid_columnconfigure(0, weight=1)
        self.vazio_audio = ctk.CTkLabel(self.cartoes_audio,
            text="Ative o microfone e comece a conversar.", text_color=COR_SUAVE,
            font=("Segoe UI", 13))
        self.vazio_audio.grid(row=0, column=0, pady=34)
        self.historico_audio = scrolledtext.ScrolledText(
            conteudo_audio, wrap="word", state="disabled", bg=COR_ENTRADA,
            fg=COR_TEXTO, insertbackground=COR_TEXTO, relief="flat",
            font=("Segoe UI", 11), padx=22, pady=14, width=1, height=4,
        )
        self._configurar_historico(self.historico_audio)
        self._cartoes_historico[self.historico_audio] = (self.cartoes_audio, self.vazio_audio)
        self.area_audio.grid_remove()

        rodape = tk.Frame(self.raiz, bg=COR_FUNDO)
        rodape.grid(row=4, column=0, columnspan=2, sticky="ew", padx=28, pady=(0, 16))
        self.estado = self._rotulo(rodape, "Iniciando…", 10, COR_SUAVE)
        self.estado.pack(side="left")
        self.botao_atualizacao = self._botao(rodape, "Verificar versão", self.verificar_atualizacao,
                                           icone="refresh")
        self.botao_atualizacao.configure(font=("Segoe UI", 9), padx=10, pady=5)
        self.botao_atualizacao.pack(side="right")
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
        self.descricao_audio.configure(wraplength=max(300, evento.width - 90))
        self.detalhes_confirmacao.configure(wraplength=max(250, evento.width - 340))

    def selecionar_modo(self, modo):
        if modo not in {"texto", "voz"} or modo == self.modo:
            return
        self.modo = modo
        if modo == "voz":
            self.area_escrita.grid_remove()
            self.area_audio.grid()
            self.aba_texto.configure(text="Texto", bg=COR_BOTAO, fg=COR_SUAVE)
            self.aba_voz.configure(text="Voz", bg="#352d58", fg=COR_TEXTO)
            self.linha_texto.configure(bg=COR_BORDA)
            self.linha_voz.configure(bg=COR_AUDIO)
            self._desenhar_onda()
            if self.pronto and not self.microfone_ligado and not self.microfone_mutado:
                self.motor.ativar_microfone()
                self._mostrar_microfone(True)
            elif self.microfone_mutado:
                self._mostrar_microfone(False)
        else:
            self.area_audio.grid_remove()
            self.area_escrita.grid()
            self.aba_texto.configure(text="Texto", bg="#1d3b57", fg=COR_TEXTO)
            self.aba_voz.configure(text="Voz", bg=COR_BOTAO, fg=COR_SUAVE)
            self.linha_voz.configure(bg=COR_BORDA)
            self.linha_texto.configure(bg=COR_DESTAQUE)
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
        self.onda.create_line(0, centro, largura, centro, fill=COR_BORDA, width=1)
        quantidade = max(12, min(74, largura // 12))
        espacamento = largura / (quantidade + 1)
        energia = min(1.0, 0.40 + self.nivel_audio * 2.7) if self.microfone_ligado else 0.05
        for indice in range(quantidade):
            proporcao = indice / max(1, quantidade - 1)
            envelope = math.sin(math.pi * proporcao) ** 1.8
            ritmo = abs(math.sin(indice * 0.49 + self.fase_onda))
            amplitude = min(altura * 0.43, 3 + energia * envelope * (12 + 34 * ritmo))
            x = (indice + 1) * espacamento
            cor = COR_AUDIO if proporcao < 0.5 else COR_DESTAQUE
            self.onda.create_line(x, centro - amplitude, x, centro + amplitude,
                                  fill=cor, width=4, capstyle="round")
        self.fase_onda += 0.19
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
                             bg=COR_BOTAO if ativo else COR_AUDIO,
                             fg=COR_AUDIO if ativo else COR_FUNDO)
        self.estado_audio.configure(text="Estou ouvindo" if ativo else
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
        microfone_anterior = voz.MICROFONE_SELECIONADO
        reiniciar_microfone = (self.microfone_ligado and
                              microfone_anterior != dados["microfone"])
        if reiniciar_microfone:
            self.motor.desativar_microfone()
            self._mostrar_microfone(False)
        configuracao.aplicar(dados)
        if reiniciar_microfone:
            self._agendar(250, self._retomar_microfone_configurado)
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
        if dados["verificar_atualizacoes"] and not self.verificacao_iniciada:
            self.verificar_atualizacao(automatica=True)

    def _retomar_microfone_configurado(self):
        if self.pronto and self.modo == "voz" and not self.microfone_mutado:
            self.motor.ativar_microfone()
            self._mostrar_microfone(True)

    def verificar_atualizacao(self, automatica=False):
        """Consulta releases em segundo plano; a abertura do link exige clique."""
        if self.verificacao_em_andamento:
            return
        self.verificacao_iniciada = True
        self.verificacao_em_andamento = True
        self.cancelar_atualizacao = threading.Event()
        self._verificacao_id += 1
        identificador = self._verificacao_id
        cancelar = self.cancelar_atualizacao
        self.botao_atualizacao.configure(text="Cancelar consulta · timeout 5 s",
                                         command=self.cancelar_verificacao, state="normal")
        def trabalho():
            try:
                resultado = atualizacoes.consultar(cancelar=cancelar)
                self.eventos.put(("atualizacao", resultado, automatica, "", identificador))
            except atualizacoes.VerificacaoCancelada:
                return
            except Exception as erro:
                self.eventos.put(("atualizacao", None, automatica, type(erro).__name__, identificador))
        threading.Thread(target=trabalho, name="verificar-atualizacao", daemon=True).start()

    def cancelar_verificacao(self):
        if not self.verificacao_em_andamento:
            return
        self.cancelar_atualizacao.set()
        self._verificacao_id += 1
        self.verificacao_em_andamento = False
        self.botao_atualizacao.configure(text="Verificar versão", command=self.verificar_atualizacao)
        self.estado.configure(text="Consulta cancelada. A conexão pode terminar em até 5 segundos.")
        try:
            self.ultima_verificacao = atualizacoes.salvar_ultima_verificacao("cancelada")
        except OSError:
            pass

    def mostrar_atualizacao(self):
        if not self.atualizacao:
            self.verificar_atualizacao()
            return
        release = self.atualizacao
        notas = release["notas"].strip() or "Notas da versão disponíveis na página da release."
        escolha = messagebox.askyesnocancel(
            "Atualização disponível",
            f"Versão {release['versao']} {'(Beta)' if release.get('beta') else '(estável)'} disponível.\n\n"
            f"{notas[:1200]}\n\nSim: abrir a release oficial.\nNão: verificar um instalador já baixado.\nCancelar: fechar.",
            parent=self.raiz,
        )
        if escolha is True:
            webbrowser.open_new_tab(release["url"])
        elif escolha is False:
            arquivo = filedialog.askopenfilename(parent=self.raiz, title="Selecione o instalador baixado",
                                                  filetypes=[("Instalador do Assistente IA", "*.exe")])
            if arquivo:
                self.estado.configure(text="Verificando SHA-256 e assinatura do instalador…")
                def trabalho():
                    try:
                        atualizacoes.verificar_instalador(arquivo, release)
                        self.eventos.put(("instalador_verificado", True, ""))
                    except Exception as erro:
                        self.eventos.put(("instalador_verificado", False, str(erro) if isinstance(erro, ValueError)
                                         else "Não foi possível verificar o instalador."))
                threading.Thread(target=trabalho, name="verificar-instalador", daemon=True).start()

    def _mostrar_pesquisa(self):
        ativa = internet.habilitada()
        self.pesquisa.configure(text="Pesquisa: ligada" if ativa else "Pesquisa: desligada",
                                bg=COR_BOTAO, fg=COR_DESTAQUE if ativa else COR_SUAVE)

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

    def _renderizar_mensagem(self, widget, mensagem, links_permitidos):
        for tipo, linguagem, conteudo in renderizacao.fragmentos(mensagem.strip()):
            if tipo == "codigo":
                self._inserir_codigo(widget, linguagem, conteudo)
            else:
                self._inserir_prosa(widget, conteudo, links_permitidos)

    @staticmethod
    def _ajustar_altura_cartao(widget):
        try:
            linhas = widget.count("1.0", "end-1c", "displaylines")
            altura = max(1, linhas[0] if linhas else 1)
            if int(widget.cget("height")) != altura:
                widget.configure(height=altura)
        except tk.TclError:
            pass

    def _adicionar_cartao(self, historico, autor, mensagem, links_permitidos):
        lista, vazio = self._cartoes_historico[historico]
        vazio.grid_remove()
        usuario = autor.startswith("Você")
        cor_papel = COR_DESTAQUE if usuario else COR_ERRO if autor == "Erro" else COR_AUDIO
        nome = {"IA": "ASSISTENTE", "Você": "VOCÊ", "Você · não salvo": "VOCÊ · NÃO SALVO"}.get(autor, autor.upper())
        indice = len([filho for filho in lista.winfo_children() if isinstance(filho, ctk.CTkFrame)])
        cartao = ctk.CTkFrame(lista, fg_color="#1b2e4c" if usuario else "#192941",
                               border_color="#314c72", border_width=1, corner_radius=13)
        cartao.grid(row=indice + 1, column=0, sticky="ew", padx=10, pady=(5, 9))
        cartao.grid_columnconfigure(1, weight=1)
        avatar = ctk.CTkLabel(cartao, text="●" if usuario else "✦", width=38, height=38,
                              corner_radius=19, fg_color="#27577a" if usuario else "#35316c",
                              text_color=cor_papel, font=("Segoe UI", 19, "bold"))
        avatar.grid(row=0, column=0, sticky="nw", padx=(13, 11), pady=(10, 3))
        cabecalho = ctk.CTkFrame(cartao, fg_color="transparent")
        cabecalho.grid(row=0, column=1, sticky="ew", padx=(0, 18), pady=(8, 0))
        cabecalho.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(cabecalho, text=nome, anchor="w", text_color=cor_papel,
                     font=("Segoe UI", 10, "bold"), height=22).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(cabecalho, text=datetime.now().strftime("%H:%M"),
                     text_color=COR_SUAVE, font=("Segoe UI", 9), height=22).grid(row=0, column=1)
        corpo = tk.Text(cartao, wrap="word", width=1, height=1, relief="flat", bd=0,
                        bg="#1b2e4c" if usuario else "#192941", fg=COR_TEXTO,
                        insertbackground=COR_TEXTO, font=("Segoe UI", 11),
                        padx=0, pady=0, cursor="arrow", highlightthickness=0)
        corpo.grid(row=1, column=1, sticky="ew", padx=(0, 18), pady=(0, 9))
        self._configurar_historico(corpo)
        self._renderizar_mensagem(corpo, mensagem, links_permitidos)
        corpo.configure(state="disabled")
        corpo.bind("<Configure>", lambda _evento, texto=corpo: self._ajustar_altura_cartao(texto))
        corpo.after_idle(lambda texto=corpo: self._ajustar_altura_cartao(texto))
        lista.after(60, lambda vista=lista: vista._parent_canvas.yview_moveto(1.0)
                    if vista.winfo_exists() else None)

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
        nome = {"IA": "ASSISTENTE", "Você": "VOCÊ", "Você · não salvo": "VOCÊ · NÃO SALVO"}.get(autor, autor.upper())
        widget.insert("end", nome + "\n", papel)
        self._renderizar_mensagem(widget, mensagem, links_permitidos)
        widget.insert("end", "\n", "corpo")
        widget.configure(state="disabled")
        widget.see("end")
        self._adicionar_cartao(widget, autor, mensagem, links_permitidos)

    def _processar_eventos(self):
        if not self._janela_ativa():
            return
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
                    if not self.verificacao_iniciada and configuracao.carregar()["verificar_atualizacoes"]:
                        self.verificar_atualizacao(automatica=True)
                    if self.modo == "voz" and not self.microfone_mutado:
                        self.motor.ativar_microfone()
                        self._mostrar_microfone(True)
                elif tipo == "mensagem":
                    origem, autor, mensagem = dados
                    destino = self.historico_audio if origem == "audio" else self.historico_escrita
                    self._escrever(destino, autor, mensagem)
                elif tipo == "atualizacao":
                    release, automatica, erro, identificador = dados
                    if identificador != self._verificacao_id:
                        continue
                    self.verificacao_em_andamento = False
                    self.botao_atualizacao.configure(state="normal", command=self.verificar_atualizacao)
                    try:
                        estado = "disponivel" if release else "falha" if erro else "atualizada"
                        self.ultima_verificacao = atualizacoes.salvar_ultima_verificacao(estado, release)
                    except OSError:
                        pass
                    if release:
                        self.atualizacao = release
                        self.botao_atualizacao.configure(text="Nova versão " + release["versao"] +
                                                        (" · Beta" if release.get("beta") else ""),
                                                        command=self.mostrar_atualizacao, bg=COR_PESQUISA)
                        self.estado.configure(text="Nova versão disponível: " + release["versao"])
                    elif erro:
                        self.botao_atualizacao.configure(text="Verificar versão", command=self.verificar_atualizacao)
                        if not automatica:
                            self.estado.configure(text="Não foi possível consultar as atualizações (" + erro + ").", fg=COR_ERRO)
                    else:
                        self.atualizacao = None
                        self.botao_atualizacao.configure(text="Verificar versão", command=self.verificar_atualizacao)
                        if not automatica:
                            self.estado.configure(text="Você já usa a versão mais recente publicada.", fg=COR_SUAVE)
                elif tipo == "instalador_verificado":
                    valido, mensagem = dados
                    self.estado.configure(text="Instalador verificado." if valido else mensagem,
                                          fg=COR_SUAVE if valido else COR_ERRO)
                    if valido:
                        messagebox.showinfo("Instalador verificado", "SHA-256 e assinatura Authenticode válidos.", parent=self.raiz)
                    else:
                        messagebox.showerror("Falha na verificação", mensagem, parent=self.raiz)
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
                        lista, vazio = self._cartoes_historico[widget]
                        for filho in lista.winfo_children():
                            if filho is not vazio:
                                filho.destroy()
                        vazio.grid()
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
        self.cancelar_atualizacao.set()
        for identificador in self._agendamentos:
            try:
                self.raiz.after_cancel(identificador)
            except tk.TclError:
                pass
        self._agendamentos.clear()
        self.motor.fechar()
        # O CustomTkinter mantém verificações periódicas registradas no Tk.
        # Ao fechar a raiz, cancele-as para não executar callbacks já destruídos.
        try:
            for identificador in self.raiz.tk.call("after", "info"):
                self.raiz.tk.call("after", "cancel", identificador)
        except tk.TclError:
            pass
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
        assert (recursos / "assistente_ia.ico").is_file()
        assert (recursos / "assistente_ia.png").is_file()
        janela.fechar()
    else:
        JanelaAssistente().executar()


if __name__ == "__main__":
    executar()
