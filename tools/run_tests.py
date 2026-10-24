#!/usr/bin/env python3
"""Run portable regression checks against the checked-in application sources."""
import argparse
import hashlib
import hmac
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]


def finished_vectors():
    transcript = b"client hello|server hello|certificate|key exchange"
    secret = bytes(range(48))
    result = []
    for name in ("sha256", "sha384"):
        digest = getattr(hashlib, name)
        for label in (b"client finished", b"server finished"):
            seed = label + digest(transcript).digest()
            a = hmac.new(secret, seed, digest).digest()
            result.append(hmac.new(secret, a + seed, digest).digest()[:12].hex())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cc", default=os.environ.get("CC", "gcc" if os.name == "nt" else "cc"))
    args = parser.parse_args()
    compiler = shutil.which(args.cc)
    if not compiler:
        parser.error("C compiler not found; use --cc with a GCC-compatible compiler path")
    env = os.environ.copy()
    env["PATH"] = str(Path(compiler).parent) + os.pathsep + env.get("PATH", "")
    git = shutil.which("git")
    if not git:
        parser.error("Git 2.29 or newer is required for pack interoperability checks")
    flags = ["-std=c99", "-O1", "-flto", "-fwhole-program", "-ffunction-sections", "-fdata-sections",
             "-DMBEDTLS_HAVE_INT32"]
    # The port's unsigned-long arithmetic and paired uint64_t require ILP32
    # on Unix. MinGW uses 32-bit long even on 64-bit Windows.
    if os.name != "nt":
        flags.append("-m32")
    flags += ["-include", str(ROOT / "tests/host_abi.h")]
    for script in ("menu_catalog.py", "make_trust_roots.py"):
        subprocess.run([sys.executable, str(ROOT / "tools" / script), "--check"], check=True, env=env)
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"),
                    "-p", "test_tools.py", "-v"], check=True, env=env)
    for directory in ("tests", "SRC", "SRC/PolarSSL"):
        flags += ["-I", str(ROOT / directory)]
    sources = [ROOT / "tests/tls_finished.c"]
    sources += [ROOT / "SRC/PolarSSL" / (name + ".c") for name in
                ("md", "md5", "sha1", "sha256", "sha512", "platform_util", "constant_time")]
    with tempfile.TemporaryDirectory(prefix="ghclassic-tests-") as temporary:
        executable = Path(temporary) / ("tls_finished.exe" if os.name == "nt" else "tls_finished")
        subprocess.run([compiler, *flags, *(str(p) for p in sources),
                        "-Wl,--gc-sections", "-o", str(executable)], check=True, env=env)
        subprocess.run([str(executable), *finished_vectors()], check=True, env=env)
        executable = Path(temporary) / ("plain_defaults.exe" if os.name == "nt" else "plain_defaults")
        subprocess.run([compiler, *flags, str(ROOT / "tests/plain_defaults.c"),
                        "-Wl,--gc-sections", "-o", str(executable)], check=True, env=env)
        subprocess.run([str(executable)], check=True, env=env)
        executable = Path(temporary) / ("incremental_push.exe" if os.name == "nt" else "incremental_push")
        subprocess.run([compiler, *flags, str(ROOT / "tests/incremental_push.c"),
                        "-Wl,--gc-sections", "-o", str(executable)], check=True, env=env)
        subprocess.run([str(executable), temporary], check=True, env=env)
        sys.path.insert(0, str(ROOT / "tests"))
        from verify_push import verify
        verify(temporary, git, env)
        executable = Path(temporary) / ("commit_encoding.exe" if os.name == "nt" else "commit_encoding")
        subprocess.run([compiler, *flags, str(ROOT / "tests/commit_encoding.c"),
                        "-Wl,--gc-sections", "-o", str(executable)], check=True, env=env)
        native = bytes([9, 13, *range(32, 127), *range(128, 256)])
        expected = native.decode("mac_roman").replace("\r", "\n").encode("utf-8")
        subprocess.run([str(executable), expected.hex()], check=True, env=env)
        executable = Path(temporary) / ("vault_policy.exe" if os.name == "nt" else "vault_policy")
        vault_sources = [ROOT / "tests/vault_policy.c", *sources[1:]]
        vault_sources += [ROOT / "SRC/PolarSSL" / (name + ".c")
                          for name in ("aes", "gcm", "cipher", "cipher_wrap",
                                       "chacha20", "poly1305", "chachapoly")]
        subprocess.run([compiler, *flags, *(str(p) for p in vault_sources),
                        "-Wl,--gc-sections", "-o", str(executable)], check=True, env=env)
        subprocess.run([str(executable)], check=True, env=env)


if __name__ == "__main__":
    main()
