# ==========================================
# REGISTRO DE ERRORES
# ==========================================
# El usuario no debe ver una traza de Python.
# Pero el técnico sí la necesita.
#
# Las excepciones controladas ya llevan un
# mensaje legible; aquí se guarda el detalle
# técnico completo en un archivo de texto.
# ==========================================


import logging
import logging.handlers
import os
import traceback


# ==========================================
# ARCHIVO
# ==========================================

NOMBRE_ARCHIVO = "registro_errores.log"

RAIZ = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

RUTA = os.path.join(RAIZ, NOMBRE_ARCHIVO)

# Tamaño máximo de cada archivo y cuántas copias
# se guardan. Sin esto el log crecía sin
# límite: en una máquina con uso normal llegó a
# pesar casi un megabyte y ya no servía para
# buscar nada.
#
# Con 2 MB y 3 copias el disco se queda en unos
# 6 MB como mucho.
TAMANO_MAXIMO = 2 * 1024 * 1024

COPIAS = 3


_configurado = False


# ==========================================
# CONFIGURACIÓN
# ==========================================

def configurar():
    """
    Prepara el logging una sola vez.

    Usa RotatingFileHandler: cuando el archivo
    llega a TAMANO_MAXIMO se renombra a .1, el
    anterior pasa a .2 y el más viejo se
    borra. Así el log nunca crece sin límite.
    """

    global _configurado

    if _configurado:
        return

    try:

        manejador = logging.handlers.RotatingFileHandler(
            RUTA,
            maxBytes=TAMANO_MAXIMO,
            backupCount=COPIAS,
            encoding="utf-8"
        )

        manejador.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | "
                "%(name)s | %(message)s"
            )
        )

        raiz = logging.getLogger()

        raiz.setLevel(logging.ERROR)

        raiz.addHandler(manejador)

        _configurado = True

    except OSError:
        # Si el archivo no se puede abrir, el
        # sistema sigue funcionando igual: solo
        # se pierde el historial.
        _configurado = True


# ==========================================
# ESCRITURA
# ==========================================

def registrar_error(error):
    """
    Guarda una excepción con su traza.
    """

    configurar()

    logging.error(
        "%s: %s",
        type(error).__name__,
        error
    )

    logging.error(
        "%s",
        "".join(
            traceback.format_exception(
                type(error),
                error,
                error.__traceback__
            )
        )
    )


def registrar_error_inesperado(error):
    """
    Para fallos que no son de MySQL ni de
    validación: bugs y errores de Qt.
    """

    configurar()

    logging.critical(
        "Fallo inesperado: %s: %s",
        type(error).__name__,
        error
    )

    logging.critical(
        "%s",
        "".join(
            traceback.format_exception(
                type(error),
                error,
                error.__traceback__
            )
        )
    )
