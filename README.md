# ZEB-Silencio 200T Windows Controller

Desktop companion software for Zebronics ZEB-Silencio 200T wireless ANC headphones on Windows. Reverse-engineered from the official Android companion app (ZEB-Aural IQ / `com.xibier.audio`).

---

## Features

- **Active Noise Cancellation (ANC) Control**:
  - ANC OFF
  - ANC ON (Hybrid 48dB Active Noise Cancellation)
  - Transparency Mode (Ambient audio passthrough)
- **10-Band Graphic Equalizer**:
  - Real-time adjustment across 10 bands: 32Hz, 62Hz, 125Hz, 250Hz, 500Hz, 1kHz, 2kHz, 4kHz, 8kHz, 16kHz
  - Sliders adjustable from -12 dB to +12 dB
  - Built-in presets: Default / Flat, OnePlus Buds 3, AirPods, Pop, Rock, Classical, Jazz, Country, Hip Hop, Bass Boost, Vocal
  - Android-style tap-to-activate preset buttons
  - Custom preset management: save custom EQ curves with unique names and delete user presets
  - Persistent default preset: automatically applied upon Bluetooth connection
- **Low-Latency Gaming Mode**:
  - Toggle ultra-low latency work mode for gaming and video playback
- **Battery Status & Monitoring**:
  - Real-time battery percentage monitoring and live charging status
- **Zero-Config Bluetooth Discovery & Auto-Reconnect**:
  - Automatic detection of paired headphones via Windows Bluetooth PnP APIs
  - Background auto-reconnect watcher restores connection whenever headphones are turned on
- **System Tray Integration**:
  - Minimizes to system notification tray
  - Quick-action context menu to switch EQ presets or restore window
- **Find Device**:
  - Triggers a beeping tone on the headphones to locate them
- **Desktop GUI & Command Line Interface (CLI)**:
  - CustomTkinter Dark Mode graphical interface (`run_app.bat` or `python run_app.py`)
  - Terminal CLI for scripting, macros, and shortcut keys (`cli.py`)

---

## Reverse-Engineering Summary

Analysis of the companion Android application (`com.xibier.audio`) revealed:
1. **Hardware Platform**:
   - Chipset: Bluetrum (AB series) audio processor.
2. **Communication Transport**:
   - Classic Bluetooth Serial Port Profile (SPP / RFCOMM) with standard SPP UUID `00001101-0000-1000-8000-00805F9B34FB`.
   - Windows automatically enumerates this as a Standard Serial over Bluetooth Link.
3. **Protocol Framing**:
   - 5-byte frame header:
     - Byte 0: `Sequence & 0x0F` (0..15 counter)
     - Byte 1: `Command ID` (e.g., `44` for ANC, `32` for EQ, `37` for Gaming Mode, `39` for Device Info)
     - Byte 2: `Command Type` (`1` = Request, `2` = Response, `3` = Notification)
     - Byte 3: `Fragment Info` (`0x00` for unfragmented frames)
     - Byte 4: `Payload Length`
   - TLV (Type-Length-Value) format for queries and telemetry reports.

---

## How to Run

### 1. Requirements
Ensure your headphones are paired with Windows via Bluetooth:
1. Turn on your ZEB-Silencio 200T headphones and ensure they are connected in Windows Settings -> Bluetooth & devices.
2. Install Python dependencies:
   ```cmd
   pip install -r requirements.txt
   ```

### 2. Launch GUI
Double-click `run_app.bat` or run:
```cmd
python run_app.py
```

### 3. Command Line Control (CLI)
Control headphone settings directly from terminal:
```cmd
# Check battery and current mode
python cli.py status

# Switch ANC modes
python cli.py anc on
python cli.py anc off
python cli.py anc trans

# Toggle Low-Latency Gaming Mode
python cli.py game on
python cli.py game off

# Apply EQ preset
python cli.py eq "OnePlus Buds 3"
python cli.py eq "AirPods"
python cli.py eq rock
python cli.py eq default
```

### 4. Build Standalone Executable (.exe)
To produce a single, portable executable that runs without Python installed:
```cmd
python build_exe.py
```
The output file will be generated at `ZEB-Silencio-200T.exe`.

---

## Project Structure

```
Headphone/
├── app/
│   ├── __init__.py           # Package version and metadata
│   ├── config.py             # User configuration (%APPDATA%) and preset storage
│   ├── connection.py         # Windows Bluetooth & serial COM port auto-discovery
│   ├── controller.py         # State manager, telemetry listeners, and high-level API
│   ├── gui.py                # CustomTkinter Dark Mode GUI application
│   ├── protocol.py           # Bluetrum binary protocol definitions and packet framing
│   └── assets/               # Application icons and device imagery
├── background_service.py     # Headless background service for silent auto-tuning
├── build_exe.py              # PyInstaller build automation script
├── cli.py                    # Command-line interface
├── README.md                 # Project documentation
├── requirements.txt          # Python dependencies
├── run_app.bat               # Windows batch launcher
├── run_app.py                # Python GUI entry point
├── start_background_service.bat
├── stop_background_service.bat
└── ZEB-Silencio-200T.exe     # Standalone portable Windows executable
```
