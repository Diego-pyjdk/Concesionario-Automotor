from PySide6.QtWidgets import QLabel
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QHBoxLayout,
    QMessageBox
)

from errores import ErrorSistema

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
    crear_boton_secundario,
    conectar_enter_guardar,
    avisar_error
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

        self.resize(420, 480)
        self.setMinimumWidth(360)

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
        self.error_campos = QLabel('')
        self.error_campos.setObjectName('aviso_error')
        self.error_campos.setWordWrap(True)
        self.error_campos.hide()
        layout_principal.addWidget(self.error_campos)

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

        # Return guarda, Escape cierra (lo
        # segundo lo resuelve QDialog solo).

        conectar_enter_guardar(
            [self.campo_nombre],
            self.guardar
        )

        self.campo_nombre.setFocus()

    def cargar_datos(self):

        id_marca, nombre = self.marca

        self.campo_nombre.setText(nombre)

    def guardar(self):
        self.error_campos.hide()

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
            self.error_campos.setText(error)
            self.error_campos.show()
            self.campo_nombre.setFocus()

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
        # El UNIQUE de marcas.nombre puede
        # saltar aunque la comprobación de
        # arriba pasara: dos ventanas abiertas a
        # la vez. Sin este try, la excepción
        # escapaba del diálogo y caia la
        # aplicación.

        try:

            if self.marca:
                actualizar_marca(
                    id_marca,
                    nombre
                )

                mensaje = (
                    "La marca se actualizó "
                    "correctamente."
                )

            else:
                insertar_marca(nombre)

                mensaje = (
                    "La marca se guardó "
                    "correctamente."
                )

        except ErrorSistema as error:

            avisar_error(self, error)

            return

        QMessageBox.information(
            self,
            "Operación realizada",
            mensaje
        )

        self.accept()
