#!/usr/bin/env python3
# M4-SUPPLY-COVERAGE-02 R2 fixed regression runner (oracle v2).
# - Every expected field is read from regression_set.coverage.v2.json and compared
#   exactly; any missing/extra/mismatched key FAILs.
# - Fixtures are built once; oracle expectations are never derived from output.
# - Exit code is non-zero when any case fails (R1 exited 0 despite 3 fails).
# - v1 oracle (regression_set.coverage.json) and v1 failure evidence are frozen.
import copy, json, math, os, sys
from coverage_planner import coverage, collection_plan

HERE = os.path.dirname(os.path.abspath(__file__))
policy = json.load(open(os.path.join(HERE, "supply_policy.candidate.json")))
matrix = json.load(open(os.path.join(HERE, "source_plan_matrix.json")))
SPEC = json.load(open(os.path.join(HERE, "regression_set.coverage.v2.json")))
EXPECT = {c["id"]: c["expect"] for c in SPEC["cases"]}
BASIS = {c["id"]: c.get("basis", "") for c in SPEC["cases"]}

PACK = {"name": "food-tree", "version": "1.1.0",
        "hash": "2d7a034e36e629519f47574031be499719b126d1deace1bc048f97d2531faab0"}
PACK_ALT = {"name": "food-tree", "version": "1.0.0",
            "hash": "f94de00fcb1d746f69a8ea96a897df21d36b2ad3418d02cf3e48b05dc33a4955"}

def rec(i, cell, **kw):
    # ODS main exact-ref: integer version. RAW source_refs (if any) carry no version.
    r = {"record_id": f"raw:case-{i:03d}", "project_id": "proj-food",
         "layer": "DW", "version": 1, "hash": f"h{i:03d}", "cell_id": cell}
    r.update(kw)
    return r

def cov(records, attempts=None, scope=None, pack=PACK, pol=policy):
    return coverage(pack, records, attempts or {}, pol, batch_scope=scope)

def counts_of(report, cell):
    return report["cells"][cell]["counts"]


def fz_records(anchor, bands=("value", "mid", "high")):
    out = []
    for i, band in enumerate(bands, start=1):
        kw = {"url": f"fz{i}", "role": "independent_reviewer",
              "admission_status": "verified_merchant", "entity_key": f"fz{i}",
              "price_tier": band}
        if anchor:
            kw["anchor_dishes"] = ["佛跳墙"]
        out.append(rec(100 + i, "min_fuzhou", **kw))
    return out


def build(cid):
    if cid == "C01_dedup_same_url":
        r = cov([rec(1, "yueA_cantonese_meal", url="u1", content_hash="h1", role="crowd_diner",
                     independent_diner=True, admission_status="crowd_diner"),
                 rec(2, "yueA_cantonese_meal", url="u1", content_hash="h1", role="crowd_diner",
                     independent_diner=True, admission_status="crowd_diner")])
        c = counts_of(r, "yueA_cantonese_meal")
        return {k: c[k] for k in ("materials", "independent_posts", "verified_operating_entities")}

    if cid == "C02_dedup_same_content_hash":
        r = cov([rec(1, "yueA_shunde", url="uA", content_hash="same", role="crowd_diner",
                     independent_diner=True, admission_status="crowd_diner"),
                 rec(2, "yueA_shunde", url="uB", content_hash="same", role="crowd_diner",
                     independent_diner=True, admission_status="crowd_diner")])
        c = counts_of(r, "yueA_shunde")
        return {k: c[k] for k in ("materials", "independent_posts")}

    if cid == "C03_roles_not_mixed":
        r = cov([rec(1, "yueA_hakka", url="u1", role="crowd_diner", admission_status="m2_review"),
                 rec(2, "yueA_hakka", url="u2", role="crowd_diner", admission_status="lexical_match"),
                 rec(3, "yueA_hakka", url="u3", role="operator", admission_status="ocr_low_confidence")])
        c = counts_of(r, "yueA_hakka")
        return {k: c[k] for k in ("materials", "independent_posts", "verified_operating_entities")}

    if cid == "C04_unknown_not_zero":
        r = cov([])
        cell = r["cells"]["yueA_cantonese_meal"]
        return {"status": cell["status"],
                "verified_operating_entities": cell["counts"]["verified_operating_entities"],
                "quota_verdict": cell["quota_evaluation"]["verdict"]}

    if cid == "C05_negation_neighbor":
        r = cov([rec(1, "yueA_cantonese_meal", url="u1", role="crowd_diner",
                     admission_status="verified_merchant", entity_key="e1", is_negation=True),
                 rec(2, "yueA_cantonese_meal", url="u2", role="crowd_diner",
                     admission_status="verified_merchant", entity_key="e2", is_neighbor_mention=True)])
        cell = r["cells"]["yueA_cantonese_meal"]
        reasons = [d["reason"] for d in r["dropped_records"]]
        return {"status": cell["status"],
                "verified_operating_entities": cell["counts"]["verified_operating_entities"],
                "dropped_count": len(reasons),
                "dropped_reason": reasons[0] if reasons else None}

    if cid == "C06_cross_domain_rejected":
        r = cov([rec(1, "software_release_node", url="u1", role="official",
                     admission_status="verified_merchant", entity_key="s1")])
        reasons = [d["reason"] for d in r["dropped_records"]]
        return {"dropped_reason": reasons[0] if reasons else None}

    if cid == "C07_ocr_low_confidence":
        r = cov([rec(1, "yueA_congee_noodle_rice", url="u1", role="crowd_diner",
                     admission_status="ocr_low_confidence")])
        cell = r["cells"]["yueA_congee_noodle_rice"]
        return {"status": cell["status"], "materials": cell["counts"]["materials"],
                "verified_operating_entities": cell["counts"]["verified_operating_entities"]}

    if cid == "C08_quota_no_basis_refused":
        r = cov([])
        plan = collection_plan(["cat_market_stall"], r, policy, matrix, budget=None)
        bl = [b["reason"] for b in plan["blockers"]]
        return {"plan_blocker": bl[0] if bl else None, "total": plan["total"]}

    if cid == "C09_pinned_pack_version":
        r = cov([])
        a = collection_plan(["yueA_cantonese_meal"], r, policy, matrix, budget=100)
        b = collection_plan(["yueA_cantonese_meal"], r, policy, matrix, budget=100)
        r2 = cov([], pack=PACK_ALT)
        c = collection_plan(["yueA_cantonese_meal"], r2, policy, matrix, budget=100)
        return {"same": [t["task_id"] for t in a["tasks"]] ==
                         [t["task_id"] for t in b["tasks"]],
                "different": [t["task_id"] for t in a["tasks"]] !=
                             [t["task_id"] for t in c["tasks"]]}

    if cid == "C10_quota_keeps_material_count":
        r = cov([rec(i, "yueA_hakka", url=f"u{i}", role="crowd_diner",
                     admission_status="m2_review") for i in range(1, 5)] +
                [rec(5, "yueA_hakka", url="u5", role="independent_reviewer",
                     admission_status="verified_merchant", entity_key="e1")])
        cell = r["cells"]["yueA_hakka"]
        return {"materials": cell["counts"]["materials"],
                "verified_operating_entities": cell["counts"]["verified_operating_entities"],
                "status": cell["status"]}

    if cid == "C11_candidate_target_never_approved":
        r = cov([rec(i, "yueA_cantonese_meal", url=f"u{i}", role="independent_reviewer",
                     admission_status="verified_merchant", entity_key=f"e{i}") for i in range(1, 6)])
        qe = r["cells"]["yueA_cantonese_meal"]["quota_evaluation"]
        return {"quota_verdict": qe["verdict"], "approved": qe["approved"]}

    if cid == "C12_minbei_no_node":
        cellp = next(c for c in policy["cells"] if c["cell_id"] == "min_minbei")
        r = cov([])
        plan = collection_plan(["min_minbei"], r, policy, matrix, budget=100)
        bl = [b["reason"] for b in plan["blockers"]]
        return {"mapping": cellp["mapping_status"],
                "status": r["cells"]["min_minbei"]["status"],
                "blocker": bl[0] if bl else None}

    if cid == "C13_fuzhou_three_bands_anchor":
        q = next(c for c in policy["cells"] if c["cell_id"] == "min_fuzhou")["target_quota"]
        return {"count": q["count"], "bands": q["required_price_bands"],
                "anchor": q["anchor_dish"]}

    if cid == "C14_idempotent_plan":
        r = cov([])
        a = collection_plan(["yueA_cantonese_meal", "yueA_shunde"], r, policy, matrix, budget=100)
        b = collection_plan(["yueA_cantonese_meal", "yueA_shunde"], r, policy, matrix, budget=100)
        return {"idempotent":
                json.dumps(a["tasks"], sort_keys=True) == json.dumps(b["tasks"], sort_keys=True)}

    if cid == "C15_no_budget_still_planned":
        r = cov([])
        plan = collection_plan(["yueA_cantonese_meal"], r, policy, matrix, budget=None)
        return {"total_positive": plan["total"] > 0,
                "all_status": sorted({t["status"] for t in plan["tasks"]})[0]
                               if plan["tasks"] else None,
                "budget_cap": plan["budget"]["cap"]}

    if cid == "C16_budget_truncates":
        r = cov([])
        plan = collection_plan(["yueA_cantonese_meal", "yueA_hakka", "yueA_shunde"],
                               r, policy, matrix, budget=0)
        reasons = [x["reason"] for x in plan["reasons"]]
        return {"truncated": plan["truncated"],
                "reasons_contains": "budget_exhausted" if "budget_exhausted" in reasons else None}

    if cid == "C17_attempted_failed":
        r = cov([], attempts={"yueA_dim_sum": [{"source_type": "ugc_community", "status": "failed"}]})
        return {"status": r["cells"]["yueA_dim_sum"]["status"]}

    if cid == "C18_diner_missing_admission":
        r = cov([rec(1, "yueA_hakka", url="u1", role="crowd_diner", independent_diner=True)])
        return {"independent_posts": counts_of(r, "yueA_hakka")["independent_posts"]}

    if cid == "C19_diner_brand_new_unrecognized":
        r = cov([rec(1, "yueA_hakka", url="u1", role="crowd_diner", independent_diner=True,
                     admission_status="brand_new_unrecognized")])
        return {"independent_posts": counts_of(r, "yueA_hakka")["independent_posts"]}

    if cid == "C20_diner_verified_with_identity":
        r = cov([rec(1, "yueA_hakka", url="u1", role="crowd_diner", independent_diner=True,
                     admission_status="verified_independent_diner", identity_evidence_ref="id:1"),
                 rec(2, "yueA_hakka", url="u2", role="independent_reviewer",
                     admission_status="verified_merchant", entity_key="e1")])
        c = counts_of(r, "yueA_hakka")
        return {"independent_posts": c["independent_posts"],
                "verified_operating_entities": c["verified_operating_entities"]}

    if cid == "C21_partial_mapping_blocked":
        r = cov([])
        plan = collection_plan(["yueA_dim_sum"], r, policy, matrix, budget=100)
        bl = [x["reason"] for x in plan["blockers"]]
        return {"blocker": bl[0] if bl else None}

    if cid == "C22_fuzhou_no_anchor_below":
        g = cov(fz_records(False))["cells"]["min_fuzhou"]["quota_evaluation"]
        return {"verdict": g["verdict"], "missing_anchor": g["gate"]["missing_anchor"]}

    if cid == "C23_fuzhou_anchor_met":
        g = cov(fz_records(True))["cells"]["min_fuzhou"]["quota_evaluation"]
        return {"verdict": g["verdict"]}

    if cid == "C24_minnan_single_band_below":
        r = cov([rec(200 + i, "min_minnan", url=f"mn{i}", role="independent_reviewer",
                     admission_status="verified_merchant", entity_key=f"mn{i}",
                     price_tier="mid") for i in range(1, 6)])
        g = r["cells"]["min_minnan"]["quota_evaluation"]
        return {"verdict": g["verdict"], "bands_ok": g["gate"]["bands_ok"]}

    if cid == "C25_approved_gate_full":
        pol_ok = copy.deepcopy(policy)
        next(c for c in pol_ok["cells"] if c["cell_id"] == "min_fuzhou")["target_quota"]["approved"] = True
        v_ok = cov(fz_records(True), pol=pol_ok)["cells"]["min_fuzhou"]["quota_evaluation"]["verdict"]
        v_bad = cov(fz_records(False), pol=copy.deepcopy(pol_ok))["cells"]["min_fuzhou"]["quota_evaluation"]["verdict"]
        return {"satisfied": v_ok, "unsatisfied": v_bad}

    if cid == "C26_quote_status_not_verbatim":
        unknown_n = excerpt_n = 0
        shas_ok = True
        for c in policy["cells"]:
            for key in ("expected_supply", "target_quota", "observed_historical"):
                b = (c.get(key) or {}).get("basis") if isinstance(c.get(key), dict) else None
                if b:
                    shas_ok = shas_ok and bool(b.get("source_sha256"))
                    unknown_n += b.get("quote_status") == "unknown"
                    excerpt_n += b.get("quote_status") == "excerpt"
        return {"placeholder": "unknown" if unknown_n >= 1 else None,
                "ellipsis": "excerpt" if excerpt_n >= 1 else None,
                "source_sha_kept": shas_ok}

    if cid == "C27_unobserved_deficit_null":
        r = cov([], scope=["min_fuzhou"])
        plan = collection_plan(["min_fuzhou"], r, policy, matrix, budget=100)
        t = next(t for t in plan["tasks"] if t["cell_id"] == "min_fuzhou")
        return {"verified_entities_observed": t["verified_entities_observed"],
                "deficit": t["deficit"]}

    if cid == "C28_unknown_verified_null":
        r = cov([])
        cell = r["cells"]["yueA_shunde"]
        return {"status": cell["status"],
                "verified_operating_entities": cell["counts"]["verified_operating_entities"]}

    if cid == "C29_unknown_plan_deficit_null":
        r = cov([])
        plan = collection_plan(["min_fuzhou"], r, policy, matrix, budget=100)
        t = next(t for t in plan["tasks"] if t["cell_id"] == "min_fuzhou")
        return {"verified_entities_observed": t["verified_entities_observed"],
                "deficit": t["deficit"], "coverage_status": t["coverage_status"],
                "ranking_assumption": t["ranking_assumption"]}

    if cid == "C30_bands_and_constraint":
        pol = copy.deepcopy(policy)
        q = next(c for c in pol["cells"] if c["cell_id"] == "min_fuzhou")["target_quota"]
        q["count"] = 3
        q["required_price_bands"] = ["value"]
        q["price_band_min_count"] = 2
        q["anchor_dish"] = "佛跳墙"
        # 3 entities all value band, all with anchor: required bands pass but min
        # band count fails, so the AND gate must still be below.
        g = cov(fz_records(True, bands=("value", "value", "value")), pol=pol)
        g = g["cells"]["min_fuzhou"]["quota_evaluation"]
        return {"verdict": g["verdict"], "bands_ok": g["gate"]["bands_ok"],
                "required_bands_ok": g["gate"]["required_bands_ok"],
                "min_bands_ok": g["gate"]["min_bands_ok"]}

    if cid == "C31_task_hashes_and_refs":
        def first_task(records, scope=None):
            r = cov(records, scope=scope)
            plan = collection_plan(["min_fuzhou"], r, policy, matrix, budget=100)
            return r, next(t for t in plan["tasks"] if t["cell_id"] == "min_fuzhou")
        r_empty, t_empty = first_task([], scope=["min_fuzhou"])
        r_three, t_three = first_task(fz_records(True))
        hashes = [t_three["policy_hash"], t_three["matrix_hash"], t_three["coverage_hash"]]
        return {"hashes_present": all(isinstance(h, str) and len(h) == 64 for h in hashes)
                              and r_three["policy_hash"] == t_three["policy_hash"]
                              and r_three["coverage_hash"] == t_three["coverage_hash"],
                "empty_vs_three_isolated": t_empty["task_id"] != t_three["task_id"],
                "observed_refs_count": len(t_three["observed_refs"] or [])}

    if cid == "C32_invalid_request_rejected":
        r = cov([])
        def raises(budget=None, status=None, limit=100):
            try:
                collection_plan(["yueA_cantonese_meal"], r, policy, matrix,
                                budget=budget,
                                task_status=status if status else "PLANNED_NOT_SUBMITTED",
                                task_limit=limit)
                return False
            except ValueError:
                return True
        return {"rejects_bool_budget": raises(budget=True),
                "rejects_nan_budget": raises(budget=float("nan")),
                "rejects_negative_budget": raises(budget=-1),
                "rejects_string_budget": raises(budget="100"),
                "rejects_unknown_status": raises(status="SUBMITTED"),
                "rejects_bad_task_limit": raises(limit=0)}

    if cid == "C33_idempotent_isolated":
        r = cov([])
        a = collection_plan(["min_fuzhou"], r, policy, matrix, budget=100)
        b = collection_plan(["min_fuzhou"], r, policy, matrix, budget=100)
        ids_a = [t["task_id"] for t in a["tasks"]]
        ids_b = [t["task_id"] for t in b["tasks"]]
        r2 = cov(fz_records(True))
        c = collection_plan(["min_fuzhou"], r2, policy, matrix, budget=100)
        ids_c = [t["task_id"] for t in c["tasks"]]
        return {"same_input_same_ids": ids_a == ids_b,
                "different_input_isolated": ids_a != ids_c}

    if cid == "C34_oracle_negative_control":
        ok_real, _ = compare(EXPECT["C23_fuzhou_anchor_met"], build("C23_fuzhou_anchor_met"))
        mutated = copy.deepcopy(EXPECT["C23_fuzhou_anchor_met"])
        mutated["verdict"] = "below_candidate_target"
        ok_mut, _ = compare(mutated, build("C23_fuzhou_anchor_met"))
        return {"mutated_expectation_fails": ok_real and not ok_mut}

    if cid == "C35_invalid_attempt_rejected":
        try:
            cov([], attempts={"min_fuzhou": [{"status": "some_unknown_status"}]})
            rejected = False
        except ValueError:
            rejected = True
        return {"invalid_attempt_rejected": rejected}

    if cid == "C36_ods_raw_ref_contract":
        good = rec(1, "min_fuzhou", url="u1", role="official",
                   admission_status="verified_merchant", entity_key="e1",
                   source_refs=[{"project_id": "proj-food", "layer": "RAW",
                                 "record_id": "raw:1", "hash": "rh1"}])
        r_good = cov([good])
        raw_ok = not any(d["reason"] == "malformed_raw_source_refs" for d in r_good["dropped_records"])
        bad = rec(2, "min_fuzhou", url="u2", role="official",
                  admission_status="verified_merchant", entity_key="e2")
        bad["version"] = "v1"
        r_bad = cov([bad])
        bad_dropped = any(d["reason"] == "missing_or_invalid_ods_exact_ref"
                          for d in r_bad["dropped_records"])
        return {"raw_sourcerefs_versionless_ok": raw_ok,
                "ods_noninteger_version_dropped": bad_dropped}

    raise KeyError(cid)


def compare(expect, actual):
    """Exact comparison: same key set, same values. Missing keys FAIL."""
    if not isinstance(actual, dict):
        return False, [f"actual not an object: {actual!r}"]
    diffs = []
    for k in expect:
        if k not in actual:
            diffs.append(f"missing actual key {k}")
        elif actual[k] != expect[k]:
            diffs.append(f"{k}: expect={expect[k]!r} actual={actual[k]!r}")
    for k in actual:
        if k not in expect:
            diffs.append(f"unexpected actual key {k}={actual[k]!r}")
    return not diffs, diffs


results = []
for cid in EXPECT:
    try:
        actual = build(cid)
        ok, diffs = compare(EXPECT[cid], actual)
    except Exception as e:  # a crash is a FAIL, never a silent skip
        actual, ok, diffs = {"exception": repr(e)}, False, [f"exception: {e!r}"]
    results.append({"case": cid, "pass": ok, "expect": EXPECT[cid], "got": actual,
                    "diffs": diffs, "basis": BASIS.get(cid, "")})

passed = sum(1 for x in results if x["pass"])
total = len(results)
fails = [x["case"] for x in results if not x["pass"]]
report = {"oracle_version": "v2", "summary": f"{passed}/{total} passed",
          "failures": fails,
          "note": "v2 frozen oracle. v1 oracle and v1 failures preserved unchanged.",
          "results": results}
json.dump(report, open(os.path.join(HERE, "regression_results.json"), "w"),
          ensure_ascii=False, indent=2)
for x in results:
    print(("PASS" if x["pass"] else "FAIL"), x["case"],
          "" if x["pass"] else f"diffs={x['diffs']}")
print(f"\n{passed}/{total} passed; failures={fails}")
sys.exit(0 if passed == total else 1)
