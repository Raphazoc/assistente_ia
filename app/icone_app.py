"""Ícone visual compartilhado pela janela, pelo cabeçalho e pelo instalador."""

import os
import sys
import tkinter as tk
from pathlib import Path

import customtkinter as ctk
from PIL import Image


def recursos():
    raiz = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return raiz / "resources"


def aplicar(janela, padrao=False):
    """Aplica o mesmo símbolo à janela e aos diálogos, com fallback para Tk."""
    pasta = recursos()
    png = pasta / "assistente_ia.png"
    ico = pasta / "assistente_ia.ico"
    if png.is_file():
        try:
            foto = tk.PhotoImage(file=str(png))
            janela._icone_assistente = foto
            janela.iconphoto(padrao, foto)
        except tk.TclError:
            pass
    if os.name == "nt" and ico.is_file():
        try:
            if padrao:
                janela.iconbitmap(default=str(ico))
            else:
                janela.iconbitmap(str(ico))
        except tk.TclError:
            pass


def imagem_cabecalho(tamanho=54):
    with Image.open(recursos() / "assistente_ia.png") as origem:
        imagem = origem.convert("RGBA")
    return ctk.CTkImage(light_image=imagem, dark_image=imagem, size=(tamanho, tamanho))
