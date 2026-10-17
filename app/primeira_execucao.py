"""Assistente de instalação e configurações locais do aplicativo."""

import os
import threading
import queue
import tkinter as tk
from tkinter import messagebox, ttk

from . import configuracao, diagnostico, diagnostico_inicial, internet, main, servicos


FUNDO = "#1b2935"
TEXTO = "#ecf2f5"
SUAVE = "#a8bec9"
DESTAQUE = "#56c7ba"


class AssistenteConfiguracao:
    def __init__(self, raiz, ao_salvar, primeira=True, erro_configuracao=""):
        self.ao_salvar = ao_salvar
        self.primeira = primeira
        self.resultado = None
        self.eventos = queue.Queue()
        self._agendamentos = set()
        self._fechado = False
        self.janela = tk.Toplevel(raiz)
        self.janela.title("Primeira execução" if primeira else "Configurações")
        self.janela.geometry("760x620")
        self.janela.minsize(630, 560)
        self.janela.configure(bg=FUNDO, padx=20, pady=18)
        self.janela.transient(raiz)
        self.janela.bind("<Destroy>", self._ao_destruir)
        self.janela.grid_columnconfigure(0, weight=1)
        self.janela.grid_rowconfigure(2, weight=1)
        try:
            dados = configuracao.carregar()
        except ValueError:
            dados = configuracao.PADRAO.copy()
        self.modelo = tk.StringVar(value=dados["modelo"])
        self.embedding = tk.StringVar(value=dados["modelo_memoria"])
        self.idioma = tk.StringVar(value=dados["idioma"])
        self.historico = tk.StringVar(value=str(dados["limite_historico"]))
        self.pesquisa = tk.BooleanVar(value=internet.habilitada())
        provedores = servicos.carregar()
        self.buscador = tk.StringVar(value=provedores["buscador"])
        self.voz = tk.StringVar(value=provedores["voz"])
        self.voice_id = tk.StringVar(value=provedores["voice_id"])
        self.remover_brave = tk.BooleanVar(value=False)
        self.remover_elevenlabs = tk.BooleanVar(value=False)

        self._rotulo(self.janela, "Configure sua assistente" if primeira else "Configurações", 18, TEXTO).grid(row=0, column=0, sticky="w")
        self._rotulo(self.janela, "Modelos, pesquisa, voz e diagnóstico em um só lugar.", 10, SUAVE).grid(row=1, column=0, sticky="w", pady=(0, 12))
        estilo = ttk.Style(self.janela)
        estilo.configure("Assistente.TNotebook", background=FUNDO, borderwidth=0)
        estilo.configure("Assistente.TNotebook.Tab", background="#304858", foreground=TEXTO,
                        padding=(15, 9), font=("Segoe UI", 10, "bold"))
        estilo.map("Assistente.TNotebook.Tab", background=[("selected", "#405f70")],
                   foreground=[("selected", "#ffffff")])
        abas = ttk.Notebook(self.janela, style="Assistente.TNotebook")
        abas.grid(row=2, column=0, sticky="nsew")
        geral, pesquisa, voz, diagnostico = (tk.Frame(abas, bg=FUNDO, padx=12, pady=16) for _ in range(4))
        for quadro, titulo in ((geral, "Geral"), (pesquisa, "Pesquisa"),
                              (voz, "Voz"), (diagnostico, "Diagnóstico")):
            abas.add(quadro, text=titulo)
            quadro.grid_columnconfigure(1, weight=1)
        self.abas = abas

        self._rotulo(geral, "Ollama local · http://127.0.0.1:11434", 10, SUAVE).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 15))
        self._rotulo(geral, "Modelo de conversa").grid(row=1, column=0, sticky="w", pady=7)
        self.combo_modelo = ttk.Combobox(geral, textvariable=self.modelo, width=42)
        self.combo_modelo.grid(row=1, column=1, sticky="ew", padx=(14, 0), pady=7)
        self._rotulo(geral, "Modelo de memória").grid(row=2, column=0, sticky="w", pady=7)
        self.combo_embedding = ttk.Combobox(geral, textvariable=self.embedding, width=42)
        self.combo_embedding.grid(row=2, column=1, sticky="ew", padx=(14, 0), pady=7)
        self._rotulo(geral, "Idioma").grid(row=3, column=0, sticky="w", pady=7)
        ttk.Combobox(geral, textvariable=self.idioma, values=sorted(configuracao.IDIOMAS),
                     state="readonly", width=16).grid(row=3, column=1, sticky="w", padx=(14, 0), pady=7)
        self._rotulo(geral, "Limite de histórico").grid(row=4, column=0, sticky="w", pady=7)
        tk.Spinbox(geral, from_=10, to=500, textvariable=self.historico, width=8,
                   bg="#13212c", fg=TEXTO, buttonbackground="#304858").grid(row=4, column=1, sticky="w", padx=(14, 0), pady=7)
        self._rotulo(geral, "Os modelos precisam estar instalados. Use a aba Diagnóstico para verificar.", 10, SUAVE).grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(15, 0))

        self._checkbox(pesquisa, "Permitir pesquisas online", self.pesquisa).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        self._rotulo(pesquisa, "Toda busca exige autorização individual. O filtro de conteúdo adulto continua ativo.", 10, SUAVE).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 15))
        self._rotulo(pesquisa, "Provedor").grid(row=2, column=0, sticky="w", pady=7)
        ttk.Combobox(pesquisa, textvariable=self.buscador, values=("duckduckgo", "brave"),
                     state="readonly", width=22).grid(row=2, column=1, sticky="w", padx=(14, 0), pady=7)
        self._rotulo(pesquisa, "Nova chave Brave").grid(row=3, column=0, sticky="w", pady=7)
        self.chave_brave = self._entrada_secreta(pesquisa, 3)
        self._checkbox(pesquisa, "Remover chave Brave salva", self.remover_brave).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=7)
        self.estado_brave = self._rotulo(pesquisa, self._estado_chave("brave"), 10, SUAVE)
        self.estado_brave.grid(row=5, column=0, columnspan=2, sticky="w", pady=7)

        self._rotulo(voz, "Provedor de voz").grid(row=0, column=0, sticky="w", pady=7)
        ttk.Combobox(voz, textvariable=self.voz, values=("edge", "elevenlabs"),
                     state="readonly", width=22).grid(row=0, column=1, sticky="w", padx=(14, 0), pady=7)
        self._rotulo(voz, "Nova chave ElevenLabs").grid(row=1, column=0, sticky="w", pady=7)
        self.chave_elevenlabs = self._entrada_secreta(voz, 1)
        self._checkbox(voz, "Remover chave ElevenLabs salva", self.remover_elevenlabs).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=7)
        self.estado_elevenlabs = self._rotulo(voz, self._estado_chave("elevenlabs"), 10, SUAVE)
        self.estado_elevenlabs.grid(row=3, column=0, columnspan=2, sticky="w", pady=7)
        self._rotulo(voz, "ID da voz ElevenLabs").grid(row=4, column=0, sticky="w", pady=7)
        tk.Entry(voz, textvariable=self.voice_id, bg="#13212c", fg=TEXTO,
                 insertbackground=TEXTO, relief="flat").grid(row=4, column=1, sticky="ew", padx=(14, 0), pady=7, ipady=7)
        self._rotulo(voz, "Deixe a nova chave em branco para manter a atual.", 10, SUAVE).grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(5, 12))
        testes = tk.Frame(voz, bg=FUNDO)
        testes.grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))
        for texto, funcao in (("Testar microfone", diagnostico_inicial.testar_microfone),
                             ("Testar alto-falante", diagnostico_inicial.testar_alto_falante),
                             ("Testar voz", diagnostico_inicial.testar_voz)):
            self._botao(testes, texto, lambda f=funcao, t=texto: self._testar(t, f)).pack(side="left", padx=(0, 8))

        diagnostico.grid_rowconfigure(0, weight=1)
        self.diagnostico = tk.Text(diagnostico, wrap="word", state="disabled", bg="#13212c",
                                   fg=TEXTO, relief="flat", font=("Segoe UI", 10), padx=10, pady=8)
        self.diagnostico.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 12))
        ferramentas = tk.Frame(diagnostico, bg=FUNDO)
        ferramentas.grid(row=1, column=0, columnspan=2, sticky="w")
        self._botao(ferramentas, "Verificar novamente", self.verificar).pack(side="left")
        self._botao(ferramentas, "Copiar diagnóstico", self.copiar_diagnostico).pack(side="left", padx=(8, 0))
        self._botao(ferramentas, "Abrir pasta de dados", self.abrir_pasta_dados).pack(side="left", padx=(8, 0))
        self.aviso = self._rotulo(self.janela, erro_configuracao or "Verificando o Ollama e os dispositivos…", 10, SUAVE)
        self.aviso.grid(row=3, column=0, sticky="w", pady=(10, 0))
        rodape = tk.Frame(self.janela, bg=FUNDO)
        rodape.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        self._botao(rodape, "Cancelar", self.janela.destroy).pack(side="right", padx=(8, 0))
        self._botao(rodape, "Salvar e continuar" if primeira else "Salvar", self.salvar, True).pack(side="right")
        self._agendar(80, self.verificar)
        self._agendar(80, self._processar_eventos)

    def _agendar(self, atraso, funcao):
        referencia = {}
        def executar():
            self._agendamentos.discard(referencia["id"])
            if not self._fechado:
                funcao()
        referencia["id"] = self.janela.after(atraso, executar)
        self._agendamentos.add(referencia["id"])

    def _ao_destruir(self, evento):
        if evento.widget is not self.janela:
            return
        self._fechado = True
        for identificador in self._agendamentos:
            try:
                self.janela.after_cancel(identificador)
            except tk.TclError:
                pass
        self._agendamentos.clear()

    @staticmethod
    def _rotulo(pai, texto, tamanho=10, cor=TEXTO):
        return tk.Label(pai, text=texto, bg=FUNDO, fg=cor, font=("Segoe UI", tamanho),
                        anchor="w", justify="left", wraplength=610)

    @staticmethod
    def _botao(pai, texto, comando, destaque=False):
        return tk.Button(pai, text=texto, command=comando, relief="flat", cursor="hand2",
                         bg=DESTAQUE if destaque else "#304858", fg="#101820" if destaque else TEXTO,
                         font=("Segoe UI", 10, "bold"), padx=12, pady=7)

    @staticmethod
    def _checkbox(pai, texto, variavel):
        return tk.Checkbutton(pai, text=texto, variable=variavel, bg=FUNDO, fg=TEXTO,
                              selectcolor="#304858", activebackground=FUNDO,
                              activeforeground=TEXTO, font=("Segoe UI", 10))

    @staticmethod
    def _entrada_secreta(pai, linha):
        entrada = tk.Entry(pai, show="•", bg="#13212c", fg=TEXTO,
                           insertbackground=TEXTO, relief="flat")
        entrada.grid(row=linha, column=1, sticky="ew", padx=(14, 0), pady=7, ipady=7)
        return entrada

    @staticmethod
    def _estado_chave(provedor):
        try:
            salva = bool(servicos.obter_chave(provedor))
        except Exception:
            return "Cofre de credenciais indisponível."
        return "Chave configurada no cofre do Windows." if salva else "Nenhuma chave configurada."

    def _escrever_diagnostico(self, texto):
        self.diagnostico.configure(state="normal")
        self.diagnostico.delete("1.0", "end")
        self.diagnostico.insert("end", texto)
        self.diagnostico.configure(state="disabled")

    def verificar(self):
        self.aviso.configure(text="Verificando o Ollama e os dispositivos…")
        def trabalho():
            resultado = diagnostico_inicial.verificar()
            self.eventos.put(("verificacao", resultado))
        threading.Thread(target=trabalho, name="diagnostico-inicial", daemon=True).start()

    def _processar_eventos(self):
        try:
            while True:
                tipo, dado = self.eventos.get_nowait()
                if tipo == "verificacao":
                    self._mostrar_resultado(dado)
                elif tipo == "teste":
                    self.aviso.configure(text=dado)
        except queue.Empty:
            pass
        try:
            if not self._fechado and self.janela.winfo_exists():
                self._agendar(80, self._processar_eventos)
        except tk.TclError:
            pass

    def copiar_diagnostico(self):
        texto = self.diagnostico.get("1.0", "end-1c")
        self.janela.clipboard_clear()
        self.janela.clipboard_append(texto)
        self.aviso.configure(text="Diagnóstico copiado. Nenhuma chave ou conversa foi incluída.")

    def abrir_pasta_dados(self):
        try:
            os.startfile(str(configuracao.CONFIGURACAO.parent))
        except OSError:
            self.aviso.configure(text="Não foi possível abrir a pasta de dados. Confira o caminho mostrado no diagnóstico.")

    def _mostrar_resultado(self, resultado):
        if not self.janela.winfo_exists():
            return
        self.resultado = resultado
        modelos = resultado["modelos"]
        self.combo_modelo["values"] = modelos
        self.combo_embedding["values"] = modelos
        linhas = [
            f"Assistente IA: {resultado.get('versao_app', 'versão não disponível')}",
            f"Ollama instalado: {'sim' if resultado['ollama_instalado'] else 'não detectado no PATH'}",
            f"Servidor local: {'funcionando · versão ' + resultado['ollama_versao'] if resultado['ollama_ativo'] else 'indisponível'}",
            f"Python: {resultado['python']}",
            f"Modelos encontrados: {', '.join(modelos) if modelos else 'nenhum'}",
            f"Modelo de conversa selecionado: {'disponível' if self.modelo.get() in modelos else 'ausente'}",
            f"Modelo de memória selecionado: {'disponível' if self.embedding.get() in modelos else 'ausente'}",
            f"Microfone: {'detectado' if resultado['microfone'] else 'não detectado'}",
            f"Alto-falante: {'detectado' if resultado['alto_falante'] else 'não detectado'}",
            f"Voz local Piper: {'disponível' if resultado.get('voz_local') else 'modelo ausente'}",
            f"Pesquisa: {'ligada' if internet.habilitada() else 'desligada'} · provedor: {servicos.carregar()['buscador']}",
            f"Voz online: {servicos.carregar()['voz']}",
            f"Configuração: {diagnostico_inicial.caminho_publico(configuracao.CONFIGURACAO)}",
            f"Banco: {diagnostico_inicial.caminho_publico(main.BANCO)}",
            f"Logs: {diagnostico_inicial.caminho_publico(diagnostico.PASTA_LOGS / 'assistente.log')}",
        ]
        if not resultado["ollama_ativo"]:
            linhas.append("Ação: instale ou abra o Ollama; depois clique em 'Verificar novamente'.")
        elif not modelos:
            linhas.append("Ação: baixe um modelo de conversa e outro de memória com 'ollama pull NOME'.")
        elif self.modelo.get() not in modelos or self.embedding.get() not in modelos:
            linhas.append("Ação: escolha modelos instalados na aba Geral ou baixe os ausentes com 'ollama pull NOME'.")
        if not resultado["microfone"]:
            linhas.append("Áudio: confira o microfone padrão e a permissão de acesso do Windows.")
        if not resultado["alto_falante"]:
            linhas.append("Áudio: confira o alto-falante padrão do Windows.")
        if resultado.get("voz_local") is False:
            linhas.append("Voz: o modelo local Piper está ausente; reinstale o aplicativo.")
        recentes = resultado.get("eventos_recentes", [])
        linhas.append("Eventos técnicos recentes (sem conteúdo):")
        linhas.extend(f"  {hora} · {evento}" for hora, evento in recentes)
        if not recentes:
            linhas.append("  Nenhum evento registrado.")
        self._escrever_diagnostico("\n".join(linhas))
        self.aviso.configure(text="Escolha modelos instalados e salve." if resultado["ollama_ativo"] else
                             "A conversa ficará indisponível até o Ollama funcionar.")

    def _testar(self, titulo, funcao):
        self.aviso.configure(text=titulo + " em andamento…")
        def trabalho():
            try:
                resultado = funcao()
                mensagem = ("Microfone funcionando." if resultado > 0.003 else
                            "Microfone aberto, mas sem sinal. Fale perto dele e tente novamente.") if titulo == "Testar microfone" else titulo + ": concluído."
            except Exception as erro:
                mensagem = titulo + f": falhou ({type(erro).__name__}). Confira o dispositivo padrão do Windows."
            self.eventos.put(("teste", mensagem))
        threading.Thread(target=trabalho, name="teste-audio", daemon=True).start()

    def salvar(self):
        try:
            try:
                limite = int(self.historico.get())
            except ValueError as erro:
                raise ValueError("Campo 'limite_historico' inválido: use um número de 10 a 500.") from erro
            dados = configuracao.validar({
                "modelo": self.modelo.get().strip(), "modelo_memoria": self.embedding.get().strip(),
                "idioma": self.idioma.get(), "limite_historico": limite,
                "configurado": True,
            })
            if self.resultado is None or not self.resultado["ollama_ativo"]:
                if self.primeira:
                    raise ValueError("O Ollama local precisa estar funcionando. Clique em 'Verificar novamente'.")
                atuais = configuracao.carregar()
                if any(dados[campo] != atuais[campo] for campo in ("modelo", "modelo_memoria")):
                    raise ValueError("Para trocar modelos, abra o Ollama e clique em 'Verificar novamente'.")
            else:
                for campo in ("modelo", "modelo_memoria"):
                    if dados[campo] not in self.resultado["modelos"]:
                        raise ValueError(f"O modelo '{dados[campo]}' não está instalado. Escolha um da lista ou use 'ollama pull'.")
            buscador, voz = self.buscador.get(), self.voz.get()
            voice_id = self.voice_id.get().strip()
            if buscador not in servicos.BUSCADORES or voz not in servicos.VOZES:
                raise ValueError("Provedor de pesquisa ou voz inválido.")
            if not servicos.id_voz_valido(voice_id):
                raise ValueError("ID da voz ElevenLabs inválido.")
            novas = {
                "brave": self.chave_brave.get().strip(),
                "elevenlabs": self.chave_elevenlabs.get().strip(),
            }
            remover = {
                "brave": self.remover_brave.get(),
                "elevenlabs": self.remover_elevenlabs.get(),
            }
            for provedor, chave in novas.items():
                if len(chave) > 500 or "\n" in chave or "\r" in chave:
                    raise ValueError(f"A chave de {provedor} é inválida.")
                if chave and remover[provedor]:
                    raise ValueError(f"Escolha entre substituir ou remover a chave de {provedor}.")
            for provedor, necessario in (("brave", buscador == "brave"),
                                         ("elevenlabs", voz == "elevenlabs")):
                if not necessario:
                    continue
                if remover[provedor]:
                    raise ValueError(f"O provedor {provedor} precisa de uma chave.")
                if not novas[provedor]:
                    try:
                        disponivel = bool(servicos.obter_chave(provedor))
                    except Exception as erro:
                        raise ValueError("Não foi possível acessar o cofre de credenciais do Windows.") from erro
                    if not disponivel:
                        raise ValueError(f"Informe a chave da API {provedor}.")
            if voz == "elevenlabs" and not voice_id:
                raise ValueError("Informe o ID da voz ElevenLabs.")
            try:
                for provedor in novas:
                    if novas[provedor] or remover[provedor]:
                        servicos.salvar_chave(provedor, "" if remover[provedor] else novas[provedor])
            except Exception as erro:
                raise ValueError("Não foi possível salvar as chaves no cofre de credenciais do Windows.") from erro
            servicos.salvar(buscador, voz, voice_id)
            configuracao.salvar(dados)
            internet.definir_habilitada(self.pesquisa.get())
        except (ValueError, OSError) as erro:
            messagebox.showerror("Configuração", str(erro), parent=self.janela)
            return
        self.janela.destroy()
        self.ao_salvar(dados)
