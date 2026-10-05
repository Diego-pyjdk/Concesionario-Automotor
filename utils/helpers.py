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
    QVBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox
)

from PySide6.QtGui import QColor

from PySide6.QtCore import Qt, QTimer

from errores import (
    ErrorValidacion,
    PermisoDenegado
)

from utils.registro import registrar_error


# ==========================================
# TABLA
# ==========================================

def crear_tabla(
    columnas,
    columna_acciones=None,
    ancho_acciones=148,
    anchos_fijos=None
):
    """
    Crea una tabla con la configuración estándar
    de la aplicación: columnas elásticas, sin
    edición directa y filas alternadas.

    anchos_fijos es un dict {columna: ancho} para
    las columnas que no deben repartirse el
    espacio (fechas, importes). Sin esto, Stretch
    las divide a partes iguales y el texto se
    corta en unas y sobra en otras.
    """

    tabla = QTableWidget()

    tabla.setColumnCount(len(columnas))

    tabla.setHorizontalHeaderLabels(columnas)

    tabla.horizontalHeader().setSectionResizeMode(
        QHeaderView.Stretch
    )

    if anchos_fijos:

        for indice, ancho in anchos_fijos.items():

            tabla.horizontalHeader().setSectionResizeMode(
                indice,
                QHeaderView.Fixed
            )

            tabla.setColumnWidth(indice, ancho)

    if columna_acciones is not None:
        tabla.horizontalHeader().setSectionResizeMode(
            columna_acciones,
            QHeaderView.Fixed
        )

        tabla.setColumnWidth(
            columna_acciones,
            ancho_acciones
        )

    # La columna de números de fila estorba:
    # todas las tablas tienen su propia columna
    # ID, así que sobra un índice duplicado.

    tabla.verticalHeader().setVisible(False)

    # Las tablas no se ordenan con el ratón, así
    # que el indicador de orden solo añade ruido.

    tabla.horizontalHeader().setSortIndicatorShown(
        False
    )

    # La altura por defecto la calcula Qt a
    # partir del texto, e ignora los widgets que
    # se incrustan en las celdas: los botones
    # Editar/Eliminar salían cortados. 44 px
    # deja sitio para un botón de 30 px con su
    # margen.
    tabla.verticalHeader().setDefaultSectionSize(44)

    tabla.setSelectionBehavior(
        QTableWidget.SelectRows
    )

    tabla.setSelectionMode(
        QTableWidget.SingleSelection
    )

    tabla.setEditTriggers(
        QTableWidget.NoEditTriggers
    )

    tabla.setAlternatingRowColors(True)

    tabla.setShowGrid(False)

    return tabla


# ==========================================
# TONOS DE CELDA
# ==========================================
# Una QTableWidgetItem no admite objectName, así
# que el color va como fondo. Todos los tonos
# viven aquí para no repetir códigos de color
# por las vistas.
# ==========================================

TONOS_CELDA = {
    "tono_ok": "#dcfce7",
    "tono_fuerte_ok": "#16a34a",
    "tono_info": "#dbeafe",
    "tono_aviso": "#fef3c7",
    "tono_peligro": "#fee2e2"
}


def celda(texto, centrar=False, objeto=None):
    """
    Crea un item de tabla a partir de un valor
    de la base de datos.

    objeto es el nombre de un tono (ver
    TONOS_CELDA) para pintar esa celda. Se usa
    en la auditoría.
    """

    item = QTableWidgetItem(str(texto))

    if centrar:
        item.setTextAlignment(Qt.AlignCenter)

    if objeto in TONOS_CELDA:

        fondo = QColor(TONOS_CELDA[objeto])

        item.setBackground(fondo)

        if objeto == "tono_fuerte_ok":
            item.setForeground(
                QColor("#ffffff")
            )

    return item


# ==========================================
# BOTONES DE ACCIÓN
# ==========================================

def crear_botones_accion(
    al_editar,
    al_eliminar,
    texto_editar="Editar",
    texto_eliminar="Eliminar",
    mostrar_eliminar=True,
    acciones_extra=None,
    ancho_editar=72,
    ancho_eliminar=94
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

    acciones_extra mete botones adicionales
    entre los dos, para las tablas que necesitan
    un tercer camino (una venta lleva Ver,
    Contrato y Eliminar). Cada uno es una tupla:

        (texto, al_hacer_click, objeto, ancho)

    "objeto" es el objectName del estilo (ver
    gui/estilo.css) y "ancho", sus píxeles.

    Los tres anchos tienen que casar con lo que
    devuelva ancho_acciones_para(), o los
    botones se salen de su celda.

    ------------------------------
    # LOS ANCHOS POR DEFECTO
    # ------------------------------

    72 y 94, MEDIDOS con la hoja de estilos puesta:
    "Editar" pide 68 y "Eliminar" pide 90 con
    `QPushButton#boton_editar` (11 px, negrita, sin
    relleno). Antes eran 60 y 72, y las dos palabras
    salían recortadas en clientes, autos, marcas y
    usuarios.

    Se miden CON la hoja puesta a propósito: sin ella
    Qt mide con la fuente por defecto y con su relleno,
    y "Eliminar" pide 110 en vez de 90. Arreglar los
    anchos con esa medición los deja todavía más
    cortos, porque el error va al revés.
    `test_los_botones_no_se_recortan` los comprueba
    todos contra `sizeHint()`, con la hoja puesta.

    Las callbacks reciben la fila como argumento,
    así que quien las conecta debe capturar el
    índice con un valor por defecto.
    """

    contenedor = QWidget()

    # Sin altura fija, Qt encoge el contenedor
    # hasta el alto del texto de la celda (unos
    # 25 px) y los botones de 30 px quedan
    # cortados a media altura.

    contenedor.setFixedHeight(34)

    acciones = QHBoxLayout(contenedor)

    acciones.setContentsMargins(4, 2, 4, 2)

    acciones.setSpacing(6)

    boton_editar = QPushButton(texto_editar)

    boton_editar.setObjectName(
        "boton_editar"
    )

    boton_editar.setFixedSize(ancho_editar, 30)

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

    boton_eliminar.setFixedSize(ancho_eliminar, 30)

    boton_eliminar.setToolTip(
        texto_eliminar
    )

    # ------------------------------
    # SOLO SE CONECTA SI SE MUESTRA
    # ------------------------------
    # Conectar un None revienta: clicked.connect(None)
    # da "Expected signal or callable, got NoneType".
    #
    # Antes se conectaba siempre y el botón se
    # añadía al layout solo si mostrar_eliminar, así
    # que pasar (al_eliminar=None, mostrar_eliminar=
    # False) reventaba al construir la fila. Como
    # hasta ahora todo el mundo pasaba la función de
    # borrar, no se había visto nunca.

    if al_eliminar is not None:

        boton_eliminar.clicked.connect(
            al_eliminar
        )

    acciones.addWidget(
        boton_editar
    )

    for texto, conectar, objeto, ancho in acciones_extra or []:

        boton_extra = QPushButton(texto)

        boton_extra.setObjectName(objeto)

        boton_extra.setFixedSize(ancho, 30)

        boton_extra.setToolTip(texto)

        boton_extra.clicked.connect(conectar)

        acciones.addWidget(boton_extra)

    if mostrar_eliminar:

        acciones.addWidget(
            boton_eliminar
        )

    return contenedor


# ==========================================
# BOTONES
# ==========================================

def avisar_error(padre, error):
    """
    Muestra un error controlado de un formulario.

    Los formularios llaman a database/*.py sin
    pasar por VistaBase.proteger(), así que una
    excepción (permiso denegado, clave repetida,
    conexión caída) escapaba del diálogo y
    ejecutaba la aplicación. Este helper las
    recoge y las enseña.

    Solo hay que envolver la llamada:

        try:
            insertar_cliente(...)
        except ErrorSistema as error:
            avisar_error(self, error)
            return
    """

    if isinstance(error, (ErrorValidacion, PermisoDenegado)):

        # Son previstos: el mensaje basta y no
        # ensucia el registro con ruido.

        texto = error.mensaje

    else:

        registrar_error(error)

        texto = (
            "No se pudo completar la operación.\n\n"
            "El detalle técnico está en "
            "registro_errores.log."
        )

    QMessageBox.warning(
        padre,
        "No se pudo completar la operación",
        texto
    )


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


def crear_boton_peligro(texto, al_hacer_click, altura=40):
    """
    Acción destructiva: borrar, anular, purgar.

    Se distingue del principal a propósito: un
    botón rojo en la misma pantalla que uno azul
    hace evidente cuál destruye datos.
    """

    boton = QPushButton(texto)

    boton.setObjectName(
        "boton_peligro"
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
# BÚSQUEDA
# ==========================================
# Tiempo que hay que dejar de escribir antes de
# filtrar. Sin esta espera cada tecla dispara
# una consulta a MySQL.
# ==========================================

ESPERA_BUSQUEDA_MS = 350


# ==========================================
# ANCHO DE LA COLUMNA DE ACCIONES
# ==========================================
# Un boton de accion va con setFixedSize, asi
# que el layout no lo puede encoger: si la
# columna se queda corta, los botones se salen
# de su celda y se pintan encima de la
# columna vecina.
#
# El ancho no se pone a ojo. Se calcula a
# partir de los botones que lleva, y se le
# suma el espacio de la barra de desplazamiento
# vertical, que Qt le resta al area visible de
# la tabla y que no se ve en el ancho de la
# columna.

ESPACIO_ACCIONES = 6

MARGEN_ACCIONES = 8

ANCHO_BARRA = 20


def ancho_acciones_para(anchos):
    """
    Ancho que necesita la columna de acciones
    para que quepan sus botones.

    anchos es la lista de anchos, en el mismo
    orden en que se pintan. Se pasan los del
    caso mas ancho (con todos los permisos),
    porque la columna es la misma para todos.
    """

    if not anchos:
        return 148

    return (
        sum(anchos)
        + ESPACIO_ACCIONES * (len(anchos) - 1)
        + MARGEN_ACCIONES
        + ANCHO_BARRA
    )


def ajustar_alto_tabla(tabla, maximo=340):
    """
    Ajusta la altura de una tabla al número de
    filas que tiene.

    Sin esto, una tabla con dos filas dentro de
    un setMaximumHeight() fijo se queda con
    una barra de desplazamiento y solo enseña
    la primera fila.
    """

    filas = tabla.rowCount()

    cabecera = tabla.horizontalHeader().height()

    if filas == 0:

        tabla.setFixedHeight(cabecera + 8)

        return

    alto_fila = tabla.rowHeight(0)

    tabla.setFixedHeight(
        min(cabecera + filas * alto_fila + 4, maximo)
    )


def crear_busqueda(placeholder, al_buscar, con_boton=True):
    """
    Campo de búsqueda con dos comportamientos:

      - Enter filsa en el acto
      - al dejar de escribir filtra solo

    Devuelve un contenedor con .campo y .boton
    (o el QLineEdit suelto si con_boton=False).
    El temporizador cuelga del campo para que
    quien lo use no tenga que acordarse de
    pararlo.
    """

    campo = QLineEdit()

    campo.setPlaceholderText(placeholder)

    campo.setClearButtonEnabled(True)

    campo.setFixedHeight(40)

    temporizador = QTimer(campo)

    temporizador.setSingleShot(True)

    temporizador.setInterval(ESPERA_BUSQUEDA_MS)

    temporizador.timeout.connect(
        lambda: _disparar(campo, al_buscar)
    )

    campo.returnPressed.connect(
        lambda: _disparar(campo, al_buscar)
    )

    campo.textChanged.connect(
        lambda texto: _al_teclear(campo, texto, temporizador)
    )

    campo.temporizador = temporizador

    if not con_boton:

        return campo

    contenedor = QWidget()

    layout = QHBoxLayout(contenedor)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)

    boton = QPushButton("🔍 Buscar")

    boton.setObjectName("boton_filtro")

    boton.setFixedHeight(40)

    boton.clicked.connect(
        lambda: _disparar(campo, al_buscar)
    )

    layout.addWidget(campo)
    layout.addWidget(boton)

    contenedor.campo = campo
    contenedor.boton = boton

    return contenedor


def _al_teclear(campo, texto, temporizador):
    """
    Vaciar el filtro no espera: sin texto no hay
    nada que filtrar, así que va de inmediato.
    """

    if not texto:
        return

    temporizador.start()


def _disparar(campo, al_buscar):
    """
    Filtra ya y cancela el filtrado automático
    pendiente, para no consultar dos veces por la
    misma pulsación.
    """

    temporizador = getattr(campo, "temporizador", None)

    if temporizador is not None:
        temporizador.stop()

    al_buscar(campo.text().strip())


# ==========================================
# ESTADO VACÍO
# ==========================================

def crear_estado_vacio(mensaje, detalle=""):
    """
    Aviso que ocupa el lugar de una tabla sin
    filas.

    Una tabla con encabezado y cero líneas parece
    un fallo; esto explica que aún no hay nada.
    """

    contenedor = QWidget()

    layout = QVBoxLayout(contenedor)
    layout.setContentsMargins(20, 40, 20, 40)
    layout.setSpacing(8)
    layout.addStretch()

    icono = QLabel("📭")

    icono.setObjectName("estado_vacio_icono")

    icono.setAlignment(Qt.AlignCenter)

    layout.addWidget(icono)

    texto = QLabel(mensaje)

    texto.setObjectName("estado_vacio_titulo")

    texto.setAlignment(Qt.AlignCenter)

    texto.setWordWrap(True)

    layout.addWidget(texto)

    if detalle:

        ayuda = QLabel(detalle)

        ayuda.setObjectName("estado_vacio_detalle")

        ayuda.setAlignment(Qt.AlignCenter)

        ayuda.setWordWrap(True)

        layout.addWidget(ayuda)

    layout.addStretch()

    return contenedor


# ==========================================
# TECLADO EN FORMULARIOS
# ==========================================
# Escape ya lo resuelve QDialog: cierra con
# reject() sin escribir nada.
#
# Return no: QLineEdit, QSpinBox y QComboBox se
# lo quedan y emiten returnPressed. Por eso cada
# formulario conecta sus campos al guardado.
# ==========================================

def conectar_enter_guardar(campos, guardar):
    """
    Conecta Return para guardar en los campos
    indicados.
    """

    for campo in campos:

        if campo is None:
            continue

        campo.returnPressed.connect(guardar)


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
