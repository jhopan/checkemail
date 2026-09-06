"""Loader data akun - dipisah per mode (Gmail vs UNUD).

3 fungsi loader, masing-masing 1 format. Tidak ada auto-detect yang
menebak-nebak - pilih loader sesuai file yang dimiliki:

  load_gmail_accounts(path)     -> "email,password" / "email"
  load_unud_accounts(path)      -> "nim,nama"
  load_accounts_auto(path)      -> deteksi otomatis (untuk kenyamanan)

Delimiter auto-detect: koma (,) atau titik koma (;).
Baris kosong dan baris mulai dengan '#' di-skip.
"""

import re

from .config import DEFAULT_PASSWORD, EMAIL_DOMAIN


# ── Helper umum ──────────────────────────────────────────────

def _read_lines(csv_path):
    """Baca file, return list baris bersih (skip kosong & komentar)."""
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        for raw in f:
            line = raw.strip()
            if line and not line.startswith('#'):
                yield line


def _split_delimiter(line):
    """Split baris pakai koma atau titik koma. Return list ter-trim."""
    if ',' in line:
        parts = line.split(',')
    elif ';' in line:
        parts = line.split(';')
    else:
        parts = [line]
    return [p.strip() for p in parts]


def _is_email(s):
    return '@' in s and '.' in s.split('@')[-1]


def generate_email(nama, nim):
    """Generate email UNUD dari nama belakang + NIM.
    Contoh: 'Gede Davananda Wicaksana' + '2305541113'
         -> 'wicaksana.2305541113@student.unud.ac.id'
    """
    nama_belakang = nama.strip().split()[-1].lower()
    nama_belakang = re.sub(r'[^a-z]', '', nama_belakang)
    return f"{nama_belakang}.{nim}{EMAIL_DOMAIN}"


def _skip_header(first_field):
    return first_field.lower() in ('nim', 'email', 'email,password', 'nim,nama')


# ── Loader Gmail / Universal ─────────────────────────────────

def load_gmail_accounts(csv_path, default_password=None):
    """Baca file akun Gmail/universal.

    Format per baris:
      email,password   -> password spesifik
      email            -> pakai default_password

    Return list of dict: {email, password, nim: '', nama: ''}
    """
    default_password = default_password or DEFAULT_PASSWORD
    accounts = []

    for line in _read_lines(csv_path):
        parts = _split_delimiter(line)
        first = parts[0]

        if _skip_header(first):
            continue
        if not _is_email(first):
            continue

        password = parts[1] if len(parts) > 1 and parts[1] else default_password
        accounts.append({
            'email': first,
            'password': password,
            'nim': '',
            'nama': '',
        })

    return accounts


# ── Loader UNUD ──────────────────────────────────────────────

def load_unud_accounts(csv_path, default_password=None):
    """Baca file akun mahasiswa UNUD.

    Format per baris:
      nim,nama         -> email di-generate otomatis
                          (namabelakang.nim@student.unud.ac.id)

    Return list of dict: {email, password, nim, nama}
    """
    default_password = default_password or DEFAULT_PASSWORD
    accounts = []

    for line in _read_lines(csv_path):
        parts = _split_delimiter(line)
        first = parts[0]

        if _skip_header(first):
            continue
        if _is_email(first):
            continue  # bukan format nim,nama

        nim = first
        nama = parts[1] if len(parts) > 1 else ''
        if not nim or not nama:
            continue

        accounts.append({
            'email': generate_email(nama, nim),
            'password': default_password,
            'nim': nim,
            'nama': nama,
        })

    return accounts


# ── Auto-detect (kenyamanan) ─────────────────────────────────

def detect_mode(csv_path):
    """Deteksi mode file: 'gmail' atau 'unud'.
    Lihat baris data pertama yang valid: ada '@' = gmail, tidak = unud.
    """
    for line in _read_lines(csv_path):
        parts = _split_delimiter(line)
        if not parts or _skip_header(parts[0]):
            continue
        return 'gmail' if _is_email(parts[0]) else 'unud'
    return 'gmail'


def load_accounts_auto(csv_path, default_password=None):
    """Deteksi otomatis mode file lalu pakai loader yang sesuai."""
    if detect_mode(csv_path) == 'unud':
        return load_unud_accounts(csv_path, default_password)
    return load_gmail_accounts(csv_path, default_password)


# Alias lama (backward compatible)
load_accounts = load_accounts_auto
