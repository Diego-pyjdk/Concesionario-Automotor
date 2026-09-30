from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QDateEdit,
    QPushButton,
    QTabWidget,
    QFrame
)

from PySide6.QtCore import QDate

from database.autos import (
    obtener_autos_disponibles,
    obtener_autos_sin_stock
)

from database.clientes import (
    obtener_clientes
)

from database.ventas import (
    obtener_ventas,
    obtener_total_vendido
)

from utils.helpers import (
    crear_tabla,
    celda,
    crear_titulo
)


COLUMNAS_AUTOS = [
    "ID",
    "Marca",
    "Modelo",
    "Año",
    "Precio",
    "Color",
    "Stock"
]


class ReportesView(QWidget):
    """
    Reportes de inventario, clientes y ventas.

    El filtro de fechas solo afecta a las ventas
    y al total vendido: el inventario y la lista
    de clientes son Instantes, no series de
    tiempo.
    """

    def __init__(self):
        super().__init__()

        self.crear_interfaz()
        self.cargar_datos()

    def crear_interfaz(self):

        layout_principal = QVBoxLayout()

        layout_principal.setContentsMargins(
            30, 25, 30, 25
        )

        layout_principal.setSpacing(20)

        self.setLayout(layout_principal)

        layout_principal.addWidget(
            crear_titulo("Reportes")
        )

        # ------------------------------
        # FILTROS
        # ------------------------------

        filtros = QFrame()
        filtros.setObjectName("filtros")

        layout_filtros = QHBoxLayout()
        layout_filtros.setContentsMargins(20, 15, 20, 15)
        layout_filtros.setSpacing(12)

        filtros.setLayout(layout_filtros)

        self.campo_desde = QDateEdit()

        self.campo_desde.setCalendarPopup(True)

        self.campo_desde.setDisplayFormat("dd/MM/yyyy")

        self.campo_desde.setDate(
            QDate.currentDate().addDays(-30)
        )

        self.campo_hasta = QDateEdit()

        self.campo_hasta.setCalendarPopup(True)

        self.campo_hasta.setDisplayFormat("dd/MM/yyyy")

        self.campo_hasta.setDate(
            QDate.currentDate()
        )

        boton_aplicar = QPushButton("Aplicar filtros")

        boton_aplicar.setObjectName(
            "boton_principal"
        )

        boton_aplicar.clicked.connect(
            self.aplicar_filtros
        )

        boton_limpiar = QPushButton("Restablecer")

        boton_limpiar.setObjectName(
            "boton_secundario"
        )

        boton_limpiar.clicked.connect(
            self.restablecer
        )

        layout_filtros.addWidget(QLabel("Desde:"))
        layout_filtros.addWidget(self.campo_desde)
        layout_filtros.addWidget(QLabel("Hasta:"))
        layout_filtros.addWidget(self.campo_hasta)
        layout_filtros.addWidget(boton_aplicar)
        layout_filtros.addWidget(boton_limpiar)
        layout_filtros.addStretch()

        layout_principal.addWidget(filtros)

        # ------------------------------
        # TOTALES
        # ------------------------------

        self.etiqueta_ventas = QLabel("")

        self.etiqueta_ventas.setObjectName(
            "subtitulo"
        )

        self.etiqueta_total = QLabel("")

        self.etiqueta_total.setObjectName(
            "titulo"
        )

        layout_principal.addWidget(
            self.etiqueta_ventas
        )

        layout_principal.addWidget(
            self.etiqueta_total
        )

        # ------------------------------
        # PESTAÑAS
        # ------------------------------

        self.pestanas = QTabWidget()

        # DISPONIBLES

        self.tabla_disponibles = crear_tabla(
            COLUMNAS_AUTOS
        )

        self.pestanas.addTab(
            self.tabla_disponibles,
            "Vehículos disponibles"
        )

        # SIN STOCK

        self.tabla_sin_stock = crear_tabla(
            COLUMNAS_AUTOS
        )

        self.pestanas.addTab(
            self.tabla_sin_stock,
            "Vehículos sin stock"
        )

        # CLIENTES

        self.tabla_clientes = crear_tabla(
            [
                "ID",
                "Nombre",
                "Apellido",
                "Teléfono",
                "Email"
            ]
        )

        self.pestanas.addTab(
            self.tabla_clientes,
            "Clientes"
        )

        # VENTAS

        self.tabla_ventas = crear_tabla(
            [
                "ID",
                "Fecha",
                "Cliente",
                "Vehículo",
                "Precio"
            ]
        )

        self.pestanas.addTab(
            self.tabla_ventas,
            "Ventas"
        )

        layout_principal.addWidget(
            self.pestanas
        )

    # =============================
    # FILTROS
    # =============================

    def obtener_rango(self):

        desde = self.campo_desde.date().toString(
            "yyyy-MM-dd"
        )

        hasta = self.campo_hasta.date().toString(
            "yyyy-MM-dd"
        )

        return desde, hasta

    def aplicar_filtros(self):

        self.cargar_datos()

    def restablecer(self):

        self.campo_desde.setDate(
            QDate.currentDate().addDays(-30)
        )

        self.campo_hasta.setDate(
            QDate.currentDate()
        )

        self.cargar_datos()

    # =============================
    # CARGAR
    # =============================

    def cargar_datos(self):

        desde, hasta = self.obtener_rango()

        # ------------------------------
        # INVENTARIO
        # ------------------------------
        # No depende de las fechas.
        # ------------------------------

        self.mostrar_autos(
            self.tabla_disponibles,
            obtener_autos_disponibles()
        )

        self.mostrar_autos(
            self.tabla_sin_stock,
            obtener_autos_sin_stock()
        )

        self.pestanas.setTabText(
            0,
            f"Vehículos disponibles "
            f"({self.tabla_disponibles.rowCount()})"
        )

        self.pestanas.setTabText(
            1,
            f"Vehículos sin stock "
            f"({self.tabla_sin_stock.rowCount()})"
        )

        # ------------------------------
        # CLIENTES
        # ------------------------------

        clientes = obtener_clientes()

        self.mostrar_clientes(clientes)

        self.pestanas.setTabText(
            2,
            f"Clientes ({len(clientes)})"
        )

        # ------------------------------
        # VENTAS
        # ------------------------------

        ventas = obtener_ventas(
            desde=desde,
            hasta=hasta
        )

        self.mostrar_ventas(ventas)

        total, importe = obtener_total_vendido(
            desde=desde,
            hasta=hasta
        )

        self.pestanas.setTabText(
            3,
            f"Ventas ({len(ventas)})"
        )

        plural = "venta" if total == 1 else "ventas"

        self.etiqueta_ventas.setText(
            f"Rango del {self.campo_desde.date().toString('dd/MM/yyyy')} "
            f"al {self.campo_hasta.date().toString('dd/MM/yyyy')}  ·  "
            f"{total} {plural}"
        )

        self.etiqueta_total.setText(
            f"Total vendido: $ {float(importe):,.2f}"
        )

    # =============================
    # MOSTRAR
    # =============================

    def mostrar_autos(self, tabla, autos):

        tabla.setRowCount(len(autos))

        for fila, auto in enumerate(autos):

            for columna, dato in enumerate(auto):

                centrar = columna in [0, 3, 6]

                tabla.setItem(
                    fila,
                    columna,
                    celda(dato, centrar=centrar)
                )

    def mostrar_clientes(self, clientes):

        self.tabla_clientes.setRowCount(len(clientes))

        for fila, cliente in enumerate(clientes):

            (
                id_cliente,
                nombre,
                apellido,
                telefono,
                email
            ) = cliente

            self.tabla_clientes.setItem(
                fila,
                0,
                celda(id_cliente, centrar=True)
            )

            self.tabla_clientes.setItem(
                fila,
                1,
                celda(nombre)
            )

            self.tabla_clientes.setItem(
                fila,
                2,
                celda(apellido)
            )

            self.tabla_clientes.setItem(
                fila,
                3,
                celda(telefono or "")
            )

            self.tabla_clientes.setItem(
                fila,
                4,
                celda(email or "")
            )

    def mostrar_ventas(self, ventas):

        self.tabla_ventas.setRowCount(len(ventas))

        for fila, venta in enumerate(ventas):

            (
                id_venta,
                fecha,
                cliente,
                vehiculo,
                precio
            ) = venta

            self.tabla_ventas.setItem(
                fila,
                0,
                celda(id_venta, centrar=True)
            )

            self.tabla_ventas.setItem(
                fila,
                1,
                celda(fecha, centrar=True)
            )

            self.tabla_ventas.setItem(
                fila,
                2,
                celda(cliente)
            )

            self.tabla_ventas.setItem(
                fila,
                3,
                celda(vehiculo)
            )

            self.tabla_ventas.setItem(
                fila,
                4,
                celda(f"{float(precio):,.2f}")
            )
