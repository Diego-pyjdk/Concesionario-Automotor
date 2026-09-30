from gui.formularios.auto_form import AutoForm

from database.autos import (
    obtener_autos,
    buscar_autos,
    eliminar_auto as eliminar_auto_db
)

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)

from PySide6.QtCore import Qt


class AutosView(QWidget):

    def __init__(self):
        super().__init__()

        self.crear_interfaz()

    def crear_interfaz(self):

        layout_principal = QVBoxLayout()
        layout_principal.setContentsMargins(30, 25, 30, 25)
        layout_principal.setSpacing(20)

        self.setLayout(layout_principal)

        # =============================
        # ENCABEZADO
        # =============================

        encabezado = QHBoxLayout()

        titulo = QLabel("Vehículos")
        titulo.setObjectName("titulo")

        boton_nuevo = QPushButton("+ Nuevo vehículo")
        boton_nuevo.setObjectName("boton_principal")
        boton_nuevo.setFixedHeight(40)

        boton_nuevo.clicked.connect(self.nuevo_auto)

        encabezado.addWidget(titulo)
        encabezado.addStretch()
        encabezado.addWidget(boton_nuevo)

        layout_principal.addLayout(encabezado)

        # =============================
        # BÚSQUEDA
        # =============================

        busqueda_layout = QHBoxLayout()

        self.campo_busqueda = QLineEdit()

        self.campo_busqueda.setPlaceholderText(
            "Buscar por modelo, marca..."
        )

        self.campo_busqueda.setFixedHeight(40)

        boton_buscar = QPushButton("🔍 Buscar")
        boton_buscar.setFixedHeight(40)

        boton_buscar.clicked.connect(self.buscar)

        busqueda_layout.addWidget(self.campo_busqueda)
        busqueda_layout.addWidget(boton_buscar)

        layout_principal.addLayout(busqueda_layout)

        # =============================
        # TABLA
        # =============================

        self.tabla = QTableWidget()

        self.tabla.setColumnCount(8)

        self.tabla.setHorizontalHeaderLabels([
            "ID",
            "Marca",
            "Modelo",
            "Año",
            "Precio",
            "Color",
            "Stock",
            "Acciones"
        ])

        # Todas las columnas se expanden
        self.tabla.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        # La columna de acciones tiene tamaño fijo
        self.tabla.horizontalHeader().setSectionResizeMode(
            7,
            QHeaderView.Fixed
        )

        self.tabla.setColumnWidth(7, 148)

        # Seleccionar una fila completa
        self.tabla.setSelectionBehavior(
            QTableWidget.SelectRows
        )

        # No permitir editar directamente la tabla
        self.tabla.setEditTriggers(
            QTableWidget.NoEditTriggers
        )

        # Filas alternadas
        self.tabla.setAlternatingRowColors(True)

        layout_principal.addWidget(self.tabla)

        # Cargar datos desde MySQL
        self.cargar_datos()

    # =============================
    # NUEVO VEHÍCULO
    # =============================

    def nuevo_auto(self):

        formulario = AutoForm(self)

        if formulario.exec():

            self.cargar_datos()

    # =============================
    # CARGAR VEHÍCULOS
    # =============================

    def cargar_datos(self):

        autos = obtener_autos()

        self.mostrar_autos(autos)

    # =============================
    # MOSTRAR VEHÍCULOS
    # =============================

    def mostrar_autos(self, autos):

        self.tabla.setRowCount(len(autos))

        for fila, auto in enumerate(autos):

            # -------------------------
            # DATOS
            # -------------------------

            for columna, dato in enumerate(auto):

                item = QTableWidgetItem(str(dato))

                # Centrar ID, Año y Stock
                if columna in [0, 3, 6]:

                    item.setTextAlignment(
                        Qt.AlignCenter
                    )

                self.tabla.setItem(
                    fila,
                    columna,
                    item
                )

            # -------------------------
            # BOTONES DE ACCIONES
            # -------------------------

            contenedor = QWidget()

            acciones = QHBoxLayout(contenedor)

            acciones.setContentsMargins(
                4,
                2,
                4,
                2
            )

            acciones.setSpacing(6)

            # BOTÓN EDITAR

            boton_editar = QPushButton("Editar")

            boton_editar.setObjectName(
                "boton_editar"
            )

            boton_editar.setFixedSize(
                60,
                30
            )

            boton_editar.setToolTip(
                "Editar vehículo"
            )

            boton_editar.clicked.connect(
                lambda checked=False, fila=fila:
                self.editar_auto(fila)
            )

            # BOTÓN ELIMINAR

            boton_eliminar = QPushButton("Eliminar")

            boton_eliminar.setObjectName(
                "boton_eliminar"
            )

            boton_eliminar.setFixedSize(
                72,
                30
            )

            boton_eliminar.setToolTip(
                "Eliminar vehículo"
            )

            boton_eliminar.clicked.connect(
                lambda checked=False, fila=fila:
                self.eliminar_auto(fila)
            )

            # Agregar botones al layout

            acciones.addWidget(
                boton_editar
            )

            acciones.addWidget(
                boton_eliminar
            )

            # Colocar botones en la tabla

            self.tabla.setCellWidget(
                fila,
                7,
                contenedor
            )

    # =============================
    # EDITAR VEHÍCULO
    # =============================

    def editar_auto(self, fila):

        datos = []

        # Obtener los datos de la fila
        for columna in range(7):

            item = self.tabla.item(
                fila,
                columna
            )

            datos.append(
                item.text() if item else ""
            )

        # Convertir los datos a sus tipos correspondientes

        auto = (
            int(datos[0]),
            datos[1],
            datos[2],
            int(datos[3]),
            float(datos[4]),
            datos[5],
            int(datos[6])
        )

        # Abrir formulario de edición

        formulario = AutoForm(
            self,
            auto
        )

        # Si guardó los cambios
        if formulario.exec():

            self.cargar_datos()

    # =============================
    # ELIMINAR VEHÍCULO
    # =============================

    def eliminar_auto(self, fila):

        item = self.tabla.item(
            fila,
            0
        )

        if not item:
            return

        id_auto = int(
            item.text()
        )

        respuesta = QMessageBox.question(
            self,
            "Eliminar vehículo",
            "¿Estás seguro de que deseas eliminar este vehículo?",
            QMessageBox.Yes | QMessageBox.No
        )

        if respuesta == QMessageBox.Yes:

            eliminar_auto_db(
                id_auto
            )

            self.cargar_datos()

    # =============================
    # BUSCAR VEHÍCULO
    # =============================

    def buscar(self):

        texto = self.campo_busqueda.text().strip()

        # Si está vacío, mostrar todos
        if not texto:

            self.cargar_datos()

            return

        # Buscar en MySQL

        autos = buscar_autos(
            texto
        )

        # Mostrar resultados

        self.mostrar_autos(
            autos
        )