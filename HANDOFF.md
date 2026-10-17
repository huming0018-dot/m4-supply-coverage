# M4-SUPPLY-COVERAGE-02 R2 HANDOFF (Deuce side)

唯一新副本：`/tmp/m4-supply-coverage-02-r2-oracle-f9ac80/`。
- R1 目录 `/tmp/m4-supply-coverage-02-r1-7f3c29/`（含 v1 25/28 失败与 R1 bundle c516a511…）原样保留。
- 首版目录 `/tmp/m4-supply-coverage-02-407d22/`（17/17 与旧 bundle b20eea67…）原样保留。
- 未删未改任何旧文件；未重发树包；未碰 Root 已采用版本。

## 版本边界（重要）
- Root 已采用并发布：**food-tree 1.2.0** hash `509a6ff28cd5d447d99f0b8b608c765ba743f957cc62fcdced92199c8581dd71`
  （495 树不变 + 已审福州/闽南两格 policy + 来源/回归）。本 planner 包与 1.2.0 **不是同包**。
- Deuce 的 34 cells policy / 122 行矩阵 / 通用 coverage_planner **均未被 Root 采用、未上线**；
  仅 Root 1.2.0 内福州/闽南两格 policy 已采用。本交付不得称已上线或冒同包。
- 本纯函数只做形状/一致性；来源真实性由 Root 的 SDK adapter 核。

## oracle 版本化（ORACLE-REVISION.md，不改 fixture）
- 冻结 v1：`regression_set.coverage.json`（28 条）与 R1 真实失败（25/28，C01/C02/C05 FAIL）保留。
- 冻结 v2：`regression_set.coverage.v2.json`（36 条）。版本化修订（fixture 输入不变）：
  - C01 → materials 1 / independent_posts 0 / verified_operating_entities 0（crowd_diner 非白名单无身份依据、无已核商户）。
  - C02 → materials 1 / independent_posts 0（同 content_hash 归组 1；准入不达标）。
  - C05 → status unknown / verified_operating_entities null / dropped 2（全拒后无观察，null 不伪 0）。
  - C27 → verified_entities_observed null / deficit null（空跑未观察，v1 的 0/3 是伪造差额）。
  - 每条修订在 v2 spec 内保留 v1_expect 与 basis；旧 expected 与失败证据未暗改。

## R2 四组阻断修复（coverage_planner.py）
1. **None→0 deficit 修复**：unknown / unobserved_in_batch / attempted_failed 等非观察态，
   `verified_entities_observed=null` 且 `deficit=null`；只有 observed 态给数值 deficit。
   未知候选排在独立分组（`ranking_assumption="observation_unknown_deficit_null_not_zero"`），
   排名默认假设不冒真实差额。
2. **价格带 AND 门**：`required_price_bands` 与 `price_band_min_count` 同时给出时两个约束 AND；
   3 家全 value 带 anchor（required 满足但 min_count=2 不满足）判 below（C30）。
   candidate / approved 共用同一个 `_quota_gate`。
3. **runner 全由冻结 v2 驱动**：每 case 构造 flat actual，逐键 deep-equal；
   缺键/多键/类型不符均 FAIL；C34 负控：改一个 expected 必 FAIL（已实测 MUTATED_EXIT=1）；
   任何 FAIL 时进程 `sys.exit(1)`（修复 R1 25/28 却 exit 0）。
4. **合同绑定与隔离**：
   - coverage 输出 `policy_hash`、`coverage_hash`；plan 输出 `policy_hash/matrix_hash/coverage_hash`。
   - task 绑定完整请求（node_ids/crossfacet/source_type/target_fields/evidence_required/
     stop_conditions/roots）、budget（cap/weight）、精确 `observed_refs`（已核实体的
     project/layer/record_id/version/hash/entity_key）。
   - task_id 对上述全部 canonical payload 取 hash；空 coverage 与 3 商户 coverage 的 task_id 不同（C31/C33）。
   - 同输入幂等、不同输入隔离（C09/C14/C33）。
   - 非法请求拒绝：budget 拒 bool/NaN/inf/负数/非数值；task_status 仅 PLANNED_NOT_SUBMITTED；
     task_limit 正整数；selected_cells 字符串列表（C32）。
   - attempts 仅允许 status∈{failed,succeeded}，非法状态抛 ValueError（C35）。

## 引用合同（ODS 整数 vs RAW 无 version，不混为一种）
- 主 exact-ref（ODS 记录）：project_id/layer/record_id/hash 非空，**version 必须整数**（bool 拒绝）；
  非整数 version 判 dropped `missing_or_invalid_ods_exact_ref`（C36）。
- 嵌套 `source_refs`（RAW）：按 SDK 约定**无 version**，只做形状校验（project/layer/record_id/hash）；
  不补假 version，不与 ODS 整数合同混判；形状错判 `malformed_raw_source_refs`（C36）。
- 来源真实性由 SDK adapter 核；纯 planner 不做 Storage 真实性替代。
- 未知 admission（C19 brand_new_unrecognized 等）保持保守未认证、不计 post/商户，不被误拒。

## 一次真实窄测（冻结 v2，36/36）
- 命令：`python3 run_regressions.py`（见 `run_regressions.log`）。
- 结果：36/36 PASS，进程 exit 0。
- 负控实测（不写入交付目录）：临时副本篡改 C23 一个 expected → C23、C34 FAIL，进程 exit 1。
- v2 fixture 默认 version=1（整数）以对齐 ODS 合同；这是合同对齐，不是改输入造绿。
- v1 runner/regset/结果日志原样保留，未被覆盖。

## 未做 / 边界
- 不新采集 / OCR / 模型 / 框架 / 生产 / timer / push / 删除覆盖 / 公开上传 / outbox 提交。
- 不重跑旧任务、不重发树、不重造 495。
- 候选数据 JSON（policy/matrix）为 R1 生成版本，本轮未重生成；builder 原件保留在目录。
- 34 cells/122 矩阵全部 candidate_pending_owner_adoption、approved=false；
  price_tier 为 policy 本地 crossfacet；闽北/莆仙/茶餐厅等无稳定 ID → pending_review。
- 历史"家"标 count_type=historical_curated_shops_NOT_verified_operating_entities、verified=null；
  93 底册标 official_ledger_entries_recall_NOT_verified_operating_entities。
- Deuce 仅有 PRD rev4 吸收版（464 行）；原 PRD2.0/2.2 M4 六件原文 Deuce 缺，Root 已逐行独审。

## 交付物（R2 单 txt 容器，成员与字节/SHA 见容器 manifest）
coverage_planner.py、supply_policy.candidate.json、source_plan_matrix.json、
regression_set.coverage.json（v1 冻结）、regression_set.coverage.v2.json（v2 冻结）、
run_regressions.py、regression_results.json、run_regressions.log、ORACLE-REVISION.md、HANDOFF.md。
