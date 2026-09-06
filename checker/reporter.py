"""Reporter: output laporan ke console, CSV, dan HTML."""

import csv
import os
from datetime import datetime


def _counts(results):
    return {
        'berhasil': [r for r in results if r['status'] == 'berhasil'],
        'verifikasi': [r for r in results if r['status'] == 'verifikasi'],
        'gagal': [r for r in results if r['status'] == 'gagal'],
        'error': [r for r in results if r['status'] == 'error'],
        'unknown': [r for r in results if r['status'] == 'unknown'],
    }


def generate_report(results, output_path, append=False):
    """Tulis CSV + ringkasan console. append=True = tambah tanpa hapus data lama."""
    fieldnames = ['nim', 'nama', 'email', 'status']

    file_exists = os.path.exists(output_path) and os.path.getsize(output_path) > 0
    mode = 'a' if (append and file_exists) else 'w'

    with open(output_path, mode, newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if mode == 'w' or not file_exists:
            writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, '') for k in fieldnames})

    c = _counts(results)

    print("\n" + "=" * 70)
    print("                    RINGKASAN HASIL PENGECEKAN")
    print("=" * 70)
    print(f"  Total akun dicek  : {len(results)}")
    print(f"  [OK]   Berhasil    : {len(c['berhasil'])}  -> password BELUM di ubah")
    print(f"  [!]    Verifikasi  : {len(c['verifikasi'])}  -> password SUDAH di ganti (aman)")
    print(f"  [X]    Gagal       : {len(c['gagal'])}  -> email salah / password diganti")
    print(f"  [E]    Error        : {len(c['error'])}")
    print(f"  [?]    Unknown      : {len(c['unknown'])}")
    print("=" * 70)
    print(f"  Mode           : "
          f"{'APPEND (tambah ke data lama)' if append and file_exists else 'OVERWRITE (ganti data lama)'}")
    print(f"  Laporan CSV    : {os.path.abspath(output_path)}")
    print("=" * 70)

    print("\n" + "-" * 95)
    print(f"{'No':>3} | {'NIM':<15} | {'Nama':<30} | {'Email':<45} | {'Status':<12}")
    print("-" * 95)
    for i, r in enumerate(results, 1):
        print(f"{i:>3} | {r.get('nim', ''):<15} | "
              f"{r.get('nama', '-')[:30]:<30} | "
              f"{r['email'][:45]:<45} | {r['status']:<12}")
    print("-" * 95)


def generate_html_report(results, html_path):
    """Tulis laporan HTML."""
    c = _counts(results)
    lainnya = len(c['error']) + len(c['unknown'])

    icon_map = {
        'berhasil': ('OK', '#22c55e'),
        'verifikasi': ('!', '#f59e0b'),
        'gagal': ('X', '#ef4444'),
        'error': ('E', '#ef4444'),
        'unknown': ('?', '#6b7280'),
    }
    rows_html = ""
    for i, r in enumerate(results, 1):
        icon, color = icon_map.get(r['status'], ('?', '#6b7280'))
        rows_html += f"""
        <tr>
            <td style="text-align:center">{i}</td>
            <td><code>{r.get('nim', '-')}</code></td>
            <td>{r.get('nama', '-')}</td>
            <td><code style="font-size:12px">{r['email']}</code></td>
            <td style="text-align:center"><span style="background:{color};color:white;
                padding:2px 8px;border-radius:4px;font-weight:bold;font-size:11px">{icon}</span>
                {r['status']}</td>
            <td>{r['keterangan']}</td>
            <td style="font-size:12px;color:#666">{r.get('timestamp', '')}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Laporan Cek Akun Email</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 20px; background: #f8fafc; }}
        h1 {{ color: #1e40af; border-bottom: 3px solid #1e40af; padding-bottom: 10px; }}
        .summary {{ display: flex; gap: 15px; margin: 20px 0; flex-wrap: wrap; }}
        .card {{ padding: 15px 25px; border-radius: 8px; color: white; font-weight: bold;
                 min-width: 120px; text-align: center; }}
        .card.berhasil {{ background: #22c55e; }}
        .card.verifikasi {{ background: #f59e0b; }}
        .card.gagal {{ background: #ef4444; }}
        .card.lainnya {{ background: #6b7280; }}
        .card .num {{ font-size: 28px; }}
        .card .label {{ font-size: 12px; opacity: 0.9; }}
        table {{ width: 100%; border-collapse: collapse; background: white;
                 border-radius: 8px; overflow: hidden;
                 box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        th {{ background: #1e40af; color: white; padding: 12px 8px; text-align: left;
              font-size: 13px; }}
        td {{ padding: 10px 8px; border-bottom: 1px solid #e5e7eb; font-size: 13px; }}
        tr:hover {{ background: #f1f5f9; }}
        .footer {{ margin-top: 20px; text-align: center; color: #94a3b8; font-size: 12px; }}
    </style>
</head>
<body>
    <h1>Laporan Cek Akun Email</h1>
    <p>Dibuat: {datetime.now().strftime('%d %B %Y, %H:%M:%S')}</p>
    <div class="summary">
        <div class="card berhasil"><div class="num">{len(c['berhasil'])}</div>
            <div class="label">BERHASIL (belum ganti)</div></div>
        <div class="card verifikasi"><div class="num">{len(c['verifikasi'])}</div>
            <div class="label">VERIFIKASI (sudah aman)</div></div>
        <div class="card gagal"><div class="num">{len(c['gagal'])}</div>
            <div class="label">GAGAL</div></div>
        <div class="card lainnya"><div class="num">{lainnya}</div>
            <div class="label">LAINNYA</div></div>
    </div>
    <table>
        <thead><tr>
            <th style="width:40px">No</th><th>NIM</th><th>Nama</th><th>Email</th>
            <th>Status</th><th>Keterangan</th><th>Waktu Cek</th>
        </tr></thead>
        <tbody>{rows_html}
        </tbody>
    </table>
    <div class="footer">
        Generated by Email Checker (Camoufox HTTP API)
    </div>
</body>
</html>"""
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
