"""
High-Level Headphone Controller for ZEB-Silencio 200T
Manages headphone state, sends requests, and interprets responses/notifications.
"""

import time
import threading
from typing import Dict, List, Any, Optional, Callable
from app.connection import BluetoothConnection, find_silencio_com_port, get_available_com_ports
from app import protocol


class HeadphoneController:
    def __init__(self, port: Optional[str] = None):
        self.conn = BluetoothConnection(port)
        self.conn.on_packet_received = self._handle_packet
        self.conn.on_connection_change = self._handle_connection_change
        
        # State
        self.device_name = "ZEB-Silencio 200T"
        self.battery = 0
        self.is_charging = False
        self.anc_mode = protocol.ANC_MODE_OFF # 0=OFF, 1=ON, 2=TRANSPARENCY
        self.work_mode = protocol.WORK_MODE_NORMAL # 0=NORMAL, 1=GAMING
        self.warning_tone = protocol.WARNING_TONE_ON # 0=OFF, 1=ON
        self.one_drag_two = protocol.ONE_DRAG_TWO_OFF # 0=OFF, 1=ON
        self.current_eq_name = "Default / Flat"
        self.eq_gains = [0] * 10
        self.firmware_version = ""
        
        # Observer callbacks
        self.on_state_update: Optional[Callable[[str, Any], None]] = None
        self.on_connection_update: Optional[Callable[[bool, str], None]] = None

    @property
    def is_connected(self) -> bool:
        return self.conn.is_connected

    def connect(self, port: Optional[str] = None) -> bool:
        success = self.conn.connect(port)
        if success:
            # Query current device info after short delay
            threading.Thread(target=self._delayed_init_query, daemon=True).start()
        return success

    def disconnect(self):
        self.conn.disconnect()

    def _delayed_init_query(self):
        time.sleep(0.5)
        self.query_device_info()

    def query_device_info(self):
        """Sends DeviceInfo request to fetch all initial states."""
        query_payload = protocol.build_device_info_query()
        self.conn.send_command(protocol.COMMAND_DEVICE_INFO, query_payload)

    def set_anc_mode(self, mode: int):
        """
        Sets ANC mode:
          0 = ANC OFF
          1 = ANC ON
          2 = Transparency Mode
        """
        self.anc_mode = mode
        payload = protocol.build_anc_request(mode)
        self.conn.send_command(protocol.COMMAND_ANC_MODE, payload)
        self._notify_state("anc_mode", mode)

    def set_work_mode(self, mode: int):
        """
        Sets Work mode (Gaming / Normal):
          0 = Normal (Music mode)
          1 = Gaming mode (Low latency)
        """
        self.work_mode = mode
        payload = protocol.build_work_mode_request(mode)
        self.conn.send_command(protocol.COMMAND_WORK_MODE, payload)
        self._notify_state("work_mode", mode)

    def set_warning_tone(self, enabled: bool):
        """Enable or disable voice prompt tones."""
        val = protocol.WARNING_TONE_ON if enabled else protocol.WARNING_TONE_OFF
        self.warning_tone = val
        payload = protocol.build_warning_tone_request(val)
        self.conn.send_command(protocol.COMMAND_WARNING_TONE, payload)
        self._notify_state("warning_tone", val)

    def set_one_drag_two(self, enabled: bool):
        """Enable or disable dual device pairing (multipoint)."""
        val = protocol.ONE_DRAG_TWO_ON if enabled else protocol.ONE_DRAG_TWO_OFF
        self.one_drag_two = val
        payload = protocol.build_one_drag_two_request(val)
        self.conn.send_command(protocol.COMMAND_ONE_DRAG_TWO, payload)
        self._notify_state("one_drag_two", val)

    def set_eq_preset(self, preset_name: str):
        """Applies a built-in EQ preset."""
        if preset_name in protocol.EQ_PRESETS:
            gains = protocol.EQ_PRESETS[preset_name]
            self.current_eq_name = preset_name
            self.eq_gains = list(gains)
            # Find preset index (0 for Flat, etc.)
            preset_idx = list(protocol.EQ_PRESETS.keys()).index(preset_name)
            payload = protocol.build_eq_request(preset_idx, gains, is_custom=False)
            self.conn.send_command(protocol.COMMAND_EQ, payload)
            self._notify_state("eq", {"name": self.current_eq_name, "gains": self.eq_gains})

    def set_custom_eq(self, gains: List[int]):
        """Applies custom 10-band EQ gains."""
        self.current_eq_name = "Custom"
        self.eq_gains = list(gains)
        payload = protocol.build_eq_request(0, gains, is_custom=True)
        self.conn.send_command(protocol.COMMAND_EQ, payload)
        self._notify_state("eq", {"name": "Custom", "gains": self.eq_gains})

    def find_device(self):
        """Triggers find device ring/beep on headphones."""
        payload = bytes([1]) # Ring start
        self.conn.send_command(protocol.COMMAND_FIND_DEVICE, payload)

    def _handle_packet(self, cmd: int, cmd_type: int, payload: bytes):
        """Processes incoming response/notification packets."""
        # Check if it's a DeviceInfo response or Notification
        if cmd in (protocol.COMMAND_DEVICE_INFO, protocol.COMMAND_NOTIFY):
            tlvs = protocol.parse_tlv_payload(payload)
            for tag, val in tlvs.items():
                self._process_tlv(tag, val)
        elif cmd == protocol.COMMAND_ANC_MODE:
            if len(payload) >= 1:
                self.anc_mode = payload[0]
                self._notify_state("anc_mode", self.anc_mode)
        elif cmd == protocol.COMMAND_WORK_MODE:
            if len(payload) >= 1:
                self.work_mode = payload[0]
                self._notify_state("work_mode", self.work_mode)
        elif cmd == protocol.COMMAND_WARNING_TONE:
            if len(payload) >= 1:
                self.warning_tone = payload[0]
                self._notify_state("warning_tone", self.warning_tone)
        elif cmd == protocol.COMMAND_EQ:
            eq_data = protocol.parse_eq_info(payload)
            self.eq_gains = eq_data["gains"]
            if eq_data["is_custom"]:
                self.current_eq_name = "Custom"
            self._notify_state("eq", {"name": self.current_eq_name, "gains": self.eq_gains})

    def _process_tlv(self, tag: int, val: bytes):
        if tag == protocol.INFO_DEVICE_POWER:
            bat_info = protocol.parse_battery_info(val)
            self.battery = bat_info["battery"]
            self.is_charging = bat_info["is_charging"]
            self._notify_state("battery", bat_info)
        elif tag == protocol.INFO_ANC_MODE:
            if len(val) >= 1:
                self.anc_mode = val[0]
                self._notify_state("anc_mode", self.anc_mode)
        elif tag == protocol.INFO_WORK_MODE:
            if len(val) >= 1:
                self.work_mode = val[0]
                self._notify_state("work_mode", self.work_mode)
        elif tag == protocol.INFO_WARNING_TONE:
            if len(val) >= 1:
                self.warning_tone = val[0]
                self._notify_state("warning_tone", self.warning_tone)
        elif tag == protocol.INFO_ONE_DRAG_TWO:
            if len(val) >= 1:
                self.one_drag_two = val[-1]
                self._notify_state("one_drag_two", self.one_drag_two)
        elif tag == protocol.INFO_EQ_SETTING:
            eq_data = protocol.parse_eq_info(val)
            self.eq_gains = eq_data["gains"]
            if eq_data["is_custom"]:
                self.current_eq_name = "Custom"
            self._notify_state("eq", {"name": self.current_eq_name, "gains": self.eq_gains})
        elif tag == protocol.INFO_BLUETOOTH_NAME:
            try:
                self.device_name = val.decode("utf-8", errors="ignore").rstrip("\x00")
                self._notify_state("device_name", self.device_name)
            except Exception:
                pass
        elif tag == protocol.INFO_FIRMWARE_VERSION:
            try:
                self.firmware_version = val.decode("utf-8", errors="ignore").rstrip("\x00")
                self._notify_state("firmware_version", self.firmware_version)
            except Exception:
                pass

    def _notify_state(self, key: str, value: Any):
        if self.on_state_update:
            try:
                self.on_state_update(key, value)
            except Exception as e:
                print(f"[Controller] State update callback error: {e}")

    def _handle_connection_change(self, connected: bool, message: str):
        if self.on_connection_update:
            try:
                self.on_connection_update(connected, message)
            except Exception as e:
                print(f"[Controller] Connection update callback error: {e}")
