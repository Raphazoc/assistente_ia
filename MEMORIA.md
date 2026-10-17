# Memória da assistente

As conversas e lembranças ficam em `memoria.db` e continuam disponíveis após
reiniciar o programa. A atualização do banco preserva os registros existentes
e cria uma cópia de segurança antes da migração.

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

## Uso por voz

Os comandos digitados com `/` estão disponíveis no modo de texto. No modo
de áudio, a palavra de ativação também é exigida para comandos falados; por
padrão, comece com **“Aurora”**. Para gerenciar uma lembrança pelo número,
use **Esc → 4** e siga as opções exibidas.
