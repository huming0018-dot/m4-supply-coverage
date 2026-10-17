# ORACLE-REVISION — regression oracle v1 → v2（Root 裁定版）

本文件**只版本化修订 oracle 期望值**，不改任何受控 fixture 记录，不改 planner 来迁就旧 oracle。
- v1 oracle：`regression_set.coverage.json`（R1 副本，28 条，保留不动）。
- v1 真实失败证据：R1 目录 `regression_results.json` / `run_regressions.log`（25/28，C01/C02/C05 FAIL，保留）。
- v2 oracle：本文档先行冻结；待 Root 本轮剩余 R1 发现齐了之后，与 runner 其余修复同批落地为
  `regression_set.coverage.v2.json` + 新 runner（届时跑一次、出唯一新日志/新单 txt 包）。
- fixture 构造（C01/C02/C05 的输入记录）在 v1、v2 下**完全相同**，只修订预期。

## 逐项修订

### C01_dedup_same_url
- 输入：两条记录，同 `url="u1"`、`content_hash="h1"`，role=crowd_diner，
  independent_diner=true，`admission_status="crowd_diner"`，无 entity_key、无 identity_evidence_ref。
- v1 oracle：materials=1，independent_posts=1，verified_operating_entities=1。
- **v2 oracle：materials=1，independent_posts=0，verified_operating_entities=0。**
- 规范理由：
  1. 同 URL/content_hash 连通归组 → 1 个材料组（不变）。
  2. 独立食客必须同时满足：independent_diner=true + role=crowd_diner
     + admission_status∈policy 白名单（`verified_independent_diner`）+ `identity_evidence_ref` 非空。
     本 fixture 只有 `admission_status="crowd_diner"`（非白名单、无身份依据）→ 不计已准入 post。
  3. 已核经营实体仅 `admission_status=verified_merchant` 且有 entity_key 才计；本 fixture 无 → 0。
  4. v1 把"有独立食客标记"误当已准入 post、并凭空要 1 个已核商户，违反白名单+身份依据契约。

### C02_dedup_same_content_hash
- 输入：两条记录，不同 url（uA/uB）、同 `content_hash="same"`，role=crowd_diner，
  independent_diner=true，`admission_status="crowd_diner"`。
- v1 oracle：materials=1，independent_posts=1。
- **v2 oracle：materials=1，independent_posts=0。**
- 规范理由：
  1. 同 content_hash 连通归组 → 1 个材料组（这正是本用例要测的，保持）。
  2. 准入判定与 C01 相同：`crowd_diner` 非白名单且无 identity_evidence_ref → 0 已准入 post。
  3. v1 的 materials=1 正确；independent_posts=1 是旧宽松准入的错误期望。

### C05_negation_neighbor
- 输入：两条记录，均 `admission_status=verified_merchant` 带 entity_key，
  一条 is_negation=true，一条 is_neighbor_mention=true。
- v1 oracle：verified_operating_entities=0，dropped 含 negation_or_neighbor_cannot_verify。
- **v2 oracle：coverage status=unknown，verified_operating_entities=null，
  dropped 含两条 negation_or_neighbor_cannot_verify。**
- 规范理由：
  1. 否定/邻店提及即便带已核身份也不能验证本格 → 两条均 dropped（这一点保持）。
  2. 全部候选被拒后，该格没有任何可采信观察，状态为 unknown（不是 observed）。
  3. unknown 状态下未核计数必须为 null，不得用 0 冒市场事实；v1 期望 0 与"unknown 不伪 0"契约冲突。
  4. runner 用新版 oracle 的显式 null 断言，**不再硬编码 0**。

## 未变项（防止越权修订）
- 其余 C03–C28（含 C18–C28 全部 R1 反例/正控）v1 oracle 与新契约一致，v2 不改期望。
- C03/C04/C06–C17/C18–C28 的 fixture 与期望均不动。

## 本轮其余 R1 修复要求（Root 已列，待同批落地，不在本文档内编造结果）
1. 任务与 coverage 必须绑定 pack_ref + policy hash + matrix hash + coverage hash；
   并绑定**精确观察 refs**（被计入的 verified 记录的 project/layer/record_id/version/hash），
   不接受 caller 口头 refs。
2. 当前 plan 对 `verified_operating_entities=None` 用 `have=0` 直接算 deficit —— 需修：
   unknown/未观察态下 `verified_entities_observed=null` 且 `deficit=null`，
   不得用排名/默认假设冒真实差额；只有 observed 态才给数值 deficit。
3. 任务预算 / 来源 / 结构（node_ids、crossfacet、target_fields、stop_conditions 等）变更必须改变 task_id；
   幂等包含这些字段。
4. 非法 budget（负数/非数值/超额）与非法 status（非 PLANNED_NOT_SUBMITTED 等）必须拒绝并报错，
   不静默产出。

## 边界
- 本目录是 R2 唯一新副本；R1 目录（含 v1 失败、R1 bundle）与 407d22 旧目录全部保留，不删不覆盖。
- 不动 Root 1.2.0 / 509a6ff2… 树包；不重发树。
- 未完成第 1–4 项前不跑回归、不封新包；等 Root 本轮剩余发现到齐后同批施工。
