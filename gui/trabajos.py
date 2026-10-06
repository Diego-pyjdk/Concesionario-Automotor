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
        self.senales.finalizado.emit(self.numero, resultado, error)


class Trabajos(QObject):
    def __init__(self, parent):
        super().__init__(parent)
        self.pendientes = {}
        self.numero = 0

    def ejecutar(self, operacion, terminado, fallido):
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
        if entrada is None:
            return
        tarea, terminado, fallido, generacion = entrada
        if generacion != sesion.generacion:
            return
        if error:
            fallido(error)
        else:
            terminado(resultado)
