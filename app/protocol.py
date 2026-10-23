"""
Bluetrum Protocol Implementation
Reversed from ZEB-Aural IQ (com.xibier.audio) for ZEB-Silencio 200T
"""

from typing import Dict, List, Tuple, Any, Optional

# Command IDs
COMMAND_EQ = 32                 # 0x20
COMMAND_MUSIC_CONTROL = 33      # 0x21
COMMAND_KEY = 34                # 0x22
COMMAND_AUTO_SHUTDOWN = 35      # 0x23
COMMAND_FACTORY_RESET = 36      # 0x24
COMMAND_WORK_MODE = 37          # 0x25 (Game Mode / Normal)
COMMAND_IN_EAR_DETECT = 38      # 0x26
COMMAND_DEVICE_INFO = 39        # 0x27
COMMAND_NOTIFY = 40             # 0x28
COMMAND_LANGUAGE = 41           # 0x29
COMMAND_FIND_DEVICE = 42        # 0x2A
COMMAND_AUTO_ANSWER = 43        # 0x2B
COMMAND_ANC_MODE = 44           # 0x2C
COMMAND_BLUETOOTH_NAME = 45     # 0x2D
COMMAND_LED_MODE = 46           # 0x2E
COMMAND_CLEAR_PAIR_RECORD = 47  # 0x2F
COMMAND_ANC_GAIN = 48           # 0x30
COMMAND_TRANSPARENCY_GAIN = 49  # 0x31
COMMAND_SOUND_EFFECT_3D = 50    # 0x32
COMMAND_ONE_DRAG_TWO = 51       # 0x33 (Dual device pairing)
COMMAND_WARNING_TONE = 52       # 0x34 (Prompt tone)
COMMAND_DISABLE_TOUCH = 53      # 0x35
COMMAND_CUSTOM = 55             # 0x37

# Command Types
COMMAND_TYPE_REQUEST = 1
COMMAND_TYPE_RESPONSE = 2
COMMAND_TYPE_NOTIFY = 3

# TLV Tags
INFO_DEVICE_POWER = 1
INFO_FIRMWARE_VERSION = 2
INFO_BLUETOOTH_NAME = 3
INFO_EQ_SETTING = 4
INFO_KEY_SETTINGS = 5
INFO_DEVICE_VOLUME = 6
INFO_PLAY_STATE = 7
INFO_WORK_MODE = 8
INFO_IN_EAR_STATUS = 9
INFO_LANGUAGE_SETTING = 10
INFO_AUTO_ANSWER = 11
INFO_ANC_MODE = 12
INFO_IS_TWS = 13
INFO_TWS_CONNECTED = 14
INFO_LED_SWITCH = 15
INFO_FW_CHECKSUM = 16
INFO_ANC_GAIN = 17
INFO_TRANSPARENCY_GAIN = 18
INFO_ANC_GAIN_NUM = 19
INFO_TRANSPARENCY_GAIN_NUM = 20
INFO_ALL_EQ_SETTINGS = 21
INFO_MAIN_SIDE = 22
INFO_PRODUCT_COLOR = 23
INFO_SOUND_EFFECT_3D = 24
INFO_ONE_DRAG_TWO = 25
INFO_WARNING_TONE = 28
INFO_DISABLE_TOUCH = 29
INFO_MAX_VOLUME_SWITCH = 37
INFO_MAX_VOLUME_LEVEL = 38
INFO_DEVICE_SN = 49

# Modes
ANC_MODE_OFF = 0
ANC_MODE_ON = 1
ANC_MODE_TRANSPARENCY = 2

WORK_MODE_NORMAL = 0
WORK_MODE_GAMING = 1

WARNING_TONE_OFF = 0
WARNING_TONE_ON = 1

ONE_DRAG_TWO_OFF = 0
ONE_DRAG_TWO_ON = 1

# Standard 10-band EQ frequencies in Hz
EQ_FREQUENCIES = [32, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]

# Presets matching requested sound profiles
EQ_PRESETS: Dict[str, List[int]] = {
    "AirPods": [2, 3, 2, 1, 0, 1, 0, -2, -3, -1],
    "OnePlus Buds 3": [3, 4, 3, 2, 1, 0, -1, -3, -3, -2],
    "Default / Flat": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "Pop": [3, 1, 0, -2, -4, -4, -2, 0, 1, 2],
    "Rock": [-2, 0, 2, 4, -2, -2, 0, 0, 4, 4],
    "Classical": [0, 5, 5, 1, 0, 0, 0, 0, 2, 2],
    "Jazz": [0, 0, 0, 4, 4, 4, 0, 2, 3, 4],
    "Country": [-2, 0, 0, 2, 2, 0, 0, 0, 4, 4],
    "Hip Hop": [4, 3, 2, -1, 0, 1, 2, 1, 0, -2],
    "Bass Boost": [6, 5, 4, 2, 1, 0, 0, 0, 0, 0],
    "Vocal": [-2, -2, -1, 1, 3, 4, 3, 1, 0, -1]
}

# Bluetrum mode byte to preset name mapping
MODE_TO_PRESET: Dict[int, str] = {
    0: "Default / Flat",
    1: "Pop",
    2: "Rock",
    3: "Classical",
    4: "Jazz",
    5: "Country",
    6: "Hip Hop"
}

PRESET_TO_MODE: Dict[str, int] = {
    "AirPods": 32,
    "OnePlus Buds 3": 32,
    "Default / Flat": 0,
    "Pop": 1,
    "Rock": 2,
    "Classical": 3,
    "Jazz": 4,
    "Country": 5,
    "Hip Hop": 6,
    "Bass Boost": 32,
    "Vocal": 32,
    "Custom": 32
}


def identify_preset_name(mode: int, gains: List[int], custom_presets: Optional[Dict[str, List[int]]] = None) -> str:
    """
    Identifies the preset name given the mode byte and the 10 gain values.
    """
    # 1. Exact match against known preset gain curves
    for preset_name, preset_gains in EQ_PRESETS.items():
        if gains == preset_gains:
            return preset_name

    # 1b. Exact match against user custom presets
    if custom_presets:
        for preset_name, preset_gains in custom_presets.items():
            if gains == preset_gains:
                return preset_name
            
    # 2. Standard preset modes 0-6 if gains are close or default
    if mode in MODE_TO_PRESET and mode < 32:
        return MODE_TO_PRESET[mode]
            
    return "Custom" 


def build_packet(cmd: int, payload: bytes = b"", cmd_type: int = COMMAND_TYPE_REQUEST, seq: int = 0) -> bytes:
    """
    Builds a 5-byte header + payload packet according to Bluetrum protocol.
    Header format:
      Byte 0: seq & 0x0F
      Byte 1: cmd
      Byte 2: cmd_type
      Byte 3: 0 (fragment info: unfragmented)
      Byte 4: len(payload)
      Bytes 5..: payload
    """
    payload_len = len(payload)
    if payload_len > 250:
        # Note: If necessary, could fragment, but control packets are <= 32 bytes
        raise ValueError(f"Payload too large for single packet: {payload_len}")
    
    header = bytes([
        seq & 0x0F,
        cmd & 0xFF,
        cmd_type & 0xFF,
        0x00,
        payload_len & 0xFF
    ])
    return header + payload


def build_device_info_query() -> bytes:
    """
    Creates a compact DeviceInfo query fitting inside Bluetrum 15-byte MTU:
    Power (1), ANC Mode (12), Work Mode (8), EQ Setting (4).
    Payload length is 4 * 2 = 8 bytes.
    """
    tags_to_request = [
        INFO_DEVICE_POWER,
        INFO_ANC_MODE,
        INFO_WORK_MODE,
        INFO_EQ_SETTING,
    ]
    payload = bytearray()
    for tag in tags_to_request:
        payload.append(tag)
        payload.append(0)  # Length 0 means query
    return bytes(payload)


def build_anc_request(mode: int) -> bytes:
    """0 = OFF, 1 = ON, 2 = TRANSPARENCY"""
    return bytes([mode & 0xFF])


def build_work_mode_request(mode: int) -> bytes:
    """0 = NORMAL, 1 = GAMING (Low Latency)"""
    return bytes([mode & 0xFF])


def build_eq_request(preset_id: int, gains: List[int], is_custom: bool = False) -> bytes:
    """
    Builds EQ payload:
      Byte 0: count of bands (10)
      Byte 1: preset id or (custom_id + 32)
      Bytes 2..11: 10 gain values (signed bytes, -12 to +12 dB)
    """
    count = 10
    if is_custom and preset_id < 32:
        mode_id = preset_id + 32
    else:
        mode_id = preset_id
    payload = bytearray([count, mode_id & 0xFF])
    for i in range(count):
        g = gains[i] if i < len(gains) else 0
        g = max(-12, min(12, int(g)))
        payload.append(g & 0xFF)
    return bytes(payload)


def parse_packets_from_stream(buffer: bytearray) -> List[Tuple[int, int, bytes]]:
    """
    Parses complete frames from a byte buffer.
    Returns list of (cmd, cmd_type, payload).
    Modifies buffer in-place, removing parsed bytes.
    Includes framing recovery for corrupted or misaligned stream data.
    """
    packets = []
    while len(buffer) >= 5:
        cmd_type = buffer[2]
        payload_len = buffer[4]
        
        # Valid Bluetrum command types are 1 (Request), 2 (Response), 3 (Notify)
        # Valid payload lengths for control messages are <= 250
        if cmd_type not in (1, 2, 3) or payload_len > 250:
            # Framing de-sync: discard the first misaligned byte and re-scan
            del buffer[0]
            continue
            
        total_len = 5 + payload_len
        if len(buffer) < total_len:
            # Need more data for this complete packet
            break
            
        cmd = buffer[1]
        payload = bytes(buffer[5:total_len])
        del buffer[:total_len]
        packets.append((cmd, cmd_type, payload))
        
    return packets


def parse_tlv_payload(payload: bytes) -> Dict[int, bytes]:
    """
    Parses a concatenated TLV payload into a dictionary {tag: value_bytes}.
    """
    result = {}
    idx = 0
    while idx + 2 <= len(payload):
        tag = payload[idx]
        length = payload[idx + 1]
        val_start = idx + 2
        val_end = val_start + length
        if val_end <= len(payload):
            result[tag] = payload[val_start:val_end]
            idx = val_end
        else:
            break
    return result


def parse_battery_info(data: bytes) -> Dict[str, Any]:
    """
    Parses INFO_DEVICE_POWER TLV data.
    Byte 0: Left earbud (TWS)
    Byte 1: Right earbud / Headband main battery (Silencio 200T)
    Byte 2: Charging case
    For headband headphones (Silencio 200T), battery is reported in Byte 1 (right_battery).
    """
    res = {
        "battery": 0,
        "is_charging": False,
        "left_battery": 0,
        "left_charging": False,
        "right_battery": 0,
        "right_charging": False,
        "case_battery": 0,
        "case_charging": False
    }
    if len(data) > 0:
        b0 = data[0]
        res["left_battery"] = b0 & 0x7F
        res["left_charging"] = (b0 & 0x80) != 0
        res["battery"] = res["left_battery"]
        res["is_charging"] = res["left_charging"]
    if len(data) > 1:
        b1 = data[1]
        res["right_battery"] = b1 & 0x7F
        res["right_charging"] = (b1 & 0x80) != 0
        # For non-TWS / headband headphones, data[1] is the primary battery
        if res["right_battery"] > 0 or res["left_battery"] == 0:
            res["battery"] = res["right_battery"]
            res["is_charging"] = res["right_charging"]
    if len(data) > 2:
        b2 = data[2]
        res["case_battery"] = b2 & 0x7F
        res["case_charging"] = (b2 & 0x80) != 0
        
    return res


def parse_eq_info(data: bytes) -> Dict[str, Any]:
    """
    Parses INFO_EQ_SETTING TLV data.
    """
    if len(data) < 2:
        return {"mode": 0, "gains": [0]*10}
    
    count = data[0]
    mode = data[1]
    gains = []
    for i in range(2, min(2 + count, len(data))):
        val = data[i]
        # signed byte conversion
        if val > 127:
            val -= 256
        gains.append(val)
        
    # Pad to 10 if fewer
    while len(gains) < 10:
        gains.append(0)
        
    return {
        "count": count,
        "mode": mode,
        "is_custom": mode >= 32,
        "gains": gains
    }
