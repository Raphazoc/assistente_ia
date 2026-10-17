# Primeira execução e diagnóstico

Na primeira abertura do aplicativo Windows, a conversa espera a configuração
inicial. A tela **Configure sua assistente** verifica se o Ollama local responde,
lista os modelos instalados e mostra se há microfone e alto-falante detectados.
Ela não envia conversas nem chaves de API durante essa verificação.

1. Instale e abra o [Ollama](https://ollama.com/download), se ainda não estiver funcionando.
2. No terminal, instale os modelos recomendados, se estiverem ausentes:

   ```powershell
   ollama pull qwen3:8b
   ollama pull qwen3-embedding:0.6b
   ```

3. Clique em **Verificar novamente**. Você também pode escolher outros modelos
   já instalados nas listas de conversa e memória.
4. Selecione o idioma, o limite de histórico e se deseja habilitar pesquisas.
   Mesmo habilitadas, as pesquisas pedem autorização individual.
5. Use **Testar microfone**, **Testar alto-falante** e **Testar voz**. Os testes
   de áudio não guardam a gravação do microfone.
6. Clique em **Salvar e continuar**. A conversa só inicia quando os dois
   modelos escolhidos estão disponíveis no Ollama local.

Depois, o botão **Configurações** abre a mesma janela, agora organizada nas abas
**Geral**, **Pesquisa**, **Voz** e **Diagnóstico**. Na aba Geral você altera
modelos, idioma e limite de histórico. Pesquisa permite ativar ou desativar
buscas e escolher DuckDuckGo ou Brave Search. Voz escolhe Edge ou ElevenLabs,
permite testar os dispositivos e configurar o ID da voz. O filtro +18 e a
autorização por pesquisa continuam ativos independentemente do provedor.

As chaves Brave e ElevenLabs ficam no cofre de credenciais do Windows. Os
campos de nova chave aparecem vazios mesmo quando uma chave já existe. Deixe
em branco para mantê-la, ou marque **Remover chave** para apagá-la. Escolher um
provedor que exige API requer uma chave configurada. **Copiar diagnóstico**
copia a versão do aplicativo e do Python, estados do Ollama e do áudio,
provedores, caminhos abreviados e códigos dos últimos eventos técnicos. Não
inclui mensagens de conversa, chaves de API nem o nome da conta do Windows.
**Abrir pasta de dados** leva aos arquivos locais para investigar uma falha.
Se o Ollama cair depois da configuração inicial, ainda é
possível salvar idioma, histórico, pesquisa e voz; para mudar os modelos, abra
o Ollama e use **Verificar novamente**.

O arquivo principal fica em `%LOCALAPPDATA%\AssistenteIA\config_geral.json`.
Se um campo estiver inválido, o aplicativo mostra qual campo precisa ser
corrigido e reabre a configuração. Configurações de busca e voz ficam em
arquivos separados na mesma pasta. A memória está em `memoria.db` e os logs
técnicos em `logs\assistente.log`.

Se o servidor aparecer indisponível, confira se o Ollama está aberto e use
**Verificar novamente**. Se um modelo aparecer ausente, escolha outro já
instalado ou execute `ollama pull NOME`. Se o microfone ou a saída de áudio não
forem detectados, confira o dispositivo padrão e as permissões de microfone do
Windows. A digitação pode ser usada sem microfone ou alto-falante.
Quando uma resposta falhar, a janela mostra uma orientação curta para corrigir
o problema. O texto original da exceção não é exibido nem gravado no log.

Para desenvolvedores, os testes são executados com:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

O instalador é gerado com `installer\build.ps1`; ele executa também um teste
de abertura do aplicativo empacotado.
