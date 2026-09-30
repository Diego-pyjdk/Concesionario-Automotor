from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QMessageBox
)

from database.clientes import (
    obtener_clientes,
    buscar_clientes,
    eliminar_cliente as eliminar_cliente_db
)

from utils.helpers import (
    crear_tabla,
    celda,
    crear_botones_accion,
    crear_boton_principal,
    crear_titulo
)

from gui.vista_base import VistaBase

from gui.formularios.cliente_form import ClienteForm


class ClientesView(VistaBase):

    def __init__(self, parent=None, puede_gestionar=True):
        super().__init__(parent)

        self.puede_gestionar = puede_gestionar

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
            crear_titulo("Clientes")
        )

        encabezado.addStretch()

        if self.puede_gestionar:

            encabezado.addWidget(
                crear_boton_principal(
                    "+ Nuevo cliente",
                    self.nuevo_cliente
                )
            )

        layout_principal.addLayout(encabezado)

        # ------------------------------
        # BÚSQUEDA
        # ------------------------------

        busqueda_layout = QHBoxLayout()

        self.campo_busqueda = QLineEdit()

        self.campo_busqueda.setPlaceholderText(
            "Buscar por nombre, apellido, "
            "teléfono o email..."
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
                "Nombre",
                "Apellido",
                "Teléfono",
                "Email",
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
    # NUEVO CLIENTE
    # =============================

    def nuevo_cliente(self):

        formulario = ClienteForm(self)

        if formulario.exec():
            self.cargar_datos()

    # =============================
    # CARGAR CLIENTES
    # =============================

    def cargar_datos(self):

        self.mostrar_clientes(
            obtener_clientes()
        )

    # =============================
    # MOSTRAR CLIENTES
    # =============================

    def mostrar_clientes(self, clientes):

        self.tabla.setRowCount(len(clientes))

        for fila, cliente in enumerate(clientes):

            (
                id_cliente,
                nombre,
                apellido,
                telefono,
                email
            ) = cliente

            self.tabla.setItem(
                fila,
                0,
                celda(id_cliente, centrar=True)
            )

            self.tabla.setItem(
                fila,
                1,
                celda(nombre)
            )

            self.tabla.setItem(
                fila,
                2,
                celda(apellido)
            )

            self.tabla.setItem(
                fila,
                3,
                celda(telefono or "")
            )

            self.tabla.setItem(
                fila,
                4,
                celda(email or "")
            )

            botones = crear_botones_accion(
                lambda _, f=fila: self.editar_cliente(f),
                lambda _, f=fila: self.eliminar_cliente(f),
                mostrar_eliminar=self.puede_gestionar
            )

            self.tabla.setCellWidget(
                fila,
                5,
                botones
            )

    # =============================
    # EDITAR CLIENTE
    # =============================

    def editar_cliente(self, fila):

        valores = []

        for columna in range(5):

            item = self.tabla.item(fila, columna)

            if item is None:
                return

            valores.append(item.text())

        (
            id_cliente,
            nombre,
            apellido,
            telefono,
            email
        ) = valores

        cliente = (
            int(id_cliente),
            nombre,
            apellido,
            telefono or None,
            email or None
        )

        formulario = ClienteForm(
            self,
            cliente
        )

        if formulario.exec():
            self.cargar_datos()

    # =============================
    # ELIMINAR CLIENTE
    # =============================

    def eliminar_cliente(self, fila):

        item = self.tabla.item(fila, 0)

        if not item:
            return

        id_cliente = int(item.text())

        respuesta = QMessageBox.question(
            self,
            "Eliminar cliente",
            "¿Estás seguro de que deseas "
            "eliminar este cliente?",
            QMessageBox.Yes | QMessageBox.No
        )

        if respuesta != QMessageBox.Yes:
            return

        # Un cliente con ventas no se puede
        # eliminar: se perdería el historial.

        if not eliminar_cliente_db(id_cliente):
            QMessageBox.warning(
                self,
                "No se puede eliminar",
                "El cliente tiene ventas registradas. "
                "No se puede eliminar para no "
                "perder el historial."
            )

            return

        self.cargar_datos()

    # =============================
    # BUSCAR CLIENTE
    # =============================

    def buscar(self):

        texto = self.campo_busqueda.text().strip()

        if not texto:
            self.cargar_datos()
            return

        self.mostrar_clientes(
            buscar_clientes(texto)
        )
