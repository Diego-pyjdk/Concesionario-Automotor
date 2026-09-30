from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QMessageBox
)

from database.marcas import (
    obtener_marcas,
    buscar_marcas,
    eliminar_marca as eliminar_marca_db
)

from utils.helpers import (
    crear_tabla,
    celda,
    crear_botones_accion,
    crear_boton_principal,
    crear_titulo
)

from gui.formularios.marca_form import MarcaForm


class MarcasView(QWidget):

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
            crear_titulo("Marcas")
        )

        encabezado.addStretch()

        encabezado.addWidget(
            crear_boton_principal(
                "+ Nueva marca",
                self.nueva_marca
            )
        )

        layout_principal.addLayout(encabezado)

        # ------------------------------
        # BÚSQUEDA
        # ------------------------------

        busqueda_layout = QHBoxLayout()

        self.campo_busqueda = QLineEdit()

        self.campo_busqueda.setPlaceholderText(
            "Buscar marca..."
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
            ["ID", "Nombre", "Acciones"],
            columna_acciones=2,
            ancho_acciones=148
        )

        layout_principal.addWidget(self.tabla)

        # ------------------------------
        # CARGAR
        # ------------------------------

        self.cargar_datos()

    # =============================
    # NUEVA MARCA
    # =============================

    def nueva_marca(self):

        formulario = MarcaForm(self)

        if formulario.exec():
            self.cargar_datos()

    # =============================
    # CARGAR MARCAS
    # =============================

    def cargar_datos(self):

        self.mostrar_marcas(
            obtener_marcas()
        )

    # =============================
    # MOSTRAR MARCAS
    # =============================

    def mostrar_marcas(self, marcas):

        self.tabla.setRowCount(len(marcas))

        for fila, marca in enumerate(marcas):

            id_marca, nombre = marca

            self.tabla.setItem(
                fila,
                0,
                celda(id_marca, centrar=True)
            )

            self.tabla.setItem(
                fila,
                1,
                celda(nombre)
            )

            botones = crear_botones_accion(
                lambda _, f=fila: self.editar_marca(f),
                lambda _, f=fila: self.eliminar_marca(f)
            )

            self.tabla.setCellWidget(
                fila,
                2,
                botones
            )

    # =============================
    # EDITAR MARCA
    # =============================

    def editar_marca(self, fila):

        item_id = self.tabla.item(fila, 0)

        item_nombre = self.tabla.item(fila, 1)

        if not item_id or not item_nombre:
            return

        marca = (
            int(item_id.text()),
            item_nombre.text()
        )

        formulario = MarcaForm(
            self,
            marca
        )

        if formulario.exec():
            self.cargar_datos()

    # =============================
    # ELIMINAR MARCA
    # =============================

    def eliminar_marca(self, fila):

        item = self.tabla.item(fila, 0)

        if not item:
            return

        id_marca = int(item.text())

        respuesta = QMessageBox.question(
            self,
            "Eliminar marca",
            "¿Estás seguro de que deseas eliminar "
            "esta marca?",
            QMessageBox.Yes | QMessageBox.No
        )

        if respuesta != QMessageBox.Yes:
            return

        # Una marca con vehículos no se puede
        # eliminar: se perdería la información
        # del vehículo.

        if not eliminar_marca_db(id_marca):
            QMessageBox.warning(
                self,
                "No se puede eliminar",
                "La marca tiene vehículos asociados. "
                "Elimina o cambia de marca esos "
                "vehículos primero."
            )

            return

        self.cargar_datos()

    # =============================
    # BUSCAR MARCA
    # =============================

    def buscar(self):

        texto = self.campo_busqueda.text().strip()

        if not texto:
            self.cargar_datos()
            return

        self.mostrar_marcas(
            buscar_marcas(texto)
        )
