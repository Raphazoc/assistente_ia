# Contribuir

O projeto está em Beta. Abra uma issue para mudanças grandes e descreva o
problema observado, o comportamento desejado e como reproduzi-lo. Para corrigir
um bug, trabalhe em uma branch e envie um pull request com a mudança mais
focada possível.

1. Use Python 3.13 e crie `.venv` conforme o [README](README.md).
2. Instale `requirements.txt` e execute
   `.\.venv\Scripts\python.exe -m unittest discover -s tests -q`.
3. Se alterar a interface Windows, execute
   `.\.venv\Scripts\python.exe aplicativo.py --smoke-test`.
4. Atualize os guias relacionados e explique no PR os testes executados.
5. Verifique `git status` antes de enviar. Não inclua `.db`, backups, logs,
   chaves de API ou configurações pessoais.

Para mudanças no instalador, siga [INSTALACAO.md](INSTALACAO.md) e
[docs/RELEASE.md](docs/RELEASE.md). O CI monta e testa o instalador; uma tag
de versão gera somente um rascunho de release para revisão.
