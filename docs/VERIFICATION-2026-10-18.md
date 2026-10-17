# 独立复核记录 · 2026-10-18

> 复核对象：`m4-supply-coverage-02-r2-planner-bundle/v1`（Deuce 侧交付）
> 复核方式：**解包 → 校验哈希 → 独立复跑 → 自建负控**。不采信文档自述。

## 1. 完整性

10 个文件逐一 `sha256` 校验，**10/10 与容器 manifest 声明一致**：

```
✅ coverage_planner.py            ✅ supply_policy.candidate.json
✅ source_plan_matrix.json        ✅ regression_set.coverage.json (v1 冻结)
✅ regression_set.coverage.v2.json (v2)    ✅ run_regressions.py
✅ regression_results.json        ✅ run_regressions.log
✅ ORACLE-REVISION.md             ✅ HANDOFF.md
```

## 2. 回归复跑

```
$ python3 run_regressions.py
…36/36 passed; failures=[]
exit 0
```

**与 HANDOFF 声称的 36/36 PASS / exit 0 一致。**

## 3. 负控（自建，非照抄其结论）

在**临时副本**上篡改 C23 的一个 expected：

```
C23: verdict 'meets_candidate_target' → 'MUTATED'
→ FAIL C23_fuzhou_anchor_met
→ FAIL C34_oracle_negative_control
→ 34/36 passed; failures=[C23_fuzhou_anchor_met, C34_oracle_negative_control]
→ exit 1
```

原样目录重跑仍 36/36 / exit 0，且**与容器声明逐字节一致**（负控未污染交付件）。
**runner 不是空转 greens** —— 这一点由本次实测确认。

## 4. 结论

| 项 | 结论 |
|---|---|
| 交付件完整性 | ✅ 通过 |
| 回归 | ✅ 36/36，exit 0 |
| 负控有效性 | ✅ 篡改必失败，exit 1 |
| 版本边界表述 | ✅ HANDOFF 明确"非同包、未上线"，未越界声称 |
| 上线状态 | ❌ **仍未上线**，与 Root 采用的 1.2.0 无关 |

## 5. 复核中发现的工程问题（非本包逻辑缺陷）

1. **bash 变量紧跟全角标点会被并入变量名**
   `exit $neg_rc）` 在中文环境下报 `neg_rc：unbound variable`。
   写含中文的 shell 脚本时，变量引用一律用 `${var}` 定界。
   → 已修 `agentkit/gate.sh`，并写入 `AGENTS.md` 第 6 节。

2. **交付件对目录结构有隐式假设**
   `run_regressions.py` 用 `HERE = dirname(__file__)` 平铺读取同级 JSON。
   给这批文件加子目录会直接 `FileNotFoundError`。
   → 因此本次**不重构目录**，治理层（`agentkit/`）独立放置；
     已在 `AGENTS.md` 第 6 节记录该约束。

3. **`regression_results.json` 会被 runner 覆写**
   跑一次回归就改动该文件，`--strict` 完整性检查会报漂移。
   → 已列入 `AGENTS.md` 的易变区说明；该文件不在冻结清单内。

## 6. 未验证项（明确不声称）

- 未核 `supply_policy` / `source_plan_matrix` 的**采样口径与来源真实性**——
  本包为纯函数，来源真实性由 SDK adapter 负责。
- 未做真实端到端采集验证。
- 未评估 34 cells policy 的业务合理性（`approved=false`，待Root 采纳）。
