"""Ícones vetoriais simples, renderizados em alta resolução para os botões do desktop."""

import math
from functools import lru_cache

import customtkinter as ctk
from PIL import Image, ImageDraw


def obter(nome, cor="#f3f6ff", tamanho=20):
    # CTkImage guarda PhotoImage associada a uma instância de Tk. Cada janela de
    # testes pode criar outro interpretador; compartilhe somente os pixels PIL.
    imagem = _desenhar(nome, cor, tamanho)
    return ctk.CTkImage(light_image=imagem, dark_image=imagem, size=(tamanho, tamanho))


@lru_cache(maxsize=96)
def _desenhar(nome, cor, tamanho):
    escala = 4
    imagem = Image.new("RGBA", (24 * escala, 24 * escala), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(imagem)
    tinta = (*bytes.fromhex(cor.lstrip("#")), 255)

    def linha(pontos, largura=2.2):
        desenho.line([(round(x * escala), round(y * escala)) for x, y in pontos],
                     fill=tinta, width=round(largura * escala), joint="curve")

    def elipse(caixa, largura=2.2, preencher=False):
        desenho.ellipse(tuple(round(v * escala) for v in caixa),
                       outline=tinta, width=round(largura * escala),
                       fill=tinta if preencher else None)

    def retangulo(caixa, raio=2, largura=2.2, preencher=False):
        desenho.rounded_rectangle(tuple(round(v * escala) for v in caixa),
                                  radius=round(raio * escala), outline=tinta,
                                  width=round(largura * escala),
                                  fill=tinta if preencher else None)

    if nome == "search":
        elipse((3, 3, 15, 15))
        linha(((14, 14), (21, 21)), 2.8)
    elif nome == "memory":
        elipse((3, 3, 21, 9))
        linha(((3, 6), (3, 18)))
        linha(((21, 6), (21, 18)))
        desenho.arc((3 * escala, 10 * escala, 21 * escala, 16 * escala),
                    0, 180, fill=tinta, width=round(2 * escala))
        desenho.arc((3 * escala, 15 * escala, 21 * escala, 21 * escala),
                    0, 180, fill=tinta, width=round(2 * escala))
    elif nome == "settings":
        elipse((8, 8, 16, 16))
        for angulo in range(0, 360, 45):
            rad = math.radians(angulo)
            linha(((12 + 7 * math.cos(rad), 12 + 7 * math.sin(rad)),
                   (12 + 10 * math.cos(rad), 12 + 10 * math.sin(rad))), 3)
    elif nome == "text":
        retangulo((2, 3, 22, 18), raio=3)
        linha(((6, 18), (6, 22), (11, 18)))
        linha(((6, 8), (18, 8)))
        linha(((6, 12), (15, 12)))
    elif nome == "voice":
        retangulo((9, 2, 15, 14), raio=3)
        desenho.arc((5 * escala, 5 * escala, 19 * escala, 19 * escala),
                    0, 180, fill=tinta, width=round(2.2 * escala))
        linha(((12, 19), (12, 22)))
        linha(((8, 22), (16, 22)))
    elif nome == "send":
        linha(((2, 11), (22, 3), (15, 21), (11, 14), (2, 11)))
        linha(((11, 14), (22, 3)))
    elif nome == "stop":
        retangulo((5, 5, 19, 19), raio=2, preencher=True)
    elif nome == "refresh":
        desenho.arc((3 * escala, 3 * escala, 21 * escala, 21 * escala),
                    40, 320, fill=tinta, width=round(2.2 * escala))
        linha(((18, 3), (21, 9), (15, 9)))
    elif nome == "add":
        linha(((12, 3), (12, 21)), 2.8)
        linha(((3, 12), (21, 12)), 2.8)
    elif nome == "edit":
        linha(((4, 20), (8, 19), (20, 7), (17, 4), (5, 16), (4, 20)))
        linha(((14, 7), (17, 10)))
    elif nome == "save":
        retangulo((3, 3, 21, 21), raio=2)
        retangulo((7, 3, 17, 10), raio=0)
        retangulo((7, 14, 17, 21), raio=1)
    elif nome == "delete":
        linha(((4, 7), (20, 7)))
        linha(((9, 4), (15, 4)))
        linha(((6, 8), (7, 21), (17, 21), (18, 8)))
        linha(((10, 11), (10, 18)))
        linha(((14, 11), (14, 18)))
    elif nome == "history":
        elipse((3, 3, 21, 21))
        linha(((12, 7), (12, 12), (16, 15)))
    elif nome == "summary":
        retangulo((5, 2, 19, 22), raio=2)
        for y, fim in ((8, 16), (12, 16), (16, 13)):
            linha(((8, y), (fim, y)))
    elif nome == "check":
        linha(((3, 12), (9, 18), (21, 5)), 2.8)
    elif nome == "close":
        linha(((5, 5), (19, 19)), 2.8)
        linha(((19, 5), (5, 19)), 2.8)
    elif nome == "folder":
        linha(((2, 7), (9, 7), (11, 10), (22, 10), (20, 20), (3, 20), (2, 7)))
    elif nome == "speaker":
        linha(((3, 9), (7, 9), (13, 4), (13, 20), (7, 15), (3, 15), (3, 9)))
        desenho.arc((9 * escala, 5 * escala, 23 * escala, 19 * escala),
                    -55, 55, fill=tinta, width=round(2 * escala))
    elif nome == "copy":
        retangulo((7, 7, 21, 21), raio=2)
        linha(((3, 16), (3, 3), (16, 3)))
    else:
        raise ValueError(f"Ícone desconhecido: {nome}")

    imagem = imagem.resize((tamanho * 2, tamanho * 2), Image.Resampling.LANCZOS)
    return imagem
