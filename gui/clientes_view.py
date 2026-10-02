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
        "Acciones"
    ]

    columna_acciones = 5

    texto_nuevo = "+ Nuevo cliente"

    placeholder_busqueda = (
        "Buscar por nombre, apellido, "
        "teléfono o email..."
    )

    mensaje_vacio = "Todavía no hay clientes"

    detalle_vacio = (
        "Registra un cliente para poder "
        "asociarlo a una venta."
    )

    def cargar_datos(self):

        self.mostrar_de(obtener_clientes)

    def pintar_fila(self, fila, cliente):

        (
            id_cliente,
            nombre,
            apellido,
            telefono,
            email
        ) = cliente

        self.marcar_columnas(
            fila,
            [
                id_cliente,
                nombre,
                apellido,
                telefono or "",
                email or ""
            ],
            centrar={0}
        )

        botones = crear_botones_accion(
            lambda _, f=fila: self.editar_cliente(f),
            lambda _, f=fila: self.eliminar_cliente(f),
            mostrar_eliminar=self.puede_gestionar
        )

        self.poner_acciones(fila, botones)

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

        valores = self.leer_valores(fila, 5)

        if valores is None:

            return

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
