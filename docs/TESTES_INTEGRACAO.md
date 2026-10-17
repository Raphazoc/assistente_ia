# Testes de integração

Execute a suíte completa na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

`tests/test_integracao.py` usa diretórios temporários e substitui Ollama,
provedores de busca e dispositivos quando precisa provocar falhas. Ele cobre:

| Cenário | Resultado esperado |
| --- | --- |
| Primeira abertura sem Ollama | Configuração inicial abre; conversa não inicia. |
| Configuração inválida | O campo ou arquivo problemático é mostrado; conversa não inicia. |
| Caminhos de aplicativo empacotado | Recursos são copiados para dados do usuário sem sobrescrever configurações ou memória em uma segunda abertura. |
| Banco corrompido | Arquivo é preservado; conexão é fechada; diagnóstico indica problema na memória. |
| Modelo ausente após iniciar | Erro amigável na conversa; uma pergunta seguinte ainda pode ser respondida. |
| Pesquisa sem rede | Resposta local informa que a busca falhou, sem inventar fontes. |
| Falha da API Brave | A consulta autorizada usa DuckDuckGo; fonte e provedor ficam registrados no histórico. |

O comando `installer\build.ps1` ainda executa `--smoke-test` no executável
empacotado, conferindo a abertura da janela e os recursos incluídos. No GitHub
Actions, `installer\test_install.ps1` verifica o SHA-256 e faz instalação,
abertura e desinstalação em outro runner Windows sem o ambiente virtual do
build. O resultado fica no workflow e o instalador, com seu hash, é guardado
como artefato; nenhuma Release é publicada automaticamente.

Antes de publicar uma versão para usuários novos, instale o arquivo
`dist-installer\AssistenteIA-Setup.exe` em um Windows limpo, sem Python, usando
uma conta de teste. Confira a primeira execução, a falta e a instalação do
Ollama, a escolha dos modelos, microfone e alto-falante, uma conversa local,
a desinstalação e se os arquivos de memória permanecem apenas na pasta de dados
do usuário. Esse cenário requer uma máquina ou VM limpa; não é simulado pela
suíte automatizada.
