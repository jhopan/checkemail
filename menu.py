#!/usr/bin/env python3
"""
Menu utama Email Account Checker.
Atur semua pengaturan: password, server browser, mode (Gmail/UNUD), dll.

Jalankan: python menu.py
"""

import os
import sys
import json
import subprocess

from checker import (
    CamofoxClient,
    DEFAULT_PASSWORD,
    DEFAULT_SERVER_URL,
    DELAY_BETWEEN_ACCOUNTS,
    load_gmail_accounts,
    load_unud_accounts,
    load_accounts_auto,
    detect_mode,
)

CONFIG_FILE = "config.json"


def load_config():
    """Baca config tersimpan. Return dict (merge dengan default)."""
    cfg = {
        "mode": "unud",              # 'gmail' atau 'unud'
        "gmail_csv": "gmail_accounts.csv",
        "unud_csv": "unud_accounts.csv",
        "password": DEFAULT_PASSWORD,
        "server_url": DEFAULT_SERVER_URL,
        "output_file": "hasil_cek.csv",
        "html_file": "hasil_cek.html",
        "delay": DELAY_BETWEEN_ACCOUNTS,
        "fresh": False,
        "pause": True,
        "append": False,
        "html": True,
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                saved = json.load(f)
            cfg.update({k: v for k, v in saved.items() if v is not None})
        except Exception:
            pass
    return cfg


def save_config(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)


def get_csv_file(cfg):
    """Ambil file CSV sesuai mode aktif."""
    return cfg['gmail_csv'] if cfg['mode'] == 'gmail' else cfg['unud_csv']


def load_for_mode(cfg):
    """Load akun pakai loader sesuai mode aktif."""
    csv_file = get_csv_file(cfg)
    if cfg['mode'] == 'gmail':
        return load_gmail_accounts(csv_file, cfg['password']), csv_file
    return load_unud_accounts(csv_file, cfg['password']), csv_file


def show_config(cfg):
    print("\n" + "-" * 50)
    print("  PENGATURAN SAAT INI:")
    print("-" * 50)
    print(f"  Mode aktif             : {cfg['mode'].upper()}")
    print(f"  1. Password default    : {cfg['password']}")
    print(f"  2. Server browser      : {cfg['server_url']}")
    print(f"  3. File CSV (Gmail)    : {cfg['gmail_csv']}")
    print(f"  4. File CSV (UNUD)     : {cfg['unud_csv']}")
    print(f"  5. File output CSV     : {cfg['output_file']}")
    print(f"  6. HTML report         : {'aktif' if cfg['html'] else 'nonaktif'} ({cfg['html_file']})")
    print(f"  7. Delay antar akun    : {cfg['delay']} detik")
    print(f"  8. Fresh session       : {'YA' if cfg['fresh'] else 'TIDAK'}")
    print(f"  9. Pause @ berhasil    : {'YA' if cfg['pause'] else 'TIDAK'}")
    print(f"  10. Append             : {'YA' if cfg['append'] else 'TIDAK'}")
    print("-" * 50)


def settings_menu(cfg):
    """Sub-menu ubah pengaturan."""
    while True:
        show_config(cfg)
        print("""
--- UBAH PENGATURAN ---
  0. Kembali (simpan otomatis)
  m. Ganti mode (gmail <-> unud)
  Pilih nomor yang mau diubah:""")
        choice = input("> ").strip().lower()

        if choice == '0':
            save_config(cfg)
            print("✅ Pengaturan tersimpan.")
            return

        elif choice == 'm':
            cfg['mode'] = 'unud' if cfg['mode'] == 'gmail' else 'gmail'
            print(f"✅ Mode sekarang: {cfg['mode'].upper()}")

        elif choice == '1':
            cfg['password'] = input("Password default baru: ").strip() or cfg['password']

        elif choice == '2':
            cfg['server_url'] = input("URL server browser: ").strip() or cfg['server_url']

        elif choice == '3':
            val = input("File CSV Gmail: ").strip()
            if val and os.path.exists(val):
                cfg['gmail_csv'] = val
            else:
                print(f"❌ File tidak ada: {val}")

        elif choice == '4':
            val = input("File CSV UNUD: ").strip()
            if val and os.path.exists(val):
                cfg['unud_csv'] = val
            else:
                print(f"❌ File tidak ada: {val}")

        elif choice == '5':
            cfg['output_file'] = input("File output CSV: ").strip() or cfg['output_file']

        elif choice == '6':
            cfg['html'] = not cfg['html']
            print(f"HTML report: {'AKTIF' if cfg['html'] else 'NONAKTIF'}")

        elif choice == '7':
            try:
                cfg['delay'] = int(input("Delay (detik): ").strip() or cfg['delay'])
            except ValueError:
                print("❌ Harus angka")

        elif choice == '8':
            cfg['fresh'] = not cfg['fresh']
            print(f"Fresh session: {'YA' if cfg['fresh'] else 'TIDAK'}")

        elif choice == '9':
            cfg['pause'] = not cfg['pause']
            print(f"Pause @ berhasil: {'YA' if cfg['pause'] else 'TIDAK'}")

        elif choice == '10':
            cfg['append'] = not cfg['append']
            print(f"Append: {'YA' if cfg['append'] else 'TIDAK'}")

        else:
            print("❌ Pilihan tidak valid")


def check_server_status(cfg):
    """Cek status server browser."""
    print(f"\nMengecek server: {cfg['server_url']}...")
    client = CamofoxClient(cfg['server_url'])
    if client.check_server():
        print("✅ Server berjalan - browser connected!")
        return True
    print("❌ Server tidak berjalan.")
    print("\nCara menjalankan:")
    print("  1. Buka terminal baru")
    print("  2. cd C:\\Users\\ACER\\camofox-browser")
    print("  3. npm start")
    return False


def open_browser_folder():
    """Buka folder camofox-browser di explorer."""
    path = r"C:\Users\ACER\camofox-browser"
    if os.path.exists(path):
        subprocess.Popen(['explorer', path])
        print("✅ Folder dibuka di Explorer")
    else:
        print(f"❌ Folder tidak ada: {path}")


def open_output_folder():
    """Buka folder hasil di explorer."""
    subprocess.Popen(['explorer', os.path.abspath('.')])
    print("✅ Folder dibuka di Explorer")


def start_checker(cfg):
    """Jalankan proses cek akun sesuai mode aktif."""
    from check import run_checker

    if not check_server_status(cfg):
        return

    accounts, csv_file = load_for_mode(cfg)
    if not accounts:
        print(f"❌ Tidak ada akun di {csv_file}")
        return

    total = len(accounts)
    print(f"\nFile: {csv_file} | Mode: {cfg['mode'].upper()} | Total: {total}")
    print("-" * 75)
    for i, s in enumerate(accounts, 1):
        ident = s['nim'] or '-'
        nama = s['nama'][:25] or '-'
        pwd = '*' * len(s['password']) if s['password'] else '-'
        print(f"  {i:>3}. {ident:<15} | {nama:<25} | {s['email']:<40} | pwd: {pwd}")
    print("-" * 75)

    # Mulai dari akun ke-N (dihitung dari list asli, index 1-based)
    start_str = input(f"Mulai dari akun ke-? (Enter = 1): ").strip()
    start = 1
    if start_str:
        try:
            start = int(start_str)
            if start < 1:
                start = 1
            if start > total:
                print(f"❌ Melebihi total akun ({total})")
                return
        except ValueError:
            print("❌ Bukan angka, mulai dari 1")
            start = 1

    # Mau cek berapa akun (dari posisi start)
    sisa = total - start + 1
    limit_str = input(f"Mau cek berapa akun? (Enter = sisa {sisa}): ").strip()
    limit = sisa
    if limit_str:
        try:
            limit = int(limit_str)
            if limit < 1:
                print("❌ Harus angka >= 1")
                return
            if limit > sisa:
                print(f"⚠️  Melebihi sisa ({sisa}), pakai semua sisa")
                limit = sisa
        except ValueError:
            print("❌ Harus angka, pakai sisa akun")

    accounts = accounts[start - 1 : start - 1 + limit]
    print(f"✅ Akan mengecek {len(accounts)} akun (#{start} s/d #{start - 1 + len(accounts)})")

    run_checker(
        accounts=accounts,
        csv_file=csv_file,
        output=cfg['output_file'],
        html_file=cfg['html_file'] if cfg['html'] else None,
        password=cfg['password'],
        delay=cfg['delay'],
        fresh=cfg['fresh'],
        pause=cfg['pause'],
        append=cfg['append'],
    )


def preview_csv(cfg):
    """Lihat isi file CSV sesuai mode."""
    accounts, csv_file = load_for_mode(cfg)
    if not os.path.exists(csv_file):
        print(f"❌ File tidak ada: {csv_file}")
        return
    if not accounts:
        print(f"❌ Tidak ada akun di {csv_file}")
        return
    print(f"\nFile: {csv_file} | Mode: {cfg['mode'].upper()} | Total: {len(accounts)}")
    print("-" * 75)
    for i, s in enumerate(accounts, 1):
        ident = s['nim'] or '-'
        nama = s['nama'][:25] or '-'
        pwd = '*' * len(s['password']) if s['password'] else '-'
        print(f"  {i:>3}. {ident:<15} | {nama:<25} | {s['email']:<40} | pwd: {pwd}")
    print("-" * 75)


def main():
    cfg = load_config()

    while True:
        print()
        print("=" * 50)
        print("   EMAIL ACCOUNT CHECKER - MENU UTAMA")
        print("=" * 50)
        print(f"   Mode aktif: {cfg['mode'].upper()}")
        print("=" * 50)
        print("""
  1. MULAI CEK AKUN
  2. Pengaturan (mode, password, server, dll)
  3. Lihat pengaturan saat ini
  4. Preview file CSV (mode aktif)
  5. Cek status server browser
  6. Buka folder camofox-browser
  7. Buka folder hasil
  0. Keluar
""")
        choice = input("Pilih menu: ").strip()

        if choice == '1':
            start_checker(cfg)
        elif choice == '2':
            settings_menu(cfg)
        elif choice == '3':
            show_config(cfg)
            input("\nTekan Enter untuk kembali...")
        elif choice == '4':
            preview_csv(cfg)
            input("\nTekan Enter untuk kembali...")
        elif choice == '5':
            check_server_status(cfg)
            input("\nTekan Enter untuk kembali...")
        elif choice == '6':
            open_browser_folder()
        elif choice == '7':
            open_output_folder()
        elif choice == '0':
            save_config(cfg)
            print("Pengaturan tersimpan. Sampai jumpa!")
            break
        else:
            print("❌ Pilihan tidak valid")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDibatalkan.")
        sys.exit(0)
