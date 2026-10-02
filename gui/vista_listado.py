# ==========================================
# VISTA DE LISTADO
# ==========================================
# Base de las pantallas de listado: vehículos,
# marcas, clientes, ventas y usuarios.
#
# Antes cada una repetía el mismo esqueleto:
# encabezado, botón de alta, buscador, tabla y
# el mensaje de "sin resultados". Esa copia
# quintuplicada era el punto donde se colaban
# las diferencias.
#
# Aquí queda una sola vez. Cada vista concreta
# solo declara sus columnas y cómo pintar cada
# fila.
#
# Uso típico:
#
#     class MiVista(VistaListado):
#
#         columnas = ["ID", "Nombre", "Acciones"]
#
#         def __init__(self):
#             super().__init__(puede_gestionar=True)
#
#         def cargar_datos(self):
#             self.mostrar_filas(buscar())
# ==========================================


from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QStackedWidget
)

from utils.helpers import (
    crear_tabla,
    celda,
    crear_busqueda,
    crear_estado_vacio,
    crear_boton_principal,
    crear_titulo,
    ancho_acciones_para
)

from gui.vista_base import VistaBase


class VistaListado(VistaBase):
    """
    Pantalla de listado con búsqueda.
    """

    # ------------------------------
    # LO QUE DECLARA CADA VISTA
    # ------------------------------

    titulo = "Listado"

    columnas = []

    # Placeholder del buscador.

    placeholder_busqueda = "Buscar..."

    # Texto del botón de alta.

    texto_nuevo = "+ Nuevo"

    # Estructura de la tabla.

    columna_acciones = None

    # Editar (60) + Eliminar (72) con sus
    # separaciones, el margen y la barra de
    # desplazamiento vertical. Se calcula en
    # vez de poner 148 a mano: 148 se quedaba
    # corto y los botones se salían de su celda
    # encima de la columna vecina. Las vistas
    # con más botones (ventas, contratos) lo
    # recalculan con los suyos.

    ancho_acciones = ancho_acciones_para([60, 72])

    anchos_fijos = None

    # Estado vacío.

    mensaje_vacio = "Todavía no hay registros"
    detalle_vacio = ""

    # Si la vista no tiene búsqueda (Reportes).

    con_busqueda = True

    def __init__(
        self,
        parent=None,
        puede_gestionar=True,
        con_busqueda=True
    ):
        super().__init__(parent)

        self.puede_gestionar = puede_gestionar

        self.con_busqueda = con_busqueda

        self.crear_interfaz()

        self.cargar_datos()

    # =============================
    # INTERFAZ
    # =============================

    def crear_interfaz(self):

        layout_principal = QVBoxLayout()

        layout_principal.setContentsMargins(
            30, 25, 30, 25
        )

        layout_principal.setSpacing(18)

        self.setLayout(layout_principal)

        layout_principal.addLayout(
            self.crear_encabezado()
        )

        if self.con_busqueda:

            layout_principal.addWidget(
                self.crear_buscador()
            )

        # ------------------------------
        # TABLA O ESTADO VACÍO
        # ------------------------------
        # Un QStackedWidget alterna entre la
        # tabla y el aviso: así el hueco vacío se
        # explica en vez de parecer un fallo.
        # ------------------------------

        self.contenedor = QStackedWidget()

        self.tabla = crear_tabla(
            self.columnas,
            columna_acciones=self.columna_acciones,
            ancho_acciones=self.ancho_acciones,
            anchos_fijos=self.anchos_fijos
        )

        self.estado_vacio = crear_estado_vacio(
            self.mensaje_vacio,
            self.detalle_vacio
        )

        self.contenedor.addWidget(self.tabla)

        self.contenedor.addWidget(
            self.estado_vacio
        )

        layout_principal.addWidget(
            self.contenedor
        )

    def crear_encabezado(self):

        layout = QHBoxLayout()

        columna = QVBoxLayout()
        columna.setSpacing(2)

        columna.addWidget(
            crear_titulo(self.titulo)
        )

        self.etiqueta_conteo = QLabel("")

        self.etiqueta_conteo.setObjectName(
            "subtitulo"
        )

        columna.addWidget(
            self.etiqueta_conteo
        )

        layout.addLayout(columna)

        layout.addStretch()

        # ------------------------------
        # ACCIONES DEL ENCABEZADO
        # ------------------------------
        # La subclase puede añadir botones
        # (exportar, restaurar...) en
        # self.acciones_encabezado.
        # ------------------------------

        self.acciones_encabezado = QHBoxLayout()
        self.acciones_encabezado.setSpacing(10)

        self.boton_nuevo = crear_boton_principal(
            self.texto_nuevo,
            self.nuevo_registro
        )

        if self.muestra_boton_nuevo():

            self.acciones_encabezado.addWidget(
                self.boton_nuevo
            )

        layout.addLayout(
            self.acciones_encabezado
        )

        return layout

    def muestra_boton_nuevo(self):
        """
        El botón de alta solo aparece si la vista
        además sabe abrir su formulario.
        """

        return (
            self.puede_gestionar
            and hasattr(self, "nuevo_registro")
        )

    def crear_buscador(self):

        self.contenedor_busqueda = crear_busqueda(
            self.placeholder_busqueda,
            self.buscar
        )

        return self.contenedor_busqueda

    # =============================
    # PINTADO
    # =============================

    def mostrar_de(self, operacion, *args):
        """
        Consulta protegida y vuelca el resultado.

        proteger() devuelve None cuando la
        consulta falla, así que hay que mirar
        antes de pedirle el tamaño. Esta comprobación
        la hacen las cinco vistas.
        """

        resultado = self.proteger(
            operacion,
            *args
        )

        if resultado is None:

            return

        self.mostrar_filas(resultado)

    def mostrar_filas(self, filas):
        """
        Vuelca las filas en la tabla y decide si
        se ve la tabla o el estado vacío.

        Las subclases llaman a esto desde
        cargar_datos() y buscar().
        """

        self.filas = filas

        vacio = len(filas) == 0

        self.contenedor.setCurrentIndex(
            1 if vacio else 0
        )

        if vacio:

            self.etiqueta_conteo.setText("")

            return

        self.tabla.setRowCount(len(filas))

        for fila, registro in enumerate(filas):

            self.pintar_fila(fila, registro)

        self.actualizar_conteo()

    def pintar_fila(self, fila, registro):
        """
        Qué hacer con cada registro. Por defecto
        no pinta nada: cada vista lo define.
        """

    def marcar_columnas(self, fila, valores, centrar=None):
        """
        Escribe una lista de valores en columnas
        consecutivas.

        centrar es el conjunto de índices que van
        centrados; si no se indica, ninguno.
        """

        centrar = centrar or set()

        for columna, valor in enumerate(valores):

            self.tabla.setItem(
                fila,
                columna,
                self.crear_celda(
                    valor,
                    centrar=columna in centrar
                )
            )

    def crear_celda(self, valor, centrar=False, objeto=None):

        return celda(
            valor,
            centrar=centrar,
            objeto=objeto
        )

    def poner_acciones(self, fila, widget):

        if self.columna_acciones is None:
            return

        self.tabla.setCellWidget(
            fila,
            self.columna_acciones,
            widget
        )

    def leer_valores(self, fila, columnas):
        """
        Lee N celdas consecutivas de una fila.

        Devuelve None si falta alguna en vez de
        inventar un vacío: las vistas convierten
        los valores a int/float y un "" inesperado
        reventaría el formulario de edición.
        """

        valores = []

        for columna in range(columnas):

            item = self.tabla.item(fila, columna)

            if item is None:

                return None

            valores.append(item.text())

        return valores

    def actualizar_conteo(self, sufijo="registros"):

        total = len(getattr(self, "filas", []))

        plural = sufijo if total == 1 else sufijo + "s"

        self.etiqueta_conteo.setText(
            f"{total} {plural}"
        )

    def actualizar_conteo_con(self, texto):

        self.etiqueta_conteo.setText(texto)

    # =============================
    # A REEMPLAZAR
    # =============================

    def nuevo_registro(self):
        """
        Abre el formulario de alta. Solo lo
        invocan las vistas que pueden escribir.
        """

    def cargar_datos(self):
        """
        Consulta la base y llama a mostrar_filas.
        """

    def buscar(self, texto):
        """
        Filtra. Por defecto, texto vacío recarga
        todo; cada vista sustituye la búsqueda
        real.
        """

        self.cargar_datos()

    # =============================
    # CONFIRMACIONES
    # =============================

    def confirmar_borrado(self, nombre, extra=""):
        """
        Confirmación de borrado con el texto de
        "no se puede deshacer".
        """

        mensaje = (
            f"¿Eliminar {nombre}?\n\n"
            "Esta acción no se puede deshacer."
        )

        if extra:

            mensaje += f"\n\n{extra}"

        return self.confirmar(
            "Confirmar borrado",
            mensaje
        )
