# core/connection_registry.py

connected_charge_points = {}

def register(cp_id, charge_point):
    connected_charge_points[cp_id] = charge_point

def get(cp_id):
    return connected_charge_points.get(cp_id)

def unregister(cp_id):
    connected_charge_points.pop(cp_id, None)

def list_connected():
    return list(connected_charge_points.keys())
