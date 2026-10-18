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
Cada execução bem-sucedida do instalador, inclusive atualizações e reinstalações,
zera a memória instalada: apaga `memoria.db`, seus diários SQLite e a pasta
`backups/` em `%LOCALAPPDATA%\AssistenteIA`. A primeira abertura confirma a
limpeza antes de conectar ao banco e cria uma memória vazia. A cópia automática
de bancos antigos foi removida. Configurações, chaves de API e arquivos de
trabalho não são apagados. A desinstalação isolada não limpa esses dados; a
próxima instalação limpa a memória.

O modo antigo por terminal continua disponível com `python main.py`.

## Build no GitHub Actions

O workflow `.github/workflows/windows.yml` executa os testes em pull requests.
Em pushes para `main`, tags `v*` ou pela opção **Run workflow**, ele também gera
o instalador e o SHA-256. Um segundo runner Windows baixa esses arquivos,
confere o hash, instala em uma pasta temporária, abre o executável empacotado,
desinstala e verifica que a pasta do programa foi removida enquanto os dados do
usuário foram preservados. Os dois arquivos ficam disponíveis juntos como
artefato **assistente-ia-windows** por 14 dias. Ao enviar uma tag `vX.Y.Z`
correspondente à versão do código e do instalador, o workflow confere que ela
aponta para um commit de `main` e cria uma **Release Beta em rascunho** com o
mesmo `.exe` e `.sha256`. Revise as notas e publique manualmente após os testes
em uma máquina Windows limpa. Pushes comuns não criam releases.

O runner tem ferramentas de desenvolvimento instaladas e não substitui o teste
em um Windows realmente limpo, sem Python e sem Ollama. Esse teste manual está
descrito em [Testes de integração](docs/TESTES_INTEGRACAO.md).
Builds locais continuam sem assinatura enquanto não houver certificado.
Releases por tag exigem PFX Authenticode nos secrets do repositório: o CI assina
o aplicativo e o instalador, valida ambos e bloqueia o rascunho se faltarem
credenciais ou a assinatura não for válida. O instalador atual, gerado antes de
configurar certificado, permanece sem assinatura. O SHA-256 não comprova autoria.

## Preparar uma release Beta

Siga o [checklist de release](docs/RELEASE.md) antes de criar a tag. A tag deve
apontar para o commit de `main` que contém a versão correspondente em
`app/versao.py` e `installer/AssistenteIA.iss`. O workflow só monta o rascunho;
nenhuma versão é publicada sem revisão manual.
