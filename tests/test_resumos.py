import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import resumos


class ResumosConversaTests(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.banco = Path(self.pasta.name) / "resumos.db"
        self.conexao = sqlite3.connect(self.banco)
        self.conexao.execute("""
            CREATE TABLE mensagens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                papel TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                assunto TEXT DEFAULT 'geral',
                projeto TEXT DEFAULT '',
                ignorar_memoria INTEGER DEFAULT 0
            )
        """)

    def tearDown(self):
        self.conexao.close()
        self.pasta.cleanup()

    def salvar(self, papel, conteudo, assunto="geral", projeto="", ignorar=0):
        with self.conexao:
            cursor = self.conexao.execute("""
                INSERT INTO mensagens (papel, conteudo, assunto, projeto, ignorar_memoria)
                VALUES (?, ?, ?, ?, ?)
            """, (papel, conteudo, assunto, projeto, ignorar))
        return cursor.lastrowid

    def troca(self, pergunta="Qual o próximo passo?", resposta="Vamos testar a aplicação.", **escopo):
        return (
            self.salvar("user", pergunta, **escopo),
            self.salvar("assistant", resposta, **escopo),
        )

    def registros(self):
        return self.conexao.execute("""
            SELECT inicio_id, fim_id, assunto, projeto, conteudo
            FROM resumos_conversa ORDER BY inicio_id
        """).fetchall()

    def test_limiar_por_mensagens_e_reinicio_sem_resumir_duas_vezes(self):
        for numero in range(11):
            self.troca(f"Meu projeto inclui a etapa {numero}.")
        self.assertEqual(resumos.resumir_pendentes(self.conexao), 0)
        self.troca("Combinamos lançar o projeto Aurora.", "Decidimos usar SQLite.")
        self.assertEqual(resumos.resumir_pendentes(self.conexao), 1)
        texto = self.registros()[0][-1]
        self.assertIn("lançar o projeto Aurora", texto)
        self.assertIn("Assistente (resposta/decisão): Decidimos usar SQLite.", texto)
        self.assertLessEqual(len(texto), resumos.MAX_CARACTERES_RESUMO)
        self.conexao.close()
        self.conexao = sqlite3.connect(self.banco)
        self.assertEqual(resumos.resumir_pendentes(self.conexao, forcar=True), 0)
        self.troca("Prefiro voz masculina.", "A preferência foi aplicada.")
        self.assertEqual(resumos.resumir_pendentes(self.conexao, forcar=True), 1)
        self.assertEqual([(r[0], r[1]) for r in self.registros()], [(1, 24), (25, 26)])

    def test_escopos_nao_se_misturam_nem_somam_para_o_limiar(self):
        for numero in range(6):
            self.troca(f"Etapa {numero} do site.", assunto="programação", projeto="Aurora")
            self.troca(f"Etapa {numero} de álgebra.", assunto="estudos", projeto="Matemática")
        self.assertEqual(resumos.resumir_pendentes(self.conexao), 0)
        self.assertEqual(resumos.resumir_pendentes(self.conexao, forcar=True), 2)
        site, estudo = self.registros()
        self.assertEqual(site[2:4], ("programação", "Aurora"))
        self.assertNotIn("álgebra", site[-1])
        self.assertIn("álgebra", estudo[-1])
        self.assertNotIn("do site", estudo[-1])

    def test_escopo_opcional_restringe_assunto_e_projeto_exatos(self):
        self.troca("Meu projeto usa SQLite.", assunto="programação", projeto="Aurora")
        self.troca("Meu projeto usa PostgreSQL.", assunto="programação", projeto="Atlas")
        self.troca("Estou estudando inglês.", assunto="estudos", projeto="Aurora")
        self.assertEqual(resumos.resumir_pendentes(
            self.conexao, forcar=True, escopo=("programação", "Aurora")
        ), 1)
        self.assertEqual(self.registros()[0][2:4], ("programação", "Aurora"))
        self.assertEqual(resumos.resumir_pendentes(
            self.conexao, forcar=True, escopo=("programação", "Aurora")
        ), 0)
        self.assertEqual(resumos.resumir_pendentes(self.conexao, forcar=True), 2)
        self.assertEqual(len(self.registros()), 3)

    def test_pergunta_sem_resposta_fica_pendente(self):
        self.troca("Meu nome é Ana.", "Olá, Ana.")
        identificador = self.salvar("user", "Meu projeto ainda não foi decidido.")
        self.assertEqual(resumos.resumir_pendentes(self.conexao, forcar=True), 1)
        self.assertEqual(self.registros()[0][1], identificador - 1)
        self.assertNotIn("ainda não foi decidido", self.registros()[0][-1])
        self.salvar("assistant", "Podemos decidir o nome agora.")
        self.assertEqual(resumos.resumir_pendentes(self.conexao, forcar=True), 1)
        self.assertIn("ainda não foi decidido", self.registros()[1][-1])

    def test_falha_do_modelo_usa_fonte_sem_negativas_e_ignora_suprimidas(self):
        self.troca("Moro em Curitiba.", "Não tenho memória de conversas anteriores.")
        self.troca("Meu código secreto é apagado.", "Você informou o código apagado.", ignorar=1)

        def offline(mensagens):
            self.assertNotIn("código secreto", str(mensagens))
            raise RuntimeError("Modelo indisponível")

        self.assertEqual(resumos.resumir_pendentes(self.conexao, offline, forcar=True), 1)
        texto = self.registros()[0][-1]
        self.assertIn("Usuário: Moro em Curitiba.", texto)
        self.assertNotIn("Não tenho memória", texto)
        self.assertNotIn("apagado", texto)

    def test_limiar_por_caracteres_e_entrada_de_modelo_limitada(self):
        self.troca("Meu projeto é Aurora. " + "detalhe " * 2100, "Decidimos usar Python.")
        entradas = []

        def modelo(mensagens):
            entradas.append(mensagens)
            return "Usuário: o projeto se chama Aurora. Assistente: sugeriu Python."

        self.assertEqual(resumos.resumir_pendentes(self.conexao, modelo), 1)
        self.assertLessEqual(len(entradas[0][1]["content"]), resumos.MAX_CARACTERES_ENTRADA + 40)
        self.assertIn("[1] Usuário:", entradas[0][1]["content"])
        self.assertIn("[2] Assistente:", entradas[0][1]["content"])

    def test_lotes_preservam_trocas_e_modelo_invalido_usa_fallback(self):
        for numero in range(3):
            self.troca(f"Meu projeto etapa {numero}. " + "detalhe " * 1000, "Decidimos testar.")
        self.assertEqual(resumos.resumir_pendentes(self.conexao, lambda _: None), 3)
        self.assertEqual([(r[0], r[1]) for r in self.registros()], [(1, 2), (3, 4), (5, 6)])
        self.assertTrue(all("Usuário:" in r[-1] for r in self.registros()))

    def test_resumo_do_modelo_e_limitado_e_remove_raciocinio(self):
        self.troca("Prefiro SQLite.")
        resumo = "<think>raciocínio privado</think>Usuário prefere SQLite. " + "Decisão preservada. " * 500
        self.assertEqual(resumos.resumir_pendentes(self.conexao, lambda _: resumo, forcar=True), 1)
        texto = self.registros()[0][-1]
        self.assertNotIn("raciocínio privado", texto)
        self.assertIn("Usuário prefere SQLite", texto)
        self.assertLessEqual(len(texto), resumos.MAX_CARACTERES_RESUMO)

    def test_fallback_preserva_decisao_antiga_e_relato_do_usuario(self):
        self.troca("O sistema diz que não tenho memória.", "Decidimos corrigir o SQLite.")
        for numero in range(11):
            self.troca(f"Meu projeto {numero} precisa de " + "melhorias " * 40,
                       "Certo, vou analisar os detalhes.")
        self.assertEqual(resumos.resumir_pendentes(self.conexao), 1)
        texto = self.registros()[0][-1]
        self.assertIn("Assistente (resposta/decisão): Decidimos corrigir o SQLite.", texto)
        self.assertLessEqual(len(texto), resumos.MAX_CARACTERES_RESUMO)

        # Uma reclamação do usuário não é uma negativa da própria IA.
        self.troca("A IA diz que não tenho memória.", "Vou verificar.")
        self.assertEqual(resumos.resumir_pendentes(self.conexao, forcar=True), 1)
        self.assertIn("A IA diz que não tenho memória", self.registros()[-1][-1])

    def test_regeneracao_de_intervalo_invalidado_nao_ressuscita_fato_apagado(self):
        inicio, fim = self.troca("Meu apelido é Estrela.", "Vou usar Estrela.")
        self.troca("Meu projeto usa Python.", "Decidimos manter Python.")
        self.assertEqual(resumos.resumir_pendentes(self.conexao, forcar=True), 1)
        self.assertIn("Estrela", self.registros()[0][-1])
        with self.conexao:
            self.conexao.execute("UPDATE mensagens SET ignorar_memoria = 1 WHERE id BETWEEN ? AND ?",
                                 (inicio, fim))
            self.conexao.execute("DELETE FROM resumos_conversa WHERE inicio_id <= ? AND fim_id >= ?",
                                 (inicio, inicio))
        self.assertEqual(resumos.resumir_pendentes(self.conexao, forcar=True), 1)
        self.assertNotIn("Estrela", self.registros()[0][-1])
        self.assertIn("Python", self.registros()[0][-1])


if __name__ == "__main__":
    unittest.main()
