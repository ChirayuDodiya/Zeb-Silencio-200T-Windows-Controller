"""
ZEB-Silencio 200T - Windows Studio Controller
Commercial-grade audio hardware companion for Zebronics ZEB-Silencio 200T wireless headphones.
Spacious, uncrowded split console with generous margins, calibrated for high-resolution screens with zero scrolling.
"""

import os
import sys
import time
import threading
import tkinter as tk
import customtkinter as ctk
from PIL import Image
from typing import List, Dict, Optional, Tuple

try:
    import pystray
except ImportError:
    pystray = None

from app.controller import HeadphoneController
from app.connection import find_silencio_com_port, get_available_com_ports
from app import protocol
from app import config


# ---------------------------------------------------------------------------
# COLOR TOKEN SYSTEM (Nordic Studio Audio Console)
# ---------------------------------------------------------------------------
COLOR_BG_ROOT = "#0B0C0E"       # Deep matte obsidian chassis
COLOR_SURFACE = "#13151A"       # Elevated deck surface
COLOR_SURFACE_WELL = "#0D0F13"  # Inset hardware well (sliders, visualizers)
COLOR_BORDER = "#1F232B"        # Precision hairline border
COLOR_BORDER_FOCUS = "#383E4C"  # Border focus/hover
COLOR_ACCENT = "#E5A93C"        # Warm studio amber / champagne gold
COLOR_ACCENT_HOVER = "#F5B84B"  # Interactive hover
COLOR_ACCENT_BG = "#2B2111"     # Translucent accent background
COLOR_EMERALD = "#22C55E"       # Connected / battery healthy
COLOR_EMERALD_BG = "#0B2618"    # Emerald badge background
COLOR_CORAL = "#EF4444"         # Disconnected / warning / delete
COLOR_CORAL_BG = "#291214"      # Coral badge background
COLOR_TEXT_PRIMARY = "#F3F4F6"  # Pure high-legibility readout
COLOR_TEXT_SECONDARY = "#8E96A6"# Calibrated studio grey
COLOR_TEXT_MUTED = "#555D6E"    # Disabled / subtle indicators


def is_windows_startup_enabled() -> bool:
    startup_dir = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    lnk_path = os.path.join(startup_dir, "ZEB-Silencio-200T.lnk")
    return os.path.exists(lnk_path)


def set_windows_startup(enabled: bool):
    try:
        startup_dir = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
        lnk_path = os.path.join(startup_dir, "ZEB-Silencio-200T.lnk")
        if enabled:
            if getattr(sys, 'frozen', False):
                target_exe = sys.executable
            else:
                target_exe = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ZEB-Silencio-200T.exe"))
                if not os.path.exists(target_exe):
                    target_exe = sys.executable
            cwd = os.path.dirname(target_exe)
            import win32com.client
            wscript = win32com.client.Dispatch("WScript.Shell")
            s = wscript.CreateShortcut(lnk_path)
            s.TargetPath = target_exe
            s.Arguments = "--minimized"
            s.WorkingDirectory = cwd
            s.Save()
        else:
            if os.path.exists(lnk_path):
                os.remove(lnk_path)
    except Exception as e:
        print(f"[Startup] Error setting startup shortcut: {e}")


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller bundles."""
    if hasattr(sys, '_MEIPASS'):
        p = os.path.join(sys._MEIPASS, relative_path)
        if os.path.exists(p):
            return p
        base_name = os.path.basename(relative_path)
        p2 = os.path.join(sys._MEIPASS, "assets", base_name)
        if os.path.exists(p2):
            return p2
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(curr_dir, relative_path)
    if os.path.exists(p):
        return p
    p_parent = os.path.join(os.path.dirname(curr_dir), relative_path)
    if os.path.exists(p_parent):
        return p_parent
    return p


# ---------------------------------------------------------------------------
# STUDIO MODAL DIALOGS
# ---------------------------------------------------------------------------
class StudioConfirmDialog(ctk.CTkToplevel):
    def __init__(self, parent, title: str, message: str, on_confirm, confirm_text: str = "Confirm"):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x170")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(fg_color=COLOR_BG_ROOT)
        self.transient(parent)
        self.grab_set()

        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 200
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 85
            self.geometry(f"400x170+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        card = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        card.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_TEXT_PRIMARY).pack(pady=(16, 4))
        ctk.CTkLabel(card, text=message, font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_SECONDARY, wraplength=340).pack(pady=(0, 16))

        btn_box = ctk.CTkFrame(card, fg_color="transparent")
        btn_box.pack(fill="x", padx=18)

        ctk.CTkButton(
            btn_box, text="Cancel", width=90, height=32, corner_radius=6,
            fg_color="#1E232B", hover_color="#2A303C", text_color=COLOR_TEXT_PRIMARY,
            command=self.destroy
        ).pack(side="left")
        
        def confirm_and_close():
            self.destroy()
            on_confirm()

        ctk.CTkButton(
            btn_box, text=confirm_text, width=105, height=32, corner_radius=6,
            fg_color=COLOR_CORAL, hover_color="#DC2626", text_color="#FFFFFF",
            font=ctk.CTkFont(weight="bold"),
            command=confirm_and_close
        ).pack(side="right")


class StudioInputDialog(ctk.CTkToplevel):
    def __init__(self, parent, title: str, prompt: str, on_submit):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x185")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(fg_color=COLOR_BG_ROOT)
        self.transient(parent)
        self.grab_set()

        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 200
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 92
            self.geometry(f"400x185+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        card = ctk.CTkFrame(self, fg_color=COLOR_SURFACE, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        card.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_TEXT_PRIMARY).pack(pady=(14, 2))
        ctk.CTkLabel(card, text=prompt, font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_SECONDARY).pack(pady=(0, 10))

        self.entry = ctk.CTkEntry(
            card, height=34, corner_radius=6,
            fg_color=COLOR_SURFACE_WELL, border_color=COLOR_BORDER_FOCUS,
            text_color=COLOR_TEXT_PRIMARY, placeholder_text="e.g. Warm Studio, Acoustic Bass"
        )
        self.entry.pack(fill="x", padx=18, pady=(0, 14))
        self.entry.focus_set()

        btn_box = ctk.CTkFrame(card, fg_color="transparent")
        btn_box.pack(fill="x", padx=18)

        ctk.CTkButton(
            btn_box, text="Cancel", width=90, height=32, corner_radius=6,
            fg_color="#1E232B", hover_color="#2A303C", text_color=COLOR_TEXT_PRIMARY,
            command=self.destroy
        ).pack(side="left")

        def submit():
            val = self.entry.get().strip()
            if val:
                self.destroy()
                on_submit(val)

        self.entry.bind("<Return>", lambda e: submit())

        ctk.CTkButton(
            btn_box, text="Save Preset", width=110, height=32, corner_radius=6,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color="#111317",
            font=ctk.CTkFont(weight="bold"),
            command=submit
        ).pack(side="right")


# ---------------------------------------------------------------------------
# MAIN APPLICATION WINDOW (SPACIOUS BALANCED CONSOLE)
# ---------------------------------------------------------------------------
class SilencioApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Start minimized if background service requested
        if "--minimized" in sys.argv or "--background" in sys.argv:
            self.withdraw()

        # Window Frame Calibration (Generous 1160x780 size for standard 1080p/1440p displays)
        self.title("ZEB-Silencio 200T — Windows Audio Studio")
        self.geometry("1160x780")
        self.minsize(1040, 700)
        
        ctk.set_appearance_mode("dark")
        self.configure(fg_color=COLOR_BG_ROOT)

        # Window Icon
        ico_path = get_resource_path(os.path.join("assets", "icon.ico"))
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        # Controller Backend
        self.controller = HeadphoneController(mac=config.get_mac_address())
        self.controller.on_state_update = self._on_state_update_threadsafe
        self.controller.on_connection_update = self._on_connection_update_threadsafe

        # Core State Variables
        self.var_anc = ctk.StringVar(value="ANC OFF")
        self.var_game_mode = ctk.BooleanVar(value=False)
        self.var_eq_preset = ctk.StringVar(value=config.get_default_preset())
        self.eq_sliders: List[ctk.CTkSlider] = []
        self.eq_labels: List[ctk.CTkLabel] = []
        self.preset_buttons: Dict[str, ctk.CTkButton] = {}
        self.anc_mode_tiles: Dict[str, Dict] = {}

        # Build Interface
        self._build_ui()

        # Window Close -> Hide to System Tray
        self.protocol("WM_DELETE_WINDOW", self._on_window_close)

        # System Tray Icon Setup
        self.tray_icon = None
        self._init_tray_icon()

        # Windows Startup Check
        if not is_windows_startup_enabled():
            set_windows_startup(True)

        # Auto-connect discovery on start
        self.after(200, self._auto_connect_startup)

    # -----------------------------------------------------------------------
    # USER INTERFACE BUILDER
    # -----------------------------------------------------------------------
    def _build_ui(self):
        # 3 Rows: Header (60px), Main Viewport (fills 100%), Telemetry Footer (32px)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_top_header()
        self._build_main_viewport()
        self._build_telemetry_footer()

    # --- 1. SLIM PRECISION HEADER ---
    def _build_top_header(self):
        header = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color=COLOR_SURFACE, border_width=0)
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_columnconfigure(1, weight=1)

        # Brand & Model Badge
        brand_box = ctk.CTkFrame(header, fg_color="transparent")
        brand_box.grid(row=0, column=0, padx=24, pady=10, sticky="w")

        logo_path = get_resource_path(os.path.join("assets", "logo.webp"))
        if os.path.exists(logo_path):
            try:
                pil_logo = Image.open(logo_path).resize((26, 26), Image.Resampling.LANCZOS)
                ctk_logo = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(26, 26))
                lbl_icon = ctk.CTkLabel(brand_box, image=ctk_logo, text="")
                lbl_icon.pack(side="left", padx=(0, 10))
            except Exception:
                pass

        title_col = ctk.CTkFrame(brand_box, fg_color="transparent")
        title_col.pack(side="left")

        title_lbl = ctk.CTkLabel(
            title_col, 
            text="SILENCIO 200T", 
            font=ctk.CTkFont(family="Segoe UI Variable Display", size=17, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        title_lbl.pack(side="left")

        sep = ctk.CTkLabel(title_col, text="·", font=ctk.CTkFont(size=14), text_color=COLOR_TEXT_MUTED)
        sep.pack(side="left", padx=8)

        sub_lbl = ctk.CTkLabel(
            title_col, 
            text="WINDOWS AUDIO STUDIO", 
            font=ctk.CTkFont(size=11, weight="bold"), 
            text_color=COLOR_TEXT_MUTED
        )
        sub_lbl.pack(side="left")

        # Hardware Link Controls
        link_box = ctk.CTkFrame(header, fg_color="transparent")
        link_box.grid(row=0, column=2, padx=24, pady=10, sticky="e")

        self.lbl_status_pill = ctk.CTkLabel(
            link_box,
            text="● Disconnected",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_CORAL,
            fg_color=COLOR_CORAL_BG,
            corner_radius=12,
            padx=14,
            pady=5
        )
        self.lbl_status_pill.pack(side="left", padx=8)

        self.cbox_ports = ctk.CTkComboBox(
            link_box,
            values=self._get_port_list(),
            width=100,
            height=30,
            corner_radius=6,
            fg_color=COLOR_SURFACE_WELL,
            border_color=COLOR_BORDER,
            button_color="#1E232B",
            button_hover_color="#2A303C",
            text_color=COLOR_TEXT_PRIMARY,
            command=self._on_port_selected
        )
        self.cbox_ports.pack(side="left", padx=5)

        self.btn_connect = ctk.CTkButton(
            link_box,
            text="Connect",
            width=90,
            height=30,
            corner_radius=6,
            command=self._toggle_connection,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color="#111317",
            font=ctk.CTkFont(weight="bold")
        )
        self.btn_connect.pack(side="left", padx=5)

    # --- 2. MAIN VIEWPORT (2-COLUMN BALANCED SPLIT) ---
    def _build_main_viewport(self):
        # Generous padding around the entire viewport
        viewport = ctk.CTkFrame(self, fg_color=COLOR_BG_ROOT)
        viewport.grid(row=1, column=0, sticky="nsew", padx=20, pady=14)
        viewport.grid_rowconfigure(0, weight=1)
        viewport.grid_columnconfigure(0, weight=0, minsize=340) # Left: Hardware Deck
        viewport.grid_columnconfigure(1, weight=1)              # Right: Equalizer Studio

        self._build_left_hardware_column(viewport)
        self._build_right_studio_column(viewport)

    # --- LEFT COLUMN: HARDWARE & COCKPIT ---
    def _build_left_hardware_column(self, parent):
        deck = ctk.CTkFrame(parent, width=340, corner_radius=12, fg_color=COLOR_SURFACE, border_width=1, border_color=COLOR_BORDER)
        deck.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=0)
        deck.grid_propagate(False)

        # 1. Device Turntable & Battery Row (Spacious)
        turntable = ctk.CTkFrame(deck, fg_color=COLOR_SURFACE_WELL, corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        turntable.pack(fill="x", padx=16, pady=(16, 12))

        top_row = ctk.CTkFrame(turntable, fg_color="transparent")
        top_row.pack(fill="x", padx=12, pady=12)

        img_path = get_resource_path(os.path.join("assets", "headphone.png"))
        if os.path.exists(img_path):
            try:
                pil_img = Image.open(img_path)
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(92, 92))
                lbl_img = ctk.CTkLabel(top_row, image=ctk_img, text="")
                lbl_img.pack(side="left", padx=(0, 12))
            except Exception as e:
                print(f"[UI] Error loading hero image: {e}")

        meta_col = ctk.CTkFrame(top_row, fg_color="transparent")
        meta_col.pack(side="left", fill="both", expand=True)

        self.lbl_dev_name = ctk.CTkLabel(
            meta_col, 
            text="ZEB-Silencio 200T", 
            font=ctk.CTkFont(family="Segoe UI Variable Display", size=15, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        self.lbl_dev_name.pack(fill="x", pady=(4, 0))

        lbl_chip = ctk.CTkLabel(
            meta_col, 
            text="48dB ANC · Bluetrum AB", 
            font=ctk.CTkFont(size=11), 
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        )
        lbl_chip.pack(fill="x", pady=(0, 8))

        # Battery Gauge inside turntable
        bat_box = ctk.CTkFrame(meta_col, fg_color="transparent")
        bat_box.pack(fill="x")

        self.lbl_battery = ctk.CTkLabel(
            bat_box, 
            text="-- %", 
            font=ctk.CTkFont(size=13, weight="bold"), 
            text_color=COLOR_EMERALD,
            anchor="w"
        )
        self.lbl_battery.pack(side="left")

        self.progress_battery = ctk.CTkProgressBar(
            bat_box, height=6, width=96, corner_radius=3, 
            fg_color="#181B22", progress_color=COLOR_EMERALD
        )
        self.progress_battery.set(0.0)
        self.progress_battery.pack(side="right", padx=(8, 0))

        # 2. Acoustic Noise Cancellation (ANC Deck)
        anc_card = ctk.CTkFrame(deck, fg_color="transparent")
        anc_card.pack(fill="x", padx=16, pady=(0, 12))

        anc_hdr = ctk.CTkFrame(anc_card, fg_color="transparent")
        anc_hdr.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(anc_hdr, text="ACOUSTIC ISOLATION", font=ctk.CTkFont(size=10, weight="bold"), text_color=COLOR_TEXT_MUTED).pack(side="left")
        self.lbl_anc_status = ctk.CTkLabel(anc_hdr, text="Passive Seal", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY)
        self.lbl_anc_status.pack(side="right")

        modes = [
            ("ANC ON", "ANC Active", "48dB Hybrid noise cancellation"),
            ("Transparency", "Ambient Sound", "Natural microphone passthrough"),
            ("ANC OFF", "Acoustics Off", "Passive isolation seal")
        ]

        self.anc_mode_tiles = {}

        for mode_key, mode_title, mode_desc in modes:
            tile = ctk.CTkFrame(
                anc_card, 
                corner_radius=8, 
                fg_color=COLOR_SURFACE_WELL, 
                border_width=1, 
                border_color=COLOR_BORDER,
                height=48
            )
            tile.pack(fill="x", pady=4)
            tile.pack_propagate(False)
            tile.bind("<Button-1>", lambda e, m=mode_key: self._on_anc_selected(m))

            tile_content = ctk.CTkFrame(tile, fg_color="transparent")
            tile_content.pack(fill="both", expand=True, padx=12, pady=6)
            tile_content.bind("<Button-1>", lambda e, m=mode_key: self._on_anc_selected(m))

            row1 = ctk.CTkFrame(tile_content, fg_color="transparent")
            row1.pack(fill="x")
            row1.bind("<Button-1>", lambda e, m=mode_key: self._on_anc_selected(m))

            t_lbl = ctk.CTkLabel(row1, text=mode_title, font=ctk.CTkFont(size=12, weight="bold"), text_color=COLOR_TEXT_PRIMARY)
            t_lbl.pack(side="left")
            t_lbl.bind("<Button-1>", lambda e, m=mode_key: self._on_anc_selected(m))

            radio_indicator = ctk.CTkLabel(row1, text="○", font=ctk.CTkFont(size=13), text_color=COLOR_TEXT_MUTED)
            radio_indicator.pack(side="right")
            radio_indicator.bind("<Button-1>", lambda e, m=mode_key: self._on_anc_selected(m))

            d_lbl = ctk.CTkLabel(tile_content, text=mode_desc, font=ctk.CTkFont(size=10), text_color=COLOR_TEXT_MUTED)
            d_lbl.pack(anchor="w", pady=(1, 0))
            d_lbl.bind("<Button-1>", lambda e, m=mode_key: self._on_anc_selected(m))

            self.anc_mode_tiles[mode_key] = {
                "frame": tile,
                "title": t_lbl,
                "indicator": radio_indicator
            }

        self._update_anc_tiles_ui("ANC OFF")

        # 3. Hardware Toggles (Gaming Mode & Startup Auto-Boot)
        toggles_card = ctk.CTkFrame(deck, fg_color="transparent")
        toggles_card.pack(fill="x", padx=16, pady=(0, 12))

        # Gaming Mode
        game_box = ctk.CTkFrame(toggles_card, fg_color=COLOR_SURFACE_WELL, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        game_box.pack(fill="x", pady=4)
        g_inner = ctk.CTkFrame(game_box, fg_color="transparent")
        g_inner.pack(fill="x", padx=12, pady=8)

        g_title = ctk.CTkFrame(g_inner, fg_color="transparent")
        g_title.pack(side="left")
        ctk.CTkLabel(g_title, text="Low Latency Gaming", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(g_title, text="< 45ms synchronized audio", font=ctk.CTkFont(size=9), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        self.sw_game = ctk.CTkSwitch(
            g_inner, text="", variable=self.var_game_mode, command=self._on_game_mode_toggle,
            progress_color=COLOR_ACCENT, button_color="#FFFFFF", width=42, height=22
        )
        self.sw_game.pack(side="right")

        # Startup Auto-Boot
        startup_box = ctk.CTkFrame(toggles_card, fg_color=COLOR_SURFACE_WELL, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        startup_box.pack(fill="x", pady=4)
        s_inner = ctk.CTkFrame(startup_box, fg_color="transparent")
        s_inner.pack(fill="x", padx=12, pady=8)

        s_title = ctk.CTkFrame(s_inner, fg_color="transparent")
        s_title.pack(side="left")
        ctk.CTkLabel(s_title, text="Auto-Tune on Startup", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(s_title, text="Apply default EQ on boot", font=ctk.CTkFont(size=9), text_color=COLOR_TEXT_MUTED).pack(anchor="w")

        self.var_startup = ctk.BooleanVar(value=is_windows_startup_enabled())
        self.sw_startup = ctk.CTkSwitch(
            s_inner, text="", variable=self.var_startup, command=self._on_startup_toggle,
            progress_color=COLOR_ACCENT, button_color="#FFFFFF", width=42, height=22
        )
        self.sw_startup.pack(side="right")

        # 4. Action Row (Sync Status & Locate Device)
        act_row = ctk.CTkFrame(deck, fg_color="transparent")
        act_row.pack(fill="x", padx=16, pady=(6, 16))

        btn_refresh = ctk.CTkButton(
            act_row, text="Sync Status", height=32, corner_radius=6,
            command=self._refresh_status, fg_color="#1E232B", hover_color="#2A303C",
            text_color=COLOR_TEXT_PRIMARY, font=ctk.CTkFont(size=11, weight="bold")
        )
        btn_refresh.pack(side="left", fill="x", expand=True, padx=(0, 4))

        btn_find = ctk.CTkButton(
            act_row, text="Locate Device", height=32, corner_radius=6,
            command=self._find_device, fg_color="#1E232B", hover_color="#2A303C",
            text_color=COLOR_TEXT_PRIMARY, font=ctk.CTkFont(size=11, weight="bold")
        )
        btn_find.pack(side="left", fill="x", expand=True, padx=(4, 0))

    # --- RIGHT COLUMN: MASTERING STUDIO & 10-BAND EQUALIZER ---
    def _build_right_studio_column(self, parent):
        deck = ctk.CTkFrame(parent, corner_radius=12, fg_color=COLOR_SURFACE, border_width=1, border_color=COLOR_BORDER)
        deck.grid(row=0, column=1, sticky="nsew", padx=(0, 0), pady=0)

        # 1. Studio Header Row (Spacious)
        hdr = ctk.CTkFrame(deck, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16, 10))

        title_box = ctk.CTkFrame(hdr, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box, 
            text="10-BAND STUDIO EQUALIZER", 
            font=ctk.CTkFont(family="Segoe UI Variable Display", size=14, weight="bold"), 
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side="left")

        self.lbl_default_indicator = ctk.CTkLabel(
            title_box,
            text=f"Default: {config.get_default_preset()}",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_ACCENT,
            fg_color=COLOR_ACCENT_BG,
            corner_radius=8,
            padx=10,
            pady=2
        )
        self.lbl_default_indicator.pack(side="left", padx=12)

        actions_box = ctk.CTkFrame(hdr, fg_color="transparent")
        actions_box.pack(side="right")

        self.btn_save_preset = ctk.CTkButton(
            actions_box, text="+ Save Preset", width=105, height=28, corner_radius=6,
            command=self._save_preset_prompt, fg_color="#1E232B", hover_color="#2A303C",
            text_color=COLOR_TEXT_PRIMARY, font=ctk.CTkFont(size=11, weight="bold")
        )
        self.btn_save_preset.pack(side="left", padx=(0, 8))

        self.btn_delete_preset = ctk.CTkButton(
            actions_box, text="Delete", width=74, height=28, corner_radius=6,
            command=self._delete_current_preset_prompt, fg_color=COLOR_SURFACE_WELL,
            hover_color="#2A1215", text_color=COLOR_TEXT_MUTED, font=ctk.CTkFont(size=11, weight="bold"),
            state="disabled"
        )
        self.btn_delete_preset.pack(side="left")

        # 2. Live Frequency Response Curve Canvas (Expanded Height 82px)
        canvas_card = ctk.CTkFrame(deck, fg_color=COLOR_SURFACE_WELL, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        canvas_card.pack(fill="x", padx=18, pady=(0, 10))

        self.eq_canvas = tk.Canvas(
            canvas_card, height=82, bg=COLOR_SURFACE_WELL, highlightthickness=0, cursor="crosshair"
        )
        self.eq_canvas.pack(fill="x", padx=12, pady=6)
        self.eq_canvas.bind("<Configure>", lambda e: self._redraw_eq_curve())

        # 3. 10 Precision Faders Well (Generous Height 145px)
        sliders_frame = ctk.CTkFrame(deck, fg_color=COLOR_SURFACE_WELL, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        sliders_frame.pack(fill="x", padx=18, pady=(0, 12))
        sliders_frame.grid_columnconfigure(list(range(10)), weight=1)

        freq_labels = ["32Hz", "62Hz", "125Hz", "250Hz", "500Hz", "1kHz", "2kHz", "4kHz", "8kHz", "16kHz"]
        default_preset = config.get_default_preset()
        if default_preset == "Custom":
            init_gains = config.get_custom_eq()
        else:
            init_gains = protocol.EQ_PRESETS.get(default_preset, [0] * 10)

        self.eq_sliders.clear()
        self.eq_labels.clear()

        for i in range(10):
            col_box = ctk.CTkFrame(sliders_frame, fg_color="transparent")
            col_box.grid(row=0, column=i, padx=2, pady=10, sticky="nsew")

            val_lbl = ctk.CTkLabel(
                col_box, 
                text=f"{init_gains[i]:+d}dB", 
                font=ctk.CTkFont(size=11, weight="bold"), 
                text_color=COLOR_ACCENT if init_gains[i] != 0 else COLOR_TEXT_MUTED
            )
            val_lbl.pack(pady=(0, 4))
            self.eq_labels.append(val_lbl)

            slider = ctk.CTkSlider(
                col_box, from_=-12, to=12, number_of_steps=24,
                orientation="vertical", height=145, width=17,
                fg_color="#181B22", progress_color=COLOR_BORDER_FOCUS,
                button_color=COLOR_ACCENT, button_hover_color=COLOR_ACCENT_HOVER,
                command=lambda val, idx=i: self._on_slider_moved(idx, val)
            )
            slider.set(init_gains[i])
            slider.pack(pady=3)
            self.eq_sliders.append(slider)

            f_lbl = ctk.CTkLabel(col_box, text=freq_labels[i], font=ctk.CTkFont(size=10, weight="bold"), text_color=COLOR_TEXT_SECONDARY)
            f_lbl.pack(pady=(4, 0))

        self.after(100, self._redraw_eq_curve)

        # 4. Preset Selector Palette (Spacious 2 Rows)
        self.preset_frame = ctk.CTkFrame(deck, fg_color="transparent")
        self.preset_frame.pack(fill="x", padx=18, pady=(0, 12))
        self._build_preset_buttons()

        # 5. Master Equalizer Actions (Generous Height 36px)
        eq_actions = ctk.CTkFrame(deck, fg_color="transparent")
        eq_actions.pack(fill="x", padx=18, pady=(0, 16))

        self.btn_set_default = ctk.CTkButton(
            eq_actions, text="★ Set as Startup Default", height=36, corner_radius=6,
            command=self._set_current_as_default, fg_color="#1E232B", hover_color="#2A303C",
            text_color=COLOR_TEXT_PRIMARY, font=ctk.CTkFont(size=11, weight="bold")
        )
        self.btn_set_default.pack(side="left", padx=(0, 10))

        btn_apply_eq = ctk.CTkButton(
            eq_actions, text="Commit to Headphone Firmware", height=36, corner_radius=6,
            command=self._apply_current_eq, fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color="#111317", font=ctk.CTkFont(size=12, weight="bold")
        )
        btn_apply_eq.pack(side="left", fill="x", expand=True)

    # --- 3. TELEMETRY STATUS FOOTER ---
    def _build_telemetry_footer(self):
        footer = ctk.CTkFrame(self, height=32, corner_radius=0, fg_color=COLOR_SURFACE, border_width=1, border_color=COLOR_BORDER)
        footer.grid(row=2, column=0, sticky="ew", padx=0, pady=0)
        footer.grid_columnconfigure(0, weight=1)

        self.lbl_log = ctk.CTkLabel(
            footer, text="Ready. Select Bluetooth COM port and click Connect.",
            font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_MUTED, anchor="w"
        )
        self.lbl_log.grid(row=0, column=0, sticky="ew", padx=20, pady=5)

        lbl_spec = ctk.CTkLabel(
            footer, text="Bluetrum SPP · 48kHz / 24-bit DSP",
            font=ctk.CTkFont(size=10, weight="bold"), text_color="#363C4A"
        )
        lbl_spec.grid(row=0, column=1, sticky="e", padx=20, pady=5)

    # -----------------------------------------------------------------------
    # LIVE FREQUENCY RESPONSE CURVE VISUALIZER
    # -----------------------------------------------------------------------
    def _redraw_eq_curve(self):
        try:
            w = self.eq_canvas.winfo_width()
            h = self.eq_canvas.winfo_height()
            if w <= 10 or h <= 10:
                return

            self.eq_canvas.delete("all")

            y_center = h / 2.0
            db_span = 12.0
            y_scale = (h * 0.38) / db_span

            # Grid lines
            self.eq_canvas.create_line(0, y_center, w, y_center, fill="#242934", width=1, dash=(3, 3))
            self.eq_canvas.create_text(18, y_center - 7, text="0 dB", fill="#464E60", font=("Segoe UI", 8))

            y_p6 = y_center - (6.0 * y_scale)
            y_m6 = y_center + (6.0 * y_scale)
            self.eq_canvas.create_line(0, y_p6, w, y_p6, fill="#181B22", width=1, dash=(2, 4))
            self.eq_canvas.create_line(0, y_m6, w, y_m6, fill="#181B22", width=1, dash=(2, 4))
            self.eq_canvas.create_text(18, y_p6 - 6, text="+6", fill="#343A48", font=("Segoe UI", 7))
            self.eq_canvas.create_text(18, y_m6 - 6, text="-6", fill="#343A48", font=("Segoe UI", 7))

            gains = [float(s.get()) for s in self.eq_sliders] if self.eq_sliders else [0.0] * 10
            num_bands = len(gains)

            col_width = w / float(num_bands)
            points = []

            # Start point at x=0
            first_y = y_center - (gains[0] * y_scale)
            points.append(0.0)
            points.append(first_y)

            # Control points
            for i in range(num_bands):
                x = (i + 0.5) * col_width
                y = y_center - (gains[i] * y_scale)
                points.append(x)
                points.append(y)

            # End point at x=w
            last_y = y_center - (gains[-1] * y_scale)
            points.append(float(w))
            points.append(last_y)

            # Shaded polygon under curve down to baseline
            poly_points = list(points)
            poly_points.extend([float(w), y_center, 0.0, y_center])
            self.eq_canvas.create_polygon(poly_points, smooth=True, fill="#1B1710", outline="")

            # Smooth Glowing Curve Path
            self.eq_canvas.create_line(points, smooth=True, fill=COLOR_ACCENT, width=2)

            # Beads at control points
            for i in range(num_bands):
                x = (i + 0.5) * col_width
                y = y_center - (gains[i] * y_scale)
                r = 3.5
                self.eq_canvas.create_oval(x - r, y - r, x + r, y + r, fill=COLOR_ACCENT, outline="#FFF4DD", width=1)

        except Exception as e:
            print(f"[Curve] Redraw error: {e}")

    # -----------------------------------------------------------------------
    # LOGIC: PRESET BUTTONS & SELECTION
    # -----------------------------------------------------------------------
    def _build_preset_buttons(self):
        for widget in self.preset_frame.winfo_children():
            widget.destroy()
        self.preset_buttons.clear()

        ref_presets = ["OnePlus Buds 3", "AirPods", "Default / Flat"]
        genre_presets = ["Bass Boost", "Vocal", "Rock", "Pop", "Jazz", "Classical", "Hip Hop"]
        custom_presets = list(config.get_custom_presets().keys())
        all_presets = ref_presets + genre_presets + custom_presets

        active_preset = self.var_eq_preset.get()

        cols = 5
        for i, name in enumerate(all_presets):
            row = i // cols
            col = i % cols
            is_active = (name == active_preset)

            btn = ctk.CTkButton(
                self.preset_frame,
                text=name,
                height=28,
                corner_radius=6,
                font=ctk.CTkFont(size=10, weight="bold" if is_active else "normal"),
                fg_color=COLOR_ACCENT if is_active else COLOR_SURFACE_WELL,
                hover_color=COLOR_ACCENT_HOVER if is_active else "#1F232C",
                text_color="#111317" if is_active else COLOR_TEXT_SECONDARY,
                border_width=1,
                border_color=COLOR_ACCENT if is_active else COLOR_BORDER,
                command=lambda p=name: self._select_preset(p)
            )
            btn.grid(row=row, column=col, padx=3, pady=3, sticky="ew")
            self.preset_frame.grid_columnconfigure(col, weight=1)
            self.preset_buttons[name] = btn

    def _select_preset(self, preset_name: str):
        self.var_eq_preset.set(preset_name)
        custom_presets = config.get_custom_presets()

        if preset_name in protocol.EQ_PRESETS:
            gains = protocol.EQ_PRESETS[preset_name]
        elif preset_name in custom_presets:
            gains = custom_presets[preset_name]
        else:
            gains = config.get_custom_eq()

        for i in range(10):
            val = gains[i]
            self.eq_sliders[i].set(val)
            self.eq_labels[i].configure(
                text=f"{val:+d}dB",
                text_color=COLOR_ACCENT if val != 0 else COLOR_TEXT_MUTED
            )

        self.controller.set_eq_preset(preset_name)
        self._highlight_active_preset(preset_name)
        self._update_delete_button_state(preset_name)
        self._redraw_eq_curve()
        self._log(f"Loaded EQ Preset: {preset_name}")

    def _highlight_active_preset(self, active_name: str):
        for name, btn in self.preset_buttons.items():
            is_active = (name == active_name)
            btn.configure(
                fg_color=COLOR_ACCENT if is_active else COLOR_SURFACE_WELL,
                hover_color=COLOR_ACCENT_HOVER if is_active else "#1F232C",
                text_color="#111317" if is_active else COLOR_TEXT_SECONDARY,
                font=ctk.CTkFont(size=10, weight="bold" if is_active else "normal"),
                border_color=COLOR_ACCENT if is_active else COLOR_BORDER
            )

    def _update_delete_button_state(self, preset_name: str):
        if preset_name in config.get_custom_presets():
            self.btn_delete_preset.configure(
                state="normal", 
                fg_color=COLOR_CORAL, 
                hover_color="#DC2626", 
                text_color="#FFFFFF"
            )
        else:
            self.btn_delete_preset.configure(
                state="disabled", 
                fg_color=COLOR_SURFACE_WELL, 
                text_color=COLOR_TEXT_MUTED
            )

    def _on_slider_moved(self, idx: int, value: float):
        int_val = int(round(value))
        self.eq_labels[idx].configure(
            text=f"{int_val:+d}dB",
            text_color=COLOR_ACCENT if int_val != 0 else COLOR_TEXT_MUTED
        )
        self.var_eq_preset.set("Custom")
        self._highlight_active_preset("")
        self._update_delete_button_state("Custom")
        self._redraw_eq_curve()
        self.controller.mark_user_action()

    def _save_preset_prompt(self):
        def on_name_entered(clean_name: str):
            if clean_name in protocol.EQ_PRESETS:
                self._log(f"Built-in preset '{clean_name}' cannot be overwritten.")
                return
            gains = [int(round(s.get())) for s in self.eq_sliders]
            config.save_custom_preset(clean_name, gains)
            self._build_preset_buttons()
            self._select_preset(clean_name)
            self._log(f"Saved custom preset: '{clean_name}'")

        StudioInputDialog(
            self,
            title="Save Custom Preset",
            prompt="Enter a descriptive profile name for this curve:",
            on_submit=on_name_entered
        )

    def _delete_current_preset_prompt(self):
        target = self.var_eq_preset.get()
        if target in config.get_custom_presets():
            StudioConfirmDialog(
                self,
                title="Delete Preset",
                message=f"Permanently delete custom profile '{target}'?",
                on_confirm=lambda: self._execute_delete_preset(target),
                confirm_text="Delete Profile"
            )

    def _execute_delete_preset(self, name: str):
        config.delete_custom_preset(name)
        self._build_preset_buttons()
        default_preset = config.get_default_preset()
        self._select_preset(default_preset)
        self._log(f"Deleted custom preset: '{name}'")

    def _set_current_as_default(self):
        current = self.var_eq_preset.get()
        if current == "Custom":
            gains = [int(round(s.get())) for s in self.eq_sliders]
            config.set_custom_eq(gains)
        config.set_default_preset(current)
        if hasattr(self, "lbl_default_indicator"):
            self.lbl_default_indicator.configure(text=f"Default: {current}")
        self._log(f"Default EQ on connect saved as: {current}")

    def _apply_current_eq(self):
        gains = [int(round(s.get())) for s in self.eq_sliders]
        config.set_custom_eq(gains)
        self.controller.set_custom_eq(gains)
        self._log(f"Committed 10-band acoustic curve to DSP: {gains}")

    # -----------------------------------------------------------------------
    # LOGIC: ANC MODES & HARDWARE TOGGLES
    # -----------------------------------------------------------------------
    def _on_anc_selected(self, mode_str: str):
        if mode_str == "ANC ON":
            self.controller.set_anc_mode(protocol.ANC_MODE_ON)
            self._log("Switched to Active Noise Cancellation (48dB Hybrid ANC)")
        elif mode_str == "Transparency":
            self.controller.set_anc_mode(protocol.ANC_MODE_TRANSPARENCY)
            self._log("Switched to Ambient Passthrough (Transparency Mode)")
        else:
            self.controller.set_anc_mode(protocol.ANC_MODE_OFF)
            self._log("Switched to Passive Seal (ANC OFF)")
        self._update_anc_tiles_ui(mode_str)

    def _update_anc_tiles_ui(self, active_mode: str):
        for mode_key, tile_data in self.anc_mode_tiles.items():
            is_active = (mode_key == active_mode)
            tile_data["frame"].configure(
                fg_color=COLOR_ACCENT_BG if is_active else COLOR_SURFACE_WELL,
                border_color=COLOR_ACCENT if is_active else COLOR_BORDER,
                border_width=1
            )
            tile_data["title"].configure(
                text_color=COLOR_ACCENT if is_active else COLOR_TEXT_PRIMARY
            )
            tile_data["indicator"].configure(
                text="●" if is_active else "○",
                text_color=COLOR_ACCENT if is_active else COLOR_TEXT_MUTED
            )

        status_text = {
            "ANC ON": "48dB Isolation",
            "Transparency": "Passthrough Active",
            "ANC OFF": "Passive Seal"
        }.get(active_mode, "Passive Seal")
        self.lbl_anc_status.configure(text=status_text)

    def _on_game_mode_toggle(self):
        val = self.var_game_mode.get()
        mode = protocol.WORK_MODE_GAMING if val else protocol.WORK_MODE_NORMAL
        self.controller.set_work_mode(mode)
        self._log(f"Low latency gaming mode: {'ENABLED' if val else 'DISABLED'}")

    def _on_startup_toggle(self):
        val = self.var_startup.get()
        set_windows_startup(val)
        self._log(f"Auto-tune on Windows startup: {'ENABLED' if val else 'DISABLED'}")

    # -----------------------------------------------------------------------
    # LOGIC: CONNECTION & BLUETOOTH
    # -----------------------------------------------------------------------
    def _get_port_list(self) -> List[str]:
        ports = get_available_com_ports()
        items = [p[0] for p in ports]
        auto_port = find_silencio_com_port()
        if auto_port and auto_port not in items:
            items.insert(0, auto_port)
        elif auto_port and auto_port in items:
            items.remove(auto_port)
            items.insert(0, auto_port)
        if not items:
            items = ["COM5", "COM3"]
        return items

    def _auto_connect_startup(self):
        auto_port = find_silencio_com_port() or "COM5"
        self.cbox_ports.set(auto_port)
        self._log(f"Auto-detecting ZEB-Silencio 200T on {auto_port}...")
        self.controller.start_auto_reconnect(auto_port)

    def _toggle_connection(self):
        if self.controller.is_connected:
            self.controller.stop_auto_reconnect()
            self.controller.disconnect()
            self._log("Bluetooth session disconnected.")
        else:
            port = self.cbox_ports.get()
            self._log(f"Opening RFCOMM serial link on {port}...")
            self.controller.start_auto_reconnect(port)
            threading.Thread(target=lambda: self.controller.connect(port), daemon=True).start()

    def _on_port_selected(self, choice: str):
        if self.controller.is_connected:
            self.controller.disconnect()

    def _refresh_status(self):
        if self.controller.is_connected:
            self._log("Synchronizing device telemetry...")
            threading.Thread(target=self._run_refresh, daemon=True).start()
        else:
            self._log("Headphone is not connected.")

    def _run_refresh(self):
        try:
            self.controller.refresh_sync()
            self._log(f"Sync complete. Battery: {self.controller.battery}%, Profile: {self.controller.current_eq_name}")
        except Exception as e:
            print(f"[UI] Refresh error: {e}")
            self._log("Telemetry sync failed.")

    def _find_device(self):
        if self.controller.is_connected:
            self._log("Emitting locator tone on headphone speakers...")
            self.controller.find_device()
        else:
            self._log("Headphone is not connected.")

    def _log(self, text: str):
        self.lbl_log.configure(text=f"● {text}")

    # -----------------------------------------------------------------------
    # THREADSAFE TELEMETRY DISPATCHERS
    # -----------------------------------------------------------------------
    def _on_state_update_threadsafe(self, key: str, value):
        self.after(0, lambda: self._apply_state_update(key, value))

    def _on_connection_update_threadsafe(self, connected: bool, message: str):
        self.after(0, lambda: self._apply_connection_update(connected, message))

    def _apply_connection_update(self, connected: bool, message: str):
        if connected:
            self.lbl_status_pill.configure(
                text="● Connected", 
                text_color=COLOR_EMERALD, 
                fg_color=COLOR_EMERALD_BG
            )
            self.btn_connect.configure(
                text="Disconnect", 
                fg_color="#1E232B", 
                hover_color=COLOR_CORAL,
                text_color=COLOR_TEXT_PRIMARY
            )
            def_preset = config.get_default_preset()
            self._log(f"Connected: {message} · Auto-loaded '{def_preset}' tuning.")
            self._select_preset(def_preset)
            if self.tray_icon:
                try:
                    self.tray_icon.notify(
                        f"Connected via Bluetooth! Applied {def_preset} profile.",
                        "ZEB-Silencio 200T Studio"
                    )
                except Exception:
                    pass
        else:
            self.lbl_status_pill.configure(
                text="● Disconnected", 
                text_color=COLOR_CORAL, 
                fg_color=COLOR_CORAL_BG
            )
            self.btn_connect.configure(
                text="Connect", 
                fg_color=COLOR_ACCENT, 
                hover_color=COLOR_ACCENT_HOVER,
                text_color="#111317"
            )
            self._log(f"{message} (Auto-watcher active)")

    def _apply_state_update(self, key: str, value):
        if key == "battery":
            pct = value.get("battery", 0)
            is_chg = value.get("is_charging", False)
            chg_icon = " ⚡" if is_chg else ""
            self.lbl_battery.configure(text=f"{pct}%{chg_icon}")
            self.progress_battery.set(pct / 100.0)
            if pct <= 20:
                self.progress_battery.configure(progress_color=COLOR_CORAL)
                self.lbl_battery.configure(text_color=COLOR_CORAL)
            else:
                self.progress_battery.configure(progress_color=COLOR_EMERALD)
                self.lbl_battery.configure(text_color=COLOR_EMERALD)

        elif key == "anc_mode":
            mode_map = {
                protocol.ANC_MODE_OFF: "ANC OFF",
                protocol.ANC_MODE_ON: "ANC ON",
                protocol.ANC_MODE_TRANSPARENCY: "Transparency"
            }
            str_val = mode_map.get(value, "ANC OFF")
            self.var_anc.set(str_val)
            self._update_anc_tiles_ui(str_val)

        elif key == "work_mode":
            self.var_game_mode.set(value == protocol.WORK_MODE_GAMING)

        elif key == "device_name":
            self.lbl_dev_name.configure(text=value)

        elif key == "eq":
            gains = value.get("gains", [0]*10)
            name = value.get("name", "Custom")

            cur_preset = self.var_eq_preset.get()
            custom_presets = config.get_custom_presets()
            expected_gains = protocol.EQ_PRESETS.get(cur_preset) or custom_presets.get(cur_preset)
            if expected_gains and expected_gains == gains:
                name = cur_preset

            self.var_eq_preset.set(name)
            self._highlight_active_preset(name)
            self._update_delete_button_state(name)
            for i in range(min(10, len(gains))):
                val = gains[i]
                self.eq_sliders[i].set(val)
                self.eq_labels[i].configure(
                    text=f"{val:+d}dB",
                    text_color=COLOR_ACCENT if val != 0 else COLOR_TEXT_MUTED
                )
            self._redraw_eq_curve()

    # -----------------------------------------------------------------------
    # SYSTEM TRAY INTEGRATION
    # -----------------------------------------------------------------------
    def _init_tray_icon(self):
        if not pystray:
            return
        try:
            ico_path = get_resource_path(os.path.join("assets", "icon.ico"))
            if not os.path.exists(ico_path):
                img_path = get_resource_path(os.path.join("assets", "headphone.png"))
                pil_img = Image.open(img_path) if os.path.exists(img_path) else Image.new("RGBA", (64, 64), (229, 169, 60, 255))
            else:
                pil_img = Image.open(ico_path)

            menu = pystray.Menu(
                pystray.MenuItem("Open Audio Studio", self._show_window_from_tray, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Apply OnePlus Buds 3", lambda icon, item: self._apply_preset_from_tray("OnePlus Buds 3")),
                pystray.MenuItem("Apply AirPods Profile", lambda icon, item: self._apply_preset_from_tray("AirPods")),
                pystray.MenuItem("Apply Stored Custom EQ", lambda icon, item: self._apply_preset_from_tray("Custom")),
                pystray.MenuItem("Apply Flat / Reference", lambda icon, item: self._apply_preset_from_tray("Default / Flat")),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Start with Windows", self._toggle_startup_from_tray, checked=lambda item: is_windows_startup_enabled()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Exit Studio", self._quit_app)
            )

            self.tray_icon = pystray.Icon("ZEB-Silencio-200T", pil_img, "ZEB-Silencio 200T Studio", menu)
            self.tray_icon.run_detached()
        except Exception as e:
            print(f"[Tray] Error initializing tray icon: {e}")

    def _show_window_from_tray(self, icon=None, item=None):
        self.after(0, self._restore_window)

    def _restore_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _on_window_close(self):
        self.withdraw()

    def _apply_preset_from_tray(self, preset_name: str):
        self.after(0, lambda: self._select_preset(preset_name))

    def _toggle_startup_from_tray(self, icon=None, item=None):
        current = is_windows_startup_enabled()
        set_windows_startup(not current)
        self.var_startup.set(not current)

    def _quit_app(self, icon=None, item=None):
        self.controller.stop_auto_reconnect()
        self.controller.disconnect()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.after(0, self.destroy)


def main():
    app = SilencioApp()
    app.mainloop()


if __name__ == "__main__":
    main()
