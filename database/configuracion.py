import mysql.connector

from database.conexion import obtener_conexion

from database.auditoria import registrar_accion

from permisos import (
    requiere_permiso,
    GESTIONAR_CONFIGURACION
)


# =============================
# DATOS DEL SISTEMA
# =============================

NOMBRE_SISTEMA = "Concesionario Automotor"

VERSION_SISTEMA = "1.1.0"

CLAVE_STOCK_MINIMO = "stock_minimo"

STOCK_MINIMO_POR_DEFECTO = 3


# =============================
# AJUSTES
# =============================

def obtener_configuracion():
    """
    Devuelve la tabla clave/valor como
    diccionario de cadenas.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT clave, valor
        FROM configuracion
    """

    cursor.execute(consulta)

    ajustes = {
        fila[0]: fila[1]
        for fila in cursor.fetchall()
    }

    cursor.close()
    conexion.close()

    return ajustes


def obtener_stock_minimo():
    """
    Umbral de stock bajo.

    Si el valor guardado no es un número
    utilizable, cae al valor por defecto en
    lugar de romper el panel principal.
    """

    ajustes = obtener_configuracion()

    valor = ajustes.get(CLAVE_STOCK_MINIMO)

    if valor is None:

        return STOCK_MINIMO_POR_DEFECTO

    try:

        numero = int(valor)

    except (TypeError, ValueError):

        return STOCK_MINIMO_POR_DEFECTO

    if numero < 0:

        return STOCK_MINIMO_POR_DEFECTO

    return numero


@requiere_permiso(GESTIONAR_CONFIGURACION)
def actualizar_stock_minimo(valor):
    """
    Cambia el umbral de stock bajo y deja la
    entrada en la auditoría.

    Devuelve el valor guardado.
    """

    anterior = obtener_stock_minimo()

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        INSERT INTO configuracion
        (clave, valor, descripcion)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE valor = %s
    """

    descripcion = (
        "Un vehículo con stock menor o igual a "
        "este valor aparece como stock bajo."
    )

    valores = (
        CLAVE_STOCK_MINIMO,
        str(valor),
        descripcion,
        str(valor)
    )

    cursor.execute(consulta, valores)

    conexion.commit()

    cursor.close()
    conexion.close()

    registrar_accion(
        "configuracion",
        "CONFIGURACION",
        f"Umbral de stock bajo: {anterior} -> {valor}"
    )

    return valor


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
