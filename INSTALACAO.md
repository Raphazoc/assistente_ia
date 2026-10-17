# Aplicativo para Windows

Na primeira abertura, o [assistente de configuração](docs/PRIMEIRA_EXECUCAO.md)
verifica o Ollama, mostra modelos disponíveis e oferece testes de áudio. A
conversa começa depois de escolher dois modelos instalados. O botão
**Configurações** reúne modelos, idioma, histórico, pesquisa, voz e diagnóstico.

O aplicativo abre uma janela com duas abas exclusivas: **Texto** e **Voz**.
Em Texto, a conversa e o campo de digitação ocupam a área principal. Em Voz,
aparecem o estado do microfone, a onda de áudio, os controles e a transcrição.
Ao entrar na aba Voz, o microfone começa a ouvir automaticamente; ao voltar
para Texto, ele é desligado. O botão **Mutar microfone** permite pausar a escuta
sem sair da aba Voz. O mute permanece ao alternar abas.
Na janela Configurações, as abas Pesquisa e Voz permitem configurar Brave Search e ElevenLabs com chaves
guardadas no cofre do sistema. As opções padrão continuam disponíveis sem chave.
Mensagens do usuário, da IA, arquivos e erros têm cores próprias. **Enviar**
usa a área de escrita. **Ativar microfone** mantém a escuta ligada: basta falar,
fazer uma pausa para encerrar a frase e aguardar a resposta; a escuta recomeça
automaticamente. **Desligar microfone** encerra a escuta e **Parar resposta**
interrompe a fala da IA. A pesquisa online pode ser ligada ou desligada no topo
da janela. Cada pesquisa ligada ainda pede autorização específica; o filtro de
conteúdo adulto continua ativo.
O botão **Memória** abre lembranças, histórico e resumos com edição e exclusão
individuais. **Não salvar esta troca**, no rodapé da Escrita, deixa aquela
pergunta e resposta fora do banco. Exemplos de código aparecem em blocos
destacados, com cores de sintaxe e opção de copiar.

O instalador inclui Python, dependências e a voz local Piper. O [Ollama](https://ollama.com/)
e os modelos `qwen3:8b` e `qwen3-embedding:0.6b` precisam estar instalados e
em execução neste computador. O reconhecimento de voz pode baixar o modelo
Whisper `small` na primeira utilização; se ele não estiver disponível, o
programa tenta o modelo `base`. A voz neural online também requer internet.

## Criar o instalador

Em PowerShell, na pasta do projeto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\installer\build.ps1
```

O script instala PyInstaller no `.venv`, confere que a versão do aplicativo e a
do instalador coincidem, gera `dist\AssistenteIA\AssistenteIA.exe`, verifica que
a janela e a voz local foram empacotadas e usa o compilador do
[Inno Setup](https://jrsoftware.org/isinfo.php) para criar
`dist-installer\AssistenteIA-Setup.exe`. Ele também gera
`dist-installer\AssistenteIA-Setup.exe.sha256` para conferir o download.
Instale Inno Setup 6 ou 7 antes de
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

## Build no GitHub Actions

O workflow `.github/workflows/windows.yml` executa os testes em pull requests.
Em pushes para `main`, tags `v*` ou pela opção **Run workflow**, ele também gera
o instalador e o SHA-256. Um segundo runner Windows baixa esses arquivos,
confere o hash, instala em uma pasta temporária, abre o executável empacotado,
desinstala e verifica que a pasta do programa foi removida enquanto os dados do
usuário foram preservados. Os dois arquivos ficam disponíveis juntos como
artefato **assistente-ia-windows** por 14 dias. O workflow não publica Release:
para distribuir, publique o mesmo `.exe` e `.sha256` após revisar o resultado.

O runner tem ferramentas de desenvolvimento instaladas e não substitui o teste
em um Windows realmente limpo, sem Python e sem Ollama. Esse teste manual está
descrito em [Testes de integração](docs/TESTES_INTEGRACAO.md).
O instalador atual não possui assinatura digital; uma futura versão assinada
exige certificado de assinatura de código. O SHA-256 comprova integridade em
relação ao arquivo publicado, mas não substitui uma assinatura.
