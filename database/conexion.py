# ==========================================
# CONEXIÓN A MYSQL
# ==========================================
# Las credenciales NO van en el código.
#
# Se leen del entorno, y el entorno se completa
# con un archivo .env en la raíz del proyecto
# (que está en .gitignore, así que nunca se
# versiona).
#
# Copiar .env.example a .env y rellenarlo.
# ==========================================


import os

import mysql.connector

from errores import traducir_error


# ==========================================
# ARCHIVO .env
# ==========================================

ARCHIVO_ENV = ".env"

_raiz = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

RUTA_ENV = os.path.join(_raiz, ARCHIVO_ENV)

_cargado = False


def cargar_env():
    """
    Lee el .env sin dependencias externas.

    Las variables ya presentes en el entorno
    mandan sobre el archivo, para que en
    producción baste con exportarlas.
    """

    global _cargado

    if _cargado:
        return

    _cargado = True

    if not os.path.exists(RUTA_ENV):
        return

    try:
        # utf-8-sig y no utf-8: si el archivo
        # lleva BOM (lo añade de más el Bloc de
        # notas al guardarlo), la primera clave
        # se llamaría "\ufeffDB_HOST" y no se
        # leería. El fallo sería silencioso: se
        # usaría el valor por defecto y todo
        # parecería correcto.
        with open(
            RUTA_ENV,
            "r",
            encoding="utf-8-sig"
        ) as archivo:

            for linea in archivo:

                linea = linea.strip()

                if not linea:
                    continue

                if linea.startswith("#"):
                    continue

                if "=" not in linea:
                    continue

                clave, _, valor = linea.partition("=")

                clave = clave.strip()

                valor = valor.strip()

                # Quita comillas envolventes
                if len(valor) >= 2 and valor[0] == valor[-1]:
                    if valor[0] in ('"', "'"):
                        valor = valor[1:-1]

                os.environ.setdefault(clave, valor)

    except OSError:
        pass


# ==========================================
# CONFIGURACIÓN
# ==========================================

def configuracion():
    """
    Parámetros de conexión con valores por
    defecto para un MySQL local de escritorio.
    """

    cargar_env()

    return {
        "host": os.environ.get(
            "DB_HOST",
            "localhost"
        ),
        "port": int(os.environ.get(
            "DB_PORT",
            "3306"
        )),
        "user": os.environ.get(
            "DB_USER",
            "root"
        ),
        "password": os.environ.get(
            "DB_PASSWORD",
            "224426"
        ),
        "database": os.environ.get(
            "DB_NAME",
            "concesionario"
        )
    }


def sin_password():
    """
    Datos de conexión sin la contraseña, para
    mostrarlos en Configuración sin filtrar el
    secreto.
    """

    datos = configuracion()

    return {
        "host": datos["host"],
        "port": datos["port"],
        "user": datos["user"],
        "database": datos["database"]
    }


# ==========================================
# CONEXIÓN
# ==========================================

def obtener_conexion():
    """
    Abre una conexión nueva.

    Los fallos de MySQL llegan como
    ErrorBaseDatos con un mensaje ya traducible
    por la interfaz.
    """

    try:
        return mysql.connector.connect(
            **configuracion()
        )

    except mysql.connector.Error as error:

        raise traducir_error(error) from error
