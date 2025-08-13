"""
Normalizador para cargadores ABB Terra DC.
"""
class ABBTerraDCNormalizer:
    def __init__(self):
        self.name = "ABB Terra DC"

    def normalize_boot_notification(self, payload):
        return payload

    def authorize(self, id_tag):
        return {"status": "Accepted"}
