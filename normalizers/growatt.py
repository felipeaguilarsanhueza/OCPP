"""
Normalizador para cargadores Growatt.
"""
class GrowattNormalizer:
    def __init__(self):
        self.name = "Growatt"

    def normalize_boot_notification(self, payload):
        # Growatt puede enviar campos con diferencias menores
        return payload

    def authorize(self, id_tag):
        # Simulación de aceptación para pruebas
        return {"status": "Accepted"}
