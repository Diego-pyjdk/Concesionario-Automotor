from utils.helpers import ancho_acciones_para
from PySide6.QtWidgets import QMenu
from gui.fichas_dialog import AutoFichaDialog
from utils.helpers import crear_boton_secundario
from PySide6.QtWidgets import QComboBox
from database.autos import (
    obtener_autos,
    buscar_autos,
    eliminar_auto as eliminar_auto_db
)

from utils.moneda import (
    formatear_numero,
    parsear_importe
)

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
    ancho_acciones = ancho_acciones_para([84])

    texto_nuevo = "+ Nuevo vehículo"

    placeholder_busqueda = "Buscar por modelo, marca..."

    mensaje_vacio = "Todavía no hay vehículos"

    detalle_vacio = (
        "Necesitas al menos una marca para "
        "poder registrar un vehículo."
    )

    def crear_interfaz(self):
        super().crear_interfaz()
        self.acciones_encabezado.addWidget(crear_boton_secundario('Ver ficha', self.abrir_ficha))
        self.tabla.cellDoubleClicked.connect(lambda fila, columna: self.abrir_ficha(fila))
        self.filtro_stock = QComboBox()
        self.filtro_stock.addItems(['Todo el inventario','Con stock','Sin stock'])
        self.filtro_stock.currentIndexChanged.connect(self.aplicar_filtro_stock)
        self.layout().insertWidget(2,self.filtro_stock)

    def mostrar_filas(self, filas):
        self.filas_completas = list(filas)
        self.aplicar_filtro_stock()

    def aplicar_filtro_stock(self, *_args):
        indice = self.filtro_stock.currentIndex()
        filas = getattr(self,'filas_completas',[])
        if indice == 1:
            filas = [fila for fila in filas if fila[6] > 0]
        elif indice == 2:
            filas = [fila for fila in filas if fila[6] <= 0]
        super().mostrar_filas(filas)

    def abrir_ficha(self, fila=None):
        if fila is None or isinstance(fila, bool):
            fila = self.tabla.currentRow()
        if fila < 0 or self.tabla.item(fila, 0) is None:
            return
        dialogo = AutoFichaDialog(self, int(self.tabla.item(fila, 0).text()))
        dialogo.exec()
        self.cargar_datos()

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

        boton = crear_botones_accion(lambda _, f=fila: self.menu_fila(f), None, texto_editar='Más…', mostrar_eliminar=False, ancho_editar=84)
        self.poner_acciones(fila, boton)

    def menu_fila(self, fila):
        menu = QMenu(self)
        menu.addAction('Ver ficha', lambda: self.abrir_ficha(fila))
        if self.puede_gestionar:
            menu.addAction('Editar', lambda: self.editar_auto(fila))
            menu.addSeparator()
            menu.addAction('Eliminar', lambda: self.eliminar_auto(fila))
        boton = self.tabla.cellWidget(fila, self.columna_acciones)
        menu.exec(boton.mapToGlobal(boton.rect().bottomLeft()))


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

        ------------------------------
        # EL PRECIO SE DESHACE CON
        # parsear_importe()
        # ------------------------------

        La columna 4 se pinta con `formatear_numero()` y
        aquí hay que deshacer ese texto para volver a
        tener el número. Antes era:

            float(datos[4].replace(",", ""))

        con el separador de miles COSIDO A LA COMA. Ese
        era el punto más frágil de la aplicación: con la
        moneda en guaraníes, que usa el punto de miles,
        `float("25.000.000")` es un ValueError y el botón
        **Editar** de cualquier vehículo de más de 999
        reventaba sin mensaje.

        Y si alguien cambiaba ese `replace` por
        `replace(".", "")` para arreglarlo sin mirar, un
        precio de 25.000.000 se leía como 25. Un error
        silencioso que vale mil veces menos, en el
        precio de un vehículo, que es el dato más
        importante de la ficha.

        `parsear_importe()` decide por la FORMA del
        texto: con dos puntos, son de miles. Con un punto
        y tres cifras detrás, también. No depende de lo
        que haya escrito quien llama.

        Y si aun así no se entiende, devuelve None y se
        dice que no se encontró el vehículo, en vez de
        reventar con un ValueError sin contexto.
        """

        datos = self.leer_valores(fila, 7)

        if datos is None:

            return None

        precio = parsear_importe(datos[4])

        if precio is None:

            return None

        return (
            int(datos[0]),
            datos[1],
            datos[2],
            int(datos[3]),
            float(precio),
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
