#!/usr/bin/env python3
"""Maintain Macintosh companion records in an ordinary modern Git checkout.

Run rename/remove after git mv/git rm of ONE logical file, then stage the
companion changes with git add -A .ghclient-mac. This never changes data forks,
invokes a Git write, guesses rename matches, or operates on whole directories.
"""
import argparse
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
import struct
import subprocess
import tempfile

NAMESPACE = ".ghclient-mac"
VERSION = b"GHClient Macintosh forks 1\nmetadata GHMETA01 + path + AppleDouble\n"
MAX_RECORD = 64 * 1024 * 1024


def logical_path(name):
    parts = name.split("/")
    if (not name or any(p in ("", ".", "..") or p.lower() == ".git" for p in parts)
            or parts[0] == NAMESPACE or "\0" in name):
        raise ValueError("invalid logical path: " + repr(name))
    if os.name == "nt" and (any(c in name for c in '\\:<>"|?*')
                            or any(p.endswith((".", " ")) or Path(p).is_reserved() for p in parts)):
        raise ValueError("path cannot be represented in a Windows checkout: " + repr(name))
    return name.encode("utf-8")


def companion_path(name):
    digest = hashlib.sha1(logical_path(name)).hexdigest()
    return Path(NAMESPACE, "forks", digest[:2], digest[2:14], digest[14:])


def is_link(path):
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def checked_path(root, relative, must_exist=True):
    relative = Path(relative)
    if relative.anchor or relative.drive:
        raise ValueError("physical path must be relative to the checkout")
    path = root
    for component in relative.parts:
        if component in ("", ".", ".."):
            raise ValueError("invalid physical path")
        path /= component
        if path.exists() or path.is_symlink():
            if is_link(path):
                raise ValueError("symlink or reparse point refused: " + str(path))
        elif must_exist:
            raise ValueError("missing file: " + str(path))
    return path


@dataclass(frozen=True)
class Record:
    path: str
    apple: bytes
    info: bytes
    resource: bytes
    raw: bytes


def decode(raw):
    if len(raw) < 12 or len(raw) > MAX_RECORD or raw[:8] != b"GHMETA01":
        raise ValueError("invalid companion header")
    length, = struct.unpack_from(">I", raw, 8)
    if length > len(raw) - 12:
        raise ValueError("truncated companion path")
    name = raw[12:12 + length].decode("utf-8")
    logical_path(name)
    apple = raw[12 + length:]
    if len(apple) < 26 or apple[:8] != struct.pack(">II", 0x00051607, 0x00020000):
        raise ValueError("invalid AppleDouble header")
    count, = struct.unpack_from(">H", apple, 24)
    if not count or count > (len(apple) - 26) // 12:
        raise ValueError("invalid AppleDouble table")
    entries, ranges = {}, []
    for i in range(count):
        kind, offset, size = struct.unpack_from(">III", apple, 26 + i * 12)
        if (kind in entries or offset < 26 + 12 * count
                or offset > len(apple) or size > len(apple) - offset):
            raise ValueError("invalid or duplicate AppleDouble entry")
        entries[kind] = apple[offset:offset + size]
        if size:
            ranges.append((offset, offset + size))
    ranges.sort()
    if any(a[1] > b[0] for a, b in zip(ranges, ranges[1:])):
        raise ValueError("overlapping AppleDouble entries")
    if 2 not in entries or len(entries.get(9, b"")) != 32:
        raise ValueError("resource fork and 32-byte Finder information required")
    return Record(name, apple, entries[9], entries[2], raw)


def encode_path(record, name):
    encoded = logical_path(name)
    return b"GHMETA01" + struct.pack(">I", len(encoded)) + encoded + record.apple


def records(root):
    namespace = checked_path(root, NAMESPACE, False)
    if not namespace.exists():
        return {}
    marker = checked_path(root, Path(NAMESPACE, "version"))
    if marker.stat().st_size != len(VERSION) or marker.read_bytes() != VERSION:
        raise ValueError("unknown Macintosh companion version")
    result = {}

    def walk(directory):
        for path in sorted(directory.iterdir()):
            if is_link(path):
                raise ValueError("linked companion path refused: " + str(path))
            if path.is_dir():
                yield from walk(path)
            elif path.is_file():
                yield path
            else:
                raise ValueError("nonregular companion: " + str(path))

    forks = checked_path(root, Path(NAMESPACE, "forks"), False)
    if not forks.exists():
        return result
    for path in walk(forks):
        if path.stat().st_size > MAX_RECORD:
            raise ValueError("companion exceeds size bound: " + str(path))
        record = decode(path.read_bytes())
        if path.relative_to(root).as_posix() != companion_path(record.path).as_posix() or record.path in result:
            raise ValueError("companion hash/path mismatch: " + str(path))
        result[record.path] = record
    return result


def validate(root, found, allow_missing=()):
    for name in found:
        if name in allow_missing:
            continue
        path = checked_path(root, Path(*name.split("/")))
        if not path.is_file():
            raise ValueError("companion has no regular data-fork file: " + repr(name))


def index_entries(root):
    output = subprocess.run(["git", "-C", str(root), "ls-files", "--stage", "-z"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout
    entries = {}
    for line in output.split(b"\0"):
        if not line:
            continue
        header, name = line.split(b"\t", 1)
        mode, oid, stage = header.split()
        if stage != b"0" or len(oid) != 40:
            raise ValueError("requires a resolved SHA-1 Git index")
        entries[name.decode("utf-8")] = mode, oid
    return entries


def staged_source_matches(root, relative, raw):
    entry = index_entries(root).get(relative.as_posix())
    oid = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest().encode("ascii")
    if not entry or entry[0] != b"100644" or entry[1] != oid:
        raise ValueError("companion differs from the Git index; preserve or stage its edits first")


def validate_index(root):
    entries = index_entries(root)
    names = sorted(name for name in entries if name.startswith(NAMESPACE + "/"))
    if not names:
        return 0
    process = subprocess.Popen(["git", "-C", str(root), "cat-file", "--batch"],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    count, total, marker = 0, 0, False
    try:
        for name in names:
            mode, oid = entries[name]
            if mode != b"100644":
                raise ValueError("companion entries must be regular nonexecutable files")
            process.stdin.write(oid + b"\n")
            process.stdin.flush()
            header = process.stdout.readline(256).split()
            if len(header) != 3 or header[:2] != [oid, b"blob"]:
                raise ValueError("invalid staged companion object")
            size = int(header[2])
            total += size
            if size < 0 or total > MAX_RECORD:
                raise ValueError("staged companions exceed the 64 MiB validation bound")
            raw = process.stdout.read(size)
            if len(raw) != size or process.stdout.read(1) != b"\n":
                raise ValueError("truncated staged companion object")
            if name == NAMESPACE + "/version":
                if raw != VERSION:
                    raise ValueError("unknown staged Macintosh companion version")
                marker = True
            else:
                record = decode(raw)
                if name != companion_path(record.path).as_posix():
                    raise ValueError("staged companion hash/path mismatch: " + repr(name))
                if entries.get(record.path, (None,))[0] not in (b"100644", b"100755"):
                    raise ValueError("staged companion has no regular data fork: " + repr(record.path))
                count += 1
        if not marker:
            raise ValueError("missing staged Macintosh companion version")
        process.stdin.close()
        if process.wait():
            raise ValueError("Git could not finish reading staged objects")
        return count
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
        if not process.stdin.closed:
            process.stdin.close()


def publish_new(root, relative, data):
    target = checked_path(root, relative, False)
    target.parent.mkdir(parents=True, exist_ok=True)
    checked_path(root, relative.parent)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".mac-forks-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # Atomic publication that cannot replace an existing record. If this
        # filesystem cannot hard-link, fail while retaining the original.
        os.link(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def rename(root, old, new):
    logical_path(old)
    logical_path(new)
    if old == new:
        raise ValueError("old and new paths are identical")
    found = records(root)
    validate(root, found, (old,))
    before = checked_path(root, Path(*old.split("/")), False)
    after = checked_path(root, Path(*new.split("/")))
    if before.exists() or not after.is_file():
        raise ValueError("run git mv for one regular file before repairing its companion")
    if old not in found:
        return 0
    source = checked_path(root, companion_path(old))
    if source.read_bytes() != found[old].raw:
        raise ValueError("source companion changed during operation")
    staged_source_matches(root, companion_path(old), found[old].raw)
    publish_new(root, companion_path(new), encode_path(found[old], new))
    if source.read_bytes() != found[old].raw:
        raise ValueError("source changed; both companion records retained for review")
    source.unlink()
    return 1


def remove(root, old):
    logical_path(old)
    found = records(root)
    validate(root, found, (old,))
    if checked_path(root, Path(*old.split("/")), False).exists():
        raise ValueError("run git rm for one file before removing its companion")
    if old not in found:
        return 0
    relative = companion_path(old)
    source = checked_path(root, relative)
    # Match git rm's protection against silently losing unstaged edits.
    staged_source_matches(root, relative, found[old].raw)
    if source.read_bytes() != found[old].raw:
        raise ValueError("source companion changed during operation")
    source.unlink()
    return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("validate")
    check.add_argument("--cached", action="store_true", help="validate the staged snapshot before committing")
    move = commands.add_parser("rename")
    move.add_argument("old")
    move.add_argument("new")
    delete = commands.add_parser("remove")
    delete.add_argument("path")
    args = parser.parse_args()
    try:
        root = args.repo.resolve(strict=True)
        if args.command == "validate":
            if args.cached:
                count = validate_index(root)
            else:
                found = records(root)
                validate(root, found)
                count = len(found)
            print("Validated %d Macintosh companion records%s" % (count, " in the Git index" if args.cached else ""))
        else:
            count = rename(root, args.old, args.new) if args.command == "rename" else remove(root, args.path)
            print("Updated %d companion record(s). Stage with: git add -A .ghclient-mac" % count)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, "mac_forks: %s\n" % error)


if __name__ == "__main__":
    main()
