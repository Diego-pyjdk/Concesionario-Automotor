from database import fichas
from database.conexion import obtener_conexion, conexiones_libres
from permisos import requiere_permiso, VER_FINANCIERA, GESTIONAR_FINANCIERA, tiene_permiso
from gui.fichas_dialog import DialogoFicha
from utils.helpers import crear_tabla, crear_boton_principal, crear_boton_secundario, configurar_campo_monetario
from utils.moneda import formato_dinero
from errores import ErrorSistema
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QComboBox,QPlainTextEdit,QCheckBox,QDateEdit,QDoubleSpinBox,QLabel,QDialog


@conexiones_libres
@fichas.traducir_mysql
@requiere_permiso(VER_FINANCIERA)
def contratos_seguimiento():
    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("""SELECT c.id,c.numero,c.moneda,CONCAT(cl.nombre,' ',cl.apellido) AS cliente
        FROM contratos c JOIN clientes cl ON cl.id=c.cliente_id
        WHERE c.estado != 'cancelado' ORDER BY c.id DESC""")
    return cursor.fetchall()


class SeguimientoDialog(DialogoFicha):
    def __init__(self, parent=None, contrato_id=None):
        super().__init__(parent,'Seguimiento de cobranza')
        self.contrato_id = contrato_id
        self.registros = []
        self.tabla_registros = self.tabla('Agenda e historial',['ID','Cliente','Contrato','Fecha','Canal','Notas','Contacto','Promesa','Estado'])
        barra = QHBoxLayout()
        self.pendientes = QCheckBox('Solo pendientes')
        self.pendientes.setChecked(True)
        self.pendientes.toggled.connect(self.cargar)
        barra.addWidget(self.pendientes)
        if tiene_permiso(GESTIONAR_FINANCIERA):
            barra.addWidget(crear_boton_principal('Registrar contacto',self.nuevo))
            barra.addWidget(crear_boton_secundario('Marcar atendido',self.completar))
        self.layout_principal.insertLayout(1,barra)
        self.cargar()

    def cargar(self, *_args):
        datos = self.proteger(fichas.seguimiento,self.contrato_id,self.pendientes.isChecked())
        if datos is not None:
            self.registros = datos
            self.pintar(self.tabla_registros,[(r['id'],r['cliente'],r['numero'],r['fecha'],r['canal'],r['notas'],r['proximo_contacto'],
                (f"{r['promesa_fecha']} · {formato_dinero(r['promesa_importe'],moneda=r['moneda'])}" if r['promesa_fecha'] else ''),
                'Atendido' if r['completado'] else 'Pendiente') for r in datos])

    def nuevo(self):
        dialogo = ContactoForm(self,self.contrato_id)
        if dialogo.exec():
            self.cargar()

    def completar(self):
        fila = self.tabla_registros.currentRow()
        if fila >= 0:
            self.proteger(fichas.completar_seguimiento,self.registros[fila]['id'])
            self.cargar()


class ContactoForm(QDialog):
    def __init__(self,parent=None,contrato_id=None):
        super().__init__(parent)
        self.setWindowTitle('Registrar contacto de cobranza')
        self.resize(620,570)
        layout = QVBoxLayout(self)
        formulario = QFormLayout()
        self.contrato = QComboBox()
        self.contratos = contratos_seguimiento()
        for c in self.contratos:
            self.contrato.addItem(f"{c['numero']} · {c['cliente']} ({c['moneda']})",c['id'])
        if contrato_id:
            self.contrato.setCurrentIndex(self.contrato.findData(contrato_id))
        self.canal = QComboBox()
        self.canal.addItems(['llamada','whatsapp','presencial','otro'])
        self.notas = QPlainTextEdit()
        self.proximo = QDateEdit(QDate.currentDate())
        self.proximo.setCalendarPopup(True)
        self.con_proximo = QCheckBox('Programar próximo contacto')
        self.con_promesa = QCheckBox('Registrar promesa de pago')
        self.promesa = QDateEdit(QDate.currentDate())
        self.promesa.setCalendarPopup(True)
        self.importe = QDoubleSpinBox()
        configurar_campo_monetario(self.importe)
        for texto, campo in [('Contrato',self.contrato),('Canal',self.canal),('Notas',self.notas),('',self.con_proximo),('Próximo contacto',self.proximo),('',self.con_promesa),('Fecha de promesa',self.promesa),('Importe prometido',self.importe)]:
            formulario.addRow(texto,campo)
        layout.addLayout(formulario)
        self.aviso = QLabel('Una promesa no registra un pago ni modifica el saldo.')
        self.aviso.setWordWrap(True)
        layout.addWidget(self.aviso)
        botones = QHBoxLayout()
        botones.addWidget(crear_boton_secundario('Cancelar',self.reject))
        botones.addWidget(crear_boton_principal('Guardar contacto',self.guardar))
        layout.addLayout(botones)
        self.contrato.currentIndexChanged.connect(self.ajustar_moneda)
        self.ajustar_moneda()
        self.proximo.setEnabled(False)
        self.promesa.setEnabled(False)
        self.importe.setEnabled(False)
        self.con_proximo.toggled.connect(self.proximo.setEnabled)
        self.con_promesa.toggled.connect(self.promesa.setEnabled)
        self.con_promesa.toggled.connect(self.importe.setEnabled)

    def ajustar_moneda(self, *_args):
        indice = self.contrato.currentIndex()
        if indice >= 0:
            moneda = self.contratos[indice]['moneda']
            self.importe.setDecimals(0 if moneda == 'PYG' else 2)
            self.importe.setPrefix('Gs ' if moneda == 'PYG' else '$ ')

    def guardar(self):
        try:
            fichas.registrar_seguimiento(self.contrato.currentData(),self.canal.currentText(),self.notas.toPlainText(),
                self.proximo.date().toPython() if self.con_proximo.isChecked() else None,
                self.promesa.date().toPython() if self.con_promesa.isChecked() else None,
                self.importe.value() if self.con_promesa.isChecked() else None)
            self.accept()
        except ErrorSistema as error:
            self.aviso.setText(error.mensaje)
