"""Reanalyze the unchanged four-rater panel; no new human evaluation."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
from itertools import combinations
import json
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "PROJECT_REGISTRY.json").exists())
OWNER = ROOT / "projects/03-sequential-coc-verification"
FIELDS = ("temporal_requirement_explicit", "required_action_sequence", "textual_consistency")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def coefficients(votes, categories):
    if not votes or len(votes[0]) < 2 or any(len(v) != len(votes[0]) for v in votes):
        raise ValueError("A complete panel with at least two raters is required")
    if len(categories) < 2 or len(set(categories)) != len(categories):
        raise ValueError("At least two distinct nominal categories are required")
    counts = Counter(v for row in votes for v in row)
    if not set(counts) <= set(categories) or any(not v for row in votes for v in row):
        raise ValueError("Unknown or missing category")
    n, r, q = len(votes), len(votes[0]), len(categories)
    pa = sum(sum(c * (c - 1) for c in Counter(row).values()) / (r * (r - 1)) for row in votes) / n
    proportions = {c: counts[c] / (n * r) for c in categories}
    kappa_pe = sum(p * p for p in proportions.values())
    ac1_pe = sum(p * (1 - p) for p in proportions.values()) / (q - 1)
    return {"subjects": n, "raters": r, "ratings": n * r, "category_count": q,
            "category_counts": {c: counts[c] for c in categories}, "category_proportions": proportions,
            "raw_agreement": pa, "fleiss_chance_agreement": kappa_pe,
            "fleiss_kappa": (pa - kappa_pe) / (1 - kappa_pe) if kappa_pe < 1 else None,
            "ac1_chance_agreement": ac1_pe, "gwet_ac1": (pa - ac1_pe) / (1 - ac1_pe),
            "disputed_subjects": sum(len(set(row)) > 1 for row in votes)}


def pairwise_exact_check(votes, categories):
    """Direct rater-pair enumeration and exact rational arithmetic."""
    pairs = [a == b for row in votes for a, b in combinations(row, 2)]
    pa = Fraction(sum(pairs), len(pairs))
    flat = [v for row in votes for v in row]
    probabilities = [Fraction(flat.count(c), len(flat)) for c in categories]
    pe_k = sum(p * p for p in probabilities)
    pe_a = (1 - pe_k) / (len(categories) - 1)
    return {"raw_agreement": float(pa),
            "fleiss_kappa": float((pa - pe_k) / (1 - pe_k)) if pe_k != 1 else None,
            "gwet_ac1": float((pa - pe_a) / (1 - pe_a))}


def run(output):
    review = OWNER / "artifacts/restricted/sequential-coc-consistency-v1/review"
    files = sorted(review.glob("contract_review_[AB](*).csv"))
    panel = []
    for path in files:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        indexed = {row["review_id"]: row for row in rows}
        if len(indexed) != len(rows):
            raise ValueError("Duplicate review ID")
        panel.append(indexed)
    if len(panel) != 4 or any(set(p) != set(panel[0]) for p in panel) or len(panel[0]) != 27:
        raise ValueError("Expected the preserved complete four-rater, 27-subject panel")
    ids = sorted(panel[0])
    categories = {field: sorted({p[rid][field] for p in panel for rid in ids}) for field in FIELDS}
    protocol = {"project_id": "sequential-coc-verification", "subjects": 27, "raters": 4,
                "categories": categories, "weights": "UNWEIGHTED_NOMINAL",
                "category_policy": "Original observed labels, frozen before coefficient calculation; no recoding. Action sequences are exact strings (39 observed categories), not a closed vocabulary.",
                "missing_policy": "Reject blanks; NOT_APPLICABLE and UNKNOWN remain original nominal categories.",
                "formulas": {"fleiss_pe": "sum(p_j^2)", "ac1_pe": "sum(p_j*(1-p_j))/(q-1)", "coefficient": "(P_a-P_e)/(1-P_e)"},
                "sources": ["https://doi.org/10.1348/000711006X126600", "https://github.com/kgwet/irrCAC/blob/master/R/agree.coeff3.raw.r"],
                "new_human_evaluation": False, "population_inference": False}
    output.mkdir(parents=True, exist_ok=False)
    save(output / "protocol.json", protocol)
    manifest = {"project_id": "sequential-coc-verification", "task_id": "reviewer-agreement-reanalysis",
                "status": "PREPARED", "created_at": datetime.now(timezone.utc).isoformat(),
                "source_sha256": digest(Path(__file__)), "protocol_sha256": digest(output / "protocol.json"),
                "inputs": [{"path": str(p.relative_to(ROOT)), "sha256": digest(p)} for p in files]}
    save(output / "RUN_MANIFEST.json", manifest)
    previous = json.loads((OWNER / "artifacts/restricted/kiee-review-revision-001/reanalysis-2026-09-30-001/agreement.json").read_text())
    results = {}
    for field in FIELDS:
        votes = [[p[rid][field] for p in panel] for rid in ids]
        stats = coefficients(votes, categories[field])
        exact = pairwise_exact_check(votes, categories[field])
        for key, value in exact.items():
            assert abs(stats[key] - value) < 1e-12
        assert abs(stats["fleiss_kappa"] - previous[field]["kappa"]) < 1e-12
        assert abs(stats["raw_agreement"] - previous[field]["raw_agreement"]) < 1e-12
        results[field] = stats
    result = {"status": "COMPLETED", "project_id": "sequential-coc-verification", "fields": results,
              "verification": "Existing Fleiss kappa and raw agreement reproduced; AC1 cross-checked by exact rater-pair enumeration and Fraction arithmetic.",
              "new_human_evaluation": False, "labels_changed": False,
              "interpretation": "Chance models differ. AC1 does not repair disagreement, missing qualifications/training/adjudication, or provide natural semantic gold."}
    save(output / "RESULT.json", result)
    labels = dict(zip(FIELDS, ("시간 요구", "행동열", "텍스트 일관성")))
    table = "\n".join(f"| {labels[f]} | {s['category_count']} | {s['raw_agreement']:.6f} | {s['fleiss_chance_agreement']:.6f} | {s['fleiss_kappa']:.6f} | {s['ac1_chance_agreement']:.6f} | {s['gwet_ac1']:.6f} |" for f, s in results.items())
    (output / "REPORT_KO.md").write_text(f"""# 기존 4인×27장면 일치도 재분석

원 CSV를 변경하지 않고 3항목의 관측 범주를 계산 전에 고정했다. 결측은 허용하지 않으며 해당 없음/미상도 원 명목 범주로 유지했다. 행동열은 원 문자열 그대로 39개 관측 범주다. 새 사람 평가나 자연 정답 구축이 아니다.

| 항목 | 범주 q | 쌍별 일치 | κ 우연 일치 | Fleiss κ | AC1 우연 일치 | Gwet AC1 |
|---|---|---|---|---|---|---|
{table}

시간 요구는 YES 81/108, NO 26/108, AMBIGUOUS 1/108이며 우연 일치 모형에 따라 보정 계수가 달라진다. 범주 편중의 영향을 보여 주지만 검토자 자격이나 낮은 일치의 인과적 원인을 확정하지 않는다. 텍스트 일관성은 원시 일치율 0.407407, 불일치 23/27로 낮으며 AC1을 함께 보더라도 실제 판정 불일치는 유지된다. 행동열 AC1은 39개 관측 문자열 범주에 조건부이며 범주 수에 민감한 추가 요약이다. κ를 AC1로 대체하거나 더 큰 계수만 선택하지 않는다.

기존 κ·일치율을 1e-12 이내 재현했고, 전체 평가자 쌍을 직접 열거한 분수 계산으로 AC1을 대조했다. 원 27장면은 비무작위 표본이며 108평가를 독립 자연 표본으로 계산하지 않는다. 검토자 자격·교육·합의 사유의 결손은 이번 통계 재분석으로 복원되지 않는다.

계산 근거: [Gwet (2008)](https://doi.org/10.1348/000711006X126600), [저자의 irrCAC 구현](https://github.com/kgwet/irrCAC/blob/master/R/agree.coeff3.raw.r). 기존 패널의 조건부 기술 통계이며 모집단 신뢰구간·유의성은 제시하지 않는다.
""")
    manifest.update(status="COMPLETED", completed_at=datetime.now(timezone.utc).isoformat(),
                    outputs={name: digest(output / name) for name in ("RESULT.json", "REPORT_KO.md")})
    assert all(digest(ROOT / row["path"]) == row["sha256"] for row in manifest["inputs"])
    save(output / "RUN_MANIFEST.json", manifest)
    print(json.dumps({f: {k: v[k] for k in ("raw_agreement", "fleiss_kappa", "gwet_ac1")} for f, v in results.items()}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    import re
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*-\d{3}", args.run_id):
        parser.error("run-id must use lowercase kebab-case and a three-digit suffix")
    run(OWNER / "artifacts/restricted/kiee-review-revision-001" / args.run_id)
