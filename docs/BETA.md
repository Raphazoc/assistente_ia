# Escopo da versão Beta

O projeto está na série `0.5.x`. **Beta** significa que os fluxos principais
funcionam, mas ainda precisam de validação em computadores Windows diferentes.

| Recurso | Estado atual |
| --- | --- |
| Conversa local com Ollama e histórico SQLite | Funcional, com recuperação de falhas coberta por testes. |
| Configuração inicial, diagnóstico e preferências | Funcional no aplicativo Windows. |
| Memórias, resumos e backups | Funcionais; a busca semântica exige o modelo de embeddings. |
| Interface desktop e instalador por usuário | Funcionais em testes automatizados Windows. |
| Pesquisa online autorizada | Experimental: fontes podem falhar ou se contradizer; o filtro pode bloquear conteúdo legítimo. |
| Voz e transcrição | Experimentais: dependem de dispositivos, rede, drivers e qualidade do áudio. |
| Ações locais sobre arquivos | Experimentais: exigem confirmação; confira o plano antes de aceitar. |
| Aviso de atualização | Funcional para releases publicadas; o download e a instalação são manuais. |

Antes de chamar uma release de estável, é necessário testar o instalador em
Windows sem Python, validar atualização e desinstalação em máquinas reais,
revisar segurança e privacidade e resolver os problemas encontrados na Beta.
O [checklist de release](RELEASE.md) registra essas verificações.
