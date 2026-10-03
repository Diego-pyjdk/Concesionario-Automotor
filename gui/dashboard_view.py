# ==========================================
# PANEL PRINCIPAL
# ==========================================
# Todas las cifras salen de database/reportes.py.
# Aquí no se calcula nada: se consulta una vez y
# se pinta.
#
# El vendedor entra a este panel (VER_TABLERO),
# así que no puede usar consultas que pidan
# VER_REPORTES. De ahí que obtener_resumen() y
# las estadísticas del día y del mes permitan
# TABLERO y el detalle de reportes no.
# ==========================================


from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QStackedWidget
)

from database.reportes import (
    obtener_resumen,
    obtener_ultima_venta,
    obtener_ventas_del_dia,
    obtener_ventas_del_mes,
    obtener_top_vehiculos,
    obtener_ventas_por_cliente
)

from database.configuracion import obtener_stock_minimo

from database.ventas import obtener_ventas_recientes

from utils.helpers import (
    crear_tabla,
    crear_titulo,
    crear_estado_vacio,
    celda
)

from utils.moneda import (
    formato_dinero,
    formatear_numero
)

from gui.vista_base import VistaBase


class DashboardView(VistaBase):

    def __init__(self):
        super().__init__()

        self.crear_interfaz()

        self.cargar_datos()

    # =============================
    # INTERFAZ
    # =============================

    def crear_interfaz(self):

        layout = QVBoxLayout()

        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(18)

        self.setLayout(layout)

        layout.addWidget(
            crear_titulo("Panel principal")
        )

        self.etiqueta_subtitulo = QLabel("")

        self.etiqueta_subtitulo.setObjectName(
            "subtitulo"
        )

        layout.addWidget(
            self.etiqueta_subtitulo
        )

        # ------------------------------
        # CIFRAS PRINCIPALES
        # ------------------------------

        tarjetas = QHBoxLayout()
        tarjetas.setSpacing(15)

        self.tarjeta_autos = self.crear_tarjeta(
            "🚗", "Vehículos"
        )

        self.tarjeta_clientes = self.crear_tarjeta(
            "👤", "Clientes"
        )

        self.tarjeta_ventas = self.crear_tarjeta(
            "💰", "Ventas"
        )

        self.tarjeta_marcas = self.crear_tarjeta(
            "🏷", "Marcas"
        )

        tarjetas.addWidget(self.tarjeta_autos)
        tarjetas.addWidget(self.tarjeta_clientes)
        tarjetas.addWidget(self.tarjeta_ventas)
        tarjetas.addWidget(self.tarjeta_marcas)

        layout.addLayout(tarjetas)

        # ------------------------------
        # CIFRAS DEL PERÍODO
        # ------------------------------

        tiles = QHBoxLayout()
        tiles.setSpacing(15)

        self.tile_hoy = self.crear_tile("Ventas de hoy")
        self.tile_mes = self.crear_tile("Ventas del mes")
        self.tile_total = self.crear_tile("Total vendido")
        self.tile_stock = self.crear_tile("Stock bajo")

        tiles.addWidget(self.tile_hoy)
        tiles.addWidget(self.tile_mes)
        tiles.addWidget(self.tile_total)
        tiles.addWidget(self.tile_stock)

        layout.addLayout(tiles)

        # ------------------------------
        # TABLAS
        # ------------------------------

        paneles = QHBoxLayout()
        paneles.setSpacing(15)

        self.panel_ventas = self.crear_panel(
            "🧾  Últimas ventas",
            ["Fecha", "Cliente", "Vehículo", "Precio"],
            vacio="Sin ventas registradas"
        )

        self.panel_top = self.crear_panel(
            "🏆  Vehículos más vendidos",
            ["Vehículo", "Unidades", "Importe"],
            anchos_fijos={1: 80},
            vacio="Sin ventas registradas"
        )

        self.panel_clientes = self.crear_panel(
            "👥  Clientes con más compras",
            ["Cliente", "Compras", "Importe"],
            anchos_fijos={1: 80},
            vacio="Sin compras registradas"
        )

        # "Últimas ventas" tiene cuatro columnas y
        # las otras dos tres, así que se le da más
        # ancho: con partes iguales, Cliente y
        # Vehículo quedaban con unos pocos píxeles y
        # mostraban solo puntos suspensivos.

        paneles.addWidget(self.panel_ventas, 4)
        paneles.addWidget(self.panel_top, 3)
        paneles.addWidget(self.panel_clientes, 3)

        layout.addLayout(paneles)

        # ------------------------------
        # PIE
        # ------------------------------

        self.etiqueta_pie = QLabel("")

        self.etiqueta_pie.setObjectName("pie")

        layout.addWidget(self.etiqueta_pie)

    def crear_tarjeta(self, icono, nombre):

        tarjeta = QFrame()
        tarjeta.setObjectName("tarjeta")

        lay = QVBoxLayout()
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(2)

        tarjeta.setLayout(lay)

        etiqueta_icono = QLabel(icono)
        etiqueta_icono.setObjectName("icono")

        etiqueta_nombre = QLabel(nombre)
        etiqueta_nombre.setObjectName("nombre_tarjeta")

        etiqueta_cantidad = QLabel("—")
        etiqueta_cantidad.setObjectName("cantidad")

        lay.addWidget(etiqueta_icono)
        lay.addWidget(etiqueta_nombre)
        lay.addWidget(etiqueta_cantidad)

        tarjeta.cantidad_label = etiqueta_cantidad

        return tarjeta

    def crear_tile(self, nombre):

        marco = QFrame()
        marco.setObjectName("tile")

        lay = QVBoxLayout()
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(2)

        marco.setLayout(lay)

        etiqueta_nombre = QLabel(nombre)
        etiqueta_nombre.setObjectName("tile_nombre")

        etiqueta_valor = QLabel("—")
        etiqueta_valor.setObjectName("tile_valor")

        lay.addWidget(etiqueta_nombre)
        lay.addWidget(etiqueta_valor)

        marco.valor_label = etiqueta_valor

        return marco

    def crear_panel(
        self,
        titulo,
        columnas,
        anchos_fijos=None,
        vacio="Sin datos"
    ):
        """
        Tabla con título y estado vacío propio:
        un QStackedWidget alterna entre ambas.
        """

        marco = QFrame()
        marco.setObjectName("tarjeta")

        lay = QVBoxLayout()
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        marco.setLayout(lay)

        etiqueta_titulo = QLabel(titulo)
        etiqueta_titulo.setObjectName("subtitulo")

        lay.addWidget(etiqueta_titulo)

        contenedor = QStackedWidget()

        tabla = crear_tabla(
            columnas,
            anchos_fijos=anchos_fijos
        )

        tabla.setMinimumHeight(200)

        contenedor.addWidget(tabla)
        contenedor.addWidget(crear_estado_vacio(vacio))

        lay.addWidget(contenedor)

        marco.tabla = tabla
        marco.contenedor = contenedor

        return marco

    # =============================
    # DATOS
    # =============================

    def cargar_datos(self):
        """
        Una pasada: consulta y pinta.

        El resumen se pide UNA vez y se reparte
        entre tarjetas, mosaicos y pie: pedirlo
        tres veces serían tres viajes a MySQL
        para el mismo dato.
        """

        resumen = self.proteger(obtener_resumen)

        self.cargar_tarjetas(resumen)
        self.cargar_tiles(resumen)
        self.cargar_tablas()
        self.cargar_pie()

    def cargar_tarjetas(self, resumen):

        if resumen is None:

            return

        self.tarjeta_autos.cantidad_label.setText(
            str(resumen["total_autos"])
        )

        self.tarjeta_clientes.cantidad_label.setText(
            str(resumen["total_clientes"])
        )

        self.tarjeta_ventas.cantidad_label.setText(
            str(resumen["total_ventas"])
        )

        self.tarjeta_marcas.cantidad_label.setText(
            str(resumen["total_marcas"])
        )

        self.etiqueta_subtitulo.setText(
            f"{resumen['unidades']} unidades en "
            f"inventario  ·  "
            f"{resumen['sin_stock']} vehículo(s) sin stock"
        )

    def cargar_tiles(self, resumen):

        hoy = self.proteger(obtener_ventas_del_dia)

        if hoy is not None:

            total, importe = hoy

            self.tile_hoy.valor_label.setText(
                f"{total}  ·  {self.dinero(importe)}"
            )

        mes = self.proteger(obtener_ventas_del_mes)

        if mes is not None:

            total, importe = mes

            self.tile_mes.valor_label.setText(
                f"{total}  ·  {self.dinero(importe)}"
            )

        if resumen is not None:

            self.tile_total.valor_label.setText(
                self.dinero(resumen["ingresos"])
            )

            umbral = self.proteger(
                obtener_stock_minimo
            )

            if umbral is not None:

                self.tile_stock.valor_label.setText(
                    f"{resumen['stock_bajo']} (≤ {umbral})"
                )

    def cargar_tablas(self):

        recientes = self.proteger(
            obtener_ventas_recientes, 6
        )

        if recientes is not None:

            filas = [
                (
                    str(fecha),
                    cliente,
                    vehiculo,
                    formatear_numero(precio)
                )
                for (
                    _, fecha, cliente,
                    vehiculo, precio
                ) in recientes
            ]

            self.pintar_panel(
                self.panel_ventas,
                filas,
                centricos={0}
            )

        top = self.proteger(obtener_top_vehiculos, 6)

        if top is not None:

            filas = [
                (
                    vehiculo,
                    unidades,
                    formatear_numero(importe)
                )
                for vehiculo, unidades, importe in top
            ]

            self.pintar_panel(
                self.panel_top,
                filas,
                centricos={1}
            )

        clientes = self.proteger(
            obtener_ventas_por_cliente, 6
        )

        if clientes is not None:

            filas = [
                (
                    cliente,
                    compras,
                    formatear_numero(importe)
                )
                for cliente, compras, importe in clientes
            ]

            self.pintar_panel(
                self.panel_clientes,
                filas,
                centricos={1}
            )

    def cargar_pie(self):

        ultima = self.proteger(obtener_ultima_venta)

        if ultima:

            texto = f"Última venta: {ultima}"
        else:

            texto = "Todavía no hay ventas"

        self.etiqueta_pie.setText(texto)

    # =============================
    # PINTADO
    # =============================

    def pintar_panel(self, panel, filas, centricos=None):

        centricos = centricos or set()

        vacio = len(filas) == 0

        panel.contenedor.setCurrentIndex(
            1 if vacio else 0
        )

        if vacio:

            return

        tabla = panel.tabla

        tabla.setRowCount(len(filas))

        for indice, fila in enumerate(filas):

            for columna, valor in enumerate(fila):

                tabla.setItem(
                    indice,
                    columna,
                    celda(
                        valor,
                        centrar=columna in centricos
                    )
                )

    def dinero(self, valor):
        """
        Importes del panel. Delega en
        utils.moneda para que el símbolo de la
        moneda sea el mismo que en el resto de la
        aplicación.
        """

        return formato_dinero(valor)
