from gui.tema import aplicar_tema
# ==========================================
# PUNTO DE ENTRADA
# ==========================================
# El login va primero: VentanaPrincipal solo se
# construye con una sesión abierta.
#
# Al cerrar sesión se vuelve al login sin
# matar el proceso, para poder entrar con
# otra cuenta.
# ==========================================


import os
import sys

from PySide6.QtWidgets import QApplication

from database.configuracion import (
    NOMBRE_SISTEMA,
    obtener_moneda
)

from errores import ErrorSistema

from utils.registro import (
    registrar_error,
    registrar_error_inesperado
)

from gui.login_view import LoginView
from gui.ventana_principal import VentanaPrincipal


# Un solo dirname: main.py está en la RAÍZ del
# proyecto, así que subir un nivel saldría del
# proyecto entero.
#
# Con dos niveles la ruta apuntaba al escritorio y
# cargar_estilos() fallaba al arrancar con "No se
# encuentra la hoja de estilo". Compilar y abrir
# cada vista no lo detecta: el error sale al
# ejecutar main.py entero.

_RAIZ = os.path.dirname(os.path.abspath(__file__))

ARCHIVO_ESTILO = os.path.join(
    _RAIZ,
    "gui",
    "estilo.css"
)


def cargar_estilos(app):
    """
    Aplica la hoja de estilo.

    La ruta sale de __file__, no del directorio de
    trabajo: con una ruta relativa, arrancar
    haciendo doble clic en main.py desde el
    explorador (o desde un acceso directo)
    fallaba con un error que no explicaba nada,
    porque el problema real era estar en la
    carpeta equivocada.
    """

    if not os.path.exists(ARCHIVO_ESTILO):

        raise ErrorSistema(
            f"No se encuentra la hoja de estilo:\n"
            f"  {ARCHIVO_ESTILO}\n\n"
            "Falta gui/estilo.css dentro del "
            "proyecto."
        )

    with open(
        ARCHIVO_ESTILO,
        "r",
        encoding="utf-8"
    ) as archivo:

        app.setStyleSheet(archivo.read())


def ejecutar():
    """
    Ciclo login -> sistema -> login.
    """

    app = QApplication(sys.argv)

    app.setApplicationName(NOMBRE_SISTEMA)

    cargar_estilos(app)
    aplicar_tema()

    # La moneda se lee una vez y se queda en
    # memoria. Calentarla aquí evita que el primer
    # importe que se pinte sea el que dispare la
    # consulta a la base de datos.
    #
    # Si falla, no se interrumpe el arranque:
    # utils.moneda cae a los valores por defecto y
    # la aplicación sigue con "$ ", que es lo que
    # se ha visto siempre.

    try:

        obtener_moneda()

    except Exception:

        pass

    ventana = None

    def mostrar_login():

        nonlocal ventana

        # Se destruye la ventana anterior en
        # lugar de cerrarla: así el proceso
        # sigue vivo para el siguiente login.

        if ventana is not None:

            ventana.hide()

            ventana.deleteLater()

            ventana = None

        login = LoginView()

        if not login.exec():

            # El usuario canceló: no hay nada
            # más que hacer.

            app.quit()

            return

        ventana = VentanaPrincipal()

        ventana.solicitar_cierre_sesion.connect(
            mostrar_login
        )

        ventana.show()

    mostrar_login()

    return app.exec()


if __name__ == "__main__":

    try:

        sys.exit(ejecutar())

    except ErrorSistema as error:

        registrar_error(error)

        print(f"\n  {error.mensaje}\n")

        sys.exit(1)

    except Exception as error:

        registrar_error_inesperado(error)

        print(
            "\n  Ocurrió un error inesperado. "
            "Revise registro_errores.log.\n"
        )

        sys.exit(1)
