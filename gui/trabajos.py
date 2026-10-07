# Consultas de lectura fuera del hilo de la interfaz.
import copy
from PySide6.QtCore import QObject, Signal, Slot, QRunnable, QThreadPool
import sesion


class Senales(QObject):
    finalizado = Signal(int, object, object)


class Tarea(QRunnable):
    def __init__(self, numero, operacion, contexto):
        super().__init__()
        self.numero = numero
        self.operacion = operacion
        self.contexto = contexto
        self.senales = Senales()

    def run(self):
        token = sesion.contexto_trabajo.set(self.contexto)
        try:
            resultado = self.operacion()
            error = None
        except Exception as excepcion:
            resultado, error = None, excepcion
        finally:
            sesion.contexto_trabajo.reset(token)

        # ------------------------------
        # EL QUE PIDIO EL DATO PUEDE
        # HABER DESAPARECIDO
        # ------------------------------
        #
        # Cambiar de seccion o cerrar sesion con una
        # consulta en vuelo destruye la vista que la
        # pidio. Entonces `senales` ya no existe y
        # `emit` avisa con "Signal source has been
        # deleted", desde un hilo, donde no hay a quien
        # enseñarselo.
        #
        # Perder el resultado es lo correcto: ya no hay
        # pantalla que lo pinte. Lo que no puede ser es
        # que el worker gruje en consola por eso.
        try:
            self.senales.finalizado.emit(
                self.numero,
                resultado,
                error
            )
        except RuntimeError:
            pass


class Trabajos(QObject):
    def __init__(self, parent):
        super().__init__(parent)
        self.pendientes = {}
        self.numero = 0
        self.cancelado = False

        if parent is not None:
            parent.destroyed.connect(self.cancelar)

    def cancelar(self):
        """
        La vista se ha destruido: no queda nadie a quien
        entregar el resultado.

        Se vacian las pendientes para que un `terminar`
        que llegue tarde no intente pintar sobre un
        widget que ya no existe.
        """

        self.cancelado = True
        self.pendientes.clear()

    def ejecutar(self, operacion, terminado, fallido):
        if self.cancelado:
            return None
        self.numero += 1
        numero = self.numero
        tarea = Tarea(numero, operacion, copy.copy(sesion.obtener_sesion()))
        self.pendientes[numero] = (tarea, terminado, fallido, sesion.generacion)
        tarea.senales.finalizado.connect(self.terminar)
        QThreadPool.globalInstance().start(tarea)
        return numero

    @Slot(int, object, object)
    def terminar(self, numero, resultado, error):
        entrada = self.pendientes.pop(numero, None)
        if entrada is None or self.cancelado:
            return
        tarea, terminado, fallido, generacion = entrada
        if generacion != sesion.generacion:
            return
        if error:
            fallido(error)
        else:
            terminado(resultado)
