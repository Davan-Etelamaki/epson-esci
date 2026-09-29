# epson-esci

**Make EPSON ESC-I flatbed scanners work on Linux — the ones SANE calls
`Unsupported`.**

These scanners are not broken and not unsupported in practice. They need EPSON's
proprietary `epkowa` backend plus a non-free interpreter plugin, and they receive
their operating firmware from the host at run time. Until every piece is in place
they look physically dead: the LED blinks forever and no scanner API can talk to
them.

The tool reads SANE's own device databases to work out what any attached EPSON
scanner needs, so the **diagnosis** covers all 594 models in `epkowa.desc`. The
**automated fix** currently covers 1 of the 19 plugin families — see
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
GT-S640, GT-S650, GT-F500, GT-F600, GT-F700 and relatives. `epson-esci explain
<usbid>` tells you whether a given id needs a plugin.

## Scope: what works for which models

Measured, not aspirational:

| Commands | Coverage |
| --- | --- |
| `detect`, `explain`, `doctor`, `reset` | all 594 models in `epkowa.desc` — everything is read from your system at run time |
| `fetch`, `install`, `firmware --repair` | **1 of 19 plugin families**: `iscan-plugin-gt-s650`, i.e. GT-S650 and Perfection V39 |

Worth knowing before you decide this tool is for you: **545 of those 594 models
need no plugin at all** — open-source SANE handles them, and you want
`sane-airscan` or the `epsonds` backend instead. This exists for the awkward 49
that need a non-free interpreter and look physically dead without one.

If `explain` names a plugin other than `iscan-plugin-gt-s650`, expect
`doctor`, `explain` and `reset` to work and `fetch` to have nothing to download.
Install the plugin from your distribution, then use `firmware` to check the blob.
[Supporting another model](#supporting-another-model) is around 15 minutes per
family and pull requests are welcome.

## Quick start

```bash
./epson-esci doctor            # what is wrong, and what fixes it
./epson-esci fetch             # download EPSON bundles, verify checksums
./epson-esci install --from ~/epson-esci-cache
./epson-esci doctor            # should now report "working, with warnings"
scanimage -L                   # then wait a few seconds for the list to fill
```

`install` is the only command that needs root, and `--dry-run` on it prints the
whole plan without touching the system.

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
| `explain [usbid]` | Full requirement chain for a USB id, or for the attached device | no |
| `doctor [--json]` | Every check, plus a verdict; exits non-zero if broken | no |
| `firmware [--repair --from DIR]` | Classify firmware blobs against known-good/known-bad hashes | write needs root |
| `reset [usbid]` | USB-reset a wedged scanner, print its new device name | yes |
| `fetch [--dest DIR] [--only NAME]` | Download and verify EPSON bundles | no |
| `install --from DIR [--dry-run]` | Install from a fetched directory | yes |

`doctor` exits 0 when healthy or merely warned, 1 when something is broken — so it
works as a CI or boot check.

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
| `no backend` / absent from `scanimage -L` | epkowa not enabled | add `epkowa` to `/etc/sane.d/dll.d/iscan` |
| Two devices listed, long pauses | `epkowa.conf` narrowed to `usb 0x04b8 0x013d` | use a bare `usb` line |
| Works, then dies after an apt upgrade | plugin reinstall restored bad firmware | `sudo apt-mark hold iscan-plugin-gt-s650` |
| GUI shows nothing for ~5 s | mDNS discovery | wait, or drop `net autodiscovery` |
| Random wedging | starved bus power | direct port or self-powered hub |

## Supporting another model

`detect`, `explain` and `doctor` already cover any id present in `epkowa.desc`.
To add end-to-end fetch/repair for a new plugin family:

1. Find the plugin name: `./epson-esci explain 04b8:XXXX`.
2. Get EPSON's bundle URL and record its sha256 or sha512 in `BUNDLES`. The AUR
   PKGBUILDs are a good independent source for those checksums — cross-check.
3. If the blob collides across packages, add its sha1 to `FIRMWARE_DB` under
   `good`, `bad` or `unknown` with a note naming the package and the affected
   board revision.

Deliberate limit: only bundles whose checksums are recorded can be fetched. An
unverified download is worse than none.

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
- Pop!_OS 24.04 (Ubuntu 24.04 base), sane-backends 1.2.1, kernel 7.1.5.

## Provenance

Written against a real Perfection V39 (board rev J371A) that was fixed with this
exact procedure, on the first attempt, as an unprivileged user. The USB ids,
model names, plugin names and support statuses are read from the databases your
system already has, so they describe your machine rather than the author's.

If `doctor` gives a wrong verdict for a model not listed above, open an issue
with the output of `epson-esci doctor --json` — the checks are data-driven, so a
new model usually needs a table entry and nothing else.
