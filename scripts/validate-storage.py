#!/usr/bin/env python3
"""Reproducible SIMULATED validation. Never writes USB/block devices."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from labinstruments.storage import MockRemovableStorage, RemovableStorage
from labinstruments.storage_workflow import storage_boot_test

parser = argparse.ArgumentParser()
parser.add_argument('--output', default='local/storage-validation-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
args = parser.parse_args()
out = Path(args.output).resolve()
out.mkdir(parents=True, exist_ok=False)
start = datetime.now(timezone.utc).isoformat()
tests = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                       cwd=root, capture_output=True, text=True)
(out / 'software-tests.log').write_text(tests.stdout + tests.stderr)
commands = []
with tempfile.TemporaryDirectory(prefix='hil-storage-validation-') as temporary:
    sandbox = Path(temporary)
    image = sandbox / 'test.img'
    image.write_bytes(b'AI-HIL-SIMULATED\n' * 4096)
    config = root / 'examples/storage/mock.json'
    for argv in [['list'], ['zynq_dev', 'status'], ['zynq_dev', 'host'],
                 ['zynq_dev', 'device'], ['zynq_dev', 'partitions'],
                 ['zynq_dev', 'target'], ['zynq_dev', 'off'],
                 ['zynq_dev', 'flash', str(image), '--dry-run'],
                 ['zynq_dev', 'flash', str(image), '--verify']]:
        proc = subprocess.run([sys.executable, '-m', 'labinstruments.storage_cli',
                               '--json', '--config', str(config), '--runtime', str(sandbox / 'runtime'),
                               *argv], cwd=root, capture_output=True, text=True)
        commands.append({'argv': argv, 'exit': proc.returncode,
                         'stdout': json.loads(proc.stdout), 'stderr': proc.stderr})
    log = sandbox / 'runtime/operations.jsonl'
    if log.exists():
        (out / 'operations.jsonl').write_bytes(log.read_bytes())
    backend = MockRemovableStorage('SIMULATED-ZYNQ', sandbox / 'mock')
    storage = RemovableStorage('zynq-test', backend, sandbox / 'workflow-runtime', settle=0)
    chunks = queue.Queue()
    def receive(timeout):
        try:
            return chunks.get(timeout=timeout)
        except queue.Empty:
            return b''
    def simulated_reset():
        chunks.put(b'[SIMULATED UART]\r\nU-Boot 2025.01\r\nLinux version 6.6\r\nlogin:\r\nhealth: PASS\r\n')
    boot = storage_boot_test(storage, lambda: None,
                             {str(image): '/boot/BOOT.BIN'}, simulated_reset, receive,
                             out / 'zynq-simulated', timeout=2,
                             health_check=lambda uart: uart.expect('health: PASS', 1))
identity = subprocess.run([sys.executable, '-m', 'labinstruments.storage_cli',
                           'discover', '--json'], cwd=root, capture_output=True, text=True)
files = ['labinstruments/storage.py', 'labinstruments/storage_cli.py',
         'labinstruments/storage_workflow.py', 'tests/test_storage.py',
         'flake.nix', 'flake.lock', 'scripts/validate-storage.py']
report = {'timestamp': start, 'validation': 'TESTED / SIMULATED',
          'hardware_validation': 'REQUIRES HARDWARE', 'tests_exit': tests.returncode,
          'cli': commands, 'boot': boot, 'usb_discovery': json.loads(identity.stdout),
          'python': sys.version, 'source_sha256': {
              name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files},
          'sd_mux_revision': '9dd189d973da64e033a0c5c2adb3d94b23153d94',
          'result': 'PASS' if tests.returncode == 0 and all(c['exit'] == 0 for c in commands)
                              and boot['result'] == 'PASS' else 'FAIL'}
(out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'result': report['result'], 'report': str(out), 'simulated': True}))
sys.exit(0 if report['result'] == 'PASS' else 1)
