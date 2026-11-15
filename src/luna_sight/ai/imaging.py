"""Çıkarıma gönderilecek görüntünün hazırlanması ve kökeninin kaydı.

Spec bölüm 4.2: önce gerçek bilimsel görüntü kullanılır. Elimizdeki gerçek
görüntü NASA **Moon Trek / LRO WAC** mozaiğidir (`data/manifest.csv` içinde
kökeniyle kayıtlı). 3B görünümden alınan kare kullanılırsa bu **ayrıca
işaretlenir**: oradaki aydınlatma ve gölgeleme çizim motorundan gelir,
ölçülmüş yüzey özelliği değildir ve modele öyle sunulmamalıdır.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[3]
WAC_TEXTURE = REPO_ROOT / "app" / "static" / "moon" / "textures" / "moon_trek_wac_4k.jpg"

#: Model jpg/png/jpeg/webp kabul ediyor (NVIDIA model kartı).
ALLOWED_FORMATS = ("JPEG", "PNG", "WEBP")
MAX_SIDE_PX = 1024
MAX_PAYLOAD_BYTES = 4 * 1024 * 1024


class ImagePreparationError(RuntimeError):
    """Görüntü doğrulanamadı ya da hazırlanamadı."""


@dataclass(frozen=True)
class PreparedImage:
    """Çıkarıma hazır görüntü ve kökeni."""

    data_url: str
    width: int
    height: int
    source_label: str
    is_rendered: bool
    provenance_note: str

    @property
    def payload_bytes(self) -> int:
        return len(self.data_url)


def _to_data_url(image: Image.Image, fmt: str = "JPEG", quality: int = 88) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, quality=quality)
    raw = buffer.getvalue()
    if len(raw) > MAX_PAYLOAD_BYTES:
        raise ImagePreparationError(
            f"Görüntü yükü çok büyük: {len(raw) / 1e6:.1f} MB "
            f"(sınır {MAX_PAYLOAD_BYTES / 1e6:.0f} MB)."
        )
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:image/{fmt.lower()};base64,{encoded}"


def _fit(image: Image.Image, max_side: int = MAX_SIDE_PX) -> Image.Image:
    if max(image.size) <= max_side:
        return image
    scale = max_side / max(image.size)
    size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
    return image.resize(size, Image.LANCZOS)


def validate_image(image: Image.Image) -> None:
    if image.width < 32 or image.height < 32:
        raise ImagePreparationError(
            f"Görüntü çok küçük: {image.width}x{image.height} (en az 32x32)."
        )


def crop_wac_tile(
    latitude_deg: float,
    longitude_deg_east: float,
    half_span_deg: float = 12.0,
    texture_path: Path | None = None,
) -> PreparedImage:
    """Moon Trek WAC mozaiğinden bölge kırpar.

    Mozaik eşdikdörtgen (plate carrée) yerleştirilmiştir: yatay eksen
    boylam -180..180, dikey eksen enlem 90..-90. Kırpma bu doğrusal
    eşlemeyle yapılır; piksel seviyesinde jeodezik hassasiyet iddia
    edilmez ve bu sınır not olarak taşınır.
    """
    path = texture_path or WAC_TEXTURE
    if not path.exists():
        raise ImagePreparationError(f"Taban harita bulunamadı: {path}")

    with Image.open(path) as source:
        source = source.convert("RGB")
        width, height = source.size

        def to_x(lon: float) -> int:
            return int(round((lon + 180.0) / 360.0 * width))

        def to_y(lat: float) -> int:
            return int(round((90.0 - lat) / 180.0 * height))

        left = to_x(max(-180.0, longitude_deg_east - half_span_deg))
        right = to_x(min(180.0, longitude_deg_east + half_span_deg))
        top = to_y(min(90.0, latitude_deg + half_span_deg))
        bottom = to_y(max(-90.0, latitude_deg - half_span_deg))
        if right - left < 8 or bottom - top < 8:
            raise ImagePreparationError("Kırpma penceresi çok dar.")

        tile = source.crop((left, top, right, bottom))
        validate_image(tile)
        tile = _fit(tile)
        data_url = _to_data_url(tile)

    return PreparedImage(
        data_url=data_url,
        width=tile.width,
        height=tile.height,
        source_label="NASA Moon Trek / LRO WAC mozaiği (4K)",
        is_rendered=False,
        provenance_note=(
            "Gerçek gözlemsel görüntü. Eşdikdörtgen mozaikten "
            f"{latitude_deg:.4f}°, {longitude_deg_east:.4f}° (doğu-pozitif) "
            f"merkezli ±{half_span_deg:.0f}° pencereyle kırpıldı. Kutba yakın "
            "bölgelerde eşdikdörtgen izdüşüm belirgin biçimde gerer; bu kırpma "
            "görsel inceleme içindir, ölçüm için kullanılmaz."
            " Bu 4K küresel mozaik yalnızca bölgesel bağlam sağlar; küçük kaya "
            "blokları ve ince yüzey dokusu bu çözünürlükte doğrulanamaz."
        ),
    )


def prepare_uploaded_image(data: bytes, filename: str = "") -> PreparedImage:
    """Kullanıcının yüklediği görüntüyü doğrula ve hazırla."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            fmt = (image.format or "").upper()
            if fmt not in ALLOWED_FORMATS:
                raise ImagePreparationError(
                    f"Desteklenmeyen biçim: {fmt or 'bilinmiyor'}. "
                    f"İzinli: {', '.join(ALLOWED_FORMATS)}."
                )
            image = image.convert("RGB")
            validate_image(image)
            image = _fit(image)
            data_url = _to_data_url(image)
            size = image.size
    except ImagePreparationError:
        raise
    except Exception as exc:  # bozuk dosya, desteklenmeyen kodek vb.
        raise ImagePreparationError(f"Görüntü okunamadı: {exc}") from exc

    return PreparedImage(
        data_url=data_url,
        width=size[0],
        height=size[1],
        source_label=f"Kullanıcı yüklemesi ({filename or 'adsız'})",
        is_rendered=False,
        provenance_note=(
            "Kullanıcı tarafından sağlandı. Kökeni ve çekim koşulları "
            "doğrulanmadı; bu görüntüden çıkan gözlemler doğrulanmamış sayılır."
        ),
    )


def prepare_rendered_capture(data: bytes, context: str = "") -> PreparedImage:
    """3B görünümden alınmış kareyi hazırla ve **çizim** olduğunu işaretle."""
    prepared = prepare_uploaded_image(data, filename="3b-goruntu")
    return PreparedImage(
        data_url=prepared.data_url,
        width=prepared.width,
        height=prepared.height,
        source_label="3B görünümden alınan kare (çizim)",
        is_rendered=True,
        provenance_note=(
            "Bu bir gözlemsel görüntü değildir; 3B motor tarafından çizilmiştir. "
            "Görünen aydınlatma, gölge ve kabartma çizim parametrelerinden gelir "
            "ve ölçülmüş yüzey özelliği sayılamaz. " + (context or "")
        ).strip(),
    )
