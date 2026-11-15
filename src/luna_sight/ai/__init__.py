"""NVIDIA Cosmos3 Nano Reasoner ile görsel yüzey analizi.

Katmanlar ayrıdır ve sorumlulukları karışmaz:

- `client`       NIM uç noktasıyla konuşur, metni taşır
- `imaging`      görüntüyü hazırlar ve kökenini kaydeder
- `schema`       model çıktısını tipli yapıya indirger, doğrular
- `orchestrator` bilimsel ölçümlerle AI gözlemini birleştirir
- `store`        oturumları saklar

Bilimsel bütünlük: sayısal ölçümlerin tek kaynağı doğrulanmış modüllerdir.
Model yorum katmanıdır; ölçüm üretmez, ürettiğini iddia ederse çelişki
olarak işaretlenir.
"""

from luna_sight.ai.client import NimClient, NimConfig, NimError, NimNotConfigured, load_config
from luna_sight.ai.imaging import (
    ImagePreparationError,
    PreparedImage,
    crop_wac_tile,
    prepare_rendered_capture,
    prepare_uploaded_image,
)
from luna_sight.ai.orchestrator import (
    RegionContext,
    analyze_region,
    ask_followup,
    build_messages,
    detect_conflicts,
    load_region_context,
    observation_rows,
)
from luna_sight.ai.schema import (
    MODEL_ID,
    AiAnalysis,
    AnalysisMetadata,
    Observation,
    RegionAnalysis,
    RegionRef,
    ScientificAnalysis,
    normalize_ai_payload,
)

__all__ = [
    "MODEL_ID",
    "AiAnalysis",
    "AnalysisMetadata",
    "ImagePreparationError",
    "NimClient",
    "NimConfig",
    "NimError",
    "NimNotConfigured",
    "Observation",
    "PreparedImage",
    "RegionAnalysis",
    "RegionContext",
    "RegionRef",
    "ScientificAnalysis",
    "analyze_region",
    "ask_followup",
    "build_messages",
    "crop_wac_tile",
    "detect_conflicts",
    "load_config",
    "load_region_context",
    "normalize_ai_payload",
    "observation_rows",
    "prepare_rendered_capture",
    "prepare_uploaded_image",
]
