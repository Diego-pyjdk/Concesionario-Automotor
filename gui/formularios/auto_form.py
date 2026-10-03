from database.autos import insertar_auto, actualizar_auto

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QMessageBox
)

from errores import ErrorSistema

from database.marcas import obtener_marcas

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


class AutoForm(QDialog):

    def __init__(self, parent=None, auto=None):
        super().__init__(parent)

        self.auto = auto

        self.setObjectName("auto_form")

        if auto:
            self.setWindowTitle("Editar vehículo")
        else:
            self.setWindowTitle("Nuevo vehículo")

        self.setFixedWidth(450)

        self.crear_interfaz()
        self.cargar_marcas()

        if self.auto:
            self.cargar_datos()

    def crear_interfaz(self):

        layout_principal = QVBoxLayout()
        self.setLayout(layout_principal)

        formulario = QFormLayout()

        self.combo_marca = QComboBox()

        self.campo_modelo = QLineEdit()
        self.campo_modelo.setPlaceholderText("Ej: Corolla")

        self.campo_anio = QSpinBox()
        self.campo_anio.setRange(1900, 2100)
        self.campo_anio.setValue(2026)

        self.campo_precio = QDoubleSpinBox()
        self.campo_precio.setRange(0, 999999999)
        self.campo_precio.setDecimals(2)

        self.campo_color = QLineEdit()
        self.campo_color.setPlaceholderText("Ej: Blanco")

        self.campo_stock = QSpinBox()
        self.campo_stock.setRange(0, 999999)

        formulario.addRow("Marca:", self.combo_marca)
        formulario.addRow("Modelo:", self.campo_modelo)
        formulario.addRow("Año:", self.campo_anio)
        formulario.addRow("Precio:", self.campo_precio)
        formulario.addRow("Color:", self.campo_color)
        formulario.addRow("Stock:", self.campo_stock)

        layout_principal.addLayout(formulario)

        # ------------------------------
        # AVISO DE STOCK
        # ------------------------------

        self.aviso_stock = QLabel("")

        self.aviso_stock.setObjectName("aviso")

        self.aviso_stock.setWordWrap(True)

        layout_principal.addWidget(self.aviso_stock)

        botones = QHBoxLayout()

        boton_cancelar = crear_boton_secundario(
            "Cancelar",
            self.reject
        )

        boton_guardar = crear_boton_principal(
            "Guardar",
            self.guardar
        )

        botones.addWidget(boton_cancelar)
        botones.addWidget(boton_guardar)

        layout_principal.addLayout(botones)

        self.actualizar_aviso()

        self.campo_stock.valueChanged.connect(
            self.actualizar_aviso
        )

        # Return guarda desde los campos de texto.
        # En los desplegables y el contador hay
        # que elegir con ratón o con tabulador:
        # un Return allí cerraría el combo.

        conectar_enter_guardar(
            [self.campo_modelo, self.campo_color],
            self.guardar
        )

    def cargar_marcas(self):

        marcas = obtener_marcas()

        for id_marca, nombre in marcas:

            self.combo_marca.addItem(
                nombre,
                id_marca
            )

    def actualizar_aviso(self):

        stock = self.campo_stock.value()

        if stock <= 0:
            self.aviso_stock.setText(
                "Sin stock: el vehículo no podrá venderse."
            )

        elif stock == 1:
            self.aviso_stock.setText(
                "Queda la última unidad disponible."
            )

        else:
            self.aviso_stock.setText(
                f"{stock} unidades disponibles."
            )

    def guardar(self):

        modelo = self.campo_modelo.text().strip()

        error = primer_error([
            texto_obligatorio(
                modelo,
                "el modelo del vehículo"
            )
        ])

        if error:
            QMessageBox.warning(
                self,
                "Dato faltante",
                error
            )

            return

        marca_id = self.combo_marca.currentData()
        anio = self.campo_anio.value()
        precio = self.campo_precio.value()
        color = self.campo_color.text().strip()
        stock = self.campo_stock.value()

        try:

            if self.auto:
                id_auto = self.auto[0]

                actualizar_auto(
                    id_auto,
                    marca_id,
                    modelo,
                    anio,
                    precio,
                    color,
                    stock
                )

                mensaje = (
                    "El vehículo se actualizó "
                    "correctamente."
                )

            else:
                insertar_auto(
                    marca_id,
                    modelo,
                    anio,
                    precio,
                    color,
                    stock
                )

                mensaje = (
                    "El vehículo se guardó "
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

    def cargar_datos(self):

        id_auto, marca, modelo, anio, precio, color, stock = self.auto

        self.campo_modelo.setText(str(modelo))
        self.campo_anio.setValue(int(anio))
        self.campo_precio.setValue(float(precio))
        self.campo_color.setText(str(color))
        self.campo_stock.setValue(int(stock))

        for indice in range(self.combo_marca.count()):

            if self.combo_marca.itemText(indice) == marca:

                self.combo_marca.setCurrentIndex(indice)
                break

        self.actualizar_aviso()
