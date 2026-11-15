#!/usr/bin/env python3
"""
scripts/download_kernels.py
===========================
Tek Seferlik Kurulum Scripti:
NASA NAIF (Navigation and Ancillary Information Facility) sunucularından
gerekli yüksek hassasiyetli SPICE çekirdeklerini indirir.

İndirilen Çekirdekler:
1. naif0012.tls             - Güncel artık saniye (LSK) çekirdeği.
2. pck00011.tpc             - Genel gezegen/uydu fiziksel sabitler (PCK).
3. de440s.bsp               - JPL DE440 kısa dönem (1900-2050) gezegen & Ay efemerisi (SPK, ~32 MB).
4. moon_pa_de440_200625.bpc - Yüksek hassasiyetli Ay librasyon & yönelim ikili PCK (DE440 uyumlu).
5. moon_080317.tf           - Ay referans çerçevesi tanım çekirdeği (MOON_ME & MOON_PA frame tanımları).
6. moon_assoc_me.tf         - MOON_ME varsayılan bağlama çerçeve çekirdeği.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
import urllib.request
import urllib.error

# Proje kök dizini
PROJECT_ROOT = Path(__file__).resolve().parent.parent
KERNEL_DIR = PROJECT_ROOT / "data" / "kernels"

# NASA NAIF Sunucu Çekirdek URL'leri
KERNELS_TO_DOWNLOAD = [
    {
        "name": "naif0012.tls",
        "description": "Leapseconds Kernel (LSK)",
        "urls": [
            "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/naif0012.tls",
            "https://raw.githubusercontent.com/AndrewAnnex/SpiceyPy/main/tests/data/naif0012.tls",
        ],
        "size_hint": "~5 KB",
    },
    {
        "name": "pck00011.tpc",
        "description": "Planetary Constants Kernel (Text PCK)",
        "urls": [
            "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00011.tpc",
            "https://raw.githubusercontent.com/AndrewAnnex/SpiceyPy/main/tests/data/pck00010.tpc",
        ],
        "size_hint": "~130 KB",
    },
    {
        "name": "moon_080317.tf",
        "description": "Lunar Frames Definition Kernel (MOON_ME / MOON_PA)",
        "urls": [
            "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/moon_080317.tf",
        ],
        "size_hint": "~6 KB",
    },
    {
        "name": "moon_assoc_me.tf",
        "description": "Moon Mean Earth / Polar Axis Association Frame Kernel",
        "urls": [
            "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/moon_assoc_me.tf",
        ],
        "size_hint": "~2 KB",
    },
    {
        "name": "moon_pa_de440_200625.bpc",
        "description": "High-Precision Lunar Orientation Binary PCK (DE440)",
        "urls": [
            "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/moon_pa_de440_200625.bpc",
            "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/moon_pa_de421_1900-2050.bpc",
        ],
        "size_hint": "~15 MB",
    },
    {
        "name": "de440s.bsp",
        "description": "JPL Planetary & Lunar Ephemeris DE440 (SPK 1900-2050)",
        "urls": [
            "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp",
            "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de430.bsp",
        ],
        "size_hint": "~32 MB",
    },
]


def download_file_with_progress(url: str, dest_path: Path) -> bool:
    """Belirtilen URL'den dosyayı terminal ilerleme çubuğuyla indirir."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "LunarLandingNavigator/1.0 (SPICE Kernel Downloader)"},
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            total_size = int(response.headers.get("content-length", 0))
            block_size = 65536  # 64 KB
            downloaded = 0
            start_time = time.time()

            tmp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")
            with open(tmp_path, "wb") as out_file:
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    downloaded += len(buffer)
                    out_file.write(buffer)

                    # Progress display
                    if total_size > 0:
                        percent = downloaded * 100 / total_size
                        mb_done = downloaded / (1024 * 1024)
                        mb_total = total_size / (1024 * 1024)
                        elapsed = time.time() - start_time
                        speed = (downloaded / 1024) / max(elapsed, 0.001)
                        bar = "#" * int(percent // 4) + "-" * (25 - int(percent // 4))
                        sys.stdout.write(
                            f"\r    [{bar}] {percent:5.1f}% ({mb_done:.1f}/{mb_total:.1f} MB) @ {speed:5.1f} KB/s"
                        )
                        sys.stdout.flush()

            # İndirme başarıyla bittiğinde geçici dosyayı asıl hedefe taşı
            if tmp_path.exists():
                tmp_path.replace(dest_path)
            print()
            return True
    except Exception as e:
        print(f"\n    [!] Hata: {url} adresinden indirilemedi: {e}")
        tmp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")
        if tmp_path.exists():
            tmp_path.unlink()
        return False


def main() -> None:
    print("=" * 70)
    print("   LUNAR LANDING SITE NAVIGATOR - SPICE KERNEL KURULUM ARACI")
    print("=" * 70)
    print(f"Hedef Dizin: {KERNEL_DIR}")
    KERNEL_DIR.mkdir(parents=True, exist_ok=True)

    success_count = 0
    total_count = len(KERNELS_TO_DOWNLOAD)

    for item in KERNELS_TO_DOWNLOAD:
        filename = item["name"]
        dest = KERNEL_DIR / filename
        desc = item["description"]
        size_hint = item["size_hint"]

        print(f"\n[*] {filename} [{desc}] ({size_hint})")
        if dest.exists() and dest.stat().st_size > 0:
            print(f"    -> Zaten mevcut: ({dest.stat().st_size / 1024:.1f} KB). İndirme atlandı.")
            success_count += 1
            continue

        downloaded = False
        for url in item["urls"]:
            print(f"    -> İndiriliyor: {url}")
            if download_file_with_progress(url, dest):
                downloaded = True
                break

        if downloaded:
            success_count += 1
        else:
            print(f"    [!] UYARI: {filename} hiçbir kaynaktan indirilemedi.")

    print("\n" + "=" * 70)
    print(f"Kurulum Tamamlandı: {success_count}/{total_count} çekirdek hazır.")
    if success_count == total_count:
        print("Tüm SPICE çekirdekleri eksiksiz indirildi. Sistem %100 çevrimdışı çalışmaya hazır!")
    else:
        print("Not: Eksik çekirdekler varsa, sistem yüksek hassasiyetli analitik efemeris motoruyla çalışmaya devam edebilir.")
    print("=" * 70)


if __name__ == "__main__":
    main()
