from pathlib import Path
from decimal import Decimal
from database import fichas
from database.contratos import obtener_contrato
from permisos import tiene_permiso, GESTIONAR_VEHICULOS, VER_FINANCIERA, GESTIONAR_FINANCIERA
from errores import ErrorSistema
from utils.helpers import crear_tabla, celda, crear_boton_principal, crear_boton_secundario, configurar_campo_monetario
from utils.moneda import formato_dinero
from gui.trabajos import Trabajos
from gui.contrato_detalle_dialog import ContratoDetalleDialog
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QPixmap, QImageReader
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QTabWidget,
    QWidget, QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QFileDialog,
    QListWidget, QMessageBox, QDateEdit, QCheckBox, QDoubleSpinBox, QScrollArea
)


class DialogoFicha(QDialog):
    def __init__(self, parent, titulo):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.resize(960, 650)
        self.setMinimumSize(620, 420)
        self.layout_principal = QVBoxLayout(self)
        self.aviso = QLabel('')
        self.aviso.setObjectName('aviso_error')
        self.aviso.setWordWrap(True)
        self.aviso.hide()
        self.layout_principal.addWidget(self.aviso)
        self.trabajos = Trabajos(self)
        self.pestanas = QTabWidget()
        self.layout_principal.addWidget(self.pestanas)
        self.layout_principal.addWidget(crear_boton_secundario('Cerrar', self.reject))

    def proteger(self, operacion, *args):
        try:
            self.aviso.hide()
            return operacion(*args)
        except ErrorSistema as error:
            self.aviso.setText(error.mensaje)
            self.aviso.show()
            return None

    def tabla(self, titulo, columnas):
        tabla = crear_tabla(columnas)
        self.pestanas.addTab(tabla, titulo)
        return tabla

    def pintar(self, tabla, filas):
        tabla.setRowCount(len(filas))
        for i, fila in enumerate(filas):
            for j, valor in enumerate(fila):
                tabla.setItem(i, j, celda('' if valor is None else valor))


class ClienteFichaDialog(DialogoFicha):
    def __init__(self, parent, cliente_id):
        super().__init__(parent, 'Ficha del cliente')
        self.cliente_id = cliente_id
        self.datos = QLabel('')
        self.datos.setWordWrap(True)
        self.layout_principal.insertWidget(0, self.datos)
        self.ventas = self.tabla('Ventas y contratos', ['Venta','Fecha','Vehículo','Importe','Contrato','Estado'])
        self.ventas.cellDoubleClicked.connect(self.abrir_contrato)
        if tiene_permiso(VER_FINANCIERA):
            self.pagos = self.tabla('Pagos', ['Recibo','Fecha','Importe','Estado'])
            self.saldos = self.tabla('Saldos por venta', ['Venta','Precio','Saldo'])
        self.cargar()

    def cargar(self):
        resultado = self.proteger(fichas.ficha_cliente, self.cliente_id)
        if resultado is None:
            return
        cliente, self.registros = resultado
        self.datos.setText(f"{cliente['nombre']} {cliente['apellido']}\nDocumento: {cliente.get('documento') or '—'} · Teléfono: {cliente.get('telefono') or '—'}\nCorreo: {cliente.get('email') or '—'}\nDoble clic sobre una venta para consultar su contrato.")
        self.pintar(self.ventas, [(v['id'],v['fecha'],v['vehiculo'],formato_dinero(v['precio'],moneda=v['moneda']),v['numero'],v['estado']) for v in self.registros])
        if tiene_permiso(VER_FINANCIERA):
            datos = self.proteger(fichas.pagos_cliente, self.cliente_id)
            if datos is not None:
                pagos, saldos = datos
                self.pintar(self.pagos, [(p['recibo'] or p['id'],p['fecha'],formato_dinero(p['importe'],moneda=p['moneda']), 'Anulado' if p['anulado'] else 'Registrado') for p in pagos])
                self.pintar(self.saldos, [(v['id'],formato_dinero(v['precio'],moneda=v['moneda']),formato_dinero(v['saldo'],moneda=v['moneda'])) for v in saldos])

    def abrir_contrato(self, fila, _columna):
        contrato_id = self.registros[fila]['contrato_id']
        if contrato_id:
            dialogo = ContratoDetalleDialog(self, id_contrato=contrato_id)
            dialogo.setModal(False)
            dialogo.show()
            self.dialogo_detalle = dialogo


class UnidadForm(QDialog):
    def __init__(self, parent, auto_id, unidad=None):
        super().__init__(parent)
        self.auto_id = auto_id
        self.unidad = unidad
        self.setWindowTitle('Unidad del vehículo')
        self.resize(520, 420)
        layout = QVBoxLayout(self)
        formulario = QFormLayout()
        self.vin = QLineEdit()
        self.vin.setMaxLength(40)
        self.matricula = QLineEdit()
        self.matricula.setMaxLength(30)
        self.km = QSpinBox()
        self.km.setRange(0, 2147483647)
        self.estado = QComboBox()
        self.estado.addItems(['disponible','reservado','taller'])
        self.notas = QPlainTextEdit()
        for etiqueta, campo in [('Chasis / VIN',self.vin),('Matrícula',self.matricula),('Kilometraje',self.km),('Estado',self.estado),('Observaciones',self.notas)]:
            formulario.addRow(etiqueta, campo)
        layout.addLayout(formulario)
        self.aviso = QLabel('Identifica una unidad del stock existente; no aumenta el stock.')
        self.aviso.setWordWrap(True)
        layout.addWidget(self.aviso)
        botones = QHBoxLayout()
        botones.addWidget(crear_boton_secundario('Cancelar',self.reject))
        botones.addWidget(crear_boton_principal('Guardar',self.guardar))
        layout.addLayout(botones)
        if unidad:
            self.vin.setText(unidad['vin'])
            self.matricula.setText(unidad['matricula'] or '')
            self.km.setValue(unidad['kilometraje'])
            self.estado.setCurrentText(unidad['estado'])
            self.notas.setPlainText(unidad['observaciones'] or '')

    def guardar(self):
        try:
            fichas.guardar_unidad(self.auto_id,self.vin.text(),self.matricula.text(),self.km.value(),self.estado.currentText(),self.notas.toPlainText(),self.unidad['id'] if self.unidad else None)
            self.accept()
        except ErrorSistema as error:
            self.aviso.setText(error.mensaje)


class AutoFichaDialog(DialogoFicha):
    def __init__(self, parent, auto_id):
        super().__init__(parent, 'Ficha del vehículo')
        self.auto_id = auto_id
        self.puede = tiene_permiso(GESTIONAR_VEHICULOS)
        hoja = QWidget()
        layout = QVBoxLayout(hoja)
        self.cabecera = QLabel('')
        self.cabecera.setWordWrap(True)
        layout.addWidget(self.cabecera)
        formulario = QFormLayout()
        self.combustible = QComboBox()
        self.combustible.addItems(['','Nafta','Diésel','Híbrido','Eléctrico','Otro'])
        self.combustible.setEditable(True)
        self.transmision = QComboBox()
        self.transmision.addItems(['','Manual','Automática','CVT','Otra'])
        self.transmision.setEditable(True)
        self.notas = QPlainTextEdit()
        formulario.addRow('Combustible',self.combustible)
        formulario.addRow('Transmisión',self.transmision)
        formulario.addRow('Observaciones',self.notas)
        layout.addLayout(formulario)
        for campo in (self.combustible,self.transmision,self.notas):
            campo.setEnabled(self.puede)
        if self.puede:
            layout.addWidget(crear_boton_principal('Guardar ficha',self.guardar))
        self.pestanas.addTab(hoja,'Datos')
        fotos = QWidget()
        lay = QVBoxLayout(fotos)
        self.imagen = QLabel('Sin fotos')
        self.imagen.setAlignment(Qt.AlignCenter)
        self.imagen.setMinimumHeight(200)
        lay.addWidget(self.imagen,1)
        self.lista_fotos = QListWidget()
        self.lista_fotos.setMaximumHeight(100)
        self.lista_fotos.currentRowChanged.connect(self.mostrar_foto)
        lay.addWidget(self.lista_fotos)
        if self.puede:
            botones = QHBoxLayout()
            botones.addWidget(crear_boton_principal('Agregar foto',self.agregar_foto))
            botones.addWidget(crear_boton_secundario('Eliminar seleccionada',self.borrar_foto))
            lay.addLayout(botones)
        self.pestanas.addTab(fotos,'Fotos')
        hoja_unidades = QWidget()
        lay = QVBoxLayout(hoja_unidades)
        self.tabla_unidades = crear_tabla(['ID','Chasis/VIN','Matrícula','Km','Estado','Venta'])
        self.tabla_unidades.cellDoubleClicked.connect(self.editar_unidad)
        lay.addWidget(self.tabla_unidades)
        if self.puede:
            lay.addWidget(crear_boton_principal('Identificar unidad del stock',self.nueva_unidad))
        self.pestanas.addTab(hoja_unidades,'Unidades')
        self.cargar()

    def cargar(self):
        datos = self.proteger(fichas.ficha_auto,self.auto_id)
        if datos is None:
            return
        self.cabecera.setText(f"{datos['marca']} {datos['modelo']} · {datos['anio']} · {datos['color'] or '—'}\nStock: {datos['stock']} · Precio de lista: {formato_dinero(datos['precio'])}")
        self.combustible.setCurrentText(datos['combustible'] or '')
        self.transmision.setCurrentText(datos['transmision'] or '')
        self.notas.setPlainText(datos['observaciones'] or '')
        self.fotos = self.proteger(fichas.fotos_auto,self.auto_id) or []
        self.lista_fotos.clear()
        for foto in self.fotos:
            self.lista_fotos.addItem(foto['nombre'])
        self.lista_fotos.setCurrentRow(0)
        self.unidades = self.proteger(fichas.unidades_auto,self.auto_id) or []
        self.pintar(self.tabla_unidades,[(u['id'],u['vin'],u['matricula'],u['kilometraje'],u['situacion'],u['venta_id']) for u in self.unidades])

    def guardar(self):
        self.proteger(fichas.guardar_ficha,self.auto_id,self.combustible.currentText(),self.transmision.currentText(),self.notas.toPlainText())
        if not self.aviso.isVisible():
            self.cargar()

    def mostrar_foto(self, fila):
        if 0 <= fila < len(self.fotos):
            pixmap = QPixmap()
            pixmap.loadFromData(bytes(self.fotos[fila]['contenido']))
            self.imagen.setPixmap(pixmap.scaled(720,330,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        else:
            self.imagen.setText('Sin fotos')

    def agregar_foto(self):
        ruta, _ = QFileDialog.getOpenFileName(self,'Seleccionar foto','','Imágenes (*.jpg *.jpeg *.png *.webp)')
        if not ruta:
            return
        archivo = Path(ruta)
        if archivo.stat().st_size > 5 * 1024 * 1024:
            self.aviso.setText('La foto debe ocupar como máximo 5 MB.')
            self.aviso.show()
            return
        reader = QImageReader(ruta)
        reader.setAutoTransform(True)
        if reader.size().width() * reader.size().height() > 40_000_000:
            self.aviso.setText('La foto supera 40 megapíxeles. Redúcela antes de cargarla.')
            self.aviso.show()
            return
        if reader.read().isNull():
            self.aviso.setText('No se pudo leer la imagen.')
            self.aviso.show()
            return
        self.proteger(fichas.agregar_foto,self.auto_id,archivo.read_bytes(),archivo.name)
        self.cargar()

    def borrar_foto(self):
        fila = self.lista_fotos.currentRow()
        if fila >= 0 and QMessageBox.question(self,'Eliminar foto','¿Eliminar esta foto?') == QMessageBox.Yes:
            self.proteger(fichas.eliminar_foto,self.fotos[fila]['id'])
            self.cargar()

    def nueva_unidad(self):
        if UnidadForm(self,self.auto_id).exec():
            self.cargar()

    def editar_unidad(self, fila, _columna):
        if self.puede and not self.unidades[fila]['venta_id']:
            if UnidadForm(self,self.auto_id,self.unidades[fila]).exec():
                self.cargar()
