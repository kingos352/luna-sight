#!/usr/bin/env python3
"""Demo videosu için arayüz karelerini yakalar.

`docs/DEMO_SCRIPT.md` içindeki dört segmenti sırayla gezer ve her sahnenin
karesini PNG olarak yazar. Kareler `scripts/k5_build_video.py` tarafından
videoya dönüştürülür.

Kareler **gerçek arayüzden** alınır: uygulama gerçek `outputs/k3` çıktılarını
okur, yani videoda görünen her sayı depodaki veriyle aynıdır.

Tarayıcı, kurulu Chrome'un DevTools Protokolü üzerinden sürülür. Ek paket
kurulmaz: `websockets` zaten Streamlit ile gelir, Pillow da öyle. Playwright
denendi ve 42 MB'lık tekerlek indirmesi bu ağda takıldı; ayrıca dört rolün CI
koşusuna böyle bir indirme eklemek istenmez.

Kullanım:

    .venv\\Scripts\\python.exe -m streamlit run app/app.py --server.port 8502
    .venv\\Scripts\\python.exe scripts/k5_record_demo.py --out build/frames
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from websockets.sync.client import connect

# Arayüz 900 piksel yüksekliğinde yakalanır; kalan 180 piksel montajda
# altyazı şeridine ayrılır. Böylece altyazı hiçbir zaman arayüzün
# üzerine binmez ve ölçekleme yapılmaz.
VIEWPORT = (1920, 900)
READY_TEXT = "Aday bölge seçimi"
PLOT_SELECTOR = '[data-testid="stPlotlyChart"]'
CHROME_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)


def _find_chrome() -> str:
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    raise RuntimeError(f"Chrome bulunamadı: {CHROME_CANDIDATES}")


class Chrome:
    """Chrome DevTools Protokolü üzerinden tek sayfalık oturum."""

    def __init__(self, port: int = 9222, headless: bool = True) -> None:
        self.port = port
        self.headless = headless
        self._process: subprocess.Popen[bytes] | None = None
        self._socket = None
        self._next_id = 0

    # -- yaşam döngüsü ---------------------------------------------------
    def start(self) -> None:
        flags = [
            _find_chrome(),
            f"--remote-debugging-port={self.port}",
            f"--window-size={VIEWPORT[0]},{VIEWPORT[1]}",
            "--hide-scrollbars",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank",
        ]
        if self.headless:
            flags.insert(1, "--headless=new")
        self._process = subprocess.Popen(
            flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        self._wait_for_endpoint()

    def _wait_for_endpoint(self, timeout: float = 30.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"http://localhost:{self.port}/json/version", timeout=2)
                return
            except (urllib.error.URLError, OSError):
                time.sleep(0.3)
        raise RuntimeError("Chrome DevTools uç noktası açılmadı")

    def open_page(self, url: str) -> None:
        browser_url = json.load(
            urllib.request.urlopen(f"http://localhost:{self.port}/json/version", timeout=10)
        )["webSocketDebuggerUrl"]
        with connect(browser_url, max_size=None) as browser:
            request = {"id": 1, "method": "Target.createTarget", "params": {"url": url}}
            browser.send(json.dumps(request))
            target_id = json.loads(browser.recv())["result"]["targetId"]
        self._socket = connect(
            f"ws://localhost:{self.port}/devtools/page/{target_id}",
            max_size=None,
            open_timeout=30,
        )
        self.send("Page.enable")
        self.send("Runtime.enable")
        self.send(
            "Emulation.setDeviceMetricsOverride",
            {"width": VIEWPORT[0], "height": VIEWPORT[1], "deviceScaleFactor": 1, "mobile": False},
        )

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
        if self._process is not None:
            self._process.terminate()

    # -- protokol --------------------------------------------------------
    def send(self, method: str, params: dict | None = None) -> dict:
        assert self._socket is not None, "open_page çağrılmadı"
        self._next_id += 1
        message_id = self._next_id
        self._socket.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        while True:
            payload = json.loads(self._socket.recv())
            if payload.get("id") == message_id:
                if "error" in payload:
                    raise RuntimeError(f"{method}: {payload['error']}")
                return payload.get("result", {})

    def evaluate(self, expression: str) -> object:
        result = self.send(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        return result.get("result", {}).get("value")

    def screenshot(self, path: Path) -> None:
        data = self.send("Page.captureScreenshot", {"format": "png"})["data"]
        path.write_bytes(base64.b64decode(data))

    def press(self, key: str, code: str, key_code: int) -> None:
        for event in ("rawKeyDown", "keyUp"):
            self.send(
                "Input.dispatchKeyEvent",
                {"type": event, "key": key, "code": code, "windowsVirtualKeyCode": key_code},
            )

    # -- yardımcılar -----------------------------------------------------
    def wait_for_text(self, needle: str, timeout: float = 90.0) -> None:
        deadline = time.time() + timeout
        probe = f"document.body.innerText.includes({json.dumps(needle)})"
        while time.time() < deadline:
            if self.evaluate(probe):
                return
            time.sleep(0.5)
        raise RuntimeError(f"metin görünmedi: {needle!r}")

    def settle(self, seconds: float = 1.0) -> None:
        """Streamlit yeniden çalıştıktan sonra çizimin oturmasını bekle."""
        time.sleep(seconds)

    def scroll_to(self, y: int) -> None:
        """Sayfayı kaydır.

        Streamlit ana içeriği `window` yerine kendi kabında kaydırabiliyor;
        her iki hedef de denenir.
        """
        script = f"""
        (() => {{
          const y = {y};
          window.scrollTo({{top: y, behavior: 'instant'}});
          const panes = document.querySelectorAll(
            '[data-testid="stAppViewContainer"] section, section.main, .main'
          );
          panes.forEach(p => {{ if (p.scrollHeight > p.clientHeight) p.scrollTop = y; }});
          return true;
        }})()
        """
        self.evaluate(script)
        time.sleep(0.4)

    def center_element(self, css: str) -> bool:
        """Verilen ögeyi kadrajın ortasına getir.

        Kaydırma değeriyle uğraşmak yerine hedefi doğrudan ortalamak, düzen
        değiştiğinde de doğru kadrajı verir. Yalnızca görünür ögeleri
        (offsetWidth > 0 && offsetHeight > 0) eşler; böylece kapalı expander
        veya etkin olmayan sekmedeki 0x0 grafikler atlanır.
        """
        script = f"""
        (() => {{
          const el = Array.from(document.querySelectorAll({json.dumps(css)})).find(
            node => node.offsetWidth > 0 && node.offsetHeight > 0
          );
          if (!el) return false;
          el.scrollIntoView({{block: 'center', inline: 'center'}});
          return true;
        }})()
        """
        found = bool(self.evaluate(script))
        time.sleep(0.4)
        return found

    def click_text(self, text: str, role: str | None = None) -> bool:
        """Metnine göre tıkla. Bulunamazsa False döner, akış durmaz."""
        selector = f'[role="{role}"]' if role else "button, [role='tab'], summary, div, span"
        script = f"""
        (() => {{
          const needle = {json.dumps(text)};
          const nodes = Array.from(document.querySelectorAll({json.dumps(selector)}));
          const hit = nodes.find(n => (n.innerText || '').trim().includes(needle));
          if (!hit) return false;
          hit.scrollIntoView({{block: 'center'}});
          hit.click();
          return true;
        }})()
        """
        return bool(self.evaluate(script))

    def focus_last_slider(self) -> bool:
        """Zaman adımı kaydırıcısına odaklan.

        Streamlit kaydırıcıyı `input[type=range]` olarak çizer; `role="slider"`
        bulunmaz. Sayfadaki son kaydırıcı zaman adımıdır, ilki kenar çubuğundaki
        görev süresidir.
        """
        script = """
        (() => {
          const sliders = Array.from(document.querySelectorAll('input[type=range]'));
          if (!sliders.length) return false;
          const target = sliders[sliders.length - 1];
          target.scrollIntoView({block: 'center'});
          target.focus();
          return true;
        })()
        """
        return bool(self.evaluate(script))

    def hide_browser_chrome(self) -> None:
        """Streamlit araç çubuğunu ve Deploy düğmesini gizle.

        Bunlar uygulamanın bilimsel içeriği değil, geliştirme kabuğudur;
        jüri videosunda görünmemeli. Uygulama kodu değiştirilmez, yalnızca
        kayıt sırasında CSS enjekte edilir.
        """
        script = """
        (() => {
          const style = document.createElement('style');
          style.textContent = `
            [data-testid="stToolbar"], [data-testid="stDecoration"],
            [data-testid="stStatusWidget"], header[data-testid="stHeader"] {
              display: none !important;
            }
            .stApp { top: 0 !important; }
          `;
          document.head.appendChild(style);
          return true;
        })()
        """
        self.evaluate(script)


class Recorder:
    """Kareleri sıralı adlarla yazar; sıra numarası montajda kullanılır."""

    def __init__(self, chrome: Chrome, out_dir: Path) -> None:
        self.chrome = chrome
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.index = 0

    def shot(self, scene: str) -> Path:
        self.index += 1
        path = self.out_dir / f"{self.index:03d}_{scene}.png"
        self.chrome.screenshot(path)
        print(f"  {path.name}")
        return path


def scene_intro(rec: Recorder) -> None:
    print("segment 1 - giris")
    rec.chrome.scroll_to(0)
    rec.shot("intro_hero")
    rec.chrome.scroll_to(260)
    rec.shot("intro_steps")


def scene_compare(rec: Recorder) -> None:
    print("segment 2 - A/B karsilastirma")
    chrome = rec.chrome
    chrome.scroll_to(620)
    rec.shot("compare_metrics")
    chrome.scroll_to(1000)
    rec.shot("compare_metrics_lower")
    if chrome.click_text("Topoğrafik engel özeti"):
        chrome.settle(0.8)
        rec.shot("compare_obstacles")


def scene_horizon(rec: Recorder, frames: int, step: int, scroll: int) -> None:
    """Segment 3: ufuk görünümü ve zaman kaydırıcısı animasyonu.

    Her karede kaydırma konumu yeniden kurulur: kaydırıcıya odaklanmak ve
    Streamlit'in yeniden çalışması sayfayı kaydırabiliyor, bu da polar
    grafiğin kadraj dışında kalmasına yol açıyordu.
    """
    print("segment 3 - ufuk gorunumu")
    chrome = rec.chrome
    chrome.click_text("Ufuk görünümü", role="tab") or chrome.click_text("Ufuk görünümü")
    chrome.settle(1.6)
    if not chrome.center_element(PLOT_SELECTOR):
        chrome.scroll_to(scroll)
    rec.shot("horizon_initial")

    if not chrome.focus_last_slider():
        print("  (kaydırıcı bulunamadı, animasyon atlandı)")
        return
    for frame in range(frames):
        for _ in range(step):
            chrome.press("ArrowRight", "ArrowRight", 39)
        chrome.settle(0.55)
        if not chrome.center_element(PLOT_SELECTOR):
            chrome.scroll_to(scroll)
        rec.shot(f"horizon_t{frame:02d}")


def scene_timeline(rec: Recorder, scroll: int) -> None:
    chrome = rec.chrome
    if chrome.click_text("Zaman çizelgesi", role="tab") or chrome.click_text("Zaman çizelgesi"):
        chrome.settle(1.6)
        if not chrome.center_element(PLOT_SELECTOR):
            chrome.scroll_to(scroll)
        rec.shot("timeline")


def scene_data(rec: Recorder) -> None:
    print("segment 4 - veri ve kaynak")
    chrome = rec.chrome
    chrome.click_text("Veri ve kaynak", role="tab") or chrome.click_text("Veri ve kaynak")
    chrome.settle(1.6)
    chrome.scroll_to(420)
    rec.shot("data_cards")
    chrome.scroll_to(1150)
    rec.shot("data_provenance")
    chrome.scroll_to(1700)
    rec.shot("data_provenance_lower")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8502")
    parser.add_argument("--out", type=Path, default=Path("build/frames"))
    parser.add_argument("--port", type=int, default=9333)
    parser.add_argument("--slider-frames", type=int, default=18)
    parser.add_argument("--slider-step", type=int, default=9)
    parser.add_argument("--horizon-scroll", type=int, default=980)
    parser.add_argument("--headed", action="store_true", help="tarayıcıyı görünür aç")
    args = parser.parse_args(argv)

    chrome = Chrome(port=args.port, headless=not args.headed)
    chrome.start()
    try:
        print(f"acilis: {args.url}")
        chrome.open_page(args.url)
        chrome.wait_for_text(READY_TEXT)
        chrome.hide_browser_chrome()
        chrome.settle(2.5)

        rec = Recorder(chrome, args.out)
        scene_intro(rec)
        scene_compare(rec)
        scene_horizon(rec, args.slider_frames, args.slider_step, args.horizon_scroll)
        scene_timeline(rec, args.horizon_scroll)
        scene_data(rec)
        print(f"\ntoplam {rec.index} kare -> {args.out}")
    finally:
        chrome.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
