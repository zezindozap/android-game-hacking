import base64
import importlib.util
import json
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib import save, util  # noqa: E402


def load_addon():
    spec = importlib.util.spec_from_file_location("dops_addon", ROOT / "mitm" / "addon.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestSniff(unittest.TestCase):
    def test_json(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write('{"coins": 1}')
            p = Path(f.name)
        info = save.sniff(p)
        self.assertEqual(info["format"], "json")
        self.assertTrue(info["editable"])

    def test_enc1(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".save", delete=False) as f:
            f.write(b"ENC1:" + base64.b64encode(b"\x00" * 64))
            p = Path(f.name)
        info = save.sniff(p)
        self.assertEqual(info["format"], "actk-obscuredfile")
        self.assertEqual(info["cipher_len"], 64)
        self.assertTrue(info["block_aligned"])
        self.assertFalse(info["editable"])


class TestAddon(unittest.TestCase):
    def test_matches(self):
        addon = load_addon()
        rules = {"host": "validador.example", "match_path": "/verify"}
        self.assertTrue(addon.matches(rules, "validador.example", "/verify"))
        self.assertFalse(addon.matches(rules, "outro.example", "/verify"))
        self.assertFalse(addon.matches(rules, "validador.example", "/other"))

    def test_patched_body_keeps_fields(self):
        addon = load_addon()
        rules = {"patch": {"result": 1}}
        body = json.loads(addon.patched_body(rules, b'{"result":0,"error":"x"}'))
        self.assertEqual(body["result"], 1)
        self.assertEqual(body["error"], "x")

    def test_patched_body_bad_json(self):
        addon = load_addon()
        body = json.loads(addon.patched_body({"patch": {"result": 1}}, b"not-json"))
        self.assertEqual(body, {"result": 1})


class TestTargets(unittest.TestCase):
    def test_parse_all(self):
        for path in (ROOT / "targets").glob("*.toml"):
            with open(path, "rb") as f:
                cfg = tomllib.load(f)
            self.assertIn("package", cfg, str(path))
            self.assertTrue(cfg["package"].count(".") >= 1, str(path))

    def test_expand(self):
        self.assertEqual(util.expand("/x/{package}/y", {"package": "a.b"}), "/x/a.b/y")


if __name__ == "__main__":
    unittest.main()


class TestMitm(unittest.TestCase):
    def test_free_port(self):
        import socket
        from lib import mitm

        port = mitm._free_port(0)
        self.assertGreater(port, 0)
        with socket.socket() as s:
            s.bind(("127.0.0.1", port))


class TestDispatcher(unittest.TestCase):
    def test_parse_sni(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("dops_dispatch", ROOT / "mitm" / "dispatch.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        data = (ROOT / "tests" / "fixtures" / "clienthello-example.bin").read_bytes()
        self.assertEqual(mod.parse_sni(data), "example.com")
