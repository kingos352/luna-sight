"""Görünürlük durumları, gerekçe kodları ve motor yapılandırması.

Sözleşme (`docs/DATA_CONTRACT.md`) üç durum tanımlar: ``visible``,
``blocked``, ``uncertain``. Eksik ya da yetersiz veri **asla** görünür veya
engelli sınıfına çevrilmez; ``uncertain`` olarak raporlanır ve gerekçe kodu
taşır.
"""

from __future__ import annotations

from dataclasses import dataclass

VISIBLE = "visible"
BLOCKED = "blocked"
UNCERTAIN = "uncertain"

STATES = (VISIBLE, BLOCKED, UNCERTAIN)
DEFINITE_STATES = (VISIBLE, BLOCKED)
"""Geçiş sınırı inceltmesine girebilecek kesin durumlar."""

REASON_CLEAR = "clear"
REASON_OCCLUDED = "occluded"
REASON_TRANSITION = "transition_band"
REASON_MISSING_EPHEMERIS = "missing_ephemeris"
REASON_MISSING_HORIZON = "missing_horizon"
REASON_QUALITY_MISSING = "quality_missing"

REASONS = (
    REASON_CLEAR,
    REASON_OCCLUDED,
    REASON_TRANSITION,
    REASON_MISSING_EPHEMERIS,
    REASON_MISSING_HORIZON,
    REASON_QUALITY_MISSING,
)


@dataclass(frozen=True)
class VisibilityConfig:
    """Sınıflandırma parametreleri; çıktılarda aynen kaydedilir.

    ``margin_deg``
        Ufuk ile hedef yüksekliği arasındaki geçiş bandının yarı genişliği.
        Ufuk profili ve yükseklik verisi belirli bir belirsizlik taşıdığı için
        bu bandın içindeki örnekler ``uncertain`` sayılır. Varsayılan 0.1°;
        güney kutbunda Güneş yüksekliği saatte yaklaşık 0.005–0.015°
        değiştiğinden bu bant kabaca 15–40 saatlik bir belirsizlik penceresine
        karşılık gelir. Bu yüzden duyarlılık analizi yapılmalıdır.
    ``refine_boundaries``
        Kesin durumlar arasındaki geçiş zamanını örnekler arasında doğrusal
        enterpolasyonla incelt.
    ``quality_flag_missing``
        Bu kalite bayrağını taşıyan örnekler doğrudan ``uncertain`` sayılır.
    """

    margin_deg: float = 0.10
    refine_boundaries: bool = True
    quality_flag_missing: str = "missing"

    def __post_init__(self) -> None:
        if self.margin_deg < 0.0:
            raise ValueError("margin_deg negatif olamaz.")

    def as_dict(self) -> dict[str, object]:
        return {
            "margin_deg": self.margin_deg,
            "refine_boundaries": self.refine_boundaries,
            "quality_flag_missing": self.quality_flag_missing,
        }
