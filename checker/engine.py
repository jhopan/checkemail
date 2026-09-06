"""Engine cek login Google via Camofox.

Logic utama: navigate ke login, handle "Choose an account",
ketik email/password, detect hasil (berhasil/verifikasi/gagal/error).
"""

import time
import traceback
from datetime import datetime

import requests

from .client import CamofoxClient, log
from .config import (
    LOGIN_URL, LOGOUT_URL,
    CHOOSE_ACCOUNT_SIGNALS, MYACCOUNT_SIGNALS,
    VERIFY_SIGNALS, EMAIL_ERROR_SIGNALS,
    WRONG_PWD_SIGNALS, SOMETHING_WRONG_SIGNALS, SUCCESS_SIGNALS,
)

ACCOUNTCHOOSER_URL = (
    "https://accounts.google.com/accountchooser"
    "?continue=https://accounts.google.com/signin"
)


def _any_signal(text_lower, signals):
    return any(sig in text_lower for sig in signals)


def _handle_choose_account(client, snapshot, url):
    """Handle halaman 'Choose an account'. Return (snapshot, url) baru."""
    log("  Halaman 'Choose an account' terdeteksi")

    # Retry klik 'Use another account' sampai 5x
    for attempt in range(5):
        log(f"  Klik 'Use another account' (attempt {attempt+1}/5)")

        # Method 1: HTTP click via ref (Playwright native = trusted click)
        ref = client.find_ref_by_text(snapshot, "Use another account") \
            or client.find_ref_by_text(snapshot, "Gunakan akun lain")
        if ref:
            log(f"  HTTP click ref={ref}...")
            client.click(ref)
            client.wait(4)
        else:
            # Method 2: JS evaluate fallback
            log("  Ref tidak ditemukan, JS click...")
            client.evaluate("""
            (() => {
                const els = document.querySelectorAll(
                    'div[role="link"], a, button, li, span');
                for (const el of els) {
                    const t = el.textContent.trim().toLowerCase();
                    if (t === 'use another account' || t === 'gunakan akun lain' ||
                        t.includes('use another account') || t.includes('gunakan akun lain')) {
                        el.dispatchEvent(new PointerEvent('pointerdown',
                            {bubbles: true, cancelable: true, pointerId: 1,
                             pointerType: 'mouse'}));
                        el.dispatchEvent(new PointerEvent('pointerup',
                            {bubbles: true, cancelable: true, pointerId: 1,
                             pointerType: 'mouse'}));
                        el.dispatchEvent(new MouseEvent('mousedown',
                            {bubbles: true, cancelable: true}));
                        el.dispatchEvent(new MouseEvent('mouseup',
                            {bubbles: true, cancelable: true}));
                        el.dispatchEvent(new MouseEvent('click',
                            {bubbles: true, cancelable: true}));
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

        # Berhasil kalau email input muncul
        if "email or phone" in snapshot.lower() or "email atau nomor" in snapshot.lower():
            log(f"  Halaman login muncul! (attempt {attempt+1})")
            return snapshot, url
        log("  Masih di halaman choose account, retry...")

    # Fallback: navigate langsung ke login URL
    log("  Gagal klik, navigate ke login URL langsung")
    client.navigate(LOGIN_URL)
    client.wait(4)
    return client.get_full_snapshot()


def _handle_logged_in(client, snapshot, url):
    """Handle kondisi akun sebelumnya masih login. Return (snapshot, url)."""
    log("  Akun sebelumnya masih login - navigate ke accountchooser")
    client.navigate(ACCOUNTCHOOSER_URL)
    client.wait(4)
    snapshot, url = client.get_full_snapshot()
    client.wait(3)
    if _any_signal(snapshot.lower(), CHOOSE_ACCOUNT_SIGNALS):
        snapshot, url = _handle_choose_account(client, snapshot, url)
    return snapshot, url


def check_account(client, email, password):
    """Cek login satu akun Google. Return dict hasil."""
    result = {
        "email": email,
        "status": "unknown",
        "keterangan": "",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        # ── STEP 1: Pastikan tab aktif ──
        if not client.ensure_tab(LOGIN_URL):
            result["status"] = "error"
            result["keterangan"] = "Tidak bisa buka tab di server Camofox"
            return result
        client.wait(4)

        # ── STEP 2: Snapshot awal + handle choose account / myaccount ──
        log("  Ambil snapshot...")
        snapshot, url = client.get_full_snapshot()
        client.wait(3)

        snap_lower = snapshot.lower()
        if _any_signal(snap_lower, CHOOSE_ACCOUNT_SIGNALS):
            snapshot, url = _handle_choose_account(client, snapshot, url)
        elif _any_signal(snap_lower, MYACCOUNT_SIGNALS) or "myaccount" in url.lower():
            snapshot, url = _handle_logged_in(client, snapshot, url)

        # ── STEP 3: Ketik email ──
        log(f"  Ketik email via JS: {email}")
        client.type_text_js('input[name="identifier"], #identifierId', email)
        client.wait(3)

        # ── STEP 4: Klik Next (email) ──
        log("  Klik Next (email) via JS...")
        client.click_js('#identifierNext')
        client.wait(3)

        # ── STEP 5: Tunggu halaman password / verifikasi ──
        log("  Tunggu 5 detik untuk halaman password...")
        client.wait(5)

        found_pwd = found_verify = found_error = False
        for retry in range(15):
            snapshot, url = client.get_full_snapshot()
            sl = snapshot.lower()

            if "enter your password" in sl or "masukkan sandi" in sl:
                found_pwd = True
                log(f"  Halaman password ditemukan! (retry {retry+1})")
                break
            if _any_signal(sl, VERIFY_SIGNALS) or "/challenge" in url.lower():
                found_verify = True
                log(f"  Halaman verifikasi ditemukan! (retry {retry+1})")
                break
            if _any_signal(sl, EMAIL_ERROR_SIGNALS):
                found_error = True
                log(f"  Email tidak ditemukan! (retry {retry+1})")
                break
            if _any_signal(sl, WRONG_PWD_SIGNALS):
                found_pwd = True
                log(f"  Password salah terdeteksi! (retry {retry+1})")
                break
            if _any_signal(sl, SOMETHING_WRONG_SIGNALS):
                found_error = True
                log(f"  Something wrong terdeteksi! (retry {retry+1})")
                break
            client.wait(2)

        if found_error:
            result["status"] = "gagal"
            result["keterangan"] = "Email tidak ditemukan di Google"
            return result
        if found_verify:
            result["status"] = "verifikasi"
            result["keterangan"] = (
                "Akun sudah aman, password sudah di ganti (minta verifikasi)")
            return result
        if not found_pwd:
            debug = snapshot[:300].replace('\n', ' | ')
            result["keterangan"] = (
                f"Tidak menemukan kolom password. URL: {url[:60]} | {debug[:100]}")
            return result

        # ── STEP 6: Ketik password ──
        log("  Ketik password via JS...")
        client.type_text_js(
            'input[name="Passwd"], input[type="password"]', password)
        client.wait(3)

        # ── STEP 7: Klik Next (password) ──
        log("  Klik Next (password) via JS...")
        client.click_js('#passwordNext')

        # ── STEP 8: Tunggu hasil login ──
        log("  Tunggu 5 detik untuk halaman hasil...")
        client.wait(5)

        final_status, final_ket = "unknown", "Status tidak diketahui"
        for retry in range(15):
            snapshot, url = client.get_full_snapshot()
            sl = snapshot.lower()
            ul = url.lower()

            if _any_signal(sl, VERIFY_SIGNALS) or "/challenge" in ul:
                final_status = "verifikasi"
                final_ket = (
                    "Akun sudah aman, password sudah di ganti (minta verifikasi)")
                log(f"  Hasil: verifikasi (retry {retry+1})")
                break
            if _any_signal(sl, WRONG_PWD_SIGNALS):
                final_status = "gagal"
                final_ket = "Password salah - sudah diganti dari default"
                log(f"  Hasil: gagal - password salah (retry {retry+1})")
                break
            if _any_signal(sl, SOMETHING_WRONG_SIGNALS):
                final_status = "error"
                final_ket = "Google menolak login (something wrong) - coba lagi nanti"
                log(f"  Hasil: error - something wrong (retry {retry+1})")
                break
            if _any_signal(sl, SUCCESS_SIGNALS) or "myaccount" in ul:
                # Klik "I understand" kalau muncul (akun baru)
                ref = client.find_ref_by_text(snapshot, "I understand") \
                    or client.find_ref_by_text(snapshot, "Saya mengerti")
                if ref:
                    client.click_js('button:has-text("I understand")')
                    log("  Klik 'I understand' via JS")
                    client.wait(3)
                final_status = "berhasil"
                final_ket = "Login berhasil, password belum di ubah"
                log(f"  Hasil: berhasil (retry {retry+1})")
                break
            client.wait(2)

        result["status"] = final_status
        result["keterangan"] = final_ket
        if final_status == "unknown":
            debug = snapshot[:300].replace('\n', ' | ')
            result["keterangan"] = (
                f"Status tidak diketahui. URL: {url[:60]} | {debug[:100]}")

    except requests.exceptions.ConnectionError as e:
        result["status"] = "error"
        result["keterangan"] = f"Tidak bisa connect ke server Camofox: {str(e)[:100]}"
    except requests.exceptions.Timeout:
        result["status"] = "error"
        result["keterangan"] = "Timeout - server Camofox tidak merespons"
    except Exception as e:
        result["status"] = "error"
        result["keterangan"] = f"Error: {str(e)[:150]}"
        traceback.print_exc()

    return result


def do_logout(client):
    """Logout lalu navigasi kembali ke halaman login."""
    try:
        client.navigate(LOGOUT_URL)
        client.wait(3)
        client.navigate(LOGIN_URL)
        client.wait(3)
    except Exception:
        pass


def beep_success():
    """Bunyi beep (Windows). No-op di OS lain."""
    try:
        import winsound
        winsound.Beep(1000, 500)
    except Exception:
        pass
