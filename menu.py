#!/usr/bin/env python3
"""
Menu utama Email Account Checker.
Atur semua pengaturan di sini: password, server browser, CSV, dll.

Jalankan: python menu.py
"""

import os
import sys
import json
import webbrowser
import subprocess

from checker import DEFAULT_PASSWORD, DEFAULT_SERVER_URL, DELAY_BETWEEN_ACCOUNTS

CONFIG_FILE = "config.json"


def load_config():
    """Baca config tersimpan. Return dict."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    # Default
    return {
        "password": DEFAULT_PASSWORD,
        "server_url": DEFAULT_SERVER_URL,
        "csv_file": "accounts.csv",
        "output_file": "hasil_cek.csv",
        "html_file": "hasil_cek.html",
        "delay": DELAY_BETWEEN_ACCOUNTS,
        "fresh": False,
        "pause": True,
        "append": False,
        "html": True,
        "yes": True,
    }


def save_config(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)


def show_config(cfg):
    print("\n" + "-" * 50)
    print("  PENGATURAN SAAT INI:")
    print("-" * 50)
    print(f"  1. Password default    : {cfg['password']}")
    print(f"  2. Server browser      : {cfg['server_url']}")
    print(f"  3. File CSV akun       : {cfg['csv_file']}")
    print(f"  4. File output CSV     : {cfg['output_file']}")
    print(f"  5. File output HTML    : {'aktif' if cfg['html'] else 'nonaktif'} ({cfg['html_file']})")
    print(f"  6. Delay antar akun    : {cfg['delay']} detik")
    print(f"  7. Fresh session       : {'YA' if cfg['fresh'] else 'TIDAK'}")
    print(f"  8. Pause @ berhasil    : {'YA' if cfg['pause'] else 'TIDAK'}")
    print(f"  9. Append (gak overwrite): {'YA' if cfg['append'] else 'TIDAK'}")
    print("-" * 50)


def settings_menu(cfg):
    """Sub-menu ubah pengaturan."""
    while True:
        show_config(cfg)
        print("""
--- UBAH PENGATURAN ---
  0. Kembali ke menu utama
  Pilih nomor yang mau diubah:""")
        choice = input("> ").strip()

        if choice == '0':
            save_config(cfg)
            print("✅ Pengaturan tersimpan.")
            return

        elif choice == '1':
            cfg['password'] = input("Password default baru: ").strip() or cfg['password']

        elif choice == '2':
            cfg['server_url'] = input("URL server browser: ").strip() or cfg['server_url']

        elif choice == '3':
            csv_file = input("File CSV akun: ").strip()
            if csv_file and os.path.exists(csv_file):
                cfg['csv_file'] = csv_file
            else:
                print(f"❌ File tidak ada: {csv_file}")

        elif choice == '4':
            cfg['output_file'] = input("File output CSV: ").strip() or cfg['output_file']

        elif choice == '5':
            cfg['html'] = not cfg['html']
            print(f"HTML report: {'AKTIF' if cfg['html'] else 'NONAKTIF'}")

        elif choice == '6':
            try:
                cfg['delay'] = int(input("Delay (detik): ").strip() or cfg['delay'])
            except ValueError:
                print("❌ Harus angka")

        elif choice == '7':
            cfg['fresh'] = not cfg['fresh']
            print(f"Fresh session: {'YA' if cfg['fresh'] else 'TIDAK'}")

        elif choice == '8':
            cfg['pause'] = not cfg['pause']
            print(f"Pause @ berhasil: {'YA' if cfg['pause'] else 'TIDAK'}")

        elif choice == '9':
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
    path = os.path.abspath('.')
    subprocess.Popen(['explorer', path])
    print("✅ Folder dibuka di Explorer")


def start_checker(cfg):
    """Jalankan proses cek akun."""
    from check import run_checker  # import runner dari check.py

    if not check_server_status(cfg):
        return

    run_checker(
        csv_file=cfg['csv_file'],
        output=cfg['output_file'],
        html_file=cfg['html_file'] if cfg['html'] else None,
        password=cfg['password'],
        delay=cfg['delay'],
        fresh=cfg['fresh'],
        pause=cfg['pause'],
        append=cfg['append'],
    )


def preview_csv(cfg):
    """Lihat isi file CSV."""
    if not os.path.exists(cfg['csv_file']):
        print(f"❌ File tidak ada: {cfg['csv_file']}")
        return
    from checker import load_accounts
    accounts = load_accounts(cfg['csv_file'], cfg['password'])
    mode = 'UNUD' if accounts and accounts[0]['nim'] else 'UNIVERSAL'
    print(f"\nMode terdeteksi: {mode}")
    print(f"Total akun: {len(accounts)}")
    print("-" * 70)
    for i, s in enumerate(accounts, 1):
        ident = s['nim'] or '-'
        nama = s['nama'][:25] or '-'
        pwd = '*' * len(s['password']) if s['password'] else '-'
        print(f"  {i:>3}. {ident:<15} | {nama:<25} | {s['email']:<40} | pwd: {pwd}")
    print("-" * 70)


def main():
    cfg = load_config()

    while True:
        print()
        print("=" * 50)
        print("   EMAIL ACCOUNT CHECKER - MENU UTAMA")
        print("=" * 50)
        print("""
  1. MULAI CEK AKUN
  2. Pengaturan (password, server, dll)
  3. Lihat pengaturan saat ini
  4. Preview file CSV
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
