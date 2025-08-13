"""
Gestor de conexiones a cargadores OCPP.

Este módulo define un `ConnectionManager` que mantiene en memoria las conexiones
activas (cp_id -> instancia de `ChargePoint`) y ofrece utilidades para
interactuar con ellas (consultar conectados, marcar transacciones activas, etc.).
"""
from typing import Optional


class ConnectionManager:
    """Administra conexiones a charge points y su estado en memoria."""
    def __init__(self):
        # Estructura: cp_id -> instancia de ChargePoint
        self.connections: dict[str, object] = {}

    def add(self, cp_id: str, charge_point: object) -> None:
        """Registra una conexión de `ChargePoint` bajo su `cp_id`."""
        self.connections[cp_id] = charge_point

    def remove(self, cp_id: str) -> None:
        """Elimina la conexión de `ChargePoint` asociada al `cp_id`."""
        self.connections.pop(cp_id, None)

    def get(self, cp_id: str) -> Optional[object]:
        """Obtiene la instancia de `ChargePoint` para el `cp_id` dado."""
        return self.connections.get(cp_id)

    def all(self) -> list[str]:
        """Devuelve la lista de todos los `cp_id` actualmente conectados."""
        return list(self.connections.keys())

    # Métodos auxiliares que delegan en ChargePoint

    def set_active_transaction(self, cp_id: str, transaction_id: int) -> None:
        """Marca una transacción como activa en la instancia `ChargePoint`."""
        cp = self.get(cp_id)
        if cp:
            cp.active_transaction = transaction_id

    def clear_active_transaction(self, cp_id: str) -> None:
        """Limpia la transacción activa de la instancia `ChargePoint`."""
        cp = self.get(cp_id)
        if cp:
            cp.active_transaction = None

    def set_pending_remote_start(self, cp_id: str, value: bool) -> None:
        """Indica si hay un arranque remoto pendiente para el cargador."""
        cp = self.get(cp_id)
        if cp:
            cp.pending_remote_start = value

    def set_pending_remote_stop(self, cp_id: str, value: bool) -> None:
        """Indica si hay una parada remota pendiente para el cargador."""
        cp = self.get(cp_id)
        if cp:
            cp.pending_remote_stop = value


# Instancia singleton para usar en toda la aplicación
manager = ConnectionManager()
