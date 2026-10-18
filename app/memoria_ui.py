"""Gerenciador visual das lembranças, conversas e resumos locais."""

import tkinter as tk
from tkinter import messagebox, ttk
import customtkinter as ctk

from . import icones, icone_app


FUNDO = "#0b1424"
CABECALHO = "#12223a"
CARTAO = "#172b47"
BORDA = "#2b4366"
TEXTO = "#f3f6ff"
SUAVE = "#a8bad2"
ACENTO = "#4bd8d0"


class JanelaMemoria:
    def __init__(self, raiz, solicitar):
        self.solicitar = solicitar
        self.dados = {}
        self.janela = tk.Toplevel(raiz)
        self.janela.title("Gerenciar memória")
        icone_app.aplicar(self.janela)
        self.janela.geometry("1060x740")
        self.janela.minsize(760, 560)
        self.janela.configure(bg=FUNDO, padx=18, pady=16)
        self.janela.transient(raiz)
        self.janela.grid_columnconfigure(0, weight=1)
        self.janela.grid_rowconfigure(2, weight=1)
        self.janela.bind("<Configure>", self._ajustar_layout)
        self.ativa = tk.BooleanVar(value=True)
        self.tipo_filtro = tk.StringVar(value="Todas")
        self.busca = tk.StringVar()
        self.tipo = tk.StringVar(value="fato")
        self.assunto = tk.StringVar(value="geral")
        self.projeto = tk.StringVar()
        self.importancia = tk.StringVar(value="4")
        self.incluir_backups = tk.BooleanVar(value=False)

        topo = ctk.CTkFrame(self.janela, fg_color="transparent")
        topo.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ctk.CTkLabel(topo, text="Memória", text_color=TEXTO,
                     font=("Segoe UI", 23, "bold")).pack(side="left")
        self._botao(topo, "Atualizar", lambda: self.solicitar("listar"), icone="refresh").pack(side="right")
        ctk.CTkSwitch(topo, text="Memória ativa", variable=self.ativa,
                      command=self._alternar_memoria, text_color=TEXTO,
                      progress_color=ACENTO, font=("Segoe UI", 12, "bold")).pack(side="right", padx=18)
        self.descricao = ctk.CTkLabel(
            self.janela, text="Gerencie lembranças, consulte o histórico e leia os resumos.",
            text_color=SUAVE, font=("Segoe UI", 11), anchor="w", justify="left")
        self.descricao.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        estilo = ttk.Style(self.janela)
        estilo.theme_use("clam")
        estilo.configure("Memoria.Treeview", background=CARTAO, fieldbackground=CARTAO,
                        foreground=TEXTO, rowheight=33, borderwidth=0,
                        font=("Segoe UI", 11))
        estilo.configure("Memoria.Treeview.Heading", background="#263f60", foreground=TEXTO,
                        font=("Segoe UI", 11, "bold"), padding=(8, 7), relief="flat")
        estilo.map("Memoria.Treeview", background=[("selected", "#28557a")],
                   foreground=[("selected", "#ffffff")])
        estilo.map("Memoria.Treeview.Heading", background=[("active", "#315079")])
        abas = ctk.CTkTabview(self.janela, fg_color=CABECALHO, corner_radius=16,
                              border_width=1, border_color=BORDA,
                              segmented_button_fg_color="#1c3150",
                              segmented_button_selected_color="#28557a",
                              segmented_button_selected_hover_color="#34688e",
                              segmented_button_unselected_color="#1c3150",
                              segmented_button_unselected_hover_color="#304d70",
                              text_color=TEXTO, anchor="w")
        abas.grid(row=2, column=0, sticky="nsew")
        self.abas = abas
        lembrancas, editor, historico, resumos = (abas.add(nome) for nome in
                                                 ("Lembranças", "Editar", "Histórico", "Resumos"))
        for quadro in (lembrancas, editor, historico, resumos):
            quadro.grid_columnconfigure(0, weight=1)
        self._montar_lembrancas(lembrancas)
        self._montar_editor(editor)
        self._montar_historico(historico)
        self._montar_resumos(resumos)
        self.abas.set("Lembranças")

        rodape = tk.Frame(self.janela, bg=FUNDO)
        rodape.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.estado = ctk.CTkLabel(rodape, text="Carregando memória…", text_color=SUAVE,
                                  font=("Segoe UI", 11), anchor="w")
        self.estado.pack(fill="x", pady=(0, 6))
        acoes_rodape = tk.Frame(rodape, bg=FUNDO)
        acoes_rodape.pack(fill="x")
        self._botao(acoes_rodape, "Apagar toda a memória", self._apagar_tudo,
                    perigo=True, icone="delete").pack(side="right")
        ctk.CTkCheckBox(acoes_rodape, text="Incluir backups ao apagar",
                        variable=self.incluir_backups, text_color=SUAVE,
                        border_color=BORDA, fg_color="#70394d",
                        font=("Segoe UI", 11)).pack(side="right", padx=(0, 14))
        self.solicitar("listar")

    @staticmethod
    def _botao(pai, texto, comando, perigo=False, icone=None, destaque=False):
        fundo = "#70394d" if perigo else ACENTO if destaque else "#1c3150"
        return ctk.CTkButton(
            pai, text=texto, command=comando, cursor="hand2", height=40,
            corner_radius=10, fg_color=fundo,
            hover_color="#8e4962" if perigo else "#70e6df" if destaque else "#304d70",
            text_color=FUNDO if destaque else TEXTO,
            text_color_disabled="#7890aa", font=("Segoe UI", 11, "bold"),
            image=icones.obter(icone, "#0b1424" if destaque else "#ffb3c3" if perigo else ACENTO)
            if icone else None,
        )

    @staticmethod
    def _arvore(pai, colunas, larguras, altura=8):
        quadro = tk.Frame(pai, bg=CARTAO)
        quadro.grid_rowconfigure(0, weight=1)
        quadro.grid_columnconfigure(0, weight=1)
        arvore = ttk.Treeview(quadro, columns=colunas, show="headings", height=altura,
                              style="Memoria.Treeview", selectmode="browse")
        for coluna, largura in zip(colunas, larguras):
            arvore.heading(coluna, text=coluna)
            arvore.column(coluna, width=largura, minwidth=50, stretch=coluna == colunas[-1])
        barra = ctk.CTkScrollbar(quadro, orientation="vertical", command=arvore.yview,
                                 fg_color=CABECALHO, button_color="#41638c",
                                 button_hover_color=ACENTO)
        horizontal = ctk.CTkScrollbar(quadro, orientation="horizontal", command=arvore.xview,
                                      fg_color=CABECALHO, button_color="#41638c",
                                      button_hover_color=ACENTO)
        arvore.configure(yscrollcommand=barra.set, xscrollcommand=horizontal.set)
        arvore.grid(row=0, column=0, sticky="nsew")
        barra.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        return quadro, arvore

    def _ajustar_layout(self, evento):
        if evento.widget is self.janela:
            largura = max(420, evento.width - 90)
            if hasattr(self, "descricao"):
                self.descricao.configure(wraplength=largura)
            if hasattr(self, "explicacao"):
                self.explicacao.configure(wraplength=largura)

    def _montar_lembrancas(self, pai):
        pai.grid_rowconfigure(1, weight=1)
        filtros = tk.Frame(pai, bg=CABECALHO)
        filtros.grid(row=0, column=0, sticky="ew", padx=10, pady=(12, 8))
        filtros.grid_columnconfigure(2, weight=1)
        ctk.CTkOptionMenu(filtros, variable=self.tipo_filtro,
                          values=["Todas", "Fatos", "Preferências"], width=160,
                          height=38, fg_color=CARTAO, button_color="#35547a",
                          text_color=TEXTO, font=("Segoe UI", 11)).grid(row=0, column=0, padx=(0, 10))
        self.tipo_filtro.trace_add("write", lambda *_: self._preencher_lembrancas())
        ctk.CTkLabel(filtros, text="Buscar", text_color=SUAVE,
                     font=("Segoe UI", 11)).grid(row=0, column=1, padx=(0, 10))
        busca = ctk.CTkEntry(filtros, textvariable=self.busca,
                             placeholder_text="Buscar lembrança, assunto ou projeto",
                             height=38, fg_color=CARTAO, border_color=BORDA,
                             text_color=TEXTO, font=("Segoe UI", 11))
        busca.grid(row=0, column=2, sticky="ew")
        self.busca.trace_add("write", lambda *_: self._preencher_lembrancas())
        quadro, self.arvore_lembrancas = self._arvore(
            pai, ("ID", "Tipo", "Assunto", "Projeto", "Importância", "Lembrança"),
            (55, 105, 110, 110, 115, 410))
        quadro.grid(row=1, column=0, sticky="nsew", padx=10)
        self.arvore_lembrancas.bind("<<TreeviewSelect>>", self._selecionar_lembranca)
        botoes = tk.Frame(pai, bg=CABECALHO)
        botoes.grid(row=2, column=0, sticky="ew", padx=10, pady=(10, 4))
        self._botao(botoes, "Nova lembrança", self._nova,
                    icone="add", destaque=True).pack(side="left")
        self.botao_editar = self._botao(botoes, "Editar selecionada", self._editar_selecionada,
                                       icone="edit")
        self.botao_editar.pack(side="left", padx=(8, 0))
        self.botao_excluir = self._botao(botoes, "Excluir selecionada", self._excluir,
                                        perigo=True, icone="delete")
        self.botao_excluir.pack(side="right")
        self.botao_editar.configure(state="disabled")
        self.botao_excluir.configure(state="disabled")
        self.explicacao = ctk.CTkLabel(
            pai, text="Selecione uma lembrança para ver a origem e o uso.",
            text_color=SUAVE, font=("Segoe UI", 11), justify="left",
            anchor="w", wraplength=850, height=45)
        self.explicacao.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 7))

    def _montar_editor(self, pai):
        pai.grid_rowconfigure(1, weight=1)
        self.titulo_editor = ctk.CTkLabel(pai, text="Nova lembrança",
                                          text_color=TEXTO, font=("Segoe UI", 18, "bold"),
                                          anchor="w")
        self.titulo_editor.grid(row=0, column=0, sticky="ew", padx=18, pady=(13, 4))
        formulario = tk.Frame(pai, bg=CABECALHO)
        formulario.grid(row=1, column=0, sticky="nsew", padx=18)
        formulario.grid_columnconfigure(0, weight=1, uniform="formulario")
        formulario.grid_columnconfigure(1, weight=1, uniform="formulario")
        formulario.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(formulario, text="O que devo lembrar?", text_color=SUAVE,
                     font=("Segoe UI", 11), anchor="w").grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.texto_lembranca = ctk.CTkTextbox(formulario, height=110, wrap="word",
                                              fg_color=CARTAO, border_color=BORDA,
                                              border_width=1, text_color=TEXTO,
                                              font=("Segoe UI", 12))
        self.texto_lembranca.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
        campos = tk.Frame(formulario, bg=CABECALHO)
        campos.grid(row=0, column=1, rowspan=2, sticky="nsew")
        campos.grid_columnconfigure(0, weight=1)
        campos.grid_columnconfigure(1, weight=1)
        for coluna, linha, rotulo, variavel in (
            (0, 0, "Assunto", self.assunto),
            (1, 0, "Projeto (opcional)", self.projeto),
        ):
            ctk.CTkLabel(campos, text=rotulo, text_color=SUAVE,
                         font=("Segoe UI", 11), anchor="w").grid(
                row=linha, column=coluna, sticky="ew", padx=(0, 7) if coluna == 0 else (7, 0))
            ctk.CTkEntry(campos, textvariable=variavel, height=38,
                         fg_color=CARTAO, border_color=BORDA, text_color=TEXTO,
                         font=("Segoe UI", 11)).grid(
                row=linha + 1, column=coluna, sticky="ew", padx=(0, 7) if coluna == 0 else (7, 0),
                pady=(3, 8))
        for coluna, rotulo, variavel, valores in (
            (0, "Tipo", self.tipo, ["fato", "preferencia"]),
            (1, "Importância", self.importancia, ["1", "2", "3", "4", "5"]),
        ):
            ctk.CTkLabel(campos, text=rotulo, text_color=SUAVE,
                         font=("Segoe UI", 11), anchor="w").grid(
                row=2, column=coluna, sticky="ew", padx=(0, 7) if coluna == 0 else (7, 0))
            ctk.CTkOptionMenu(campos, variable=variavel, values=valores,
                              height=38, fg_color=CARTAO, button_color="#35547a",
                              text_color=TEXTO, font=("Segoe UI", 11)).grid(
                row=3, column=coluna, sticky="ew", padx=(0, 7) if coluna == 0 else (7, 0),
                pady=(3, 8))
        ctk.CTkLabel(formulario,
                     text="Fatos e preferências salvos podem aparecer nas próximas respostas.",
                     text_color=SUAVE, font=("Segoe UI", 10), anchor="w",
                     wraplength=400, justify="left").grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(7, 0))
        acoes = tk.Frame(pai, bg=CABECALHO)
        acoes.grid(row=2, column=0, sticky="e", padx=18, pady=(7, 10))
        self._botao(acoes, "Voltar à lista", lambda: self.abas.set("Lembranças"),
                    icone="close").pack(side="left", padx=(0, 9))
        self._botao(acoes, "Salvar lembrança", self._salvar,
                    icone="save", destaque=True).pack(side="left")

    def _montar_historico(self, pai):
        pai.grid_rowconfigure(1, weight=1)
        pai.grid_columnconfigure(0, weight=1, uniform="painel_historico")
        pai.grid_columnconfigure(1, weight=1, uniform="painel_historico")
        ctk.CTkLabel(pai, text="Mensagens recentes", text_color=TEXTO,
                     font=("Segoe UI", 16, "bold"), anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(10, 7))
        quadro, self.arvore_historico = self._arvore(
            pai, ("ID", "Origem", "Prévia", "Data", "Assunto", "Projeto"),
            (50, 70, 350, 140, 105, 100), altura=4)
        quadro.grid(row=1, column=0, sticky="nsew", padx=(10, 5))
        self.arvore_historico.bind("<<TreeviewSelect>>", self._selecionar_historico)
        leitura = tk.Frame(pai, bg=CABECALHO)
        leitura.grid(row=1, column=1, sticky="nsew", padx=(5, 10))
        leitura.grid_columnconfigure(0, weight=1)
        leitura.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(leitura, text="Mensagem completa", text_color=SUAVE,
                     font=("Segoe UI", 11), anchor="w").grid(
            row=0, column=0, sticky="ew", pady=(0, 5))
        self.previa_historico = ctk.CTkTextbox(leitura, height=90, wrap="word", state="disabled",
                                               fg_color=CARTAO, border_color=BORDA,
                                               border_width=1, text_color=TEXTO,
                                               font=("Segoe UI", 11))
        self.previa_historico.grid(row=1, column=0, sticky="nsew")
        self.botao_nao_usar = self._botao(pai, "Não usar esta troca na memória",
                                          self._nao_usar, icone="close")
        self.botao_nao_usar.grid(row=2, column=0, columnspan=2, sticky="e", padx=10, pady=(8, 10))
        self.botao_nao_usar.configure(state="disabled")

    def _montar_resumos(self, pai):
        pai.grid_rowconfigure(1, weight=1)
        pai.grid_columnconfigure(0, weight=1, uniform="painel_resumos")
        pai.grid_columnconfigure(1, weight=1, uniform="painel_resumos")
        ctk.CTkLabel(pai, text="Resumos automáticos", text_color=TEXTO,
                     font=("Segoe UI", 16, "bold"), anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(10, 7))
        quadro, self.arvore_resumos = self._arvore(
            pai, ("ID", "Prévia", "Assunto", "Projeto", "Mensagens"),
            (50, 350, 110, 110, 110), altura=4)
        quadro.grid(row=1, column=0, sticky="nsew", padx=(10, 5), pady=(0, 10))
        self.arvore_resumos.bind("<<TreeviewSelect>>", self._selecionar_resumo)
        leitura = tk.Frame(pai, bg=CABECALHO)
        leitura.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=(0, 10))
        leitura.grid_columnconfigure(0, weight=1)
        leitura.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(leitura, text="Resumo completo", text_color=SUAVE,
                     font=("Segoe UI", 11), anchor="w").grid(
            row=0, column=0, sticky="ew", pady=(0, 5))
        self.previa_resumo = ctk.CTkTextbox(leitura, height=90, wrap="word", state="disabled",
                                            fg_color=CARTAO, border_color=BORDA,
                                            border_width=1, text_color=TEXTO,
                                            font=("Segoe UI", 11))
        self.previa_resumo.grid(row=1, column=0, sticky="nsew")

    @staticmethod
    def _prever(widget, texto):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", texto)
        widget.configure(state="disabled")

    def mostrar_dados(self, dados):
        if not self.janela.winfo_exists():
            return
        historico_atual = self.arvore_historico.selection()
        resumo_atual = self.arvore_resumos.selection()
        self.dados = dados
        self.ativa.set(dados["ativa"])
        self._preencher_lembrancas()
        for item in self.arvore_historico.get_children():
            self.arvore_historico.delete(item)
        for registro in dados["historico"]:
            self.arvore_historico.insert("", "end", iid=str(registro["id"]), values=(
                registro["id"], "Você" if registro["papel"] == "user" else "IA",
                registro["conteudo"].replace("\n", " ")[:100], registro["data"],
                registro["assunto"], registro["projeto"] or "—"))
        for item in self.arvore_resumos.get_children():
            self.arvore_resumos.delete(item)
        for registro in dados["resumos"]:
            self.arvore_resumos.insert("", "end", iid=str(registro["id"]), values=(
                registro["id"], registro["conteudo"].replace("\n", " ")[:100],
                registro["assunto"], registro["projeto"] or "—",
                f"{registro['inicio_id']}–{registro['fim_id']}"))
        if historico_atual and self.arvore_historico.exists(historico_atual[0]):
            self.arvore_historico.selection_set(historico_atual[0])
            self._selecionar_historico()
        else:
            self._prever(self.previa_historico, "Selecione uma mensagem para ler o texto completo.")
            self.botao_nao_usar.configure(state="disabled")
        if resumo_atual and self.arvore_resumos.exists(resumo_atual[0]):
            self.arvore_resumos.selection_set(resumo_atual[0])
            self._selecionar_resumo()
        else:
            self._prever(self.previa_resumo, "Selecione um resumo para ler o texto completo.")
        self.estado.configure(text=(f"{dados['total_lembrancas']} lembranças · {dados['total_historico']} mensagens · "
                                     f"{len(dados['resumos'])} resumos exibidos"), text_color=SUAVE)

    def mostrar_erro(self, mensagem):
        self.estado.configure(text=mensagem, text_color="#f5a0a0")
        messagebox.showerror("Memória", mensagem, parent=self.janela)

    def _preencher_lembrancas(self):
        if not self.dados:
            return
        atual = self.arvore_lembrancas.selection()
        selecionado = atual[0] if atual else None
        for item in self.arvore_lembrancas.get_children():
            self.arvore_lembrancas.delete(item)
        filtro = self.tipo_filtro.get()
        busca = self.busca.get().casefold().strip()
        for registro in self.dados["lembrancas"]:
            if ((filtro == "Fatos" and registro["tipo"] != "fato") or
                    (filtro == "Preferências" and registro["tipo"] != "preferencia")):
                continue
            if busca and busca not in (registro["conteudo"] + " " + registro["assunto"] + " " + registro["projeto"]).casefold():
                continue
            mid = str(registro["id"])
            self.arvore_lembrancas.insert("", "end", iid=mid, values=(
                mid, "Preferência" if registro["tipo"] == "preferencia" else "Fato",
                registro["assunto"], registro["projeto"] or "—", registro["importancia"],
                registro["conteudo"].replace("\n", " ")[:110]))
        if selecionado and self.arvore_lembrancas.exists(selecionado):
            self.arvore_lembrancas.selection_set(selecionado)
            self._selecionar_lembranca()
        else:
            self.explicacao.configure(text="Selecione uma lembrança para ver a origem e o uso.")
            self.botao_editar.configure(state="disabled")
            self.botao_excluir.configure(state="disabled")

    def _selecionar_lembranca(self, _evento=None):
        selecao = self.arvore_lembrancas.selection()
        if not selecao:
            return
        registro = next((r for r in self.dados.get("lembrancas", []) if r["id"] == int(selecao[0])), None)
        if not registro:
            return
        self.texto_lembranca.delete("1.0", "end")
        self.texto_lembranca.insert("1.0", registro["conteudo"])
        for variavel, chave in ((self.tipo, "tipo"), (self.assunto, "assunto"),
                                (self.projeto, "projeto"), (self.importancia, "importancia")):
            variavel.set(str(registro[chave]))
        self.titulo_editor.configure(text=f"Editar lembrança #{registro['id']}")
        self.botao_editar.configure(state="normal")
        self.botao_excluir.configure(state="normal")
        self.explicacao.configure(text=(
            f"Origem: {registro['fontes']} mensagem(ns) associada(s). "
            f"Usada em {registro['usos']} resposta(s) registrada(s). "
            "A seleção considera assunto, projeto, termos da pergunta, similaridade e importância; "
            "isso não garante que a lembrança será usada em toda resposta."))

    def _selecionar_historico(self, _evento=None):
        selecao = self.arvore_historico.selection()
        if selecao:
            registro = next((r for r in self.dados.get("historico", []) if r["id"] == int(selecao[0])), None)
            if registro:
                aviso = "[Não usada na memória]\n\n" if registro["ignorar_memoria"] else ""
                self._prever(self.previa_historico, aviso + registro["conteudo"])
                self.botao_nao_usar.configure(state="disabled" if registro["ignorar_memoria"] else "normal")

    def _selecionar_resumo(self, _evento=None):
        selecao = self.arvore_resumos.selection()
        if selecao:
            registro = next((r for r in self.dados.get("resumos", []) if r["id"] == int(selecao[0])), None)
            if registro:
                self._prever(self.previa_resumo, registro["conteudo"])

    def _nova(self):
        self.arvore_lembrancas.selection_remove(*self.arvore_lembrancas.selection())
        self.texto_lembranca.delete("1.0", "end")
        self.tipo.set("fato")
        self.assunto.set(self.dados.get("contexto", ("geral", ""))[0])
        self.projeto.set(self.dados.get("contexto", ("geral", ""))[1])
        self.importancia.set("4")
        self.explicacao.configure(text="Nova lembrança. Ela poderá ser recuperada em futuras respostas.")
        self.titulo_editor.configure(text="Nova lembrança")
        self.botao_editar.configure(state="disabled")
        self.botao_excluir.configure(state="disabled")
        self.abas.set("Editar")
        self.texto_lembranca.focus_set()

    def _editar_selecionada(self):
        if self.arvore_lembrancas.selection():
            self.abas.set("Editar")
            self.texto_lembranca.focus_set()

    def _salvar(self):
        try:
            importancia = int(self.importancia.get())
        except ValueError:
            self.mostrar_erro("A importância deve ser um número de 1 a 5.")
            return
        if not 1 <= importancia <= 5:
            self.mostrar_erro("A importância deve ser um número de 1 a 5.")
            return
        texto = self.texto_lembranca.get("1.0", "end-1c").strip()
        if not texto:
            self.mostrar_erro("Escreva a lembrança antes de salvar.")
            return
        dados = {"texto": texto,
                 "tipo": self.tipo.get(), "assunto": self.assunto.get(),
                 "projeto": self.projeto.get(), "importancia": importancia}
        selecao = self.arvore_lembrancas.selection()
        if selecao:
            dados["id"] = int(selecao[0])
        self.solicitar("editar" if selecao else "guardar", **dados)
        self.estado.configure(text="Salvando lembrança…", text_color=SUAVE)
        self.abas.set("Lembranças")

    def _excluir(self):
        selecao = self.arvore_lembrancas.selection()
        if selecao and messagebox.askyesno("Excluir lembrança", "Excluir esta lembrança da recuperação futura? O histórico e backups podem manter o texto original.", parent=self.janela):
            self.solicitar("excluir", id=int(selecao[0]))

    def _nao_usar(self):
        selecao = self.arvore_historico.selection()
        if selecao and messagebox.askyesno("Não usar na memória", "Esta troca continuará no histórico, mas não será usada para memórias e resumos futuros. Continuar?", parent=self.janela):
            self.solicitar("nao_usar", id=int(selecao[0]))

    def _alternar_memoria(self):
        self.solicitar("habilitar", ativa=self.ativa.get())

    def _apagar_tudo(self):
        incluir = self.incluir_backups.get()
        aviso = ("Apagar definitivamente conversas, lembranças, vetores e resumos do banco ativo? "
                 + ("Os backups locais também serão removidos." if incluir else
                    "Os backups locais permanecerão e poderão restaurar os dados."))
        if messagebox.askyesno("Apagar toda a memória", aviso, icon="warning", parent=self.janela):
            self.solicitar("apagar_tudo", incluir_backups=incluir)
