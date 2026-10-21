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
Limits: 32 MiB per outgoing pack and 2 MiB per Git object.
Fetch and Clone responses are currently buffered, with a 4 MiB limit.

Independent software. Third-party copyright and license notices are in
SRC/LICENSES.txt and the source headers.

## First launch

[Download Classic Github 0.1](Output/GitHubClassic-0.1.sit) and expand the
archive on your Macintosh. Keep the application and login helper together.

On a modern computer, open SRC/Create Network Setup.html and generate a
fresh .ghsetup file. Transfer it to the Mac in binary mode and select it in
the app's secure networking setup dialog. Choose a local vault passphrase,
then approve GitHub Device Flow on a phone or modern computer.

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
