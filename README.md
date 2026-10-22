# Classic Github

A GitHub client for classic Macintosh. Version 0.1.

Native Changes and History, fork-aware commits and diffs, branches, Fetch,
Clone, Pull and Push. GitHub sign-in uses Device Flow and verified HTTPS.
Saved authorization is encrypted with a separate local passphrase.

## Build

SRC contains the CodeWarrior Pro 4 project, C sources, bundled TLS library,
editable interface resources and third-party license notices.
Sources retain Macintosh text encoding and line endings.

Open SRC/Classic Github.mcp in CodeWarrior Pro 4. Choose FAT MacOS Toolbox
and Make. The installed classic Mac SDK and CodeWarrior libraries are required.
The project searches SRC recursively and writes to the sibling Output folder.
The FAT application is named Classic Github; its Finder creator is GHCl.
GHLoginHelper.c is the helper entry point; it uses LoginHelper.rsrc.

Output contains the FAT 68K/PowerPC application, individual architecture
builds and login helper. Keep Classic Github and GHClient Login Helper
in the same folder. The docs directory is reserved for future documentation.

Approve GitHub sign-in on a phone or modern computer. GitHub account
passwords are not used as Git credentials.

Clone with Classic Github to restore Macintosh resource forks and Finder
attributes. A normal Git checkout alone does not restore those forks.

## Version 0.1

System 7.5.3 with Open Transport is the target. Tested in QEMU with
Mac OS 9.2.2; physical 68040 and System 7.5.3 testing remains open.
Designed for 640x480, with monochrome cues and color on capable displays.
History is first-parent, staging is whole-file and rebase is linear.
Transfers select one branch; submodule checkout is not supported.
Push prepares its pack on disk and uploads in 16 KiB chunks.
Limits: 128 MiB per on-disk outgoing pack, 256 MiB of history read while
preparing Push, and 2 MiB per Git object.
Fetch and Clone responses are currently buffered, with a 64 MiB body limit
and 64 MiB expanded-pack limit. The application requests 192 MiB preferred
memory (8 MiB minimum); larger repositories need the preferred allocation.
Quit the application before changing its Memory settings in Finder Get Info.
Active Fetch/Clone downloads have a ten-minute total allowance and show bytes
received; stalled TLS I/O still times out after two minutes without progress.

Independent software. Third-party copyright and license notices are in
SRC/LICENSES.txt and the source headers.

## First launch

[Download the installer](Install%20Github%20Classic.sit), or
[download the application archive](Output/GitHubClassic-0.1.sit). Expand the
archive on your Macintosh. Keep the application and login helper together.

1. Choose **Help > Secure Networking Setup...**. On a fresh installation, the
   Set Up Secure Networking window opens. Existing setup is reused; the command
   shows Secure Networking Ready when it is ready for this session.
2. Smash the keyboard and move the mouse **inside the setup window**. Use
   different keys and vary your direction and pace. Allow at least 30 seconds;
   Continue stays disabled until enough varied activity has been collected.
3. Click **Continue**, then choose and confirm a local vault passphrase. This
   protects the network state and any saved login. It is separate from your
   GitHub password. Creating or unlocking the vault can take a while.
4. Choose **Help > Test GitHub Connection** to check Internet access and verified
   HTTPS. Setup itself runs locally and does not contact GitHub.
5. Open **File > Preferences** to sign in. Approve GitHub Device Flow on a phone
   or modern computer. No browser is needed on the Macintosh.

You can return to Secure Networking Setup at any time. An existing setup does
not require collecting input again; a locked vault may ask for its local
passphrase. Signing in also opens setup automatically if needed. The built-in
Help > Classic Github Guide includes these setup steps.

The initial seed is conditioned from active user input in memory, then saved
as encrypted network state. Existing installations reuse their saved state.
The collector relies on an unpredictable operator and input-timing variation;
its activity checks are not a measurement or certification of min-entropy.
QEMU verifies the workflow; physical Macintosh timing validation remains open.

For managed provisioning, Import Setup File accepts a fresh 64-byte .ghsetup
file. SRC/Create Network Setup.html remains an optional offline generator for
modern computers. Generate a separate file for each Macintosh and transfer
it in binary mode. Never distribute a shared setup seed or a pre-created vault.

An installer needs the FAT Classic Github application and GHClient Login
Helper in the same folder, plus the Read Me and SRC/LICENSES.txt notices.

## GitHub authorization

The distributed application uses the public OAuth Client ID in SRC/OAuthConfig.h.
It identifies Classic Github, not a particular repository. Each user approves
the application with their own GitHub account through Device Flow. Public
repository access is requested by default; private access is an explicit option.
Keep personal access tokens and client secrets out of source and release files.

The GitHub-hosted registration controls the name and homepage shown during
authorization. Its public name should be Classic Github and its homepage should
be https://github.com/bbenchoff/GitHubClassic, with Device Flow enabled.
Changing that display information does not require replacing the public Client ID.

Advanced token sign-in uses the permissions of the token supplied by its user.
A token restricted to another repository cannot grant access to this one.

## Installer sources

SRC/Installer contains the Installer VISE 6 project, color and monochrome PICT
artwork, an editable artwork resource file, and the native Read Me. The VISE
project archives the application, login helper, Read Me and license notices.
Refresh its sources from the current Output and SRC folders before building.
The installer is in Output/Installer. Its downloadable StuffIt archive,
Install Github Classic.sit, is at the repository root.
