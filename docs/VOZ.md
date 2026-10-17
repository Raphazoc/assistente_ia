# Voz da assistente

A voz principal é a `pt-BR-AntonioNeural`, usando o serviço online de voz
da Microsoft por meio do [edge-tts](https://github.com/rany2/edge-tts).
O texto a ser falado é enviado ao serviço; o reconhecimento de voz e o
modelo de conversa continuam usando a configuração do projeto.

Para ouvir uma demonstração no dispositivo de áudio padrão do Windows:

```powershell
.\.venv\Scripts\python.exe -m app.fala
```

As dependências de voz já foram instaladas neste ambiente. Para reinstalar:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-voz.txt
```

Em `app/fala.py`, ajuste `VOZ_ONLINE` para mudar a voz, por exemplo para
`pt-BR-FranciscaNeural` (feminina), ou `VELOCIDADE_ONLINE` para mudar o ritmo.
O valor `+0%` usa a velocidade original, e `+3%` deixa a fala um pouco mais ágil.

O áudio é reproduzido em um único fluxo, preparando o próximo trecho em
paralelo. A pontuação é preservada; blocos de código e marcações de formatação
não são lidos literalmente. No modo de voz, o modelo recebe orientação para
responder de forma mais breve e conversada.
As fontes das pesquisas continuam visíveis na resposta em texto, mas a voz
não lê os links nem a lista de fontes em voz alta.

Se a conexão falhar, o programa usa o modelo Piper já existente e tenta
o serviço online novamente após um minuto. Se parte da resposta já tiver
sido falada, a alternativa local recebe somente os trechos restantes.
Para usar apenas a voz local, defina `USAR_VOZ_ONLINE = False` em `app/fala.py`.

No aplicativo, **Configurações → Voz** permite escolher a voz online padrão (Edge) ou
ElevenLabs. Para ElevenLabs, informe a chave da API e o ID de uma voz da sua
conta. O campo de chave vazio mantém a chave já guardada. A chave fica no cofre
de credenciais do sistema, não no arquivo JSON. O texto limpo da resposta é
enviado apenas ao provedor de voz escolhido; fontes e links não são narrados.
Se a API falhar, o Piper local continua disponível como reserva.

## Microfone e troca de modo

Durante a escuta ou a digitação, pressione **Esc** no terminal do programa
para abrir o menu: **1 — digitação**, **2 — áudio**, **3 — alterar nome para
interromper a fala**, **4 — gerenciar memórias**, **5 — ativar/desativar pesquisas na
internet**, **6 — sair e fechar a IA**, **0 — manter o modo atual**.
A entrada em andamento é descartada ao abrir o menu e não é enviada à IA.
Também é possível dizer **"modo texto"** para ir direto ao teclado.
Para voltar ao microfone, digite **"voz"**.
O atalho de teclado funciona no terminal do Windows, incluindo o terminal
integrado do VS Code. Se estiver usando uma entrada sem terminal, digite
**"menu"** ou diga **"menu"**.

O microfone agora identifica fala usando o Silero VAD já incluído no
`faster-whisper`. A gravação termina após aproximadamente **1,5 segundo de
silêncio** depois da fala, em vez de esperar seis segundos fixos.
Pausas mais curtas permitem continuar a mesma frase. Isso detecta uma pausa
na voz; não analisa se a frase está gramaticalmente completa.

Para dar mais tempo entre palavras, aumente `SILENCIO_FINAL` em `app/voz.py`
(por exemplo, `1.5`). Para respostas mais rápidas, diminua com cuidado,
pois uma pausa natural pode encerrar a gravação. O limite de uma fala
contínua é de 30 segundos, e silêncio sem fala não é enviado ao Whisper.
Depois de encerrar a gravação, ainda é necessário transcrever o áudio
e gerar a resposta da IA.

No aplicativo Windows, as abas **Texto** e **Voz** mostram áreas separadas.
Ao selecionar Voz, o microfone é ativado automaticamente. **Mutar microfone**
pausa a escuta e permanece assim mesmo se você alternar entre as abas; voltar
para Texto desliga a captura. A IA espera o início da
fala sem prazo fixo e volta a ouvir após
cada resposta. Enquanto responde, a escuta normal pausa para evitar que a IA
transcreva a própria voz; a interrupção por nome continua disponível se estiver
configurada. O microfone começa desligado ao abrir o aplicativo na aba Texto.

O reconhecimento usa o Whisper `small` com busca mais cuidadosa e dicas para
nomes técnicos em inglês, como Python, GitHub e VS Code. O modelo pode ser
baixado na primeira utilização. Se `small` falhar ao carregar, o programa tenta
`base`. Palavras pronunciadas com sotaque ainda podem exigir confirmação.

## Conversa e interrupção

No modo de áudio, fale diretamente, por exemplo **"explique o que é uma
variável"**. Comandos como **"menu"**, **"modo texto"** e **"sair"** também
funcionam sem nome. Se preferir, **"Aurora, explique Python"** continua
funcionando. O nome sozinho não envia um pedido. Sem a exigência do nome,
outras falas próximas ao microfone também podem ser capturadas.

O nome é usado para interromper uma resposta enquanto a IA está falando.
Altere-o pelo menu **Esc → 3**. A escolha fica salva em `resources/config_voz.json`
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
Em `resources/config_voz.json`, `interromper_por_voz: false` desativa a escuta durante
a reprodução; Espaço e Esc continuam disponíveis.

Os modelos de reconhecimento são preparados em segundo plano. A GPU é usada
para o Whisper apenas quando as bibliotecas CUDA necessárias funcionarem;
caso contrário, a CPU assume. Falhas de microfone, voz online e saída local
estão explicadas em [CONFIABILIDADE.md](CONFIABILIDADE.md).

O gerenciamento de fatos, assuntos, projetos e resumos está descrito em
[MEMORIA.md](MEMORIA.md). No modo de voz, você pode dizer, por exemplo,
**"lembre que prefiro explicações curtas"** para guardar uma lembrança
sem depender da geração de uma resposta pelo modelo.

Para pesquisas online, a assistente mostra as consultas e pede autorização
antes de acessar o buscador. No modo de voz, confirme com **“autorizo”**
apenas após ver a consulta proposta. Os detalhes e os
filtros obrigatórios estão em [INTERNET.md](INTERNET.md).
