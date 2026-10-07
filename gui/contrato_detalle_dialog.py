# ==========================================
# DETALLE DE UN CONTRATO
# ==========================================
# Todo lo que hay que saber de un contrato en un
# diálogo: qué se vendió, qué se financia, cuál es el
# cronograma, qué se ha cobrado, qué respalda la
# deuda y qué se ha cambiado por el camino.
#
# Está en pestañas y no en un scroll largo porque las
# cosas que se miran son de naturalezas distintas: el
# cronograma se LEE de arriba abajo, el historial se
# recorre buscando una fecha, y las garantías son una
# lista corta. Encajadas en un scroll habría que
# pasar por unas para ver las otras, y quien viene a
# ver "cuánto se ha pagado" acaba buscando en las
# cuotas.
#
# Los datos del contrato van FIJOS arriba, no en una
# pestaña: son el contexto de todo lo de abajo, y
# tenerlos siempre delante evita la sensación de que
# cada pestaña es una pantalla distinta.
#
#
# ----------------------------------------------------
# LO QUE ESTA PANTALLA NO ES
# ----------------------------------------------------
# El historial se MUESTRA. No se permite corregir ni
# borrar nada desde aquí: los pagos se anulan (que no
# es borrarlos), las cuotas se anulan y se reactivan,
# y las garantías cambian de estado. Todo con su
# motivo y con su rastro. Una pantalla donde se pudiera
# retocar un contrato firmado no sería una pantalla de
# detalle, sería un segundo formulario con permiso de
# escritura.


from datetime import date
from decimal import Decimal

from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHeaderView
)

from database.auditoria import historial_contrato

from database.contratos import (
    ESTADOS as ESTADOS_CONTRATO,
    obtener_contrato
)

from database.pagos import obtener_pagos_detalle

import database.financiera as financiera

import database.garantias as garantias

from permisos import (
    tiene_permiso,
    GESTIONAR_CONTRATOS,
    GESTIONAR_FINANCIERA,
    VER_AUDITORIA
)

from utils.helpers import (
    ancho_acciones_para,
    ajustar_alto_tabla,
    celda,
    crear_botones_accion,
    crear_boton_principal,
    crear_boton_secundario,
    crear_tabla,
    crear_titulo
)

from utils.moneda import formato_dinero

from utils.contrato_pdf import generar_contrato

from utils.recibo_pdf import generar_recibo

from utils.registro import registrar_error_inesperado

from gui.formularios.garantia_form import (
    FormularioInscripcion,
    GarantiaForm
)

from gui.formularios.pago_adelantado_form import (
    PagoAdelantadoForm
)

from gui.formularios.pago_cuota_form import PagoCuotaForm


# ==========================================
# TONOS POR ESTADO DE CUOTA
# ==========================================
# Los nombres de TONOS_CELDA. Un estado "anulada" no
# lleva tono: no es un problema, es una decisión, y
# marcarla en rojo la haría parecer una deuda viva.

TONO = {
    financiera.ESTADO_PAGADA: "tono_ok",
    financiera.ESTADO_PARCIAL: "tono_aviso",
    financiera.ESTADO_VENCIDA: "tono_peligro",
    financiera.ESTADO_PENDIENTE: None,
    financiera.ESTADO_ANULADA: None
}

# El mismo estado, pintado en la fila entera. La
# tabla de pagos usa un tono para los anulados, que
# sí son un caso a destacar: un cobro que se anuló
# está mal, y no debe pasar por un cobro más.

TONO_ANULADO = "tono_peligro"

COLUMNA_ACCIONES_CUOTAS = 7
COLUMNA_ACCIONES_PAGOS = 7
COLUMNA_ACCIONES_GARANTIAS = 6

ANCHO_COBRAR = 80
ANCHO_ANULAR = 86
ANCHO_ANULAR_CUOTA = 86
ANCHO_REACTIVAR = 94
ANCHO_GARANTIA = 100

ANCHO_ACCIONES_CUOTAS = ancho_acciones_para([
    ANCHO_COBRAR,
    ANCHO_ANULAR,
    ANCHO_REACTIVAR
])

ANCHO_ACCIONES_PAGOS = ancho_acciones_para([
    ANCHO_ANULAR
])

ANCHO_ACCIONES_GARANTIAS = ancho_acciones_para([
    ANCHO_GARANTIA
])


class ContratoDetalleDialog(QDialog):
    """
    El detalle de un contrato.

    __init__ no lanza: si el contrato no existe o el
    rol no tiene permiso, se pinta el motivo y el
    diálogo se cierra solo. Un diálogo que revienta
    al construirlo por un id malo deja la pantalla en
    blanco sin decir por qué.
    """

    def __init__(self, parent=None, id_contrato=None):
        super().__init__(parent)

        self.id_contrato = id_contrato

        self.puede_gestionar = tiene_permiso(
            GESTIONAR_CONTRATOS
        )

        self.puede_cobrar = tiene_permiso(
            GESTIONAR_FINANCIERA
        )

        self.puede_ver_historial = tiene_permiso(
            VER_AUDITORIA
        )

        self.contrato = None
        self.cuotas = []
        self.pagos = []
        self.resumen = {}

        # Lo pone texto_vehiculo() cuando el
        # contrato no tiene fotografía del vehículo.
        # Se inicializa aquí porque pintar_pie() lo
        # consulta aunque el contrato se haya leído bien
        # y no llegue a tocarlo.

        self.sin_fotografia = False

        self.crear_interfaz()

        self.cargar()

    # =============================
    # INTERFAZ
    # =============================

    def crear_interfaz(self):

        self.setWindowTitle("Detalle del contrato")

        self.setModal(True)

        self.resize(1000, 740)

        layout = QVBoxLayout()

        layout.setSpacing(12)

        self.setLayout(layout)

        self.titulo = crear_titulo("Contrato")

        layout.addWidget(self.titulo)

        # ------------------------------
        # LOS DATOS FIJOS
        # ------------------------------

        self.marco_datos = QFrame()

        self.marco_datos.setObjectName("tarjeta")

        self.rejilla = QGridLayout()

        self.rejilla.setSpacing(6)

        self.marco_datos.setLayout(self.rejilla)

        layout.addWidget(self.marco_datos)

        # ------------------------------
        # PESTAÑAS
        # ------------------------------

        self.pestanas = QTabWidget()

        self.pestanas.addTab(
            self.crear_panel_cronograma(),
            "📅  Cronograma"
        )

        self.pestanas.addTab(
            self.crear_panel_pagos(),
            "💵  Pagos"
        )

        self.pestanas.addTab(
            self.crear_panel_garantias(),
            "🔒  Garantías"
        )

        # ------------------------------
        # EL HISTORIAL SOLO SI SE PUEDE
        # ------------------------------
        # La pestaña se AÑADE, no se deshabilita:
        # leer la auditoría exige su permiso, y una
        # pestaña que al pinchar avisa de nada es peor
        # que no tenerla.
        #
        # Y no es una molestia: el vendedor ve los
        # contratos, pero el rastro completo es de
        # la administración.

        if self.puede_ver_historial:

            self.pestanas.addTab(
                self.crear_panel_historial(),
                "🕓  Historial"
            )

        else:

            self.area_historial = None

        layout.addWidget(self.pestanas)

        # ------------------------------
        # PIE
        # ------------------------------

        self.etiqueta_pie = QLabel("")

        self.etiqueta_pie.setObjectName("pie")

        self.etiqueta_pie.setWordWrap(True)

        layout.addWidget(self.etiqueta_pie)

        # ------------------------------
        # BOTONES
        # ------------------------------

        self.boton_pdf = crear_boton_secundario(
            "Imprimir contrato (PDF)",
            self.generar_pdf
        )

        self.boton_recibo = crear_boton_secundario(
            "Imprimir recibo",
            self.generar_recibo
        )

        fila = QHBoxLayout()

        fila.setSpacing(10)

        fila.addWidget(self.boton_pdf)

        fila.addWidget(self.boton_recibo)

        fila.addStretch()

        fila.addWidget(crear_boton_secundario(
            "Cerrar", self.reject
        ))

        layout.addLayout(fila)

    # ------------------------------
    # PANELES
    # ------------------------------

    def crear_panel_cronograma(self):

        panel = QWidget()

        layout = QVBoxLayout()

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(8)

        self.tabla_cuotas = crear_tabla(
            [
                "Nº",
                "Vencimiento",
                "Importe",
                "Saldo",
                "Pagos",
                "Días",
                "Estado"
            ],
            columna_acciones=COLUMNA_ACCIONES_CUOTAS,
            ancho_acciones=ANCHO_ACCIONES_CUOTAS,
            anchos_fijos={1: 110}
        )

        cabecera = self.tabla_cuotas.horizontalHeader()

        for indice in (0, 2, 3, 4, 5):

            cabecera.setSectionResizeMode(
                indice,
                QHeaderView.ResizeToContents
            )

        layout.addWidget(self.tabla_cuotas)

        self.etiqueta_cronograma = QLabel("")

        self.etiqueta_cronograma.setObjectName("pie")

        self.etiqueta_cronograma.setWordWrap(True)

        layout.addWidget(self.etiqueta_cronograma)

        # ------------------------------
        # LOS BOTONES DEL CRONOGRAMA
        # ------------------------------

        fila = QHBoxLayout()

        fila.setSpacing(10)

        self.boton_generar = crear_boton_principal(
            "Generar cronograma",
            self.generar_cronograma
        )

        self.boton_cobrar = crear_boton_principal(
            "Cobrar la más antigua",
            self.cobrar_pendiente
        )

        fila.addWidget(self.boton_generar)

        fila.addWidget(self.boton_cobrar)

        self.boton_adelantado = crear_boton_principal(
            "Cobrar adelantado",
            self.cobrar_adelantado
        )

        fila.addWidget(self.boton_adelantado)

        fila.addStretch()

        layout.addLayout(fila)

        panel.setLayout(layout)

        return panel

    def crear_panel_pagos(self):

        panel = QWidget()

        layout = QVBoxLayout()

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(8)

        # ------------------------------
        # EL DINERO, EN CUATRO CIFRAS
        # ------------------------------

        self.etiquetas_dinero = {}

        marco = QFrame()

        marco.setObjectName("tarjeta")

        rejilla = QGridLayout()

        rejilla.setSpacing(6)

        for indice, (clave, rotulo) in enumerate((
            ("financiado", "Saldo financiado"),
            ("cobrado", "Cobrado"),
            ("pendiente", "Pendiente"),
            ("vencido", "Vencido")
        )):

            etiqueta = QLabel(f"{rotulo}: —")

            etiqueta.setObjectName("pie")

            self.etiquetas_dinero[clave] = etiqueta

            rejilla.addWidget(
                etiqueta, indice // 2, indice % 2
            )

        marco.setLayout(rejilla)

        layout.addWidget(marco)

        # ------------------------------
        # EL LISTADO
        # ------------------------------

        self.tabla_pagos = crear_tabla(
            [
                "Recibo",
                "Fecha",
                "Importe",
                "Forma",
                "Cuota",
                "Registró",
                "Estado"
            ],
            columna_acciones=COLUMNA_ACCIONES_PAGOS,
            ancho_acciones=ANCHO_ACCIONES_PAGOS,
            anchos_fijos={1: 100}
        )

        cabecera = self.tabla_pagos.horizontalHeader()

        for indice in (1, 2, 4):

            cabecera.setSectionResizeMode(
                indice,
                QHeaderView.ResizeToContents
            )

        layout.addWidget(self.tabla_pagos)

        self.etiqueta_pagos = QLabel("")

        self.etiqueta_pagos.setObjectName("pie")

        self.etiqueta_pagos.setWordWrap(True)

        layout.addWidget(self.etiqueta_pagos)

        panel.setLayout(layout)

        return panel

    def crear_panel_garantias(self):

        panel = QWidget()

        layout = QVBoxLayout()

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(8)

        # ------------------------------
        # EL AVISO REGISTRAL, SIEMPRE
        # ------------------------------
        # Va antes de la tabla y no se quita nunca:
        # da igual cuántas garantías haya. Un
        # gravamen es una inscripción en el Registro
        # Público y lo que se anota aquí es lo que el
        # concesionario AFIRMA. Recordarlo en cada
        # pantalla es lo barato; descubrirlo cuando
        # ya se ha marcado una garantía como liberada
        # sin hacer la baja de verdad, no.

        self.aviso_registral = QLabel(
            garantias.AVISO_GRAVAMEN
        )

        self.aviso_registral.setObjectName("aviso")

        self.aviso_registral.setWordWrap(True)

        layout.addWidget(self.aviso_registral)

        self.tabla_garantias = crear_tabla(
            [
                "Tipo",
                "Descripción",
                "Estado",
                "Nº inscripción",
                "Inscripción",
                "Gravamen"
            ],
            columna_acciones=COLUMNA_ACCIONES_GARANTIAS,
            ancho_acciones=ANCHO_ACCIONES_GARANTIAS,
            anchos_fijos={4: 100}
        )

        cabecera = self.tabla_garantias.horizontalHeader()

        cabecera.setSectionResizeMode(
            5, QHeaderView.ResizeToContents
        )

        layout.addWidget(self.tabla_garantias)

        self.etiqueta_garantias = QLabel("")

        self.etiqueta_garantias.setObjectName("pie")

        layout.addWidget(self.etiqueta_garantias)

        self.boton_garantia = crear_boton_principal(
            "Registrar garantía",
            self.nueva_garantia
        )

        layout.addWidget(self.boton_garantia)

        panel.setLayout(layout)

        return panel

    def crear_panel_historial(self):

        panel = QWidget()

        layout = QVBoxLayout()

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(8)

        self.etiqueta_historial = QLabel(
            "Todo lo que se ha registrado sobre este "
            "contrato, con el valor anterior y el nuevo, "
            "del más reciente al más antiguo."
        )

        self.etiqueta_historial.setObjectName("pie")

        self.etiqueta_historial.setWordWrap(True)

        layout.addWidget(self.etiqueta_historial)

        self.area_historial = QTextEdit()

        self.area_historial.setReadOnly(True)

        layout.addWidget(self.area_historial)

        panel.setLayout(layout)

        return panel

    # =============================
    # CARGA
    # =============================

    def dinero(self, valor):
        """
        Un importe de ESTE contrato, con la moneda de
        ESTE contrato.

        ------------------------------
        # POR QUÉ UN MÉTODO Y NO UNA
        # VARIABLE SUELTA
        # ------------------------------

        Porque son diecinueve llamadas y basta con que
        una se quede sin `moneda=` para que un importe de
        un contrato firmado salga en la moneda que hay
        configurada ahora. Eso no se ve mirando el
        código: se ve en una pantalla, cuando un
        contrato en dólares dice "Gs. 25.000" porque el
        concesionario cambió de moneda hace un mes.

        Con este método no se puede olvidar: o se usa
        `self.dinero(...)`, o no hay imports que toque.

        Y los contratos ya guardan su moneda
        (`contratos.moneda`, la que tenía el ajuste en el
        momento de firmar). Un contrato firmado que se
        reimprime diciendo otra moneda es un documento
        que ya no sirve para nada.
        """

        return formato_dinero(
            valor,
            moneda=(self.contrato or {}).get("moneda")
        )

    def cargar(self):

        self.contrato = self.leer_contrato()

        if self.contrato is None:

            return

        self.pintar_datos()

        self.leer_pagos()

        self.leer_cuotas()

        self.leer_resumen()

        self.pintar_cronograma()

        self.pintar_pagos()

        self.pintar_garantias()

        self.pintar_historial()

        self.pintar_pie()

    def leer_contrato(self):

        """

        El contrato, o None con el motivo YA EN LAS
        ETIQUETAS del diálogo.

        obtener_contrato() va con permiso: si al rol no
        le falta, la vista no llega hasta aquí. Pero el
        id puede no existir, y eso sí hay que tratarlo: un
        contrato borrado desde otra pantalla dejaría
        este dialogo en blanco.

        ------------------------------
        # POR QUÉ NO SE AVISA CON UN
        # CUADRO DE MENSAJE
        # ------------------------------

        Porque esto pasa al CONSTRUIR el dialogo, que
        todavía no está en pantalla. Un QMessageBox en
        ese momento sale por encima de un diálogo que el
        usuario no ve todavía y, si el diálogo queda
         detrás, parece que la aplicación se ha colgado.

        El motivo va al título y al pie, que es donde el
        usuario lo va a leer de todas formas.

        """

        if self.id_contrato is None:

            self.pintar_problema(
                "No se señaló qué contrato abrir",
                "Este detalle necesita el numero de un "
                "contrato."
            )

            return None

        try:

            contrato = obtener_contrato(self.id_contrato)

        except Exception:

            registrar_error_inesperado(
                Exception(
                    "No se pudo leer el contrato "
                    f"{self.id_contrato}."
                )
            )

            self.pintar_problema(
                "No se pudo leer",
                "No se pudo leer el contrato. El detalle "
                "técnico está en registro_errores.log."
            )

            return None

        if not contrato:

            self.pintar_problema(
                "Contrato no encontrado",
                "El contrato indicado no existe. Puede que "
                "se haya eliminado desde otra pantalla."
            )

            return None

        return contrato

    def pintar_problema(self, titulo, detalle):

        """

        Deja el diálogo explicando qué pasa, en vez de
        en blanco.

        Y apaga lo que ya no tiene sentido: sin el
        contrato leído, el cronograma, los pagos y las
        garantías no se pueden generar, y un botón
        activo que va a fallar es peor que un botón
        apagado.

        """

        self.titulo.setText(titulo)

        self.etiqueta_pie.setText(detalle)

        self.marco_datos.setVisible(False)

        self.pestanas.setVisible(False)

        self.boton_pdf.setEnabled(False)

        self.boton_recibo.setEnabled(False)

    def leer_pagos(self):

        try:

            self.pagos = obtener_pagos_detalle(
                self.contrato["venta_id"]
            )

        except Exception:

            registrar_error_inesperado(
                Exception(
                    "No se pudieron leer los pagos de "
                    f"la venta {self.contrato['venta_id']}."
                )
            )

            self.pagos = []

    def leer_cuotas(self):

        try:

            self.cuotas = financiera.obtener_cuotas(
                self.id_contrato
            )

        except Exception:

            self.cuotas = []

    def leer_resumen(self):

        try:

            self.resumen = financiera.resumen_de_cuotas(
                self.id_contrato
            )

        except Exception:

            self.resumen = {}

    # =============================
    # LOS DATOS DE ARRIBA
    # =============================

    def pintar_datos(self):

        contrato = self.contrato

        self.titulo.setText(
            f"Contrato {contrato['numero']}"
        )

        # ------------------------------
        # EL VEHÍCULO, DE LA FOTOGRAFÍA
        # ------------------------------

        vehiculo = self.texto_vehiculo()

        campos = [
            ("Cliente", contrato["cliente"]),
            ("Documento", contrato["documento"] or "—"),
            ("Teléfono", contrato["telefono"] or "—"),
            ("Vehículo", vehiculo or "—"),
            ("Fecha", str(contrato["fecha"])),
            ("Vendedor", contrato["vendedor"]),
            ("Estado",
             ESTADOS_CONTRATO.get(
                 contrato["estado"], contrato["estado"]
             )),
            ("Forma de pago", contrato["forma_pago"]),
            ("Precio de venta",
             self.dinero(contrato["precio_venta"])),
            ("Precio de lista",
             self.dinero(
                 contrato["precio_lista"]
                 or contrato["precio_venta"]
             )),
            ("Entrega inicial",
             self.dinero(contrato["anticipo"])),
            ("Saldo financiado",
             self.dinero(
                 contrato["saldo_financiado"] or 0
             )),
            ("Cuotas",
             self.texto_cuotas_pactadas()),
            ("Tasa de interés",
             (
                 f"{contrato['tasa_interes']} %"
                 if contrato["tasa_interes"]
                 else "sin tasa"
             )),
            ("Gastos de administración",
             self.dinero(
                 contrato["gastos_administrativos"] or 0
             )),
            ("Periodicidad",
             contrato["periodicidad"] or "—"),
            ("Primer vencimiento",
             str(contrato["primer_vencimiento"] or "—")),
            ("Día de vencimiento",
             (
                 str(contrato["dia_vencimiento"])
                 if contrato["dia_vencimiento"]
                 else "—"
             )),
            ("Moneda", contrato["moneda"] or "—")
        ]

        # ------------------------------
        # CUATRO PARES POR FILA
        # ------------------------------
        # La rejilla es de 8 columnas: rótulo,
        # valor, rótulo, valor, rótulo, valor, rótulo,
        # valor. Con 18 campos sale casi entero y no
        # hay una fila a medio llenar que descuadre.
        #
        # Y no se le dice cuántas columnas tiene:
        # QGridLayout no tiene setColumnCount. Las
        # columnas son las que salgan de los widgets
        # que se le meten, y por eso el índice se
        # calcula a partir del campo, no fijo.

        for indice, (rotulo, valor) in enumerate(campos):

            etiqueta = QLabel(f"{rotulo}:")

            etiqueta.setObjectName("pie")

            valor_etiqueta = QLabel(str(valor))

            valor_etiqueta.setWordWrap(True)

            self.rejilla.addWidget(
                etiqueta,
                indice // 4,
                (indice % 4) * 2
            )

            self.rejilla.addWidget(
                valor_etiqueta,
                indice // 4,
                (indice % 4) * 2 + 1
            )

        # ------------------------------
        # LO QUE NO CABE EN LA REJILLA
        # ------------------------------
        # Las cláusulas y las observaciones son texto
        # largo, y metidas en la rejilla encogerían
        # todas las columnas para que quepa un
        # párrafo. Van debajo, a lo ancho.

        for rotulo, valor in (
            ("Retención",
             contrato["retencion"] or "—"),
            ("Observaciones",
             contrato["observaciones"] or ""),
            ("Cláusulas pactadas",
             contrato["clausulas"] or "")
        ):

            if not valor:

                continue

            self.anexar_texto(
                rotulo, str(valor), len(campos) // 4
            )

    def texto_vehiculo(self):
        """
        El vehículo tal como se firmó.

        Del contrato, no del JOIN: lo que se firmó no
        cambia porque alguien corrija el vehículo
        después. Y si el contrato es anterior a la
        fotografía, se lee del vehículo actual y se
        avisa, porque dejar el campo en blanco parece
        un dato que falta cuando lo que falta es el
        snapshot.
        """

        contrato = self.contrato

        partes = [
            contrato["marca"],
            contrato["modelo"],
            str(contrato["anio"]) if contrato["anio"] else ""
        ]

        vehiculo = " ".join(p for p in partes if p)

        if vehiculo and contrato["color"]:

            vehiculo += f" · {contrato['color']}"

        if vehiculo:

            return vehiculo

        actual = " ".join(p for p in (
            contrato["marca_actual"],
            contrato["modelo_actual"]
        ) if p)

        if actual:

            self.sin_fotografia = True

        return actual

    def texto_cuotas_pactadas(self):

        contrato = self.contrato

        if not contrato["cantidad_cuotas"]:

            return "pago contado"

        texto = f"{contrato['cantidad_cuotas']} cuota(s)"

        if contrato["monto_cuota"]:

            texto += (
                f" de {self.dinero(contrato['monto_cuota'])}"
            )

        return texto

    def anexar_texto(self, rotulo, valor, fila):
        """
        Una fila a lo ancho de la rejilla.

        "fila" la pasa quien llama, y no se saca de
        self.rejilla.rowCount(): en un QGridLayout eso
        NO es el número de filas que se han puesto.
        rowCount() cuenta las filas que ha calculado Qt
        por su cuenta, que con celdas que ocupan ocho
        columnas no tiene por qué coincidir, y el texto
        acabaría encima de un campo.
        """

        etiqueta = QLabel(f"{rotulo}: {valor}")

        etiqueta.setObjectName("pie")

        etiqueta.setWordWrap(True)

        self.rejilla.addWidget(etiqueta, fila, 0, 1, 8)

    # =============================
    # CRONOGRAMA
    # =============================

    def pintar_cronograma(self):

        filas = self.cuotas

        self.tabla_cuotas.setRowCount(len(filas))

        for indice, cuota in enumerate(filas):

            valores = [
                f"{cuota['numero']}",
                str(cuota["fecha_vencimiento"]),
                self.dinero(cuota["importe"]),
                self.dinero(cuota["saldo"]),
                f"{cuota['cantidad_pagos']}",
                self.texto_dias(cuota),
                financiera.ESTADOS.get(
                    cuota["estado"], cuota["estado"]
                )
            ]

            tono = TONO.get(cuota["estado"])

            for columna, valor in enumerate(valores):

                self.tabla_cuotas.setItem(
                    indice,
                    columna,
                    celda(
                        valor,
                        centrar=columna in {0, 2, 3, 4, 5},
                        objeto=tono
                    )
                )

            self.pintar_acciones_cuota(indice, cuota)

        # ------------------------------
        # LOS BOTONES
        # ------------------------------

        pendiente = self.cuota_pendiente()

        self.boton_generar.setEnabled(
            not filas
            and self.puede_gestionar
            and self.saldo_financiado() > 0
        )

        self.boton_cobrar.setEnabled(
            pendiente is not None
            and self.puede_cobrar
        )

        # ------------------------------
        # EL ADELANTADO, AL LADO
        # ------------------------------
        # Mismo permiso y misma condición que el de
        # una cuota: hacen falta las mismas dos cosas,
        # que el contrato tenga cronograma y quede algo
        # por cobrar.

        self.boton_adelantado.setEnabled(
            pendiente is not None
            and self.puede_cobrar
        )

        if not filas:

            self.etiqueta_cronograma.setText(
                "Este contrato no tiene cronograma."
                + (
                    " Genérelo para poder registrar "
                    "cobros de cuotas."
                    if self.saldo_financiado() > 0
                    else " Es un pago contado: no "
                    "tiene cuotas y no se le "
                    "generan."
                )
            )

            return

        self.etiqueta_cronograma.setText(
            f"{len(filas)} cuota(s) por "
            f"{self.dinero(self.importe_cronograma())}."
            + (
                f" {self.resumen.get('pagadas', 0)} "
                "pagada(s), "
                f"{self.resumen.get('parciales', 0)} "
                "parcial(es), "
                f"{self.resumen.get('vencidas', 0)} "
                "vencida(s)."
                if self.resumen else ""
            )
        )

    def texto_dias(self, cuota):
        """
        Cuánto le falta o le sobra.

        Una cuota pagada no dice "0 días": ya está
        saldada, y un cero al lado del saldo en cero
        parece un error de cálculo.
        """

        if cuota["estado"] == financiera.ESTADO_PAGADA:

            return "—"

        if cuota["estado"] == (
            financiera.ESTADO_ANULADA
        ):

            return "—"

        dias = (
            cuota["fecha_vencimiento"] - date.today()
        ).days

        if dias < 0:

            return f"{abs(dias)} tarde"

        if dias == 0:

            return "hoy"

        return f"en {dias} d."

    def pintar_acciones_cuota(self, indice, cuota):

        acciones = []

        # ------------------------------
        # COBRAR
        # ------------------------------

        if (
            self.puede_cobrar
            and Decimal(str(cuota["saldo"])) > 0
            and cuota["estado"] != (
                financiera.ESTADO_ANULADA
            )
        ):

            acciones.append((
                "Cobrar",
                lambda _, c=cuota:
                self.cobrar(c["id"]),
                None,
                ANCHO_COBRAR
            ))

        # ------------------------------
        # ANULAR O REACTIVAR
        # ------------------------------
        # Solo sin pagos: con dinero cobrado, anular la
        # cuota dejaría el saldo del contrato sin
        # cuadrar. Lo comprueba la capa de datos
        # también, pero esconder el botón es más
        # honesto que dejar que salte un aviso.

        if self.puede_gestionar:

            anulada = cuota["estado"] == (
                financiera.ESTADO_ANULADA
            )

            sin_pagos = (
                Decimal(str(cuota["saldo"]))
                == Decimal(str(cuota["importe"]))
            )

            if anulada and sin_pagos:

                acciones.append((
                    "Reactivar",
                    lambda _, c=cuota:
                    self.reactivar(c["id"]),
                    None,
                    ANCHO_REACTIVAR
                ))

            elif not anulada and sin_pagos:

                acciones.append((
                    "Anular",
                    lambda _, c=cuota:
                    self.anular_cuota(c),
                    None,
                    ANCHO_ANULAR_CUOTA
                ))

        if not acciones:

            return

        self.tabla_cuotas.setCellWidget(
            indice,
            COLUMNA_ACCIONES_CUOTAS,
            crear_botones_accion(
                al_editar=acciones[0][1],
                texto_editar=acciones[0][0],
                al_eliminar=None,
                mostrar_eliminar=False,
                acciones_extra=acciones[1:],
                ancho_editar=acciones[0][3]
            )
        )

    def importe_cronograma(self):

        total = Decimal("0.00")

        for cuota in self.cuotas:

            if cuota["estado"] != (
                financiera.ESTADO_ANULADA
            ):

                total += Decimal(str(cuota["importe"]))

        return total

    def saldo_financiado(self):

        return Decimal(
            str(self.contrato["saldo_financiado"] or 0)
        )

    def cuota_pendiente(self):
        """
        La cuota más antigua con saldo, o None.

        "Más antigua" y no "la número 1": si la
        primera está anulada, o ya cobrada, la que hay
        que cobrar es la siguiente. Y van en orden de
        número, que es el orden de vencimiento porque
        el cronograma se genera así.
        """

        for cuota in self.cuotas:

            if (
                cuota["estado"] != (
                    financiera.ESTADO_ANULADA
                )
                and Decimal(str(cuota["saldo"])) > 0
            ):

                return cuota

        return None

    # =============================
    # PAGOS
    # =============================

    def pintar_pagos(self):

        pagos = self.pagos

        self.tabla_pagos.setRowCount(len(pagos))

        for indice, pago in enumerate(pagos):

            anulado = pago["estado"] == "anulado"

            valores = [
                pago["recibo"] or "—",
                str(pago["fecha"]),
                self.dinero(pago["importe"]),
                pago["forma"],
                (
                    f"{pago['numero_cuota']}"
                    if pago["numero_cuota"] is not None
                    else "—"
                ),
                pago["usuario_nombre"] or "sin registrar",
                "Anulado" if anulado else "Convalidado"
            ]

            for columna, valor in enumerate(valores):

                self.tabla_pagos.setItem(
                    indice,
                    columna,
                    celda(
                        valor,
                        centrar=columna in {1, 2, 4},
                        objeto=(
                            TONO_ANULADO if anulado else None
                        )
                    )
                )

            # ------------------------------
            # SOLO SE ANULA LO QUE SE
            # IMPUTÓ A UNA CUOTA
            # ------------------------------
            # Anular un pago SIN cuota no devuelve
            # nada a ninguna parte: el saldo de la
            # cuota es el único que se recalcula al
            # anular. Dejarlo disponible sería un
            # botón que dice que deshizo y no
            # deshace.

            if (
                self.puede_gestionar
                and not anulado
                and pago["cuota_id"]
            ):

                self.tabla_pagos.setCellWidget(
                    indice,
                    COLUMNA_ACCIONES_PAGOS,
                    crear_botones_accion(
                        al_editar=(
                            lambda _, p=pago:
                            self.anular_pago(p)
                        ),
                        texto_editar="Anular",
                        al_eliminar=None,
                        mostrar_eliminar=False,
                        ancho_editar=ANCHO_ANULAR
                    )
                )

        ajustar_alto_tabla(self.tabla_pagos)

        # ------------------------------
        # LOS TOTALES
        # ------------------------------

        cobrados = [
            p for p in pagos
            if p["estado"] == "convalidado"
        ]

        total = sum(
            (Decimal(str(p["importe"])) for p in cobrados),
            Decimal("0.00")
        )

        pendiente = self.saldo_financiado() - total

        self.etiquetas_dinero["financiado"].setText(
            "Saldo financiado: "
            + self.dinero(self.saldo_financiado())
        )

        self.etiquetas_dinero["cobrado"].setText(
            f"Cobrado: {self.dinero(total)}"
        )

        self.etiquetas_dinero["pendiente"].setText(
            f"Pendiente: {self.dinero(pendiente)}"
        )

        self.etiquetas_dinero["vencido"].setText(
            "Vencido: "
            + self.dinero(self.importe_vencido())
        )

        if not pagos:

            self.etiqueta_pagos.setText(
                "Todavía no se ha registrado ningún pago "
                "de este contrato."
            )

            return

        anulados = len(pagos) - len(cobrados)

        self.etiqueta_pagos.setText(
            f"{len(cobrados)} pago(s) convalidado(s)"
            + (
                f"  ·  {anulados} anulado(s), que no "
                "suman"
                if anulados else ""
            )
            + ". Un pago anulado no se borra: queda "
            "registrado con su motivo, y por eso sale "
            "en la lista."
        )

    def importe_vencido(self):
        """
        Lo vencido, por fechas y no por estado.

        Una cuota que alguien marcó a mano y que luego
        se pagó no está vencida, y una que nadie marcó
        y que pasó su fecha sí lo está. El estado
        da la primera respuesta; la fecha, la correcta.
        """

        total = Decimal("0.00")

        hoy = date.today()

        for cuota in self.cuotas:

            if (
                cuota["estado"] != (
                    financiera.ESTADO_ANULADA
                )
                and Decimal(str(cuota["saldo"])) > 0
                and hoy > cuota["fecha_vencimiento"]
            ):

                total += Decimal(str(cuota["saldo"]))

        return total

    # =============================
    # GARANTÍAS
    # =============================

    def pintar_garantias(self):

        try:

            filas = garantias.obtener_garantias(
                self.id_contrato
            )

        except Exception:

            filas = []

        self.tabla_garantias.setRowCount(len(filas))

        for indice, fila in enumerate(filas):

            valores = [
                garantias.TIPOS.get(
                    fila["tipo"], fila["tipo"]
                ),
                fila["descripcion"] or "—",
                garantias.ESTADOS.get(
                    fila["estado"], fila["estado"]
                ),
                fila["numero_inscripcion"] or "—",
                (
                    str(fila["fecha_inscripcion"])
                    if fila["fecha_inscripcion"]
                    else "—"
                ),
                "Sí" if fila["es_gravamen"] else "No"
            ]

            tono = None

            if fila["estado"] == "inscrita" and fila[
                "es_gravamen"
            ]:

                tono = "tono_info"

            for columna, valor in enumerate(valores):

                self.tabla_garantias.setItem(
                    indice,
                    columna,
                    celda(
                        valor,
                        centrar=columna in {4, 5},
                        objeto=tono
                    )
                )

            self.pintar_acciones_garantia(indice, fila)

        ajustar_alto_tabla(self.tabla_garantias)

        self.boton_garantia.setEnabled(self.puede_gestionar)

        if not filas:

            self.etiqueta_garantias.setText(
                "Este contrato no tiene garantías "
                "registradas. Sin respaldo, una venta "
                "financiada vencida solo deja el "
                "papeleo."
            )

            return

        sin_liberar = sum(
            1 for f in filas
            if f["estado"] in ("pendiente", "inscrita")
        )

        self.etiqueta_garantias.setText(
            f"{len(filas)} garantía(s) registrada(s), "
            f"{sin_liberar} sin liberar."
            + (
                " El contrato tiene saldo pendiente, "
                "así que no se pueden liberar: liberar "
                "es devolverle el respaldo al cliente."
                if self.saldo_pendiente_real() > 0 else ""
            )
        )

    def pintar_acciones_garantia(self, indice, fila):

        if not self.puede_gestionar:

            return

        # ------------------------------
        # SOLO EL SIGUIENTE PASO
        # ------------------------------
        # De cada estado sale un botón, el único legal.
        # Poner los dos posibles y dejar que uno falle
        # es hacer que el usuario descubra las reglas
        # por el camino.

        permitidos = garantias.TRANSICIONES.get(
            fila["estado"], []
        )

        if not permitidos:

            return

        siguiente = permitidos[0]

        textos = {
            "inscrita": "Inscribir",
            "liberada": "Liberar",
            "rechazada": "Rechazar"
        }

        self.tabla_garantias.setCellWidget(
            indice,
            COLUMNA_ACCIONES_GARANTIAS,
            crear_botones_accion(
                al_editar=(
                    lambda _, f=fila, s=siguiente:
                    self.cambiar_garantia(f, s)
                ),
                texto_editar=textos.get(
                    siguiente, siguiente
                ),
                al_eliminar=None,
                mostrar_eliminar=False,
                ancho_editar=ANCHO_GARANTIA
            )
        )

    def saldo_pendiente_real(self):
        """
        Lo que queda por cobrar: lo financiado menos
        lo cobrado.

        NO es saldo_financiado. Ese es el importe que
        se pactó, no lo que queda, y usarlo para decidir
        si se puede liberar una garantía haría creer
        que un contrato pagado del todo sigue debiendo
        su precio entero.
        """

        if self.contrato is None:

            return Decimal("0.00")

        cobrado = sum(
            (
                Decimal(str(p["importe"]))
                for p in self.pagos
                if p["estado"] == "convalidado"
            ),
            Decimal("0.00")
        )

        return self.saldo_financiado() - cobrado

    # =============================
    # HISTORIAL
    # =============================

    def pintar_historial(self):

        if not self.puede_ver_historial:

            return

        try:

            registros = historial_contrato(
                self.id_contrato
            )

        except Exception:

            self.area_historial.setText(
                "No se pudo leer el historial. El "
                "detalle está en registro_errores.log."
            )

            return

        if not registros:

            self.area_historial.setText(
                "Todavía no hay nada registrado sobre "
                "este contrato."
            )

            return

        lineas = []

        for registro in registros:

            # Por índice y no desempaquetando: la forma
            # de esta fila es un contrato entre la
            # consulta y quien la pinta, y desempaquetar
            # revienta en cuanto caiga una columna más
            # (que es lo que pasó con valor_anterior).

            fecha = str(registro[1])[:19]

            usuario = registro[2] or "sistema"

            accion = registro[3]

            descripcion = registro[5] or ""

            anterior = (
                registro[6] if len(registro) > 6 else None
            )

            nuevo = (
                registro[7] if len(registro) > 7 else None
            )

            linea = f"{fecha}  ·  {usuario}  ·  {accion}"

            if descripcion:

                linea += f"\n    {descripcion}"

            if anterior is not None or nuevo is not None:

                linea += (
                    f"\n    antes: "
                    f"{anterior if anterior is not None else '(sin dato)'}"
                    f"\n    ahora: "
                    f"{nuevo if nuevo is not None else '(sin dato)'}"
                )

            lineas.append(linea)

        self.area_historial.setText("\n\n".join(lineas))

    def pintar_pie(self):

        partes = []

        if self.sin_fotografia:

            partes.append(
                "Este contrato es anterior a la "
                "fotografía del vehículo: se muestra "
                "el dato actual, que puede no ser el "
                "que se firmó."
            )

        if self.contrato["estado"] == "cancelado":

            partes.append(
                "Contrato cancelado: no admite cobros "
                "ni cambios en las cuotas."
            )

        self.etiqueta_pie.setText("  ·  ".join(partes))

    # =============================
    # ACCIONES
    # =============================

    def generar_cronograma(self):
        """
        Crear las cuotas del contrato.

        Se pregunta antes: el cronograma es el
        documento que se pactó y crearlo sin querer
        deja cuotas que no se pueden borrar, solo
        anular. Y la generación no es lenta, así que
        no hay prisa.
        """

        if not self.confirmar(
            "Generar el cronograma",
            f"Se crearán "
            f"{self.contrato['cantidad_cuotas']} cuotas "
            f"por {self.dinero(self.saldo_financiado())}, "
            f"la primera el "
            f"{self.contrato['primer_vencimiento']}.\n\n"
            "Un cronograma ya creado no se puede "
            "cambiar: hay que anular antes los pagos.\n\n"
            "¿Continuar?"
        ):

            return

        total, motivo = financiera.generar_cronograma(
            self.id_contrato
        )

        if total == 0:

            self.avisar(motivo, error=True)

            return

        self.cargar()

        self.avisar(
            f"Se generaron {total} cuotas."
        )

    def cobrar_pendiente(self):

        pendiente = self.cuota_pendiente()

        if not pendiente:

            self.avisar(
                "No hay cuotas pendientes de cobro.",
                error=True
            )

            return

        self.cobrar(pendiente["id"])

    def cobrar_adelantado(self):
        """
        Cobrar varias cuotas seguidas de una vez.

        Es un camino aparte del de una cuota, y tiene
        que serlo: registrar_pago_cuota() rechaza un
        importe mayor que el saldo de la cuota, porque
        no tiene a qué imputar el sobrante. Poner
        veinte mil ahí, con el cliente delante y una
        cuota de diez, daría un error que no explica
        lo que el cliente quería hacer.
        """

        formulario = PagoAdelantadoForm(
            self, self.id_contrato
        )

        if not formulario.exec():

            return

        self.cargar()

        if formulario.recibos:

            self.avisar(
                f"Cobro adelantado registrado.\n\n"
                f"Recibo: {formulario.recibos[0]}"
            )

    def cobrar(self, id_cuota):
        """
        Cobrar una cuota, y recargar si salió bien.

        El formulario devuelve el recibo que se generó,
        porque el cajero lo necesita para entregarlo en
        mano y no puede buscarlo en la base después de
        cerrar.
        """

        formulario = PagoCuotaForm(self, id_cuota)

        if not formulario.exec():

            return

        recibo = formulario.recibo

        self.cargar()

        if recibo:

            self.avisar(
                f"Pago registrado. Recibo {recibo}.",
                aviso_impresion=True
            )

    def anular_cuota(self, cuota):

        if not self.confirmar(
            "Anular la cuota",
            f"Se anulará la cuota {cuota['numero']}, de "
            f"{self.dinero(cuota['importe'])}.\n\n"
            "Deja de ser exigible y vuelve a "
            "sumar al cronograma pendiente. Podrá "
            "reactivarla después.\n\n"
            "¿Continuar?"
        ):

            return

        motivo, ok = self.pedir_motivo(
            "Por qué se anula la cuota"
        )

        if not ok:

            return

        correcto, resultado = financiera.anular_cuota(
            cuota["id"], motivo
        )

        if not correcto:

            self.avisar(resultado, error=True)

            return

        self.cargar()

        self.avisar("Cuota anulada.")

    def reactivar(self, id_cuota):

        motivo, ok = self.pedir_motivo(
            "Por qué se reactiva la cuota"
        )

        if not ok:

            return

        correcto, resultado = financiera.reactivar_cuota(
            id_cuota, motivo
        )

        if not correcto:

            self.avisar(resultado, error=True)

            return

        self.cargar()

        self.avisar("Cuota reactivada.")

    def anular_pago(self, pago):
        """
        Anular un pago.

        No se borra: se anula, con su motivo, su
        usuario y su fecha, y el importe vuelve a la
        cuota. La diferencia importa: "se cobró de más
        y se devolvió" y "nunca se cobró" no son lo
        mismo, y el cliente lo recuerda distinto.
        """

        if not self.confirmar(
            "Anular el pago",
            f"Se anulará el pago "
            f"{pago['recibo'] or ''} de "
            f"{self.dinero(pago['importe'])} "
            f"y el importe volverá a la cuota.\n\n"
            "El pago no se borra: queda registrado "
            "como anulado, con su motivo.\n\n"
            "¿Continuar?"
        ):

            return

        motivo, ok = self.pedir_motivo(
            "Motivo de la anulación"
        )

        if not ok:

            return

        correcto, resultado = financiera.anular_pago(
            pago["id"], motivo
        )

        if not correcto:

            self.avisar(resultado, error=True)

            return

        self.cargar()

        self.avisar("Pago anulado y devuelto a la cuota.")

    # ------------------------------
    # GARANTÍAS
    # ------------------------------

    def nueva_garantia(self):

        if GarantiaForm(self, self.id_contrato).exec():

            self.cargar()

    def cambiar_garantia(self, garantia, siguiente):

        # ------------------------------
        # INSCRIBIR: PIDE EL NÚMERO
        # ------------------------------

        if siguiente == "inscrita":

            if FormularioInscripcion(
                self, garantia["id"]
            ).exec():

                self.cargar()

            return

        # ------------------------------
        # LIBERAR: AVISA DOS VECES
        # ------------------------------
        # Liberar es devolverle al cliente su respaldo.
        # La comprobación de saldo la hace la capa de
        # datos, pero aquí hay que decir la verdad
        # sobre lo que significa: un contrato pagado
        # del todo NO significa garantía liberada en
        # el Registro Público.

        if siguiente == "liberada":

            if not self.confirmar(
                "Liberar la garantía",
                "Liberar la garantía es devolverle al "
                "cliente su respaldo.\n\n"
                "Solo se permite si el contrato no "
                "tiene saldo pendiente, y solo "
                "DESPUÉS de haber hecho la baja de "
                "verdad donde corresponda.\n\n"
                "Marcar aquí 'liberada' no libera nada "
                "en ningún registro.\n\n"
                "¿Ya está hecha? ¿Continuar?"
            ):

                return

            correcto, resultado = garantias.\
                cambiar_estado_garantia(
                    garantia["id"],
                    "liberada",
                    fecha_liberacion=date.today()
                )

        elif siguiente == "rechazada":

            if not self.confirmar(
                "Marcar la garantía como rechazada",
                "Se registrará que la garantía "
                "ofrecida no llegó a aceptarse.\n\n"
                "¿Continuar?"
            ):

                return

            correcto, resultado = garantias.\
                cambiar_estado_garantia(
                    garantia["id"], "rechazada"
                )

        else:

            return

        if not correcto:

            self.avisar(resultado, error=True)

            return

        self.cargar()

        self.avisar("Garantía actualizada.")

    # ------------------------------
    # PDF
    # ------------------------------

    def generar_pdf(self):

        try:

            ruta = generar_contrato(
                self.contrato,
                # El cronograma ya está cargado en
                # `self.cuotas`: un contrato financiado
                # sin la tabla de vencimientos no dice
                # cuánto ni cuándo tiene que pagar.
                cuotas=self.cuotas
            )

        except Exception as error:

            registrar_error_inesperado(error)

            self.avisar(
                "No se pudo generar el PDF. El "
                "detalle está en registro_errores.log.",
                error=True
            )

            return

        self.avisar_documento("el contrato", ruta)

    def generar_recibo(self):
        """
        Imprimir el papel de un cobro.

        ------------------------------
        # SE AGRUPA POR RECIBO
        # ------------------------------

        Un cobro adelantado son VARIOS pagos con el
        MISMO número de recibo: el cliente entregó una
        suma, se guardó como N imputaciones a N cuotas
        y se lleva un papel.

        Si se eligiera por pago, aparecerían N líneas
        con el mismo número de recibo y habría que
        elegir "cuál de estos cinco", cuando el cliente
        no compró cinco cobros: compró uno. Y el PDF de
        uno solo diría diez mil de un total de treinta,
        que es justo el papel que no sirve.

        Se agrupa por recibo y el PDF lleva la tabla de
        imputación.
        """

        grupos = self.agrupar_por_recibo()

        if not grupos:

            self.avisar(
                "Este contrato todavía no tiene pagos "
                "que imprimir.",
                error=True
            )

            return

        if len(grupos) == 1:

            elegido = grupos[0]

        else:

            elegido = self.elegir_recibo(grupos)

        if elegido is None:

            return

        # ------------------------------
        # LAS CUOTAS, EN EL MISMO ORDEN
        # ------------------------------
        # generar_recibo() las empareja por posición, y
        # obtener_pagos_detalle() viene por fecha
        # descendente mientras que las cuotas se leen
        # por número. Sin ordenar, la primera línea del
        # reparto sería la última cuota.

        pagos = sorted(
            elegido["pagos"],
            key=lambda p: (
                p["numero_cuota"] is None,
                p["numero_cuota"] or 0
            )
        )

        por_id = {c["id"]: c for c in self.cuotas}

        cuotas = [
            por_id[p["cuota_id"]]
            for p in pagos
            if p["cuota_id"] in por_id
        ]

        try:

            ruta = generar_recibo(
                pagos,
                self.contrato,
                cuotas
            )

        except Exception as error:

            registrar_error_inesperado(error)

            self.avisar(
                "No se pudo generar el recibo. El "
                "detalle está en registro_errores.log.",
                error=True
            )

            return

        self.avisar_documento("el recibo", ruta)

    def agrupar_por_recibo(self):
        """
        Los cobros convalidados, agrupados por recibo.

        Un pago sin recibo, o con uno repetido por
        error, se agrupa solo. No se inventa un número
        para agrupar: es preferible un papel con un
        "(sin recibo)" antes que dos recibios que en
        realidad son el mismo papel.
        """

        grupos = {}

        for pago in self.pagos:

            if pago["estado"] != "convalidado":

                continue

            clave = pago["recibo"] or f"sin-{pago['id']}"

            if clave not in grupos:

                grupos[clave] = {
                    "recibo": pago["recibo"],
                    "pagos": []
                }

            grupos[clave]["pagos"].append(pago)

        lista = list(grupos.values())

        for grupo in lista:

            grupo["total"] = sum(
                (
                    Decimal(str(p["importe"]))
                    for p in grupo["pagos"]
                ),
                Decimal("0.00")
            )

            grupo["cuotas"] = ", ".join(
                str(numero)
                for numero in sorted(
                    p["numero_cuota"]
                    for p in grupo["pagos"]
                    if p["numero_cuota"] is not None
                )
            ) or "pago a cuenta"

        return lista

    def elegir_recibo(self, grupos):
        """
        De cuál de los cobros es el recibo, o None.

        Recibe los GRUPOS (uno por recibo), no los pagos
        sueltos: la línea dice cuántas cuotas cubre y el
        total, que es lo que el cajero necesita ver para
        distinguir dos recibos del mismo importe.

        Se pregunta con un diálogo propio y no con un
        desplegable: el número de recibo y el importe
        son lo largo de cada línea, y en un desplegable
        estrecho se cortan justo los dos datos que
        sirven para decidir.
        """

        textos = []

        for grupo in grupos:

            propias = len(grupo["pagos"]) > 1

            cuota = (
                f"{grupo['cuotas']}"
                if not propias else
                f"cuotas {grupo['cuotas']}"
            )

            textos.append(
                f"{grupo['recibo'] or '(sin recibo)'}   ·   "
                f"{grupo['pagos'][0]['fecha']}   ·   "
                f"{self.dinero(grupo['total'])}   ·   "
                f"{cuota}"
            )

        elegido, ok = QInputDialog.getItem(
            self,
            "Qué recibo imprimir",
            "Recibo:",
            textos,
            0,
            False
        )

        if not ok or elegido not in textos:

            return None

        return grupos[textos.index(elegido)]

    def avisar_documento(self, que, ruta):
        """
        Dice dónde quedó el documento y ofrece abrirlo.

        Abrirlo con QDesktopServices y no con un cartel
        con la ruta: copiar una ruta a mano para
        pegarla en el explorador es un paso de más
        cada vez, y la carpeta de documentos está
        siempre en el mismo sitio.
        """

        respuesta = QMessageBox.question(
            self,
            "Documento generado",
            f"El PDF de {que} se guardó en:\n"
            f"{ruta}\n\n¿Quiere abrirlo?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if respuesta != QMessageBox.Yes:

            return

        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        if not QDesktopServices.openUrl(
            QUrl.fromLocalFile(ruta)
        ):

            self.avisar(
                "No se pudo abrir el documento. Ábralo "
                f"desde:\n{ruta}",
                error=True
            )

    # =============================
    # AVISOS
    # =============================

    def pedir_motivo(self, titulo):
        """
        Pide un motivo y lo exige.

        Devuelve (motivo, True) o ("", False).

        Una anulación sin motivo no se guarda, y es
        mejor no abrir la ventana que abrirla y que el
        usuario la cancele sin entender por qué: por eso
        el motivo vacío devuelve False y no un True con
        cadena vacía.
        """

        texto, ok = QInputDialog.getText(
            self,
            titulo,
            "Explica el motivo (obligatorio):",
            QLineEdit.Normal,
            ""
        )

        if not ok:

            return ("", False)

        if not texto.strip():

            self.avisar(
                "El motivo es obligatorio.",
                error=True
            )

            return ("", False)

        return (texto.strip(), True)

    def avisar(self, texto, error=False, aviso_impresion=False):

        # ------------------------------
        # LO QUE SE AVISA, Y CÓMO
        # ------------------------------

        if error:

            QMessageBox.warning(
                self, "No se pudo completar", texto
            )

            return

        QMessageBox.information(
            self, "Realizado", texto
        )

    def confirmar(self, titulo, mensaje):

        respuesta = QMessageBox.question(
            self,
            titulo,
            mensaje,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        return respuesta == QMessageBox.Yes
