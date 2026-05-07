#!/usr/bin/env python3
"""
APRS Bridge — Whim Terminal HAM Service
Connects to Direwolf (KISS TCP interface) and decodes APRS packets.
Emits JSON lines to stdout for the HAM tab to consume.

Usage:
    python aprs_bridge.py --simulate --callsign N0CALL
    python aprs_bridge.py --host 127.0.0.1 --port 8001 --mode kiss --callsign N0CALL
"""

import argparse
import json
import re
import socket
import sys
import time

KISS_FEND = 0xC0
KISS_FESC = 0xDB
KISS_TFEND = 0xDC
KISS_TFESC = 0xDD


def emit(packet):
    line = json.dumps(packet, separators=(",", ":"))
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def kiss_unescape(data):
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == KISS_FESC:
            i += 1
            if i < len(data):
                if data[i] == KISS_TFEND:
                    out.append(KISS_FEND)
                elif data[i] == KISS_TFESC:
                    out.append(KISS_FESC)
                else:
                    out.append(data[i])
        else:
            out.append(data[i])
        i += 1
    return bytes(out)


def decode_ax25_address(data):
    if len(data) < 7:
        return ""
    call = ""
    for i in range(6):
        ch = (data[i] >> 1) & 0x7F
        if ch > 32:
            call += chr(ch)
    call = call.strip()
    ssid = (data[6] >> 1) & 0x0F
    if ssid > 0:
        return f"{call}-{ssid}"
    return call


def decode_ax25_frame(raw):
    if len(raw) < 16:
        return None
    dest = decode_ax25_address(raw[0:7])
    src = decode_ax25_address(raw[7:14])

    path = []
    idx = 14
    while idx + 7 <= len(raw):
        if raw[idx - 1] & 0x01:
            break
        digi = decode_ax25_address(raw[idx:idx + 7])
        if digi:
            path.append(digi)
        idx += 7

    info_start = idx + 2
    if info_start >= len(raw):
        return None

    info = raw[info_start:]
    try:
        info_text = info.decode("ascii", errors="replace")
    except Exception:
        info_text = ""

    raw_text = (f"{src}>{dest},{','.join(path)}:{info_text}" if path
                else f"{src}>{dest}:{info_text}")
    return {"src": src, "dest": dest, "path": ",".join(path),
            "info": info_text, "raw": raw_text}


def parse_aprs_position(info_text):
    if not info_text:
        return None
    dt = info_text[0]
    if dt in ("!", "=", "/", "@"):
        text = info_text[1:]
        if dt in ("/", "@") and len(text) >= 7:
            text = text[7:]
        m = re.match(
            r"(\d{4}\.\d{2})([NS])(.)"
            r"(\d{5}\.\d{2})([EW])", text)
        if m:
            lat_s, lat_ns, _sym_tbl, lon_s, lon_ew = m.groups()
            lat = float(lat_s[:2]) + float(lat_s[2:]) / 60.0
            if lat_ns == "S":
                lat = -lat
            lon = float(lon_s[:3]) + float(lon_s[3:]) / 60.0
            if lon_ew == "W":
                lon = -lon
            rest = text[m.end():]
            symbol = rest[0] if rest else ""
            comment = rest[1:].strip() if len(rest) > 1 else ""
            return lat, lon, comment, symbol
    return None


class KISSListener:
    def __init__(self, host, port):
        self.host = host
        self.port = int(port)

    def run(self):
        emit({"info": f"Connecting to Direwolf KISS at {self.host}:{self.port}..."})
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.host, self.port))
            sock.settimeout(None)
        except Exception as ex:
            emit({"error": f"Connection failed: {ex}"})
            return

        emit({"info": f"Connected to Direwolf at {self.host}:{self.port}"})
        buf = bytearray()

        try:
            while True:
                data = sock.recv(1024)
                if not data:
                    emit({"error": "Connection closed by Direwolf"})
                    break
                buf.extend(data)

                while KISS_FEND in buf:
                    start = buf.index(KISS_FEND)
                    end = -1
                    for i in range(start + 1, len(buf)):
                        if buf[i] == KISS_FEND:
                            end = i
                            break
                    if end == -1:
                        break

                    frame = bytes(buf[start + 1:end])
                    buf = buf[end + 1:]
                    if not frame:
                        continue
                    if frame[0] != 0x00:
                        continue

                    ax25_data = kiss_unescape(frame[1:])
                    decoded = decode_ax25_frame(ax25_data)
                    if not decoded:
                        continue

                    pkt = {"callsign": decoded["src"], "raw": decoded["raw"],
                           "path": decoded["path"]}
                    pos = parse_aprs_position(decoded["info"])
                    if pos:
                        pkt["lat"] = pos[0]
                        pkt["lon"] = pos[1]
                        pkt["comment"] = pos[2]
                        pkt["symbol"] = pos[3]
                    emit(pkt)
        except Exception as ex:
            emit({"error": str(ex)})
        finally:
            sock.close()


class SimulatedListener:
    def __init__(self, callsign, count=8):
        self.callsign = callsign
        self.count = count

    def run(self):
        import random
        emit({"info": "Simulated APRS bridge active"})

        sample_cs = ["W0ABC-9", "KD0XYZ-7", "N0HAM-1", "K0MOZ-15",
                      "WB0TUA-9", "KC0SHR-7", "W0OZK-1", "N0SPR-9"]
        comments = ["En route", "Base station", "Mobile", "Weather station",
                     "Digipeater", "IGate", "Portable", "Emergency"]
        stations = []
        for i in range(min(self.count, len(sample_cs))):
            stations.append({
                "callsign": sample_cs[i],
                "lat": 36.35 + random.uniform(-0.05, 0.05),
                "lon": -93.20 + random.uniform(-0.05, 0.05),
                "comment": comments[i % len(comments)],
                "symbol": random.choice(["/", "\\", ">", "-"]),
            })

        # Initial burst
        for s in stations:
            path = random.choice(["WIDE1-1,WIDE2-1", "RELAY,WIDE", "WIDE1-1"])
            raw = (f"{s['callsign']}>{self.callsign},{path}:"
                   f"!{abs(s['lat']) * 100:.2f}{'N' if s['lat'] >= 0 else 'S'}"
                   f"{s['symbol']}"
                   f"{abs(s['lon']) * 100:.2f}{'E' if s['lon'] >= 0 else 'W'}"
                   f" {s['comment']}")
            emit({"callsign": s["callsign"], "lat": s["lat"], "lon": s["lon"],
                  "comment": s["comment"], "symbol": s["symbol"],
                  "path": path, "raw": raw})
            time.sleep(0.3)

        while True:
            time.sleep(30)
            for s in stations:
                s["lat"] += random.uniform(-0.002, 0.002)
                s["lon"] += random.uniform(-0.002, 0.002)
                path = random.choice(["WIDE1-1,WIDE2-1", "RELAY,WIDE", "WIDE1-1"])
                raw = (f"{s['callsign']}>{self.callsign},{path}:"
                       f"!{abs(s['lat']) * 100:.2f}{'N' if s['lat'] >= 0 else 'S'}"
                       f"{s['symbol']}"
                       f"{abs(s['lon']) * 100:.2f}{'E' if s['lon'] >= 0 else 'W'}"
                       f" {s['comment']}")
                emit({"callsign": s["callsign"], "lat": s["lat"], "lon": s["lon"],
                      "comment": s["comment"], "symbol": s["symbol"],
                      "path": path, "raw": raw})


def main():
    parser = argparse.ArgumentParser(description="Whim HAM APRS Bridge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default="8001")
    parser.add_argument("--mode", default="kiss", choices=["kiss", "agwpe"])
    parser.add_argument("--callsign", default="N0CALL")
    parser.add_argument("--simulate", action="store_true")
    args = parser.parse_args()

    if args.simulate:
        SimulatedListener(args.callsign).run()
    else:
        KISSListener(args.host, args.port).run()


if __name__ == "__main__":
    main()
