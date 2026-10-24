"""Modern-host maintenance checks against real temporary Git repositories."""
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import mac_forks as forks
import make_trust_roots
import menu_catalog


def fixture(path="Old.c", resource=b"RESOURCE\0\xff"):
    info = b"TEXTCWIE" + bytes(24)
    apple = (struct.pack(">II16sH", 0x51607, 0x20000, bytes(16), 2)
             + struct.pack(">III", 9, 50, 32)
             + struct.pack(">III", 2, 82, len(resource)) + info + resource)
    name = path.encode("utf-8")
    return b"GHMETA01" + struct.pack(">I", len(name)) + name + apple


class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="classic-forks-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.git("init", "-q", "--object-format=sha1")
        (self.root / "Old.c").write_bytes(b"original data fork\r")
        marker = self.root / forks.NAMESPACE / "version"
        marker.parent.mkdir()
        marker.write_bytes(forks.VERSION)
        self.raw = fixture()
        self.record_path = self.root / forks.companion_path("Old.c")
        self.record_path.parent.mkdir(parents=True)
        self.record_path.write_bytes(self.raw)
        self.git("add", "-A")
        self.commit()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), "-c", "commit.gpgsign=false",
                               "-c", "core.autocrlf=false", "-c", "core.hooksPath=" + str(self.root / "no-hooks"),
                               *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    def commit(self):
        self.git("-c", "user.name=Fixture", "-c", "user.email=test@example.invalid",
                 "commit", "-q", "-m", "Fixture")

    def move_data(self):
        (self.root / "src").mkdir()
        self.git("mv", "Old.c", "src/Renamé.c")

    def test_rename_and_remove_preserve_payload_and_validate_staged_snapshot(self):
        self.assertEqual(forks.validate_index(self.root), 1)
        self.move_data()
        with self.assertRaises(ValueError):
            forks.validate_index(self.root)
        self.assertEqual(forks.rename(self.root, "Old.c", "src/Renamé.c"), 1)
        target = self.root / forks.companion_path("src/Renamé.c")
        self.assertEqual(forks.decode(target.read_bytes()).apple, forks.decode(self.raw).apple)
        self.assertEqual((self.root / "src/Renamé.c").read_bytes(), b"original data fork\r")
        self.assertFalse(self.record_path.exists())
        forks.validate(self.root, forks.records(self.root))
        with self.assertRaises(ValueError):
            forks.validate_index(self.root)  # helper never silently stages
        self.git("add", "-A", forks.NAMESPACE)
        self.assertEqual(forks.validate_index(self.root), 1)
        self.commit()
        self.git("rm", "src/Renamé.c")
        self.assertEqual(forks.remove(self.root, "src/Renamé.c"), 1)
        self.assertFalse(target.exists())
        self.git("add", "-A", forks.NAMESPACE)
        self.assertEqual(forks.validate_index(self.root), 0)

    def test_unstaged_resource_edits_are_retained(self):
        changed = fixture(resource=b"UNSTAGED RESOURCE")
        self.record_path.write_bytes(changed)
        self.move_data()
        with self.assertRaisesRegex(ValueError, "differs from the Git index"):
            forks.rename(self.root, "Old.c", "src/Renamé.c")
        self.assertEqual(self.record_path.read_bytes(), changed)
        self.assertFalse((self.root / forks.companion_path("src/Renamé.c")).exists())
        with self.assertRaisesRegex(ValueError, "differs from the Git index"):
            forks.remove(self.root, "Old.c")
        self.assertEqual(self.record_path.read_bytes(), changed)

    def test_existing_destination_record_is_never_replaced(self):
        self.move_data()
        destination = self.root / forks.companion_path("src/Renamé.c")
        destination.parent.mkdir(parents=True, exist_ok=True)
        other = fixture("src/Renamé.c", b"OTHER RESOURCE")
        destination.write_bytes(other)
        with self.assertRaises(FileExistsError):
            forks.rename(self.root, "Old.c", "src/Renamé.c")
        self.assertEqual(self.record_path.read_bytes(), self.raw)
        self.assertEqual(destination.read_bytes(), other)

    def test_unknown_version_and_orphans_are_refused(self):
        marker = self.root / forks.NAMESPACE / "version"
        marker.write_bytes(b"future format\n")
        with self.assertRaises(ValueError):
            forks.records(self.root)
        marker.write_bytes(forks.VERSION)
        self.git("rm", "Old.c")
        with self.assertRaises(ValueError):
            forks.validate(self.root, forks.records(self.root))
        with self.assertRaises(ValueError):
            forks.validate_index(self.root)

    def test_malformed_tables_and_path_traversal_are_refused(self):
        record = forks.decode(self.raw)
        self.assertEqual(record.resource, b"RESOURCE\0\xff")
        for bad in (b"", self.raw[:11], self.raw[:8] + struct.pack(">I", 0xffffffff) + self.raw[12:]):
            with self.subTest(bad=bad[:12]), self.assertRaises(ValueError):
                forks.decode(bad)
        for path in ("../escape", "a/../../escape", "/absolute", ".git/config", "a/.GIT/config", ".ghclient-mac/file"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                forks.companion_path(path)
        start = 12 + len("Old.c")
        for relative, value in ((26, 2), (30, 0), (34, 33), (42, 0xffffffff)):
            raw = bytearray(self.raw)
            struct.pack_into(">I", raw, start + relative, value)
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                forks.decode(bytes(raw))

    def test_linked_working_paths_are_refused(self):
        self.move_data()
        target = self.root / "src/Renamé.c"
        target.unlink()
        try:
            target.symlink_to(self.root / "outside")
        except OSError as error:
            self.skipTest("symlink creation unavailable: " + str(error))
        with self.assertRaisesRegex(ValueError, "symlink or reparse"):
            forks.rename(self.root, "Old.c", "src/Renamé.c")
        self.assertEqual(self.record_path.read_bytes(), self.raw)

    def test_misnamed_hash_is_refused(self):
        wrong = self.record_path.with_name("0" * 26)
        self.record_path.rename(wrong)
        with self.assertRaisesRegex(ValueError, "hash/path"):
            forks.records(self.root)


class GeneratorTests(unittest.TestCase):
    def test_catalog_matches_header_and_rejects_duplicate_commands(self):
        rows = menu_catalog.catalog(ROOT / "tools/menu_catalog.tsv")
        self.assertEqual(menu_catalog.render(rows), (ROOT / "SRC/MenuCommands.h").read_bytes())
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.tsv"
            path.write_text("menu\titem\tcommand\timplemented\n128\t1\tMC_ABOUT\t1\n129\t2\tMC_ABOUT\t1\n")
            with self.assertRaises(ValueError):
                menu_catalog.catalog(path)

    def test_root_inputs_are_pinned_and_reproduce_header(self):
        source = ROOT / "tools/trust-roots"
        self.assertEqual(make_trust_roots.generate(source), (ROOT / "SRC/TrustRoots.h").read_bytes())
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "roots"
            shutil.copytree(source, directory)
            manifest = json.loads((directory / "manifest.json").read_text())
            pem = directory / manifest["certificates"][0]["file"]
            text = pem.read_text()
            pem.write_text(text.replace("MIIF", "MIIG", 1))
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                make_trust_roots.generate(directory)


if __name__ == "__main__":
    unittest.main()
