"""Composable boot workflow, independent of storage transport and DUT framework."""
from __future__ import annotations
import json
from pathlib import Path
import threading
import time
from .storage import StorageError


class UARTCapture:
    """receive(timeout_seconds) -> bytes must honor its timeout.

    Capture begins before reset and persists every received byte, including failure
    output. The adapter is supplied by the DUT's UART resource (no serial guessing).
    """
    def __init__(self, receive, path):
        self.receive, self.path = receive, Path(path)
        self.stop = threading.Event()
        self.condition = threading.Condition()
        self.buffer = bytearray()
        self.offset = 0
        self.error = None
        self.thread = threading.Thread(target=self._capture, daemon=True)

    def __enter__(self):
        self.file = self.path.open('xb')
        self.thread.start()
        return self

    def _capture(self):
        try:
            while not self.stop.is_set():
                chunk = self.receive(0.2)
                if chunk:
                    self.file.write(chunk)
                    self.file.flush()
                    with self.condition:
                        self.buffer.extend(chunk)
                        # Bound RAM, preserving full stream on disk.
                        if len(self.buffer) > 4 * 1024 * 1024:
                            trim = len(self.buffer) - 2 * 1024 * 1024
                            del self.buffer[:trim]
                            self.offset = max(0, self.offset - trim)
                        self.condition.notify_all()
        except BaseException as e:
            with self.condition:
                self.error = e
                self.condition.notify_all()

    def expect(self, marker, timeout):
        deadline = time.monotonic() + timeout
        marker = marker.encode() if isinstance(marker, str) else marker
        with self.condition:
            while True:
                if self.error:
                    raise StorageError('UART', str(self.error))
                found = self.buffer.find(marker, self.offset)
                if found >= 0:
                    self.offset = found + len(marker)
                    return True
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise StorageError('BOOT_TIMEOUT', f'UART missing {marker!r}')
                self.condition.wait(min(0.2, remaining))

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join(timeout=1)
        if self.thread.is_alive():
            raise StorageError('UART', 'UART adapter did not honor receive timeout')
        self.file.close()


def storage_boot_test(storage, build, boot_files, power_cycle, uart_receive,
                      artifacts, markers=('U-Boot', 'Linux version', 'login:'),
                      timeout=120, health_check=None):
    """build() -> None; boot_files maps local filenames to partition paths.

    Uses the existing resource objects supplied by the caller. No DUT framework,
    guessed USB identity, or generic shell power-control hooks are introduced.
    """
    directory = Path(artifacts)
    directory.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    result = {'storage': storage.name, 'simulated': storage.backend.simulated,
              'validation': 'SIMULATED' if storage.backend.simulated else 'REQUIRES HARDWARE',
              'uart_log': str(directory / 'uart.bin'), 'markers': []}
    try:
        build()
        with storage:
            with storage.host() as sd:
                for source, destination in boot_files.items():
                    sd.copy(source, destination)
            storage.acquire_target()
            storage.wait_for_target()
            with UARTCapture(uart_receive, directory / 'uart.bin') as uart:
                power_cycle()
                deadline = time.monotonic() + timeout
                for marker in markers:
                    uart.expect(marker, max(0, deadline - time.monotonic()))
                    result['markers'].append(marker)
                if health_check is not None and not health_check(uart):
                    raise StorageError('HEALTH_CHECK', 'DUT health check failed')
        result['result'] = 'PASS'
    except BaseException as e:
        result.update(result='FAIL', error={'code': getattr(e, 'code', 'INTERRUPTED' if
                      isinstance(e, KeyboardInterrupt) else 'WORKFLOW'), 'message': str(e)})
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise
    finally:
        result['duration'] = time.monotonic() - start
        (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result
