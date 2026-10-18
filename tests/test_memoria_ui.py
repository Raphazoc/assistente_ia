"""Fluxos de uso da janela de memória, sem acessar o banco real."""

import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from app.memoria_ui import JanelaMemoria


def _dados():
    return {
        "ativa": True,
        "contexto": ("geral", ""),
        "lembrancas": [
            {"id": 7, "tipo": "fato", "assunto": "trabalho", "projeto": "site",
             "importancia": 4, "conteudo": "Prefere exemplos curtos.", "fontes": 2, "usos": 3},
            {"id": 8, "tipo": "preferencia", "assunto": "pessoal", "projeto": "",
             "importancia": 5, "conteudo": "Respostas em português.", "fontes": 1, "usos": 1},
        ],
        "historico": [
            {"id": 21, "data": "2026-10-18", "papel": "user", "assunto": "trabalho",
             "projeto": "site", "conteudo": "Mensagem completa de exemplo.",
             "ignorar_memoria": False},
        ],
        "resumos": [
            {"id": 30, "assunto": "trabalho", "projeto": "site", "inicio_id": 20,
             "fim_id": 21, "conteudo": "Resumo completo de exemplo."},
        ],
        "total_lembrancas": 2,
        "total_historico": 1,
    }


class JanelaMemoriaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.raiz = tk.Tk()
        except tk.TclError:
            raise unittest.SkipTest("Ambiente sem interface gráfica")
        cls.raiz.geometry("100x100+0+0")

    @classmethod
    def tearDownClass(cls):
        cls.raiz.destroy()

    def setUp(self):
        self.pedidos = Mock()
        self.painel = JanelaMemoria(self.raiz, self.pedidos)
        self.painel.mostrar_dados(_dados())
        self.raiz.update()

    def tearDown(self):
        if hasattr(self, "painel") and self.painel.janela.winfo_exists():
            self.painel.janela.destroy()

    def test_abas_e_acoes_permanecem_visiveis_no_tamanho_minimo(self):
        self.painel.janela.geometry("760x560")
        for nome in ("Lembranças", "Editar", "Histórico", "Resumos"):
            self.painel.abas.set(nome)
            self.raiz.update()
            self.assertEqual(self.painel.abas.get(), nome)
        self.assertGreater(self.painel.previa_historico.winfo_height(), 80)
        self.assertGreater(self.painel.previa_resumo.winfo_height(), 80)
        self.assertGreater(self.painel.botao_nao_usar.winfo_height(), 25)
        self.painel.abas.set("Editar")
        self.raiz.update()
        self.assertGreater(self.painel.texto_lembranca.winfo_height(), 80)
        self.assertLess(
            self.painel.texto_lembranca.winfo_rootx() + self.painel.texto_lembranca.winfo_width(),
            self.painel.janela.winfo_rootx() + self.painel.janela.winfo_width(),
        )

    def test_editar_e_criar_lembrancas_pelo_formulario(self):
        self.painel.arvore_lembrancas.selection_set("7")
        self.painel._selecionar_lembranca()
        self.painel._editar_selecionada()
        self.assertEqual(self.painel.abas.get(), "Editar")
        self.assertEqual(self.painel.texto_lembranca.get("1.0", "end-1c"), "Prefere exemplos curtos.")
        self.painel.texto_lembranca.delete("1.0", "end")
        self.painel.texto_lembranca.insert("1.0", "Prefere exemplos com código.")
        self.painel._salvar()
        self.pedidos.assert_any_call("editar", texto="Prefere exemplos com código.",
                                    tipo="fato", assunto="trabalho", projeto="site",
                                    importancia=4, id=7)
        self.painel._nova()
        self.painel.texto_lembranca.insert("1.0", "Nova informação")
        self.painel._salvar()
        self.pedidos.assert_any_call("guardar", texto="Nova informação", tipo="fato",
                                    assunto="geral", projeto="", importancia=4)

    def test_busca_atualiza_selecao_e_acoes(self):
        self.painel.arvore_lembrancas.selection_set("7")
        self.painel._selecionar_lembranca()
        self.assertEqual(self.painel.botao_editar.cget("state"), "normal")
        self.painel.busca.set("português")
        self.assertEqual(self.painel.arvore_lembrancas.get_children(), ("8",))
        self.assertEqual(self.painel.botao_editar.cget("state"), "disabled")
        self.assertEqual(self.painel.botao_excluir.cget("state"), "disabled")

    def test_historico_resumos_e_exclusao(self):
        self.painel.arvore_historico.selection_set("21")
        self.painel._selecionar_historico()
        self.assertIn("Mensagem completa", self.painel.previa_historico.get("1.0", "end"))
        self.assertEqual(self.painel.botao_nao_usar.cget("state"), "normal")
        self.painel.arvore_resumos.selection_set("30")
        self.painel._selecionar_resumo()
        self.assertIn("Resumo completo", self.painel.previa_resumo.get("1.0", "end"))
        with patch("app.memoria_ui.messagebox.askyesno", return_value=True):
            self.painel._nao_usar()
        self.pedidos.assert_any_call("nao_usar", id=21)
        self.painel.arvore_lembrancas.selection_set("8")
        with patch("app.memoria_ui.messagebox.askyesno", return_value=True):
            self.painel._excluir()
        self.pedidos.assert_any_call("excluir", id=8)


if __name__ == "__main__":
    unittest.main()
