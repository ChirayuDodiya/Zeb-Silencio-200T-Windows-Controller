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

# Standard Presets
EQ_PRESETS: Dict[str, List[int]] = {
    "Default / Flat": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "Pop": [2, 1, 0, -1, -2, -1, 0, 1, 2, 3],
    "Rock": [4, 3, 2, 0, -1, 0, 2, 3, 4, 4],
    "Jazz": [3, 2, 1, 2, -1, -1, 0, 1, 2, 3],
    "Classical": [4, 3, 2, 2, -2, -2, 0, 2, 3, 3],
    "Country": [2, 1, 0, 1, 2, 1, 0, 1, 2, 2],
    "Hip Hop": [5, 4, 2, 1, -1, -1, 1, 2, 3, 4],
    "Bass Boost": [6, 5, 4, 2, 1, 0, 0, 0, 0, 0],
    "Vocal": [-2, -2, -1, 1, 3, 4, 3, 1, 0, -1],
    "Treble Boost": [-1, 0, 0, 0, 1, 2, 3, 5, 6, 6]
}


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
    Creates a DeviceInfo query requesting all essential state TLVs:
    Power, AncMode, WorkMode, EqSettings, WarningTone, OneDragTwo, BluetoothName, FwVersion
    """
    tags_to_request = [
        INFO_DEVICE_POWER,
        INFO_ANC_MODE,
        INFO_WORK_MODE,
        INFO_EQ_SETTING,
        INFO_WARNING_TONE,
        INFO_ONE_DRAG_TWO,
        INFO_BLUETOOTH_NAME,
        INFO_FIRMWARE_VERSION,
        INFO_ANC_GAIN,
        INFO_TRANSPARENCY_GAIN,
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


def build_warning_tone_request(mode: int) -> bytes:
    """0 = OFF, 1 = ON"""
    return bytes([mode & 0xFF])


def build_one_drag_two_request(mode: int) -> bytes:
    """[1, 1, mode] where mode is 0 = OFF, 1 = ON"""
    return bytes([1, 1, mode & 0xFF])


def build_eq_request(preset_id: int, gains: List[int], is_custom: bool = False) -> bytes:
    """
    Builds EQ payload:
      Byte 0: count of bands (10)
      Byte 1: preset id or (custom_id + 32)
      Bytes 2..11: 10 gain values (signed bytes, -12 to +12 dB)
    """
    count = 10
    mode_id = (preset_id + 32) if is_custom else preset_id
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
    """
    packets = []
    while len(buffer) >= 5:
        # Check header
        seq = buffer[0] & 0x0F
        cmd = buffer[1]
        cmd_type = buffer[2]
        frag_info = buffer[3]
        payload_len = buffer[4]
        
        total_len = 5 + payload_len
        if len(buffer) < total_len:
            # Need more data
            break
            
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
    Byte 0: Headphone / Left battery: (b & 0x7F) is level %, (b & 0x80) != 0 is charging.
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
