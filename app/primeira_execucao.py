"""Assistente de instalação e configurações locais do aplicativo."""

import os
import threading
import queue
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from . import configuracao, diagnostico, diagnostico_inicial, icone_app, internet, main, servicos, voz as captura_voz


FUNDO = "#0b1424"
PAINEL = "#12223a"
ENTRADA = "#172b47"
BORDA = "#2b4366"
TEXTO = "#f3f6ff"
SUAVE = "#a8bad2"
DESTAQUE = "#4bd8d0"
ROXO = "#ad91ff"
ctk.set_appearance_mode("dark")


class _AbasConfiguracao(ctk.CTkFrame):
    """Abas arredondadas no mesmo padrão visual da conversa principal."""

    def __init__(self, pai):
        super().__init__(pai, fg_color="transparent")
        self._quadros = {}
        self._botoes = {}
        self._atual = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._barra = ctk.CTkFrame(self, fg_color="transparent")
        self._barra.grid(row=0, column=0, sticky="w", pady=(0, 9))
        self._painel = ctk.CTkFrame(self, fg_color=PAINEL, corner_radius=17,
                                   border_width=1, border_color=BORDA)
        self._painel.grid(row=1, column=0, sticky="nsew")
        self._painel.grid_columnconfigure(0, weight=1)
        self._painel.grid_rowconfigure(0, weight=1)

    def add(self, nome):
        if nome == "Diagnóstico":
            quadro = ctk.CTkFrame(self._painel, fg_color="transparent")
        else:
            quadro = ctk.CTkScrollableFrame(self._painel, fg_color="transparent",
                corner_radius=0, scrollbar_button_color="#355076",
                scrollbar_button_hover_color=DESTAQUE)
        quadro.grid(row=0, column=0, sticky="nsew", padx=18, pady=16)
        quadro.grid_remove()
        botao = ctk.CTkButton(self._barra, text=nome, command=lambda n=nome: self.set(n),
                              width=139, height=39, corner_radius=10, fg_color="#1c3150",
                              hover_color="#274564", text_color=SUAVE,
                              font=("Segoe UI", 11, "bold"))
        botao.pack(side="left", padx=(0, 8))
        self._quadros[nome] = quadro
        self._botoes[nome] = botao
        if self._atual is None:
            self.set(nome)
        return quadro

    def tabs(self):
        return tuple(self._quadros)

    def set(self, nome):
        if nome not in self._quadros:
            raise ValueError("Aba desconhecida.")
        if self._atual is not None:
            self._quadros[self._atual].grid_remove()
            self._botoes[self._atual].configure(fg_color="#1c3150", text_color=SUAVE)
        self._atual = nome
        self._quadros[nome].grid()
        self._botoes[nome].configure(fg_color="#1d3b57", text_color=DESTAQUE)


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
        icone_app.aplicar(self.janela)
        self.janela.geometry("820x680")
        self.janela.minsize(680, 590)
        self.janela.configure(bg=FUNDO, padx=24, pady=20)
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
        self.microfone = tk.StringVar(value=dados["microfone"] or captura_voz.MICROFONE_PADRAO)
        self.mostrar_todas_entradas = tk.BooleanVar(value=False)
        self.historico = tk.StringVar(value=str(dados["limite_historico"]))
        self.verificar_atualizacoes = tk.BooleanVar(value=dados["verificar_atualizacoes"])
        self.pesquisa = tk.BooleanVar(value=internet.habilitada())
        provedores = servicos.carregar()
        self.buscador = tk.StringVar(value=provedores["buscador"])
        self.voz = tk.StringVar(value=provedores["voz"])
        self.voice_id = tk.StringVar(value=provedores["voice_id"])
        self.remover_brave = tk.BooleanVar(value=False)
        self.remover_elevenlabs = tk.BooleanVar(value=False)

        self._rotulo(self.janela, "Configure sua assistente" if primeira else "Configurações",
                     23, TEXTO).grid(row=0, column=0, sticky="w")
        self._rotulo(self.janela, "Ajuste modelos, pesquisa e voz. Confira o funcionamento em Diagnóstico.",
                     11, SUAVE).grid(row=1, column=0, sticky="w", pady=(0, 17))
        abas = _AbasConfiguracao(self.janela)
        abas.grid(row=2, column=0, sticky="nsew")
        geral, pesquisa, voz, diagnostico = (abas.add(nome) for nome in
                                             ("Geral", "Pesquisa", "Voz", "Diagnóstico"))
        for quadro in (geral, pesquisa, voz, diagnostico):
            quadro.grid_columnconfigure(1, weight=1)
        self.abas = abas

        self._rotulo(geral, "MODELOS E PREFERÊNCIAS", 10, DESTAQUE).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 3))
        self._rotulo(geral, "Escolha os modelos instalados no seu Ollama local.", 11, SUAVE).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 7))
        etiqueta_ollama = ctk.CTkFrame(geral, fg_color=ENTRADA, corner_radius=10)
        etiqueta_ollama.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        self._rotulo(etiqueta_ollama, "●  OLLAMA LOCAL    http://127.0.0.1:11434", 10, DESTAQUE).pack(
            anchor="w", padx=14, pady=6)
        self._rotulo(geral, "Modelo de conversa").grid(row=3, column=0, sticky="w", pady=4)
        self.combo_modelo = ctk.CTkComboBox(geral, variable=self.modelo, values=[self.modelo.get()],
            height=37, fg_color=ENTRADA, border_color=BORDA, button_color="#274768",
            dropdown_fg_color=ENTRADA, text_color=TEXTO, font=("Segoe UI", 11))
        self.combo_modelo.grid(row=3, column=1, sticky="ew", padx=(16, 0), pady=4)
        self._rotulo(geral, "Modelo de memória").grid(row=4, column=0, sticky="w", pady=4)
        self.combo_embedding = ctk.CTkComboBox(geral, variable=self.embedding, values=[self.embedding.get()],
            height=37, fg_color=ENTRADA, border_color=BORDA, button_color="#274768",
            dropdown_fg_color=ENTRADA, text_color=TEXTO, font=("Segoe UI", 11))
        self.combo_embedding.grid(row=4, column=1, sticky="ew", padx=(16, 0), pady=4)
        self._rotulo(geral, "Idioma").grid(row=5, column=0, sticky="w", pady=4)
        ctk.CTkOptionMenu(geral, variable=self.idioma, values=sorted(configuracao.IDIOMAS),
            height=37, width=145, fg_color=ENTRADA, button_color="#274768",
            button_hover_color="#355b83", text_color=TEXTO,
            font=("Segoe UI", 11)).grid(row=5, column=1, sticky="w", padx=(16, 0), pady=4)
        self._rotulo(geral, "Limite de histórico").grid(row=6, column=0, sticky="w", pady=4)
        ctk.CTkEntry(geral, textvariable=self.historico, width=100, height=37,
            fg_color=ENTRADA, border_color=BORDA, text_color=TEXTO,
            font=("Segoe UI", 11)).grid(row=6, column=1, sticky="w", padx=(16, 0), pady=4)
        self._rotulo(geral, "Entre 10 e 2000 mensagens. A resposta usa o trecho que cabe no contexto do modelo.",
            10, SUAVE).grid(row=7, column=0, columnspan=2, sticky="w", pady=(6, 3))
        self._checkbox(geral, "Avisar quando houver nova versão", self.verificar_atualizacoes).grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(2, 2))

        self._rotulo(pesquisa, "PESQUISA ONLINE", 10, DESTAQUE).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 7))
        self._rotulo(pesquisa, "Consulte fontes externas quando precisar de informação atual.",
            11, SUAVE).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 17))
        self._checkbox(pesquisa, "Permitir pesquisas online", self.pesquisa).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(0, 14))
        self._rotulo(pesquisa, "Cada busca pede autorização. O bloqueio de conteúdo adulto permanece ativo.",
            10, SUAVE).grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 16))
        self._rotulo(pesquisa, "Provedor").grid(row=4, column=0, sticky="w", pady=7)
        ctk.CTkOptionMenu(pesquisa, variable=self.buscador, values=["duckduckgo", "brave"],
            width=190, height=37, fg_color=ENTRADA, button_color="#274768",
            button_hover_color="#355b83", text_color=TEXTO,
            font=("Segoe UI", 11)).grid(row=4, column=1, sticky="w", padx=(16, 0), pady=7)
        self._rotulo(pesquisa, "Nova chave Brave").grid(row=5, column=0, sticky="w", pady=7)
        self.chave_brave = self._entrada_secreta(pesquisa, 5)
        self._checkbox(pesquisa, "Remover chave Brave salva", self.remover_brave).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(10, 3))
        self.estado_brave = self._rotulo(pesquisa, self._estado_chave("brave"), 10, SUAVE)
        self.estado_brave.grid(row=7, column=0, columnspan=2, sticky="w", pady=7)

        self._rotulo(voz, "VOZ E DISPOSITIVOS", 10, ROXO).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 7))
        self._rotulo(voz, "Escolha o microfone e a voz. Teste antes de usar.", 11, SUAVE).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 16))
        self._rotulo(voz, "Provedor de voz").grid(row=6, column=0, sticky="w", pady=7)
        ctk.CTkOptionMenu(voz, variable=self.voz, values=["edge", "elevenlabs"],
            width=190, height=37, fg_color=ENTRADA, button_color="#274768",
            button_hover_color="#355b83", text_color=TEXTO,
            font=("Segoe UI", 11)).grid(row=6, column=1, sticky="w", padx=(16, 0), pady=7)
        self._rotulo(voz, "Nova chave ElevenLabs").grid(row=7, column=0, sticky="w", pady=7)
        self.chave_elevenlabs = self._entrada_secreta(voz, 7)
        self._checkbox(voz, "Remover chave ElevenLabs salva", self.remover_elevenlabs).grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(8, 2))
        self.estado_elevenlabs = self._rotulo(voz, self._estado_chave("elevenlabs"), 10, SUAVE)
        self.estado_elevenlabs.grid(row=9, column=0, columnspan=2, sticky="w", pady=5)
        self._rotulo(voz, "ID da voz ElevenLabs").grid(row=10, column=0, sticky="w", pady=7)
        ctk.CTkEntry(voz, textvariable=self.voice_id, height=37, fg_color=ENTRADA,
            border_color=BORDA, text_color=TEXTO, font=("Segoe UI", 11)).grid(
                row=10, column=1, sticky="ew", padx=(16, 0), pady=7)
        self._rotulo(voz, "Deixe a chave em branco para manter a atual.", 10, SUAVE).grid(
            row=11, column=0, columnspan=2, sticky="w", pady=(6, 9))
        self._rotulo(voz, "Microfone de entrada", 12).grid(row=2, column=0, sticky="w", pady=7)
        self.combo_microfone = ctk.CTkOptionMenu(
            voz, variable=self.microfone, values=[captura_voz.MICROFONE_PADRAO],
            height=42, fg_color=ENTRADA, button_color="#274768",
            button_hover_color="#355b83", text_color=TEXTO, font=("Segoe UI", 12),
        )
        self.combo_microfone.grid(row=2, column=1, sticky="ew", padx=(16, 0), pady=7)
        self.estado_microfones = self._rotulo(voz, "", 10, SUAVE)
        self.estado_microfones.grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 5))
        self._checkbox_todas = self._checkbox(
            voz, "Mostrar todas as entradas", self.mostrar_todas_entradas)
        self._checkbox_todas.configure(command=self._atualizar_microfones)
        self._checkbox_todas.grid(row=4, column=0, sticky="w", pady=(0, 10))
        self._botao(voz, "Atualizar microfones", self._atualizar_microfones).grid(
            row=4, column=1, sticky="w", padx=(16, 0), pady=(0, 10))
        testes = ctk.CTkFrame(voz, fg_color="transparent")
        testes.grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 16))
        linha_testes = ctk.CTkFrame(testes, fg_color="transparent")
        linha_testes.pack(anchor="w")
        self._botao(linha_testes, "Testar este microfone", self._testar_microfone).pack(side="left", padx=(0, 8))
        for texto, funcao in (("Testar alto-falante", diagnostico_inicial.testar_alto_falante),
                             ("Testar voz", diagnostico_inicial.testar_voz)):
            self._botao(linha_testes, texto, lambda f=funcao, t=texto: self._testar(t, f)).pack(
                side="left", padx=(0, 8))
        self.resultado_microfone = self._rotulo(
            testes, "Escolha um microfone e fale durante o teste de 2 segundos.", 10, SUAVE)
        self.resultado_microfone.pack(anchor="w", pady=(6, 0))
        self._atualizar_microfones()

        diagnostico.grid_rowconfigure(1, weight=1)
        self._rotulo(diagnostico, "DIAGNÓSTICO", 10, DESTAQUE).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        self.diagnostico = ctk.CTkTextbox(diagnostico, wrap="word", state="disabled",
            fg_color=ENTRADA, border_color=BORDA, border_width=1, corner_radius=12,
            text_color=TEXTO, font=("Consolas", 10),
            scrollbar_button_color="#355076")
        self.diagnostico.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 12))
        ferramentas = ctk.CTkFrame(diagnostico, fg_color="transparent")
        ferramentas.grid(row=2, column=0, columnspan=2, sticky="w")
        self._botao(ferramentas, "Verificar ambiente", self.verificar).pack(side="left")
        self._botao(ferramentas, "Copiar diagnóstico", self.copiar_diagnostico).pack(side="left", padx=(8, 0))
        self._botao(ferramentas, "Abrir pasta de dados", self.abrir_pasta_dados).pack(side="left", padx=(8, 0))
        self.aviso = self._rotulo(self.janela, erro_configuracao or
                                  "Verificando o Ollama e os dispositivos…", 10, SUAVE)
        self.aviso.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        rodape = ctk.CTkFrame(self.janela, fg_color="transparent")
        rodape.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        self._botao(rodape, "Cancelar", self.janela.destroy).pack(side="right", padx=(8, 0))
        self._botao(rodape, "Salvar e continuar" if primeira else "Salvar", self.salvar, True).pack(side="right")
        self.verificar()
        self._agendar(20, self._processar_eventos)

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
    def _rotulo(pai, texto, tamanho=11, cor=TEXTO):
        return ctk.CTkLabel(pai, text=texto, text_color=cor,
                            font=("Segoe UI", tamanho), anchor="w", justify="left",
                            wraplength=560)

    @staticmethod
    def _botao(pai, texto, comando, destaque=False):
        return ctk.CTkButton(pai, text=texto, command=comando, cursor="hand2",
                             fg_color=DESTAQUE if destaque else "#1c3150",
                             hover_color="#75e7df" if destaque else "#2b496b",
                             text_color=FUNDO if destaque else TEXTO,
                             corner_radius=10, height=39,
                             font=("Segoe UI", 11, "bold"))

    @staticmethod
    def _checkbox(pai, texto, variavel):
        return ctk.CTkCheckBox(pai, text=texto, variable=variavel, text_color=TEXTO,
                               fg_color=DESTAQUE, hover_color="#75e7df",
                               border_color=BORDA, checkmark_color=FUNDO,
                               font=("Segoe UI", 11))

    @staticmethod
    def _entrada_secreta(pai, linha):
        entrada = ctk.CTkEntry(pai, show="•", height=37, fg_color=ENTRADA,
                               border_color=BORDA, text_color=TEXTO,
                               font=("Segoe UI", 11))
        entrada.grid(row=linha, column=1, sticky="ew", padx=(16, 0), pady=7)
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
                elif tipo == "teste_microfone":
                    mensagem, cor = dado
                    self.resultado_microfone.configure(text=mensagem, text_color=cor)
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
        self.combo_modelo.configure(values=modelos or [self.modelo.get()])
        self.combo_embedding.configure(values=modelos or [self.embedding.get()])
        linhas = [
            f"Assistente IA: {resultado.get('versao_app', 'versão não disponível')}",
            f"Ollama instalado: {'sim' if resultado['ollama_instalado'] else 'não detectado no PATH'}",
            f"Servidor local: {'funcionando · versão ' + resultado['ollama_versao'] if resultado['ollama_ativo'] else 'indisponível'}",
            f"Versão do Ollama: {'compatível' if resultado.get('ollama_versao_compativel') else 'antiga' if resultado.get('ollama_versao_compativel') is False else 'não verificada'}",
            f"RAM física: {resultado.get('ram_gb') or 'não detectada'} GB",
            f"VRAM NVIDIA: {resultado.get('vram_nvidia_gb') or 'não detectada'} GB (opcional; CPU continua disponível)",
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
        if resultado.get("ollama_versao_compativel") is False:
            linhas.append("Ação: atualize o Ollama para a versão 0.6.0 ou superior.")
        if resultado.get("ram_gb") is not None and resultado["ram_gb"] < 8:
            linhas.append("Recursos: menos de 8 GB de RAM; o modelo padrão pode ficar lento ou não carregar. Escolha um modelo menor.")
        if resultado.get("vram_nvidia_gb") is not None and resultado["vram_nvidia_gb"] < 6:
            linhas.append("Recursos: VRAM abaixo de 6 GB; a inferência pode usar RAM/CPU e ficar mais lenta.")
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
                if titulo == "Testar microfone" and isinstance(erro, RuntimeError) and str(erro).startswith("O microfone escolhido não está disponível"):
                    mensagem = "Microfone escolhido indisponível. Atualize a lista e selecione outro."
                else:
                    mensagem = titulo + f": falhou ({type(erro).__name__}). Confira o áudio do Windows."
            self.eventos.put(("teste", mensagem))
        threading.Thread(target=trabalho, name="teste-audio", daemon=True).start()

    def _microfone_escolhido(self):
        escolha = self.microfone.get()
        return "" if escolha == captura_voz.MICROFONE_PADRAO else escolha

    def _atualizar_microfones(self):
        try:
            todas = [nome for nome, _ in captura_voz.listar_microfones()]
            recomendadas = [nome for nome, _ in captura_voz.listar_microfones_recomendados()]
            padrao = captura_voz.nome_microfone_padrao()
            padrao_compativel = captura_voz.microfone_padrao_compativel()
        except Exception:
            todas = recomendadas = []
            self.estado_microfones.configure(text="Não foi possível consultar os microfones. Verifique o áudio do Windows.")
        else:
            self.estado_microfones.configure(text=(
                f"{len(recomendadas)} microfone(s) recomendado(s) de {len(todas)} entrada(s). "
                f"Padrão do Windows: {padrao}." +
                (" Escolha um recomendado: o padrão não aceita a captura." if not padrao_compativel else "")))
        atual = self.microfone.get()
        nomes = todas if self.mostrar_todas_entradas.get() else recomendadas
        opcoes = [captura_voz.MICROFONE_PADRAO, *nomes]
        if atual not in opcoes:
            opcoes.append(atual)
            if atual not in todas:
                self.estado_microfones.configure(text="Microfone salvo indisponível. Escolha outro e salve.")
        self.combo_microfone.configure(values=opcoes)

    def _testar_microfone(self):
        escolha = self._microfone_escolhido()
        nome = self.microfone.get()
        self.resultado_microfone.configure(text=f"Testando {nome}. Fale agora por 2 segundos…", text_color=SUAVE)
        def trabalho():
            try:
                nivel = diagnostico_inicial.testar_microfone(escolha)
                if nivel > 0.003:
                    resultado = (f"{nome}: sinal detectado. Se é o microfone desejado, clique em Salvar.", DESTAQUE)
                else:
                    resultado = (f"{nome}: nenhum sinal detectado. Tente falar perto dele ou escolha outro.", "#ffb0ab")
            except Exception as erro:
                if "16 kHz" in str(erro):
                    resultado = (f"{nome}: entrada incompatível. Escolha uma das recomendadas.", "#ffb0ab")
                else:
                    resultado = (f"{nome}: não foi possível captar áudio ({type(erro).__name__}). Escolha outro.", "#ffb0ab")
            self.eventos.put(("teste_microfone", resultado))
        threading.Thread(target=trabalho, name="teste-microfone", daemon=True).start()

    def salvar(self):
        try:
            try:
                limite = int(self.historico.get())
            except ValueError as erro:
                raise ValueError("Campo 'limite_historico' inválido: use um número de 10 a 2000.") from erro
            dados = configuracao.validar({
                "modelo": self.modelo.get().strip(), "modelo_memoria": self.embedding.get().strip(),
                "idioma": self.idioma.get(), "limite_historico": limite,
                "microfone": self._microfone_escolhido(),
                "verificar_atualizacoes": self.verificar_atualizacoes.get(),
                "configurado": True,
            })
            if dados["microfone"]:
                captura_voz.resolver_microfone(dados["microfone"])
            if self.resultado is None or not self.resultado["ollama_ativo"]:
                if self.primeira:
                    raise ValueError("O Ollama local precisa estar funcionando. Clique em 'Verificar ambiente'.")
                atuais = configuracao.carregar()
                if any(dados[campo] != atuais[campo] for campo in ("modelo", "modelo_memoria")):
                    raise ValueError("Para trocar modelos, abra o Ollama e clique em 'Verificar ambiente'.")
            else:
                if self.resultado.get("ollama_versao_compativel") is False:
                    raise ValueError("O Ollama instalado é antigo. Atualize para a versão 0.6.0 ou superior.")
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
        except (ValueError, OSError, RuntimeError) as erro:
            messagebox.showerror("Configuração", str(erro), parent=self.janela)
            return
        self.janela.destroy()
        self.ao_salvar(dados)
