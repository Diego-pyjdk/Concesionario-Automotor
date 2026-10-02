from database.ventas import (
    obtener_ventas,
    eliminar_venta as eliminar_venta_db
)

from utils.helpers import (
    crear_botones_accion
)

from gui.vista_listado import VistaListado

from gui.formularios.venta_form import VentaForm


class VentasView(VistaListado):

    titulo = "Ventas"

    columnas = [
        "ID",
        "Fecha",
        "Cliente",
        "Vehículo",
        "Precio",
        "Acciones"
    ]

    columna_acciones = 5

    texto_nuevo = "+ Nueva venta"

    placeholder_busqueda = "Buscar por cliente o vehículo..."

    mensaje_vacio = "Todavía no hay ventas"

    detalle_vacio = (
        "Registra la primera venta para verlas "
        "aquí."
    )

    anchos_fijos = {1: 110, 4: 120}

    def __init__(
        self,
        parent=None,
        puede_registrar=True,
        puede_gestionar=True
    ):
        self.puede_registrar = puede_registrar

        super().__init__(
            parent,
            puede_gestionar=puede_gestionar
        )

    def muestra_boton_nuevo(self):
        """
        El vendedor registra ventas aunque no
        pueda gestionarlas, así que aquí manda
        puede_registrar y no puede_gestionar.
        """

        return self.puede_registrar

    def cargar_datos(self):

        self.mostrar_de(obtener_ventas)

    def pintar_fila(self, fila, venta):

        (
            id_venta,
            fecha,
            cliente,
            vehiculo,
            precio
        ) = venta

        self.marcar_columnas(
            fila,
            [
                id_venta,
                str(fecha),
                cliente,
                vehiculo,
                f"{float(precio):,.2f}"
            ],
            centrar={0, 1}
        )

        # Las ventas no se editan: el primer
        # botón muestra el detalle.

        botones = crear_botones_accion(
            lambda _, f=fila: self.ver_venta(f),
            lambda _, f=fila: self.eliminar_venta(f),
            texto_editar="Ver",
            mostrar_eliminar=self.puede_gestionar
        )

        self.poner_acciones(fila, botones)

    def buscar(self, texto):

        if not texto:

            self.cargar_datos()

            return

        # Con lambda y no con argumentos posicionales:
        # obtener_ventas tiene tres parámetros y
        # pasar el texto en el tercero es frágil.
        self.mostrar_de(
            lambda: obtener_ventas(texto=texto)
        )

    # =============================
    # ALTA
    # =============================

    def nuevo_registro(self):

        formulario = VentaForm(self)

        if formulario.exec():

            self.cargar_datos()

    # =============================
    # DETALLE
    # =============================

    def ver_venta(self, fila):
        """
        Detalle de solo lectura: una venta es
        histórico y no se edita.
        """

        titulos = [
            "ID",
            "Fecha",
            "Cliente",
            "Vehículo",
            "Precio"
        ]

        lineas = []

        for columna, titulo in enumerate(titulos):

            item = self.tabla.item(fila, columna)

            if item:

                lineas.append(
                    f"{titulo}: {item.text()}"
                )

        if not lineas:

            return

        self.mostrar_exito("\n".join(lineas))

    # =============================
    # ANULACIÓN
    # =============================

    def eliminar_venta(self, fila):

        item = self.tabla.item(fila, 0)

        if not item:

            return

        id_venta = int(item.text())

        if not self.confirmar_borrado(
            f"la venta {id_venta}",
            "La unidad volverá al stock del "
            "vehículo."
        ):

            return

        resultado = self.proteger(
            eliminar_venta_db,
            id_venta
        )

        if resultado is None:

            return

        if not resultado:

            self.mostrar_mensaje_error(
                "La venta no se pudo anular."
            )

            return

        self.mostrar_exito(
            f"La venta {id_venta} se anuló y la "
            "unidad volvió al stock."
        )

        self.cargar_datos()
