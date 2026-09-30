from PySide6.QtWidgets import (
    QMainWindow,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QStackedWidget
)

from PySide6.QtCore import Qt

from database.configuracion import NOMBRE_SISTEMA

from gui.dashboard_view import DashboardView
from gui.autos_view import AutosView
from gui.marcas_view import MarcasView
from gui.clientes_view import ClientesView
from gui.ventas_view import VentasView
from gui.reportes_view import ReportesView
from gui.configuracion_view import ConfiguracionView


class VentanaPrincipal(QMainWindow):

    # =============================
    # SECCIONES
    # =============================
    # El orden de esta lista es el orden de las
    # páginas en el QStackedWidget, y el índice
    # es el que usa la barra lateral.
    # =============================

    SECCIONES = [
        ("🏠  Inicio", 0),
        ("🚗  Vehículos", 1),
        ("🏷  Marcas", 2),
        ("👤  Clientes", 3),
        ("💰  Ventas", 4),
        ("📊  Reportes", 5),
        ("⚙  Configuración", 6)
    ]

    def __init__(self):
        super().__init__()

        self.setWindowTitle(NOMBRE_SISTEMA)
        self.resize(1200, 700)

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

        self.paginas.addWidget(DashboardView())
        self.paginas.addWidget(AutosView())
        self.paginas.addWidget(MarcasView())
        self.paginas.addWidget(ClientesView())
        self.paginas.addWidget(VentasView())
        self.paginas.addWidget(ReportesView())
        self.paginas.addWidget(ConfiguracionView())

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

        # Se guardan las referencias para poder
        # marcar la sección activa.
        self.botones_menu = []

        for texto, indice in self.SECCIONES:

            boton = QPushButton(texto)

            boton.setObjectName(
                "boton_menu"
            )

            boton.clicked.connect(
                lambda _, i=indice: self.navegar(i)
            )

            layout.addWidget(boton)

            self.botones_menu.append(boton)

        layout.addStretch()

        # Estado inicial
        self.marcar_activo(0)

        return sidebar

    # ==========================================
    # NAVEGACIÓN
    # ==========================================

    def navegar(self, indice):
        """
        Cambia de sección y refresca los datos de
        la página destino, para que un cambio
        hecho en otra sección se vea al volver.
        """

        self.paginas.setCurrentIndex(indice)

        self.marcar_activo(indice)

        pagina = self.paginas.widget(indice)

        recargar = getattr(
            pagina,
            "cargar_datos",
            None
        )

        if callable(recargar):
            recargar()

    def marcar_activo(self, indice):

        for posicion, boton in enumerate(self.botones_menu):

            if posicion == indice:
                boton.setObjectName(
                    "boton_menu_activo"
                )
            else:
                boton.setObjectName(
                    "boton_menu"
                )

            # Hay que reaplicar el estilo tras
            # cambiar el objectName.

            boton.style().unpolish(boton)
            boton.style().polish(boton)
