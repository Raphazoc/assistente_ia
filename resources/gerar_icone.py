"""Gera o ícone do Assistente IA: conversa, voz e um brilho de IA."""

from pathlib import Path

from PIL import Image, ImageDraw


PASTA = Path(__file__).resolve().parent


def criar():
    tamanho = 1024
    imagem = Image.new("RGBA", (tamanho, tamanho), (0, 0, 0, 0))
    fundo = Image.new("RGBA", imagem.size, (0, 0, 0, 0))
    desenho_fundo = ImageDraw.Draw(fundo)
    for y in range(tamanho):
        razao = y / (tamanho - 1)
        cor = (int(11 + 17 * razao), int(24 + 14 * razao), int(43 + 31 * razao), 255)
        desenho_fundo.line((0, y, tamanho, y), fill=cor)
    mascara = Image.new("L", imagem.size)
    ImageDraw.Draw(mascara).rounded_rectangle((28, 28, 996, 996), radius=226, fill=255)
    imagem.paste(fundo, (0, 0), mascara)
    desenho = ImageDraw.Draw(imagem)
    desenho.rounded_rectangle((52, 52, 972, 972), radius=206,
                               outline=(64, 111, 150, 255), width=21)

    # A cauda faz a forma ser reconhecida como conversa até na barra de tarefas.
    desenho.polygon(((214, 670), (149, 834), (381, 700)), fill=(70, 216, 207, 255))
    desenho.rounded_rectangle((137, 215, 850, 706), radius=150,
                               fill=(70, 216, 207, 255))
    desenho.rounded_rectangle((163, 241, 824, 680), radius=132,
                               outline=(152, 252, 241, 255), width=16)

    # Uma forma de onda simples representa a conversa por voz.
    barras = ((276, 432, 584), (364, 359, 630), (452, 311, 663),
              (540, 369, 620), (628, 430, 584))
    for esquerda, topo, base in barras:
        desenho.rounded_rectangle((esquerda, topo, esquerda + 58, base), radius=29,
                                   fill=(13, 37, 62, 255))

    # Brilho pequeno de IA, mantido fora da área principal para não poluir 16 px.
    desenho.polygon(((796, 118), (813, 164), (859, 181), (813, 198),
                     (796, 244), (779, 198), (733, 181), (779, 164)),
                    fill=(186, 150, 255, 255))
    desenho.ellipse((866, 240, 893, 267), fill=(186, 150, 255, 255))

    imagem.resize((512, 512), Image.Resampling.LANCZOS).save(PASTA / "assistente_ia.png")
    imagem.save(PASTA / "assistente_ia.ico", format="ICO",
                sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                       (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    criar()
