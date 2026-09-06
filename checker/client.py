"""Camofox HTTP API client.

Client untuk berinteraksi dengan server camofox-browser (port 9377).
Menangani: create tab, snapshot, type, click (HTTP & JS), navigate, session.
"""

import re
import time
import requests

from .config import REQUEST_TIMEOUT, LOGIN_URL


def log(msg, level="INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}")


class CamofoxClient:
    """Client untuk server Camofox via HTTP API."""

    def __init__(self, server_url=None, user_id=None):
        self.server_url = (server_url or "").rstrip('/')
        # Fix: Windows resolve localhost ke IPv6 (::1) yang timeout
        if 'localhost' in self.server_url:
            self.server_url = self.server_url.replace('localhost', '127.0.0.1')
        # User ID unik per run = session selalu fresh
        self.user_id = user_id or f"checker_{int(time.time())}"
        self.session_key = f"session_{int(time.time())}"
        self.tab_id = None

    # ── HTTP helpers ──────────────────────────────────────────

    def _get(self, path, **kwargs):
        return requests.get(
            f"{self.server_url}{path}", timeout=REQUEST_TIMEOUT, **kwargs
        ).json()

    def _post(self, path, data=None, timeout=REQUEST_TIMEOUT):
        return requests.post(
            f"{self.server_url}{path}", json=data, timeout=timeout
        ).json()

    def _delete(self, path):
        return requests.delete(
            f"{self.server_url}{path}", timeout=REQUEST_TIMEOUT
        ).json()

    # ── Server / session ──────────────────────────────────────

    def check_server(self):
        """Cek server jalan. Coba beberapa varian URL (Windows IPv6 issue)."""
        for url in [
            "http://127.0.0.1:9377/health",
            "http://localhost:9377/health",
            f"{self.server_url}/health",
        ]:
            try:
                data = requests.get(url, timeout=10).json()
                if data.get("ok"):
                    return True
            except Exception:
                continue
        return False

    def delete_session(self):
        self._delete(f"/sessions/{self.user_id}")

    def delete_persisted_profile(self):
        try:
            self._delete(f"/sessions/{self.user_id}/persistence")
        except Exception:
            pass

    def clear_cookies(self):
        try:
            self._post(
                f"/sessions/{self.user_id}/cookies",
                {"userId": self.user_id, "sessionKey": self.session_key,
                 "cookies": []},
            )
        except Exception:
            pass

    # ── Tab management ────────────────────────────────────────

    def create_tab(self, url):
        """Buka tab baru. Retry 3x, auto-renew session kalau expired."""
        data = {
            "userId": self.user_id,
            "sessionKey": self.session_key,
            "url": url,
        }
        for attempt in range(3):
            try:
                result = self._post("/tabs", data, timeout=90)
                if "tabId" in result:
                    self.tab_id = result["tabId"]
                    return result
                err = result.get("error", "")
                if result.get("code") == "session_expired" or "expired" in err:
                    log(f"  Session expired, renew... (attempt {attempt+1})")
                    try:
                        self._delete(f"/sessions/{self.user_id}")
                    except Exception:
                        pass
                    self.session_key = f"session_{int(time.time())}_{attempt}"
                    data["sessionKey"] = self.session_key
                    time.sleep(2)
                    continue
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
        """Pastikan tab aktif. Kalau mati/tidak ada, buat baru."""
        if self.tab_id:
            try:
                self._get(f"/tabs/{self.tab_id}/snapshot",
                          params={"userId": self.user_id})
                return True
            except Exception:
                self.tab_id = None
        log("  Tab tidak ditemukan, buat tab baru...")
        result = self.create_tab(url)
        if "tabId" in result:
            time.sleep(4)
            return True
        return False

    def close_tab(self):
        if self.tab_id:
            try:
                self._delete(f"/tabs/{self.tab_id}?userId={self.user_id}")
            except Exception:
                pass
            self.tab_id = None

    # ── Page interaction ──────────────────────────────────────

    def get_snapshot(self):
        return self._get(
            f"/tabs/{self.tab_id}/snapshot", params={"userId": self.user_id}
        )

    def get_full_snapshot(self):
        data = self.get_snapshot()
        return data.get("snapshot", ""), data.get("url", "")

    def navigate(self, url):
        return self._post(
            f"/tabs/{self.tab_id}/navigate",
            {"userId": self.user_id, "url": url},
        )

    def type_text(self, ref, text):
        return self._post(
            f"/tabs/{self.tab_id}/type",
            {"userId": self.user_id, "ref": ref, "text": text},
        )

    def click(self, ref):
        """HTTP click (Playwright native = trusted click).
        Ignore timeout - klik sering berhasil walau response timeout."""
        try:
            return self._post(
                f"/tabs/{self.tab_id}/click",
                {"userId": self.user_id, "ref": ref},
            )
        except requests.exceptions.Timeout:
            return {"ok": True, "note": "click sent (response timed out)"}
        except Exception as e:
            return {"error": str(e)}

    def evaluate(self, js_code):
        """Jalankan JavaScript di halaman."""
        try:
            return self._post(
                f"/tabs/{self.tab_id}/evaluate",
                {"userId": self.user_id, "expression": js_code},
            )
        except Exception:
            return {"error": "evaluate failed"}

    def type_text_js(self, selector, text):
        """Ketik via JS: native setter + human typing (50-150ms per karakter)."""
        chars_js = ",".join([repr(c) for c in text])
        js = f"""
        (async () => {{
            const el = document.querySelector('{selector}');
            if (!el) return 'not found';
            el.focus();
            const ns = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            const chars = [{chars_js}];
            let cur = '';
            for (const ch of chars) {{
                cur += ch;
                ns.call(el, cur);
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
                el.dispatchEvent(new Event('change', {{bubbles: true}}));
                await new Promise(r => setTimeout(r, 50 + Math.random() * 100));
            }}
            return 'typed ' + chars.length + ' chars';
        }})()
        """
        return self.evaluate(js)

    def click_js(self, selector):
        """Klik via JS: PointerEvent + MouseEvent + native click."""
        js = f"""
        (() => {{
            const el = document.querySelector('{selector}');
            if (!el) return 'not found';
            const btn = el.querySelector('button') || el;
            btn.dispatchEvent(new PointerEvent('pointerdown',
                {{bubbles: true, cancelable: true, pointerId: 1, pointerType: 'mouse'}}));
            btn.dispatchEvent(new PointerEvent('pointerup',
                {{bubbles: true, cancelable: true, pointerId: 1, pointerType: 'mouse'}}));
            btn.dispatchEvent(new MouseEvent('mousedown', {{bubbles: true, cancelable: true}}));
            btn.dispatchEvent(new MouseEvent('mouseup', {{bubbles: true, cancelable: true}}));
            btn.dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true}}));
            btn.click();
            return 'clicked';
        }})()
        """
        return self.evaluate(js)

    # ── Snapshot helpers ──────────────────────────────────────

    @staticmethod
    def find_ref_by_text(snapshot_text, search_text):
        """Cari ref [eN] di baris snapshot yang mengandung search_text."""
        for line in snapshot_text.split('\n'):
            if search_text.lower() in line.lower():
                m = re.search(r'\[e(\d+)\]', line)
                if m:
                    return f"e{m.group(1)}"
        return None

    def wait(self, seconds):
        time.sleep(seconds)
