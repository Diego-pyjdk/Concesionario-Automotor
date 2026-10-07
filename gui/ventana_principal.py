from gui.login_view import PanelFotografia
from gui.vista_base import VistaBase
from gui.tema import aplicar_tema, AJUSTES
from gui.iconos import icono
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QScrollArea, QSizePolicy
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
    VER_CONTRATOS,
    GESTIONAR_CONTRATOS,
    VER_FINANCIERA,
    GESTIONAR_USUARIOS,
    VER_AUDITORIA,
    VER_CONFIGURACION
)

from database.configuracion import NOMBRE_SISTEMA

from database.auditoria import registrar_logout

from gui.dashboard_view import DashboardView
from gui.autos_view import AutosView
from gui.marcas_view import MarcasView
from gui.clientes_view import ClientesView
from gui.ventas_view import VentasView
from gui.contratos_view import ContratosView
from gui.cartera_view import CarteraView
from gui.reportes_view import ReportesView
from gui.usuarios_view import UsuariosView
from gui.auditoria_view import AuditoriaView
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
    #
    # Y aquí hay una cosa que no es obvia: la
    # lista de secciones tiene que coincidir
    # con el orden en que las pruebas las
    # recorren. tests/ cuenta cuántas ve el
    # administrador y cuántas el vendedor, y
    # un apartado nuevo cambia esos números.
    # ==========================================

    # La cartera va DESPUÉS de Contratos y antes
    # de Reportes, y por el orden de la
    # información: primero qué se vendió, luego
    # qué se debe, luego cómo va el negocio.
    #
    # Solo el administrador la ve. No es un
    # capricho: la cartera dice a cuánto debe
    # cada cliente del concesionario, no solo
    # los del vendedor, y trae el teléfono para
    # llamarle. Ver los contratos propios ya
    # puede en la sección anterior.

    SECCIONES = [
        ("🏠  Inicio", DashboardView, VER_TABLERO),
        ("🚗  Vehículos", AutosView, VER_VEHICULOS),
        ("🏷  Marcas", MarcasView, VER_MARCAS),
        ("👤  Clientes", ClientesView, VER_CLIENTES),
        ("💰  Ventas", VentasView, VER_VENTAS),
        ("📄  Contratos", ContratosView, VER_CONTRATOS),
        ("💳  Cartera", CarteraView, VER_FINANCIERA),
        ("📊  Reportes", ReportesView, VER_REPORTES),
        ("👥  Usuarios", UsuariosView, GESTIONAR_USUARIOS),
        ("🛡  Auditoría", AuditoriaView, VER_AUDITORIA),
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

        # Con siete columnas en contratos más los
        # botones de fila, 1200 px se quedaba
        # corto: el nombre del cliente salía con
        # puntos suspensivos. 1320 da el hueco
        # que necesitan; la ventana sigue
        # siendo redimensionable.
        self.resize(1320, 780)
        self.setMinimumSize(800, 540)

        self.crear_interfaz()

    def crear_interfaz(self):

        contenedor = PanelFotografia()
        self.setCentralWidget(contenedor)

        layout_principal = QHBoxLayout()
        layout_principal.setContentsMargins(0, 0, 0, 0)
        layout_principal.setSpacing(0)

        contenedor.setLayout(layout_principal)

        sidebar = self.crear_sidebar()

        self.paginas = QStackedWidget()

        self.sidebar = sidebar
        layout_principal.addWidget(sidebar)
        self.fondo_contenido = QWidget()
        self.fondo_contenido.setObjectName("contenido_luxury")
        columna = QVBoxLayout(self.fondo_contenido)
        columna.setContentsMargins(18, 0, 18, 18)
        columna.setSpacing(0)
        cabecera = QWidget()
        cabecera.setObjectName("cabecera_luxury")
        cabecera.setFixedHeight(140)
        rotulos = QVBoxLayout(cabecera)
        rotulos.setContentsMargins(24, 22, 24, 22)
        marca = QLabel(NOMBRE_SISTEMA)
        marca.setObjectName("marca_interior_luxury")
        lema = QLabel("Los autos de tus sueños en LuxuryCars")
        lema.setObjectName("lema_interior_luxury")
        lema.setWordWrap(True)
        rotulos.addWidget(marca)
        rotulos.addWidget(lema)
        columna.addWidget(cabecera)
        self.paginas.setObjectName("paginas_luxury")
        columna.addWidget(self.paginas, 1)
        layout_principal.addWidget(self.fondo_contenido, 1)
        self.actualizar_fondo_luxury()

        self.construir_paginas()
        if str(AJUSTES.value('menu_contraido','false')).lower() == 'true':
            self.alternar_menu()
        QTimer.singleShot(0, lambda: self.navegar(0))

    # ==========================================
    # PÁGINAS
    # ==========================================

    def construir_paginas(self):
        """
        Solo se crean las vistas permitidas al
        rol en sesión.
        """

        self.botones_menu = []
        self.definiciones = []
        self.paginas_creadas = set()
        self.vistas = {}
        self.grupos_menu = []
        grupo_anterior = None

        for texto, vista, permiso in self.SECCIONES:

            if not tiene_permiso(permiso):
                continue

            nombre = texto.split('  ', 1)[-1]
            grupo = ('Administración' if nombre in ('Usuarios','Auditoría','Configuración')
                     else 'Finanzas' if nombre in ('Contratos','Cartera','Reportes') else 'Operaciones')
            if grupo != grupo_anterior:
                etiqueta = QLabel(grupo.upper())
                etiqueta.setObjectName('grupo_menu')
                self.contenedor_menu.addWidget(etiqueta)
                self.grupos_menu.append(etiqueta)
                grupo_anterior = grupo
            pagina = QWidget()
            self.definiciones.append((vista, texto))

            indice = self.paginas.addWidget(pagina)

            boton = QPushButton(nombre)
            boton.setIcon(icono(nombre))
            boton.setToolTip(nombre)
            boton.setProperty('texto_completo', nombre)

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

        if vista is ContratosView:

            return vista(
                puede_gestionar=tiene_permiso(
                    GESTIONAR_CONTRATOS
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

        titulo = QLabel(NOMBRE_SISTEMA)
        self.titulo_sidebar = titulo
        titulo.setObjectName("titulo_sidebar")
        titulo.setAlignment(Qt.AlignCenter)

        layout.addWidget(titulo)

        layout.addSpacing(20)

        self.contenedor_menu = QVBoxLayout()
        self.contenedor_menu.setSpacing(8)
        self.contenedor_menu.setContentsMargins(0,0,0,0)

        menu = QWidget()
        menu.setObjectName('menu_sidebar')
        menu.setLayout(self.contenedor_menu)
        area = QScrollArea()
        area.setFrameShape(QFrame.NoFrame)
        area.setWidgetResizable(True)
        area.setWidget(menu)
        layout.addWidget(area, 1)

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

        self.boton_salir = boton_salir
        herramientas = QHBoxLayout()
        for texto, accion in [('☰', self.alternar_menu), ('◐', self.alternar_tema)]:
            boton = QPushButton(texto)
            boton.setObjectName('boton_herramienta')
            boton.setToolTip('Contraer menú' if texto == '☰' else 'Cambiar tema claro / oscuro')
            boton.clicked.connect(accion)
            herramientas.addWidget(boton)
        layout.addLayout(herramientas)
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

        if indice not in self.paginas_creadas:
            clase, texto = self.definiciones[indice]
            VistaBase.diferir_carga = True
            try:
                pagina = self.crear_vista(clase, texto)
            finally:
                VistaBase.diferir_carga = False
            anterior = self.paginas.widget(indice)
            self.paginas.removeWidget(anterior)
            anterior.deleteLater()
            area = QScrollArea()
            area.setFrameShape(QFrame.NoFrame)
            area.setWidgetResizable(True)
            pagina.setObjectName("pagina_luxury")
            pagina.setAutoFillBackground(False)
            for widget in pagina.findChildren(QWidget):
                if type(widget) is QWidget and not widget.objectName():
                    widget.setObjectName("superficie_transparente_luxury")
            area.setObjectName("area_luxury")
            area.setWidget(pagina)
            area.viewport().setAutoFillBackground(False)
            area.viewport().setObjectName("viewport_luxury")
            for desplazamiento in pagina.findChildren(QScrollArea):
                desplazamiento.setObjectName("area_luxury")
                desplazamiento.viewport().setAutoFillBackground(False)
                desplazamiento.viewport().setObjectName("viewport_luxury")
            area.setMinimumSize(0,0)
            area.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Ignored)
            self.paginas.insertWidget(indice, area)
            self.vistas[indice] = pagina
            self.paginas_creadas.add(indice)
            if hasattr(pagina, 'navegar_a'):
                pagina.navegar_a.connect(self.abrir_seccion)

        self.paginas.setCurrentIndex(indice)

        self.marcar_activo(indice)

        pagina = self.vistas[indice]

        recargar = getattr(
            pagina,
            "cargar_datos",
            None
        )

        if callable(recargar):

            recargar()

    def abrir_seccion(self, nombre):
        nueva = nombre == 'Nueva venta'
        nombre = 'Ventas' if nueva else nombre
        for indice, (_, texto) in enumerate(self.definiciones):
            if texto.split('  ', 1)[-1] == nombre:
                self.navegar(indice)
                if nueva:
                    QTimer.singleShot(0, self.vistas[indice].nuevo_registro)
                return

    def alternar_tema(self):
        aplicar_tema(not bool(QApplication.instance().property('tema_oscuro')))
        self.actualizar_fondo_luxury()

    def actualizar_fondo_luxury(self):
        # Solo los contenedores dejan ver la fotografía; las tablas y
        # tarjetas conservan sus superficies y colores de cada tema.
        oscuro = bool(QApplication.instance().property("tema_oscuro"))
        superficie = "rgba(11, 22, 40, 215)" if oscuro else "rgba(241, 245, 249, 230)"
        self.fondo_contenido.setStyleSheet("""
            QWidget#contenido_luxury, QWidget#cabecera_luxury,
            QWidget#pagina_luxury, QWidget#superficie_transparente_luxury,
            QScrollArea#area_luxury, QWidget#viewport_luxury {
                background: transparent; border: none;
            }
            QStackedWidget#paginas_luxury {
                background: %s; border-radius: 14px;
            }
            QLabel#marca_interior_luxury {
                background: transparent; color: #ffffff;
                font-size: 32px; font-weight: 700;
            }
            QLabel#lema_interior_luxury {
                background: transparent; color: #e2e8f0;
                font-size: 16px;
            }
        """ % superficie)

    def alternar_menu(self):
        contraido = self.sidebar.width() > 100
        self.sidebar.setFixedWidth(82 if contraido else 230)
        self.sidebar.setProperty('contraido', contraido)
        self.sidebar.style().unpolish(self.sidebar)
        self.sidebar.style().polish(self.sidebar)
        for boton in self.botones_menu:
            boton.style().unpolish(boton)
            boton.style().polish(boton)
        for boton in self.botones_menu:
            boton.setText('' if contraido else boton.property('texto_completo'))
        for etiqueta in self.grupos_menu:
            etiqueta.setVisible(not contraido)
        self.titulo_sidebar.setText('LC' if contraido else NOMBRE_SISTEMA)
        self.etiqueta_usuario.setVisible(not contraido)
        self.boton_salir.setText('Salir' if contraido else 'Cerrar sesión')
        AJUSTES.setValue('menu_contraido', contraido)

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

        # Se registra ANTES de destruir la sesión:
        # después ya no habría usuario al que
        # atribuírselo.

        registrar_logout()

        # Destruir la sesión antes de cerrar la
        # ventana: si algo queda visible, ya no
        # puede hacer nada contra la base.

        modulo_sesion.cerrar_sesion()

        self.solicitar_cierre_sesion.emit()

        self.hide()
