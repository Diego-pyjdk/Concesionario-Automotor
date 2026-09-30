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


_configurado = False


# ==========================================
# CONFIGURACIÓN
# ==========================================

def configurar():
    """
    Prepara el logging una sola vez.
    """

    global _configurado

    if _configurado:
        return

    try:
        logging.basicConfig(
            filename=RUTA,
            level=logging.ERROR,
            format=(
                "%(asctime)s | %(levelname)s | "
                "%(name)s | %(message)s"
            ),
            encoding="utf-8"
        )

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
