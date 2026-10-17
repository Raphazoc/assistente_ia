"""Gerenciador visual das lembranças, conversas e resumos locais."""

import tkinter as tk
from tkinter import messagebox, ttk


FUNDO = "#172530"
CARTAO = "#203341"
TEXTO = "#edf5f7"
SUAVE = "#a8bec9"
ACENTO = "#58cfc3"


class JanelaMemoria:
    def __init__(self, raiz, solicitar):
        self.solicitar = solicitar
        self.dados = {}
        self.janela = tk.Toplevel(raiz)
        self.janela.title("Gerenciar memória")
        self.janela.geometry("980x690")
        self.janela.minsize(730, 540)
        self.janela.configure(bg=FUNDO, padx=16, pady=14)
        self.janela.transient(raiz)
        self.janela.grid_columnconfigure(0, weight=1)
        self.janela.grid_rowconfigure(2, weight=1)
        self.ativa = tk.BooleanVar(value=True)
        self.tipo_filtro = tk.StringVar(value="Todas")
        self.busca = tk.StringVar()
        self.tipo = tk.StringVar(value="fato")
        self.assunto = tk.StringVar(value="geral")
        self.projeto = tk.StringVar()
        self.importancia = tk.StringVar(value="4")
        self.incluir_backups = tk.BooleanVar(value=False)

        topo = tk.Frame(self.janela, bg=FUNDO)
        topo.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        tk.Label(topo, text="Memória", bg=FUNDO, fg=TEXTO,
                 font=("Segoe UI", 18, "bold")).pack(side="left")
        self._botao(topo, "Atualizar", lambda: self.solicitar("listar")).pack(side="right")
        tk.Checkbutton(topo, text="Memória ativa", variable=self.ativa,
                       command=self._alternar_memoria, bg=FUNDO, fg=ACENTO,
                       selectcolor=CARTAO, activebackground=FUNDO,
                       activeforeground=ACENTO, font=("Segoe UI", 10, "bold")).pack(side="right", padx=18)
        tk.Label(self.janela, text="Lembranças, histórico e resumos são dados diferentes. Desligar a memória não apaga o histórico.",
                 bg=FUNDO, fg=SUAVE, font=("Segoe UI", 10), anchor="w").grid(row=1, column=0, sticky="ew", pady=(0, 10))

        estilo = ttk.Style(self.janela)
        estilo.configure("Memoria.Treeview", background=CARTAO, fieldbackground=CARTAO,
                        foreground=TEXTO, rowheight=27, font=("Segoe UI", 10))
        estilo.configure("Memoria.Treeview.Heading", background="#365062", foreground=TEXTO,
                        font=("Segoe UI", 10, "bold"))
        estilo.map("Memoria.Treeview", background=[("selected", "#42667b")], foreground=[("selected", "#ffffff")])
        estilo.configure("Memoria.TNotebook", background=FUNDO, borderwidth=0)
        estilo.configure("Memoria.TNotebook.Tab", background="#304858", foreground=TEXTO, padding=(13, 8))
        estilo.map("Memoria.TNotebook.Tab", background=[("selected", "#49667a")], foreground=[("selected", "#ffffff")])
        abas = ttk.Notebook(self.janela, style="Memoria.TNotebook")
        abas.grid(row=2, column=0, sticky="nsew")
        self.abas = abas
        lembrancas, historico, resumos = (tk.Frame(abas, bg=FUNDO, padx=8, pady=10) for _ in range(3))
        for quadro, nome in ((lembrancas, "Lembranças"), (historico, "Histórico"), (resumos, "Resumos")):
            abas.add(quadro, text=nome)
            quadro.grid_columnconfigure(0, weight=1)
        self._montar_lembrancas(lembrancas)
        self._montar_historico(historico)
        self._montar_resumos(resumos)

        rodape = tk.Frame(self.janela, bg=FUNDO)
        rodape.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.estado = tk.Label(rodape, text="Carregando memória…", bg=FUNDO, fg=SUAVE,
                              font=("Segoe UI", 9), anchor="w")
        self.estado.pack(side="left", fill="x", expand=True)
        self._botao(rodape, "Apagar toda a memória", self._apagar_tudo, perigo=True).pack(side="right")
        tk.Checkbutton(rodape, text="Incluir backups", variable=self.incluir_backups,
                       bg=FUNDO, fg=SUAVE, selectcolor=CARTAO, activebackground=FUNDO,
                       activeforeground=TEXTO).pack(side="right", padx=(0, 10))
        self.solicitar("listar")

    @staticmethod
    def _botao(pai, texto, comando, perigo=False):
        return tk.Button(pai, text=texto, command=comando, relief="flat", cursor="hand2",
                         bg="#87505a" if perigo else "#315364", fg=TEXTO,
                         activebackground="#9c5c65" if perigo else "#42677a",
                         activeforeground=TEXTO, font=("Segoe UI", 9, "bold"), padx=12, pady=6)

    @staticmethod
    def _arvore(pai, colunas, larguras, altura=8):
        quadro = tk.Frame(pai, bg=FUNDO)
        arvore = ttk.Treeview(quadro, columns=colunas, show="headings", height=altura,
                              style="Memoria.Treeview", selectmode="browse")
        for coluna, largura in zip(colunas, larguras):
            arvore.heading(coluna, text=coluna)
            arvore.column(coluna, width=largura, minwidth=50, stretch=coluna == colunas[-1])
        barra = ttk.Scrollbar(quadro, orient="vertical", command=arvore.yview)
        arvore.configure(yscrollcommand=barra.set)
        arvore.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        return quadro, arvore

    def _montar_lembrancas(self, pai):
        pai.grid_rowconfigure(1, weight=2)
        pai.grid_rowconfigure(3, weight=1)
        filtros = tk.Frame(pai, bg=FUNDO)
        filtros.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        tk.Label(filtros, text="Filtrar", bg=FUNDO, fg=SUAVE).pack(side="left")
        ttk.Combobox(filtros, textvariable=self.tipo_filtro, values=("Todas", "Fatos", "Preferências"),
                     state="readonly", width=15).pack(side="left", padx=8)
        self.tipo_filtro.trace_add("write", lambda *_: self._preencher_lembrancas())
        busca = tk.Entry(filtros, textvariable=self.busca, bg=CARTAO, fg=TEXTO,
                         insertbackground=TEXTO, relief="flat")
        busca.pack(side="left", fill="x", expand=True, padx=(8, 0), ipady=5)
        self.busca.trace_add("write", lambda *_: self._preencher_lembrancas())
        quadro, self.arvore_lembrancas = self._arvore(
            pai, ("ID", "Tipo", "Assunto", "Projeto", "Importância", "Lembrança"),
            (55, 105, 110, 110, 90, 410))
        quadro.grid(row=1, column=0, sticky="nsew")
        self.arvore_lembrancas.bind("<<TreeviewSelect>>", self._selecionar_lembranca)
        self.explicacao = tk.Label(pai, text="Selecione uma lembrança para ver a origem e o uso.",
                                  bg=FUNDO, fg=SUAVE, justify="left", anchor="w", wraplength=900)
        self.explicacao.grid(row=2, column=0, sticky="ew", pady=(8, 5))
        formulario = tk.Frame(pai, bg=FUNDO)
        formulario.grid(row=3, column=0, sticky="nsew")
        formulario.grid_columnconfigure(0, weight=1)
        self.texto_lembranca = tk.Text(formulario, height=3, wrap="word", bg=CARTAO, fg=TEXTO,
                                       insertbackground=TEXTO, relief="flat", padx=8, pady=6,
                                       font=("Segoe UI", 10))
        self.texto_lembranca.grid(row=0, column=0, columnspan=6, sticky="nsew")
        for coluna, rotulo, variavel in ((0, "Tipo", self.tipo), (2, "Assunto", self.assunto),
                                         (4, "Projeto", self.projeto)):
            tk.Label(formulario, text=rotulo, bg=FUNDO, fg=SUAVE).grid(row=1, column=coluna, sticky="w", pady=7)
            if rotulo == "Tipo":
                ttk.Combobox(formulario, textvariable=variavel, values=("fato", "preferencia"),
                             state="readonly", width=12).grid(row=1, column=coluna + 1, sticky="ew", padx=(5, 12))
            else:
                tk.Entry(formulario, textvariable=variavel, bg=CARTAO, fg=TEXTO,
                         insertbackground=TEXTO, relief="flat", width=16).grid(
                             row=1, column=coluna + 1, sticky="ew", padx=(5, 12), ipady=4)
        tk.Label(formulario, text="Importância (1–5)", bg=FUNDO, fg=SUAVE).grid(row=2, column=0, sticky="w")
        tk.Spinbox(formulario, from_=1, to=5, textvariable=self.importancia, width=5,
                   bg=CARTAO, fg=TEXTO, buttonbackground="#365062").grid(row=2, column=1, sticky="w")
        botoes = tk.Frame(formulario, bg=FUNDO)
        botoes.grid(row=3, column=0, columnspan=6, sticky="e", pady=(8, 0))
        self._botao(botoes, "Nova", self._nova).pack(side="left", padx=4)
        self._botao(botoes, "Salvar", self._salvar).pack(side="left", padx=4)
        self._botao(botoes, "Excluir selecionada", self._excluir, perigo=True).pack(side="left", padx=4)

    def _montar_historico(self, pai):
        pai.grid_rowconfigure(0, weight=2)
        pai.grid_rowconfigure(1, weight=1)
        quadro, self.arvore_historico = self._arvore(
            pai, ("ID", "Data", "Origem", "Assunto", "Projeto", "Prévia"),
            (55, 140, 75, 105, 100, 400))
        quadro.grid(row=0, column=0, sticky="nsew")
        self.arvore_historico.bind("<<TreeviewSelect>>", self._selecionar_historico)
        self.previa_historico = tk.Text(pai, height=6, wrap="word", state="disabled",
                                        bg=CARTAO, fg=TEXTO, relief="flat", padx=9, pady=8)
        self.previa_historico.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self._botao(pai, "Não usar esta troca na memória", self._nao_usar).grid(row=2, column=0, sticky="e", pady=(8, 0))

    def _montar_resumos(self, pai):
        pai.grid_rowconfigure(0, weight=2)
        pai.grid_rowconfigure(1, weight=1)
        quadro, self.arvore_resumos = self._arvore(
            pai, ("ID", "Assunto", "Projeto", "Mensagens", "Prévia"),
            (55, 110, 110, 110, 450))
        quadro.grid(row=0, column=0, sticky="nsew")
        self.arvore_resumos.bind("<<TreeviewSelect>>", self._selecionar_resumo)
        self.previa_resumo = tk.Text(pai, height=8, wrap="word", state="disabled",
                                     bg=CARTAO, fg=TEXTO, relief="flat", padx=9, pady=8)
        self.previa_resumo.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

    @staticmethod
    def _prever(widget, texto):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", texto)
        widget.configure(state="disabled")

    def mostrar_dados(self, dados):
        if not self.janela.winfo_exists():
            return
        self.dados = dados
        self.ativa.set(dados["ativa"])
        self._preencher_lembrancas()
        for item in self.arvore_historico.get_children():
            self.arvore_historico.delete(item)
        for registro in dados["historico"]:
            self.arvore_historico.insert("", "end", iid=str(registro["id"]), values=(
                registro["id"], registro["data"], "Você" if registro["papel"] == "user" else "IA",
                registro["assunto"], registro["projeto"] or "—", registro["conteudo"].replace("\n", " ")[:100]))
        for item in self.arvore_resumos.get_children():
            self.arvore_resumos.delete(item)
        for registro in dados["resumos"]:
            self.arvore_resumos.insert("", "end", iid=str(registro["id"]), values=(
                registro["id"], registro["assunto"], registro["projeto"] or "—",
                f"{registro['inicio_id']}–{registro['fim_id']}", registro["conteudo"].replace("\n", " ")[:100]))
        self.estado.configure(text=(f"{dados['total_lembrancas']} lembranças · {dados['total_historico']} mensagens · "
                                     f"{len(dados['resumos'])} resumos exibidos"), fg=SUAVE)

    def mostrar_erro(self, mensagem):
        self.estado.configure(text=mensagem, fg="#f5a0a0")
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
        self.texto_lembranca.focus_set()

    def _salvar(self):
        try:
            importancia = int(self.importancia.get())
        except ValueError:
            self.mostrar_erro("A importância deve ser um número de 1 a 5.")
            return
        dados = {"texto": self.texto_lembranca.get("1.0", "end-1c").strip(),
                 "tipo": self.tipo.get(), "assunto": self.assunto.get(),
                 "projeto": self.projeto.get(), "importancia": importancia}
        selecao = self.arvore_lembrancas.selection()
        if selecao:
            dados["id"] = int(selecao[0])
        self.solicitar("editar" if selecao else "guardar", **dados)

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
