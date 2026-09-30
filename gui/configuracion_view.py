from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QTableWidgetItem
)

from database.configuracion import (
    NOMBRE_SISTEMA,
    VERSION_SISTEMA,
    estado_conexion
)

from utils.helpers import (
    crear_tabla,
    crear_boton_principal,
    crear_titulo
)


class ConfiguracionView(QWidget):

    def __init__(self):
        super().__init__()

        self.crear_interfaz()
        self.comprobar_conexion()

    def crear_interfaz(self):

        layout_principal = QVBoxLayout()

        layout_principal.setContentsMargins(
            30, 25, 30, 25
        )

        layout_principal.setSpacing(20)

        self.setLayout(layout_principal)

        layout_principal.addWidget(
            crear_titulo("Configuración")
        )

        subtitulo = QLabel(
            "Información del sistema y estado de la "
            "base de datos"
        )

        layout_principal.addWidget(subtitulo)

        # ------------------------------
        # DATOS DEL SISTEMA
        # ------------------------------

        panel_sistema = QFrame()
        panel_sistema.setObjectName("tarjeta")

        layout_sistema = QVBoxLayout()
        layout_sistema.setContentsMargins(20, 18, 20, 18)
        layout_sistema.setSpacing(10)

        titulo_sistema = QLabel("Sistema")
        titulo_sistema.setObjectName("subtitulo")

        layout_sistema.addWidget(titulo_sistema)

        self.tabla_sistema = crear_tabla(
            ["Campo", "Valor"]
        )

        self.tabla_sistema.setMaximumHeight(160)

        layout_sistema.addWidget(self.tabla_sistema)

        panel_sistema.setLayout(layout_sistema)

        # ------------------------------
        # CONEXIÓN
        # ------------------------------

        panel_conexion = QFrame()
        panel_conexion.setObjectName("tarjeta")

        layout_conexion = QVBoxLayout()
        layout_conexion.setContentsMargins(20, 18, 20, 18)
        layout_conexion.setSpacing(10)

        titulo_conexion = QLabel("Base de datos")
        titulo_conexion.setObjectName("subtitulo")

        layout_conexion.addWidget(titulo_conexion)

        self.etiqueta_estado = QLabel("")

        self.etiqueta_estado.setObjectName(
            "estado_conexion"
        )

        self.etiqueta_estado.setWordWrap(True)

        layout_conexion.addWidget(
            self.etiqueta_estado
        )

        self.tabla_conexion = crear_tabla(
            ["Detalle", "Valor"]
        )

        self.tabla_conexion.setMaximumHeight(120)

        layout_conexion.addWidget(
            self.tabla_conexion
        )

        botones = QHBoxLayout()

        botones.addWidget(
            crear_boton_principal(
                "Probar conexión",
                self.comprobar_conexion
            )
        )

        botones.addStretch()

        layout_conexion.addLayout(botones)

        panel_conexion.setLayout(layout_conexion)

        layout_principal.addWidget(panel_sistema)
        layout_principal.addWidget(panel_conexion)
        layout_principal.addStretch()

        # ------------------------------
        # DATOS FIJOS
        # ------------------------------

        self.cargar_sistema()

    def cargar_sistema(self):

        datos = [
            ("Nombre del sistema", NOMBRE_SISTEMA),
            ("Versión", VERSION_SISTEMA)
        ]

        self.tabla_sistema.setRowCount(len(datos))

        for fila, (campo, valor) in enumerate(datos):

            self.tabla_sistema.setItem(
                fila,
                0,
                QTableWidgetItem(campo)
            )

            self.tabla_sistema.setItem(
                fila,
                1,
                QTableWidgetItem(valor)
            )

    # =============================
    # CONEXIÓN
    # =============================

    def comprobar_conexion(self):

        conectado, detalle = estado_conexion()

        if conectado:
            self.etiqueta_estado.setText(
                "🟢  Conectado con MySQL"
            )

            self.etiqueta_estado.setObjectName(
                "estado_ok"
            )

        else:
            self.etiqueta_estado.setText(
                "🔴  Sin conexión con MySQL"
            )

            self.etiqueta_estado.setObjectName(
                "estado_error"
            )

        # Hay que reaplicar el estilo tras
        # cambiar el objectName.

        self.etiqueta_estado.style().unpolish(
            self.etiqueta_estado
        )

        self.etiqueta_estado.style().polish(
            self.etiqueta_estado
        )

        # ------------------------------
        # DETALLE
        # ------------------------------

        filas = [("Servidor MySQL", detalle)]

        self.tabla_conexion.setRowCount(len(filas))

        for fila, (campo, valor) in enumerate(filas):

            self.tabla_conexion.setItem(
                fila,
                0,
                QTableWidgetItem(campo)
            )

            self.tabla_conexion.setItem(
                fila,
                1,
                QTableWidgetItem(str(valor))
            )
