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

from PySide6.QtCore import Qt, Signal

import sesion as modulo_sesion

from permisos import (
    tiene_permiso,
    VER_TABLERO,
    VER_VEHICULOS,
    GESTIONAR_VEHICULOS,
    VER_MARCAS,
    GESTIONAR_MARCAS,
    VER_CLIENTES,
    GESTIONAR_CLIENTES,
    VER_VENTAS,
    REGISTRAR_VENTAS,
    GESTIONAR_VENTAS,
    VER_REPORTES,
    GESTIONAR_USUARIOS,
    VER_CONFIGURACION
)

from database.configuracion import NOMBRE_SISTEMA

from gui.dashboard_view import DashboardView
from gui.autos_view import AutosView
from gui.marcas_view import MarcasView
from gui.clientes_view import ClientesView
from gui.ventas_view import VentasView
from gui.reportes_view import ReportesView
from gui.usuarios_view import UsuariosView
from gui.configuracion_view import ConfiguracionView


class VentanaPrincipal(QMainWindow):

    # ==========================================
    # SECCIONES
    # ==========================================
    # Cada entrada es
    # (texto, clase_de_la_vista, permiso_para_ver)
    #
    # La vista NO se construye si el rol no
    # tiene el permiso de lectura: así ni
    # siquiera existe el widget prohibido.
    # ==========================================

    SECCIONES = [
        ("🏠  Inicio", DashboardView, VER_TABLERO),
        ("🚗  Vehículos", AutosView, VER_VEHICULOS),
        ("🏷  Marcas", MarcasView, VER_MARCAS),
        ("👤  Clientes", ClientesView, VER_CLIENTES),
        ("💰  Ventas", VentasView, VER_VENTAS),
        ("📊  Reportes", ReportesView, VER_REPORTES),
        ("👥  Usuarios", UsuariosView, GESTIONAR_USUARIOS),
        ("⚙  Configuración",
         ConfiguracionView,
         VER_CONFIGURACION)
    ]

    solicitar_cierre_sesion = Signal()

    def __init__(self):
        super().__init__()

        sesion = modulo_sesion.obtener_sesion()

        if not sesion.activa:

            # Sin sesión no se abre el sistema: es
            # la protección contra saltarse el
            # login.

            raise PermissionError(
                "No hay sesión activa."
            )

        titulo = NOMBRE_SISTEMA

        if sesion.nombre_completo:

            titulo = (
                f"{titulo} — "
                f"{sesion.nombre_completo}"
            )

        self.setWindowTitle(titulo)

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

        layout_principal.addWidget(sidebar)
        layout_principal.addWidget(self.paginas)

        self.construir_paginas()

    # ==========================================
    # PÁGINAS
    # ==========================================

    def construir_paginas(self):
        """
        Solo se crean las vistas permitidas al
        rol en sesión.
        """

        self.botones_menu = []

        for texto, vista, permiso in self.SECCIONES:

            if not tiene_permiso(permiso):
                continue

            pagina = self.crear_vista(
                vista,
                texto
            )

            indice = self.paginas.addWidget(pagina)

            boton = QPushButton(texto)

            boton.setObjectName(
                "boton_menu"
            )

            boton.clicked.connect(
                lambda _, i=indice: self.navegar(i)
            )

            self.contenedor_menu.addWidget(boton)

            self.botones_menu.append(boton)

        if not self.botones_menu:

            # Un rol sin ninguna sección legible
            # no debería poder iniciar sesión, pero
            # si llegara aquí se cierra la ventana
            # en vez de mostrar un marco vacío.

            self.marcar_activo(0)

            return

        self.marcar_activo(0)

    def crear_vista(self, vista, texto):
        """
        Pasa a cada vista solo lo que necesita
        para esconder los botones que el rol no
        puede usar.
        """

        if vista is AutosView:

            return vista(
                puede_gestionar=tiene_permiso(
                    GESTIONAR_VEHICULOS
                )
            )

        if vista is MarcasView:

            return vista(
                puede_gestionar=tiene_permiso(
                    GESTIONAR_MARCAS
                )
            )

        if vista is ClientesView:

            return vista(
                puede_gestionar=tiene_permiso(
                    GESTIONAR_CLIENTES
                )
            )

        if vista is VentasView:

            return vista(
                puede_registrar=tiene_permiso(
                    REGISTRAR_VENTAS
                ),
                puede_gestionar=tiene_permiso(
                    GESTIONAR_VENTAS
                )
            )

        return vista()

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

        self.contenedor_menu = QVBoxLayout()
        self.contenedor_menu.setSpacing(10)

        layout.addLayout(self.contenedor_menu)

        layout.addStretch()

        # ------------------------------
        # USUARIO
        # ------------------------------

        self.etiqueta_usuario = self.crear_bloque_usuario()

        layout.addWidget(self.etiqueta_usuario)

        # ------------------------------
        # CERRAR SESIÓN
        # ------------------------------

        boton_salir = QPushButton(
            "🚪  Cerrar sesión"
        )

        boton_salir.setObjectName(
            "boton_salir"
        )

        boton_salir.clicked.connect(
            self.cerrar_sesion
        )

        layout.addWidget(boton_salir)

        return sidebar

    def crear_bloque_usuario(self):

        sesion = modulo_sesion.obtener_sesion()

        marco = QFrame()
        marco.setObjectName("bloque_usuario")

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        marco.setLayout(layout)

        nombre = QLabel(
            sesion.nombre_usuario or ""
        )

        nombre.setObjectName(
            "usuario_nombre"
        )

        rol = QLabel(
            "Administrador"
            if sesion.es_administrador
            else "Vendedor"
        )

        rol.setObjectName(
            "usuario_rol"
        )

        layout.addWidget(nombre)
        layout.addWidget(rol)

        return marco

    # ==========================================
    # NAVEGACIÓN
    # ==========================================

    def navegar(self, indice):
        """
        Cambia de sección y refresca los datos de
        la página destino.
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

    # ==========================================
    # CERRAR SESIÓN
    # ==========================================

    def cerrar_sesion(self):

        from PySide6.QtWidgets import QMessageBox

        respuesta = QMessageBox.question(
            self,
            "Cerrar sesión",
            "¿Seguro que quieres cerrar la sesión?",
            QMessageBox.Yes | QMessageBox.No
        )

        if respuesta != QMessageBox.Yes:
            return

        # Destruir la sesión antes de cerrar la
        # ventana: si algo queda visible, ya no
        # puede hacer nada contra la base.

        modulo_sesion.cerrar_sesion()

        self.solicitar_cierre_sesion.emit()

        self.hide()
