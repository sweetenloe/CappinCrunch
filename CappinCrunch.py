import json
import math
import os
import shlex
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk


APP_TITLE = "CappinCrunch"
PROFILE_PATH = os.path.expanduser("~/.cappincrunch_profiles.json")


def check_ac_power():
    base = "/sys/class/power_supply"
    if not os.path.isdir(base):
        return None
    try:
        for name in os.listdir(base):
            power_path = os.path.join(base, name)
            type_path = os.path.join(power_path, "type")
            online_path = os.path.join(power_path, "online")
            if not os.path.isfile(type_path) or not os.path.isfile(online_path):
                continue
            try:
                with open(type_path, "r", encoding="ascii") as f:
                    ptype = f.read().strip()
                if ptype != "Mains":
                    continue
                with open(online_path, "r", encoding="ascii") as f:
                    online = f.read().strip()
                if online == "1":
                    return True
                if online == "0":
                    return False
            except OSError:
                continue
    except OSError:
        return None
    return None


def which_crunch():
    return shutil.which("crunch")


class CappinCrunchApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("900x680")
        self.minsize(840, 620)

        self.mode_var = tk.StringVar(value="charset")
        self.allow_battery_var = tk.BooleanVar(value=False)
        self.post_cmd_var = tk.StringVar()
        self.profile_name_var = tk.StringVar()
        self.profile_select_var = tk.StringVar()
        self.charset_choice_var = tk.StringVar()
        self.charset_custom_var = tk.StringVar()
        self.pattern_choice_var = tk.StringVar()
        self.pattern_custom_var = tk.StringVar()
        self.smart_mode_var = tk.BooleanVar(value=False)
        self.combine_keywords_var = tk.BooleanVar(value=False)

        self.charset_presets = [
            ("Lowercase (a-z)", "abcdefghijklmnopqrstuvwxyz"),
            ("Uppercase (A-Z)", "ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
            ("Digits (0-9)", "0123456789"),
            ("Lower + Upper", "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"),
            ("Lower + Digits", "abcdefghijklmnopqrstuvwxyz0123456789"),
            ("Upper + Digits", "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"),
            ("Alpha (a-zA-Z)", "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"),
            ("Alphanumeric (a-zA-Z0-9)", "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"),
            ("Hex (0-9a-f)", "0123456789abcdef"),
            ("Hex (0-9A-F)", "0123456789ABCDEF"),
            ("Symbols (common)", "!@#$%^&*()-_=+[]{};:,.?/"),
            ("All (alpha+digits+symbols)", "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+[]{};:,.?/"),
            ("Custom", None),
        ]
        self.pattern_presets = [
            ("None (no pattern)", ""),
            ("Lowercase (@)", "@"),
            ("Uppercase (,)", ","),
            ("Digits (%)", "%"),
            ("Symbols (^)", "^"),
            ("Lower+Digits (@@%%)", "@@%%"),
            ("Upper+Digits (,,%%)", ",,%%"),
            ("Alpha (,,@@)", ",,@@"),
            ("Alpha+Digits (,,@@%%)", ",,@@%%"),
            ("Lower+Upper+Digits (@@,,%%)", "@@,,%%"),
            ("Custom", None),
        ]

        self.charset_choice_var.set("Lowercase (a-z)")
        self.charset_custom_var.set("abcdefghijklmnopqrstuvwxyz")
        self.pattern_choice_var.set("None (no pattern)")
        self.pattern_custom_var.set("")

        self.profiles = {}
        self._build_ui()
        self._load_profiles()
        self._set_mode_state()
        self._update_command_preview()

    def _build_ui(self):
        container = ttk.Frame(self)
        container.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        canvas = tk.Canvas(container, highlightthickness=0)
        vscroll = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        root = ttk.Frame(canvas, padding=12)
        root_id = canvas.create_window((0, 0), window=root, anchor="nw")

        def on_root_configure(_event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_configure(event):
            canvas.itemconfigure(root_id, width=event.width)

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        root.bind("<Configure>", on_root_configure)
        canvas.bind("<Configure>", on_canvas_configure)
        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", on_mousewheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        settings = ttk.LabelFrame(root, text="Crunch Settings", padding=10)
        settings.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        settings.columnconfigure(1, weight=1)

        mode_frame = ttk.Frame(settings)
        mode_frame.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        ttk.Label(mode_frame, text="Mode:").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            mode_frame,
            text="Charset generation",
            variable=self.mode_var,
            value="charset",
            command=self._on_mode_change,
        ).grid(row=0, column=1, padx=8)
        ttk.Radiobutton(
            mode_frame,
            text="Custom dictionary (permutations)",
            variable=self.mode_var,
            value="custom",
            command=self._on_mode_change,
        ).grid(row=0, column=2, padx=8)

        ttk.Label(settings, text="Min length:").grid(row=1, column=0, sticky="w")
        self.min_entry = ttk.Entry(settings, width=10)
        self.min_entry.insert(0, "8")
        self.min_entry.grid(row=1, column=1, sticky="w")

        ttk.Label(settings, text="Max length:").grid(row=1, column=2, sticky="w")
        self.max_entry = ttk.Entry(settings, width=10)
        self.max_entry.insert(0, "12")
        self.max_entry.grid(row=1, column=3, sticky="w")

        ttk.Label(settings, text="Charset:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.charset_combo = ttk.Combobox(
            settings,
            textvariable=self.charset_choice_var,
            values=[label for label, _value in self.charset_presets],
            state="readonly",
            width=28,
        )
        self.charset_combo.grid(row=2, column=1, sticky="w", pady=(6, 0))
        self.charset_entry = ttk.Entry(settings, textvariable=self.charset_custom_var)
        self.charset_entry.grid(row=2, column=2, columnspan=2, sticky="ew", pady=(6, 0), padx=(6, 0))

        ttk.Label(settings, text="Pattern (-t):").grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.pattern_combo = ttk.Combobox(
            settings,
            textvariable=self.pattern_choice_var,
            values=[label for label, _value in self.pattern_presets],
            state="readonly",
            width=28,
        )
        self.pattern_combo.grid(row=3, column=1, sticky="w", pady=(6, 0))
        self.pattern_entry = ttk.Entry(settings, textvariable=self.pattern_custom_var)
        self.pattern_entry.grid(row=3, column=2, columnspan=2, sticky="ew", pady=(6, 0), padx=(6, 0))

        custom_frame = ttk.LabelFrame(root, text="Custom Dictionary Words", padding=10)
        custom_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        custom_frame.columnconfigure(0, weight=1)
        custom_frame.rowconfigure(0, weight=1)
        self.custom_text = tk.Text(custom_frame, height=6, wrap="word")
        self.custom_text.grid(row=0, column=0, sticky="nsew")
        custom_hint = ttk.Label(
            custom_frame,
            text="Provide words separated by spaces or newlines. Crunch uses -p to permute these words.",
        )
        custom_hint.grid(row=1, column=0, sticky="w", pady=(6, 0))
        options_frame = ttk.Frame(custom_frame)
        options_frame.grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.smart_mode_chk = ttk.Checkbutton(
            options_frame,
            text="Smart mode (add prefix/suffix from charset)",
            variable=self.smart_mode_var,
            command=self._on_smart_mode_toggle,
        )
        self.smart_mode_chk.grid(row=0, column=0, sticky="w")
        self.combine_keywords_chk = ttk.Checkbutton(
            options_frame,
            text="Combine keywords",
            variable=self.combine_keywords_var,
            command=self._update_command_preview,
        )
        self.combine_keywords_chk.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.load_words_btn = ttk.Button(
            custom_frame, text="Load words from file", command=self._load_words_from_file
        )
        self.load_words_btn.grid(row=3, column=0, sticky="w", pady=(6, 0))

        exec_frame = ttk.LabelFrame(root, text="Execution", padding=10)
        exec_frame.grid(row=2, column=0, sticky="ew", padx=4, pady=4)
        exec_frame.columnconfigure(1, weight=1)
        ttk.Label(exec_frame, text="Post command:").grid(row=0, column=0, sticky="w")
        self.post_cmd_entry = ttk.Entry(exec_frame, textvariable=self.post_cmd_var)
        self.post_cmd_entry.grid(row=0, column=1, sticky="ew")
        ttk.Label(exec_frame, text="Use {wordlist} placeholder.").grid(
            row=0, column=2, sticky="w", padx=(6, 0)
        )

        self.allow_battery_chk = ttk.Checkbutton(
            exec_frame,
            text="Allow running on battery power",
            variable=self.allow_battery_var,
        )
        self.allow_battery_chk.grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))

        profile_frame = ttk.LabelFrame(root, text="Profiles", padding=10)
        profile_frame.grid(row=3, column=0, sticky="ew", padx=4, pady=4)
        profile_frame.columnconfigure(1, weight=1)
        ttk.Label(profile_frame, text="Profile name:").grid(row=0, column=0, sticky="w")
        self.profile_name_entry = ttk.Entry(profile_frame, textvariable=self.profile_name_var)
        self.profile_name_entry.grid(row=0, column=1, sticky="ew")
        ttk.Button(profile_frame, text="Save Profile", command=self._save_profile).grid(
            row=0, column=2, padx=(6, 0)
        )
        ttk.Label(profile_frame, text="Load profile:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.profile_combo = ttk.Combobox(
            profile_frame, textvariable=self.profile_select_var, state="readonly"
        )
        self.profile_combo.grid(row=1, column=1, sticky="ew", pady=(6, 0))
        ttk.Button(profile_frame, text="Load", command=self._load_profile).grid(
            row=1, column=2, padx=(6, 0), pady=(6, 0)
        )

        preview_frame = ttk.LabelFrame(root, text="Crunch Command Preview", padding=10)
        preview_frame.grid(row=4, column=0, sticky="ew", padx=4, pady=4)
        preview_frame.columnconfigure(0, weight=1)
        self.preview_label = ttk.Label(preview_frame, text="", foreground="#4b4b4b")
        self.preview_label.grid(row=0, column=0, sticky="w")
        self.estimate_label = ttk.Label(preview_frame, text="", foreground="#4b4b4b")
        self.estimate_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

        output_frame = ttk.LabelFrame(root, text="Output File", padding=10)
        output_frame.grid(row=5, column=0, sticky="ew", padx=4, pady=4)
        output_frame.columnconfigure(1, weight=1)
        ttk.Label(output_frame, text="Output file:").grid(row=0, column=0, sticky="w")
        self.output_entry = ttk.Entry(output_frame)
        self.output_entry.grid(row=0, column=1, sticky="ew")
        ttk.Button(output_frame, text="Browse", command=self._browse_output).grid(
            row=0, column=2, sticky="e", padx=(6, 0)
        )

        action_frame = ttk.Frame(root)
        action_frame.grid(row=6, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(action_frame, text="Run Crunch", command=self._on_run).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(action_frame, text="Dry Run", command=self._on_dry_run).grid(
            row=0, column=1, sticky="w", padx=6
        )
        ttk.Button(action_frame, text="Clear Log", command=self._clear_log).grid(
            row=0, column=2, sticky="w", padx=6
        )

        log_frame = ttk.LabelFrame(root, text="Log Output", padding=10)
        log_frame.grid(row=7, column=0, sticky="nsew", padx=4, pady=4)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=12, state="disabled", wrap="word")
        self.log_text.grid(row=0, column=0, sticky="nsew")

        root.rowconfigure(7, weight=1)

        for widget in (
            self.min_entry,
            self.max_entry,
            self.charset_entry,
            self.pattern_entry,
            self.output_entry,
            self.custom_text,
        ):
            widget.bind("<KeyRelease>", lambda _e: self._update_command_preview())
        self.charset_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_charset_choice())
        self.pattern_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_pattern_choice())
        self.post_cmd_entry.bind("<KeyRelease>", lambda _e: self._update_command_preview())

    def _browse_output(self):
        path = filedialog.asksaveasfilename(
            title="Select output wordlist file",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, path)
            self._update_command_preview()

    def _on_mode_change(self):
        self._set_mode_state()
        self._update_command_preview()

    def _set_mode_state(self):
        is_custom = self.mode_var.get() == "custom"
        state = "disabled" if is_custom else "normal"
        for entry in (self.min_entry, self.max_entry):
            entry.configure(state=state)
        self.custom_text.configure(state="normal" if is_custom else "disabled")
        self.load_words_btn.configure(state="normal" if is_custom else "disabled")
        self.smart_mode_chk.configure(state="normal" if is_custom else "disabled")
        self.combine_keywords_chk.configure(state="normal" if is_custom else "disabled")
        self._refresh_charset_state()
        self._refresh_pattern_state()

    def _on_charset_choice(self):
        self._refresh_charset_state()
        self._update_command_preview()

    def _on_pattern_choice(self):
        self._refresh_pattern_state()
        self._update_command_preview()

    def _on_smart_mode_toggle(self):
        self._refresh_charset_state()
        self._update_command_preview()

    def _preset_value(self, presets, label):
        for preset_label, value in presets:
            if preset_label == label:
                return value
        return None

    def _find_preset_label(self, presets, value):
        for preset_label, preset_value in presets:
            if preset_value == value:
                return preset_label
        return "Custom"

    def _refresh_charset_state(self):
        if self.mode_var.get() == "custom":
            if not self.smart_mode_var.get():
                self.charset_combo.configure(state="disabled")
                self.charset_entry.configure(state="disabled")
                return
        self.charset_combo.configure(state="readonly")
        value = self._preset_value(self.charset_presets, self.charset_choice_var.get())
        if value is None:
            self.charset_entry.configure(state="normal")
            return
        self.charset_custom_var.set(value)
        self.charset_entry.configure(state="disabled")

    def _refresh_pattern_state(self):
        if self.mode_var.get() == "custom":
            self.pattern_combo.configure(state="disabled")
            self.pattern_entry.configure(state="disabled")
            return
        self.pattern_combo.configure(state="readonly")
        value = self._preset_value(self.pattern_presets, self.pattern_choice_var.get())
        if value is None:
            self.pattern_entry.configure(state="normal")
            return
        self.pattern_custom_var.set(value)
        self.pattern_entry.configure(state="disabled")

    def _append_log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")

    def _load_words_from_file(self):
        path = filedialog.askopenfilename(
            title="Select a wordlist file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = f.read()
        except OSError as exc:
            messagebox.showerror(APP_TITLE, f"Failed to load file: {exc}")
            return
        self.custom_text.configure(state="normal")
        self.custom_text.delete("1.0", tk.END)
        self.custom_text.insert(tk.END, data)
        self._update_command_preview()

    def _update_command_preview(self):
        if self._smart_enabled():
            self.preview_label.configure(text="Smart mode will generate a wordlist directly.")
        else:
            cmd = self._build_command(preview_only=True)
            if cmd is None:
                self.preview_label.configure(text="Fill required fields to preview command.")
                self.estimate_label.configure(text="")
                return
            self.preview_label.configure(text=" ".join(shlex.quote(part) for part in cmd))
        estimate = self._estimate_wordlist()
        self.estimate_label.configure(text=estimate or "")

    def _validate_power(self):
        if self.allow_battery_var.get():
            return True
        status = check_ac_power()
        if status is True:
            return True
        if status is False:
            messagebox.showerror(
                APP_TITLE,
                "AC power not detected. Plug in the device or enable 'Allow running on battery power'.",
            )
            return False
        answer = messagebox.askyesno(
            APP_TITLE,
            "Unable to detect AC power state. Proceed anyway?",
        )
        return answer

    def _ensure_crunch(self):
        if which_crunch():
            return True
        install = messagebox.askyesno(
            APP_TITLE,
            "Crunch is not installed. Install it now using apt-get?",
        )
        if not install:
            return False

        self._append_log("Crunch not found. Attempting installation via apt-get...")
        if shutil.which("pkexec"):
            install_cmd = ["pkexec", "apt-get", "install", "-y", "crunch"]
        elif shutil.which("sudo"):
            install_cmd = ["sudo", "apt-get", "install", "-y", "crunch"]
        else:
            messagebox.showerror(
                APP_TITLE,
                "No privilege escalation tool found (pkexec or sudo). Install crunch manually.",
            )
            return False

        try:
            result = subprocess.run(
                install_cmd,
                capture_output=True,
                text=True,
                check=False,
            )
            self._append_log(result.stdout.strip())
            if result.stderr.strip():
                self._append_log(result.stderr.strip())
            if result.returncode != 0:
                messagebox.showerror(
                    APP_TITLE,
                    "Crunch installation failed. Check the log for details.",
                )
                return False
        except OSError as exc:
            messagebox.showerror(APP_TITLE, f"Installation failed: {exc}")
            return False
        return which_crunch() is not None

    def _load_profiles(self):
        self.profiles = {}
        if not os.path.isfile(PROFILE_PATH):
            self.profile_combo["values"] = []
            return
        try:
            with open(PROFILE_PATH, "r", encoding="ascii") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self.profiles = data
        except (OSError, json.JSONDecodeError):
            self._append_log("Warning: could not load profiles file.")
        self.profile_combo["values"] = sorted(self.profiles.keys())

    def _save_profiles_file(self):
        try:
            with open(PROFILE_PATH, "w", encoding="ascii") as f:
                json.dump(self.profiles, f, indent=2, sort_keys=True)
        except OSError as exc:
            messagebox.showerror(APP_TITLE, f"Failed to save profile: {exc}")

    def _save_profile(self):
        name = self.profile_name_var.get().strip()
        if not name:
            messagebox.showerror(APP_TITLE, "Profile name is required.")
            return
        self.profiles[name] = self._collect_settings()
        self._save_profiles_file()
        self._load_profiles()
        self.profile_select_var.set(name)
        self._append_log(f"Saved profile '{name}'.")

    def _load_profile(self):
        name = self.profile_select_var.get().strip()
        if not name:
            messagebox.showerror(APP_TITLE, "Select a profile to load.")
            return
        data = self.profiles.get(name)
        if not isinstance(data, dict):
            messagebox.showerror(APP_TITLE, "Profile data is invalid.")
            return
        self._apply_settings(data)
        self._append_log(f"Loaded profile '{name}'.")
        self._update_command_preview()

    def _collect_settings(self):
        return {
            "mode": self.mode_var.get(),
            "min_len": self.min_entry.get().strip(),
            "max_len": self.max_entry.get().strip(),
            "charset": self._get_charset(),
            "charset_choice": self.charset_choice_var.get(),
            "pattern": self._get_pattern(),
            "pattern_choice": self.pattern_choice_var.get(),
            "output": self.output_entry.get().strip(),
            "custom_words": self.custom_text.get("1.0", tk.END).strip(),
            "post_cmd": self.post_cmd_var.get().strip(),
            "allow_battery": bool(self.allow_battery_var.get()),
            "smart_mode": bool(self.smart_mode_var.get()),
            "combine_keywords": bool(self.combine_keywords_var.get()),
        }

    def _apply_settings(self, data):
        self.mode_var.set(data.get("mode", "charset"))
        self._set_mode_state()
        self._set_entry(self.min_entry, data.get("min_len", ""))
        self._set_entry(self.max_entry, data.get("max_len", ""))
        charset_value = data.get("charset", "")
        charset_choice = data.get("charset_choice")
        if charset_choice not in [label for label, _value in self.charset_presets]:
            charset_choice = self._find_preset_label(self.charset_presets, charset_value)
        self.charset_choice_var.set(charset_choice)
        self.charset_custom_var.set(charset_value)

        pattern_value = data.get("pattern", "")
        pattern_choice = data.get("pattern_choice")
        if pattern_choice not in [label for label, _value in self.pattern_presets]:
            pattern_choice = self._find_preset_label(self.pattern_presets, pattern_value)
        self.pattern_choice_var.set(pattern_choice)
        self.pattern_custom_var.set(pattern_value)

        self.smart_mode_var.set(bool(data.get("smart_mode", False)))
        self.combine_keywords_var.set(bool(data.get("combine_keywords", False)))
        self._refresh_charset_state()
        self._refresh_pattern_state()
        self._set_entry(self.output_entry, data.get("output", ""))
        self.custom_text.configure(state="normal")
        self.custom_text.delete("1.0", tk.END)
        self.custom_text.insert(tk.END, data.get("custom_words", ""))
        if self.mode_var.get() != "custom":
            self.custom_text.configure(state="disabled")
        self.post_cmd_var.set(data.get("post_cmd", ""))
        self.allow_battery_var.set(bool(data.get("allow_battery", False)))

    def _set_entry(self, entry, value):
        entry.configure(state="normal")
        entry.delete(0, tk.END)
        entry.insert(0, value)

    def _parse_int(self, value, field):
        try:
            return int(value)
        except ValueError:
            raise ValueError(f"{field} must be an integer.")

    def _get_charset(self):
        value = self._preset_value(self.charset_presets, self.charset_choice_var.get())
        if value is None:
            return self.charset_custom_var.get().strip()
        return value

    def _get_pattern(self):
        value = self._preset_value(self.pattern_presets, self.pattern_choice_var.get())
        if value is None:
            return self.pattern_custom_var.get().strip()
        return value

    def _smart_enabled(self):
        return self.mode_var.get() == "custom" and self.smart_mode_var.get()

    def _expanded_keywords(self, words):
        if not self.combine_keywords_var.get():
            return words
        separators = ["", "_", "-"]
        combined = []
        seen = set()
        for word in words:
            if word not in seen:
                combined.append(word)
                seen.add(word)
        for first in words:
            for second in words:
                if first == second:
                    continue
                for sep in separators:
                    candidate = f"{first}{sep}{second}"
                    if candidate not in seen:
                        combined.append(candidate)
                        seen.add(candidate)
        return combined

    def _estimate_smart_total(self, keywords, charset):
        base = len(charset) + 1
        return len(keywords) * base * base

    def _confirm_cap(self, estimate):
        answer = messagebox.askyesno(
            APP_TITLE,
            f"This will generate about {self._format_count(estimate)} entries.\n"
            "Would you like to cap the number of generated entries?",
        )
        if not answer:
            return None
        cap = simpledialog.askinteger(
            APP_TITLE,
            "Enter a maximum number of entries to generate:",
            minvalue=1,
        )
        return cap

    def _build_command(self, preview_only=False):
        output_path = self.output_entry.get().strip()
        if not output_path:
            output_path = os.path.join(os.getcwd(), "namethisoutput.txt")
            if not preview_only:
                self._set_entry(self.output_entry, output_path)
        output_dir = os.path.dirname(output_path) or "."
        if not os.path.isdir(output_dir):
            return None if preview_only else self._error("Output directory does not exist.")

        if self.mode_var.get() == "custom":
            words_raw = self.custom_text.get("1.0", tk.END).strip()
            if not words_raw:
                return None if preview_only else self._error("Provide at least one word.")
            words = [w for w in words_raw.split() if w]
            cmd = ["crunch", "1", "1", "-p"] + words + ["-o", output_path]
            return cmd

        min_len = self.min_entry.get().strip()
        max_len = self.max_entry.get().strip()
        charset = self._get_charset()
        pattern = self._get_pattern()

        if not min_len or not max_len:
            return None if preview_only else self._error("Min and max lengths are required.")
        if not charset:
            return None if preview_only else self._error("Charset is required.")

        try:
            min_val = self._parse_int(min_len, "Min length")
            max_val = self._parse_int(max_len, "Max length")
        except ValueError as exc:
            return None if preview_only else self._error(str(exc))

        if min_val <= 0 or max_val <= 0:
            return None if preview_only else self._error("Lengths must be positive.")
        if min_val > max_val:
            return None if preview_only else self._error("Min length cannot exceed max length.")

        cmd = ["crunch", str(min_val), str(max_val), charset]
        if pattern:
            cmd += ["-t", pattern]
            if not preview_only and (len(pattern) < min_val or len(pattern) > max_val):
                pat_len = len(pattern)
                fix = messagebox.askyesno(
                    APP_TITLE,
                    f"Pattern length ({pat_len}) is outside Min/Max ({min_val}-{max_val}).\n"
                    "Fix Min/Max to match the pattern length?",
                )
                if not fix:
                    return self._error("Pattern length must be within Min/Max.")
                self._set_entry(self.min_entry, str(pat_len))
                self._set_entry(self.max_entry, str(pat_len))
                min_val = pat_len
                max_val = pat_len
                cmd = ["crunch", str(min_val), str(max_val), charset, "-t", pattern]
        cmd += ["-o", output_path]
        return cmd

    def _estimate_wordlist(self):
        try:
            if self.mode_var.get() == "custom":
                words_raw = self.custom_text.get("1.0", tk.END).strip()
                words = [w for w in words_raw.split() if w]
                if not words:
                    return None
                if self._smart_enabled():
                    charset = self._get_charset()
                    if not charset:
                        return None
                    words = self._expanded_keywords(words)
                    estimate = self._estimate_smart_total(words, charset)
                    return f"Estimated entries: {self._format_count(estimate)} (smart mode)"
                count = math.factorial(len(words))
                return f"Estimated entries: {self._format_count(count)} (permutations of {len(words)} words)"

            min_len = self.min_entry.get().strip()
            max_len = self.max_entry.get().strip()
            charset = self._get_charset()
            pattern = self._get_pattern()
            if not min_len or not max_len or not charset:
                return None
            min_val = self._parse_int(min_len, "Min length")
            max_val = self._parse_int(max_len, "Max length")
            if min_val <= 0 or max_val <= 0 or min_val > max_val:
                return None

            if pattern:
                if len(pattern) == 0:
                    return None
                estimate = self._estimate_from_pattern(pattern, charset)
                if estimate is None:
                    return "Estimated entries: unavailable (pattern too complex)"
                return f"Estimated entries: {self._format_count(estimate)} (pattern-based)"

            base = len(charset)
            total = 0
            for length in range(min_val, max_val + 1):
                total += base ** length
            return f"Estimated entries: {self._format_count(total)}"
        except (ValueError, OverflowError):
            return "Estimated entries: unavailable (check inputs)"

    def _estimate_from_pattern(self, pattern, charset):
        counts = []
        base = len(charset)
        for ch in pattern:
            if ch == "@":
                counts.append(base)
            elif ch == "%":
                counts.append(10)
            elif ch == ",":
                counts.append(33)
            elif ch == "^":
                counts.append(1)
            else:
                counts.append(1)
        try:
            total = 1
            for count in counts:
                total *= count
            return total
        except OverflowError:
            return None

    def _format_count(self, count):
        for suffix, limit in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
            if count >= limit:
                return f"{count / limit:.2f}{suffix}"
        return str(count)

    def _error(self, message):
        messagebox.showerror(APP_TITLE, message)
        return None

    def _run_subprocess(self, cmd, on_done):
        def worker():
            self._append_log(f"Running: {' '.join(shlex.quote(c) for c in cmd)}")
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
            except OSError as exc:
                self._append_log(f"Failed to start: {exc}")
                on_done(False)
                return

            if process.stdout:
                for line in process.stdout:
                    self._append_log(line.rstrip())

            return_code = process.wait()
            if return_code != 0:
                self._append_log(f"Process exited with code {return_code}.")
                on_done(False)
                return
            on_done(True)

        threading.Thread(target=worker, daemon=True).start()

    def _on_run(self):
        if not self._validate_power():
            return
        if self._smart_enabled():
            if not self._run_smart_generation():
                return
            return
        if not self._ensure_crunch():
            return
        cmd = self._build_command()
        if not cmd:
            return

        def after_crunch(success):
            if not success:
                return
            post_cmd = self.post_cmd_var.get().strip()
            if not post_cmd:
                self._append_log("Crunch completed successfully.")
                return
            wordlist_path = self.output_entry.get().strip()
            expanded = post_cmd.replace("{wordlist}", wordlist_path)
            try:
                post_args = shlex.split(expanded)
            except ValueError as exc:
                self._append_log(f"Post command parse error: {exc}")
                return
            self._run_subprocess(post_args, lambda ok: self._append_log("Post command done." if ok else "Post command failed."))

        self._run_subprocess(cmd, after_crunch)

    def _on_dry_run(self):
        if self._smart_enabled():
            estimate = self._estimate_wordlist()
            self._append_log("Dry run only. Smart mode would generate a wordlist directly.")
            if estimate:
                self._append_log(estimate)
            return
        cmd = self._build_command()
        if not cmd:
            return
        self._append_log("Dry run only. No commands executed.")
        self._append_log(f"Would run: {' '.join(shlex.quote(c) for c in cmd)}")
        estimate = self._estimate_wordlist()
        if estimate:
            self._append_log(estimate)

    def _run_smart_generation(self):
        output_path = self.output_entry.get().strip()
        if not output_path:
            output_path = os.path.join(os.getcwd(), "namethisoutput.txt")
            self._set_entry(self.output_entry, output_path)
        output_dir = os.path.dirname(output_path) or "."
        if not os.path.isdir(output_dir):
            self._error("Output directory does not exist.")
            return False

        words_raw = self.custom_text.get("1.0", tk.END).strip()
        if not words_raw:
            self._error("Provide at least one word.")
            return False
        charset = self._get_charset()
        if not charset:
            self._error("Charset is required for smart mode.")
            return False

        base_words = [w for w in words_raw.split() if w]
        keywords = self._expanded_keywords(base_words)
        estimate = self._estimate_smart_total(keywords, charset)
        cap = None
        if estimate > 100000:
            cap = self._confirm_cap(estimate)
            if cap is None:
                pass

        prefixes = [""] + list(charset)
        suffixes = [""] + list(charset)
        count = 0
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                for word in keywords:
                    for pre in prefixes:
                        for suf in suffixes:
                            f.write(f"{pre}{word}{suf}\n")
                            count += 1
                            if cap and count >= cap:
                                self._append_log(
                                    f"Smart mode capped at {self._format_count(cap)} entries."
                                )
                                self._append_log(f"Saved wordlist to: {output_path}")
                                return True
        except OSError as exc:
            self._error(f"Failed to write output: {exc}")
            return False

        self._append_log(f"Smart mode generated {self._format_count(count)} entries.")
        self._append_log(f"Saved wordlist to: {output_path}")
        post_cmd = self.post_cmd_var.get().strip()
        if post_cmd:
            expanded = post_cmd.replace("{wordlist}", output_path)
            try:
                post_args = shlex.split(expanded)
            except ValueError as exc:
                self._append_log(f"Post command parse error: {exc}")
                return True
            self._run_subprocess(
                post_args,
                lambda ok: self._append_log("Post command done." if ok else "Post command failed."),
            )
        return True


if __name__ == "__main__":
    app = CappinCrunchApp()
    app.mainloop()
