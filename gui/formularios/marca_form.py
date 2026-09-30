from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QHBoxLayout,
    QMessageBox
)

from database.marcas import (
    marca_existe,
    insertar_marca,
    actualizar_marca
)

from utils.validaciones import (
    texto_obligatorio,
    primer_error
)

from utils.helpers import (
    crear_boton_principal,
    crear_boton_secundario
)


class MarcaForm(QDialog):

    def __init__(self, parent=None, marca=None):
        super().__init__(parent)

        self.marca = marca

        self.setObjectName("marca_form")

        if marca:
            self.setWindowTitle("Editar marca")
        else:
            self.setWindowTitle("Nueva marca")

        self.setFixedWidth(420)

        self.crear_interfaz()

        if self.marca:
            self.cargar_datos()

    def crear_interfaz(self):

        layout_principal = QVBoxLayout()
        self.setLayout(layout_principal)

        formulario = QFormLayout()

        self.campo_nombre = QLineEdit()
        self.campo_nombre.setPlaceholderText("Ej: Toyota")

        formulario.addRow("Nombre:", self.campo_nombre)

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

        self.campo_nombre.setFocus()

    def cargar_datos(self):

        id_marca, nombre = self.marca

        self.campo_nombre.setText(nombre)

    def guardar(self):

        nombre = self.campo_nombre.text().strip()

        # ------------------------------
        # VALIDACIONES
        # ------------------------------

        error = primer_error([
            texto_obligatorio(
                nombre,
                "el nombre"
            )
        ])

        if error:
            QMessageBox.warning(
                self,
                "Dato faltante",
                error
            )

            return

        id_marca = None

        if self.marca:
            id_marca = self.marca[0]

        if marca_existe(nombre, id_marca):
            QMessageBox.warning(
                self,
                "Marca duplicada",
                "Ya existe una marca con ese nombre."
            )

            return

        # ------------------------------
        # GUARDAR
        # ------------------------------

        if self.marca:
            actualizar_marca(
                id_marca,
                nombre
            )

            mensaje = "La marca se actualizó correctamente."

        else:
            insertar_marca(nombre)

            mensaje = "La marca se guardó correctamente."

        QMessageBox.information(
            self,
            "Operación realizada",
            mensaje
        )

        self.accept()
