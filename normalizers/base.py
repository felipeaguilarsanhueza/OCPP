"""
Normalizador base para mensajes/formatos de distintos fabricantes.

Define una interfaz mínima que otros normalizadores deben implementar para
autorizar tags y adaptar payloads.
"""
class GenericNormalizer:
    def __init__(self):
        self.whitelist = {"RFID123", "TEST123", "USER456","7A519560","NO.000000333526"}

    def authorize(self, id_tag):
        if id_tag in self.whitelist:
            return {"status": "Accepted"}
        return {"status": "Invalid"}
