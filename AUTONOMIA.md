# Autonomia da assistente

A assistente já usa memória para manter o contexto, ajusta o jeito de conversar
ao horário e às preferências salvas e pode decidir quando propor uma pesquisa.
Cada pesquisa continua exigindo autorização específica antes de acessar a rede.
Cumprimentos e agradecimentos curtos vão direto para a resposta, sem uma chamada
extra ao modelo para planejar pesquisa.

Ela também reconhece pedidos diretos de ação no computador. Antes de executar,
mostra no terminal o tipo de ação e o alvo exato. Responda **`s`** ou **`sim`**
na digitação, ou diga **“confirmo”** no modo de voz. Outra resposta cancela.
A confirmação vale para uma ação; texto de páginas, memórias e respostas da
própria assistente não autoriza ações.

| Pedido de exemplo | O que pode fazer |
| --- | --- |
| “Abra a calculadora” | Abre Calculadora, Bloco de Notas ou Explorador de Arquivos. |
| “Abra https://www.python.org/” | Verifica endereço e conteúdo antes de abrir o site no navegador. |
| “Liste a pasta docs” | Lista até 100 itens de uma pasta do projeto no terminal. |
| “Leia o arquivo MEMORIA.md” | Mostra no terminal um arquivo de texto do projeto de até 50 KB. |
| “Crie a pasta notas” | Cria uma pasta dentro do projeto, sem substituir outra. |
| “Mova notas.txt para arquivo/notas.txt” | Move um arquivo comum dentro do projeto, sem sobrescrever o destino. |

Pastas do ambiente virtual, Git, logs e backups não entram nessas ações.
Arquivos essenciais e arquivos Python não podem ser movidos por esse fluxo.
O conteúdo de arquivos lidos e os nomes de uma listagem aparecem apenas no
terminal; a resposta falada recebe só a confirmação da operação. O acesso
a sites depende da verificação de conteúdo e pode ser recusado. Abrir uma
página no navegador não garante que o site não mude depois da verificação.

A assistente pode acompanhar a conversa com perguntas úteis, mas não inicia
falas sozinha em segundo plano. A fala ainda espera a resposta completa do
Ollama antes de começar; transmissão gradual da resposta e da voz é uma
próxima melhoria possível para reduzir a espera percebida. Os tempos reais
dependem do computador, do modelo, do microfone e do serviço de voz.
