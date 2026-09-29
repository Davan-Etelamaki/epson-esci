# epson-esci

**Make EPSON ESC-I flatbed scanners work on Linux — the ones SANE calls
`Unsupported`.**

These scanners are not broken and not unsupported in practice. They need EPSON's
proprietary `epkowa` backend plus a non-free interpreter plugin, and they receive
their operating firmware from the host at run time. Until every piece is in place
they look physically dead: the LED blinks forever and no scanner API can talk to
them.

The tool reads SANE's own device databases to work out what any attached EPSON
scanner needs, so the **diagnosis** covers every USB scanner in `epkowa.desc` —
539 model names across 203 USB ids. The **automated fix** covers 13 of the 19
plugin families — see
[Scope](#scope-what-works-for-which-models). It ships no EPSON binaries — see
[Redistribution](#redistribution-and-licensing).

```
$ ./epson-esci detect
04b8:013d  bus 009 dev 080  GT-S650, Perfection V39  [plugin: iscan-plugin-gt-s650]
    open-source SANE: Unsupported -- supported by the epkowa backend plus non-free interpreter
```

## Contents

- [Who this is for](#who-this-is-for)
- [Scope: what works for which models](#scope-what-works-for-which-models)
- [Quick start](#quick-start)
- [Why these scanners look dead](#why-these-scanners-look-dead)
- [Commands](#commands)
- [How detection works](#how-detection-works)
- [The firmware collision problem](#the-firmware-collision-problem)
- [Wedging and recovery](#wedging-and-recovery)
- [USB power and topology](#usb-power-and-topology)
- [Why GUIs show no scanners for a few seconds](#why-guis-show-no-scanners-for-a-few-seconds)
- [Troubleshooting](#troubleshooting)
- [Supporting another model](#supporting-another-model)
- [Tests](#tests)
- [Removing it](#removing-it)
- [Redistribution and licensing](#redistribution-and-licensing)
- [Tested against](#tested-against)

## Who this is for

Your scanner shows one of these, and you have confirmed it is listed as
`Unsupported` in the SANE supported-devices table:

- The scanner "does not turn on" — the LED blinks and never goes steady.
- `scanimage -L` lists nothing, or only network scanners.
- `sane-find-scanner` finds it only as root; as a user it says "Access denied".
- `scanimage -d <device>` fails with `sane_start: Invalid argument`.
- `scanimage -d <device>` fails with `Error during device I/O`.

Models that behave this way include the Perfection V19, V33, V35, V37, V39, V370,
GT-S640, GT-S650, GT-F500, GT-F600, GT-F700 and relatives. To check before you
install anything, name the scanner the way it is printed on the label:

```
$ ./epson-esci explain "Perfection V39"
04b8:013d
  model   Perfection V39
  status  good   interface USB
  plugin  iscan-plugin-gt-s650
  note    requires DFSG non-free iscan-plugin-gt-s650; overseas version of the GT-S650
  open-source SANE says: Unsupported -- supported by the epkowa backend plus non-free interpreter
```

A name that matches several ids is listed rather than guessed, because printing
a confident answer about the wrong scanner is the worst thing this tool could do.

## Scope: what works for which models

Measured, not aspirational:

| Commands | Coverage |
| --- | --- |
| `detect`, `explain`, `doctor`, `reset` | all 539 USB models in `epkowa.desc` (203 ids) — read from your system at run time |
| `fetch`, `install` | **13 of the 19 plugin families** — 9 as `.deb`, 4 as rpm only |
| `firmware` | names the source package for 7 families; gives a verdict only where a human has confirmed one |

Worth knowing before you decide this tool is for you: **490 of those 539 need no
plugin at all** — open-source SANE handles them, and you want `sane-airscan` or
the `epsonds` backend instead. This exists for the 49 that need a non-free
interpreter and look physically dead without one.

(The file describes 594 model entries; 55 of them name no USB id — SCSI and
IEEE1394 only — so they are outside anything a USB scan can reach, and this tool
does not claim them.)

The 13 families `fetch` can install:

| | |
| --- | --- |
| `.deb` | `cx4400` `ds-30` `gt-1500` `gt-f670` `gt-f700` `gt-s650` `gt-x750` `gt-x770` `perfection-v370` |
| rpm only | `gt-s600` `gt-x820` `gt-x830` `perfection-v550` |

On those four, `fetch` works and `install` stops short: it prints the `dnf` or
`rpm` commands for the packages it fetched and still installs the udev rule,
rather than running apt at a system that has no apt.
| no bundle exists | `gt-7200` `gt-7300` `gt-9400` `gt-f500` `gt-f520` `gt-f600` |

Those last six are 2004-era flatbeds and old WorkForce units. EPSON CDN answers
404 for every version of them in both formats, so `fetch` names the gap and
points at your distribution rather than failing with a bare HTTP error.
`doctor`, `explain` and `reset` still work for them — only `fetch` and `install`
need the bundle.

## Quick start

```bash
chmod +x epson-esci            # one file, stdlib only; or: sudo make install

./epson-esci doctor            # what is wrong, and what fixes it
./epson-esci fetch             # download what this scanner needs, verify checksums
./epson-esci install --from ~/epson-esci-cache
./epson-esci doctor --probe    # ask the scanner to actually scan
scanimage -L                   # then wait a few seconds for the list to fill
```

`fetch` works out which plugin your scanner needs from `epkowa.desc`, so it
downloads one bundle rather than nineteen. `install` is the only command that
needs root, and `--dry-run` prints the whole plan without touching the system.

## Why these scanners look dead

They are bus-powered ESC-I2 devices with **no firmware of their own in flash**. On
the first real command the driver uploads a firmware blob to the scanner, which
re-enumerates on the USB bus (`device firmware changed` in `dmesg`) and only then
behaves like a scanner. Four things must all be true:

1. **The epkowa backend is installed and enabled.** `epson`, `epson2` and `epsonds`
   will never claim these ids — that is a support decision recorded in SANE's own
   device tables, not a bug you can patch around.
2. **The interpreter plugin for this device is installed.**
3. **The interpreter is registered.** `/var/lib/iscan/interpreter` must contain a
   line binding this USB id to the plugin and the firmware file. If that line is
   missing, every USB transfer simply times out, which is indistinguishable from a
   dead scanner.
4. **The firmware blob is the right build for this board revision.** See below.

Plus the boring one: your user must be allowed to open `/dev/bus/usb/BBB/DDD`.

## Commands

| Command | What it does | Root |
| --- | --- | --- |
| `detect [--json]` | List attached EPSON devices and what each needs | no |
| `explain [id or model name]` | Requirement chain for a USB id, a model name, or the attached device | no |
| `doctor [--json] [--probe]` | Every check, plus a verdict; exits non-zero if broken | no |
| `firmware [--repair --from DIR]` | Classify firmware blobs against known-good/known-bad hashes | write needs root |
| `reset [usbid]` | USB-reset a wedged scanner, print its new device name | yes |
| `fetch [--dest DIR] [--only FAM] [--all]` | Download and verify what this scanner needs | no |
| `install --from DIR [--dry-run]` | Install from a fetched directory | yes |

`doctor` works as a CI or boot check. The exit codes are a contract:

| Code | Meaning |
| --- | --- |
| 0 | healthy, or warnings only |
| 1 | something is broken, or the scanner needs a bundle this tool cannot supply |
| 2 | usage or permission problem: bad argument, missing directory, no root where writing is needed |

`--version`, `doctor --json` and the exact command you ran are the three things
worth pasting into a bug report. `--probe` is opt-in because it is the one command
that touches hardware: it makes the scan head move.

## How detection works

There is no single place that says what a scanner needs, so the tool cross-reads
three independent sources and reconciles them:

| Source | Gives you |
| --- | --- |
| `/usr/share/iscan-data/epkowa.desc` | model names, support status, and the required `iscan-plugin-*` name parsed out of the `:comment` field |
| `/usr/share/doc/libsane-common/sane-backends.html` | whether an **open-source** backend covers the id, in SANE's own words |
| `/var/lib/iscan/interpreter` | which plugin and firmware file are actually registered |
| `/sys/bus/usb/devices/*` | what is physically attached, power draw, hub topology, device node |

Two details worth knowing, because both cost real debugging time:

- **One USB id maps to several marketing names.** `04b8:013d` is `GT-S650` in Japan
  and `Perfection V39` elsewhere. `detect` prints all of them.
- **The sources disagree on ID format.** sysfs says `04b8`, `epkowa.desc` and the
  interpreter registry say `0x04b8`, and SANE's HTML says `0x04b8/0x013d`. All
  comparisons go through `norm_id()`. When you add a source, normalise both sides
  or you get silent empty results rather than an error.

The plugin requirement is *derived*, not hard-coded: `epkowa.desc` states it in
prose (`requires DFSG non-free iscan-plugin-gt-s650`) and the tool extracts it.
That is what makes this work for models the author never touched.

## The firmware collision problem

The same firmware filename can ship with different contents in different EPSON
packages, and **one build can be broken for one board revision while working for
every other revision of the same model**. This is the single most confusing failure
in this family, because the driver, the plugin and the config are all correct.

The documented case:

| sha1 | Source | Result on Perfection V39 rev **J371A** |
| --- | --- | --- |
| `bd30c27113b06e957c63891fb6c10ca7a80034ee` | `iscan-plugin-gt-s650` 1.1.1 | `sane_start: Invalid argument` |
| `997f953d3e9373aa515c92bd3025d6a3ac22b8e5` | `epsonscan2-non-free-plugin` 1.0.0.5 (bundle 6.6.2.5) | works |
| `48a29638abec6ed431b4c486ceae35ee244d8555` | `epsonscan2-non-free-plugin` 1.0.0.6 (bundle 6.7.65.0) | unverified |

`firmware` hashes every registered blob and classifies it. `firmware --repair
--from <dir>` swaps in a known-good copy and keeps a `.before-epson-esci` backup.

**Reinstalling or upgrading the plugin package overwrites the good blob with the
bad one.** Protect it:

```bash
sudo apt-mark hold iscan-plugin-gt-s650
```

## Wedging and recovery

These scanners lose their uploaded firmware state — after a failed scan, a suspend,
or a hub power-cycle. The device keeps enumerating normally, so it still looks
present, but refuses all bulk transfers:

```
sanei_usb_write_bulk: trying to write 2 bytes
sanei_usb_write_bulk: 1B 03
sanei_usb_write_bulk: write failed: Input/output error
scanimage: open of device epkowa:interpreter:009:080 failed: Error during device I/O
```

`reset` issues a USB function-level reset, which re-runs the firmware upload — no
cable involved. The device re-enumerates under a **new device number**, so the
command prints the new name:

```
reset 04b8:013d: 009/080 -> 009/081  (power/control=on)
device name is now: epkowa:interpreter:009:081
```

Never hard-code the `BBB:DDD` suffix. It changes on every re-plug and every reset.
`scanimage -L` is always authoritative.

A plain `doctor` **cannot see this state**. Every check in it is read-only, and
every one of them passes while the scanner refuses to talk — only the device
knows. `--probe` is the check that asks the device:

```
$ ./epson-esci doctor --probe
  [PASS] device liveness: device answered with a 4952 byte scan
```

A `FAIL` there means the reset above is the fix. Where `scanimage` is not
installed the check reports INFO rather than guessing.

## USB power and topology

These scanners are bus-powered and typically declare 500 mA. Cascaded unpowered
hubs can enumerate them but cannot carry the current the lamp draws, which is why
they wedge in the first place. `doctor` counts hub hops and warns:

```
[WARN] USB topology: behind 3 hub hops (usb9->9-2->9-2.4->9-2.4.4->9-2.4.4.1), declares 500mA
       fix: plug into a direct motherboard port or a self-powered hub
```

A rear motherboard port, USB 2.0 preferred, or a **self-powered** hub. If another
device on the same hub is stuck failing enumeration (`attempt power cycle` in
`dmesg`), it resets its neighbours and will keep knocking the scanner off.

## Why GUIs show no scanners for a few seconds

Document Scanner and friends call `sane_get_devices()` once at startup, and every
backend configured for `net autodiscovery` runs mDNS/avahi before it returns:

```
[+0.17s] sane_init () -> SANE_STATUS_GOOD
[+5.44s] sane_get_devices () -> SANE_STATUS_GOOD
```

The list is empty the whole time, so the app looks broken when it is only slow.
Wait a few seconds, or delete the `net autodiscovery` lines from the backends
`doctor` lists if you never scan over the network.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| LED blinks forever, nothing detects it | interpreter not registered | `sudo iscan-registry -a`, else reinstall the plugin |
| `Access denied` as user, works as root | no udev rule for this id | install EPSON's `60-iscan.rules` — shipped in the bundle root, **not by any .deb** |
| `sane_start: Invalid argument` | wrong firmware build for this board rev | `epson-esci firmware --repair --from <dir>` |
| `Error during device I/O` | lost firmware state | `sudo epson-esci reset` |
| `doctor` says working, scans still fail | wedged, invisible to read-only checks | `./epson-esci doctor --probe`, then reset |
| `no backend` / absent from `scanimage -L` | epkowa not enabled | add `epkowa` to `/etc/sane.d/dll.d/iscan` |
| Two devices listed, long pauses | `epkowa.conf` narrowed to `usb 0x04b8 0x013d` | use a bare `usb` line |
| Works, then dies after an apt upgrade | plugin reinstall restored bad firmware | `sudo apt-mark hold iscan-plugin-gt-s650` |
| GUI shows nothing for ~5 s | mDNS discovery | wait, or drop `net autodiscovery` |
| `install` on Fedora/openSUSE does nothing | family is rpm-only | it prints the rpm commands; the udev rule still gets installed |
| Random wedging | starved bus power | direct port or self-powered hub |

## Supporting another model

`detect`, `explain` and `doctor` already cover any id present in `epkowa.desc`.
To add end-to-end fetch/repair for a new plugin family:

1. Find the plugin name: `./epson-esci explain 04b8:XXXX`.
2. Read the family off it (`iscan-plugin-gt-x820` → `gt-x820`) and probe EPSON's
   CDN, which is regular:

   ```
   https://download2.ebz.epson.net/iscan/plugin/<family>/{deb,rpm}/x64/
       iscan-<family>-bundle-<bundlever>.x64.{deb,rpm}.tar.gz
   ```

   Two traps, both found the hard way:
   - **`<bundlever>` is the iscan core version, not the plugin version.** They
     differ per family and using the plugin version 404s. Most families are on
     `2.30.4`; `gt-f500`, `gt-f520` and `gt-f600` are on `2.27.1`.
   - **Four families publish rpm only.** A deb-only assumption silently finds
     nothing for `gt-s600`, `gt-x820`, `gt-x830` and `perfection-v550`.

3. Download it, hash it, and record the sha256 you computed in `BUNDLES`. Never
   record a checksum you did not compute yourself from a completed download.
4. Extract the firmware blob, hash it with sha1, and if it collides across
   packages add it to `FIRMWARE_DB` under `good`, `conflict` or `unknown` with a
   note naming the package and the board revision. `OBSERVED_FIRMWARE` is derived
   from `BUNDLES`, so step 3 already tells `firmware` where a blob came from.
5. Add the same entry to `data/verified-sources.json`; a test fails if the two
   disagree.

Deliberate limit: only bundles whose checksums are recorded can be fetched. An
unverified download is worse than none.

**What "verified" means here.** For all 13 families the URL resolves and the
checksum was reproduced from a local download. That is not a fixed scanner:
only `gt-s650` / Perfection V39 has been confirmed to scan end to end.

## Tests

```bash
make test          # or: python3 tests/run-tests.py
```

53 checks. No scanner, no root, no network. Fixtures stand in for sysfs,
`epkowa.desc`, the interpreter registry, the SANE device table and udev, so the
generic paths get exercised for models nobody here owns — including the failure
modes that are awkward to reproduce on purpose: a wedged device, a registry with
no line for the attached scanner, a firmware build from the wrong package.

Every data path is overridable so fixtures can be used at all:
`EPSON_ESCI_SYSFS`, `EPSON_ESCI_DESC`, `EPSON_ESCI_INTERPRETER`,
`EPSON_ESCI_SANE_DOC`, `EPSON_ESCI_SANE_CONFIG`, `EPSON_ESCI_UDEV_DIRS`.

The suite is checked against deliberate regressions — a corrupted checksum, a
firmware conflict promoted to a hard failure, a broken derivation — and it fails
on each. A suite that cannot fail is not evidence.

## Removing it

Nothing uninstalls automatically — these are proprietary packages you chose to
install, and taking them off is worth deciding on purpose.

```bash
sudo apt remove iscan iscan-data iscan-plugin-gt-s650
sudo dpkg -r libsane       # the transitional shim 'install' built. It exists only
                           # in dpkg's own status and in no repository, so apt
                           # will not offer to remove it.
sudo rm /etc/udev/rules.d/60-iscan.rules
sudo udevadm control --reload-rules
rm -rf ~/epson-esci-cache  # EPSON-licensed downloads
```

Do **not** remove `libsane1`. It is a distribution package other software uses;
the shim depends on it, not the other way round.

`apt remove` takes the plugin's own copy of `esfw010c.bin` with it — that file is
owned by `iscan-plugin-gt-s650` — but leaves behind everything this tool created:

```bash
ls /usr/share/iscan/       # *.before-epson-esci and *.bak outlive the uninstall
```

The interpreter registry is not cleaned either. `grep 04b8
/var/lib/iscan/interpreter` should print nothing. If a line is left, pass the
spec as separate arguments exactly as the file shows it — the leading word
`interpreter` is part of the spec, and quoting the whole line as one argument
fails with `not enough parameters`:

```bash
sudo iscan-registry -r interpreter usb 0x04b8 0x013d \\
     /usr/lib/iscan/libiscan-plugin-gt-s650 /usr/share/iscan/esfw010c.bin
```

With the plugin gone the scanner goes back to looking dead: blinking LED, nothing
in `scanimage -L`. That is the correct end state, not a failed uninstall.

## Redistribution and licensing

**This repository contains no EPSON binaries.** EPSON's end-user licence, section 3:

> "You may not rent, lease, distribute, lend the Software to third parties or
> incorporate the Software into a revenue generating product or service."

and its preamble defines "Software" as including "any related documentation,
**firmware**, or updates". The only permitted transfer requires handing over "the
Epson Hardware" too. `iscan-plugin-gt-s650` states outright: "The original source
is non-free and can not be made available."

So this tool ships **URLs and checksums only**, exactly as AUR package recipes do,
and for the same reason: each user downloads from EPSON and accepts EPSON's licence
themselves. Debian and Ubuntu ship none of these packages for the same reason.

| Piece | Licence | In this repo |
| --- | --- | --- |
| `epson-esci`, this README | yours | yes |
| `iscan-data` | GPL-2.0+ | no, fetched |
| `iscan` | GPL **and** EPSON EULA (mixed; ships a non-free blob) | no, fetched |
| `iscan-plugin-*` | EPSON EULA, source expressly unavailable | no, fetched |
| firmware blobs | EPSON EULA ("firmware") | no, fetched |

Do not mirror EPSON's files here, in git, or as release assets — that is the same
distribution. Users must accept the EULA by downloading from EPSON. Using the
firmware swap on hardware you own is inside the licence's personal-use grant.

## Tested against

- Perfection V39 (model label J371A, `04b8:013d`) — full A4 scan at 300 dpi as an
  unprivileged user.
- `epson-esci explain` verified against `04b8:014a`, `04b8:012d`, `04b8:012a`,
  `04b8:0119`, `04b8:012c`, correctly distinguishing plugin-required models from
  ones SANE already marks `Complete`.
- All 13 fetchable families: bundle URL resolves over https and the recorded
  sha256 reproduced from a local download. Seven firmware blobs extracted and
  hashed. Re-downloading the `gt-s650` bundle yields exactly the blob that broke
  this scanner, which reproduces the diagnosis from a clean download.
- 53 fixture checks pass (`make test`), and were confirmed to fail on three
  deliberate regressions.
- Pop!_OS 24.04 (Ubuntu 24.04 base), sane-backends 1.2.1, kernel 7.1.5.

## Provenance

Written against a real Perfection V39 (board rev J371A) that was fixed with this
exact procedure, on the first attempt, as an unprivileged user. The USB ids,
model names, plugin names and support statuses are read from the databases your
system already has, so they describe your machine rather than the author's.

If `doctor` gives a wrong verdict for a model not listed above, open an issue
with the output of `epson-esci doctor --json` — the checks are data-driven, so a
new model usually needs a table entry and nothing else.
