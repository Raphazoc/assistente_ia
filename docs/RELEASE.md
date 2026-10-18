# Checklist de release Beta

Este projeto está na série `0.5.x`; não reduza a versão para `0.2` por causa
de roteiros antigos. Só altere a versão quando houver uma nova release pronta.

1. Atualize `app/versao.py`, `installer/AssistenteIA.iss`, o status do `README.md`
   e o changelog. Use o mesmo número em todos os lugares.
2. Execute os testes, Ruff, mypy e cobertura do workflow; confira Python 3.13
   e 3.14 nos jobs **testes**, **instalador** e **testar_instalacao**.
3. Teste manualmente em Windows sem Python: instalar, primeira execução sem
   Ollama, configurar modelos, conversa local, voz, pesquisa autorizada,
   atualização de uma instalação anterior, desinstalação e preservação do banco.
4. Configure os secrets `ASSISTENTE_PFX_BASE64`, `ASSISTENTE_PFX_PASSWORD` e
   `ASSISTENTE_CERT_THUMBPRINT` no GitHub. O PFX deve ser de certificado de
   assinatura de código válido, com cadeia confiável. Nunca coloque o PFX no
   repositório. O CI assina o executável e instalador, verifica carimbo de tempo,
   certificado esperado e assinatura antes de permitir o rascunho da release.
   Consulte [Assinatura do instalador](ASSINATURA.md) para preparar o certificado.
5. Crie e envie a tag `vX.Y.Z` apontando para o commit validado em `main`.
   O workflow confere a versão, a assinatura, o hash e a instalação antes de criar um
   **rascunho Beta** com o instalador e o manifesto SHA-256.
6. Revise as notas geradas, os arquivos anexados e os limites conhecidos.
   Publique a release manualmente. O aviso de atualização do aplicativo só
   encontra releases publicadas.

Depois de publicar, confira no GitHub que o ativo `AssistenteIA-Setup.exe`
apresenta digest SHA-256 na API de releases. O aplicativo exige esse digest e
uma assinatura Authenticode válida para verificar um instalador escolhido pelo
usuário. Ele não baixa nem executa instaladores automaticamente.

Não coloque bancos, configurações pessoais, chaves de API ou logs nos anexos
nem nas notas. O workflow não executa essa revisão humana.
