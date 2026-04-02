#!/usr/bin/env python3
"""
LoRa Bridge — Whim Terminal GeoF Service
Listens on a serial LoRa gateway (or TCP socket) for collar packets,
performs point-in-polygon geofence checks, and emits JSON lines to stdout
for the GeoF tab to consume.

Usage:
    python lora_bridge.py --fence ~/.openclaw/fence_config.json [--port /dev/ttyUSB0] [--baud 115200]
    python lora_bridge.py --fence ~/.openclaw/fence_config.json --tcp 0.0.0.0:9600
"""

import argparse
import json
import os
import sys
import time
import threading
import socket
from datetime import datetime

try:
    import serial
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False


def load_fence(path):
    if not os.path.isfile(path):
        return []
    with open(path, "r") as f:
        data = json.load(f)
    return [(v[0], v[1]) for v in data.get("vertices", [])]


def point_in_polygon(lat, lon, polygon):
    """Ray-casting algorithm for point-in-polygon."""
    n = len(polygon)
    if n < 3:
        return True  # no fence defined = inside
    inside = False
    j = n - 1
    for i in range(n):
        yi, xi = polygon[i]
        yj, xj = polygon[j]
        if ((yi > lon) != (yj > lon)) and \
                (lat < (xj - xi) * (lon - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def emit(packet):
    line = json.dumps(packet, separators=(",", ":"))
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def parse_lora_payload(raw):
    """Parse a raw LoRa payload string into a collar packet dict.
    Expected CSV format: COLLAR_ID,LAT,LON,BATTERY,STATUS
    Also accepts JSON payloads.
    """
    raw = raw.strip()
    if raw.startswith("{"):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            pass
    parts = raw.split(",")
    if len(parts) >= 4:
        try:
            return {
                "collar_id": parts[0].strip(),
                "lat": float(parts[1]),
                "lon": float(parts[2]),
                "battery": int(parts[3]),
                "name": parts[4].strip() if len(parts) > 4 else parts[0].strip(),
            }
        except (ValueError, IndexError):
            pass
    return None


class SerialListener:
    def __init__(self, port, baud, fence_path):
        self.port = port
        self.baud = baud
        self.fence_path = fence_path
        self.fence = load_fence(fence_path)

    def run(self):
        if not HAS_SERIAL:
            emit({"error": "pyserial not installed"})
            return
        try:
            ser = serial.Serial(self.port, self.baud, timeout=2)
        except Exception as ex:
            emit({"error": f"Serial open failed: {ex}"})
            return
        emit({"info": f"Listening on {self.port} @ {self.baud} baud"})
        while True:
            try:
                line = ser.readline().decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                pkt = parse_lora_payload(line)
                if pkt is None:
                    continue
                self._check_fence(pkt)
                emit(pkt)
            except Exception as ex:
                emit({"error": str(ex)})
                time.sleep(1)

    def _check_fence(self, pkt):
        self.fence = load_fence(self.fence_path)
        lat = pkt.get("lat", 0)
        lon = pkt.get("lon", 0)
        if not point_in_polygon(lat, lon, self.fence):
            pkt["alert"] = "OUTSIDE_FENCE"


class TCPListener:
    def __init__(self, host, port, fence_path):
        self.host = host
        self.port = port
        self.fence_path = fence_path
        self.fence = load_fence(fence_path)

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(5)
        emit({"info": f"TCP listening on {self.host}:{self.port}"})
        while True:
            conn, addr = sock.accept()
            threading.Thread(target=self._handle_client,
                             args=(conn, addr), daemon=True).start()

    def _handle_client(self, conn, addr):
        buf = b""
        try:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    text = line.decode("utf-8", errors="replace").strip()
                    if not text:
                        continue
                    pkt = parse_lora_payload(text)
                    if pkt is None:
                        continue
                    self._check_fence(pkt)
                    emit(pkt)
        except Exception as ex:
            emit({"error": f"Client {addr}: {ex}"})
        finally:
            conn.close()

    def _check_fence(self, pkt):
        self.fence = load_fence(self.fence_path)
        lat = pkt.get("lat", 0)
        lon = pkt.get("lon", 0)
        if not point_in_polygon(lat, lon, self.fence):
            pkt["alert"] = "OUTSIDE_FENCE"


class SimulatedListener:
    """Generates synthetic collar data for testing without hardware."""
    def __init__(self, fence_path, count=3):
        self.fence_path = fence_path
        self.count = count
        self.fence = load_fence(fence_path)

    def run(self):
        import random
        emit({"info": "Simulated LoRa bridge active"})
        collars = []
        for i in range(self.count):
            collars.append({
                "collar_id": f"C{i+1:03d}",
                "name": f"Cow-{i+1}",
                "lat": 36.35 + random.uniform(-0.01, 0.01),
                "lon": -93.20 + random.uniform(-0.01, 0.01),
                "battery": random.randint(60, 100),
            })
        while True:
            for c in collars:
                c["lat"] += random.uniform(-0.001, 0.001)
                c["lon"] += random.uniform(-0.001, 0.001)
                c["battery"] = max(0, c["battery"] - random.randint(0, 1))
                pkt = dict(c)
                self.fence = load_fence(self.fence_path)
                if not point_in_polygon(pkt["lat"], pkt["lon"], self.fence):
                    pkt["alert"] = "OUTSIDE_FENCE"
                emit(pkt)
            time.sleep(20 * 60)  # 20-minute heartbeat


def main():
    parser = argparse.ArgumentParser(description="Whim GeoF LoRa Bridge")
    parser.add_argument("--fence", required=True, help="Path to fence_config.json")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate")
    parser.add_argument("--tcp", default="", help="TCP listen address host:port")
    parser.add_argument("--simulate", action="store_true",
                        help="Run with simulated collar data")
    parser.add_argument("--sf", type=int, default=12,
                        help="LoRa Spreading Factor (7-12, default 12 for hilly terrain)")
    args = parser.parse_args()

    emit({"info": f"LoRa SF={args.sf} (higher=better range over ridges)"})

    if args.simulate:
        SimulatedListener(args.fence).run()
    elif args.tcp:
        parts = args.tcp.split(":")
        host = parts[0] if parts[0] else "0.0.0.0"
        port = int(parts[1]) if len(parts) > 1 else 9600
        TCPListener(host, port, args.fence).run()
    else:
        SerialListener(args.port, args.baud, args.fence).run()


if __name__ == "__main__":
    main()
