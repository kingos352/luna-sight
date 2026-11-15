"""NVIDIA NIM istemcisi (OpenAI uyumlu sohbet tamamlama).

2026-11-15 canlı model listesinde Cosmos3 bulunmadı; Cosmos Reason2 8B vardı.
Model seçimi açıkça yapılandırılır. Cosmos3 NIM örnek adresi:

    POST http://127.0.0.1:8000/v1/chat/completions

Bu yüzden taban adres yapılandırılabilir. Barındırılan bir uç nokta
yayınlandığında yalnızca ortam değişkeni değişir, kod değişmez.

Ortam değişkenleri:

- ``LUNA_SIGHT_NIM_BASE_URL``  taban adres (varsayılan NVIDIA hosted API)
- ``NVIDIA_API_KEY``          anahtar; yerel konteynerde gerekmez
- ``LUNA_SIGHT_NIM_MODEL``    model kimliği (varsayılan Nemotron 3.5 Super VL)

Anahtar yalnızca ``Authorization`` başlığına yazılır; günlüğe, hata
metnine veya yanıt nesnesine **hiçbir koşulda** konmaz.
"""

from __future__ import annotations

import ipaddress
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.exceptions import MaxRetryError, ReadTimeoutError
from urllib3.util.retry import Retry

from luna_sight.ai.schema import MODEL_ID

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
CHAT_PATH = "/chat/completions"

#: Geçici hatalar. 429 hız sınırı; 5xx sunucu tarafı.
RETRY_STATUS = (429, 500, 502, 503, 504)


class NimError(RuntimeError):
    """NIM çağrısı başarısız. Mesaj anahtar içermez."""


class NimNotConfigured(NimError):
    """Uç nokta erişilebilir değil ya da kimlik bilgisi eksik."""


@dataclass(frozen=True)
class NimConfig:
    base_url: str
    model: str
    api_key: str | None = field(repr=False)
    timeout: float
    max_retries: int
    reasoning_effort: str | None = None

    def __post_init__(self) -> None:
        if self.reasoning_effort not in (None, "none", "low", "high"):
            raise NimNotConfigured("LUNA_SIGHT_NIM_REASONING_EFFORT: none, low veya high olmalı.")
        url = urlsplit(self.base_url)
        if (
            url.scheme not in ("http", "https")
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise NimNotConfigured("NIM adresi kimlik bilgisi içermeyen bir HTTP(S) URL olmalı.")
        if self.requires_key and url.scheme != "https":
            raise NimNotConfigured("Uzak NIM bağlantısında HTTPS gerekiyor.")

    @property
    def endpoint(self) -> str:
        return self.base_url.rstrip("/") + CHAT_PATH

    @property
    def requires_key(self) -> bool:
        """Yerel konteyner anahtar istemez; uzak uç nokta ister."""
        host = urlsplit(self.base_url).hostname or ""
        if host.lower() == "localhost":
            return False
        try:
            return not ipaddress.ip_address(host).is_loopback
        except ValueError:
            return True

    def describe(self) -> str:
        """Günlüğe ve arayüze yazılabilir özet. Anahtar sızdırmaz."""
        state = "anahtar var" if self.api_key else "anahtar yok"
        return f"{self.endpoint} · model={self.model} · {state}"


def load_config(
    base_url: str | None = None,
    model: str | None = None,
    timeout: float = 90.0,
    max_retries: int = 2,
) -> NimConfig:
    """Ortamdan yapılandırmayı oku."""
    load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)
    return NimConfig(
        base_url=base_url or os.environ.get("LUNA_SIGHT_NIM_BASE_URL", DEFAULT_BASE_URL),
        model=model or os.environ.get("LUNA_SIGHT_NIM_MODEL", MODEL_ID),
        api_key=os.environ.get("NVIDIA_API_KEY") or None,
        timeout=timeout,
        max_retries=max_retries,
        reasoning_effort=os.environ.get("LUNA_SIGHT_NIM_REASONING_EFFORT") or None,
    )


def build_session(max_retries: int = 2, backoff_factor: float = 1.5) -> requests.Session:
    """Hız sınırı ve geçici sunucu hatasında geri çekilen oturum."""
    retry = Retry(
        total=max_retries,
        connect=max_retries,
        read=0,
        status=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=RETRY_STATUS,
        allowed_methods=frozenset({"POST"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = "luna-sight/0.1 (NASA Space Apps prototype)"
    return session


@dataclass
class NimClient:
    """Tek sorumluluğu: istek kurmak, göndermek, metni geri vermek.

    Ayrıştırma ve doğrulama `schema` katmanında yapılır; burada model
    çıktısına güvenilmez, yalnızca taşınır.
    """

    config: NimConfig
    session: requests.Session | None = None
    last_latency_s: float | None = None

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = build_session(self.config.max_retries)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def chat(
        self,
        messages: list[dict[str, object]],
        max_tokens: int = 768,
        temperature: float = 0.2,
    ) -> str:
        """Sohbet tamamlama çağır ve yanıt metnini döndür."""
        if self.config.requires_key and not self.config.api_key:
            raise NimNotConfigured(
                "Uzak uç nokta için NVIDIA_API_KEY gerekiyor. Yerel NIM "
                "konteyneri kullanıyorsanız LUNA_SIGHT_NIM_BASE_URL değerini "
                "http://127.0.0.1:8000/v1 olarak ayarlayın."
            )

        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        if self.config.reasoning_effort is not None:
            payload["reasoning_effort"] = self.config.reasoning_effort
        assert self.session is not None
        started = time.perf_counter()
        try:
            response = self.session.post(
                self.config.endpoint,
                json=payload,
                headers=self._headers(),
                timeout=self.config.timeout,
                allow_redirects=False,
            )
        except requests.Timeout:
            raise NimError(f"NIM zaman aşımı ({self.config.timeout:.0f} sn).") from None
        except requests.ConnectionError as exc:
            if any(
                isinstance(arg, ReadTimeoutError)
                or (isinstance(arg, MaxRetryError) and isinstance(arg.reason, ReadTimeoutError))
                for arg in exc.args
            ):
                raise NimError(
                    f"AI hizmeti {self.config.timeout:.0f} saniyede yanıt vermedi. "
                    "Yeniden deneyebilirsiniz."
                ) from None
            hint = (
                "AI hizmetine bağlanılamadı. Ağ bağlantısını kontrol edip yeniden deneyin."
                if self.config.requires_key
                else "Yerel NIM sunucusuna bağlanılamadı. Sunucunun çalıştığını kontrol edin."
            )
            raise NimNotConfigured(hint) from None
        except requests.RequestException:
            raise NimError("NIM isteği tamamlanamadı.") from None
        finally:
            self.last_latency_s = time.perf_counter() - started

        if response.status_code == 429:
            raise NimError("NIM hız sınırı (429). Biraz sonra tekrar deneyin.")
        if response.status_code in (401, 403):
            raise NimNotConfigured("NIM kimlik doğrulaması reddedildi (401/403).")
        if response.status_code == 404:
            cosmos_note = (
                " NVIDIA Cosmos Reason2 API erişiminin kapatıldığını bildirmiştir; "
                "erişilebilir bir NIM sunucusu veya başka bir görsel model gerekir."
                if "cosmos-reason2" in self.config.model
                else ""
            )
            raise NimNotConfigured(
                "NIM HTTP 404: model yolu veya hesap erişimi bulunamadı. "
                "Model listesinde görünmek çıkarım erişimini garanti etmez." + cosmos_note
            )
        if response.status_code != 200:
            # Sunucu gövdesi anahtarı veya isteği yansıtabilir; dışarı taşınmaz.
            raise NimError(f"NIM HTTP {response.status_code}.")

        try:
            data = response.json()
            choices = data["choices"]
            content = choices[0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise NimError("NIM yanıtı beklenen biçimde değil.") from None

        if isinstance(content, list):
            # Bazı NIM sürümleri parça listesi döndürür.
            content = "".join(
                part["text"]
                for part in content
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            )
        if not isinstance(content, str) or not content.strip():
            raise NimError("NIM boş veya metin olmayan yanıt döndürdü.")
        return content

    def probe(self) -> tuple[bool, str]:
        """Uç noktanın erişilebilir olup olmadığını söyle.

        Arayüz bunu kullanarak "NIM kapalı" durumunu önceden gösterir ve
        kullanıcıyı çıkarım beklerken bekletmez.
        """
        assert self.session is not None
        if self.config.requires_key and not self.config.api_key:
            return False, "Uzak uç nokta için NVIDIA_API_KEY eksik."
        try:
            response = self.session.get(
                self.config.base_url.rstrip("/") + "/models",
                headers=self._headers(),
                timeout=5,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            return False, f"Erişilemiyor: {type(exc).__name__}"
        if response.status_code != 200:
            return False, f"HTTP {response.status_code}"
        try:
            ids = {entry["id"] for entry in response.json()["data"]}
        except (ValueError, KeyError, TypeError):
            return False, "Model listesi okunamadı."
        if self.config.model not in ids:
            return False, "Seçilen model uç noktanın model listesinde yok."
        return True, "Model listede mevcut; görsel çıkarım henüz doğrulanmadı."
