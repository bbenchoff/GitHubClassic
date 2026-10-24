#!/usr/bin/env python3
"""Verify a closed GH Merge test image against its generated manifest.

Put Away and detach the image before reading it here. This is a fixture
checker, not a general filesystem checker or a hardware recovery test.
Requires Git and machfs 1.3.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zlib

import machfs
from hfs_read import catalog, volume


def require(condition, message):
    if not condition:
        raise ValueError(message)


def normalized(info):
    info = bytearray(info)
    info[8] &= 254
    info[10:16] = bytes(6)
    info[28:32] = bytes(4)
    return bytes(info)


def flatten(folder, prefix=()):
    result = {}
    for name, child in folder.items():
        key = prefix + (name,)
        if isinstance(child, machfs.Folder):
            result.update(flatten(child, key))
        else:
            result[key] = child
    return result


def refpath(name):
    digest = hashlib.sha1(name.encode("ascii")).hexdigest()
    return "refs", digest[:2], digest[2:14], digest[14:]


def verify(image, manifest, slot):
    raw = image.read_bytes()
    tree, native = volume(raw), catalog(raw)
    recipe = json.loads(manifest.read_text(encoding="utf-8"))
    log = tree[slot + " Merge Results"].data.decode("mac_roman").replace("\r", "\n").splitlines()
    expected_app = {"PPC": "MacOS Toolbox PPC", "68K": "MacOS Toolbox 68K", "FAT": "Classic Github"}[slot]
    require(log[:3] == ["GHClient native merge checkout v1", "application=" + expected_app,
                       "application_slice=" + ("68K" if slot == "68K" else "PowerPC")], "wrong application slice")
    require(log[-2:] == ["result=0", "passed=6"], "native diagnostic did not pass six cases")
    rows = {row.split()[0].split("=", 1)[1]: dict(pair.split("=", 1) for pair in row.split())
            for row in log[3:-2]}
    cases = [case for case in recipe["cases"] if case["slot"] == slot]
    require(len(cases) == len(rows) == 6, "incomplete fixture set")
    for case in cases:
        name = case["folder"]
        nodes = flatten(tree[name])
        store = flatten(tree[name][".git"])
        row = rows[name[len(slot) + 1:]]
        success = row["case"] in ("Merge", "Forward", "Forced")
        require(row["prepare"] == row["read"] == row["close"] == "0", name + ": native operation failed")
        require(int(row["kind"]) == case["expected_kind"] and int(row["apply"]) == case["expected_apply"], name + ": wrong result")
        require(int(row["advanced"]) == int(success) and row["after"] == case["expected_tip"], name + ": wrong advancement")
        require(row["current"] == case["current"] and row["incoming"] == case["incoming"], name + ": wrong input tips")
        require(store["HEAD",].data == b"ref: refs/heads/main\n", name + ": HEAD changed")
        for ref, oid in (("refs/heads/main", case["expected_tip"]),
                         ("refs/remotes/origin/topic", case["expected_other"])):
            require(store[refpath(ref)].data == ref.encode() + b"\0" + oid.encode() + b"\n", name + ": wrong ref")
        require({"/".join(path) for path in nodes if path[0] != ".git"} == set(case["expected_files"]), name + ": unexpected working paths")
        for path, expected in case["expected_files"].items():
            key = tuple(path.split("/"))
            require(nodes[key].data == bytes.fromhex(expected["data"]), name + ": data fork differs")
            require(nodes[key].rsrc == bytes.fromhex(expected["resource"]), name + ": resource fork differs")
            info = native[tuple(part.encode("mac_roman") for part in (name, *key))]["info"]
            require(normalized(info) == normalized(bytes.fromhex(expected["finder"])), name + ": Finder information differs")
        if success:
            require(("checkout-intent",) not in store and store["checkout-journal",].data[:8] == b"GHCI0001",
                    name + ": checkout not complete")
        with tempfile.TemporaryDirectory(prefix="classic-native-check-") as temporary:
            repo = Path(temporary)

            def git(*args):
                return subprocess.run(["git", "-C", str(repo), *args], stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, check=True).stdout

            git("init", "--bare", "--object-format=sha1", "--initial-branch=main", "-q")
            found = set()
            for path, node in store.items():
                if path[0] != "objects":
                    continue
                oid = "".join(path[1:])
                body = zlib.decompress(node.data)
                require(hashlib.sha1(body).hexdigest() == oid, name + ": invalid object identity")
                header, content = body.split(b"\0", 1)
                kind, size = header.split()
                require(kind in (b"blob", b"tree", b"commit") and int(size) == len(content), name + ": invalid object envelope")
                target = repo / "objects" / oid[:2] / oid[2:]
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(node.data)
                found.add(oid)
            require(set(recipe["input_oids"]) <= found, name + ": original object missing")
            (repo / "index").write_bytes(store["index",].data)
            git("update-ref", "refs/heads/main", case["expected_tip"])
            git("update-ref", "refs/remotes/origin/topic", case["expected_other"])
            git("fsck", "--full", "--strict", "--no-dangling")
            expected_tree = case["expected_tree"] or git("rev-parse", case["expected_tip"] + "^{tree}").decode().strip()
            require(git("write-tree").decode().strip() == expected_tree, name + ": wrong index tree")
    print(slot + ": six native cases verified; refs, index, Git objects, both forks and Finder information match")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--slice", choices=("PPC", "68K", "FAT"), required=True)
    args = parser.parse_args()
    try:
        verify(args.image, args.manifest, args.slice)
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, "merge check: %s\n" % error)


if __name__ == "__main__":
    main()
