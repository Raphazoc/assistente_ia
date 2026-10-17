import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import main
import memoria
import resumos


class MemoriaLongoPrazoTests(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.banco = Path(self.pasta.name) / "memoria.db"
        self.configuracao = patch.object(main, "BANCO", self.banco)
        self.configuracao.start()
        self.conexao = main.iniciar_banco()

    def tearDown(self):
        self.conexao.close()
        self.configuracao.stop()
        self.pasta.cleanup()

    def reiniciar(self):
        self.conexao.close()
        self.conexao = main.iniciar_banco()

    def mensagem(self, papel, texto, assunto=None, projeto=None):
        a, p = memoria.contexto_ativo(self.conexao)
        with self.conexao:
            cursor = self.conexao.execute("""
                INSERT INTO mensagens (papel, conteudo, assunto, projeto)
                VALUES (?, ?, ?, ?)
            """, (papel, texto, a if assunto is None else assunto,
                  p if projeto is None else projeto))
        return cursor.lastrowid

    def fato_com_resposta(self, texto, resposta="Certo, informação recebida."):
        origem = self.mensagem("user", texto)
        assistente = self.mensagem("assistant", resposta)
        memoria.processar_mensagem(self.conexao, origem)
        identificador = self.conexao.execute(
            "SELECT memoria_id FROM fontes_memoria WHERE mensagem_id=?", (origem,)
        ).fetchone()[0]
        return identificador, origem, assistente

    def vetor_fato(self, identificador, vetor=(1, 0)):
        with self.conexao:
            self.conexao.execute("INSERT INTO vetores_lembrancas VALUES (?, ?, ?)",
                                 (identificador, main.MODELO_MEMORIA, json.dumps(vetor)))

    def buscar(self, pergunta, vetores=None):
        vetores = vetores or Mock(return_value=[[1, 0]])
        with contextlib.redirect_stdout(io.StringIO()):
            return memoria.selecionar(self.conexao, pergunta, vetores, main.MODELO_MEMORIA)

    def test_migracao_preserva_registros_e_cria_copia_antes_de_alterar(self):
        legado = Path(self.pasta.name) / "legado.db"
        conexao = sqlite3.connect(legado)
        with conexao:
            conexao.execute("""
                CREATE TABLE mensagens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    papel TEXT NOT NULL,
                    conteudo TEXT NOT NULL,
                    data TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conexao.execute("INSERT INTO mensagens(papel,conteudo) VALUES ('user', 'Meu nome é Alice.')")
            conexao.execute("INSERT INTO mensagens(papel,conteudo) VALUES ('assistant', 'Olá, Alice.')")
        conexao.close()

        with patch.object(main, "BANCO", legado), contextlib.redirect_stdout(io.StringIO()):
            migrada = main.iniciar_banco()
            try:
                self.assertEqual(migrada.execute(
                    "SELECT id,papel,conteudo FROM mensagens ORDER BY id"
                ).fetchall(), [(1, "user", "Meu nome é Alice."), (2, "assistant", "Olá, Alice.")])
                self.assertEqual(migrada.execute(
                    "SELECT assunto,projeto,ignorar_memoria FROM mensagens WHERE id=1"
                ).fetchone(), ("geral", "", 0))
            finally:
                migrada.close()
            segunda = main.iniciar_banco()
            segunda.close()

        copias = list((Path(self.pasta.name) / "backyp").glob("memoria_antes_v2_*.db"))
        self.assertEqual(len(copias), 1)
        copia = sqlite3.connect(copias[0])
        try:
            self.assertEqual(copia.execute("SELECT COUNT(*) FROM mensagens").fetchone()[0], 2)
            self.assertNotIn("assunto", {r[1] for r in copia.execute("PRAGMA table_info(mensagens)")})
            self.assertIsNone(copia.execute(
                "SELECT name FROM sqlite_master WHERE name='memorias'"
            ).fetchone())
        finally:
            copia.close()

    def test_fato_duravel_deduplica_acentos_e_preserva_importancia_no_reinicio(self):
        identificador = memoria.guardar(self.conexao, "Prefiro café sem açúcar.", importancia=5)
        repetido = memoria.guardar(self.conexao, "PREFIRO CAFE SEM ACUCAR!", importancia=2)
        self.assertEqual(repetido, identificador)
        self.reiniciar()
        self.assertEqual(memoria.guardar(self.conexao, "Prefiro café sem açúcar."), identificador)
        self.assertEqual(self.conexao.execute("SELECT COUNT(*) FROM memorias").fetchone()[0], 1)
        self.assertEqual(self.conexao.execute(
            "SELECT importancia FROM memorias WHERE id=?", (identificador,)
        ).fetchone()[0], 5)
        self.assertIn("Prefiro café sem açúcar.", " ".join(self.buscar("Qual café eu prefiro?")))

    def test_correcao_de_fato_canonico_substitui_valor_e_oculta_fontes_antigas(self):
        identificador, origem, resposta = self.fato_com_resposta("Moro em São Paulo.")
        with self.conexao:
            self.conexao.execute("INSERT INTO vetores_memoria VALUES (?, ?, ?)",
                                 (origem, main.MODELO_MEMORIA, "[1, 0]"))
        nova_origem = self.mensagem("user", "Moro em Recife.")
        memoria.processar_mensagem(self.conexao, nova_origem)
        self.assertEqual(self.conexao.execute(
            "SELECT id,conteudo,chave FROM memorias"
        ).fetchall(), [(identificador, "Moro em Recife.", "localizacao")])
        self.assertEqual(self.conexao.execute(
            "SELECT id,ignorar_memoria FROM mensagens ORDER BY id"
        ).fetchall(), [(origem, 1), (resposta, 1), (nova_origem, 0)])
        self.assertIsNone(self.conexao.execute(
            "SELECT 1 FROM vetores_memoria WHERE mensagem_id=?", (origem,)
        ).fetchone())
        self.reiniciar()
        memoria.processar_pendentes(self.conexao)
        contexto = " ".join(self.buscar("Onde moro?"))
        self.assertIn("Recife", contexto)
        self.assertNotIn("São Paulo", contexto)

    def test_exclusao_seletiva_nao_ressuscita_apos_reinicio_e_reindexacao(self):
        apagar, origem, resposta = self.fato_com_resposta("Meu nome é Iara.")
        manter, _, _ = self.fato_com_resposta("Meu projeto usa SQLite.")
        self.vetor_fato(apagar)
        with self.conexao:
            self.conexao.execute("INSERT INTO vetores_memoria VALUES (?, ?, ?)",
                                 (origem, main.MODELO_MEMORIA, "[1, 0]"))
        memoria.excluir(self.conexao, apagar)
        self.reiniciar()
        memoria.processar_pendentes(self.conexao)
        with patch.object(main, "gerar_vetores", side_effect=lambda textos: [[1, 0] for _ in textos]):
            with contextlib.redirect_stdout(io.StringIO()):
                main.indexar_memorias_antigas(self.conexao)
        self.assertEqual([r[0] for r in memoria.listar(self.conexao, todos=True)], [manter])
        self.assertIsNone(self.conexao.execute(
            "SELECT 1 FROM vetores_memoria WHERE mensagem_id=?", (origem,)
        ).fetchone())
        self.assertEqual(self.conexao.execute(
            "SELECT COUNT(*) FROM mensagens WHERE id IN (?,?) AND ignorar_memoria=1", (origem, resposta)
        ).fetchone()[0], 2)
        self.assertNotIn("Iara", str(main.carregar_historico(self.conexao)))
        self.assertNotIn("Iara", " ".join(self.buscar("O que você lembra de mim?")))

    def test_memoria_manual_vincula_texto_existente_e_exclusao_oculta_o_par(self):
        origem = self.mensagem("user", "Anote isso: Meu apelido é Foguete.")
        resposta = self.mensagem("assistant", "Vou usar esse apelido.")
        identificador = memoria.guardar(self.conexao, "Meu apelido é Foguete.")
        self.assertIsNotNone(self.conexao.execute(
            "SELECT 1 FROM fontes_memoria WHERE memoria_id=? AND mensagem_id=?", (identificador, origem)
        ).fetchone())
        memoria.excluir(self.conexao, identificador)
        memoria.processar_pendentes(self.conexao)
        self.assertEqual(self.conexao.execute(
            "SELECT ignorar_memoria FROM mensagens WHERE id IN (?,?) ORDER BY id", (origem, resposta)
        ).fetchall(), [(1,), (1,)])
        self.assertEqual(self.conexao.execute("SELECT COUNT(*) FROM memorias").fetchone()[0], 0)
        self.assertEqual(resumos.resumir_pendentes(self.conexao, forcar=True), 0)

    def test_assuntos_projetos_e_contexto_persistem_com_isolamento_na_busca(self):
        memoria.definir_contexto(self.conexao, assunto="pessoal")
        pessoal = memoria.guardar(self.conexao, "Prefiro café sem açúcar.")
        memoria.definir_contexto(self.conexao, assunto="programação", projeto="Aurora")
        aurora = memoria.guardar(self.conexao, "O banco do projeto Aurora é SQLite.")
        memoria.definir_contexto(self.conexao, projeto="Atlas")
        atlas = memoria.guardar(self.conexao, "O banco do projeto Atlas é PostgreSQL.")
        memoria.definir_contexto(self.conexao, assunto="estudos")
        memoria.guardar(self.conexao, "Estudar normalização de banco de dados.")
        memoria.definir_contexto(self.conexao, assunto="programação")
        self.reiniciar()
        self.assertEqual(memoria.contexto_ativo(self.conexao), ("programação", "atlas"))
        self.assertEqual([r[0] for r in memoria.listar(self.conexao)], [atlas])
        contexto = " ".join(self.buscar("Lembra do banco do projeto?"))
        self.assertIn("PostgreSQL", contexto)
        self.assertIn("café sem açúcar", contexto)
        self.assertNotIn("SQLite", contexto)
        self.assertNotIn("normalização", contexto)
        self.assertEqual(self.conexao.execute(
            "SELECT assunto,projeto FROM memorias WHERE id=?", (aurora,)
        ).fetchone(), ("programação", "aurora"))
        self.assertEqual(len(memoria.listar(self.conexao, todos=True)), 4)
        self.assertNotEqual(pessoal, atlas)

    def test_busca_lexical_funciona_quando_modelo_de_embeddings_falha(self):
        alvo = memoria.guardar(self.conexao, "O banco principal é PostgreSQL.")
        memoria.guardar(self.conexao, "Prefiro café sem açúcar.", importancia=5)
        self.vetor_fato(alvo)
        offline = Mock(side_effect=RuntimeError("Servidor offline"))
        encontrados = self.buscar("Qual banco PostgreSQL escolhi?", offline)
        offline.assert_called_once()
        self.assertIn("PostgreSQL", " ".join(encontrados))
        self.assertNotIn("café", " ".join(encontrados))

    def test_busca_semantica_encontra_parafrase_e_exclui_ruido_importante(self):
        alvo = memoria.guardar(self.conexao, "A máquina necessita de mais capacidade.", importancia=3)
        ruido = memoria.guardar(self.conexao, "Prefiro café sem açúcar.", importancia=5)
        self.vetor_fato(alvo, (1, 0))
        self.vetor_fato(ruido, (-1, 0))
        encontrados = self.buscar("Como ampliar a infraestrutura?", Mock(return_value=[[1, 0]]))
        self.assertEqual(len(encontrados), 1)
        self.assertIn("máquina necessita", encontrados[0])
        self.assertNotIn("café", encontrados[0])

    def test_fato_e_mensagem_de_origem_nao_duplicam_contexto(self):
        identificador, origem, _ = self.fato_com_resposta("Meu projeto usa SQLite.")
        self.vetor_fato(identificador)
        with self.conexao:
            self.conexao.execute("INSERT INTO vetores_memoria VALUES (?, ?, ?)",
                                 (origem, main.MODELO_MEMORIA, "[1, 0]"))
        encontrados = self.buscar("Qual SQLite usamos?")
        self.assertEqual(len(encontrados), 1)
        self.assertTrue(encontrados[0].startswith("Fato #"))

    def test_edicao_invalida_vetor_e_mantem_novo_texto_e_metadados(self):
        identificador, origem, _ = self.fato_com_resposta("Meu nome é Maria.")
        self.vetor_fato(identificador)
        memoria.editar(self.conexao, identificador, "Meu nome é Lia.",
                       assunto="Pessoal", projeto="Casa", importancia=5)
        self.assertEqual(self.conexao.execute(
            "SELECT conteudo,assunto,projeto,importancia FROM memorias WHERE id=?", (identificador,)
        ).fetchone(), ("Meu nome é Lia.", "pessoal", "casa", 5))
        self.assertIsNone(self.conexao.execute(
            "SELECT 1 FROM vetores_lembrancas WHERE memoria_id=?", (identificador,)
        ).fetchone())
        self.assertEqual(self.conexao.execute(
            "SELECT ignorar_memoria FROM mensagens WHERE id=?", (origem,)
        ).fetchone()[0], 1)

    def test_edicao_duplicada_desfaz_supressao_e_preserva_fatos(self):
        primeiro, origem, resposta = self.fato_com_resposta("Prefiro café sem açúcar.")
        memoria.guardar(self.conexao, "Gosto de chá verde.")
        with self.assertRaises(ValueError):
            memoria.editar(self.conexao, primeiro, "Gosto de chá verde.")
        self.assertEqual(self.conexao.execute(
            "SELECT conteudo FROM memorias WHERE id=?", (primeiro,)
        ).fetchone()[0], "Prefiro café sem açúcar.")
        self.assertEqual(self.conexao.execute(
            "SELECT ignorar_memoria FROM mensagens WHERE id IN (?,?) ORDER BY id", (origem, resposta)
        ).fetchall(), [(0,), (0,)])

    def test_comandos_guardam_listam_editam_excluem_e_organizam(self):
        memoria.tratar_comando(self.conexao, "/assunto Trabalho")
        memoria.tratar_comando(self.conexao, "/projeto Atlas")
        self.assertIn("salva", memoria.tratar_comando(self.conexao, "/lembrar A entrega será em novembro."))
        identificador = self.conexao.execute("SELECT id FROM memorias").fetchone()[0]
        self.assertIn("novembro", memoria.tratar_comando(self.conexao, "/memorias"))
        self.assertIn("atualizada", memoria.tratar_comando(
            self.conexao, f"/memoria editar {identificador} A entrega será em dezembro."
        ))
        self.assertEqual(self.conexao.execute(
            "SELECT conteudo,assunto,projeto FROM memorias WHERE id=?", (identificador,)
        ).fetchone(), ("A entrega será em dezembro.", "trabalho", "atlas"))
        self.assertIn("excluída", memoria.tratar_comando(self.conexao, f"/memoria excluir {identificador}"))
        self.assertIn("Nenhuma", memoria.tratar_comando(self.conexao, "/memorias"))
        self.assertIsNone(memoria.tratar_comando(self.conexao, "Vamos conversar normalmente."))
        with self.assertRaises(ValueError):
            memoria.excluir(self.conexao, identificador)

    def test_edicao_invalida_resumo_e_regeneracao_omite_fato_antigo(self):
        identificador, _, _ = self.fato_com_resposta("Meu nome é Cecília.", "Olá, Cecília.")
        self.fato_com_resposta("Meu projeto usa Python.", "Decidimos manter Python.")
        self.assertEqual(resumos.resumir_pendentes(self.conexao, forcar=True), 1)
        self.assertIn("Cecília", self.conexao.execute("SELECT conteudo FROM resumos_conversa").fetchone()[0])
        memoria.editar(self.conexao, identificador, "Meu nome é Laura.")
        self.assertEqual(self.conexao.execute("SELECT COUNT(*) FROM resumos_conversa").fetchone()[0], 0)
        self.assertEqual(resumos.resumir_pendentes(self.conexao, forcar=True), 1)
        texto = self.conexao.execute("SELECT conteudo FROM resumos_conversa").fetchone()[0]
        self.assertNotIn("Cecília", texto)
        self.assertIn("Python", texto)
        self.assertIn("Laura", " ".join(self.buscar("Qual meu nome?")))

    def test_exclusao_oculta_parafrases_derivadas_e_sua_cadeia_no_historico(self):
        identificador, _, _ = self.fato_com_resposta("Moro em Curitiba.")
        pergunta = self.mensagem("user", "Qual minha cidade?")
        memoria.registrar_contexto(self.conexao,
                                  f"Fato #{identificador} [geral; projeto: geral]: Moro em Curitiba.", [])
        with contextlib.redirect_stdout(io.StringIO()):
            primeira = main.salvar_mensagem(self.conexao, "assistant", "Você vive em Curitiba.")
        historico = [{"id": primeira, "role": "assistant", "content": "Você vive em Curitiba."}]
        segunda_pergunta = self.mensagem("user", "Pode repetir?")
        memoria.registrar_contexto(self.conexao, "", historico)
        with contextlib.redirect_stdout(io.StringIO()):
            segunda = main.salvar_mensagem(self.conexao, "assistant", "Sua cidade é Curitiba.")
        self.assertEqual(resumos.resumir_pendentes(self.conexao, forcar=True), 1)
        memoria.excluir(self.conexao, identificador)
        self.assertEqual(self.conexao.execute(
            "SELECT ignorar_memoria FROM mensagens WHERE id IN (?,?) ORDER BY id", (primeira, segunda)
        ).fetchall(), [(1,), (1,)])
        self.assertEqual(memoria.filtrar_historico(self.conexao, historico), [])
        self.assertEqual(self.conexao.execute("SELECT COUNT(*) FROM resumos_conversa").fetchone()[0], 0)
        self.reiniciar()
        memoria.processar_pendentes(self.conexao)
        resumos.resumir_pendentes(self.conexao, forcar=True)
        self.assertNotIn("Curitiba", str(main.carregar_historico(self.conexao)))
        self.assertEqual(self.conexao.execute(
            "SELECT ignorar_memoria FROM mensagens WHERE id IN (?,?) ORDER BY id", (pergunta, segunda_pergunta)
        ).fetchall(), [(0,), (0,)])

    def test_proveniencia_via_conversa_e_resumo_tambem_oculta_derivadas(self):
        identificador, origem, _ = self.fato_com_resposta("Me chamo Beatriz.")
        resumos.resumir_pendentes(self.conexao, forcar=True)
        resumo = self.conexao.execute("SELECT id FROM resumos_conversa").fetchone()[0]
        derivadas = []
        for marcador in (f"Conversa #{origem}", f"Resumo #{resumo}"):
            self.mensagem("user", "Como posso me apresentar?")
            memoria.registrar_contexto(self.conexao, marcador, [])
            with contextlib.redirect_stdout(io.StringIO()):
                derivadas.append(main.salvar_mensagem(self.conexao, "assistant", "Apresente-se como Beatriz."))
        memoria.excluir(self.conexao, identificador)
        for derivada in derivadas:
            self.assertEqual(self.conexao.execute(
                "SELECT ignorar_memoria FROM mensagens WHERE id=?", (derivada,)
            ).fetchone()[0], 1)

    def test_proveniencia_de_resumo_nao_inclui_projeto_intercalado(self):
        memoria.definir_contexto(self.conexao, assunto="programação", projeto="Aurora")
        self.fato_com_resposta("Meu projeto usa SQLite.")
        memoria.definir_contexto(self.conexao, projeto="Atlas")
        outro_projeto, _, _ = self.fato_com_resposta("Meu projeto usa PostgreSQL.")
        memoria.definir_contexto(self.conexao, projeto="Aurora")
        self.fato_com_resposta("Prefiro testes automáticos.")
        resumos.resumir_pendentes(self.conexao, forcar=True, escopo=("programação", "aurora"))
        resumo = self.conexao.execute("SELECT id FROM resumos_conversa").fetchone()[0]
        memoria.registrar_contexto(self.conexao, f"Resumo #{resumo}", [])
        with contextlib.redirect_stdout(io.StringIO()):
            derivada = main.salvar_mensagem(self.conexao, "assistant", "Para Aurora, mantenha SQLite e testes.")
        memoria.excluir(self.conexao, outro_projeto)
        self.assertEqual(self.conexao.execute(
            "SELECT ignorar_memoria FROM mensagens WHERE id=?", (derivada,)
        ).fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
