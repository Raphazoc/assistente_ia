# Voz da assistente

A voz principal é a `pt-BR-AntonioNeural`, usando o serviço online de voz
da Microsoft por meio do [edge-tts](https://github.com/rany2/edge-tts).
O texto a ser falado é enviado ao serviço; o reconhecimento de voz e o
modelo de conversa continuam usando a configuração do projeto.

Para ouvir uma demonstração no dispositivo de áudio padrão do Windows:

```powershell
.\.venv\Scripts\python.exe fala.py
```

As dependências de voz já foram instaladas neste ambiente. Para reinstalar:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-voz.txt
```

Em `fala.py`, ajuste `VOZ_ONLINE` para mudar a voz, por exemplo para
`pt-BR-FranciscaNeural` (feminina), ou `VELOCIDADE_ONLINE` para mudar o ritmo.
O valor `+0%` usa a velocidade original, e `+3%` deixa a fala um pouco mais ágil.

O áudio é reproduzido em um único fluxo, preparando o próximo trecho em
paralelo. A pontuação é preservada; blocos de código e marcações de formatação
não são lidos literalmente. No modo de voz, o modelo recebe orientação para
responder de forma mais breve e conversada.

Se a conexão falhar, o programa usa o modelo Piper já existente e tenta
o serviço online novamente após um minuto. Se parte da resposta já tiver
sido falada, a alternativa local recebe somente os trechos restantes.
Para usar apenas a voz local, defina `USAR_VOZ_ONLINE = False` em `fala.py`.

## Microfone e troca de modo

Durante a escuta ou a digitação, pressione **Esc** no terminal do programa
para abrir o menu: **1 — digitação**, **2 — áudio**, **3 — alterar palavra de
ativação**, **4 — gerenciar memórias**, **0 — manter o modo atual**.
A entrada em andamento é descartada ao abrir o menu e não é enviada à IA.
Também é possível dizer **"Aurora, modo texto"** para ir direto ao teclado.
Para voltar ao microfone, digite **"voz"**.
O atalho de teclado funciona no terminal do Windows, incluindo o terminal
integrado do VS Code. Se estiver usando uma entrada sem terminal, digite
**"menu"** ou diga **"Aurora, menu"**.

O microfone agora identifica fala usando o Silero VAD já incluído no
`faster-whisper`. A gravação termina após aproximadamente **0,7 segundo de
silêncio** depois da fala, em vez de esperar seis segundos fixos.
Pausas mais curtas permitem continuar a mesma frase. Isso detecta uma pausa
na voz; não analisa se a frase está gramaticalmente completa.

Para dar mais tempo entre palavras, aumente `SILENCIO_FINAL` em `voz.py`
(por exemplo, `1.0`). Para respostas mais rápidas, diminua com cuidado,
pois uma pausa natural pode encerrar a gravação. O limite de uma fala
contínua é de 30 segundos, e silêncio sem fala não é enviado ao Whisper.
Depois de encerrar a gravação, ainda é necessário transcrever o áudio
e gerar a resposta da IA.

## Palavra de ativação e interrupção

No modo de áudio, comece seu pedido com **"Aurora"**, por exemplo:
**"Aurora, explique o que é uma variável"**. Você também pode dizer somente
**"Aurora"** e fazer o pedido nos oito segundos seguintes. O nome precisa
aparecer completo no início da fala; menções no meio de outra conversa
não ativam a IA. Os comandos falados, incluindo sair e mudar de modo,
também precisam da ativação. A digitação não precisa dela.

Altere o nome pelo menu **Esc → 3**. A escolha fica salva em `config_voz.json`
e permanece após reiniciar. Você pode escolher de uma a quatro palavras,
com até 40 letras. Prefira um nome distinto de palavras comuns no ambiente.

Durante a resposta falada:

- **Espaço** interrompe o áudio.
- **Esc** interrompe e abre o menu de modos.
- **"Aurora, pare"** interrompe pelo microfone.
- **"Aurora, agora explique outro assunto"** interrompe e envia o novo pedido.

A interrupção pelo teclado também funciona enquanto o serviço online gera
o áudio. A interrupção por voz precisa detectar e transcrever a chamada,
por isso leva mais tempo. Ela usa o reconhecimento local, com janelas de
até 2,5 segundos durante a reprodução.

O microfone aplica filtro de frequências, limiar adaptativo de ruído,
confirmação de fala em blocos consecutivos e rejeição de transcrições de
baixa confiança. O monitor também ignora trechos que repetem a própria
resposta. Esses cuidados reduzem ativações falsas; não garantem eliminá-las.
O filtro não é um cancelador acústico de eco: **use fones** para melhorar a
interrupção por voz quando as caixas de som chegam ao microfone.
Em `config_voz.json`, `interromper_por_voz: false` desativa a escuta durante
a reprodução; Espaço e Esc continuam disponíveis.

O gerenciamento de fatos, assuntos, projetos e resumos está descrito em
[MEMORIA.md](MEMORIA.md). No modo de voz, você pode dizer, por exemplo,
**"Aurora, lembre que prefiro explicações curtas"** para guardar uma lembrança
sem depender da geração de uma resposta pelo modelo.
