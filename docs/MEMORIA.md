# Memória da assistente

As conversas e lembranças ficam em `memoria.db` e continuam disponíveis após
reiniciar o programa. A atualização do banco preserva os registros existentes
e cria uma cópia de segurança antes da migração.
Backups automáticos diários e restauração manual estão descritos em
[CONFIABILIDADE.md](CONFIABILIDADE.md).

## Guardar e gerenciar fatos

Use os comandos abaixo no modo de digitação. Os números das lembranças
aparecem ao listar a memória.

| Comando | Exemplo e efeito |
| --- | --- |
| `/lembrar <fato>` | `/lembrar Prefiro respostas curtas` guarda um fato importante no contexto ativo. |
| `/memorias` | Lista as lembranças disponíveis e seus IDs. |
| `/memoria editar <id> <novo texto>` | `/memoria editar 12 Prefiro respostas detalhadas` substitui a lembrança 12. |
| `/memoria excluir <id>` | `/memoria excluir 12` remove a lembrança 12 da recuperação. |
| `/assunto <nome>` | `/assunto estudos` organiza novas mensagens e lembranças por assunto. Use `/assunto geral` para voltar ao assunto padrão. |
| `/projeto <nome>` | `/projeto aplicativo` seleciona um projeto. Use `/projeto nenhum` para sair dele. |
| `/resumir` | Solicita o resumo das mensagens elegíveis do contexto ativo. |

Também é possível abrir **Esc → 4 — Memórias** para listar, adicionar,
editar ou excluir lembranças, mudar assunto ou projeto e consultar resumos.
Para guardar um fato com segurança, prefira `/lembrar` ou essa opção do menu.

A assistente também identifica algumas afirmações pessoais estáveis em
primeira pessoa e guarda o texto original do usuário. Essa seleção é
conservadora: nem todo fato importante será reconhecido automaticamente.

No aplicativo Windows, o botão **Memória** abre um gerenciador visual. A aba
**Lembranças** separa fatos e preferências, filtra por texto, assunto ou
projeto e permite criar, editar ou excluir cada item. Ao selecionar uma
lembrança, a tela mostra quantas mensagens a originaram e em quantas respostas
registradas ela foi usada. A escolha em cada resposta também depende da
pergunta, do contexto ativo, da importância e da similaridade.

A aba **Histórico** mostra as mensagens salvas separadamente das lembranças.
**Não usar esta troca na memória** mantém a mensagem visível, mas retira a
troca e as lembranças associadas da recuperação futura. A aba **Resumos**
permite consultar os resumos já criados. Documentos ainda não são importados
para essa memória; arquivos lidos em ações locais não viram lembranças por
conta própria.

O controle **Memória ativa** desliga ou religa a recuperação e a extração
automática de fatos. Com ele desligado, o histórico da conversa continua
sendo salvo para consulta, mas as novas mensagens são marcadas para não
entrar na memória de longo prazo. A conversa da sessão atual ainda tem
contexto enquanto o aplicativo está aberto.

Na aba Texto, marque **Não salvar esta troca** antes de enviar uma mensagem
particular. A pergunta e a resposta aparecem na janela, mas não são gravadas
no banco nem reutilizadas como contexto nas próximas respostas. A opção volta
a ficar desmarcada após o envio.

## Assuntos, projetos e seleção

Defina o assunto e o projeto antes de conversar sobre eles. Lembranças
criadas nesse contexto ficam associadas a ele. Um projeto ativo não recupera
lembranças dos outros projetos; informações gerais de perfil ainda podem
ser usadas.

Ao responder, a assistente seleciona fatos, resumos e trechos de conversa
considerando o contexto e a relevância para a pergunta. Se o serviço de
embeddings estiver indisponível, a busca continua usando palavras e
registros recentes. O contexto enviado ao modelo é limitado: uma resposta
não representa necessariamente tudo que existe no banco.

## Resumos automáticos

Conversas longas recebem resumos ao atingir **24 mensagens ou 10.000
caracteres**, dentro do mesmo contexto. O comando `/resumir` antecipa a
solicitação para as mensagens elegíveis. Os resumos automáticos usam
trechos selecionados das mensagens originais, sem depender da geração pelo
modelo.

Os resumos ajudam a recuperar o histórico sem reenviar a conversa inteira.
Eles podem omitir detalhes; fatos que precisam ser preservados devem ser
guardados como lembranças importantes.

## Atualização e exclusão

Ao editar ou excluir uma lembrança, os trechos originais associados deixam
de ser recuperados para o modelo e os resumos que os cobrem são invalidados.
Isso evita que a versão antiga reapareça por meio dessas fontes.

O arquivo de conversas no SQLite pode manter as mensagens originais para
consulta do histórico. Portanto, excluir uma lembrança não equivale a apagar
definitivamente todos os vestígios do texto: o histórico e cópias de
segurança podem continuar contendo esses dados.

O botão **Apagar toda a memória** remove lembranças, histórico, vetores e
resumos do banco ativo após confirmação. Marque **Incluir backups** se também
quiser excluir as cópias gerenciadas pelo aplicativo. Cópias feitas fora da
pasta de backups do aplicativo não são localizadas por esse botão.

## Uso por voz

Os comandos que começam com `/` estão disponíveis no modo de texto. No modo
de áudio, fale o pedido diretamente. Para guardar uma lembrança, diga, por
exemplo, **“Lembre que prefiro respostas curtas”**. Para listar, editar ou
excluir lembranças pelo número, use **Esc → 4** e siga as opções exibidas.
Os controles de áudio e digitação estão em [VOZ.md](VOZ.md).

## Personalidade dinâmica

A assistente mantém um jeito confiante, bem-humorado e paciente, mas ajusta
o ritmo conforme manhã, tarde, noite ou madrugada no horário local. A resposta
é gerada pelo modelo a cada conversa, considerando a pergunta, o histórico
e as preferências de estilo disponíveis; o horário não precisa ser mencionado.

Para mudar o jeito dela de forma persistente, diga, por exemplo,
**“Lembre que prefiro respostas sem piadas”** ou use `/lembrar Prefiro respostas
sem piadas`. Essas preferências também são recuperadas ao falar de outro
assunto. Você pode editá-las ou excluí-las em **Esc → 4**.

## Pesquisas online

As respostas com fontes online também ficam no histórico local e podem
aparecer nos resumos e na recuperação de conversas. As páginas consultadas
não são importadas automaticamente como fatos pessoais. A pesquisa exige
autorização para cada pedido, conforme [INTERNET.md](INTERNET.md).
