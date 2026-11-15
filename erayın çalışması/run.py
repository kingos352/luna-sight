#!/usr/bin/env python3
"""
run.py
======
Yerel Ay İniş Sahası Navigasyon ve Yörünge Simülasyon Sistemi Başlatıcı.

Kullanım:
    python run.py
    veya
    python run.py --port 8000 --host 127.0.0.1
"""

import argparse
import sys
from pathlib import Path

# Proje dizinini Python arama yoluna ekle
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Lunar Landing Site Navigator Sunucusu")
    parser.add_argument("--host", default="127.0.0.1", help="Bağlanılacak host (Varsayılan: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bağlanılacak port (Varsayılan: 8000)")
    parser.add_argument("--reload", action="store_true", help="Geliştirici otomatik yeniden yükleme")
    args = parser.parse_args()

    print("=" * 75)
    print("   LUNAR LANDING SITE NAVIGATOR & ORBIT SIMULATION SYSTEM")
    print("   Yerel Ay İniş Sahası Navigasyon ve Yörünge Simülasyon Sistemi")
    print("=" * 75)
    print(f"[*] Durum: %100 Yerel / Çevrimdışı (Offline) Mod")
    print(f"[*] Referans Çerçevesi: MOON_ME (Mean Earth / Polar Axis)")
    print(f"[*] Web Arayüzü: http://{args.host}:{args.port}")
    print(f"[*] API Belgeleri: http://{args.host}:{args.port}/docs")
    print("=" * 75)

    uvicorn.run("backend.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
