# ==========================================
# LOGIN LUXURYCARS
# ==========================================
# La autenticación y la sesión conservan su flujo original.

from pathlib import Path

from database.usuarios import autenticar, hay_usuarios
from database.configuracion import NOMBRE_SISTEMA
import sesion as modulo_sesion
from errores import ErrorSistema
from utils.validaciones import texto_obligatorio, primer_error
from utils.registro import registrar_error

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPixmap, QLinearGradient
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QWidget, QPushButton, QFrame
)
from PySide6.QtSvgWidgets import QSvgWidget


RAIZ = Path(__file__).resolve().parents[1]


class PanelFotografia(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.imagen = QPixmap(str(RAIZ / "assets" / "login_fondo.png"))

        self.setMinimumWidth(0)

    def paintEvent(self, evento):
        # Recorte proporcional, nunca estirar la fotografía.
        pintor = QPainter(self)

        pintor.fillRect(self.rect(), QColor("#0b1422"))

        if not self.imagen.isNull():
            escala = max(
                self.width() / self.imagen.width(),
                self.height() / self.imagen.height()
            )

            ancho = self.width() / escala

            alto = self.height() / escala

            origen = QRectF(
                (self.imagen.width() - ancho) * 0.28,
                (self.imagen.height() - alto) / 2,
                ancho,
                alto
            )

            pintor.drawPixmap(QRectF(self.rect()), self.imagen, origen)

        sombra = QLinearGradient(0, 0, 0, self.height())

        sombra.setColorAt(0, QColor(4, 10, 20, 140))

        sombra.setColorAt(0.42, QColor(4, 10, 20, 5))

        sombra.setColorAt(1, QColor(4, 10, 20, 220))

        pintor.fillRect(self.rect(), sombra)

        pintor.end()


class LoginView(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"{NOMBRE_SISTEMA} - Iniciar sesión")

        self.setObjectName("login_luxury")

        self.setMinimumSize(620, 540)

        pantalla = QApplication.primaryScreen()

        disponible = pantalla.availableGeometry() if pantalla else None

        self.resize(
            min(1120, disponible.width() - 40) if disponible else 1120,
            min(710, disponible.height() - 60) if disponible else 710
        )

        self.crear_interfaz()

        self.avisar_sin_usuarios()

        self.boton_entrar.setEnabled(self.campo_usuario.isEnabled())

        self.campo_usuario.setFocus()

    def crear_interfaz(self):
        self.setStyleSheet("""
            QDialog#login_luxury { background: #0b1628; }
            QDialog#login_luxury QWidget { font-family: 'Segoe UI'; }
            QDialog#login_luxury QLabel {
                background: transparent; color: #f1f5fb; border: none;
            }
            QDialog#login_luxury QLabel#marca_luxury {
                font-size: 32px; font-weight: 600;
            }
            QDialog#login_luxury QLabel#lema_luxury {
                font-size: 30px; font-weight: 600;
            }
            QDialog#login_luxury QFrame#formulario_luxury {
                background: #0b1628; border: none;
            }
            QDialog#login_luxury QLabel#bienvenido_luxury {
                font-size: 35px; font-weight: 700;
            }
            QDialog#login_luxury QLabel#ayuda_luxury {
                color: #a3b2cb; font-size: 14px;
            }
            QDialog#login_luxury QLabel#etiqueta_luxury {
                font-size: 14px; font-weight: 500;
            }
            QDialog#login_luxury QLineEdit {
                background: #101d30; color: #f1f5fb;
                border: 1px solid #394b68; border-radius: 9px;
                padding: 12px; font-size: 14px;
                selection-background-color: #2563eb;
            }
            QDialog#login_luxury QLineEdit:focus { border: 1px solid #60a5fa; }
            QDialog#login_luxury QLineEdit:disabled { color: #8290a6; }
            QDialog#login_luxury QPushButton {
                background: transparent; color: #afc1df;
                border: none; border-radius: 9px; padding: 10px;
                font-size: 14px;
            }
            QDialog#login_luxury QPushButton:hover { background: #1a2b44; }
            QDialog#login_luxury QPushButton:focus { border: 1px solid #93c5fd; }
            QDialog#login_luxury QPushButton#entrar_luxury {
                background: #2563eb; color: #ffffff;
                font-size: 16px; font-weight: 600; padding: 14px;
            }
            QDialog#login_luxury QPushButton#entrar_luxury:hover { background: #3478f6; }
            QDialog#login_luxury QPushButton#entrar_luxury:pressed { background: #1d4ed8; }
            QDialog#login_luxury QPushButton#entrar_luxury:disabled {
                background: #283c5e; color: #a3b2cb;
            }
            QDialog#login_luxury QLabel#error_luxury {
                background: #362032; color: #fecdd3; border-radius: 6px;
                padding: 9px; font-size: 13px;
            }
        """)

        principal = QHBoxLayout(self)

        principal.setContentsMargins(0, 0, 0, 0)

        principal.setSpacing(0)

        self.fotografia = PanelFotografia()

        foto_layout = QVBoxLayout(self.fotografia)

        foto_layout.setContentsMargins(34, 36, 34, 38)

        self.logo = QSvgWidget(str(RAIZ / "assets" / "logo_luxurycars.svg"))

        self.logo.setFixedSize(260, 55)

        self.logo.setStyleSheet("background: transparent;")

        foto_layout.addWidget(self.logo)

        marca = QLabel(NOMBRE_SISTEMA)

        marca.setObjectName("marca_luxury")

        foto_layout.addWidget(marca)

        foto_layout.addStretch()

        lema = QLabel("Los autos de tus sueños en LuxuryCars")

        lema.setObjectName("lema_luxury")

        lema.setWordWrap(True)

        foto_layout.addWidget(lema)

        principal.addWidget(self.fotografia, 55)

        formulario = QFrame()

        formulario.setObjectName("formulario_luxury")

        formulario.setMinimumWidth(370)

        campos = QVBoxLayout(formulario)

        campos.setContentsMargins(34, 30, 34, 30)

        campos.setSpacing(12)

        campos.addStretch()

        acento = QLabel()

        acento.setFixedSize(40, 4)

        acento.setStyleSheet("background: #3b82f6; border-radius: 2px;")

        campos.addWidget(acento)

        campos.addSpacing(12)

        titulo = QLabel("Bienvenido")

        titulo.setObjectName("bienvenido_luxury")

        campos.addWidget(titulo)

        subtitulo = QLabel("Ingresá a tu cuenta para continuar")

        subtitulo.setObjectName("ayuda_luxury")

        subtitulo.setWordWrap(True)

        campos.addWidget(subtitulo)

        campos.addSpacing(20)

        etiqueta_usuario = QLabel("Usuario")

        etiqueta_usuario.setObjectName("etiqueta_luxury")

        campos.addWidget(etiqueta_usuario)

        self.campo_usuario = QLineEdit()

        self.campo_usuario.setPlaceholderText("Ingresá tu usuario")

        self.campo_usuario.setAccessibleName("Usuario")

        self.campo_usuario.setMinimumHeight(46)

        etiqueta_usuario.setBuddy(self.campo_usuario)

        campos.addWidget(self.campo_usuario)

        campos.addSpacing(8)

        etiqueta_clave = QLabel("Contraseña")

        etiqueta_clave.setObjectName("etiqueta_luxury")

        campos.addWidget(etiqueta_clave)

        fila_clave = QHBoxLayout()

        fila_clave.setSpacing(4)

        self.campo_contrasena = QLineEdit()

        self.campo_contrasena.setPlaceholderText("Ingresá tu contraseña")

        self.campo_contrasena.setAccessibleName("Contraseña")

        self.campo_contrasena.setEchoMode(QLineEdit.Password)

        self.campo_contrasena.setMinimumHeight(46)

        etiqueta_clave.setBuddy(self.campo_contrasena)

        fila_clave.addWidget(self.campo_contrasena, 1)

        self.boton_ver = QPushButton("Mostrar")

        self.boton_ver.setCheckable(True)

        self.boton_ver.setAutoDefault(False)

        self.boton_ver.setAccessibleName("Mostrar contraseña")

        self.boton_ver.toggled.connect(self.alternar_contrasena)

        fila_clave.addWidget(self.boton_ver)

        campos.addLayout(fila_clave)

        self.etiqueta_error = QLabel("")

        self.etiqueta_error.setObjectName("error_luxury")

        self.etiqueta_error.setTextFormat(Qt.PlainText)

        self.etiqueta_error.setWordWrap(True)

        self.etiqueta_error.hide()

        campos.addWidget(self.etiqueta_error)

        campos.addSpacing(12)

        self.boton_entrar = QPushButton("Iniciar sesión")

        self.boton_entrar.setObjectName("entrar_luxury")

        self.boton_entrar.setDefault(True)

        self.boton_entrar.clicked.connect(self.entrar)

        campos.addWidget(self.boton_entrar)

        cancelar = QPushButton("Cancelar")

        cancelar.setAutoDefault(False)

        cancelar.clicked.connect(self.reject)

        campos.addWidget(cancelar)

        campos.addStretch()

        principal.addWidget(formulario, 45)

        self.setTabOrder(self.campo_usuario, self.campo_contrasena)

        self.setTabOrder(self.campo_contrasena, self.boton_ver)

        self.setTabOrder(self.boton_ver, self.boton_entrar)

        self.setTabOrder(self.boton_entrar, cancelar)

    def alternar_contrasena(self, visible):
        self.campo_contrasena.setEchoMode(
            QLineEdit.Normal if visible else QLineEdit.Password
        )

        self.boton_ver.setText("Ocultar" if visible else "Mostrar")

        self.boton_ver.setAccessibleName(
            "Ocultar contraseña" if visible else "Mostrar contraseña"
        )

    def resizeEvent(self, evento):
        super().resizeEvent(evento)

        if hasattr(self, "fotografia"):
            # Pantallas pequeñas: priorizar el formulario completo.
            self.fotografia.setVisible(self.width() >= 850)

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

            self.campo_usuario.setEnabled(False)

            self.campo_contrasena.setEnabled(False)

            return

        self.etiqueta_error.setText(
            "No hay ningún usuario creado.\n"
            "Ejecuta crear_admin.py para crear el "
            "primer administrador."
        )

        self.etiqueta_error.setVisible(True)

        self.campo_usuario.setEnabled(False)

        self.campo_contrasena.setEnabled(False)

    # =============================
    # ERRORES
    # =============================

    def mostrar_error(self, mensaje):

        self.etiqueta_error.setText(mensaje)

        self.etiqueta_error.setVisible(True)

    def limpiar_error(self):
        """
        En vez de dejar el recuadro vacío flotando,
        se oculta.
        """

        self.etiqueta_error.setText("")

        self.etiqueta_error.setVisible(False)

    # =============================
    # ENTRAR
    # =============================

    def entrar(self):

        if not self.campo_usuario.isEnabled():

            return

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

        self.limpiar_error()

        self.accept()
