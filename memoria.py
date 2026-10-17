"""Fatos duráveis, organização e recuperação do histórico persistente."""

import json
import heapq
import math
import re
import sqlite3
import unicodedata

import resumos
import diagnostico


STOPWORDS = set("a o as os um uma uns umas de da do das dos em no na nos nas para por com e ou que se eu meu minha meus minhas voce voces seu sua seus suas qual quais como quando onde pode poderia favor sobre foi era ser esta estou tem tenho lembra lembrar conversamos conversa conversas anteriormente passado passadas salvo salvas guardou diga fale saber".split())


def normalizar(texto):
    """Normaliza texto para comparação e deduplicação de fatos."""
    texto = unicodedata.normalize("NFKD", texto.casefold())
    return " ".join(re.findall(r"\w+", "".join(c for c in texto if not unicodedata.combining(c))))


def iniciar_estrutura(conexao):
    """Cria ou atualiza as tabelas usadas pela memória persistente."""
    colunas = {r[1] for r in conexao.execute("PRAGMA table_info(mensagens)")}
    for nome, tipo in (
        ("assunto", "TEXT NOT NULL DEFAULT 'geral'"),
        ("projeto", "TEXT NOT NULL DEFAULT ''"),
        ("ignorar_memoria", "INTEGER NOT NULL DEFAULT 0"),
    ):
        if nome not in colunas:
            conexao.execute(f"ALTER TABLE mensagens ADD COLUMN {nome} {tipo}")
    conexao.executescript("""
        CREATE TABLE IF NOT EXISTS memorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conteudo TEXT NOT NULL,
            normalizado TEXT NOT NULL,
            assunto TEXT NOT NULL DEFAULT 'geral',
            projeto TEXT NOT NULL DEFAULT '',
            importancia INTEGER NOT NULL DEFAULT 3 CHECK(importancia BETWEEN 1 AND 5),
            chave TEXT,
            criada_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            atualizada_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(normalizado, assunto, projeto)
        );
        CREATE TABLE IF NOT EXISTS fontes_memoria (
            memoria_id INTEGER NOT NULL REFERENCES memorias(id) ON DELETE CASCADE,
            mensagem_id INTEGER NOT NULL REFERENCES mensagens(id) ON DELETE CASCADE,
            PRIMARY KEY(memoria_id, mensagem_id)
        );
        CREATE TABLE IF NOT EXISTS vetores_lembrancas (
            memoria_id INTEGER NOT NULL REFERENCES memorias(id) ON DELETE CASCADE,
            modelo TEXT NOT NULL,
            vetor TEXT NOT NULL,
            PRIMARY KEY(memoria_id, modelo)
        );
        CREATE TABLE IF NOT EXISTS mensagens_processadas (
            mensagem_id INTEGER PRIMARY KEY REFERENCES mensagens(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS dependencias_memoria (
            memoria_id INTEGER NOT NULL REFERENCES memorias(id) ON DELETE CASCADE,
            resposta_id INTEGER NOT NULL REFERENCES mensagens(id) ON DELETE CASCADE,
            PRIMARY KEY(memoria_id, resposta_id)
        );
        CREATE TABLE IF NOT EXISTS config_memoria (chave TEXT PRIMARY KEY, valor TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_memorias_escopo ON memorias(projeto, assunto);
        CREATE INDEX IF NOT EXISTS idx_mensagens_escopo ON mensagens(projeto, assunto, id);
    """)
    resumos.iniciar_estrutura(conexao)
    conexao.execute("CREATE TEMP TABLE IF NOT EXISTS memorias_no_contexto (id INTEGER PRIMARY KEY)")
    conexao.commit()


def contexto_ativo(conexao):
    """Retorna o assunto e o projeto atualmente selecionados."""
    dados = dict(conexao.execute("SELECT chave, valor FROM config_memoria"))
    return dados.get("assunto", "geral"), dados.get("projeto", "")


def definir_contexto(conexao, assunto=None, projeto=None):
    """Atualiza o escopo da memória e devolve o novo contexto ativo."""
    with conexao:
        for chave, valor in (("assunto", assunto), ("projeto", projeto)):
            if valor is None:
                continue
            valor = " ".join(valor.casefold().split())
            if len(valor) > 80:
                raise ValueError("O nome do assunto ou projeto deve ter até 80 caracteres.")
            if chave == "assunto":
                valor = valor or "geral"
            elif normalizar(valor) in {"nenhum", "geral", "sem projeto"}:
                valor = ""
            conexao.execute("INSERT OR REPLACE INTO config_memoria VALUES (?, ?)", (chave, valor))
    return contexto_ativo(conexao)


def _chave_fato(texto):
    normal = normalizar(texto)
    for padrao, chave in (
        (r"^(meu nome e|me chamo)\b", "nome"),
        (r"^(moro em|minha cidade e)\b", "localizacao"),
        (r"^meu aniversario e\b", "aniversario"),
        (r"^meu codigo de teste e\b", "codigo_teste"),
    ):
        if re.match(padrao, normal):
            return chave
    return None


def detectar_fato(texto):
    """Identifica afirmações do usuário que podem ser guardadas como memória."""
    texto = texto.strip()
    if not texto or "?" in texto or len(texto) > 1200 or "```" in texto:
        return None
    explicito = re.match(
        r"(?is)^(?:lembre[- ]se de que|lembre que|guarde (?:esta |essa )?informa[çc][ãa]o\s*:?|"
        r"anote (?:que|isso\s*:)|n[ãa]o esque[çc]a (?:que|de que))\s*(.+)", texto
    )
    if explicito:
        return explicito.group(1).strip()
    normal = normalizar(texto)
    if _chave_fato(texto) or re.match(
        r"^(prefiro|gosto de|trabalho como|trabalho com|estou (?:desenvolvendo|criando|estudando)|"
        r"meu projeto (?:se chama|usa|utiliza)|minha linguagem favorita e)\b", normal
    ):
        return texto
    return None


def _suprimir_fontes(conexao, identificador):
    ids = [r[0] for r in conexao.execute(
        "SELECT mensagem_id FROM fontes_memoria WHERE memoria_id = ?", (identificador,)
    )]
    ids.extend(r[0] for r in conexao.execute("SELECT resposta_id FROM dependencias_memoria WHERE memoria_id=?",(identificador,)))
    fato = conexao.execute("SELECT normalizado,assunto,projeto,chave FROM memorias WHERE id=?", (identificador,)).fetchone()
    if fato and len(fato[0]) >= 8:
        valor = re.sub(r"^(meu nome e|me chamo|moro em|minha cidade e|meu aniversario e|meu codigo de teste e)\s+", "", fato[0]) if fato[3] else ""
        for mid, texto in conexao.execute(
            "SELECT id,conteudo FROM mensagens WHERE assunto=? AND projeto=? AND ignorar_memoria=0", fato[1:3]
        ):
            conteudo = f" {normalizar(texto)} "
            if f" {fato[0]} " in conteudo or (len(valor) >= 3 and f" {valor} " in conteudo):
                ids.append(mid)
    for origem in set(ids):
        # Oculta também a resposta imediatamente ligada à fala antiga.
        proxima = conexao.execute(
            "SELECT id, papel FROM mensagens WHERE id > ? ORDER BY id LIMIT 1", (origem,)
        ).fetchone()
        afetadas = [origem] + ([proxima[0]] if proxima and proxima[1] == "assistant" else [])
        for mensagem in afetadas:
            conexao.execute("UPDATE mensagens SET ignorar_memoria = 1 WHERE id = ?", (mensagem,))
            conexao.execute("DELETE FROM vetores_memoria WHERE mensagem_id = ?", (mensagem,))
            conexao.execute(
                "DELETE FROM resumos_conversa WHERE inicio_id <= ? AND fim_id >= ?", (mensagem, mensagem)
            )


def registrar_contexto(conexao, texto, historico):
    """Rastreia fatos expostos ao modelo, inclusive via resumos/respostas anteriores."""
    ids = {int(i) for i in re.findall(r"(?m)^Fato #(\d+)\b", texto)}
    mensagens = {int(i) for i in re.findall(r"(?m)^Conversa #(\d+)\b", texto)}
    mensagens.update(m["id"] for m in historico if "id" in m)
    for i in re.findall(r"(?m)^Resumo #(\d+)\b", texto):
        intervalo = conexao.execute("SELECT inicio_id,fim_id,assunto,projeto FROM resumos_conversa WHERE id=?",(int(i),)).fetchone()
        if intervalo:
            mensagens.update(r[0] for r in conexao.execute(
                "SELECT id FROM mensagens WHERE id BETWEEN ? AND ? AND assunto=? AND projeto=? AND ignorar_memoria=0",intervalo
            ))
    for mensagem in mensagens:
        ids.update(r[0] for r in conexao.execute("SELECT memoria_id FROM fontes_memoria WHERE mensagem_id=?",(mensagem,)))
        ids.update(r[0] for r in conexao.execute("SELECT memoria_id FROM dependencias_memoria WHERE resposta_id=?",(mensagem,)))
    conexao.execute("DELETE FROM memorias_no_contexto")
    conexao.executemany("INSERT OR IGNORE INTO memorias_no_contexto VALUES (?)",[(i,) for i in ids])
    conexao.commit()


def vincular_resposta(conexao, identificador):
    with conexao:
        conexao.execute("""INSERT OR IGNORE INTO dependencias_memoria
            SELECT m.id, ? FROM memorias_no_contexto c JOIN memorias m ON m.id=c.id""",(identificador,))


def filtrar_historico(conexao, historico):
    ativo = contexto_ativo(conexao)
    permitidas = []
    for mensagem in historico:
        if "id" in mensagem:
            dados = conexao.execute("SELECT ignorar_memoria,assunto,projeto FROM mensagens WHERE id=?",(mensagem["id"],)).fetchone()
            if not dados or dados[0] or not _no_escopo(dados[1],dados[2],ativo):
                continue
        permitidas.append(mensagem)
    return permitidas


def guardar(conexao, texto, assunto=None, projeto=None, importancia=4, origem=None):
    """Salva ou atualiza um fato, vinculando-o às mensagens que o originaram."""
    texto = texto.strip()
    if not texto or len(texto) > 2000:
        raise ValueError("A lembrança deve ter entre 1 e 2000 caracteres.")
    if not 1 <= int(importancia) <= 5:
        raise ValueError("A importância deve ser de 1 a 5.")
    ativo_assunto, ativo_projeto = contexto_ativo(conexao)
    assunto = ativo_assunto if assunto is None else assunto
    projeto = ativo_projeto if projeto is None else projeto
    normal, chave = normalizar(texto), _chave_fato(texto)
    with conexao:
        existente = conexao.execute(
            "SELECT id FROM memorias WHERE normalizado = ? AND assunto = ? AND projeto = ?",
            (normal, assunto, projeto),
        ).fetchone()
        if not existente and chave:
            existente = conexao.execute(
                "SELECT id FROM memorias WHERE chave = ? AND assunto = ? AND projeto = ? ORDER BY id DESC LIMIT 1",
                (chave, assunto, projeto),
            ).fetchone()
            if existente:
                _suprimir_fontes(conexao, existente[0])
        if existente:
            identificador = existente[0]
            conexao.execute(
                "UPDATE memorias SET conteudo=?,normalizado=?,importancia=MAX(importancia,?),atualizada_em=CURRENT_TIMESTAMP WHERE id=?",
                (texto, normal, importancia, identificador),
            )
            conexao.execute("DELETE FROM vetores_lembrancas WHERE memoria_id=?", (identificador,))
        else:
            identificador = conexao.execute(
                "INSERT INTO memorias(conteudo,normalizado,assunto,projeto,importancia,chave) VALUES (?,?,?,?,?,?)",
                (texto, normal, assunto, projeto, importancia, chave),
            ).lastrowid
        if origem is not None:
            conexao.execute("INSERT OR IGNORE INTO fontes_memoria VALUES (?, ?)", (identificador, origem))
        elif len(normal) >= 8:
            for mid, conteudo in conexao.execute(
                "SELECT id,conteudo FROM mensagens WHERE papel='user' AND ignorar_memoria=0 AND assunto=? AND projeto=?",
                (assunto, projeto),
            ):
                if f" {normal} " in f" {normalizar(conteudo)} ":
                    conexao.execute("INSERT OR IGNORE INTO fontes_memoria VALUES (?,?)", (identificador,mid))
    return identificador


def editar(conexao, identificador, texto, assunto=None, projeto=None, importancia=None):
    """Edita uma memória existente e mantém seus vínculos e o escopo válido."""
    antiga = conexao.execute("SELECT assunto,projeto,importancia FROM memorias WHERE id=?", (identificador,)).fetchone()
    if not antiga:
        raise ValueError("Lembrança não encontrada.")
    texto = texto.strip()
    if not texto or len(texto) > 2000:
        raise ValueError("A lembrança deve ter entre 1 e 2000 caracteres.")
    assunto = antiga[0] if assunto is None else assunto.strip().casefold() or "geral"
    projeto = antiga[1] if projeto is None else projeto.strip().casefold()
    importancia = antiga[2] if importancia is None else int(importancia)
    if not 1 <= importancia <= 5:
        raise ValueError("A importância deve ser de 1 a 5.")
    try:
        with conexao:
            _suprimir_fontes(conexao, identificador)
            conexao.execute(
                "UPDATE memorias SET conteudo=?,normalizado=?,assunto=?,projeto=?,importancia=?,chave=?,atualizada_em=CURRENT_TIMESTAMP WHERE id=?",
                (texto, normalizar(texto), assunto, projeto, importancia, _chave_fato(texto), identificador),
            )
            conexao.execute("DELETE FROM vetores_lembrancas WHERE memoria_id=?", (identificador,))
    except sqlite3.IntegrityError as erro:
        raise ValueError("Já existe uma lembrança igual nesse assunto e projeto.") from erro


def excluir(conexao, identificador):
    """Remove uma memória e suas referências associadas."""
    if not conexao.execute("SELECT 1 FROM memorias WHERE id=?", (identificador,)).fetchone():
        raise ValueError("Lembrança não encontrada.")
    with conexao:
        _suprimir_fontes(conexao, identificador)
        conexao.execute("DELETE FROM fontes_memoria WHERE memoria_id=?", (identificador,))
        conexao.execute("DELETE FROM vetores_lembrancas WHERE memoria_id=?", (identificador,))
        conexao.execute("DELETE FROM dependencias_memoria WHERE memoria_id=?", (identificador,))
        conexao.execute("DELETE FROM memorias WHERE id=?", (identificador,))


def processar_mensagem(conexao, identificador):
    """Extrai e registra fatos de uma mensagem ainda não processada."""
    if conexao.execute("SELECT 1 FROM mensagens_processadas WHERE mensagem_id=?", (identificador,)).fetchone():
        return
    registro = conexao.execute(
        "SELECT conteudo,assunto,projeto FROM mensagens WHERE id=? AND papel='user' AND ignorar_memoria=0", (identificador,)
    ).fetchone()
    if registro:
        fato = detectar_fato(registro[0])
        if fato:
            guardar(conexao, fato, registro[1], registro[2], importancia=3, origem=identificador)
    with conexao:
        conexao.execute("INSERT OR IGNORE INTO mensagens_processadas VALUES (?)", (identificador,))


def processar_pendentes(conexao):
    """Processa em lote as mensagens novas que podem gerar memórias."""
    ultimo_id = 0
    while True:
        ids = conexao.execute("""
            SELECT m.id FROM mensagens m
            LEFT JOIN mensagens_processadas p ON p.mensagem_id=m.id
            WHERE m.papel='user' AND m.ignorar_memoria=0
              AND p.mensagem_id IS NULL AND m.id>?
            ORDER BY m.id LIMIT 100
        """, (ultimo_id,)).fetchall()
        if not ids:
            return
        for identificador, in ids:
            processar_mensagem(conexao, identificador)
        ultimo_id = ids[-1][0]


def listar(conexao, todos=False):
    """Lista memórias do contexto ativo ou de todos os contextos."""
    registros = conexao.execute(
        "SELECT id,conteudo,assunto,projeto,importancia FROM memorias ORDER BY importancia DESC,id DESC"
    ).fetchall()
    assunto, projeto = contexto_ativo(conexao)
    return [r for r in registros if todos or (r[3] == projeto and (assunto == "geral" or r[2] == assunto))]


def _no_escopo(assunto, projeto, ativo):
    a, p = ativo
    return projeto in ("", p) and (a == "geral" or assunto in (a, "geral", "pessoal"))


def preferencias_de_estilo(conexao, limite=3):
    """Obtém preferências de comunicação recentes para orientar respostas."""
    """Recupera preferências explícitas de conversa, mesmo em perguntas de outro tema."""
    ativo = contexto_ativo(conexao)
    preferencias = []
    for identificador, texto, assunto, projeto in conexao.execute(
        "SELECT id,conteudo,assunto,projeto FROM memorias ORDER BY id DESC"
    ):
        if not _no_escopo(assunto, projeto, ativo):
            continue
        frase = normalizar(texto)
        if not re.search(r"\b(?:prefiro|gosto|nao gosto|quero|responda|fale|seja)\b", frase):
            continue
        if not re.search(
            r"\b(?:respost\w*|explica\w*|tom|humor|piad\w*|brincad\w*|"
            r"zoeir\w*|serio\w*|direto\w*|curto\w*|detalhad\w*|"
            r"formal\w*|informal\w*|pacien\w*|calm\w*|giria\w*)\b",
            frase,
        ):
            continue
        preferencias.append(f"Fato #{identificador} [{assunto}; projeto: {projeto or 'geral'}]: {texto[:250]}")
        if len(preferencias) >= limite:
            break
    return preferencias


def recentes(conexao, limite=8):
    """Retorna fatos atualizados recentemente no contexto ativo."""
    ativo = contexto_ativo(conexao)
    registros = conexao.execute(
        "SELECT id,conteudo,assunto,projeto FROM mensagens WHERE papel='user' AND ignorar_memoria=0 ORDER BY id DESC"
    )
    saida = []
    for identificador, texto, assunto, projeto in registros:
        if _no_escopo(assunto, projeto, ativo):
            saida.append(f"Conversa #{identificador} [{assunto}; projeto: {projeto or 'geral'}]: {texto[:450]}")
            if len(saida) >= limite:
                break
    return saida


def _cosseno(a, b):
    if len(a) != len(b) or not a or not all(math.isfinite(x) for x in [*a, *b]):
        return 0
    norma = math.sqrt(sum(x*x for x in a) * sum(x*x for x in b))
    return sum(x*y for x,y in zip(a,b)) / norma if norma else 0


def selecionar(conexao, pergunta, gerar_vetores, modelo, limite=10):
    """Seleciona memórias relevantes por escopo, termos e similaridade semântica."""
    ativo = contexto_ativo(conexao)
    def candidatos():
        for i, texto, assunto, projeto, importancia, vetor in conexao.execute("""
            SELECT m.id,m.conteudo,m.assunto,m.projeto,m.importancia,v.vetor FROM memorias m
            LEFT JOIN vetores_lembrancas v ON v.memoria_id=m.id AND v.modelo=? ORDER BY m.id DESC
        """, (modelo,)):
            if _no_escopo(assunto, projeto, ativo):
                yield "Fato", i, texto, assunto, projeto, importancia, vetor
        for i, texto, assunto, projeto, vetor in conexao.execute("""
            SELECT m.id,m.conteudo,m.assunto,m.projeto,v.vetor FROM mensagens m
            LEFT JOIN vetores_memoria v ON v.mensagem_id=m.id AND v.modelo=?
            WHERE m.papel='user' AND m.ignorar_memoria=0 ORDER BY m.id DESC
        """, (modelo,)):
            if _no_escopo(assunto, projeto, ativo):
                yield "Conversa", i, texto, assunto, projeto, 1, vetor
        for i, texto, assunto, projeto in conexao.execute(
            "SELECT id,conteudo,assunto,projeto FROM resumos_conversa ORDER BY id DESC"
        ):
            if _no_escopo(assunto, projeto, ativo):
                yield "Resumo", i, texto, assunto, projeto, 2, None

    consulta = set(normalizar(pergunta).split()) - STOPWORDS
    vetor_pergunta = None
    possui_vetores = conexao.execute("""
        SELECT EXISTS(
            SELECT 1 FROM vetores_lembrancas v JOIN memorias m ON m.id=v.memoria_id
            WHERE v.modelo=? AND (m.projeto='' OR m.projeto=?)
              AND (?='geral' OR m.assunto IN (?, 'geral', 'pessoal')) LIMIT 1
        ) OR EXISTS(
            SELECT 1 FROM vetores_memoria v JOIN mensagens m ON m.id=v.mensagem_id
            WHERE v.modelo=? AND m.ignorar_memoria=0
              AND (m.projeto='' OR m.projeto=?)
              AND (?='geral' OR m.assunto IN (?, 'geral', 'pessoal')) LIMIT 1
        )
    """, (modelo, ativo[1], ativo[0], ativo[0], modelo, ativo[1], ativo[0], ativo[0])).fetchone()[0]
    if possui_vetores:
        try:
            vetor_pergunta = gerar_vetores([pergunta])[0]
        except Exception as erro:
            diagnostico.registrar("memoria.busca_semantica_falhou", erro=erro)
            print("[MEMÓRIA] Busca semântica indisponível; usando texto e registros recentes.")
    ampla = bool(re.search(r"convers|lembran|lembra|mem[oó]ria", pergunta.casefold()))
    classificados = []
    capacidade = max(500, limite * 50)
    for ordem, (tipo,i,texto,assunto,projeto,importancia,vetor) in enumerate(candidatos()):
        palavras = set(normalizar(texto + " " + assunto + " " + projeto).split()) - STOPWORDS
        lexical = len(consulta & palavras) / max(1, len(consulta))
        semantico = 0
        if vetor_pergunta is not None and vetor:
            try:
                semantico = _cosseno(vetor_pergunta, json.loads(vetor))
            except (ValueError, TypeError, OverflowError):
                pass
        if not lexical and semantico < 0.45 and not (ampla and tipo != "Conversa"):
            continue
        score = lexical * 4 + max(0, semantico) * 2 + importancia * 0.12 + 0.1/(1+ordem)
        if projeto == ativo[1] and projeto:
            score += 0.4
        if assunto == ativo[0] and assunto != "geral":
            score += 0.2
        item = (score, -ordem, tipo, i, texto, assunto, projeto)
        if len(classificados) < capacidade:
            heapq.heappush(classificados, item)
        elif item > classificados[0]:
            heapq.heapreplace(classificados, item)
    vistos, selecionados, por_assunto = set(), [], {}
    for _, _, tipo, i, texto, assunto, projeto in sorted(classificados, reverse=True):
        normal = normalizar(texto)
        if normal in vistos or por_assunto.get(assunto, 0) >= max(3, limite // 2):
            continue
        vistos.add(normal)
        por_assunto[assunto] = por_assunto.get(assunto,0) + 1
        tamanho = 1800 if tipo == "Resumo" else 1200 if tipo == "Fato" else 450
        selecionados.append(f"{tipo} #{i} [{assunto}; projeto: {projeto or 'geral'}]: {texto[:tamanho]}")
        if len(selecionados) >= limite:
            break
    return selecionados


def indexar_fatos(conexao, gerar_vetores, modelo):
    """Gera e atualiza vetores dos fatos que ainda não foram indexados."""
    pendentes = conexao.execute("""
        SELECT m.id,m.conteudo FROM memorias m LEFT JOIN vetores_lembrancas v
        ON v.memoria_id=m.id AND v.modelo=? WHERE v.memoria_id IS NULL
    """, (modelo,)).fetchall()
    for inicio in range(0,len(pendentes),16):
        lote = pendentes[inicio:inicio+16]
        vetores = gerar_vetores([r[1] for r in lote])
        if len(vetores) != len(lote):
            raise ValueError("A indexação retornou uma quantidade inesperada de vetores.")
        with conexao:
            conexao.executemany(
                "INSERT OR REPLACE INTO vetores_lembrancas VALUES (?,?,?)",
                [(i,modelo,json.dumps(v)) for (i,_),v in zip(lote,vetores)],
            )


def tratar_comando(conexao, texto):
    """Executa comandos de memória e retorna resposta ou None para conversa normal."""
    texto = texto.strip()
    if normalizar(texto) in {"memorias", "listar memorias", "minhas memorias"} or texto == "/memorias":
        registros = listar(conexao, todos=True)
        return "\n".join(f"#{i} [{a}; {p or 'geral'}; importância {v}]: {t}" for i,t,a,p,v in registros) or "Nenhuma lembrança importante salva."
    if texto.startswith("/lembrar "):
        i = guardar(conexao, texto[len("/lembrar "):])
        return f"Lembrança #{i} salva."
    natural = re.match(r"(?is)^(?:lembre[- ]se de que|lembre que|guarde (?:esta |essa )?informa[çc][ãa]o\s*:?)\s+(.+)", texto)
    if natural:
        return f"Lembrança #{guardar(conexao,natural.group(1))} salva."
    editar_match = re.fullmatch(r"(?is)/memoria editar\s+(\d+)\s+(.+)", texto)
    if editar_match:
        editar(conexao,int(editar_match[1]),editar_match[2])
        return f"Lembrança #{editar_match[1]} atualizada. As fontes antigas foram retiradas do contexto."
    apagar = re.fullmatch(r"(?is)(?:/memoria excluir|exclua a mem[oó]ria|esque[çc]a a mem[oó]ria)\s+#?(\d+)[.!]?", texto)
    if apagar:
        excluir(conexao,int(apagar[1]))
        return f"Lembrança #{apagar[1]} excluída do sistema de memória."
    escopo = re.fullmatch(r"(?is)/(assunto|projeto)\s+(.+)", texto)
    if escopo:
        a,p = definir_contexto(conexao, **{escopo[1].lower():escopo[2]})
        return f"Contexto ativo: assunto {a}; projeto {p or 'geral'}."
    if normalizar(texto) in {"resumir conversa", "resuma nossa conversa"} or texto == "/resumir":
        n = resumos.resumir_pendentes(conexao, forcar=True, escopo=contexto_ativo(conexao))
        return f"Resumos criados: {n}." if n else "Não há novos trechos completos para resumir."
    if texto.startswith(("/memoria", "/lembrar", "/assunto", "/projeto", "/resumir")):
        return "Use /memorias, /lembrar FATO, /memoria editar ID TEXTO, /memoria excluir ID, /assunto NOME, /projeto NOME ou /resumir."
    return None


def gerenciar(conexao, ler_texto):
    """Apresenta o menu interativo de consulta e manutenção da memória."""
    from controles import SolicitarMenu

    while True:
        assunto, projeto = contexto_ativo(conexao)
        print(f"\n===== MEMÓRIAS | {assunto} | {projeto or 'sem projeto'} =====")
        print("1 - Listar lembranças (todos os assuntos/projetos)")
        print("2 - Guardar uma lembrança importante")
        print("3 - Editar lembrança, assunto, projeto ou importância")
        print("4 - Excluir uma lembrança pelo ID")
        print("5 - Escolher assunto e projeto ativos")
        print("6 - Gerar e consultar resumos do contexto ativo")
        print("0 - Voltar (ou Esc)")
        try:
            opcao = ler_texto("Opção: ").strip()
            if opcao == "0":
                return
            if opcao == "1":
                print(tratar_comando(conexao,"/memorias"))
            elif opcao == "2":
                texto = ler_texto("Fato a guardar: ").strip()
                importancia = int(ler_texto("Importância de 1 a 5 (Enter = 4): ").strip() or "4")
                print(f"Lembrança #{guardar(conexao,texto,importancia=importancia)} salva.")
            elif opcao == "3":
                identificador = int(ler_texto("ID da lembrança a editar: "))
                registro = conexao.execute("SELECT conteudo,assunto,projeto,importancia FROM memorias WHERE id=?",(identificador,)).fetchone()
                if not registro:
                    raise ValueError("Lembrança não encontrada.")
                print(f"Atual: {registro[0]} [{registro[1]}; {registro[2] or 'sem projeto'}; importância {registro[3]}]")
                texto = ler_texto("Novo texto (Enter mantém): ").strip() or registro[0]
                novo_assunto = ler_texto("Assunto (Enter mantém): ").strip() or registro[1]
                novo_projeto = ler_texto("Projeto (Enter mantém; 'nenhum' remove): ").strip() or registro[2]
                if normalizar(novo_projeto) == "nenhum":
                    novo_projeto = ""
                importancia = int(ler_texto("Importância 1 a 5 (Enter mantém): ").strip() or registro[3])
                editar(conexao,identificador,texto,novo_assunto,novo_projeto,importancia)
                print("Lembrança atualizada; fontes antigas removidas do contexto.")
            elif opcao == "4":
                identificador = int(ler_texto("ID da lembrança a excluir: "))
                excluir(conexao,identificador)
                print(f"Lembrança #{identificador} excluída do sistema de memória.")
            elif opcao == "5":
                novo_assunto = ler_texto("Assunto ativo (Enter mantém; 'geral' remove filtro): ").strip() or assunto
                novo_projeto = ler_texto("Projeto ativo (Enter mantém; 'nenhum' remove): ").strip() or projeto
                definir_contexto(conexao,novo_assunto,novo_projeto)
                print("Contexto atualizado. As novas conversas usarão esse assunto e projeto.")
            elif opcao == "6":
                print(tratar_comando(conexao,"/resumir"))
                linhas = conexao.execute(
                    "SELECT conteudo FROM resumos_conversa WHERE assunto=? AND projeto=? ORDER BY id DESC LIMIT 5", (assunto,projeto)
                ).fetchall()
                for linha, in linhas:
                    print("\n" + linha)
            else:
                print("Opção inválida.")
        except SolicitarMenu:
            return
        except ValueError as erro:
            print(f"Não foi possível concluir: {erro}")
