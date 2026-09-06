#!/usr/bin/env python3
"""
Email Account Checker - Runner.
Bisa dijalankan langsung (CLI flags) atau dipanggil dari menu.py.
"""

import os
import sys

from checker import (
    CamofoxClient,
    check_account,
    do_logout,
    beep_success,
    load_gmail_accounts,
    load_unud_accounts,
    load_accounts_auto,
    generate_report,
    generate_html_report,
    DEFAULT_PASSWORD,
    DEFAULT_SERVER_URL,
    DELAY_BETWEEN_ACCOUNTS,
)


def run_checker(accounts, csv_file, output="hasil_cek.csv", html_file=None,
                password=DEFAULT_PASSWORD, delay=DELAY_BETWEEN_ACCOUNTS,
                fresh=False, pause=True, append=False):
    """Jalankan proses cek akun. accounts = list dari loaders.
    Dipanggil dari menu.py atau CLI."""
    if not accounts:
        print("Tidak ada akun. Pastikan file CSV benar.")
        return

    mode = 'UNUD (auto-generate)' if accounts[0]['nim'] else 'UNIVERSAL (email langsung)'

    print("\n" + "=" * 60)
    print("  KONFIGURASI:")
    print(f"  File CSV        : {os.path.abspath(csv_file)}")
    print(f"  Mode            : {mode}")
    print(f"  Password default: {password}")
    print(f"  Total akun      : {len(accounts)}")
    print(f"  Delay antar akun: {delay} detik")
    print(f"  Output          : {output}" + (f" + {html_file}" if html_file else ""))
    print(f"  Fresh session   : {'YA' if fresh else 'TIDAK'}")
    print(f"  Pause @ berhasil: {'YA' if pause else 'TIDAK'}")
    print(f"  Append mode     : {'YA' if append else 'TIDAK (overwrite)'}")
    print("=" * 60)

    # Preview akun
    print("\nDaftar akun yang akan dicek:")
    print("-" * 60)
    for i, s in enumerate(accounts, 1):
        ident = s['nim'] if s['nim'] else '-'
        nama = s['nama'][:30] if s['nama'] else '-'
        print(f"  {i:>3}. {ident:<15} | {nama:<30} | {s['email']}")
    print("-" * 60)

    # Konfirmasi
    val = input(f"\nLanjut cek {len(accounts)} akun? (Y/n): ").strip().lower()
    if val in ('n', 'no'):
        print("Dibatalkan.")
        return

    # ── Cek server ──
    print("\nMengecek server Camofox...")
    client = CamofoxClient(DEFAULT_SERVER_URL)
    if not client.check_server():
        print(f"\n❌ Server Camofox tidak berjalan di {DEFAULT_SERVER_URL}")
        print("  1. Buka terminal baru")
        print("  2. cd C:\\Users\\ACER\\camofox-browser")
        print("  3. npm start")
        return
    print("  ✅ Server berjalan - browser connected!")

    # ── Cleanup session lama ──
    if fresh:
        try:
            client.delete_session()
            client.delete_persisted_profile()
            print("  Session lama dihapus (fresh)")
        except Exception:
            pass
    else:
        try:
            client.delete_session()
        except Exception:
            pass
    client.wait(1)

    # ── Loop cek akun ──
    results = []
    for i, account in enumerate(accounts, 1):
        ident = account['nim'] or account['email'].split('@')[0]
        nama = account['nama'] or '-'
        print(f"\n[{i}/{len(accounts)}] Mengecek: {ident} - {nama[:35]}")
        print(f"  Email: {account['email']}")

        if fresh and i > 1:
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

        generate_report(results, output, append=append)
        if html_file:
            generate_html_report(results, html_file)

        do_logout(client)

        # Beep + pause saat BERHASIL
        if result['status'] == 'berhasil':
            beep_success()
            if pause:
                print("\n  🔔 BERHASIL login! Beep sudah dibunyikan.")
                print("  Tekan Enter untuk lanjut...")
                try:
                    input()
                except KeyboardInterrupt:
                    print("\n  Dihentikan pengguna.")
                    break

        if i < len(accounts):
            client.wait(delay)

    # ── Cleanup ──
    try:
        client.close_tab()
        client.delete_session()
    except Exception:
        pass

    # ── Laporan final ──
    generate_report(results, output, append=append)
    if html_file:
        generate_html_report(results, html_file)
        print(f"\nLaporan HTML: {os.path.abspath(html_file)}")

    print(f"\nSelesai! {len(results)} akun selesai dicek.")
    print(f"Laporan CSV: {os.path.abspath(output)}")


def cli():
    """Mode CLI dengan flags (untuk advanced user)."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Cek login akun Google via Camofox HTTP API")
    parser.add_argument('--mode', choices=['gmail', 'unud', 'auto'], default='auto',
                        help='Mode loader: gmail, unud, atau auto-detect (default: auto)')
    parser.add_argument('--csv', default=None,
                        help='File CSV akun (default: gmail_accounts.csv / unud_accounts.csv)')
    parser.add_argument('--output', default='hasil_cek.csv',
                        help='File output laporan (default: hasil_cek.csv)')
    parser.add_argument('--html', default=None,
                        help='File output laporan HTML (opsional)')
    parser.add_argument('--password', default=DEFAULT_PASSWORD,
                        help=f'Password default (default: {DEFAULT_PASSWORD})')
    parser.add_argument('--delay', type=int, default=DELAY_BETWEEN_ACCOUNTS,
                        help=f'Jeda antar akun (default: {DELAY_BETWEEN_ACCOUNTS}s)')
    parser.add_argument('--server-url', default=DEFAULT_SERVER_URL,
                        help=f'URL server Camofox (default: {DEFAULT_SERVER_URL})')
    parser.add_argument('--fresh', action='store_true',
                        help='Mulai dengan session kosong')
    parser.add_argument('--append', action='store_true',
                        help='Tambah hasil ke file output yang sudah ada')
    parser.add_argument('--pause', action='store_true',
                        help='Tunggu Enter setelah akun BERHASIL login')
    args = parser.parse_args()

    # Pilih loader sesuai mode
    if args.mode == 'gmail' or (args.mode == 'auto' and args.csv):
        csv_file = args.csv or 'gmail_accounts.csv'
        accounts = load_gmail_accounts(csv_file, args.password)
    elif args.mode == 'unud':
        csv_file = args.csv or 'unud_accounts.csv'
        accounts = load_unud_accounts(csv_file, args.password)
    else:
        csv_file = args.csv or 'accounts.csv'
        accounts = load_accounts_auto(csv_file, args.password)

    run_checker(
        accounts=accounts,
        csv_file=csv_file,
        output=args.output,
        html_file=args.html,
        password=args.password,
        delay=args.delay,
        fresh=args.fresh,
        pause=args.pause,
        append=args.append,
    )


if __name__ == '__main__':
    try:
        cli()
    except KeyboardInterrupt:
        print("\n\nDibatalkan.")
        sys.exit(0)
