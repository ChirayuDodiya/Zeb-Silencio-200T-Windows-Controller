"""
Bluetooth Serial Port Connection Manager
Handles auto-discovery of ZEB-Silencio 200T COM port, connection lifecycle, and I/O.
"""

import sys
import time
import serial
import serial.tools.list_ports
import threading
import subprocess
import re
from typing import Optional, Callable, List, Tuple
from app.protocol import build_packet, parse_packets_from_stream

TARGET_MAC = "41:42:F3:8D:54:52"
TARGET_NAME_PATTERNS = ["silencio", "zeb-silencio", "zeb", "x1040", "x-1040"]
SPP_UUID = "{00001101-0000-1000-8000-00805F9B34FB}"


def find_silencio_com_port() -> Optional[str]:
    """
    Scans Windows PnP device list for a Serial Port linked to ZEB-Silencio 200T or its MAC address.
    """
    try:
        # Run PowerShell command to find Bluetooth Serial ports
        cmd = [
            "powershell", "-NoProfile", "-Command",
            'Get-PnpDevice -Class Ports | Select-Object FriendlyName, InstanceId | ConvertTo-Csv -NoTypeInformation'
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            lines = res.stdout.strip().splitlines()
            for line in lines[1:]: # Skip header
                parts = [p.strip('"\r ') for p in line.split('","')]
                if len(parts) >= 2:
                    friendly_name = parts[0]
                    instance_id = parts[1].upper()
                    
                    # Check if instance_id contains the MAC address 4142F38D5452
                    clean_mac = TARGET_MAC.replace(":", "").replace("-", "")
                    if clean_mac in instance_id:
                        # Extract COM port from FriendlyName, e.g. "Standard Serial over Bluetooth link (COM5)"
                        m = re.search(r'\((COM\d+)\)', friendly_name)
                        if m:
                            return m.group(1)
                            
                    # Alternatively check if instance_id has the SPP GUID
                    if SPP_UUID.upper() in instance_id:
                        for pattern in TARGET_NAME_PATTERNS:
                            if pattern in friendly_name.lower():
                                m = re.search(r'\((COM\d+)\)', friendly_name)
                                if m:
                                    return m.group(1)
    except Exception as e:
        print(f"[Discovery] Error querying PnP devices: {e}")
        
    # Fallback: scan available serial ports via pyserial
    ports = serial.tools.list_ports.comports()
    for p in ports:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").upper()
        clean_mac = TARGET_MAC.replace(":", "").replace("-", "")
        if clean_mac in hwid:
            return p.device
        if "bluetooth" in desc:
            for pattern in TARGET_NAME_PATTERNS:
                if pattern in desc:
                    return p.device
                    
    return None


def get_available_com_ports() -> List[Tuple[str, str]]:
    """Returns list of (port_name, description) for all system COM ports."""
    ports = serial.tools.list_ports.comports()
    return [(p.device, p.description) for p in ports]


class BluetoothConnection:
    def __init__(self, port: Optional[str] = None):
        self.port = port
        self.serial: Optional[serial.Serial] = None
        self.is_connected = False
        self.seq = 0
        self._rx_buffer = bytearray()
        self._lock = threading.Lock()
        self._running = False
        self._reader_thread: Optional[threading.Thread] = None
        
        # Callbacks
        self.on_packet_received: Optional[Callable[[int, int, bytes], None]] = None
        self.on_connection_change: Optional[Callable[[bool, str], None]] = None

    def connect(self, port: Optional[str] = None) -> bool:
        """Connects to the specified or auto-discovered COM port."""
        target_port = port or self.port or find_silencio_com_port()
        if not target_port:
            if self.on_connection_change:
                self.on_connection_change(False, "No Bluetooth COM port found for ZEB-Silencio 200T.")
            return False
            
        self.port = target_port
        try:
            print(f"[Connection] Opening {self.port} at 115200 baud...")
            self.serial = serial.Serial(
                port=self.port,
                baudrate=115200,
                timeout=1.0,
                write_timeout=2.0
            )
            self.is_connected = True
            self._running = True
            self._rx_buffer.clear()
            
            # Start background reader thread
            self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self._reader_thread.start()
            
            print(f"[Connection] Connected to {self.port}!")
            if self.on_connection_change:
                self.on_connection_change(True, f"Connected to {self.port}")
            return True
        except Exception as e:
            self.is_connected = False
            self.serial = None
            err_msg = str(e)
            if "semaphore timeout" in err_msg.lower():
                err_msg = "Headphones not connected to Windows. Please turn on your headphones and connect via Windows Bluetooth Settings."
            print(f"[Connection] Connection failed: {err_msg}")
            if self.on_connection_change:
                self.on_connection_change(False, err_msg)
            return False

    def disconnect(self):
        """Disconnects serial port and terminates reader thread."""
        self._running = False
        if self.serial:
            try:
                self.serial.close()
            except Exception:
                pass
            self.serial = None
            
        self.is_connected = False
        if self.on_connection_change:
            self.on_connection_change(False, "Disconnected")

    def send_command(self, cmd: int, payload: bytes = b"", cmd_type: int = 1) -> bool:
        """Constructs and sends a Bluetrum command packet."""
        with self._lock:
            if not self.is_connected or not self.serial:
                return False
                
            seq = self.seq
            self.seq = (self.seq + 1) % 16
            
            pkt = build_packet(cmd, payload, cmd_type, seq)
            try:
                self.serial.write(pkt)
                self.serial.flush()
                # print(f"[TX] CMD={cmd} TYPE={cmd_type} LEN={len(payload)}: {pkt.hex(' ')}")
                return True
            except Exception as e:
                print(f"[Connection] Write failed: {e}")
                self.disconnect()
                return False

    def _reader_loop(self):
        """Background thread continuously reading data from serial port."""
        while self._running and self.serial and self.serial.is_open:
            try:
                data = self.serial.read(self.serial.in_waiting or 1)
                if data:
                    self._rx_buffer.extend(data)
                    packets = parse_packets_from_stream(self._rx_buffer)
                    for cmd, cmd_type, payload in packets:
                        # print(f"[RX] CMD={cmd} TYPE={cmd_type} LEN={len(payload)}: {payload.hex(' ')}")
                        if self.on_packet_received:
                            try:
                                self.on_packet_received(cmd, cmd_type, payload)
                            except Exception as ex:
                                print(f"[Connection] Callback error: {ex}")
                else:
                    time.sleep(0.01)
            except (serial.SerialException, OSError) as e:
                print(f"[Connection] Serial read error: {e}")
                break
                
        if self.is_connected:
            self.disconnect()
