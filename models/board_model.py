class Puerto:
    """Modelo para representar un puerto PON"""
    
    def __init__(self, puerto: str, total_onts: int, online_onts: int, 
                 puerto_completo: str = None):
        self.puerto = puerto
        self.puerto_completo = puerto_completo or f"0/X/{puerto}"
        self.total_onts = total_onts
        self.online_onts = online_onts
        self.offline_onts = total_onts - online_onts
        self.percentage = round((online_onts / total_onts) * 100) if total_onts > 0 else 0
        self.status = self._calculate_status()
    
    def _calculate_status(self) -> str:
        """Calcula el estado del puerto basado en el porcentaje de ONTs online"""
        if self.percentage >= 70:
            return 'online'
        elif self.percentage >= 30:
            return 'warning'
        else:
            return 'critical'
    
    def is_healthy(self) -> bool:
        """Retorna True si el puerto estÃ¡ en estado saludable"""
        return self.status == 'online'
    
    def needs_attention(self) -> bool:
        """Retorna True si el puerto necesita atenciÃ³n"""
        return self.status in ['warning', 'critical']
    
    def to_dict(self) -> dict:
        """Convierte el objeto a diccionario"""
        return {
            'puerto': self.puerto,
            'puerto_completo': self.puerto_completo,
            'total_onts': self.total_onts,
            'online_onts': self.online_onts,
            'offline_onts': self.offline_onts,
            'percentage': self.percentage,
            'status': self.status
        }


class TarjetaBoard:
    """Modelo para representar una tarjeta con sus puertos"""
    
    def __init__(self, tarjeta: str):
        self.tarjeta = tarjeta
        self.puertos = []
    
    def add_puerto(self, puerto: Puerto):
        """Agrega un puerto a la tarjeta"""
        self.puertos.append(puerto)
    
    def get_estadisticas(self) -> dict:
        """Calcula estadÃ­sticas generales de la tarjeta"""
        total_puertos = len(self.puertos)
        puertos_online = len([p for p in self.puertos if p.status == 'online'])
        puertos_warning = len([p for p in self.puertos if p.status == 'warning'])
        puertos_critical = len([p for p in self.puertos if p.status == 'critical'])
        
        total_onts = sum(p.total_onts for p in self.puertos)
        total_online = sum(p.online_onts for p in self.puertos)
        total_offline = total_onts - total_online
        
        return {
            'total_puertos': total_puertos,
            'puertos_online': puertos_online,
            'puertos_warning': puertos_warning,
            'puertos_critical': puertos_critical,
            'total_onts': total_onts,
            'total_online': total_online,
            'total_offline': total_offline,
            'porcentaje_general': round((total_online / total_onts) * 100) if total_onts > 0 else 0
        }
    
    def get_puertos_criticos(self) -> list:
        """Retorna lista de puertos en estado crÃ­tico"""
        return [p for p in self.puertos if p.status == 'critical']
    
    def get_puertos_warning(self) -> list:
        """Retorna lista de puertos en estado warning"""
        return [p for p in self.puertos if p.status == 'warning']
    
    def to_dict(self) -> dict:
        """Convierte el objeto a diccionario"""
        return {
            'tarjeta': self.tarjeta,
            'puertos': [p.to_dict() for p in self.puertos],
            'estadisticas': self.get_estadisticas()
        }