# Comprehensive Reverse-Engineering Guide: ZEB-Silencio 200T

This document provides a complete, step-by-step breakdown of how the **ZEB-Silencio 200T** Android companion app was reverse-engineered from decompiled APK code, how each protocol value, UUID, and command structure was discovered, and how the system was ported to a native Windows controller.

---

## Table of Contents
1. [Initial APK Exploration & App Discovery](#1-initial-apk-exploration--app-discovery)
2. [Locating Chipset Architecture & SDKs](#2-locating-chipset-architecture--sdks)
3. [Matching the Physical Headphone Hardware](#3-matching-the-physical-headphone-hardware)
4. [Transport Layer Analysis: Bluetooth SPP vs BLE](#4-transport-layer-analysis-bluetooth-spp-vs-ble)
5. [Dissecting the Binary Framing Protocol](#5-dissecting-the-binary-framing-protocol)
6. [Decoding Commands, Requests, & Telemetry (TLV)](#6-decoding-commands-requests--telemetry-tlv)
7. [Extracting the 10-Band Equalizer Specifications](#7-extracting-the-10-band-equalizer-specifications)
8. [Connecting on Windows: The COM Port Discovery](#8-connecting-on-windows-the-com-port-discovery)
9. [Architecture of the Windows Port](#9-architecture-of-the-windows-port)

---

## 1. Initial APK Exploration & App Discovery

The directory contained decompiled code from JADX:
- `apk_code/resources/`: Application resources (`AndroidManifest.xml`, XML layouts, drawables, strings).
- `apk_code/sources/`: Decompiled Java source files across various Java packages.

### Step 1.1: Reading `AndroidManifest.xml`
Viewing `apk_code/resources/AndroidManifest.xml` provided:
```xml
package="com.xibier.audio"
android:theme="@style/Theme.Langsdom"
android:name="com.pairip.application.Application"
```
Key activities listed:
- `com.xibier.audio.ui.DeviceActivity` (Main control dashboard)
- `com.xibier.audio.ui.EqSettingActivity` (Equalizer interface)
- `com.xibier.audio.ui.EqCustomEditActivity` (Custom EQ curves)
- `com.xibier.audio.ui.KeySettingActivity` (Button gesture customization)
- `com.xibier.audio.ui.DeviceScanActivity` (Bluetooth scanning & pairing)
- `com.xibier.audio.ui.FirmwareUpgradeActivity` (OTA firmware updater)

### Step 1.2: Reading `strings.xml`
Inspecting `apk_code/resources/res/values/strings.xml` revealed the real product and app branding:
```xml
<string name="app_name">ZEB-Aural IQ</string>
<string name="anc_on">ANC ON</string>
<string name="anc_off">ANC OFF</string>
<string name="anc_switch">ANC switch</string>
```
This confirmed that the APK was **ZEB-Aural IQ**, the official Zebronics audio companion application.

---

## 2. Locating Chipset Architecture & SDKs

Audio headphones rely on dedicated SoC (System-on-a-Chip) Bluetooth processors. By listing the packages in `apk_code/sources/com/`:
- `com/xibier/audio` (App UI and data models)
- `com/bluetrum` (**Bluetrum Technology / 中科蓝讯**)
- `com/jieli` (**Zhuhai JieLi Technology / 杰理科技**)

In `apk_code/resources/assets/`, we found:
- `update_1.fot`: The `.fot` extension is the proprietary firmware update package format for **Bluetrum** Bluetooth chips.

### Step 2.1: The Chipset Selector Fork in Java
In `apk_code/sources/cb/j.java` (the ViewModel for `DeviceActivity`):
```java
public j() {
    if (va.l.f12407a.i() == 2) {
        this.f2654d = new wa.m();  // Bluetrum Implementation
    } else {
        this.f2654d = new n();     // JieLi Implementation
    }
}
```
And in `apk_code/sources/cb/l.java` (the Equalizer ViewModel):
```java
public l() {
    if (va.l.f12407a.i() == 2) {
        this.f2662d = new x();     // Bluetrum EQ Implementation
    } else {
        this.f2662d = new f4();    // JieLi EQ Implementation
    }
}
```
This proved that the app handles both chipsets, using `2` as the identifier for **Bluetrum**.

---

## 3. Matching the Physical Headphone Hardware

In `apk_code/sources/sa/i.java`, the app enumerates product definitions:
- `sa/e.java` (`X-1045`): Chipset type = `2` (Bluetrum)
- `sa/f.java` (`XM15B`): Chipset type = `1` (JieLi)
- `sa/g.java` (`X-1037`): Chipset type = `2` (Bluetrum)
- `sa/h.java` (`X1040` / `ZEB-Envy Pro`): Chipset type = `2` (Bluetrum)

### Step 3.1: Querying Windows Bluetooth Device Enumerator
By querying Windows PnP devices using PowerShell:
```powershell
Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName, InstanceId
```
The output contained:
```
FriendlyName : ZEB-Silencio 200T
InstanceId   : BTHENUM\DEV_4142F38D5452\7&13F7C83F&0&BLUETOOTHDEVICE_4142F38D5452
```

### Step 3.2: The MAC Address Clue
The MAC address of the headphone is:
$$\text{41 : 42 : F3 : 8D : 54 : 52}$$
In ASCII hexadecimal encoding:
- `0x41` = `'A'`
- `0x42` = `'B'`
`"AB"` is the universal signature prefix of **AppoTech / Bluetrum AB-series chips** (e.g., AB5301, AB5616, AB5656). This confirmed beyond any doubt that the **ZEB-Silencio 200T** is powered by the **Bluetrum** platform.

---

## 4. Transport Layer Analysis: Bluetooth SPP vs BLE

Did the app talk to the headphones over BLE GATT or Classic Bluetooth RFCOMM?

### Step 4.1: Checking BLE Advertisements
In `apk_code/sources/qa/a.java` and `apk_code/sources/com/xibier/audio/data/BleAdvMsg.java`:
```java
byte[] manufacturerData = scanRecord.getManufacturerSpecificData(3107); // 3107 = 0x0C23
```
In `BleAdvMsg.java`:
```java
this.bid = ByteUtil.bytesToInt(bArr[0], bArr[1]);
this.pid = ByteUtil.bytesToInt(bArr[2], bArr[3]);
this.edrConnectState = bArr[4];
// MAC address bytes are XOR masked with 0xAD (173):
for (int i = 5; i < 11; i++) {
    sb.append(ByteUtil.byteToClearHexString((byte) (bArr[i] ^ 173)));
}
this.edrMac = sb.toString();
```
The BLE advertisement is strictly used for proximity popups and device discovery (similar to Google Fast Pair).

### Step 4.2: Checking Connection Establishment
In `apk_code/sources/ra/a.java` (the Bluetrum device connection adapter):
```java
public static final UUID f10999o = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB");
...
@Override
public final void connect() {
    BluetoothSppService bluetoothSppService = new BluetoothSppService(...);
    this.f11003h = bluetoothSppService;
    bluetoothSppService.connect(this.f11002e, f10999o);
}
```
And in `apk_code/sources/com/bluetrum/devicemanager/bluetooth/BluetoothSppService.java`:
```java
public void write(byte[] bArr) {
    cVar.f7c.write(bArr); // Direct write to BluetoothSocket.getOutputStream()
}
```
`00001101-0000-1000-8000-00805F9B34FB` is the official Bluetooth SIG **Serial Port Profile (SPP)** UUID.
The communication channel is a direct, bidirectional RFCOMM serial socket.

---

## 5. Dissecting the Binary Framing Protocol

In `apk_code/sources/com/bluetrum/devicemanager/DeviceCommManager.java` and `f.java` / `g.java`, the framing mechanism is implemented:

### Step 5.1: The 5-Byte Packet Header
```
+---------------+---------------+------------------+-----------------+------------------+--------------------+
| Byte 0        | Byte 1        | Byte 2           | Byte 3          | Byte 4           | Bytes 5..5+N-1     |
+---------------+---------------+------------------+-----------------+------------------+--------------------+
| Seq (4 bits)  | Command ID    | Command Type     | Frag Info       | Payload Len (N)  | Payload Bytes      |
+---------------+---------------+------------------+-----------------+------------------+--------------------+
```

Detailed Breakdown:
1. **Byte 0 (`Seq`)**:
   - Encoded as `seq & 0x0F` (increments from 0 to 15, wrapping modulo 16).
2. **Byte 1 (`Command ID`)**:
   - The operation byte (e.g., `0x2C` for ANC, `0x20` for EQ).
3. **Byte 2 (`Command Type`)**:
   - `1`: `COMMAND_TYPE_REQUEST` (Client $\rightarrow$ Headphone)
   - `2`: `COMMAND_TYPE_RESPONSE` (Headphone $\rightarrow$ Client)
   - `3`: `COMMAND_TYPE_NOTIFY` (Headphone push event $\rightarrow$ Client)
4. **Byte 3 (`Fragment Info`)**:
   - High 4 bits: `((total_fragments - 1) << 4) & 0xF0`
   - Low 4 bits: `fragment_index & 0x0F`
   - For standard unfragmented control commands, this is always `0x00`.
5. **Byte 4 (`Payload Length`)**:
   - Length of the trailing payload bytes (0 to 250).
6. **Bytes 5.. (`Payload`)**:
   - Command parameters or TLV data.

---

## 6. Decoding Commands, Requests, & Telemetry (TLV)

In `apk_code/sources/com/bluetrum/devicemanager/cmd/Command.java`, every command and telemetry tag is declared as static constants:

### 6.1 Command IDs (`Command.java`)
| Constant | Value (Dec) | Value (Hex) | Purpose |
|---|---|---|---|
| `COMMAND_EQ` | 32 | `0x20` | Set / Query Equalizer |
| `COMMAND_MUSIC_CONTROL` | 33 | `0x21` | Play, pause, volume |
| `COMMAND_KEY` | 34 | `0x22` | Button remap |
| `COMMAND_AUTO_SHUTDOWN` | 35 | `0x23` | Sleep timer |
| `COMMAND_FACTORY_RESET` | 36 | `0x24` | Factory reset |
| `COMMAND_WORK_MODE` | 37 | `0x25` | Normal vs Gaming mode |
| `COMMAND_DEVICE_INFO` | 39 | `0x27` | Query device state |
| `COMMAND_NOTIFY` | 40 | `0x28` | State change notifications |
| `COMMAND_FIND_DEVICE` | 42 | `0x2A` | Locate headphones / beep |
| `COMMAND_ANC_MODE` | 44 | `0x2C` | Active Noise Cancellation |
| `COMMAND_BLUETOOTH_NAME` | 45 | `0x2D` | Read/write Bluetooth name |
| `COMMAND_ANC_GAIN` | 48 | `0x30` | ANC intensity level |
| `COMMAND_TRANSPARENCY_GAIN` | 49 | `0x31` | Transparency passthrough level |
| `COMMAND_ONE_DRAG_TWO` | 51 | `0x33` | Multipoint / Dual pairing |
| `COMMAND_WARNING_TONE` | 52 | `0x34` | Voice prompt tones |

### 6.2 Specific Payload Implementations

#### Active Noise Cancellation (`AncModeRequest.java`)
```java
// Command: 44 (0x2C)
Payload: [mode]
  0 = ANC_MODE_OFF
  1 = ANC_MODE_ON (Noise Cancellation)
  2 = ANC_MODE_TRANSPARENCY (Ambient sound)
```

#### Low Latency Gaming Mode (`WorkModeRequest.java`)
```java
// Command: 37 (0x25)
Payload: [mode]
  0 = WORK_MODE_NORMAL (Music mode)
  1 = WORK_MODE_GAMING (Low latency mode)
```

#### Voice Prompts (`WarningToneRequest.java`)
```java
// Command: 52 (0x34)
Payload: [mode]
  0 = WARNING_TONE_OFF
  1 = WARNING_TONE_ON
```

#### Dual Device Multipoint (`OneDragTwoRequest.java`)
```java
// Command: 51 (0x33)
Payload: [0x01, 0x01, mode]
  0 = OFF
  1 = ON
```

### 6.3 Telemetry TLV Records (`DeviceCommManager.java`)
When the headphone sends telemetry in response to `COMMAND_DEVICE_INFO` (`39`) or `COMMAND_NOTIFY` (`40`), it formats the payload in TLVs:
```
[Tag (1 byte)] [Length (1 byte)] [Value (N bytes)]
```

#### Battery Level (`PowerPayloadHandler.java` & `DeviceComponentPower.java`)
- **Tag**: `1` (`INFO_DEVICE_POWER`)
- **Byte 0**: Left earbud / Headphone battery:
  - `byte & 0x7F` = Battery percentage ($0 \dots 100\%$)
  - `(byte & 0x80) != 0` = Charging status (1 = charging, 0 = discharging)
- **Byte 1** (optional): Right earbud (for TWS models)
- **Byte 2** (optional): Charging case battery

---

## 7. Extracting the 10-Band Equalizer Specifications

Tracing the EQ logic in the Android app:
1. `EqSettingActivity.java` calls `cb/l.java`.
2. `cb/l.java` instantiates `wa/x.java` (`EqModelImpl`).
3. `wa/x.java` formats the request using `com.bluetrum.devicemanager.cmd.request.EqRequest`.

### Step 7.1: The Frequency Bands
In `sa/c.java`:
```java
public static final int[] f11274c = {31, 62, 125, 250, 500, LicenseUtil.VALIDATE_LINE, 2000, 4000, 8000, 16000};
```
Where `LicenseUtil.VALIDATE_LINE` is `1000`.
The hardware equalizer features **10 bands**:
$$32\text{ Hz},\; 62\text{ Hz},\; 125\text{ Hz},\; 250\text{ Hz},\; 500\text{ Hz},\; 1\text{ kHz},\; 2\text{ kHz},\; 4\text{ kHz},\; 8\text{ kHz},\; 16\text{ kHz}$$

### Step 7.2: Official Preset Gain Curves
In `sa/c.java`, the exact gain curves programmed into the app were extracted:
```java
// Flat / Original (Mode 0)
{0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f}

// Rock (Mode 2)
{3.0f, 1.0f, 0.0f, -2.0f, -4.0f, -4.0f, -2.0f, 0.0f, 1.0f, 2.0f}

// Pop (Mode 1)
{-2.0f, 0.0f, 2.0f, 4.0f, -2.0f, -2.0f, 0.0f, 0.0f, 4.0f, 4.0f}

// Jazz (Mode 4)
{0.0f, 0.0f, 0.0f, 4.0f, 4.0f, 4.0f, 0.0f, 2.0f, 3.0f, 4.0f}

// Country (Mode 5)
{0.0f, 5.0f, 5.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 2.0f, 2.0f}

// Hip Hop (Mode 6)
{-2.0f, 0.0f, 0.0f, 2.0f, 2.0f, 0.0f, 0.0f, 0.0f, 4.0f, 4.0f}

// Classical (Mode 3)
{4.0f, 3.0f, 2.0f, -1.0f, 0.0f, 1.0f, 2.0f, 1.0f, 0.0f, -2.0f}
```

### Step 7.3: The `COMMAND_EQ` (`32`) Payload Structure
In `EqRequest.java`:
```java
ByteBuffer buf = ByteBuffer.allocate(count + 2);
buf.put(count);   // Byte 0: Number of bands = 10 (0x0A)
buf.put(mode_id); // Byte 1: Preset ID (0..6) or Custom ID (32 / 0x20)
for (int i = 0; i < count; i++) {
    buf.put((byte) gain[i]); // Bytes 2..11: Signed byte gains (-12 to +12 dB)
}
```
When transmitted over Bluetooth SPP, the complete packet is:
```
[seq, 0x20, 0x01, 0x00, 0x0C, 0x0A, mode_id, g0, g1, g2, g3, g4, g5, g6, g7, g8, g9]
```

---

## 8. Connecting on Windows: The COM Port Discovery

On Windows, paired Bluetooth Classic devices implementing SPP are handled by the `BTHENUM` driver, which automatically attaches a virtual COM port.

By querying the system's serial ports:
```powershell
Get-PnpDevice -Class Ports | Select-Object FriendlyName, InstanceId
```
We found:
```
FriendlyName : Standard Serial over Bluetooth link (COM5)
InstanceId   : BTHENUM\{00001101-0000-1000-8000-00805F9B34FB}_LOCALMFG&0002\7&2A948D35&0&4142F38D5452_C00000000
```
Key elements in the Windows `InstanceId`:
1. `{00001101-0000-1000-8000-00805F9B34FB}`: The exact Bluetooth SPP UUID.
2. `4142F38D5452`: The exact MAC address of your ZEB-Silencio 200T.
3. `COM5`: The active communication port assigned to your headphone.

Opening `COM5` with standard baud rate (`115200`, 8N1) connects directly to the headphone's RFCOMM stream without requiring any custom kernel drivers.

---

## 9. Architecture of the Windows Port

The complete solution was structured into modular components:

```
d:\College\Headphone\
├── app\
│   ├── protocol.py       # Bluetrum binary encoder, decoder, and TLV parser
│   ├── connection.py     # COM port auto-discovery and thread-safe serial I/O
│   ├── controller.py     # High-level state machine (ANC, EQ, Battery, WorkMode)
│   ├── gui.py            # CustomTkinter Dark Mode GUI application
│   └── assets/           # Extracted visual assets from APK (headphone image, logo)
├── run_app.py            # Main application launcher
├── run_app.bat           # 1-click Windows batch file
├── cli.py                # Command-line control tool for scripting and hotkeys
├── steps.md              # This technical reverse-engineering document
└── README.md             # Project overview and quick start guide
```

### Highlights of the Implementation:
1. **Auto-Discovery**: `find_silencio_com_port()` inspects Windows PnP devices dynamically, so even if the COM port changes, it re-binds automatically.
2. **Asynchronous Receiver**: A background thread continuously streams serial bytes into a circular buffer and extracts complete frames, notifying the UI without blocking.
3. **Live EQ Tuning**: Changing sliders in the GUI dynamically calculates the 10-band payload and transmits it with a debounce so you can hear sound adjustments in real-time while music is playing.

---

## 10. Dual-Device Real-Time Synchronization (Phone & Laptop Co-existence)

When the headphones are connected to both a phone (running the ZEB-Aural IQ Android app) and a Windows laptop via Bluetooth multipoint (`one_drag_two`), actions performed on one device must automatically reflect on the other.

### The Problem
Setting an EQ preset from the laptop updated the headphone DSP and was visible on the phone because the phone app actively synchronizes state. However, setting a preset on the phone did **not** update the laptop app because:
1. **No Cross-Link Broadcast**: Bluetrum Bluetooth firmware executes commands locally from the phone's RFCOMM channel, but does not emit unsolicited broadcast notifications across the secondary Windows RFCOMM connection.
2. **Preset Identification**: The Bluetrum protocol returns `mode` (0–6 for presets, 32+ for custom) inside `INFO_EQ_SETTING` (tag 4). The original desktop app code only checked `is_custom` and did not map modes 0–6 back to their preset names (Rock, Pop, Classical, etc.).

### The Solution
1. **Exact Preset & Gain Recognition**:
   Using the decompiled curves from `sa.c` and mode translation table from `p.c.a`, `protocol.identify_preset_name(mode, gains)` checks:
   - Mode 0: `Default / Flat`
   - Mode 1: `Pop`
   - Mode 2: `Rock`
   - Mode 3: `Classical`
   - Mode 4: `Jazz`
   - Mode 5: `Country`
   - Mode 6: `Hip Hop`
   - Mode 32+: `Bass Boost`, `Vocal`, `AirPods`, `OnePlus Buds 3`, or `Custom`
2. **Continuous Background Polling Loop**:
   A dedicated background thread in `controller.py` sends `COMMAND_DEVICE_INFO` while connected. When the headphone replies with `INFO_EQ_SETTING` (tag 4), any changes made on the phone are detected.
3. **User Action Debouncing**:
   When the user moves sliders or clicks a preset on the laptop, `mark_user_action()` records the timestamp and pauses polling queries for 2.0 seconds to prevent query responses from interrupting active slider adjustments.
4. **Thread-Safe Reactive UI**:
   When new EQ data arrives from the background thread, the GUI updates both the preset dropdown (`cbox_presets`) and moves all 10 sliders to match the phone's curve in real time.

---

## 11. Hardware Protocol Findings & Windows Driver Constraints

During live hardware debugging with physical ZEB-Silencio 200T units over Windows virtual serial (`COM5`), several critical lower-level quirks and protocol edge cases were discovered:

### 11.1 Windows Virtual Bluetooth Serial Driver (`bthenum.sys`) Drops RX Without DTR/RTS
- **Discovery**: In Python (`pyserial`), opening `serial.Serial(port, 115200)` defaults to `dtr=False, rts=False`. On Windows 10/11, the Bluetooth virtual serial driver (`bthenum.sys`) silently discards inbound Bluetooth SPP packets if DTR (Data Terminal Ready) and RTS (Request To Send) control signals are not asserted. Outbound transmission (`TX`) succeeds, giving the illusion that the connection is working, but the application receives zero incoming bytes.
- **Fix**: Explicitly asserting `self.serial.dtr = True` and `self.serial.rts = True` immediately upon opening the port unblocks the kernel driver and delivers incoming Bluetooth packets.

### 11.2 Bluetrum MTU Handshake (`0xFF, 0x00`)
- **Discovery**: In `va/i.java:39`, immediately after RFCOMM connection establishment, the Bluetrum Android SDK issues:
  ```java
  defaultDeviceCommManager.registerDeviceInfoCallback((byte) -1, MtuPayloadHandler.class, new g(0, defaultDeviceCommManager));
  defaultDeviceCommManager.sendRequest(new DeviceInfoRequest((byte) -1));
  ```
  `(byte) -1` maps to unsigned `0xFF` (`requireMaxPacketSize()`). Sending `[seq, 0x27, 0x01, 0x00, 0x02, 0xFF, 0x00]` acts as the required session initialization handshake. The headphone responds with `CMD=40 TYPE=3 PAYLOAD=23 02 07 00` (auto-shutdown timeout tag 35 set to 7 minutes), confirming the communication session is active.

### 11.3 Over-Ear Headband Battery Telemetry vs TWS Earbuds
- **Discovery**: In `com/bluetrum/devicemanager/models/DevicePower.java`, byte 0 is mapped to `leftSidePower`, byte 1 to `rightSidePower`, and byte 2 to `casePower`. For true wireless earbuds (TWS), both left and right batteries are reported. For headband/over-ear models like the ZEB-Silencio 200T (verified in `DeviceActivity.java:245-255`), byte 0 is `0` and byte 1 contains the primary headband battery percentage (`right_battery = byte1 & 0x7F`) and charging state (`charging = (byte1 & 0x80) != 0`).
- **Fix**: `protocol.parse_battery_info()` assigns `battery = right_battery` whenever `right_battery > 0` or `left_battery == 0`, correctly displaying the headphone's actual battery level and charging indicator.

### 11.4 Bluetrum Firmware Rejects Bundled Multi-Tag Queries (Single-Tag TLV Requirement)
- **Discovery**: In `build_device_info_query()`, attempting to query multiple TLV tags simultaneously (e.g. `[1, 0, 12, 0, 8, 0, 4, 0, ...]`) inside a single packet causes the Bluetrum firmware on the ZEB-Silencio 200T to silently discard the packet and return 0 bytes. The firmware parser strictly requires **one tag per query packet** with a 2-byte payload format `[tag, 0x00]`.
- **Fix**: Replaced the bundled query with sequential individual tag requests for `INFO_DEVICE_POWER` (Tag 1), `INFO_EQ_SETTING` (Tag 4), `INFO_ANC_MODE` (Tag 12), and `INFO_WORK_MODE` (Tag 8), with 50ms inter-packet spacing. The headphone reliably answers every query with its corresponding TLV response.

### 11.5 Distinguishing Command ACKs from State Updates
- **Discovery**: In Bluetrum protocol, command responses (`cmd_type = 2`) for commands like `COMMAND_EQ` (32) or `COMMAND_ANC_MODE` (44) return a 1-byte status ACK (`0x00` for success). If the response handler treats `[0x00]` as new state data (e.g. passing `b"\x00"` to `parse_eq_info()`), the EQ is mistakenly overwritten with `Default / Flat` [0]*10. The controller guards `_handle_packet` by requiring `len(payload) >= 2` for EQ updates and checking for notification type packets (`cmd_type = 3`).

### 11.6 Live Multipoint Phone-to-Laptop Synchronization
- **Discovery**: Multipoint dual-connection Bluetooth headphones process DSP changes made on one channel (the Android phone) internally, but do not automatically broadcast unsolicited notifications across the second channel (the Windows RFCOMM serial port).
- **Fix**: The laptop controller runs a lightweight background polling thread every 1.5 seconds that queries the single-tag TLVs. When the user selects a preset (Pop, Rock, Classical, etc.) or moves EQ sliders on the Android app, the next polling query fetches Tag 4, extracts the preset ID and 10 gain values, and immediately updates the Windows GUI dropdown and slider positions in real time.

### 11.7 Synchronous Request-Response Queue & UART Collision Elimination
- **Discovery**: In `com/bluetrum/devicemanager/DeviceCommManager.java:282-345`, the Bluetrum SDK strictly enforces a single in-flight request queue (`if (this.f != null) return;`). The headphone's embedded microcontroller uses a small hardware UART buffer. When queries (e.g. Battery Tag 1, EQ Tag 4, ANC Tag 12) are transmitted in an asynchronous rapid burst (<100ms), the headphone's receiver overruns while simultaneously transmitting outgoing response packets and auto-shutdown notifications, silently dropping subsequent queries.
- **Fix**: Implemented `query_tag_sync()` using a `threading.Lock` and `threading.Event`. Each tag query packet is transmitted and waits on the reader thread to signal that the specific tag's response has arrived (typically 30–50ms) before the next query is dispatched. This guarantees zero packet collisions across serial I/O, allowing `cli.py status`, GUI startup, manual refresh, and background synchronization to reliably populate the 74% battery level, active EQ preset curve, and noise cancellation status.



