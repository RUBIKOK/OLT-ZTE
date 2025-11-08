from netmiko import ConnectHandler
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class ConnectionService:
    """Servicio para manejar la conexión SSH al dispositivo"""
    
    def __init__(self, device_config: dict):
        self.device_config = device_config
        self.connection: Optional[ConnectHandler] = None
        self.current_context = "global"  # Rastrear el contexto actual
    
    def connect(self) -> ConnectHandler:
        """Establece y mantiene la conexión SSH"""
        try:
            if self.connection is None or not self.connection.is_alive():
                logger.info("Estableciendo nueva conexión SSH")
                self.connection = ConnectHandler(**self.device_config)
                self._initialize_connection()
                self.current_context = "config"  # Después de inicializar estamos en modo config
            return self.connection
        except Exception as e:
            logger.error(f"Error estableciendo conexión: {e}")
            raise
    
    def _initialize_connection(self):
        """Inicializa la conexión con los comandos necesarios"""
        self.connection.write_channel("enable\n")
        self.connection.read_until_pattern(r"#")
        self.connection.write_channel("config\n")
        self.connection.read_until_pattern(r"\)")
    
    def execute_command(self, command: str, delay_factor: int = 1, timeout: int = 20) -> str:
        """Ejecuta un comando y retorna la salida"""
        try:
            conn = self.connect()
            return conn.send_command(
                command,
                delay_factor=delay_factor,
                expect_string=r"#",
                read_timeout=timeout
            )
        except Exception as e:
            logger.error(f"Error ejecutando comando '{command}': {e}")
            raise
    
    def execute_global_command(self, command: str, delay_factor: int = 1, timeout: int = 20) -> str:
        """Ejecuta un comando en contexto global (saliendo de cualquier interfaz)"""
        try:
            conn = self.connect()
            
            # Si estamos en una interfaz específica, salir al modo config global
            if self.current_context.startswith("interface"):
                logger.info(f"Saliendo del contexto {self.current_context} al modo config global")
                conn.write_channel("quit\n")
                conn.read_until_pattern(r"\)#")
                self.current_context = "config"
            
            # Ejecutar el comando
            result = conn.send_command(
                command,
                delay_factor=delay_factor,
                expect_string=r"#",
                read_timeout=timeout
            )
            
            return result
        except Exception as e:
            logger.error(f"Error ejecutando comando global '{command}': {e}")
            raise
    
    def enter_interface(self, tarjeta: str):
        """Entra a la interfaz GPON especificada"""
        try:
            conn = self.connect()
            
            # Si ya estamos en una interfaz diferente, salir primero
            interface_name = f"gpon-0/{tarjeta}"
            if self.current_context.startswith("interface") and self.current_context != f"interface-{interface_name}":
                logger.info(f"Saliendo del contexto actual: {self.current_context}")
                conn.write_channel("quit\n")
                conn.read_until_pattern(r"\)#")
                self.current_context = "config"
            
            # Entrar a la interfaz específica
            if self.current_context != f"interface-{interface_name}":
                logger.info(f"Entrando a interfaz gpon 0/{tarjeta}")
                conn.write_channel(f"interface gpon 0/{tarjeta}\n")
                conn.read_until_pattern(r"#")
                self.current_context = f"interface-{interface_name}"
                
        except Exception as e:
            logger.error(f"Error entrando a interfaz gpon 0/{tarjeta}: {e}")
            raise
    
    def exit_interface(self):
        """Sale de la interfaz actual y vuelve al modo config"""
        try:
            if self.current_context.startswith("interface"):
                conn = self.connect()
                logger.info(f"Saliendo del contexto {self.current_context}")
                conn.write_channel("quit\n")
                conn.read_until_pattern(r"\)#")
                self.current_context = "config"
        except Exception as e:
            logger.error(f"Error saliendo de interfaz: {e}")
            raise
    
    def ensure_config_mode(self):
        """Asegura que estemos en modo config global"""
        try:
            conn = self.connect()
            
            # Si estamos en una interfaz, salir
            if self.current_context.startswith("interface"):
                logger.info("Asegurando modo config global")
                conn.write_channel("quit\n")
                conn.read_until_pattern(r"\)#")
                self.current_context = "config"
                
        except Exception as e:
            logger.error(f"Error asegurando modo config: {e}")
            raise
    
    def get_current_context(self) -> str:
        """Retorna el contexto actual de la conexión"""
        return self.current_context
    
    def disconnect(self):
        """Cierra la conexión"""
        if self.connection and self.connection.is_alive():
            try:
                # Salir de cualquier interfaz antes de desconectar
                if self.current_context.startswith("interface"):
                    self.connection.write_channel("quit\n")
                    self.connection.read_until_pattern(r"\)#")
                
                self.connection.disconnect()
                logger.info("Conexión cerrada correctamente")
            except Exception as e:
                logger.error(f"Error cerrando conexión: {e}")
            finally:
                self.connection = None
                self.current_context = "global"