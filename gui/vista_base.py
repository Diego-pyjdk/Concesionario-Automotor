from gui.trabajos import Trabajos
# ==========================================
# VISTA CON MANEJO DE ERRORES
# ==========================================
# Base de todas las vistas.
#
# Ningún error de MySQL debe cerrar la
# aplicación: una conexión perdida, una clave
# foránea o un dato raro se convierten en un
# mensaje que el usuario puede leer.
#
# El detalle técnico va a registro_errores.log,
# nunca a un cuadro de diálogo.
# ==========================================


from PySide6.QtWidgets import (
    QWidget,
    QMessageBox
)

from errores import (
    ErrorSistema,
    ErrorValidacion,
    PermisoDenegado,
    ErrorBaseDatos
)

from utils.registro import (
    registrar_error,
    registrar_error_inesperado
)


class VistaBase(QWidget):
    """
    Añade una capa de seguridad alrededor de
    cualquier llamada a la base de datos.
    """

    diferir_carga = False

    def __init__(self, parent=None):
        super().__init__(parent)
        self.carga_asincrona = VistaBase.diferir_carga
        self.trabajos = Trabajos(self)
        self.cache_consultas = None
        self.version_lote = 0

    def consultar_async(self, operacion, terminado):
        return self.trabajos.ejecutar(operacion, terminado, self.mostrar_error)

    def consultar_lote(self, consultas, pintar):
        self.version_lote += 1
        version = self.version_lote
        def obtener():
            return {(operacion, repr(args), repr(sorted(kwargs.items()))): operacion(*args, **kwargs)
                    for operacion, args, kwargs in consultas}
        def recibido(datos):
            if version != self.version_lote:
                return
            self.cache_consultas = datos
            try:
                pintar()
            finally:
                self.cache_consultas = None
        return self.consultar_async(obtener, recibido)

    # ------------------------------
    # EJECUCIÓN PROTEGIDA
    # ------------------------------

    def proteger(self, operacion, *args, **kwargs):
        """
        Ejecuta una operación y traduce
        cualquier fallo a un aviso en pantalla.

        Devuelve None si la operación falló, así
        que el código que la llama no debe asumir
        un resultado.
        """

        if self.cache_consultas is not None:
            clave = (operacion, repr(args), repr(sorted(kwargs.items())))
            if clave in self.cache_consultas:
                return self.cache_consultas[clave]

        try:

            return operacion(*args, **kwargs)

        except PermisoDenegado as error:

            self.mostrar_error(error)

            return None

        except ErrorValidacion as error:

            self.mostrar_error(error)

            return None

        except ErrorBaseDatos as error:

            registrar_error(error)

            self.mostrar_error(error)

            return None

        except ErrorSistema as error:

            registrar_error(error)

            self.mostrar_error(error)

            return None

        except Exception as error:

            registrar_error_inesperado(error)

            self.mostrar_error_inesperado()

            return None

    # ------------------------------
    # AVISOS
    # ------------------------------

    def mostrar_error(self, error):
        """
        Muestra un error controlado.
        """

        if isinstance(error, ErrorSistema):
            self.mostrar_mensaje_error(error.mensaje)
        else:
            registrar_error_inesperado(error)
            self.mostrar_error_inesperado()

    def mostrar_mensaje_error(self, mensaje):
        """
        Muestra un texto de error sin excepciones
        de por medio: es el caso de un borrado
        bloqueado por una clave foránea, que la
        capa de datos devuelve como booleano.
        """

        QMessageBox.warning(
            self,
            "No se pudo completar la operación",
            mensaje
        )

    def mostrar_error_inesperado(self):
        """
        Fallo que no debería ocurrir. No se
        muestra la traza: solo se indica dónde
        mirar.
        """

        QMessageBox.critical(
            self,
            "Error inesperado",
            "Ocurrió un problema inesperado al "
            "realizar la operación.\n\n"
            "La operación se canceló y no se "
            "guardó nada. El detalle técnico está "
            "en registro_errores.log."
        )

    def mostrar_exito(self, mensaje):
        QMessageBox.information(
            self,
            "Operación realizada",
            mensaje
        )

    def confirmar(self, titulo, mensaje):
        """
        Confirmación con los mismos botones que
        usa el resto del sistema.
        """

        respuesta = QMessageBox.question(
            self,
            titulo,
            mensaje,
            QMessageBox.Yes | QMessageBox.No
        )

        return respuesta == QMessageBox.Yes
