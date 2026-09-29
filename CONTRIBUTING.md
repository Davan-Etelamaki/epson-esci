# Contributing

One executable Python file, `epson-esci`, standard library only. No build step,
no CI, nothing to install.

## Dev loop

```bash
./epson-esci --help
./epson-esci explain 04b8:013d
python3 tests/run-tests.py     # 53 checks; no scanner, no root, no network
```

## Running checks without hardware

Every data path the tool reads is overridable, which is the only reason the
checks can run against fixtures on a machine with no scanner attached:

| Variable | Stands in for |
| --- | --- |
| `EPSON_ESCI_SYSFS` | `/sys/bus/usb/devices` |
| `EPSON_ESCI_DESC` | `/usr/share/iscan-data/epkowa.desc` |
| `EPSON_ESCI_INTERPRETER` | `/var/lib/iscan/interpreter` |
| `EPSON_ESCI_SANE_DOC` | `/usr/share/doc/libsane-common/sane-backends.html` |
| `EPSON_ESCI_SANE_CONFIG` | `/etc/sane.d` |
| `EPSON_ESCI_UDEV_DIRS` | the udev `rules.d` directories |

`tests/run-tests.py` builds throwaway fixtures for all of them in a temp
directory. Add a case there whenever you touch a parser — a change proven only
on the author's V39 has not been proven to work at all.

## Adding a model

Diagnosis already covers all 594 models in `epkowa.desc`; there is no model list
to extend. To add fetch/install for a plugin family, add a `BUNDLES` entry whose
`sha256` **you** verified by downloading that exact URL and hashing it. Copying
a hash out of someone else's recipe is not verification. If the family ships an
interpreter blob, add its `sha1` to the entry's `firmware` list.

Update `data/verified-sources.json` in the same commit. The test suite fails if
the code and that evidence file disagree, so the record of what was actually
verified cannot drift from what the tool offers to download.

## Never call a firmware blob globally good or bad

The same build runs on one board revision and fails on another — that is the
documented `esfw010c.bin` case. Record a build as a *symptom to match* under
`conflict`, naming the package and the affected board revision, so a working
GT-S650 is never reported as broken. Only mark a build `good` when it has been
confirmed on real hardware, and say which revision.

## Bug reports

Please include the output of `epson-esci doctor --json`. The checks are
data-driven, so a wrong verdict is usually a missing table entry, and the JSON
says exactly which check fired.
