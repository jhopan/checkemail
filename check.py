#!/usr/bin/env python3
"""
Email Account Checker - Uji Login Akun Google via Camofox
==========================================================
Versi modular. Support 3 format CSV (auto-detect):

  1. email,password   -> universal (password spesifik per akun)
  2. email            -> universal (pakai --password)
  3. nim,nama         -> mode UNUD (email auto-generate + password default)

Cara pakai:
  1. Jalankan server Camofox: cd camofox-browser && npm start
  2. Siapkan file CSV
  3. Jalankan: python check.py --csv accounts.csv

Contoh:
  python check.py --csv accounts.csv --yes          # universal
  python check.py --csv students.csv --yes          # mode UNUD
  python check.py --csv accounts.csv --yes --pause  # pause saat berhasil
"""

import os
import argparse

from checker import (
    CamofoxClient,
    check_account,
    do_logout,
    beep_success,
    load_accounts,
    generate_report,
    generate_html_report,
    DEFAULT_PASSWORD,
    DEFAULT_SERVER_URL,
    DELAY_BETWEEN_ACCOUNTS,
)


def main():
    parser = argparse.ArgumentParser(
        description="Cek login akun Google via Camofox HTTP API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Format CSV (auto-detect):
  email,password          -> password spesifik per akun
  email                   -> pakai --password
  nim,nama                -> mode UNUD (email auto-generate)

Contoh:
  python check.py --csv accounts.csv --yes
  python check.py --csv students.csv --yes --pause
  python check.py --csv accounts.csv --password otherpass --yes

PRASYARAT:
  1. Server Camofox jalan: cd camofox-browser && npm start
        """,
    )
    parser.add_argument('--csv', default='accounts.csv',
                        help='File CSV akun (default: accounts.csv)')
    parser.add_argument('--output', default='hasil_cek.csv',
                        help='File output laporan (default: hasil_cek.csv)')
    parser.add_argument('--html', default=None,
                        help='File output laporan HTML (opsional)')
    parser.add_argument('--password', default=DEFAULT_PASSWORD,
                        help=f'Password default (default: {DEFAULT_PASSWORD})')
    parser.add_argument('--delay', type=int, default=DELAY_BETWEEN_ACCOUNTS,
                        help=f'Jeda antar akun (default: {DELAY_BETWEEN_ACCOUNTS}s)')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Skip konfirmasi, langsung jalan')
    parser.add_argument('--server-url', default=DEFAULT_SERVER_URL,
                        help=f'URL server Camofox (default: {DEFAULT_SERVER_URL})')
    parser.add_argument('--fresh', action='store_true',
                        help='Mulai dengan session kosong')
    parser.add_argument('--append', action='store_true',
                        help='Tambah hasil ke file output yang sudah ada')
    parser.add_argument('--pause', action='store_true',
                        help='Tunggu Enter setelah akun BERHASIL login')
    args = parser.parse_args()

    # ── Validasi file ──
    if not os.path.exists(args.csv):
        print(f"File tidak ditemukan: {args.csv}")
        print("\nFormat CSV (auto-detect):")
        print("  email,password   -> password spesifik per akun")
        print("  email            -> pakai --password")
        print("  nim,nama         -> mode UNUD (email auto-generate)")
        print("\nContoh isi file:")
        print("  budi@gmail.com,password123")
        print("  budi@gmail.com")
        print("  2305541113,Gede Davananda Wicaksana")
        return

    # ── Baca akun ──
    accounts = load_accounts(args.csv, default_password=args.password)
    if not accounts:
        print("Tidak ada akun di file. Pastikan format benar.")
        return

    mode = 'UNUD (auto-generate email)' if accounts[0]['nim'] else 'UNIVERSAL (email langsung)'

    print("=" * 70)
    print("        EMAIL ACCOUNT CHECKER - Powered by Camoufox HTTP API")
    print("=" * 70)
    print(f"  File CSV        : {os.path.abspath(args.csv)}")
    print(f"  File output     : {os.path.abspath(args.output)}")
    print(f"  Mode            : {mode}")
    print(f"  Password default: {args.password}")
    print(f"  Total akun      : {len(accounts)}")
    print(f"  Delay antar akun: {args.delay} detik")
    print(f"  Server Camofox  : {args.server_url}")
    print(f"  Mode output     : "
          f"{'APPEND (tambah data)' if args.append else 'OVERWRITE (ganti data)'}")
    print("=" * 70)

    # ── Cek server Camofox ──
    print("\nMengecek server Camofox...")
    client = CamofoxClient(args.server_url)
    if not client.check_server():
        print(f"\n❌ Server Camofox tidak berjalan di {args.server_url}")
        print("\nCara menjalankan:")
        print("  1. Buka terminal baru")
        print("  2. cd C:\\Users\\ACER\\camofox-browser")
        print("  3. npm start")
        return
    print("  ✅ Server Camofox berjalan - browser connected!")

    # ── Cleanup session lama ──
    if args.fresh:
        print("\nMode --fresh: membersihkan session lama...")
        try:
            client.delete_session()
            client.delete_persisted_profile()
            print("  Session lama dihapus - mulai bersih")
        except Exception:
            print("  Tidak ada session lama")
        client.wait(1)
    else:
        try:
            client.delete_session()
        except Exception:
            pass
        client.wait(1)

    # ── Preview akun ──
    print("\nDaftar akun yang akan dicek:")
    print("-" * 70)
    for i, s in enumerate(accounts, 1):
        ident = s['nim'] if s['nim'] else '-'
        nama = s['nama'][:35] if s['nama'] else '-'
        print(f"  {i:>3}. {ident:<15} | {nama:<35} | {s['email']}")
    print("-" * 70)

    # ── Konfirmasi ──
    if not args.yes:
        print(f"\nAkan mengecek {len(accounts)} akun. "
              f"Tekan Enter untuk mulai (Ctrl+C untuk batal)...")
        try:
            input()
        except KeyboardInterrupt:
            print("\nDibatalkan.")
            return

    # ── Loop cek akun ──
    results = []
    for i, account in enumerate(accounts, 1):
        ident = account['nim'] or account['email'].split('@')[0]
        nama = account['nama'] or '-'
        print(f"\n[{i}/{len(accounts)}] Mengecek: {ident} - {nama[:35]}")
        print(f"  Email: {account['email']}")

        # Mode fresh: tutup tab + hapus cookies antar akun
        if args.fresh and i > 1:
            try:
                client.close_tab()
                client.clear_cookies()
                client.wait(1)
            except Exception:
                pass

        result = check_account(client, account['email'], account['password'])
        result['nim'] = account['nim']
        result['nama'] = account['nama']

        icon = {
            'berhasil': '[OK]', 'verifikasi': '[!]',
            'gagal': '[X]', 'error': '[E]', 'unknown': '[?]',
        }.get(result['status'], '[?]')
        print(f"  {icon} {result['status'].upper()} - {result['keterangan']}")

        results.append(result)

        # Simpan hasil sementara
        generate_report(results, args.output, append=args.append)
        if args.html:
            generate_html_report(results, args.html)

        # Logout
        do_logout(client)

        # Beep + pause saat BERHASIL
        if result['status'] == 'berhasil':
            beep_success()
            if args.pause:
                print("\n  🔔 BERHASIL login! Beep sudah dibunyikan.")
                print("  Tekan Enter untuk lanjut...")
                try:
                    input()
                except KeyboardInterrupt:
                    print("\n  Dihentikan pengguna.")
                    break

        # Delay antar akun
        if i < len(accounts):
            client.wait(args.delay)

    # ── Cleanup ──
    try:
        client.close_tab()
        client.delete_session()
    except Exception:
        pass

    # ── Laporan final ──
    generate_report(results, args.output, append=args.append)
    if args.html:
        generate_html_report(results, args.html)
        print(f"\nLaporan HTML tersimpan: {os.path.abspath(args.html)}")

    print(f"\nSelesai! {len(results)} akun selesai dicek.")
    print(f"Laporan CSV: {os.path.abspath(args.output)}")


if __name__ == '__main__':
    main()
