# Solução de problemas

Comece em **Configurações → Diagnóstico → Verificar novamente**. O botão
**Copiar diagnóstico** reúne versão, modelos, estado dos dispositivos e códigos
de eventos sem incluir chaves ou texto da conversa.

| Sintoma | O que verificar |
| --- | --- |
| A primeira execução não avança | Abra o Ollama, instale os modelos mostrados como ausentes e clique em **Verificar novamente**. A tela exige um modelo de conversa e um de embeddings disponíveis. |
| A IA para de responder | Confira se o Ollama continua aberto. Reabra **Configurações → Diagnóstico** e verifique o modelo selecionado. |
| O microfone não ouve | Em **Configurações → Voz**, veja o dispositivo padrão, escolha uma entrada recomendada e fale durante **Testar este microfone**. Confira também se a aba Voz não está **Mutada** e se o Windows permite acesso ao microfone. Entradas técnicas em **Mostrar todas as entradas** podem não aceitar 16 kHz. |
| A transcrição erra palavras | Fale perto do microfone, reduza ruído ambiente e aguarde a pausa de fim de frase. Nomes em inglês ainda podem ser interpretados incorretamente; confira a transcrição antes de repetir. |
| A IA não fala | Use **Testar alto-falante** e **Testar voz**. Confira o dispositivo de saída, a internet para a voz online e o modelo Piper local. |
| A pesquisa não acontece | Confira **Pesquisa: ligada**. Autorize cada consulta quando ela aparecer. Pedidos ou fontes bloqueados pelo filtro de segurança não são liberados pela chave Brave. |
| Uma página não abre | Algumas fontes bloqueiam leitura automatizada. O assistente pode usar apenas o resumo filtrado do buscador e deve mostrar isso junto da fonte. Abra o link original se precisar conferir o conteúdo. |
| A API Brave ou ElevenLabs falha | Confira a chave em **Configurações**, o acesso à internet e os limites do provedor. A busca pode usar DuckDuckGo; a voz pode usar Piper local. |
| A atualização não aparece | Use **Verificar versão**. O aviso encontra releases publicadas; rascunhos não aparecem. Uma falha de rede não impede a conversa local. |
| A memória parece ausente | Confira a pasta de dados em **Diagnóstico** e a tela **Memória**. A busca semântica depende do modelo de embeddings, mas o histórico local continua acessível. |

Se o problema persistir, abra uma issue usando o [modelo de relato de bug](../.github/ISSUE_TEMPLATE/bug_report.md).
Inclua os passos para reproduzir e o diagnóstico copiado. Não anexe
`memoria.db`, backups, chaves, gravações ou logs completos sem revisar: eles
podem conter informações pessoais ou caminhos locais.
