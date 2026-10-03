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


import functools
import os
import threading

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
            ""
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

# Las conexiones abiertas dentro de una función
# protegida se anotan aquí, para poder devolverlas
# todas cuando la función termine, pase lo que
# pase. Es una lista por hilo porque la interfaz
# es de un solo hilo hoy, pero MySQL Connector
# admite uso simultáneo desde varios y nada
# garantiza que siga siendo así.

_pila = threading.local()


def obtener_conexion():
    """
    Abre una conexión nueva.

    Los fallos de MySQL llegan como
    ErrorBaseDatos con un mensaje ya traducible
    por la interfaz.

    Si hay una función con @conexiones_libres
    en curso, la conexión se anota en su pila para
    que se cierre aunque la función reviente antes
    de llegar a su conexion.close().
    """

    try:

        conexion = mysql.connector.connect(
            **configuracion()
        )

    except mysql.connector.Error as error:

        raise traducir_error(error) from error

    pila = getattr(_pila, "abiertas", None)

    if pila is not None:

        pila.append(conexion)

    return conexion


def conexiones_libres(funcion):
    """
    Garantiza que las conexiones que abra la
    función se cierren al terminar.

    Sin esto, un INSERT que falla a mitad (una
    clave foránea, un UNIQUE, MySQL que se cae)
    saca la excepción con la conexión todavía
    abierta. MySQL no la suelta: sigue
    sosteniendo la sesión en el servidor, ocupa
    una de las max_connections y, si la función
    había abierto una transacción, se lleva por
    delante los bloqueos de las filas que
    hubiera tocado. Con unos pocos fallos
    seguidos la aplicación deja de poder
    conectar, y no hay forma de saber por qué
    mirando el mensaje de error.

    No cambia el comportamiento de la función:
    ni traga excepciones ni altera el valor que
    se devuelve. Solo añade el cierre.

    Va por encima de @requiere_permiso, para que
    también cubra el caso de que el permiso se
    compruebe y falle.
    """

    @functools.wraps(funcion)
    def envoltura(*args, **kwargs):

        anterior = getattr(_pila, "abiertas", None)

        _pila.abiertas = []

        try:

            return funcion(*args, **kwargs)

        finally:

            for conexion in _pila.abiertas:

                try:

                    conexion.close()

                except Exception:

                    # Si no se puede cerrar, no hay
                    # nada que hacer: MySQL la
                    # recicla por su cuenta al
                    # expirar. Lo que no puede ser
                    # es tapar el error que hizo
                    # fallar a la función.

                    pass

            _pila.abiertas = anterior

    return envoltura
