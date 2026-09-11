"""Camoufox LOCAL client - 1 instance browser, auto-cleanup.

Aturan (sesuai kebutuhan user):
  1. SATU instance browser saja, di-reuse antar akun.
  2. Butuh fresh (login state kotor)? -> kill instance lama dulu,
     baru launch baru. Tidak pernah 2 browser bareng.
  3. Browser PASTI ikut mati walau script crash / Ctrl+C / di-kill
     (atexit + signal handler + subprocess langsung).

Arsitektur ringan ala cf-auto: playwright sync API nge-drive binary
camoufox.exe. Tidak ada server npm, tidak ada HTTP layer.
"""

import atexit
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

from .config import LOGIN_URL

# Path binary Camoufox (di-resolve 1x saat import)
_CAMOUFOX_EXE = None


def _resolve_exe():
    global _CAMOUFOX_EXE
    if _CAMOUFOX_EXE is None:
        from camoufox.pkgman import camoufox_path
        _CAMOUFOX_EXE = str(camoufox_path() / "camoufox.exe")
    return _CAMOUFOX_EXE


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}")


def kill_stale_camoufox():
    """Kill camoufox.exe yatim SEBELUM launch instance baru.
    Catatan: 1 instance Firefox = ~8 proses OS (main + content + gpu +
    utility) - SEMUA bernama camoufox.exe. Jadi yang dibandingkan bukan
    'jumlah proses' tapi ADA/TIDAKNYA proses saat browser kita mati."""
    try:
        # Skip kalau instance kita sendiri masih hidup (jangan bunuh diri sendiri)
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq camoufox.exe"],
            capture_output=True, text=True, timeout=15,
        ).stdout.lower()
        if "camoufox.exe" in out:
            log("  Kill instance Camoufox lama (butuh fresh)...")
            subprocess.run(
                ["taskkill", "/F", "/IM", "camoufox.exe"],
                capture_output=True, text=True, timeout=15,
            )
            time.sleep(2)
    except Exception:
        pass


class CamofoxClient:
    """Camoufox lokal. 1 client = 1 browser = 1 page.

    Usage:
        c = CamofoxClient()
        c.create_tab(url)          # launch browser kalau belum jalan
        ...
        c.delete_session()         # tutup browser (atau otomatis saat exit)
    """

    def __init__(self, server_url=None, user_id=None):
        self.user_id = user_id or f"local_{int(time.time())}"
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._cleanup_registered = False
        self._register_cleanup()

    # ── Cleanup guarantee (atexit + signal) ──────────────────

    def _register_cleanup(self):
        if self._cleanup_registered:
            return
        self._cleanup_registered = True
        atexit.register(self.delete_session)
        # Ctrl+C / terminate dari luar
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                prev = signal.getsignal(sig)

                def handler(signum, frame, _prev=prev):
                    self.delete_session()
                    if callable(_prev):
                        _prev(signum, frame)
                    else:
                        sys.exit(1)

                signal.signal(sig, handler)
            except Exception:
                pass

    def _kill_orphans(self):
        """Jangan pernah 2 instance: kill camoufox.exe yatim dulu."""
        if self._browser is not None and self._browser.is_connected():
            return  # instance kita sendiri masih hidup, jangan dikill
        kill_stale_camoufox()

    # ── Lifecycle ─────────────────────────────────────────────

    def _launch(self):
        """Launch 1 instance. Reuse kalau masih hidup."""
        if self._browser is not None and self._browser.is_connected():
            return
        self._kill_orphans()
        log("  Launch Camoufox (1 instance)...")
        self._pw = sync_playwright().start()
        self._browser = self._pw.firefox.launch(
            executable_path=_resolve_exe(),
            headless=False,
            firefox_user_prefs={
                "dom.webdriver.enabled": False,
                "marionette.enabled": False,
                "devtools.webdriver.enabled": False,
                "privacy.resistFingerprinting": False,
            },
        )

    def _ensure_page(self, url=None):
        """Pastikan browser + context + page ada (reuse).
        PENTING: kalau context lama mati, TUTUP dulu sebelum bikin baru -
        context yatim menumpuk memori (penyebab 3GB kemarin)."""
        self._launch()
        try:
            if self._context is not None:
                # Context masih hidup? cek dengan akses ringan
                _ = self._browser.contexts
                if self._context not in self._browser.contexts:
                    self._context = None
                    self._page = None
            if self._context is None:
                self._context = self._browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    locale="en-US",
                )
            if self._page is None or self._page.is_closed():
                self._page = self._context.new_page()
                if url:
                    self._page.goto(url, wait_until="domcontentloaded",
                                    timeout=60000)
            return self._page
        except Exception as e:
            # Context/page/browser mati - tutup semuanya dulu, jangan numpuk
            msg = str(e).lower()
            if ('closed' in msg or 'target' in msg or 'context' in msg):
                try:
                    self.delete_session()
                except Exception:
                    pass
                self._launch()
                self._context = self._browser.new_context(
                    viewport={"width": 1280, "height": 800}, locale="en-US")
                self._page = self._context.new_page()
                if url:
                    self._page.goto(url, wait_until="domcontentloaded",
                                    timeout=60000)
                return self._page
            raise

    # ── Server-compat API (dipakai engine.py) ─────────────────

    def check_server(self):
        return True

    def create_tab(self, url):
        page = self._ensure_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)
        return {"tabId": id(page)}

    def ensure_tab(self, url=LOGIN_URL):
        self._ensure_page(url)
        return True

    def fresh(self):
        """Browser fresh: TUTUP instance lama dulu, buka baru nanti.
        Satu-satunya cara 'reset' - tidak pernah 2 instance."""
        log("  Fresh browser: tutup instance lama dulu...")
        self.delete_session()
        kill_stale_camoufox()

    def close_tab(self):
        try:
            if self._page and not self._page.is_closed():
                self._page.close()
        except Exception:
            pass
        self._page = None

    def delete_session(self):
        """Tutup SEMUA: page, context, browser, playwright."""
        for closer, attr in [
            ("page", "_page"), ("context", "_context"),
            ("browser", "_browser"), ("pw", "_pw"),
        ]:
            obj = getattr(self, attr, None)
            if obj is None:
                continue
            try:
                if attr == "_page":
                    if not obj.is_closed():
                        obj.close()
                elif attr == "_browser":
                    if obj.is_connected():
                        obj.close()
                else:
                    obj.close() if attr == "_context" else obj.stop()
            except Exception:
                pass
            setattr(self, attr, None)

    # Alias agar engine.py lama tetap jalan
    delete_persisted_profile = lambda self: None

    def clear_cookies(self):
        try:
            if self._context:
                self._context.clear_cookies()
        except Exception:
            pass

    def wait(self, seconds):
        time.sleep(seconds)

    # ── Snapshot (format a11y [eN] ala server) ────────────────

    def get_snapshot(self):
        page = self._ensure_page()
        url = page.url
        try:
            page.set_default_timeout(15000)
            snapshot = page.evaluate("""
            () => {
                const lines = [];
                let ref = 0;
                const walk = (el, depth) => {
                    if (ref > 60) return;
                    for (const child of el.children) {
                        const tag = child.tagName.toLowerCase();
                        if (['script','style','noscript','svg','path'].includes(tag)) continue;
                        const text = (child.textContent || '').trim().split('\\n')[0].substring(0, 80);
                        let role = null;
                        if (tag === 'input') {
                            const t = child.type || 'text';
                            if (t === 'hidden') continue;
                            role = 'textbox "' + (child.getAttribute('aria-label') || child.placeholder || child.name || t) + '"';
                        } else if (tag === 'button' || (child.getAttribute('role') === 'button')) {
                            role = 'button';
                        } else if (tag === 'a') {
                            role = 'link';
                        } else if (tag === 'h1' || tag === 'h2' || tag === 'h3') {
                            role = 'heading "' + text + '"';
                        }
                        if (role) {
                            ref += 1;
                            lines.push('  - ' + role + ' [e' + ref + ']');
                        } else if (text && depth < 12) {
                            lines.push('  - text: ' + text);
                        }
                        walk(child, depth + 1);
                    }
                };
                walk(document.body, 0);
                return lines.join('\\n');
            }
            """)
        except Exception as e:
            snapshot = f"  - text: [snapshot error: {str(e)[:80]}]"
        return snapshot, url

    def get_full_snapshot(self):
        return self.get_snapshot()

    @staticmethod
    def find_ref_by_text(snapshot_text, search_text):
        for line in snapshot_text.split('\n'):
            if search_text.lower() in line.lower():
                m = re.search(r'\[e(\d+)\]', line)
                if m:
                    return f"e{m.group(1)}"
        return None

    # ── Interactions ──────────────────────────────────────────

    def evaluate(self, js_code):
        """JS di halaman. Navigasi setelah aksi = aksi berhasil."""
        page = self._ensure_page()
        try:
            page.set_default_timeout(30000)
            res = page.evaluate(js_code)
            return {"ok": True, "result": res}
        except Exception as e:
            msg = str(e)
            if any(k in msg.lower() for k in [
                    'navigation', 'context or browser has been closed',
                    'execution context was destroyed', 'target closed']):
                return {"ok": True, "note": "page navigated after action"}
            return {"error": msg[:150]}

    def type_text_js(self, selector, text):
        """Ketik human-like: native setter + 50-150ms per char."""
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
        """Klik via JS. Sinkron + cepat: klik dieksekusi tanpa menunggu
        navigasi. Kalau context mati karena navigasi = klik berhasil."""
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
        page = self._ensure_page()
        try:
            page.set_default_timeout(10000)
            res = page.evaluate(js)
            return {"ok": True, "result": res}
        except Exception as e:
            msg = str(e)
            if any(k in msg.lower() for k in [
                    'navigation', 'context or browser has been closed',
                    'execution context was destroyed', 'target closed']):
                return {"ok": True, "note": "page navigated after click"}
            return {"error": msg[:150]}

    def click(self, ref):
        """Klik trusted via Playwright locator (urutan element)."""
        page = self._ensure_page()
        try:
            n = int(re.search(r'\d+', ref).group())
            handles = page.query_selector_all(
                'input:not([type=hidden]), button, a, [role=button]')
            if 1 <= n <= len(handles):
                handles[n - 1].click(timeout=15000)
                return {"ok": True, "clicked": f"e{n}"}
            return {"error": f"ref e{n} di luar jangkauan ({len(handles)})"}
        except Exception as e:
            return {"error": str(e)[:150]}

    def navigate(self, url):
        page = self._ensure_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)
        return {"ok": True}

    def type_text(self, ref, text):
        """Isi field via Playwright locator (urutan element)."""
        page = self._ensure_page()
        try:
            n = int(re.search(r'\d+', ref).group())
            handles = page.query_selector_all(
                'input:not([type=hidden]), button, a, [role=button]')
            if 1 <= n <= len(handles):
                handles[n - 1].fill(text, timeout=15000)
                return {"ok": True}
            return {"error": f"ref e{n} di luar jangkauan"}
        except Exception as e:
            return {"error": str(e)[:150]}
