from .abb_terra_ac import ABBTerraACNormalizer
from .abb_terra_dc import ABBTerraDCNormalizer
from .growatt import GrowattNormalizer
from .base import GenericNormalizer  # <- Nuevo fallback

def get_normalizer(vendor: str, model: str):
    vendor = vendor.lower()
    model = model.lower()

    if "abb" in vendor:
        if "terra" in model and "ac" in model:
            return ABBTerraACNormalizer()
        elif "terra" in model and "dc" in model:
            return ABBTerraDCNormalizer()
        else:
            # Soporte genérico para otros ABB como CDT_TACW22
            return GenericNormalizer()

    elif "growatt" in vendor:
        return GrowattNormalizer()

    # Fallback general para otros fabricantes
    return GenericNormalizer()
