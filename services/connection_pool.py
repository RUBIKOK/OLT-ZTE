# services/connection_pool.py - VERSIÓN CORREGIDA

import threading
import time
import uuid
from typing import Dict, Optional
from netmiko import ConnectHandler
import logging

logger = logging.getLogger(__name__)

class ConnectionPool:
    """Pool de conexiones SSH independientes por sesión"""
    
    def __init__(self, device_config: dict, max_idle_time: int = 300):
        self.device_config = device_config
        self.max_idle_time = max_idle_time  # 5 minutos por defecto
        self.connections: Dict[str, Dict] = {}
        self.lock = threading.Lock()
        
        # ============ CORRECCIÓN 1: Control del hilo de limpieza ============
        self.cleanup_running = True
        
        # Hilo de limpieza de conexiones inactivas
        self.cleanup_thread = threading.Thread(target=self._cleanup_inactive_connections, daemon=True)
        self.cleanup_thread.start()
        logger.info(f"Pool de conexiones inicializado. Max idle time: {max_idle_time}s")
    
    def get_connection(self, session_id: str) -> 'SessionConnection':
        """Obtiene o crea una conexión para la sesión especificada"""
        with self.lock:
            if session_id not in self.connections:
                logger.info(f"Creando nueva entrada para sesión {session_id}")
                self.connections[session_id] = {
                    'connection': None,
                    'last_used': time.time(),
                    'current_context': 'global',
                    'created_at': time.time(),
                    'connection_attempts': 0,
                    'last_error': None
                }
            else:
                # Actualizar último uso
                self.connections[session_id]['last_used'] = time.time()
        
        return SessionConnection(self, session_id)
    
    def _get_ssh_connection(self, session_id: str) -> ConnectHandler:
        """Obtiene la conexión SSH real, creándola si es necesario"""
        session_data = self.connections[session_id]
        
        # ============ CORRECCIÓN 2: Verificación mejorada de conexión ============
        if session_data['connection'] is None or not self._is_connection_alive(session_data['connection']):
            logger.info(f"Estableciendo nueva conexión SSH para sesión {session_id}")
            
            try:
                # Incrementar contador de intentos
                session_data['connection_attempts'] += 1
                
                # ============ CORRECCIÓN 3: Configuración mejorada de conexión ============
                connection_config = self.device_config.copy()
                
                # Ajustar timeouts si hay muchos intentos fallidos
                if session_data['connection_attempts'] > 1:
                    connection_config['timeout'] = min(connection_config.get('timeout', 30) + 10, 60)
                    connection_config['auth_timeout'] = min(connection_config.get('auth_timeout', 10) + 5, 30)
                    logger.info(f"Intento {session_data['connection_attempts']} para sesión {session_id}, aumentando timeouts")
                
                session_data['connection'] = ConnectHandler(**connection_config)
                self._initialize_connection(session_data['connection'])
                session_data['current_context'] = 'config'
                session_data['last_error'] = None
                
                logger.info(f"Conexión SSH establecida exitosamente para sesión {session_id}")
                
            except Exception as e:
                session_data['last_error'] = str(e)
                logger.error(f"Error estableciendo conexión SSH para sesión {session_id}: {e}")
                
                # ============ CORRECCIÓN 4: Límite de intentos de reconexión ============
                if session_data['connection_attempts'] >= 3:
                    logger.error(f"Máximo de intentos alcanzado para sesión {session_id}")
                    raise Exception(f"No se pudo establecer conexión después de {session_data['connection_attempts']} intentos: {e}")
                
                raise
        
        return session_data['connection']
    
    def _is_connection_alive(self, connection: ConnectHandler) -> bool:
        """Verifica si una conexión está viva de manera más robusta"""
        if connection is None:
            return False
        
        try:
            # ============ CORRECCIÓN 5: Verificación mejorada de conexión ============
            # Método más confiable para verificar la conexión
            if hasattr(connection, 'remote_conn') and connection.remote_conn:
                # Intentar enviar un comando simple y rápido
                connection.write_channel("\n")
                time.sleep(0.1)
                output = connection.read_channel()
                return True
            else:
                return False
        except Exception as e:
            logger.debug(f"Conexión no está viva: {e}")
            return False
    
    def _initialize_connection(self, connection: ConnectHandler):
        """Inicializa la conexión con los comandos necesarios"""
        try:
            # ============ CORRECCIÓN 6: Inicialización más robusta ============
            logger.debug("Inicializando conexión SSH...")
            
            # Entrar en modo privilegiado
            # connection.write_channel("enable\n")
            # time.sleep(1)
            # output = connection.read_channel()
            
            # Verificar si necesita password para enable
            # if "Password:" in output:
            #     enable_secret = self.device_config.get('secret', '')
            #     if enable_secret:
            #         connection.write_channel(f"{enable_secret}\n")
            #         time.sleep(1)
            #     else:
            #         logger.warning("Se requiere secret para enable pero no está configurado")
            
            # Entrar en modo configuración
            connection.write_channel("configure terminal\n")
            time.sleep(1)
            output = connection.read_channel()
            
            # Verificar que estamos en modo config
            if not ("#" in output and ")" in output):
                logger.warning("Posible problema entrando en modo config")
            
            # Configurar terminal para evitar paginación
            connection.write_channel("screen-length 0 temporary\n")
            time.sleep(0.5)
            connection.read_channel()
            
            logger.debug("Conexión inicializada correctamente")
            
        except Exception as e:
            logger.error(f"Error inicializando conexión: {e}")
            raise
    
    def disconnect_session(self, session_id: str):
        """Desconecta una sesión específica"""
        with self.lock:
            if session_id in self.connections:
                session_data = self.connections[session_id]
                if session_data['connection'] and self._is_connection_alive(session_data['connection']):
                    try:
                        # ============ CORRECCIÓN 7: Desconexión más cuidadosa ============
                        # Salir de cualquier interfaz antes de desconectar
                        if session_data['current_context'].startswith("interface"):
                            session_data['connection'].write_channel("quit\n")
                            time.sleep(0.5)
                            session_data['connection'].read_channel()
                        
                        # Salir del modo config
                        session_data['connection'].write_channel("quit\n")
                        time.sleep(0.5)
                        session_data['connection'].read_channel()
                        
                        # Cerrar conexión
                        session_data['connection'].disconnect()
                        logger.info(f"Conexión cerrada correctamente para sesión {session_id}")
                        
                    except Exception as e:
                        logger.warning(f"Error cerrando conexión para sesión {session_id}: {e}")
                
                del self.connections[session_id]
                logger.info(f"Sesión {session_id} eliminada del pool")
    
    def _cleanup_inactive_connections(self):
        """Limpia conexiones inactivas en segundo plano"""
        logger.info("Hilo de limpieza de conexiones iniciado")
        
        while self.cleanup_running:
            try:
                current_time = time.time()
                inactive_sessions = []
                
                with self.lock:
                    for session_id, session_data in self.connections.items():
                        idle_time = current_time - session_data['last_used']
                        
                        # ============ CORRECCIÓN 8: Limpieza más inteligente ============
                        # Marcar como inactiva si excede el tiempo límite
                        if idle_time > self.max_idle_time:
                            inactive_sessions.append((session_id, idle_time))
                        
                        # También limpiar sesiones con conexiones muertas después de mucho tiempo
                        elif idle_time > 60 and session_data['connection']:
                            if not self._is_connection_alive(session_data['connection']):
                                inactive_sessions.append((session_id, idle_time))
                                logger.info(f"Sesión {session_id} marcada para limpieza (conexión muerta)")
                
                # Desconectar sesiones inactivas fuera del lock
                for session_id, idle_time in inactive_sessions:
                    logger.info(f"Limpiando conexión inactiva para sesión {session_id} (inactiva por {idle_time:.1f}s)")
                    self.disconnect_session(session_id)
                
                # Log periódico del estado
                if len(self.connections) > 0:
                    logger.debug(f"Pool status: {len(self.connections)} conexiones activas")
                
                time.sleep(30)  # Verificar cada 30 segundos (más frecuente)
                
            except Exception as e:
                logger.error(f"Error en limpieza de conexiones: {e}")
                time.sleep(60)
    
    def get_active_connections_count(self) -> int:
        """Retorna el número de conexiones activas"""
        with self.lock:
            return len(self.connections)
    
    def get_session_context(self, session_id: str) -> str:
        """Retorna el contexto actual de una sesión"""
        with self.lock:
            if session_id in self.connections:
                return self.connections[session_id]['current_context']
        return 'global'
    
    def set_session_context(self, session_id: str, context: str):
        """Establece el contexto de una sesión"""
        with self.lock:
            if session_id in self.connections:
                self.connections[session_id]['current_context'] = context

    # ============ CORRECCIÓN 9: Métodos adicionales para diagnóstico ============
    def get_session_info(self, session_id: str) -> Dict:
        """Retorna información detallada de una sesión"""
        with self.lock:
            if session_id in self.connections:
                session_data = self.connections[session_id].copy()
                session_data['is_alive'] = self._is_connection_alive(session_data['connection'])
                session_data['idle_time'] = time.time() - session_data['last_used']
                return session_data
        return {}

    def cleanup(self):
        """Limpia todos los recursos del pool"""
        logger.info("Iniciando limpieza completa del pool de conexiones")
        self.cleanup_running = False
        
        # Esperar un poco para que termine el hilo de limpieza
        if self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=5)
        
        # Cerrar todas las conexiones
        sessions_to_disconnect = list(self.connections.keys())
        for session_id in sessions_to_disconnect:
            self.disconnect_session(session_id)
        
        logger.info("Pool de conexiones limpiado completamente")


class SessionConnection:
    """Wrapper para una conexión específica de sesión"""
    
    def __init__(self, pool: ConnectionPool, session_id: str):
        self.pool = pool
        self.session_id = session_id
    
    @property
    def current_context(self) -> str:
        return self.pool.get_session_context(self.session_id)
    
    def connect(self) -> ConnectHandler:
        """Establece y mantiene la conexión SSH"""
        return self.pool._get_ssh_connection(self.session_id)
    
    def execute_command(self, command: str, delay_factor: int = 1, timeout: int = 20) -> str:
        """Ejecuta un comando y retorna la salida"""
        try:
            conn = self.connect()
            
            # ============ CORRECCIÓN 10: Ejecución más robusta de comandos ============
            logger.debug(f"Ejecutando comando en sesión {self.session_id}: {command}")
            
            result = conn.send_command(
                command,
                delay_factor=delay_factor,
                expect_string=r"#",
                read_timeout=timeout,
                strip_prompt=True,
                strip_command=True
            )
            
            # Actualizar último uso
            with self.pool.lock:
                if self.session_id in self.pool.connections:
                    self.pool.connections[self.session_id]['last_used'] = time.time()
            
            logger.debug(f"Comando ejecutado exitosamente (longitud respuesta: {len(result)})")
            return result
            
        except Exception as e:
            logger.error(f"Error ejecutando comando '{command}' en sesión {self.session_id}: {e}")
            raise
    
    def execute_global_command(self, command: str, delay_factor: int = 1, timeout: int = 20) -> str:
        """Ejecuta un comando en contexto global"""
        try:
            conn = self.connect()
            
            # Si estamos en una interfaz específica, salir al modo config global
            if self.current_context.startswith("interface"):
                logger.info(f"Saliendo del contexto {self.current_context} al modo config global")
                conn.write_channel("exit\n")
                time.sleep(0.5)
                conn.read_channel()
                self.pool.set_session_context(self.session_id, "config")
            
            # Ejecutar el comando
            result = self.execute_command(command, delay_factor, timeout)
            return result
            
        except Exception as e:
            logger.error(f"Error ejecutando comando global '{command}' en sesión {self.session_id}: {e}")
            raise
    
    def enter_interface(self, tarjeta: str):
        """Entra a la interfaz GPON especificada"""
        try:
            conn = self.connect()
            
            # ============ CORRECCIÓN 11: Manejo mejorado de interfaces ============
            interface_name = f"gpon-0/{tarjeta}"
            target_context = f"interface-{interface_name}"
            
            # Si ya estamos en la interfaz correcta, no hacer nada
            if self.current_context == target_context:
                logger.debug(f"Ya en interfaz {interface_name}")
                return
            
            # Si estamos en una interfaz diferente, salir primero
            if self.current_context.startswith("interface"):
                logger.info(f"Saliendo del contexto actual: {self.current_context}")
                conn.write_channel("quit\n")
                time.sleep(0.5)
                conn.read_channel()
                self.pool.set_session_context(self.session_id, "config")
            
            # Entrar a la interfaz específica
            logger.info(f"Entrando a interfaz gpon 0/{tarjeta} en sesión {self.session_id}")
            conn.write_channel(f"interface gpon 0/{tarjeta}\n")
            time.sleep(1)
            output = conn.read_channel()
            
            # Verificar que entramos correctamente
            if "#" in output:
                self.pool.set_session_context(self.session_id, target_context)
                logger.debug(f"Contexto cambiado a {target_context}")
            else:
                logger.warning(f"Posible problema entrando a interfaz {interface_name}")
                raise Exception(f"No se pudo entrar a la interfaz gpon 0/{tarjeta}")
                
        except Exception as e:
            logger.error(f"Error entrando a interfaz gpon 0/{tarjeta} en sesión {self.session_id}: {e}")
            raise
    
    def exit_interface(self):
        """Sale de la interfaz actual y vuelve al modo config"""
        try:
            if self.current_context.startswith("interface"):
                conn = self.connect()
                logger.info(f"Saliendo del contexto {self.current_context} en sesión {self.session_id}")
                conn.write_channel("quit\n")
                time.sleep(0.5)
                output = conn.read_channel()
                
                # Verificar que salimos correctamente
                if ")" in output and "#" in output:
                    self.pool.set_session_context(self.session_id, "config")
                    logger.debug("Regresado a modo config")
                else:
                    logger.warning("Posible problema saliendo de interfaz")
                    
        except Exception as e:
            logger.error(f"Error saliendo de interfaz en sesión {self.session_id}: {e}")
            raise
    
    def ensure_config_mode(self):
        """Asegura que estemos en modo config global"""
        try:
            # Si estamos en una interfaz, salir
            if self.current_context.startswith("interface"):
                logger.info(f"Asegurando modo config global en sesión {self.session_id}")
                self.exit_interface()
                
        except Exception as e:
            logger.error(f"Error asegurando modo config en sesión {self.session_id}: {e}")
            raise
    
    def get_current_context(self) -> str:
        """Retorna el contexto actual de la conexión"""
        return self.current_context
    
    # ============ CORRECCIÓN 12: Métodos adicionales útiles ============
    def test_connection(self) -> bool:
        """Prueba la conexión ejecutando un comando simple"""
        try:
            conn = self.connect()
            conn.write_channel("\n")
            time.sleep(0.2)
            output = conn.read_channel()
            return "#" in output or ">" in output
        except Exception as e:
            logger.debug(f"Test de conexión falló: {e}")
            return False
    
    def get_session_info(self) -> Dict:
        """Retorna información de la sesión"""
        return self.pool.get_session_info(self.session_id)
    
    def disconnect(self):
        """Cierra la conexión de esta sesión"""
        self.pool.disconnect_session(self.session_id)