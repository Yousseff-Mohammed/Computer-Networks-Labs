import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import logging

# Local modules
from send_email    import send_email
from receive_email import fetch_latest_email, print_email

# Plyer for desktop notifications
try:
    from plyer import notification as plyer_notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False
    logging.warning("plyer not installed – push notifications disabled.  "
                    "Install with: pip install plyer")

log = logging.getLogger(__name__)

# Notification helper
def _push_notification(title: str, message: str) -> None:
    if PLYER_AVAILABLE:
        plyer_notification.notify(
            title          = title,
            message        = message[:256],          # Plyer truncates long msgs
            app_name       = "CCE Email Client",
            timeout        = 8,                       # seconds
        )
    else:
        log.info("Push notification (plyer unavailable): %s – %s", title, message)


# Background polling thread
class MailPoller(threading.Thread):
    def __init__(self, config_getter, on_new_mail, interval: int = 30):
        super().__init__(daemon=True)
        self._config_getter = config_getter   # callable → dict of IMAP config
        self._on_new_mail   = on_new_mail     # callback(email_dict)
        self._interval      = interval
        self._last_subject  = None
        self._running       = True

    def stop(self):
        self._running = False

    def run(self):
        while self._running:
            try:
                cfg = self._config_getter()
                if cfg:
                    result = fetch_latest_email(**cfg)
                    if result:
                        subject = result["subject"]
                        if subject != self._last_subject:
                            self._last_subject = subject
                            self._on_new_mail(result)
            except Exception as exc:
                log.error("Poller error: %s", exc)
            time.sleep(self._interval)

# Main application window
class EmailClientApp(tk.Tk):
    DEFAULT_SMTP_HOST = "smtp.gmail.com"
    DEFAULT_SMTP_PORT = 587
    DEFAULT_IMAP_HOST = "imap.gmail.com"
    DEFAULT_IMAP_PORT = 993

    def __init__(self):
        super().__init__()
        self.title("Email Client")
        self.geometry("820x680")
        self.resizable(True, True)
        self._configure_style()
        self._build_ui()

        # Background poller (starts when user clicks "Start Polling")
        self._poller: MailPoller | None = None

    # Style
    def _configure_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook.Tab", padding=[12, 6], font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("TLabel",  font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"))

    # UI construction
    def _build_ui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._build_send_tab(nb)
        self._build_receive_tab(nb)
        self._build_settings_tab(nb)

        # Status bar
        self._status_var = tk.StringVar(value="Ready.")
        ttk.Label(self, textvariable=self._status_var,
                  relief=tk.SUNKEN, anchor=tk.W).pack(
            fill=tk.X, side=tk.BOTTOM, padx=10, pady=(0, 5))

    # Send tab
    def _build_send_tab(self, nb: ttk.Notebook):
        frame = ttk.Frame(nb, padding=15)
        nb.add(frame, text="✉  Send")

        fields = [
            ("From (your e-mail):", "send_from"),
            ("Password:",           "send_pass"),
            ("To (recipient):",     "send_to"),
            ("Subject:",            "send_subj"),
        ]

        self._send_vars: dict[str, tk.StringVar] = {}

        for row, (label, key) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=4)
            var = tk.StringVar()
            self._send_vars[key] = var
            show = "*" if key == "send_pass" else ""
            ttk.Entry(frame, textvariable=var, show=show, width=50).grid(
                row=row, column=1, sticky=tk.EW, padx=(10, 0), pady=4)

        # Body
        r = len(fields)
        ttk.Label(frame, text="Body:").grid(row=r, column=0, sticky=tk.NW, pady=4)
        self._send_body = scrolledtext.ScrolledText(frame, width=50, height=10,
                                                     font=("Consolas", 10))
        self._send_body.grid(row=r, column=1, sticky=tk.NSEW, padx=(10, 0), pady=4)

        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(r, weight=1)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=r+1, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_frame, text="Send E-Mail", command=self._on_send).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Clear", command=self._clear_send).pack(side=tk.LEFT, padx=5)

    # Receive tab

    def _build_receive_tab(self, nb: ttk.Notebook):
        frame = ttk.Frame(nb, padding=15)
        nb.add(frame, text="📥  Receive")

        top = ttk.Frame(frame)
        top.pack(fill=tk.X)

        fields = [
            ("E-Mail:",   "recv_email"),
            ("Password:", "recv_pass"),
        ]
        self._recv_vars: dict[str, tk.StringVar] = {}

        for col, (label, key) in enumerate(fields):
            ttk.Label(top, text=label).grid(row=0, column=col*2, sticky=tk.W, padx=(0 if col==0 else 15, 0))
            var = tk.StringVar()
            self._recv_vars[key] = var
            show = "*" if key == "recv_pass" else ""
            ttk.Entry(top, textvariable=var, show=show, width=28).grid(row=0, column=col*2+1, sticky=tk.EW, padx=(5, 0))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=8)
        ttk.Button(btn_frame, text="Fetch Latest E-Mail", command=self._on_receive).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Start Auto-Poll (30 s)", command=self._on_start_poll).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Stop Polling", command=self._on_stop_poll).pack(side=tk.LEFT, padx=5)

        # Headers display
        hdr_frame = ttk.LabelFrame(frame, text="Headers", padding=8)
        hdr_frame.pack(fill=tk.X, pady=(0, 8))
        self._hdr_vars = {}
        for i, lbl in enumerate(["From", "To", "Subject", "Date"]):
            ttk.Label(hdr_frame, text=f"{lbl}:").grid(row=i, column=0, sticky=tk.W, pady=2)
            v = tk.StringVar()
            self._hdr_vars[lbl.lower()] = v
            ttk.Label(hdr_frame, textvariable=v, wraplength=550, justify=tk.LEFT).grid(
                row=i, column=1, sticky=tk.W, padx=(10, 0))

        # Body display
        body_frame = ttk.LabelFrame(frame, text="Body", padding=8)
        body_frame.pack(fill=tk.BOTH, expand=True)
        self._recv_body = scrolledtext.ScrolledText(body_frame, font=("Consolas", 10),
                                                     state=tk.DISABLED)
        self._recv_body.pack(fill=tk.BOTH, expand=True)

    # Settings tab
    def _build_settings_tab(self, nb: ttk.Notebook):
        frame = ttk.Frame(nb, padding=15)
        nb.add(frame, text="⚙  Settings")

        ttk.Label(frame, text="SMTP Settings", style="Header.TLabel").grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 6))

        smtp_fields = [("SMTP Host:", "smtp_host"), ("SMTP Port:", "smtp_port")]
        imap_fields = [("IMAP Host:", "imap_host"), ("IMAP Port:", "imap_port")]

        self._settings_vars: dict[str, tk.StringVar] = {}

        defaults = {
            "smtp_host": self.DEFAULT_SMTP_HOST,
            "smtp_port": str(self.DEFAULT_SMTP_PORT),
            "imap_host": self.DEFAULT_IMAP_HOST,
            "imap_port": str(self.DEFAULT_IMAP_PORT),
        }

        def add_fields(fields, start_row):
            for i, (label, key) in enumerate(fields):
                ttk.Label(frame, text=label).grid(row=start_row+i, column=0, sticky=tk.W, pady=4)
                var = tk.StringVar(value=defaults[key])
                self._settings_vars[key] = var
                ttk.Entry(frame, textvariable=var, width=35).grid(
                    row=start_row+i, column=1, sticky=tk.W, padx=(10, 0), pady=4)

        add_fields(smtp_fields, 1)
        ttk.Label(frame, text="IMAP Settings", style="Header.TLabel").grid(
            row=4, column=0, columnspan=2, sticky=tk.W, pady=(12, 6))
        add_fields(imap_fields, 5)

        ttk.Label(frame, text="Use STARTTLS for SMTP (port 587):",
                  ).grid(row=8, column=0, sticky=tk.W, pady=4)
        self._use_tls = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, variable=self._use_tls).grid(row=8, column=1, sticky=tk.W, padx=(10,0))

        ttk.Button(frame, text="Save Settings", command=self._save_settings).grid(
            row=9, column=0, columnspan=2, pady=12)

    # Event handlers
    def _on_send(self):
        v = self._send_vars
        sender   = v["send_from"].get().strip()
        password = v["send_pass"].get()
        to       = v["send_to"].get().strip()
        subject  = v["send_subj"].get().strip()
        body     = self._send_body.get("1.0", tk.END).strip()

        if not all([sender, password, to, subject, body]):
            messagebox.showwarning("Missing Fields", "Please fill in all fields before sending.")
            return

        smtp_host = self._settings_vars["smtp_host"].get().strip()
        smtp_port = int(self._settings_vars["smtp_port"].get().strip())
        use_tls   = self._use_tls.get()

        self._set_status("Sending…")
        threading.Thread(
            target=self._send_worker,
            args=(smtp_host, smtp_port, sender, password, to, subject, body, use_tls),
            daemon=True,
        ).start()

    def _send_worker(self, smtp_host, smtp_port, sender, password, to, subject, body, use_tls):
        ok = send_email(smtp_host, smtp_port, sender, password, to, subject, body, use_tls)
        self.after(0, self._send_complete, ok)

    def _send_complete(self, ok: bool):
        if ok:
            self._set_status("E-mail sent successfully.")
            messagebox.showinfo("Success", "E-mail sent successfully!")
        else:
            self._set_status("Failed to send e-mail.")
            messagebox.showerror("Error", "Failed to send e-mail.\nCheck credentials and server settings.")

    def _on_receive(self):
        cfg = self._build_imap_config()
        if cfg is None:
            return
        self._set_status("Fetching latest e-mail…")
        threading.Thread(target=self._receive_worker, args=(cfg,), daemon=True).start()

    def _receive_worker(self, cfg: dict):
        result = fetch_latest_email(**cfg)
        self.after(0, self._receive_complete, result)

    def _receive_complete(self, result: dict | None):
        if result:
            self._display_email(result)
            self._set_status(f'Latest e-mail fetched: "{result["subject"]}"')
        else:
            self._set_status("Could not fetch e-mail.")
            messagebox.showerror("Error", "Could not fetch e-mail.\nCheck credentials and server settings.")

    def _on_start_poll(self):
        cfg = self._build_imap_config()
        if cfg is None:
            return
        if self._poller and self._poller.is_alive():
            messagebox.showinfo("Polling", "Polling is already running.")
            return
        self._poller = MailPoller(
            config_getter=lambda: self._build_imap_config(silent=True),
            on_new_mail=self._on_new_mail_arrived,
            interval=30,
        )
        self._poller.start()
        self._set_status("📡 Polling started (every 30 s).")

    def _on_stop_poll(self):
        if self._poller:
            self._poller.stop()
            self._poller = None
        self._set_status("Polling stopped.")

    def _on_new_mail_arrived(self, email_dict: dict):
        # Update UI from main thread
        self.after(0, self._display_email, email_dict)
        self.after(0, self._set_status, f'📬 New e-mail: "{email_dict['subject']}"')
        # Push notification
        _push_notification(
            title   = f"New e-mail from {email_dict['from'][:40]}",
            message = email_dict["subject"],
        )

    def _clear_send(self):
        for v in self._send_vars.values():
            v.set("")
        self._send_body.delete("1.0", tk.END)

    def _save_settings(self):
        self._set_status("Settings saved.")
        messagebox.showinfo("Settings", "Settings saved.")

    # Helpers
    def _build_imap_config(self, silent: bool = False) -> dict | None:
        email_addr = self._recv_vars["recv_email"].get().strip()
        password   = self._recv_vars["recv_pass"].get()
        imap_host  = self._settings_vars["imap_host"].get().strip()
        imap_port  = self._settings_vars["imap_port"].get().strip()

        if not all([email_addr, password]):
            if not silent:
                messagebox.showwarning("Missing Fields", "Enter your e-mail and password in the Receive tab.")
            return None

        return dict(
            imap_host     = imap_host,
            imap_port     = int(imap_port),
            email_address = email_addr,
            password      = password,
        )

    def _display_email(self, email_dict: dict):
        for key in ("from", "to", "subject", "date"):
            self._hdr_vars[key].set(email_dict.get(key, ""))
        self._recv_body.configure(state=tk.NORMAL)
        self._recv_body.delete("1.0", tk.END)
        self._recv_body.insert(tk.END, email_dict.get("body", ""))
        self._recv_body.configure(state=tk.DISABLED)

    def _set_status(self, msg: str):
        self._status_var.set(msg)


# Entry point
if __name__ == "__main__":
    app = EmailClientApp()
    app.mainloop()