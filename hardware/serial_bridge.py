"""Optional STM32 / Microcontroller Serial Bridge for Hardware-in-the-Loop Tasks."""

from __future__ import annotations

import argparse
import json


def send_serial_command(port: str, baudrate: int, payload: str, dry_run: bool = True) -> dict:
    if dry_run:
        return {"status": "dry_run", "port": port, "baudrate": baudrate, "payload": payload}
    import serial  # type: ignore

    with serial.Serial(port, baudrate=baudrate, timeout=2) as ser:
        ser.write((payload.strip() + "\n").encode("utf-8"))
        reply = ser.readline().decode("utf-8", errors="replace").strip()
    return {"status": "sent", "port": port, "reply": reply}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DesktopPilot Hardware Serial Bridge")
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--cmd", default="PING")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    print(json.dumps(send_serial_command(args.port, args.baud, args.cmd, dry_run=not args.live)))
