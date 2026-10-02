from database.ventas import (
    obtener_ventas,
    eliminar_venta as eliminar_venta_db
)

from database.contratos import (
    contrato_de_venta,
    venta_bloqueada_por_contrato
)

from permisos import (
    tiene_permiso,
    CREAR_CONTRATOS
)

from utils.helpers import (
    crear_botones_accion,
    ancho_acciones_para
)

from gui.vista_listado import VistaListado

from gui.formularios.venta_form import VentaForm

from gui.formularios.contrato_form import ContratoForm


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

    ANCHO_VER = 56

    ANCHO_CONTRATO = 68

    ANCHO_ELIMINAR = 70

    ancho_acciones = ancho_acciones_para([
        ANCHO_VER,
        ANCHO_CONTRATO,
        ANCHO_ELIMINAR
    ])

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
        # botón muestra el detalle. El segundo
        # abre el contrato, que es el paso que
        # sigue a la venta.

        acciones_extra = []

        if tiene_permiso(CREAR_CONTRATOS):

            acciones_extra.append((
                "Contrato",
                lambda _, f=fila: self.crear_contrato(f),
                "boton_editar",
                self.ANCHO_CONTRATO
            ))

        botones = crear_botones_accion(
            lambda _, f=fila: self.ver_venta(f),
            lambda _, f=fila: self.eliminar_venta(f),
            texto_editar="Ver",
            mostrar_eliminar=self.puede_gestionar,
            acciones_extra=acciones_extra,
            ancho_editar=self.ANCHO_VER,
            ancho_eliminar=self.ANCHO_ELIMINAR
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

        if not formulario.exec():

            return

        # El formulario de venta ofrece crear
        # el contrato al confirmar, pero no lo
        # abre: se cierra primero y desde aqui
        # se lanza. Abrirlo dentro apilaba dos
        # dialogos modales.

        if formulario.venta_para_contrato:

            self.abrir_contrato(
                formulario.venta_para_contrato
            )

            return

        self.cargar_datos()

    def abrir_contrato(self, id_venta):
        """
        Abre el contrato de una venta concreta,
        buscando sus datos en la base.
        """

        venta = self.buscar_venta(id_venta)

        if venta is None:

            self.mostrar_mensaje_error(
                "No se encontró la venta."
            )

            self.cargar_datos()

            return

        ContratoForm(self, venta).exec()

        self.cargar_datos()

    def buscar_venta(self, id_venta):
        """
        Los datos de una venta concreta.

        Devuelve la tupla que necesita
        ContratoForm, o None si no existe.
        """

        for venta in self.proteger(obtener_ventas) or []:

            if venta[0] == id_venta:

                return venta

        return None

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
    # CONTRATO
    # =============================

    def crear_contrato(self, fila):
        """
        Abre el contrato de la venta elegida.

        Es el mismo formulario que usa el botón
        "+ Nuevo contrato" del módulo Contratos:
        el contrato siempre nace de una venta.
        """

        id_venta = self.leer_id_venta(fila)

        if id_venta is None:

            return

        # ------------------------------
        # ¿YA TIENE CONTRATO?
        # ------------------------------

        existente = self.proteger(
            contrato_de_venta,
            id_venta
        )

        if existente:

            self.mostrar_mensaje_error(
                f"La venta {id_venta} ya tiene el "
                f"contrato {existente['numero']}.\n\n"
                "Una venta solo admite un contrato. "
                "Si hay que rehacerlo, cancélalo "
                "desde el módulo Contratos y vuelve "
                "a intentarlo."
            )

            return

        # ------------------------------
        # DATOS DE LA VENTA
        # ------------------------------
        # La venta sale de los datos ya
        # cargados, no de una consulta nueva:
        # la fila tiene justo lo que necesita el
        # formulario.

        filas = getattr(self, "filas", [])

        if fila < 0 or fila >= len(filas):

            self.mostrar_mensaje_error(
                "No se encontró la venta."
            )

            return

        # Los datos ya están cargados en self.filas:
        # la fila tiene justo lo que necesita el
        # formulario, así que no hay que volver a
        # consultar.

        ContratoForm(self, filas[fila]).exec()

        self.cargar_datos()

    def leer_id_venta(self, fila):

        item = self.tabla.item(fila, 0)

        if not item:

            return None

        try:

            return int(item.text())

        except ValueError:

            return None

    # =============================
    # ANULACIÓN
    # =============================

    def eliminar_venta(self, fila):

        item = self.tabla.item(fila, 0)

        if not item:

            return

        id_venta = int(item.text())

        # ------------------------------
        # CONTRATO VIVO
        # ------------------------------
        # Se comprueba antes de preguntar por
        # la confirmación: el usuario no tiene
        # por qué ver una pregunta si luego no
        # va a poder hacer nada.

        numero = self.proteger(
            venta_bloqueada_por_contrato,
            id_venta
        )

        if numero:

            self.mostrar_mensaje_error(
                f"La venta {id_venta} tiene el "
                f"contrato {numero} y no se puede "
                "anular.\n\n"
                "Un contrato es un documento "
                "firmado: si la operación se cayó, "
                "hay que anular antes el contrato."
            )

            return

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
