# M4-SUPPLY-COVERAGE-02 · 食材供给覆盖度规划器

> **状态：候选，未上线。** 34 cells policy / 122 行矩阵 / `coverage_planner`
> **均未被 Root 采用、未上线**。本包与已发布的 `food-tree 1.2.0`
> （hash `509a6ff2…`）**不是同包**，任何文档不得声称同包或已上线。

## 这是什么

一个**纯函数**的覆盖度/采集规划器：读入 policy、matrix 与观察记录，输出覆盖状态、
缺口与下一步任务。**只做形状与一致性**，来源真实性由 Root 的 SDK adapter 核。

## 仓库地图

交付件（**保持平铺**，`run_regressions.py` 按 `dirname(__file__)` 同级读取 JSON）：

| 文件 | 作用 | 冻结 |
|---|---|---|
| `coverage_planner.py` | 规划器本体 | ✅ |
| `run_regressions.py` | 回归 runner | ✅ |
| `regression_set.coverage.json` | v1 oracle（28 条，冻结） | ✅ |
| `regression_set.coverage.v2.json` | v2 oracle（36 条，当前） | ✅ |
| `supply_policy.candidate.json` | 34 cells policy 候选 | |
| `source_plan_matrix.json` | 122 行来源矩阵 | |
| `regression_results.json` / `run_regressions.log` | 上次运行留痕 | |
| `ORACLE-REVISION.md` | v1→v2 oracle 修订记录（**只追加**） | |
| `HANDOFF.md` | Deuce 侧交接 | |

治理层（新增，不侵入交付件）：

| 路径 | 作用 |
|---|---|
| `AGENTS.md` | **多 agent 协作规约**：分支模型、红线、门禁 |
| `agentkit/gate.sh` | 合并门禁三关 |
| `agentkit/verify_integrity.py` | 冻结件哈希 + 基线漂移 |
| `MANIFEST.frozen.sha256` | 冻结件清单 |
| `BASELINE.sha256` | 工作区基线快照 |
| `docs/VERIFICATION-2026-10-18.md` | 独立复核记录 |

## 快速开始

```sh
python3 run_regressions.py                      # 回归，应 36/36 且 exit 0
M4_PYTHON=python3 bash agentkit/gate.sh         # 合并门禁三关
python3 agentkit/verify_integrity.py            # 只看完整性
```

## 核心契约（改动前先读 `ORACLE-REVISION.md`）

1. **`unknown` 不伪 0** —— 没有观察 ≠ 观察到 0 个。
   非观察态下 `verified_operating_entities=null`、`deficit=null`。
2. **独立信源要过白名单** —— `independent_diner=true` **且**
   `admission_status` 在 policy 白名单内 **且** `identity_evidence_ref` 非空，
   三者同时满足才算已准入 post。
3. **同 URL / content_hash 连通归组** —— 同稿多转不算多个独立来源。
4. **精确引用分ODS / RAW** —— ODS 必须整数 `version`；RAW 无 `version`，不补假值。
5. **任务只产出 `PLANNED_NOT_SUBMITTED`** —— 规划器不提交任何东西。
6. **改契约要版本化** —— 新增 v3，保留 v1/v2，只在 `ORACLE-REVISION.md` 追加。

## 相关但不属于本包

- `food-tree 1.2.0`（Root 已采用并发布）——**不同包**
- 采集 / OCR / 模型 / 生产 /定时推送 —— 均不在本包范围
