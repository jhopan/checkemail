# Email Account Checker

Uji login akun Google secara batch via Camoufox HTTP API (anti-detect browser).

## Struktur (Modular)

```
checker email/
├── checker/                 # Package modular
│   ├── __init__.py          # Public API
│   ├── config.py            # Konstanta & deteksi signals
│   ├── client.py            # Camofox HTTP API client
│   ├── engine.py            # Logic cek login
│   ├── loaders.py           # Baca CSV (auto-detect 3 format)
│   └── reporter.py          # Output console/CSV/HTML
├── check.py                 # Entry point CLI
├── accounts.csv             # Contoh CSV universal
└── students.csv             # Contoh CSV mode UNUD
```

## Format CSV (Auto-Detect)

| Format | Keterangan |
|--------|------------|
| `email,password` | Universal — password spesifik per akun |
| `email` | Universal — pakai `--password` |
| `nim,nama` | Mode UNUD — email auto-generate + password default |

Contoh `accounts.csv`:
```
budi@gmail.com,password123
siti@yahoo.com
2305541113,Gede Davananda Wicaksana
```

- Delimiter auto-detect: koma (`,`) atau titik koma (`;`)
- Baris `#` = komentar, di-skip

## Cara Pakai

```bash
# 1. Jalankan server Camofox
cd C:\Users\ACER\camofox-browser
npm start

# 2. Jalankan checker
cd "C:\Users\ACER\Documents\Project\checker email"
python check.py --csv accounts.csv --yes
```

## Opsi

| Opsi | Keterangan |
|------|------------|
| `--csv FILE` | File CSV akun (default: `accounts.csv`) |
| `--output FILE` | Output laporan CSV (default: `hasil_cek.csv`) |
| `--html FILE` | Output laporan HTML (opsional) |
| `--password PWD` | Password default (default: `unud2023`) |
| `--delay N` | Jeda antar akun (default: 3 detik) |
| `--yes, -y` | Skip konfirmasi, langsung jalan |
| `--server-url URL` | URL server Camofox (default: `http://localhost:9377`) |
| `--fresh` | Mulai dengan session kosong |
| `--append` | Tambah hasil ke file yang ada |
| `--pause` | Tunggu Enter setelah akun BERHASIL login |

## Status Hasil

| Status | Arti |
|--------|------|
| `berhasil` | Login sukses — password masih default |
| `verifikasi` | Google minta verifikasi — password sudah diganti (aman) |
| `gagal` | Email tidak ditemukan / password salah |
| `error` | Something wrong / server error |
| `unknown` | Status tidak diketahui — cek manual |

Saat akun `berhasil`, script **bunyi beep** (Windows) + pause jika pakai `--pause`.

## Penggunaan sebagai Library

```python
from checker import (
    CamofoxClient, check_account, load_accounts,
    generate_report, beep_success,
)

accounts = load_accounts('accounts.csv')
client = CamofoxClient('http://localhost:9377')

for acc in accounts:
    result = check_account(client, acc['email'], acc['password'])
    print(result['status'], result['email'])
    if result['status'] == 'berhasil':
        beep_success()
```

## Fitur

- Human-like typing (delay random 50-150ms per karakter)
- Auto-handle "Choose an account" page (retry 5x + fallback)
- Auto-detect akun masih login → navigate ke accountchooser
- Auto-retry tab creation + session renew
- Deteksi lengkap: verifikasi HP/SMS/OTP, password salah, something wrong
- Beep + pause saat login berhasil
- Laporan CSV + HTML
