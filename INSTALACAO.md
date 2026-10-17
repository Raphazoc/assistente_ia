# Aplicativo para Windows

O aplicativo abre uma janela com **Escrita à esquerda** e **Áudio à direita**.
Em janelas estreitas, as áreas ficam uma abaixo da outra, sem sobreposição.
Mensagens do usuário, da IA, arquivos e erros têm cores próprias. **Enviar**
usa a área de escrita. **Ativar microfone** mantém a escuta ligada: basta falar,
fazer uma pausa para encerrar a frase e aguardar a resposta; a escuta recomeça
automaticamente. **Desligar microfone** encerra a escuta e **Parar resposta**
interrompe a fala da IA. A pesquisa online pode ser ligada ou desligada no topo
da janela. Cada pesquisa ligada ainda pede autorização específica; o filtro de
conteúdo adulto continua ativo.

O instalador inclui Python, dependências e a voz local Piper. O [Ollama](https://ollama.com/)
e os modelos `qwen3:8b` e `qwen3-embedding:0.6b` precisam estar instalados e
em execução neste computador. O reconhecimento de voz pode baixar o modelo
Whisper na primeira utilização; a voz neural online também requer internet.

## Criar o instalador

Em PowerShell, na pasta do projeto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\installer\build.ps1
```

O script instala PyInstaller no `.venv`, gera `dist\AssistenteIA\AssistenteIA.exe`,
verifica que a janela e a voz local foram empacotadas e usa o compilador do
[Inno Setup](https://jrsoftware.org/isinfo.php) para criar
`dist-installer\AssistenteIA-Setup.exe`. Instale Inno Setup 6 ou 7 antes de
rodar o script. Se quiser testar apenas o aplicativo em pasta:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\installer\build.ps1 -SomenteAplicativo
```

O instalador é **por usuário**, sem exigir privilégio de administrador. O
programa fica em `%LOCALAPPDATA%\Programs\AssistenteIA`; o banco, as
configurações e os logs ficam em `%LOCALAPPDATA%\AssistenteIA`. Arquivos
organizados pela assistente ficam em `%USERPROFILE%\Documents\AssistenteIA`.
Atualizar ou desinstalar o programa não remove automaticamente a memória.

Na primeira abertura, o aplicativo copia `memoria.db` da pasta do projeto
quando ela está disponível em `%USERPROFILE%\assistente_ia`. Se o projeto
estiver em outro lugar, feche o aplicativo e copie o banco existente para
`%LOCALAPPDATA%\AssistenteIA\memoria.db` antes de abrir novamente.

O modo antigo por terminal continua disponível com `python main.py`.
