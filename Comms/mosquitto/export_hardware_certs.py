#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def read_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return path.read_text().strip() + "\n"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    cert_dir = repo_root / "Comms" / "mosquitto" / "certs"
    hardware_header = repo_root / "Hardware" / "certs.h"
    per_device_headers = {
        "left_glove": repo_root / "Hardware" / "Left_Glove" / "certs.h",
        "right_glove": repo_root / "Hardware" / "Right_Glove" / "certs.h",
        "headset": repo_root / "Hardware" / "Headset" / "certs.h",
    }

    ca = read_file(cert_dir / "ca.crt")

    clients = {
        "DEVICE_LEFT_GLOVE": (
            read_file(cert_dir / "clients" / "left_glove.crt"),
            read_file(cert_dir / "clients" / "left_glove.key"),
        ),
        "DEVICE_RIGHT_GLOVE": (
            read_file(cert_dir / "clients" / "right_glove.crt"),
            read_file(cert_dir / "clients" / "right_glove.key"),
        ),
        "DEVICE_HEADSET": (
            read_file(cert_dir / "clients" / "headset.crt"),
            read_file(cert_dir / "clients" / "headset.key"),
        ),
    }

    lines = []
    lines.append("#pragma once")
    lines.append("")
    lines.append("// Auto-generated from Comms/mosquitto/certs. Do not edit by hand.")
    lines.append("static const char CA_CERT[] = R\"EOF(")
    lines.append(ca.rstrip("\n"))
    lines.append(")EOF\";")
    lines.append("")

    for i, (macro, (cert, key)) in enumerate(clients.items()):
        if i == 0:
            lines.append(f"#if defined({macro})")
        else:
            lines.append(f"#elif defined({macro})")
        lines.append("static const char CLIENT_CERT[] = R\"EOF(")
        lines.append(cert.rstrip("\n"))
        lines.append(")EOF\";")
        lines.append("static const char CLIENT_KEY[] = R\"EOF(")
        lines.append(key.rstrip("\n"))
        lines.append(")EOF\";")

    lines.append("#else")
    lines.append(
        "#error \"Define one of DEVICE_LEFT_GLOVE, DEVICE_RIGHT_GLOVE, DEVICE_HEADSET before including certs.h\""
    )
    lines.append("#endif")
    lines.append("")

    hardware_header.write_text("\n".join(lines))
    print(f"Wrote {hardware_header}")

    # Also write per-device headers for Arduino's local include behavior.
    for device, header_path in per_device_headers.items():
        cert = read_file(cert_dir / "clients" / f"{device}.crt")
        key = read_file(cert_dir / "clients" / f"{device}.key")
        per_lines = [
            "#pragma once",
            "",
            "// Auto-generated from Comms/mosquitto/certs. Do not edit by hand.",
            "static const char CA_CERT[] = R\"EOF(",
            ca.rstrip("\n"),
            ")EOF\";",
            "",
            "static const char CLIENT_CERT[] = R\"EOF(",
            cert.rstrip("\n"),
            ")EOF\";",
            "static const char CLIENT_KEY[] = R\"EOF(",
            key.rstrip("\n"),
            ")EOF\";",
            "",
        ]
        header_path.write_text("\n".join(per_lines))
        print(f"Wrote {header_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
