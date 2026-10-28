#!/usr/bin/env python3
"""Dark graphical controller for the MICkz Linux audio receiver."""

from __future__ import annotations

import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


PORT = 49152
RECEIVER = Path(__file__).resolve().with_name("mickz_receiver.py")
BG = "#0b1118"
PANEL = "#111b25"
PANEL_ALT = "#15222d"
TEXT = "#e8f0f6"
MUTED = "#91a4b5"
ACCENT = "#14cba8"
ACCENT_HOVER = "#20dfb9"
DISCONNECTED = "#f29a76"


class MickzWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("MICkz — Microfone Android no Linux")
        self.root.geometry("800x650")
        self.root.minsize(720, 580)
        self.root.configure(background=BG)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.process: subprocess.Popen[str] | None = None
        self.quit_requested = False
        self.close_started_at = 0.0
        self.usb_ready = False
        self.connection_mode = tk.StringVar(value="wifi")
        self.status = tk.StringVar(value="Celular desconectado")
        self.detail = tk.StringVar(value="Inicie o MICkz no celular; a busca continua quando o receptor estiver ativo.")
        self.usb_status = tk.StringVar(value="USB não configurado")
        self.level = 0.0
        self.display_level = 0.0

        self._configure_style()
        self._build_ui()
        self._build_menu()
        self.root.protocol("WM_DELETE_WINDOW", self.quit_application)
        self.root.after(100, self._drain_events)
        self.root.after(40, self._animate_meter)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, font=("Sans", 10))
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=PANEL)
        style.configure("Inset.TFrame", background=PANEL_ALT)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Card.TLabel", background=PANEL, foreground=TEXT)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("CardMuted.TLabel", background=PANEL, foreground=MUTED)
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Sans", 22, "bold"))
        style.configure("Subtitle.TLabel", background=BG, foreground=MUTED, font=("Sans", 10))
        style.configure("Status.TLabel", background=PANEL, foreground=DISCONNECTED, font=("Sans", 15, "bold"))
        style.configure("StatusConnected.TLabel", background=PANEL, foreground=ACCENT, font=("Sans", 15, "bold"))
        style.configure("Section.TLabel", background=PANEL, foreground=TEXT, font=("Sans", 11, "bold"))
        style.configure("TButton", background=PANEL_ALT, foreground=TEXT, borderwidth=0, padding=(16, 11))
        style.map("TButton", background=[("active", "#20313f"), ("disabled", "#17212a")],
                  foreground=[("disabled", "#647585")])
        style.configure("Accent.TButton", background=ACCENT, foreground="#06211d", font=("Sans", 11, "bold"))
        style.map("Accent.TButton", background=[("active", ACCENT_HOVER), ("disabled", "#38514e")])
        style.configure("Mode.TRadiobutton", background=PANEL, foreground=MUTED, padding=(8, 5))
        style.map("Mode.TRadiobutton", background=[("active", PANEL)],
                  foreground=[("selected", TEXT), ("active", TEXT)])

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=(24, 20))
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 18))
        title_box = ttk.Frame(header)
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(title_box, text="MICkz", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="Microfone do celular no seu PC", style="Subtitle.TLabel").pack(anchor="w", pady=(2, 0))
        ttk.Label(header, text="v0.4.0", style="Muted.TLabel").pack(side="right", anchor="n", pady=6)

        status_card = ttk.Frame(outer, style="Card.TFrame", padding=(18, 16))
        status_card.pack(fill="x")
        left_status = ttk.Frame(status_card, style="Card.TFrame")
        left_status.pack(side="left", fill="x", expand=True)
        state_line = ttk.Frame(left_status, style="Card.TFrame")
        state_line.pack(anchor="w")
        self.status_dot = ttk.Label(state_line, text="●", style="Status.TLabel")
        self.status_dot.pack(side="left", padx=(0, 9))
        self.status_label = ttk.Label(state_line, textvariable=self.status, style="Status.TLabel")
        self.status_label.pack(side="left")
        ttk.Label(left_status, textvariable=self.detail, style="CardMuted.TLabel").pack(anchor="w", pady=(5, 0))
        ttk.Label(status_card, text="WI-FI  ·  REDE LOCAL", style="CardMuted.TLabel").pack(side="right", padx=(12, 0))

        meter_card = ttk.Frame(outer, style="Card.TFrame", padding=(18, 16))
        meter_card.pack(fill="x", pady=(16, 0))
        ttk.Label(meter_card, text="Nível do microfone", style="Section.TLabel").pack(anchor="w")
        self.meter = tk.Canvas(meter_card, height=82, background=PANEL, highlightthickness=0)
        self.meter.pack(fill="x", pady=(12, 4))
        ttk.Label(meter_card, text="Áudio recebido do celular", style="CardMuted.TLabel").pack(anchor="center")

        controls = ttk.Frame(outer, style="Card.TFrame", padding=(18, 14))
        controls.pack(fill="x", pady=(16, 0))
        mode_box = ttk.Frame(controls, style="Card.TFrame")
        mode_box.pack(side="left", fill="y")
        ttk.Label(mode_box, text="CONEXÃO", style="CardMuted.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Radiobutton(mode_box, text="Wi-Fi automático", value="wifi", variable=self.connection_mode,
                        style="Mode.TRadiobutton").pack(anchor="w")
        ttk.Radiobutton(mode_box, text="USB", value="usb", variable=self.connection_mode,
                        style="Mode.TRadiobutton").pack(anchor="w")

        buttons = ttk.Frame(controls, style="Card.TFrame")
        buttons.pack(side="right", anchor="center", padx=(12, 0))
        self.start_button = ttk.Button(buttons, text="Iniciar receptor", style="Accent.TButton", command=self.start_receiver)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(buttons, text="Parar", command=self.stop_receiver, state="disabled")
        self.stop_button.pack(side="left", padx=(8, 0))
        self.usb_button = ttk.Button(buttons, text="Configurar USB", command=self.configure_usb)
        self.usb_button.pack(side="left", padx=(8, 0))

        usb_line = ttk.Frame(outer)
        usb_line.pack(fill="x", pady=(8, 0))
        ttk.Label(usb_line, textvariable=self.usb_status, style="Muted.TLabel").pack(side="right")

        logs_card = ttk.Frame(outer, style="Card.TFrame", padding=(14, 12))
        logs_card.pack(fill="both", expand=True, pady=(16, 0))
        ttk.Label(logs_card, text="Atividade", style="Section.TLabel").pack(anchor="w", pady=(0, 7))
        log_frame = ttk.Frame(logs_card, style="Card.TFrame")
        log_frame.pack(fill="both", expand=True)
        self.log = tk.Text(log_frame, height=6, wrap="word", state="disabled", font=("Monospace", 9),
                           background="#0d151d", foreground="#b6c6d3", insertbackground=TEXT,
                           relief="flat", padx=10, pady=8, selectbackground="#1f665c")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._append_log("Pronto. Inicie o receptor e depois o microfone no celular; a busca Wi-Fi é automática.")

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root, background=PANEL, foreground=TEXT,
                          activebackground="#20313f", activeforeground=TEXT,
                          borderwidth=0)
        app_menu = tk.Menu(menubar, tearoff=False, background=PANEL, foreground=TEXT,
                           activebackground="#20313f", activeforeground=TEXT)
        app_menu.add_command(label="Mostrar MICkz", command=self.show_window)
        app_menu.add_separator()
        app_menu.add_command(label="Encerrar MICkz", command=self.quit_application)
        menubar.add_cascade(label="MICkz", menu=app_menu)
        self.root.configure(menu=menubar)

    def show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _append_log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", message.rstrip() + "\n")
        lines = int(self.log.index("end-1c").split(".")[0])
        if lines > 250:
            self.log.delete("1.0", f"{lines - 250}.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def start_receiver(self) -> None:
        if self.process is not None and self.process.poll() is None:
            return
        if not RECEIVER.is_file():
            messagebox.showerror("MICkz", f"Não encontrei o receptor Linux:\n{RECEIVER}", parent=self.root)
            return
        if self.connection_mode.get() == "usb" and not self.usb_ready:
            messagebox.showinfo("MICkz", "Clique em Configurar USB e autorize a depuração no celular.", parent=self.root)
            return
        host = "auto" if self.connection_mode.get() == "wifi" else "127.0.0.1"
        try:
            self.process = subprocess.Popen(
                [sys.executable, "-u", str(RECEIVER), "--host", host, "--port", str(PORT)],
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
        self._set_connection_state("searching")
        self.level = 0.0
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.usb_button.configure(state="disabled")
        self._append_log("Fonte de microfone iniciada; procurando o celular na rede…")
        threading.Thread(target=self._read_output, args=(self.process,), daemon=True).start()

    def _read_output(self, process: subprocess.Popen[str]) -> None:
        assert process.stdout is not None
        for line in process.stdout:
            self.events.put(("receiver", line.rstrip()))
        self.events.put(("exit", process.wait()))

    def stop_receiver(self) -> None:
        if self.process is None or self.process.poll() is not None:
            self._set_stopped()
            return
        self._set_connection_state("disconnected")
        self.stop_button.configure(state="disabled")
        self._append_log("Parando receptor…")
        self.process.terminate()
        threading.Thread(target=self._kill_if_stuck, args=(self.process,), daemon=True).start()

    @staticmethod
    def _kill_if_stuck(process: subprocess.Popen[str]) -> None:
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()

    def configure_usb(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self._append_log("Pare o receptor antes de alternar para USB.")
            return
        self.connection_mode.set("usb")
        self.usb_status.set("Configurando encaminhamento…")
        self._append_log("Configurando encaminhamento USB com ADB…")
        self.usb_button.configure(state="disabled")
        threading.Thread(target=self._run_adb_forward, daemon=True).start()

    def _run_adb_forward(self) -> None:
        try:
            result = subprocess.run(
                ["adb", "forward", f"tcp:{PORT}", f"tcp:{PORT}"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            self.events.put(("usb", (True, result.stdout.strip() or "Encaminhamento pronto")))
        except FileNotFoundError:
            self.events.put(("usb", (False, "ADB não encontrado; instale android-tools")))
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or "Nenhum celular autorizado.").strip()
            self.events.put(("usb", (False, detail)))
        except (OSError, subprocess.TimeoutExpired) as error:
            self.events.put(("usb", (False, str(error))))

    def _set_connection_state(self, state: str) -> None:
        if state == "connected":
            self.status.set("Celular conectado")
            self.status_label.configure(style="StatusConnected.TLabel")
            self.status_dot.configure(style="StatusConnected.TLabel")
        elif state == "searching":
            self.status.set("Procurando celular…")
            self.status_label.configure(style="Status.TLabel")
            self.status_dot.configure(style="Status.TLabel")
        else:
            self.status.set("Celular desconectado")
            self.status_label.configure(style="Status.TLabel")
            self.status_dot.configure(style="Status.TLabel")
            self.level = 0.0

    def _handle_receiver_line(self, line: str) -> None:
        if not line:
            return
        if line.startswith("STATUS:"):
            state = line.split(":", 1)[1].strip()
            if state in {"connected", "disconnected", "searching"}:
                self._set_connection_state(state)
                if state == "searching":
                    self.detail.set("Buscando MICkz Android nas redes locais…")
                elif state == "disconnected":
                    self.detail.set("Aguardando o celular; a busca continua automaticamente.")
            return
        if line.startswith("DEVICE:"):
            device = line.split(":", 1)[1]
            host, _, name = device.partition("|")
            self.detail.set(f"{name.strip() or 'Android'}  ·  {host}")
            return
        if line.startswith("LEVEL:"):
            match = re.fullmatch(r"LEVEL:([\d.]+)", line)
            if match:
                self.level = max(0.0, min(1.0, float(match.group(1))))
            return
        if line == "Android desconectado":
            return
        self._append_log(line)

    def _set_stopped(self) -> None:
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.usb_button.configure(state="normal")
        self._set_connection_state("disconnected")
        self.detail.set("Inicie o receptor; a busca automática começará.")

    def _animate_meter(self) -> None:
        self.display_level += (self.level - self.display_level) * 0.45
        width = max(1, self.meter.winfo_width())
        height = max(1, self.meter.winfo_height())
        self.meter.delete("all")
        bars = max(24, min(64, width // 13))
        gap = 4
        bar_width = max(3, (width - (bars - 1) * gap) / bars)
        active = int(round(self.display_level * bars))
        top = height * 0.30
        bottom = height * 0.70
        for index in range(bars):
            x1 = index * (bar_width + gap)
            x2 = x1 + bar_width
            if index < active:
                ratio = index / max(1, bars - 1)
                color = "#f3a45b" if ratio > 0.88 else ("#1bddb3" if ratio > 0.18 else "#12a98d")
            else:
                color = "#26333e"
            self.meter.create_rectangle(x1, top, x2, bottom, fill=color, outline="")
        self.root.after(40, self._animate_meter)

    def _drain_events(self) -> None:
        while True:
            try:
                event, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if event == "receiver":
                self._handle_receiver_line(str(payload))
            elif event == "exit":
                return_code = int(payload)
                self.process = None
                if not self.quit_requested:
                    self._set_stopped()
                    if return_code:
                        self._append_log(f"O receptor encerrou com código {return_code}.")
            elif event == "usb":
                success, detail = payload  # type: ignore[misc]
                self.usb_button.configure(state="normal")
                if success:
                    self.usb_ready = True
                    self.usb_status.set("USB configurado")
                    self.detail.set("Conecte o USB e inicie o microfone no celular.")
                    self._append_log("USB pronto. No Android, selecione USB e inicie o microfone.")
                else:
                    self.usb_ready = False
                    self.usb_status.set("USB não configurado")
                    self._append_log(f"Falha ao configurar USB: {detail}")
        if self.quit_requested:
            if self.process is None or self.process.poll() is not None:
                self.root.destroy()
                return
            if self.close_started_at and time.monotonic() - self.close_started_at > 4:
                self.process.kill()
        self.root.after(100, self._drain_events)

    def quit_application(self) -> None:
        """Explicitly stop the receiver before exiting the desktop app."""
        self.quit_requested = True
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
