# Classic Github

A native GitHub client for the Classic Mac OS. It runs on System 7.5.3 through
Mac OS 9.2.2, on 68K and PowerPC, and speaks TLS 1.2 and Git's wire protocol
with no modern computer anywhere in the middle.

<p align="center">
  <img src="docs/GitHubClassic.png" alt="The main Classic Github window: repository toolbar, Changes and History panes" width="651">
</p>

This repository was pushed to GitHub by the application it contains, running
on a classic Macintosh. That is most of the proof that it works. The full
story — why, and the four or five problems in the way — is in the writeup:
**[Classic GitHub: A GitHub client for the Classic Macintosh OS](https://bbenchoff.com/pages/MacGitHub.html)**.

## What it does

- Clone, fetch, pull, push, branches, commits, diffs, stashes, merges, and
  linear rebases, implemented directly against Git's object model and
  packfile wire protocol. No proxy server, no port of command-line git.
- Verified HTTPS on the Macintosh itself: TLS 1.2 (ECDHE-RSA, P-256,
  AES-128-GCM) over Open Transport, with certificate chain, hostname, and
  date validation. The TLS library is a Classic Mac port of Mbed-TLS
  ([MacSSL](https://bbenchoff.com/pages/MacSSL.html)), bundled in `SRC`.
- GitHub sign-in by [Device Flow](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps#device-flow):
  the Mac shows a code, you approve it on your phone. Your password and 2FA
  never touch the Macintosh. GitHub account passwords are not used as Git
  credentials.
- Saved authorization lives in an encrypted vault in
  `System Folder:Preferences` — AES-256-GCM, key derived from a separate
  local passphrase with PBKDF2-HMAC-SHA256. There is no master key compiled
  into the application.
- Fork-aware everything: commits, diffs, and status understand HFS resource
  forks and Finder metadata, not just the data fork.

<p align="center">
  <img src="docs/SignInToGithub3.png" alt="Device Flow sign-in dialog showing the code to enter at github.com/login/device" width="503">
</p>

## Resource forks in an ordinary Git repository

Classic Mac files have two forks; Git blobs have one. Classic Github commits
the data fork under the file's real name — an ordinary blob anyone on Linux
or Windows can open, edit, and diff — and stores the resource fork and Finder
metadata under a reserved `.ghclient-mac` directory:

```
Hello.c
.ghclient-mac/
├── version
└── forks/
    └── 6f/
        └── 4d9a.../
```

A change made only to a resource fork is a real Git change. Checkout reverses
the process: the HFS file is recreated with both forks and its Finder
metadata. This repository uses the scheme itself — the C sources are plain
blobs, while the CodeWarrior project, interface resources, and built
applications keep their resource forks under `.ghclient-mac`.

**Clone this repository with Classic Github to get working Macintosh files.**
A normal `git clone` on a modern machine gives you readable sources but does
not reconstruct the forks.

<p align="center">
  <img src="docs/UnstagedChanges.png" alt="Unstaged changes view reporting data fork, resource fork, and Finder attribute changes" width="651">
</p>

## Install

[Download the installer](Install%20Github%20Classic.sit) (StuffIt archive of
an Installer VISE installer), or the bare
[application archive](Output/GitHubClassic-0.1.sit). Get it onto your
Macintosh and expand it there. Keep **Classic Github** and **GHClient Login
Helper** in the same folder.

<p align="center">
  <img src="docs/Installer1.png" alt="Installer VISE splash screen: Your code. Your Macintosh." width="540">
</p>

First launch:

1. Choose **Help > Secure Networking Setup...**. On a fresh installation, the
   Set Up Secure Networking window opens. Existing setup is reused; the
   command shows Secure Networking Ready when it is ready for this session.
2. Smash the keyboard and move the mouse **inside the setup window**. Use
   different keys and vary your direction and pace. Allow at least 30
   seconds; Continue stays disabled until enough varied activity has been
   collected. This seeds the random state for TLS.
3. Click **Continue**, then choose and confirm a local vault passphrase. This
   protects the network state and any saved login, and is separate from your
   GitHub password. Creating or unlocking the vault can take a while on a
   68K machine.
4. Choose **Help > Test GitHub Connection** to check Internet access and
   verified HTTPS. Setup itself runs locally and does not contact GitHub.
5. Open **File > Preferences** to sign in, and approve the Device Flow prompt
   on a phone or modern computer. No browser is needed on the Macintosh.

The built-in **Help > Classic Github Guide** repeats these steps. You can
return to Secure Networking Setup at any time; an existing setup does not
require collecting input again, though a locked vault may ask for its
passphrase.

For managed provisioning, Import Setup File accepts a fresh 64-byte
`.ghsetup` file; `SRC/Create Network Setup.html` is an optional offline
generator for modern computers. Generate a separate file for each Macintosh
and transfer it in binary mode. Never distribute a shared setup seed or a
pre-created vault.

## Building from source

`SRC` contains the CodeWarrior Pro 4 project, C sources, the bundled TLS
library, editable interface resources, and third-party license notices.
Sources retain Macintosh text encoding and line endings.

Open `SRC/Classic Github.mcp` in CodeWarrior Pro 4, choose the FAT MacOS
Toolbox target, and Make. The installed classic Mac SDK and CodeWarrior
libraries are required. The project searches `SRC` recursively and writes to
the sibling `Output` folder. The FAT application is named Classic Github; its
Finder creator is `GHCl`. `GHLoginHelper.c` is the login helper entry point
and uses `LoginHelper.rsrc`.

`SRC/Installer` contains the Installer VISE 6 project, color and monochrome
PICT artwork, an editable artwork resource file, and the native Read Me.
Refresh its sources from the current `Output` and `SRC` folders before
building; the built installer lands in `Output/Installer`.

## Version 0.1 scope and limits

Tested in QEMU with Mac OS 9.2.2; physical 68040 and System 7.5.3 testing
remains open. Designed for 640×480, with monochrome cues and color on capable
displays. Anything slower than a fast Quadra is not a good time.

- History is first-parent, staging is whole-file, and rebase is linear.
- Transfers select one branch; submodule checkout is not supported.
- Push prepares its pack on disk and uploads in 16 KiB chunks, with limits of
  128 MiB per outgoing pack and 256 MiB of history read while preparing.
- Fetch and Clone responses are buffered, with a 64 MiB body limit, a 64 MiB
  expanded-pack limit, and a 2 MiB per-object limit.
- The application requests 192 MiB preferred memory (8 MiB minimum); larger
  repositories need the preferred allocation. Quit before changing Memory
  settings in Finder Get Info.
- Active downloads have a ten-minute total allowance and show bytes received;
  stalled TLS I/O times out after two minutes without progress.

## Security notes

Read the writeup's caveats before trusting this with anything important: the
vault is honest cryptography, but this is one person's reimplementation, not
an audited product. The entropy collector relies on an unpredictable operator
and input-timing variation; its activity checks are not a measurement or
certification of min-entropy. QEMU verifies the workflow; physical Macintosh
timing validation remains open.

The distributed application uses the public OAuth Client ID in
`SRC/OAuthConfig.h`. It identifies Classic Github, not a particular
repository; each user approves the application with their own GitHub account
through Device Flow. Public repository access is requested by default, and
private access is an explicit option. Advanced token sign-in uses the
permissions of the token its user supplies — a token restricted to another
repository cannot grant access to this one. Keep personal access tokens and
client secrets out of source and release files.

## License

Independent software, not affiliated with GitHub. Third-party copyright and
license notices are in `SRC/LICENSES.txt` and the source headers.
