#!/usr/bin/env python3
"""
Whim Security Monitor — scans for pending security updates, dangerous sudo
config, SSH exposure, and kernel CVE status.  Writes a JSON report to
~/.openclaw/security_status.json consumed by the Whim.m mobile server.

Usage:
    python3 whim_security_monitor.py            # run scan + write report
    python3 whim_security_monitor.py --signal    # also send critical alert via signal-cli
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

REPORT_PATH = os.path.expanduser("~/.openclaw/security_status.json")
OPENCLAW_CFG = os.path.expanduser("~/.openclaw/openclaw.json")

CRITICAL_PACKAGES = {
    "linux-image", "linux-generic", "linux-headers",
    "openssl", "libssl", "apparmor", "libapparmor",
    "systemd", "libnss", "runc", "containerd",
}


def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except Exception:
        return "", 1


def check_apt_updates():
    out, rc = run(["apt", "list", "--upgradable"])
    if rc != 0:
        return [], [], 0
    lines = [l for l in out.splitlines() if "/" in l and "upgradable" in l.lower()]
    critical = []
    non_critical = []
    for line in lines:
        pkg = line.split("/")[0]
        is_security = "security" in line.lower()
        is_critical_pkg = any(pkg.startswith(cp) for cp in CRITICAL_PACKAGES)
        entry = {"package": pkg, "line": line.strip(), "security_tagged": is_security}
        if is_security or is_critical_pkg:
            critical.append(entry)
        else:
            non_critical.append(entry)
    return critical, non_critical, len(lines)


def check_kernel():
    current, _ = run(["uname", "-r"])
    out, _ = run(["apt", "list", "--upgradable"])
    kernel_update = None
    for line in out.splitlines():
        if line.startswith("linux-image-generic") or line.startswith("linux-generic"):
            kernel_update = line.strip()
            break
    return {
        "current": current,
        "update_available": kernel_update,
        "needs_reboot": kernel_update is not None,
    }


def check_sudoers():
    findings = []
    sudoers_d = "/etc/sudoers.d"
    if os.path.isdir(sudoers_d):
        for fn in os.listdir(sudoers_d):
            if fn == "README":
                continue
            fp = os.path.join(sudoers_d, fn)
            try:
                out, rc = run(["sudo", "-n", "cat", fp], timeout=5)
                if rc != 0:
                    out, rc = run(["cat", fp], timeout=5)
                if "NOPASSWD" in out and "ALL" in out:
                    findings.append({
                        "file": fp,
                        "severity": "critical",
                        "detail": "NOPASSWD:ALL rule found",
                        "content": out.strip(),
                    })
                if "pwfeedback" in out.lower():
                    findings.append({
                        "file": fp,
                        "severity": "warning",
                        "detail": "pwfeedback enabled (CVE-2019-18634)",
                        "content": out.strip(),
                    })
            except Exception:
                pass
    return findings


def check_ssh():
    findings = []
    ssh_dir = os.path.expanduser("~/.ssh")
    if not os.path.isdir(ssh_dir):
        return findings

    out, rc = run(["ssh-add", "-l"])
    if rc == 0 and out and "no identities" not in out.lower():
        key_count = len([l for l in out.splitlines() if l.strip()])
        findings.append({
            "severity": "info",
            "detail": f"{key_count} SSH key(s) loaded in agent (harvestable by local attacker)",
        })

    auth_keys = os.path.join(ssh_dir, "authorized_keys")
    if os.path.isfile(auth_keys):
        with open(auth_keys) as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        if lines:
            findings.append({
                "severity": "warning",
                "detail": f"{len(lines)} authorized_keys entries (inbound SSH exposure)",
            })

    for fn in os.listdir(ssh_dir):
        fp = os.path.join(ssh_dir, fn)
        if os.path.isfile(fp) and not fn.endswith(".pub") and fn != "known_hosts" and fn != "known_hosts.old" and fn != "config":
            st = os.stat(fp)
            mode = oct(st.st_mode)[-3:]
            if mode != "600":
                findings.append({
                    "severity": "warning",
                    "detail": f"Insecure permissions ({mode}) on {fp}",
                })
    return findings


def compute_severity(critical_updates, sudoers_findings, kernel):
    if any(f["severity"] == "critical" for f in sudoers_findings):
        return "critical"
    if kernel["update_available"]:
        return "critical"
    if len(critical_updates) >= 3:
        return "critical"
    if len(critical_updates) >= 1:
        return "warning"
    if any(f["severity"] == "warning" for f in sudoers_findings):
        return "warning"
    return "ok"


def build_alert_message(report):
    sev = report["overall_severity"]
    if sev == "ok":
        return None
    lines = [f"[WHIM SEC {sev.upper()}] {report['timestamp']}"]
    if report["kernel"]["update_available"]:
        lines.append(f"  Kernel: {report['kernel']['current']} -> update available")
    if report["critical_updates"]:
        lines.append(f"  {len(report['critical_updates'])} critical package(s) need updating:")
        for u in report["critical_updates"][:5]:
            lines.append(f"    - {u['package']}")
    for f in report.get("sudoers_findings", []):
        if f["severity"] == "critical":
            lines.append(f"  SUDOERS: {f['detail']} in {f.get('file', '?')}")
    lines.append(f"  Total upgradable: {report['total_upgradable']}")
    lines.append("  Run: sudo apt update && sudo apt upgrade -y")
    return "\n".join(lines)


def send_signal_alert(message):
    if not os.path.isfile(OPENCLAW_CFG):
        return False
    try:
        with open(OPENCLAW_CFG) as f:
            cfg = json.load(f)
        signal_cfg = cfg.get("channels", {}).get("signal", {})
        if not signal_cfg.get("enabled"):
            return False
        account = signal_cfg.get("account", "")
        if not account:
            return False
        _, rc = run([
            "signal-cli", "-a", account,
            "send", "-m", message, account
        ], timeout=30)
        return rc == 0
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Whim Security Monitor")
    parser.add_argument("--signal", action="store_true", help="Send Signal alert for critical findings")
    args = parser.parse_args()

    critical_updates, non_critical_updates, total = check_apt_updates()
    kernel = check_kernel()
    sudoers_findings = check_sudoers()
    ssh_findings = check_ssh()
    severity = compute_severity(critical_updates, sudoers_findings, kernel)

    report = {
        "timestamp": datetime.now().isoformat(),
        "overall_severity": severity,
        "kernel": kernel,
        "critical_updates": critical_updates,
        "non_critical_updates": non_critical_updates,
        "total_upgradable": total,
        "sudoers_findings": sudoers_findings,
        "ssh_findings": ssh_findings,
    }

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)

    print(f"[{severity.upper()}] {total} upgradable ({len(critical_updates)} critical)")
    print(f"Report written to {REPORT_PATH}")

    if args.signal and severity in ("critical", "warning"):
        msg = build_alert_message(report)
        if msg:
            ok = send_signal_alert(msg)
            print(f"Signal alert: {'sent' if ok else 'failed'}")

    return 0 if severity == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
