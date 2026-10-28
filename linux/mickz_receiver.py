#!/usr/bin/env python3
"""Receive MICkz PCM audio and expose it as a PipeWire/PulseAudio source."""

from __future__ import annotations

import argparse
import concurrent.futures
import ipaddress
import json
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
DISCOVERY_REQUEST = b"MICKZ/1 DISCOVER\n"
STREAM_REQUEST = b"MICKZ/1 STREAM\n"


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


def receive_line(connection: socket.socket, max_bytes: int = 256) -> bytes | None:
    result = bytearray()
    while len(result) < max_bytes:
        byte = connection.recv(1)
        if not byte:
            return None
        if byte == b"\n":
            return bytes(result)
        result.extend(byte)
    return None


def local_networks() -> list[tuple[ipaddress.IPv4Network, str]]:
    """Return routable IPv4 LANs, preferring Wi-Fi interfaces."""
    result = subprocess.run(
        ["ip", "-j", "-4", "addr", "show", "scope", "global"],
        check=True,
        capture_output=True,
        text=True,
    )
    interfaces = json.loads(result.stdout)
    networks: list[tuple[ipaddress.IPv4Network, str, int]] = []
    ignored_prefixes = ("lo", "docker", "podman", "virbr", "br-", "veth", "tun", "tap", "wg", "tailscale", "zt")
    for interface in interfaces:
        name = interface.get("ifname", "")
        if name.startswith(ignored_prefixes):
            continue
        for address in interface.get("addr_info", []):
            if address.get("family") != "inet" or address.get("scope") != "global":
                continue
            local = address.get("local")
            prefix = address.get("prefixlen")
            if not local or prefix is None:
                continue
            network = ipaddress.IPv4Network(f"{local}/{prefix}", strict=False)
            if network.num_addresses > 2:
                # Avoid sending probes outside the user's local address space.
                networks.append((network, local, 0 if name.startswith(("wl", "wlan")) else 1))
    networks.sort(key=lambda entry: entry[2])
    unique: dict[str, tuple[ipaddress.IPv4Network, str]] = {}
    for network, local, _priority in networks:
        unique.setdefault(str(network), (network, local))
    return list(unique.values())


def nearby_hosts(network: ipaddress.IPv4Network, local: str):
    """Yield subnet addresses from nearest to farthest without building huge lists."""
    own = int(ipaddress.IPv4Address(local))
    first = int(network.network_address) + 1
    last = int(network.broadcast_address) - 1
    distance = 1
    while own - distance >= first or own + distance <= last:
        lower = own - distance
        upper = own + distance
        if lower >= first:
            yield str(ipaddress.IPv4Address(lower))
        if upper <= last:
            yield str(ipaddress.IPv4Address(upper))
        distance += 1


def probe_android(host: str, port: int) -> str | None:
    """Identify a MICkz Android service without starting microphone capture."""
    try:
        with socket.create_connection((host, port), timeout=0.35) as connection:
            connection.settimeout(0.5)
            connection.sendall(DISCOVERY_REQUEST)
            response = receive_line(connection)
            prefix = b"MICKZ/1 ANDROID "
            if response and response.startswith(prefix):
                return response[len(prefix):].decode("utf-8", errors="replace")
    except OSError:
        pass
    return None


def discover_android(port: int, stop_event: threading.Event) -> tuple[str, str] | None:
    """Scan local subnets using outbound TCP probes and return the first MICkz phone."""
    networks = local_networks()
    for network, local in networks:
        candidates = nearby_hosts(network, local)
        with concurrent.futures.ThreadPoolExecutor(max_workers=48) as pool:
            pending: dict[concurrent.futures.Future[str | None], str] = {}
            addresses = iter(candidates)
            exhausted = False
            while pending or not exhausted:
                while not exhausted and len(pending) < 48 and not stop_event.is_set():
                    try:
                        candidate = next(addresses)
                    except StopIteration:
                        exhausted = True
                        break
                    pending[pool.submit(probe_android, candidate, port)] = candidate
                if stop_event.is_set():
                    for future in pending:
                        future.cancel()
                    return None
                if not pending:
                    break
                done, _ = concurrent.futures.wait(
                    pending, timeout=0.1, return_when=concurrent.futures.FIRST_COMPLETED
                )
                for future in done:
                    candidate = pending.pop(future)
                    try:
                        device_name = future.result()
                    except OSError:
                        device_name = None
                    if device_name is not None:
                        for other in pending:
                            other.cancel()
                        return candidate, device_name
    return None


class Receiver:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.stop_event = threading.Event()
        self.client: socket.socket | None = None
        self.module_id: str | None = None
        self.fifo_dir: str | None = None
        self.fifo_path: str | None = None
        self.fifo_fd: int | None = None

    def request_stop(self) -> None:
        """Wake the connection/read loops so normal cleanup can run."""
        self.stop_event.set()
        if self.client is not None:
            try:
                self.client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.client.close()

    def setup_source(self) -> None:
        if not shutil.which("pactl"):
            raise RuntimeError("Não encontrei pactl. Instale PipeWire com pipewire-pulse.")
        self.remove_stale_sources()
        self.fifo_dir = tempfile.mkdtemp(prefix="mickz-")
        self.fifo_path = os.path.join(self.fifo_dir, "audio.pcm")
        os.mkfifo(self.fifo_path, 0o600)
        # Keep the FIFO open read/write so both module startup and client reconnects
        # work without blocking on a missing FIFO peer. Nonblocking writes prevent
        # a suspended PipeWire source from stopping TCP reads from the phone.
        self.fifo_fd = os.open(self.fifo_path, os.O_RDWR | os.O_NONBLOCK)
        self.module_id = run_checked([
            "pactl", "load-module", "module-pipe-source",
            f"file={self.fifo_path}", f"source_name={SOURCE_NAME}",
            "format=s16le", "rate=48000", "channels=1", "channel_map=mono",
            "source_properties=device.description=MICkz_Android_Microphone",
        ])
        print(f"Fonte de entrada criada: {SOURCE_NAME} (MICkz_Android_Microphone)")

    @staticmethod
    def remove_stale_sources() -> None:
        """Remove abandoned MICkz modules left by an interrupted receiver."""
        modules = run_checked(["pactl", "list", "short", "modules"])
        stale_ids: list[str] = []
        for line in modules.splitlines():
            fields = line.split("\t", 2)
            if len(fields) != 3 or fields[1] != "module-pipe-source":
                continue
            if f"source_name={SOURCE_NAME}" in fields[2].split():
                stale_ids.append(fields[0])
        for module_id in stale_ids:
            subprocess.run(["pactl", "unload-module", module_id], check=True, capture_output=True, text=True)
            print(f"Fonte MICkz antiga removida (módulo {module_id})")

    def serve_client(self, connection: socket.socket, address: tuple[str, int]) -> None:
        print("STATUS: connected", flush=True)
        next_level = time.monotonic()
        try:
            if self.fifo_fd is None:
                raise RuntimeError("A fonte de áudio não está aberta.")
            while not self.stop_event.is_set():
                frame = receive_exactly(connection, FRAME_BYTES)
                if frame is None:
                    break
                samples = struct.unpack("<" + "h" * (len(frame) // 2), frame)
                try:
                    written = os.write(self.fifo_fd, frame)
                except BlockingIOError:
                    # PipeWire may suspend this source until an app selects it.
                    # Keep draining TCP and report levels instead of deadlocking.
                    written = 0
                if written not in (0, len(frame)):
                    raise OSError(f"Escrita PCM incompleta: {written}/{len(frame)} bytes")
                now = time.monotonic()
                if now >= next_level:
                    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
                    level = min(1.0, (rms / 32768) * 2.5)
                    print(f"LEVEL:{level:.4f}", flush=True)
                    next_level = now + 0.04
        except (BrokenPipeError, ConnectionError, OSError) as error:
            if not self.stop_event.is_set():
                print(f"Conexão de áudio encerrada: {error}", file=sys.stderr)
        finally:
            print("STATUS: disconnected", flush=True)

    def connect_stream(self, host: str, port: int) -> socket.socket:
        connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client = connection
        try:
            connection.settimeout(2)
            connection.connect((host, port))
            connection.settimeout(1)
            connection.sendall(STREAM_REQUEST)
            response = receive_line(connection)
            if response != b"MICKZ/1 OK":
                raise ConnectionError("O dispositivo respondeu com um protocolo MICkz desconhecido.")
            connection.settimeout(None)
            return connection
        except Exception:
            connection.close()
            self.client = None
            raise

    def run(self) -> None:
        self.setup_source()
        print("STATUS: disconnected", flush=True)
        last_error = ""
        last_report = 0.0
        try:
            while not self.stop_event.is_set():
                if self.host == "auto":
                    print("STATUS: searching", flush=True)
                    found = discover_android(self.port, self.stop_event)
                    if found is None:
                        if not self.stop_event.is_set():
                            self.stop_event.wait(1)
                        continue
                    host, device_name = found
                    print(f"DEVICE:{host}|{device_name}", flush=True)
                else:
                    host = self.host
                    device_name = "Android por USB" if host == "127.0.0.1" else "Android"
                try:
                    connection = self.connect_stream(host, self.port)
                except OSError as error:
                    if self.stop_event.is_set():
                        break
                    message = str(error)
                    now = time.monotonic()
                    if message != last_error or now - last_report >= 10:
                        print(f"Conexão com {host} falhou: {message}", flush=True)
                        last_error = message
                        last_report = now
                    self.stop_event.wait(2)
                    continue
                with connection:
                    try:
                        print(f"DEVICE:{host}|{device_name}", flush=True)
                        self.serve_client(connection, (host, self.port))
                    finally:
                        self.client = None
                if self.host != "auto":
                    self.stop_event.wait(2)
        finally:
            self.close()

    def close(self) -> None:
        self.stop_event.set()
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
    parser.add_argument("--host", default="auto", help="IP do Android ou 'auto' para buscar na rede")
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
