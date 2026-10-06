from utils.helpers import ancho_acciones_para
from PySide6.QtWidgets import QMenu
from gui.fichas_dialog import ClienteFichaDialog
from utils.helpers import crear_boton_secundario
from PySide6.QtWidgets import QComboBox
from database.clientes import (
    obtener_clientes,
    buscar_clientes,
    eliminar_cliente as eliminar_cliente_db
)

from utils.helpers import (
    crear_botones_accion
)

from gui.vista_listado import VistaListado

from gui.formularios.cliente_form import ClienteForm


class ClientesView(VistaListado):

    titulo = "Clientes"

    columnas = [
        "ID",
        "Nombre",
        "Apellido",
        "Teléfono",
        "Email",
        "Documento",
        "Acciones"
    ]

    columna_acciones = 6
    ancho_acciones = ancho_acciones_para([84])

    # El correo es lo más ancho de esta tabla
    # (hasta 20 px de padding por celda), así
    # que lleva ancho fijo: repartido a partes
    # iguales se cortaba.

    anchos_fijos = {
        4: 130
    }

    texto_nuevo = "+ Nuevo cliente"

    placeholder_busqueda = (
        "Buscar por nombre, apellido, "
        "teléfono, email o documento..."
    )

    mensaje_vacio = "Todavía no hay clientes"

    detalle_vacio = (
        "Registra un cliente para poder "
        "asociarlo a una venta."
    )

    def crear_interfaz(self):
        super().crear_interfaz()
        self.acciones_encabezado.addWidget(crear_boton_secundario('Ver ficha', self.abrir_ficha))
        self.tabla.cellDoubleClicked.connect(lambda fila, columna: self.abrir_ficha(fila))

    def abrir_ficha(self, fila=None):
        if fila is None or isinstance(fila, bool):
            fila = self.tabla.currentRow()
        if fila < 0 or self.tabla.item(fila, 0) is None:
            return
        dialogo = ClienteFichaDialog(self, int(self.tabla.item(fila, 0).text()))
        dialogo.exec()
        self.cargar_datos()

    def cargar_datos(self):

        self.mostrar_de(obtener_clientes)

    def pintar_fila(self, fila, cliente):

        (
            id_cliente,
            nombre,
            apellido,
            telefono,
            email,
            documento
        ) = cliente

        self.marcar_columnas(
            fila,
            [
                id_cliente,
                nombre,
                apellido,
                telefono or "",
                email or "",
                documento or ""
            ],
            centrar={0}
        )

        boton = crear_botones_accion(lambda _, f=fila: self.menu_fila(f), None, texto_editar='Más…', mostrar_eliminar=False, ancho_editar=84)
        self.poner_acciones(fila, boton)

    def menu_fila(self, fila):
        menu = QMenu(self)
        menu.addAction('Ver ficha', lambda: self.abrir_ficha(fila))
        if self.puede_gestionar:
            menu.addAction('Editar', lambda: self.editar_cliente(fila))
            menu.addSeparator()
            menu.addAction('Eliminar', lambda: self.eliminar_cliente(fila))
        boton = self.tabla.cellWidget(fila, self.columna_acciones)
        menu.exec(boton.mapToGlobal(boton.rect().bottomLeft()))


    def buscar(self, texto):

        if not texto:

            self.cargar_datos()

            return

        self.mostrar_de(buscar_clientes, texto)

    # =============================
    # ALTA
    # =============================

    def nuevo_registro(self):

        formulario = ClienteForm(self)

        if formulario.exec():

            self.cargar_datos()

    # =============================
    # EDICIÓN
    # =============================

    def editar_cliente(self, fila):

        valores = self.leer_valores(fila, 6)

        if valores is None:

            return

        (
            id_cliente,
            nombre,
            apellido,
            telefono,
            email,
            documento
        ) = valores

        cliente = (
            int(id_cliente),
            nombre,
            apellido,
            telefono or None,
            email or None,
            documento or None
        )

        formulario = ClienteForm(self, cliente)

        if formulario.exec():

            self.cargar_datos()

    # =============================
    # BORRADO
    # =============================

    def eliminar_cliente(self, fila):

        item = self.tabla.item(fila, 0)

        item_nombre = self.tabla.item(fila, 1)

        if not item or not item_nombre:

            return

        id_cliente = int(item.text())

        nombre = (
            f"{item_nombre.text()} "
            f"{(self.tabla.item(fila, 2) or item_nombre).text()}"
        )

        if not self.confirmar_borrado(
            nombre.strip(),
            "Si tiene ventas registradas no se "
            "podrá eliminar."
        ):

            return

        resultado = self.proteger(
            eliminar_cliente_db,
            id_cliente
        )

        if resultado is None:

            return

        if not resultado:

            self.mostrar_mensaje_error(
                "El cliente tiene ventas registradas. "
                "No se puede eliminar para no "
                "perder el historial."
            )

            return

        self.mostrar_exito(
            f"El cliente '{nombre.strip()}' "
            "se eliminó correctamente."
        )

        self.cargar_datos()
