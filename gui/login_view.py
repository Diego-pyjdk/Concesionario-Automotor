# ==========================================
# LOGIN
# ==========================================
# Primera pantalla de la aplicación.
#
# No se construye VentanaPrincipal hasta que
# las credenciales son válidas: sin sesión no
# hay permisos y la ventana no serviría de nada.
#
# Muestra cuántos intentos quedan y bloquea la
# cuenta tras MAX_INTENTOS, en database/
# usuarios.py.
# ==========================================


from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit
)

from PySide6.QtCore import Qt

from database.usuarios import (
    autenticar,
    hay_usuarios
)

from database.configuracion import NOMBRE_SISTEMA

import sesion as modulo_sesion

from errores import ErrorSistema

from utils.validaciones import (
    texto_obligatorio,
    primer_error
)

from utils.registro import registrar_error

from utils.helpers import (
    crear_boton_principal,
    crear_boton_secundario
)


class LoginView(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(
            f"{NOMBRE_SISTEMA} - Iniciar sesión"
        )

        self.setObjectName("login")

        self.setFixedSize(440, 480)

        self.crear_interfaz()

        self.avisar_sin_usuarios()

        self.campo_usuario.setFocus()

    # =============================
    # INTERFAZ
    # =============================

    def crear_interfaz(self):

        layout_principal = QVBoxLayout()

        layout_principal.setContentsMargins(
            40, 35, 40, 35
        )

        layout_principal.setSpacing(12)

        self.setLayout(layout_principal)

        # ------------------------------
        # CABECERA
        # ------------------------------

        icono = QLabel("🚗")

        icono.setObjectName(
            "login_icono"
        )

        icono.setAlignment(Qt.AlignCenter)

        layout_principal.addWidget(icono)

        titulo = QLabel(NOMBRE_SISTEMA)

        titulo.setObjectName(
            "login_titulo"
        )

        titulo.setAlignment(Qt.AlignCenter)

        layout_principal.addWidget(titulo)

        subtitulo = QLabel(
            "Sistema de gestión de vehículos"
        )

        subtitulo.setObjectName(
            "login_subtitulo"
        )

        subtitulo.setAlignment(Qt.AlignCenter)

        layout_principal.addWidget(subtitulo)

        layout_principal.addSpacing(20)

        # ------------------------------
        # USUARIO
        # ------------------------------

        self.campo_usuario = QLineEdit()

        self.campo_usuario.setPlaceholderText(
            "Nombre de usuario"
        )

        self.campo_usuario.setObjectName(
            "campo_login"
        )

        self.campo_usuario.setMinimumHeight(42)

        layout_principal.addWidget(self.campo_usuario)

        # ------------------------------
        # CONTRASEÑA
        # ------------------------------

        self.campo_contrasena = QLineEdit()

        self.campo_contrasena.setPlaceholderText(
            "Contraseña"
        )

        self.campo_contrasena.setEchoMode(
            QLineEdit.Password
        )

        self.campo_contrasena.setObjectName(
            "campo_login"
        )

        self.campo_contrasena.setMinimumHeight(42)

        self.campo_contrasena.returnPressed.connect(
            self.entrar
        )

        layout_principal.addWidget(
            self.campo_contrasena
        )

        # ------------------------------
        # ERROR
        # ------------------------------

        self.etiqueta_error = QLabel("")

        self.etiqueta_error.setObjectName(
            "login_error"
        )

        self.etiqueta_error.setWordWrap(True)

        layout_principal.addWidget(
            self.etiqueta_error
        )

        layout_principal.addSpacing(10)

        # ------------------------------
        # BOTONES
        # ------------------------------

        botones = QHBoxLayout()

        boton_cancelar = crear_boton_secundario(
            "Cancelar",
            self.reject
        )

        boton_entrar = crear_boton_principal(
            "Iniciar sesión",
            self.entrar
        )

        botones.addWidget(
            boton_cancelar
        )

        botones.addWidget(
            boton_entrar
        )

        layout_principal.addLayout(botones)

        # ------------------------------
        # PIE
        # ------------------------------

        pie = QLabel(
            "Las contraseñas se guardan cifradas "
            "con PBKDF2."
        )

        pie.setObjectName(
            "login_pie"
        )

        pie.setAlignment(Qt.AlignCenter)

        pie.setWordWrap(True)

        layout_principal.addStretch()

        layout_principal.addWidget(pie)

    # =============================
    # ESTADO INICIAL
    # =============================

    def avisar_sin_usuarios(self):
        """
        Si la tabla está vacía no hay forma de
        entrar: hay que decirlo.
        """

        try:

            if hay_usuarios():
                return

        except ErrorSistema as error:

            registrar_error(error)

            self.mostrar_error(error.mensaje)

            return

        self.etiqueta_error.setText(
            "No hay ningún usuario creado.\n"
            "Ejecuta crear_admin.py para crear el "
            "primer administrador."
        )

        self.campo_usuario.setEnabled(False)

        self.campo_contrasena.setEnabled(False)

    # =============================
    # ERRORES
    # =============================

    def mostrar_error(self, mensaje):
        self.etiqueta_error.setText(mensaje)

    # =============================
    # ENTRAR
    # =============================

    def entrar(self):

        nombre_usuario = self.campo_usuario.text().strip()

        contrasena = self.campo_contrasena.text()

        error = primer_error([
            texto_obligatorio(
                nombre_usuario,
                "el usuario"
            )
        ])

        if error:

            self.mostrar_error(error)

            return

        try:

            correcto, mensaje, datos = autenticar(
                nombre_usuario,
                contrasena
            )

        except ErrorSistema as error_sistema:

            registrar_error(error_sistema)

            self.mostrar_error(
                error_sistema.mensaje
            )

            return

        if not correcto:

            self.mostrar_error(mensaje)

            self.campo_contrasena.clear()

            self.campo_contrasena.setFocus()

            return

        modulo_sesion.iniciar_sesion(datos)

        self.etiqueta_error.setText("")

        self.accept()
