# Validação da Beta em computadores Windows

Execute a matriz em **contas de teste sem dados pessoais**, preferencialmente em
um Windows 10 e um Windows 11 reais, com e sem Ollama. O instalador reinicia a
memória a cada instalação; nunca execute o teste de instalação em uma conta com
histórico que queira preservar. Registre data, versão do Windows, CPU, RAM,
presença de Python/Ollama/modelos, SHA-256 do instalador, resultado e falhas.

| Cenário | Windows 10 | Windows 11 | Critério |
| --- | --- | --- | --- |
| Instalação em conta limpa, sem Python | pendente | pendente | Abre sem dependência de Python do sistema |
| Ollama ausente / modelo ausente | pendente | pendente | Diagnóstico compreensível, sem travar |
| Conversa, memória e restauração | pendente | pendente | Dados corretos e sem regressão |
| Voz com microfone real | pendente | pendente | Captura, pausa e encerramento seguros |
| Instalação, atualização e desinstalação | pendente | pendente | Conferir dados antes/depois em conta descartável |
| Assinatura Authenticode oficial | pendente | pendente | Certificado confiável e carimbo de tempo válidos |

O CI testa a instalação em runner Windows descartável, o que não comprova o
comportamento em hardware e drivers variados. A matriz acima permanece pendente
de validação em máquinas reais.

Antes de uma release pública, use o roteiro de [release](RELEASE.md) e
[assinatura](ASSINATURA.md). Sem certificado Authenticode oficial, a etapa de
assinatura do pipeline falha e a release não deve ser publicada como assinada.
