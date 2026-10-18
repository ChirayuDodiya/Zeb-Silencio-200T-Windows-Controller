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

from app.controller import HeadphoneController
from app.connection import find_silencio_com_port, get_available_com_ports
from app import protocol


class SilencioApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Config
        self.title("ZEB-Silencio 200T - Windows Controller")
        self.geometry("980x760")
        self.minsize(860, 680)
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Controller
        self.controller = HeadphoneController()
        self.controller.on_state_update = self._on_state_update_threadsafe
        self.controller.on_connection_update = self._on_connection_update_threadsafe

        # UI State Variables
        self.var_anc = ctk.StringVar(value="ANC OFF")
        self.var_game_mode = ctk.BooleanVar(value=False)
        self.var_warning_tone = ctk.BooleanVar(value=True)
        self.var_one_drag_two = ctk.BooleanVar(value=False)
        self.var_eq_preset = ctk.StringVar(value="Default / Flat")
        self.eq_sliders: List[ctk.CTkSlider] = []
        self.eq_labels: List[ctk.CTkLabel] = []

        self._build_ui()

        # Auto-connect in background on start
        self.after(500, self._auto_connect_startup)

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
            text="🎧 ZEB-Silencio 200T", 
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
        img_path = os.path.join(os.path.dirname(__file__), "assets", "headphone.png")
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
            text="🔄 Refresh",
            width=100,
            command=self._refresh_status,
            fg_color="#334155",
            hover_color="#475569"
        )
        btn_refresh.pack(side="left", expand=True, padx=4)

        btn_find = ctk.CTkButton(
            btn_action_box,
            text="🔔 Find Device",
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
        f1.pack(fill="x", padx=15, pady=6)
        ctk.CTkLabel(f1, text="⚡ Low Latency Gaming Mode", font=ctk.CTkFont(size=13)).pack(side="left")
        self.sw_game = ctk.CTkSwitch(f1, text="", variable=self.var_game_mode, command=self._on_game_mode_toggle)
        self.sw_game.pack(side="right")

        # Switch 2: Voice Prompt
        f2 = ctk.CTkFrame(features_card, fg_color="transparent")
        f2.pack(fill="x", padx=15, pady=6)
        ctk.CTkLabel(f2, text="📢 Voice Prompt / Tone", font=ctk.CTkFont(size=13)).pack(side="left")
        self.sw_tone = ctk.CTkSwitch(f2, text="", variable=self.var_warning_tone, command=self._on_warning_tone_toggle)
        self.sw_tone.pack(side="right")

        # Switch 3: Dual Connection
        f3 = ctk.CTkFrame(features_card, fg_color="transparent")
        f3.pack(fill="x", padx=15, pady=(6, 15))
        ctk.CTkLabel(f3, text="🔗 Dual Device Multipoint", font=ctk.CTkFont(size=13)).pack(side="left")
        self.sw_dual = ctk.CTkSwitch(f3, text="", variable=self.var_one_drag_two, command=self._on_one_drag_two_toggle)
        self.sw_dual.pack(side="right")

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
        eq_hdr.pack(fill="x", padx=18, pady=(15, 12))
        ctk.CTkLabel(eq_hdr, text="10-Band Equalizer", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")

        # Preset Dropdown
        self.cbox_presets = ctk.CTkComboBox(
            eq_hdr,
            values=list(protocol.EQ_PRESETS.keys()) + ["Custom"],
            variable=self.var_eq_preset,
            command=self._on_eq_preset_selected,
            width=150
        )
        self.cbox_presets.pack(side="right", padx=(10, 0))

        btn_reset_eq = ctk.CTkButton(
            eq_hdr,
            text="Reset",
            width=65,
            command=self._reset_eq,
            fg_color="#334155",
            hover_color="#475569"
        )
        btn_reset_eq.pack(side="right")

        # 10 Sliders Container
        sliders_frame = ctk.CTkFrame(eq_card, fg_color="#0f172a", corner_radius=10)
        sliders_frame.pack(fill="x", padx=18, pady=(0, 18))
        sliders_frame.grid_columnconfigure(list(range(10)), weight=1)

        freq_labels = ["32Hz", "62Hz", "125Hz", "250Hz", "500Hz", "1kHz", "2kHz", "4kHz", "8kHz", "16kHz"]
        for i in range(10):
            col_box = ctk.CTkFrame(sliders_frame, fg_color="transparent")
            col_box.grid(row=0, column=i, padx=3, pady=12, sticky="nsew")

            # Gain label on top
            val_lbl = ctk.CTkLabel(col_box, text="0dB", font=ctk.CTkFont(size=11), text_color="#38bdf8")
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
            slider.set(0)
            slider.pack(pady=4)
            self.eq_sliders.append(slider)

            # Freq label on bottom
            f_lbl = ctk.CTkLabel(col_box, text=freq_labels[i], font=ctk.CTkFont(size=11), text_color="#94a3b8")
            f_lbl.pack(pady=(4, 0))

        # Apply EQ Button
        btn_apply_eq = ctk.CTkButton(
            eq_card,
            text="Save & Apply EQ to Headphone",
            height=36,
            command=self._apply_current_eq,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        btn_apply_eq.pack(fill="x", padx=18, pady=(0, 18))

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
        self._log(f"Auto-detected port: {auto_port}. Attempting connection...")
        threading.Thread(target=lambda: self.controller.connect(auto_port), daemon=True).start()

    def _toggle_connection(self):
        if self.controller.is_connected:
            self.controller.disconnect()
        else:
            port = self.cbox_ports.get()
            self._log(f"Connecting to {port}...")
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

    def _on_warning_tone_toggle(self):
        val = self.var_warning_tone.get()
        self.controller.set_warning_tone(val)
        self._log(f"Voice Prompts set to: {'ON' if val else 'OFF'}")

    def _on_one_drag_two_toggle(self):
        val = self.var_one_drag_two.get()
        self.controller.set_one_drag_two(val)
        self._log(f"Dual Device Multipoint set to: {'ON' if val else 'OFF'}")

    def _on_eq_preset_selected(self, preset_name: str):
        if preset_name in protocol.EQ_PRESETS:
            gains = protocol.EQ_PRESETS[preset_name]
            for i in range(10):
                self.eq_sliders[i].set(gains[i])
                self.eq_labels[i].configure(text=f"{gains[i]:+d}dB")
            self.controller.set_eq_preset(preset_name)
            self._log(f"Loaded EQ Preset: {preset_name}")

    def _on_slider_moved(self, idx: int, value: float):
        int_val = int(round(value))
        self.eq_labels[idx].configure(text=f"{int_val:+d}dB")
        self.var_eq_preset.set("Custom")
        self.cbox_presets.set("Custom")
        self.controller.mark_user_action()

    def _reset_eq(self):
        self.var_eq_preset.set("Default / Flat")
        self._on_eq_preset_selected("Default / Flat")

    def _apply_current_eq(self):
        gains = [int(round(s.get())) for s in self.eq_sliders]
        self.controller.set_custom_eq(gains)
        self._log(f"Applied Custom EQ: {gains}")

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
            self._log(f"Connected: {message}")
        else:
            self.lbl_status_pill.configure(
                text="● Disconnected", 
                text_color="#ef4444", 
                fg_color="#27272a"
            )
            self.btn_connect.configure(text="Connect", fg_color="#2563eb", hover_color="#1d4ed8")
            self._log(message)

    def _apply_state_update(self, key: str, value):
        if key == "battery":
            pct = value.get("battery", 0)
            is_chg = value.get("is_charging", False)
            chg_icon = " ⚡" if is_chg else ""
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
        elif key == "warning_tone":
            self.var_warning_tone.set(value == protocol.WARNING_TONE_ON)
        elif key == "one_drag_two":
            self.var_one_drag_two.set(value == protocol.ONE_DRAG_TWO_ON)
        elif key == "device_name":
            self.lbl_dev_name.configure(text=value)
        elif key == "eq":
            gains = value.get("gains", [0]*10)
            name = value.get("name", "Custom")
            self.var_eq_preset.set(name)
            self.cbox_presets.set(name)
            for i in range(min(10, len(gains))):
                self.eq_sliders[i].set(gains[i])
                self.eq_labels[i].configure(text=f"{gains[i]:+d}dB")


def main():
    app = SilencioApp()
    app.mainloop()


if __name__ == "__main__":
    main()
