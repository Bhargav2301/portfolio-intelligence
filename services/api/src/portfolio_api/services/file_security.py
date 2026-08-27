from __future__ import annotations

import socket
import struct
from dataclasses import dataclass


class MalwareScannerUnavailable(RuntimeError):
    pass


class MalwareDetected(ValueError):
    pass


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    engine: str
    message: str


def scan_with_clamav(content: bytes, host: str, port: int, timeout: float = 10.0) -> ScanResult:
    """Use ClamAV's INSTREAM protocol without writing the source to a shared path."""
    try:
        with socket.create_connection((host, port), timeout=timeout) as connection:
            connection.sendall(b"zINSTREAM\0")
            view = memoryview(content)
            for offset in range(0, len(view), 64 * 1024):
                chunk = view[offset : offset + 64 * 1024]
                connection.sendall(struct.pack(">I", len(chunk)))
                connection.sendall(chunk)
            connection.sendall(struct.pack(">I", 0))
            response = connection.recv(4096).decode("utf-8", errors="replace").strip("\0\r\n")
    except OSError as error:
        raise MalwareScannerUnavailable("ClamAV is unavailable") from error
    if response.endswith("FOUND"):
        raise MalwareDetected(response)
    if not response.endswith("OK"):
        raise MalwareScannerUnavailable(f"Unexpected ClamAV response: {response}")
    return ScanResult(clean=True, engine="clamav", message=response)
