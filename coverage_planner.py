#!/usr/bin/env python3
# M4-SUPPLY-COVERAGE-02 R1 generic coverage / collection planner (review fix).
# Domain-neutral: no food names, no domain lists. All policy (quotas, source roles,
# cells) comes from the pack/policy objects.
#
# R1 review fixes:
#  - task field verified_entities_observed = ACTUAL observed count (deficit separate).
#  - quota gate validates count AND price_band_min_count/required_price_bands AND
#    anchor_dish, for BOTH candidate and approved branches.
#  - partial_pending mapping is NOT auto-planned: blocker blocked_partial_mapping.
#  - non-observed states (unknown/unassessed/unobserved_in_batch/attempted_failed)
#    report verified_operating_entities = null, never a fabricated 0 market fact.
# Other rules unchanged:
#  - exact refs (project/layer/record_id/version/hash);
#  - URL/content_hash connected-component dedupe;
#  - three counts separate (materials / independent posts / verified entities);
#  - lexical/M2_REVIEW/OCR-low-confidence never count as verified merchants or
#    independent diner posts;
#  - empty materials never equal zero supply;
#  - PLANNED_NOT_SUBMITTED tasks only; deterministic & idempotent.
import hashlib, json, math
from collections import defaultdict

PLANNED_STATUS = "PLANNED_NOT_SUBMITTED"

NOT_VERIFIED = {"lexical_match", "m2_review", "ocr_low_confidence", "rejected", "unverified"}
VERIFIED = "verified_merchant"
# states in which no verification happened in-batch -> verified count is null
NO_ASSERT_STATES = {"unknown", "unassessed", "unobserved_in_batch", "attempted_failed"}


def _canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _components(records):
    parent = list(range(len(records)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    url_idx, hash_idx = {}, {}
    for i, r in enumerate(records):
        u, h = r.get("url"), r.get("content_hash")
        if u:
            if u in url_idx:
                union(i, url_idx[u])
            url_idx.setdefault(u, i)
        if h:
            if h in hash_idx:
                union(i, hash_idx[h])
            hash_idx.setdefault(h, i)
    comps = defaultdict(list)
    for i in range(len(records)):
        comps[find(i)].append(i)
    return list(comps.values())


def _main_ref_ok(r):
    """Main ODS exact-ref contract: project/layer/record_id/hash non-null,
    version must be an INTEGER (ODS integer version). bool rejected."""
    if not all(r.get(k) is not None for k in ("project_id", "layer", "record_id", "version", "hash")):
        return False
    return isinstance(r["version"], int) and not isinstance(r["version"], bool)


def _source_refs_ok(r):
    """RAW source_refs follow the SDK convention: NO version field.
    The pure function only checks shape/consistency; the SDK adapter verifies
    authenticity. RAW version-less refs must NOT be judged by the ODS contract."""
    refs = r.get("source_refs")
    if refs is None:
        return True
    if not isinstance(refs, list):
        return False
    for s in refs:
        if not isinstance(s, dict):
            return False
        if not all(s.get(k) is not None for k in ("project_id", "layer", "record_id", "hash")):
            return False
        if "version" in s and s["version"] is not None:
            # RAW convention has no version; a stray non-null version here is a
            # contract mismatch, not a reason to invent one.
            if not (isinstance(s["version"], int) and not isinstance(s["version"], bool)):
                return False
    return True


def _validate_attempts(attempts):
    if attempts is None:
        return
    if not isinstance(attempts, dict):
        raise ValueError("attempts must be a dict cell_id -> list")
    for cid, lst in attempts.items():
        if not isinstance(lst, list):
            raise ValueError(f"attempts[{cid}] must be a list")
        for a in lst:
            if not isinstance(a, dict) or a.get("status") not in {"failed", "succeeded"}:
                raise ValueError(f"attempts[{cid}] invalid attempt status: {a!r}")


def _quota_gate(q, verified_entities, verified_bands, verified_anchors):
    """Single gate used by candidate AND approved branches.
    Count AND (required_price_bands AND price_band_min_count, BOTH when given) AND anchor."""
    have = len(verified_entities)
    count_ok = have >= q["count"]
    req_bands = q.get("required_price_bands")
    min_bands = q.get("price_band_min_count")
    missing_bands = [b for b in req_bands if b not in verified_bands] if req_bands else []
    req_bands_ok = (not req_bands) or (not missing_bands)
    min_bands_ok = True
    if min_bands is not None:
        min_bands_ok = len(verified_bands) >= min_bands
    # both constraints apply simultaneously (AND)
    band_ok = req_bands_ok and min_bands_ok
    anchor = q.get("anchor_dish")
    missing_anchor = bool(anchor) and anchor not in verified_anchors
    anchor_ok = not missing_anchor
    satisfied = count_ok and band_ok and anchor_ok
    return {
        "count": q["count"], "have": have, "count_ok": count_ok,
        "bands_ok": band_ok,
        "required_price_bands": req_bands,
        "missing_required_bands": missing_bands,
        "price_band_min_count": min_bands,
        "observed_band_count": len(verified_bands),
        "required_bands_ok": req_bands_ok, "min_bands_ok": min_bands_ok,
        "anchor_dish": anchor, "anchor_ok": anchor_ok, "missing_anchor": missing_anchor,
        "satisfied": satisfied,
    }


def coverage(pack_ref, verified_records, attempts, policy, batch_scope=None, keyword_roots=None):
    keyword_roots = keyword_roots or {}
    adm = policy.get("independent_diner_admission", {})
    diner_allowed = set(adm.get("allowed_statuses", []))
    require_identity = bool(adm.get("requires_identity_evidence", True))
    _validate_attempts(attempts)
    attempts = attempts or {}
    scope = set(batch_scope) if batch_scope is not None else None
    policy_cell_ids = {c["cell_id"] for c in policy["cells"]}
    by_cell = defaultdict(list)
    dropped = []
    for r in verified_records:
        if not _main_ref_ok(r):
            dropped.append({"record_id": r.get("record_id"), "reason": "missing_or_invalid_ods_exact_ref"})
            continue
        if not _source_refs_ok(r):
            dropped.append({"record_id": r.get("record_id"), "reason": "malformed_raw_source_refs"})
            continue
        if not r.get("cell_id"):
            dropped.append({"record_id": r.get("record_id"), "reason": "missing_cell_id"})
            continue
        if r["cell_id"] not in policy_cell_ids:
            dropped.append({"record_id": r.get("record_id"),
                            "reason": "cell_id_not_in_policy", "cell_id": r["cell_id"]})
            continue
        if r.get("is_negation") or r.get("is_neighbor_mention"):
            if r.get("admission_status") == VERIFIED:
                dropped.append({"record_id": r.get("record_id"),
                                "reason": "negation_or_neighbor_cannot_verify"})
                continue
        by_cell[r["cell_id"]].append(r)

    policy_hash = hashlib.sha256(_canonical(policy).encode("utf-8")).hexdigest()
    out = {"pack_ref": pack_ref,
           "policy_hash": policy_hash,
           "counts_scope": "observed_in_batch_only_not_market_fact",
           "dropped_records": dropped, "cells": {}}
    for cell in policy["cells"]:
        cid = cell["cell_id"]
        recs = by_cell.get(cid, [])
        comps = _components(recs) if recs else []
        materials = len(comps)
        # independent diner voice: flag alone is insufficient. Must be a crowd_diner
        # with an admission status on the policy allowlist AND identity evidence.
        # missing status / brand_new_unrecognized / review / lexical stay unknown.
        independent_posts = 0
        for comp in comps:
            counts_as_diner = False
            for i in comp:
                r = recs[i]
                if r.get("independent_diner") is not True or r.get("role") != "crowd_diner":
                    continue
                if r.get("admission_status") not in diner_allowed:
                    continue
                if r.get("admission_status") in NOT_VERIFIED:
                    continue
                if require_identity and not r.get("identity_evidence_ref"):
                    continue
                counts_as_diner = True
            if counts_as_diner:
                independent_posts += 1
        verified_entities, verified_bands, verified_anchors = set(), set(), set()
        observed_refs = []
        for comp in comps:
            for i in comp:
                r = recs[i]
                if r.get("admission_status") == VERIFIED and r.get("entity_key"):
                    verified_entities.add(r["entity_key"])
                    observed_refs.append({
                        "project_id": r["project_id"], "layer": r["layer"],
                        "record_id": r["record_id"], "version": r["version"],
                        "hash": r["hash"], "entity_key": r["entity_key"]})
                    if r.get("price_tier"):
                        verified_bands.add(r["price_tier"])
                    for a in r.get("anchor_dishes", []) or []:
                        verified_anchors.add(a)
        observed_refs = sorted(observed_refs,
                               key=lambda x: _canonical(x)) if observed_refs else []

        if cell["mapping_status"] == "pending_review":
            state, reason = "unassessed", "no stable 495 node mapping (pending_review)"
        elif recs:
            state, reason = "observed", "materials present in batch"
        elif any(a.get("status") == "failed" for a in attempts.get(cid, [])):
            state, reason = "attempted_failed", "attempts failed and no admissible material"
        elif scope is not None and cid in scope:
            state, reason = "unobserved_in_batch", "batch targeted cell but returned no admissible material"
        else:
            state, reason = "unknown", "no batch coverage and no failed attempt; unknown is NOT zero supply"

        # verified count is null unless an observation actually happened in batch
        if state in NO_ASSERT_STATES:
            counts = {"materials": materials, "independent_posts": independent_posts,
                      "verified_operating_entities": None, "entity_keys": None,
                      "verified_price_bands": None, "observed_refs": None}
        else:
            counts = {"materials": materials, "independent_posts": independent_posts,
                      "verified_operating_entities": len(verified_entities),
                      "entity_keys": sorted(verified_entities),
                      "verified_price_bands": sorted(verified_bands),
                      "observed_refs": observed_refs}

        q = cell.get("target_quota")
        exp = cell.get("expected_supply") or {}
        if q is None:
            quota_eval = {"verdict": "no_quota_basis", "approved": False,
                          "note": "no target quota; cannot judge attainment"}
        elif exp.get("status") == "unknown" or (exp.get("supply_tier") is None
                                                and exp.get("value") is None):
            quota_eval = {"verdict": "unassessed_expected_supply_unknown",
                          "approved": q.get("approved", False),
                          "note": "expected_supply unknown; meeting candidate count does not prove attainment"}
        else:
            gate = _quota_gate(q, verified_entities, verified_bands, verified_anchors)
            if not q.get("approved"):
                quota_eval = {
                    "verdict": "meets_candidate_target" if gate["satisfied"]
                               else "below_candidate_target",
                    "approved": False, "policy_status": q.get("policy_status"),
                    "gate": gate,
                    "note": "candidate engineering target, Owner adoption NOT approved; not a market fact",
                }
            else:
                quota_eval = {"verdict": "met" if gate["satisfied"] else "below",
                              "approved": True, "gate": gate}

        out["cells"][cid] = {
            "status": state, "reason": reason,
            "node_ids": cell["node_ids"], "mapping_status": cell["mapping_status"],
            "counts": counts, "expected_supply_status": exp.get("status"),
            "quota_evaluation": quota_eval,
        }
    # coverage hash binds the entire evaluated coverage (not the hash header itself)
    out["coverage_hash"] = hashlib.sha256(
        _canonical({"pack_ref": pack_ref, "policy_hash": policy_hash,
                    "dropped_records": dropped, "cells": out["cells"]}).encode("utf-8")
    ).hexdigest()
    return out


def _validate_budget(budget):
    if budget is None:
        return
    # bool is a subclass of int in Python; reject it explicitly
    if isinstance(budget, bool) or not isinstance(budget, (int, float)):
        raise ValueError(f"invalid budget type: {type(budget).__name__}")
    if isinstance(budget, float) and math.isnan(budget):
        raise ValueError("invalid budget: NaN")
    if math.isinf(budget):
        raise ValueError("invalid budget: inf")
    if budget < 0:
        raise ValueError(f"invalid budget: negative {budget}")


def _task_id(payload):
    return "task:" + hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()[:16]


def collection_plan(selected_cells, coverage_report, policy, matrix, budget=None,
                    keyword_roots=None, task_limit=100, task_status=PLANNED_STATUS):
    _validate_budget(budget)
    if task_status != PLANNED_STATUS:
        raise ValueError(f"invalid task status: {task_status!r}; only {PLANNED_STATUS} accepted")
    if not isinstance(task_limit, int) or isinstance(task_limit, bool) or task_limit <= 0:
        raise ValueError(f"invalid task_limit: {task_limit!r}")
    if not isinstance(selected_cells, list) or not all(isinstance(c, str) for c in selected_cells):
        raise ValueError("selected_cells must be a list of cell_id strings")
    keyword_roots = keyword_roots or {}
    cov = coverage_report["cells"]
    policy_hash = coverage_report.get("policy_hash") or hashlib.sha256(
        _canonical(policy).encode("utf-8")).hexdigest()
    coverage_hash = coverage_report.get("coverage_hash") or hashlib.sha256(
        _canonical(coverage_report["cells"]).encode("utf-8")).hexdigest()
    matrix_hash = hashlib.sha256(_canonical(matrix).encode("utf-8")).hexdigest()
    cell_by_id = {c["cell_id"]: c for c in policy["cells"]}
    rows_by_cell = defaultdict(list)
    for row in matrix["rows"]:
        rows_by_cell[row["cell_id"]].append(row)

    blockers, tasks, reasons, candidates = [], [], [], []
    for cid in selected_cells:
        cell = cell_by_id.get(cid)
        if cell is None:
            blockers.append({"cell_id": cid, "reason": "unknown_cell_id"})
            continue
        if cell["mapping_status"] == "pending_review":
            blockers.append({"cell_id": cid, "reason": "blocked_pending_review"})
            continue
        # any partial mapping (partial_pending / partial_mapping) is NOT auto-planned
        if "partial" in cell["mapping_status"]:
            blockers.append({"cell_id": cid, "reason": "blocked_partial_mapping"})
            continue
        q = cell.get("target_quota")
        if q is None:
            blockers.append({"cell_id": cid, "reason": "no_quota_basis"})
            continue
        cov_cell = cov.get(cid, {})
        if cov_cell.get("status") == "unassessed":
            blockers.append({"cell_id": cid, "reason": "coverage_unassessed"})
            continue
        counts = cov_cell.get("counts", {})
        observed = counts.get("verified_operating_entities")
        observed_refs = counts.get("observed_refs")
        # observed is null for unknown/unobserved/attempted-failed states: deficit
        # must stay null too — never convert None into a fabricated 0 deficit.
        if isinstance(observed, int):
            have, deficit = observed, max(0, q["count"] - observed)
            observation_group = 0  # measured deficit drives ranking first
        else:
            have, deficit = None, None
            observation_group = 1  # ranked separately; ranking here is a default
                                   # planning assumption, never a claimed gap
        tier = (cell.get("expected_supply") or {}).get("supply_tier")
        tier_rank = {"scarce": 0, "normal": 1, "abundant": 2}.get(tier, 3)
        for row in rows_by_cell.get(cid, []):
            if row["status"] != "plannable":
                continue
            candidates.append((observation_group, tier_rank, row["budget_weight"],
                               cid, row, cell, q, deficit, have, observed_refs,
                               cov_cell.get("status")))

    candidates.sort(key=lambda x: (x[0], x[1], x[2]))

    spent = 0
    for og, tier_rank, weight, cid, row, cell, q, deficit, have, obs_refs, cov_status in candidates:
        roots = sorted({t for nid in row["node_ids"] for t in keyword_roots.get(nid, [])})
        request = {
            "cell_id": cid, "city": cell["city"], "node_ids": row["node_ids"],
            "crossfacet_price": row.get("crossfacet_price"),
            "source_type": row["source_type"],
            "target_fields": row["target_fields"],
            "evidence_required": row["evidence_required"],
            "stop_conditions": row["stop_conditions"],
            "roots": roots,
        }
        # task_id binds full content (pack/policy/matrix/coverage hashes), exact
        # observed refs, and all budget/request parameters.
        payload = {
            "pack_ref": coverage_report["pack_ref"],
            "policy_hash": policy_hash, "matrix_hash": matrix_hash,
            "coverage_hash": coverage_hash,
            "observed_refs": obs_refs,
            "request": request,
            "quota_basis": q["basis"],
            "budget_cap": budget, "budget_weight": weight,
        }
        tid = _task_id(payload)
        task = {
            "task_id": tid,
            "status": PLANNED_STATUS,
            "pack_ref": coverage_report["pack_ref"],
            "policy_hash": policy_hash, "matrix_hash": matrix_hash,
            "coverage_hash": coverage_hash,
            "cell_id": cid, "city": cell["city"], "node_ids": row["node_ids"],
            "crossfacet_price": row.get("crossfacet_price"),
            "source_type": row["source_type"],
            "query": {"roots": roots, "city": cell["city"], "node_ids": row["node_ids"],
                      "note": "roots resolved from pack keyword_roots; never hardcoded in planner"},
            "target_fields": row["target_fields"],
            "evidence_required": row["evidence_required"],
            "quota_basis": q["basis"],
            "candidate_pool": q["count"] * q.get("candidate_pool_multiplier", 1),
            "coverage_status": cov_status,
            "verified_entities_observed": have,
            "deficit": deficit,
            "ranking_assumption": "measured_deficit" if og == 0 else
                                  "observation_unknown_deficit_null_not_zero",
            "observed_refs": obs_refs,
            "stop_conditions": row["stop_conditions"],
            "budget_weight": weight,
            "budget": None if budget is None else {"cap": budget, "cost_units": weight},
        }
        if budget is not None and spent + weight > budget:
            reasons.append({"cell_id": cid, "source_type": row["source_type"],
                            "reason": "budget_exhausted", "would_cost": weight, "spent": spent})
            continue
        if len(tasks) >= task_limit:
            reasons.append({"cell_id": cid, "source_type": row["source_type"],
                            "reason": "task_limit_reached", "limit": task_limit})
            continue
        if budget is not None:
            spent += weight
        tasks.append(task)

    ids = [t["task_id"] for t in tasks]
    assert len(ids) == len(set(ids)), "duplicate task_id generated"
    truncated = len(candidates) != len(tasks) or budget is not None
    return {
        "pack_ref": coverage_report["pack_ref"],
        "policy_hash": policy_hash, "matrix_hash": matrix_hash,
        "coverage_hash": coverage_hash,
        "total": len(tasks), "truncated": truncated,
        "reasons": reasons, "blockers": blockers,
        "budget": {"cap": budget, "spent": spent if budget is not None else None},
        "tasks": tasks,
    }
