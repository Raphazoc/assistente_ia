# Checklist: monitoramento privado durante os estudos

> Arquivado em 19/10/2026: o recurso Acompanhar estudos foi removido a pedido
> do usuário na versão 0.5.6. Este documento registra somente o planejamento
> anterior; os itens abaixo não representam funcionalidades disponíveis.

Objetivo original: permitir que a AssistenteIA analise o conteúdo usado nos estudos,
sem capturar a tela inteira e sem compartilhar o conteúdo com outras pessoas
ou serviços por padrão.

## Escopo e fontes permitidas

- [ ] Adicionar um modo **Acompanhar estudos** separado da conversa normal.
- [ ] Permitir selecionar uma única fonte por vez:
  - [ ] Janela do VS Code.
  - [ ] Aba ou página autorizada do navegador, como o Boot.dev.
  - [ ] Região selecionada da tela, como alternativa de menor exposição.
- [ ] Não capturar a tela inteira por padrão.
- [ ] Mostrar claramente qual fonte está sendo monitorada.
- [ ] Permitir trocar de arquivo dentro do VS Code sem perder a sessão.
- [ ] Permitir navegar para outro exercício na aba autorizada do Boot.dev.
- [ ] Não conceder acesso automático a outras abas, janelas ou aplicativos.
- [ ] Solicitar nova autorização quando a fonte monitorada mudar.
- [ ] Pausar o monitoramento quando a fonte selecionada for fechada,
  minimizada ou deixar de estar disponível.

## Controle pelo usuário

- [ ] Exigir uma ação explícita para iniciar o monitoramento.
- [ ] Exibir os controles **Analisar agora**, **Pausar** e **Encerrar acesso**.
- [ ] Permitir análise sob demanda antes de ativar capturas periódicas.
- [ ] Permitir configurar o intervalo entre análises, com limite seguro.
- [ ] Informar visualmente quando uma captura estiver sendo realizada.
- [ ] Pedir confirmação antes de enviar qualquer conteúdo para um serviço
  externo.
- [ ] Não alterar código, respostas ou exercícios automaticamente.
- [ ] Mostrar a sugestão e exigir confirmação antes de aplicar uma correção.

## Privacidade: acesso somente do proprietário

- [ ] Manter a funcionalidade desativada até o proprietário habilitá-la.
- [ ] Processar as imagens localmente pelo Ollama sempre que possível.
- [ ] Não enviar capturas, OCR, histórico ou transcrições para terceiros sem
  autorização individual.
- [ ] Não criar conta, sincronização ou compartilhamento remoto como requisito.
- [ ] Armazenar configurações e dados de estudo somente na pasta de dados local
  do usuário.
- [ ] Não armazenar capturas de tela por padrão.
- [ ] Se o usuário optar por salvar uma captura, pedir confirmação e informar
  o caminho do arquivo.
- [ ] Não registrar em logs o conteúdo visual, texto reconhecido, senhas,
  tokens, cookies ou dados pessoais.
- [ ] Permitir apagar qualquer histórico local relacionado ao monitoramento.
- [ ] Documentar que outras pessoas com acesso à conta do Windows ou aos
  arquivos locais podem acessar dados não protegidos pelo sistema operacional.
- [ ] Restringir permissões dos arquivos de configuração, histórico e logs ao
  usuário atual quando o Windows permitir.

## Proteção de conteúdo sensível

- [ ] Exibir um aviso para não deixar senhas, chaves de API, cookies ou dados
  pessoais visíveis na fonte monitorada.
- [ ] Oferecer uma lista local de regiões ou padrões para ocultar antes da
  análise.
- [ ] Bloquear ou pedir confirmação para campos reconhecidos como senha.
- [ ] Permitir interromper imediatamente a captura por um atalho de teclado.
- [ ] Limpar da memória temporária a imagem após a análise, salvo opt-in
  explícito do usuário.

## Análise e apoio ao aprendizado

- [ ] Detectar erros de sintaxe, mensagens do terminal e problemas no código.
- [ ] Explicar o motivo do erro em português brasileiro.
- [ ] Oferecer dicas graduais antes de apresentar a solução completa.
- [ ] Identificar quando o conteúdo é um exercício e evitar entregar a
  resposta sem solicitação.
- [ ] Permitir perguntar: **Por que isso está errado?**
- [ ] Permitir solicitar uma correção sugerida para um trecho específico.
- [ ] Manter a análise limitada à fonte e ao contexto autorizados.
- [ ] Indicar quando a confiança da análise for baixa ou quando o conteúdo
  estiver ilegível.

## Implementação técnica

- [ ] Definir uma abstração de fonte monitorada, sem acoplar a lógica à captura
  da tela inteira.
- [ ] Implementar captura de janela no Windows para o VS Code.
- [ ] Avaliar extensão do Chrome/Edge para limitar a captura a uma aba.
- [ ] Implementar seleção e validação da janela ou aba autorizada.
- [ ] Usar OCR somente quando necessário; preferir dados estruturados quando a
  integração da fonte permitir.
- [ ] Redimensionar e limitar imagens antes da análise para reduzir exposição.
- [ ] Rejeitar fontes inválidas ou que não possam ser identificadas com
  segurança.
- [ ] Executar a análise fora da thread da interface.
- [ ] Cancelar captura, OCR e análise ao pausar ou encerrar o monitoramento.
- [ ] Usar o modelo local configurado no projeto por padrão.
- [ ] Tornar qualquer integração externa opt-in, visível e revogável.

## Testes e critérios de aceite

- [ ] Confirmar que o VS Code é capturado sem capturar outras janelas.
- [ ] Confirmar que trocar para outro aplicativo não transfere acesso a ele.
- [ ] Confirmar que a aba autorizada do Boot.dev continua disponível ao
  navegar dentro dela.
- [ ] Confirmar que abrir ou selecionar outra aba exige nova autorização.
- [ ] Confirmar que minimizar ou fechar a fonte pausa o monitoramento.
- [ ] Confirmar que **Encerrar acesso** interrompe novas capturas e análises.
- [ ] Confirmar que nenhuma imagem é persistida sem opt-in.
- [ ] Confirmar que logs não contêm conteúdo da tela ou dados sensíveis.
- [ ] Confirmar que o modo local funciona sem conexão com a internet.
- [ ] Confirmar que falhas de captura ou OCR são exibidas explicitamente, sem
  continuar com uma análise como se tivesse sido concluída.
- [ ] Testar autorização, pausa, troca de fonte e encerramento no Windows 10 e
  Windows 11.
- [ ] Documentar no README como iniciar, pausar, encerrar e revogar o acesso.

## Definição de pronto

O recurso estará pronto quando o usuário conseguir acompanhar somente o VS
Code ou somente uma aba autorizada do navegador, pausar e encerrar o acesso a
qualquer momento, receber correções explicadas e verificar que nenhum conteúdo
foi salvo ou enviado externamente sem sua autorização explícita.
