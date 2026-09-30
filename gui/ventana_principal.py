from PySide6.QtWidgets import (
    QMainWindow,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QStackedWidget,
)
from PySide6.QtCore import Qt

from gui.autos_view import AutosView


class VentanaPrincipal(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Concesionario")
        self.resize(1200, 700)

        self.autos_view = AutosView()

        self.crear_interfaz()

    def crear_interfaz(self):

        contenedor = QWidget()
        self.setCentralWidget(contenedor)

        layout_principal = QHBoxLayout()
        layout_principal.setContentsMargins(0, 0, 0, 0)
        layout_principal.setSpacing(0)

        contenedor.setLayout(layout_principal)

        sidebar = self.crear_sidebar()

        self.paginas = QStackedWidget()

        dashboard = self.crear_dashboard()

        self.paginas.addWidget(dashboard)
        self.paginas.addWidget(self.autos_view)

        layout_principal.addWidget(sidebar)
        layout_principal.addWidget(self.paginas)

    # ==========================================
    # SIDEBAR
    # ==========================================

    def crear_sidebar(self):

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)

        layout = QVBoxLayout()
        layout.setContentsMargins(15, 20, 15, 20)
        layout.setSpacing(10)

        sidebar.setLayout(layout)

        titulo = QLabel("🚗 CONCESIONARIO")
        titulo.setObjectName("titulo_sidebar")
        titulo.setAlignment(Qt.AlignCenter)

        layout.addWidget(titulo)

        layout.addSpacing(20)

        boton_inicio = QPushButton("🏠  Inicio")
        boton_autos = QPushButton("🚗  Vehículos")
        boton_clientes = QPushButton("👤  Clientes")
        boton_ventas = QPushButton("💰  Ventas")
        boton_reportes = QPushButton("📊  Reportes")
        boton_configuracion = QPushButton("⚙  Configuración")

        layout.addWidget(boton_inicio)
        layout.addWidget(boton_autos)
        layout.addWidget(boton_clientes)
        layout.addWidget(boton_ventas)
        layout.addWidget(boton_reportes)
        layout.addWidget(boton_configuracion)

        layout.addStretch()

        # Navegación
        boton_inicio.clicked.connect(
            lambda: self.paginas.setCurrentIndex(0)
        )

        boton_autos.clicked.connect(
            lambda: self.paginas.setCurrentIndex(1)
        )

        return sidebar

    # ==========================================
    # DASHBOARD
    # ==========================================

    def crear_dashboard(self):

        contenido = QFrame()

        layout = QVBoxLayout()
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(20)

        contenido.setLayout(layout)

        titulo = QLabel("Panel principal")
        titulo.setObjectName("titulo")

        layout.addWidget(titulo)

        subtitulo = QLabel(
            "Bienvenido al sistema de gestión del concesionario"
        )

        layout.addWidget(subtitulo)

        tarjetas_layout = QHBoxLayout()
        tarjetas_layout.setSpacing(15)

        tarjetas_layout.addWidget(
            self.crear_tarjeta("🚗", "Vehículos", "0")
        )

        tarjetas_layout.addWidget(
            self.crear_tarjeta("👤", "Clientes", "0")
        )

        tarjetas_layout.addWidget(
            self.crear_tarjeta("💰", "Ventas", "0")
        )

        layout.addLayout(tarjetas_layout)

        actividad = QLabel("Actividad reciente")
        actividad.setObjectName("subtitulo")

        layout.addWidget(actividad)

        layout.addStretch()

        return contenido

    # ==========================================
    # TARJETA
    # ==========================================

    def crear_tarjeta(self, icono, nombre, cantidad):

        tarjeta = QFrame()
        tarjeta.setObjectName("tarjeta")

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)

        tarjeta.setLayout(layout)

        icono_label = QLabel(icono)
        icono_label.setObjectName("icono")

        nombre_label = QLabel(nombre)
        nombre_label.setObjectName("nombre_tarjeta")

        cantidad_label = QLabel(cantidad)
        cantidad_label.setObjectName("cantidad")

        layout.addWidget(icono_label)
        layout.addWidget(nombre_label)
        layout.addWidget(cantidad_label)

        return tarjeta