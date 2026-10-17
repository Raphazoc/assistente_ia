import os
import sys


class SolicitarMenu(Exception):
    """Interrompe a entrada atual para escolher o modo de conversa."""


class InterromperFala(Exception):
    """Cancela a reprodução sem tratar a interrupção como uma falha de voz."""


def tecla_durante_fala():
    """Lê atalhos não bloqueantes do Windows para menu e cancelamento da fala."""
    if os.name != "nt" or sys.stdin is None or not sys.stdin.isatty():
        return None
    import msvcrt

    while msvcrt.kbhit():
        tecla = msvcrt.getwch()
        if tecla in ("\x00", "\xe0"):
            msvcrt.getwch()
        elif tecla == "\x1b":
            return "menu"
        elif tecla == " ":
            return "parar"
    return None


def ler_texto(mensagem):
    """Lê uma linha, permitindo abrir o menu com Esc sem pressionar Enter."""
    if os.name != "nt" or not sys.stdin.isatty():
        return input(mensagem)

    import msvcrt

    print(mensagem, end="", flush=True)
    caracteres = []
    while True:
        tecla = msvcrt.getwch()
        if tecla == "\x1b":
            print()
            raise SolicitarMenu()
        if tecla == "\x03":
            raise KeyboardInterrupt()
        if tecla == "\x1a":
            raise EOFError()
        if tecla in ("\r", "\n"):
            print()
            return "".join(caracteres)
        if tecla == "\b":
            if caracteres:
                caracteres.pop()
                print("\b \b", end="", flush=True)
        elif tecla in ("\x00", "\xe0"):
            msvcrt.getwch()
        elif tecla.isprintable():
            caracteres.append(tecla)
            print(tecla, end="", flush=True)
