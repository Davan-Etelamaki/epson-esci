# Security

## Integrity model

Every download is pinned to a sha256 (sha512 for the epsonscan2 bundle) recorded
in the source. `fetch` hashes what it received and aborts on a mismatch before
extracting anything, then refuses to install from a partial directory. All URLs
are https on EPSON's own CDN; the test suite rejects any other URL.

This is deliberate. Other packaging in this ecosystem still pulls these same
firmware blobs over **plain HTTP** with nothing but an md5 embedded in the URL
path — the old `iscan-firmware` recipe style still in circulation in the AUR.
It survives only while the mirror is honest: an md5 over plain HTTP catches a
corrupt download, not an attacker. Do not weaken this file's pinning to match.

## No EPSON binaries here

The repo stores URLs and checksums only, so it is not a distribution channel for
firmware or plugins — both because EPSON's EULA forbids redistributing them and
because a mirror here would be a place to substitute a tampered blob. Each user
downloads from EPSON and accepts EPSON's licence themselves.

## Commands that write

- `install --from DIR` (root): runs `apt-get install -y` on the local `.deb`
  paths found under DIR, builds and installs a transitional `libsane` package
  when the system only has `libsane1`, copies the EPSON udev rule into
  `/etc/udev/rules.d` and reloads udev rules, runs `iscan-registry -a`, then the
  firmware repair. `--dry-run` prints the whole plan and writes nothing.
- `firmware --repair --from DIR` (root to write the blob directory): copies a
  known-good blob over the registered one, first saving the original as
  `<blob>.before-epson-esci`. An existing backup is never overwritten.
- `reset [usbid]` (root): opens `/dev/bus/usb/BBB/DDD` and issues a
  `USBDEVFS_RESET` ioctl. Writes nothing to disk; the device re-enumerates.

`doctor --probe` is opt-in because it makes the scan head move.

## Reporting

File an issue for ordinary bugs; report privately instead when it would expose
a serial number, a hostname, a local path, or a real scanned document. Scanned
pages routinely carry third-party personal data — identity documents, medical
and financial records. Never commit a sample scan; `.gitignore` excludes
`*.png`, `*.tif` and `*.jpg` so it is hard to do by accident.
