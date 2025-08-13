"""
Normalizador para cargadores ABB Terra AC.
"""
class ABBTerraACNormalizer:
    def __init__(self):
        # Puedes cargar configuraciones específicas aquí si lo deseas
        self.name = "ABB Terra AC"

    def normalize_boot_notification(self, payload):
        # Adaptación específica si ABB Terra AC reporta campos distintos
        return payload

    def authorize(self, id_tag):
        # Lógica personalizada para ABB Terra AC
        return {"status": "Accepted"}
