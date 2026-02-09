# services/ont_service.py - VERSIÓN CORREGIDA

import datetime
from typing import List, Dict
import logging
import re
import time
from models.ont_model import ONT, ONTCollection

logger = logging.getLogger(__name__)

class ONTService:
    """Servicio para operaciones con ONTs"""
    
    def __init__(self, session_connection):
        """
        Args:
            session_connection: Instancia de SessionConnection del pool
        """
        self.session_connection = session_connection
    
    def obtener_onts(self, tarjeta: str, puerto: str) -> ONTCollection:
        """Obtiene información de ONTs para un puerto específico"""
        try:
            logger.info(f"Iniciando consulta de ONTs para tarjeta {tarjeta}, puerto {puerto} en sesión {self.session_connection.session_id}")
            
            # Validación de parámetros
            if not self._validate_parameters(tarjeta, puerto):
                raise ValueError(f"Parámetros inválidos: tarjeta={tarjeta}, puerto={puerto}")
            
            # Detectar tipo de OLT (Huawei o ZTE)
            olt_type = 'ZTE'
            
            # Obtener datos según el tipo de OLT
            if olt_type == 'ZTE':
                onts_data = self._obtener_onts_zte(tarjeta, puerto)
            else:
                onts_data = self._obtener_onts_huawei(tarjeta, puerto)
            
            # Crear colección
            collection = ONTCollection()
            valid_onts = 0
            
            for ont_id, ont_data in onts_data.items():
                try:
                    ont = ONT(**ont_data)
                    collection.add_ont(ont)
                    valid_onts += 1
                except Exception as ont_error:
                    logger.warning(f"Error creando ONT {ont_id}: {ont_error}")
                    continue
            
            logger.info(f"Se procesaron {valid_onts}/{len(onts_data)} ONTs válidas en sesión {self.session_connection.session_id}")
            return collection
            
        except Exception as e:
            logger.error(f"Error obteniendo ONTs para {tarjeta}/{puerto}: {e}")
            try:
                self.session_connection.exit_interface()
            except:
                pass
            raise
    
    def obtener_autofind_onts(self) -> List[Dict[str, str]]:
        """Obtiene información de ONTs detectadas automáticamente (autofind)"""
        try:
            logger.info(f"Iniciando consulta de autofind ONTs en sesión {self.session_connection.session_id}")
            
            # Asegurar que estamos en modo config global antes del comando autofind
            self.session_connection.ensure_config_mode()
            
            # ============ CORRECCIÓN 3: Timeout específico para autofind ============
            # Ejecutar comando autofind con timeout largo
            output_autofind = self.session_connection.execute_global_command(
                "show gpon onu uncfg",
                delay_factor=3,  # Factor de delay más alto
                timeout=45       # Timeout más largo para autofind
            )

            # Logging limitado para evitar logs enormes
            logger.debug(f"Output Autofind (primeros 1000 chars): {output_autofind[:1000]}...")
            
            # Parsear datos
            autofind_onts = self._parse_autofind_data(output_autofind)
            
            logger.info(f"Se encontraron {len(autofind_onts)} ONTs en autofind en sesión {self.session_connection.session_id}")
            return autofind_onts
            
        except Exception as e:
            logger.error(f"Error obteniendo ONTs autofind en sesión {self.session_connection.session_id}: {e}")
            # Asegurar modo config en caso de error
            try:
                self.session_connection.ensure_config_mode()
            except:
                pass
            raise
    
    # ============ CORRECCIÓN 4: Validación de parámetros ============
    def _validate_parameters(self, tarjeta: str, puerto: str) -> bool:
        """Valida los parámetros de entrada"""
        try:
            # Validar tarjeta (1-17)
            if not re.match(r'^(1[0-7]|[1-9])$', tarjeta):
                logger.error(f"Tarjeta inválida: {tarjeta}")
                return False
            
            # Validar puerto (0-16)
            if not re.match(r'^(1[0-6]|[0-9])$', puerto):
                logger.error(f"Puerto inválido: {puerto}")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error validando parámetros: {e}")
            return False
    
    def _parse_autofind_data(self, output_autofind: str) -> List[Dict[str, str]]:
        """Parsea la información de ONTs no configuradas (múltiples formatos)"""
        autofind_onts = []
        
        if not output_autofind or len(output_autofind.strip()) < 10:
            logger.warning("Output de autofind vacío o muy corto")
            return autofind_onts
        
        # Detectar el formato del output
        format_type = self._detect_autofind_format(output_autofind)
        
        if format_type == 'table':
            # Formato tipo tabla (show gpon onu uncfg)
            autofind_onts = self._parse_table_format(output_autofind)
        elif format_type == 'blocks':
            # Formato de bloques (display ont autofind all)
            autofind_onts = self._parse_blocks_format(output_autofind)
        else:
            logger.warning("Formato de autofind no reconocido")
        
        logger.info(f"Autofind parsing: {len(autofind_onts)} ONTs válidas encontradas")
        return autofind_onts


    def _detect_autofind_format(self, output: str) -> str:
        """Detecta el formato del output de autofind"""
        # Formato tabla: tiene "OnuIndex" y "gpon-onu_"
        if 'OnuIndex' in output and 'gpon-onu_' in output:
            return 'table'
        
        # Formato bloques: tiene "Number:" y campos separados por ":"
        if 'Number:' in output and 'F/S/P:' in output:
            return 'blocks'
        
        return 'unknown'


    def _parse_table_format(self, output: str) -> List[Dict[str, str]]:
        """Parsea formato tipo tabla (show gpon onu uncfg)"""
        onts = []
        lines = output.split('\n')
        
        # Buscar el header y la línea de separación
        data_started = False
        
        for line in lines:
            line = line.strip()
            
            # Saltar líneas vacías
            if not line:
                continue
            
            # Detectar línea de separación (marca el inicio de datos)
            if '---' in line:
                data_started = True
                continue
            
            # Saltar header
            if 'OnuIndex' in line or 'Sn' in line or 'State' in line:
                continue
            
            # Parsear líneas de datos
            if data_started and 'gpon-onu_' in line:
                ont_data = self._parse_table_line(line)
                if ont_data:
                    onts.append(ont_data)
        
        return onts


    def _parse_table_line(self, line: str) -> Dict[str, str]:
        """Parsea una línea del formato tabla"""
        # Formato: gpon-onu_1/2/3:1         HWTC00FFF039        unknown
        parts = line.split()
        
        if len(parts) < 2:
            return None
        
        onu_index = parts[0]  # gpon-onu_1/2/3:1
        sn = parts[1]         # HWTC00FFF039
        state = parts[2] if len(parts) > 2 else 'unknown'
        
        # Parsear el OnuIndex: gpon-onu_F/S/P:ID
        try:
            # Extraer F/S/P:ID
            if 'gpon-onu_' in onu_index:
                fsp_part = onu_index.split('gpon-onu_')[1]  # 1/2/3:1
                
                # Separar F/S/P de ID
                if ':' in fsp_part:
                    fsp, ont_id = fsp_part.split(':')
                else:
                    fsp = fsp_part
                    ont_id = '1'
                
                # Parsear F/S/P
                fsp_parts = fsp.split('/')
                if len(fsp_parts) == 3:
                    frame = fsp_parts[0]
                    slot = fsp_parts[1]   # board
                    port = fsp_parts[2]
                    
                    ont_data = {
                        'number': ont_id,
                        'fsp': fsp,
                        'board': slot,
                        'port': port,
                        'sn': sn,
                        'sn_hex': sn,  # En este formato ya viene el SN limpio
                        'state': state,
                        'pon_type': self._detect_pon_type_from_sn(sn),
                        'vendor_id': sn[:4] if len(sn) >= 4 else 'Unknown',
                        'type': 'Unknown',
                        'ont_version': '',
                        'software_version': '',
                        'equipment_id': '',
                        'autofind_time': '',
                        'password': '',
                        'loid': ''
                    }
                    
                    # Validar SN
                    if len(sn) >= 8:
                        return ont_data
                    else:
                        logger.warning(f"SN muy corto en tabla: {sn}")
                        
        except (IndexError, ValueError) as e:
            logger.warning(f"Error parseando línea de tabla: {line} - {e}")
        
        return None


    def _detect_pon_type_from_sn(self, sn: str) -> str:
        """Detecta el tipo de PON basado en el vendor ID del SN"""
        if not sn or len(sn) < 4:
            return 'GPON'
        
        vendor = sn[:4].upper()
        
        # Vendors comunes de GPON
        gpon_vendors = ['HWTC', 'GPTF', 'MONU', 'VSOL', 'ZTEG', 'ALCL']
        
        # Vendors comunes de XG-PON (10G)
        xgpon_vendors = ['HWTX', 'ZTEX']
        
        if vendor in xgpon_vendors:
            return 'XG-PON'
        elif vendor in gpon_vendors or vendor.startswith('D031'):
            return 'GPON'
        else:
            return 'GPON'  # Default


    def _parse_blocks_format(self, output: str) -> List[Dict[str, str]]:
        """Parsea formato de bloques (display ont autofind all)"""
        autofind_onts = []
        
        # Dividir por bloques usando la línea de separación
        separator_patterns = [
            '----------------------------------------------------------------------------',
            '---------------------------------------------------------------------',
            '═' * 50
        ]
        
        blocks = [output]
        
        for separator in separator_patterns:
            if separator in output:
                blocks = output.split(separator)
                break
        
        # Si no hay separadores, intentar por bloques de texto
        if len(blocks) == 1:
            blocks = self._split_by_ont_blocks(output)
        
        processed_blocks = 0
        valid_onts = 0
        
        for block in blocks:
            processed_blocks += 1
            if not block.strip():
                continue
            
            ont_data = self._parse_autofind_block(block.strip())
            if ont_data:
                autofind_onts.append(ont_data)
                valid_onts += 1
        
        logger.info(f"Bloques procesados: {processed_blocks}, ONTs válidas: {valid_onts}")
        return autofind_onts
    
    def _detect_olt_type(self) -> str:
        """Detecta el tipo de OLT (Huawei o ZTE)"""
        try:
            # Ejecutar comando simple para detectar
            output = self.session_connection.execute_command("show version", timeout=10)
            
            if 'ZTE' in output.upper() or 'ZXAN' in output.upper():
                return 'ZTE'
            elif 'HUAWEI' in output.upper() or 'MA5' in output.upper():
                return 'HUAWEI'
            else:
                # Si no puede detectar, asumir Huawei por defecto
                return 'HUAWEI'
        except:
            return 'HUAWEI'


    def _obtener_onts_zte(self, tarjeta: str, puerto: str) -> Dict[str, dict]:
        """Obtiene ONTs de OLT ZTE"""
        onts_data = {}
        
        try:
            # Comando para obtener estado de ONUs
            output_state = self.session_connection.execute_command(
                f"show gpon onu state gpon-olt_1/{tarjeta}/{puerto}",
                delay_factor=2,
                timeout=30
            )
            logger.debug(f"Output State (primeros 500 chars): {output_state[:500]}...")
            
            # Parsear datos de estado
            self._parse_zte_state_data(output_state, onts_data, tarjeta, puerto)
            
            # Obtener información óptica para cada ONT
            for ont_id in list(onts_data.keys()):
                try:
                    output_power = self.session_connection.execute_command(
                        f"show pon power attenuation gpon-onu_1/{tarjeta}/{puerto}:{ont_id}",
                        delay_factor=2,
                        timeout=20
                    )
                    self._parse_zte_power_data(output_power, onts_data, ont_id)
                except Exception as e:
                    logger.warning(f"Error obteniendo power para ONT {ont_id}: {e}")
                    # Asignar valores null si no se puede obtener
                    if ont_id in onts_data:
                        onts_data[ont_id].update({
                            'ont_rx': None,
                            'olt_rx': None,
                            'temperature': None,
                            'distance': None
                        })
            
            try:
                onts_list = list(onts_data.values())
                onts_enriquecidas = self._enriquecer_con_descripciones_zte(
                     onts_list, tarjeta, puerto)

                # Actualizar los valores de vuelta en el dict principal
                for ont in onts_enriquecidas:
                     ont_id = ont['id']
                     if ont_id in onts_data:
                         onts_data[ont_id]['descripcion'] = ont.get('descripcion')

            except Exception as e:
                 logger.warning(f"No se pudo enriquecer con descripciones: {e}")
                
            return onts_data
            
        except Exception as e:
            logger.error(f"Error obteniendo ONTs ZTE: {e}")
            return onts_data


    def _obtener_onts_huawei(self, tarjeta: str, puerto: str) -> Dict[str, dict]:
        """Obtiene ONTs de OLT Huawei"""
        onts_data = {}
        
        try:
            # Entrar a la interfaz GPON
            self.session_connection.enter_interface(tarjeta)
            
            try:
                output_optical = self.session_connection.execute_command(
                    f"display ont optical-info {puerto} all",
                    delay_factor=2,
                    timeout=30
                )
                
                output_summary = self.session_connection.execute_command(
                    f"display ont info summary {puerto}",
                    delay_factor=2,
                    timeout=25
                )
                
            finally:
                try:
                    self.session_connection.exit_interface()
                except Exception as exit_error:
                    logger.warning(f"Error saliendo de interfaz: {exit_error}")
            
            logger.debug(f"Output Summary (primeros 500 chars): {output_summary[:500]}...")
            logger.debug(f"Output Optical (primeros 500 chars): {output_optical[:500]}...")
            
            # Parsear datos
            onts_data = self._parse_ont_data(output_summary, output_optical, tarjeta, puerto)
            
            return onts_data
            
        except Exception as e:
            logger.error(f"Error obteniendo ONTs Huawei: {e}")
            try:
                self.session_connection.exit_interface()
            except:
                pass
            return onts_data


    def _parse_zte_state_data(self, output: str, onts: Dict[str, dict], 
                            tarjeta: str, puerto: str):
        """Parsea el output de 'show gpon onu state' de ZTE"""
        lines = output.split('\n')
        data_started = False
        onts_found = 0
        
        for line in lines:
            line = line.strip()
            
            # Detectar línea de separación
            if '---' in line:
                data_started = True
                continue
            
            # Saltar headers
            if 'OnuIndex' in line or 'Admin State' in line:
                continue
            
            # Parsear líneas de datos
            if data_started and 'gpon-onu_' in line:
                parts = line.split()
                
                if len(parts) >= 4:
                    try:
                        # Formato: gpon-onu_1/2/2:1  enable  enable  operation  working
                        onu_index = parts[0]  # gpon-onu_1/2/2:1
                        admin_state = parts[1]
                        omcc_state = parts[2]
                        o7_state = parts[3]
                        phase_state = parts[4] if len(parts) > 4 else 'unknown'
                        # Extraer ONT ID del index
                        if ':' in onu_index:
                            ont_id = onu_index.split(':')[1]
                            
                            # Determinar estado general
                            if admin_state == 'disable':
                                estado = 'disabled'
                            elif phase_state == 'working' and o7_state == 'operation':
                                estado = 'online'
                            elif phase_state.lower() == 'dyinggasp' or 'dying' in phase_state.lower():
                                estado = 'dying_gasp'
                            elif phase_state == 'LOS' or phase_state == 'los':
                                estado = 'LOS'
                            elif phase_state == 'Offline':
                                estado = 'offline'
                            else:
                                # Log para estados desconocidos
                                logger.warning(f"Estado desconocido para ONT {ont_id}: phase={phase_state}, o7={o7_state}, admin={admin_state}")
                                estado = 'offline'
                            
                            onts[ont_id] = {
                                'id': ont_id,
                                'tarjeta': tarjeta,
                                'puerto': puerto,
                                'estado': estado,
                                'last_down_cause': None,
                                'last_down_time': None,
                                'descripcion': onu_index,
                                'ont_rx': None,
                                'olt_rx': None,
                                'temperature': None,
                                'distance': None
                            }
                            onts_found += 1
                            
                    except (IndexError, ValueError) as e:
                        logger.warning(f"Error parseando línea ZTE state: '{line}' - {e}")
        
        logger.info(f"ZTE State parsing: {onts_found} ONTs encontradas")


    def _parse_zte_power_data(self, output: str, onts: Dict[str, dict], ont_id: str):
        """Parsea el output de 'show pon power attenuation' de ZTE"""
        lines = output.split('\n')
        
        ont_rx = None
        olt_rx = None
        
        for line in lines:
            line = line.strip()
            
            # Línea up: OLT Rx y ONU Tx
            # up      Rx :-20.491(dbm)      Tx:2.649(dbm)        23.140(dB)
            if line.startswith('up'):
                parts = line.split()
                for i, part in enumerate(parts):
                    # Soportar ambos formatos: "Rx:" o "Rx"
                    if part.startswith('Rx:') or part == 'Rx':
                        if part == 'Rx' and i + 1 < len(parts):
                            # Formato: "Rx :-20.491(dbm)"
                            olt_rx_str = parts[i + 1].replace(':', '').replace('(dbm)', '').strip()
                        else:
                            # Formato: "Rx:-20.491(dbm)"
                            olt_rx_str = part.split(':')[1].replace('(dbm)', '').strip()
                        olt_rx = self._safe_float_parse(olt_rx_str)
                        break
            
            # Línea down: OLT Tx y ONU Rx
            # down    Tx :6.644(dbm)        Rx:-17.092(dbm)      23.736(dB)
            elif line.startswith('down'):
                parts = line.split()
                for i, part in enumerate(parts):
                    # Soportar ambos formatos: "Rx:" o "Rx"
                    if part.startswith('Rx:') or part == 'Rx':
                        if part == 'Rx' and i + 1 < len(parts):
                            # Formato: "Rx :-17.092(dbm)"
                            ont_rx_str = parts[i + 1].replace(':', '').replace('(dbm)', '').strip()
                        else:
                            # Formato: "Rx:-17.092(dbm)"
                            ont_rx_str = part.split(':')[1].replace('(dbm)', '').strip()
                        ont_rx = self._safe_float_parse(ont_rx_str)
                        break
        
        # Log para debugging
        logger.debug(f"ONT {ont_id} - ONT Rx: {ont_rx}, OLT Rx: {olt_rx}")
        
        # Actualizar datos
        if ont_id in onts:
            onts[ont_id].update({
                'ont_rx': ont_rx,
                'olt_rx': olt_rx
            })


    def _parse_ont_data(self, output_summary: str, output_optical: str, 
                    tarjeta: str, puerto: str) -> Dict[str, dict]:
        """Parsea los datos de salida de los comandos (Huawei)"""
        onts = {}
        
        if not output_summary or len(output_summary.strip()) < 10:
            logger.warning("Output summary vacío o muy corto")
            return onts
        
        # Parsear summary
        try:
            self._parse_summary_data(output_summary, onts, tarjeta, puerto)
        except Exception as e:
            logger.error(f"Error parseando summary data: {e}")
        
        # Parsear optical info (si existe)
        if output_optical and len(output_optical.strip()) >= 10:
            try:
                self._parse_optical_data(output_optical, onts)
            except Exception as e:
                logger.error(f"Error parseando optical data: {e}")
        
        # Asegurar que todos los ONTs tengan valores null si faltan datos
        for ont_id in onts:
            onts[ont_id].setdefault('ont_rx', None)
            onts[ont_id].setdefault('olt_rx', None)
            onts[ont_id].setdefault('temperature', None)
            onts[ont_id].setdefault('distance', None)
            onts[ont_id].setdefault('last_down_cause', None)
            onts[ont_id].setdefault('last_down_time', None)
        
        return onts


    def _parse_summary_data(self, output_summary: str, onts: Dict[str, dict], 
                        tarjeta: str, puerto: str):
        """Parsea la información del comando summary (Huawei)"""
        lines = output_summary.split('\n')
        
        estado_start = False
        desc_start = False
        lines_processed = 0
        onts_found = 0
        
        for line in lines:
            line = line.strip()
            lines_processed += 1
            
            # Detectar inicio de tablas
            if "ONT  Run     Last" in line or "ONT-ID  Run-state" in line:
                estado_start = True
                desc_start = False
                continue
            elif "ONT        SN        Type" in line or "ONT-ID        SN" in line:
                desc_start = True
                estado_start = False
                continue
            
            # Parsear estados
            if estado_start and line and not line.startswith('-') and not line.startswith('ONT'):
                parts = line.split()
                if len(parts) >= 2 and parts[0].isdigit():
                    try:
                        ont_id = parts[0]
                        estado = parts[1] if len(parts) > 1 else 'unknown'
                        
                        causa = None
                        last_down_time = None
                        
                        # Buscar patrón de fecha/hora
                        if len(parts) > 3:
                            date_pattern = r'\d{4}-\d{2}-\d{2}'
                            time_pattern = r'\d{2}:\d{2}:\d{2}'
                            
                            date_found = None
                            time_found = None
                            
                            for i, part in enumerate(parts[2:], 2):
                                if re.match(date_pattern, part):
                                    date_found = part
                                    if i + 1 < len(parts) and re.match(time_pattern, parts[i + 1]):
                                        time_found = parts[i + 1]
                                        if i + 2 < len(parts) and parts[i + 2] != "-":
                                            causa = parts[i + 2]
                                    break
                            
                            if date_found and time_found:
                                last_down_time = f"{date_found} {time_found}"
                        
                        onts[ont_id] = {
                            'id': ont_id,
                            'tarjeta': tarjeta,
                            'puerto': puerto,
                            'estado': estado,
                            'last_down_cause': causa,
                            'last_down_time': last_down_time,
                            'descripcion': ''
                        }
                        onts_found += 1
                        
                    except (IndexError, ValueError) as e:
                        logger.warning(f"Error parseando línea de estado: '{line}' - {e}")
            
            # Parsear descripciones
            elif desc_start and line and not line.startswith('-'):
                parts = line.split()
                if len(parts) >= 6 and parts[0].isdigit():
                    ont_id = parts[0]
                    if ont_id in onts:
                        desc_parts = []
                        found_desc_start = False
                        
                        for part in parts:
                            if not found_desc_start:
                                if '/' in part and '-' in part:
                                    found_desc_start = True
                                    continue
                            else:
                                desc_parts.append(part)
                        
                        if desc_parts:
                            onts[ont_id]['descripcion'] = '_'.join(desc_parts)
        
        logger.info(f"Summary parsing: {lines_processed} líneas, {onts_found} ONTs encontradas")


    def _parse_optical_data(self, output_optical: str, onts: Dict[str, dict]):
        """Parsea la información del comando optical (Huawei)"""
        optical_lines = output_optical.split('\n')
        optical_parsed = 0
        
        for line in optical_lines:
            line = line.strip()
            if not line or line.startswith('-') or 'ONT' in line:
                continue
            
            parts = line.split()
            
            if len(parts) >= 6 and parts[0].isdigit():
                try:
                    ont_id = parts[0]
                    
                    ont_rx = self._safe_float_parse(parts[1])
                    olt_rx = self._safe_float_parse(parts[3])
                    temperature = self._safe_int_parse(parts[4])
                    distance = self._safe_int_parse(parts[6])
                    
                    if ont_id in onts:
                        onts[ont_id].update({
                            'ont_rx': ont_rx,
                            'olt_rx': olt_rx,
                            'temperature': temperature,
                            'distance': distance
                        })
                        optical_parsed += 1
                        
                except (ValueError, IndexError) as e:
                    logger.warning(f"Error parsing optical line: '{line}' - {e}")
        
        logger.info(f"Optical parsing: {optical_parsed} ONTs con datos ópticos")


    def _safe_float_parse(self, value: str) -> float:
        """Parsea un valor float de forma segura"""
        try:
            return float(value.replace('(dbm)', '').strip())
        except (ValueError, AttributeError):
            return None


    def _safe_int_parse(self, value: str) -> int:
        """Parsea un valor int de forma segura"""
        try:
            return int(value.strip())
        except (ValueError, AttributeError):
            return None

    # ============ CORRECCIÓN 14: Funciones auxiliares para parsing seguro ============
    def _safe_float_parse(self, value: str) -> float:
        """Parsea un valor float de manera segura"""
        try:
            # Limpiar el valor
            cleaned = re.sub(r'[^\d\-.]', '', str(value))
            if cleaned and cleaned != '-':
                return float(cleaned)
        except (ValueError, TypeError):
            pass
        return None

    def _safe_int_parse(self, value: str) -> int:
        """Parsea un valor int de manera segura"""
        try:
            # Limpiar el valor
            cleaned = re.sub(r'[^\d]', '', str(value))
            if cleaned:
                return int(cleaned)
        except (ValueError, TypeError):
            pass
        return None
    
    def obtener_detalles_ont(self, tarjeta: str, puerto: str, ont_id: str) -> str:
        """Obtiene información detallada de una ONT específica"""
        try:
            logger.info(f"Obteniendo detalles para ONT {ont_id} en {tarjeta}/{puerto}")
            
            # Detectar tipo de OLT
            olt_type = 'ZTE'
            
            if olt_type == 'ZTE':
                return self._obtener_detalles_ont_zte(tarjeta, puerto, ont_id)
            else:
                return self._obtener_detalles_ont_huawei(tarjeta, puerto, ont_id)
                
        except Exception as e:
            logger.error(f"Error obteniendo detalles de ONT {ont_id}: {e}")
            raise


    def _obtener_detalles_ont_zte(self, tarjeta: str, puerto: str, ont_id: str) -> str:
        """Obtiene detalles de ONT en OLT ZTE"""
        try:
            # Comando para obtener información detallada
            output = self.session_connection.execute_command(
                f"show gpon onu detail-info gpon-onu_1/{tarjeta}/{puerto}:{ont_id}",
                delay_factor=2,
                timeout=30
            )
            
            logger.debug(f"Output ZTE detail (primeros 500 chars): {output[:500]}...")
            
            # Parsear el output
            info_basica = self._parsear_info_basica_zte(output)
            tabla_historico = self._parsear_historico_zte(output)
            
            # Formatear resultado
            resultado = "=" * 50 + "\n"
            resultado += "INFORMACIÓN BÁSICA DE LA ONT\n"
            resultado += "=" * 50 + "\n"
            resultado += info_basica + "\n\n"
            
            resultado += "=" * 50 + "\n"
            resultado += "HISTORIAL DE CONEXIONES\n"
            resultado += "=" * 50 + "\n"
            resultado += tabla_historico
            
            logger.info(f"Detalles de ONT {ont_id} (ZTE) obtenidos exitosamente")
            return resultado
            
        except Exception as e:
            logger.error(f"Error obteniendo detalles ONT ZTE {ont_id}: {e}")
            raise


    def _obtener_detalles_ont_huawei(self, tarjeta: str, puerto: str, ont_id: str) -> str:
        """Obtiene detalles de ONT en OLT Huawei"""
        try:
            # Entrar a la interfaz
            self.session_connection.enter_interface(tarjeta)
            
            try:
                outputinfo = self.session_connection.execute_command(
                    f"display ont info {puerto} {ont_id}",
                    delay_factor=2,
                    timeout=30
                )
                
                outputhistory = self.session_connection.execute_command(
                    f"display ont register-info {puerto} {ont_id}",
                    delay_factor=2,
                    timeout=25
                )
                
            finally:
                try:
                    self.session_connection.exit_interface()
                except Exception as exit_error:
                    logger.warning(f"Error saliendo de interfaz: {exit_error}")
            
            # Limpiar el output
            cleaned_output_info = self.obtener_info_basica_ont(outputinfo)
            cleaned_output_history = self._formatear_tabla_registros(outputhistory)
            
            # Unir ambas salidas
            resultado = "=" * 50 + "\n"
            resultado += "INFORMACIÓN BÁSICA DE LA ONT\n"
            resultado += "=" * 50 + "\n"
            resultado += cleaned_output_info + "\n\n"
            
            resultado += "=" * 50 + "\n"
            resultado += "HISTORIAL\n"
            resultado += "=" * 50 + "\n"
            resultado += cleaned_output_history
            
            logger.info(f"Detalles de ONT {ont_id} (Huawei) obtenidos exitosamente")
            return resultado
            
        except Exception as e:
            logger.error(f"Error obteniendo detalles ONT Huawei {ont_id}: {e}")
            try:
                self.session_connection.exit_interface()
            except:
                pass
            raise


    def _parsear_info_basica_zte(self, output: str) -> str:
        """Parsea la información básica de una ONT ZTE"""
        lines = output.split('\n')
        info_lines = []
        start_found = False
        history_start = False
        
        for line in lines:
            line_stripped = line.strip()
            
            # Detectar inicio de información
            if 'ONU interface:' in line_stripped:
                start_found = True
            
            # Detectar inicio de tabla de histórico
            if 'Authpass Time' in line_stripped or 'OfflineTime' in line_stripped:
                history_start = True
                break
            
            # Recolectar líneas de información básica
            if start_found and not history_start:
                if line_stripped and not line_stripped.startswith('--'):
                    info_lines.append(line_stripped)
        
        return '\n'.join(info_lines)


    def _parsear_historico_zte(self, output: str) -> str:
        """Parsea la tabla de histórico de una ONT ZTE"""
        lines = output.split('\n')
        registros = []
        in_table = False
        
        for line in lines:
            line_stripped = line.strip()
            
            # Detectar inicio de tabla
            if 'Authpass Time' in line_stripped:
                in_table = True
                continue
            
            # Parsear líneas de la tabla
            if in_table and line_stripped:
                # Ignorar líneas de separación
                if line_stripped.startswith('--'):
                    continue
                
                # Parsear línea de datos
                # Formato: "   1   2025-10-17 08:27:34    2025-10-18 06:02:46     DyingGasp"
                parts = line_stripped.split()
                
                if len(parts) >= 3 and parts[0].isdigit():
                    index = parts[0]
                    auth_time = f"{parts[1]} {parts[2]}" if len(parts) > 2 else parts[1]
                    
                    # Detectar si está online (fecha 0000-00-00)
                    if len(parts) >= 5:
                        offline_time = f"{parts[3]} {parts[4]}"
                        
                        # Si la fecha es 0000-00-00, está online
                        if '0000-00-00' in offline_time:
                            cause = 'ONU is currently online'
                            offline_time_display = '-'
                        else:
                            cause = ' '.join(parts[5:]) if len(parts) > 5 else '-'
                            offline_time_display = offline_time
                    else:
                        offline_time_display = '-'
                        cause = 'ONU is currently online'
                    
                    registros.append({
                        'index': index,
                        'auth_time': auth_time,
                        'offline_time': offline_time_display,
                        'cause': cause
                    })
        
        # Formatear tabla
        if not registros:
            return "No hay histórico disponible"
        
        tabla = "HISTÓRICO DE REGISTROS:\n"
        tabla += "#   UP AUTH TIME             OFFLINE TIME              DOWN REASON\n"
        tabla += "-" * 85 + "\n"
        
        for registro in registros:
            index = registro['index']
            auth_time = registro['auth_time']
            offline_time = registro['offline_time']
            cause = registro['cause']
            
            if offline_time == '-':
                linea = f"{index:>3}  {auth_time:23}  {offline_time:24}  {cause}"
            else:
                linea = f"{index:>3}  {auth_time:23}  {offline_time:23}  {cause}"
            
            tabla += linea + "\n"
        
        return tabla


    def obtener_info_basica_ont(self, output: str) -> str:
        """Extrae solo la sección de información básica hasta Global ONT-ID (Huawei)"""
        lines = output.split('\n')
        basic_info_lines = []
        start_found = False
        
        for line in lines:
            line = line.strip()
            
            if not line:
                continue
                
            # Buscar el inicio de la información básica
            if 'F/S/P' in line and ':' in line:
                start_found = True
                
            if start_found:
                basic_info_lines.append(line)
                
                # Detener cuando llegamos al final de la sección básica
                if 'Global ONT-ID' in line and ':' in line:
                    break
                    
                # También detener si encontramos el próximo separador
                if '------------' in line and len(basic_info_lines) > 5:
                    if basic_info_lines and '------------' in basic_info_lines[-1]:
                        basic_info_lines.pop()
                    break
        
        return '\n'.join(basic_info_lines)      


    def _formatear_tabla_registros(self, output_text: str) -> str:
        """Formatea el output de display ont register-info como tabla (Huawei)"""
        try:
            if not isinstance(output_text, str):
                output_text = str(output_text)
                
            lines = output_text.split('\n')
            registros = []
            registro_actual = {}
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Parsear líneas con formato "Clave : Valor"
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if key == 'Index':
                        if registro_actual:
                            registros.append(registro_actual)
                        registro_actual = {'index': value}
                    elif key == 'Auth-type':
                        registro_actual['auth_type'] = value
                    elif key == 'SN':
                        registro_actual['sn'] = value
                    elif key == 'TYPE':
                        registro_actual['type'] = value
                    elif key == 'UpTime':
                        registro_actual['up_time'] = value
                    elif key == 'DownTime':
                        registro_actual['down_time'] = value
                    elif key == 'DownCause':
                        registro_actual['down_cause'] = value
            
            # Agregar el último registro
            if registro_actual:
                registros.append(registro_actual)
            
            # Crear tabla formateada
            tabla = "HISTÓRICO DE REGISTROS:\n"
            tabla += "#   UP AUTH TIME             OFFLINE TIME              DOWN REASON\n"
            tabla += "-" * 80 + "\n"
            
            for registro in registros:
                index = registro.get('index', '')
                up_time = registro.get('up_time', '')
                down_time = registro.get('down_time', '-')
                down_cause = registro.get('down_cause', '-')
                
                if down_time == '-':
                    linea = f"{index:2}  {up_time:23}   ONU is currently online"
                else:
                    linea = f"{index:2}  {up_time:23}   {down_time:23}   {down_cause}"
                
                tabla += linea + "\n"
            
            return tabla
            
        except Exception as e:
            logger.error(f"Error formateando tabla de registros: {e}")
            return f"Error al formatear histórico: {str(e)}\nOutput original:\n{output_text}"

    def ejecutar_barrido_rapido(self, tarjeta: str, puerto: str, incluir_nombres: bool = False) -> dict:
        """
        Ejecuta barrido rápido para obtener información básica de ONTs
        
        Args:
            tarjeta: Número de tarjeta
            puerto: Número de puerto
            incluir_nombres: Si True, obtiene las descripciones de las ONTs (más lento)
        
        Returns:
            dict: Diccionario con ONTs y estadísticas
        """
        try:
            logger.info(f"Iniciando barrido {'completo' if incluir_nombres else 'rápido'} "
                    f"para tarjeta {tarjeta}, puerto {puerto}")
            
            # Validar parámetros
            if not self._validate_parameters(tarjeta, puerto):
                raise ValueError(f"Parámetros inválidos: tarjeta={tarjeta}, puerto={puerto}")
            
            # Detectar tipo de OLT
            olt_type = 'ZTE'
            
            if olt_type == 'ZTE':
                return self._barrido_rapido_zte(tarjeta, puerto, incluir_nombres)
            else:
                return self._barrido_rapido_huawei(tarjeta, puerto)
                
        except Exception as e:
            logger.error(f"Error en barrido rápido {tarjeta}/{puerto}: {e}")
            raise


    def _barrido_rapido_zte(self, tarjeta: str, puerto: str, incluir_nombres: bool = False) -> dict:
        """Barrido rápido para OLT ZTE"""
        try:
            # Comando para obtener estado de ONUs
            output = self.session_connection.execute_command(
                f"show gpon onu state gpon-olt_1/{tarjeta}/{puerto}",
                delay_factor=2,
                timeout=25
            )
            
            logger.debug(f"Output ZTE state (primeros 500 chars): {output[:500]}...")
            
            # Parsear resultados
            onts = self._parsear_barrido_zte(output, tarjeta, puerto)
            
            # Enriquecer con descripciones solo si está habilitado
            if incluir_nombres:
                logger.info(f"Enriqueciendo con descripciones para {len(onts)} ONTs...")
                onts = self._enriquecer_con_descripciones_zte(onts, tarjeta, puerto)
            else:
                logger.info("Modo rápido: omitiendo obtención de descripciones")
            
            # Calcular estadísticas
            total = len(onts)
            online = sum(1 for ont in onts if ont['estado'].lower() == 'online')
            offline = total - online
            
            logger.info(f"Barrido ZTE completado: {total} ONTs ({online} online, {offline} offline)")
            
            return {
                'tarjeta': tarjeta,
                'puerto': puerto,
                'onts': onts,
                'estadisticas': {
                    'total': total,
                    'online': online,
                    'offline': offline
                },
                'incluyo_nombres': incluir_nombres
            }
            
        except Exception as e:
            logger.error(f"Error en barrido ZTE {tarjeta}/{puerto}: {e}")
            raise


    def _barrido_rapido_huawei(self, tarjeta: str, puerto: str) -> dict:
        """Barrido rápido para OLT Huawei"""
        try:
            # Asegurar modo config
            self.session_connection.ensure_config_mode()
            
            # Ejecutar comando
            output = self.session_connection.execute_global_command(
                f"display ont info summary 0/{tarjeta}/{puerto}",
                delay_factor=2,
                timeout=25
            )
            
            # Parsear resultados
            onts = self._parsear_barrido_rapido(output, tarjeta, puerto)
            
            # Calcular estadísticas
            total = len(onts)
            online = sum(1 for ont in onts if ont['estado'].lower() == 'online')
            offline = total - online
            
            logger.info(f"Barrido Huawei completado: {total} ONTs ({online} online, {offline} offline)")
            
            return {
                'tarjeta': tarjeta,
                'puerto': puerto,
                'onts': onts,
                'estadisticas': {
                    'total': total,
                    'online': online,
                    'offline': offline
                }
            }
            
        except Exception as e:
            logger.error(f"Error en barrido Huawei {tarjeta}/{puerto}: {e}")
            raise


    def _parsear_barrido_zte(self, output: str, tarjeta: str, puerto: str) -> list:
        """Parsea la salida de 'show gpon onu state' de ZTE"""
        onts = []
        lines = output.split('\n')
        data_started = False
        
        for line in lines:
            line = line.strip()
            
            # Detectar línea de separación
            if '---' in line:
                data_started = True
                continue
            
            # Saltar headers
            if 'OnuIndex' in line or 'Admin State' in line:
                continue
            
            # Parsear líneas de datos
            if data_started and 'gpon-onu_' in line:
                parts = line.split()
                
                if len(parts) >= 4:
                    try:
                        # Formato: gpon-onu_1/2/2:1  enable  enable  operation  working
                        onu_index = parts[0]  # gpon-onu_1/2/2:1
                        admin_state = parts[1]
                        omcc_state = parts[2]
                        o7_state = parts[3]
                        phase_state = parts[4] if len(parts) > 4 else 'unknown'
                        
                        # Extraer ONT ID del index
                        if ':' in onu_index:
                            ont_id = onu_index.split(':')[1]
                            
                            # Determinar estado (mismo criterio que antes)
                            if admin_state == 'disable':
                                estado = 'disabled'
                            elif phase_state == 'working' and o7_state == 'operation':
                                estado = 'online'
                            elif phase_state.lower() == 'dyinggasp' or 'dying' in phase_state.lower():
                                estado = 'dying_gasp'
                            elif phase_state.upper() == 'LOS' or phase_state == 'los':
                                estado = 'LOS'
                            elif phase_state in ['down', 'failed', 'offline']:
                                estado = 'offline'
                            else:
                                logger.warning(f"Estado desconocido: phase={phase_state}, o7={o7_state}, admin={admin_state}")
                                estado = 'offline'
                            
                            ont = {
                                'id': ont_id,
                                'tarjeta': tarjeta,
                                'puerto': puerto,
                                'descripcion': onu_index,  # Se puede enriquecer después
                                'estado': estado,
                                'admin_state': admin_state,
                                'phase_state': phase_state
                            }
                            
                            onts.append(ont)
                            
                    except (IndexError, ValueError) as e:
                        logger.warning(f"Error parseando línea ZTE: '{line}' - {e}")
        
        logger.info(f"Barrido ZTE parseado: {len(onts)} ONTs encontradas")
        return onts


    def _enriquecer_con_descripciones_zte(self, onts: list, tarjeta: str, puerto: str) -> list:
        """
        Enriquece las ONTs con sus descripciones (opcional)
        Esto puede ser lento si hay muchas ONTs
        """
        try:
            # Solo enriquecer ONTs online para ser más rápido
            for ont in onts:
                # if ont['estado'] == 'online':
                    try:
                        # Obtener descripción de forma rápida
                        output = self.session_connection.execute_command(
                            f"show gpon onu detail-info gpon-onu_1/{tarjeta}/{puerto}:{ont['id']}",
                            delay_factor=1,
                            timeout=15
                        )
                        
                        # Extraer solo el nombre/descripción
                        for line in output.split('\n'):
                            if 'Name:' in line:
                                descripcion = line.split('Name:')[1].strip()
                                ont['descripcion'] = descripcion
                                break
                            elif 'Description:' in line:
                                descripcion = line.split('Description:')[1].strip()
                                # Tomar solo parte del description (puede ser muy largo)
                                if len(descripcion) > 100:
                                    descripcion = descripcion[:97] + '...'
                                ont['descripcion'] = descripcion
                                break
                                
                    except Exception as e:
                        logger.warning(f"No se pudo obtener descripción para ONT {ont['id']}: {e}")
                        ont['descripcion'] = f"ONT-{ont['id']}"
                # else:
                #     # Para ONTs offline, usar un nombre genérico
                #     ont['descripcion'] = f"ONT-{ont['id']} ({ont['estado']})"
            
            return onts
            
        except Exception as e:
            logger.warning(f"Error enriqueciendo con descripciones: {e}")
            return onts


    def _parsear_barrido_rapido(self, output: str, tarjeta: str, puerto: str) -> list:
        """
        Parsea la salida de 'display ont info summary' para barrido rápido (Huawei)
        Extrae: ID, Estado y Descripción
        """
        onts = []
        lines = output.split('\n')
        
        # Buscar la segunda tabla (con descripciones)
        desc_start = False
        
        for line in lines:
            line = line.strip()
            
            # Detectar inicio de la tabla con descripciones
            if "ONT        SN        Type" in line or "ONT-ID        SN" in line:
                desc_start = True
                continue
            
            # Detectar fin de tabla
            if desc_start and line.startswith('---'):
                continue
            
            # Parsear líneas de ONTs
            if desc_start and line and not line.startswith('ONT'):
                parts = line.split()
                
                if len(parts) >= 3 and parts[0].isdigit():
                    ont_id = parts[0]
                    
                    # Buscar donde empieza la descripción
                    desc_parts = []
                    found_power = False
                    
                    for part in parts[1:]:
                        if '/' in part and ('-' in part or part[0].isdigit()):
                            found_power = True
                            continue
                        
                        if found_power:
                            desc_parts.append(part)
                    
                    descripcion = ' '.join(desc_parts) if desc_parts else ''
                    
                    ont = {
                        'id': ont_id,
                        'tarjeta': tarjeta,
                        'puerto': puerto,
                        'descripcion': descripcion,
                        'estado': 'online'
                    }
                    
                    onts.append(ont)
        
        # Segunda pasada: obtener estados de la primera tabla
        estado_start = False
        
        for line in lines:
            line = line.strip()
            
            # Detectar tabla de estados
            if "ONT  Run     Last" in line or "ONT-ID  Run-state" in line:
                estado_start = True
                continue
            elif "ONT        SN        Type" in line:
                estado_start = False
                break
            
            # Parsear estados
            if estado_start and line and not line.startswith('-') and not line.startswith('ONT'):
                parts = line.split()
                if len(parts) >= 2 and parts[0].isdigit():
                    ont_id = parts[0]
                    estado = parts[1] if len(parts) > 1 else 'unknown'
                    
                    # Actualizar el estado en la lista de ONTs
                    for ont in onts:
                        if ont['id'] == ont_id:
                            ont['estado'] = estado
                            break
        
        logger.info(f"Barrido Huawei parseado: {len(onts)} ONTs encontradas")
        return onts

    # ============================================
# 3. BACKEND - Services (services/ont_service.py)
# ============================================

    def obtener_siguiente_onu_id(self, board: str, port: str) -> int:
        """Obtiene el siguiente ID de ONU disponible en un puerto"""
        try:
            # Ejecutar comando para ver configuración actual
            output = self.session_connection.execute_command(
                f"show run interface gpon-olt_1/{board}/{port}",
                delay_factor=2,
                timeout=20
            )
            
            # Parsear IDs existentes
            used_ids = set()
            lines = output.split('\n')
            
            for line in lines:
                line = line.strip()
                # Buscar líneas tipo: "onu 1 type V-SOL-V2801D-1GT1 sn HWTC0037DCC7"
                if line.startswith('onu ') and ' type ' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            onu_id = int(parts[1])
                            used_ids.add(onu_id)
                        except ValueError:
                            continue
            
            # Encontrar el siguiente ID disponible (1-128 típicamente)
            for i in range(1, 129):
                if i not in used_ids:
                    return i
            
            # Si llegamos aquí, el puerto está lleno
            raise Exception("Puerto lleno: no hay IDs disponibles")
            
        except Exception as e:
            logger.error(f"Error obteniendo siguiente ONU ID: {e}")
            raise


    def autorizar_ont(self, board: str, port: str, onu_id: str, sn: str, 
                    onu_type: str, vlan: str, zone: str = "", name: str = "",
                    onu_mode: str = "routing") -> dict:
        """Autoriza una ONT en el OLT"""
        try:
            logger.info(f"Autorizando ONT: {board}/{port}:{onu_id} SN:{sn}")
            
            # Validaciones
            if not all([board, port, onu_id, sn, onu_type, vlan]):
                raise ValueError("Faltan parámetros obligatorios")
            
            # Limpiar SN
            sn_clean = re.sub(r'[^A-Za-z0-9]', '', sn)
            
            # Entrar a modo configuración
            self.session_connection.execute_command("configure terminal", timeout=10)
            
            commands_executed = []
            
            try:
                # 1. Configurar ONU en la interfaz gpon-olt
                cmd1 = f"interface gpon-olt_1/{board}/{port}"
                self.session_connection.execute_command(cmd1, timeout=10)
                commands_executed.append(cmd1)
                
                cmd2 = f"onu {onu_id} type {onu_type} sn {sn_clean}"
                self.session_connection.execute_command(cmd2, timeout=10)
                commands_executed.append(cmd2)
                
                # Salir de la interfaz
                self.session_connection.execute_command("exit", timeout=5)
                
                # 2. Configurar interface gpon-onu
                cmd3 = f"interface gpon-onu_1/{board}/{port}:{onu_id}"
                self.session_connection.execute_command(cmd3, timeout=10)
                commands_executed.append(cmd3)
                
                # Nombre (si se proporciona)
                if name:
                    name_clean = name.replace(' ', '_')
                    cmd4 = f"name {name_clean}"
                    self.session_connection.execute_command(cmd4, timeout=10)
                    commands_executed.append(cmd4)
                    time.sleep(5)
                
                # SN binding
                cmd5 = "sn-bind enable sn"
                self.session_connection.execute_command(cmd5, timeout=10)
                commands_executed.append(cmd5)
                time.sleep(5)
                
                # TCONT
                cmd6 = "tcont 1 name T1 profile UL1G"
                self.session_connection.execute_command(cmd6, timeout=10)
                commands_executed.append(cmd6)
                time.sleep(5)
                
                # GEMPORT
                cmd7 = "gemport 1 unicast tcont 1 dir both"
                self.session_connection.execute_command(cmd7, timeout=10)
                commands_executed.append(cmd7)
                time.sleep(5)
                
                # Encriptación
                cmd8 = "encrypt 1 enable downstream"
                self.session_connection.execute_command(cmd8, timeout=10)
                commands_executed.append(cmd8)
                time.sleep(5)
                
                # Switchport
                cmd9 = "switchport mode hybrid vport 1"
                self.session_connection.execute_command(cmd9, timeout=10)
                commands_executed.append(cmd9)
                time.sleep(5)
                
                # Service port
                cmd10 = f"service-port 1 vport 1 user-vlan {vlan} vlan {vlan}"
                self.session_connection.execute_command(cmd10, timeout=10)
                commands_executed.append(cmd10)
                time.sleep(5)
                
                # Salir de interface
                self.session_connection.execute_command("exit", timeout=5)
                
                # 3. Configurar pon-onu-mng
                cmd11 = f"pon-onu-mng gpon-onu_1/{board}/{port}:{onu_id}"
                self.session_connection.execute_command(cmd11, timeout=10)
                commands_executed.append(cmd11)
                time.sleep(5)
                
                # Service
                # service_name = zone if zone else "ServiceName"
                cmd12 = f"service ServiceName type internet gemport 1 vlan {vlan}"
                self.session_connection.execute_command(cmd12, timeout=10)
                commands_executed.append(cmd12)
                time.sleep(5)
                
                # ============================================
                # ⭐ AQUÍ SE AGREGA EL COMANDO PARA BRIDGING ⭐
                # ============================================
                if onu_mode.lower() == 'bridging':
                    cmd13 = f"vlan port eth_0/1 mode tag vlan {vlan}"
                    self.session_connection.execute_command(cmd13, timeout=10)
                    commands_executed.append(cmd13)
                    logger.info(f"Modo Bridging: VLAN {vlan} configurada en eth_0/1")
                    time.sleep(5)
            
                # Salir
                self.session_connection.execute_command("exit", timeout=5)
                self.session_connection.execute_command("exit", timeout=5)
                
                # Guardar configuración
                self.session_connection.execute_command("write", timeout=30)
                commands_executed.append("write")
                
                logger.info(f"ONT {sn_clean} autorizada exitosamente en {board}/{port}:{onu_id}")
                
                return {
                    'status': 'success',
                    'message': f'ONT autorizada exitosamente en posición {onu_id}',
                    'onu_id': onu_id,
                    'commands_executed': commands_executed
                }
                
            except Exception as cmd_error:
                logger.error(f"Error ejecutando comandos: {cmd_error}")
                # Intentar salir de los modos de configuración
                try:
                    self.session_connection.execute_command("exit", timeout=5)
                    self.session_connection.execute_command("exit", timeout=5)
                    self.session_connection.execute_command("exit", timeout=5)
                except:
                    pass
                raise
                
        except Exception as e:
            logger.error(f"Error autorizando ONT: {e}")
            raise

    def eliminar_ont(self, board: str, port: str, ont_id: str) -> dict:
        '''Elimina una ONT del OLT'''
        try:
            logger.info(f"Eliminando ONT: {board}/{port}:{ont_id}")
            
            # Validaciones
            if not all([board, port, ont_id]):
                raise ValueError("Faltan parámetros obligatorios")
            
            commands_executed = []
            
            try:
                # Entrar a modo configuración
                self.session_connection.execute_command("configure terminal", timeout=10)
                commands_executed.append("configure terminal")
                
                # Entrar a la interfaz gpon-olt
                cmd1 = f"interface gpon-olt_1/{board}/{port}"
                self.session_connection.execute_command(cmd1, timeout=10)
                commands_executed.append(cmd1)
                
                # Eliminar ONU
                cmd2 = f"no onu {ont_id}"
                output = self.session_connection.execute_command(cmd2, timeout=15)
                commands_executed.append(cmd2)
                
                # Verificar si hubo errores
                if "error" in output.lower() or "invalid" in output.lower():
                    raise Exception(f"Error al eliminar ONT: {output}")
                
                # Salir de la interfaz
                self.session_connection.execute_command("exit", timeout=5)
                
                # Salir de config mode
                self.session_connection.execute_command("exit", timeout=5)
                
                # Guardar configuración
                self.session_connection.execute_command("write", timeout=30)
                commands_executed.append("write")
                
                logger.info(f"ONT {ont_id} eliminada exitosamente de {board}/{port}")
                
                return {
                    'status': 'success',
                    'message': f'ONT {ont_id} eliminada exitosamente',
                    'ont_id': ont_id,
                    'commands_executed': commands_executed
                }
                
            except Exception as cmd_error:
                logger.error(f"Error ejecutando comandos de eliminación: {cmd_error}")
                # Intentar salir de los modos de configuración
                try:
                    self.session_connection.execute_command("exit", timeout=5)
                    self.session_connection.execute_command("exit", timeout=5)
                except:
                    pass
                raise
                
        except Exception as e:
            logger.error(f"Error eliminando ONT: {e}")
            raise

    def buscar_ont_por_sn(self, sn: str) -> dict:
        """Busca una ONT por Serial Number usando comando directo de ZTE"""
        try:
            logger.info(f"Buscando ONT con SN: {sn}")
            
            # Limpiar SN
            sn_clean = re.sub(r'[^A-Za-z0-9]', '', sn.upper())
            
            # Ejecutar comando directo de búsqueda
            output = self.session_connection.execute_command(
                f"show gpon onu by sn {sn_clean}",
                delay_factor=2,
                timeout=15
            )
            
            logger.debug(f"Output búsqueda: {output}")
            
            # Parsear resultado
            # Formato esperado:
            # SearchResult
            # -----------------
            # gpon-onu_1/1/16:1
            
            onu_interface = None
            lines = output.split('\n')
            
            for line in lines:
                line = line.strip()
                # Buscar línea que contenga gpon-onu_
                if 'gpon-onu_' in line:
                    onu_interface = line.strip()
                    break
            
            if not onu_interface:
                logger.info(f"ONT {sn_clean} no encontrada")
                return {
                    'status': 'success',
                    'found': False,
                    'message': f'ONT con SN {sn_clean} no encontrada'
                }
            
            # Parsear interface: gpon-onu_1/1/16:1
            # Formato: gpon-onu_BOARD/PORT:ONT_ID
            match = re.match(r'gpon-onu_(\d+)/(\d+)/(\d+):(\d+)', onu_interface)
            
            if not match:
                raise Exception(f"Formato de interface inválido: {onu_interface}")
            
            frame = match.group(1)  # Siempre 1
            board = match.group(2)
            port = match.group(3)
            ont_id = match.group(4)
            
            logger.info(f"ONT encontrada en: Board {board}, Port {port}, ID {ont_id}")
            
            # Obtener detalles completos
            ont_details = self._obtener_detalles_completos_zte(
                board, port, ont_id, onu_interface
            )
            
            return {
                'status': 'success',
                'found': True,
                'data': ont_details
            }
            
        except Exception as e:
            logger.error(f"Error buscando ONT por SN: {e}")
            raise


    def _obtener_detalles_completos_zte(self, board: str, port: str, 
                                        ont_id: str, interface: str) -> dict:
        """Obtiene detalles completos de una ONT usando comandos ZTE"""
        try:
            # Ejecutar comando detail-info
            output = self.session_connection.execute_command(
                f"show gpon onu detail-info {interface}",
                delay_factor=2,
                timeout=20
            )
            
            # Parsear información básica
            ont_data = self._parsear_detail_info_zte(output, board, port, ont_id)
            
            # Obtener información de potencia
            try:
                power_output = self.session_connection.execute_command(
                    f"show pon power attenuation {interface}",
                    delay_factor=2,
                    timeout=15
                )
                self._parsear_power_zte(power_output, ont_data)
            except Exception as e:
                logger.warning(f"No se pudo obtener info de potencia: {e}")
            
            return ont_data
            
        except Exception as e:
            logger.error(f"Error obteniendo detalles: {e}")
            # Retornar info básica si falla
            return {
                'sn': 'Unknown',
                'board': board,
                'port': port,
                'ont_id': ont_id,
                'interface': interface,
                'type': 'Unknown',
                'estado': 'unknown',
                'ont_rx': None,
                'olt_rx': None,
                'temperature': None,
                'distance': None,
                'descripcion': '',
                'name': '',
                'admin_state': 'unknown',
                'phase_state': 'unknown',
                'online_duration': '',
                'onu_distance': ''
            }


    def _parsear_detail_info_zte(self, output: str, board: str, 
                                port: str, ont_id: str) -> dict:
        """Parsea el output de 'show gpon onu detail-info'"""
        lines = output.split('\n')
        
        ont_data = {
            'board': board,
            'port': port,
            'ont_id': ont_id,
            'interface': f"gpon-onu_1/{board}/{port}:{ont_id}",
            'sn': '',
            'type': '',
            'name': '',
            'estado': 'unknown',
            'admin_state': '',
            'phase_state': '',
            'descripcion': '',
            'online_duration': '',
            'onu_distance': '',
            'ont_rx': None,
            'olt_rx': None,
            'temperature': None,
            'distance': None
        }
        
        for line in lines:
            line = line.strip()
            
            if ':' not in line:
                continue
            
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            
            if key == 'Name':
                ont_data['name'] = value
            elif key == 'Type':
                ont_data['type'] = value
            elif key == 'State':
                # ready, offline, etc.
                pass
            elif key == 'Admin state':
                ont_data['admin_state'] = value
            elif key == 'Phase state':
                ont_data['phase_state'] = value
                # Determinar estado general
                if value == 'working':
                    ont_data['estado'] = 'online'
                elif value.lower() == 'dyinggasp':
                    ont_data['estado'] = 'dying_gasp'
                elif value.upper() == 'LOS':
                    ont_data['estado'] = 'LOS'
                else:
                    ont_data['estado'] = 'offline'
            elif key == 'Serial number':
                ont_data['sn'] = value
            elif key == 'Description':
                ont_data['descripcion'] = value
            elif key == 'ONU Distance':
                ont_data['onu_distance'] = value
                # Extraer valor numérico si tiene formato "3382m"
                match = re.search(r'(\d+)', value)
                if match:
                    ont_data['distance'] = int(match.group(1))
            elif key == 'Online Duration':
                ont_data['online_duration'] = value
        
        return ont_data


    def _parsear_power_zte(self, output: str, ont_data: dict):
        """Parsea el output de 'show pon power attenuation'"""
        lines = output.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Línea up: OLT Rx
            if line.startswith('up'):
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.startswith('Rx:') or part == 'Rx':
                        if part == 'Rx' and i + 1 < len(parts):
                            olt_rx_str = parts[i + 1].replace(':', '').replace('(dbm)', '').strip()
                        else:
                            olt_rx_str = part.split(':')[1].replace('(dbm)', '').strip()
                        ont_data['olt_rx'] = self._safe_float_parse(olt_rx_str)
                        break
            
            # Línea down: ONT Rx
            elif line.startswith('down'):
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.startswith('Rx:') or part == 'Rx':
                        if part == 'Rx' and i + 1 < len(parts):
                            ont_rx_str = parts[i + 1].replace(':', '').replace('(dbm)', '').strip()
                        else:
                            ont_rx_str = part.split(':')[1].replace('(dbm)', '').strip()
                        ont_data['ont_rx'] = self._safe_float_parse(ont_rx_str)
                        break


    def _safe_float_parse(self, value: str) -> float:
        """Parsea un valor float de forma segura"""
        try:
            return float(value.replace('(dbm)', '').strip())
        except (ValueError, AttributeError):
            return None