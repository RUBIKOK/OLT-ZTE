# services/ont_db.py
import sqlite3
import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class ONTDatabase:
    """Maneja la base de datos SQLite para ONTs"""
    
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'onts.db')
    
    @classmethod
    def init_db(cls):
        """Inicializa la base de datos y crea la tabla si no existe"""
        try:
            # Crear directorio data si no existe
            os.makedirs(os.path.dirname(cls.DB_PATH), exist_ok=True)
            
            conn = sqlite3.connect(cls.DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS onts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tarjeta TEXT NOT NULL,
                    puerto TEXT NOT NULL,
                    onu_id TEXT NOT NULL,
                    sn TEXT NOT NULL,
                    name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(tarjeta, puerto, onu_id)
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_sn ON onts(sn)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_location ON onts(tarjeta, puerto)
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Base de datos inicializada correctamente")
            
        except Exception as e:
            logger.error(f"Error inicializando base de datos: {e}")
            raise
    
    @classmethod
    def guardar_ont(cls, tarjeta: str, puerto: str, onu_id: str, sn: str, name: str = None):
        """Guarda o actualiza una ONT en la base de datos"""
        try:
            conn = sqlite3.connect(cls.DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO onts (tarjeta, puerto, onu_id, sn, name, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (tarjeta, puerto, onu_id, sn, name))
            
            conn.commit()
            conn.close()
            logger.info(f"ONT guardada: {tarjeta}/{puerto}:{onu_id} - SN: {sn}")
            
        except Exception as e:
            logger.error(f"Error guardando ONT: {e}")
            raise
    
    @classmethod
    def guardar_onts_batch(cls, onts: List[Dict]):
        """Guarda múltiples ONTs en un batch (más eficiente)"""
        try:
            conn = sqlite3.connect(cls.DB_PATH)
            cursor = conn.cursor()
            
            for ont in onts:
                cursor.execute('''
                    INSERT OR REPLACE INTO onts (tarjeta, puerto, onu_id, sn, name, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (
                    ont.get('tarjeta'),
                    ont.get('puerto'),
                    ont.get('onu_id'),
                    ont.get('sn'),
                    ont.get('name')
                ))
            
            conn.commit()
            conn.close()
            logger.info(f"Batch guardado: {len(onts)} ONTs")
            
        except Exception as e:
            logger.error(f"Error guardando batch de ONTs: {e}")
            raise
    
    @classmethod
    def obtener_ont_por_sn(cls, sn: str) -> Optional[Dict]:
        """Obtiene una ONT por su serial number"""
        try:
            conn = sqlite3.connect(cls.DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT *
                FROM onts
                WHERE sn LIKE ?
                OR name LIKE ?
            ''', ('%' + sn + '%', '%' + sn + '%'))
                        
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            return None
            
        except Exception as e:
            logger.error(f"Error buscando ONT por SN {sn}: {e}")
            return None
    
    @classmethod
    def obtener_ont_por_ubicacion(cls, tarjeta: str, puerto: str, onu_id: str) -> Optional[Dict]:
        """Obtiene una ONT por su ubicación"""
        try:
            conn = sqlite3.connect(cls.DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM onts WHERE tarjeta = ? AND puerto = ? AND onu_id = ?
            ''', (tarjeta, puerto, onu_id))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            return None
            
        except Exception as e:
            logger.error(f"Error buscando ONT por ubicación: {e}")
            return None
    
    @classmethod
    def obtener_todas_onts(cls) -> List[Dict]:
        """Obtiene todas las ONTs de la base de datos"""
        try:
            conn = sqlite3.connect(cls.DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM onts ORDER BY tarjeta, puerto, onu_id
            ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error obteniendo todas las ONTs: {e}")
            return []
    
    @classmethod
    def obtener_onts_por_puerto(cls, tarjeta: str, puerto: str) -> List[Dict]:
        """Obtiene todas las ONTs de un puerto específico"""
        try:
            conn = sqlite3.connect(cls.DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM onts WHERE tarjeta = ? AND puerto = ?
                ORDER BY onu_id
            ''', (tarjeta, puerto))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error obteniendo ONTs del puerto {tarjeta}/{puerto}: {e}")
            return []
    
    @classmethod
    def eliminar_ont(cls, tarjeta: str, puerto: str, onu_id: str):
        """Elimina una ONT de la base de datos"""
        try:
            conn = sqlite3.connect(cls.DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM onts WHERE tarjeta = ? AND puerto = ? AND onu_id = ?
            ''', (tarjeta, puerto, onu_id))
            
            conn.commit()
            conn.close()
            logger.info(f"ONT eliminada: {tarjeta}/{puerto}:{onu_id}")
            
        except Exception as e:
            logger.error(f"Error eliminando ONT: {e}")
            raise
    
    @classmethod
    def actualizar_name(cls, tarjeta: str, puerto: str, onu_id: str, name: str):
        """Actualiza solo el name de una ONT"""
        try:
            conn = sqlite3.connect(cls.DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE onts SET name = ?, updated_at = CURRENT_TIMESTAMP
                WHERE tarjeta = ? AND puerto = ? AND onu_id = ?
            ''', (name, tarjeta, puerto, onu_id))
            
            conn.commit()
            conn.close()
            logger.info(f"Name actualizado para ONT {tarjeta}/{puerto}:{onu_id}")
            
        except Exception as e:
            logger.error(f"Error actualizando name de ONT: {e}")
            raise
    
    @classmethod
    def limpiar_tabla(cls):
        """Elimina todos los registros de la tabla (usar con cuidado)"""
        try:
            conn = sqlite3.connect(cls.DB_PATH)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM onts')
            
            conn.commit()
            conn.close()
            logger.warning("Tabla de ONTs limpiada completamente")
            
        except Exception as e:
            logger.error(f"Error limpiando tabla: {e}")
            raise