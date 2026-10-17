# Assistente Pessoal Local com IA

Assistente pessoal em Python, desenvolvido para conversar em português
brasileiro, preservar memória entre sessões e alternar entre interação por
texto e por voz. A geração de respostas e os embeddings são executados
localmente pelo [Ollama](https://ollama.com/), enquanto a pesquisa na internet
é opcional, limitada e sempre depende de autorização.

O projeto foi pensado como uma base extensível para estudos de inteligência
artificial aplicada, memória persistente, reconhecimento de voz, síntese de
fala e recuperação de informação.

## Visão geral

O assistente oferece:

- Conversa em modo texto ou microfone.
- Respostas geradas por um modelo local do Ollama.
- Memória persistente em SQLite.
- Recuperação semântica de lembranças usando embeddings.
- Organização da memória por assunto e projeto.
- Resumos persistentes de conversas longas.
- Comandos explícitos para salvar, listar, editar e excluir lembranças.
- Pesquisa na internet com autorização por consulta.
- Limites de consultas, páginas, tamanho de conteúdo e contexto.
- Filtros para conteúdo adulto e fontes não públicas.
- Voz online com alternativa local usando Piper.
- Reconhecimento de fala com Faster-Whisper.
- Interrupção da fala por teclado ou palavra de ativação.
- Backups automáticos e restauração validada do banco SQLite.
- Logs técnicos rotativos sem registrar o conteúdo das conversas.
- Testes automatizados para os principais componentes.

## Arquitetura

O fluxo principal está concentrado em `main.py`, que coordena os módulos:

| Módulo | Responsabilidade |
| --- | --- |
| `main.py` | Inicialização, ciclo de conversa, Ollama e integração dos recursos |
| `memoria.py` | Fatos persistentes, escopos, busca e gerenciamento da memória |
| `resumos.py` | Resumos de conversas antigas e recuperação histórica |
| `banco.py` | Backups, integridade e restauração do SQLite |
| `internet.py` | Planejamento, busca, leitura e filtragem de fontes |
| `voz.py` | Captura e transcrição de áudio com Faster-Whisper |
| `fala.py` | Síntese de fala online e local |
| `ativacao.py` | Palavra de ativação e interrupção durante a fala |
| `controles.py` | Entrada de teclado e controles de interação |
| `diagnostico.py` | Eventos técnicos e logs rotativos |

### Modelos padrão

O projeto usa, por padrão:

- `qwen3:8b`: geração de respostas e planejamento de pesquisas.
- `qwen3-embedding:0.6b`: embeddings para recuperação semântica.
- `pt_BR-faber-medium.onnx`: voz local de reserva do Piper.
- Faster-Whisper: reconhecimento de fala em português.

O cliente Ollama é configurado para `http://127.0.0.1:11434`. Assim, as
conversas não são enviadas para outro host por uma configuração remota
acidental do cliente.

## Requisitos

### Requisitos gerais

- Windows, Linux ou macOS.
- Python 3.9 ou superior.
- Git, caso o projeto seja obtido por clone.
- Ollama instalado e em execução.
- Espaço em disco para os modelos de IA.
- Microfone e saída de áudio para usar os modos de voz.

O modo texto depende apenas do Python, das dependências do projeto e do
Ollama. O modo de voz exige dependências adicionais e pode exigir configuração
específica do dispositivo de áudio ou de aceleração por GPU.

### Hardware

O modo texto pode funcionar em máquinas mais simples, dependendo do modelo
escolhido. O modelo padrão `qwen3:8b`, embeddings, transcrição e síntese de
voz consomem mais memória e podem se beneficiar de uma GPU compatível.

Se a GPU não estiver disponível para a transcrição, o código tenta usar a CPU
quando possível. O desempenho dependerá do hardware e da configuração local.

## Instalação

### 1. Obter o projeto

```powershell
git clone https://github.com/Raphazoc/assistente_ia.git
cd assistente_ia
```

### 2. Criar e ativar um ambiente virtual

No Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

No Linux ou macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependências

Para usar o modo texto e os recursos de pesquisa:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Para habilitar reconhecimento e síntese de voz:

```powershell
python -m pip install -r requirements-voz.txt
```

O arquivo `requirements-voz.txt` inclui Faster-Whisper, Piper, Edge-TTS,
SoundDevice e bibliotecas de suporte a áudio.

### 4. Instalar e preparar o Ollama

Instale o Ollama pelo site oficial e confirme que o serviço está ativo.
Depois, baixe os modelos utilizados pelo projeto:

```powershell
ollama pull qwen3:8b
ollama pull qwen3-embedding:0.6b
```

Teste a instalação:

```powershell
ollama list
```

Os nomes dos modelos precisam corresponder às constantes definidas em
`main.py`. Se você optar por outros modelos, altere `MODELO` e
`MODELO_MEMORIA` de acordo com os modelos instalados.

## Executando

Para usar a janela Windows instalável, veja [INSTALACAO.md](INSTALACAO.md).
Ela mostra Escrita e Áudio em dois painéis lado a lado, sem sobreposição.
O modo por terminal abaixo continua disponível.

Na raiz do projeto, com o ambiente virtual ativado:

```powershell
python main.py
```

Na inicialização, o programa:

1. Abre ou cria `memoria.db`.
2. Atualiza a estrutura do banco quando necessário.
3. Processa memórias e resumos pendentes.
4. Tenta indexar lembranças semanticamente.
5. Cria um backup automático quando necessário.
6. Exibe o menu para escolher texto ou voz.

Para encerrar uma sessão, use `sair`, `encerrar` ou `desligar assistente`.
Também é possível abrir o menu digitando `menu` ou pressionando `Esc`.

## Modos de interação

### Digitação

Escolha `1` no menu inicial ou digite `texto`. As mensagens são digitadas
diretamente no terminal.

### Voz

Escolha `2` no menu inicial ou digite `voz`. O assistente captura o áudio,
transcreve a fala e responde usando síntese de voz.

Durante a fala:

- `Espaço` interrompe a reprodução.
- `Esc` interrompe e abre o menu.
- A palavra de ativação seguida de `pare` interrompe por voz.
- A palavra de ativação seguida de um novo pedido interrompe a resposta e
  encaminha o novo pedido.

A palavra de ativação padrão é `Aurora`. Ela pode ser alterada pela opção `3`
do menu. O valor é salvo em `config_voz.json`.

### Comandos rápidos

| Comando | Ação |
| --- | --- |
| `menu` | Abre o menu principal |
| `texto` / `modo texto` | Muda para digitação |
| `voz` / `modo voz` | Muda para o microfone |
| `sair` | Encerra o assistente |
| `/memorias` | Lista as lembranças salvas |
| `/lembrar TEXTO` | Salva uma lembrança |
| `/memoria editar ID TEXTO` | Edita uma lembrança |
| `/memoria excluir ID` | Exclui uma lembrança |
| `/assunto NOME` | Define o assunto ativo |
| `/projeto NOME` | Define o projeto ativo |
| `/resumir` | Gera resumo do contexto atual |
| `/pesquisar ASSUNTO` | Solicita pesquisa na internet |

Também são reconhecidas frases naturais como `lembre que...` e `guarde esta
informação...`.

## Memória persistente

As mensagens e lembranças são armazenadas no banco local `memoria.db`, que não
deve ser versionado. A memória possui:

- Fatos e preferências duráveis.
- Associação entre lembranças e mensagens de origem.
- Importância de 1 a 5.
- Assunto e projeto ativos.
- Busca textual e recuperação semântica.
- Resumos de conversas extensas.
- Exclusão e edição com remoção das associações antigas de contexto.

Para separar contextos, por exemplo:

```text
/assunto estudos
/projeto assistente pessoal
/lembrar estou estudando recuperação semântica
```

O histórico completo continua no banco, mas apenas uma seleção relevante é
enviada ao modelo em cada resposta. Isso reduz o contexto e evita tratar todo
o histórico como instrução ativa.

## Pesquisa na internet

A pesquisa é desativada por padrão em `config_internet.json`:

```json
{
  "ativa": true
}
```

Ela também pode ser ativada ou desativada pela opção `5` do menu. Mesmo
habilitada, cada consulta exige autorização explícita. A pesquisa:

- Decide se uma pergunta realmente precisa de informação externa.
- Limita o plano a duas consultas.
- Limita resultados, páginas lidas e bytes processados.
- Aceita apenas URLs HTTP/HTTPS públicas.
- Bloqueia endereços locais, portas não permitidas e fontes adultas.
- Trata o conteúdo das páginas como dado não confiável.
- Anexa fontes e horário da consulta à resposta quando a pesquisa é concluída.

Para solicitar uma consulta diretamente, use:

```text
/pesquisar versão atual do Python
```

Não habilite esse recurso se o objetivo for executar o programa totalmente
offline. A geração da resposta e a memória permanecem locais, mas o recurso
de pesquisa acessa serviços externos quando autorizado.

## Voz e áudio

A fala usa uma estratégia de fallback:

1. Tenta a voz neural online configurada em `fala.py`.
2. Se o serviço online falhar, usa a voz local Piper.

O modelo local esperado é:

```text
vozes/pt_BR-faber-medium.onnx
vozes/pt_BR-faber-medium.onnx.json
```

Para testar a transcrição de voz isoladamente:

```powershell
python voz.py
```

Para testar a síntese de fala:

```powershell
python fala.py
```

O modo de voz pode precisar de permissões do sistema operacional, drivers de
áudio e configuração do dispositivo padrão. A indisponibilidade do microfone
não impede o uso do modo texto.

## Backups e restauração

O assistente cria backups automáticos do SQLite em `backups/`, mantendo as
últimas cópias automáticas conforme a política do módulo `banco.py`.

Listar backups:

```powershell
python banco.py listar
```

Criar backup manual:

```powershell
python banco.py backup
```

Restaurar um backup listado:

```powershell
python banco.py restaurar NOME_DO_BACKUP.db
```

Antes de restaurar:

- Feche o assistente.
- Execute `listar` e copie exatamente o nome retornado.
- Não altere manualmente os arquivos dentro de `backups/`.

O processo valida a integridade do backup e cria uma cópia de segurança do
banco atual antes de substituir o arquivo.

## Diagnóstico e logs

Eventos técnicos são gravados em:

```text
logs/assistente.log
```

O log usa rotação e registra códigos de evento, duração, quantidade e tipo da
exceção. O conteúdo das mensagens, respostas e pesquisas não é registrado
pelo módulo de diagnóstico.

Arquivos locais gerados pelo uso, como `memoria.db`, `backups/`, `logs/`,
ambientes virtuais e caches, estão no `.gitignore` para evitar o envio de
dados pessoais ou artefatos de execução ao repositório.

## Testes

Com as dependências instaladas, execute:

```powershell
python -m pytest
```

Os testes ficam em `tests/` e cobrem, entre outros pontos:

- Ativação e interrupção por voz.
- Controles de entrada.
- Memória e comandos persistentes.
- Síntese e limpeza de texto para fala.
- Filtros e planejamento de pesquisa.
- Confiabilidade, backups e diagnósticos.

Para executar um arquivo específico:

```powershell
python -m pytest tests/test_memoria.py
python -m pytest tests/test_internet.py
```

## Estrutura do repositório

```text
.
├── main.py                 # Entrada e ciclo principal
├── memoria.py              # Memória e recuperação
├── resumos.py              # Resumos persistentes
├── internet.py             # Pesquisa autorizada
├── banco.py                # Backup e restauração
├── voz.py                  # Reconhecimento de fala
├── fala.py                 # Síntese de fala
├── ativacao.py             # Palavra de ativação
├── controles.py            # Teclado e exceções de controle
├── diagnostico.py          # Logs técnicos
├── config_voz.json         # Preferências de ativação
├── config_internet.json    # Ativação da pesquisa
├── docs/                   # Documentação detalhada dos subsistemas
├── vozes/                  # Modelo local de voz
├── tests/                  # Testes automatizados
├── requirements.txt        # Dependências gerais
└── requirements-voz.txt    # Dependências de áudio e voz
```

## Privacidade e segurança

Este projeto prioriza execução local, mas alguns recursos têm comportamentos
distintos:

- O Ollama é acessado pelo endereço local `127.0.0.1`.
- As conversas persistem em um banco SQLite local.
- A pesquisa na internet envia consultas somente quando habilitada e
  autorizada.
- A voz online envia o texto da resposta ao provedor de síntese configurado.
- A voz local Piper evita esse envio durante o fallback local.
- O banco e os logs são ignorados pelo Git.
- O conteúdo recuperado da internet não é tratado como instrução confiável.

Revise `fala.py`, `internet.py` e as configurações locais antes de usar o
projeto em um ambiente com requisitos específicos de privacidade.

## Limitações conhecidas

- A qualidade e a velocidade das respostas dependem do modelo Ollama e do
  hardware disponível.
- A transcrição e a reprodução de áudio dependem dos drivers e dispositivos
  do sistema.
- A voz online requer conectividade; a voz local requer o modelo Piper.
- A pesquisa na internet não garante que todas as fontes sejam acessíveis ou
  que o conteúdo esteja atualizado.
- A memória semântica depende do modelo de embeddings; se o modelo estiver
  indisponível, o programa mantém a conversa e pode usar busca textual.
- O programa foi projetado para uso local e interativo, não para atender
  múltiplos usuários simultaneamente.

## Contribuição

Antes de propor alterações:

1. Crie um ambiente virtual.
2. Execute os testes existentes.
3. Mantenha dados pessoais fora do Git.
4. Atualize a documentação quando alterar comandos ou configurações.
5. Adicione testes para novos comportamentos.

Pull requests devem explicar o problema, a solução, os impactos de privacidade
e como a alteração foi validada.

## Documentação complementar

As explicações detalhadas de cada subsistema ficam na pasta [`docs/`](./docs/):

- [Memória e resumos](./docs/MEMORIA.md)
- [Pesquisa na internet](./docs/INTERNET.md)
- [Voz e áudio](./docs/VOZ.md)
- [Confiabilidade, diagnóstico e recuperação](./docs/CONFIABILIDADE.md)

## Licença

O código-fonte deste projeto é distribuído sob a [Licença MIT](./LICENSE).

Isso permite usar, copiar, modificar e redistribuir o código, inclusive em
projetos comerciais, desde que o aviso de copyright e o texto da licença sejam
mantidos. O software é fornecido "como está", sem garantias.

A Licença MIT se aplica ao código deste projeto criado por seus autores. Os
modelos de IA, bibliotecas, vozes, dados e serviços de terceiros utilizados
podem possuir licenças e termos próprios, que continuam válidos
independentemente da licença deste repositório.

Entre os componentes que devem ser verificados separadamente estão:

- Ollama e os modelos `qwen3:8b` e `qwen3-embedding:0.6b`;
- Faster-Whisper e seus modelos de reconhecimento;
- Piper e o modelo `vozes/pt_BR-faber-medium.onnx`;
- Edge-TTS e o serviço online de síntese de voz;
- Bibliotecas instaladas por `requirements.txt` e `requirements-voz.txt`;
- Serviços externos acessados pelo recurso opcional de pesquisa.

Antes de redistribuir esses componentes, confirme os termos oficiais de cada
projeto, modelo ou serviço. A Licença MIT deste repositório não transforma
componentes de terceiros em software MIT nem concede direitos sobre eles.
