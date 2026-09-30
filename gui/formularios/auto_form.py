from database.autos import insertar_auto, actualizar_auto

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
    QHBoxLayout,
    QMessageBox
)

from database.marcas import obtener_marcas


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

        botones = QHBoxLayout()

        boton_cancelar = QPushButton("Cancelar")
        boton_guardar = QPushButton("Guardar")

        boton_guardar.setObjectName("boton_principal")

        botones.addWidget(boton_cancelar)
        botones.addWidget(boton_guardar)

        layout_principal.addLayout(botones)

        boton_cancelar.clicked.connect(self.reject)
        boton_guardar.clicked.connect(self.guardar)

    def cargar_marcas(self):

        marcas = obtener_marcas()

        for id_marca, nombre in marcas:

            self.combo_marca.addItem(
                nombre,
                id_marca
            )

    def guardar(self):

        modelo = self.campo_modelo.text().strip()

        if not modelo:
            QMessageBox.warning(
                self,
                "Dato faltante",
                "Debes ingresar el modelo del vehículo."
            )
            return

        marca_id = self.combo_marca.currentData()
        anio = self.campo_anio.value()
        precio = self.campo_precio.value()
        color = self.campo_color.text().strip()
        stock = self.campo_stock.value()

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

            mensaje = "El vehículo se actualizó correctamente."
        else:
            insertar_auto(
                marca_id,
                modelo,
                anio,
                precio,
                color,
                stock
            )

            mensaje = "El vehículo se guardó correctamente."

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