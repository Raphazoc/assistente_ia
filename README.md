# Assistente Pessoal Local com IA

> **Status: Beta em testes.** Versão do aplicativo: `v0.5.3`. O projeto ainda
> está em validação e pode mudar antes de uma versão estável.

Assistente pessoal em Python, desenvolvido para conversar em português
brasileiro, preservar memória entre sessões e alternar entre interação por
texto e por voz. A geração de respostas e os embeddings são executados
localmente pelo [Ollama](https://ollama.com/), enquanto a pesquisa na internet
é opcional, limitada e sempre depende de autorização.

O projeto foi pensado como uma base extensível para estudos de inteligência
artificial aplicada, memória persistente, reconhecimento de voz, síntese de
fala e recuperação de informação.

Há duas formas de uso:

- **Terminal**, executada por `main.py`, com menu para texto e voz.
- **Aplicativo desktop para Windows**, executado por `app/aplicativo.py` ou pelo
  instalador gerado em `dist-installer/`.

## Visão geral

Veja a [prévia visual da nova interface](./docs/interface-conceito.png) e as
[capturas do aplicativo em Texto](./docs/interface-texto-real.png) e
[Voz](./docs/interface-voz-real.png). A prévia é um conceito; as capturas mostram
a implementação atual no Windows. As abas mantêm texto e voz separados, e cada
mensagem aparece em um cartão próprio. A interface usa CustomTkinter para os
painéis, botões e rolagem arredondados.

Veja também as abas reais de [Configurações](./docs/interface-configuracoes-real.png),
[Pesquisa](./docs/interface-configuracoes-pesquisa.png),
[Voz](./docs/interface-configuracoes-voz.png) e
[Diagnóstico](./docs/interface-configuracoes-diagnostico.png).

O assistente oferece:

- Conversa em modo texto ou microfone.
- Respostas geradas por um modelo local do Ollama.
- Memória persistente em SQLite.
- Recuperação semântica de lembranças usando embeddings.
- Organização da memória por assunto e projeto.
- Resumos persistentes de conversas longas.
- Comandos explícitos para salvar, listar, editar e excluir lembranças.
- Pesquisa na internet com autorização por consulta.
- Ações locais limitadas, como abrir programas, sites e pastas, listar pastas,
  ler arquivos de texto, criar pastas e mover arquivos comuns.
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
| `app/aplicativo.py` | Interface desktop Windows e processamento fora da thread da interface |
| `app/memoria.py` | Fatos persistentes, escopos, busca e gerenciamento da memória |
| `app/resumos.py` | Resumos de conversas antigas e recuperação histórica |
| `app/banco.py` | Backups, integridade e restauração do SQLite |
| `app/conversa.py` | Ordem compartilhada de ação, pesquisa e resposta no desktop e terminal |
| `app/servico_ollama.py` | Chamadas locais, retry e diagnóstico do Ollama |
| `app/contexto_memoria.py` | Seleção e limites do contexto de memória |
| `app/coordenador_acoes.py` | Confirmação e execução de ações locais |
| `app/internet.py` | Planejamento, busca, leitura e filtragem de fontes |
| `app/acoes.py` | Planejamento, confirmação, validação e execução de ações locais |
| `app/voz.py` | Captura e transcrição de áudio com Faster-Whisper |
| `app/fala.py` | Síntese de fala online e local |
| `app/ativacao.py` | Palavra de ativação e interrupção durante a fala |
| `app/controles.py` | Entrada de teclado e controles de interação |
| `app/diagnostico.py` | Eventos técnicos e logs rotativos |

### Modelos padrão

O projeto usa, por padrão:

- `qwen3:8b`: geração de respostas e planejamento de pesquisas.
- `qwen3-embedding:0.6b`: embeddings para recuperação semântica.
- `pt_BR-faber-medium.onnx`: voz local de reserva do Piper.
- Faster-Whisper: reconhecimento de fala em português.

O cliente Ollama é configurado para `http://127.0.0.1:11434`. Assim, as
conversas não são enviadas para outro host por uma configuração remota
acidental do cliente.

## Requisitos mínimos

====================================================
### Configuração Local usada para criar e testar o projeto.

Processador (CPU)	Intel Core i5-10400F - 2,90 GHz
Placa de vídeo (GPU)	NVIDIA GeForce RTX 3060 - GPU (VRAM)	12 GB
Memória RAM	32 GB DDR4 - 3200MHz

====================================================


### Sistema operacional

- Windows 10 ou Windows 11, 64 bits.
- O modo desktop e o instalador foram preparados para Windows.
- O modo terminal pode funcionar em Linux ou macOS, mas o foco principal é
  Windows.

### Hardware mínimo recomendado

- **Processador:** 4 núcleos.
- **Memória RAM:** 8 GB no mínimo; 16 GB recomendado.
- **Armazenamento:** pelo menos 15 GB livres.
- **Microfone e alto-falantes:** necessários somente para os recursos de voz.
- **GPU:** opcional. O reconhecimento de voz pode funcionar pela CPU, mas
  ficará mais lento.

### Dependências obrigatórias

Para executar o código-fonte:

- Python 3.13 ou superior;
- Ambiente virtual recomendado;
- Ollama instalado e em execução;
- Modelo principal `qwen3:8b`;
- Modelo de embeddings `qwen3-embedding:0.6b`.

Instale os modelos com:

```powershell
ollama pull qwen3:8b
ollama pull qwen3-embedding:0.6b
```

### Recursos de voz

Para usar microfone e síntese de fala:

- Microfone funcional;
- Saída de áudio;
- Drivers de áudio instalados;
- Dependências de `requirements-voz.txt`;
- Modelo local Piper:

```text
resources\vozes\pt_BR-faber-medium.onnx
```

O Faster-Whisper pode utilizar a CPU. Uma GPU compatível pode acelerar a
transcrição.

### Internet

A internet não é necessária para:

- Conversar usando o Ollama local;
- Usar a memória local;
- Usar o banco SQLite;
- Usar a voz local Piper;
- Executar ações locais.

A internet é necessária ou recomendada para:

- Baixar dependências e modelos;
- Usar a pesquisa online;
- Usar a voz neural Edge-TTS;
- Baixar atualizações;
- Baixar alguns modelos de reconhecimento no primeiro uso.

### Uso do instalador

Quem usar o instalador não precisa instalar Python nem PyInstaller, pois o
aplicativo e suas dependências já estarão empacotados.

Ainda será necessário instalar separadamente:

- Ollama;
- `qwen3:8b`;
- `qwen3-embedding:0.6b`.

### Resumo

| Item | Requisito mínimo |
| --- | --- |
| Sistema | Windows 10/11, 64 bits |
| Processador | 4 núcleos |
| Memória RAM | 8 GB |
| Memória recomendada | 16 GB |
| Armazenamento livre | 15 GB |
| GPU | Opcional |
| Python | 3.13 ou superior, para executar o código-fonte |
| Ollama | Obrigatório |
| Microfone | Opcional, somente para voz |
| Internet | Opcional para uso local |

Para uma experiência mais confortável com o modelo `qwen3:8b`, voz e memória
semântica simultaneamente, recomenda-se 16 GB de RAM, SSD e uma GPU compatível.
A GPU não é obrigatória.


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

Instale primeiro as dependências gerais:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Para habilitar a captura de áudio e a síntese de fala, instale também:

```powershell
python -m pip install -r requirements-voz.txt
```

O arquivo `requirements.txt` inclui Faster-Whisper para reconhecimento de voz.
O arquivo `requirements-voz.txt` adiciona Piper, Edge-TTS, SoundDevice, AV,
Emoji e bibliotecas de suporte a áudio.

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

Os nomes dos modelos podem ser escolhidos na primeira execução ou em
**Configurações → Geral**, entre os modelos instalados no Ollama.

## Executando

Para usar a janela Windows instalável, veja [INSTALACAO.md](INSTALACAO.md).
Na primeira abertura, siga o [guia de configuração](docs/PRIMEIRA_EXECUCAO.md)
para verificar o Ollama, escolher modelos e testar o áudio.
Depois, use **Configurações** para ajustar modelos, idioma, histórico,
pesquisa e voz na mesma janela, além de consultar o diagnóstico.
Em **Configurações → Voz**, a lista inicial mostra um microfone por dispositivo
que aceita a captura de voz, sem repetições de APIs de áudio. A tela identifica
o microfone padrão do Windows; use **Testar este microfone** falando por dois
segundos e salve o que captar sua voz. **Mostrar todas as entradas** exibe as
opções técnicas para diagnóstico, e **Atualizar microfones** detecta aparelhos
recém-conectados. O ícone do aplicativo também aparece na janela e nos atalhos.
Ela tem abas separadas para Texto e Voz: a conversa escrita ocupa a área
principal, e a aba Voz mostra a escuta, seus controles e a transcrição.
O botão **Memória** abre o gerenciamento visual: filtre ou busque lembranças,
selecione uma para editar ou excluir, e use a aba **Editar** para criar uma nova.
Histórico e resumos têm lista e leitura lado a lado. A janela mantém essas ações
acessíveis mesmo no tamanho mínimo. Veja a [captura da aba Memória](./docs/interface-memoria-real.png).
Na escrita, **Não salvar esta troca** evita gravar aquela pergunta e
resposta. Exemplos em blocos Markdown aparecem com fonte monoespaçada, cores
de sintaxe e comando para copiar o código.

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

### Aplicativo desktop para Windows

#### Download

Baixe o instalador da release Beta publicada mais recente:

[**Releases do Assistente IA para Windows**](https://github.com/Raphazoc/assistente_ia/releases)

O aplicativo pode verificar novas versões publicadas ao iniciar. Esse aviso pode
ser desativado em **Configurações → Geral**; o botão **Verificar versão** permite
uma consulta manual. Quando houver uma versão nova, clique no aviso para ler as
notas e escolher se deseja abrir a página oficial da release. O aplicativo não
baixa nem instala atualizações por conta própria. A consulta usa apenas a API
pública de releases do GitHub e não envia conversas nem chaves de API.
O botão mostra o resultado da última consulta e permite cancelar uma consulta
em andamento. Quando houver atualização, a janela informa se é Beta; você pode
abrir a release ou selecionar o instalador baixado para conferir o SHA-256 da
release e a assinatura Authenticode antes de executá-lo. Versões iguais ou mais
antigas são recusadas nessa verificação.

O instalador inclui o aplicativo, o Python, as dependências e o modelo local
de voz Piper. O Ollama e os modelos de linguagem continuam sendo instalados
separadamente. Na release, baixe `AssistenteIA-Setup.exe` e confira o SHA-256
com o arquivo `.sha256` publicado junto. As versões Beta não aparecem no
atalho `releases/latest` do GitHub.

#### Gerar o instalador

Para criar o aplicativo empacotado e, opcionalmente, o instalador:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\installer\build.ps1
```

O script gera `dist\AssistenteIA\AssistenteIA.exe` e, quando o Inno Setup
está instalado, `dist-installer\AssistenteIA-Setup.exe` e seu arquivo `.sha256`.
O [workflow Windows](.github/workflows/windows.yml) executa testes, gera os
arquivos e testa instalação/desinstalação em outro runner antes de disponibilizar
o artefato. Para gerar somente a
pasta executável:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\installer\build.ps1 -SomenteAplicativo
```

O aplicativo desktop mantém os dados do usuário em
`%LOCALAPPDATA%\AssistenteIA` e os arquivos organizados pela assistente em
`%USERPROFILE%\Documents\AssistenteIA`. O instalador não inclui nem inicia o
Ollama automaticamente: o serviço e os modelos precisam estar instalados
separadamente.

O desktop, o terminal (`python main.py`) e `python -m app.banco` usam o mesmo
`%LOCALAPPDATA%\AssistenteIA\memoria.db`. Feche o aplicativo antes de restaurar
um backup. A configuração inicial mostra **Verificar ambiente**: consulta Ollama,
modelos, versão, dispositivos, RAM e VRAM NVIDIA (quando disponível).

`requirements-prod.txt` e `requirements-voz.txt` fixam as dependências diretas;
`requirements-ci.txt` fixa também as transitivas para testes e empacotamento
Windows. O CI executa Ruff, mypy e cobertura mínima dos módulos críticos em
Python 3.13 e 3.14. Atualizações são verificadas semanalmente em um workflow
separado e exigem revisão antes de alterar o lock.

O instalador gerado localmente fica em:

```text
dist-installer\AssistenteIA-Setup.exe
```

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
do menu. O valor é salvo em `resources/config_voz.json`.

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
deve ser versionado.

**Ao instalar ou atualizar pelo instalador Windows, a memória instalada é
zerada**, inclusive histórico, resumos e backups. Configurações e chaves
permanecem. O aplicativo não importa mais automaticamente um banco antigo.

A memória possui:

- Fatos e preferências duráveis.
- Associação entre lembranças e mensagens de origem.
- Importância de 1 a 5.
- Assunto e projeto ativos.
- Busca textual e recuperação semântica.
- Resumos de conversas extensas.
- Exclusão e edição com remoção das associações antigas de contexto.
- Gerenciador visual para filtrar fatos e preferências, consultar uso e origem,
  desligar a memória e apagar dados após confirmação.

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

A pesquisa é controlada por `resources/config_internet.json`. Neste repositório, o
arquivo inicial está habilitado:

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
- Anexa fontes, buscador utilizado e horário da consulta à resposta quando a pesquisa é concluída.
- Permite abrir a fonte original pelo título na interface desktop; os links não são falados.

Para solicitar uma consulta diretamente, use:

```text
/pesquisar versão atual do Python
```

Em **Configurações → Pesquisa**, é possível escolher Brave Search e guardar a
chave no cofre de credenciais do sistema. Quando a API falha, a assistente tenta
DuckDuckGo com a mesma consulta autorizada e informa qual buscador encontrou as
fontes. Os filtros de conteúdo e a autorização por pesquisa continuam ativos.

Não habilite esse recurso se o objetivo for executar o programa totalmente
offline. A geração da resposta e a memória permanecem locais, mas o recurso
de pesquisa acessa serviços externos quando autorizado.

## Ações locais

Quando o pedido começa com um verbo de ação, a assistente pode propor uma
operação local. O plano é validado e exige confirmação antes da execução.
Atualmente são suportadas:

- abrir Bloco de Notas, Calculadora ou Explorador de Arquivos;
- abrir uma URL HTTP/HTTPS pública após verificar seu conteúdo;
- abrir ou listar uma pasta do projeto;
- ler arquivos de texto permitidos, com limite de tamanho;
- criar uma pasta;
- mover arquivos comuns dentro da pasta do projeto.

As ações não podem acessar pastas protegidas, sair da pasta do projeto ou
alterar arquivos essenciais. Perguntas sobre como realizar uma tarefa não são
tratadas automaticamente como autorização para executá-la.

## Voz e áudio

A fala usa uma estratégia de fallback:

1. Tenta a voz neural online configurada em `app/fala.py`.
2. Se o serviço online falhar, usa a voz local Piper.

O modelo local esperado é:

```text
resources/vozes/pt_BR-faber-medium.onnx
resources/vozes/pt_BR-faber-medium.onnx.json
```

Para testar a transcrição de voz isoladamente:

```powershell
python -m app.voz
```

Para testar a síntese de fala:

```powershell
python -m app.fala
```

O modo de voz pode precisar de permissões do sistema operacional, drivers de
áudio e configuração do dispositivo padrão. A indisponibilidade do microfone
não impede o uso do modo texto.

## Backups e restauração

O assistente cria backups automáticos do SQLite em `backups/`, mantendo as
últimas cópias automáticas conforme a política do módulo `app/banco.py`.
Se encontrar cópias históricas na antiga pasta `backyp`, move-as com verificação
de hash para `backups/legado`. Novas cópias da migração também são arquivadas
em `backups/legado`; o programa não cria mais arquivos em `backyp`. Essas cópias
de esquema antigo são arquivos históricos e não aparecem na lista de restauração
do esquema atual.

Listar backups:

```powershell
python -m app.banco listar
```

Criar backup manual:

```powershell
python -m app.banco backup
```

Restaurar um backup listado:

```powershell
python -m app.banco restaurar NOME_DO_BACKUP.db
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
- Inicialização, falhas e recuperação entre interface, banco, Ollama e pesquisa
  ([cenários de integração](docs/TESTES_INTEGRACAO.md)).
- Confiabilidade, backups e diagnósticos.

Para executar um arquivo específico:

```powershell
python -m pytest tests/test_memoria.py
python -m pytest tests/test_internet.py
```

## Estrutura do repositório

```text
.
|-- app/                    # Código principal da assistente
|   |-- main.py             # Ciclo principal e integração dos recursos
|   |-- aplicativo.py       # Interface desktop Windows
|   |-- memoria.py          # Memória e recuperação
|   |-- internet.py         # Pesquisa autorizada
|   `-- voz.py              # Reconhecimento de fala
|-- resources/              # Configurações e modelos distribuídos
|-- legacy/                 # Versões antigas mantidas para referência
|-- docs/                   # Documentação dos subsistemas
|-- tests/                  # Testes automatizados
|-- installer/              # Empacotamento Windows
|-- AssistenteIA.spec       # Configuração do PyInstaller
|-- INSTALACAO.md           # Empacotamento e instalação
`-- requirements.txt        # Dependências gerais
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

Revise `app/fala.py`, `app/internet.py` e as configurações locais antes de usar o
projeto em um ambiente com requisitos específicos de privacidade.
Consulte também a [política de privacidade](./PRIVACIDADE.md) e as
[orientações de segurança](./SECURITY.md).

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
Veja [CONTRIBUTING.md](./CONTRIBUTING.md) para o fluxo de contribuição.

## Documentação complementar

As explicações detalhadas de cada subsistema ficam na pasta [`docs/`](./docs/):

- [Memória e resumos](./docs/MEMORIA.md)
- [Pesquisa na internet](./docs/INTERNET.md)
- [Voz e áudio](./docs/VOZ.md)
- [Confiabilidade, diagnóstico e recuperação](./docs/CONFIABILIDADE.md)
- [Configurações](./docs/CONFIGURACAO.md)
- [Solução de problemas](./docs/PROBLEMAS.md)
- [Escopo da versão Beta](./docs/BETA.md)
- [Checklist de release Beta](./docs/RELEASE.md)
- [Histórico de mudanças](./CHANGELOG.md)

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
- Piper e o modelo `resources/vozes/pt_BR-faber-medium.onnx`;
- Edge-TTS e o serviço online de síntese de voz;
- Bibliotecas instaladas por `requirements.txt` e `requirements-voz.txt`;
- Serviços externos acessados pelo recurso opcional de pesquisa.

Antes de redistribuir esses componentes, confirme os termos oficiais de cada
projeto, modelo ou serviço. A Licença MIT deste repositório não transforma
componentes de terceiros em software MIT nem concede direitos sobre eles.
