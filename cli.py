"""
ZEB-Silencio 200T Command Line Interface (CLI)
Quick control via terminal or keyboard shortcuts:
  python cli.py status
  python cli.py anc [on|off|trans]
  python cli.py game [on|off]
  python cli.py tone [on|off]
  python cli.py eq [preset_name]
"""

import sys
import time
import argparse
from app.controller import HeadphoneController
from app import protocol


def main():
    parser = argparse.ArgumentParser(description="Control ZEB-Silencio 200T from Windows CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Status
    subparsers.add_parser("status", help="Get battery, ANC, and headphone state")

    # ANC
    anc_p = subparsers.add_parser("anc", help="Set Active Noise Cancellation")
    anc_p.add_argument("mode", choices=["on", "off", "trans"], help="ANC mode (on, off, trans)")

    # Game Mode
    game_p = subparsers.add_parser("game", help="Set Gaming / Low Latency mode")
    game_p.add_argument("state", choices=["on", "off"], help="Gaming mode (on, off)")

    # Voice Prompts
    tone_p = subparsers.add_parser("tone", help="Enable or disable voice prompt tones")
    tone_p.add_argument("state", choices=["on", "off"], help="Voice prompt state (on, off)")

    # EQ
    eq_p = subparsers.add_parser("eq", help="Apply EQ preset")
    eq_p.add_argument("preset", choices=[k.lower().replace(" ", "").replace("/", "") for k in protocol.EQ_PRESETS.keys()], help="Preset name")

    # Port option
    parser.add_argument("--port", help="Specify serial port (default: auto-detected, e.g. COM5)", default=None)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    ctrl = HeadphoneController(args.port)
    print(f"Connecting to ZEB-Silencio 200T...")
    if not ctrl.connect(sync=True):
        print("Failed to connect. Ensure headphone is on and connected to Windows via Bluetooth.")
        sys.exit(1)

    if args.command == "status":
        print(f"Device: {ctrl.device_name}")
        print(f"Battery: {ctrl.battery}% {'(Charging)' if ctrl.is_charging else ''}")
        anc_names = {0: "OFF", 1: "ON (Cancelling)", 2: "Transparency / Ambient"}
        print(f"ANC Mode: {anc_names.get(ctrl.anc_mode, 'Unknown')}")
        print(f"Gaming Mode: {'ON' if ctrl.work_mode == 1 else 'OFF'}")
        print(f"Voice Prompts: {'ON' if ctrl.warning_tone == 1 else 'OFF'}")
        print(f"Dual Device (Multipoint): {'ON' if ctrl.one_drag_two == 1 else 'OFF'}")
        print(f"EQ Preset: {ctrl.current_eq_name} - Gains: {ctrl.eq_gains}")

    elif args.command == "anc":
        mode_map = {"off": 0, "on": 1, "trans": 2}
        ctrl.set_anc_mode(mode_map[args.mode])
        print(f"ANC set to: {args.mode.upper()}")
        time.sleep(0.3)

    elif args.command == "game":
        val = 1 if args.state == "on" else 0
        ctrl.set_work_mode(val)
        print(f"Gaming mode set to: {args.state.upper()}")
        time.sleep(0.3)

    elif args.command == "tone":
        val = (args.state == "on")
        ctrl.set_warning_tone(val)
        print(f"Voice prompts set to: {args.state.upper()}")
        time.sleep(0.3)

    elif args.command == "eq":
        # Match preset
        target_preset = None
        for k in protocol.EQ_PRESETS.keys():
            normalized = k.lower().replace(" ", "").replace("/", "")
            if normalized == args.preset:
                target_preset = k
                break
        if target_preset:
            ctrl.set_eq_preset(target_preset)
            print(f"Applied EQ preset: {target_preset}")
        time.sleep(0.3)

    ctrl.disconnect()
    print("Done.")


if __name__ == "__main__":
    main()
