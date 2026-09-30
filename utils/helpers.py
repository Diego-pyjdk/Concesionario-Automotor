# ==========================================
# COMPONENTES REUTILIZABLES
# ==========================================
# Todo el estilo vive en gui/estilo.css y se
# aplica con setObjectName. Aqui solo se
# construye la geometría, nunca el color.
# ==========================================


from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QCheckBox,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView
)

from PySide6.QtCore import Qt


# ==========================================
# TABLA
# ==========================================

def crear_tabla(columnas, columna_acciones=None, ancho_acciones=148):
    """
    Crea una tabla con la configuración estándar
    de la aplicación: columnas elásticas, sin
    edición directa y filas alternadas.
    """

    tabla = QTableWidget()

    tabla.setColumnCount(len(columnas))

    tabla.setHorizontalHeaderLabels(columnas)

    tabla.horizontalHeader().setSectionResizeMode(
        QHeaderView.Stretch
    )

    if columna_acciones is not None:
        tabla.horizontalHeader().setSectionResizeMode(
            columna_acciones,
            QHeaderView.Fixed
        )

        tabla.setColumnWidth(
            columna_acciones,
            ancho_acciones
        )

    tabla.setSelectionBehavior(
        QTableWidget.SelectRows
    )

    tabla.setEditTriggers(
        QTableWidget.NoEditTriggers
    )

    tabla.setAlternatingRowColors(True)

    return tabla


def celda(texto, centrar=False):
    """
    Crea un item de tabla a partir de un valor
    de la base de datos.
    """

    item = QTableWidgetItem(str(texto))

    if centrar:
        item.setTextAlignment(Qt.AlignCenter)

    return item


# ==========================================
# BOTONES DE ACCIÓN
# ==========================================

def crear_botones_accion(
    al_editar,
    al_eliminar,
    texto_editar="Editar",
    texto_eliminar="Eliminar",
    mostrar_eliminar=True
):
    """
    Contenedor con los botones de acción que se
    incrustan en la última columna de una tabla.

    texto_editar y texto_eliminar permiten
    adaptar la etiqueta: una venta no se edita,
    así que su primer botón muestra el detalle.

    mostrar_eliminar=False deja el botón fuera
    para los roles que no pueden borrar. Ojo:
    eso solo esconde el botón. La operación
    sigue protegida en database/*.py.

    Las callbacks reciben la fila como argumento,
    así que quien las conecta debe capturar el
    índice con un valor por defecto.
    """

    contenedor = QWidget()

    acciones = QHBoxLayout(contenedor)

    acciones.setContentsMargins(4, 2, 4, 2)

    acciones.setSpacing(6)

    boton_editar = QPushButton(texto_editar)

    boton_editar.setObjectName(
        "boton_editar"
    )

    boton_editar.setFixedSize(60, 30)

    boton_editar.setToolTip(
        texto_editar
    )

    boton_editar.clicked.connect(
        al_editar
    )

    boton_eliminar = QPushButton(texto_eliminar)

    boton_eliminar.setObjectName(
        "boton_eliminar"
    )

    boton_eliminar.setFixedSize(72, 30)

    boton_eliminar.setToolTip(
        texto_eliminar
    )

    boton_eliminar.clicked.connect(
        al_eliminar
    )

    acciones.addWidget(
        boton_editar
    )

    if mostrar_eliminar:

        acciones.addWidget(
            boton_eliminar
        )

    return contenedor


# ==========================================
# BOTONES
# ==========================================

def crear_boton_secundario(texto, al_hacer_click):
    """
    Botón que acompaña a uno principal dentro de
    un formulario. Necesita objectName porque la
    regla base de QPushButton está pensada para
    la barra lateral.
    """

    boton = QPushButton(texto)

    boton.setObjectName(
        "boton_secundario"
    )

    boton.clicked.connect(
        al_hacer_click
    )

    return boton


def crear_boton_principal(texto, al_hacer_click, altura=40):
    """
    Botón de acción destacada.
    """

    boton = QPushButton(texto)

    boton.setObjectName(
        "boton_principal"
    )

    boton.setFixedHeight(altura)

    boton.clicked.connect(
        al_hacer_click
    )

    return boton


def crear_titulo(texto):
    """
    Título de sección dentro de una vista.
    """

    titulo = QLabel(texto)

    titulo.setObjectName(
        "titulo"
    )

    return titulo


# ==========================================
# CAMPOS
# ==========================================

def crear_campo_contrasena(texto, confirmar=False):
    """
    Campo de contraseña con la opción de
    revelar lo escrito.

    Devuelve (campo, contenedor).
    """

    contenedor = QWidget()

    layout = QHBoxLayout(contenedor)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    campo = QLineEdit()
    campo.setEchoMode(QLineEdit.Password)
    campo.setPlaceholderText(texto)

    ver = QCheckBox("Ver")
    ver.setObjectName("casilla_ver")

    def alternar(marcado):

        if marcado:
            campo.setEchoMode(QLineEdit.Normal)
        else:
            campo.setEchoMode(QLineEdit.Password)

    ver.toggled.connect(alternar)

    layout.addWidget(campo)
    layout.addWidget(ver)

    contenedor.campo = campo

    if confirmar:
        return campo, contenedor

    return campo, contenedor
