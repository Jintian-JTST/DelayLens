"""Read a completed original run, replay in memory, and verify its existing ZIPs."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path, compressed: bool = False) -> str:
    digest = hashlib.sha256()
    with (gzip.open(path, 'rb') if compressed else path.open('rb')) as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def verify(run: Path) -> dict:
    from backend.ingest.artifacts import SEGMENT_FIELDS
    from backend.ingest.derive import derive, raw_paths, read_polls

    metadata = json.loads((run / 'run.json').read_text(encoding='utf-8'))
    require(metadata['status'] == 'completed' and bool(metadata['ended_at']), 'Recorder has not completed')
    quality = json.loads((run / 'derived/quality.json').read_text(encoding='utf-8'))
    require(quality['recording_status'] == 'completed', 'Final derived output is not ready')
    polls, recovery = read_polls(raw_paths(run))
    result = derive(polls, metadata['route'])
    csv_output = io.StringIO(newline='')
    writer = csv.DictWriter(csv_output, fieldnames=SEGMENT_FIELDS, lineterminator='\n')
    writer.writeheader()
    writer.writerows(result['segments'])
    require(csv_output.getvalue() == (run / 'derived/segments.csv').read_text(encoding='utf-8'), 'Replay CSV differs')
    require(result['events'] == json.loads((run / 'derived/stop_events.json').read_text(encoding='utf-8')), 'Replay events differ')
    require(len(result['segments']) == quality['independent_trips'], 'Segment count differs')
    require(len(polls) == quality['raw_polls'], 'Poll count differs')
    raw_hash = sha256(run / 'polls.jsonl')
    require(raw_hash == sha256(run / 'polls.jsonl.gz', compressed=True), 'Raw JSONL/GZIP differ')
    route_id = metadata['route']['route_id']
    final_data = run / 'exports' / f'delaylens-{route_id}-final-data.zip'
    final_source = run / 'exports' / f'delaylens-{route_id}-final-source.zip'
    require(final_data.is_file() and final_source.is_file(), 'Automatic final ZIPs are not ready')
    archives = []
    for archive_path in sorted((run / 'exports').glob('*.zip')):
        with zipfile.ZipFile(archive_path) as archive:
            require(archive.testzip() is None, 'ZIP CRC failure')
            manifest = json.loads(archive.read('MANIFEST.json'))
            for entry in manifest['files']:
                content = archive.read(entry['path'])
                require(len(content) == entry['bytes'], 'ZIP size mismatch')
                require(hashlib.sha256(content).hexdigest() == entry['sha256'], 'ZIP manifest mismatch')
        archives.append({'path': archive_path.name, 'bytes': archive_path.stat().st_size,
                         'sha256': sha256(archive_path), 'crc_and_manifest_verified': True})
    with zipfile.ZipFile(final_data) as archive:
        require(json.loads(archive.read('run.json')) == metadata, 'Final ZIP run metadata differs')
        require(json.loads(archive.read('quality.json')) == quality, 'Final ZIP quality differs')
        require(archive.read('segments.csv').decode('utf-8') == csv_output.getvalue(), 'Final ZIP CSV differs')
        with archive.open('raw/polls.jsonl.gz') as compressed, gzip.GzipFile(fileobj=compressed) as raw:
            count = 0
            for count, line in enumerate(raw, 1):
                require(count <= len(polls) and json.loads(line) == polls[count - 1], 'Archived canonical raw poll differs')
            require(count == len(polls), 'Archived canonical raw count differs')
    hourly = quality['coverage_hourly']
    usable_hours = [hour['hour_utc'] for hour in hourly if hour['usable_segments']]
    return {'route_id': route_id, 'recording_status': metadata['status'], 'started_at': metadata['started_at'],
            'ended_at': metadata['ended_at'], 'last_poll_utc': quality['last_poll_utc'],
            'raw_polls': len(polls), 'successful_polls': quality['successful_polls'],
            'failed_polls': quality['failed_polls'], 'independent_trips': len(result['segments']),
            'replayed_events': len(result['events']), 'support_state': quality['support_state'],
            'data_gate': quality['data_gate'], 'acceptance_gate': quality['acceptance_gate'],
            'poll_hours': [hour['hour_utc'] for hour in hourly if hour['successful_polls']],
            'usable_segment_hours': usable_hours,
            'target_15_runs_and_3_usable_hours_met': len(result['segments']) >= 15 and len(usable_hours) >= 3,
            'raw_jsonl_sha256': raw_hash, 'recovery': recovery, 'archives': archives,
            'human_review_claimed': False, 'database_counts_pooled': False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.run.resolve()), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
