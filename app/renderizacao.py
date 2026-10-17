"""Separação conservadora de prosa e blocos Markdown para a interface desktop."""

import re


ABERTURA = re.compile(r"^[ \t]*(`{2,}|~{3,})([A-Za-z0-9_+.#-]*)[ \t]*$")


def fragmentos(texto):
    """Retorna (tipo, linguagem, conteúdo), preservando o código original."""
    linhas = texto.splitlines(keepends=True)
    partes = []
    prosa = []
    indice = 0
    while indice < len(linhas):
        abertura = ABERTURA.fullmatch(linhas[indice].rstrip("\r\n"))
        if not abertura:
            prosa.append(linhas[indice])
            indice += 1
            continue
        cerca, linguagem = abertura.groups()
        fim = indice + 1
        while fim < len(linhas):
            candidata = linhas[fim].strip()
            if candidata and set(candidata) == {cerca[0]} and len(candidata) >= len(cerca):
                break
            fim += 1
        if prosa:
            partes.append(("texto", "", "".join(prosa)))
            prosa = []
        codigo = "".join(linhas[indice + 1:fim]).rstrip("\r\n")
        partes.append(("codigo", linguagem or "código", codigo))
        indice = fim + 1 if fim < len(linhas) else fim
    if prosa:
        partes.append(("texto", "", "".join(prosa)))
    return partes
