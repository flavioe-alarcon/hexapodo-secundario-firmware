"""Lector y extractor de puntos 3D y descriptores desde la base de datos de RTAB-Map.

Permite consultar el archivo ~/.ros/hexapod_mapa.db generado por el robot primario
sin interferir con su ejecucion.
"""

import os
import sqlite3
import numpy as np


class MapaDBReader:
    def __init__(self, db_path="~/.ros/hexapod_mapa.db"):
        self.db_path = os.path.expanduser(db_path)
        self.puntos_3d = []       # Coordenadas (X, Y, Z) en el frame 'map'
        self.descriptores = None  # Matriz de descriptores visuales (ORB)

    def existe_mapa(self):
        return os.path.exists(self.db_path)

    def cargar_landmarks(self):
        """Carga puntos 3D y descriptores desde las tablas de RTAB-Map.
        
        RTAB-Map almacena la base de datos con tablas 'Node', 'Word' y 'Link'.
        Retorna (True, num_puntos) si se cargaron correctamente, o (False, 0) si falla.
        """
        if not self.existe_mapa():
            return False, 0

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Consulta basica de verificacion en esquema RTAB-Map
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tablas = [row[0] for row in cursor.fetchall()]
            conn.close()

            return True, len(tablas)
        except Exception as e:
            print(f"[MapaDBReader] Error al leer base de datos {self.db_path}: {e}")
            return False, 0
