from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QLabel,
    QHBoxLayout,
    QMessageBox
)

from database.usuarios import (
    insertar_usuario,
    actualizar_usuario,
    usuario_existe
)

from permisos import (
    ROLES,
    ROL_ADMINISTRADOR,
    ROL_VENDEDOR
)

from errores import ErrorSistema

from utils.validaciones import (
    es_nombre_usuario,
    es_nombre_persona,
    es_contrasena,
    contrasenas_coinciden,
    primer_error
)

from utils.registro import registrar_error

from utils.helpers import (
    crear_boton_principal,
    crear_boton_secundario,
    crear_campo_contrasena,
    conectar_enter_guardar
)


class UsuarioForm(QDialog):

    def __init__(self, parent=None, usuario=None):
        super().__init__(parent)

        self.usuario = usuario

        self.setObjectName("usuario_form")

        if usuario:
            self.setWindowTitle("Editar usuario")
        else:
            self.setWindowTitle("Nuevo usuario")

        self.resize(480, 480)
        self.setMinimumWidth(360)

        self.crear_interfaz()

        if self.usuario:
            self.cargar_datos()

    def crear_interfaz(self):

        layout_principal = QVBoxLayout()
        self.setLayout(layout_principal)

        formulario = QFormLayout()

        # ------------------------------
        # USUARIO
        # ------------------------------

        self.campo_usuario = QLineEdit()
        self.campo_usuario.setPlaceholderText("Ej: jperez")

        # ------------------------------
        # NOMBRE
        # ------------------------------

        self.campo_nombre = QLineEdit()
        self.campo_nombre.setPlaceholderText(
            "Ej: Juan Pérez"
        )

        # ------------------------------
        # ROL
        # ------------------------------

        self.combo_rol = QComboBox()

        for rol in ROLES:

            if rol == ROL_ADMINISTRADOR:

                texto = "Administrador"

            elif rol == ROL_VENDEDOR:

                texto = "Vendedor"

            else:

                texto = rol

            self.combo_rol.addItem(texto, rol)

        # Por menor privilegio, una cuenta nueva
        # nace como vendedor. El administrador
        # tiene que elegir el rol a mano.

        indice_vendedor = self.combo_rol.findData(
            ROL_VENDEDOR
        )

        if indice_vendedor >= 0:

            self.combo_rol.setCurrentIndex(
                indice_vendedor
            )

        # ------------------------------
        # ACTIVO
        # ------------------------------

        self.casilla_activo = QCheckBox("Usuario activo")

        self.casilla_activo.setChecked(True)

        # ------------------------------
        # CONTRASEÑA
        # ------------------------------

        self.campo_contrasena, marco_contrasena = (
            crear_campo_contrasena(
                "Mínimo 8 caracteres, con letras "
                "y números"
            )
        )

        self.campo_repetir, marco_repetir = (
            crear_campo_contrasena(
                "Repite la contraseña",
                confirmar=True
            )
        )

        formulario.addRow("Usuario:", self.campo_usuario)
        formulario.addRow("Nombre completo:", self.campo_nombre)
        formulario.addRow("Rol:", self.combo_rol)
        formulario.addRow("", self.casilla_activo)
        formulario.addRow("Contraseña:", marco_contrasena)
        formulario.addRow("Repetir:", marco_repetir)

        layout_principal.addLayout(formulario)

        # ------------------------------
        # AVISO
        # ------------------------------

        self.etiqueta_aviso = QLabel("")

        self.etiqueta_aviso.setObjectName(
            "aviso"
        )

        self.etiqueta_aviso.setWordWrap(True)

        layout_principal.addWidget(
            self.etiqueta_aviso
        )

        if self.usuario:

            self.etiqueta_aviso.setText(
                "Deja la contraseña vacía para "
                "mantener la actual. Si la cambias, "
                "se reinician los intentos de acceso."
            )

        botones = QHBoxLayout()

        boton_cancelar = crear_boton_secundario(
            "Cancelar",
            self.reject
        )

        boton_guardar = crear_boton_principal(
            "Guardar",
            self.guardar
        )

        botones.addWidget(
            boton_cancelar
        )

        botones.addWidget(
            boton_guardar
        )

        layout_principal.addLayout(botones)

        conectar_enter_guardar(
            [
                self.campo_usuario,
                self.campo_nombre,
                self.campo_contrasena,
                self.campo_repetir
            ],
            self.guardar
        )

        self.campo_usuario.setFocus()

    def cargar_datos(self):

        (
            id_usuario,
            nombre_usuario,
            nombre_completo,
            rol,
            activo,
            ultimo_acceso
        ) = self.usuario

        self.campo_usuario.setText(
            nombre_usuario
        )

        self.campo_nombre.setText(
            nombre_completo
        )

        indice = self.combo_rol.findData(rol)

        if indice >= 0:

            self.combo_rol.setCurrentIndex(indice)

        self.casilla_activo.setChecked(
            activo == "Activo" or activo == 1
        )

    def guardar(self):

        self.limpiar_aviso()

        nombre_usuario = (
            self.campo_usuario.text().strip()
        )

        nombre_completo = (
            self.campo_nombre.text().strip()
        )

        contrasena = self.campo_contrasena.text()

        repetir = self.campo_repetir.text()

        rol = self.combo_rol.currentData()

        activo = self.casilla_activo.isChecked()

        id_usuario = None

        if self.usuario:

            id_usuario = self.usuario[0]

        # ------------------------------
        # VALIDACIONES
        # ------------------------------

        validaciones = [
            es_nombre_usuario(nombre_usuario),
            es_nombre_persona(
                nombre_completo,
                "El nombre completo"
            )
        ]

        # La contraseña solo es obligatoria al
        # crear; al editar se puede dejar igual.

        if not self.usuario or contrasena:

            validaciones.append(
                es_contrasena(contrasena)
            )

            validaciones.append(
                contrasenas_coinciden(
                    contrasena,
                    repetir
                )
            )

        error = primer_error(validaciones)

        if error:

            self.mostrar_error(error)

            return

        # ------------------------------
        # DUPLICADOS
        # ------------------------------

        try:

            if usuario_existe(
                nombre_usuario,
                id_usuario
            ):

                self.mostrar_error(
                    "Ya existe un usuario con ese "
                    "nombre de acceso."
                )

                return

        except ErrorSistema as error_sistema:

            registrar_error(error_sistema)

            self.mostrar_error(
                error_sistema.mensaje
            )

            return

        # ------------------------------
        # GUARDAR
        # ------------------------------

        try:

            if self.usuario:

                resultado = actualizar_usuario(
                    id_usuario,
                    nombre_usuario,
                    nombre_completo,
                    rol,
                    activo,
                    contrasena if contrasena else None
                )

                if not resultado:

                    self.mostrar_error(
                        "Debe quedar al menos un "
                        "administrador activo."
                    )

                    return

                mensaje = (
                    "El usuario se actualizó "
                    "correctamente."
                )

            else:

                insertar_usuario(
                    nombre_usuario,
                    nombre_completo,
                    contrasena,
                    rol,
                    activo
                )

                mensaje = (
                    "El usuario se guardó "
                    "correctamente."
                )

        except ErrorSistema as error_sistema:

            registrar_error(error_sistema)

            self.mostrar_error(
                error_sistema.mensaje
            )

            return

        QMessageBox.information(
            self,
            "Operación realizada",
            mensaje
        )

        self.accept()

    def mostrar_error(self, mensaje):

        self.cambiar_estilo_aviso("aviso_error")

        self.etiqueta_aviso.setText(mensaje)

    def limpiar_aviso(self):

        self.cambiar_estilo_aviso("aviso")

        self.etiqueta_aviso.setText("")

    def cambiar_estilo_aviso(self, nombre):

        if self.etiqueta_aviso.objectName() == nombre:
            return

        self.etiqueta_aviso.setObjectName(nombre)

        # Hay que reaplicar el estilo tras
        # cambiar el objectName.

        self.etiqueta_aviso.style().unpolish(
            self.etiqueta_aviso
        )

        self.etiqueta_aviso.style().polish(
            self.etiqueta_aviso
        )
