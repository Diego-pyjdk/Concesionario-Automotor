from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QHBoxLayout,
    QMessageBox
)

from database.clientes import (
    insertar_cliente,
    actualizar_cliente
)

from utils.validaciones import (
    texto_obligatorio,
    es_email,
    es_telefono,
    primer_error
)

from utils.helpers import (
    crear_boton_principal,
    crear_boton_secundario,
    conectar_enter_guardar
)


class ClienteForm(QDialog):

    def __init__(self, parent=None, cliente=None):
        super().__init__(parent)

        self.cliente = cliente

        self.setObjectName("cliente_form")

        if cliente:
            self.setWindowTitle("Editar cliente")
        else:
            self.setWindowTitle("Nuevo cliente")

        self.setFixedWidth(450)

        self.crear_interfaz()

        if self.cliente:
            self.cargar_datos()

    def crear_interfaz(self):

        layout_principal = QVBoxLayout()
        self.setLayout(layout_principal)

        formulario = QFormLayout()

        self.campo_nombre = QLineEdit()
        self.campo_nombre.setPlaceholderText("Ej: Ana")

        self.campo_apellido = QLineEdit()
        self.campo_apellido.setPlaceholderText("Ej: Ruiz")

        self.campo_telefono = QLineEdit()
        self.campo_telefono.setPlaceholderText("Ej: 3001234567")

        self.campo_email = QLineEdit()
        self.campo_email.setPlaceholderText("Ej: ana@correo.com")

        formulario.addRow("Nombre:", self.campo_nombre)
        formulario.addRow("Apellido:", self.campo_apellido)
        formulario.addRow("Teléfono:", self.campo_telefono)
        formulario.addRow("Email:", self.campo_email)

        layout_principal.addLayout(formulario)

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

        # Return guarda desde cualquiera de los
        # cuatro campos.

        conectar_enter_guardar(
            [
                self.campo_nombre,
                self.campo_apellido,
                self.campo_telefono,
                self.campo_email
            ],
            self.guardar
        )

        self.campo_nombre.setFocus()

    def cargar_datos(self):

        (
            id_cliente,
            nombre,
            apellido,
            telefono,
            email
        ) = self.cliente

        self.campo_nombre.setText(str(nombre))

        self.campo_apellido.setText(str(apellido))

        self.campo_telefono.setText(
            "" if telefono is None else str(telefono)
        )

        self.campo_email.setText(
            "" if email is None else str(email)
        )

    def guardar(self):

        nombre = self.campo_nombre.text().strip()

        apellido = self.campo_apellido.text().strip()

        telefono = self.campo_telefono.text().strip()

        email = self.campo_email.text().strip()

        # ------------------------------
        # VALIDACIONES
        # ------------------------------

        error = primer_error([
            texto_obligatorio(nombre, "el nombre"),
            texto_obligatorio(apellido, "el apellido"),
            es_telefono(telefono, "El teléfono"),
            es_email(email, "El email")
        ])

        if error:
            QMessageBox.warning(
                self,
                "Dato inválido",
                error
            )

            return

        # ------------------------------
        # NORMALIZAR
        # ------------------------------
        # Las columnas son opcionales: un campo
        # vacío se guarda como NULL, no como
        # cadena vacía.
        # ------------------------------

        if not telefono:
            telefono = None

        if not email:
            email = None

        # ------------------------------
        # GUARDAR
        # ------------------------------

        if self.cliente:
            actualizar_cliente(
                self.cliente[0],
                nombre,
                apellido,
                telefono,
                email
            )

            mensaje = "El cliente se actualizó correctamente."

        else:
            insertar_cliente(
                nombre,
                apellido,
                telefono,
                email
            )

            mensaje = "El cliente se guardó correctamente."

        QMessageBox.information(
            self,
            "Operación realizada",
            mensaje
        )

        self.accept()
