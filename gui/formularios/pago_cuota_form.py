# ==========================================
# COBRO DE UNA CUOTA
# ==========================================
# El formulario para registrar un pago contra una
# cuota concreta.
#
# Tres decisiones que lo definen:
#
# 1. NO deja escribir el importe a ciegas. Muestra de
#    qué se trata, cuánto queda y cuánto se va a
#    cobrar. Un formulario de cobro que solo pide una
#    cifra es un formulario de errores.
#
# 2. El importe por defecto es EL SALDO COMPLETO. Es
#    lo que se cobra casi siempre, y tener que
#    escribirlo cada vez es una fuente de erratas.
#
# 3. Deja pagar una parte. Un cliente que paga la
#    mitad paga la mitad, y queda registrado como tal.


from datetime import date
from decimal import Decimal

from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout
)

import database.financiera as financiera

from database.pagos import FORMAS_PAGO

from errores import PermisoDenegado

from utils.helpers import (
    crear_boton_principal,
    crear_boton_secundario,
    conectar_enter_guardar
)

from utils.moneda import formato_dinero

from utils.registro import registrar_error_inesperado


class PagoCuotaForm(QDialog):

    def __init__(self, parent=None, id_cuota=None):
        super().__init__(parent)

        self.id_cuota = id_cuota

        self.cuota = None

        self.recibo = None

        self.crear_interfaz()

        self.cargar()

    # =============================
    # INTERFAZ
    # =============================

    def crear_interfaz(self):

        self.setWindowTitle("Registrar pago de cuota")

        self.setModal(True)

        self.setMinimumWidth(470)

        layout = QVBoxLayout()

        layout.setSpacing(14)

        self.setLayout(layout)

        # ------------------------------
        # QUÉ SE ESTÁ COBRANDO
        # ------------------------------

        self.etiqueta_contexto = QLabel("")

        self.etiqueta_contexto.setObjectName("aviso")

        self.etiqueta_contexto.setWordWrap(True)

        layout.addWidget(self.etiqueta_contexto)

        # ------------------------------
        # LOS DATOS DEL PAGO
        # ------------------------------

        formulario = QFormLayout()

        formulario.setSpacing(10)

        self.campo_importe = QDoubleSpinBox()

        self.campo_importe.setRange(0, 999999999)

        self.campo_importe.setDecimals(2)

        # Sin separador de miles en el campo. QDoubleSpinBox
        # lo pone con el punto, que en el formato que se
        # usa para escribir se lee como decimal: obliga a
        # teclear 1000,50 en vez de 1.000,50.

        self.campo_importe.setGroupSeparatorShown(False)

        formulario.addRow(
            "Importe a cobrar:", self.campo_importe
        )

        self.campo_fecha = QDateEdit()

        self.campo_fecha.setCalendarPopup(True)

        self.campo_fecha.setDisplayFormat("dd/MM/yyyy")

        self.campo_fecha.setDate(
            self.campo_fecha.date().fromString(
                date.today().isoformat(), "yyyy-MM-dd"
            )
        )

        formulario.addRow("Fecha:", self.campo_fecha)

        self.campo_forma = QComboBox()

        self.campo_forma.addItems(FORMAS_PAGO)

        formulario.addRow(
            "Forma de pago:", self.campo_forma
        )

        self.campo_recibo = QLineEdit()

        self.campo_recibo.setPlaceholderText(
            "Se genera solo si se deja vacío"
        )

        formulario.addRow("Recibo:", self.campo_recibo)

        self.campo_concepto = QLineEdit()

        self.campo_concepto.setPlaceholderText("Opcional")

        formulario.addRow("Concepto:", self.campo_concepto)

        layout.addLayout(formulario)

        # ------------------------------
        # EL ESTADO DE LA CUOTA
        # ------------------------------

        self.etiqueta_estado = QLabel("")

        self.etiqueta_estado.setObjectName("pie")

        self.etiqueta_estado.setWordWrap(True)

        layout.addWidget(self.etiqueta_estado)

        # ------------------------------
        # ERROR
        # ------------------------------
        # Las etiquetas de error empiezan ocultas: si no,
        # queda un recuadro rojo vacío que parece un
        # error que ya ocurrió.

        self.etiqueta_error = QLabel("")

        self.etiqueta_error.setObjectName("aviso_error")

        self.etiqueta_error.setWordWrap(True)

        self.etiqueta_error.setVisible(False)

        layout.addWidget(self.etiqueta_error)

        # ------------------------------
        # BOTONES
        # ------------------------------

        fila = QHBoxLayout()

        fila.setSpacing(10)

        fila.addStretch()

        fila.addWidget(crear_boton_secundario(
            "Cancelar", self.reject
        ))

        self.boton_guardar = crear_boton_principal(
            "Registrar pago", self.guardar
        )

        fila.addWidget(self.boton_guardar)

        layout.addLayout(fila)

        conectar_enter_guardar(
            [self.campo_importe, self.campo_concepto],
            self.guardar
        )

    # =============================
    # DATOS
    # =============================

    def cargar(self):

        self.cuota = self.obtener_cuota()

        if not self.cuota:

            self.mostrar_error(
                "La cuota indicada no existe."
            )

            self.boton_guardar.setEnabled(False)

            return

        cuota = self.cuota

        cliente = (
            f"{cuota['cliente_nombre']} "
            f"{cuota['cliente_apellido']}"
        )

        vehiculo = f"{cuota['marca']} {cuota['modelo']}"

        self.etiqueta_contexto.setText(
            f"<b>{cliente}</b><br>"
            f"{vehiculo} · contrato "
            f"{cuota['contrato_numero']}<br>"
            f"Cuota {cuota['numero']}: "
            f"{formato_dinero(cuota['importe'])} "
            f"· vence "
            f"{cuota['fecha_vencimiento']}"
        )

        saldo = Decimal(str(cuota["saldo"]))

        # El campo no puede aceptar más que el saldo:
        #evita que se teclee de más. La validación de
        # verdad la hace la capa de datos, dentro de la
        # transacción y con la cuota bloqueada; esto
        # solo evita el error.

        self.campo_importe.setMaximum(float(saldo))

        # Y por defecto, el saldo completo.

        self.campo_importe.setValue(float(saldo))

        self.campo_importe.selectAll()

        self.pintar_estado()

        # ------------------------------
        # SI NO SE PUEDE COBRAR
        # ------------------------------

        motivos = self.motivos_bloqueo()

        if motivos:

            self.motivos = motivos

            self.boton_guardar.setEnabled(False)

            self.campo_importe.setEnabled(False)

            self.campo_fecha.setEnabled(False)

            self.etiqueta_estado.setText(
                "  ·  ".join(motivos)
            )

        else:

            self.motivos = []

    def obtener_cuota(self):

        try:

            return financiera.obtener_cuota(self.id_cuota)

        except PermisoDenegado:

            return None

    def motivos_bloqueo(self):
        """
        Por qué no se puede cobrar, o lista vacía.

        Se calcula antes de tocar nada, para no dejar
        el formulario lleno de campos que el usuario
        pueda escribir y que no van a servir para nada.
        """

        cuota = self.cuota

        motivos = []

        if cuota["estado"] == financiera.ESTADO_ANULADA:

            motivos.append(
                "La cuota está anulada y no admite pagos. "
                "Reactívela antes si procede."
            )

        if cuota["contrato_estado"] == "cancelado":

            motivos.append("El contrato está cancelado.")

        if Decimal(str(cuota["saldo"])) <= 0:

            motivos.append("La cuota ya está pagada.")

        return motivos

    def pintar_estado(self):

        cuota = self.cuota

        partes = [
            "Estado: "
            + financiera.ESTADOS.get(cuota["estado"], "?")
        ]

        if cuota["dias_atraso"] > 0:

            partes.append(
                f"Vencida hace {cuota['dias_atraso']} día(s)"
            )

        elif cuota["estado"] != financiera.ESTADO_PAGADA:

            dias = (
                cuota["fecha_vencimiento"] - date.today()
            ).days

            if dias > 0:

                partes.append(f"Vence en {dias} día(s)")

            elif dias == 0:

                partes.append("Vence hoy")

        if cuota["cantidad_pagos"] > 0:

            partes.append(
                f"{cuota['cantidad_pagos']} pago(s) anterior(es)"
            )

        partes.append(
            f"Saldo: {formato_dinero(cuota['saldo'])}"
        )

        self.etiqueta_estado.setText("  ·  ".join(partes))

    # =============================
    # GUARDAR
    # =============================

    def guardar(self):

        self.ocultar_error()

        if self.motivos:

            self.mostrar_error(" ".join(self.motivos))

            return

        importe = self.campo_importe.value()

        if importe <= 0:

            self.mostrar_error(
                "El importe tiene que ser mayor que cero."
            )

            return

        saldo = Decimal(str(self.cuota["saldo"]))

        if Decimal(str(importe)) > saldo:

            self.mostrar_error(
                "El importe es mayor que el saldo de la "
                f"cuota ({formato_dinero(saldo)})."
            )

            return

        self.recibo = (
            self.campo_recibo.text().strip()
            or financiera.siguiente_numero_recibo()
        )

        fecha = self.campo_fecha.date().toString("yyyy-MM-dd")

        concepto = self.campo_concepto.text().strip() or None

        try:

            id_pago, motivo = financiera.registrar_pago_cuota(
                id_cuota=self.id_cuota,
                importe=importe,
                fecha=fecha,
                forma=self.campo_forma.currentText(),
                recibo=self.recibo,
                concepto=concepto
            )

        except PermisoDenegado as error:

            self.mostrar_error(error.mensaje)

            return

        except Exception as error:

            registrar_error_inesperado(error)

            self.mostrar_error(
                "Ocurrió un problema al registrar el "
                "pago. No se guardó nada. El detalle "
                "está en registro_errores.log."
            )

            return

        if id_pago is None:

            self.mostrar_error(motivo)

            return

        self.accept()

    # =============================
    # ERROR
    # =============================

    def mostrar_error(self, mensaje):

        self.etiqueta_error.setText(mensaje)

        self.etiqueta_error.setVisible(True)

    def ocultar_error(self):

        self.etiqueta_error.setText("")

        self.etiqueta_error.setVisible(False)