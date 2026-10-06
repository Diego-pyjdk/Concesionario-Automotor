from datetime import datetime
from utils.respaldo import crear_respaldo, verificar_respaldo
from gui.trabajos import Trabajos
from errores import ErrorSistema
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QFileDialog
from utils.helpers import crear_boton_principal, crear_boton_secundario


class RespaldoDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Copias de seguridad')
        self.resize(620,280)
        layout = QVBoxLayout(self)
        self.estado = QLabel('Guarda tablas, datos y fotos de MySQL.\nEl archivo contiene información privada; guárdalo en un lugar seguro.\nPara recuperar usa restaurar_respaldo.py en una base nueva.')
        self.estado.setWordWrap(True)
        layout.addWidget(self.estado)
        self.crear = crear_boton_principal('Crear respaldo',self.elegir)
        self.verificar = crear_boton_secundario('Verificar archivo',self.comprobar)
        self.cerrar = crear_boton_secundario('Cerrar',self.reject)
        for boton in (self.crear,self.verificar,self.cerrar):
            layout.addWidget(boton)
        self.trabajos = Trabajos(self)
        self.ocupado = False

    def elegir(self):
        nombre = 'respaldo_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.zip'
        ruta,_ = QFileDialog.getSaveFileName(self,'Guardar respaldo',nombre,'ZIP (*.zip)')
        if not ruta:
            return
        if not ruta.lower().endswith('.zip'):
            ruta += '.zip'
        self.ocupado = True
        for boton in (self.crear,self.verificar,self.cerrar):
            boton.setEnabled(False)
        self.estado.setText('Creando y verificando copia…')
        self.trabajos.ejecutar(lambda: crear_respaldo(ruta),lambda filas: self.finalizar(f'Respaldo verificado: {len(filas)} tablas.\n{ruta}'),self.error)

    def finalizar(self,texto):
        self.ocupado = False
        self.estado.setText(texto)
        for boton in (self.crear,self.verificar,self.cerrar):
            boton.setEnabled(True)

    def error(self,error):
        self.finalizar(error.mensaje if isinstance(error,ErrorSistema) else 'No se pudo completar la copia.')

    def comprobar(self):
        ruta,_ = QFileDialog.getOpenFileName(self,'Verificar respaldo','','ZIP (*.zip)')
        if ruta:
            self.ocupado = True
            for boton in (self.crear,self.verificar,self.cerrar):
                boton.setEnabled(False)
            self.trabajos.ejecutar(lambda: verificar_respaldo(ruta),lambda datos: self.finalizar(f"Respaldo íntegro: {len(datos['tablas'])} tablas."),self.error)

    def reject(self):
        if not self.ocupado:
            super().reject()

    def closeEvent(self,event):
        if self.ocupado:
            event.ignore()
        else:
            super().closeEvent(event)
