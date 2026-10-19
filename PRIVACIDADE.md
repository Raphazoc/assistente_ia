# Privacidade

O aplicativo é executado no computador do usuário. Conversas, transcrições
enviadas ao modelo, lembranças e resumos ficam no banco SQLite local
`%LOCALAPPDATA%\AssistenteIA\memoria.db` no aplicativo instalado. Backups
ficam na pasta de dados local. Esses arquivos não possuem criptografia própria;
a proteção em repouso depende da conta e do disco do Windows.

O Ollama é acessado em `127.0.0.1` para respostas e embeddings. Recursos
opcionais podem enviar dados a serviços externos:

- **Pesquisa:** depois de uma autorização específica, consultas vão ao
  buscador escolhido (DuckDuckGo ou Brave), e páginas públicas selecionadas
  são lidas. O filtro +18 permanece ativo.
- **Voz online:** o texto da resposta vai ao serviço de síntese escolhido
  (Edge ou ElevenLabs). A alternativa Piper é local.
- **Atualizações:** quando a verificação automática está ativa, o aplicativo
  consulta os metadados públicos das releases no GitHub. O botão manual faz a
  mesma consulta. A requisição revela ao GitHub informações normais de rede,
  como endereço IP, e a versão do aplicativo no User-Agent; não envia a
  conversa, o banco nem chaves.
- **Modelos:** o reconhecimento por Faster-Whisper pode baixar modelos na
  primeira utilização. Baixar modelos Ollama também requer internet.
- **Perfil de voz opcional:** ao escolher **Registrar minha voz**, o aplicativo
  baixa um modelo público de verificação e processa duas gravações localmente.
  O áudio bruto é descartado; apenas um vetor numérico de locutor fica em
  `%LOCALAPPDATA%\AssistenteIA\perfil_voz.json`. Esse perfil pode ser apagado
  na aba Voz e é removido em cada instalação e na desinstalação.

Chaves de API ficam no cofre de credenciais do Windows. Os logs rotativos
registram códigos de evento, tempos, contagens e tipos de erro, sem texto de
conversas, transcrições ou chaves. Arquivos organizados por ações locais podem
ficar em `%USERPROFILE%\Documents\AssistenteIA`.

Em **Memória**, você pode editar ou excluir lembranças, desativar a criação de
novas memórias e marcar uma troca para não ser usada em recuperações futuras.
Na aba **Texto**, **Não salvar esta troca** evita gravar aquela pergunta e
resposta. **Apagar toda a memória** remove o conteúdo do banco ativo; marque
a opção de incluir backups se também quiser apagar as cópias locais. A
desinstalação preserva a pasta de dados do usuário. Cada nova instalação limpa
o banco de memória e seus backups, mantendo configurações e chaves de API.
Feche o aplicativo antes de excluir manualmente arquivos da pasta de dados.

O projeto não inclui telemetria própria. Serviços externos podem ter políticas
de retenção diferentes; consulte os termos do provedor que escolher.

O aplicativo não captura a tela nem janelas de outros programas.
