from gui.seguimiento_dialog import SeguimientoDialog
from PySide6.QtWidgets import QGridLayout, QFrame
# ==========================================
# CARTERA: CUENTAS POR COBRAR
# ==========================================
# La pantalla de trabajo de la cobranza.
#
# No es un listado más: tiene CUATRO pestañas porque
# la pregunta que se hace el cobrador cambia según el
# momento del día.
#
#   Por cobrar   quién debe y desde cuándo. La lista
#                de trabajo completa, ordenada por
#                retraso y no por importe.
#
#   Vencidas     lo que ya pasó su fecha. Es lo que no
#                puede esperar, y sale marcado.
#
#   Por vencer   lo que vence pronto. Cobrar antes de
#                la fecha no obliga a discutir nada, y
#                por eso merece su propia lista.
#
#   Antigüedad   la cartera por tramos de retraso. El
#                total no dice si hay un problema o
#                muchos pequeños.
#
# Y las cuotas vencidas salen de la MISMA
# fuente que la cartera, no de un segundo sitio: si
# el contrato dice que debe y la cuota dice que no,
# alguien tiene que poder explicar por qué.


from decimal import Decimal

from PySide6.QtWidgets import (
    QLabel,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QComboBox
)

import database.cobranza as cobranza
import database.financiera as financiera

# El plazo por defecto de "por vencer" vive en database.financiera.
# Se importa también suelto porque el combo de la pantalla lo usa
# como valor de repuesto cuando el texto tecleado no es un número:
# sin este import, esa línea era un NameError y tumbaba la
# pestaña entera.

from database.financiera import DIAS_AVISO_POR_DEFECTO

from permisos import (
    tiene_permiso,
    GESTIONAR_FINANCIERA
)

from utils.helpers import (
    celda,
    crear_tabla,
    crear_botones_accion,
    crear_boton_secundario,
    crear_titulo,
    ancho_acciones_para
)

from utils.moneda import formato_dinero

from gui.vista_base import VistaBase
from gui.contrato_detalle_dialog import (
    ContratoDetalleDialog
)
from gui.formularios.pago_adelantado_form import (
    PagoAdelantadoForm
)
from gui.formularios.pago_cuota_form import (
    PagoCuotaForm
)


# ==========================================
# TONOS DE ESTADO
# ==========================================
# Los nombres de TONOS_CELDA, no unos colores
# propios.
#
# Poner el color de cada vista por su cuenta suena a
# más libertad y acaba con cuatro pantallas que casan
# casi pero no, donde el mismo rojo es un tono más
# oscuro en cada sitio. Los tonos viven en
# utils/helpers.py y quien cambia uno los cambia en
# todas partes.

TONO = {
    "vencido": "tono_peligro",
    "por_vencer": "tono_aviso",
    "al_dia": "tono_ok"
}

# ------------------------------
# POSICIONES Y ANCHOS
# ------------------------------
# En vez de "columna 5" y "siete botones de 80", los
# números van con nombre. La columna de acciones de
# las dos tablas de cuotas es la misma y su ancho el
# mismo, así que comparten las constantes.

COLUMNA_ACCIONES_CARTERA = 8

CENTRAR_CARTERA = {0, 4, 5, 6, 7}

COLUMNA_ACCIONES_CUOTA = 7

CENTRAR_CUOTA = {3, 5, 6}

# ------------------------------
# LOS ANCHOS DE LOS BOTONES
# ------------------------------
# MEDIDOS con la hoja de estilos puesta, que es como
# los mide `QPushButton.sizeHint()`:
#
#   "Adelantado"  112
#   "Cobrar"       68
#   "Ver"          35
#
# Se mide CON la hoja a proposito: sin ella Qt mide con
# la fuente por defecto y con su relleno, y "Adelantado"
# pide 134 en vez de 112. Arreglar los anchos con esa
# medicion los deja mas anchos de lo necesario, que es
# inofensivo; al reves, si quedan cortos.
#
# Los tres estaban mas estrechos de lo que necesitan y
# el texto salia cortado. En una columna de acciones un
# texto a medias no se sabe si es "Adelantado" o
# "Adelanta", y el boton de cobrar no es un adorno:
# decide de quien es el dinero.
#
# `test_los_botones_no_se_recortan` los comprueba uno a
# uno en todas las tablas de la aplicacion, asi que un
# texto nuevo sale ahi y no en una pantalla.

ANCHO_COBRAR = 72

ANCHO_VER = 56

ANCHO_ADELANTADO = 116

# Calculado, no puesto a mano (ver utils/helpers.py).
#
# El ancho se calcula con los TRES botones, aunque el
# rol que no cobra solo vea dos: la columna es la
# misma para todos, y si se calculara según el permiso
# las tablas no casarían al cambiar de sección.

ANCHO_ACCIONES_CARTERA = ancho_acciones_para([
    ANCHO_ADELANTADO,
    ANCHO_COBRAR,
    ANCHO_VER
])

ANCHO_ACCIONES_CUOTA = ancho_acciones_para([
    ANCHO_COBRAR
])


class CarteraView(VistaBase):

    titulo = "Cartera"

    def __init__(self, parent=None):
        super().__init__(parent)

        self.puede_gestionar = tiene_permiso(
            GESTIONAR_FINANCIERA
        )

        self.crear_interfaz()

        # ------------------------------
        # LAS VENCIDAS SE MARCAN AL ABRIR
        # ------------------------------
        # No hay ningún proceso de fondo que revise
        # las cuotas cada noche: se revisan aquí, al
        # abrir la cartera.
        #
        # Basta porque vencida es un estado derivado
        # de la fecha: no cambia por sí sola hasta que
        # alguien mira, y la cartera se mira todos los
        # días. Un proceso de fondo solo añadiría una
        # cosa que puede romperse sin que nadie lo note.

        self.proteger(financiera.procesar_vencidas)

        if not self.carga_asincrona:
            self.recargar()

    # =============================
    # INTERFAZ
    # =============================

    @property
    def texto_cobrar(self):
        """
        "Cobrar" o "Ver", según lo que el rol pueda
        hacer.

        El botón dice la verdad: poner "Cobrar" en una
        tabla donde el clic no cobra es peor que no
        ponerlo, porque el usuario descubre el permiso
        cuando ya está delante del cliente.
        """

        return (
            "Cobrar"
            if self.puede_gestionar
            else "Ver"
        )

    def crear_interfaz(self):

        layout = QVBoxLayout()

        layout.setSpacing(12)

        layout.addWidget(crear_boton_secundario('Agenda de cobranza', self.abrir_seguimiento))
        layout.addWidget(crear_titulo(
            "Cartera y cobranza"
        ))

        # ------------------------------
        # RESUMEN
        # ------------------------------
        # Arriba, el número. Abajo están los nombres.
        # Quien entra aquí quiere saber primero cuánto
        # hay que cobrar y cuánto está atrasado, antes
        # de leer una tabla.

        self.etiquetas = {}

        self.tarjetas = QWidget()

        layout_tarjetas = QGridLayout()

        layout_tarjetas.setContentsMargins(0, 0, 0, 0)

        layout_tarjetas.setSpacing(6)

        self.tarjetas.setLayout(layout_tarjetas)

        for clave, titulo in (
            ("contratos", "Contratos"),
            ("saldo", "Total por cobrar"),
            ("vencido", "Vencido"),
            ("importe_vencido", "Importe vencido"),
            ("por_vencer", "Sin vencer aún"),
            ("dias_promedio", "Retraso medio")
        ):

            etiqueta = QLabel(f"{titulo}: —")

            etiqueta.setObjectName("tile_valor")

            self.etiquetas[clave] = etiqueta

            marco = QFrame()
            marco.setObjectName('tile')
            contenido = QVBoxLayout(marco)
            nombre = QLabel(titulo)
            nombre.setObjectName('tile_nombre')
            etiqueta.setWordWrap(True)
            contenido.addWidget(nombre)
            contenido.addWidget(etiqueta)
            indice = len(self.etiquetas) - 1
            layout_tarjetas.addWidget(marco, indice // 3, indice % 3)

        layout.addWidget(self.tarjetas)

        # ------------------------------
        # PESTAÑAS
        # ------------------------------

        self.pestanas = QTabWidget()

        self.pestanas.addTab(
            self.crear_panel_por_cobrar(),
            "Por cobrar"
        )

        self.pestanas.addTab(
            self.crear_panel_vencidas(),
            "Vencidas"
        )

        self.pestanas.addTab(
            self.crear_panel_por_vencer(),
            "Por vencer"
        )

        self.pestanas.addTab(
            self.crear_panel_antiguedad(),
            "Antigüedad"
        )

        layout.addWidget(self.pestanas)

        self.setLayout(layout)

    def abrir_seguimiento(self):
        SeguimientoDialog(self).exec()

    def crear_panel_por_cobrar(self):

        panel = QWidget()

        layout = QVBoxLayout()

        layout.setContentsMargins(0, 0, 0, 0)

        # ------------------------------
        # "Acciones" VA EN LA LISTA
        # ------------------------------
        # `crear_tabla()` no añade la columna de
        # acciones: solo le pone el ancho fijo. Si el
        # índice queda fuera de la lista, la columna no
        # existe, `setCellWidget()` no pone nada y los
        # botones NO SE VEN, sin error ni aviso. Por eso
        # la lista llega hasta `columna_acciones`.

        self.tabla = crear_tabla(
            [
                "Contrato",
                "Cliente",
                "Vehículo",
                "Teléfono",
                "Saldo",
                "Vencido",
                "Retraso",
                "Próximo",
                "Acciones"
            ],
            columna_acciones=8,
            ancho_acciones=ANCHO_ACCIONES_CARTERA
        )

        cabecera = self.tabla.horizontalHeader()

        for indice in (4, 5):

            cabecera.setSectionResizeMode(
                indice,
                QHeaderView.ResizeToContents
            )

        cabecera.setSectionResizeMode(
            1, QHeaderView.Stretch
        )

        self.etiqueta_pie = QLabel("")

        self.etiqueta_pie.setObjectName("pie")

        layout.addWidget(self.tabla)

        layout.addWidget(self.etiqueta_pie)

        panel.setLayout(layout)

        return panel

    def crear_panel_vencidas(self):

        panel = QWidget()

        layout = QVBoxLayout()

        layout.setContentsMargins(0, 0, 0, 0)

        self.tabla_vencidas = crear_tabla(
            [
                "Contrato",
                "Cliente",
                "Teléfono",
                "Cuota",
                "Vencía",
                "Saldo cuota",
                "Días",
                "Acciones"
            ],
            columna_acciones=7,
            ancho_acciones=ANCHO_ACCIONES_CUOTA
        )

        self.etiqueta_pie_vencidas = QLabel("")

        self.etiqueta_pie_vencidas.setObjectName("pie")

        layout.addWidget(self.tabla_vencidas)

        layout.addWidget(self.etiqueta_pie_vencidas)

        panel.setLayout(layout)

        return panel

    def crear_panel_por_vencer(self):

        panel = QWidget()

        layout = QVBoxLayout()

        layout.setContentsMargins(0, 0, 0, 0)

        self.campo_dias_aviso = QComboBox()

        self.campo_dias_aviso.addItems([
            "7", "15", "30", "60", "90"
        ])

        ajustes = financiera.leer_ajustes()

        self.campo_dias_aviso.setCurrentText(
            str(ajustes["dias_aviso"])
        )

        self.campo_dias_aviso.currentTextChanged.connect(
            lambda _: self.pintar_por_vencer()
        )

        fila = QLabel("Vencen en los próximos:")

        fila.setObjectName("etiqueta_filtro")

        layout.addWidget(fila)

        layout.addWidget(self.campo_dias_aviso)

        self.tabla_por_vencer = crear_tabla(
            [
                "Contrato",
                "Cliente",
                "Teléfono",
                "Cuota",
                "Vence",
                "Saldo cuota",
                "Días",
                "Acciones"
            ],
            columna_acciones=7,
            ancho_acciones=ANCHO_ACCIONES_CUOTA
        )

        self.etiqueta_pie_por_vencer = QLabel("")

        self.etiqueta_pie_por_vencer.setObjectName("pie")

        layout.addWidget(self.tabla_por_vencer)

        layout.addWidget(self.etiqueta_pie_por_vencer)

        panel.setLayout(layout)

        return panel

    def crear_panel_antiguedad(self):

        panel = QWidget()

        layout = QVBoxLayout()

        layout.setContentsMargins(0, 0, 0, 0)

        # Esta tabla no lleva botones: es un resumen de
        # tramos, no una lista de trabajo. Sin
        # `columna_acciones` para no pasar un índice
        # que no existe.

        self.tabla_antiguedad = crear_tabla(
            ["Tramo", "Contratos", "Importe"]
        )

        self.etiqueta_concentracion = QLabel("")

        self.etiqueta_concentracion.setObjectName("pie")

        self.etiqueta_concentracion.setWordWrap(True)

        layout.addWidget(crear_boton_secundario(
            "Actualizar",
            self.recargar
        ))

        layout.addWidget(self.tabla_antiguedad)

        layout.addWidget(self.etiqueta_concentracion)

        panel.setLayout(layout)

        return panel

    # =============================
    # DATOS
    # =============================

    def cargar_datos(self):
        self.recargar()

    def recargar(self):
        if self.carga_asincrona and self.cache_consultas is None:
            dias = self.campo_dias_aviso.currentText().strip()
            dias = int(dias) if dias.isdigit() else DIAS_AVISO_POR_DEFECTO
            consultas = [(cobranza.resumen_cartera, (), {}), (cobranza.cuentas_por_cobrar, (), {}),
                (cobranza.cuotas_vencidas, (), {}), (cobranza.cuotas_por_vencer, (dias,), {}),
                (cobranza.envejecer_cartera, (), {}), (cobranza.concentracion_cartera, (), {})]
            self.consultar_lote(consultas, self.recargar)
            return
        self.pintar_resumen()

        self.pintar_por_cobrar()

        self.pintar_vencidas()

        self.pintar_por_vencer()

        self.pintar_antiguedad()

    def pintar_resumen(self):

        resumen = self.proteger(cobranza.resumen_cartera)

        if not resumen:

            return

        def numero(valor):
            """
            Un entero sin decimales cuando es
            redondo. "12 contratos" se lee mejor que
            "12.00 contratos", y "3 vencidas" mejor
            que "3.00".
            """

            try:

                valor = float(valor)

            except (TypeError, ValueError):

                return "—"

            return (
                f"{valor:,.0f}"
                if valor == int(valor)
                else f"{valor:,.1f}"
            )

        textos = {
            "contratos": (
                f"{resumen['contratos']} contrato(s) con "
                f"saldo pendiente"
            ),
            "saldo": (
                f"Total por cobrar: "
                f"{formato_dinero(resumen['saldo_total'])}"
            ),
            "vencido": (
                f"Con cuotas vencidas: "
                f"{resumen['clientes_vencidos']} cliente(s), "
                f"{formato_dinero(resumen['vencido'])}"
            ),
            "importe_vencido": (
                f"Importe vencido: "
                f"{formato_dinero(resumen['importe_vencido'])}"
            ),
            "por_vencer": (
                f"Todavía sin vencer: "
                f"{formato_dinero(resumen['por_vencer'])}"
            ),
            "dias_promedio": (
                f"Retraso medio: "
                f"{numero(resumen['dias_promedio'])} día(s)"
            )
        }

        for clave, texto in textos.items():

            self.etiquetas[clave].setText(texto)

    def pintar_por_cobrar(self):

        filas = self.proteger(
            cobranza.cuentas_por_cobrar
        )

        if filas is None:

            return

        self.tabla.setRowCount(len(filas))

        for indice, fila in enumerate(filas):

            cliente = (
                f"{fila['cliente_nombre']} "
                f"{fila['cliente_apellido']}"
            )

            vehiculo = f"{fila['marca']} {fila['modelo']}"

            valores = [
                fila["numero"],
                cliente,
                vehiculo,
                fila["cliente_telefono"] or "—",
                formato_dinero(fila["saldo"]),
                formato_dinero(fila["importe_vencido"]),
                (
                    f"{fila['dias_atraso']} d."
                    if fila["dias_atraso"] > 0
                    else "—"
                ),
                (
                    fila["proximo_vencimiento"].isoformat()
                    if fila["proximo_vencimiento"]
                    else "—"
                )
            ]

            # ------------------------------
            # EL TONO VA POR FILA ENTERA
            # ------------------------------
            # Marcar solo las columnas 5 y 6 haría
            # que el saldo pareciera un aviso
            # suelto en medio de una fila normal.
            # Esto es una lista de trabajo: lo
            # urgente tiene que leerse de un
            # vistazo, y un color por celda hay que
            # buscarlo.

            tono = TONO["al_dia"]

            if fila["dias_atraso"] > 0:

                tono = TONO["por_vencer"]

            if fila["cuotas_vencidas"] > 0:

                tono = TONO["vencido"]

            for columna, valor in enumerate(valores):

                self.tabla.setItem(
                    indice,
                    columna,
                    celda(
                        valor,
                        centrar=columna in CENTRAR_CARTERA,
                        objeto=tono
                    )
                )

            # ------------------------------
            # ACCIONES
            # ------------------------------
            # El id del contrato se captura POR
            # VALOR. La callback de
            # crear_botones_accion() recibe el
            # índice de la fila, no el contrato, y
            # las dos cosas no tienen nada que
            # ver: la tabla viene ordenada por
            # retraso, así que la fila 0 puede ser
            # el contrato 88 y la fila 3 el 12.

            self.tabla.setCellWidget(
                indice,
                COLUMNA_ACCIONES_CARTERA,
                self.crear_botones_cartera(
                    fila["contrato_id"]
                )
            )

        plural = (
            "contrato" if len(filas) == 1 else "contratos"
        )

        self.etiqueta_pie.setText(
            f"{len(filas)} {plural} por cobrar  ·  "
            "ordenado por retraso: lo más atrasado "
            "va primero"
        )

    def crear_botones_cartera(self, contrato_id):
        """
        Tres botones si se puede cobrar, uno si no.

        "Cobrar" es la cuota más antigua, que es lo que
        se cobra casi siempre. "Adelantado" es el caso
        de quien paga dos meses seguidos de una vez, y
        va primero porque desde la cartera, que está
        ordenada por retraso, es la pregunta que se
        hace el cajero: "y si este señor quiere dejar
        pagado el mes que viene?"

        Y no se puede resolver con el mismo botón: un
        cobro de una cuota NO admite más que el saldo
        de esa cuota, así que meter 20.000 ahí daría
        error de "mayor que el saldo". Hace falta otro
        camino.

        ------------------------------
        # EL OBJECTNAME DE LOS EXTRAS
        # ------------------------------

        Los tres van con "boton_editar", que es lo que
        usan "Ver" y "Contrato" en Ventas y Contratos.

        Sin `objectName` un QPushButton cae en la regla
        base de la hoja, que es la de la BARRA LATERAL:
        13 px, relleno de 10x14 y texto a la izquierda.
        Los botones salían como elementos de menú, con
        otro cuerpo y otro color, y medían 112 px en vez
        de 68. Con `objectName` se miden bien y se ven
        como lo que son.
        """

        if not self.puede_gestionar:

            return crear_botones_accion(
                al_editar=(
                    lambda _, c=contrato_id:
                    self.abrir_detalle(c)
                ),
                al_eliminar=None,
                texto_editar="Ver",
                mostrar_eliminar=False,
                ancho_editar=ANCHO_VER
            )

        return crear_botones_accion(
            al_editar=(
                lambda _, c=contrato_id:
                self.cobrar_adelantado(c)
            ),
            texto_editar="Adelantado",
            al_eliminar=None,
            mostrar_eliminar=False,
            acciones_extra=[
                (
                    "Cobrar",
                    lambda _, c=contrato_id:
                    self.cobrar_contrato(c),
                    "boton_editar",
                    ANCHO_COBRAR
                ),
                (
                    "Ver",
                    lambda _, c=contrato_id:
                    self.abrir_detalle(c),
                    "boton_editar",
                    ANCHO_VER
                )
            ],
            ancho_editar=ANCHO_ADELANTADO
        )

    def pintar_vencidas(self):

        filas = self.proteger(cobranza.cuotas_vencidas)

        if filas is None:

            return

        self.tabla_vencidas.setRowCount(len(filas))

        for indice, cuota in enumerate(filas):

            valores = [
                cuota["contrato_numero"],
                cuota["cliente"],
                cuota["telefono"] or "—",
                f"{cuota['numero']}",
                cuota["fecha_vencimiento"].isoformat(),
                formato_dinero(cuota["saldo"]),
                f"{cuota['dias_atraso']} d."
            ]

            for columna, valor in enumerate(valores):

                self.tabla_vencidas.setItem(
                    indice,
                    columna,
                    celda(
                        valor,
                        centrar=columna in CENTRAR_CUOTA,
                        objeto=TONO["vencido"]
                    )
                )

            self.tabla_vencidas.setCellWidget(
                indice,
                COLUMNA_ACCIONES_CUOTA,
                crear_botones_accion(
                    al_editar=(
                        lambda _, c=cuota:
                        self.cobrar_cuota(c["id"])
                    ),
                    texto_editar=self.texto_cobrar,
                    al_eliminar=None,
                    mostrar_eliminar=False,
                    ancho_editar=ANCHO_COBRAR
                )
            )

        plural = "cuota" if len(filas) == 1 else "cuotas"

        self.etiqueta_pie_vencidas.setText(
            f"{len(filas)} {plural} vencida(s) con saldo"
        )

    def pintar_por_vencer(self):

        dias = self.campo_dias_aviso.currentText().strip()

        if not dias.isdigit():

            dias = str(DIAS_AVISO_POR_DEFECTO)

        filas = self.proteger(
            cobranza.cuotas_por_vencer,
            int(dias)
        )

        if filas is None:

            return

        self.tabla_por_vencer.setRowCount(len(filas))

        for indice, cuota in enumerate(filas):

            valores = [
                cuota["contrato_numero"],
                cuota["cliente"],
                cuota["telefono"] or "—",
                f"{cuota['numero']}",
                cuota["fecha_vencimiento"].isoformat(),
                formato_dinero(cuota["saldo"]),
                (
                    f"en {cuota['dias_para_vencer']} d."
                    if cuota["dias_para_vencer"] >= 0
                    else "tarde"
                )
            ]

            for columna, valor in enumerate(valores):

                self.tabla_por_vencer.setItem(
                    indice,
                    columna,
                    celda(
                        valor,
                        centrar=columna in CENTRAR_CUOTA,
                        objeto=TONO["por_vencer"]
                    )
                )

            self.tabla_por_vencer.setCellWidget(
                indice,
                COLUMNA_ACCIONES_CUOTA,
                crear_botones_accion(
                    al_editar=(
                        lambda _, c=cuota:
                        self.cobrar_cuota(c["id"])
                    ),
                    texto_editar=self.texto_cobrar,
                    al_eliminar=None,
                    mostrar_eliminar=False,
                    ancho_editar=ANCHO_COBRAR
                )
            )

        plural = "cuota" if len(filas) == 1 else "cuotas"

        self.etiqueta_pie_por_vencer.setText(
            f"{len(filas)} {plural} vence(n) en {dias} días"
        )

    def pintar_antiguedad(self):

        tramos = self.proteger(cobranza.envejecer_cartera)

        if tramos is None:

            return

        self.tabla_antiguedad.setRowCount(len(tramos))

        for indice, tramo in enumerate(tramos):

            # ------------------------------
            # EL ÚLTIMO TRAMO VA MARCADO
            # ------------------------------
            # Una deuda con seis meses casi
            # siempre necesita otra gestión:
            # convenio, garantía, venta de
            # cartera. Es el único dato de esta
            # tabla que pide una decisión, así
            # que es el único que se destaca.

            ultimo = indice == len(tramos) - 1

            tono = None

            if ultimo and tramo["contratos"]:

                tono = TONO["vencido"]

            valores = [
                tramo["etiqueta"],
                f"{tramo['contratos']}",
                formato_dinero(tramo["importe"])
            ]

            for columna, valor in enumerate(valores):

                self.tabla_antiguedad.setItem(
                    indice,
                    columna,
                    celda(
                        valor,
                        centrar=columna in {1, 2},
                        objeto=tono
                    )
                )

        principales, porcentaje = self.proteger(
            cobranza.concentracion_cartera
        )

        if principales and porcentaje:

            nombres = ", ".join(
                f"{p['cliente']} ({p['porcentaje']:.0f} %)"
                for p in principales[:3]
            )

            self.etiqueta_concentracion.setText(
                f"Los {len(principales)} deudores más "
                f"grandes concentran el {porcentaje} % de "
                f"la cartera: {nombres}"
            )

        else:

            self.etiqueta_concentracion.setText(
                "No hay deuda pendiente."
            )

    # =============================
    # ACCIONES
    # =============================

    def abrir_detalle(self, contrato_id):
        """
        Abre el detalle completo del contrato.
        """

        self.proteger(
            lambda: ContratoDetalleDialog(
                self, contrato_id
            ).exec()
        )

    def cobrar_contrato(self, contrato_id):
        """
        Cobrar la cuota más antigua sin pagar del
        contrato.

        La más antigua, no la primera: una cuota de
        hace cuatro meses no se salta porque delante
        haya otra de mañana. Y la que tiene saldo, no
        la número 1: si la primera está anulada, la
        siguiente es la que se cobra.
        """

        cuotas = self.proteger(
            financiera.obtener_cuotas, contrato_id
        )

        if not cuotas:

            return

        pendiente = next(
            (
                c for c in cuotas
                if Decimal(str(c["saldo"])) > 0
                and c["estado"] != (
                    financiera.ESTADO_ANULADA
                )
            ),
            None
        )

        if not pendiente:

            self.mostrar_mensaje_error(
                "Este contrato no tiene cuotas pendientes."
            )

            return

        self.cobrar_cuota(pendiente["id"])

    def cobrar_cuota(self, id_cuota):
        """
        Abre el formulario de cobro de una cuota.

        Sin permiso de cobro se abre el detalle: el
        botón se pone "Ver" en vez de "Cobrar" para
        que el texto diga la verdad, pero el camino
        tiene que llevar a algún sitio.
        """

        if not self.puede_gestionar:

            self.abrir_detalle_de_cuota(id_cuota)

            return

        formulario = self.proteger(
            lambda: PagoCuotaForm(self, id_cuota)
        )

        if not formulario:

            return

        if formulario.exec():

            self.recargar()

    def abrir_detalle_de_cuota(self, id_cuota):
        """
        Ver una cuota sin cobrarla.
        """

        cuota = self.proteger(financiera.obtener_cuota, id_cuota)

        if not cuota:

            return

        self.abrir_detalle(cuota["contrato_id"])

    def cobrar_adelantado(self, contrato_id):
        """
        Cobrar varias cuotas seguidas de una vez.

        Desde la cartera, sin abrir el detalle: el
        cajero ve la fila, la cobra y sigue. Abrir el
        detalle para esto serían tres clics y una
        pantalla de más para escribir un número que
        ya sabe.
        """

        if not self.puede_gestionar:

            self.abrir_detalle(contrato_id)

            return

        formulario = self.proteger(
            lambda: PagoAdelantadoForm(
                self, contrato_id
            )
        )

        if not formulario:

            return

        if formulario.exec():

            self.recargar()

            if formulario.recibos:

                # Un solo recibo para todo el cobro, y
                # el mismo para las N partes: se le
                # enseña al cajero para que lo entregue
                # en mano, que es como se va de aquí.

                QMessageBox.information(
                    self,
                    "Cobro adelantado registrado",
                    f"Se han cubierto "
                    f"{len(formulario.recibos)} cuota(s)."
                    f"\n\nRecibo: {formulario.recibos[0]}"
                )
