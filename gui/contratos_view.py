# ==========================================
# LISTADO DE CONTRATOS
# ==========================================
# Un contrato no se edita: se cancela y se
# rehace desde la venta. Por eso la columna de
# acciones ofrece ver el detalle, generar el
# PDF, cambiar el estado y borrar, y solo
# enseña los dos últimos a quien puede
# gestionarlos.
#
# El alta tampoco va por el botón de "nuevo":
# el contrato nace de una venta, así que el
# botón lista las ventas que aún no lo tienen.
# ==========================================


import os
import subprocess
import sys

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QInputDialog
)

from database.contratos import (
    obtener_contratos,
    ventas_sin_contrato,
    cambiar_estado as cambiar_estado_db,
    eliminar_contrato as eliminar_contrato_db,
    registrar_pdf,
    ESTADOS,
    TRANSICIONES
)

from permisos import (
    tiene_permiso,
    CREAR_CONTRATOS
)

from utils.helpers import (
    crear_botones_accion,
    ancho_acciones_para
)

from utils.contrato_pdf import (
    generar_contrato,
    ruta_relativa,
    formato_dinero,
    formato_fecha,
    cuota_importe
)

from gui.vista_listado import VistaListado

from gui.formularios.contrato_form import ContratoForm


# Filtro de estado. La primera opción es "todos".

ESTADOS_FILTRO = [("", "Todos los estados")] + [
    (clave, texto)
    for clave, texto in ESTADOS.items()
]


def abrir_archivo(ruta):
    """
    Abre el PDF con el visor del sistema.

    Un contrato se revisa e imprime, así que
    conviene abrirlo directamente en vez de
    dejar la ruta copiada en el portapapeles.
    """

    try:

        if sys.platform.startswith("win"):

            os.startfile(ruta)

        elif sys.platform == "darwin":

            subprocess.Popen(["open", ruta])

        else:

            subprocess.Popen(["xdg-open", ruta])

        return True

    except OSError:

        return False


class ContratosView(VistaListado):

    titulo = "Contratos"

    columnas = [
        "Nº",
        "Cliente",
        "Vehículo",
        "Fecha",
        "Precio",
        "Estado",
        "Acciones"
    ]

    # La forma de pago no sale en la tabla: con
    # cuatro botones de fila no cabe, y es un
    # dato del contrato, no algo que se vaya a
    # recorrer en el listado. Se lee en el
    # detalle y en el PDF.

    columna_acciones = 6

    ANCHO_VER = 56

    ANCHO_PDF = 56

    ANCHO_ESTADO = 72

    ANCHO_ELIMINAR = 94

    # Se calcula con los cuatro botones: es el
    # caso más ancho, y es el mismo para todos
    # los roles. Ponerlo a mano era lo que
    # dejaba los botones fuera de su celda.

    ancho_acciones = ancho_acciones_para([
        ANCHO_VER,
        ANCHO_PDF,
        ANCHO_ESTADO,
        ANCHO_ELIMINAR
    ])

    # Los anchos fijos cubren lo que mide de
    # verdad el texto a 13 px MAS el padding
    # de 20 px de la celda (QTableWidget::item
    # { padding: 9px 10px } en gui/estilo.css).
    # Sin ese padding el número y el precio
    # salían con puntos suspensivos.

    anchos_fijos = {
        0: 132,
        3: 100,
        4: 132,
        5: 92
    }

    texto_nuevo = "+ Nuevo contrato"

    placeholder_busqueda = (
        "Buscar por número, cliente o vehículo..."
    )

    mensaje_vacio = "Todavía no hay contratos"

    detalle_vacio = (
        "Los contratos se crean desde el "
        "historial de ventas, una vez "
        "registrada la operación."
    )

    def __init__(self, parent=None, puede_gestionar=True):
        super().__init__(
            parent,
            puede_gestionar=puede_gestionar
        )

    # =============================
    # INTERFAZ
    # =============================

    @property
    def puede_crear(self):
        """
        El botón de alta depende de crear
        contratos, no de gestionarlos: el
        vendedor documenta su venta aunque no
        pueda cancelar nada.
        """

        return tiene_permiso(CREAR_CONTRATOS)

    def muestra_boton_nuevo(self):
        return self.puede_crear

    def crear_buscador(self):
        """
        La búsqueda y el filtro de estado van
        en la misma fila: los dos acotan la
        misma lista.
        """

        contenedor = QWidget()

        layout = QHBoxLayout(contenedor)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(10)

        layout.addWidget(
            super().crear_buscador(),
            stretch=1
        )

        self.combo_estado = QComboBox()

        self.combo_estado.setFixedHeight(40)

        self.combo_estado.setMinimumWidth(190)

        for clave, texto in ESTADOS_FILTRO:

            self.combo_estado.addItem(texto, clave)

        self.combo_estado.currentIndexChanged.connect(
            self.al_cambiar_estado
        )

        layout.addWidget(self.combo_estado)

        return contenedor

    # =============================
    # FILTRO
    # =============================

    @property
    def estado_seleccionado(self):
        """
        El estado con el que se filtra. La
        cadena vacía significa "todos".
        """

        return self.combo_estado.currentData()

    def al_cambiar_estado(self):

        # El filtro manda sobre lo que hay
        # escrito en el buscador: si no, una
        # búsqueda sin resultados dejaría la
        # lista vacía y el usuario pensaría que
        # no hay contratos de ese estado.

        self.cargar_datos()

    def cargar_datos(self):

        self.mostrar_de(
            obtener_contratos,
            self.estado_seleccionado or None
        )

    def buscar(self, texto):

        if not texto:

            self.cargar_datos()

            return

        self.mostrar_de(
            obtener_contratos,
            self.estado_seleccionado or None,
            texto
        )

    # =============================
    # PINTADO
    # =============================

    def pintar_fila(self, fila, contrato):

        self.marcar_columnas(
            fila,
            [
                contrato["numero"] or "(sin número)",
                contrato["cliente"],
                contrato["vehiculo"],
                formato_fecha(contrato["fecha"]),
                formato_dinero(contrato["precio_venta"])
            ]
        )

        # ------------------------------
        # ESTADO CON TONO
        # ------------------------------
        # El estado va con fondo porque es la
        # columna que de un vistazo dice si la
        # operación sigue en marcha o se cayó.
        # Va en su propia columna, la 5: por eso
        # no se añade a la lista de arriba, que
        # escribe siempre desde la columna 0.

        self.pintar_tono_estado(fila, contrato["estado"])

        self.poner_acciones(
            fila,
            self.crear_botones(fila)
        )

    def pintar_tono_estado(self, fila, estado):

        if estado == "activo":
            objeto = "tono_ok"

        elif estado == "finalizado":
            objeto = "tono_info"

        elif estado == "cancelado":
            objeto = "tono_peligro"

        else:
            objeto = "tono_aviso"

        self.tabla.setItem(
            fila,
            self.columna_acciones - 1,
            self.crear_celda(
                ESTADOS.get(estado, estado),
                objeto=objeto
            )
        )

    def crear_botones(self, fila):

        acciones_extra = [
            (
                "PDF",
                lambda _, f=fila: self.generar_pdf_de(f),
                "boton_editar",
                self.ANCHO_PDF
            )
        ]

        if self.puede_gestionar:

            acciones_extra.append((
                "Estado",
                lambda _, f=fila: self.cambiar_estado_de(f),
                "boton_editar",
                self.ANCHO_ESTADO
            ))

        return crear_botones_accion(
            lambda _, f=fila: self.ver_detalle(f),
            lambda _, f=fila: self.eliminar_de(f),
            texto_editar="Ver",
            mostrar_eliminar=self.puede_gestionar,
            acciones_extra=acciones_extra,
            ancho_editar=self.ANCHO_VER,
            ancho_eliminar=self.ANCHO_ELIMINAR
        )

    # =============================
    # ALTA
    # =============================

    def nuevo_registro(self):
        """
        Abre el contrato de la venta elegida
        entre las que aún no lo tienen.
        """

        ventas = self.proteger(ventas_sin_contrato)

        if ventas is None:

            return

        if not ventas:

            self.mostrar_mensaje_error(
                "Todas las ventas registradas ya "
                "tienen su contrato."
            )

            return

        self.elegir_venta(ventas)

    def elegir_venta(self, ventas):

        ventana = QDialog(self)

        ventana.setWindowTitle(
            "Elegir venta para el contrato"
        )

        ventana.setFixedWidth(600)

        layout = QVBoxLayout(ventana)

        layout.setSpacing(12)

        aviso = QLabel(
            "Elige la venta que quieres documentar.\n"
            "El contrato hereda el cliente, el "
            "vehículo y el precio de ella."
        )

        aviso.setObjectName("subtitulo")

        aviso.setWordWrap(True)

        layout.addWidget(aviso)

        combo = QComboBox()

        for venta in ventas:

            combo.addItem(
                f"Venta {venta[0]}   ·   {venta[2]}   ·   "
                f"{venta[3]}   ·   {formato_dinero(venta[4])}"
            )

        layout.addWidget(combo)

        botones = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )

        botones.button(
            QDialogButtonBox.Ok
        ).setObjectName("boton_principal")

        botones.button(
            QDialogButtonBox.Ok
        ).setText("Continuar")

        botones.accepted.connect(ventana.accept)

        botones.rejected.connect(ventana.reject)

        layout.addWidget(botones)

        if not ventana.exec():

            return

        # ------------------------------
        # ABRIR EL FORMULARIO
        # ------------------------------
        # Se pasa el ID de la venta, no la fila del
        # desplegable. El combo se ha construido con
        # esas filas para que el usuario elija, pero
        # el formulario busca los datos por su cuenta
        # con venta_para_contrato(): así solo hay una
        # forma de fila en toda la aplicación y ningún
        # constructor tiene que adivinar cuántas
        # columnas le pasan.

        venta = ventas[combo.currentIndex()]

        formulario = ContratoForm(self, venta[0])

        if formulario.exec():

            self.cargar_datos()

    # =============================
    # DETALLE
    # =============================

    def ver_detalle(self, fila):

        contrato = self.leer_contrato(fila)

        if contrato is None:

            return

        self.mostrar_exito(
            self.resumen_texto(contrato)
        )

    def resumen_texto(self, contrato):
        """
        El detalle completo en texto. Es lo
        mismo que muestra el PDF, para poder
        consultarlo sin generar el archivo.
        """

        lineas = [
            f"Número: {contrato['numero']}",
            f"Estado: {ESTADOS.get(contrato['estado'])}",
            "",
            "CLIENTE",
            f"  {contrato['cliente']}",
            f"  Documento: "
            f"{contrato['documento'] or 'No registrado'}",
            f"  Teléfono: "
            f"{contrato['telefono'] or 'No registrado'}",
            f"  Email: "
            f"{contrato['email'] or 'No registrado'}",
            "",
            "VEHÍCULO",
            f"  {contrato['marca']} {contrato['modelo']} "
            f"({contrato['anio']})",
            f"  Color: {contrato['color'] or 'No registrado'}",
            f"  Precio de lista: "
            f"{formato_dinero(contrato['precio_lista'])}",
            "",
            "CONDICIONES",
            f"  Fecha: {formato_fecha(contrato['fecha'])}",
            f"  Precio de venta: "
            f"{formato_dinero(contrato['precio_venta'])}",
            f"  Forma de pago: {contrato['forma_pago']}",
            f"  Anticipo: "
            f"{formato_dinero(contrato['anticipo'])}"
        ]

        cuota = cuota_importe(contrato)

        if cuota is not None:

            lineas.append(
                f"  Importe de la cuota: "
                f"{formato_dinero(cuota)} "
                f"({contrato['cantidad_cuotas']} cuotas)"
            )

        lineas.extend([
            f"  Vendedor responsable: "
            f"{contrato['vendedor']}",
            "",
            f"VENTA ASOCIADA: {contrato['venta_id']}"
        ])

        if contrato["observaciones"]:

            lineas.extend([
                "",
                "OBSERVACIONES",
                f"  {contrato['observaciones']}"
            ])

        return "\n".join(lineas)

    # =============================
    # PDF
    # =============================

    def generar_pdf_de(self, fila):

        contrato = self.leer_contrato(fila)

        if contrato is None:

            return

        try:

            ruta = generar_contrato(contrato)

        except OSError as error:

            self.mostrar_mensaje_error(
                "No se pudo escribir el archivo:\n\n"
                f"{error}"
            )

            return

        self.proteger(
            registrar_pdf,
            contrato["id"],
            ruta_relativa(contrato["numero"])
        )

        if abrir_archivo(ruta):

            self.mostrar_exito(
                f"El PDF del contrato "
                f"{contrato['numero']} se generó y se "
                f"abrió:\n\n{ruta}"
            )

            return

        self.mostrar_exito(
            f"El PDF del contrato "
            f"{contrato['numero']} se generó en:\n\n"
            f"{ruta}\n\n"
            "No se pudo abrir automáticamente: "
            "ábrelo con doble clic desde el "
            "explorador de archivos."
        )

    # =============================
    # ESTADO
    # =============================

    def cambiar_estado_de(self, fila):

        contrato = self.leer_contrato(fila)

        if contrato is None:

            return

        actual = contrato["estado"]

        permitidos = TRANSICIONES.get(actual, [])

        if not permitidos:

            self.mostrar_mensaje_error(
                f"Un contrato en estado "
                f"'{ESTADOS[actual]}' no admite más "
                "cambios.\n\n"
                "Si hay que rehacerlo, cancélelo "
                "desde la venta y cree uno nuevo."
            )

            return

        etiquetas = [
            ESTADOS[estado] for estado in permitidos
        ]

        elegida, aceptada = QInputDialog.getItem(
            self,
            "Cambiar estado del contrato",
            f"Contrato {contrato['numero']}\n"
            f"Estado actual: {ESTADOS[actual]}\n\n"
            "Nuevo estado:",
            etiquetas,
            0,
            False
        )

        if not aceptada:

            return

        nuevo = permitidos[etiquetas.index(elegida)]

        if nuevo == "cancelado" and not self.confirmar(
            "Cancelar el contrato",
            f"¿Cancelar el contrato "
            f"{contrato['numero']}?\n\n"
            "Un contrato cancelado no surte efecto, "
            "pero el registro se conserva. Podrás "
            "rehacerlo desde la venta."
        ):

            return

        resultado = self.proteger(
            cambiar_estado_db,
            contrato["id"],
            nuevo
        )

        if resultado is None:

            return

        correcto, motivo = resultado

        if not correcto:

            self.mostrar_mensaje_error(motivo)

            return

        self.mostrar_exito(
            f"El contrato {contrato['numero']} pasó "
            f"a '{ESTADOS[nuevo]}'."
        )

        self.cargar_datos()

    # =============================
    # BORRADO
    # =============================

    def eliminar_de(self, fila):

        contrato = self.leer_contrato(fila)

        if contrato is None:

            return

        if not self.confirmar_borrado(
            f"el contrato {contrato['numero']}",
            "Un contrato es un documento firmado. "
            "Si solo hay un error de forma, "
            "conviene cancelarlo en vez de "
            "borrarlo: así queda constancia."
        ):

            return

        resultado = self.proteger(
            eliminar_contrato_db,
            contrato["id"]
        )

        if resultado is None:

            return

        correcto, motivo = resultado

        if not correcto:

            self.mostrar_mensaje_error(motivo)

            return

        self.mostrar_exito(
            f"El contrato {contrato['numero']} "
            "se eliminó."
        )

        self.cargar_datos()

    # =============================
    # APOYO
    # =============================

    def leer_contrato(self, fila):
        """
        El contrato de esa fila.

        Se toma de los datos ya cargados y no
        de lo escrito en las celdas: así el PDF
        no depende de lo que se ve en pantalla,
        que puede estar recortado por el filtro
        o desactualizado.
        """

        filas = getattr(self, "filas", [])

        if fila < 0 or fila >= len(filas):

            return None

        return filas[fila]
