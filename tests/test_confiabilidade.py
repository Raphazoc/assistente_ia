import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from ollama import ResponseError

from app import banco
from app import diagnostico
from app import main
from app import memoria
from app import voz


class ConfiabilidadeTests(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.base = Path(self.pasta.name)
        self.banco = self.base / "memoria.db"
        self.patch_banco = patch.object(main, "BANCO", self.banco)
        self.patch_logs = patch.object(diagnostico, "PASTA_LOGS", self.base / "logs")
        self.patch_banco.start()
        self.patch_logs.start()
        self.conexao = main.iniciar_banco()

    def tearDown(self):
        self.conexao.close()
        diagnostico.encerrar()
        self.patch_logs.stop()
        self.patch_banco.stop()
        self.pasta.cleanup()

    def _mensagens(self, conexao):
        return [r[0] for r in conexao.execute("SELECT conteudo FROM mensagens ORDER BY id")]

    def test_backup_automatico_manual_e_restauracao_preservam_estado_anterior(self):
        automaticos = banco.listar_backups(self.banco)
        self.assertEqual(len(automaticos), 1)
        self.assertTrue(automaticos[0].name.startswith("automatico_"))
        self.assertIsNone(banco.backup_automatico(self.conexao, self.banco))

        self.conexao.execute("INSERT INTO mensagens(papel,conteudo) VALUES ('user','primeira versão')")
        self.conexao.commit()
        copia = banco.criar_backup(self.conexao, self.banco)
        self.conexao.execute("INSERT INTO mensagens(papel,conteudo) VALUES ('user','segunda versão')")
        self.conexao.commit()
        self.conexao.close()

        seguranca = banco.restaurar(self.banco, copia.name)
        with contextlib.closing(sqlite3.connect(self.banco)) as restaurada:
            self.assertEqual(self._mensagens(restaurada), ["primeira versão"])
            banco.verificar_integridade(restaurada, exigir_estrutura=True)
        with contextlib.closing(sqlite3.connect(seguranca)) as anterior:
            self.assertEqual(self._mensagens(anterior), ["primeira versão", "segunda versão"])
        self.conexao = sqlite3.connect(self.banco)

    def test_backup_corrompido_e_nome_externo_nao_alteram_banco(self):
        copia = banco.criar_backup(self.conexao, self.banco)
        copia.write_bytes(b"nao e um SQLite")
        with self.assertRaises(sqlite3.DatabaseError):
            banco.restaurar(self.banco, copia.name)
        with self.assertRaises(ValueError):
            banco.restaurar(self.banco, "../memoria.db")
        banco.verificar_integridade(self.conexao, exigir_estrutura=True)

    def test_backup_rejeita_conexao_de_outro_banco(self):
        with self.assertRaises(ValueError):
            banco.criar_backup(self.conexao, self.base / "outro.db")

    def test_retencao_remove_so_backups_automaticos_excedentes(self):
        manual = banco.criar_backup(self.conexao, self.banco)
        with patch.object(banco, "RETENCAO_AUTOMATICA", 3):
            for _ in range(5):
                banco.criar_backup(self.conexao, self.banco, tipo="automatico")
        copias = banco.listar_backups(self.banco)
        self.assertEqual(sum(p.name.startswith("automatico_") for p in copias), 3)
        self.assertTrue(manual.exists())

    def test_log_omite_segredos_e_limita_eventos(self):
        # Usa o logger real, isolado do arquivo de diagnóstico da sessão.
        diagnostico.encerrar()
        diagnostico.registrar("ollama.resposta.falha", erro=RuntimeError("senha=abc123"), quantidade=2)
        caminho = diagnostico.PASTA_LOGS / "assistente.log"
        linhas = caminho.read_text(encoding="utf-8").splitlines()
        evento = json.loads(linhas[-1])
        self.assertEqual(evento["tipo_erro"], "RuntimeError")
        self.assertNotIn("abc123", caminho.read_text(encoding="utf-8"))
        with self.assertRaises(ValueError):
            diagnostico.registrar("meu_segredo_abc123")

    def test_eventos_recentes_descartam_conteudo_estranho_do_log(self):
        diagnostico.encerrar()
        diagnostico.registrar("ollama.resposta.falha", erro=RuntimeError("senha=abc123"))
        diagnostico.encerrar()
        caminho = diagnostico.PASTA_LOGS / "assistente.log"
        with caminho.open("a", encoding="utf-8") as arquivo:
            arquivo.write('{"hora_utc":"2026-01-01T12:00:00+00:00","evento":"senha=abc123"}\n')
        recentes = diagnostico.eventos_recentes()
        self.assertEqual(recentes[0][1], "ollama.resposta.falha")
        self.assertNotIn("abc123", repr(recentes))

    def test_ollama_tenta_uma_vez_mais_apos_falha_transitoria(self):
        funcao = Mock(side_effect=[httpx.ConnectError("segredo=abc123"), {"message": {"content": "ok"}}])
        with patch.object(main.time, "sleep") as pausa:
            resposta = main.consultar_ollama(funcao, "ollama.resposta", model=main.MODELO)
        self.assertEqual(resposta["message"]["content"], "ok")
        self.assertEqual(funcao.call_count, 2)
        pausa.assert_called_once()

    def test_ollama_erro_404_nao_faz_retentativa(self):
        funcao = Mock(side_effect=ResponseError("segredo=abc123", status_code=404))
        with self.assertRaisesRegex(RuntimeError, "modelo não encontrado") as erro:
            main.consultar_ollama(funcao, "ollama.resposta", model=main.MODELO)
        self.assertNotIn("abc123", str(erro.exception))
        funcao.assert_called_once()

    def test_apos_tres_falhas_do_microfone_programa_volta_ao_texto(self):
        saida = io.StringIO()
        with (
            patch.object(main, "indexar_memorias_antigas"),
            patch.object(main, "preparar_pesquisa", return_value=None),
            patch.object(main, "ler_texto", side_effect=["2", "sair"]),
            patch.object(main, "reconhecer_voz", side_effect=OSError("segredo=abc123")) as ouvir,
            patch.object(main.time, "sleep"),
            patch.object(voz, "preparar_modelos"),
            contextlib.redirect_stdout(saida),
        ):
            main.main()
        self.assertEqual(ouvir.call_count, 3)
        self.assertIn("mudou para digitação", saida.getvalue())
        self.assertNotIn("abc123", saida.getvalue())

    def test_whisper_cai_para_cpu_se_a_gpu_falhar_durante_transcricao(self):
        gpu = Mock(model=SimpleNamespace(device="cuda"))
        gpu.transcribe.side_effect = RuntimeError("biblioteca CUDA ausente")
        cpu = Mock(model=SimpleNamespace(device="cpu"))
        cpu.transcribe.return_value = (iter([SimpleNamespace(text=" Aurora, oi ")]), None)
        with (
            patch.object(voz, "carregar_modelo", side_effect=[gpu, cpu]) as carregar,
            patch.object(voz, "_cuda_indisponivel", False),
        ):
            texto = voz.transcrever_audio([0.0] * 16000)
            self.assertEqual(texto, "Aurora, oi")
            self.assertTrue(voz._cuda_indisponivel)
            carregar.cache_clear.assert_called_once()
            self.assertFalse(cpu.transcribe.call_args.kwargs["vad_filter"])

    def test_falha_total_da_voz_nao_impede_a_resposta_escrita(self):
        with (
            patch("app.fala.falar", side_effect=OSError("trecho privado")),
            patch.object(main, "MonitorInterrupcao"),
            contextlib.redirect_stdout(io.StringIO()) as saida,
        ):
            self.assertIsNone(main.reproduzir_resposta("Resposta preservada."))
        self.assertIn("resposta escrita permanece", saida.getvalue())
        self.assertNotIn("trecho privado", saida.getvalue())

    def test_mil_ciclos_de_gravacao_e_reabertura_preservam_integridade(self):
        for numero in range(1000):
            self.conexao.execute(
                "INSERT INTO mensagens(papel,conteudo) VALUES (?,?)",
                ("user", f"ciclo {numero}"),
            )
            if numero % 100 == 99:
                self.conexao.commit()
                copia = banco.criar_backup(self.conexao, self.banco)
                with contextlib.closing(sqlite3.connect(copia)) as verificada:
                    banco.verificar_integridade(verificada, exigir_estrutura=True)
                self.conexao.close()
                self.conexao = sqlite3.connect(self.banco)
        self.assertEqual(self.conexao.execute("SELECT COUNT(*) FROM mensagens").fetchone()[0], 1000)
        banco.verificar_integridade(self.conexao, exigir_estrutura=True)

    def test_busca_em_historico_grande_ainda_encontra_fato_antigo(self):
        self.conexao.execute("INSERT INTO mensagens(papel,conteudo) VALUES ('user','Projeto orquídea usa sensores azuis.')")
        self.conexao.executemany(
            "INSERT INTO mensagens(papel,conteudo) VALUES ('user',?)",
            [(f"Notas diferentes do ciclo {i}.",) for i in range(2000)],
        )
        self.conexao.commit()
        encontrados = memoria.selecionar(
            self.conexao, "O que usa o projeto orquídea?", Mock(), main.MODELO_MEMORIA,
        )
        self.assertTrue(any("sensores azuis" in item for item in encontrados))

    def test_sessao_longa_continua_depois_de_erro_do_ollama(self):
        falhas = 0
        def responder(**argumentos):
            nonlocal falhas
            pedido = argumentos["messages"][-1]["content"]
            if pedido == "pedido 20" and falhas < 2:
                falhas += 1
                raise httpx.ConnectError("conteudo privado")
            return {"message": {"content": "Resposta local."}}

        entradas = ["1"] + [f"pedido {i}" for i in range(120)] + ["sair"]
        with (
            patch.object(main, "indexar_memorias_antigas"),
            patch.object(main, "indexar_nova_mensagem"),
            patch.object(main, "preparar_pesquisa", return_value=None),
            patch.object(main, "chat", side_effect=responder),
            patch.object(main, "ler_texto", side_effect=entradas),
            patch.object(main.time, "sleep"),
            contextlib.redirect_stdout(io.StringIO()) as saida,
        ):
            main.main()
        self.assertEqual(falhas, 2)
        self.assertIn("Ollama indisponível", saida.getvalue())
        self.assertEqual(self.conexao.execute("SELECT COUNT(*) FROM mensagens WHERE papel='user'").fetchone()[0], 120)
        self.assertEqual(self.conexao.execute("SELECT COUNT(*) FROM mensagens WHERE papel='assistant'").fetchone()[0], 119)
        banco.verificar_integridade(self.conexao, exigir_estrutura=True)


if __name__ == "__main__":
    unittest.main()
