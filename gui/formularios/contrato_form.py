# ==========================================
# FORMULARIO DE CONTRATO
# ==========================================
# Se abre siempre a partir de una venta: el
# contrato hereda cliente, vehículo, precio y
# fecha de ella, así que aquí solo se rellena
# lo que la venta no sabe: cómo se paga, qué
# se financia y qué se anota.
#
# El contrato no se edita después. Si hay que
# corregirlo, se cancela y se vuelve a hacer
# desde la venta.
#
#
# ----------------------------------------------------
# LA VISTA PREVIA DEL CRONOGRAMA
# ----------------------------------------------------
# La parte que más trabajo cuesta de este
# formulario, y la razón de que exista.
#
# Un cronograma con 72 cuotas es un documento que
# el cliente firma sin ver. Firmar a ciegas 72
# vencimientos es pedir un problema en el mes seis,
# y no hay forma de arreglarlo después: un
# cronograma firmado no se puede cambiar, hay que
# anular los pagos y rehacerlo.
#
# Por eso aquí se ve el cronograma ANTES de
# firmar, con las fechas y los importes de verdad,
# calculados con la MISMA función que los va a
# guardar: calcular_cronograma(), que reparte el
# total y deja el residuo de redondeo en la última
# cuota para que la suma cuadre hasta el céntimo.
#
# Si esta vista previa calculara el reparto con
# otra fórmula, la última cuota del papel sería
# distinta de la que ve el cliente. Que se use la
# misma función no es una florituras: es lo único
# que hace que lo que se enseña sea lo que se
# firma.


import calendar

from datetime import date
from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QDate

from PySide6.QtWidgets import (
    QCheckBox,
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
    QPlainTextEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget
)

from errores import (
    ErrorSistema,
    ErrorValidacion
)

import database.financiera as financiera

from database.contratos import (
    crear_contrato,
    obtener_contrato,
    registrar_pdf,
    venta_para_contrato,
    FORMAS_PAGO,
    ESTADOS
)

from utils.validaciones import (
    es_precio,
    primer_error
)

from utils.helpers import (
    ajustar_alto_tabla,
    celda,
    crear_boton_principal,
    crear_boton_secundario,
    crear_tabla,
    conectar_enter_guardar,
    avisar_error
)

from utils.contrato_pdf import (
    generar_contrato,
    ruta_relativa
)

from utils.moneda import (
    formato_dinero,
    prefijo_moneda
)

# El símbolo de la moneda vive en utils.moneda. Aquí
# no se escribe ninguno: si lo hiciera, cambiar la
# moneda no tocaría este formulario.

from utils.registro import registrar_error_inesperado



class ContratoForm(QDialog):

    def __init__(self, parent=None, id_venta=None):
        super().__init__(parent)

        # Recibe el ID, no una fila.
        #
        # Antes recibía la fila, y se abría desde dos
        # sitios con dos formas distintas: desde
        # Contratos venía de ventas_sin_contrato() (5
        # columnas) y desde Ventas venía de
        # obtener_ventas() (6, porque trae el
        # vendedor). El formulario desempaquetaba 5 en
        # los dos casos, así que crear el contrato al
        # confirmar una venta —el flujo principal— moría
        # con "too many values to unpack".
        #
        # Que el formulario lea él lo que necesita quita
        # el problema de raíz: un constructor con una
        # sola entrada, que no puede adivinar cuántas
        # columnas le han pasado.

        self.id_venta = id_venta

        self.venta = venta_para_contrato(id_venta)

        self.id_guardado = None

        self.setObjectName("contrato_form")

        self.setWindowTitle("Crear contrato de compraventa")

        self.resize(620, 720)

        self.crear_interfaz()

    # =============================
    # INTERFAZ
    # =============================

    def pintar_no_disponible(self):
        """
        Cuando no hay ninguna venta asociada.
        Pasa cuando el id no existe, o cuando la
        venta ya tiene un contrato: se anuló la venta
        en otra pantalla mientras el formulario está
        abierto, o se creó el contrato desde otro sitio.

        Se explica en vez de reventar. Un
        `TypeError: cannot unpack` al abrir un
        formulario deja la aplicación sin ventana y sin
        decir nada, que es lo que pasaba antes.
        """

        self.precio = Decimal("0.00")

        layout = QVBoxLayout()

        self.setLayout(layout)

        etiqueta = QLabel(
            "No se puede crear el contrato.\n\n"
            "La venta indicada no existe o ya tiene un "
            "contrato. Si se creó desde otro sitio, "
            "cierra esto y vuelve a la lista de "
            "contratos."
        )

        etiqueta.setObjectName("aviso_error")

        etiqueta.setWordWrap(True)

        layout.addWidget(etiqueta)

        layout.addStretch()

        fila = QHBoxLayout()

        fila.addStretch()

        fila.addWidget(crear_boton_secundario(
            "Cerrar", self.reject
        ))

        layout.addLayout(fila)

    def crear_interfaz(self):

        if not self.venta:

            self.pintar_no_disponible()

            return

        (
            id_venta,
            fecha,
            cliente,
            vehiculo,
            precio
        ) = self.venta

        # ------------------------------
        # EL PRECIO, PARA LOS CÁLCULOS
        # ------------------------------
        # Se guarda como Decimal y no como float: el
        # saldo a financiar es una resta sobre él, y
        # "25000.0 - 40000.0" en coma flotante y
        # Decimal(str(...)) dan cosas distintas a
        # partir del decimal quince.

        self.precio = Decimal(str(precio))

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
        # DOS PESTAÑAS
        # ------------------------------
        # "Pago" y "Financiación" en vez de un
        # formulario largo, porque no siempre hay
        # financiación: en una venta de contado, la
        # pestaña entera está vacía y estorba.

        self.pestanas = QTabWidget()

        self.pestanas.addTab(
            self.crear_panel_pago(), "Condiciones de pago"
        )

        self.pestanas.addTab(
            self.crear_panel_financiacion(),
            "Financiación y cronograma"
        )

        self.pestanas.addTab(
            self.crear_panel_anotaciones(),
            "Cláusulas y notas"
        )

        layout_principal.addWidget(self.pestanas)

        # ------------------------------
        # CÁLCULO EN VIVO
        # ------------------------------
        # Fuera de las pestañas, siempre visible:
        # es la respuesta a "¿cuánto y cuándo?" y no
        # puede estar escondida detrás de una
        # pestaña que el usuario no ha abierto.

        self.etiqueta_resumen = QLabel("")

        self.etiqueta_resumen.setObjectName("aviso")

        self.etiqueta_resumen.setWordWrap(True)

        layout_principal.addWidget(
            self.etiqueta_resumen
        )

        # ------------------------------
        # ERROR
        # ------------------------------

        self.etiqueta_error = QLabel("")

        self.etiqueta_error.setObjectName("aviso_error")

        self.etiqueta_error.setWordWrap(True)

        self.etiqueta_error.setVisible(False)

        layout_principal.addWidget(
            self.etiqueta_error
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

        botones.addStretch()

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

        self.conectar_reacciones()

        # ------------------------------
        # EL ESTADO INICIAL DE LOS CAMPOS
        # ------------------------------
        # La forma de pago arranca siendo la
        # PRIMERA de la lista, que es "Contado". Sin
        # esta llamada, los campos de anticipo y
        # cuotas se quedan habilitados en un contrato
        # de contado, que es un formulario que se
        # contradice a sí mismo: acepta un anticipo
        # que luego la capa de datos rechaza.
        #
        # Y no llega con la señal: poner "Contado" en
        # un combo que ya estaba en "Contado" NO
        # emite currentTextChanged, que solo salta
        # cuando el texto cambia de verdad. Por eso
        # hay que llamar al método, y no confiar en
        # que la conexión se encargue.

        self.al_cambiar_forma_pago()

        self.pestanas.setCurrentIndex(0)

        self.campo_anticipo.setFocus()

        self.campo_anticipo.selectAll()

    # ------------------------------
    # PANELES
    # ------------------------------

    def crear_panel_pago(self):

        panel = QWidget()

        layout = QVBoxLayout(panel)

        layout.setSpacing(12)

        formulario = QFormLayout()

        formulario.setSpacing(10)

        self.campo_forma_pago = QComboBox()

        self.campo_forma_pago.addItems(FORMAS_PAGO)

        formulario.addRow(
            "Forma de pago:", self.campo_forma_pago
        )

        self.campo_anticipo = QLineEdit("0")

        self.campo_anticipo.setPlaceholderText(
            f"Ej: {formato_dinero(self.precio / 2)}"
        )

        formulario.addRow(
            "Entrega inicial:", self.campo_anticipo
        )

        self.campo_cuotas = QSpinBox()

        ajustes = financiera.leer_ajustes()

        self.campo_cuotas.setRange(0, ajustes["maximo_cuotas"])

        self.campo_cuotas.setValue(12)

        self.campo_cuotas.setSpecialValueText("Sin cuotas")

        formulario.addRow(
            "Cantidad de cuotas:", self.campo_cuotas
        )

        layout.addLayout(formulario)

        # ------------------------------
        # EL SALDO, QUE SE CALCULA SOLO
        # ------------------------------
        # Se muestra y no se escribe: es la resta, y
        # pedirla a mano es pedir un error de
        # tecleo en la cifra que más importa.
        #
        # Salvo que se marque "otro saldo", que es el
        # caso real: una financiera financia el precio
        # de lista y el cliente pone la diferencia.

        self.campo_saldo_fijo = QCheckBox(
            "El saldo financiado es otro importe"
        )

        layout.addWidget(self.campo_saldo_fijo)

        self.campo_saldo = QLineEdit()

        self.campo_saldo.setPlaceholderText(
            "Saldo a financiar"
        )

        self.campo_saldo.setVisible(False)

        formulario_saldo = QFormLayout()

        formulario_saldo.setSpacing(10)

        formulario_saldo.addRow(
            "Saldo financiado:", self.campo_saldo
        )

        self.marco_saldo = QWidget()

        self.marco_saldo.setLayout(formulario_saldo)

        self.marco_saldo.setVisible(False)

        layout.addWidget(self.marco_saldo)

        layout.addStretch()

        return panel

    def crear_panel_financiacion(self):

        panel = QWidget()

        layout = QVBoxLayout(panel)

        layout.setSpacing(12)

        formulario = QFormLayout()

        formulario.setSpacing(10)

        # ------------------------------
        # CÓMO VENCEN
        # ------------------------------

        self.campo_periodicidad = QComboBox()

        for clave in (
            financiera.TODAS_LAS_PERIODICIDADES
        ):

            self.campo_periodicidad.addItem(
                clave.capitalize(), clave
            )

        # ------------------------------
        # MENSUAL POR DEFECTO
        # ------------------------------
        # No se deja el primero de la lista, que es
        # "semanal": TODAS_LAS_PERIODICIDADES empieza
        # por ahí, así que un combo recién creado
        # queda en semanal y un crédito de 12 cuotas
        # se repartiría en doce semanas.
        #
        # Se busca por DATO y no por texto, porque
        # "Mensual" con mayúscula no es lo que guarda
        # calcular_cronograma().

        indice = self.campo_periodicidad.findData(
            financiera.PERIODICIDAD_POR_DEFECTO
        )

        if indice >= 0:

            self.campo_periodicidad.setCurrentIndex(indice)

        formulario.addRow(
            "Periodicidad:", self.campo_periodicidad
        )

        self.campo_primer_vencimiento = QDateEdit()

        self.campo_primer_vencimiento.setCalendarPopup(True)

        self.campo_primer_vencimiento.setDisplayFormat(
            "dd/MM/yyyy"
        )

        # ------------------------------
        # EL VENCIMIENTO POR DEFECTO
        # ------------------------------
        # Un mes después de HOY, no de la fecha de la
        # venta. La venta puede llevar semanas cerrada
        # y un cliente que firma en octubre no puede
        # empezar a pagar en marzo.

        self.poner_vencimiento_por_defecto()

        formulario.addRow(
            "Primer vencimiento:",
            self.campo_primer_vencimiento
        )

        # ------------------------------
        # LAS CONDICIONES ECONÓMICAS
        # ------------------------------

        self.campo_tasa = QDoubleSpinBox()

        self.campo_tasa.setRange(0, 999)

        self.campo_tasa.setDecimals(2)

        self.campo_tasa.setSuffix(" %")

        self.campo_tasa.setValue(0)

        self.campo_tasa.setGroupSeparatorShown(False)

        formulario.addRow(
            "Interés anual:", self.campo_tasa
        )

        self.campo_gastos = QDoubleSpinBox()

        self.campo_gastos.setRange(0, 999999999)

        self.campo_gastos.setDecimals(2)

        self.campo_gastos.setGroupSeparatorShown(False)

        self.campo_gastos.setPrefix(prefijo_moneda())

        formulario.addRow(
            "Gastos de administración:", self.campo_gastos
        )

        self.campo_retencion = QDoubleSpinBox()

        self.campo_retencion.setRange(0, 100)

        self.campo_retencion.setDecimals(3)

        self.campo_retencion.setSuffix(" %")

        self.campo_retencion.setGroupSeparatorShown(False)

        formulario.addRow(
            "Retención:", self.campo_retencion
        )

        # ------------------------------
        # LO QUE NO SE CALCULA AQUÍ
        # ------------------------------
        # Aviso fijo, siempre visible, porque la
        # retención y la mora dependen de lo que
        # corresponda legalmente y NO están
        # validadas. Está aquí para que nadie las
        # rellene creyendo que el programa sabe lo que
        # hace con ellas.

        aviso_fiscal = QLabel(
            "La retención y la mora se GUARDAN como "
            "dato pactado. La aplicación no calcula "
            "ninguna de las dos ni aplica ninguna "
            "obligación fiscal.\n\n"
            "Revise con un asesor fiscal cuál es el "
            "porcentaje y la base de cálculo antes de "
            "firmar un contrato financiado."
        )

        aviso_fiscal.setObjectName("aviso")

        aviso_fiscal.setWordWrap(True)

        layout.addLayout(formulario)

        layout.addWidget(aviso_fiscal)

        # ------------------------------
        # LA VISTA PREVIA
        # ------------------------------

        etiqueta_previa = QLabel(
            "Así va a quedar el cronograma:"
        )

        etiqueta_previa.setObjectName("etiqueta_filtro")

        layout.addWidget(etiqueta_previa)

        self.tabla_previa = crear_tabla(
            ["Nº", "Vencimiento", "Importe"],
            columna_acciones=-1,
            anchos_fijos={1: 130, 2: 150}
        )

        cabecera = self.tabla_previa.horizontalHeader()

        cabecera.setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )

        layout.addWidget(self.tabla_previa)

        self.etiqueta_previa = QLabel("")

        self.etiqueta_previa.setObjectName("pie")

        self.etiqueta_previa.setWordWrap(True)

        layout.addWidget(self.etiqueta_previa)

        return panel

    def crear_panel_anotaciones(self):

        panel = QWidget()

        layout = QVBoxLayout(panel)

        layout.setSpacing(12)

        etiqueta_clausulas = QLabel(
            "Cláusulas pactadas:"
        )

        etiqueta_clausulas.setObjectName("etiqueta_filtro")

        layout.addWidget(etiqueta_clausulas)

        self.campo_clausulas = QPlainTextEdit()

        self.campo_clausulas.setPlaceholderText(
            "Lo que pactan las dos partes y vaya a "
            "salir en el contrato firmado.\n\n"
            "La redacción de estas cláusulas depende "
            "de lo que firme cada parte. Este campo "
            "guarda el texto; no lo redacta ni lo "
            "revisa nadie."
        )

        self.campo_clausulas.setMinimumHeight(120)

        layout.addWidget(self.campo_clausulas)

        etiqueta_observaciones = QLabel("Observaciones:")

        etiqueta_observaciones.setObjectName(
            "etiqueta_filtro"
        )

        layout.addWidget(etiqueta_observaciones)

        self.campo_observaciones = QPlainTextEdit()

        self.campo_observaciones.setPlaceholderText(
            "Ej: el vehículo se entrega con "
            "documentación al día y service "
            "del último año."
        )

        self.campo_observaciones.setFixedHeight(90)

        layout.addWidget(self.campo_observaciones)

        layout.addStretch()

        return panel

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
    # REACCIONES
    # =============================

    def conectar_reacciones(self):

        self.campo_forma_pago.currentTextChanged.connect(
            self.al_cambiar_forma_pago
        )

        self.campo_anticipo.textChanged.connect(
            self.actualizar_todo
        )

        self.campo_cuotas.valueChanged.connect(
            self.actualizar_todo
        )

        self.campo_saldo_fijo.toggled.connect(
            self.al_marcar_saldo_fijo
        )

        self.campo_saldo.textChanged.connect(
            self.actualizar_todo
        )

        self.campo_periodicidad.currentIndexChanged.connect(
            self.actualizar_todo
        )

        self.campo_primer_vencimiento.dateChanged.connect(
            self.actualizar_todo
        )

        self.campo_gastos.valueChanged.connect(
            self.actualizar_todo
        )

        self.campo_tasa.valueChanged.connect(
            self.actualizar_todo
        )

        # Return guarda, pero no desde el combo:
        # ahí abre y cierra la lista desplegable.

        conectar_enter_guardar(
            [self.campo_anticipo, self.campo_saldo],
            self.guardar
        )

    def al_cambiar_forma_pago(self, _texto=None):
        """
        "Contado" no admite anticipo ni cuotas.

        Los campos se DESACTIVAN en vez de vaciarse: si
        se vaciaran, al volver a "Anticipo + cuotas"
        habría que reescribirlos, y un usuario que
        prueba las dos formas perdería lo que tenía
        escrito.
        """

        contado = (
            self.campo_forma_pago.currentText() == "Contado"
        )

        self.campo_anticipo.setEnabled(not contado)

        self.campo_cuotas.setEnabled(not contado)

        self.campo_saldo_fijo.setEnabled(not contado)

        self.al_marcar_saldo_fijo(self.campo_saldo_fijo.isChecked())

        self.actualizar_todo()

    def al_marcar_saldo_fijo(self, marcado):
        """
        El campo de saldo propio, o la resta.
        """

        puede = (
            marcado
            and self.campo_forma_pago.currentText()
            != "Contado"
        )

        self.campo_saldo.setVisible(puede)

        self.marco_saldo.setVisible(puede)

        self.actualizar_todo()

    def actualizar_todo(self):

        self.actualizar_resumen()

        self.actualizar_previa()

    # =============================
    # CÁLCULO
    # =============================

    def leer_anticipo(self):
        """
        El anticipo como Decimal, o None si el campo
        está vacío o no se puede leer.

        None y no 0: cero es un anticipo LEGÍTIMO
        (un crédito sin entrega inicial), y un campo
        vacío o mal escrito no es lo mismo. Con 0
        como valor de error, un campo con "abc"
        parecía un crédito sin anticipo.
        """

        texto = self.campo_anticipo.text().strip()

        if not texto:

            return None

        return self.leer_importe(texto)

    def leer_importe(self, texto):
        """
        Un importe escrito a Decimal, o None.

        Admite el separador de miles de la
        configuración porque el usuario pega
        números de otros programas: si está pegando
        un importe, viene con separador.
        """

        limpio = texto.strip().replace(" ", "")

        if not limpio:

            return None

        try:

            return Decimal(limpio.replace(",", ""))

        except (InvalidOperation, ValueError):

            return None

    def poner_vencimiento_por_defecto(self):
        """
        El primer vencimiento, un mes después de hoy.

        Del DÍA de hoy y no del de la venta: una venta
        puede llevar semanas cerrada y un cliente que
        firma en octubre no puede empezar a pagar en
        marzo.

        Y con el día recortado cuando el mes destino es
        más corto. Poner el 31 y que caiga en el 28 de
        febrero no es un error del usuario: es el único
        día posible, y obligarle a corregirlo a mano
        para un crédito que no va a ser problema.
        El recorte se hace una sola vez aquí; el
        cronograma, al avanzar, usa su propio día de
        referencia.

        Si HOY es día 31, el mes destino se elige el
        siguiente: "31 de marzo" es más cercano a un
        mes por delante que "28 de febrero", que son 28
        días.
        """

        hoy = date.today()

        mes = hoy.month + 1
        anio = hoy.year

        if mes > 12:

            mes = 1
            anio += 1

        ultimo = calendar.monthrange(anio, mes)[1]

        self.campo_primer_vencimiento.setDate(
            QDate(anio, mes, min(hoy.day, ultimo))
        )

    def leer_primer_vencimiento(self):
        """
        La fecha del QDateEdit como datetime.date.

        QDateEdit.date() devuelve un QDate, y calcular_
        cronograma() espera una fecha de Python.
        QDate.toPython() hace la conversión; hacerlo a
        mano con .year(), .month() y .day() funciona,
        pero es código que se puede equivocar sin que
        nada lo note.
        """

        return self.campo_primer_vencimiento.date().toPython()

    def saldo_es_fijo(self):
        """
        Si el usuario ha puesto su propio saldo.

        Se decide por la casilla, NO por si el campo
        se ve. isVisible() es False mientras el
        diálogo no se ha mostrado, así que un formulario
        recién creado tenía el campo "oculto" y el saldo
        que se usaba era la resta, no el que el usuario
        acababa de escribir.
        Y el caso real: una venta de contado tampoco
        tiene saldo propio, y allí la casilla está
        desactivada.
        """

        if self.campo_forma_pago.currentText() == "Contado":

            return False

        return self.campo_saldo_fijo.isChecked()

    def saldo_a_financiar(self):
        """
        Lo que se financia, o None si los números de
        arriba no cuadran.

        None en vez de 0 para no tener que distinguir
        "no hay nada que financiar" de "no se puede
        saber todavía": la primera es una respuesta y
        la segunda es una espera.
        """

        forma = self.campo_forma_pago.currentText()

        if forma == "Contado":

            return Decimal("0.00")

        if self.saldo_es_fijo():

            return self.leer_importe(
                self.campo_saldo.text()
            )

        anticipo = self.leer_anticipo()

        if anticipo is None:

            return None

        if anticipo > self.precio:

            return None

        saldo = (
            self.precio - anticipo
            - Decimal(str(self.campo_gastos.value()))
        )

        return saldo if saldo > 0 else Decimal("0.00")

    def actualizar_resumen(self):

        saldo = self.saldo_a_financiar()

        if saldo is None:

            self.etiqueta_resumen.setText(
                "El anticipo tiene que ser un número, y "
                "no puede pasar del precio de venta."
            )

            return

        if saldo == 0:

            self.etiqueta_resumen.setText(
                "Pago completo: no queda nada por "
                "financiar."
            )

            return

        cuotas = self.campo_cuotas.value()

        if cuotas < 1:

            self.etiqueta_resumen.setText(
                "Total a financiar: "
                f"{formato_dinero(saldo)}"
            )

            return

        partes = [
            f"Total a financiar: {formato_dinero(saldo)}"
        ]

        if self.campo_gastos.value():

            partes.append(
                "gastos de administración: "
                f"{formato_dinero(self.campo_gastos.value())}"
            )

        if self.campo_tasa.value():

            partes.append(
                f"interés anual: "
                f"{self.campo_tasa.value():.2f} %"
            )

        partes.append(
            f"premio total estimado: "
            f"{formato_dinero(self.interes_estimado(saldo, cuotas))}"
        )

        self.etiqueta_resumen.setText(
            "  ·  ".join(partes)
        )

    def interes_estimado(self, saldo, cuotas):
        """
        Cuánto se paga de más por el interés.

        Es una ESTIMACIÓN con interés simple sobre el
        saldo original, y va marcada como tal.

        No es un cálculo financiero: el interés real
        de un crédito se paga sobre el saldo que
        queda, que baja en cada cuota. Aquí se calcula
        sobre el saldo entero durante todo el plazo, y
        sale más alto que la realidad.
        #
        #
        # Es una estimación sobre el saldo original, con
        # interés simple y sin mora ni gastos de
        # cobranza: la cuota real sale distinta. Por eso
        # la etiqueta dice "estimado" y no "total a pagar".
        # El cronograma de abajo SÍ es exacto, porque
        # reparte el saldo pactado y nada más: el interés
        # va dentro del saldo financiado que se firma, no
        # se calcula en cada cuota.
        """

        tasa = float(self.campo_tasa.value())

        if tasa <= 0:

            return Decimal("0.00")

        años = float(cuotas) / 12.0

        return (
            Decimal(str(saldo))
            * Decimal(str(tasa))
            * Decimal(str(años))
            / Decimal("100")
        )

    # ------------------------------
    # LA VISTA PREVIA
    # ------------------------------

    def actualizar_previa(self):
        """
        El cronograma que se va a firmar.

        Sale de calcular_cronograma(), la MISMA
        función que usará generar_cronograma(): si
        aquí se repartiera de otra manera, la última
        cuota del papel sería distinta de la que ve
        el cliente.
        """

        saldo = self.saldo_a_financiar()

        cuotas = self.campo_cuotas.value()

        if saldo is None or cuotas < 1 or saldo <= 0:

            self.tabla_previa.setRowCount(0)

            self.etiqueta_previa.setText(
                "No hay nada que repartir todavía."
            )

            return

        try:

            cronograma = financiera.calcular_cronograma(
                cuotas,
                self.campo_periodicidad.currentData(),
                self.leer_primer_vencimiento(),
                saldo
            )

        except ErrorValidacion as error:

            self.tabla_previa.setRowCount(0)

            self.etiqueta_previa.setText(
                error.mensaje
            )

            return

        self.pintar_previa(cronograma)

    def pintar_previa(self, cronograma):

        self.tabla_previa.setRowCount(len(cronograma))

        for indice, cuota in enumerate(cronograma):

            valores = [
                f"{cuota['numero']}",
                str(cuota['fecha_vencimiento']),
                formato_dinero(cuota['importe'])
            ]

            # ------------------------------
            # LA ÚLTIMA VA MARCADA
            # ------------------------------
            # Es la que se lleva el residuo del
            # redondeo, y por eso no es igual que
            # las demás. Sin marcarlo, un cliente que
            # compara ve que la última no cuadra y
            # piensa que hay un error.

            ultima = indice == len(cronograma) - 1

            for columna, valor in enumerate(valores):

                self.tabla_previa.setItem(
                    indice,
                    columna,
                    celda(
                        valor,
                        centrar=columna == 2,
                        objeto=(
                            "tono_aviso" if ultima else None
                        )
                    )
                )

        ajustar_alto_tabla(self.tabla_previa, maximo=300)

        total = sum(
            (Decimal(str(c["importe"])) for c in cronograma),
            Decimal("0.00")
        )

        cuota = cronograma[0]["importe"]

        ultima = cronograma[-1]["importe"]

        self.etiqueta_previa.setText(
            f"{len(cronograma)} cuotas de "
            f"{formato_dinero(cuota)}, "
            f"la última de {formato_dinero(ultima)} "
            "(se lleva el residuo para que la suma "
            f"cuadre). Total: {formato_dinero(total)}."
        )

    # =============================
    # GUARDAR
    # =============================

    def guardar(self):

        self.ocultar_error()

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

        error = self.validar()

        if error:

            self.mostrar_error(error)

            return

        anticipo = self.leer_anticipo()

        if anticipo is None:

            anticipo = Decimal("0.00")

        observaciones = (
            self.campo_observaciones.toPlainText().strip()
        )

        clausulas = (
            self.campo_clausulas.toPlainText().strip()
        )

        saldo = None

        if self.saldo_es_fijo():

            saldo = self.leer_importe(
                self.campo_saldo.text()
            )

        primer_vencimiento = None

        if cuotas > 0:

            primer_vencimiento = (
                self.leer_primer_vencimiento()
            )

        # ------------------------------
        # GUARDAR
        # ------------------------------

        try:

            id_contrato, motivo = crear_contrato(
                venta_id=id_venta,
                forma_pago=forma_pago,
                anticipo=float(anticipo),
                cantidad_cuotas=cuotas,
                observaciones=observaciones or None,
                saldo_financiado=(
                    float(saldo) if saldo is not None
                    else None
                ),
                tasa_interes=float(self.campo_tasa.value()),
                periodicidad=(
                    self.campo_periodicidad.currentData()
                ),
                primer_vencimiento=primer_vencimiento,
                gastos_administrativos=float(
                    self.campo_gastos.value()
                ),
                retencion=float(self.campo_retencion.value()),
                clausulas=clausulas or None
            )

        except ErrorSistema as error:

            avisar_error(self, error)

            return

        except Exception as error:

            registrar_error_inesperado(error)

            self.mostrar_error(
                "Ocurrió un problema al crear el "
                "contrato. No se guardó nada. El "
                "detalle está en registro_errores.log."
            )

            return

        if id_contrato is None:

            self.mostrar_error(motivo)

            return

        self.id_guardado = id_contrato

        # ------------------------------
        # EL CRONOGRAMA
        # ------------------------------
        # Se genera AQUÍ, con el contrato recién
        # firmado, y no desde el detalle.
        #
        # La razón es práctica y no de gusto: un
        # contrato financiado sin cronograma es un
        # contrato a medias, y quien lo acaba de
        # firmar está delante del cliente. Si se deja
        # para luego, se queda así.
        #
        # generar_cronograma() lleva CREAR_CONTRATOS,
        # que es el permiso con el que se ha llegado
        # aquí, así que no hay una segunda decisión
        # que tomar.

        if cuotas > 0:

            generadas, motivo = (
                financiera.generar_cronograma(id_contrato)
            )

            if generadas == 0:

                # ------------------------------
                # EL CONTRATO YA ESTÁ
                # ------------------------------
                # El contrato se guardó y las cuotas
                # no. Se avisa y NO se deshace: el
                # documento firmado existe y se puede
                # generar el cronograma desde el
                # detalle. Borrarlo dejaría al cliente
                # sin contrato, que es peor.

                QMessageBox.warning(
                    self,
                    "Contrato creado, cronograma no",
                    "El contrato se guardó, pero las "
                    f"cuotas no:\n\n{motivo}\n\n"
                    "Puede generar el cronograma desde "
                    "el detalle del contrato."
                )

                self.accept()

                return

        # ------------------------------
        # PDF
        # ------------------------------
        # Se genera aquí y no en el listado: el
        # flujo pedido es guardar y a continuación
        # obtener el documento, y así el archivo
        # existe nada más confirmar.

        self.generar_pdf(id_contrato, generadas)

    def validar(self):
        """
        Lo que no se puede firmar, o None.

        Devuelve el primer error encontrado, en el
        orden en que el usuario lo vería: si hay tres
        cosas malas, se avisa de la primera y se deja
        corregir. Avisar de las tres en un mensaje
        largo es más difícil de usar que arreglar una
        cosa, recargar y ver la siguiente.
        """

        forma_pago = self.campo_forma_pago.currentText()

        anticipo_texto = self.campo_anticipo.text().strip()

        error = primer_error([
            es_precio(anticipo_texto, "La entrega inicial")
        ])

        if error:

            return error

        if (
            float(anticipo_texto or 0)
            > float(self.precio)
        ):

            return (
                "La entrega inicial no puede ser mayor "
                "que el precio de venta."
            )

        if (
            forma_pago == "Contado"
            and float(anticipo_texto or 0) > 0
        ):

            return (
                "En contado no hay entrega inicial ni "
                "cuotas: el pago es completo."
            )

        # ------------------------------
        # EL SALDO FIJO
        # ------------------------------

        if self.saldo_es_fijo():

            propio = self.leer_importe(
                self.campo_saldo.text()
            )

            if propio is None:

                return (
                    "El saldo financiado tiene que ser "
                    "un número."
                )

            if propio < 0:

                return (
                    "El saldo financiado no puede ser "
                    "negativo."
                )

            if propio == 0 and (
                self.campo_cuotas.value() > 0
            ):

                return (
                    "No hay nada que financiar: el saldo "
                    "es cero y no se pueden generar "
                    "cuotas."
                )

            if propio > 0 and (
                self.campo_cuotas.value() < 1
            ):

                return (
                    "Si queda saldo por financiar, hay "
                    "que decir en cuántas cuotas se paga."
                )

            return None

        # ------------------------------
        # LAS CUOTAS
        # ------------------------------

        if self.campo_cuotas.value() < 1:

            return None

        saldo = self.saldo_a_financiar()

        if saldo is None:

            return (
                "Los números no cuadran: revise la "
                "entrega inicial y los gastos de "
                "administración."
            )

        if saldo <= 0:

            return (
                "No queda nada por financiar: la "
                "entrega inicial y los gastos ya "
                "cubren el precio. Ponga cero cuotas "
                "o baje la entrega inicial."
            )

        return None

    # ------------------------------
    # PDF
    # ------------------------------

    def generar_pdf(self, id_contrato, generadas=0):
        """
        Crea el PDF nada más guardar el contrato.
        """

        try:

            contrato = obtener_contrato(id_contrato)

        except ErrorSistema as error:

            avisar_error(self, error)

            self.accept()

            return

        if not contrato:

            self.accept()

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

        # ------------------------------
        # EL PDF CON LAS CUOTAS
        # ------------------------------
        # generar_contrato() se llama DESPUÉS de
        # generar_cronograma(): el PDF imprime el
        # cronograma y necesita leer las cuotas. Al revés
        # saldría un contrato con las condiciones y sin
        # la tabla de vencimientos, que es media
        # información para el cliente.

        # Anotar dónde quedó el archivo es
        # informativo: si falla, el contrato ya
        # está guardado y el PDF existe, así que
        # no se pierde nada por avisar.

        try:

            registrar_pdf(
                id_contrato,
                ruta_relativa(contrato["numero"])
            )

        except ErrorSistema:

            pass

        mensaje = (
            f"El contrato {contrato['numero']} se guardó "
            "correctamente.\n\n"
            "El PDF se generó en:\n"
            f"{ruta}"
        )

        if generadas:

            mensaje += (
                f"\n\nSe generaron {generadas} cuotas con "
                "el cronograma que vio antes de firmar."
            )

        QMessageBox.information(
            self,
            "Contrato creado",
            mensaje + "\n\nDesde el módulo Contratos "
            "puede abrir el detalle, cobrar las cuotas "
            "y abrirlo de nuevo cuando lo necesite."
        )

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
