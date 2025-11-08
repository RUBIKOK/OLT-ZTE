# config.py - VERSIÓN CORREGIDA

import os
import re
from typing import Dict, Any

class Config:
    """Configuración de la aplicación"""
    
    # Configuración de la aplicación
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'tu-clave-secreta-muy-segura-aqui'
    APP_VERSION = "1.2.0"
    
    # ============ CORRECCIÓN 1: Configuración mejorada del dispositivo OLT ============
    DEVICE_CONFIG = {
        'device_type': 'zte_zxros',
        'ip': os.environ.get('OLT_IP') or '10.0.0.62',
        'username': os.environ.get('OLT_USERNAME') or 'zte',
        'password': os.environ.get('OLT_PASSWORD') or 'zte',
        'port': int(os.environ.get('OLT_PORT', 22)),
        
        # Timeouts más conservadores y configurables
        'timeout': int(os.environ.get('OLT_TIMEOUT', 45)),  # Aumentado de 30 a 45
        'session_timeout': int(os.environ.get('OLT_SESSION_TIMEOUT', 300)),
        'blocking_timeout': int(os.environ.get('OLT_BLOCKING_TIMEOUT', 25)),  # Aumentado
        'banner_timeout': int(os.environ.get('OLT_BANNER_TIMEOUT', 20)),     # Aumentado
        'conn_timeout': int(os.environ.get('OLT_CONN_TIMEOUT', 15)),         # Aumentado
        'auth_timeout': int(os.environ.get('OLT_AUTH_TIMEOUT', 15)),         # Aumentado
        
        # Configuraciones adicionales para estabilidad
        'fast_cli': False,
        'global_delay_factor': float(os.environ.get('OLT_DELAY_FACTOR', 2)),
        'keepalive': int(os.environ.get('OLT_KEEPALIVE', 30)),  # Nuevo
        'secret': os.environ.get('OLT_ENABLE_SECRET') or '',
        
        # ============ CORRECCIÓN 2: Configuraciones específicas de Huawei ============
        # Configuraciones específicas para dispositivos Huawei
        'allow_agent': False,
        #'look_for_keys': False,
        'use_keys': False,
        #'key_policy': 'auto_add',
        
        # Configuraciones para manejar prompts específicos de Huawei
        #'strip_ansi_escape_codes': True,
        #'strip_command': True,
        #'strip_prompt': True,
        #'normalize': True,
        
        # Configuración de encoding
        'encoding': 'utf-8',
        'session_log': None,  # Deshabilitar logging de sesión por defecto
    }
    
    # ============ CORRECCIÓN 3: Configuración mejorada del pool de conexiones ============
    CONNECTION_POOL_CONFIG = {
        'max_idle_time': int(os.environ.get('MAX_IDLE_TIME', 300)),        # 5 minutos
        'cleanup_interval': int(os.environ.get('CLEANUP_INTERVAL', 30)),   # 30 segundos
        'max_connections': int(os.environ.get('MAX_CONNECTIONS', 50)),     # Máximo 50
        'connection_timeout': int(os.environ.get('CONNECTION_TIMEOUT', 60)),  # Timeout para nuevas conexiones
        'max_retries': int(os.environ.get('MAX_CONNECTION_RETRIES', 3)),   # Máximo reintentos
        'retry_delay': int(os.environ.get('RETRY_DELAY', 5)),              # Delay entre reintentos
    }
    
    # ============ CORRECCIÓN 4: Configuración mejorada de logging ============
    LOGGING_CONFIG = {
        'level': os.environ.get('LOG_LEVEL', 'INFO').upper(),
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'date_format': '%Y-%m-%d %H:%M:%S',
        'file': os.environ.get('LOG_FILE', None),  # Por defecto no archivo, solo consola
        'max_size': int(os.environ.get('LOG_MAX_SIZE', 10485760)),  # 10MB
        'backup_count': int(os.environ.get('LOG_BACKUP_COUNT', 5)),
        
        # Configuración específica por logger
        'loggers': {
            'netmiko': os.environ.get('NETMIKO_LOG_LEVEL', 'WARNING').upper(),
            'paramiko': os.environ.get('PARAMIKO_LOG_LEVEL', 'WARNING').upper(),
            'urllib3': 'WARNING',
        },
        
        # Filtrar logs sensibles
        'filter_sensitive': True,
        'sensitive_keywords': ['password', 'secret', 'token', 'key'],
    }
    
    # ============ CORRECCIÓN 5: Configuración mejorada de Flask ============
    FLASK_CONFIG = {
        'host': os.environ.get('FLASK_HOST', '0.0.0.0'),
        'port': int(os.environ.get('FLASK_PORT', 5008)),
        'debug': os.environ.get('FLASK_DEBUG', 'False').lower() == 'true',
        'threaded': True,
        'use_reloader': False,  # Evitar problemas con hilos
        'processes': 1,  # Usar solo un proceso para mantener conexiones
        
        # Configuraciones adicionales de Flask
        'max_content_length': int(os.environ.get('MAX_CONTENT_LENGTH', 16777216)),  # 16MB
        'send_file_max_age_default': int(os.environ.get('SEND_FILE_MAX_AGE', 43200)),  # 12 horas
        'permanent_session_lifetime': int(os.environ.get('SESSION_LIFETIME', 7200)),  # 2 horas
    }
    
    # ============ CORRECCIÓN 6: Configuraciones de la aplicación ============
    APP_CONFIG = {
        'max_ont_per_query': int(os.environ.get('MAX_ONT_PER_QUERY', 128)),  # Máximo ONTs por consulta
        'excel_timeout': int(os.environ.get('EXCEL_TIMEOUT', 300)),          # 5 minutos para Excel
        'api_rate_limit': int(os.environ.get('API_RATE_LIMIT', 60)),         # Requests por minuto
        'session_cleanup_interval': int(os.environ.get('SESSION_CLEANUP', 3600)),  # 1 hora
        
        # Configuraciones de la interfaz
        'default_page_size': int(os.environ.get('DEFAULT_PAGE_SIZE', 50)),
        'max_page_size': int(os.environ.get('MAX_PAGE_SIZE', 200)),
        
        # Configuraciones de monitoreo
        'health_check_interval': int(os.environ.get('HEALTH_CHECK_INTERVAL', 300)),  # 5 minutos
        'performance_monitoring': os.environ.get('PERFORMANCE_MONITORING', 'True').lower() == 'true',
    }
    
    # ============ CORRECCIÓN 7: Configuraciones de seguridad ============
    SECURITY_CONFIG = {
        'csrf_enabled': os.environ.get('CSRF_ENABLED', 'True').lower() == 'true',
        'secure_headers': os.environ.get('SECURE_HEADERS', 'True').lower() == 'true',
        'rate_limiting': os.environ.get('RATE_LIMITING', 'True').lower() == 'true',
        
        # Configuración de sesiones
        'session_cookie_secure': os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true',
        'session_cookie_httponly': True,
        'session_cookie_samesite': 'Lax',
        
        # Headers de seguridad
        'security_headers': {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin'
        }
    }
    
    @classmethod
    def validate_config(cls):
        """Valida la configuración"""
        errors = []
        
        # ============ CORRECCIÓN 8: Validación mejorada ============
        # Validar configuración del dispositivo
        device_errors = cls._validate_device_config()
        if device_errors:
            errors.extend(device_errors)
        
        # Validar configuración de red
        network_errors = cls._validate_network_config()
        if network_errors:
            errors.extend(network_errors)
        
        # Validar configuración de logging
        logging_errors = cls._validate_logging_config()
        if logging_errors:
            errors.extend(logging_errors)
        
        if errors:
            raise ValueError(f"Errores de configuración:\n" + "\n".join(f"- {error}" for error in errors))
        
        return True
    
    @classmethod
    def _validate_device_config(cls) -> list:
        """Valida la configuración del dispositivo"""
        errors = []
        device_config = cls.DEVICE_CONFIG
        
        # Campos requeridos
        required_fields = ['ip', 'username', 'password', 'device_type']
        for field in required_fields:
            if not device_config.get(field):
                errors.append(f"Campo requerido faltante en DEVICE_CONFIG: {field}")
        
        # Validar IP
        ip = device_config.get('ip')
        if ip and not cls._is_valid_ip(ip):
            errors.append(f"IP inválida: {ip}")
        
        # Validar puerto
        port = device_config.get('port')
        if port and not (1 <= port <= 65535):
            errors.append(f"Puerto inválido: {port}")
        
        # Validar timeouts
        timeout_fields = ['timeout', 'session_timeout', 'blocking_timeout', 'banner_timeout', 'conn_timeout', 'auth_timeout']
        for field in timeout_fields:
            value = device_config.get(field)
            if value and not (1 <= value <= 3600):  # Entre 1 segundo y 1 hora
                errors.append(f"Timeout inválido para {field}: {value}")
        
        return errors
    
    @classmethod
    def _validate_network_config(cls) -> list:
        """Valida la configuración de red"""
        errors = []
        flask_config = cls.FLASK_CONFIG
        
        # Validar puerto de Flask
        port = flask_config.get('port')
        if port and not (1024 <= port <= 65535):
            errors.append(f"Puerto de Flask inválido: {port}")
        
        # Validar host
        host = flask_config.get('host')
        if host and host not in ['0.0.0.0', '127.0.0.1', 'localhost'] and not cls._is_valid_ip(host):
            errors.append(f"Host de Flask inválido: {host}")
        
        return errors
    
    @classmethod
    def _validate_logging_config(cls) -> list:
        """Valida la configuración de logging"""
        errors = []
        logging_config = cls.LOGGING_CONFIG
        
        # Validar nivel de logging
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        level = logging_config.get('level')
        if level and level not in valid_levels:
            errors.append(f"Nivel de logging inválido: {level}")
        
        # Validar archivo de log
        log_file = logging_config.get('file')
        if log_file:
            try:
                log_dir = os.path.dirname(log_file)
                if log_dir and not os.path.exists(log_dir):
                    os.makedirs(log_dir, exist_ok=True)
            except Exception as e:
                errors.append(f"No se puede crear directorio de logs: {e}")
        
        return errors
    
    @classmethod
    def _is_valid_ip(cls, ip: str) -> bool:
        """Valida si una cadena es una IP válida"""
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            
            for part in parts:
                if not (0 <= int(part) <= 255):
                    return False
            
            return True
        except (ValueError, AttributeError):
            return False
    
    # ============ CORRECCIÓN 9: Métodos de utilidad ============
    @classmethod
    def get_environment_info(cls) -> Dict[str, Any]:
        """Retorna información del entorno"""
        return {
            'python_version': os.sys.version,
            'environment_variables': {
                key: '***' if any(sensitive in key.lower() for sensitive in ['password', 'secret', 'key']) 
                     else value
                for key, value in os.environ.items() 
                if key.startswith(('OLT_', 'FLASK_', 'LOG_'))
            },
            'config_validation': 'OK' if cls._test_validate_config() else 'ERROR'
        }
    
    @classmethod
    def _test_validate_config(cls) -> bool:
        """Prueba la validación de configuración sin lanzar excepción"""
        try:
            cls.validate_config()
            return True
        except Exception:
            return False
    
    @classmethod
    def get_connection_test_config(cls) -> Dict[str, Any]:
        """Retorna configuración para pruebas de conexión"""
        config = cls.DEVICE_CONFIG.copy()
        
        # Timeouts más cortos para pruebas
        config.update({
            'timeout': 10,
            'conn_timeout': 5,
            'auth_timeout': 5,
            'banner_timeout': 5,
            'blocking_timeout': 10
        })
        
        return config
    
    # ============ CORRECCIÓN 10: Configuración de desarrollo vs producción ============
    @classmethod
    def is_development(cls) -> bool:
        """Retorna True si estamos en modo desarrollo"""
        return cls.FLASK_CONFIG['debug'] or os.environ.get('ENVIRONMENT', 'production').lower() == 'development'
    
    @classmethod
    def apply_production_settings(cls):
        """Aplica configuraciones específicas de producción"""
        if not cls.is_development():
            # Ajustar configuraciones para producción
            cls.FLASK_CONFIG['debug'] = False
            cls.LOGGING_CONFIG['level'] = 'WARNING'
            cls.SECURITY_CONFIG['session_cookie_secure'] = True
            cls.SECURITY_CONFIG['secure_headers'] = True
    
    # ============ CORRECCIÓN 11: Configuración dinámica ============
    @classmethod
    def update_device_config(cls, **kwargs):
        """Actualiza la configuración del dispositivo dinámicamente"""
        for key, value in kwargs.items():
            if key in cls.DEVICE_CONFIG:
                cls.DEVICE_CONFIG[key] = value
        
        # Revalidar después de actualizar
        cls.validate_config()
    
    @classmethod
    def get_masked_config(cls) -> Dict[str, Any]:
        """Retorna la configuración con campos sensibles enmascarados"""
        import copy
        
        masked_config = copy.deepcopy({
            'DEVICE_CONFIG': cls.DEVICE_CONFIG,
            'CONNECTION_POOL_CONFIG': cls.CONNECTION_POOL_CONFIG,
            'FLASK_CONFIG': cls.FLASK_CONFIG,
            'APP_CONFIG': cls.APP_CONFIG,
            'SECURITY_CONFIG': cls.SECURITY_CONFIG
        })
        
        # Enmascarar campos sensibles
        sensitive_fields = ['password', 'secret']
        for config_section in masked_config.values():
            if isinstance(config_section, dict):
                for key in config_section:
                    if any(sensitive in key.lower() for sensitive in sensitive_fields):
                        config_section[key] = '***MASKED***'
        
        return masked_config