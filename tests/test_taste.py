import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "taste-graph" / "scripts"))
import taste  # noqa: E402


class TasteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.vault = Path(self.tmp.name) / "vault" / "taste"
        self.run_ok("init", "--dir", str(self.vault), "--locale", "pt-BR")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = taste.main(["--home", str(self.home), *argv])
        return code, out.getvalue(), err.getvalue()

    def run_ok(self, *argv):
        code, out, err = self.run_cli(*argv)
        self.assertEqual(code, 0, err)
        return out

    def add(self, payload):
        return self.run_ok("add", json.dumps(payload))

    def note(self, name):
        return (self.vault / "obras" / f"{name}.md").read_text()

    def test_init_creates_folders_and_profile(self):
        for folder in ("obras", "pessoas", "temas"):
            self.assertTrue((self.vault / folder).is_dir())
        self.assertIn("Perfil de gostos", (self.vault / "perfil.md").read_text())
        self.assertIn("Perfil de gostos", self.run_ok("profile"))

    def test_init_keeps_an_existing_profile(self):
        (self.vault / "perfil.md").write_text("meu texto\n")
        self.run_ok("init", "--dir", str(self.vault), "--locale", "pt-BR")
        self.assertEqual((self.vault / "perfil.md").read_text(), "meu texto\n")

    def test_add_writes_obsidian_note_with_links(self):
        out = self.add({"type": "movie", "title": "Filme A", "year": 2001, "status": "favorite", "rating": 5,
                        "creators": ["Diretora X"], "themes": ["terror", "luto"], "note": "Me prendeu.",
                        "date": "2026-10-13"})
        self.assertIn("✅ Nova nota: Filme A (filme) · favorito · ★5", out)
        meta, body = taste.parse_note(self.note("Filme A"))
        self.assertEqual(meta["creators"], ["[[Diretora X]]"])
        self.assertEqual(meta["themes"], ["[[terror]]", "[[luto]]"])
        self.assertEqual(meta["year"], 2001)
        self.assertIn("## Notas\n- 2026-10-13 · Me prendeu.", body)

    def test_update_merges_lists_and_appends_notes(self):
        self.add({"type": "book", "title": "Livro B", "status": "current", "themes": ["clássico"],
                  "note": "Começando.", "date": "2026-10-01"})
        out = self.add({"title": "livro b", "status": "done", "rating": 4, "themes": ["Clássico", "sertão"],
                        "note": "Terminei.", "date": "2026-10-20"})
        self.assertIn("✅ Atualizado: Livro B (livro) · visto · ★4", out)
        meta, body = taste.parse_note(self.note("Livro B"))
        self.assertEqual(meta["themes"], ["[[clássico]]", "[[sertão]]"])
        self.assertEqual(meta["updated"], "2026-10-20")
        self.assertLess(body.index("Começando."), body.index("Terminei."))

    def test_hub_note_created_at_second_work(self):
        out = self.add({"type": "movie", "title": "Um", "creators": ["Fulano"]})
        self.assertNotIn("🔗", out)
        out = self.add({"type": "movie", "title": "Dois", "creators": ["Fulano"]})
        self.assertIn("🔗 Fulano agora liga 2 obras", out)
        self.assertIn("kind: \"person\"", (self.vault / "pessoas" / "Fulano.md").read_text())
        self.assertNotIn("🔗", self.add({"type": "movie", "title": "Três", "creators": ["Fulano"]}))

    def test_hand_edited_note_is_preserved(self):
        path = self.vault / "obras" / "Série C.md"
        path.write_text("---\ntype: series\ntitle: Série C\nthemes: [\"[[comédia]]\", humor]\ncreators:\n"
                        "  - \"[[Criador]]\"\nmood: leve\n---\n# Série C\n\nMeu texto livre.\n\n## Notas\n"
                        "- 2026-01-01 · antiga\n\n## Outra seção\nfica.\n")
        self.add({"title": "Série C", "themes": ["drama"], "note": "nova", "date": "2026-10-13"})
        meta, body = taste.parse_note(path.read_text())
        self.assertEqual(meta["themes"], ["[[comédia]]", "humor", "[[drama]]"])
        self.assertEqual(meta["creators"], ["[[Criador]]"])
        self.assertEqual(meta["mood"], "leve")
        self.assertIn("Meu texto livre.", body)
        self.assertIn("- 2026-01-01 · antiga\n- 2026-10-13 · nova\n\n## Outra seção\nfica.", body)

    def test_titles_with_reserved_characters(self):
        self.add({"type": "book", "title": "Grande Sertão: Veredas", "creators": ["Autor: Z"]})
        meta, _ = taste.parse_note(self.note("Grande Sertão- Veredas"))
        self.assertEqual(meta["title"], "Grande Sertão: Veredas")
        self.assertEqual(meta["creators"], ["[[Autor- Z|Autor: Z]]"])
        self.assertIn("Grande Sertão: Veredas", self.run_ok("show", "grande sertao: veredas"))

    def test_same_title_different_type(self):
        self.add({"type": "book", "title": "Buracos"})
        self.add({"type": "movie", "title": "Buracos"})
        self.assertTrue((self.vault / "obras" / "Buracos (filme).md").exists())
        code, _, err = self.run_cli("add", json.dumps({"title": "Buracos", "rating": 4}))
        self.assertEqual(code, 1)
        self.assertIn("pass \"type\"", err)
        self.add({"title": "Buracos", "type": "movie", "rating": 4})
        self.assertIn("rating: 4", self.note("Buracos (filme)"))

    def test_batch_add_and_index(self):
        self.add([
            {"type": "movie", "title": "A", "status": "favorite", "rating": 5, "creators": ["D"], "themes": ["t1"]},
            {"type": "movie", "title": "B", "status": "want", "creators": ["D"], "themes": ["t1"]},
            {"type": "food", "title": "Feijoada", "status": "favorite", "themes": ["brasileira"]},
        ])
        out = self.run_ok("index")
        self.assertIn("A · filme · ★5 favorito · D · t1", out)
        self.assertIn("## Pessoas\nD (2)", out)
        self.assertIn("## Temas\nt1 (2)", out)
        self.assertNotIn("brasileira (1)", out)
        self.assertNotIn("Feijoada", self.run_ok("index", "--type", "movie"))
        self.assertNotIn("· A ·", self.run_ok("index", "--status", "want"))

    def test_find_is_accent_insensitive(self):
        self.add({"type": "series", "title": "Série D", "themes": ["ficção científica"]})
        self.assertIn("Série D", self.run_ok("find", "ficcao", "cientifica"))
        self.assertIn("Nada encontrado", self.run_ok("find", "faroeste"))

    def test_validation_errors(self):
        for payload, msg in (({"title": "X"}, "is new"), ({"title": "X", "type": "film"}, "type must"),
                             ({"title": "X", "type": "movie", "rating": 7}, "rating"),
                             ({"title": "X", "type": "movie", "genre": "y"}, "Unknown fields")):
            code, _, err = self.run_cli("add", json.dumps(payload))
            self.assertEqual(code, 1)
            self.assertIn(msg, err)

    def test_recommendation_log(self):
        out = self.run_ok("rec", json.dumps({"request": "entediado, filme pra animar", "picks": ["A", "B"]}))
        self.assertIn("📝", out)
        self.assertIn("entediado, filme pra animar → A, B", self.run_ok("recs"))

    def test_requires_init(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = taste.main(["--home", str(Path(self.tmp.name) / "empty"), "index"])
        self.assertEqual(code, 1)
        self.assertIn("init --dir", err.getvalue())

    def test_english_locale(self):
        home = Path(self.tmp.name) / "en"
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            taste.main(["--home", str(home), "init", "--dir", str(Path(self.tmp.name) / "en-vault")])
            taste.main(["--home", str(home), "add", json.dumps({"type": "game", "title": "G", "status": "done"})])
        self.assertIn("✅ New note: G (game) · done", out.getvalue())
        self.assertTrue((Path(self.tmp.name) / "en-vault" / "works" / "G.md").exists())


if __name__ == "__main__":
    unittest.main()
