# Google Account Checker - Uji Login Akun Google Mahasiswa

Script Python untuk mengecek login akun Google mahasiswa secara batch (banyak akun sekaligus). Script ini menggunakan Playwright untuk automasi browser.

## 📦 Instalasi

### 1. Install Python 3.8+
Pastikan Python sudah terinstall di komputer Anda.

### 2. Install dependencies
```bash
cd google-account-checker
pip install -r requirements.txt
```

### 3. Install browser Playwright
```bash
playwright install chromium
```

## 📁 Struktur File

```
google-account-checker/
├── check_google_accounts.py   # Script utama
├── students.csv              # Data mahasiswa (EDIT INI)
├── requirements.txt          # Dependencies
├── README.md                 # Petunjuk ini
├── hasil_cek.csv             # Output laporan (otomatis)
└── hasil_cek.html            # Output laporan HTML (opsional)
```

## 📝 Format File CSV

File `students.csv` harus memiliki header berikut:
```
nim,nama,alamat,nohp,status
```

Contoh isi:
```csv
nim,nama,alamat,nohp,status
2305541126,Putu Gede Ananda Krishna Dipayana,Jl. Raya Tuban No. 99X,085958922425,Non-aktif
2305541127,I Made Krishna Mahayana,Jl. Pertulaka No. 15,081999587658,Aktif
```

Email akan **otomatis di-generate** dari nama belakang + NIM:
- `Putu Gede Ananda Krishna Dipayana` + `2305541126` → `dipayana.2305541126@student.unud.ac.id`

## 🚀 Cara Pakai

### Cara dasar:
```bash
python check_google_accounts.py
```
Script akan membaca `students.csv`, cek semua akun, dan simpan hasil ke `hasil_cek.csv`.

### Opsi lengkap:
```bash
python check_google_accounts.py --csv students.csv --output hasil_cek.csv --html hasil_cek.html --headless --delay 5
```

### Parameter:
| Parameter | Default | Keterangan |
|-----------|---------|------------|
| `--csv` | `students.csv` | Path file CSV data mahasiswa |
| `--output` | `hasil_cek.csv` | Path file output laporan CSV |
| `--html` | (none) | Path file output laporan HTML (opsional) |
| `--password` | `unud2023` | Password default untuk login |
| `--headless` | (off) | Jalankan browser tanpa GUI (lebih cepat) |
| `--delay` | `3` | Jeda antar akun dalam detik |
| `--no-logout` | (off) | Jangan logout setelah cek (untuk debug) |

### Contoh kasus:

**Cek dengan password baru:**
```bash
python check_google_accounts.py --password unud2024
```

**Cek mode headless (tanpa tampilan browser):**
```bash
python check_google_accounts.py --headless
```

**Cek dengan laporan HTML:**
```bash
python check_google_accounts.py --html laporan.html
```

**Cek file CSV berbeda:**
```bash
python check_google_accounts.py --csv data_mhs_baru.csv --output laporan_baru.csv
```

## 📊 Status yang Mungkin Muncul

| Status | Icon | Arti |
|--------|------|------|
| `berhasil` | [OK] | Login berhasil - password masih default (belum diubah) |
| `verifikasi` | [!] | Google minta verifikasi - password SUDAH diganti (akun aman) |
| `gagal` | [X] | Password salah atau email tidak ditemukan |
| `timeout` | [T] | Halaman tidak merespons dalam 30 detik |
| `error` | [E] | Error lainnya |
| `unknown` | [?] | Status tidak diketahui - perlu cek manual |

## 📋 Output

### 1. CSV (hasil_cek.csv)
Kolom: `nim, nama, email, status, keterangan, timestamp`

### 2. HTML (hasil_cek.html) - jika pakai `--html`
Laporan visual dengan tabel berwarna dan ringkasan statistik.

## ⚠️ Tips Penting

1. **Jangan cek terlalu cepat**: Google bisa blok jika login terlalu sering dalam waktu singkat. Gunakan `--delay 5` atau lebih.
2. **Mode headless**: Lebih cepat tapi Google lebih mudah deteksi bot. Jika ada masalah, jangan pakai `--headless`.
3. **Hasil tersimpan otomatis**: Setiap selesai cek 1 akun, hasil langsung disimpan ke CSV. Jika script dihentikan di tengah, hasil yang sudah dicek tetap tersimpan.
4. **Password default**: Jika password mahasiswa sudah diganti, login akan gagal/verifikasi = berarti akun sudah aman.

## 🔄 Update Data Mahasiswa

Untuk cek mahasiswa baru:
1. Edit `students.csv` - tambah baris baru dengan data mahasiswa
2. Jalankan ulang script

## ❓ Troubleshooting

**Error: "Playwright belum terinstall"**
```bash
pip install playwright
playwright install chromium
```

**Error: "Browser tidak bisa launch"**
- Jangan pakai `--headless` (gunakan mode GUI)
- Atau coba: `playwright install --with-deps chromium`

**Semua akun status "unknown"**
- Google mungkin mengubah tampilan login. Buka browser secara manual ke `accounts.google.com/signin` dan cek struktur halaman terbaru.
- Atau coba tanpa `--headless` untuk lihat apa yang terjadi.

**Login selalu gagal padahal email benar**
- Cek format email: `namabelakang.nim@student.unud.ac.id`
- Pastikan nama belakang dieja dengan benar (tanpa spasi di akhir)
- Coba login manual untuk 1 akun sebagai pembanding
