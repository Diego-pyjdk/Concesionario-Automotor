# ==========================================
# DIAGNÓSTICO
# ==========================================
# Herramientas de comprobación para el
# administrador: responde "¿está todo bien?" sin
# tener que abrir una consola.
#
# Solo LECTURA. Aquí no se cambia ni una palabra
# de la configuración ni de la base de datos.
#
# Por diseño no se muestran contraseñas: ni la
# de MySQL ni las de los usuarios. Solo datos de
# forma, que es lo que hace falta para
# diagnosticar.
# ==========================================


import os
import platform
import sys
import time

from database.conexion import (
    obtener_conexion,
    sin_password,
    RUTA_ENV
)

from permisos import requiere_permiso, GESTIONAR_CONFIGURACION

from utils.registro import RUTA as RUTA_LOG


VERSION_MINIMA_PYTHON = (3, 10)


# ==========================================
# ENTORNO
# ==========================================

def obtener_entorno():
    """
    Datos del equipo y del intérprete. No
    requieren conexión, así que sirven para
    diagnosticar aunque MySQL esté caído.
    """

    return [
        ("Sistema operativo",
         f"{platform.system()} {platform.release()}"),
        ("Arquitectura", platform.machine()),
        ("Versión de Python", platform.python_version()),
        ("Intérprete", sys.executable),
        ("Carpeta de trabajo", os.getcwd())
    ]


def comprobar_python():
    """
    (ok, mensaje) con la versión mínima.
    """

    actual = sys.version_info[:2]

    if actual < VERSION_MINIMA_PYTHON:

        return False, (
            f"Se necesita Python "
            f"{VERSION_MINIMA_PYTHON[0]}."
            f"{VERSION_MINIMA_PYTHON[1]} o superior; "
            f"esta es {platform.python_version()}."
        )

    return True, platform.python_version()


def obtener_dependencias():
    """
    Versiones de lo imprescindible. Si algo
    falta, la app ni arranca: aquí se ve por qué.
    """

    filas = []

    for nombre, modulo in (
        ("PySide6", "PySide6"),
        ("mysql-connector-python", "mysql.connector")
    ):

        version = "NO INSTALADO"

        try:

            import importlib

            cargado = importlib.import_module(modulo)

            version = getattr(
                cargado, "__version__", "instalado"
            )

        except ImportError:
            pass

        filas.append((nombre, version))

    return filas


def obtener_conexion_configurada():
    """
    Datos de conexión SIN la contraseña.

    Existe sin_password() justamente para esto:
    la contraseña no debe poder acabar en un
    cuadro de texto ni en un archivo de
    diagnóstico.
    """

    datos = sin_password()

    return [
        ("Servidor", datos["host"]),
        ("Puerto", datos["port"]),
        ("Usuario", datos["user"]),
        ("Base de datos", datos["database"])
    ]


def obtener_archivos():
    """
    Estado de los archivos que importan. La
    contraseña no se lee: solo se comprueba que
    el archivo exista.
    """

    return [
        (
            "Archivo .env",
            "Presente" if os.path.exists(RUTA_ENV)
            else "FALTA: copie .env.example a .env"
        ),
        ("Registro de errores", describir_log())
    ]


def describir_log():
    """
    Estado del archivo de errores, sin leerlo.
    """

    if not os.path.exists(RUTA_LOG):

        return "Todavía no hay errores registrados"

    try:

        tamano = os.path.getsize(RUTA_LOG)

    except OSError:

        return "No se puede leer"

    if tamano == 0:

        return "Vacío (sin errores)"

    return (
        f"{tamano / 1024:.1f} KB de errores "
        "registrados"
    )


# ==========================================
# BASE DE DATOS
# ==========================================

def comprobar_conexion():
    """
    Prueba rápida: responde sí o no y en cuánto
    tardó.
    """

    tiempo = time.perf_counter()

    try:

        conexion = obtener_conexion()

        cursor = conexion.cursor()

        cursor.execute("SELECT 1")

        cursor.close()
        conexion.close()

        latencia = int(
            (time.perf_counter() - tiempo) * 1000
        )

        return True, f"Conectado en {latencia} ms"

    except Exception as error:

        return False, str(error)


@requiere_permiso(GESTIONAR_CONFIGURACION)
def obtener_base_datos():
    """
    Estado y características de MySQL.
    """

    tiempo = time.perf_counter()

    conexion = obtener_conexion()

    cursor = conexion.cursor(dictionary=True)

    latencia = int(
        (time.perf_counter() - tiempo) * 1000
    )

    consulta = """
        SELECT
            VERSION() AS version,
            @@character_set_database AS charset,
            @@collation_database AS collation,
            @@max_connections AS conexiones_max,
            @@wait_timeout AS espera
    """

    cursor.execute(consulta)

    fila = cursor.fetchone()

    cursor.close()
    conexion.close()

    return {
        "version": fila["version"],
        "charset": fila["charset"],
        "collation": fila["collation"],
        "conexiones_max": fila["conexiones_max"],
        "espera": fila["espera"],
        "latencia_ms": latencia
    }


@requiere_permiso(GESTIONAR_CONFIGURACION)
def obtener_tablas():
    """
    Filas y tamaño de cada tabla.

    El conteo sale de consultas UNION explícitas
    y el tamaño de information_schema: se cruzan
    en Python. Así el nombre de tabla nunca se
    interpola en el SQL.

    El UNION lleva una línea por cada tabla de
    database/esquema.sql. Si al añadir una tabla
    se olvida esta lista, la tabla sigue
    apareciendo en el diagnóstico (la saca
    information_schema) pero con SIEMPRE 0
    filas, porque el get() no la encuentra: un
    fallo silencioso que hay que evitar.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    conteos = """
        SELECT 'auditoria' AS tabla, COUNT(*) AS filas
        FROM auditoria
        UNION ALL
        SELECT 'autos', COUNT(*) FROM autos
        UNION ALL
        SELECT 'clientes', COUNT(*) FROM clientes
        UNION ALL
        SELECT 'configuracion', COUNT(*)
        FROM configuracion
        UNION ALL
        SELECT 'convenios', COUNT(*)
        FROM convenios
        UNION ALL
        SELECT 'contratos', COUNT(*)
        FROM contratos
        UNION ALL
        SELECT 'cuotas', COUNT(*)
        FROM cuotas
        UNION ALL
        SELECT 'garantias', COUNT(*)
        FROM garantias
        UNION ALL
        SELECT 'marcas', COUNT(*) FROM marcas
        UNION ALL
        SELECT 'pagos', COUNT(*)
        FROM pagos
        UNION ALL
        SELECT 'usuarios', COUNT(*) FROM usuarios
        UNION ALL
        SELECT 'ventas', COUNT(*) FROM ventas
        UNION ALL SELECT 'auto_fichas', COUNT(*) FROM auto_fichas
        UNION ALL SELECT 'auto_fotos', COUNT(*) FROM auto_fotos
        UNION ALL SELECT 'unidades_vehiculo', COUNT(*) FROM unidades_vehiculo
        UNION ALL SELECT 'venta_unidades', COUNT(*) FROM venta_unidades
        UNION ALL SELECT 'seguimiento_cobranza', COUNT(*) FROM seguimiento_cobranza
    """

    cursor.execute(conteos)

    filas_por_tabla = {
        fila["tabla"]: fila["filas"]
        for fila in cursor.fetchall()
    }

    consulta = """
        SELECT
            TABLE_NAME AS nombre,
            DATA_LENGTH AS datos,
            INDEX_LENGTH AS indice
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
        ORDER BY TABLE_NAME
    """

    cursor.execute(consulta)

    tamanos = cursor.fetchall()

    cursor.close()
    conexion.close()

    resultado = []

    for fila in tamanos:

        nombre = fila["nombre"]

        mb = (
            (fila["datos"] + fila["indice"])
            / 1024 / 1024
        )

        resultado.append((
            nombre,
            filas_por_tabla.get(nombre, 0),
            f"{mb:.2f} MB"
        ))

    resultado.sort(
        key=lambda fila: (-fila[1], fila[0])
    )

    return resultado
