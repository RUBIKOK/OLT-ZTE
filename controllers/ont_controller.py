# controllers/ont_controller.py - VERSIÓN CORREGIDA

import io
from flask import Blueprint, request, render_template, send_file, flash, redirect, url_for, session, jsonify, make_response
import logging
import sys
import os
import re
import traceback
import uuid

# Agregar el directorio raíz al path si es necesario
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config import Config
    from services.connection_pool import ConnectionPool
    from services.ont_service import ONTService
    from services.excel_service import ExcelService
    from models.ont_model import ONT, ONTCollection
except ImportError as e:
    print(f"Error de importación básica: {e}")
    print("Verificar que todos los archivos básicos estén en su lugar correcto")
    sys.exit(1)

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Crear blueprint
ont_bp = Blueprint('ont', __name__)

# Inicializar pool de conexiones (ÚNICO PARA TODA LA APLICACIÓN)
connection_pool = ConnectionPool(Config.DEVICE_CONFIG, max_idle_time=300)
excel_service = ExcelService()

# Intentar importar BoardService
board_service = None
try:
    from services.board_service import BoardService
    board_service = BoardService
    logger.info("BoardService inicializado correctamente")
except ImportError as e:
    logger.error(f"Error importando BoardService: {e}")
except Exception as e:
    logger.error(f"Error inicializando BoardService: {e}")

def get_session_id():
    """Obtiene o crea un ID único para la sesión actual"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        logger.info(f"Nueva sesión creada: {session['session_id']}")
    return session['session_id']

def get_connection_for_session():
    """Obtiene una conexión específica para la sesión actual"""
    session_id = get_session_id()
    return connection_pool.get_connection(session_id)

# ============ CORRECCIÓN 1: Manejo de errores mejorado ============
def handle_service_error(error, operation_name, session_id=None):
    """Manejo centralizado de errores de servicios"""
    error_msg = str(error)
    session_info = f" en sesión {session_id}" if session_id else ""
    
    logger.error(f"Error en {operation_name}{session_info}: {error_msg}")
    
    # Determinar tipo de error para el usuario
    if "timeout" in error_msg.lower():
        user_msg = "La operación tardó demasiado. Intente nuevamente."
    elif "connection" in error_msg.lower():
        user_msg = "Error de conexión con el dispositivo. Verifique la conectividad."
    elif "authentication" in error_msg.lower():
        user_msg = "Error de autenticación. Verifique las credenciales."
    else:
        user_msg = f"Error al realizar {operation_name}: {error_msg}"
    
    return user_msg

@ont_bp.route("/")
def home():
    """Página de inicio - NO carga automáticamente las ONTs en autofind"""
    return render_template("home.html", autofind_list=[])

@ont_bp.route("/onts", methods=["GET", "POST"])
def ont_page():
    ont_collection = ONTCollection()
    tarjeta = ""
    puerto = ""
    summary = {"total_onts": 0, "online_onts": 0, "critical_onts": 0}

    if request.method == "POST":
        # ============ CORRECCIÓN 2: Validación mejorada de entrada ============
        tarjeta = request.form.get("tarjeta", "").strip()
        puerto = request.form.get("puerto", "").strip()
        
        # Validaciones específicas
        if not tarjeta or not puerto:
            flash("Por favor ingrese tarjeta y puerto válidos", "error")
            return render_template("ont.html", onts=[], tarjeta=tarjeta, puerto=puerto, summary=summary)
        
        # Validar formato de tarjeta (1-17)
        if not re.match(r'^(1[0-7]|[1-9])$', tarjeta):
            flash("Tarjeta debe ser un número entre 1 y 17", "error")
            return render_template("ont.html", onts=[], tarjeta=tarjeta, puerto=puerto, summary=summary)
        
        # Validar formato de puerto (0-16)
        if not re.match(r'^(1[0-6]|[0-9])$', puerto):
            flash("Puerto debe ser un número entre 0 y 16", "error")
            return render_template("ont.html", onts=[], tarjeta=tarjeta, puerto=puerto, summary=summary)
        
        try:
            # Usar conexión específica de la sesión
            connection_service = get_connection_for_session()
            ont_service = ONTService(connection_service)
            
            ont_collection = ont_service.obtener_onts(tarjeta, puerto)
            summary = ont_collection.get_summary()
            session['last_onts'] = ont_collection.to_dict_list()
            session['last_query'] = f"Tarjeta_{tarjeta}_Puerto_{puerto}"
            
            # ============ CORRECCIÓN 3: Mensajes más informativos ============
            total_onts = ont_collection.get_total_count()
            online_onts = ont_collection.get_online_count()
            if total_onts == 0:
                flash(f"No se encontraron ONTs en la tarjeta {tarjeta}, puerto {puerto}", "warning")
            else:
                flash(f"Se encontraron {total_onts} ONTs ({online_onts} online, {total_onts-online_onts} offline)", "success")
                
        except Exception as e:
            session_id = get_session_id()
            user_msg = handle_service_error(e, "consultar ONTs", session_id)
            flash(user_msg, "error")

    return render_template(
        "ont.html",
        onts=ont_collection.to_dict_list(),
        tarjeta=tarjeta,
        puerto=puerto,
        summary=summary
    )

@ont_bp.route("/download_tarjeta/<tarjeta>")
def download_tarjeta(tarjeta):
    """Consulta todos los puertos (0-15) de una tarjeta y descarga el Excel"""
    try:
        # ============ CORRECCIÓN 4: Validación de parámetros URL ============
        if not tarjeta or not re.match(r'^(1[0-7]|[1-9])$', tarjeta):
            flash("Tarjeta inválida. Debe ser un número entre 1 y 17", "error")
            return redirect(url_for("ont.ont_page"))

        # Usar conexión específica de la sesión
        connection_service = get_connection_for_session()
        ont_service = ONTService(connection_service)

        all_onts = ONTCollection()
        puertos_procesados = 0
        puertos_con_error = 0
        
        # ============ CORRECCIÓN 5: Mejor manejo de errores por puerto ============
        for p in range(16):  # puertos 0-15
            try:
                partial = ont_service.obtener_onts(tarjeta, str(p))
                all_onts.extend(partial)
                puertos_procesados += 1
                
                # Log progreso cada 4 puertos
                if p % 4 == 0:
                    logger.info(f"Procesando puerto {p}/15 para tarjeta {tarjeta}")
                    
            except Exception as e:
                puertos_con_error += 1
                logger.warning(f"Error en puerto {p} para tarjeta {tarjeta}: {e}")
                continue

        # Información del procesamiento
        logger.info(f"Tarjeta {tarjeta}: {puertos_procesados} puertos procesados, {puertos_con_error} con errores")

        if all_onts.get_total_count() == 0:
            flash(f"No se encontraron ONTs en la tarjeta {tarjeta}. Verifique que la tarjeta esté activa.", "warning")
            return redirect(url_for("ont.ont_page"))

        # Generar archivo Excel
        file_stream = excel_service.generar_reporte(all_onts)
        filename = f"Reporte_Tarjeta_{tarjeta}_Completa.xlsx"
    
        response = make_response(send_file(
            file_stream,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ))
        
        # Agregar cookie para indicar que la descarga inició
        response.set_cookie('download_started', 'true', max_age=5)
        
        return response
        
    except Exception as e:
        session_id = get_session_id()
        user_msg = handle_service_error(e, f"generar Excel de tarjeta {tarjeta}", session_id)
        flash(user_msg, "error")
        return redirect(url_for("ont.ont_page"))

# ============================================
# 4. BACKEND - Routes (routes/ont_routes.py)
# ============================================

@ont_bp.route("/api/next_onu_id/<board>/<port>", methods=["GET"])
def api_next_onu_id(board, port):
    """API para obtener el siguiente ID de ONU disponible"""
    try:
        connection_service = get_connection_for_session()
        ont_service = ONTService(connection_service)
        
        next_id = ont_service.obtener_siguiente_onu_id(board, port)
        
        return jsonify({
            'status': 'success',
            'next_id': next_id,
            'board': board,
            'port': port
        })
        
    except Exception as e:
        logger.error(f"Error en API next_onu_id: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@ont_bp.route("/api/authorize_ont", methods=["POST"])
def api_authorize_ont():
    """API para autorizar una ONT"""
    try:
        data = request.get_json()
        
        # Validar datos requeridos
        required = ['board', 'port', 'onu_id', 'sn', 'onu_type', 'vlan']
        missing = [field for field in required if not data.get(field)]
        
        if missing:
            return jsonify({
                'status': 'error',
                'error': f'Faltan campos requeridos: {", ".join(missing)}'
            }), 400
        
        connection_service = get_connection_for_session()
        ont_service = ONTService(connection_service)
        
        result = ont_service.autorizar_ont(
            board=data['board'],
            port=data['port'],
            onu_id=data['onu_id'],
            sn=data['sn'],
            onu_type=data['onu_type'],
            vlan=data['vlan'],
            zone=data.get('zone', ''),
            name=data.get('name', ''),
            onu_mode=data.get('onu_mode', 'routing')
        )
        
        return jsonify(result)
        
    except Exception as e:
        session_id = get_session_id()
        logger.error(f"Error en API authorize_ont (sesión {session_id}): {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500
    
@ont_bp.route("/download_excel")
def download_excel():
    """Controlador para descargar Excel"""
    try:
        # Obtener datos de la sesión
        last_onts_data = session.get('last_onts', [])
        if not last_onts_data:
            flash("No hay datos para exportar. Realice una consulta primero.", "warning")
            return redirect(url_for('ont.ont_page'))
        
        # ============ CORRECCIÓN 7: Validación de datos de sesión ============
        try:
            # Recrear colección desde los datos de sesión
            ont_collection = ONTCollection()
            for ont_data in last_onts_data:
                # Validar campos obligatorios
                required_fields = ['id', 'tarjeta', 'puerto', 'estado']
                if not all(field in ont_data for field in required_fields):
                    logger.warning(f"Datos incompletos para ONT: {ont_data}")
                    continue
                    
                ont = ONT(
                    id=ont_data.get('id', ''),
                    tarjeta=ont_data.get('tarjeta', ''),
                    puerto=ont_data.get('puerto', ''),
                    ont_rx=ont_data.get('ont_rx'),
                    olt_rx=ont_data.get('olt_rx'),
                    temperature=ont_data.get('temperature'),
                    distance=ont_data.get('distance'),
                    estado=ont_data.get('estado', ''),
                    last_down_time=ont_data.get('last_down_time', ''),
                    last_down_cause=ont_data.get('last_down_cause', ''),
                    descripcion=ont_data.get('descripcion', '')
                )
                ont_collection.add_ont(ont)
        
        except Exception as e:
            logger.error(f"Error recreando colección de ONTs: {e}")
            flash("Error procesando datos de la sesión. Realice una nueva consulta.", "error")
            return redirect(url_for('ont.ont_page'))
        
        if ont_collection.get_total_count() == 0:
            flash("No hay ONTs válidas para exportar. Realice una nueva consulta.", "warning")
            return redirect(url_for('ont.ont_page'))
        
        # Generar archivo
        file_stream = excel_service.generar_reporte(ont_collection)
        
        # Nombre del archivo con información de la consulta
        query_info = session.get('last_query', 'ONTs')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"Reporte_{query_info}_{timestamp}.xlsx"
        
        return send_file(
            file_stream,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    except Exception as e:
        session_id = get_session_id()
        user_msg = handle_service_error(e, "generar Excel", session_id)
        flash(user_msg, "error")
        return redirect(url_for('ont.ont_page'))

@ont_bp.route("/monitor")
def monitor():
    """Vista del monitor de puertos PON"""
    return render_template("monitor.html")

@ont_bp.route("/api/board/<tarjeta>")
def get_board_data(tarjeta):
    """API endpoint para obtener datos de una tarjeta específica"""
    try:
        logger.info(f"=== API Request: Tarjeta {tarjeta} en sesión {get_session_id()} ===")

        if board_service is None:
            logger.error("BoardService no está disponible")
            return jsonify({
                "error": "Servicio de tarjetas no disponible. Verifique la configuración del servidor."
            }), 500

        # ============ CORRECCIÓN 8: Validación de API más robusta ============
        # Validar formato de tarjeta
        if not re.match(r'^(1[0-7]|[1-9])$', tarjeta):
            logger.warning(f"Formato de tarjeta inválido: {tarjeta}")
            return jsonify({
                "error": f"Formato de tarjeta inválido: '{tarjeta}'. Solo se permiten números entre 1 y 17",
                "provided_value": tarjeta,
                "valid_range": "1-17"
            }), 400

        # Usar conexión específica de la sesión
        connection_service = get_connection_for_session()
        board_service_instance = BoardService(connection_service)
        
        board_data = board_service_instance.obtener_puertos_tarjeta(tarjeta)
        
        # ============ CORRECCIÓN 9: Enriquecimiento de respuesta API ============
        response_data = {
            "tarjeta": tarjeta,
            "timestamp": datetime.now().isoformat(),
            "session_id": get_session_id(),
            **board_data
        }
        
        logger.info(f"Consulta exitosa para tarjeta {tarjeta} en sesión {get_session_id()}")
        return jsonify(response_data)

    except Exception as e:
        session_id = get_session_id()
        error_msg = handle_service_error(e, f"consultar API tarjeta {tarjeta}", session_id)
        logger.error(traceback.format_exc())
        
        return jsonify({
            "error": error_msg,
            "tarjeta": tarjeta,
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id
        }), 500

# ============ CORRECCIÓN 10: Imports faltantes ============
from datetime import datetime

@ont_bp.route("/api/test")
def test_api():
    """Endpoint de prueba para verificar que la API funciona"""
    session_id = get_session_id()
    active_connections = connection_pool.get_active_connections_count()
    
    return jsonify({
        "status": "ok", 
        "message": "API funcionando correctamente",
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id,
        "active_connections": active_connections,
        "board_service_available": board_service is not None,
        "version": "1.2.0"
    })

@ont_bp.route("/api/autofind/refresh")
def refresh_autofind():
    """API endpoint para refrescar datos de autofind"""
    try:
        logger.info(f"Iniciando consulta de autofind ONTs en sesión {get_session_id()}")
        
        # Usar conexión específica de la sesión
        connection_service = get_connection_for_session()
        ont_service = ONTService(connection_service)
        
        autofind_list = ont_service.obtener_autofind_onts()
        
        # ============ CORRECCIÓN 11: Validación y limpieza de datos autofind ============
        # Filtrar y validar datos
        valid_autofind = []
        for ont in autofind_list:
            if ont.get('sn') and ont.get('board') and ont.get('port'):
                # Limpiar serial number
                ont['sn'] = re.sub(r'[^A-Za-z0-9-]', '', ont['sn'])
                valid_autofind.append(ont)
        
        logger.info(f"Se procesaron {len(valid_autofind)}/{len(autofind_list)} ONTs válidas en autofind")
        
        return jsonify({
            "status": "success",
            "count": len(valid_autofind),
            "total_found": len(autofind_list),
            "data": valid_autofind,
            "message": f"Se encontraron {len(valid_autofind)} ONUs detectadas automáticamente",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        session_id = get_session_id()
        error_msg = handle_service_error(e, "refrescar autofind", session_id)
        
        return jsonify({
            "status": "error",
            "message": error_msg,
            "count": 0,
            "data": [],
            "timestamp": datetime.now().isoformat()
        }), 500

# ============ RESTO DE RUTAS (sin cambios significativos) ============

@ont_bp.route("/api/session/disconnect")
def disconnect_session():
    """Endpoint para desconectar manualmente la sesión actual"""
    try:
        session_id = get_session_id()
        connection_pool.disconnect_session(session_id)
        # Limpiar el session_id para forzar una nueva conexión
        session.pop('session_id', None)
        
        return jsonify({
            "status": "success",
            "message": f"Sesión {session_id} desconectada correctamente",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error desconectando sesión: {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@ont_bp.route("/api/connections/status")
def connections_status():
    """Endpoint para ver el estado de las conexiones"""
    try:
        return jsonify({
            "active_connections": connection_pool.get_active_connections_count(),
            "current_session": get_session_id(),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500
    
@ont_bp.route("/api/ont_info/<tarjeta>/<puerto>/<ont_id>")
def get_ont_info(tarjeta, puerto, ont_id):
    """API endpoint para ejecutar display ont info"""
    try:
        # Validar parámetros
        if not re.match(r'^(1[0-7]|[1-9])$', tarjeta):
            return jsonify({"error": "Tarjeta inválida. Debe ser entre 1-17"}), 400
        
        if not re.match(r'^(1[0-6]|[0-9])$', puerto):
            return jsonify({"error": "Puerto inválido. Debe ser entre 0-16"}), 400
        
        if not ont_id.isdigit():
            return jsonify({"error": "ID de ONT inválido. Debe ser numérico"}), 400
        
        connection_service = get_connection_for_session()
        ont_service = ONTService(connection_service)

        output = ont_service.obtener_detalles_ont(tarjeta, puerto, ont_id) 

        return jsonify({
            "status": "success",
            "command": f"display ont info {puerto} {ont_id}",
            "output": output,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        session_id = get_session_id()
        error_msg = handle_service_error(e, f"ejecutar display ont info {ont_id}", session_id)
            
        return jsonify({
            "error": error_msg,
            "timestamp": datetime.now().isoformat()
        }), 500
    
@ont_bp.route("/barrido", methods=["GET", "POST"])
def barrido():
    """Página de barrido rápido de puertos"""
    resultados = None
    tarjeta = ""
    puerto = ""
    habilitar_nombres = False

    if request.method == "POST":
        tarjeta = request.form.get("tarjeta", "").strip()
        puerto = request.form.get("puerto", "").strip()
        habilitar_nombres = request.form.get("habilitar_nombres") == "on"
        
        # Validaciones
        if not tarjeta or not puerto:
            flash("Por favor ingrese tarjeta y puerto válidos", "error")
            return render_template("barrido.html", 
                                 resultados=resultados, 
                                 tarjeta=tarjeta, 
                                 puerto=puerto,
                                 habilitar_nombres=habilitar_nombres,
                                 available_olts=Config.get_available_olts())
        
        # Validar formato de tarjeta (1-17)
        if not re.match(r'^(1[0-7]|[1-9])$', tarjeta):
            flash("Tarjeta debe ser un número entre 1 y 17", "error")
            return render_template("barrido.html", 
                                 resultados=resultados, 
                                 tarjeta=tarjeta, 
                                 puerto=puerto,
                                 habilitar_nombres=habilitar_nombres,
                                 available_olts=Config.get_available_olts())
        
        # Validar formato de puerto (0-16)
        if not re.match(r'^(1[0-6]|[0-9])$', puerto):
            flash("Puerto debe ser un número entre 0 y 16", "error")
            return render_template("barrido.html", 
                                 resultados=resultados, 
                                 tarjeta=tarjeta, 
                                 puerto=puerto,
                                 habilitar_nombres=habilitar_nombres,
                                 available_olts=Config.get_available_olts())
        
        try:
            connection_service = get_connection_for_session()
            ont_service = ONTService(connection_service)
            
            # Ejecutar barrido rápido con opción de nombres
            resultados = ont_service.ejecutar_barrido_rapido(
                tarjeta, 
                puerto, 
                incluir_nombres=habilitar_nombres
            )
            
            # Mensaje informativo
            stats = resultados.get('estadisticas', {})
            modo_barrido = "completo" if habilitar_nombres else "rápido"
            flash(f"Barrido {modo_barrido} completado: {stats.get('total', 0)} ONTs "
                  f"({stats.get('online', 0)} online, {stats.get('offline', 0)} offline)", 
                  "success")
                
        except Exception as e:
            session_id = get_session_id()
            user_msg = handle_service_error(e, "ejecutar barrido", session_id)
            flash(user_msg, "error")

    return render_template(
        "barrido.html",
        resultados=resultados,
        tarjeta=tarjeta,
        puerto=puerto,
        habilitar_nombres=habilitar_nombres
    )

@ont_bp.route("/api/delete_ont", methods=["POST"])
def api_delete_ont():
    '''API para eliminar una ONT'''
    try:
        data = request.get_json()
        
        # Validar datos requeridos
        required = ['ont_id', 'board', 'port']
        missing = [field for field in required if not data.get(field)]
        
        if missing:
            return jsonify({
                'status': 'error',
                'error': f'Faltan campos requeridos: {", ".join(missing)}'
            }), 400
        
        connection_service = get_connection_for_session()
        ont_service = ONTService(connection_service)
        
        result = ont_service.eliminar_ont(
            board=data['board'],
            port=data['port'],
            ont_id=data['ont_id']
        )
        
        return jsonify(result)
        
    except Exception as e:
        session_id = get_session_id()
        logger.error(f"Error en API delete_ont (sesión {session_id}): {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@ont_bp.route("/search")
def search_page():
    """Página de búsqueda de ONT por SN"""
    return render_template("search.html")


@ont_bp.route("/api/search_ont", methods=["POST"])
def api_search_ont():
    """API para buscar una ONT por Serial Number en toda la OLT"""
    try:
        data = request.get_json()
        sn = data.get('sn', '').strip().upper()
        
        if not sn or len(sn) < 8:
            return jsonify({
                'status': 'error',
                'error': 'Serial Number inválido'
            }), 400
        
        connection_service = get_connection_for_session()
        ont_service = ONTService(connection_service)
        
        # Buscar ONT en toda la OLT
        result = ont_service.buscar_ont_por_sn(sn)
        
        return jsonify(result)
        
    except Exception as e:
        session_id = get_session_id()
        logger.error(f"Error en API search_ont (sesión {session_id}): {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500
    
# ============ CORRECCIÓN 12: Manejo de errores global mejorado ============
@ont_bp.errorhandler(Exception)
def handle_error(error):
    """Manejo global de errores"""
    session_id = session.get('session_id', 'unknown')
    logger.error(f"Error no manejado en sesión {session_id}: {error}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    
    # Si es una petición AJAX (API), devolver JSON
    if request.path.startswith('/api/'):
        return jsonify({
            "error": "Error interno del servidor",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }), 500
    
    # Si es una petición normal, mostrar mensaje flash
    flash("Ha ocurrido un error inesperado. Por favor intente nuevamente.", "error")
    return redirect(url_for('ont.home'))