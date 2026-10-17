# Desempenho, diagnóstico e recuperação

O Ollama usa o modelo principal `qwen3:8b` e o de memória
`qwen3-embedding:0.6b` localmente. Neste computador, a RTX 3060 tem 12 GB e
ambos os modelos foram carregados simultaneamente na GPU. O programa usa o
mesmo contexto de 8.192 tokens nas chamadas de conversa e de planejamento,
mantém o modelo principal carregado por 15 minutos e o de embeddings por
5 minutos após cada uso. Isso evita recarregamentos frequentes; outros
programas abertos também consomem a memória da placa.
Cumprimentos e agradecimentos curtos dispensam a chamada extra de planejamento
de pesquisa. Perguntas sobre fatos atuais continuam passando pelo planejamento
e exigem autorização antes de qualquer acesso à internet.
Na recuperação de lembranças, o programa percorre o histórico inteiro, mas
mantém apenas os candidatos mais relevantes em uma lista de tamanho limitado.
A indexação inicial também processa mensagens em lotes.

O reconhecimento de voz prepara os modelos em segundo plano ao entrar no
modo de áudio. O detector de fala já decide quando a gravação terminou;
o Whisper não repete essa etapa na transcrição. Se as bibliotecas CUDA do
Whisper estiverem disponíveis, ele tenta usar a GPU com `int8_float16`.
Caso contrário, usa a CPU com `int8` e quatro threads. Neste computador,
o teste de execução na GPU do Whisper falhou pela ausência de
`cublas64_12.dll`, por isso a transcrição fica na CPU. O Ollama continua
usando a RTX 3060.
As bibliotecas necessárias para ativar a transcrição na GPU estão descritas
pelo [projeto faster-whisper](https://github.com/SYSTRAN/faster-whisper#gpu).

## Recuperação de falhas

- **Ollama:** uma falha transitória de conexão recebe uma nova tentativa.
  Depois disso, a pergunta continua salva no banco e o terminal mostra
  como verificar o serviço e os modelos.
- **Microfone:** após três falhas consecutivas, o programa volta à digitação.
  Digite `voz` para tentar de novo após corrigir o dispositivo.
- **Voz sintetizada:** se o serviço online falhar, a voz local assume. Se o
  dispositivo de saída ou a voz local falhar, a resposta continua disponível
  no terminal e no histórico.
- **Memória:** uma falha de indexação não apaga a conversa; a busca por texto
  e os registros recentes continuam disponíveis.

Os eventos técnicos ficam em `logs/assistente.log`, com rotação de 2 MB e
três arquivos antigos. O log registra horários UTC, duração, códigos de
etapa, contagens e o **tipo** de erro. Ele não registra perguntas, respostas,
transcrições, URLs, consultas ou mensagens completas de exceção. Os logs
e os backups são ignorados pelo Git.

## Backup e restauração

O programa faz um backup SQLite validado após abrir o banco e, depois,
no máximo uma vez a cada 24 horas de uso. Mantém as sete cópias automáticas
mais recentes em `backups/`. Backups manuais e as cópias criadas antes de
uma restauração ficam preservados até você removê-los. A criação usa a API
de backup do SQLite, inclusive com o programa aberto, e verifica a
integridade da cópia antes de publicá-la.

Para listar ou criar um backup manual:

```powershell
.\.venv\Scripts\python.exe banco.py listar
.\.venv\Scripts\python.exe banco.py backup
```

Para restaurar, **feche o assistente** e use exatamente um nome exibido
pelo comando `listar`:

```powershell
.\.venv\Scripts\python.exe banco.py restaurar manual_20261016T120000Z_1234abcd.db
```

O nome acima é apenas um exemplo. A restauração verifica a integridade e
as tabelas da cópia. Antes de trocar o banco atual, cria um backup adicional
com prefixo `antes_restauro_`. Se a cópia for inválida, o banco atual não é
alterado. Um arquivo SQLite ativo em modo WAL precisa ser fechado antes.

O banco e as cópias são arquivos locais **sem criptografia própria**. A
proteção contra leitura por outros usuários depende das permissões do
Windows e da criptografia do disco, como BitLocker. Mantenha sua conta do
Windows protegida e não compartilhe a pasta `backups/`.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

A suíte inclui mil ciclos simulados de gravação, fechamento, reabertura
e verificação do banco e uma sessão de 120 perguntas com falha recuperável
do Ollama. Também verifica histórico grande, corrupção de cópia, restauração,
queda da GPU do Whisper e falhas repetidas do microfone. Esses testes não
substituem uma sessão de áudio de várias horas com o microfone e
alto-falantes reais.
