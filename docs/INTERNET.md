# Pesquisa na internet

A assistente usa o modelo local para decidir quando precisa de uma pesquisa.
Ela pode consultar o DuckDuckGo e ler páginas reais para responder com fontes,
mas pede sua autorização **antes de cada pesquisa**. Uma autorização não vale
para perguntas futuras, novas consultas ou navegação livre.

## Como usar

Reinicie o programa para carregar a atualização:

```powershell
.\.venv\Scripts\python.exe main.py
```

As dependências estão em `requirements.txt`. Para reinstalar:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Pergunte normalmente, por exemplo **“Qual é a versão mais recente do Python?”**.
Quando o modelo identificar necessidade de verificar fontes, o terminal mostra
o motivo e as consultas propostas. Também é possível pedir diretamente:
**`/pesquisar documentação oficial do Python`**. Esse comando continua exigindo
autorização e respeitando os filtros.

- **Digitação:** responda `s`, `sim`, `autorizo` ou `autorizar` à confirmação.
- **Voz:** após conferir as consultas propostas no terminal, diga **“autorizo”**.
  **“Aurora, autorizo”** também funciona, mas o nome não é obrigatório.
- **Recusar:** Enter, `não`, silêncio ou resposta ambígua não liberam a pesquisa.
- **Cancelar:** Esc durante a confirmação cancela e abre o menu.
- **Desativar:** **Esc → 5** alterna a pesquisa; a escolha é salva em
  `config_internet.json`. Reativar não dispensa futuras autorizações.

No aplicativo Windows, use **Pesquisa: ligada/desligada** no topo da janela.
A escolha é salva nas configurações do aplicativo e vale nas próximas aberturas.
Desligar a pesquisa impede o acesso ao buscador; ligar novamente mantém a
autorização individual antes de cada busca.

Cada autorização cobre somente as consultas exibidas, no máximo duas, e a
leitura de até três fontes públicas de texto retornadas por elas. O programa
não segue links das páginas para ampliar a pesquisa. Se precisar de outra
pesquisa, faça um novo pedido e confirme novamente.

Os links efetivamente consultados aparecem ao final da resposta no terminal.
Quando uma página não pôde ser lida e foi usado apenas o resumo do buscador,
a fonte recebe essa indicação. A data de consulta não é a data de publicação.
Se não houver fontes utilizáveis, o programa informa a limitação.

## Restrições

O Safe Search estrito é imposto no buscador, com `kp=1` e a preferência
equivalente em cookie, conforme os parâmetros oficiais do
[DuckDuckGo](https://duckduckgo.com/duckduckgo-help-pages/settings/params).
A versão de `ddgs` fica fixada porque essa integração define o parâmetro
explicitamente, sem depender do modo automático da biblioteca.

Além disso, o programa verifica o pedido, as consultas, os endereços, os
resumos e os textos lidos. Bloqueia termos e domínios adultos conhecidos,
marcações de página adulta e usa o modelo local para classificar as fontes.
Pedidos explícitos de instruções para roubo de credenciais, invasão, malware,
explosivos, golpes ou fraude também são bloqueados. O modelo local decide se
uma pergunta precisa de pesquisa, mas uma negativa genérica do planejamento
não bloqueia por si só um pedido comum. Se o planejamento ou a classificação
de fontes falhar, a etapa correspondente não é liberada.

Os filtros são obrigatórios e não têm opção de desligar. Eles reduzem o risco,
mas não garantem detectar todo conteúdo impróprio; o modelo pode errar e
bloquear conteúdo legítimo. Páginas são tratadas como dados, e suas instruções
não concedem permissão para novas ações.

A navegação aceita somente HTTP/HTTPS público, com validação de DNS, IP e
redirecionamentos. Endereços locais, redes privadas, credenciais na URL,
portas alternativas, anexos e conteúdo que não seja HTML ou texto são
recusados. Há limites de tamanho e tempo de leitura. A pesquisa não executa
JavaScript, programas ou comandos, não instala nada, não acessa contas e não
salva arquivos baixados. Os bytes das páginas são lidos apenas para extrair texto.

## Privacidade e memória

O planejamento e a classificação usam o Ollama local. Antes da autorização,
nenhuma consulta de pesquisa é enviada ao buscador. Após autorizar, as
consultas exibidas são enviadas ao DuckDuckGo, e os sites das fontes recebem
as requisições de leitura, incluindo seu IP de rede. Confira o texto das
consultas antes de aprovar: ele pode conter detalhes do pedido.

O banco SQLite inteiro não é enviado ao buscador. A resposta com as fontes
continua salva no histórico local e pode participar dos resumos e da
recuperação de conversas descritos em [MEMORIA.md](MEMORIA.md). Não há
importação automática das páginas como fatos pessoais do usuário.

A voz online existente também usa a internet para sintetizar as respostas,
conforme [VOZ.md](VOZ.md). A confirmação descrita aqui controla as pesquisas;
a configuração da síntese de voz continua em `fala.py`.
