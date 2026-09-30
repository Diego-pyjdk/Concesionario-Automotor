from database.autos import (
    obtener_autos,
    buscar_autos,
    eliminar_auto as eliminar_auto_db
)

from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QMessageBox
)

from utils.helpers import (
    crear_tabla,
    celda,
    crear_botones_accion,
    crear_boton_principal,
    crear_titulo
)

from gui.vista_base import VistaBase

from gui.formularios.auto_form import AutoForm


class AutosView(VistaBase):

    def __init__(self, parent=None, puede_gestionar=True):
        super().__init__(parent)

        self.puede_gestionar = puede_gestionar

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

        encabezado.addWidget(crear_titulo("Vehículos"))

        encabezado.addStretch()

        # Un vendedor solo consulta: el botón
        # no aparece. La protección real está en
        # database/autos.py.

        if self.puede_gestionar:

            encabezado.addWidget(
                crear_boton_principal(
                    "+ Nuevo vehículo",
                    self.nuevo_auto
                )
            )

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

        self.campo_busqueda.returnPressed.connect(
            self.buscar
        )

        boton_buscar = QPushButton("🔍 Buscar")

        boton_buscar.setObjectName("boton_filtro")

        boton_buscar.setFixedHeight(40)

        boton_buscar.clicked.connect(self.buscar)

        busqueda_layout.addWidget(self.campo_busqueda)
        busqueda_layout.addWidget(boton_buscar)

        layout_principal.addLayout(busqueda_layout)

        # =============================
        # TABLA
        # =============================
        # El orden de estas 7 columnas es el
        # contrato con database/autos.py: cada
        # valor se escribe por posición.
        # =============================

        self.tabla = crear_tabla(
            [
                "ID",
                "Marca",
                "Modelo",
                "Año",
                "Precio",
                "Color",
                "Stock",
                "Acciones"
            ],
            columna_acciones=7,
            ancho_acciones=148
        )

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

                # Centrar ID, Año y Stock
                centrar = columna in [0, 3, 6]

                self.tabla.setItem(
                    fila,
                    columna,
                    celda(dato, centrar=centrar)
                )

            # -------------------------
            # BOTONES DE ACCIONES
            # -------------------------

            botones = crear_botones_accion(
                lambda _, f=fila: self.editar_auto(f),
                lambda _, f=fila: self.eliminar_auto(f),
                mostrar_eliminar=self.puede_gestionar
            )

            # Colocar botones en la tabla
            self.tabla.setCellWidget(fila, 7, botones)

    # =============================
    # EDITAR VEHÍCULO
    # =============================

    def editar_auto(self, fila):

        datos = []

        # Obtener los datos de la fila
        for columna in range(7):

            item = self.tabla.item(fila, columna)

            if item is None:

                return

            datos.append(item.text())

        # Convertir los datos a sus tipos
        # correspondientes

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

        formulario = AutoForm(self, auto)

        # Si guardó los cambios
        if formulario.exec():

            self.cargar_datos()

    # =============================
    # ELIMINAR VEHÍCULO
    # =============================

    def eliminar_auto(self, fila):

        item = self.tabla.item(fila, 0)

        if not item:
            return

        id_auto = int(item.text())

        respuesta = QMessageBox.question(
            self,
            "Eliminar vehículo",
            "¿Estás seguro de que deseas eliminar este vehículo?",
            QMessageBox.Yes | QMessageBox.No
        )

        if respuesta != QMessageBox.Yes:
            return

        # Un vehículo con ventas no se puede
        # eliminar: se perdería el historial.

        if not eliminar_auto_db(id_auto):

            QMessageBox.warning(
                self,
                "No se puede eliminar",
                "El vehículo tiene ventas registradas. "
                "No se puede eliminar para no perder "
                "el historial."
            )

            return

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

        autos = buscar_autos(texto)

        # Mostrar resultados

        self.mostrar_autos(autos)
