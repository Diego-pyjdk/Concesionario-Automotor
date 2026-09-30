import mysql.connector

from database.conexion import obtener_conexion


# =============================
# DATOS DEL SISTEMA
# =============================

NOMBRE_SISTEMA = "Concesionario Automotor"

VERSION_SISTEMA = "1.0.0"


# =============================
# ESTADO DE LA CONEXIÓN
# =============================

def estado_conexion():
    """
    Comprueba que MySQL responda.

    Devuelve (conectado, detalle).
    """

    try:
        conexion = obtener_conexion()

        cursor = conexion.cursor()

        cursor.execute("SELECT VERSION()")

        version = cursor.fetchone()[0]

        cursor.close()
        conexion.close()

        return True, version

    except mysql.connector.Error as error:

        return False, str(error)
