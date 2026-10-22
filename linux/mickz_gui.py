#!/usr/bin/env python3
"""Graphical controller for the MICkz Linux audio receiver."""

from __future__ import annotations

import queue
import re
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


PORT = 49152
RECEIVER = Path(__file__).resolve().with_name("mickz_receiver.py")


def local_ip() -> str:
    """Return the local IPv4 address selected for outbound traffic, if any."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))
        address = probe.getsockname()[0]
        return address if address != "0.0.0.0" else "Não detectado"
    except OSError:
        return "Não detectado"
    finally:
        probe.close()


class MickzWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("MICkz — Microfone Android no Linux")
        self.root.geometry("700x590")
        self.root.minsize(620, 520)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.process: subprocess.Popen[str] | None = None
        self.closing = False
        self.close_started_at = 0.0

        self.status = tk.StringVar(value="Parado")
        self.ip = tk.StringVar(value=local_ip())
        self.level = tk.StringVar(value="Pico: —    RMS: —")
        self.usb_status = tk.StringVar(value="USB: não configurado")

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close_window)
        self.root.after(100, self._drain_events)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=20)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="MICkz", font=("TkDefaultFont", 22, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="Use o microfone do Android como entrada de áudio no Linux.",
        ).pack(anchor="w", pady=(2, 14))

        connection = ttk.LabelFrame(outer, text="Receptor Linux", padding=14)
        connection.pack(fill="x")

        state_row = ttk.Frame(connection)
        state_row.pack(fill="x")
        ttk.Label(state_row, text="Estado:", font=("TkDefaultFont", 10, "bold")).pack(side="left")
        ttk.Label(state_row, textvariable=self.status).pack(side="left", padx=(7, 0))
        ttk.Label(state_row, textvariable=self.level).pack(side="right")

        address_row = ttk.Frame(connection)
        address_row.pack(fill="x", pady=(12, 0))
        ttk.Label(address_row, text="IP para Wi-Fi:").pack(side="left")
        ttk.Label(address_row, textvariable=self.ip, font=("TkDefaultFont", 10, "bold")).pack(
            side="left", padx=(6, 0)
        )
        ttk.Label(address_row, text=f"    Porta TCP: {PORT}").pack(side="left", padx=(10, 0))
        self.copy_button = ttk.Button(address_row, text="Copiar IP", command=self.copy_ip)
        self.copy_button.pack(side="right")

        actions = ttk.Frame(connection)
        actions.pack(fill="x", pady=(14, 0))
        self.start_button = ttk.Button(actions, text="Iniciar receptor", command=self.start_receiver)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(
            actions, text="Parar receptor", command=self.stop_receiver, state="disabled"
        )
        self.stop_button.pack(side="left", padx=(8, 0))

        phone = ttk.LabelFrame(outer, text="Conectar o celular", padding=14)
        phone.pack(fill="x", pady=(14, 0))
        ttk.Label(
            phone,
            text=(
                "Wi-Fi: conecte os dois aparelhos à mesma rede e informe no MICkz Android\n"
                "o IP mostrado acima."
            ),
            justify="left",
        ).pack(anchor="w")
        usb_row = ttk.Frame(phone)
        usb_row.pack(fill="x", pady=(10, 0))
        ttk.Button(usb_row, text="Configurar USB", command=self.configure_usb).pack(side="left")
        ttk.Label(usb_row, textvariable=self.usb_status).pack(side="left", padx=(10, 0))
        ttk.Label(
            phone,
            text="Depois, use 127.0.0.1 no celular. O receptor precisa estar iniciado.",
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        logs_frame = ttk.LabelFrame(outer, text="Atividade", padding=8)
        logs_frame.pack(fill="both", expand=True, pady=(14, 0))
        self.log = tk.Text(logs_frame, height=9, wrap="word", state="disabled", font=("TkFixedFont", 9))
        scrollbar = ttk.Scrollbar(logs_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._append_log("MICkz pronto. Inicie o receptor antes de conectar o celular.")

    def _append_log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", message.rstrip() + "\n")
        lines = int(self.log.index("end-1c").split(".")[0])
        if lines > 500:
            self.log.delete("1.0", f"{lines - 500}.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def copy_ip(self) -> None:
        address = self.ip.get()
        if address == "Não detectado":
            self._append_log("Não foi possível detectar o IP. Confirme a conexão de rede do computador.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(address)
        self._append_log(f"IP copiado: {address}")

    def start_receiver(self) -> None:
        if self.process is not None and self.process.poll() is None:
            return
        if not RECEIVER.is_file():
            messagebox.showerror("MICkz", f"Não encontrei o receptor Linux:\n{RECEIVER}", parent=self.root)
            return
        try:
            self.process = subprocess.Popen(
                [sys.executable, "-u", str(RECEIVER), "--host", "0.0.0.0", "--port", str(PORT)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as error:
            messagebox.showerror("MICkz", f"Não foi possível iniciar o receptor:\n{error}", parent=self.root)
            return
        self.status.set("Iniciando…")
        self.level.set("Pico: —    RMS: —")
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        threading.Thread(target=self._read_output, args=(self.process,), daemon=True).start()

    def _read_output(self, process: subprocess.Popen[str]) -> None:
        assert process.stdout is not None
        for line in process.stdout:
            self.events.put(("log", line.rstrip()))
        self.events.put(("exit", process.wait()))

    def stop_receiver(self) -> None:
        if self.process is None or self.process.poll() is not None:
            self._set_stopped()
            return
        self.status.set("Parando…")
        self.stop_button.configure(state="disabled")
        self._append_log("Solicitando parada do receptor…")
        self.process.terminate()
        threading.Thread(target=self._kill_if_stuck, args=(self.process,), daemon=True).start()

    @staticmethod
    def _kill_if_stuck(process: subprocess.Popen[str]) -> None:
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()

    def configure_usb(self) -> None:
        if self.process is None or self.process.poll() is not None:
            messagebox.showinfo("MICkz", "Inicie o receptor antes de configurar o USB.", parent=self.root)
            return
        self.usb_status.set("Configurando…")
        self._append_log("Configurando redirecionamento USB com adb…")
        threading.Thread(target=self._run_adb_reverse, daemon=True).start()

    def _run_adb_reverse(self) -> None:
        try:
            result = subprocess.run(
                ["adb", "reverse", f"tcp:{PORT}", f"tcp:{PORT}"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            self.events.put(("usb", (True, result.stdout.strip() or "USB configurado")))
        except FileNotFoundError:
            self.events.put(("usb", (False, "adb não encontrado; instale android-tools")))
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or "Nenhum celular autorizado.").strip()
            self.events.put(("usb", (False, detail)))
        except (OSError, subprocess.TimeoutExpired) as error:
            self.events.put(("usb", (False, str(error))))

    def _handle_receiver_line(self, line: str) -> None:
        if not line:
            return
        self._append_log(line)
        normalized = line.lower()
        if "aguardando android" in normalized:
            self.status.set("Aguardando celular")
        elif "android conectado" in normalized:
            self.status.set("Celular conectado")
        elif "android desconectado" in normalized:
            self.status.set("Aguardando celular")
        elif normalized.startswith("pcm:"):
            match = re.search(r"pico\s+([\d.]+)%.*rms\s+([\d.]+)%", normalized)
            if match:
                self.level.set(f"Pico: {match.group(1)}%    RMS: {match.group(2)}%")
        elif "erro:" in normalized or "error" in normalized:
            self.status.set("Erro no receptor")

    def _set_stopped(self) -> None:
        self.status.set("Parado")
        self.level.set("Pico: —    RMS: —")
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")

    def _drain_events(self) -> None:
        while True:
            try:
                event, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if event == "log":
                self._handle_receiver_line(str(payload))
            elif event == "exit":
                return_code = int(payload)
                self.process = None
                if not self.closing:
                    self._set_stopped()
                    if return_code:
                        self.status.set("Receptor encerrado com erro")
                        self._append_log(f"O receptor encerrou com código {return_code}.")
                    else:
                        self._append_log("Receptor parado.")
            elif event == "usb":
                success, detail = payload  # type: ignore[misc]
                if success:
                    self.usb_status.set("USB pronto — use 127.0.0.1 no celular")
                    self._append_log("Redirecionamento USB configurado. No app Android, use 127.0.0.1.")
                else:
                    self.usb_status.set("USB não configurado")
                    self._append_log(f"Falha ao configurar USB: {detail}")
        if self.closing:
            if self.process is None or self.process.poll() is not None:
                self.root.destroy()
                return
            if self.close_started_at and time.monotonic() - self.close_started_at > 4:
                self.process.kill()
        self.root.after(100, self._drain_events)

    def close_window(self) -> None:
        self.closing = True
        process = self.process
        if process is not None and process.poll() is None:
            self.close_started_at = time.monotonic()
            process.terminate()
            self.root.after(100, self._drain_events)
            return
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    MickzWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
