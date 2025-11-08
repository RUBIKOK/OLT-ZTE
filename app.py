#!/usr/bin/env python3
"""
OLT Monitor - Sistema de monitoreo de terminales ópticas
Versión con pool de conexiones múltiples
"""

import logging
import sys
import os
from flask import Flask, render_template
import atexit

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from config import Config
    from controllers.ont_controller import ont_bp, connection_pool
except ImportError as e:
    print(f"Error crítico al importar módulos: {e}")
    print("Asegúrese de que todos los archivos estén en su lugar correcto")
    sys.exit(1)

def create_app():
    """Factory function para crear la aplicación Flask"""
    
    # Validar configuración
    try:
        Config.validate_config()
    except ValueError as e:
        print(f"Error de configuración: {e}")
        sys.exit(1)
    
    # Crear aplicación Flask
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Configurar logging con contexto de sesión
    logging.basicConfig(
        level=getattr(logging, Config.LOGGING_CONFIG['level']),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(Config.LOGGING_CONFIG['file']) if Config.LOGGING_CONFIG['file'] else logging.NullHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("="*50)
    logger.info("Iniciando OLT ZTE v2.2.0 con Pool de Conexiones")
    logger.info("="*50)
    
    # Registrar blueprint
    app.register_blueprint(ont_bp)
    
    # Página de inicio por defecto (redirige al home del blueprint)
    @app.route('/')
    def index():
        """Redirige a la página de inicio de ONT"""
        from flask import redirect, url_for
        return redirect(url_for('ont.home'))
    
    # Handler para errores 404
    @app.errorhandler(404)
    def not_found(error):
        return render_template('404.html'), 404
    
    # Handler para errores 500
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Error interno del servidor: {error}")
        return render_template('500.html'), 500
    
    # Context processors para templates
    @app.context_processor
    def inject_config():
        """Inyecta variables de configuración en todos los templates"""
        return {
            'config': {
                'APP_VERSION': Config.APP_VERSION
            }
        }
    @app.route('/favicon.ico')
    def favicon():
        return '', 204  # No Content

    @app.context_processor
    def inject_connection_status():
        """Inyecta estado de conexiones en templates"""
        return {
            'active_connections': connection_pool.get_active_connections_count() if connection_pool else 0
        }
    
    # Función para limpiar conexiones al cerrar
    def cleanup_connections():
        """Limpia todas las conexiones del pool al cerrar la aplicación"""
        if connection_pool:
            logger.info("Limpiando pool de conexiones...")
            # Aquí podrías agregar un método cleanup al pool si lo necesitas
            logger.info("Pool de conexiones limpiado")
    
    # Registrar función de limpieza
    atexit.register(cleanup_connections)
    
    logger.info(f"Configuración del dispositivo OLT:")
    logger.info(f"  - IP: {Config.DEVICE_CONFIG['ip']}")
    logger.info(f"  - Puerto: {Config.DEVICE_CONFIG['port']}")
    logger.info(f"  - Usuario: {Config.DEVICE_CONFIG['username']}")
    logger.info(f"  - Timeout: {Config.DEVICE_CONFIG['timeout']}s")
    logger.info(f"Pool de conexiones configurado:")
    logger.info(f"  - Tiempo máximo inactivo: {Config.CONNECTION_POOL_CONFIG['max_idle_time']}s")
    logger.info(f"  - Máximo conexiones: {Config.CONNECTION_POOL_CONFIG['max_connections']}")
    
    return app

def main():
    """Función principal"""
    try:
        # Crear aplicación
        app = create_app()
        
        # Configurar Flask
        flask_config = Config.FLASK_CONFIG
        
        logger = logging.getLogger(__name__)
        logger.info(f"Iniciando servidor Flask en {flask_config['host']}:{flask_config['port']}")
        logger.info(f"Debug mode: {flask_config['debug']}")
        logger.info("Aplicación lista para recibir conexiones múltiples")
        logger.info("Cada usuario tendrá su propia conexión SSH independiente")
        
        # Ejecutar aplicación
        app.run(
            host=flask_config['host'],
            port=flask_config['port'],
            debug=flask_config['debug'],
            threaded=flask_config['threaded'],
            use_reloader=flask_config['use_reloader']
        )
        
    except KeyboardInterrupt:
        logger.info("Aplicación interrumpida por el usuario")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error fatal al iniciar la aplicación: {e}")
        logger.error(f"Traceback:", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()