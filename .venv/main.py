import sqlite3
from pathlib import Path
from ollama import chat

# Configurações
MODELO = "qwen3:8b"
BANCO = Path(__file__).resolve().parent / "memoria.db"

PERSONALIDADE = """
Você é uma inteligência artificial pessoal.

Suas características:
- Responda sempre em português brasileiro.
- Seja amigável, inteligente e prestativa.
- Ajude com programação e estudos.
- Explique conceitos de maneira didática.
- Utilize as informações disponíveis na conversa.
- Não invente lembranças que não estejam no histórico.
"""

# Conexão com o banco de dados
conexao = sqlite3.connect(BANCO)

# Criação da tabela
conexao.execute("""
CREATE TABLE IF NOT EXISTS mensagens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    papel TEXT NOT NULL,
    conteudo TEXT NOT NULL,
    data TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

conexao.commit()


def carregar_memoria():
    """Recupera as últimas 30 mensagens salvas."""

    cursor = conexao.execute("""
        SELECT papel, conteudo
        FROM mensagens
        ORDER BY id DESC
        LIMIT 30
    """)

    registros = cursor.fetchall()

    historico = [
        {
            "role": "system",
            "content": PERSONALIDADE
        }
    ]

    for papel, conteudo in reversed(registros):
        historico.append({
            "role": papel,
            "content": conteudo
        })

    return historico


def salvar_conversa(pergunta, resposta):
    """Armazena a pergunta e a resposta no SQLite."""

    with conexao:
        conexao.execute(
            "INSERT INTO mensagens (papel, conteudo) VALUES (?, ?)",
            ("user", pergunta)
        )

        conexao.execute(
            "INSERT INTO mensagens (papel, conteudo) VALUES (?, ?)",
            ("assistant", resposta)
        )


def iniciar_ia():
    """Inicializa a conversa com memória."""

    historico = carregar_memoria()

    print("\nIA iniciada com memória permanente!")
    print("Digite 'sair' para encerrar.\n")

    while True:
        pergunta = input("Você: ").strip()

        if pergunta.lower() == "sair":
            print("\nIA: Até a próxima!")
            break

        if not pergunta:
            continue

        mensagem = {
            "role": "user",
            "content": pergunta
        }

        try:
            resposta = chat(
                model=MODELO,
                messages=historico + [mensagem]
            )

            texto = resposta.message.content

            if not texto:
                print("IA: Não consegui gerar uma resposta.")
                continue

            print(f"\nIA: {texto}\n")

            salvar_conversa(pergunta, texto)

            historico.append(mensagem)

            historico.append({
                "role": "assistant",
                "content": texto
            })

        except Exception as erro:
            print(f"Erro: {erro}")


try:
    iniciar_ia()

except KeyboardInterrupt:
    print("\nPrograma encerrado.")

finally:
    conexao.close()