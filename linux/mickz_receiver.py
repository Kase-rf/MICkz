#!/usr/bin/env python3
"""Receive MICkz PCM audio and expose it as a PipeWire/PulseAudio source."""

from __future__ import annotations

import argparse
import math
import os
import signal
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time

SAMPLE_RATE = 48_000
CHANNELS = 1
SAMPLE_BYTES = 2
FRAME_MS = 20
FRAME_BYTES = SAMPLE_RATE * CHANNELS * SAMPLE_BYTES * FRAME_MS // 1000
SOURCE_NAME = "mickz_android_mic"


def run_checked(command: list[str]) -> str:
    result = subprocess.run(command, check=True, text=True, capture_output=True)
    return result.stdout.strip()


def receive_exactly(connection: socket.socket, size: int) -> bytes | None:
    chunks = bytearray()
    while len(chunks) < size:
        block = connection.recv(size - len(chunks))
        if not block:
            return None
        chunks.extend(block)
    return bytes(chunks)


class Receiver:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.stop_event = threading.Event()
        self.server: socket.socket | None = None
        self.client: socket.socket | None = None
        self.module_id: str | None = None
        self.fifo_dir: str | None = None
        self.fifo_path: str | None = None
        self.fifo_fd: int | None = None

    def request_stop(self) -> None:
        """Wake the accept/read loops so normal cleanup can run."""
        self.stop_event.set()
        if self.server is not None:
            self.server.close()
        if self.client is not None:
            try:
                self.client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def setup_source(self) -> None:
        if not shutil.which("pactl"):
            raise RuntimeError("Não encontrei pactl. Instale PipeWire com pipewire-pulse.")
        self.fifo_dir = tempfile.mkdtemp(prefix="mickz-")
        self.fifo_path = os.path.join(self.fifo_dir, "audio.pcm")
        os.mkfifo(self.fifo_path, 0o600)
        # Keep the FIFO open read/write so both module startup and client reconnects
        # work without blocking on a missing FIFO peer.
        self.fifo_fd = os.open(self.fifo_path, os.O_RDWR)
        self.module_id = run_checked([
            "pactl", "load-module", "module-pipe-source",
            f"file={self.fifo_path}", f"source_name={SOURCE_NAME}",
            "format=s16le", "rate=48000", "channels=1", "channel_map=mono",
            "source_properties=device.description=MICkz_Android_Microphone",
        ])
        print(f"Fonte de entrada criada: {SOURCE_NAME} (MICkz_Android_Microphone)")

    def serve_client(self, connection: socket.socket, address: tuple[str, int]) -> None:
        print(f"Android conectado: {address[0]}:{address[1]}")
        next_report = time.monotonic() + 2.0
        bytes_reported = 0
        peak = 0
        sum_squares = 0
        sample_count = 0
        try:
            if self.fifo_fd is None:
                raise RuntimeError("A fonte de áudio não está aberta.")
            while not self.stop_event.is_set():
                frame = receive_exactly(connection, FRAME_BYTES)
                if frame is None:
                    break
                samples = struct.unpack("<" + "h" * (len(frame) // 2), frame)
                peak = max(peak, max(abs(sample) for sample in samples))
                sum_squares += sum(sample * sample for sample in samples)
                sample_count += len(samples)
                written = os.write(self.fifo_fd, frame)
                if written != len(frame):
                    raise OSError(f"Escrita PCM incompleta: {written}/{len(frame)} bytes")
                bytes_reported += written
                now = time.monotonic()
                if now >= next_report:
                    rms = math.sqrt(sum_squares / sample_count) if sample_count else 0.0
                    print(
                        f"PCM: {bytes_reported} bytes/2 s, pico {peak / 32768 * 100:.1f}%, "
                        f"RMS {rms / 32768 * 100:.1f}%"
                    )
                    next_report = now + 2.0
                    bytes_reported = 0
                    peak = 0
                    sum_squares = 0
                    sample_count = 0
        except (BrokenPipeError, ConnectionError, OSError) as error:
            if not self.stop_event.is_set():
                print(f"Conexão de áudio encerrada: {error}", file=sys.stderr)
        finally:
            print("Android desconectado")

    def run(self) -> None:
        self.setup_source()
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(1)
        self.server.settimeout(1)
        print(f"Aguardando Android em {self.host}:{self.port} (PCM mono 48 kHz)")
        try:
            while not self.stop_event.is_set():
                try:
                    connection, address = self.server.accept()
                except TimeoutError:
                    continue
                except OSError:
                    if self.stop_event.is_set():
                        break
                    raise
                with connection:
                    self.client = connection
                    try:
                        self.serve_client(connection, address)
                    finally:
                        self.client = None
        finally:
            self.close()

    def close(self) -> None:
        self.stop_event.set()
        if self.server is not None:
            self.server.close()
        if self.module_id:
            subprocess.run(["pactl", "unload-module", self.module_id], check=False)
            print("Fonte virtual removida")
            self.module_id = None
        if self.fifo_fd is not None:
            os.close(self.fifo_fd)
            self.fifo_fd = None
        if self.fifo_path and os.path.exists(self.fifo_path):
            os.unlink(self.fifo_path)
        if self.fifo_dir and os.path.isdir(self.fifo_dir):
            os.rmdir(self.fifo_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0", help="Interface para escutar (padrão: todas)")
    parser.add_argument("--port", type=int, default=49152, help="Porta TCP (padrão: 49152)")
    args = parser.parse_args()
    receiver = Receiver(args.host, args.port)
    # Let the main loop exit normally so its finally block owns cleanup.
    signal.signal(signal.SIGTERM, lambda *_: receiver.request_stop())
    try:
        receiver.run()
    except KeyboardInterrupt:
        receiver.close()
    except (OSError, subprocess.CalledProcessError, RuntimeError) as error:
        receiver.close()
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
