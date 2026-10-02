# ==========================================
# FORMULARIO DE CONTRATO
# ==========================================
# Se abre siempre a partir de una venta: el
# contrato hereda cliente, vehículo, precio y
# fecha de ella, así que aquí solo se rellena
# lo que la venta no sabe: cómo se paga y qué
# se anota.
#
# El contrato no se edita después. Si hay que
# corregirlo, se cancela y se vuelve a hacer
# desde la venta.
# ==========================================


from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QPlainTextEdit,
    QMessageBox
)

from database.contratos import (
    crear_contrato,
    obtener_contrato,
    registrar_pdf,
    FORMAS_PAGO,
    ESTADOS
)

from utils.validaciones import (
    es_precio,
    primer_error
)

from utils.helpers import (
    crear_boton_principal,
    crear_boton_secundario,
    conectar_enter_guardar
)

from utils.contrato_pdf import (
    generar_contrato,
    ruta_relativa
)


def formato_dinero(valor):
    return f"$ {float(valor):,.2f}"


class ContratoForm(QDialog):

    def __init__(self, parent=None, venta=None):
        super().__init__(parent)

        # venta es una fila de ventas_sin_contrato():
        # (id, fecha, cliente, vehiculo, precio)

        self.venta = venta

        self.id_guardado = None

        self.setObjectName("contrato_form")

        self.setWindowTitle("Crear contrato de compraventa")

        self.setFixedWidth(520)

        self.crear_interfaz()

    # =============================
    # INTERFAZ
    # =============================

    def crear_interfaz(self):

        (
            id_venta,
            fecha,
            cliente,
            vehiculo,
            precio
        ) = self.venta

        layout_principal = QVBoxLayout()

        layout_principal.setSpacing(14)

        self.setLayout(layout_principal)

        # ------------------------------
        # RESUMEN DE LA VENTA
        # ------------------------------
        # No es editable: el contrato no se
        # inventa datos, los toma de la venta.

        layout_principal.addWidget(
            self.crear_resumen(
                id_venta, fecha, cliente, vehiculo, precio
            )
        )

        # ------------------------------
        # CONDICIONES DE PAGO
        # ------------------------------

        formulario = QFormLayout()

        formulario.setSpacing(10)

        self.campo_forma_pago = QComboBox()

        self.campo_forma_pago.addItems(FORMAS_PAGO)

        self.campo_forma_pago.setCurrentText(
            "Anticipo + cuotas"
            if precio else "Contado"
        )

        self.campo_anticipo = QLineEdit("0")

        self.campo_anticipo.setPlaceholderText("Ej: 5000")

        self.campo_cuotas = QSpinBox()

        self.campo_cuotas.setRange(0, 240)

        self.campo_cuotas.setValue(12)

        self.campo_cuotas.setSpecialValueText("Sin cuotas")

        formulario.addRow(
            "Forma de pago:", self.campo_forma_pago
        )

        formulario.addRow(
            "Anticipo:", self.campo_anticipo
        )

        formulario.addRow(
            "Cantidad de cuotas:", self.campo_cuotas
        )

        layout_principal.addLayout(formulario)

        # ------------------------------
        # CÁLCULO EN VIVO
        # ------------------------------
        # La cuota depende del anticipo y del
        # número de cuotas: se muestra mientras
        # se escribe para no descubrir el
        # importe al guardar.

        self.etiqueta_resumen = QLabel("")

        self.etiqueta_resumen.setObjectName("aviso")

        self.etiqueta_resumen.setWordWrap(True)

        layout_principal.addWidget(
            self.etiqueta_resumen
        )

        # ------------------------------
        # OBSERVACIONES
        # ------------------------------

        etiqueta_observaciones = QLabel("Observaciones:")

        etiqueta_observaciones.setObjectName(
            "etiqueta_filtro"
        )

        layout_principal.addWidget(
            etiqueta_observaciones
        )

        self.campo_observaciones = QPlainTextEdit()

        self.campo_observaciones.setPlaceholderText(
            "Ej: el vehículo se entrega con "
            "documentación al día y service "
            "del último año."
        )

        self.campo_observaciones.setFixedHeight(90)

        layout_principal.addWidget(
            self.campo_observaciones
        )

        # ------------------------------
        # ESTADO
        # ------------------------------
        # El contrato nace activo: es lo que
        # pasa al firmar. Los demás estados se
        # alcanzan desde el listado.

        etiqueta_estado = QLabel(
            f"Estado inicial: {ESTADOS['activo']}"
        )

        etiqueta_estado.setObjectName("subtitulo")

        layout_principal.addWidget(
            etiqueta_estado
        )

        # ------------------------------
        # BOTONES
        # ------------------------------

        botones = QHBoxLayout()

        botones.addWidget(
            crear_boton_secundario(
                "Cancelar",
                self.reject
            )
        )

        botones.addWidget(
            crear_boton_principal(
                "Confirmar y generar PDF",
                self.guardar
            )
        )

        layout_principal.addLayout(botones)

        # ------------------------------
        # REACCIONES
        # ------------------------------
        # El resumen se recalcula con cualquier
        # cambio del importe o del plazo.

        self.campo_anticipo.textChanged.connect(
            self.actualizar_resumen
        )

        self.campo_cuotas.valueChanged.connect(
            self.actualizar_resumen
        )

        # Return guarda, pero no desde el combo:
        # ahí abre y cierra la lista desplegable.

        conectar_enter_guardar(
            [
                self.campo_anticipo
            ],
            self.guardar
        )

        self.actualizar_resumen()

        self.campo_anticipo.setFocus()

        self.campo_anticipo.selectAll()

    def crear_resumen(
        self, id_venta, fecha, cliente, vehiculo, precio
    ):
        """
        Cabecera con los datos heredados de la
        venta.
        """

        contenedor = QWidget()

        contenedor.setObjectName("tarjeta")

        layout = QVBoxLayout(contenedor)

        layout.setContentsMargins(14, 12, 14, 12)

        layout.setSpacing(4)

        titulo = QLabel(f"Venta {id_venta}")

        titulo.setObjectName("nombre_tarjeta")

        layout.addWidget(titulo)

        for etiqueta, valor in (
            ("Cliente", cliente),
            ("Vehículo", vehiculo),
            ("Fecha", str(fecha)),
            ("Precio de venta", formato_dinero(precio))
        ):

            linea = QLabel(f"{etiqueta}:  {valor}")

            linea.setObjectName("pie")

            linea.setWordWrap(True)

            layout.addWidget(linea)

        return contenedor

    # =============================
    # CÁLCULO
    # =============================

    def leer_anticipo(self):
        """
        El anticipo como número, o 0 si el campo
        está vacío o no se puede leer.

        Devolver 0 en vez de fallar permite que
        el resumen se actualice mientras el
        usuario escribe y solo se avise al
        guardar.
        """

        texto = self.campo_anticipo.text().strip()

        if not texto:

            return 0.0

        try:

            return float(texto.replace(",", ""))

        except (TypeError, ValueError):

            return -1.0

    def actualizar_resumen(self):
        """
        Muestra el importe de la cuota y lo que
        queda por pagar.
        """

        precio = float(self.venta[4])

        anticipo = self.leer_anticipo()

        cuotas = self.campo_cuotas.value()

        if anticipo < 0:
            self.etiqueta_resumen.setText(
                "El anticipo tiene que ser un número."
            )
            return

        if anticipo > precio:
            self.etiqueta_resumen.setText(
                "El anticipo no puede ser mayor que "
                "el precio de venta."
            )
            return

        saldo = precio - anticipo

        if cuotas < 1:
            self.etiqueta_resumen.setText(
                f"Total a pagar: {formato_dinero(saldo)}"
            )
            return

        self.etiqueta_resumen.setText(
            f"Total a pagar: {formato_dinero(saldo)}  ·  "
            f"{cuotas} cuotas de "
            f"{formato_dinero(saldo / cuotas)}"
        )

    # =============================
    # GUARDAR
    # =============================

    def guardar(self):

        (
            id_venta,
            fecha,
            cliente,
            vehiculo,
            precio
        ) = self.venta

        forma_pago = self.campo_forma_pago.currentText()

        anticipo_texto = self.campo_anticipo.text().strip()

        anticipo_texto = anticipo_texto or "0"

        cuotas = self.campo_cuotas.value()

        observaciones = (
            self.campo_observaciones.toPlainText().strip()
        )

        # ------------------------------
        # VALIDACIONES
        # ------------------------------

        error = primer_error([
            es_precio(
                anticipo_texto,
                "El anticipo"
            )
        ])

        if not error:

            if float(anticipo_texto) > float(precio):
                error = (
                    "El anticipo no puede ser mayor que "
                    "el precio de venta."
                )

        if (
            not error
            and forma_pago == "Contado"
            and float(anticipo_texto) > 0
        ):
            error = (
                "En contado no hay anticipo ni "
                "cuotas: el pago es completo."
            )

        if error:

            QMessageBox.warning(
                self,
                "Dato inválido",
                error
            )

            return

        # ------------------------------
        # GUARDAR
        # ------------------------------

        id_contrato, motivo = crear_contrato(
            venta_id=id_venta,
            forma_pago=forma_pago,
            anticipo=float(anticipo_texto),
            cantidad_cuotas=cuotas,
            observaciones=observaciones or None
        )

        if id_contrato is None:

            QMessageBox.warning(
                self,
                "No se pudo crear el contrato",
                motivo
            )

            return

        self.id_guardado = id_contrato

        # ------------------------------
        # PDF
        # ------------------------------
        # Se genera aquí y no en el listado: el
        # flujo pedido es guardar y a continuación
        # obtener el documento, y así el archivo
        # existe nada más confirmar.

        self.generar_pdf(id_contrato)

    def generar_pdf(self, id_contrato):
        """
        Crea el PDF nada más guardar el contrato.
        """

        contrato = obtener_contrato(id_contrato)

        if not contrato:
            return

        try:

            ruta = generar_contrato(contrato)

        except OSError as error:

            QMessageBox.warning(
                self,
                "No se pudo generar el PDF",
                "El contrato se guardó, pero el "
                "archivo no pudo escribirse:\n\n"
                f"{error}"
            )

            self.accept()

            return

        registrar_pdf(
            id_contrato,
            ruta_relativa(contrato["numero"])
        )

        QMessageBox.information(
            self,
            "Contrato creado",
            f"El contrato {contrato['numero']} se "
            "guardó correctamente.\n\n"
            "El PDF se generó en:\n"
            f"{ruta}\n\n"
            "Desde el módulo Contratos puede "
            "abrirlo de nuevo cuando lo necesite."
        )

        self.accept()
