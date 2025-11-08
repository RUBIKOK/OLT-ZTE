from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ONT:
    """Modelo de datos para una ONT"""
    id: str
    tarjeta: str
    puerto: str
    ont_rx: Optional[float] = None
    olt_rx: Optional[float] = None
    rx_diff: Optional[float] = None
    temperature: Optional[int] = None
    distance: Optional[int] = None
    estado: str = ""
    last_down_time: str = ""
    last_down_cause: str = ""
    descripcion: str = ""
    
    def __post_init__(self):
        """Calcula la diferencia RX después de la inicialización"""
        if self.ont_rx is not None and self.olt_rx is not None:
            self.rx_diff = round(self.olt_rx - self.ont_rx, 2)
    
    def is_online(self) -> bool:
        """Verifica si la ONT está online"""
        return self.estado.lower() == 'online'
    
    def has_critical_rx_diff(self) -> bool:
        """Verifica si la diferencia RX es crítica (< -5.00)"""
        return self.rx_diff is not None and self.rx_diff < -5.00
    
    def to_dict(self) -> dict:
        """Convierte la ONT a diccionario para templates"""
        return {
            'id': self.id,
            'tarjeta': self.tarjeta,
            'puerto': self.puerto,
            'ont_rx': self.ont_rx,
            'olt_rx': self.olt_rx,
            'rx_diff': self.rx_diff,
            'temperature': self.temperature,
            'distance': self.distance,
            'estado': self.estado,
            'last_down_time': self.last_down_time,
            'last_down_cause': self.last_down_cause,
            'descripcion': self.descripcion,
            'is_online': self.is_online(),
            'has_critical_rx_diff': self.has_critical_rx_diff()
        }

class ONTCollection:
    """Colección de ONTs con métodos de utilidad"""
    
    def __init__(self, onts: List[ONT] = None):
        self.onts = onts or []
    
    def add_ont(self, ont: ONT):
        """Agrega una ONT a la colección"""
        self.onts.append(ont)
    
    def extend(self, other_collection):
        self.onts.extend(other_collection.onts)
        
    def get_total_count(self) -> int:
        """Retorna el total de ONTs"""
        return len(self.onts)
    
    def get_online_count(self) -> int:
        """Retorna el número de ONTs online"""
        return sum(1 for ont in self.onts if ont.is_online())
    
    def get_critical_count(self) -> int:
        """Retorna el número de ONTs con RX crítico"""
        return sum(1 for ont in self.onts if ont.has_critical_rx_diff())
    
    def to_dict_list(self) -> List[dict]:
        """Convierte todas las ONTs a lista de diccionarios"""
        return [ont.to_dict() for ont in self.onts]
    
    def get_summary(self) -> dict:
        """Retorna un resumen de la colección"""
        return {
            'total_onts': self.get_total_count(),
            'online_onts': self.get_online_count(),
            'critical_onts': self.get_critical_count()
        }