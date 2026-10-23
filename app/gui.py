"""
CustomTkinter Desktop GUI for ZEB-Silencio 200T
Modern Dark Mode Interface with ANC, 10-Band EQ, Gaming Mode, and Battery Monitoring.
"""

import os
import sys
import time
import threading
import customtkinter as ctk
from PIL import Image
from typing import List, Optional

try:
    import pystray
except ImportError:
    pystray = None

from app.controller import HeadphoneController
from app.connection import find_silencio_com_port, get_available_com_ports
from app import protocol
from app import config

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
    """Get absolute path to resource, works for dev and for PyInstaller onefile bundles."""
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

class ConfirmDialog(ctk.CTkToplevel):
    def __init__(self, parent, title: str, message: str, on_confirm, confirm_text: str = "Confirm"):
        super().__init__(parent)
        self.title(title)
        self.geometry("380x160")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(fg_color="#0f172a")
        self.transient(parent)
        self.grab_set()

        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 190
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 80
            self.geometry(f"380x160+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=15, weight="bold"), text_color="#f8fafc").pack(pady=(18, 6))
        ctk.CTkLabel(self, text=message, font=ctk.CTkFont(size=12), text_color="#94a3b8", wraplength=340).pack(pady=(0, 16))

        btn_box = ctk.CTkFrame(self, fg_color="transparent")
        btn_box.pack(fill="x", padx=25)

        ctk.CTkButton(btn_box, text="Cancel", width=90, fg_color="#334155", hover_color="#475569", command=self.destroy).pack(side="left")
        
        def confirm_and_close():
            self.destroy()
            on_confirm()

        ctk.CTkButton(btn_box, text=confirm_text, width=100, fg_color="#dc2626", hover_color="#b91c1c", command=confirm_and_close).pack(side="right")


class SilencioApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Start minimized if requested via startup flag
        if "--minimized" in sys.argv or "--background" in sys.argv:
            self.withdraw()

        # Window Config
        self.title("ZEB-Silencio 200T - Windows Controller")
        self.geometry("980x760")
        self.minsize(860, 680)
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Set Window Icon
        ico_path = get_resource_path(os.path.join("assets", "icon.ico"))
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        # Controller
        self.controller = HeadphoneController(mac=config.get_mac_address())
        self.controller.on_state_update = self._on_state_update_threadsafe
        self.controller.on_connection_update = self._on_connection_update_threadsafe

        # UI State Variables
        self.var_anc = ctk.StringVar(value="ANC OFF")
        self.var_game_mode = ctk.BooleanVar(value=False)
        self.var_eq_preset = ctk.StringVar(value=config.get_default_preset())
        self.eq_sliders: List[ctk.CTkSlider] = []
        self.eq_labels: List[ctk.CTkLabel] = []
        self.preset_buttons: Dict[str, ctk.CTkButton] = {}

        self._build_ui()

        # Minimize to System Tray instead of quitting on 'X'
        self.protocol("WM_DELETE_WINDOW", self._on_window_close)

        # System Tray Icon
        self.tray_icon = None
        self._init_tray_icon()

        # Ensure Windows startup is active so background auto-tuning works on boot
        if not is_windows_startup_enabled():
            set_windows_startup(True)

        # Start auto-reconnect watcher in background on start
        self.after(200, self._auto_connect_startup)

    def _build_ui(self):
        # Main Grid Layout (2 rows: Header, Body)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # 1. Header Frame
        header = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color="#18181b")
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_columnconfigure(1, weight=1)

        # Logo / Title
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.grid(row=0, column=0, padx=20, pady=12, sticky="w")
        
        title_lbl = ctk.CTkLabel(
            title_box, 
            text="ZEB-Silencio 200T", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_lbl.pack(side="left")

        sub_lbl = ctk.CTkLabel(
            title_box, 
            text="Control Center", 
            font=ctk.CTkFont(size=13), 
            text_color="#94a3b8"
        )
        sub_lbl.pack(side="left", padx=(8, 0))

        # Connection Controls in Header
        conn_box = ctk.CTkFrame(header, fg_color="transparent")
        conn_box.grid(row=0, column=2, padx=20, pady=10, sticky="e")

        self.lbl_status_pill = ctk.CTkLabel(
            conn_box,
            text="● Disconnected",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ef4444",
            fg_color="#27272a",
            corner_radius=12,
            padx=12,
            pady=4
        )
        self.lbl_status_pill.pack(side="left", padx=8)

        # Port Selector
        self.cbox_ports = ctk.CTkComboBox(
            conn_box,
            values=self._get_port_list(),
            width=110,
            command=self._on_port_selected
        )
        self.cbox_ports.pack(side="left", padx=5)

        self.btn_connect = ctk.CTkButton(
            conn_box,
            text="Connect",
            width=90,
            command=self._toggle_connection,
            fg_color="#2563eb",
            hover_color="#1d4ed8"
        )
        self.btn_connect.pack(side="left", padx=5)

        # 2. Main Scrollable Container
        main_scroll = ctk.CTkScrollableFrame(self, fg_color="#0f172a")
        main_scroll.grid(row=1, column=0, sticky="nsew", padx=15, pady=(10, 5))
        main_scroll.grid_columnconfigure(0, weight=1)
        main_scroll.grid_columnconfigure(1, weight=2)

        # Left Column: Device Card & Settings
        left_col = ctk.CTkFrame(main_scroll, fg_color="transparent")
        left_col.grid(row=0, column=0, sticky="nsew", padx=(5, 10), pady=5)

        # Right Column: ANC & Equalizer
        right_col = ctk.CTkFrame(main_scroll, fg_color="transparent")
        right_col.grid(row=0, column=1, sticky="nsew", padx=(10, 5), pady=5)

        # --- DEVICE PREVIEW CARD (Left) ---
        dev_card = ctk.CTkFrame(left_col, corner_radius=12, fg_color="#1e293b")
        dev_card.pack(fill="x", pady=(0, 15))

        # Headphone Image
        img_path = get_resource_path(os.path.join("assets", "headphone.png"))
        if os.path.exists(img_path):
            try:
                pil_img = Image.open(img_path)
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(190, 190))
                lbl_img = ctk.CTkLabel(dev_card, image=ctk_img, text="")
                lbl_img.pack(pady=(15, 5))
            except Exception as e:
                print(f"[UI] Error loading image: {e}")

        self.lbl_dev_name = ctk.CTkLabel(
            dev_card, 
            text="ZEB-Silencio 200T", 
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.lbl_dev_name.pack(pady=(0, 2))

        self.lbl_dev_chip = ctk.CTkLabel(
            dev_card, 
            text="Hybrid 48dB ANC • Bluetrum Wireless", 
            font=ctk.CTkFont(size=12), 
            text_color="#94a3b8"
        )
        self.lbl_dev_chip.pack(pady=(0, 15))

        # Battery Section
        bat_box = ctk.CTkFrame(dev_card, fg_color="#0f172a", corner_radius=10)
        bat_box.pack(fill="x", padx=15, pady=(0, 15))

        bat_header = ctk.CTkFrame(bat_box, fg_color="transparent")
        bat_header.pack(fill="x", padx=12, pady=(10, 4))
        
        ctk.CTkLabel(bat_header, text="Battery Level", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        self.lbl_battery = ctk.CTkLabel(bat_header, text="-- %", font=ctk.CTkFont(size=14, weight="bold"), text_color="#10b981")
        self.lbl_battery.pack(side="right")

        self.progress_battery = ctk.CTkProgressBar(bat_box, height=10, corner_radius=5)
        self.progress_battery.set(0.0)
        self.progress_battery.pack(fill="x", padx=12, pady=(0, 12))

        # Action Buttons
        btn_action_box = ctk.CTkFrame(dev_card, fg_color="transparent")
        btn_action_box.pack(fill="x", padx=15, pady=(0, 15))

        btn_refresh = ctk.CTkButton(
            btn_action_box,
            text="Refresh",
            width=100,
            command=self._refresh_status,
            fg_color="#334155",
            hover_color="#475569"
        )
        btn_refresh.pack(side="left", expand=True, padx=4)

        btn_find = ctk.CTkButton(
            btn_action_box,
            text="Find Device",
            width=100,
            command=self._find_device,
            fg_color="#334155",
            hover_color="#475569"
        )
        btn_find.pack(side="left", expand=True, padx=4)

        # --- FEATURE SWITCHES CARD (Left) ---
        features_card = ctk.CTkFrame(left_col, corner_radius=12, fg_color="#1e293b")
        features_card.pack(fill="x", pady=0)

        ctk.CTkLabel(
            features_card, 
            text="Headphone Features", 
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # Switch 1: Gaming Mode
        f1 = ctk.CTkFrame(features_card, fg_color="transparent")
        f1.pack(fill="x", padx=15, pady=(6, 15))
        ctk.CTkLabel(f1, text="Low Latency Gaming Mode", font=ctk.CTkFont(size=13)).pack(side="left")
        self.sw_game = ctk.CTkSwitch(f1, text="", variable=self.var_game_mode, command=self._on_game_mode_toggle)
        self.sw_game.pack(side="right")

        # --- NOISE CANCELLATION (ANC) CARD (Right) ---
        anc_card = ctk.CTkFrame(right_col, corner_radius=12, fg_color="#1e293b")
        anc_card.pack(fill="x", pady=(0, 15))

        anc_hdr = ctk.CTkFrame(anc_card, fg_color="transparent")
        anc_hdr.pack(fill="x", padx=18, pady=(15, 8))
        ctk.CTkLabel(anc_hdr, text="Active Noise Cancellation", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        self.lbl_anc_status = ctk.CTkLabel(anc_hdr, text="OFF", font=ctk.CTkFont(size=13, weight="bold"), text_color="#94a3b8")
        self.lbl_anc_status.pack(side="right")

        # ANC Segmented Buttons
        self.seg_anc = ctk.CTkSegmentedButton(
            anc_card,
            values=["ANC OFF", "ANC ON", "Transparency"],
            variable=self.var_anc,
            command=self._on_anc_selected,
            selected_color="#0284c7",
            selected_hover_color="#0369a1",
            height=42,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.seg_anc.pack(fill="x", padx=18, pady=(0, 18))

        # --- 10-BAND EQUALIZER CARD (Right) ---
        eq_card = ctk.CTkFrame(right_col, corner_radius=12, fg_color="#1e293b")
        eq_card.pack(fill="x", pady=0)

        eq_hdr = ctk.CTkFrame(eq_card, fg_color="transparent")
        eq_hdr.pack(fill="x", padx=18, pady=(15, 8))
        ctk.CTkLabel(eq_hdr, text="10-Band Equalizer", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")

        self.lbl_default_indicator = ctk.CTkLabel(
            eq_hdr,
            text=f"(Default: {config.get_default_preset()})",
            font=ctk.CTkFont(size=11),
            text_color="#38bdf8"
        )
        self.lbl_default_indicator.pack(side="left", padx=8)

        self.btn_delete_preset = ctk.CTkButton(
            eq_hdr,
            text="Delete Preset",
            width=100,
            height=28,
            command=self._delete_current_preset_prompt,
            fg_color="#27272a",
            hover_color="#3f3f46",
            text_color="#71717a",
            font=ctk.CTkFont(size=11, weight="bold"),
            state="disabled"
        )
        self.btn_delete_preset.pack(side="right")

        # Preset Buttons Grid (Android App Style)
        self.preset_frame = ctk.CTkFrame(eq_card, fg_color="transparent")
        self.preset_frame.pack(fill="x", padx=18, pady=(0, 10))
        self._build_preset_buttons()

        # 10 Sliders Container
        sliders_frame = ctk.CTkFrame(eq_card, fg_color="#0f172a", corner_radius=10)
        sliders_frame.pack(fill="x", padx=18, pady=(0, 18))
        sliders_frame.grid_columnconfigure(list(range(10)), weight=1)

        freq_labels = ["32Hz", "62Hz", "125Hz", "250Hz", "500Hz", "1kHz", "2kHz", "4kHz", "8kHz", "16kHz"]
        default_preset = config.get_default_preset()
        if default_preset == "Custom":
            init_gains = config.get_custom_eq()
        else:
            init_gains = protocol.EQ_PRESETS.get(default_preset, [0] * 10)
        for i in range(10):
            col_box = ctk.CTkFrame(sliders_frame, fg_color="transparent")
            col_box.grid(row=0, column=i, padx=3, pady=12, sticky="nsew")

            # Gain label on top
            val_lbl = ctk.CTkLabel(col_box, text=f"{init_gains[i]:+d}dB", font=ctk.CTkFont(size=11), text_color="#38bdf8")
            val_lbl.pack(pady=(0, 4))
            self.eq_labels.append(val_lbl)

            # Vertical Slider
            slider = ctk.CTkSlider(
                col_box,
                from_=-12,
                to=12,
                number_of_steps=24,
                orientation="vertical",
                height=160,
                command=lambda val, idx=i: self._on_slider_moved(idx, val)
            )
            slider.set(init_gains[i])
            slider.pack(pady=4)
            self.eq_sliders.append(slider)

            # Freq label on bottom
            f_lbl = ctk.CTkLabel(col_box, text=freq_labels[i], font=ctk.CTkFont(size=11), text_color="#94a3b8")
            f_lbl.pack(pady=(4, 0))

        # Equalizer Action Buttons
        eq_actions = ctk.CTkFrame(eq_card, fg_color="transparent")
        eq_actions.pack(fill="x", padx=18, pady=(0, 18))

        self.btn_set_default = ctk.CTkButton(
            eq_actions,
            text="Set as Default on Connect",
            width=180,
            height=36,
            command=self._set_current_as_default,
            fg_color="#334155",
            hover_color="#475569",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_set_default.pack(side="left", padx=(0, 10))

        self.btn_save_preset = ctk.CTkButton(
            eq_actions,
            text="+ Save as Preset",
            width=140,
            height=36,
            command=self._save_preset_prompt,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_save_preset.pack(side="left", padx=(0, 10))

        btn_apply_eq = ctk.CTkButton(
            eq_actions,
            text="Apply to Headphone",
            height=36,
            command=self._apply_current_eq,
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        btn_apply_eq.pack(side="left", fill="x", expand=True)

        # 3. Status Bar (Bottom)
        self.lbl_log = ctk.CTkLabel(
            self,
            text="Ready. Select COM port and click Connect.",
            font=ctk.CTkFont(size=12),
            text_color="#64748b",
            anchor="w"
        )
        self.lbl_log.grid(row=2, column=0, sticky="ew", padx=20, pady=(2, 6))

    def _get_port_list(self) -> List[str]:
        ports = get_available_com_ports()
        items = [p[0] for p in ports]
        # Prefer COM5 or auto-discovered
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
            self._log("Disconnected by user. (Click Connect to resume auto-connect)")
        else:
            port = self.cbox_ports.get()
            self._log(f"Connecting to {port}...")
            self.controller.start_auto_reconnect(port)
            threading.Thread(target=lambda: self.controller.connect(port), daemon=True).start()

    def _on_port_selected(self, choice: str):
        if self.controller.is_connected:
            self.controller.disconnect()

    def _refresh_status(self):
        if self.controller.is_connected:
            self._log("Querying headphone status...")
            threading.Thread(target=self._run_refresh, daemon=True).start()
        else:
            self._log("Headphone is not connected.")

    def _run_refresh(self):
        try:
            self.controller.refresh_sync()
            self._log(f"Status refreshed! Battery: {self.controller.battery}%, EQ: {self.controller.current_eq_name}")
        except Exception as e:
            print(f"[UI] Refresh error: {e}")
            self._log("Refresh failed.")

    def _find_device(self):
        if self.controller.is_connected:
            self._log("Beeping headphones (Find My Device)...")
            self.controller.find_device()
        else:
            self._log("Headphone is not connected.")

    def _on_anc_selected(self, mode_str: str):
        if mode_str == "ANC ON":
            self.controller.set_anc_mode(protocol.ANC_MODE_ON)
            self._log("Switched to Active Noise Cancellation (ANC ON)")
        elif mode_str == "Transparency":
            self.controller.set_anc_mode(protocol.ANC_MODE_TRANSPARENCY)
            self._log("Switched to Transparency / Ambient Mode")
        else:
            self.controller.set_anc_mode(protocol.ANC_MODE_OFF)
            self._log("Switched to ANC OFF")

    def _on_game_mode_toggle(self):
        val = self.var_game_mode.get()
        mode = protocol.WORK_MODE_GAMING if val else protocol.WORK_MODE_NORMAL
        self.controller.set_work_mode(mode)
        self._log(f"Gaming Mode set to: {'ON' if val else 'OFF'}")

    def _build_preset_buttons(self):
        for widget in self.preset_frame.winfo_children():
            widget.destroy()
        self.preset_buttons.clear()

        all_presets = list(protocol.EQ_PRESETS.keys()) + list(config.get_custom_presets().keys())
        active_preset = self.var_eq_preset.get()

        cols = 4
        for i, name in enumerate(all_presets):
            row = i // cols
            col = i % cols
            is_active = (name == active_preset)
            btn = ctk.CTkButton(
                self.preset_frame,
                text=name,
                height=32,
                corner_radius=6,
                font=ctk.CTkFont(size=11, weight="bold" if is_active else "normal"),
                fg_color="#0284c7" if is_active else "#1e293b",
                hover_color="#0369a1" if is_active else "#334155",
                text_color="#ffffff" if is_active else "#cbd5e1",
                border_width=1 if is_active else 0,
                border_color="#38bdf8",
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
            self.eq_sliders[i].set(gains[i])
            self.eq_labels[i].configure(text=f"{gains[i]:+d}dB")

        self.controller.set_eq_preset(preset_name)
        self._highlight_active_preset(preset_name)
        self._update_delete_button_state(preset_name)
        self._log(f"Loaded EQ Preset: {preset_name}")

    def _highlight_active_preset(self, active_name: str):
        for name, btn in self.preset_buttons.items():
            is_active = (name == active_name)
            btn.configure(
                fg_color="#0284c7" if is_active else "#1e293b",
                hover_color="#0369a1" if is_active else "#334155",
                text_color="#ffffff" if is_active else "#cbd5e1",
                font=ctk.CTkFont(size=11, weight="bold" if is_active else "normal"),
                border_width=1 if is_active else 0,
                border_color="#38bdf8"
            )

    def _update_delete_button_state(self, preset_name: str):
        if preset_name in config.get_custom_presets():
            self.btn_delete_preset.configure(state="normal", fg_color="#dc2626", hover_color="#b91c1c", text_color="#ffffff")
        else:
            self.btn_delete_preset.configure(state="disabled", fg_color="#27272a", text_color="#71717a")

    def _on_slider_moved(self, idx: int, value: float):
        int_val = int(round(value))
        self.eq_labels[idx].configure(text=f"{int_val:+d}dB")
        self.var_eq_preset.set("Custom")
        self._highlight_active_preset("")
        self._update_delete_button_state("Custom")
        self.controller.mark_user_action()

    def _save_preset_prompt(self):
        dialog = ctk.CTkInputDialog(
            text="Enter a name for your custom EQ preset:",
            title="Save Custom EQ Preset"
        )
        name = dialog.get_input()
        if name and name.strip():
            clean_name = name.strip()
            if clean_name in protocol.EQ_PRESETS:
                self._log(f"Cannot overwrite built-in preset '{clean_name}'. App-provided presets cannot be changed.")
                return
            gains = [int(round(s.get())) for s in self.eq_sliders]
            config.save_custom_preset(clean_name, gains)
            self._build_preset_buttons()
            self._select_preset(clean_name)
            self._log(f"Saved custom preset: '{clean_name}'")

    def _delete_current_preset_prompt(self):
        target = self.var_eq_preset.get()
        if target in config.get_custom_presets():
            ConfirmDialog(
                self,
                title="Delete Preset",
                message=f"Are you sure you want to permanently delete custom preset '{target}'?",
                on_confirm=lambda: self._execute_delete_preset(target),
                confirm_text="Delete"
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
            self.lbl_default_indicator.configure(text=f"(Default: {current})")
        self._log(f"Default EQ on connect set to: {current}")

    def _apply_current_eq(self):
        gains = [int(round(s.get())) for s in self.eq_sliders]
        config.set_custom_eq(gains)
        self.controller.set_custom_eq(gains)
        self._log(f"Applied EQ curve: {gains}")

    def _log(self, text: str):
        self.lbl_log.configure(text=text)

    # Threadsafe UI Updates from Controller Events
    def _on_state_update_threadsafe(self, key: str, value):
        self.after(0, lambda: self._apply_state_update(key, value))

    def _on_connection_update_threadsafe(self, connected: bool, message: str):
        self.after(0, lambda: self._apply_connection_update(connected, message))

    def _apply_connection_update(self, connected: bool, message: str):
        if connected:
            self.lbl_status_pill.configure(
                text="● Connected", 
                text_color="#10b981", 
                fg_color="#064e3b"
            )
            self.btn_connect.configure(text="Disconnect", fg_color="#dc2626", hover_color="#b91c1c")
            def_preset = config.get_default_preset()
            self._log(f"Connected: {message} ● Automatically applied {def_preset} EQ!")
            self._select_preset(def_preset)
            if self.tray_icon:
                try:
                    self.tray_icon.notify(
                        f"Connected to Bluetooth! Automatically applied {def_preset} EQ.",
                        "ZEB-Silencio 200T"
                    )
                except Exception:
                    pass
        else:
            self.lbl_status_pill.configure(
                text="● Disconnected", 
                text_color="#ef4444", 
                fg_color="#27272a"
            )
            self.btn_connect.configure(text="Connect", fg_color="#2563eb", hover_color="#1d4ed8")
            self._log(f"{message} (Auto-connect active: waiting for Bluetooth link...)")

    def _apply_state_update(self, key: str, value):
        if key == "battery":
            pct = value.get("battery", 0)
            is_chg = value.get("is_charging", False)
            chg_icon = " (Charging)" if is_chg else ""
            self.lbl_battery.configure(text=f"{pct}%{chg_icon}")
            self.progress_battery.set(pct / 100.0)
            if pct <= 20:
                self.progress_battery.configure(progress_color="#ef4444")
            else:
                self.progress_battery.configure(progress_color="#10b981")
        elif key == "anc_mode":
            mode_map = {
                protocol.ANC_MODE_OFF: ("ANC OFF", "OFF"),
                protocol.ANC_MODE_ON: ("ANC ON", "ON (Cancelling)"),
                protocol.ANC_MODE_TRANSPARENCY: ("Transparency", "Transparency")
            }
            str_val, disp_val = mode_map.get(value, ("ANC OFF", "OFF"))
            self.var_anc.set(str_val)
            self.lbl_anc_status.configure(text=disp_val)
        elif key == "work_mode":
            self.var_game_mode.set(value == protocol.WORK_MODE_GAMING)
        elif key == "device_name":
            self.lbl_dev_name.configure(text=value)
        elif key == "eq":
            gains = value.get("gains", [0]*10)
            name = value.get("name", "Custom")

            # Keep continuous state if gains match the currently selected preset
            cur_preset = self.var_eq_preset.get()
            custom_presets = config.get_custom_presets()
            expected_gains = protocol.EQ_PRESETS.get(cur_preset) or custom_presets.get(cur_preset)
            if expected_gains and expected_gains == gains:
                name = cur_preset

            self.var_eq_preset.set(name)
            self._highlight_active_preset(name)
            self._update_delete_button_state(name)
            for i in range(min(10, len(gains))):
                self.eq_sliders[i].set(gains[i])
                self.eq_labels[i].configure(text=f"{gains[i]:+d}dB")

    # System Tray Methods
    def _init_tray_icon(self):
        if not pystray:
            return
        try:
            ico_path = get_resource_path(os.path.join("assets", "icon.ico"))
            if not os.path.exists(ico_path):
                img_path = get_resource_path(os.path.join("assets", "headphone.png"))
                pil_img = Image.open(img_path) if os.path.exists(img_path) else Image.new("RGBA", (64, 64), (37, 99, 235, 255))
            else:
                pil_img = Image.open(ico_path)

            menu = pystray.Menu(
                pystray.MenuItem("Open Control Center", self._show_window_from_tray, default=True),
                pystray.Menu.SEPARATOR,

                pystray.MenuItem("Apply OnePlus Buds 3", lambda icon, item: self._apply_preset_from_tray("OnePlus Buds 3")),
                pystray.MenuItem("Apply AirPods Preset", lambda icon, item: self._apply_preset_from_tray("AirPods")),
                pystray.MenuItem("Apply Stored Custom EQ", lambda icon, item: self._apply_preset_from_tray("Custom")),
                pystray.MenuItem("Apply Flat / Default", lambda icon, item: self._apply_preset_from_tray("Default / Flat")),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "Start with Windows", 
                    self._toggle_startup_from_tray, 
                    checked=lambda item: is_windows_startup_enabled()
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Exit", self._quit_app)
            )

            self.tray_icon = pystray.Icon("ZEB-Silencio-200T", pil_img, "ZEB-Silencio 200T Controller", menu)
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
        """Hides window to tray so background auto-EQ continues running."""
        self.withdraw()

    def _apply_preset_from_tray(self, preset_name: str):
        self.after(0, lambda: self._on_eq_preset_selected(preset_name))

    def _toggle_startup_from_tray(self, icon=None, item=None):
        current = is_windows_startup_enabled()
        set_windows_startup(not current)

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
