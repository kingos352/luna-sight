"""
backend/flight_physics/seu_tmr_shield.py
========================================
Radyasyon SEU (Single Event Upset) Kalkanı ve Yazılımsal TMR (Triple Modular Redundancy).

Gereksinim:
- Kozmik ışın bit-çevirme (bit-flip) enjeksiyon simülatörü
- Yazılımsal TMR (Üçlü Modüler Oylama) aviyonik güvenilirlik kalkanı

Uzay Ortamı Arka Planı:
Dünya manyetosferinin dışındaki Ay Güney Kutbu ortamında, Galaktik Kozmik Işınlar (GCR)
ve Güneş Parçacık Olayları (SPE) sebebiyle CMOS RAM hücrelerinde ve aviyonik CPU
yazmaçlarında tekil bit çevrilmeleri (Single Event Upset - SEU) meydana gelir.
Yazılımsal TMR, kritik iniş parametrelerini 3 bağımsız kopyada saklar ve çoğunluk
oylaması (majority voting) ile bit-flip hatalarını anında onarır.
"""

from __future__ import annotations
import copy
import math
import random
import struct
from typing import Any, Dict, Generic, List, Optional, Tuple, TypeVar

T = TypeVar("T")


def flip_float_bit(value: float, bit_index: int) -> float:
    """
    IEEE 754 64-bit float değerin belirtilen bitini (0-63) tersine çevirir (SEU simülasyonu).
    """
    bit_idx = max(0, min(63, bit_index))
    # Double precision float -> 64-bit unsigned int
    packed = struct.pack(">d", float(value))
    raw_int = struct.unpack(">Q", packed)[0]
    flipped_int = raw_int ^ (1 << bit_idx)
    unpacked_bytes = struct.pack(">Q", flipped_int)
    corrupted_float = struct.unpack(">d", unpacked_bytes)[0]
    return corrupted_float


def flip_int_bit(value: int, bit_index: int) -> int:
    """32-bit tamsayı değerin belirtilen bitini (0-31) tersine çevirir."""
    bit_idx = max(0, min(31, bit_index))
    return int(value ^ (1 << bit_idx))


class TMRVariable(Generic[T]):
    """
    Kritik aviyonik parametreler için Üçlü Modüler Oylamalı (TMR) koruma sınıfı.
    Değeri 3 bağımsız bellek kopyasında tutar, her okumada çoğunluk oylaması yapar
    ve hasarlı kopyayı otomatik olarak onarır (self-healing scrub).
    """

    def __init__(self, initial_value: T, name: str = "TMR_VAR"):
        self.name = name
        self.copy_a: T = copy.deepcopy(initial_value)
        self.copy_b: T = copy.deepcopy(initial_value)
        self.copy_c: T = copy.deepcopy(initial_value)
        self.correction_count: int = 0
        self.critical_fault_count: int = 0

    def set(self, new_value: T) -> None:
        """Yeni değeri her üç kopyaya da yazar."""
        self.copy_a = copy.deepcopy(new_value)
        self.copy_b = copy.deepcopy(new_value)
        self.copy_c = copy.deepcopy(new_value)

    def get(self) -> T:
        """
        Çoğunluk oylaması (Majority Voting) ile güvenli değeri döner.
        Bir kopyada bit-flip tespit edilirse anında çoğunluk değeriyle onarılır.
        """
        val, _ = self.vote_and_repair()
        return val

    def vote_and_repair(self) -> Tuple[T, bool]:
        """
        Oylama yapar, bit bozulması varsa onarır ve (değer, onarım_yapıldı_mı) ikilisini döner.
        """
        a = self.copy_a
        b = self.copy_b
        c = self.copy_c

        # Sayısal karşılaştırmalar için float hassasiyeti kontrolü
        eq_ab = self._equals(a, b)
        eq_bc = self._equals(b, c)
        eq_ca = self._equals(c, a)

        # 1. Durum: Tüm kopyalar sağlıklı
        if eq_ab and eq_bc:
            return a, False

        # 2. Durum: Copy C bozulmuş (A == B, C farklı)
        if eq_ab:
            self.copy_c = copy.deepcopy(a)
            self.correction_count += 1
            return a, True

        # 3. Durum: Copy B bozulmuş (A == C, B farklı)
        if eq_ca:
            self.copy_b = copy.deepcopy(a)
            self.correction_count += 1
            return a, True

        # 4. Durum: Copy A bozulmuş (B == C, A farklı)
        if eq_bc:
            self.copy_a = copy.deepcopy(b)
            self.correction_count += 1
            return b, True

        # 5. Kritik Durum: 3 kopya da birbirinden farklı (Çoklu SEU Felaketi)
        self.critical_fault_count += 1
        return a, False

    def corrupt_copy(self, copy_letter: str = "A", bit_index: int = 12) -> None:
        """Test/simülasyon amacıyla seçilen kopyaya bit-flip enjekte eder."""
        target = copy_letter.upper()
        if target == "A":
            self.copy_a = self._corrupt_val(self.copy_a, bit_index)
        elif target == "B":
            self.copy_b = self._corrupt_val(self.copy_b, bit_index)
        elif target == "C":
            self.copy_c = self._corrupt_val(self.copy_c, bit_index)
        else:
            raise ValueError("Kopya harfi 'A', 'B' veya 'C' olmalıdır.")

    def _corrupt_val(self, val: Any, bit_index: int) -> Any:
        if isinstance(val, float):
            return flip_float_bit(val, bit_index)
        elif isinstance(val, int) and not isinstance(val, bool):
            return flip_int_bit(val, bit_index)
        else:
            # Diğer tipler için sembolik bozulma
            return None

    def _equals(self, v1: Any, v2: Any) -> bool:
        if isinstance(v1, float) and isinstance(v2, float):
            if math.isnan(v1) and math.isnan(v2):
                return True
            if math.isnan(v1) or math.isnan(v2):
                return False
            # SEU radyasyon kalkanı için IEEE 754 bit-seviyesinde tam eşitlik
            return struct.pack(">d", v1) == struct.pack(">d", v2)
        return bool(v1 == v2)

    def get_status(self) -> Dict[str, Any]:
        """TMR durum raporu."""
        return {
            "name": self.name,
            "copy_a": self.copy_a,
            "copy_b": self.copy_b,
            "copy_c": self.copy_c,
            "correction_count": self.correction_count,
            "critical_fault_count": self.critical_fault_count,
            "healthy": bool(self.copy_a == self.copy_b == self.copy_c),
        }


class SEUInjector:
    """
    Radyasyon ve kozmik ışın bit-flip simülatörü.
    Güneş fırtınası (SPE) veya sakin uzay koşullarına göre stokastik bit bozulması üretir.
    """

    def __init__(self, seed: Optional[int] = 42):
        self.rng = random.Random(seed)

    def simulate_flux_hit(self, storm_level: str = "QUIET") -> bool:
        """
        Seçilen radyasyon seviyesine göre tek bir döngüde SEU vuruşu olasılığı:
        QUIET: 1% | MODERATE: 8% | SOLAR_STORM: 35%
        """
        probs = {
            "QUIET": 0.01,
            "MODERATE": 0.08,
            "SOLAR_STORM": 0.35,
        }
        p = probs.get(storm_level.upper(), 0.05)
        return self.rng.random() < p

    def inject_random_seu(self, tmr_var: TMRVariable, copy_target: Optional[str] = None) -> Dict[str, Any]:
        """TMR değişkenine rastgele bir bit-flip enjekte eder."""
        target_copy = copy_target if copy_target else self.rng.choice(["A", "B", "C"])
        bit_idx = self.rng.randint(0, 50)
        tmr_var.corrupt_copy(target_copy, bit_index=bit_idx)
        return {
            "target_var": tmr_var.name,
            "corrupted_copy": target_copy,
            "bit_index": bit_idx,
        }


class SEUProtectedState:
    """
    Tüm iniş aviyonik durum vektörünü TMR ile kalkanlayan ana durum sınıfı.
    """

    def __init__(self):
        self.alt_m = TMRVariable[float](3200.0, name="altitude_m")
        self.v_horizontal_ms = TMRVariable[float](62.0, name="v_horizontal_ms")
        self.v_vertical_ms = TMRVariable[float](-28.0, name="v_vertical_ms")
        self.target_x = TMRVariable[float](0.50, name="target_norm_x")
        self.target_y = TMRVariable[float](0.50, name="target_norm_y")
        self.thrust_pct = TMRVariable[float](75.0, name="thrust_pct")

    def run_health_check_and_scrub(self) -> Dict[str, Any]:
        """Tüm kayıtları tarar, bit-flip varsa çoğunluk oylamasıyla temizler (Memory Scrubbing)."""
        corrections = 0
        vars_checked = [
            self.alt_m,
            self.v_horizontal_ms,
            self.v_vertical_ms,
            self.target_x,
            self.target_y,
            self.thrust_pct,
        ]
        status_list = []
        for var in vars_checked:
            val, repaired = var.vote_and_repair()
            if repaired:
                corrections += 1
            status_list.append(var.get_status())

        return {
            "total_vars": len(vars_checked),
            "repaired_in_scrub": corrections,
            "variables": status_list,
        }
