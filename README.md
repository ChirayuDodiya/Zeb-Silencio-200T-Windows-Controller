# ZEB-Silencio 200T Windows Controller 🎧

Desktop companion software for **Zebronics ZEB-Silencio 200T** wireless ANC headphones on Windows. Reverse-engineered from the official Android companion app (*ZEB-Aural IQ* / `com.xibier.audio`).

---

## 🚀 Features

- **Active Noise Cancellation (ANC) Control**:
  - `ANC OFF`
  - `ANC ON` (Hybrid 48dB Active Noise Cancellation)
  - `Transparency Mode` (Ambient audio passthrough)
- **10-Band Graphic Equalizer**:
  - Real-time adjustment for 10 bands: `32Hz`, `62Hz`, `125Hz`, `250Hz`, `500Hz`, `1kHz`, `2kHz`, `4kHz`, `8kHz`, `16kHz`
  - Gains adjustable from `-12 dB` to `+12 dB`
  - Presets: *Default / Flat, Pop, Rock, Jazz, Classical, Country, Hip Hop, Bass Boost, Vocal, Treble Boost, Custom*
- **Low-Latency Gaming Mode**:
  - Toggle ultra-low latency work mode for gaming and video playback.
- **Battery Status & Charging Indicator**:
  - Real-time battery percentage monitoring and live charging indicator (⚡).
- **Voice Prompt / Warning Tone Toggle**:
  - Enable or disable headphone voice feedback prompts.
- **Dual Device Connection (One Drag Two)**:
  - Toggle multipoint pairing with multiple devices.
- **Find My Device**:
  - Triggers a beeping tone on the headphones so you can easily locate them.
- **Both Desktop GUI & Command Line Interface (CLI)**:
  - Sleek Windows 11-style Dark Mode graphical interface (`run_app.bat` or `python run_app.py`).
  - Terminal CLI for hotkeys, macros, Stream Deck, and scripting (`cli.py`).

---

## 🔍 Reverse-Engineering Summary

Analysis of the extracted APK (`com.xibier.audio`) revealed:
1. **Hardware Platform**:
   - Chipset: **Bluetrum (AB series)** audio processor (device MAC prefix `41:42:...` = "AB").
2. **Communication Transport**:
   - Uses Classic Bluetooth **Serial Port Profile (SPP / RFCOMM)** with UUID `00001101-0000-1000-8000-00805F9B34FB`.
   - Windows automatically enumerates this as a Standard Serial over Bluetooth Link (`COM5` on your system).
3. **Protocol Framing**:
   - 5-byte frame header:
     - Byte 0: `Sequence & 0x0F` (0..15 counter)
     - Byte 1: `Command ID` (e.g., `44` for ANC, `32` for EQ, `37` for Gaming Mode, `39` for Device Info)
     - Byte 2: `Command Type` (`1` = Request, `2` = Response, `3` = Notification)
     - Byte 3: `Fragment Info` (`0x00` for unfragmented frames)
     - Byte 4: `Payload Length`
   - TLV (Type-Length-Value) format for queries and telemetry reports.

---

## 🖥️ How to Run

### 1. Requirements
Ensure your headphone is paired to Windows via Bluetooth:
1. Turn on your **ZEB-Silencio 200T** headphones and ensure they are connected to your Windows PC (Settings -> Bluetooth & devices).
2. Required python libraries (`customtkinter`, `pyserial`, `Pillow`) are already installed.

### 2. Launch GUI
Simply double click:
```cmd
run_app.bat
```
Or run from terminal:
```powershell
python run_app.py
```

### 3. Command Line Control (CLI)
You can also control everything directly from terminal:
```powershell
# Check current battery and status
python cli.py status

# Switch ANC Modes
python cli.py anc on
python cli.py anc off
python cli.py anc trans

# Toggle Low-Latency Gaming Mode
python cli.py game on
python cli.py game off

# Apply EQ Preset
python cli.py eq rock
python cli.py eq bassboost
python cli.py eq vocal

# Toggle Voice Prompt Tones
python cli.py tone on
python cli.py tone off
```

---

## 📁 Project Structure

```
d:\College\Headphone\
├── app\
│   ├── protocol.py       # Core Bluetrum binary protocol & TLV parser
│   ├── connection.py     # Windows Bluetooth / Serial COM port connection manager
│   ├── controller.py     # Headphone state manager & high-level command API
│   ├── gui.py            # CustomTkinter Dark Mode GUI
│   └── assets/           # Extracted icons and headphone image
├── run_app.py            # Desktop app entrypoint
├── run_app.bat           # 1-click Windows launcher
├── cli.py                # Command line interface tool
└── README.md             # Documentation
```
