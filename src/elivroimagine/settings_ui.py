"""Settings window using tkinter."""

import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

import keyboard
from PIL import Image, ImageTk

from .config import SUPPORTED_LANGUAGES, Config
from .recorder import AudioRecorder
from .transcriber import Transcriber

logger = logging.getLogger(__name__)


class SettingsWindow:
    """Settings window for ElivroImagine."""

    # Dark mode color palette
    _BG = "#12141c"
    _SURFACE = "#1a1d28"
    _TEXT = "#e2e4ea"
    _TEXT_DIM = "#6b7084"
    _ACCENT = "#4ecdc4"
    _ACCENT_HOVER = "#3db8b0"
    _INPUT_BG = "#0d0f16"
    _BORDER = "#262a36"
    _FIELD_BORDER = "#323847"

    def __init__(
        self,
        config: Config,
        on_save: Callable[[Config], None],
        on_capture_state_changed: Callable[[bool], None] | None = None,
    ) -> None:
        """Initialize settings window.

        Args:
            config: Current configuration.
            on_save: Callback when settings are saved.
            on_capture_state_changed: Callback when hotkey capture starts/stops.
                                       Called with True when capture starts, False when it ends.
        """
        self.config = config
        self.on_save = on_save
        self.on_capture_state_changed = on_capture_state_changed
        self._window: tk.Tk | None = None
        self._hotkey_var: tk.StringVar | None = None
        self._mode_var: tk.StringVar | None = None
        self._model_var: tk.StringVar | None = None
        self._lang_var: tk.StringVar | None = None
        self._folder_var: tk.StringVar | None = None
        self._startup_var: tk.BooleanVar | None = None
        self._mic_var: tk.StringVar | None = None
        self._sound_enabled_var: tk.BooleanVar | None = None
        self._start_vol_var: tk.DoubleVar | None = None
        self._stop_vol_var: tk.DoubleVar | None = None
        self._paste_enabled_var: tk.BooleanVar | None = None
        self._paste_hotkey_var: tk.StringVar | None = None
        self._paste_mode_var: tk.StringVar | None = None
        self._paste_restore_var: tk.BooleanVar | None = None
        self._available_mics: list[dict[str, str]] = []
        self._capturing_hotkey = False
        self._capture_target: tk.StringVar | None = None  # which var to update
        self._captured_keys: set[str] = set()
        self._captured_scan_code: int | None = None  # scan code of main key
        self._save_hotkey_scan_code: int | None = None  # stored scan code for save hotkey
        self._paste_hotkey_scan_code: int | None = None  # stored scan code for paste hotkey
        self._model_info_label: ttk.Label | None = None
        self._backend_var: tk.StringVar | None = None
        self._api_key_var: tk.StringVar | None = None
        self._local_only_widgets: list[tk.Widget] = []
        self._berget_only_widgets: list[tk.Widget] = []
        self._icon_photo: ImageTk.PhotoImage | None = None  # Keep reference
        self._dt_enabled_var: tk.BooleanVar | None = None
        self._dt_api_key_var: tk.StringVar | None = None
        self._dt_email_var: tk.StringVar | None = None
        self._dt_project_var: tk.StringVar | None = None
        self._dthk_enabled_var: tk.BooleanVar | None = None
        self._dthk_hotkey_var: tk.StringVar | None = None
        self._dthk_mode_var: tk.StringVar | None = None
        self._dthk_project_var: tk.StringVar | None = None
        self._dthk_hotkey_scan_code: int | None = None

    def _set_window_icon(self) -> None:
        """Set the window icon from assets (uses .ico with white circle background)."""
        if self._window is None:
            return

        try:
            ico_path = Path(__file__).parent / "assets" / "icon.ico"
            if ico_path.exists():
                self._window.iconbitmap(str(ico_path))
        except Exception:
            pass  # Silently fail if icon can't be loaded

    def _configure_styles(self) -> None:
        """Configure ttk styles for dark mode."""
        style = ttk.Style()
        style.theme_use("clam")

        # Base defaults for all widgets
        style.configure(
            ".",
            background=self._BG,
            foreground=self._TEXT,
            fieldbackground=self._INPUT_BG,
            bordercolor=self._BORDER,
            darkcolor=self._BG,
            lightcolor=self._BG,
            troughcolor=self._SURFACE,
            selectbackground=self._ACCENT,
            selectforeground=self._BG,
            font=("Segoe UI", 10),
        )

        style.configure("TFrame", background=self._BG)
        style.configure("TLabel", background=self._BG, foreground=self._TEXT)

        style.configure(
            "TLabelframe",
            background=self._BG,
            bordercolor=self._BORDER,
            padding=(10, 8),
        )
        style.configure(
            "TLabelframe.Label",
            background=self._BG,
            foreground=self._ACCENT,
            font=("Segoe UI", 10, "bold"),
        )

        style.configure(
            "TButton",
            background=self._SURFACE,
            foreground=self._TEXT,
            bordercolor=self._FIELD_BORDER,
            font=("Segoe UI", 10),
            padding=(8, 4),
        )
        style.map(
            "TButton",
            background=[("active", self._BORDER), ("pressed", self._BORDER)],
        )

        # Accent style for Save button
        style.configure(
            "Accent.TButton",
            background=self._ACCENT,
            foreground=self._BG,
            bordercolor=self._ACCENT,
            font=("Segoe UI", 10, "bold"),
            padding=(8, 4),
        )
        style.map(
            "Accent.TButton",
            background=[
                ("active", self._ACCENT_HOVER),
                ("pressed", self._ACCENT_HOVER),
            ],
        )

        style.configure(
            "TEntry",
            fieldbackground=self._INPUT_BG,
            foreground=self._TEXT,
            bordercolor=self._FIELD_BORDER,
            insertcolor=self._TEXT,
        )
        style.map(
            "TEntry",
            fieldbackground=[("readonly", self._SURFACE)],
            bordercolor=[("focus", self._ACCENT)],
        )

        style.configure(
            "TCombobox",
            fieldbackground=self._INPUT_BG,
            foreground=self._TEXT,
            background=self._SURFACE,
            bordercolor=self._FIELD_BORDER,
            arrowcolor=self._TEXT_DIM,
            font=("Segoe UI", 10),
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", self._INPUT_BG)],
            bordercolor=[("focus", self._ACCENT)],
            arrowcolor=[("active", self._ACCENT)],
        )

        style.configure(
            "TCheckbutton",
            background=self._BG,
            foreground=self._TEXT,
            indicatorbackground=self._INPUT_BG,
            indicatorcolor=self._FIELD_BORDER,
            font=("Segoe UI", 10),
        )
        style.map(
            "TCheckbutton",
            background=[("active", self._BG)],
            indicatorbackground=[("selected", self._ACCENT)],
            indicatorcolor=[("selected", self._BG)],
        )

        style.configure(
            "TRadiobutton",
            background=self._BG,
            foreground=self._TEXT,
            indicatorbackground=self._INPUT_BG,
            indicatorcolor=self._FIELD_BORDER,
            font=("Segoe UI", 10),
        )
        style.map(
            "TRadiobutton",
            background=[("active", self._BG)],
            indicatorbackground=[("selected", self._ACCENT)],
            indicatorcolor=[("selected", self._BG)],
        )

        style.configure(
            "Horizontal.TScale",
            background=self._BG,
            troughcolor=self._SURFACE,
            bordercolor=self._BORDER,
        )
        style.map(
            "Horizontal.TScale",
            background=[("active", self._ACCENT)],
        )

        style.configure(
            "Vertical.TScrollbar",
            background=self._SURFACE,
            troughcolor=self._BG,
            bordercolor=self._BG,
            arrowcolor=self._TEXT_DIM,
        )
        style.map(
            "Vertical.TScrollbar",
            background=[("active", self._BORDER)],
        )

        style.configure("TSeparator", background=self._BORDER)

        # Hint label style
        style.configure(
            "Hint.TLabel",
            background=self._BG,
            foreground=self._TEXT_DIM,
            font=("Segoe UI", 9),
        )

        # Title style
        style.configure(
            "Title.TLabel",
            background=self._BG,
            foreground=self._ACCENT,
            font=("Segoe UI", 14, "bold"),
        )

    def show(self) -> None:
        """Show the settings window."""
        if self._window is not None:
            self._window.lift()
            self._window.focus_force()
            return

        # Initialize scan codes from config
        self._save_hotkey_scan_code = self.config.hotkey.scan_code
        self._paste_hotkey_scan_code = self.config.paste_hotkey.scan_code
        self._dthk_hotkey_scan_code = self.config.devtracker_hotkey.scan_code

        self._window = tk.Tk()
        self._window.title("ElivroImagine Settings")
        self._window.geometry("550x700")
        self._window.minsize(550, 400)
        self._window.resizable(False, True)
        self._window.configure(bg=self._BG)

        # Set window icon
        self._set_window_icon()

        self._configure_styles()

        # Dark combobox dropdown list
        self._window.option_add("*TCombobox*Listbox.background", self._INPUT_BG)
        self._window.option_add("*TCombobox*Listbox.foreground", self._TEXT)
        self._window.option_add("*TCombobox*Listbox.selectBackground", self._ACCENT)
        self._window.option_add("*TCombobox*Listbox.selectForeground", self._BG)

        # Configure root grid
        self._window.rowconfigure(0, weight=0)  # title
        self._window.rowconfigure(1, weight=1)  # scrollable content
        self._window.rowconfigure(2, weight=0)  # button bar
        self._window.columnconfigure(0, weight=1)

        # Title (outside scroll area)
        title_label = ttk.Label(
            self._window,
            text="ElivroImagine Settings",
            style="Title.TLabel",
        )
        title_label.grid(row=0, column=0, pady=(20, 10))

        # Scrollable area
        scroll_frame = ttk.Frame(self._window)
        scroll_frame.grid(row=1, column=0, sticky="nsew")
        scroll_frame.rowconfigure(0, weight=1)
        scroll_frame.columnconfigure(0, weight=1)

        canvas = tk.Canvas(scroll_frame, highlightthickness=0, borderwidth=0, bg=self._BG)
        scrollbar = ttk.Scrollbar(
            scroll_frame, orient="vertical", command=canvas.yview
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Inner frame that holds all the LabelFrame groups
        inner_frame = ttk.Frame(canvas, padding=(20, 0, 20, 10))
        canvas_window = canvas.create_window(
            (0, 0), window=inner_frame, anchor="nw"
        )

        def _on_configure(event: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        inner_frame.bind("<Configure>", _on_configure)

        def _on_canvas_configure(event: tk.Event) -> None:
            canvas.itemconfigure(canvas_window, width=event.width)

        canvas.bind("<Configure>", _on_canvas_configure)

        # Mousewheel scrolling
        def _on_mousewheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Make inner_frame expand to fill width
        inner_frame.columnconfigure(0, weight=1)

        group_row = 0

        # --- Save Hotkey group ---
        save_hk_frame = ttk.LabelFrame(inner_frame, text="Save Hotkey (voice to file)")
        save_hk_frame.grid(
            row=group_row, column=0, sticky="ew", pady=(0, 10)
        )
        save_hk_frame.columnconfigure(1, weight=1)

        ttk.Label(save_hk_frame, text="Hotkey:").grid(
            row=0, column=0, sticky="w", pady=4, padx=(0, 10)
        )

        self._hotkey_var = tk.StringVar(value=self.config.hotkey.combination)
        hotkey_inner = ttk.Frame(save_hk_frame)
        hotkey_inner.grid(row=0, column=1, sticky="ew", pady=4)
        hotkey_inner.columnconfigure(0, weight=1)

        self._hotkey_entry = ttk.Entry(
            hotkey_inner, textvariable=self._hotkey_var, state="readonly"
        )
        self._hotkey_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        ttk.Button(
            hotkey_inner,
            text="Capture",
            command=lambda: self._start_hotkey_capture(self._hotkey_var),
            width=10,
        ).grid(row=0, column=1)

        ttk.Label(save_hk_frame, text="Mode:").grid(
            row=1, column=0, sticky="w", pady=4, padx=(0, 10)
        )

        self._mode_var = tk.StringVar(value=self.config.hotkey.mode)
        mode_frame = ttk.Frame(save_hk_frame)
        mode_frame.grid(row=1, column=1, sticky="w", pady=4)

        ttk.Radiobutton(
            mode_frame,
            text="Hold (release to stop)",
            variable=self._mode_var,
            value="hold",
        ).pack(side="left", padx=(0, 20))

        ttk.Radiobutton(
            mode_frame,
            text="Toggle (press again to stop)",
            variable=self._mode_var,
            value="toggle",
        ).pack(side="left")

        group_row += 1

        # --- Paste Hotkey group ---
        paste_hk_frame = ttk.LabelFrame(inner_frame, text="Paste Hotkey (voice to clipboard)")
        paste_hk_frame.grid(
            row=group_row, column=0, sticky="ew", pady=(0, 10)
        )
        paste_hk_frame.columnconfigure(1, weight=1)

        self._paste_enabled_var = tk.BooleanVar(
            value=self.config.paste_hotkey.enabled
        )
        ttk.Checkbutton(
            paste_hk_frame,
            text="Enable paste hotkey (record + paste into focused field)",
            variable=self._paste_enabled_var,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=4)

        ttk.Label(paste_hk_frame, text="Hotkey:").grid(
            row=1, column=0, sticky="w", pady=4, padx=(0, 10)
        )

        self._paste_hotkey_var = tk.StringVar(
            value=self.config.paste_hotkey.combination
        )
        paste_hk_inner = ttk.Frame(paste_hk_frame)
        paste_hk_inner.grid(row=1, column=1, sticky="ew", pady=4)
        paste_hk_inner.columnconfigure(0, weight=1)

        self._paste_hotkey_entry = ttk.Entry(
            paste_hk_inner,
            textvariable=self._paste_hotkey_var,
            state="readonly",
        )
        self._paste_hotkey_entry.grid(
            row=0, column=0, sticky="ew", padx=(0, 5)
        )

        ttk.Button(
            paste_hk_inner,
            text="Capture",
            command=lambda: self._start_hotkey_capture(self._paste_hotkey_var),
            width=10,
        ).grid(row=0, column=1)

        ttk.Label(paste_hk_frame, text="Mode:").grid(
            row=2, column=0, sticky="w", pady=4, padx=(0, 10)
        )

        self._paste_mode_var = tk.StringVar(
            value=self.config.paste_hotkey.mode
        )
        paste_mode_frame = ttk.Frame(paste_hk_frame)
        paste_mode_frame.grid(row=2, column=1, sticky="w", pady=4)

        ttk.Radiobutton(
            paste_mode_frame,
            text="Hold",
            variable=self._paste_mode_var,
            value="hold",
        ).pack(side="left", padx=(0, 20))

        ttk.Radiobutton(
            paste_mode_frame,
            text="Toggle",
            variable=self._paste_mode_var,
            value="toggle",
        ).pack(side="left")

        self._paste_restore_var = tk.BooleanVar(
            value=self.config.paste_hotkey.restore_clipboard
        )
        ttk.Checkbutton(
            paste_hk_frame,
            text="Restore clipboard after paste",
            variable=self._paste_restore_var,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=4)

        group_row += 1

        # --- Transcription group ---
        trans_frame = ttk.LabelFrame(inner_frame, text="Transcription")
        trans_frame.grid(
            row=group_row, column=0, sticky="ew", pady=(0, 10)
        )
        trans_frame.columnconfigure(1, weight=1)

        trans_row = 0

        # Backend selector
        ttk.Label(trans_frame, text="Backend:").grid(
            row=trans_row, column=0, sticky="w", pady=4, padx=(0, 10)
        )

        backend_display = {
            "local": "Local (Whisper)",
            "berget": "Berget.ai API",
        }
        current_backend = self.config.transcription.backend
        self._backend_var = tk.StringVar(
            value=backend_display.get(current_backend, "Local (Whisper)")
        )
        backend_combo = ttk.Combobox(
            trans_frame,
            textvariable=self._backend_var,
            values=list(backend_display.values()),
            state="readonly",
            width=20,
        )
        backend_combo.grid(row=trans_row, column=1, sticky="w", pady=4)
        backend_combo.bind(
            "<<ComboboxSelected>>", lambda e: self._on_backend_changed()
        )
        trans_row += 1

        # API Key field (Berget only)
        api_key_label = ttk.Label(trans_frame, text="API Key:")
        api_key_label.grid(
            row=trans_row, column=0, sticky="w", pady=4, padx=(0, 10)
        )
        self._berget_only_widgets.append(api_key_label)

        self._api_key_var = tk.StringVar(
            value=self.config.transcription.berget_api_key
        )
        api_key_entry = ttk.Entry(
            trans_frame,
            textvariable=self._api_key_var,
            show="*",
            width=40,
        )
        api_key_entry.grid(row=trans_row, column=1, sticky="w", pady=4)
        self._berget_only_widgets.append(api_key_entry)
        trans_row += 1

        # Whisper Model (Local only)
        model_label = ttk.Label(trans_frame, text="Whisper Model:")
        model_label.grid(
            row=trans_row, column=0, sticky="w", pady=4, padx=(0, 10)
        )
        self._local_only_widgets.append(model_label)

        self._model_var = tk.StringVar(value=self.config.whisper.model_size)
        model_inner = ttk.Frame(trans_frame)
        model_inner.grid(row=trans_row, column=1, sticky="ew", pady=4)
        self._local_only_widgets.append(model_inner)

        model_combo = ttk.Combobox(
            model_inner,
            textvariable=self._model_var,
            values=Transcriber.get_available_models(),
            state="readonly",
            width=15,
        )
        model_combo.pack(side="left")

        self._model_info_label = ttk.Label(
            model_inner, text="", style="Hint.TLabel"
        )
        self._model_info_label.pack(side="left", padx=(10, 0))
        self._update_model_info()
        model_combo.bind(
            "<<ComboboxSelected>>", lambda e: self._update_model_info()
        )
        trans_row += 1

        # Language (shown for both backends)
        ttk.Label(trans_frame, text="Language:").grid(
            row=trans_row, column=0, sticky="w", pady=4, padx=(0, 10)
        )

        lang_display_values = [name for _, name in SUPPORTED_LANGUAGES]
        current_lang_name = "English"
        for code, name in SUPPORTED_LANGUAGES:
            if code == self.config.whisper.language:
                current_lang_name = name
                break

        self._lang_var = tk.StringVar(value=current_lang_name)
        ttk.Combobox(
            trans_frame,
            textvariable=self._lang_var,
            values=lang_display_values,
            state="readonly",
            width=15,
        ).grid(row=trans_row, column=1, sticky="w", pady=4)

        # Apply initial visibility based on current backend
        self._on_backend_changed()

        group_row += 1

        # --- Audio group ---
        audio_frame = ttk.LabelFrame(inner_frame, text="Audio")
        audio_frame.grid(
            row=group_row, column=0, sticky="ew", pady=(0, 10)
        )
        audio_frame.columnconfigure(1, weight=1)

        ttk.Label(audio_frame, text="Microphone:").grid(
            row=0, column=0, sticky="w", pady=4, padx=(0, 10)
        )

        self._available_mics = AudioRecorder.get_available_microphones()
        mic_names = ["System Default"] + [
            m["name"] for m in self._available_mics
        ]

        current_mic_name = "System Default"
        if self.config.recording.microphone_id:
            for mic in self._available_mics:
                if mic["id"] == self.config.recording.microphone_id:
                    current_mic_name = mic["name"]
                    break

        self._mic_var = tk.StringVar(value=current_mic_name)
        ttk.Combobox(
            audio_frame,
            textvariable=self._mic_var,
            values=mic_names,
            state="readonly",
            width=40,
        ).grid(row=0, column=1, sticky="w", pady=4)

        group_row += 1

        # --- Storage group ---
        storage_frame = ttk.LabelFrame(inner_frame, text="Storage")
        storage_frame.grid(
            row=group_row, column=0, sticky="ew", pady=(0, 10)
        )
        storage_frame.columnconfigure(1, weight=1)

        ttk.Label(storage_frame, text="Folder:").grid(
            row=0, column=0, sticky="w", pady=4, padx=(0, 10)
        )

        self._folder_var = tk.StringVar(
            value=self.config.storage.transcriptions_dir
        )
        folder_inner = ttk.Frame(storage_frame)
        folder_inner.grid(row=0, column=1, sticky="ew", pady=4)
        folder_inner.columnconfigure(0, weight=1)

        ttk.Entry(folder_inner, textvariable=self._folder_var).grid(
            row=0, column=0, sticky="ew", padx=(0, 5)
        )

        ttk.Button(
            folder_inner,
            text="Browse",
            command=self._browse_folder,
            width=10,
        ).grid(row=0, column=1)

        group_row += 1

        # --- DevTracker Integration group ---
        dt_frame = ttk.LabelFrame(inner_frame, text="DevTracker Connection")
        dt_frame.grid(
            row=group_row, column=0, sticky="ew", pady=(0, 10)
        )
        dt_frame.columnconfigure(1, weight=1)

        self._dt_enabled_var = tk.BooleanVar(
            value=self.config.devtracker.enabled
        )
        ttk.Checkbutton(
            dt_frame,
            text="Enable DevTracker (save hotkey creates tasks instead of files)",
            variable=self._dt_enabled_var,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=4)

        ttk.Label(dt_frame, text="API Key:").grid(
            row=1, column=0, sticky="w", pady=4, padx=(0, 10)
        )
        self._dt_api_key_var = tk.StringVar(
            value=self.config.devtracker.api_key
        )
        ttk.Entry(
            dt_frame,
            textvariable=self._dt_api_key_var,
            show="*",
            width=40,
        ).grid(row=1, column=1, sticky="w", pady=4)

        ttk.Label(dt_frame, text="Email:").grid(
            row=2, column=0, sticky="w", pady=4, padx=(0, 10)
        )
        self._dt_email_var = tk.StringVar(
            value=self.config.devtracker.email
        )
        ttk.Entry(
            dt_frame,
            textvariable=self._dt_email_var,
            width=40,
        ).grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(dt_frame, text="Project:").grid(
            row=3, column=0, sticky="w", pady=4, padx=(0, 10)
        )
        self._dt_project_var = tk.StringVar(
            value=self.config.devtracker.project
        )
        dt_project_inner = ttk.Frame(dt_frame)
        dt_project_inner.grid(row=3, column=1, sticky="ew", pady=4)
        dt_project_inner.columnconfigure(0, weight=1)

        ttk.Entry(
            dt_project_inner,
            textvariable=self._dt_project_var,
            width=20,
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(
            dt_project_inner,
            text='e.g. "elivro"',
            style="Hint.TLabel",
        ).grid(row=0, column=1, padx=(10, 0))

        group_row += 1

        # --- DevTracker Hotkey group ---
        dthk_frame = ttk.LabelFrame(inner_frame, text="DevTracker Hotkey (project task)")
        dthk_frame.grid(
            row=group_row, column=0, sticky="ew", pady=(0, 10)
        )
        dthk_frame.columnconfigure(1, weight=1)

        self._dthk_enabled_var = tk.BooleanVar(
            value=self.config.devtracker_hotkey.enabled
        )
        ttk.Checkbutton(
            dthk_frame,
            text="Enable separate hotkey for creating tasks in a specific project",
            variable=self._dthk_enabled_var,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=4)

        ttk.Label(dthk_frame, text="Hotkey:").grid(
            row=1, column=0, sticky="w", pady=4, padx=(0, 10)
        )

        self._dthk_hotkey_var = tk.StringVar(
            value=self.config.devtracker_hotkey.combination
        )
        dthk_hk_inner = ttk.Frame(dthk_frame)
        dthk_hk_inner.grid(row=1, column=1, sticky="ew", pady=4)
        dthk_hk_inner.columnconfigure(0, weight=1)

        self._dthk_hotkey_entry = ttk.Entry(
            dthk_hk_inner,
            textvariable=self._dthk_hotkey_var,
            state="readonly",
        )
        self._dthk_hotkey_entry.grid(
            row=0, column=0, sticky="ew", padx=(0, 5)
        )

        ttk.Button(
            dthk_hk_inner,
            text="Capture",
            command=lambda: self._start_hotkey_capture(self._dthk_hotkey_var),
            width=10,
        ).grid(row=0, column=1)

        ttk.Label(dthk_frame, text="Mode:").grid(
            row=2, column=0, sticky="w", pady=4, padx=(0, 10)
        )

        self._dthk_mode_var = tk.StringVar(
            value=self.config.devtracker_hotkey.mode
        )
        dthk_mode_frame = ttk.Frame(dthk_frame)
        dthk_mode_frame.grid(row=2, column=1, sticky="w", pady=4)

        ttk.Radiobutton(
            dthk_mode_frame,
            text="Hold",
            variable=self._dthk_mode_var,
            value="hold",
        ).pack(side="left", padx=(0, 20))

        ttk.Radiobutton(
            dthk_mode_frame,
            text="Toggle",
            variable=self._dthk_mode_var,
            value="toggle",
        ).pack(side="left")

        ttk.Label(dthk_frame, text="Project:").grid(
            row=3, column=0, sticky="w", pady=4, padx=(0, 10)
        )

        self._dthk_project_var = tk.StringVar(
            value=self.config.devtracker_hotkey.project
        )
        dthk_proj_inner = ttk.Frame(dthk_frame)
        dthk_proj_inner.grid(row=3, column=1, sticky="ew", pady=4)
        dthk_proj_inner.columnconfigure(0, weight=1)

        ttk.Entry(
            dthk_proj_inner,
            textvariable=self._dthk_project_var,
            width=20,
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(
            dthk_proj_inner,
            text='e.g. "intranet"',
            style="Hint.TLabel",
        ).grid(row=0, column=1, padx=(10, 0))

        group_row += 1

        # --- Sound group ---
        sound_frame = ttk.LabelFrame(inner_frame, text="Sound")
        sound_frame.grid(
            row=group_row, column=0, sticky="ew", pady=(0, 10)
        )
        sound_frame.columnconfigure(1, weight=1)

        self._sound_enabled_var = tk.BooleanVar(
            value=self.config.sound.enabled
        )
        ttk.Checkbutton(
            sound_frame,
            text="Enable sound feedback",
            variable=self._sound_enabled_var,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=4)

        ttk.Label(sound_frame, text="Start Volume:").grid(
            row=1, column=0, sticky="w", pady=4, padx=(0, 10)
        )

        start_vol_inner = ttk.Frame(sound_frame)
        start_vol_inner.grid(row=1, column=1, sticky="ew", pady=4)
        start_vol_inner.columnconfigure(0, weight=1)

        self._start_vol_var = tk.DoubleVar(
            value=self.config.sound.start_volume
        )
        start_vol_slider = ttk.Scale(
            start_vol_inner,
            from_=0.0,
            to=1.0,
            variable=self._start_vol_var,
            orient="horizontal",
        )
        start_vol_slider.grid(row=0, column=0, sticky="ew")

        self._start_vol_label = ttk.Label(
            start_vol_inner,
            text=f"{int(self.config.sound.start_volume * 100)}%",
            width=5,
        )
        self._start_vol_label.grid(row=0, column=1, padx=(5, 0))
        start_vol_slider.configure(
            command=lambda v: self._start_vol_label.configure(
                text=f"{int(float(v) * 100)}%"
            )
        )

        ttk.Label(sound_frame, text="Stop Volume:").grid(
            row=2, column=0, sticky="w", pady=4, padx=(0, 10)
        )

        stop_vol_inner = ttk.Frame(sound_frame)
        stop_vol_inner.grid(row=2, column=1, sticky="ew", pady=4)
        stop_vol_inner.columnconfigure(0, weight=1)

        self._stop_vol_var = tk.DoubleVar(
            value=self.config.sound.stop_volume
        )
        stop_vol_slider = ttk.Scale(
            stop_vol_inner,
            from_=0.0,
            to=1.0,
            variable=self._stop_vol_var,
            orient="horizontal",
        )
        stop_vol_slider.grid(row=0, column=0, sticky="ew")

        self._stop_vol_label = ttk.Label(
            stop_vol_inner,
            text=f"{int(self.config.sound.stop_volume * 100)}%",
            width=5,
        )
        self._stop_vol_label.grid(row=0, column=1, padx=(5, 0))
        stop_vol_slider.configure(
            command=lambda v: self._stop_vol_label.configure(
                text=f"{int(float(v) * 100)}%"
            )
        )

        group_row += 1

        # --- System group ---
        system_frame = ttk.LabelFrame(inner_frame, text="System")
        system_frame.grid(
            row=group_row, column=0, sticky="ew", pady=(0, 10)
        )
        system_frame.columnconfigure(1, weight=1)

        self._startup_var = tk.BooleanVar(
            value=self.config.startup.start_with_windows
        )
        ttk.Checkbutton(
            system_frame,
            text="Start with Windows",
            variable=self._startup_var,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=4)

        # --- Button bar (pinned outside scroll area) ---
        button_bar = ttk.Frame(self._window, padding=(20, 10))
        button_bar.grid(row=2, column=0, sticky="ew")

        # Separator above buttons
        ttk.Separator(button_bar, orient="horizontal").pack(
            fill="x", pady=(0, 10)
        )

        btn_container = ttk.Frame(button_bar)
        btn_container.pack(anchor="e")

        ttk.Button(
            btn_container,
            text="Cancel",
            command=self._cancel,
            width=10,
        ).pack(side="left", padx=(0, 10))

        ttk.Button(
            btn_container,
            text="Save",
            command=self._save,
            width=10,
            style="Accent.TButton",
        ).pack(side="left")

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

    def _on_backend_changed(self) -> None:
        """Update UI visibility based on selected backend."""
        if not self._backend_var:
            return

        backend_display = self._backend_var.get()
        is_local = backend_display == "Local (Whisper)"

        # Show/hide local-only widgets
        for widget in self._local_only_widgets:
            if is_local:
                widget.grid()
            else:
                widget.grid_remove()

        # Show/hide Berget-only widgets
        for widget in self._berget_only_widgets:
            if is_local:
                widget.grid_remove()
            else:
                widget.grid()

    def _start_hotkey_capture(
        self, target_var: tk.StringVar | None = None
    ) -> None:
        """Start capturing a new hotkey using keyboard library for scan codes.

        Args:
            target_var: The StringVar to update with the captured hotkey.
                        Defaults to the save hotkey var.
        """
        if self._window is None:
            return

        self._capture_target = target_var or self._hotkey_var
        if self._capture_target is None:
            return

        self._capturing_hotkey = True
        self._captured_keys = set()
        self._captured_scan_code = None
        self._capture_target.set("Press keys or mouse...")

        # Notify app to block recordings during capture
        if self.on_capture_state_changed:
            self.on_capture_state_changed(True)

        # Use keyboard library for key capture (gets scan codes)
        keyboard.hook(self._on_keyboard_event)

        # Bind mouse button events (still use tkinter for mouse)
        self._window.bind("<Button-2>", self._on_mouse_button)  # Middle click
        self._window.bind("<Button-4>", self._on_mouse_button)  # Mouse button 4
        self._window.bind("<Button-5>", self._on_mouse_button)  # Mouse button 5

        self._window.focus_force()

    def _on_keyboard_event(self, event: keyboard.KeyboardEvent) -> bool | None:
        """Handle keyboard event during capture using keyboard library."""
        if not self._capturing_hotkey:
            return None

        if event.event_type == "down":
            key_name = event.name or ""
            scan_code = event.scan_code

            # Map to our format
            key = self._keyboard_event_to_key(key_name, scan_code)
            if key:
                self._captured_keys.add(key)

                # Store scan code for non-modifier keys
                if key not in ("<ctrl>", "<alt>", "<shift>"):
                    self._captured_scan_code = scan_code
                    logger.debug(f"Captured key: {key_name}, scan_code: {scan_code}")

                self._update_hotkey_display()

        elif event.event_type == "up":
            key_name = event.name or ""
            # Stop capturing when a non-modifier key is released
            if key_name.lower() not in ("ctrl", "alt", "shift", "control", "left ctrl",
                                         "right ctrl", "left alt", "right alt",
                                         "left shift", "right shift"):
                self._stop_hotkey_capture()

        return None  # Don't suppress the event

    def _on_mouse_button(self, event: tk.Event) -> str:
        """Handle mouse button click during capture."""
        if not self._capturing_hotkey:
            return "break"

        # Map tkinter button number to pynput-style mouse button string
        button_map = {
            2: "<mouse_middle>",  # Middle click (scroll wheel)
            4: "<mouse4>",  # Side button (back)
            5: "<mouse5>",  # Side button (forward)
        }

        if event.num in button_map:
            self._captured_keys.add(button_map[event.num])
            self._captured_scan_code = None  # Mouse buttons don't have scan codes
            self._update_hotkey_display()
            self._stop_hotkey_capture()

        return "break"

    def _stop_hotkey_capture(self) -> None:
        """Stop capturing hotkey and unbind events."""
        self._capturing_hotkey = False

        # Unhook keyboard library
        keyboard.unhook_all()

        if self._window:
            self._window.unbind("<Button-2>")
            self._window.unbind("<Button-4>")
            self._window.unbind("<Button-5>")

        # Store the captured scan code for the appropriate hotkey
        if self._capture_target == self._hotkey_var:
            self._save_hotkey_scan_code = self._captured_scan_code
            logger.debug(f"Stored save hotkey scan_code: {self._save_hotkey_scan_code}")
        elif self._capture_target == self._paste_hotkey_var:
            self._paste_hotkey_scan_code = self._captured_scan_code
            logger.debug(f"Stored paste hotkey scan_code: {self._paste_hotkey_scan_code}")
        elif self._capture_target == self._dthk_hotkey_var:
            self._dthk_hotkey_scan_code = self._captured_scan_code
            logger.debug(f"Stored devtracker hotkey scan_code: {self._dthk_hotkey_scan_code}")

        # Notify app that capture ended
        if self.on_capture_state_changed:
            self.on_capture_state_changed(False)

    def _keyboard_event_to_key(self, key_name: str, scan_code: int) -> str | None:
        """Convert keyboard library event to our hotkey format."""
        key_lower = key_name.lower()

        # Map modifier keys
        if key_lower in ("ctrl", "control", "left ctrl", "right ctrl"):
            return "<ctrl>"
        elif key_lower in ("alt", "left alt", "right alt"):
            return "<alt>"
        elif key_lower in ("shift", "left shift", "right shift"):
            return "<shift>"

        # Function keys
        if key_lower.startswith("f") and key_lower[1:].isdigit():
            return f"<{key_lower}>"

        # Named keys (like enter, space, etc.)
        if len(key_name) > 1 and key_name.isalpha():
            # For unknown/unnamed keys, use scan code notation
            if key_name == "unknown":
                return f"sc:{scan_code}"
            return key_name.lower()

        # Single character keys
        if len(key_name) == 1:
            return key_name.lower()

        # Special characters (like §) might have multi-char names
        # Use the key name if available, otherwise fall back to scan code
        if key_name and key_name != "unknown":
            return key_name
        else:
            return f"sc:{scan_code}"

    def _update_hotkey_display(self) -> None:
        """Update the hotkey display during capture."""
        if not self._capture_target:
            return

        # Sort keys: modifiers first, then regular keys/mouse buttons
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

        # Add scan code indicator for layout-specific keys
        if self._captured_scan_code and regular:
            # Show scan code in parentheses for non-standard keys
            main_key = regular[0] if regular else ""
            if main_key.startswith("sc:") or len(main_key) > 1:
                combination += f" (scan: {self._captured_scan_code})"

        self._capture_target.set(combination or "Press keys or mouse...")

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
            or self._lang_var is None
            or self._folder_var is None
            or self._startup_var is None
            or self._mic_var is None
            or self._sound_enabled_var is None
            or self._start_vol_var is None
            or self._stop_vol_var is None
            or self._paste_enabled_var is None
            or self._paste_hotkey_var is None
            or self._paste_mode_var is None
            or self._paste_restore_var is None
            or self._backend_var is None
            or self._api_key_var is None
            or self._dt_enabled_var is None
            or self._dt_api_key_var is None
            or self._dt_email_var is None
            or self._dt_project_var is None
            or self._dthk_enabled_var is None
            or self._dthk_hotkey_var is None
            or self._dthk_mode_var is None
            or self._dthk_project_var is None
        ):
            return

        # Validate settings
        hotkey = self._hotkey_var.get()
        if not hotkey or "Press keys" in hotkey:
            messagebox.showerror(
                "Invalid Settings",
                "Please set a valid hotkey.",
                parent=self._window,
            )
            return

        # Validate paste hotkey
        paste_enabled = self._paste_enabled_var.get()
        paste_hotkey = self._paste_hotkey_var.get()
        if paste_enabled:
            if not paste_hotkey or "Press keys" in paste_hotkey:
                messagebox.showerror(
                    "Invalid Settings",
                    "Please set a valid paste hotkey.",
                    parent=self._window,
                )
                return
            if paste_hotkey == hotkey:
                messagebox.showerror(
                    "Invalid Settings",
                    "Paste hotkey must differ from save hotkey.",
                    parent=self._window,
                )
                return

        folder_path = Path(self._folder_var.get()).expanduser()
        if not folder_path.parent.exists():
            messagebox.showerror(
                "Invalid Settings",
                "Storage folder parent directory does not exist.",
                parent=self._window,
            )
            return

        # Validate Berget API key if Berget backend is selected
        backend_display = self._backend_var.get()
        is_berget = backend_display == "Berget.ai API"
        if is_berget and not self._api_key_var.get().strip():
            messagebox.showerror(
                "Invalid Settings",
                "Berget.ai API key is required when using Berget.ai backend.",
                parent=self._window,
            )
            return

        # Validate DevTracker fields if enabled
        dt_enabled = self._dt_enabled_var.get()
        if dt_enabled:
            if not self._dt_api_key_var.get().strip():
                messagebox.showerror(
                    "Invalid Settings",
                    "DevTracker API key is required when DevTracker is enabled.",
                    parent=self._window,
                )
                return
            if not self._dt_email_var.get().strip():
                messagebox.showerror(
                    "Invalid Settings",
                    "DevTracker email is required when DevTracker is enabled.",
                    parent=self._window,
                )
                return
            if not self._dt_project_var.get().strip():
                messagebox.showerror(
                    "Invalid Settings",
                    "DevTracker project is required when DevTracker is enabled.",
                    parent=self._window,
                )
                return

        # Validate DevTracker hotkey fields if enabled
        dthk_enabled = self._dthk_enabled_var.get()
        dthk_hotkey = self._dthk_hotkey_var.get()
        if dthk_enabled:
            if not dt_enabled:
                messagebox.showerror(
                    "Invalid Settings",
                    "DevTracker must be enabled to use the DevTracker hotkey.",
                    parent=self._window,
                )
                return
            if not dthk_hotkey or "Press keys" in dthk_hotkey:
                messagebox.showerror(
                    "Invalid Settings",
                    "Please set a valid DevTracker hotkey.",
                    parent=self._window,
                )
                return
            if dthk_hotkey == hotkey:
                messagebox.showerror(
                    "Invalid Settings",
                    "DevTracker hotkey must differ from save hotkey.",
                    parent=self._window,
                )
                return
            if paste_enabled and dthk_hotkey == paste_hotkey:
                messagebox.showerror(
                    "Invalid Settings",
                    "DevTracker hotkey must differ from paste hotkey.",
                    parent=self._window,
                )
                return
            if not self._dthk_project_var.get().strip():
                messagebox.showerror(
                    "Invalid Settings",
                    "DevTracker hotkey project is required when enabled.",
                    parent=self._window,
                )
                return

        # Resolve language code from display name
        lang_name = self._lang_var.get()
        lang_code = "en"
        for code, name in SUPPORTED_LANGUAGES:
            if name == lang_name:
                lang_code = code
                break

        # Update config - strip scan code suffix from display for storage
        hotkey_clean = hotkey.split(" (scan:")[0]  # Remove scan code display suffix
        self.config.hotkey.combination = hotkey_clean
        self.config.hotkey.scan_code = self._save_hotkey_scan_code
        self.config.hotkey.mode = self._mode_var.get()  # type: ignore
        self.config.whisper.model_size = self._model_var.get()  # type: ignore
        self.config.whisper.language = lang_code
        self.config.storage.transcriptions_dir = self._folder_var.get()
        self.config.startup.start_with_windows = self._startup_var.get()

        # Update transcription backend config
        self.config.transcription.backend = "berget" if is_berget else "local"
        self.config.transcription.berget_api_key = self._api_key_var.get().strip()

        # Update paste hotkey config - strip scan code suffix from display
        paste_hotkey_clean = paste_hotkey.split(" (scan:")[0]
        self.config.paste_hotkey.enabled = paste_enabled
        self.config.paste_hotkey.combination = paste_hotkey_clean
        self.config.paste_hotkey.scan_code = self._paste_hotkey_scan_code
        self.config.paste_hotkey.mode = self._paste_mode_var.get()  # type: ignore
        self.config.paste_hotkey.restore_clipboard = self._paste_restore_var.get()

        # Update microphone setting
        mic_name = self._mic_var.get()
        if mic_name == "System Default":
            self.config.recording.microphone_id = None
        else:
            for mic in self._available_mics:
                if mic["name"] == mic_name:
                    self.config.recording.microphone_id = mic["id"]
                    break

        # Update sound settings
        self.config.sound.enabled = self._sound_enabled_var.get()
        self.config.sound.start_volume = self._start_vol_var.get()
        self.config.sound.stop_volume = self._stop_vol_var.get()

        # Update DevTracker settings
        self.config.devtracker.enabled = dt_enabled
        self.config.devtracker.api_key = self._dt_api_key_var.get().strip()
        self.config.devtracker.email = self._dt_email_var.get().strip()
        self.config.devtracker.project = self._dt_project_var.get().strip()

        # Update DevTracker hotkey settings - strip scan code suffix from display
        dthk_hotkey_clean = dthk_hotkey.split(" (scan:")[0]
        self.config.devtracker_hotkey.enabled = dthk_enabled
        self.config.devtracker_hotkey.combination = dthk_hotkey_clean
        self.config.devtracker_hotkey.scan_code = self._dthk_hotkey_scan_code
        self.config.devtracker_hotkey.mode = self._dthk_mode_var.get()  # type: ignore
        self.config.devtracker_hotkey.project = self._dthk_project_var.get().strip()

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
            self._window.unbind_all("<MouseWheel>")
            self._window.destroy()
            self._window = None
