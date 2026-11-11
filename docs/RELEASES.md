# Releases

## 0.3

* Clone from Server: clone, fetch, pull and push against a Git server other
  than github.com, by `http://` or `https://` address. The server is stored
  with the repository in a new `ghclient-server` record; repositories without
  one are GitHub repositories exactly as before.
* Plain `http://` uses neither the vault nor the TLS seed. `https://` to other
  servers offers ECDHE-ECDSA as well as ECDHE-RSA with AES-128-GCM, and
  verifies against the built-in roots, ISRG Root X1/X2 and an optional
  imported certificate file. github.com keeps its pinned roots and RSA-only
  profile; the wider set is selected per connection and never for GitHub.
* Server sign-in by user name and password after a 401, held in memory only.
  A refused password is forgotten. A request is retried with new credentials
  only while reading the branch advertisement; a POST is never replayed.
* Help > Trust Server Certificate imports a PEM or DER certificate.
* Failures name their cause: untrusted issuer, wrong name, expired or
  not-yet-valid certificate, refused sign-in, missing repository, redirect.
* The ignore-file editor finds File > Close by command, not by position; it
  had been retitling a separator since Open GitHub Repository was added.
* New portable test `tests/server_address.c` (176 checks) for addresses,
  stored server records and request paths.

The vault format, helper protocol, GitHub transport and existing repository
records are unchanged. A 0.2 application opening a server clone made by 0.3
ignores the server record and would address github.com; use 0.3 for those.

Download the root `Install Github Classic.sit` installer archive or the bare
`Output/GitHubClassic-0.3.sit` application archive. Both install the 0.3 app
with its login helper. The installer was rebuilt in a follow-up commit; the
built installer is in `Output/Installer` and its project in `SRC/Installer`.

Known limits for other servers: smart HTTP only, no SSH or `git://`, no
redirects, no saved passwords, one new connection per request, and IP-address
certificates must use the common name. All earlier limits still apply.

## 0.2

* Abort a TLS handshake when Finished hash/PRF calculation fails. Propagate
  the error before sending or comparing verify data; clear failed output.
* Use a stable synthetic Finder type for new plain Git files, avoiding Mac OS
  9 extension-based substitutions that could stop clone checkout. Preserve
  legacy baselines during upgrades and saved-work restoration.
* Require 12 characters consistently for newly created/rekeyed vaults and
  manual credential saves. Keep existing vaults readable; a legacy weak
  passphrase requires an explicit Change Local Passphrase operation.
* Encode new native commit messages and identities as UTF-8. Preserve file
  data-fork bytes and existing commit metadata.
* Omit verified remote history from routine fast-forward push packs. Retain
  full-pack fallback and the existing persistent push-intent/retry protocol.
* Add modern-host companion validation and single-file rename/remove repair,
  reproducible portable tests, generated-header inputs, native merge fixtures
  and architecture/maintenance documentation.

The login-helper protocol and vault format are unchanged. The existing helper
remains compatible. New functionality does not add an automatic migration or
rewrite older commits. Downgrading a 0.2 working repository to 0.1 is not part
of release validation; use a separate clone to test an older application.

Download the root `Install Github Classic.sit` installer archive or the bare
`Output/GitHubClassic-0.2.sit` application archive. Both install the 0.2 app
with its compatible login helper. The updated VISE project and artwork are
included in `SRC/Installer`; the built installer is in `Output/Installer`.

Known limits include buffered fetch/clone, full-history local verification,
uncompressed nondelta outgoing objects, retained checkout backups, no object
garbage collection, linear rebase and whole-file staging. Physical Macintosh
testing remains open. See [maintenance](MAINTENANCE.md) for checks and bounds.

## 0.1

Initial native client, fork-aware Git storage and workflows, verified HTTPS,
Device Flow sign-in, encrypted saved authorization, Toolbox UI and installer.
