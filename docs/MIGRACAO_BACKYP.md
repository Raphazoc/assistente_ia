# Arquivo legado `backyp`

Versões antigas criavam a cópia de segurança anterior à migração da memória em
`backyp/`. A partir desta versão, a abertura do banco procura apenas arquivos
com o nome histórico esperado, copia cada um para `backups/legado/`, compara o
SHA-256 da cópia com o original e só então remove o arquivo da pasta antiga.
Arquivos inesperados, links simbólicos e cópias com nome já existente no destino
permanecem intactos em `backyp/` para revisão manual.

A cópia de um banco antigo continua sendo um arquivo histórico. O comando
`python -m app.banco restaurar` aceita somente backups do esquema atual e não
restaura esse arquivo antigo diretamente. Ao migrar um banco antigo, uma nova
cópia anterior à migração é criada em `backups/legado/`; nenhuma nova cópia é
gravada em `backyp/`.
