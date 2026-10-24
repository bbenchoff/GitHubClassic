# Architecture and repository formats

Classic Github runs its Git and HTTPS implementations on the Macintosh.
CodeWarrior builds the Toolbox application for PowerPC, 68K, and a combined
FAT executable. The background login helper exchanges secrets with the app
through Apple Events; it is not a network proxy.

## Source map

| Area | Entry points |
| --- | --- |
| Application and Toolbox event loop | `Main.c`, `GHWindowUI.c`, `GHDialogUI.c`, `MenuCommands.h` |
| Objects, trees, references and indexes | `GitBytes.c`, `GitStore.c`, `GitIndex.c`, `GitHistory.c` |
| Reachability, fetch and push | `GitGraph.c`, `GitSmart.c`, `GitPack.c`, `GitPush.c`, `GitNetworkUI.c` |
| Logical files and HFS names | `GitRestore.c`, `GitPathMap.c`, `GitWorkMac.c` |
| Checkout planning and publication | `GitCheckoutPlan.c`, `GitCheckout.c`, `GitCheckoutSession.c`, `GitCheckoutMac.c` |
| Merge and saved workflows | `GitTextMerge.c`, `GitFileMerge.c`, `GitTreeMerge.c`, `GitMerge*.c`, `GitRebase*.c`, `GitStash*.c`, `GitWorkspace*.c` |
| Authentication and encrypted state | `GHAuth.c`, `GHCredentialUI.c`, `GHVault.c`, `GHStartupVault.c`, `GHStartupUI.c` |
| Transport and cryptography | `SSLWrapper.c`, `PolarSSL/`, `SHA512Pair.c` |

`Main.c` includes many implementation files directly. Inclusion order is part
of the current build: portable engines appear before the UI controllers that
call them. Files in `PolarSSL` are also project compilation units. Avoid adding
a second project compilation unit for a file already included by `Main.c`.

Portable engines use bounded inputs and callback interfaces. Native adapters
implement File Manager access, catalog identity, leases, file publication and
Toolbox interaction. A host test of a planner does not exercise its native
adapter. Change and test the relevant layers separately.

## Local storage differs from command-line Git

The application exchanges Git objects, commits, trees, indexes and packfiles,
but its physical `.git` layout is specific to Classic Github. A command-line
Git process cannot directly use this local store.

* `format` identifies `GHClient repository 1`.
* `objects/aa/bbbbbbbbbbbb/cccccccccccccccccccccccccc` stores a zlib-compressed
  canonical Git object. Concatenating the three components gives its SHA-1.
  The decompressed bytes are `type SP decimal-length NUL body`.
* Reference filenames use the same 2/12/26 split of the SHA-1 of the reference
  name. A reference record contains `reference-name NUL object-id LF`.
* `HEAD` uses a symbolic reference such as `ref: refs/heads/main`.
* `index` uses Git's index format. Logical Git names and modes remain distinct
  from their physical HFS representations.
* `ghclient-map` starts with `GHMAP001`. It records logical and native paths,
  modes, flags and Finder baselines, with a trailing SHA-1 checksum.

The split filenames accommodate HFS's 31-byte component limit. They do not
change object identities or the names carried in Git trees. To move between
this store and ordinary Git, use fetch/push and a separate clone.

## Macintosh companions

An ordinary Git snapshot keeps a file's data fork at its logical path. Its
optional companion is stored at:

```
.ghclient-mac/forks/<sha1(path)[0:2]>/<sha1(path)[2:14]>/<sha1(path)[14:40]>
```

The path is the exact UTF-8 Git path, without a terminator. The companion is:

| Bytes | Meaning |
| --- | --- |
| 0..7 | `GHMETA01` |
| 8..11 | Big-endian path-byte length |
| Following bytes | Exact logical path |
| Remainder | AppleDouble v2 envelope |

The AppleDouble envelope must contain entry 9 with exactly 32 Finder bytes
and entry 2 with the resource fork, including an empty resource fork when
appropriate. Duplicate entries, overlapping payloads, truncated ranges and
path/hash mismatches are rejected. The version marker is:

```
GHClient Macintosh forks 1
metadata GHMETA01 + path + AppleDouble
```

The native working tree reconstructs these records as actual HFS forks and
attributes. Modern Git keeps the records as files. A modern rename or deletion
must maintain its companion too; see [maintenance](MAINTENANCE.md).

Files without companions use a private synthetic Finder baseline in the path
map. New 0.2 baselines use type `GHCf` and a zero creator. Standard generic
types can trigger Mac OS 9 extension-based substitutions, including through
catalog calls. The private type avoids that behavior without assigning the
file to an editor. Existing `????????` baselines remain valid and are retained.
An unchanged synthetic baseline is not staged as newly invented Mac metadata.
Explicit companion information remains distinct from either baseline.

## Operation state and recovery

Checkout separates planning, temporary files, backups, installation and
publication of the index/map/references. Catalog identity and content checks
prevent an unfamiliar file at an expected path from being treated as owned
scratch data. `checkout-intent` and `checkout-journal` carry recovery state;
an idle journal begins with `GHCI0001`. These files are not disposable caches.

Merge, rebase and stash have additional saved state. Reopening a saved rebase
verifies the completed replay prefix. Resource forks and Finder information
participate in file merge independently from text. Binary resources are never
fed into text conflict-marker generation.

A push persists its account, repository, branch and old/new tips before the
upload. A lost response leaves an uncertain operation. Fresh remote discovery
classifies its result before retry or acknowledgement. A rejected retry alone
does not prove that an earlier request failed.

Normal fast-forward pushes now omit the completely verified closure of the
fresh advertised old tip. The graph queue retains expected object kinds at
shared boundaries. The same object/read budget covers shared and new history.
An unavailable base falls back to a full verified walk; corrupt data, I/O
errors and cancellation do not become permission to omit objects. New remote
branches and force-with-lease pushes retain full-pack behavior.

## Text and credentials

Native identity preferences and TextEdit controls contain MacRoman. New commit
identities and messages cross an explicit MacRoman-to-UTF-8 boundary, with LF
line endings and no BOM. File data forks and existing commit bytes are not
automatically re-encoded. This does not repair legacy commits already written
with undeclared MacRoman text.

The vault envelope begins with `GHVA0001`; its authenticated header describes
the PBKDF2 parameters, salt, nonce and ciphertext length. AES-256-GCM protects
the payload. The startup payload begins with `GHSV0001` and carries persistent
random state, a monotonic reservation counter and optional authorization.
Publication must complete before a reserved TLS seed is released for use.

New vault creation, passphrase changes and manual credential saves require at
least 12 characters. Older vaults still unlock and refresh under their existing
protection. Their owners must use Change Local Passphrase to strengthen them.
The helper caches unlocked state only in RAM and binds a derived-key cache to
the authenticated ciphertext identity. Classic Mac OS does not isolate those
secrets from other local applications.

The bundled TLS sources identify as Mbed TLS 2.28.9, despite their `PolarSSL`
directory name. The 0.2 Finished error-propagation patch is a local change,
not a claim that every later upstream security fix has been incorporated.
