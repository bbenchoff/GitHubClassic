# Releases

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
