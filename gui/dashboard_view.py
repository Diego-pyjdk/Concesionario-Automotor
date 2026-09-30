from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame
)

from database.dashboard import (
    obtener_resumen,
    obtener_ultima_venta,
    STOCK_MINIMO
)

from database.autos import (
    obtener_autos_stock_bajo
)

from database.ventas import (
    obtener_ventas_recientes
)

from utils.helpers import (
    crear_tabla,
    celda,
    crear_titulo
)


class DashboardView(QWidget):
    """
    Panel principal. Todos los datos salen de
    MySQL; se vuelve a consultar cada vez que el
    usuario navega a Inicio.
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
            crear_titulo("Panel principal")
        )

        subtitulo = QLabel(
            "Resumen de la actividad del concesionario"
        )

        layout_principal.addWidget(subtitulo)

        # ------------------------------
        # TARJETAS
        # ------------------------------

        tarjetas_layout = QHBoxLayout()
        tarjetas_layout.setSpacing(15)

        self.tarjeta_autos = self.crear_tarjeta(
            "🚗", "Vehículos", "0"
        )

        self.tarjeta_marcas = self.crear_tarjeta(
            "🏷", "Marcas", "0"
        )

        self.tarjeta_clientes = self.crear_tarjeta(
            "👤", "Clientes", "0"
        )

        self.tarjeta_ventas = self.crear_tarjeta(
            "💰", "Ventas", "0"
        )

        tarjetas_layout.addWidget(self.tarjeta_autos)
        tarjetas_layout.addWidget(self.tarjeta_marcas)
        tarjetas_layout.addWidget(self.tarjeta_clientes)
        tarjetas_layout.addWidget(self.tarjeta_ventas)

        layout_principal.addLayout(tarjetas_layout)

        # ------------------------------
        # FILA INFERIOR
        # ------------------------------

        inferior_layout = QHBoxLayout()
        inferior_layout.setSpacing(15)

        # STOCK BAJO

        panel_stock = QFrame()
        panel_stock.setObjectName("tarjeta")

        layout_stock = QVBoxLayout()
        layout_stock.setContentsMargins(20, 18, 20, 18)
        layout_stock.setSpacing(10)

        titulo_stock = QLabel(
            f"⚠️  Vehículos con stock bajo "
            f"(≤ {STOCK_MINIMO})"
        )

        titulo_stock.setObjectName(
            "subtitulo"
        )

        layout_stock.addWidget(titulo_stock)

        self.tabla_stock = crear_tabla(
            ["Vehículo", "Stock"],
            columna_acciones=None
        )

        self.tabla_stock.setMinimumHeight(230)

        layout_stock.addWidget(self.tabla_stock)

        panel_stock.setLayout(layout_stock)

        # VENTAS RECIENTES

        panel_ventas = QFrame()
        panel_ventas.setObjectName("tarjeta")

        layout_ventas = QVBoxLayout()
        layout_ventas.setContentsMargins(20, 18, 20, 18)
        layout_ventas.setSpacing(10)

        titulo_ventas = QLabel(
            "🧾  Ventas recientes"
        )

        titulo_ventas.setObjectName(
            "subtitulo"
        )

        layout_ventas.addWidget(titulo_ventas)

        self.tabla_ventas = crear_tabla(
            ["Fecha", "Cliente", "Vehículo", "Precio"]
        )

        self.tabla_ventas.setMinimumHeight(230)

        layout_ventas.addWidget(self.tabla_ventas)

        panel_ventas.setLayout(layout_ventas)

        inferior_layout.addWidget(panel_stock)
        inferior_layout.addWidget(panel_ventas)

        layout_principal.addLayout(inferior_layout)

        # ------------------------------
        # PIE
        # ------------------------------

        self.etiqueta_pie = QLabel("")

        self.etiqueta_pie.setObjectName(
            "pie"
        )

        layout_principal.addWidget(
            self.etiqueta_pie
        )

    def crear_tarjeta(self, icono, nombre, cantidad):

        tarjeta = QFrame()
        tarjeta.setObjectName("tarjeta")

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(4)

        tarjeta.setLayout(layout)

        icono_label = QLabel(icono)
        icono_label.setObjectName("icono")

        nombre_label = QLabel(nombre)
        nombre_label.setObjectName("nombre_tarjeta")

        cantidad_label = QLabel(cantidad)
        cantidad_label.setObjectName("cantidad")

        layout.addWidget(icono_label)
        layout.addWidget(nombre_label)
        layout.addWidget(cantidad_label)

        tarjeta.cantidad_label = cantidad_label

        return tarjeta

    # =============================
    # CARGAR
    # =============================

    def cargar_datos(self):

        resumen = obtener_resumen()

        self.tarjeta_autos.cantidad_label.setText(
            str(resumen["total_autos"])
        )

        self.tarjeta_marcas.cantidad_label.setText(
            str(resumen["total_marcas"])
        )

        self.tarjeta_clientes.cantidad_label.setText(
            str(resumen["total_clientes"])
        )

        self.tarjeta_ventas.cantidad_label.setText(
            str(resumen["total_ventas"])
        )

        # ------------------------------
        # STOCK BAJO
        # ------------------------------

        stock_bajo = obtener_autos_stock_bajo(
            STOCK_MINIMO
        )

        self.mostrar_stock_bajo(stock_bajo)

        # ------------------------------
        # VENTAS RECIENTES
        # ------------------------------

        recientes = obtener_ventas_recientes(5)

        self.mostrar_ventas(recientes)

        # ------------------------------
        # PIE
        # ------------------------------

        ingresos = float(resumen["ingresos"])

        ultima_venta = obtener_ultima_venta()

        if ultima_venta:
            texto_fecha = (
                f"Última venta: {ultima_venta}"
            )
        else:
            texto_fecha = "Todavía no hay ventas"

        self.etiqueta_pie.setText(
            f"Ingresos totales: $ {ingresos:,.2f}  ·  "
            f"{texto_fecha}"
        )

    def mostrar_stock_bajo(self, autos):

        self.tabla_stock.setRowCount(len(autos))

        for fila, auto in enumerate(autos):

            (
                id_auto,
                marca,
                modelo,
                anio,
                precio,
                color,
                stock
            ) = auto

            self.tabla_stock.setItem(
                fila,
                0,
                celda(f"{marca} {modelo}")
            )

            self.tabla_stock.setItem(
                fila,
                1,
                celda(stock, centrar=True)
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
                celda(fecha, centrar=True)
            )

            self.tabla_ventas.setItem(
                fila,
                1,
                celda(cliente)
            )

            self.tabla_ventas.setItem(
                fila,
                2,
                celda(vehiculo)
            )

            self.tabla_ventas.setItem(
                fila,
                3,
                celda(f"{float(precio):,.2f}")
            )
