from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QMessageBox
)

from database.ventas import (
    obtener_ventas,
    eliminar_venta as eliminar_venta_db
)

from utils.helpers import (
    crear_tabla,
    celda,
    crear_botones_accion,
    crear_boton_principal,
    crear_titulo
)

from gui.formularios.venta_form import VentaForm


class VentasView(QWidget):

    def __init__(self):
        super().__init__()

        self.crear_interfaz()

    def crear_interfaz(self):

        layout_principal = QVBoxLayout()

        layout_principal.setContentsMargins(
            30, 25, 30, 25
        )

        layout_principal.setSpacing(20)

        self.setLayout(layout_principal)

        # ------------------------------
        # ENCABEZADO
        # ------------------------------

        encabezado = QHBoxLayout()

        encabezado.addWidget(
            crear_titulo("Ventas")
        )

        encabezado.addStretch()

        encabezado.addWidget(
            crear_boton_principal(
                "+ Nueva venta",
                self.nueva_venta
            )
        )

        layout_principal.addLayout(encabezado)

        # ------------------------------
        # TOTAL
        # ------------------------------

        self.etiqueta_total = QLabel("")

        self.etiqueta_total.setObjectName(
            "subtitulo"
        )

        layout_principal.addWidget(
            self.etiqueta_total
        )

        # ------------------------------
        # BÚSQUEDA
        # ------------------------------

        busqueda_layout = QHBoxLayout()

        self.campo_busqueda = QLineEdit()

        self.campo_busqueda.setPlaceholderText(
            "Buscar por cliente o vehículo..."
        )

        self.campo_busqueda.setFixedHeight(40)

        self.campo_busqueda.returnPressed.connect(
            self.buscar
        )

        boton_buscar = QPushButton("🔍 Buscar")

        boton_buscar.setObjectName(
            "boton_filtro"
        )

        boton_buscar.setFixedHeight(40)

        boton_buscar.clicked.connect(
            self.buscar
        )

        busqueda_layout.addWidget(
            self.campo_busqueda
        )

        busqueda_layout.addWidget(
            boton_buscar
        )

        layout_principal.addLayout(busqueda_layout)

        # ------------------------------
        # TABLA
        # ------------------------------

        self.tabla = crear_tabla(
            [
                "ID",
                "Fecha",
                "Cliente",
                "Vehículo",
                "Precio",
                "Acciones"
            ],
            columna_acciones=5,
            ancho_acciones=148
        )

        layout_principal.addWidget(self.tabla)

        # ------------------------------
        # CARGAR
        # ------------------------------

        self.cargar_datos()

    # =============================
    # NUEVA VENTA
    # =============================

    def nueva_venta(self):

        formulario = VentaForm(self)

        if formulario.exec():
            self.cargar_datos()

    # =============================
    # CARGAR VENTAS
    # =============================

    def cargar_datos(self):

        ventas = obtener_ventas()

        self.mostrar_ventas(ventas)

        # ------------------------------
        # TOTAL
        # ------------------------------

        total = sum(
            float(venta[4])
            for venta in ventas
        )

        plural = "venta" if len(ventas) == 1 else "ventas"

        self.etiqueta_total.setText(
            f"{len(ventas)} {plural} registradas  ·  "
            f"Total vendido: $ {total:,.2f}"
        )

    # =============================
    # MOSTRAR VENTAS
    # =============================

    def mostrar_ventas(self, ventas):

        self.tabla.setRowCount(len(ventas))

        for fila, venta in enumerate(ventas):

            (
                id_venta,
                fecha,
                cliente,
                vehiculo,
                precio
            ) = venta

            self.tabla.setItem(
                fila,
                0,
                celda(id_venta, centrar=True)
            )

            self.tabla.setItem(
                fila,
                1,
                celda(fecha, centrar=True)
            )

            self.tabla.setItem(
                fila,
                2,
                celda(cliente)
            )

            self.tabla.setItem(
                fila,
                3,
                celda(vehiculo)
            )

            self.tabla.setItem(
                fila,
                4,
                celda(f"{float(precio):,.2f}")
            )

            # Las ventas no se editan: solo se
            # pueden eliminar, lo que devuelve
            # la unidad al stock.

            botones = crear_botones_accion(
                lambda _, f=fila: self.ver_venta(f),
                lambda _, f=fila: self.eliminar_venta(f),
                texto_editar="Ver"
            )

            self.tabla.setCellWidget(
                fila,
                5,
                botones
            )

    # =============================
    # VER VENTA
    # =============================

    def ver_venta(self, fila):

        item_id = self.tabla.item(fila, 0)

        if not item_id:
            return

        detalle = []

        titulos = [
            "ID",
            "Fecha",
            "Cliente",
            "Vehículo",
            "Precio"
        ]

        for columna, titulo in enumerate(titulos):

            item = self.tabla.item(fila, columna)

            if item:
                detalle.append(
                    f"{titulo}: {item.text()}"
                )

        QMessageBox.information(
            self,
            "Detalle de la venta",
            "\n".join(detalle)
        )

    # =============================
    # ELIMINAR VENTA
    # =============================

    def eliminar_venta(self, fila):

        item = self.tabla.item(fila, 0)

        if not item:
            return

        id_venta = int(item.text())

        respuesta = QMessageBox.question(
            self,
            "Eliminar venta",
            "¿Eliminar esta venta?\n\n"
            "La unidad volverá al stock del "
            "vehículo.",
            QMessageBox.Yes | QMessageBox.No
        )

        if respuesta != QMessageBox.Yes:
            return

        if not eliminar_venta_db(id_venta):
            QMessageBox.warning(
                self,
                "No se pudo eliminar",
                "La venta no se pudo eliminar."
            )

            return

        self.cargar_datos()

    # =============================
    # BUSCAR VENTA
    # =============================

    def buscar(self):

        texto = self.campo_busqueda.text().strip()

        if not texto:
            self.cargar_datos()
            return

        self.mostrar_ventas(
            obtener_ventas(texto=texto)
        )
