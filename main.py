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


import sys

from PySide6.QtWidgets import QApplication

from database.configuracion import NOMBRE_SISTEMA

from errores import ErrorSistema

from utils.registro import (
    registrar_error,
    registrar_error_inesperado
)

from gui.login_view import LoginView
from gui.ventana_principal import VentanaPrincipal


ARCHIVO_ESTILO = "gui/estilo.css"


def cargar_estilos(app):

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
