"""
High-Level Headphone Controller for ZEB-Silencio 200T
Manages headphone state, sends requests, and interprets responses/notifications.
Supports live background synchronization with phone app changes.
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
        self.current_eq_name = "OnePlus Buds 3"
        self.eq_gains = list(protocol.EQ_PRESETS.get("OnePlus Buds 3", [3, 4, 3, 2, 1, 0, -1, -3, -3, -2]))
        self.firmware_version = ""
        
        # Observer callbacks
        self.on_state_update: Optional[Callable[[str, Any], None]] = None
        self.on_connection_update: Optional[Callable[[bool, str], None]] = None

        # Concurrency & Synchronous Request/Response Queue
        self._query_lock = threading.Lock()
        self._pending_tag: Optional[int] = None
        self._pending_event = threading.Event()
        self._last_user_action_time = 0.0
        self._stop_poll_event = threading.Event()
        self._poll_thread: Optional[threading.Thread] = None

    @property
    def is_connected(self) -> bool:
        return self.conn.is_connected

    def mark_user_action(self):
        """Debounces background polling queries when user interacts with controls."""
        self._last_user_action_time = time.time()

    def query_tag_sync(self, tag: int, timeout: float = 0.4) -> bool:
        """
        Sends a single-tag DeviceInfo query and synchronously waits for its
        response on the reader thread (or timeout) before returning.
        Guarantees zero packet collisions with Bluetrum half-duplex UART receiver.
        """
        with self._query_lock:
            if not self.conn.is_connected:
                return False
            self._pending_tag = tag
            self._pending_event.clear()
            self.conn.send_command(protocol.COMMAND_DEVICE_INFO, bytes([tag, 0]))
            responded = self._pending_event.wait(timeout)
            self._pending_tag = None
            return responded

    def connect(self, port: Optional[str] = None, sync: bool = False) -> bool:
        success = self.conn.connect(port)
        if success:
            if sync:
                self._delayed_init_query()
            else:
                threading.Thread(target=self._delayed_init_query, daemon=True).start()
            self._start_polling()
        return success

    def disconnect(self):
        self._stop_polling()
        self.conn.disconnect()

    def _start_polling(self):
        self._stop_poll_event.clear()
        if self._poll_thread is None or not self._poll_thread.is_alive():
            self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._poll_thread.start()

    def _stop_polling(self):
        self._stop_poll_event.set()

    def _poll_loop(self):
        """
        Periodically queries device info so changes made on the phone (e.g. preset EQ, ANC)
        are automatically detected and reflected on the laptop.
        """
        poll_count = 0
        while not self._stop_poll_event.wait(1.5):
            if not self.is_connected:
                break
            # Skip poll query if user recently changed a setting from this laptop
            if time.time() - self._last_user_action_time < 2.0:
                continue
            try:
                poll_count += 1
                self.query_tag_sync(protocol.INFO_EQ_SETTING, timeout=0.35)
                self.query_tag_sync(protocol.INFO_DEVICE_POWER, timeout=0.35)
                if poll_count % 4 == 0:
                    self.query_tag_sync(protocol.INFO_ANC_MODE, timeout=0.35)
                    self.query_tag_sync(protocol.INFO_WORK_MODE, timeout=0.35)
            except Exception as e:
                print(f"[Controller] Polling error: {e}")

    def _delayed_init_query(self):
        time.sleep(0.3)
        # 1. Send MTU Handshake required by Bluetrum chip
        self.query_tag_sync(0xFF, timeout=0.4)
        # 2. Query core device states sequentially with synchronous waits
        self.query_tag_sync(protocol.INFO_DEVICE_POWER, timeout=0.35)
        self.query_tag_sync(protocol.INFO_ANC_MODE, timeout=0.35)
        self.query_tag_sync(protocol.INFO_WORK_MODE, timeout=0.35)
        # 3. Automatically apply OnePlus Buds 3 preset to headphone on connect
        if "OnePlus Buds 3" in protocol.EQ_PRESETS:
            time.sleep(0.1)
            self.set_eq_preset("OnePlus Buds 3")

    def query_device_info(self):
        """Sequentially queries core device tags using synchronous request-response."""
        self.query_tag_sync(protocol.INFO_EQ_SETTING, timeout=0.35)
        self.query_tag_sync(protocol.INFO_DEVICE_POWER, timeout=0.35)

    def refresh_sync(self):
        """Full synchronous refresh of all headphone parameters."""
        self.query_tag_sync(protocol.INFO_DEVICE_POWER, timeout=0.35)
        self.query_tag_sync(protocol.INFO_EQ_SETTING, timeout=0.35)
        self.query_tag_sync(protocol.INFO_ANC_MODE, timeout=0.35)
        self.query_tag_sync(protocol.INFO_WORK_MODE, timeout=0.35)

    def set_anc_mode(self, mode: int):
        """
        Sets ANC mode:
          0 = ANC OFF
          1 = ANC ON
          2 = Transparency Mode
        """
        self.mark_user_action()
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
        self.mark_user_action()
        self.work_mode = mode
        payload = protocol.build_work_mode_request(mode)
        self.conn.send_command(protocol.COMMAND_WORK_MODE, payload)
        self._notify_state("work_mode", mode)

    def set_warning_tone(self, enabled: bool):
        """Enable or disable voice prompt tones."""
        self.mark_user_action()
        val = protocol.WARNING_TONE_ON if enabled else protocol.WARNING_TONE_OFF
        self.warning_tone = val
        payload = protocol.build_warning_tone_request(val)
        self.conn.send_command(protocol.COMMAND_WARNING_TONE, payload)
        self._notify_state("warning_tone", val)

    def set_one_drag_two(self, enabled: bool):
        """Enable or disable dual device pairing (multipoint)."""
        self.mark_user_action()
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
            mode_id = protocol.PRESET_TO_MODE.get(preset_name, 0)
            is_custom = (mode_id >= 32)
            payload = protocol.build_eq_request(mode_id, gains, is_custom=is_custom)
            self.mark_user_action()
            self.conn.send_command(protocol.COMMAND_EQ, payload)
            self._notify_state("eq", {"name": self.current_eq_name, "gains": self.eq_gains, "mode": mode_id})

    def set_custom_eq(self, gains: List[int]):
        """Applies custom 10-band EQ gains."""
        self.eq_gains = list(gains)
        preset_name = protocol.identify_preset_name(32, self.eq_gains)
        self.current_eq_name = preset_name
        payload = protocol.build_eq_request(32, gains, is_custom=True)
        self.mark_user_action()
        self.conn.send_command(protocol.COMMAND_EQ, payload)
        self._notify_state("eq", {"name": self.current_eq_name, "gains": self.eq_gains, "mode": 32})

    def find_device(self):
        """Triggers find device ring/beep on headphones."""
        payload = bytes([1]) # Ring start
        self.conn.send_command(protocol.COMMAND_FIND_DEVICE, payload)

    def _update_eq_state(self, eq_data: Dict[str, Any]):
        """Updates internal EQ state and notifies observers if changed."""
        mode = eq_data.get("mode", 0)
        gains = eq_data.get("gains", [0] * 10)
        preset_name = protocol.identify_preset_name(mode, gains)

        changed = (not getattr(self, "_initial_eq_synced", False) or 
                   self.current_eq_name != preset_name or 
                   self.eq_gains != gains)
        self._initial_eq_synced = True
        self.current_eq_name = preset_name
        self.eq_gains = list(gains)

        if changed:
            print(f"[Controller] EQ updated: '{preset_name}' (mode {mode}) -> {gains}")
            self._notify_state("eq", {"name": self.current_eq_name, "gains": self.eq_gains, "mode": mode})

    def _handle_packet(self, cmd: int, cmd_type: int, payload: bytes):
        """Processes incoming response/notification packets."""
        # 1. DeviceInfo response or Notification with TLVs
        if cmd in (protocol.COMMAND_DEVICE_INFO, protocol.COMMAND_NOTIFY):
            tlvs = protocol.parse_tlv_payload(payload)
            for tag, val in tlvs.items():
                self._process_tlv(tag, val)

            # Wake up pending synchronous query
            if self._pending_tag is not None:
                if self._pending_tag in tlvs:
                    self._pending_event.set()
                elif self._pending_tag == 0xFF and (0xFF in tlvs or 35 in tlvs or cmd in (protocol.COMMAND_DEVICE_INFO, protocol.COMMAND_NOTIFY)):
                    self._pending_event.set()

        # 2. EQ update (only if it has full gain data, not a 1-byte command ACK)
        elif cmd in (protocol.COMMAND_EQ, protocol.INFO_EQ_SETTING):
            if len(payload) >= 2:
                eq_data = protocol.parse_eq_info(payload)
                self._update_eq_state(eq_data)

        # 3. ANC Mode (only notifications, ignore 1-byte command ACK)
        elif cmd in (protocol.COMMAND_ANC_MODE, protocol.INFO_ANC_MODE):
            if cmd_type == protocol.COMMAND_TYPE_NOTIFY and len(payload) >= 1:
                if self.anc_mode != payload[0]:
                    self.anc_mode = payload[0]
                    self._notify_state("anc_mode", self.anc_mode)

        # 4. Work Mode (only notifications, ignore 1-byte command ACK)
        elif cmd in (protocol.COMMAND_WORK_MODE, protocol.INFO_WORK_MODE):
            if cmd_type == protocol.COMMAND_TYPE_NOTIFY and len(payload) >= 1:
                if self.work_mode != payload[0]:
                    self.work_mode = payload[0]
                    self._notify_state("work_mode", self.work_mode)

        # 5. Warning Tone (only notifications, ignore 1-byte command ACK)
        elif cmd in (protocol.COMMAND_WARNING_TONE, protocol.INFO_WARNING_TONE):
            if cmd_type == protocol.COMMAND_TYPE_NOTIFY and len(payload) >= 1:
                if self.warning_tone != payload[0]:
                    self.warning_tone = payload[0]
                    self._notify_state("warning_tone", self.warning_tone)

        # 6. Battery Power
        elif cmd == protocol.INFO_DEVICE_POWER:
            bat_info = protocol.parse_battery_info(payload)
            self.battery = bat_info["battery"]
            self.is_charging = bat_info["is_charging"]
            self._notify_state("battery", bat_info)

    def _process_tlv(self, tag: int, val: bytes):
        if tag == protocol.INFO_DEVICE_POWER:
            bat_info = protocol.parse_battery_info(val)
            changed = (self.battery != bat_info["battery"] or self.is_charging != bat_info["is_charging"])
            self.battery = bat_info["battery"]
            self.is_charging = bat_info["is_charging"]
            if changed:
                print(f"[Controller] Battery updated: {self.battery}% (Charging: {self.is_charging})")
            self._notify_state("battery", bat_info)
        elif tag == protocol.INFO_ANC_MODE:
            if len(val) >= 1:
                changed = (self.anc_mode != val[0])
                self.anc_mode = val[0]
                if changed:
                    print(f"[Controller] ANC updated: {self.anc_mode}")
                self._notify_state("anc_mode", self.anc_mode)
        elif tag == protocol.INFO_WORK_MODE:
            if len(val) >= 1:
                changed = (self.work_mode != val[0])
                self.work_mode = val[0]
                if changed:
                    print(f"[Controller] Work mode updated: {self.work_mode}")
                self._notify_state("work_mode", self.work_mode)
        elif tag == protocol.INFO_WARNING_TONE:
            if len(val) >= 1 and self.warning_tone != val[0]:
                self.warning_tone = val[0]
                self._notify_state("warning_tone", self.warning_tone)
        elif tag == protocol.INFO_ONE_DRAG_TWO:
            if len(val) >= 1 and self.one_drag_two != val[-1]:
                self.one_drag_two = val[-1]
                self._notify_state("one_drag_two", self.one_drag_two)
        elif tag == protocol.INFO_EQ_SETTING:
            eq_data = protocol.parse_eq_info(val)
            self._update_eq_state(eq_data)
        elif tag == protocol.INFO_BLUETOOTH_NAME:
            try:
                name = val.decode("utf-8", errors="ignore").rstrip("\x00")
                if name and self.device_name != name:
                    self.device_name = name
                    self._notify_state("device_name", self.device_name)
            except Exception:
                pass
        elif tag == protocol.INFO_FIRMWARE_VERSION:
            try:
                fw = val.decode("utf-8", errors="ignore").rstrip("\x00")
                if fw and self.firmware_version != fw:
                    self.firmware_version = fw
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
        if not connected:
            self._stop_polling()
        if self.on_connection_update:
            try:
                self.on_connection_update(connected, message)
            except Exception as e:
                print(f"[Controller] Connection update callback error: {e}")
