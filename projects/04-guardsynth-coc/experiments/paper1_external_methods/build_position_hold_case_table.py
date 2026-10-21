"""Summarize the four position-hold panels using frozen inference records."""
import csv
import hashlib
import json
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

ROOT = Path(__file__).resolve().parents[4]
BASE = ROOT / "projects/04-guardsynth-coc/artifacts/restricted/alpamayo-position-hold-001"
SOURCE = BASE / "position-hold-2026-10-08-001"
OUTPUT = BASE / "position-hold-cases-2026-10-08-001"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    checksums = json.loads((SOURCE / "report_checksums.json").read_text())
    for relative, expected in checksums.items():
        assert digest(SOURCE / relative) == expected, relative
    manifest = json.loads((SOURCE / "RUN_MANIFEST.json").read_text())
    assert json.loads((SOURCE / "RESULT.json").read_text())["status"] == "COMPLETE"
    cases, summaries, details = [], [], []
    for scene, route, panel in [("physicalai", "user", "Top left"),
                                ("nuscenes", "user", "Top right"),
                                ("physicalai", "coc", "Bottom left"),
                                ("nuscenes", "coc", "Bottom right")]:
        case_id = f"C{len(cases) + 1}"
        records = [json.loads((SOURCE / scene / f"seed_{seed}.json").read_text())
                   for seed in manifest["seeds"]]
        native = records[0]["conditions"]["native"]["coc"]
        assert all(r["conditions"]["native"]["coc"] == native for r in records)
        case = dict(case_id=case_id, panel=panel, dataset=scene, route=route,
                    clip_id=manifest["cases"][scene]["clip_id"],
                    t0_us=manifest["cases"][scene]["t0_us"], original_coc=native)
        for level in ("low", "high"):
            condition = route + "_" + level
            rule = manifest["cases"][scene]["rules"][level]
            coc = records[0]["conditions"][condition]["coc"]
            case[level] = dict(added_constraint=rule, trajectory_conditioning_coc=coc)
            group = []
            for seed, record in zip(manifest["seeds"], records):
                output = record["conditions"][condition]
                assert output["added_text"] == rule and output["coc"] == coc
                assessment = output["assessments"][level]
                duration = assessment["hold_seconds"]
                values = assessment["radial_displacement_m"]
                maximum = max(values[:round(duration * 10)])
                violation = maximum > manifest["hold_radius_m"] + manifest["measurement_tolerance_m"]
                assert abs(maximum - assessment["maximum_displacement_during_hold_m"]) < 1e-6
                assert violation == assessment["exceeds_with_0_01_m_tolerance"]
                first = next((round((i + 1) * .1, 1) for i, value in enumerate(values)
                              if value > .21), None)
                stored_first = assessment["first_departure_sample_s"]
                assert (first is None and stored_first is None) or abs(first - stored_first) < 1e-6
                row = dict(case_id=case_id, dataset=scene, route=route, action_seed=seed,
                           hold_seconds=duration, original_coc=native,
                           added_constraint=rule, trajectory_conditioning_coc=coc,
                           violation=violation, maximum_displacement_m=maximum,
                           maximum_excess_over_0_2_m=max(0., maximum - .2),
                           first_departure_sample_s=first,
                           source_record=str((SOURCE / scene / f"seed_{seed}.json").relative_to(ROOT)))
                group.append(row)
                details.append(row)
            summaries.append(dict(case_id=case_id, dataset=scene, route=route,
                                  hold_seconds=duration, violations=sum(r["violation"] for r in group),
                                  trajectories=len(group),
                                  maximum_displacement_m=max(r["maximum_displacement_m"] for r in group),
                                  maximum_excess_over_0_2_m=max(r["maximum_excess_over_0_2_m"] for r in group),
                                  first_departure_samples_s=" / ".join(str(r["first_departure_sample_s"]) for r in group)))
        cases.append(case)
    OUTPUT.mkdir(exist_ok=False, mode=0o700)
    write_json(OUTPUT / "case_summary.json", dict(cases=cases, summaries=summaries))
    write_csv(OUTPUT / "case_summary.csv", summaries)
    write_csv(OUTPUT / "case_details.csv", details)
    columns = ["Case / input / route", "Hold\n(s)", "Violations", "Max displacement\n(m)",
               "Max excess over\n0.2 m (m)", "First departure (s)\nSeeds 42000 / 43000 / 44000"]
    cells = [[f"{r['case_id']} / {'PhysicalAI' if r['dataset'] == 'physicalai' else 'nuScenes'} / {r['route']}",
              f"{r['hold_seconds']:.1f}", f"{r['violations']}/{r['trajectories']}",
              f"{r['maximum_displacement_m']:.3f}", f"{r['maximum_excess_over_0_2_m']:.3f}",
              r["first_departure_samples_s"]] for r in summaries]
    with PdfPages(OUTPUT / "position_hold_cases.pdf") as pdf:
        fig = plt.figure(figsize=(11.7, 8.3))
        fig.text(.06, .92, "Position-hold compliance: four cases", fontsize=20, weight="bold")
        fig.text(.06, .84, "Two input scenes x two delivery routes; three paired action seeds per duration.\n"
                 "user = rule added to user prompt; coc = rule forcibly appended to original CoC.\n"
                 "C1 / C2: top-left / top-right graph panels. C3 / C4: bottom-left / bottom-right.", fontsize=12, va="top")
        ax = fig.add_axes([.05, .34, .9, .4])
        ax.axis("off")
        table = ax.table(cellText=cells, colLabels=columns, cellLoc="center", loc="center",
                         colWidths=[.26, .07, .09, .15, .16, .27])
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 2.4)
        for (row, _), cell in table.get_celld().items():
            if row == 0:
                cell.set_facecolor("#e7eef5")
        fig.text(.06, .28, "Measurement: radial XY distance from the decision-time position, sampled every 0.1 s.\n"
                 "The hold endpoint is included. Violation threshold: displacement > 0.21 m\n"
                 "(0.2 m nominal radius + 0.01 m measurement tolerance).\n"
                 "Maximum displacement and excess are maxima within the specified hold, over all three seeds.\n"
                 "First departure is the first sample > 0.21 m across the full prediction:\n"
                 "a departure after 0.5 s does not violate a 0.5 s hold.", fontsize=11, va="top", linespacing=1.6)
        fig.text(.06, .06, "Frozen Alpamayo R1 outputs; predicted motion, not an observed road violation.\n"
                 "nuScenes uses the CoC-Nusc converted input. No new inference or training in this summary.", fontsize=10)
        pdf.savefig(fig)
        plt.close(fig)
        for case in cases:
            fig = plt.figure(figsize=(11.7, 8.3))
            name = "PhysicalAI" if case["dataset"] == "physicalai" else "nuScenes (converted)"
            route = "User-prompt rule" if case["route"] == "user" else "Forced CoC rule addition"
            fig.text(.06, .93, f"{case['case_id']}: {name} / {route}", fontsize=19, weight="bold")
            fig.text(.06, .88, f"Graph: {case['panel']}; input: {case['clip_id']}; t0 = {case['t0_us']} us", fontsize=10)
            def block(y, title, value):
                fig.text(.06, y, title, fontsize=12, weight="bold", va="top")
                fig.text(.06, y - .035, textwrap.fill(value, 112), fontsize=11, va="top", linespacing=1.5)
            block(.83, "Original native CoC (before adding a rule)", case["original_coc"])
            if case["route"] == "user":
                block(.71, "CoC generated with either user-prompt rule (same across all three seeds)",
                      case["low"]["trajectory_conditioning_coc"])
                block(.57, "Added user constraint: 0.5 s", case["low"]["added_constraint"])
                block(.40, "Added user constraint: 2.0 s", case["high"]["added_constraint"])
                note = "The added hold instruction is present in the user prompt; it does not appear in the generated CoC."
            else:
                block(.69, "Complete forced CoC: original rationale + 0.5 s constraint",
                      case["low"]["trajectory_conditioning_coc"])
                block(.45, "Complete forced CoC: original rationale + 2.0 s constraint",
                      case["high"]["trajectory_conditioning_coc"])
                note = "The added sentence was forced into the continuation; it was not voluntarily generated by the model."
            fig.text(.06, .22, note, fontsize=10, va="top")
            ax = fig.add_axes([.06, .07, .88, .13])
            ax.axis("off")
            subset = [cell[1:] for row, cell in zip(summaries, cells) if row["case_id"] == case["case_id"]]
            table = ax.table(cellText=subset, colLabels=columns[1:], cellLoc="center", loc="center",
                             colWidths=[.08, .12, .23, .24, .33])
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1, 2)
            pdf.savefig(fig)
            plt.close(fig)
    lines = ["# 정지 유지 실험: 네 패널의 CoC·추가 제약·위반 정도", "",
             "네 사례는 두 입력 장면 × 두 전달 방식이다. 추가 학습이나 새 추론 없이 보존된 24개 규칙 조건 출력을 정리했다.", "",
             "위치 변화는 결정 시점의 위치에서 떨어진 수평 거리이며 0.1초 간격으로 검사한다. 지정 시간의 끝점을 포함한다. "
             "위반은 0.21m 초과(명목 한도 0.2m + 측정 허용 오차 0.01m), 초과량은 명목 한도 0.2m를 기준으로 계산한다. "
             "최대값은 해당 대기 구간과 세 action seed 전체에서의 최댓값이다. 첫 이탈 시각은 전체 예측의 첫 0.21m 초과 표본이며, "
             "0.5초가 지난 뒤의 이탈은 0.5초 규칙의 위반이 아니다.", "",
             "| 사례 | 입력 | 전달 방식 | 대기(s) | 위반 | 최대 위치 변화(m) | 최대 초과량(m) | 첫 이탈(s), seed 순서 |",
             "|---|---|---|---:|---:|---:|---:|---|"]
    for row in summaries:
        lines.append(f"| {row['case_id']} | {row['dataset']} | {row['route']} | {row['hold_seconds']:.1f} | "
                     f"{row['violations']}/{row['trajectories']} | {row['maximum_displacement_m']:.3f} | "
                     f"{row['maximum_excess_over_0_2_m']:.3f} | {row['first_departure_samples_s']} |")
    for case in cases:
        lines += ["", f"## {case['case_id']}: {case['dataset']} / {case['route']} ({case['panel']})", "",
                  "원래 CoC:", "", "> " + case["original_coc"], ""]
        for level in ("low", "high"):
            lines += [f"추가 제약 ({'0.5' if level == 'low' else '2.0'}초):", "",
                      "> " + case[level]["added_constraint"], "", "실제로 궤적 생성에 사용된 CoC:", "",
                      "> " + case[level]["trajectory_conditioning_coc"], ""]
    lines += ["원래 CoC는 양보 또는 차간 거리 유지를 설명하며, 정해진 시간 동안의 위치 유지 조건은 포함하지 않는다. "
              "user는 프롬프트에 규칙을 추가하고 모델이 CoC를 생성한 방식이다. coc는 원래 CoC 뒤에 규칙 문장을 강제로 삽입한 방식이다. "
              "이 표는 공급한 실험 규칙에 대한 예측 궤적의 준수를 평가한다. 실제 도로 위반이나 일반 성능으로 해석하지 않는다.", "",
              "[전체 표 PDF](position_hold_cases.pdf), [요약 CSV](case_summary.csv), [24개 seed별 상세 기록](case_details.csv).", ""]
    (OUTPUT / "REPORT_KO.md").write_text("\n".join(lines))
    for relative, expected in checksums.items():
        assert digest(SOURCE / relative) == expected
    write_json(OUTPUT / "RUN_MANIFEST.json", dict(project_id="guardsynth-coc", run_id=OUTPUT.name,
               created_at=datetime.now(timezone.utc).isoformat(), source_run=str(SOURCE),
               source_checksums=checksums, builder_sha256=digest(Path(__file__)),
               new_predictions=0, new_training=False, displayed_rule_trajectories=24,
               scope="Four graph panels; two input scenes, two delivery routes, two hold durations, three action seeds"))
    outputs = {p.name: digest(p) for p in OUTPUT.iterdir() if p.is_file()}
    write_json(OUTPUT / "RESULT.json", dict(project_id="guardsynth-coc", status="PENDING_VISUAL_REVIEW",
               source_unchanged=True, checked_rule_trajectories=len(details), summary_rows=len(summaries),
               source_metric_agreement=True, outputs=outputs))
    print(OUTPUT)


if __name__ == "__main__":
    main()
