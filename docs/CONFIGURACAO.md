# Configurações do aplicativo

No Windows, abra **Configurações** para alterar preferências. Os arquivos do
aplicativo instalado ficam em `%LOCALAPPDATA%\AssistenteIA`; ao executar o
código-fonte, os modelos de configuração ficam em `resources/`. Feche o
aplicativo antes de editar JSON manualmente e mantenha uma cópia do arquivo.

| Arquivo | Campo | Valores | Efeito |
| --- | --- | --- | --- |
| `config_geral.json` | `modelo` | Nome de modelo instalado no Ollama | Conversa e planejamento. |
| `config_geral.json` | `modelo_memoria` | Nome de modelo de embeddings instalado | Busca semântica. |
| `config_geral.json` | `idioma` | `pt-BR` ou `en-US` | Idioma da interface de voz e instruções. |
| `config_geral.json` | `microfone` | Texto vazio ou entrada listada em **Configurações → Voz** | Texto vazio usa o padrão do sistema; uma entrada escolhida é usada na conversa e no teste. |
| `config_geral.json` | `limite_historico` | Inteiro de 10 a 2000; padrão 500 | Máximo de mensagens recentes carregadas. O contexto enviado ao modelo mantém seu próprio limite de tamanho. |
| `config_geral.json` | `verificar_atualizacoes` | `true` ou `false` | Consulta releases ao iniciar. O botão manual continua disponível. |
| `config_geral.json` | `configurado` | `true` ou `false` | Indica conclusão da primeira execução. |
| `config_internet.json` | `ativa` | `true` ou `false` | Permite propor buscas; cada uma ainda exige autorização. |
| `config_servicos.json` | `buscador` | `duckduckgo` ou `brave` | Provedor principal de busca. |
| `config_servicos.json` | `voz` | `edge` ou `elevenlabs` | Provedor principal de síntese de voz. |
| `config_servicos.json` | `voice_id` | ID de voz ElevenLabs ou texto vazio | Voz usada quando ElevenLabs está selecionado. |
| `config_voz.json` | `palavra_ativacao` | Uma a quatro palavras | Nome usado para interromper a fala. |
| `config_voz.json` | `interromper_por_voz` | `true` ou `false` | Habilita a interrupção falada. |

O botão **Pesquisa: ligada/desligada** altera `config_internet.json`. As chaves
Brave e ElevenLabs ficam no cofre de credenciais do Windows, nunca nos JSON.
Use **Configurações → Pesquisa/Voz** para incluí-las ou removê-las. A seleção
de um provedor externo não remove a confirmação de busca nem o filtro +18.

Se `config_geral.json` estiver inválido, a primeira execução indica o campo
problemático. Restaurar um campo pelo valor mostrado acima é mais seguro do
que apagar a pasta inteira: ela também guarda a memória e os backups.
