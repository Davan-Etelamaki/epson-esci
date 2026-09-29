"""Checks for epson-esci that need no scanner, no root and no network.

Run:  python3 tests/run-tests.py

Fixtures stand in for sysfs, epkowa.desc, the interpreter registry, the SANE
device table and udev, so the generic paths get exercised for models nobody is
sitting in front of. The live scanner is never required.
"""

import hashlib
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "epson-esci")
EVIDENCE = os.path.join(ROOT, "data", "verified-sources.json")

PASSED = [0]
FAILED = []


def check(name, cond, detail=""):
    if cond:
        PASSED[0] += 1
        print("  ok    " + name)
    else:
        FAILED.append(name)
        print("  FAIL  " + name + ("   -> " + detail if detail else ""))


def write(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(chr(10).join(lines) + chr(10))


def load_tool():
    loader = importlib.machinery.SourceFileLoader("esci_under_test", TOOL)
    spec = importlib.util.spec_from_loader("esci_under_test", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def mkdev(parent, name, vendor, product, bus, num, title):
    d = os.path.join(parent, name)
    write(os.path.join(d, "idVendor"), [vendor])
    write(os.path.join(d, "idProduct"), [product])
    write(os.path.join(d, "busnum"), [str(bus)])
    write(os.path.join(d, "devnum"), [str(num)])
    write(os.path.join(d, "product"), [title])
    write(os.path.join(d, "bMaxPower"), ["500mA"])
    write(os.path.join(d, "speed"), ["480"])
    write(os.path.join(d, "power", "control"), ["on"])
    return d


def desc_block(model, vendor, product, status, comment):
    return [
        ":model     " + chr(34) + model + chr(34),
        ":interface " + chr(34) + "USB" + chr(34),
        ":usbid     " + chr(34) + vendor + chr(34) + " " + chr(34) + product + chr(34),
        ":status    :" + status,
        ":comment   " + chr(34) + comment + chr(34),
        "",
    ]


def build_fixture(root, esci):
    sysfs = os.path.join(root, "hubs", "usb9", "b", "c")
    mkdev(sysfs, "2.4.4.1", "04b8", "013d", 9, 101, "EPSON Perfection V39")
    mkdev(sysfs, "2.4.4.2", "04b8", "0720", 9, 102, "EPSON GT-7200")
    mkdev(sysfs, "2.4.4.3", "04b8", "0721", 9, 103, "EPSON GT-S600")

    mkdev(sysfs, "2.4.4.4", "04b8", "0722", 9, 104, "EPSON GT-ZZZ")

    gapfs = os.path.join(root, "gap", "usb9", "b", "c")
    mkdev(gapfs, "2.4.4.2", "04b8", "0720", 9, 102, "EPSON GT-7200")

    lines = []
    for m, p, s, c in [
        ("GT-S650", "0x013d", "good", "requires DFSG non-free iscan-plugin-gt-s650"),
        ("Perfection V39", "0x013d", "good",
         "requires DFSG non-free iscan-plugin-gt-s650 overseas twin of the GT-S650"),
        ("GT-7200", "0x0720", "good", "requires DFSG non-free iscan-plugin-gt-7200"),
        ("GT-S600", "0x0721", "good", "requires DFSG non-free iscan-plugin-gt-s600"),
        ("Perfection 4990 PHOTO", "0x012a", "complete", "US version of the GT-X800"),
        ("GT-ZZZ", "0x0722", "good", "requires DFSG non-free iscan-plugin-gt-zzz"),
    ]:
        lines += desc_block(m, "0x04b8", p, s, c)
    desc = os.path.join(root, "epkowa.desc")
    write(desc, lines)

    html = os.path.join(root, "sane-backends.html")
    write(html, [
        "<html><body><table>",
        "<tr><td>0x04b8/0x013d</td><td>Unsupported</td>",
        "<td>supported by the epkowa backend plus non-free interpreter</td></tr>",
        "<tr><td>0x04b8/0x012a</td><td>Complete</td>",
        "<td>US version of the GT-X800</td></tr>",
        "</table></body></html>",
    ])

    write(os.path.join(root, "sane.d", "dll.conf"), ["epson", "epson2"]) 
    write(os.path.join(root, "sane.d", "dll.d", "iscan"), ["epkowa"]) 
    write(os.path.join(root, "udev", "60-iscan.rules"),
          ["ATTRS{idProduct}==" + chr(34) + "013d" + chr(34) + ", MODE="
           + chr(34) + "0666" + chr(34)])

    plug = os.path.join(root, "lib", "libiscan-plugin-gt-s650")
    write(plug + ".so", ["elf"]) 
    good = os.path.join(root, "fw", "esfw010c.bin")
    write(good, ["firmware-placeholder"]) 

    esci.SYSFS_USB = sysfs
    esci.EPKOWA_DESC = desc
    esci.SANE_BACKENDS_HTML = html
    esci.SANE_CONFIG_DIR = os.path.join(root, "sane.d")
    esci.UDEV_RULES_DIRS = [os.path.join(root, "udev")]
    esci.INTERPRETER_DB = os.path.join(root, "interpreter")
    return {
        "sysfs": sysfs, "gapfs": gapfs, "desc": desc, "html": html,
        "plug": plug, "firmware": good,
    }

def run_cli(args, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run([sys.executable, TOOL] + args, capture_output=True, text=True, env=e)
    return p.returncode, p.stdout + p.stderr


def test_tables(esci):
    print("[1] bundle and firmware tables")
    check("13 plugin families wired", len(esci.BUNDLES) == 13, str(len(esci.BUNDLES)))
    deb = [k for k, b in esci.BUNDLES.items() if b["format"] == "deb"]
    rpm = [k for k, b in esci.BUNDLES.items() if b["format"] == "rpm"]
    check("9 deb + 4 rpm", len(deb) == 9 and len(rpm) == 4, str(len(deb)) + "+" + str(len(rpm)))
    bad = []
    for fam, b in esci.BUNDLES.items():
        if len(b["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in b["sha256"]):
            bad.append(fam + " sha256")
        if not b["url"].startswith("https://download2.ebz.epson.net/"):
            bad.append(fam + " url")
        if b["plugin"] != "iscan-plugin-" + fam:
            bad.append(fam + " plugin name")
        if b["bytes"] < 100000:
            bad.append(fam + " size")
    check("every bundle has a sha256, https url, plugin name and size", not bad, str(bad))
    leaked = [f for f in esci.NO_BUNDLE if f in esci.BUNDLES]
    check("families with no bundle are not advertised as fetchable", not leaked, str(leaked))
    check("6 families recorded as unavailable", len(esci.NO_BUNDLE) == 6, str(len(esci.NO_BUNDLE)))
    hexes = all(len(s) == 40 for _, s in sum((b["firmware"] for b in esci.BUNDLES.values()), []))
    check("observed firmware hashes are sha1 shaped", hexes)
    check("observed table derived, not duplicated",
          ("esfw010c.bin", "bd30c27113b06e957c63891fb6c10ca7a80034ee") in esci.OBSERVED_FIRMWARE)

    if os.path.exists(EVIDENCE):
        ev = json.load(open(EVIDENCE))
        by_plugin = {b["plugin"]: b for b in ev["bundles"]}
        drift = []
        for fam, b in esci.BUNDLES.items():
            e = by_plugin.get(b["plugin"])
            if not e:
                drift.append(fam + " missing from evidence file")
            elif e["sha256"] != b["sha256"] or e["url"] != b["url"]:
                drift.append(fam + " disagrees with evidence file")
        check("code agrees with data/verified-sources.json", not drift, str(drift))
    else:
        check("evidence file present", False, EVIDENCE)


def test_parsing(esci, fx):
    print("[2] parsing and id normalisation")
    check("0x prefix normalised", esci.norm_id("0x04B8") == "04b8")
    check("bare id unchanged", esci.norm_id("013d") == "013d")
    check("garbage tolerated", esci.norm_id(None) == "")
    by = esci.parse_epkowa_desc(fx["desc"])
    check("fixture desc indexed", ("04b8", "013d") in by, str(sorted(by)[:3]))
    check("one usbid maps to both marketing names",
          len(by[("04b8", "013d")]) == 2, str(len(by[("04b8", "013d")])))
    check("plugin extracted from prose",
          esci.plugin_from_comment("requires DFSG non-free iscan-plugin-gt-s650")
          == "iscan-plugin-gt-s650")
    check("no plugin when none named", esci.plugin_from_comment("plain model") is None)
    st = esci.sane_open_source_status("04b8", "013d")
    check("open-source verdict read from docs", st and st[0] == "Unsupported", str(st))
    st2 = esci.sane_open_source_status("04b8", "012a")
    check("supported model reads Complete", st2 and st2[0] == "Complete", str(st2))
    tags = [e["comment"] for v in by.values() for e in v if e.get("comment")]
    check("literal <br> folded out of comments",
          not any("<br" in c for c in tags), str(tags[:1]))


def test_firmware(esci, fx):
    print("[3] firmware classification")
    orig = esci.digest
    def fake(path, algo):
        return fake.value
    esci.digest = fake
    try:
        base = "esfw010c.bin"
        good = "0" * 40
        esci.FIRMWARE_DB.setdefault(base, {}).setdefault("good", {})[good] = "a good build"
        fake.value = good
        lvl, note = esci.firmware_state(fx["firmware"], base)
        check("known-good passes", lvl == esci.OK, lvl)
        conflict = "bd30c27113b06e957c63891fb6c10ca7a80034ee"
        fake.value = conflict
        lvl, note = esci.firmware_state(fx["firmware"], base)
        check("known-bad build is WARN not FAIL", lvl == esci.WARN, lvl)
        check("known-bad names the repair", "--repair" in note, note)
        other = "6caa307a77d791578f5c7611bb62dfb20e6c609b"
        fake.value = other
        lvl, note = esci.firmware_state(fx["firmware"], "esfw86.bin")
        check("observed build names its package", lvl == esci.INFO and "gt-1500" in note, note)
        fake.value = "f" * 40
        lvl, note = esci.firmware_state(fx["firmware"], base)
        check("unrecognised build warns", lvl == esci.WARN, lvl)
        lvl, note = esci.firmware_state(os.path.join(fx["dir"], "nope.bin"), base)
        check("missing firmware fails", lvl == esci.FAIL, lvl)
    finally:
        esci.digest = orig


def test_devices(esci, fx):
    print("[4] device discovery and requirements")
    devs = esci.find_epson_devices()
    check("all fixture devices found", len(devs) == 4, str(len(devs)))
    v39 = [d for d in devs if d["product"] == "013d"][0]
    check("model names resolved", "Perfection V39" in v39["models"], str(v39["models"]))
    check("plugin resolved", v39["plugins"] == ["iscan-plugin-gt-s650"], str(v39["plugins"]))
    check("hub chain counted", v39["hub_hops"] == 2, str(v39["hub_hops"]))
    rows = esci.checks_for(v39)
    levels = {t: l for l, t, d, f in rows}
    check("missing interpreter is a FAIL", levels.get("interpreter registration") == esci.FAIL,
          str(levels))
    write(esci.INTERPRETER_DB, ["interpreter usb 0x04b8 0x013d " + fx["plug"] + " "
                                + fx["firmware"]])
    rows = esci.checks_for(v39)
    levels = {t: l for l, t, d, f in rows}
    check("registered interpreter passes",
          levels.get("interpreter registration") == esci.OK, str(levels))
    check("plugin presence checked", levels.get("interpreter plugin") == esci.OK)
    check("topology warns behind cascaded hubs", levels.get("USB topology") == esci.WARN,
          str(levels.get("USB topology")))
    wanted, gaps = esci.device_families()
    names = [w[0] for w in wanted]
    check("device maps to its bundle", "gt-s650" in names, str(names))
    check("firmware source pulled in via also", "epsonscan2-6.6.2.5" in names, str(names))
    check("rpm family also mapped", "gt-s600" in names, str(names))
    check("unavailable family reported as a gap",
          any(g[0] == "gt-7200" for g in gaps), str(gaps))
    check("a family newer than the table is a gap, not silence",
          any(g[0] == "gt-zzz" for g in gaps), str(gaps))
    check("gap count has no duplicates", len(gaps) == len(set(g[0] for g in gaps)),
          str(gaps))


def test_cli(esci, fx):
    print("[6] command line behaviour")
    env = {
        "EPSON_ESCI_SYSFS": fx["sysfs"],
        "EPSON_ESCI_DESC": fx["desc"],
        "EPSON_ESCI_SANE_DOC": fx["html"],
        "EPSON_ESCI_SANE_CONFIG": os.path.join(fx["dir"], "sane.d"),
        "EPSON_ESCI_UDEV_DIRS": os.path.join(fx["dir"], "udev"),
        "EPSON_ESCI_INTERPRETER": esci.INTERPRETER_DB,
    }
    rc, out = run_cli(["detect"], env)
    check("detect exits 0", rc == 0, str(rc))
    check("detect names the V39", "Perfection V39" in out and "04b8:013d" in out, out[:120])
    rc, out = run_cli(["explain", "04b8:012a"], env)
    check("supported model shows no plugin", "none named" in out, out[:160])
    rc, out = run_cli(["explain", "Perfection V39"], env)
    check("explain accepts the name printed on the scanner",
          rc == 0 and "iscan-plugin-gt-s650" in out, out[:160])
    rc, out = run_cli(["explain", "04b8 013d"], env)
    check("explain accepts a space separated id", rc == 0, out[:120])
    rc, out = run_cli(["explain", "Perfection"], env)
    check("an ambiguous name is reported, not guessed",
          rc == 1 and "matches" in out, out[:160])
    rc, out = run_cli(["explain", "definitely-not-a-model"], env)
    check("an unknown model is an error", rc == 1, str(rc))
    rc, out = run_cli(["fetch", "--dry-run", "--dest", os.path.join(fx["dir"], "cache")], env)
    check("fetch picks the device bundle", "gt-s650" in out, out[:200])
    check("fetch flags rpm-only families", "rpm only" in out, out[:300])
    rpm = os.path.join(fx["dir"], "rpm-only")
    os.makedirs(os.path.join(rpm, "p"), exist_ok=True)
    open(os.path.join(rpm, "p", "iscan-plugin-gt-s600-1.0.0.x86_64.rpm"), "w").close()
    rc, out = run_cli(["install", "--from", rpm, "--dry-run"], env)
    check("rpm-only bundle says so instead of claiming no files",
          rc == 1 and "rpm-only" in out, out[:200])
    check("rpm-only bundle gives the commands to run", "dnf install" in out, out[:200])
    empty = os.path.join(fx["dir"], "emptydir")
    os.makedirs(empty, exist_ok=True)
    rc, out = run_cli(["install", "--from", empty, "--dry-run"], env)
    check("an empty cache points at fetch", rc == 2 and "fetch" in out, out[:200])
    rc, out = run_cli(["--version"], env)
    check("version is reported for bug reports", rc == 0 and "epson-esci" in out, out[:80])
    rc, out = run_cli(["firmware", "--repair"], env)
    check("--repair without --from is a clean error, not a traceback",
          rc == 2 and "Traceback" not in out and "--from" in out, out[:200])
    rc, out = run_cli(["fetch", "--only", "gt-7200", "--dry-run"], env)
    check("a named but unobtainable family gets the reason, not a usage error",
          rc == 1 and "cannot download" in out and "invalid choice" not in out,
          out[:200])
    rc, out = run_cli(["fetch", "--only", "no-such-family"], env)
    check("a made-up family lists what exists", rc == 2 and "known:" in out, out[:200])
    rc, out = run_cli(["fetch", "--only", "nosuch"], env)
    check("unknown family rejected", rc == 2, str(rc))
    gap = dict(env)
    gap["EPSON_ESCI_SYSFS"] = fx["gapfs"]
    rc, out = run_cli(["fetch", "--dry-run"], gap)
    check("unavailable family exits non-zero", rc == 1, str(rc))
    check("unavailable family explains itself", "cannot download" in out, out[:200])
    empty = dict(env)
    empty["EPSON_ESCI_SYSFS"] = os.path.join(fx["dir"], "empty")
    os.makedirs(empty["EPSON_ESCI_SYSFS"], exist_ok=True)
    rc, out = run_cli(["doctor"], empty)
    check("no device is an error, not a crash", rc == 1, str(rc))


def test_probe(esci, fx):
    print("[5] liveness probe")
    dev = {"busnum": 9, "devnum": 101}
    orig_which = esci.shutil.which
    orig_run = esci.subprocess.run
    orig_exists = esci.exists
    try:
        esci.shutil.which = lambda name: None
        lvl, note = esci.probe_device(dev)
        check("probe degrades without scanimage", lvl == esci.INFO, lvl)
        esci.shutil.which = lambda name: "/usr/bin/scanimage"

        class Res:
            def __init__(self, rc, err):
                self.returncode = rc
                self.stderr = err

        made = {"size": 0, "rc": 0, "err": ""}

        def fake_run(cmd, **kw):
            made["cmd"] = cmd
            with open(cmd[-1], "w") as fh:
                fh.write("x" * made["size"])
            return Res(made["rc"], made["err"])

        esci.subprocess.run = fake_run

        made["size"], made["rc"] = 4986, 0
        lvl, note = esci.probe_device(dev)
        check("healthy device passes", lvl == esci.OK, lvl + " " + note)
        check("probe addresses the interpreter device",
              "epkowa:interpreter:009:101" in made["cmd"], str(made["cmd"][:6]))

        made["size"], made["rc"] = 0, 1
        made["err"] = "scanimage: open of device failed: Error during device I/O"
        lvl, note = esci.probe_device(dev)
        check("wedged device fails", lvl == esci.FAIL, lvl)
        check("failure tells you to reset", "reset" in note, note)
        check("failure quotes the device", "device I/O" in note, note)

        made["size"], made["rc"] = 0, 124
        made["err"] = ""
        lvl, note = esci.probe_device(dev)
        check("timeout reported as a timeout", "never answered" in note, note)

        made["size"], made["rc"] = 138, 0
        made["err"] = "scanimage: rounded value of resolution from 50 to 300"
        lvl, note = esci.probe_device(dev)
        check("a 138 byte answer is not called healthy", lvl != esci.OK, lvl)
        check("a rounding notice is not called an error", "rounded" not in note, note)
    finally:
        esci.shutil.which = orig_which
        esci.subprocess.run = orig_run



def main():
    esci = load_tool()
    root = tempfile.mkdtemp(prefix="epson-esci-tests-")
    try:
        fx = build_fixture(root, esci)
        fx["dir"] = root
        test_tables(esci)
        test_parsing(esci, fx)
        test_firmware(esci, fx)
        test_devices(esci, fx)
        test_probe(esci, fx)
        test_cli(esci, fx)
    finally:
        import shutil
        shutil.rmtree(root, ignore_errors=True)
    print()
    print("%d passed, %d failed" % (PASSED[0], len(FAILED)))
    if FAILED:
        for n in FAILED:
            print("  failed: " + n)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())