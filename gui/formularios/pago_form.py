# ==========================================
# REGISTRAR UN PAGO
# ==========================================
# Un pago no se edita: se registra. Si está mal,
# el administrador lo borra desde el detalle de la
# venta y se vuelve a meter.
#
# El formulario enseña el saldo ANTES de aceptar
# nada: si el cliente debe 18.000 y alguien teclea
# 18.000 por costumbre, el error se ve en la
# pantalla y no hace falta esperar al aviso de
# "importe mayor que el saldo".
# ==========================================


from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QLabel,
    QMessageBox
)

from PySide6.QtCore import QDate

from errores import ErrorSistema

from database.pagos import (
    registrar_pago,
    FORMAS_PAGO
)

from utils.moneda import (
    formato_dinero,
    formatear_numero
)

from utils.validaciones import (
    texto_obligatorio,
    primer_error
)

from utils.helpers import (
    crear_boton_principal,
    crear_boton_secundario,
    conectar_enter_guardar,
    avisar_error
)


class PagoForm(QDialog):

    def __init__(
        self,
        parent=None,
        venta_id=None,
        saldo=0.0,
        forma_por_defecto="Efectivo"
    ):
        super().__init__(parent)

        self.venta_id = venta_id
        self.saldo = float(saldo or 0)

        self.setWindowTitle("Registrar pago")
        self.setModal(True)
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)

        formulario = QFormLayout()

        # ------------------------------
        # AVISO DE SALDO
        # ------------------------------

        self.etiqueta_saldo = QLabel("")

        self.etiqueta_saldo.setObjectName(
            "aviso_error"
            if self.saldo <= 0
            else "aviso"
        )

        layout.addWidget(self.etiqueta_saldo)

        # ------------------------------
        # CAMPOS
        # ------------------------------

        self.campo_importe = QDoubleSpinBox()

        self.campo_importe.setRange(
            0.01, 999999999.0
        )

        self.campo_importe.setDecimals(2)

        self.campo_importe.setSingleStep(100)

        self.campo_importe.setValue(
            min(self.saldo, 100.0) if self.saldo > 0
            else 0.01
        )

        self.campo_fecha = QDateEdit()

        self.campo_fecha.setCalendarPopup(True)

        self.campo_fecha.setDisplayFormat("dd/MM/yyyy")

        self.campo_fecha.setDate(QDate.currentDate())

        self.campo_forma = QComboBox()

        for forma in FORMAS_PAGO:

            self.campo_forma.addItem(forma)

        indice = self.campo_forma.findText(
            forma_por_defecto
        )

        if indice >= 0:

            self.campo_forma.setCurrentIndex(indice)

        self.campo_referencia = QLineEdit()

        self.campo_referencia.setPlaceholderText(
            "Nº de operación, cheque..."
        )

        self.campo_concepto = QLineEdit()

        self.campo_concepto.setPlaceholderText(
            "Ej: primera cuota"
        )

        formulario.addRow(
            "Importe:", self.campo_importe
        )

        formulario.addRow("Fecha:", self.campo_fecha)

        formulario.addRow("Forma:", self.campo_forma)

        formulario.addRow(
            "Referencia:", self.campo_referencia
        )

        formulario.addRow(
            "Concepto:", self.campo_concepto
        )

        layout.addLayout(formulario)

        # ------------------------------
        # BOTONES
        # ------------------------------

        botones = QHBoxLayout()

        botones.setSpacing(10)

        botones.addWidget(crear_boton_principal(
            "Registrar pago",
            self.guardar
        ))

        botones.addWidget(crear_boton_secundario(
            "Cancelar",
            self.reject
        ))

        botones.addStretch()

        layout.addLayout(botones)

        # Cada cambio del importe recalcula lo que
        # quedaría: mejor verlo antes de confirmar
        # que descubrirlo en el aviso de error.

        self.campo_importe.valueChanged.connect(
            self.actualizar_aviso
        )

        self.actualizar_aviso()

        # ------------------------------
        # TECLADO
        # ------------------------------
        # Return guarda, pero NO en el combo: ahí
        # abriría y cerraría la lista desplegable.

        self.campo_importe.returnPressed.connect(
            self.guardar
        )

        self.campo_referencia.returnPressed.connect(
            self.guardar
        )

        self.campo_concepto.returnPressed.connect(
            self.guardar
        )

        conectar_enter_guardar(
            [
                self.campo_importe,
                self.campo_referencia,
                self.campo_concepto
            ],
            self.guardar
        )

        self.campo_importe.setFocus()

        self.campo_importe.selectAll()

    def actualizar_aviso(self):
        """
        Muestra lo que queda después de este pago.

        Se recalcula con cada cambio del importe: es
        la forma de que nadie descubra que se pasó
        después de confirmar.
        """

        if self.saldo <= 0:

            self.etiqueta_saldo.setText(
                "Esta venta no tiene saldo pendiente."
            )

            return

        restante = self.saldo - self.campo_importe.value()

        if restante < -0.005:

            self.etiqueta_saldo.setText(
                f"El importe es mayor que el saldo "
                f"pendiente ({formato_dinero(self.saldo)})."
            )

        elif restante < 0.005:

            self.etiqueta_saldo.setText(
                f"Saldo pendiente: "
                f"{formato_dinero(self.saldo)}. "
                "Con este pago queda saldada."
            )

        else:

            self.etiqueta_saldo.setText(
                f"Saldo pendiente: "
                f"{formato_dinero(self.saldo)}. "
                f"Quedaría {formato_dinero(restante)}."
            )

    # =============================
    # GUARDAR
    # =============================

    def guardar(self):

        referencia = (
            self.campo_referencia.text().strip()
        )

        concepto = (
            self.campo_concepto.text().strip()
        )

        error = primer_error([
            texto_obligatorio(
                self.campo_forma.currentText(),
                "la forma de pago"
            )
        ])

        if error:

            QMessageBox.warning(
                self,
                "Dato faltante",
                error
            )

            return

        if self.saldo <= 0:

            QMessageBox.warning(
                self,
                "No hay saldo pendiente",
                "Esta venta ya está saldada."
            )

            return

        try:

            id_pago, motivo = registrar_pago(
                venta_id=self.venta_id,
                importe=self.campo_importe.value(),
                fecha=self.campo_fecha.date().toString(
                    "yyyy-MM-dd"
                ),
                forma=self.campo_forma.currentText(),
                referencia=referencia,
                concepto=concepto
            )

        except ErrorSistema as error:

            avisar_error(self, error)

            return

        if id_pago is None:

            QMessageBox.warning(
                self,
                "No se pudo registrar el pago",
                motivo
            )

            return

        self.saldo = max(0.0, self.saldo -
                         self.campo_importe.value())

        self.actualizar_aviso()

        QMessageBox.information(
            self,
            "Pago registrado",
            f"Se registraron "
            f"{formato_dinero(self.campo_importe.value())}."
            + (
                "\n\nLa venta queda saldada."
                if self.saldo <= 0
                else f"\n\nQueda pendiente "
                     f"{formato_dinero(self.saldo)}."
            )
        )

        self.accept()
