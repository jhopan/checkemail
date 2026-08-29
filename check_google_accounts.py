#!/usr/bin/env python3
"""
Google Account Checker - Uji Login Akun Google Mahasiswa
=========================================================
Script untuk mengecek login akun Google mahasiswa secara batch.
Format email: namabelakang.nim@student.unud.ac.id
Password default: unud2023

Cara pakai:
  1. Jalankan server Camofox: cd camofox-browser && npm start
  2. Edit file students.csv dengan data mahasiswa
  3. Jalankan: python check_google_accounts.py

Opsi:
  --csv students.csv        File CSV data mahasiswa
  --output hasil_cek.csv    File output laporan
  --password unud2023       Password default
  --delay 3                 Jeda antar akun (detik)
  --yes                     Skip konfirmasi
  --server-url              URL server Camofox (default: http://localhost:9377)
"""

import csv
import re
import sys
import os
import json
import time
import argparse
import requests
from datetime import datetime
from pathlib import Path

# ============================================================
# KONFIGURASI DEFAULT
# ============================================================
DEFAULT_PASSWORD = "unud2023"
EMAIL_DOMAIN = "@student.unud.ac.id"
LOGIN_URL = "https://accounts.google.com/signin"
LOGOUT_URL = "https://accounts.google.com/Logout"
DEFAULT_SERVER_URL = "http://localhost:9377"
REQUEST_TIMEOUT = 60      # detik timeout untuk HTTP request (Google butuh waktu load)
WAIT_AFTER_CLICK = 5      # detik tunggu setelah klik Next
DELAY_BETWEEN_ACCOUNTS = 3 # jeda antar akun

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


# ============================================================
# FUNGSI UTILITY
# ============================================================
def generate_email(nama, nim):
    """Generate email dari nama belakang + NIM"""
    nama_belakang = nama.strip().split()[-1].lower()
    nama_belakang = re.sub(r'[^a-z]', '', nama_belakang)
    return f"{nama_belakang}.{nim}{EMAIL_DOMAIN}"


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}")


# ============================================================
# CAMOFOX HTTP API CLIENT
# ============================================================
class CamofoxClient:
    """Client untuk berinteraksi dengan server Camofox via HTTP API"""

    def __init__(self, server_url=DEFAULT_SERVER_URL, user_id=None):
        self.server_url = server_url.rstrip('/')
        # Fix: Windows sering resolve localhost ke IPv6 (::1) yang timeout
        # Ganti localhost ke 127.0.0.1 untuk IPv4 yang lebih cepat
        if 'localhost' in self.server_url:
            self.server_url = self.server_url.replace('localhost', '127.0.0.1')
        # User ID unik setiap kali script dijalankan = session selalu fresh
        if user_id is None:
            user_id = f"checker_{int(time.time())}"
        self.user_id = user_id
        self.session_key = f"session_{int(time.time())}"
        self.tab_id = None

    def _get(self, path, **kwargs):
        url = f"{self.server_url}{path}"
        r = requests.get(url, timeout=REQUEST_TIMEOUT, **kwargs)
        return r.json()

    def _post(self, path, data=None, timeout=REQUEST_TIMEOUT):
        url = f"{self.server_url}{path}"
        r = requests.post(url, json=data, timeout=timeout)
        return r.json()

    def _delete(self, path):
        url = f"{self.server_url}{path}"
        r = requests.delete(url, timeout=REQUEST_TIMEOUT)
        return r.json()

    def check_server(self):
        """Cek apakah server Camofox berjalan"""
        # Coba beberapa varian URL (localhost, 127.0.0.1, ::1)
        # Windows kadang resolve localhost ke IPv6 dulu yang menyebabkan timeout
        urls_to_try = [
            f"http://127.0.0.1:9377/health",
            f"http://localhost:9377/health",
            f"{self.server_url}/health",
        ]
        for url in urls_to_try:
            try:
                r = requests.get(url, timeout=10)
                data = r.json()
                if data.get("ok", False):
                    return True
            except:
                continue
        return False

    def create_tab(self, url):
        """Buka tab baru dengan URL tertentu. Retry sampai tab benar-benar terbentuk."""
        data = {
            "userId": self.user_id,
            "sessionKey": self.session_key,
            "url": url
        }
        # Retry sampai 3x kalau tab gagal create
        for attempt in range(3):
            try:
                result = self._post("/tabs", data, timeout=90)
                if "tabId" in result:
                    self.tab_id = result["tabId"]
                    return result
                # Tab belum terbentuk, mungkin session expired
                if result.get("code") == "session_expired" or result.get("error", "").find("expired") >= 0:
                    log(f"  Session expired, buat session baru... (attempt {attempt+1})")
                    # Hapus session lama, buat baru
                    try:
                        self._delete(f"/sessions/{self.user_id}")
                    except:
                        pass
                    self.session_key = f"session_{int(time.time())}_{attempt}"
                    data["sessionKey"] = self.session_key
                    time.sleep(2)
                    continue
                # Error lain
                log(f"  Tab creation gagal: {result} (attempt {attempt+1})")
                time.sleep(3)
            except requests.exceptions.Timeout:
                log(f"  Tab creation timeout, retry... (attempt {attempt+1})")
                time.sleep(3)
            except Exception as e:
                log(f"  Tab creation error: {e} (attempt {attempt+1})")
                time.sleep(3)
        return {"error": "Tab creation failed after 3 attempts"}

    def ensure_tab(self, url=LOGIN_URL):
        """Pastikan tab aktif. Kalau tidak ada, buat baru. Kalau ada, verify masih hidup."""
        if self.tab_id:
            # Cek apakah tab masih hidup dengan ambil snapshot
            try:
                self._get(f"/tabs/{self.tab_id}/snapshot",
                          params={"userId": self.user_id})
                return True  # Tab masih hidup
            except:
                # Tab sudah mati, reset
                self.tab_id = None

        # Tab tidak ada, buat baru
        log(f"  Tab tidak ditemukan, buat tab baru...")
        result = self.create_tab(url)
        if "tabId" in result:
            time.sleep(4)  # Tunggu tab benar-benar siap
            return True
        return False

    def get_snapshot(self):
        """Ambil snapshot halaman saat ini"""
        return self._get(f"/tabs/{self.tab_id}/snapshot",
                         params={"userId": self.user_id})

    def type_text(self, ref, text):
        """Ketik teks ke element berdasarkan ref"""
        data = {"userId": self.user_id, "ref": ref, "text": text}
        return self._post(f"/tabs/{self.tab_id}/type", data)

    def click(self, ref):
        """Klik element berdasarkan ref. Ignore timeout karena klik sering berhasil walau response timeout."""
        data = {"userId": self.user_id, "ref": ref}
        try:
            return self._post(f"/tabs/{self.tab_id}/click", data)
        except requests.exceptions.Timeout:
            # Click sering berhasil walau response timeout. Return OK anyway.
            return {"ok": True, "note": "click sent (response timed out but click likely succeeded)"}
        except Exception as e:
            return {"error": str(e)}

    def evaluate(self, js_code):
        """Jalankan JavaScript di halaman (lebih reliable dari HTTP click)"""
        data = {"userId": self.user_id, "expression": js_code}
        try:
            return self._post(f"/tabs/{self.tab_id}/evaluate", data)
        except:
            return {"error": "evaluate failed"}

    def type_text_js(self, selector, text):
        """Ketik teks via JavaScript dengan native setter + delay per karakter (simulasi human typing)"""
        chars_js = ",".join([repr(c) for c in text])
        js = f"""
        (async () => {{
            const el = document.querySelector('{selector}');
            if (!el) return 'not found';
            el.focus();
            const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            const chars = [{chars_js}];
            let current = '';
            for (const ch of chars) {{
                current += ch;
                nativeSetter.call(el, current);
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
                await new Promise(r => setTimeout(r, 50 + Math.random() * 100));
            }}
            return 'typed ' + chars.length + ' chars, final: ' + el.value.length;
        }})()
        """
        return self.evaluate(js)

    def click_js(self, selector):
        """Klik element via JavaScript dengan PointerEvent + mouse events lengkap"""
        js = f"""
        (() => {{
            const el = document.querySelector('{selector}');
            if (!el) return 'not found';
            const btn = el.querySelector('button') || el;
            // PointerEvent (Google butuh ini untuk bekerja)
            btn.dispatchEvent(new PointerEvent('pointerdown', {{bubbles: true, cancelable: true, pointerId: 1, pointerType: 'mouse'}}));
            btn.dispatchEvent(new PointerEvent('pointerup', {{bubbles: true, cancelable: true, pointerId: 1, pointerType: 'mouse'}}));
            // Mouse events
            btn.dispatchEvent(new MouseEvent('mousedown', {{bubbles: true, cancelable: true}}));
            btn.dispatchEvent(new MouseEvent('mouseup', {{bubbles: true, cancelable: true}}));
            btn.dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true}}));
            return 'clicked';
        }})()
        """
        return self.evaluate(js)

    def navigate(self, url):
        """Navigasi ke URL"""
        data = {"userId": self.user_id, "url": url}
        return self._post(f"/tabs/{self.tab_id}/navigate", data)

    def close_tab(self):
        """Tutup tab"""
        if self.tab_id:
            self._delete(f"/tabs/{self.tab_id}?userId={self.user_id}")
            self.tab_id = None

    def delete_session(self):
        """Hapus session di server"""
        self._delete(f"/sessions/{self.user_id}")

    def delete_persisted_profile(self):
        """Hapus file persistence (cookies/storage state) untuk user ini"""
        try:
            self._delete(f"/sessions/{self.user_id}/persistence")
        except:
            pass

    def clear_cookies(self):
        """Hapus cookies di browser context"""
        try:
            # POST dengan empty cookies array untuk replace
            self._post(f"/sessions/{self.user_id}/cookies",
                       {"userId": self.user_id, "sessionKey": self.session_key, "cookies": []})
        except:
            pass

    def wait(self, seconds):
        """Tunggu"""
        time.sleep(seconds)

    def get_full_snapshot(self):
        """Ambil snapshot lengkap (text + URL)"""
        data = self.get_snapshot()
        return data.get("snapshot", ""), data.get("url", "")

    def find_ref(self, snapshot_text, pattern):
        """
        Cari ref di snapshot berdasarkan pattern text.
        Return ref ID (e.g. "e1") atau None.
        """
        # Pattern: cari "[eN]" sebelum/sesudah text yang cocok
        # Snapshot format: - textbox "Email or phone" [e1]
        import re
        match = re.search(r'\[(' + pattern + r')\]', snapshot_text)
        if match:
            return match.group(1)
        return None

    def find_ref_by_text(self, snapshot_text, search_text):
        """
        Cari ref berdasarkan text yang ada di snapshot.
        Contoh: cari tombol "Next" -> return ref-nya.
        """
        import re
        # Pattern: cari baris yang mengandung search_text dan punya [eN]
        lines = snapshot_text.split('\n')
        for line in lines:
            if search_text.lower() in line.lower():
                match = re.search(r'\[e(\d+)\]', line)
                if match:
                    return f"e{match.group(1)}"
        return None


# ============================================================
# FUNGSI CEK AKUN
# ============================================================
def check_account(client, email, password=DEFAULT_PASSWORD):
    """
    Cek login satu akun Google via Camofox HTTP API.
    """
    result = {
        "email": email,
        "status": "unknown",
        "keterangan": "",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    try:
        # ── STEP 1: Pastikan tab aktif ──
        if not client.ensure_tab(LOGIN_URL):
            result["status"] = "error"
            result["keterangan"] = "Tidak bisa buka tab di server Camofox"
            return result

        # Kalau tab sudah ada dan sudah login sebelumnya, navigate ke login
        # (ensure_tab sudah handle ini)
        client.wait(4)  # Tunggu halaman login load

        # ── STEP 2: Ambil snapshot ──
        log(f"  Ambil snapshot...")
        snapshot, url = client.get_full_snapshot()
        client.wait(3)  # Jeda 3 detik

        # ── DETEKSI HALAMAN "Choose an account" ──
        # Jika akun sebelumnya masih login, Google tampilkan halaman pilih akun
        choose_account_signals = ["choose an account", "pilih akun", "use another account", "gunakan akun lain"]
        if any(sig in snapshot.lower() for sig in choose_account_signals):
            log("  Halaman 'Choose an account' terdeteksi")

            # Retry klik "Use another account" sampai halaman login muncul
            max_click_retries = 5
            for click_attempt in range(max_click_retries):
                log(f"  Klik 'Use another account' (attempt {click_attempt+1}/{max_click_retries})")
                
                # Method 1: Cari ref dari snapshot, lalu HTTP click (Playwright native - trusted click)
                another_ref = client.find_ref_by_text(snapshot, "Use another account")
                if not another_ref:
                    another_ref = client.find_ref_by_text(snapshot, "Gunakan akun lain")
                if another_ref:
                    log(f"  HTTP click ref={another_ref}...")
                    client.click(another_ref)  # HTTP click, ignore timeout
                    client.wait(4)
                    snapshot, url = client.get_full_snapshot()
                    client.wait(2)
                else:
                    # Method 2: JS evaluate sebagai fallback
                    log(f"  Ref tidak ditemukan, coba JS click...")
                    client.evaluate("""
                    (() => {
                        const allElements = document.querySelectorAll('div[role="link"], a, button, li, span');
                        for (const el of allElements) {
                            const text = el.textContent.trim().toLowerCase();
                            if (text === 'use another account' || text === 'gunakan akun lain' ||
                                text.includes('use another account') || text.includes('gunakan akun lain')) {
                                el.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, cancelable: true, pointerId: 1, pointerType: 'mouse'}));
                                el.dispatchEvent(new PointerEvent('pointerup', {bubbles: true, cancelable: true, pointerId: 1, pointerType: 'mouse'}));
                                el.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true}));
                                el.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true}));
                                el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                                el.click();
                                return 'clicked: ' + text.substring(0, 30);
                            }
                        }
                        return 'not found';
                    })()
                    """)
                    client.wait(4)
                    snapshot, url = client.get_full_snapshot()
                    client.wait(2)

                # Cek apakah halaman login sudah muncul (email input ada)
                if "email or phone" in snapshot.lower() or "email atau nomor" in snapshot.lower():
                    log(f"  Halaman login muncul! (attempt {click_attempt+1})")
                    break
                # Masih di halaman choose account, retry
                log(f"  Masih di halaman choose account, retry...")
            else:
                # Fallback: navigate langsung ke login URL
                log("  Gagal klik 'Use another account', navigate ke login URL langsung")
                client.navigate("https://accounts.google.com/signin")
                client.wait(4)
                snapshot, url = client.get_full_snapshot()
                client.wait(3)
        else:
            # Cek apakah sudah login (halaman myaccount/google account)
            account_signals = ["myaccount.google.com", "akun google", "info pribadi",
                              "keamanan & login", "sandi google", "data & privasi",
                              "beranda", "favorit"]
            if any(sig in snapshot.lower() for sig in account_signals) or "myaccount" in url.lower():
                log("  Akun sebelumnya masih login - navigate ke accountchooser")
                client.navigate("https://accounts.google.com/accountchooser?continue=https://accounts.google.com/signin")
                client.wait(4)
                snapshot, url = client.get_full_snapshot()
                client.wait(3)
                if any(sig in snapshot.lower() for sig in choose_account_signals):
                    log("  Halaman 'Choose an account' muncul - retry klik")
                    max_click_retries = 5
                    for click_attempt in range(max_click_retries):
                        log(f"  Klik 'Use another account' (attempt {click_attempt+1}/{max_click_retries})")
                        another_ref = client.find_ref_by_text(snapshot, "Use another account")
                        if not another_ref:
                            another_ref = client.find_ref_by_text(snapshot, "Gunakan akun lain")
                        if another_ref:
                            log(f"  HTTP click ref={another_ref}...")
                            client.click(another_ref)
                            client.wait(4)
                            snapshot, url = client.get_full_snapshot()
                            client.wait(2)
                        else:
                            client.evaluate("""
                            (() => {
                                const allElements = document.querySelectorAll('div[role="link"], a, button, li, span');
                                for (const el of allElements) {
                                    const text = el.textContent.trim().toLowerCase();
                                    if (text === 'use another account' || text === 'gunakan akun lain' ||
                                        text.includes('use another account') || text.includes('gunakan akun lain')) {
                                        el.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, cancelable: true, pointerId: 1, pointerType: 'mouse'}));
                                        el.dispatchEvent(new PointerEvent('pointerup', {bubbles: true, cancelable: true, pointerId: 1, pointerType: 'mouse'}));
                                        el.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true}));
                                        el.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true}));
                                        el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                                        el.click();
                                        return 'clicked';
                                    }
                                }
                                return 'not found';
                            })()
                            """)
                            client.wait(4)
                            snapshot, url = client.get_full_snapshot()
                            client.wait(2)
                        if "email or phone" in snapshot.lower() or "email atau nomor" in snapshot.lower():
                            log(f"  Halaman login muncul! (attempt {click_attempt+1})")
                            break
                        log(f"  Masih di halaman choose account, retry...")
                    else:
                        log("  Gagal klik, navigate ke login URL langsung")
                        client.navigate("https://accounts.google.com/signin")
                        client.wait(4)
                        snapshot, url = client.get_full_snapshot()
                        client.wait(3)

        # ── STEP 3: Ketik email via JS ──
        log(f"  Ketik email via JS: {email}")
        result_js = client.type_text_js('input[name="identifier"], #identifierId', email)
        log(f"  Hasil ketik: {result_js}")
        client.wait(3)  # Jeda 3 detik setelah ketik

        # ── STEP 4: Klik Next (email) via JS ──
        log(f"  Klik Next (email) via JS...")
        result_js = client.click_js('#identifierNext')
        log(f"  Hasil klik: {result_js}")
        client.wait(3)  # Jeda 3 detik setelah klik

        # ── STEP 5: Tunggu halaman password/verifikasi muncul ──
        # Beri jeda 5 detik dulu — Google butuh waktu load halaman password/verifikasi
        log(f"  Tunggu 5 detik untuk halaman password...")
        client.wait(5)

        log(f"  Cek halaman password...")
        snapshot = ""
        url = ""
        max_retries = 15
        found_password_page = False
        found_verify_page = False
        found_error = False

        for retry in range(max_retries):
            snapshot, url = client.get_full_snapshot()
            snapshot_lower = snapshot.lower()

            if "enter your password" in snapshot_lower or "masukkan sandi" in snapshot_lower:
                found_password_page = True
                log(f"  Halaman password ditemukan! (retry {retry+1})")
                break
            verify_signals = ["verify it\u2019s you", "verify it's you", "verifikasi", "open the gmail app",
                              "google sent a notification", "choose a way to verify", "confirm that it's you", "challenge",
                              "enter a phone number"]
            if any(sig in snapshot_lower for sig in verify_signals) or "/challenge" in url.lower():
                found_verify_page = True
                log(f"  Halaman verifikasi ditemukan! (retry {retry+1})")
                break
            email_errors = ["couldn't find your google account", "couldn\u2019t find your google account",
                            "tidak ditemukan", "couldn't find", "enter a valid email"]
            if any(err in snapshot_lower for err in email_errors):
                found_error = True
                log(f"  Email tidak ditemukan! (retry {retry+1})")
                break
            wrong_pwd = ["wrong password", "incorrect password", "your password is incorrect"]
            if any(sig in snapshot_lower for sig in wrong_pwd):
                found_password_page = True
                log(f"  Password salah terdeteksi! (retry {retry+1})")
                break
            # Deteksi "Something went wrong" atau error Google
            something_wrong_signals = [
                "something went wrong", "something wrong",
                "terjadi kesalahan", "coba lagi nanti",
                "error", "unusual activity", "couldn't complete",
            ]
            if any(sig in snapshot_lower for sig in something_wrong_signals):
                found_error = True
                log(f"  Something wrong terdeteksi! (retry {retry+1})")
                break
            client.wait(2)

        snapshot_lower = snapshot.lower()

        if found_error:
            result["status"] = "gagal"
            result["keterangan"] = "Email tidak ditemukan di Google"
            return result
        if found_verify_page:
            result["status"] = "verifikasi"
            result["keterangan"] = "Akun sudah aman, password sudah di ganti (minta verifikasi)"
            return result
        if not found_password_page:
            debug_snapshot = snapshot[:300].replace('\n', ' | ')
            result["status"] = "unknown"
            result["keterangan"] = f"Tidak menemukan kolom password setelah 30 detik. URL: {url[:60]} | Snapshot: {debug_snapshot[:100]}"
            return result

        # ── STEP 6: Ketik password via JS ──
        log(f"  Ketik password via JS...")
        result_js = client.type_text_js('input[name="Passwd"], input[type="password"]', password)
        log(f"  Hasil ketik pwd: {result_js}")
        client.wait(3)  # Jeda 3 detik setelah ketik password

        # ── STEP 7: Klik Next (password) via JS ──
        log(f"  Klik Next (password) via JS...")
        result_js = client.click_js('#passwordNext')
        log(f"  Hasil klik pwd: {result_js}")

        # ── STEP 8: Tunggu hasil login ──
        # Beri jeda 5 detik dulu sebelum mulai cek — Google butuh waktu load halaman verifikasi
        log(f"  Tunggu 5 detik untuk halaman hasil...")
        client.wait(5)

        log(f"  Cek hasil login...")
        snapshot = ""
        url = ""
        max_retries2 = 15
        final_status = "unknown"
        final_keterangan = "Status tidak diketahui"

        for retry in range(max_retries2):
            snapshot, url = client.get_full_snapshot()
            snapshot_lower = snapshot.lower()
            url_lower = url.lower()

            # Cek 1: Verifikasi diperlukan (berbagai jenis)
            # Google bisa minta: prompt HP, SMS/OTP, kode verifikasi, dll
            verify_signals = [
                "verify it\u2019s you", "verify it's you", "verifikasi",
                "open the gmail app", "google sent a notification",
                "get a verification code", "use your phone",
                "2-step", "two-step", "choose a way to verify",
                "confirm that it's you", "challenge",
                "enter a phone number", "get a text message",
                "verification code", "enter the code",
            ]
            if any(sig in snapshot_lower for sig in verify_signals) or "/challenge" in url_lower:
                final_status = "verifikasi"
                final_keterangan = "Akun sudah aman, password sudah di ganti (minta verifikasi)"
                log(f"  Hasil: verifikasi (retry {retry+1})")
                break

            # Cek 2: Password salah
            wrong_pwd_signals = [
                "wrong password", "incorrect password",
                "your password is incorrect", "password salah",
                "sandi salah",
            ]
            if any(sig in snapshot_lower for sig in wrong_pwd_signals):
                final_status = "gagal"
                final_keterangan = "Password salah - sudah diganti dari default"
                log(f"  Hasil: gagal - password salah (retry {retry+1})")
                break

            # Cek 3: Something went wrong / error Google
            something_wrong_signals = [
                "something went wrong", "something wrong",
                "terjadi kesalahan", "coba lagi nanti",
                "unusual activity", "couldn't complete",
            ]
            if any(sig in snapshot_lower for sig in something_wrong_signals):
                final_status = "error"
                final_keterangan = "Google menolak login (something wrong) - coba lagi nanti"
                log(f"  Hasil: error - something wrong (retry {retry+1})")
                break

            # Cek 4: Login berhasil
            success_signals = [
                "favorit", "beranda", "info pribadi", "keamanan & login",
                "sandi google", "data & privasi", "akun google",
                "welcome to your", "mentransfer konten",
            ]
            is_success = any(sig in snapshot_lower for sig in success_signals)
            is_success_url = "myaccount" in url_lower
            if is_success or is_success_url:
                understand_ref = client.find_ref_by_text(snapshot, "I understand")
                if not understand_ref:
                    understand_ref = client.find_ref_by_text(snapshot, "Saya mengerti")
                if understand_ref:
                    client.click_js('button:has-text("I understand")')
                    log("  Klik 'I understand' via JS")
                    client.wait(3)
                final_status = "berhasil"
                final_keterangan = "Login berhasil, password belum di ubah"
                log(f"  Hasil: berhasil (retry {retry+1})")
                break

            # Belum ketemu hasil, tunggu 2 detik
            client.wait(2)

        result["status"] = final_status
        result["keterangan"] = final_keterangan
        if final_status == "unknown":
            debug_snapshot = snapshot[:300].replace('\n', ' | ')
            result["keterangan"] = f"Status tidak diketahui setelah 30 detik. URL: {url[:60]} | Snapshot: {debug_snapshot[:100]}"

    except requests.exceptions.ConnectionError as e:
        result["status"] = "error"
        result["keterangan"] = f"Tidak bisa connect ke server Camofox: {str(e)[:100]}"
    except requests.exceptions.Timeout:
        result["status"] = "error"
        result["keterangan"] = "Timeout - server Camofox tidak merespons dalam 30 detik"
    except Exception as e:
        result["status"] = "error"
        result["keterangan"] = f"Error: {str(e)[:150]}"
        import traceback
        traceback.print_exc()

    return result


# ============================================================
# FUNGSI LOGOUT
# ============================================================
def do_logout(client):
    """Logout dari Google dan navigasi ke halaman login berikutnya"""
    try:
        # Navigasi ke logout URL
        client.navigate(LOGOUT_URL)
        client.wait(3)
        # Lalu navigasi ke halaman login untuk akun berikutnya
        client.navigate(LOGIN_URL)
        client.wait(3)
    except:
        pass


# ============================================================
# FUNGSI BACA DATA MAHASISWA
# ============================================================
def read_students(csv_path):
    """
    Baca data dari file teks/CSV.
    Format: 1 kolom, tiap baris = "NIM,Nama"
    Contoh: 2305541113,Gede Davananda Wicaksana
    """
    students = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.lower().startswith('nim,'):
                continue
            if ',' in line:
                nim, nama = line.split(',', 1)
            elif ';' in line:
                nim, nama = line.split(';', 1)
            else:
                continue
            nim = nim.strip()
            nama = nama.strip()
            if not nim or not nama:
                continue
            email = generate_email(nama, nim)
            students.append({
                'nim': nim, 'nama': nama, 'email': email,
            })
    return students


# ============================================================
# FUNGSI LAPORAN
# ============================================================
def generate_report(results, output_path, append=False):
    """Generate laporan CSV dan ringkasan console.
    Jika append=True, tambahkan ke file yang sudah ada (tanpa hapus data lama).
    """
    fieldnames = ['nim', 'nama', 'email', 'status']

    # ── Tentukan mode file ──
    file_exists = os.path.exists(output_path) and os.path.getsize(output_path) > 0
    mode = 'a' if (append and file_exists) else 'w'

    with open(output_path, mode, newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        # Header hanya kalau file baru atau tidak append
        if mode == 'w' or not file_exists:
            writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, '') for k in fieldnames})

    # ── Ringkasan Console ──
    print("\n" + "=" * 70)
    print("                    RINGKASAN HASIL PENGECEKAN")
    print("=" * 70)

    berhasil = [r for r in results if r['status'] == 'berhasil']
    verifikasi = [r for r in results if r['status'] == 'verifikasi']
    gagal = [r for r in results if r['status'] == 'gagal']
    error = [r for r in results if r['status'] == 'error']
    unknown = [r for r in results if r['status'] == 'unknown']

    print(f"  Total akun dicek  : {len(results)}")
    print(f"  [OK]   Berhasil    : {len(berhasil)}  -> password BELUM di ubah")
    print(f"  [!]    Verifikasi  : {len(verifikasi)}  -> password SUDAH di ganti (aman)")
    print(f"  [X]    Gagal       : {len(gagal)}  -> email salah / password diganti")
    print(f"  [E]    Error        : {len(error)}")
    print(f"  [?]    Unknown      : {len(unknown)}")
    print("=" * 70)
    print(f"  Mode           : {'APPEND (tambah ke data lama)' if append and file_exists else 'OVERWRITE (ganti data lama)'}")
    print(f"  Laporan CSV    : {os.path.abspath(output_path)}")
    print("=" * 70)

    # ── Detail per akun (4 kolom: NIM | Nama | Email | Status) ──
    print("\n" + "-" * 95)
    print(f"{'No':>3} | {'NIM':<15} | {'Nama':<30} | {'Email':<45} | {'Status':<12}")
    print("-" * 95)
    for i, r in enumerate(results, 1):
        print(f"{i:>3} | {r['nim']:<15} | {r['nama'][:30]:<30} | {r['email'][:45]:<45} | {r['status']:<12}")
    print("-" * 95)


def generate_html_report(results, html_path):
    """Generate laporan HTML"""
    berhasil = [r for r in results if r['status'] == 'berhasil']
    verifikasi = [r for r in results if r['status'] == 'verifikasi']
    gagal = [r for r in results if r['status'] == 'gagal']
    lainnya = [r for r in results if r['status'] not in ('berhasil', 'verifikasi', 'gagal')]

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
            <td><code>{r['nim']}</code></td>
            <td>{r['nama']}</td>
            <td><code style="font-size:12px">{r['email']}</code></td>
            <td style="text-align:center"><span style="background:{color};color:white;padding:2px 8px;border-radius:4px;font-weight:bold;font-size:11px">{icon}</span> {r['status']}</td>
            <td>{r['keterangan']}</td>
            <td style="font-size:12px;color:#666">{r.get('timestamp', '')}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Laporan Cek Akun Google Mahasiswa</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 20px; background: #f8fafc; }}
        h1 {{ color: #1e40af; border-bottom: 3px solid #1e40af; padding-bottom: 10px; }}
        .summary {{ display: flex; gap: 15px; margin: 20px 0; flex-wrap: wrap; }}
        .card {{ padding: 15px 25px; border-radius: 8px; color: white; font-weight: bold; min-width: 120px; text-align: center; }}
        .card.berhasil {{ background: #22c55e; }}
        .card.verifikasi {{ background: #f59e0b; }}
        .card.gagal {{ background: #ef4444; }}
        .card.lainnya {{ background: #6b7280; }}
        .card .num {{ font-size: 28px; }}
        .card .label {{ font-size: 12px; opacity: 0.9; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        th {{ background: #1e40af; color: white; padding: 12px 8px; text-align: left; font-size: 13px; }}
        td {{ padding: 10px 8px; border-bottom: 1px solid #e5e7eb; font-size: 13px; }}
        tr:hover {{ background: #f1f5f9; }}
        .footer {{ margin-top: 20px; text-align: center; color: #94a3b8; font-size: 12px; }}
    </style>
</head>
<body>
    <h1>Laporan Cek Akun Google Mahasiswa</h1>
    <p>Dibuat: {datetime.now().strftime('%d %B %Y, %H:%M:%S')}</p>
    <div class="summary">
        <div class="card berhasil"><div class="num">{len(berhasil)}</div><div class="label">BERHASIL (belum ganti)</div></div>
        <div class="card verifikasi"><div class="num">{len(verifikasi)}</div><div class="label">VERIFIKASI (sudah aman)</div></div>
        <div class="card gagal"><div class="num">{len(gagal)}</div><div class="label">GAGAL</div></div>
        <div class="card lainnya"><div class="num">{len(lainnya)}</div><div class="label">LAINNYA</div></div>
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
        Password default: {DEFAULT_PASSWORD} | Domain: {EMAIL_DOMAIN}<br>
        Generated by Google Account Checker (Camoufox HTTP API)
    </div>
</body>
</html>"""
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)


# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="Cek login akun Google mahasiswa via Camofox HTTP API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh penggunaan:
  python check_google_accounts.py
  python check_google_accounts.py --csv students_baru.csv --yes
  python check_google_accounts.py --delay 5 --yes

PRASYARAT:
  1. Server Camofox harus jalan: cd camofox-browser && npm start
  2. File CSV dengan format: NIM,Nama (1 kolom, dipisah koma)
        """,
    )
    parser.add_argument('--csv', default='students.csv',
                        help='Path file CSV data mahasiswa (default: students.csv)')
    parser.add_argument('--output', default='hasil_cek.csv',
                        help='Path file output laporan CSV (default: hasil_cek.csv)')
    parser.add_argument('--html', default=None,
                        help='Path file output laporan HTML (opsional)')
    parser.add_argument('--password', default=DEFAULT_PASSWORD,
                        help=f'Password default (default: {DEFAULT_PASSWORD})')
    parser.add_argument('--delay', type=int, default=DELAY_BETWEEN_ACCOUNTS,
                        help=f'Jeda antar akun dalam detik (default: {DELAY_BETWEEN_ACCOUNTS})')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Skip konfirmasi, langsung jalan')
    parser.add_argument('--server-url', default=DEFAULT_SERVER_URL,
                        help=f'URL server Camofox (default: {DEFAULT_SERVER_URL})')
    parser.add_argument('--fresh', action='store_true',
                        help='Mulai dengan session kosong (hapus cookies sebelum mulai)')
    parser.add_argument('--append', action='store_true',
                        help='Tambah hasil ke file output yang sudah ada (tanpa hapus data lama)')
    parser.add_argument('--pause', action='store_true',
                        help='Tunggu Enter setelah tiap akun (untuk cek manual sebelum lanjut)')
    args = parser.parse_args()

    # ── Validasi file CSV ──
    if not os.path.exists(args.csv):
        print(f"File tidak ditemukan: {args.csv}")
        print("\nBuat file dengan format 1 kolom, tiap baris = NIM,Nama:")
        print("\nContoh isi file:")
        print("  2305541113,Gede Davananda Wicaksana")
        print("  2305541114,Alghifari Kurnia Assyauqillah")
        print("\nBisa pakai koma (,) atau titik koma (;)")
        return

    # ── Baca data mahasiswa ──
    students = read_students(args.csv)
    if not students:
        print("Tidak ada data mahasiswa di file CSV. Pastikan format kolom benar.")
        return

    print("=" * 70)
    print("     GOOGLE ACCOUNT CHECKER - Uji Login Akun Google Mahasiswa")
    print("          Powered by Camoufox HTTP API")
    print("=" * 70)
    print(f"  File CSV        : {os.path.abspath(args.csv)}")
    print(f"  File output     : {os.path.abspath(args.output)}")
    print(f"  Password default: {args.password}")
    print(f"  Total akun      : {len(students)}")
    print(f"  Delay antar akun: {args.delay} detik")
    print(f"  Server Camofox  : {args.server_url}")
    print(f"  Mode output     : {'APPEND (tambah data)' if args.append else 'OVERWRITE (ganti data)'}")
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
        print("\nPastikan muncul: \"server started\" dan \"browserConnected\": true")
        return
    print("  ✅ Server Camofox berjalan - browser connected!")

    # ── Mode fresh: hapus session lama sebelum mulai ──
    if args.fresh:
        print("\nMode --fresh: membersihkan session lama...")
        # Hapus session "checker" lama (userId tetap "checker" di mode fresh)
        old_client = CamofoxClient(args.server_url, user_id="checker")
        try:
            old_client.delete_session()
            log("Session lama 'checker' dihapus")
        except:
            log("Tidak ada session 'checker' lama")
        # Hapus file persistence lama
        try:
            old_client.delete_persisted_profile()
            log("Persistence profile lama dihapus")
        except:
            pass
        # Tunggu sebentar
        client.wait(1)
    else:
        # Selalu hapus session lama dengan user_id yang sama
        try:
            client.delete_session()
            log("Session lama dihapus - mulai bersih")
        except:
            log("Tidak ada session lama untuk dihapus")
        client.wait(1)

    # ── Preview daftar akun ──
    print("\nDaftar akun yang akan dicek:")
    print("-" * 70)
    for i, s in enumerate(students, 1):
        print(f"  {i:>3}. {s['nim']} | {s['nama'][:35]:<35} | {s['email']}")
    print("-" * 70)

    # ── Konfirmasi ──
    if not args.yes:
        print(f"\nAkan mengecek {len(students)} akun. Tekan Enter untuk mulai (Ctrl+C untuk batal)...")
        try:
            input()
        except KeyboardInterrupt:
            print("\nDibatalkan.")
            return

    results = []

    # ── Loop cek tiap akun ──
    for i, student in enumerate(students, 1):
        print(f"\n[{i}/{len(students)}] Mengecek: {student['nim']} - {student['nama'][:35]}")
        print(f"  Email: {student['email']}")

        # Mode fresh: tutup tab lama + hapus cookies sebelum tiap akun
        if args.fresh and i > 1:
            try:
                client.close_tab()
                client.clear_cookies()
                client.wait(1)
            except:
                pass

        result = check_account(client, student['email'], args.password)
        result['nim'] = student['nim']
        result['nama'] = student['nama']

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

        # ── Pause: tunggu Enter kalau berhasil login (untuk cek manual) ──
        if args.pause and result['status'] == 'berhasil':
            print(f"\n  ⏸️  Akun BERHASIL login. Tekan Enter untuk lanjut ke akun berikutnya...")
            try:
                input()
            except KeyboardInterrupt:
                print("\n  Dihentikan pengguna.")
                break

        # Delay
        if i < len(students):
            client.wait(args.delay)

    # ── Cleanup ──
    try:
        client.close_tab()
        client.delete_session()
    except:
        pass

    # ── Generate laporan final ──
    generate_report(results, args.output, append=args.append)
    if args.html:
        generate_html_report(results, args.html)
        print(f"\nLaporan HTML tersimpan: {os.path.abspath(args.html)}")

    print(f"\nSelesai! {len(results)} akun selesai dicek.")
    print(f"Laporan CSV: {os.path.abspath(args.output)}")


if __name__ == '__main__':
    main()
