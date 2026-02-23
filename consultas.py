# scripts/crud_onts.py
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ont_db import ONTDatabase

def menu_principal():
    """Menú interactivo para operaciones CRUD"""
    
    while True:
        print("\n" + "="*50)
        print("SISTEMA DE GESTIÓN DE ONTS")
        print("="*50)
        print("1. Ver todas las ONTs")
        print("2. Buscar ONT por SN")
        print("3. Ver ONTs de un puerto")
        print("4. Agregar/Actualizar ONT manualmente")
        print("5. Actualizar nombre de ONT")
        print("6. Eliminar ONT")
        print("7. Estadísticas")
        print("8. LIMPIAR BASE DE DATOS (peligroso)")
        print("0. Salir")
        
        opcion = input("\nSeleccione una opción: ")
        
        if opcion == "1":
            ver_todas()
        elif opcion == "2":
            buscar_por_sn()
        elif opcion == "3":
            ver_por_puerto()
        elif opcion == "4":
            agregar_ont()
        elif opcion == "5":
            actualizar_nombre()
        elif opcion == "6":
            eliminar_ont()
        elif opcion == "7":
            ver_estadisticas()
        elif opcion == "8":
            limpiar_db()
        elif opcion == "0":
            break

def ver_todas():
    onts = ONTDatabase.obtener_todas_onts()
    print(f"\nTotal: {len(onts)} ONTs")
    for ont in onts:
        print(f"{ont['tarjeta']}/{ont['puerto']}:{ont['onu_id']} - "
              f"SN: {ont['sn']} - Name: {ont.get('name', 'N/A')}")

def buscar_por_sn():
    sn = input("Ingrese SN: ").strip().upper()
    ont = ONTDatabase.obtener_ont_por_sn(sn)
    if ont:
        print(f"Encontrada: {ont['tarjeta']}/{ont['puerto']}:{ont['onu_id']}")
        print(f"Name: {ont.get('name', 'N/A')}")
        print(f"SN COMPLETO: {ont.get('sn', 'N/A')}")
    else:
        print("No encontrada")

def ver_por_puerto():
    tarjeta = input("Tarjeta: ")
    puerto = input("Puerto: ")
    onts = ONTDatabase.obtener_onts_por_puerto(tarjeta, puerto)
    print(f"\nPuerto {tarjeta}/{puerto}: {len(onts)} ONTs")
    for ont in onts:
        print(f"  ID: {ont['onu_id']} - SN: {ont['sn']} - {ont.get('name', 'N/A')}")

def agregar_ont():
    print("\n--- Agregar/Actualizar ONT ---")
    tarjeta = input("Tarjeta: ")
    puerto = input("Puerto: ")
    onu_id = input("ONU ID: ")
    sn = input("SN: ").strip().upper()
    name = input("Name (opcional): ")
    
    ONTDatabase.guardar_ont(tarjeta, puerto, onu_id, sn, name or None)
    print("ONT guardada")

def actualizar_nombre():
    print("\n--- Actualizar Nombre ---")
    tarjeta = input("Tarjeta: ")
    puerto = input("Puerto: ")
    onu_id = input("ONU ID: ")
    name = input("Nuevo nombre: ")
    
    ONTDatabase.actualizar_name(tarjeta, puerto, onu_id, name)
    print("Nombre actualizado")

def eliminar_ont():
    print("\n--- Eliminar ONT ---")
    tarjeta = input("Tarjeta: ")
    puerto = input("Puerto: ")
    onu_id = input("ONU ID: ")
    
    confirm = input(f"¿Eliminar ONT {tarjeta}/{puerto}:{onu_id}? (s/N): ")
    if confirm.lower() == 's':
        ONTDatabase.eliminar_ont(tarjeta, puerto, onu_id)
        print("ONT eliminada")

def ver_estadisticas():
    onts = ONTDatabase.obtener_todas_onts()
    puertos = {}
    for ont in onts:
        key = f"{ont['tarjeta']}/{ont['puerto']}"
        if key not in puertos:
            puertos[key] = 0
        puertos[key] += 1
    
    print(f"\nTotal ONTs: {len(onts)}")
    print("\nPor puerto:")
    for puerto, count in sorted(puertos.items()):
        print(f"  {puerto}: {count} ONTs")

def limpiar_db():
    confirm = input("⚠️  ¿ELIMINAR TODOS LOS REGISTROS? (escriba 'BORRAR'): ")
    if confirm == 'BORRAR':
        ONTDatabase.limpiar_tabla()
        print("Base de datos limpiada")
    else:
        print("Operación cancelada")

if __name__ == "__main__":
    # Asegurar que la DB existe
    ONTDatabase.init_db()
    menu_principal()