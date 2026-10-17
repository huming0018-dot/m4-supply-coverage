#!/usr/bin/env python3
"""M4-SUPPLY-COVERAGE 完整性校验：冻结件哈希 + 基线漂移。多 agent 同仓靠这个，不靠约定。"""
import argparse, hashlib, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FROZEN = ROOT / "MANIFEST.frozen.sha256"
BASELINE = ROOT / "BASELINE.sha256"
VOLATILE = ("agentkit/", "docs/", "BASELINE.sha256", "MANIFEST.frozen.sha256",
            ".gitignore", "README.md", "AGENTS.md")


def sha256(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def load(p):
    out = {}
    if not p.is_file():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        d, _, rel = line.partition("  ")
        out[rel] = d
    return out


def check(label, manifest):
    if not manifest:
        print(f"[SKIP] {label}：无清单")
        return 0
    missing = [r for r in manifest if not (ROOT / r).is_file()]
    changed = [r for r, d in manifest.items()
               if (ROOT / r).is_file() and sha256(ROOT / r) != d]
    if missing or changed:
        print(f"[FAIL] {label}")
        for r in missing:
            print(f"   缺失: {r}")
        for r in changed:
            print(f"   被改动: {r}")
        print("   -> 冻结件不得原地改。需修订请新增版本文件（如 regression_set.coverage.v3.json）"
              "并在 ORACLE-REVISION.md 追加记录，保留旧版本。")
        return 1
    print(f"[ OK ] {label}：{len(manifest)} 个文件哈希一致")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    rc = check("FROZEN 冻结件", load(FROZEN))
    base = load(BASELINE)
    if base:
        drift = [r for r, d in base.items()
                 if not (ROOT / r).is_file() or sha256(ROOT / r) != d]
        if drift:
            print(f"[DRIFT] 相对基线改动 {len(drift)} 项:")
            for r in sorted(drift):
                print(f"   {r}")
        else:
            print("[ OK ] BASELINE：无漂移")
    if a.strict:
        bad = [r for r in base if not (ROOT / r).is_file() or sha256(ROOT / r) != base[r]]
        bad = [r for r in bad if not r.startswith(VOLATILE)]
        if bad:
            print("[FAIL] --strict：非易变区被改动 -> " + ", ".join(sorted(bad)))
            rc |= 1
    print("完整性:", "PASS" if rc == 0 else "FAIL")
    return rc


if __name__ == "__main__":
    sys.exit(main())
