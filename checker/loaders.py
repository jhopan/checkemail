"""Loader data akun dari file CSV.

Auto-detect 3 format:
1. "email,password" -> universal (password spesifik per akun)
2. "email"          -> universal (pakai password default)
3. "nim,nama"       -> mode UNUD (generate email otomatis)

Delimiter auto-detect: koma (,) atau titik koma (;).
"""

import re

from .config import DEFAULT_PASSWORD, EMAIL_DOMAIN


def generate_email(nama, nim):
    """Generate email UNUD dari nama belakang + NIM.
    Contoh: 'Gede Davananda Wicaksana' + '2305541113'
         -> 'wicaksana.2305541113@student.unud.ac.id'
    """
    nama_belakang = nama.strip().split()[-1].lower()
    nama_belakang = re.sub(r'[^a-z]', '', nama_belakang)
    return f"{nama_belakang}.{nim}{EMAIL_DOMAIN}"


def _is_email(s):
    return '@' in s and '.' in s.split('@')[-1]


def load_accounts(csv_path, default_password=None):
    """Baca file CSV/teks. Return list of dict.

    Setiap dict berisi:
      email    : alamat email (wajib)
      password : password untuk login
      nim      : NIM (kosong kalau universal)
      nama     : nama (kosong kalau universal)
    """
    default_password = default_password or DEFAULT_PASSWORD
    accounts = []

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Split delimiter (koma atau titik koma)
            if ',' in line:
                parts = line.split(',')
            elif ';' in line:
                parts = line.split(';')
            else:
                # Satu kolom: bisa email langsung atau NIM saja
                parts = [line]

            parts = [p.strip() for p in parts]
            first = parts[0]

            # Skip header
            if first.lower() in ('nim', 'email', 'email,password', 'nim,nama'):
                continue

            # ── Format 1 & 2: email[,password] ──
            if _is_email(first):
                email = first
                password = parts[1] if len(parts) > 1 and parts[1] else default_password
                accounts.append({
                    'email': email,
                    'password': password,
                    'nim': '',
                    'nama': '',
                })
                continue

            # ── Format 3: nim,nama (mode UNUD) ──
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
