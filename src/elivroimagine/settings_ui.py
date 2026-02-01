"""Settings window using tkinter."""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Callable

from .config import Config
from .transcriber import Transcriber


class SettingsWindow:
    """Settings window for ElivroImagine."""

    def __init__(
        self,
        config: Config,
        on_save: Callable[[Config], None],
    ) -> None:
        """Initialize settings window.

        Args:
            config: Current configuration.
            on_save: Callback when settings are saved.
        """
        self.config = config
        self.on_save = on_save
        self._window: tk.Tk | None = None
        self._hotkey_var: tk.StringVar | None = None
        self._mode_var: tk.StringVar | None = None
        self._model_var: tk.StringVar | None = None
        self._folder_var: tk.StringVar | None = None
        self._startup_var: tk.BooleanVar | None = None
        self._capturing_hotkey = False
        self._captured_keys: set[str] = set()

    def show(self) -> None:
        """Show the settings window."""
        if self._window is not None:
            self._window.lift()
            self._window.focus_force()
            return

        self._window = tk.Tk()
        self._window.title("ElivroImagine Settings")
        self._window.geometry("500x400")
        self._window.resizable(False, False)

        # Configure grid
        self._window.columnconfigure(0, weight=1)

        # Create main frame with padding
        main_frame = ttk.Frame(self._window, padding="20")
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.columnconfigure(1, weight=1)

        row = 0

        # Title
        title_label = ttk.Label(
            main_frame,
            text="ElivroImagine Settings",
            font=("Segoe UI", 14, "bold"),
        )
        title_label.grid(row=row, column=0, columnspan=2, pady=(0, 20))
        row += 1

        # Hotkey section
        hotkey_label = ttk.Label(main_frame, text="Hotkey:")
        hotkey_label.grid(row=row, column=0, sticky="w", pady=5)

        self._hotkey_var = tk.StringVar(value=self.config.hotkey.combination)
        hotkey_frame = ttk.Frame(main_frame)
        hotkey_frame.grid(row=row, column=1, sticky="ew", pady=5)
        hotkey_frame.columnconfigure(0, weight=1)

        self._hotkey_entry = ttk.Entry(
            hotkey_frame,
            textvariable=self._hotkey_var,
            state="readonly",
        )
        self._hotkey_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        capture_btn = ttk.Button(
            hotkey_frame,
            text="Capture",
            command=self._start_hotkey_capture,
            width=10,
        )
        capture_btn.grid(row=0, column=1)
        row += 1

        # Mode section
        mode_label = ttk.Label(main_frame, text="Recording Mode:")
        mode_label.grid(row=row, column=0, sticky="w", pady=5)

        self._mode_var = tk.StringVar(value=self.config.hotkey.mode)
        mode_frame = ttk.Frame(main_frame)
        mode_frame.grid(row=row, column=1, sticky="w", pady=5)

        hold_radio = ttk.Radiobutton(
            mode_frame,
            text="Hold (release to stop)",
            variable=self._mode_var,
            value="hold",
        )
        hold_radio.pack(side="left", padx=(0, 20))

        toggle_radio = ttk.Radiobutton(
            mode_frame,
            text="Toggle (press again to stop)",
            variable=self._mode_var,
            value="toggle",
        )
        toggle_radio.pack(side="left")
        row += 1

        # Whisper model section
        model_label = ttk.Label(main_frame, text="Whisper Model:")
        model_label.grid(row=row, column=0, sticky="w", pady=5)

        self._model_var = tk.StringVar(value=self.config.whisper.model_size)
        model_frame = ttk.Frame(main_frame)
        model_frame.grid(row=row, column=1, sticky="ew", pady=5)
        model_frame.columnconfigure(0, weight=1)

        model_combo = ttk.Combobox(
            model_frame,
            textvariable=self._model_var,
            values=Transcriber.get_available_models(),
            state="readonly",
            width=15,
        )
        model_combo.grid(row=0, column=0, sticky="w")

        # Model info label
        self._model_info_label = ttk.Label(
            model_frame,
            text="",
            font=("Segoe UI", 9),
            foreground="gray",
        )
        self._model_info_label.grid(row=0, column=1, padx=(10, 0))
        self._update_model_info()
        model_combo.bind("<<ComboboxSelected>>", lambda e: self._update_model_info())
        row += 1

        # Storage folder section
        folder_label = ttk.Label(main_frame, text="Storage Folder:")
        folder_label.grid(row=row, column=0, sticky="w", pady=5)

        self._folder_var = tk.StringVar(value=self.config.storage.transcriptions_dir)
        folder_frame = ttk.Frame(main_frame)
        folder_frame.grid(row=row, column=1, sticky="ew", pady=5)
        folder_frame.columnconfigure(0, weight=1)

        folder_entry = ttk.Entry(folder_frame, textvariable=self._folder_var)
        folder_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        browse_btn = ttk.Button(
            folder_frame,
            text="Browse",
            command=self._browse_folder,
            width=10,
        )
        browse_btn.grid(row=0, column=1)
        row += 1

        # Start with Windows section
        self._startup_var = tk.BooleanVar(value=self.config.startup.start_with_windows)
        startup_check = ttk.Checkbutton(
            main_frame,
            text="Start with Windows",
            variable=self._startup_var,
        )
        startup_check.grid(row=row, column=0, columnspan=2, sticky="w", pady=10)
        row += 1

        # Separator
        separator = ttk.Separator(main_frame, orient="horizontal")
        separator.grid(row=row, column=0, columnspan=2, sticky="ew", pady=20)
        row += 1

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, sticky="e")

        cancel_btn = ttk.Button(
            button_frame,
            text="Cancel",
            command=self._cancel,
            width=10,
        )
        cancel_btn.pack(side="left", padx=(0, 10))

        save_btn = ttk.Button(
            button_frame,
            text="Save",
            command=self._save,
            width=10,
        )
        save_btn.pack(side="left")

        # Handle window close
        self._window.protocol("WM_DELETE_WINDOW", self._cancel)

        # Center window on screen
        self._window.update_idletasks()
        width = self._window.winfo_width()
        height = self._window.winfo_height()
        x = (self._window.winfo_screenwidth() // 2) - (width // 2)
        y = (self._window.winfo_screenheight() // 2) - (height // 2)
        self._window.geometry(f"{width}x{height}+{x}+{y}")

        self._window.mainloop()

    def _update_model_info(self) -> None:
        """Update model info label."""
        if self._model_var and self._model_info_label:
            model = self._model_var.get()
            info = Transcriber.get_model_info(model)  # type: ignore
            self._model_info_label.config(text=f"({info['size']}, {info['speed']})")

    def _start_hotkey_capture(self) -> None:
        """Start capturing a new hotkey."""
        if self._window is None or self._hotkey_var is None:
            return

        self._capturing_hotkey = True
        self._captured_keys = set()
        self._hotkey_var.set("Press keys...")

        # Bind key events
        self._window.bind("<KeyPress>", self._on_key_press)
        self._window.bind("<KeyRelease>", self._on_key_release)
        self._window.focus_force()

    def _on_key_press(self, event: tk.Event) -> str:
        """Handle key press during capture."""
        if not self._capturing_hotkey:
            return "break"

        key = self._event_to_key(event)
        if key:
            self._captured_keys.add(key)
            self._update_hotkey_display()

        return "break"

    def _on_key_release(self, event: tk.Event) -> str:
        """Handle key release during capture."""
        if not self._capturing_hotkey:
            return "break"

        # Stop capturing when a non-modifier key is released
        if event.keysym not in ("Control_L", "Control_R", "Alt_L", "Alt_R", "Shift_L", "Shift_R"):
            self._capturing_hotkey = False
            if self._window:
                self._window.unbind("<KeyPress>")
                self._window.unbind("<KeyRelease>")

        return "break"

    def _event_to_key(self, event: tk.Event) -> str | None:
        """Convert tkinter event to pynput-style key string."""
        keysym = event.keysym

        # Map special keys
        key_map = {
            "Control_L": "<ctrl>",
            "Control_R": "<ctrl>",
            "Alt_L": "<alt>",
            "Alt_R": "<alt>",
            "Shift_L": "<shift>",
            "Shift_R": "<shift>",
        }

        if keysym in key_map:
            return key_map[keysym]
        elif len(keysym) == 1:
            return keysym.lower()
        elif keysym.startswith("F") and keysym[1:].isdigit():
            return f"<{keysym.lower()}>"

        return None

    def _update_hotkey_display(self) -> None:
        """Update the hotkey display during capture."""
        if not self._hotkey_var:
            return

        # Sort keys: modifiers first, then regular keys
        modifiers = []
        regular = []

        for key in self._captured_keys:
            if key in ("<ctrl>", "<alt>", "<shift>"):
                modifiers.append(key)
            else:
                regular.append(key)

        # Standard modifier order
        ordered_modifiers = []
        for mod in ["<ctrl>", "<alt>", "<shift>"]:
            if mod in modifiers:
                ordered_modifiers.append(mod)

        combination = "+".join(ordered_modifiers + regular)
        self._hotkey_var.set(combination or "Press keys...")

    def _browse_folder(self) -> None:
        """Open folder browser dialog."""
        if self._window is None or self._folder_var is None:
            return

        current = Path(self._folder_var.get()).expanduser()
        if not current.exists():
            current = Path.home()

        folder = filedialog.askdirectory(
            parent=self._window,
            initialdir=str(current),
            title="Select Transcriptions Folder",
        )

        if folder:
            self._folder_var.set(folder)

    def _save(self) -> None:
        """Save settings and close window."""
        if (
            self._hotkey_var is None
            or self._mode_var is None
            or self._model_var is None
            or self._folder_var is None
            or self._startup_var is None
        ):
            return

        # Update config
        self.config.hotkey.combination = self._hotkey_var.get()
        self.config.hotkey.mode = self._mode_var.get()  # type: ignore
        self.config.whisper.model_size = self._model_var.get()  # type: ignore
        self.config.storage.transcriptions_dir = self._folder_var.get()
        self.config.startup.start_with_windows = self._startup_var.get()

        # Save and notify
        self.config.save()
        self.on_save(self.config)

        self._close()

    def _cancel(self) -> None:
        """Cancel and close window."""
        self._close()

    def _close(self) -> None:
        """Close the window."""
        if self._window:
            self._window.destroy()
            self._window = None
