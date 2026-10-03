# ==========================================
# REPORTES
# ==========================================
# Solo el administrador llega aquí (VER_REPORTES).
# Filtra por fecha, cliente, vehículo y marca, y
# de ese recorte salen cinco cifras y cuatro
# listados.
#
# Todos los listados comparten los mismos
# filtros: se construyen con la misma función
# que usa database/reportes.py, así que "por
# cliente" significa exactamente lo mismo en el
# conteo, en el importe y en el detalle.
# ==========================================


from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QComboBox,
    QDateEdit,
    QFrame,
    QWidget,
    QStackedWidget,
    QTabWidget,
    QFileDialog
)

from PySide6.QtCore import QDate

from database.reportes import (
    obtener_detalle_ventas,
    obtener_metricas,
    obtener_vehiculos_vendidos,
    obtener_clientes_con_compras,
    obtener_ventas_por_vendedor,
    obtener_stock_actual
)

from database.clientes import obtener_clientes_para_venta

from database.autos import obtener_autos_para_venta

from database.marcas import obtener_marcas

from utils.helpers import (
    crear_tabla,
    crear_titulo,
    crear_estado_vacio,
    celda,
    crear_boton_principal,
    crear_boton_secundario
)

from utils.moneda import (
    formato_dinero,
    formatear_numero
)

from gui.vista_base import VistaBase


class ReportesView(VistaBase):
    """
    No hereda de VistaListado: aquí el contenido
    no es una tabla única sino varias pestañas
    más un panel de filtros y otro de métricas.
    """

    def __init__(self):
        super().__init__()

        self.crear_interfaz()

        self.cargar_listas()

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
            crear_titulo("Reportes")
        )

        layout.addWidget(
            self.crear_panel_filtros()
        )

        layout.addWidget(
            self.crear_panel_metricas()
        )

        self.pestanas = QTabWidget()

        self.tabla_ventas = self.crear_hoja(
            "Detalle de ventas",
            ["Fecha", "Cliente", "Vehículo", "Precio"],
            anchos_fijos={0: 100, 3: 110},
            vacio="No hay ventas en este periodo"
        )

        self.tabla_vehiculos = self.crear_hoja(
            "Vehículos vendidos",
            [
                "ID", "Marca", "Modelo", "Año",
                "Unidades", "Importe", "Stock"
            ],
            anchos_fijos={3: 60, 4: 80, 5: 110, 6: 70},
            vacio="No se vendió ningún vehículo"
        )

        self.tabla_clientes = self.crear_hoja(
            "Clientes con compras",
            ["ID", "Nombre", "Apellido", "Compras", "Importe"],
            anchos_fijos={0: 60, 3: 80, 4: 120},
            vacio="Ningún cliente compró en este periodo"
        )

        self.tabla_inventario = self.crear_hoja(
            "Stock actual",
            ["Dato", "Valor"],
            anchos_fijos={0: 220},
            vacio="No hay vehículos registrados"
        )

        self.tabla_vendedores = self.crear_hoja(
            "Ventas por vendedor",
            ["Vendedor", "Ventas", "Importe"],
            anchos_fijos={1: 80, 2: 130},
            vacio="Todavía no hay ventas registradas"
        )

        self.pestanas.addTab(
            self.tabla_ventas.contenedor,
            "Detalle de ventas"
        )

        self.pestanas.addTab(
            self.tabla_vehiculos.contenedor,
            "Vehículos vendidos"
        )

        self.pestanas.addTab(
            self.tabla_clientes.contenedor,
            "Clientes con compras"
        )

        self.pestanas.addTab(
            self.tabla_vendedores.contenedor,
            "Ventas por vendedor"
        )

        self.pestanas.addTab(
            self.tabla_inventario.contenedor,
            "Stock actual"
        )

        layout.addWidget(self.pestanas)

        self.etiqueta_pie = QLabel("")

        self.etiqueta_pie.setObjectName(
            "pie"
        )

        layout.addWidget(
            self.etiqueta_pie
        )

    def crear_panel_filtros(self):

        panel = QFrame()
        panel.setObjectName("filtros")

        exterior = QVBoxLayout()
        exterior.setContentsMargins(20, 16, 20, 16)
        exterior.setSpacing(12)

        panel.setLayout(exterior)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)

        self.campo_desde = self.crear_fecha(
            QDate.currentDate().addDays(-30)
        )

        self.campo_hasta = self.crear_fecha(
            QDate.currentDate()
        )

        self.combo_cliente = QComboBox()

        self.combo_vehiculo = QComboBox()

        self.combo_marca = QComboBox()

        self._etiqueta_filtro(grid, "Desde", 0, 0)
        grid.addWidget(self.campo_desde, 1, 0)

        self._etiqueta_filtro(grid, "Hasta", 0, 1)
        grid.addWidget(self.campo_hasta, 1, 1)

        self._etiqueta_filtro(grid, "Cliente", 0, 2)
        grid.addWidget(self.combo_cliente, 1, 2)

        self._etiqueta_filtro(grid, "Vehículo", 0, 3)
        grid.addWidget(self.combo_vehiculo, 1, 3)

        self._etiqueta_filtro(grid, "Marca", 0, 4)
        grid.addWidget(self.combo_marca, 1, 4)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 2)
        grid.setColumnStretch(3, 2)
        grid.setColumnStretch(4, 2)

        exterior.addLayout(grid)

        # ------------------------------
        # BOTONES
        # ------------------------------

        botones = QHBoxLayout()
        botones.setSpacing(10)

        botones.addWidget(
            crear_boton_principal(
                "🔄  Aplicar filtros",
                self.cargar_datos
            )
        )

        botones.addWidget(
            crear_boton_secundario(
                "Restablecer",
                self.restablecer
            )
        )

        botones.addStretch()

        botones.addWidget(
            crear_boton_secundario(
                "⬇  Exportar CSV",
                self.exportar_csv
            )
        )

        exterior.addLayout(botones)

        return panel

    def _etiqueta_filtro(self, grid, texto, fila, columna):

        etiqueta = QLabel(texto)

        etiqueta.setObjectName(
            "etiqueta_filtro"
        )

        grid.addWidget(etiqueta, fila, columna)

        return etiqueta

    def crear_fecha(self, fecha):

        campo = QDateEdit()

        campo.setCalendarPopup(True)

        campo.setDisplayFormat("dd/MM/yyyy")

        campo.setDate(fecha)

        campo.dateChanged.connect(
            self.cargar_datos
        )

        return campo

    def crear_panel_metricas(self):

        panel = QFrame()
        panel.setObjectName("filtros")

        layout = QHBoxLayout()
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(15)

        panel.setLayout(layout)

        self.metrica_ventas = self.crear_metrica(
            "Ventas", layout
        )

        self.metrica_importe = self.crear_metrica(
            "Total vendido", layout
        )

        self.metrica_vehiculos = self.crear_metrica(
            "Vehículos vendidos", layout
        )

        self.metrica_clientes = self.crear_metrica(
            "Clientes con compras", layout
        )

        self.metrica_stock = self.crear_metrica(
            "Unidades en stock", layout
        )

        return panel

    def crear_metrica(self, nombre, layout):

        marco = QFrame()
        marco.setObjectName("metrica")

        interior = QVBoxLayout()
        interior.setContentsMargins(4, 0, 4, 0)
        interior.setSpacing(2)

        marco.setLayout(interior)

        etiqueta_nombre = QLabel(nombre)
        etiqueta_nombre.setObjectName("metrica_nombre")

        etiqueta_valor = QLabel("—")
        etiqueta_valor.setObjectName("metrica_valor")

        interior.addWidget(etiqueta_nombre)
        interior.addWidget(etiqueta_valor)

        layout.addWidget(marco)

        marco.valor_label = etiqueta_valor

        return marco

    def crear_hoja(
        self,
        titulo,
        columnas,
        anchos_fijos=None,
        vacio="Sin datos"
    ):
        """
        Marco de una pestaña: tabla o estado vacío.
        """

        marco = QWidget()

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)

        marco.setLayout(layout)

        contenedor = QStackedWidget()

        tabla = crear_tabla(
            columnas,
            anchos_fijos=anchos_fijos
        )

        contenedor.addWidget(tabla)
        contenedor.addWidget(
            crear_estado_vacio(vacio)
        )

        layout.addWidget(contenedor)

        marco.tabla = tabla
        marco.contenedor = contenedor

        return marco

    # =============================
    # LISTAS DE LOS FILTROS
    # =============================

    def cargar_listas(self):

        self.cargar_lista_clientes()
        self.cargar_lista_vehiculos()
        self.cargar_lista_marcas()

    def cargar_lista_clientes(self):

        self.combo_cliente.addItem("Todos", None)

        clientes = self.proteger(
            obtener_clientes_para_venta
        )

        if clientes is None:

            return

        for id_cliente, nombre, apellido in clientes:

            self.combo_cliente.addItem(
                f"{nombre} {apellido}",
                id_cliente
            )

    def cargar_lista_vehiculos(self):

        self.combo_vehiculo.addItem("Todos", None)

        autos = self.proteger(
            obtener_autos_para_venta
        )

        if autos is None:

            return

        for id_auto, vehiculo, precio, stock in autos:

            self.combo_vehiculo.addItem(
                vehiculo,
                id_auto
            )

    def cargar_lista_marcas(self):

        self.combo_marca.addItem("Todas", None)

        marcas = self.proteger(obtener_marcas)

        if marcas is None:

            return

        for id_marca, nombre in marcas:

            self.combo_marca.addItem(
                nombre,
                id_marca
            )

        # Las señales se conectan aquí y no al
        # poblar: si no, el primer elemento que
        # se añade dispararía la consulta.
        self.combo_cliente.currentIndexChanged.connect(
            self.cargar_datos
        )

        self.combo_vehiculo.currentIndexChanged.connect(
            self.cargar_datos
        )

        self.combo_marca.currentIndexChanged.connect(
            self.cargar_datos
        )

    # =============================
    # FILTROS
    # =============================

    def obtener_filtros(self):

        return {
            "desde": self.campo_desde.date().toString(
                "yyyy-MM-dd"
            ),
            "hasta": self.campo_hasta.date().toString(
                "yyyy-MM-dd"
            ),
            "cliente_id": self.combo_cliente.currentData(),
            "auto_id": self.combo_vehiculo.currentData(),
            "marca_id": self.combo_marca.currentData()
        }

    def restablecer(self):
        """
        Los combos se restauran con las señales
        cortadas: si no, cambiar los cinco filtros
        dispararía cinco consultas seguidas para
        terminar en la misma.
        """

        combos = [
            self.combo_cliente,
            self.combo_vehiculo,
            self.combo_marca
        ]

        for combo in combos:

            combo.blockSignals(True)

        self.campo_desde.setDate(
            QDate.currentDate().addDays(-30)
        )

        self.campo_hasta.setDate(
            QDate.currentDate()
        )

        for combo in combos:

            combo.setCurrentIndex(0)
            combo.blockSignals(False)

        self.cargar_datos()

    # =============================
    # DATOS
    # =============================

    def cargar_datos(self):

        filtros = self.obtener_filtros()

        self.cargar_metricas(filtros)
        self.cargar_tabla_ventas(filtros)
        self.cargar_tabla_vehiculos(filtros)
        self.cargar_tabla_clientes(filtros)
        self.cargar_tabla_vendedores(filtros)
        self.cargar_tabla_inventario()

        self.actualizar_titulos()

    def cargar_metricas(self, filtros):

        metricas = self.proteger(
            obtener_metricas,
            **filtros
        )

        if metricas is not None:

            self.metrica_ventas.valor_label.setText(
                str(metricas["ventas"])
            )

            self.metrica_importe.valor_label.setText(
                self.dinero(metricas["importe"])
            )

            self.metrica_vehiculos.valor_label.setText(
                str(metricas["vehiculos"])
            )

            self.metrica_clientes.valor_label.setText(
                str(metricas["clientes"])
            )

        stock = self.proteger(obtener_stock_actual)

        if stock is not None:

            # Texto corto a propósito: la casilla
            # es estrecha y el detalle (con y sin
            # stock, valor) está en la pestaña
            # "Stock actual".
            self.metrica_stock.valor_label.setText(
                f"{stock['unidades']} unidades"
            )

    def cargar_tabla_ventas(self, filtros):

        filas = self.proteger(
            obtener_detalle_ventas,
            **filtros
        )

        if filas is None:

            return

        datos = [
            (
                str(fecha),
                cliente,
                vehiculo,
                formatear_numero(precio)
            )
            for (
                _, fecha, cliente,
                vehiculo, precio
            ) in filas
        ]

        self.pintar(
            self.tabla_ventas,
            datos,
            centricos={0}
        )

    def cargar_tabla_vehiculos(self, filtros):

        filas = self.proteger(
            obtener_vehiculos_vendidos,
            **filtros
        )

        if filas is None:

            return

        datos = [
            (
                id_auto,
                marca,
                modelo,
                anio,
                unidades,
                formatear_numero(importe),
                stock
            )
            for (
                id_auto, marca, modelo, anio,
                unidades, importe, stock
            ) in filas
        ]

        self.pintar(
            self.tabla_vehiculos,
            datos,
            centricos={0, 3, 4, 6}
        )

    def cargar_tabla_clientes(self, filtros):

        filas = self.proteger(
            obtener_clientes_con_compras,
            **filtros
        )

        if filas is None:

            return

        datos = [
            (
                id_cliente,
                nombre,
                apellido,
                compras,
                f"{float(importe):,.2f}"
            )
            for (
                id_cliente, nombre, apellido,
                compras, importe
            ) in filas
        ]

        self.pintar(
            self.tabla_clientes,
            datos,
            centricos={0, 3}
        )

    def cargar_tabla_vendedores(self, filtros):
        """
        Quién cerró cada venta.

        Lleva los mismos filtros que las demás
        pestañas: si esta contara todo el
        histórico mientras las otras cuentan el
        periodo, los números de dos pestañas
        distintas no serían comparables.
        """

        filas = self.proteger(
            obtener_ventas_por_vendedor,
            **filtros
        )

        if filas is None:

            return

        datos = [
            (vendedor, ventas, formatear_numero(importe))
            for vendedor, ventas, importe in filas
        ]

        self.pintar(
            self.tabla_vendedores,
            datos,
            centricos={1}
        )

    def cargar_tabla_inventario(self):
        """
        El stock no tiene fechas: depende solo del
        estado actual, no del periodo filtrado.
        """

        stock = self.proteger(obtener_stock_actual)

        if stock is None:

            return

        datos = [
            ("Unidades en stock", stock["unidades"]),
            ("Vehículos con stock", stock["con_stock"]),
            ("Vehículos sin stock", stock["sin_stock"]),
            (
                "Valor del inventario",
                self.dinero(stock["valor"])
            )
        ]

        self.pintar(
            self.tabla_inventario,
            datos,
            centricos={1}
        )

    # =============================
    # PINTADO
    # =============================

    def pintar(self, marco, filas, centricos=None):

        centricos = centricos or set()

        vacio = len(filas) == 0

        marco.contenedor.setCurrentIndex(
            1 if vacio else 0
        )

        if vacio:

            return

        tabla = marco.tabla

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

    def actualizar_titulos(self):

        filas = self.tabla_ventas.tabla.rowCount()

        plural = "venta" if filas == 1 else "ventas"

        self.pestanas.setTabText(
            0, f"Detalle de ventas ({filas})"
        )

        self.pestanas.setTabText(
            1,
            f"Vehículos vendidos "
            f"({self.tabla_vehiculos.tabla.rowCount()})"
        )

        self.pestanas.setTabText(
            2,
            f"Clientes con compras "
            f"({self.tabla_clientes.tabla.rowCount()})"
        )

        desde = self.campo_desde.date().toString(
            "dd/MM/yyyy"
        )

        hasta = self.campo_hasta.date().toString(
            "dd/MM/yyyy"
        )

        self.etiqueta_pie.setText(
            f"Del {desde} al {hasta}  ·  "
            f"{filas} {plural} en el filtro"
        )

    # =============================
    # EXPORTACIÓN
    # =============================

    def exportar_csv(self):
        """
        Exporta la pestaña que esté visible, no
        todas: es lo que el usuario está
        mirando.
        """

        ruta, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar reporte",
            "reporte.csv",
            "CSV (*.csv)"
        )

        if not ruta:

            return

        hojas = {
            0: (
                self.tabla_ventas,
                "fecha;cliente;vehiculo;precio"
            ),
            1: (
                self.tabla_vehiculos,
                "id;marca;modelo;anio;unidades;"
                "importe;stock"
            ),
            2: (
                self.tabla_clientes,
                "id;nombre;apellido;compras;importe"
            ),
            3: (
                self.tabla_inventario,
                "dato;valor"
            )
        }

        marco, cabecera = hojas[
            self.pestanas.currentIndex()
        ]

        filas = self.recolectar_filas(marco.tabla)

        if not filas:

            self.mostrar_mensaje_error(
                "No hay nada que exportar con el "
                "filtro actual."
            )

            return

        try:

            with open(
                ruta,
                "w",
                encoding="utf-8-sig",
                newline=""
            ) as archivo:

                archivo.write(cabecera + "\n")

                for fila in filas:

                    archivo.write(
                        ";".join(
                            valor.replace(";", ",")
                            for valor in fila
                        ) + "\n"
                    )

        except OSError as error:

            from utils.registro import registrar_error

            registrar_error(error)

            self.mostrar_error_inesperado()

            return

        self.mostrar_exito(
            f"Se exportaron {len(filas)} filas en:\n"
            f"{ruta}"
        )

    def recolectar_filas(self, tabla):

        filas = []

        for indice in range(tabla.rowCount()):

            fila = []

            for columna in range(tabla.columnCount()):

                item = tabla.item(indice, columna)

                fila.append(
                    "" if item is None else item.text()
                )

            filas.append(fila)

        return filas

    def dinero(self, valor):
        """
        Importes de los reportes. Delega en
        utils.moneda: el símbolo sale de la
        configuración, no de aquí.
        """

        return formato_dinero(valor)
