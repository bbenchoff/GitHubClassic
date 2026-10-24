"""Check native pack output with independent command-line Git."""
from pathlib import Path
import subprocess


def verify(directory, git, env):
    directory = Path(directory)
    tip, base, full_size, incremental_size = (directory / "graph.txt").read_text().splitlines()

    def run(repo, *args, data=None):
        return subprocess.run([git, "-C", str(repo), *args], input=data,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              check=True, env=env).stdout

    def initialize(name):
        repo = directory / name
        subprocess.run([git, "init", "--bare", "--object-format=sha1",
                        "--initial-branch=main", "-q", str(repo)], check=True, env=env)
        return repo

    def import_pack(repo, path):
        output = run(repo, "index-pack", "--strict", "--stdin", data=path.read_bytes())
        digest = output.decode("ascii").split()[-1]
        index = repo / "objects/pack" / ("pack-" + digest + ".idx")
        return {line.split()[1].decode("ascii") for line in
                run(repo, "show-index", data=index.read_bytes()).splitlines()}

    oracle = initialize("oracle.git")
    full_objects = import_pack(oracle, directory / "full.pack")
    run(oracle, "update-ref", "refs/heads/main", tip)
    run(oracle, "fsck", "--full", "--no-dangling")
    expected = set(run(oracle, "rev-list", "--objects", "--no-object-names",
                       tip, "^" + base).decode("ascii").splitlines())
    target = initialize("remote.git")
    base_objects = import_pack(target, directory / "base.pack")
    run(target, "update-ref", "refs/heads/main", base)
    incremental_objects = import_pack(target, directory / "incremental.pack")
    assert incremental_objects == expected, (incremental_objects ^ expected)
    assert not incremental_objects & base_objects
    assert base_objects | incremental_objects == full_objects
    run(target, "update-ref", "refs/heads/main", tip, base)
    run(target, "fsck", "--full", "--no-dangling")
    assert not import_pack(target, directory / "same.pack")
    assert (directory / "file.pack").read_bytes() == (directory / "incremental.pack").read_bytes()
    print("Independent Git accepted the incremental push: %s -> %s bytes; %d new objects" %
          (full_size, incremental_size, len(expected)))
