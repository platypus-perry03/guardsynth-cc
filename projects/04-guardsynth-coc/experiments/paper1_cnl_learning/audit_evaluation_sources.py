"""Inventory evaluation inputs and frozen adapters without promoting raw video to gold."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
WORKTREE = ROOT.parent / 'guardsynth-cc-worktrees/guardsynth-additional-20260930'
EXPERIMENT = Path('projects/04-guardsynth-coc/artifacts/public/paper1-method-preservation-001')


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def audit(output):
    if output.exists():
        raise FileExistsError(output)
    videos = []
    for cohort in ('m16-shortlist-v1', 'm16-reserve-v1'):
        base = ROOT / 'data/restricted/nvidia_physicalai/internal-derived' / cohort
        records = json.loads((base / 'MANIFEST.json').read_text())['records']
        events = {row['relative_path'].split('/')[0]: row for row in records}
        for video in sorted(base.glob('event-*/camera_front_wide_120fov/video.mp4')):
            event = video.parent.parent
            metadata = events[event.name]
            sidecars = {name: str(event / name) for name in (
                'egomotion_offline/egomotion_offline.parquet',
                'obstacle_offline/obstacle_offline.parquet',
                'camera_front_wide_120fov/frame_timestamps.parquet') if (event / name).is_file()}
            videos.append({'source': 'PhysicalAI', 'cohort': cohort, 'event_id': event.name,
                           'clip_id': metadata['clip_id'], 'decision_timestamp_us': metadata['event_timestamp_us'],
                           'source_slice': metadata.get('shortlist_slice'),
                           'path': str(video), 'bytes': video.stat().st_size,
                           'available_sidecars': sidecars,
                           'six_task_reference_status': 'NOT_ESTABLISHED_BY_FILE_AVAILABILITY'})
    base = ROOT / 'projects/04-guardsynth-coc/artifacts/restricted/guardsynth-studio-001'
    for run in sorted(base.glob('nuscenes-*')):
        for video in sorted(run.glob('scene*front.mp4')):
            videos.append({'source': 'nuScenes', 'event_id': video.stem, 'path': str(video),
                           'bytes': video.stat().st_size,
                           'six_task_reference_status': 'NOT_ESTABLISHED_BY_FILE_AVAILABILITY'})
    roots = {'temporal': ROOT / EXPERIMENT / 'temporal-expansion-learning-2026-09-29-001',
             'static': WORKTREE / EXPERIMENT / 'static-contract-learning-2026-09-30-001',
             'maneuver': WORKTREE / EXPERIMENT / 'maneuver-contract-learning-2026-09-30-001'}
    checkpoints = []
    for task, base in roots.items():
        for seed in (42, 17, 123):
            for arm in ('P0', 'P1', 'P2'):
                path = base / f'{arm.lower()}-seed{seed}/adapter/adapter_model.safetensors'
                if not path.is_file():
                    raise FileNotFoundError(path)
                checkpoints.append({'task': task, 'arm': arm, 'seed': seed, 'path': str(path),
                                    'sha256': sha(path), 'config_sha256': sha(path.with_name('adapter_config.json'))})
    previous = ROOT / 'projects/04-guardsynth-coc/artifacts/restricted/guardsynth-eblc-learning-001/m18-cohort-feasibility-2026-09-29-006/RESULT.json'
    prior = json.loads(previous.read_text())
    output.mkdir(parents=True)
    dump(output / 'video_inventory.json', videos)
    dump(output / 'checkpoint_inventory.json', checkpoints)
    result = {'project_id': 'guardsynth-coc', 'status': 'SOURCE_AUDIT_COMPLETE_EVALUATION_DATA_NOT_YET_FROZEN',
              'video_files': len(videos), 'physicalai_event_ids': len({r['event_id'] for r in videos if r['source'] == 'PhysicalAI'}),
              'physicalai_clip_ids': len({r['clip_id'] for r in videos if r['source'] == 'PhysicalAI'}),
              'nuscenes_scene_ids': len({r['event_id'] for r in videos if r['source'] == 'nuScenes'}),
              'frozen_adapters': len(checkpoints), 'optimizer_updates': 0, 'new_predictions': 0,
              'previous_real_scene_audit': {'path': str(previous), 'sha256': sha(previous),
                  'fresh_labelled_test_rows': prior['fresh_labelled_test_rows'],
                  'speed_independent_main_test_eligible': prior['speed_independent_main_test_eligible']},
              'reference_policy': 'Keep missing applicability, candidate measurements, and target labels unresolved; do not manufacture reviewed road-action gold.'}
    dump(output / 'RESULT.json', result)
    (output / 'REPORT_KO.md').write_text(
        '# 추가 평가 자료 점검\n\n'
        f'- PhysicalAI 이벤트 영상 {result["physicalai_event_ids"]}개, nuScenes 장면 영상 {result["nuscenes_scene_ids"]}개 확인.\n'
        '- 시간·정적·기동 과제군의 P0/P1/P2 × 3 seed 체크포인트 27개와 해시를 고정했다.\n'
        '- 영상 보유와 같은 여섯 과제의 평가 정답 구성 완료는 구분한다. 이전 실장면 감사의 새 기준 정답 및 독립 주 평가 적격 사례는 0이었다.\n'
        '- 기존 정확도·제약 위반율·계약 쌍 정확도를 유지한다. 실제 장면 평가에는 관찰·규칙 적용·후보 측정값·기준 정답의 근거가 필요하다.\n'
        '- 평가 입력으로 실제 영상 이미지만 교체한 합성 문제는 실제 행동 검증으로 표시하지 않는다. 새 합성 장면 평가는 별도 합성 평가로 표시한다.\n'
        '- 학습·기존 데이터·기존 결과·원고를 변경하지 않았다. 현재 새 모델 평가를 실행한 결과는 아니다.\n')
    dump(output / 'RUN_MANIFEST.json', {'project_id': 'guardsynth-coc', 'license_class': 'RESTRICTED_INTERNAL_SOURCE_METADATA',
          'script_sha256': sha(Path(__file__)), 'input_result_sha256': sha(previous),
          'checkpoint_hashes': {r['path']: r['sha256'] for r in checkpoints},
          'output_hashes': {p.name: sha(p) for p in output.iterdir() if p.is_file()}})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    if not __import__('re').fullmatch(r'evaluation-source-audit-\d{4}-\d{2}-\d{2}-\d{3}', args.run_id):
        parser.error('use evaluation-source-audit-YYYY-MM-DD-NNN')
    output = ROOT / 'projects/04-guardsynth-coc/artifacts/restricted/paper1-evaluation-expansion-001' / args.run_id
    print(json.dumps(audit(output), ensure_ascii=False, indent=2))
