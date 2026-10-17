# AGENTS.md — 多 Agent 协作规约

> 本文件是**约束**，不是建议。机器可查的部分在 `agentkit/`，靠自觉的部分在这里。

## 0. 一句话

**每个人（或每个 agent）在自己的分支上干活；只有过门禁的分支才能进 `integration/`；
`main` 是已发布基线，任何人不得直接改。**

## 1. 分支模型

| 分支 | 用途 | 谁可写 | 保护 |
|---|---|---|---|
| `main` | **已发布基线**（当前 = M4-SUPPLY-COVERAGE-02 R2） | **任何人不可直接 push** | 禁止直推，只能走 PR |
| `integration/r2` | 集成分支，门禁通过才可推进 | 每次合并后由脚本更新 | 需门禁绿 |
| `<agent>/<slug>` | 个人/agent 工作分支 | 分支作者 | 自由 |

命名：`<agent>/<简述>`，例：`deuce/fix-none-deficit`、`review/pagination`。**不要**用
`main`、`master`、`tmp`、`test` 这类通用名当工作分支。

## 2. 红线（违反即回滚）

1. **不得原地修改冻结件**
   冻结件 = `MANIFEST.frozen.sha256` 列出的 4 个文件（`coverage_planner.py`、
   `run_regressions.py`、v1/v2 回归集）。
   要改契约 → **新增版本文件**（如 `regression_set.coverage.v3.json`），
   在 `ORACLE-REVISION.md` **追加**一节说明改了什么、为什么。
   **旧版本永不删除、永不覆盖。**

2. **不得修改测试期望来让 CI 变绿**
   门禁第 3 关会主动篡改 C23 的期望值，**若 runner 不失败就说明测试已被改成永远绿**，
   门禁直接 FAIL。这条是自指的：任何"让测试变绿"的改动都会被自己抓住。

3. **不得在 `main` 上直接提交**
   已发布基线只能通过 PR 更新，且 PR 必须附门禁输出。

4. **不得把未上线的东西写成已上线**
   当前状态：34 cells policy / 122 行矩阵 / coverage_planner **均未被 Root 采用、未上线**。
   任何文档、提交信息、PR 描述都不得声称"已上线"或与 `food-tree 1.2.0`
   （hash `509a6ff2…`）**同包**。

5. **不得用"空/未观察"冒充 0**
   `unknown` / `unobserved_in_batch` / `attempted_failed` 等非观察态，
   计数必须是 `null`，`deficit` 必须是 `null`。这是 v2 oracle 的核心契约，不是风格问题。

## 3. 合并门禁

```sh
M4_PYTHON=python3 bash agentkit/gate.sh
```

| 关 | 检查 | 不通过意味着 |
|---|---|---|
| 1 | 冻结件哈希一致 | 你（或别人）改了契约，历史结论全部失效 |
| 2 | 回归 36/36 且 exit 0 | 功能回退 |
| 3 | **负控**：篡改期望后必须 FAIL | 测试已被改成永远绿，门禁失去意义 |

**PR 描述里必须贴出门禁输出**（三关的尾部）。没有输出 = 未验证 = 不接受合并。

## 4. 开工前

```sh
git fetch origin && git checkout -b <agent>/<slug> origin/integration/r2
M4_PYTHON=python3 bash agentkit/gate.sh    # 先确认基线是绿的
```

**基线不绿就不要开工** —— 那说明上一位的改动没收敛，你会在别人的坑里继续挖。

## 5. 冲突处理

- 冻结件冲突 → **停下来说明**，不要自行合并，也不要"以最新为准"覆盖
- `planner` 工作区冲突 → 逐字段人工合并，合并后必须跑门禁
- 拿不准 → 先问，不要用"看起来是同一个东西"消解冲突

## 6. 已知的坑

- **bash 变量紧跟全角标点会被并入变量名**：`exit $neg_rc）` 会报
  `neg_rc）: unbound variable`。写脚本时变量一律用 `${var}` 定界。
- `run_regressions.py` 用 `HERE = dirname(__file__)` **平铺读取**同级 JSON。
  **不要给这批文件加子目录**，会直接 FileNotFoundError。

## 7. 状态查询

| 想知道 | 怎么做 |
|---|---|
| 基线是否绿 | `bash agentkit/gate.sh` |
| 谁改了什么 | `python3 agentkit/verify_integrity.py`（输出 DRIFT 段） |
| 冻结件有哪些 | `cat MANIFEST.frozen.sha256` |
| 这个包能不能上线 | **不能**。见红线 4 |
