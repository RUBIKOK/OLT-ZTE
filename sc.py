# scripts/sincronizar_onts.py
import sys
import os
import logging

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ont_service import ONTService
from session import SessionConnection  # Asumiendo que tienes esta clase
from services.ont_db import ONTDatabase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def sincronizar_base_datos():
    """
    Script para sincronizar la base de datos con la configuración actual de la OLT
    """
    try:
        # 1. Inicializar base de datos
        logger.info("Inicializando base de datos...")
        ONTDatabase.init_db()
        
        # 2. Crear conexión a la OLT
        # Asumiendo que tienes una clase SessionConnection configurada
        session = SessionConnection(
            host='10.0.0.62',  # IP de la OLT del show run
            username='zte',
            password='zte',
            device_type='zte_zxros'
        )
        
        session.connect()
        
        # 3. Crear servicio y ejecutar consulta completa
        service = ONTService(session)
        
        logger.info("Consultando configuración completa de la OLT...")
        resultado = service.consultar_y_guardar_todas_onts()
        
        # 4. Mostrar resultados
        print("\n" + "="*80)
        print("SINCRONIZACIÓN COMPLETADA")
        print("="*80)
        print(f"Total de ONTs encontradas: {resultado['total_onts']}")
        
        print("\nESTADÍSTICAS POR PUERTO:")
        print("-"*80)
        for puerto, stats in resultado['estadisticas_por_puerto'].items():
            print(f"Puerto {puerto}:")
            print(f"  Total: {stats['total_onts']}")
            print(f"  Con nombre: {stats['onts_con_name']}")
            print(f"  Sin nombre: {stats['onts_sin_name']}")
        
        print("\nPRIMERAS 10 ONTs GUARDADAS:")
        print("-"*80)
        for i, ont in enumerate(resultado['onts'][:10], 1):
            print(f"{i}. {ont['tarjeta']}/{ont['puerto']}:{ont['onu_id']} - "
                  f"SN: {ont['sn']} - Name: {ont.get('name', 'SIN NOMBRE')}")
        
        if len(resultado['onts']) > 10:
            print(f"... y {len(resultado['onts']) - 10} más")
        
        # 5. Ejemplo de consulta a la base de datos
        print("\nCONSULTANDO BASE DE DATOS:")
        print("-"*80)
        
        # Obtener todas las ONTs
        todas = ONTDatabase.obtener_todas_onts()
        print(f"Total en base de datos: {len(todas)}")
        
        # Buscar una ONT específica (ejemplo)
        sn_buscar = "VSOL007A55EB"
        ont_encontrada = ONTDatabase.obtener_ont_por_sn(sn_buscar)
        if ont_encontrada:
            print(f"ONT con SN {sn_buscar} encontrada:")
            print(f"  Ubicación: {ont_encontrada['tarjeta']}/{ont_encontrada['puerto']}:{ont_encontrada['onu_id']}")
            print(f"  Name: {ont_encontrada.get('name', 'SIN NOMBRE')}")
        
        session.disconnect()
        
    except Exception as e:
        logger.error(f"Error en sincronización: {e}")
        raise

if __name__ == "__main__":
    sincronizar_base_datos()