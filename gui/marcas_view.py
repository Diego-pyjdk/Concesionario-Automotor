from database.marcas import (
    obtener_marcas,
    buscar_marcas,
    eliminar_marca as eliminar_marca_db
)

from utils.helpers import (
    crear_botones_accion
)

from gui.vista_listado import VistaListado

from gui.formularios.marca_form import MarcaForm


class MarcasView(VistaListado):

    titulo = "Marcas"

    columnas = ["ID", "Nombre", "Acciones"]

    columna_acciones = 2

    texto_nuevo = "+ Nueva marca"

    placeholder_busqueda = "Buscar marca..."

    mensaje_vacio = "Todavía no hay marcas"

    detalle_vacio = (
        "Crea la primera marca para poder "
        "registrar vehículos."
    )

    def cargar_datos(self):

        self.mostrar_de(obtener_marcas)

    def pintar_fila(self, fila, marca):

        id_marca, nombre = marca

        self.marcar_columnas(
            fila,
            [id_marca, nombre],
            centrar={0}
        )

        botones = crear_botones_accion(
            lambda _, f=fila: self.editar_marca(f),
            lambda _, f=fila: self.eliminar_marca(f),
            mostrar_eliminar=self.puede_gestionar
        )

        self.poner_acciones(fila, botones)

    def buscar(self, texto):

        if not texto:

            self.cargar_datos()

            return

        self.mostrar_de(buscar_marcas, texto)

    # =============================
    # ALTA
    # =============================

    def nuevo_registro(self):

        formulario = MarcaForm(self)

        if formulario.exec():

            self.cargar_datos()

    # =============================
    # EDICIÓN
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

        formulario = MarcaForm(self, marca)

        if formulario.exec():

            self.cargar_datos()

    # =============================
    # BORRADO
    # =============================

    def eliminar_marca(self, fila):

        item = self.tabla.item(fila, 0)

        item_nombre = self.tabla.item(fila, 1)

        if not item or not item_nombre:

            return

        id_marca = int(item.text())

        if not self.confirmar_borrado(
            item_nombre.text(),
            "Si tiene vehículos asociados no se "
            "podrá eliminar."
        ):

            return

        resultado = self.proteger(
            eliminar_marca_db,
            id_marca
        )

        if resultado is None:

            return

        if not resultado:

            self.mostrar_mensaje_error(
                "La marca tiene vehículos asociados. "
                "Elimina o cambia de marca esos "
                "vehículos primero."
            )

            return

        self.mostrar_exito(
            f"La marca '{item_nombre.text()}' "
            "se eliminó correctamente."
        )

        self.cargar_datos()
