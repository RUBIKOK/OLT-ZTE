# services/session_connection.py
import paramiko
import time
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class SessionConnection:
    """Conexión SSH para OLT ZTE ZXROS"""
    
    def __init__(self, host: str, username: str, password: str, 
                 port: int = 22, device_type: str = 'zte_zxros'):
        """
        Args:
            host: Dirección IP de la OLT
            username: Usuario SSH
            password: Contraseña SSH
            port: Puerto SSH (default 22)
            device_type: Tipo de dispositivo (siempre zte_zxros)
        """
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.device_type = device_type
        
        self.client: Optional[paramiko.SSHClient] = None
        self.shell: Optional[paramiko.Channel] = None
        self.session_id = f"{host}:{port}"
        self._connected = False
        self._in_config_mode = False
        self._in_interface_mode = False
        self.current_interface = None
        
    def connect(self) -> bool:
        """Establece conexión SSH con la OLT"""
        try:
            logger.info(f"Conectando a OLT ZTE {self.host}:{self.port}")
            
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Conectar con timeout
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=30,
                allow_agent=False,
                look_for_keys=False
            )
            
            # Obtener shell interactiva
            self.shell = self.client.invoke_shell(width=200, height=1000)
            self.shell.settimeout(30)
            
            # Esperar prompt inicial
            time.sleep(2)
            output = self._read_until_prompt()
            
            # Verificar conexión exitosa
            if '>' in output or '#' in output:
                self._connected = True
                logger.info(f"Conexión exitosa a {self.host}")
                
                # Configuración inicial
                self._disable_paging()
                self._set_terminal_width()
                
                return True
            else:
                logger.error(f"No se detectó prompt en {self.host}")
                return False
                
        except paramiko.AuthenticationException:
            logger.error(f"Error de autenticación en {self.host}")
            raise
        except paramiko.SSHException as e:
            logger.error(f"Error SSH en {self.host}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error conectando a {self.host}: {e}")
            raise
    
    def _disable_paging(self):
        """Deshabilita paginación en la OLT"""
        try:
            self.shell.send("terminal length 0\n")
            time.sleep(1)
            self._read_until_prompt()
            logger.debug("Paginación deshabilitada")
        except Exception as e:
            logger.warning(f"No se pudo deshabilitar paginación: {e}")
    
    def _set_terminal_width(self, width: int = 512):
        """Configura ancho de terminal"""
        try:
            self.shell.send(f"terminal width {width}\n")
            time.sleep(1)
            self._read_until_prompt()
            logger.debug(f"Ancho terminal configurado a {width}")
        except Exception as e:
            logger.warning(f"No se pudo configurar ancho terminal: {e}")
    
    def _read_until_prompt(self, timeout: int = 30) -> str:
        """
        Lee la salida hasta encontrar el prompt
        
        Args:
            timeout: Timeout en segundos
            
        Returns:
            str: Salida completa hasta el prompt
        """
        output = ""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                if self.shell.recv_ready():
                    data = self.shell.recv(65535).decode('utf-8', errors='ignore')
                    output += data
                    
                    # Buscar prompt de ZTE (termina con > o #)
                    lines = output.split('\n')
                    last_line = lines[-1].strip() if lines else ""
                    
                    # Prompts comunes de ZTE
                    if last_line.endswith('>') or last_line.endswith('#'):
                        break
                    if '>' in last_line or '#' in last_line:
                        # Extraer última línea completa
                        for line in reversed(lines):
                            if line.strip().endswith(('>', '#')):
                                break
                else:
                    time.sleep(0.1)
            except Exception as e:
                logger.warning(f"Error leyendo datos: {e}")
                break
        
        return output
    
    def execute_command(self, command: str, delay_factor: float = 1.0, 
                       timeout: int = 30) -> str:
        """
        Ejecuta un comando en la OLT
        
        Args:
            command: Comando a ejecutar
            delay_factor: Factor de delay (1.0 = normal, 2.0 = más lento)
            timeout: Timeout en segundos
            
        Returns:
            str: Salida del comando
        """
        if not self._connected or not self.shell:
            raise ConnectionError("No hay conexión activa")
        
        try:
            # Limpiar buffer
            self._clear_buffer()
            
            # Enviar comando
            logger.debug(f"Ejecutando: {command}")
            self.shell.send(command + "\n")
            
            # Delay según factor
            time.sleep(0.5 * delay_factor)
            
            # Leer salida
            output = self._read_until_prompt(timeout)
            
            # Remover el comando del output
            lines = output.split('\n')
            if lines and command in lines[0]:
                output = '\n'.join(lines[1:])
            
            return output.strip()
            
        except Exception as e:
            logger.error(f"Error ejecutando comando '{command}': {e}")
            raise
    
    def execute_global_command(self, command: str, delay_factor: float = 1.0,
                              timeout: int = 30) -> str:
        """
        Ejecuta un comando en modo global (asegura estar en modo config si es necesario)
        
        Args:
            command: Comando a ejecutar
            delay_factor: Factor de delay
            timeout: Timeout en segundos
            
        Returns:
            str: Salida del comando
        """
        # Si el comando requiere modo configuración, asegurar que estamos en él
        if command.startswith(('configure', 'interface', 'vlan', 'gpon', 'pon')):
            self.ensure_config_mode()
        
        return self.execute_command(command, delay_factor, timeout)
    
    def enter_interface(self, slot: str, port: str = None):
        """
        Entra a modo interfaz
        
        Args:
            slot: Número de tarjeta (slot)
            port: Número de puerto (opcional)
        """
        if port:
            cmd = f"interface gpon-olt_1/{slot}/{port}"
        else:
            cmd = f"interface gpon-olt_1/{slot}"
        
        output = self.execute_command(cmd, timeout=15)
        
        if "Error" in output or "Invalid" in output:
            raise Exception(f"No se pudo entrar a interfaz: {output}")
        
        self._in_interface_mode = True
        self.current_interface = f"1/{slot}/{port}" if port else f"1/{slot}"
        logger.debug(f"En modo interfaz: {self.current_interface}")
    
    def exit_interface(self):
        """Sale del modo interfaz"""
        if self._in_interface_mode:
            self.execute_command("exit", timeout=10)
            self._in_interface_mode = False
            self.current_interface = None
            logger.debug("Salió de modo interfaz")
    
    def ensure_config_mode(self):
        """Asegura que estamos en modo configuración global"""
        try:
            # Verificar si ya estamos en modo config
            self.shell.send("\n")
            time.sleep(0.5)
            output = self._read_until_prompt(5)
            
            # Si estamos en modo interfaz, salir
            if self._in_interface_mode:
                self.exit_interface()
            
            # Si no estamos en config, entrar
            if not '(config' in output and not '#config' in output:
                if '#config' not in output:
                    output = self.execute_command("configure terminal", timeout=15)
                    if 'Error' not in output and 'Invalid' not in output:
                        self._in_config_mode = True
                        logger.debug("En modo configuración global")
                        time.sleep(0.5)
            
        except Exception as e:
            logger.warning(f"Error asegurando modo config: {e}")
            # Intentar entrar directamente
            try:
                output = self.execute_command("configure terminal", timeout=15)
                if 'Error' not in output and 'Invalid' not in output:
                    self._in_config_mode = True
            except:
                pass
    
    def _clear_buffer(self):
        """Limpia el buffer de entrada/salida"""
        if self.shell and self.shell.recv_ready():
            try:
                self.shell.recv(65535)
            except:
                pass
    
    def disconnect(self):
        """Cierra la conexión SSH"""
        try:
            if self.shell:
                # Salir de modos
                try:
                    for _ in range(3):
                        self.shell.send("exit\n")
                        time.sleep(0.5)
                except:
                    pass
                self.shell.close()
            
            if self.client:
                self.client.close()
            
            self._connected = False
            self._in_config_mode = False
            self._in_interface_mode = False
            logger.info(f"Conexión cerrada con {self.host}")
            
        except Exception as e:
            logger.error(f"Error desconectando: {e}")
    
    def is_connected(self) -> bool:
        """Verifica si la conexión está activa"""
        if not self._connected or not self.shell or not self.client:
            return False
        
        try:
            # Test de conectividad
            self.shell.send("\n")
            time.sleep(0.5)
            output = self._read_until_prompt(5)
            return bool(output)
        except:
            return False
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


# Ejemplo de uso para probar la conexión
if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(level=logging.INFO)
    
    # Prueba de conexión
    with SessionConnection(
        host='10.0.0.62',
        username='zte',
        password='zte',
        device_type='zte_zxros'
    ) as session:
        
        # Probar comandos básicos
        print("=== PRUEBA DE CONEXIÓN ZTE ZXROS ===")
        
        # Ver versión
        output = session.execute_command("show version", timeout=15)
        print("Versión:", output[:200] + "...")
        
        # Ver estado de GPON
        output = session.execute_command("show gpon onu state gpon-olt_1/1/1", timeout=20)
        print("\nEstado puerto 1/1:", output[:200] + "...")
        
        # Obtener show run (parte)
        output = session.execute_command("show run", timeout=30)
        print("\nShow run (primeras líneas):")
        for line in output.split('\n')[:20]:
            print(line)
        
        print("\n✅ Prueba completada exitosamente")