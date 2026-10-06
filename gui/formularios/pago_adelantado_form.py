# ==========================================
# COBRO ADELANTADO
# ==========================================
# Registrar de una vez varias cuotas seguidas.
#
# Es la otra mitad de `PagoCuotaForm`: aquella cobra
# UNA cuota, esta cobra las que quepan en el importe.
#
#
# ----------------------------------------------------
# POR QUÉ UN FORMULARIO APARTE
# ----------------------------------------------------
# Un cobro adelantado tiene una consecuencia que el
# cliente tiene que ver ANTES de confirmar: a qué
# cuotas se va a imputar su dinero.
#
# "Le pongo 30.000" suena simple, pero significa "la
# cuota 3, la 4 y media de la 5". Y si se le descuenta
# la 3 entera y se le olvida la 5, le va a volver a
# aparecer como deuda dentro de dos meses y va a
# pensar que es un error nuestro.
#
# Por eso la vista previa no es un adorno: es la
# respuesta a "¿qué va a pasar?", y sale de la MISMA
# función que reparte, `repartir_adelanto()`. Si esta
# pantalla calculara el reparto por su cuenta, el
# cliente vería un reparto y le aplicarían otro.


from datetime import date
from decimal import Decimal

from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout
)

from database.contratos import obtener_contrato

import database.financiera as F

from database.pagos import FORMAS_PAGO

from errores import ErrorValidacion, PermisoDenegado

from utils.helpers import (
    ajustar_alto_tabla,
    celda,
    conectar_enter_guardar,
    configurar_campo_monetario,
    crear_boton_principal,
    crear_boton_secundario,
    crear_tabla,
)

from utils.moneda import (
    formato_dinero,
)

from utils.registro import registrar_error_inesperado


class PagoAdelantadoForm(QDialog):

    # ------------------------------
    # CUANTAS CUOTAS CABEN
    # ------------------------------
    # En la lista se enseñan todas, hasta este tope.
    #
    # El tope está porque un pago de cuarenta cuotas
    # no se revisa de un vistazo, y una tabla de
    # cuarenta filas dentro de un diálogo es una
    # barra de desplazamiento con la primera fila
    # tapada. Con doce se ve el patrón entero
    # (cuántas enteras y una parcial) y se avisa abajo
    # de cuántas son.

    CUOTAS_A_MOSTRAR = 12

    def __init__(self, parent=None, id_contrato=None):
        super().__init__(parent)

        self.id_contrato = id_contrato

        self.contrato = None
        self.cuotas = []

        self.plan = []
        self.sobrante = Decimal("0.00")

        self.recibos = []

        self.crear_interfaz()

        self.cargar()

    # =============================
    # INTERFAZ
    # =============================

    def crear_interfaz(self):

        self.setWindowTitle("Cobrar cuotas adelantadas")

        self.setModal(True)

        self.resize(600, 660)

        layout = QVBoxLayout()

        layout.setSpacing(12)

        self.setLayout(layout)

        # ------------------------------
        # DE QUIÉN
        # ------------------------------

        self.etiqueta_contrato = QLabel("")

        self.etiqueta_contrato.setObjectName("aviso")

        self.etiqueta_contrato.setWordWrap(True)

        layout.addWidget(self.etiqueta_contrato)

        # ------------------------------
        # EL DINERO
        # ------------------------------

        formulario = QFormLayout()

        formulario.setSpacing(10)

        self.campo_importe = QDoubleSpinBox()

        # Rango, decimales, separador y prefijo salen de
        # la moneda configurada. En guaranies el paso de
        # la flechita tiene que ser de 100.000: con un
        # salto de 100 habia que pulsarla cientos de
        # veces para llegar al siguiente millon.

        configurar_campo_monetario(
            self.campo_importe
        )

        formulario.addRow(
            "Importe recibido:", self.campo_importe
        )

        self.campo_fecha = QDateEdit()

        self.campo_fecha.setCalendarPopup(True)

        self.campo_fecha.setDisplayFormat("dd/MM/yyyy")

        self.campo_fecha.setDate(
            self.campo_fecha.date().fromString(
                date.today().isoformat(), "yyyy-MM-dd"
            )
        )

        formulario.addRow("Fecha del cobro:", self.campo_fecha)

        self.campo_forma = QComboBox()

        self.campo_forma.addItems(FORMAS_PAGO)

        formulario.addRow(
            "Forma de pago:", self.campo_forma
        )

        self.campo_recibo = QLineEdit()

        self.campo_recibo.setPlaceholderText(
            "Se genera uno para todo el cobro"
        )

        formulario.addRow("Recibo:", self.campo_recibo)

        self.campo_concepto = QLineEdit()

        self.campo_concepto.setPlaceholderText("Opcional")

        formulario.addRow("Concepto:", self.campo_concepto)

        layout.addLayout(formulario)

        # ------------------------------
        # LO QUE SE PONE EN CADA
        # CUOTA
        # ------------------------------
        # El botón de "cuota de más" suma una cuota
        # entera al importe. Es lo que hace el cajero
        # el 95 % de las veces ("paga dos meses"), y
        # tener que calcular 10.000 * 3 en la cabeza
        # para poner 30.000 es pedir la errata.

        fila = QHBoxLayout()

        fila.setSpacing(10)

        self.boton_mas_cuota = crear_boton_secundario(
            "+ Una cuota", self.sumar_una_cuota
        )

        fila.addWidget(self.boton_mas_cuota)

        self.boton_todo = crear_boton_secundario(
            "Todo lo pendiente", self.sumar_todo
        )

        fila.addWidget(self.boton_todo)

        fila.addStretch()

        layout.addLayout(fila)

        # ------------------------------
        # LA VISTA PREVIA
        # ------------------------------

        etiqueta_previa = QLabel(
            "Así se va a repartir:"
        )

        etiqueta_previa.setObjectName("etiqueta_filtro")

        layout.addWidget(etiqueta_previa)

        self.tabla = crear_tabla(
            ["Nº", "Vencimiento", "Importe", "Saldo"],
            anchos_fijos={1: 120, 2: 140}
        )

        cabecera = self.tabla.horizontalHeader()

        cabecera.setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )

        layout.addWidget(self.tabla)

        self.etiqueta_resumen = QLabel("")

        self.etiqueta_resumen.setObjectName("pie")

        self.etiqueta_resumen.setWordWrap(True)

        layout.addWidget(self.etiqueta_resumen)

        # ------------------------------
        # ERROR
        # ------------------------------

        self.etiqueta_error = QLabel("")

        self.etiqueta_error.setObjectName("aviso_error")

        self.etiqueta_error.setWordWrap(True)

        self.etiqueta_error.setVisible(False)

        layout.addWidget(self.etiqueta_error)

        # ------------------------------
        # BOTONES
        # ------------------------------

        botones = QHBoxLayout()

        botones.setSpacing(10)

        botones.addStretch()

        botones.addWidget(crear_boton_secundario(
            "Cancelar", self.reject
        ))

        self.boton_guardar = crear_boton_principal(
            "Registrar el cobro", self.guardar
        )

        botones.addWidget(self.boton_guardar)

        layout.addLayout(botones)

        # ------------------------------
        # REACCIONES
        # ------------------------------

        self.campo_importe.valueChanged.connect(
            self.repintar
        )

        conectar_enter_guardar(
            [self.campo_concepto, self.campo_recibo],
            self.guardar
        )

    # =============================
    # DATOS
    # =============================

    def cargar(self):

        self.contrato = self.leer_contrato()

        if not self.contrato:

            self.boton_guardar.setEnabled(False)

            self.mostrar_error(
                "No se pudo leer el contrato."
            )

            return

        self.cuotas = self.leer_cuotas()

        contrato = self.contrato

        vehiculo = " ".join(
            parte for parte in (
                contrato.get("marca"),
                contrato.get("modelo"),
                (
                    str(contrato["anio"])
                    if contrato.get("anio") else ""
                )
            )
            if parte
        )

        self.etiqueta_contrato.setText(
            f"<b>Contrato {contrato['numero']}</b> · "
            f"{contrato['cliente']}<br>"
            f"{vehiculo}  ·  "
            f"financiado "
            f"{formato_dinero(contrato['saldo_financiado'])}"
        )

        # ------------------------------
        # SIN CRONOGRAMA O SIN DEUDA
        # ------------------------------

        if not self.cuotas:

            self.boton_guardar.setEnabled(False)

            self.boton_mas_cuota.setEnabled(False)

            self.boton_todo.setEnabled(False)

            self.mostrar_error(
                "Este contrato no tiene cronograma. "
                "Générelo antes de cobrar."
            )

            return

        pendientes = [
            c for c in self.cuotas
            if Decimal(str(c["saldo"])) > 0
            and c["estado"] != F.ESTADO_ANULADA
        ]

        if not pendientes:

            self.boton_guardar.setEnabled(False)

            self.boton_mas_cuota.setEnabled(False)

            self.boton_todo.setEnabled(False)

            self.mostrar_error(
                "Este contrato no tiene cuotas pendientes."
            )

            return

        # ------------------------------
        # EL IMPORTE POR DEFECTO
        # ------------------------------
        # La primera cuota entera. Es lo más probable
        # y evita tener que escribir el número de una
        # cuota que el usuario acaba de ver.

        self.cuota_pendiente = pendientes[0]

        self.saldo_venta_pendiente = sum(
            (Decimal(str(c["saldo"])) for c in pendientes),
            Decimal("0.00")
        )

        self.campo_importe.setValue(
            float(self.cuota_pendiente["saldo"])
        )

    def leer_contrato(self):

        try:

            return obtener_contrato(self.id_contrato)

        except PermisoDenegado:

            return None

        except Exception:

            registrar_error_inesperado(
                Exception(
                    "No se pudo leer el contrato "
                    f"{self.id_contrato} para un cobro "
                    "adelantado."
                )
            )

            return None

    def leer_cuotas(self):

        try:

            return F.obtener_cuotas(self.id_contrato)

        except Exception:

            return []

    # =============================
    # LOS BOTONES DE SUMA
    # =============================

    def sumar_una_cuota(self):

        self.campo_importe.setValue(
            self.campo_importe.value()
            + float(self.cuota_pendiente["importe"])
        )

    def sumar_todo(self):

        self.campo_importe.setValue(
            float(self.saldo_venta_pendiente)
        )

    # =============================
    # LA VISTA PREVIA
    # =============================

    def repintar(self):

        self.ocultar_error()

        if not self.cuotas:

            return

        importe = Decimal(
            str(self.campo_importe.value())
        )

        if importe <= 0:

            self.tabla.setRowCount(0)

            self.etiqueta_resumen.setText(
                "Escribe el importe recibido."
            )

            return

        try:

            plan, sobrante = F.repartir_adelanto(
                self.cuotas, importe
            )

        except ErrorValidacion as error:

            self.tabla.setRowCount(0)

            self.etiqueta_resumen.setText(
                error.mensaje
            )

            return

        self.plan = plan

        self.sobrante = sobrante

        self.pintar_plan(plan, sobrante)

    def pintar_plan(self, plan, sobrante):

        mostradas = plan[:self.CUOTAS_A_MOSTRAR]

        self.tabla.setRowCount(len(mostradas))

        for indice, parte in enumerate(mostradas):

            valores = [
                str(parte["numero"]),
                str(parte["fecha_vencimiento"]),
                formato_dinero(parte["importe"]),
                formato_dinero(parte["saldo_despues"])
            ]

            # ------------------------------
            # LA ÚLTIMA VA MARCADA SI DEJA
            # RESTO
            # ------------------------------
            # Es la que no queda saldada. Sin
            # marcarlo, el cajero ve ocho filas
            # iguales y no se da cuenta de que a la
            # sexta solo le cubre la mitad.
            #
            # Se marca por ser la última DEL PLAN,
            # no la última de las mostradas: con la
            # tabla recortada no son lo mismo, y el
            # aviso se perdería justo en el caso
            # largo, que es donde más hace falta.

            resto = (
                parte is plan[-1]
                and parte["saldo_despues"] > 0
            )

            for columna, valor in enumerate(valores):

                self.tabla.setItem(
                    indice,
                    columna,
                    celda(
                        valor,
                        centrar=columna in {0, 2, 3},
                        objeto=(
                            "tono_aviso" if resto else None
                        )
                    )
                )

        ajustar_alto_tabla(self.tabla, maximo=240)

        enteras = sum(
            1 for p in plan
            if p["saldo_despues"] == 0
        )

        partes = []

        if enteras:

            partes.append(
                f"{enteras} cuota(s) quedan saldadas"
            )

        if plan and plan[-1]["saldo_despues"] > 0:

            partes.append(
                f"la {plan[-1]['numero']} se paga a medias"
            )

        if sobrante > 0:

            partes.append(
                "sobran "
                f"{formato_dinero(sobrante)} sin destino"
            )

        # ------------------------------
        # EL RESUMEN
        # ------------------------------
        # Se arma SIEMPRE desde cero y se pone una vez.
        #
        # Antes se concatenaba al texto anterior cuando
        # el plan era largo, y eso enseñaba el resumen
        # del importe ANTERIOR: un cobro de cuarenta
        # cuotas decía cuántas quedaban saldadas de
        # otra cifra que el cajero ya había cambiado.
        #
        # Y no es un recorte de la lista: el reparto
        # entero se guarda igual. Sale entero en la
        # confirmación, que es donde se lee.

        if len(plan) > self.CUOTAS_A_MOSTRAR:

            partes.append(
                f"solo se ven las "
                f"{self.CUOTAS_A_MOSTRAR} primeras "
                f"de {len(plan)}"
            )

        self.etiqueta_resumen.setText(
            "  ·  ".join(partes) if partes else
            "El importe no cubre ninguna cuota."
        )

        # ------------------------------
        # LO QUE SOBRA NO SE PUEDE
        # COBRAR
        # ------------------------------
        # Un cobro adelantado imputa a cuotas
        # COMPLETAS, de la más antigua a la más
        # reciente. Repartir de a poco dejaría un
        # residuo en la cuota 3 para siempre, y el
        # cliente "debería" la 3 mientras paga la 6.
        #
        # El sobrante se rechaza con su motivo en
        # guardar(), no aquí: el botón se apaga para
        # que se vea que no se puede, y el texto
        # explica por qué.

        self.boton_guardar.setEnabled(
            not sobrante and bool(plan)
        )

    # =============================
    # GUARDAR
    # =============================

    def guardar(self):

        self.ocultar_error()

        if not self.plan:

            self.mostrar_error(
                "No hay nada que imputar."
            )

            return

        if self.sobrante > 0:

            self.mostrar_error(
                f"El importe no cabe en las cuotas "
                f"pendientes: sobran "
                f"{formato_dinero(self.sobrante)}.\n\n"
                "Un cobro adelantado cubre cuotas "
                "completas. Si el cliente entrega de "
                "más, registre ese excedente aparte."
            )

            return

        if not self.confirmar():

            return

        recibo = self.campo_recibo.text().strip() or None

        concepto = (
            self.campo_concepto.text().strip() or None
        )

        try:

            partes, motivo = F.registrar_pago_adelantado(
                id_contrato=self.id_contrato,
                importe=self.campo_importe.value(),
                fecha=self.campo_fecha
                .date().toString("yyyy-MM-dd"),
                forma=self.campo_forma.currentText(),
                recibo=recibo,
                concepto=concepto
            )

        except PermisoDenegado as error:

            self.mostrar_error(error.mensaje)

            return

        except Exception as error:

            registrar_error_inesperado(error)

            self.mostrar_error(
                "Ocurrió un problema al registrar el "
                "cobro. No se guardó nada: o entra "
                "todo o no entra nada. El detalle está "
                "en registro_errores.log."
            )

            return

        if partes is None:

            self.mostrar_error(motivo)

            return

        self.recibos = [
            p["recibo"] for p in partes
        ]

        self.accept()

    def confirmar(self):
        """
        Se pregunta antes de cobrar.

        Nótese lo que dice: cuántas cuotas y cuáles. Es
        la última vez que el cajero puede ver el reparto
        antes de que el dinero se descuente, y después
        solo se puede deshacer anulando cada pago.
        """

        if len(self.plan) == 1:

            texto = (
                "Se imputará a la cuota "
                f"{self.plan[0]['numero']}."
            )

        else:

            numeros = ", ".join(
                str(p["numero"]) for p in self.plan
            )

            texto = (
                f"Se imputará a las cuotas {numeros}."
            )

        ultima = (
            self.plan[-1]["saldo_despues"] > 0
        )

        if ultima:

            texto += (
                f"\n\nLa cuota {self.plan[-1]['numero']} "
                "se paga a medias y le quedará un resto."
            )

        texto += (
            f"\n\nImporte: "
            f"{formato_dinero(self.campo_importe.value())}"
            f" · {self.campo_forma.currentText()}"
            f"\n\nSale un solo recibo para todo el "
            "cobro. Después solo se puede deshacer "
            "anulando los pagos uno a uno."
        )

        respuesta = QMessageBox.question(
            self,
            "Confirmar el cobro adelantado",
            texto + "\n\n¿Continuar?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        return respuesta == QMessageBox.Yes

    # =============================
    # ERROR
    # =============================

    def mostrar_error(self, mensaje):

        self.etiqueta_error.setText(mensaje)

        self.etiqueta_error.setVisible(True)

    def ocultar_error(self):

        self.etiqueta_error.setText("")

        self.etiqueta_error.setVisible(False)
