from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QMessageBox
)

from PySide6.QtCore import QDate

from database.clientes import (
    obtener_clientes_para_venta
)

from database.autos import (
    obtener_autos_para_venta
)

from database.ventas import (
    registrar_venta
)

from database.contratos import (
    contrato_de_venta
)

from permisos import (
    tiene_permiso,
    CREAR_CONTRATOS
)

from errores import ErrorSistema

from utils.validaciones import (
    es_precio,
    primer_error
)

from utils.moneda import prefijo_moneda

from utils.helpers import (
    crear_boton_principal,
    crear_boton_secundario,
    avisar_error
)


# ==========================================
# NOTA DE DISEÑO
# ==========================================
# Una venta no se edita: es un registro del
# histórico. El precio queda congelado en el
# momento de la venta, aunque después cambie
# autos.precio.
#
# Si una venta está mal, se elimina (lo que
# devuelve la unidad al stock) y se vuelve a
# registrar. Así el inventario nunca queda
# descuadrado.
# ==========================================


class VentaForm(QDialog):

    # Id de la venta recien registrada, para
    # que quien abrio el formulario ofrezca
    # despues el contrato.
    #
    # El contrato NO se abre aqui. Anadirlo
    # dentro de guardar() apilaba dos
    # dialogos modales: el de la venta se
    # quedaba abierto detras del del
    # contrato y, peor, cualquier prueba
    # automatica que contestara "si" se
    # quedaba colgada esperando a que
    # alguien cerrara a mano una ventana
    # modal. Aqui solo se avisa de que
    # hace falta; el formulario se cierra y
    # es VentasView quien abre el contrato.

    venta_para_contrato = None

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("venta_form")

        self.setWindowTitle("Nueva venta")

        self.setFixedWidth(480)

        self.crear_interfaz()
        self.cargar_listas()

    def crear_interfaz(self):

        layout_principal = QVBoxLayout()
        self.setLayout(layout_principal)

        formulario = QFormLayout()

        self.combo_cliente = QComboBox()

        self.combo_auto = QComboBox()

        self.campo_fecha = QDateEdit()

        self.campo_fecha.setCalendarPopup(True)

        self.campo_fecha.setDate(
            QDate.currentDate()
        )

        self.campo_fecha.setDisplayFormat(
            "dd/MM/yyyy"
        )

        self.campo_precio = QDoubleSpinBox()

        self.campo_precio.setRange(0, 999999999)

        self.campo_precio.setDecimals(2)

        # El prefijo sale de la moneda configurada: con
        # euros tiene que poner "EUR " y no "$ ".

        self.campo_precio.setPrefix(
            prefijo_moneda()
        )

        formulario.addRow("Cliente:", self.combo_cliente)
        formulario.addRow("Vehículo:", self.combo_auto)
        formulario.addRow("Fecha:", self.campo_fecha)
        formulario.addRow("Precio:", self.campo_precio)

        layout_principal.addLayout(formulario)

        # ------------------------------
        # AVISO DE STOCK
        # ------------------------------

        self.aviso_stock = QLabel("")

        self.aviso_stock.setObjectName(
            "aviso"
        )

        self.aviso_stock.setWordWrap(True)

        layout_principal.addWidget(
            self.aviso_stock
        )

        botones = QHBoxLayout()

        boton_cancelar = crear_boton_secundario(
            "Cancelar",
            self.reject
        )

        boton_guardar = crear_boton_principal(
            "Registrar venta",
            self.guardar
        )

        botones.addWidget(
            boton_cancelar
        )

        botones.addWidget(
            boton_guardar
        )

        layout_principal.addLayout(botones)

        # Al cambiar de vehículo se propone su
        # precio, que el usuario puede ajustar.

        self.combo_auto.currentIndexChanged.connect(
            self.actualizar_precio
        )

        # Return registra la venta. No se conecta
        # al combo de cliente: allí Return abre y
        # cierra la lista desplegable.

    def cargar_listas(self):

        clientes = obtener_clientes_para_venta()

        if not clientes:
            self.combo_cliente.addItem(
                "No hay clientes registrados",
                None
            )

        for id_cliente, nombre, apellido in clientes:

            self.combo_cliente.addItem(
                f"{nombre} {apellido}",
                id_cliente
            )

        # Se bloquean las señales mientras se
        # puebla el combo para no disparar la
        # actualización del precio por cada
        # elemento.

        self.combo_auto.blockSignals(True)

        autos = obtener_autos_para_venta()

        if not autos:
            self.combo_auto.addItem(
                "No hay vehículos registrados",
                None
            )

        for id_auto, vehiculo, precio, stock in autos:

            self.combo_auto.addItem(
                f"{vehiculo}  ·  stock {stock}",
                (id_auto, precio, stock)
            )

        self.combo_auto.blockSignals(False)

        # Las señales estaban bloqueadas al poblar,
        # así que el precio del primer vehículo se
        # propone explícitamente.
        self.actualizar_precio()

    def actualizar_precio(self):

        datos = self.combo_auto.currentData()

        if not datos:
            return

        self.campo_precio.setValue(
            float(datos[1])
        )

        self.actualizar_stock()

    def actualizar_stock(self):

        datos = self.combo_auto.currentData()

        if not datos:
            self.aviso_stock.setText(
                "Debes registrar clientes y vehículos "
                "antes de vender."
            )

            return

        stock = datos[2]

        if stock <= 0:
            self.aviso_stock.setText(
                "Este vehículo no tiene stock: "
                "no se podrá registrar la venta."
            )

        elif stock == 1:
            self.aviso_stock.setText(
                "Queda la última unidad disponible."
            )

        else:
            self.aviso_stock.setText(
                f"Quedan {stock} unidades disponibles."
            )

    def guardar(self):

        cliente_id = self.combo_cliente.currentData()

        datos_auto = self.combo_auto.currentData()

        # ------------------------------
        # VALIDACIONES
        # ------------------------------

        if not cliente_id:
            QMessageBox.warning(
                self,
                "Dato faltante",
                "Debes seleccionar un cliente."
            )

            return

        if not datos_auto:
            QMessageBox.warning(
                self,
                "Dato faltante",
                "Debes seleccionar un vehículo."
            )

            return

        error = primer_error([
            es_precio(
                self.campo_precio.value(),
                "El precio"
            )
        ])

        if error:
            QMessageBox.warning(
                self,
                "Dato inválido",
                error
            )

            return

        # ------------------------------
        # REGISTRAR
        # ------------------------------
        # La transacción, la verificación de
        # stock y el descuento se resuelven
        # en database/ventas.py.

        fecha = self.campo_fecha.date().toString(
            "yyyy-MM-dd"
        )

        try:

            resultado, mensaje = registrar_venta(
                cliente_id,
                datos_auto[0],
                fecha,
                self.campo_precio.value()
            )

        except ErrorSistema as error:

            avisar_error(self, error)

            return

        if not resultado:
            QMessageBox.warning(
                self,
                "Venta no registrada",
                mensaje
            )

            return

        # ------------------------------
        # OFRECER EL CONTRATO
        # ------------------------------
        # El contrato es el paso que sigue a la
        # venta. Se ofrece con la venta ya
        # cerrada y se puede rechazar: la venta
        # queda registrada igual y el contrato se
        # crea después desde el historial.

        if self.ofrecer_contrato(resultado):

            self.venta_para_contrato = resultado

        self.accept()

    def ofrecer_contrato(self, id_venta):
        """
        Pregunta si se crea el contrato ahora.

        Devuelve True si el usuario acepta.

        Solo se pregunta a quien tiene permiso
        para crearlo. Antes hay que comprobar
        el permiso a mano: contrato_de_venta()
        lanza PermisoDenegado sin él, y esa
        excepción saltaría después de guardar la
        venta y haría creer que falló.
        """

        if not tiene_permiso(CREAR_CONTRATOS):

            return False

        if contrato_de_venta(id_venta):

            return False

        respuesta = QMessageBox.question(
            self,
            "Venta registrada",
            "La venta se registró correctamente.\n\n"
            "¿Quiere crear ahora el contrato de "
            "compraventa?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        return respuesta == QMessageBox.Yes
