from database.autos import (
    obtener_autos,
    buscar_autos,
    eliminar_auto as eliminar_auto_db
)

from utils.moneda import formatear_numero

from utils.helpers import (
    crear_botones_accion
)

from gui.vista_listado import VistaListado

from gui.formularios.auto_form import AutoForm


class AutosView(VistaListado):

    titulo = "Vehículos"

    columnas = [
        "ID",
        "Marca",
        "Modelo",
        "Año",
        "Precio",
        "Color",
        "Stock",
        "Acciones"
    ]

    columna_acciones = 7

    texto_nuevo = "+ Nuevo vehículo"

    placeholder_busqueda = "Buscar por modelo, marca..."

    mensaje_vacio = "Todavía no hay vehículos"

    detalle_vacio = (
        "Necesitas al menos una marca para "
        "poder registrar un vehículo."
    )

    def cargar_datos(self):

        self.mostrar_de(obtener_autos)

    def pintar_fila(self, fila, auto):

        (
            id_auto,
            marca,
            modelo,
            anio,
            precio,
            color,
            stock
        ) = auto

        # El precio se muestra con separador de
        # miles. leer_auto() lo deshace antes de
        # convertirlo.

        self.marcar_columnas(
            fila,
            [
                id_auto,
                marca,
                modelo,
                anio,
                formatear_numero(precio),
                color,
                stock
            ],
            centrar={0, 3, 6}
        )

        botones = crear_botones_accion(
            lambda _, f=fila: self.editar_auto(f),
            lambda _, f=fila: self.eliminar_auto(f),
            mostrar_eliminar=self.puede_gestionar
        )

        self.poner_acciones(fila, botones)

    def buscar(self, texto):

        if not texto:

            self.cargar_datos()

            return

        self.mostrar_de(buscar_autos, texto)

    # =============================
    # ALTA
    # =============================

    def nuevo_registro(self):

        formulario = AutoForm(self)

        if formulario.exec():

            self.cargar_datos()

    # =============================
    # EDICIÓN
    # =============================

    def leer_auto(self, fila):
        """
        Reconstruye el registro con los tipos que
        espera AutoForm.
        """

        datos = self.leer_valores(fila, 7)

        if datos is None:

            return None

        return (
            int(datos[0]),
            datos[1],
            datos[2],
            int(datos[3]),
            float(datos[4].replace(",", "")),
            datos[5],
            int(datos[6])
        )

    def editar_auto(self, fila):

        auto = self.leer_auto(fila)

        if auto is None:

            return

        formulario = AutoForm(self, auto)

        if formulario.exec():

            self.cargar_datos()

    # =============================
    # BORRADO
    # =============================

    def eliminar_auto(self, fila):

        item = self.tabla.item(fila, 0)

        item_modelo = self.tabla.item(fila, 2)

        if not item or not item_modelo:

            return

        id_auto = int(item.text())

        if not self.confirmar_borrado(
            item_modelo.text(),
            "Si tiene ventas registradas no se "
            "podrá eliminar."
        ):

            return

        resultado = self.proteger(
            eliminar_auto_db,
            id_auto
        )

        if resultado is None:

            return

        if not resultado:

            self.mostrar_mensaje_error(
                "El vehículo tiene ventas registradas. "
                "No se puede eliminar para no perder "
                "el historial."
            )

            return

        self.mostrar_exito(
            f"El vehículo '{item_modelo.text()}' "
            "se eliminó correctamente."
        )

        self.cargar_datos()
