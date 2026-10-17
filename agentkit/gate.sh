#!/usr/bin/env bash
# M4-SUPPLY-COVERAGE 合并门禁 —— 任何分支合进 integration/* 或 main 前必过。
#   1 冻结件完整性：oracle/回归集未被改
#   2 回归全绿    ：36/36 且 exit 0
#   3 负控有牙    ：故意改坏一个 expected，runner 必须 FAIL 且 exit 非 0
# 第 3 关防止"为了让 CI 变绿而修改测试期望"这种假通过。
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${M4_PYTHON:-python3}"
cd "$ROOT"
fail=0

echo "=== 1/3 冻结件完整性 ==="
"$PY" agentkit/verify_integrity.py || fail=1

echo
echo "=== 2/3 回归 ==="
"$PY" run_regressions.py > /tmp/m4_reg.txt 2>&1
reg_rc=$?
tail -2 /tmp/m4_reg.txt
if [ "$reg_rc" -ne 0 ]; then echo "[FAIL] 回归退出码 $reg_rc"; fail=1; fi

echo
echo "=== 3/3 负控（验证测试不是空转）==="
TMP="$(mktemp -d)"
cp -R . "$TMP/repo" 2>/dev/null
"$PY" - "$TMP/repo" <<'PYEOF'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]) / "regression_set.coverage.v2.json"
d = json.loads(p.read_text(encoding="utf-8"))
cases = d if isinstance(d, list) else d.get("cases", [])
for c in cases:
    if str(c.get("id", "")).startswith("C23"):
        exp = c.get("expected") or c.get("expect") or {}
        if isinstance(exp, dict) and exp:
            k = next(iter(exp))
            exp[k] = "MUTATED_FOR_NEGATIVE_CONTROL"
            print("   已篡改 C23: %s" % k)
            break
p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
PYEOF
( cd "$TMP/repo" && "$PY" run_regressions.py > /tmp/m4_neg.txt 2>&1 )
neg_rc=$?
tail -2 /tmp/m4_neg.txt
rm -rf "$TMP"
if [ "$neg_rc" -ne 0 ] && grep -q "FAIL" /tmp/m4_neg.txt; then
  echo "[ OK ] 负控生效：篡改后正确失败（exit ${neg_rc}）"
else
  echo "[FAIL] 负控未生效（exit ${neg_rc}）——测试可能被改成永远绿"
  fail=1
fi

echo
if [ "$fail" -eq 0 ]; then echo "门禁: PASS —— 允许发起合并"; else echo "门禁: FAIL —— 禁止合并"; fi
exit "$fail"
