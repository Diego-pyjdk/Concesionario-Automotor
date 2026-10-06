# ==========================================
# DETALLE DE UNA VENTA
# ==========================================
# Datos de la venta, estado del saldo y tabla de
# pagos, con su botón para registrar uno nuevo.
#
# Va en su propia clase y no dentro de la vista
# porque tiene estado propio: al registrar un pago
# hay que recargar la tabla y recalcular el saldo
# sin cerrar y reabrir el diálogo.
# ==========================================


from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QWidget,
    QMessageBox
)

from database.pagos import (
    obtener_pagos,
    eliminar_pago
)

from permisos import (
    tiene_permiso,
    GESTIONAR_VENTAS
)

from utils.moneda import formato_dinero

from utils.helpers import (
    celda,
    crear_tabla,
    crear_boton_principal,
    crear_boton_secundario,
    crear_boton_peligro,
    ajustar_alto_tabla
)

from gui.formularios.pago_form import PagoForm


class DetalleVentaDialog(QDialog):

    COLUMNAS_PAGO = [
        "Fecha",
        "Importe",
        "Forma",
        "Referencia",
        "Concepto",
        "Cobró",
        ""
    ]

    ANCHO_BORRAR = 76

    def __init__(
        self,
        parent,
        venta,
        funcion_saldo,
        moneda=None
    ):
        super().__init__(parent)

        # La moneda con la que se registró ESTA venta.

        self.moneda = moneda

        # La venta llega como tupla de obtener_ventas:
        # id, fecha, cliente, vehiculo, precio,
        # usuario_nombre.

        (
            self.id_venta,
            self.fecha,
            self.cliente,
            self.vehiculo,
            self.precio,
            self.vendedor
        ) = venta

        self.funcion_saldo = funcion_saldo

        self.setWindowTitle(
            f"Venta {self.id_venta} - detalle"
        )

        self.setModal(True)

        self.resize(880, 560)

        layout = QVBoxLayout(self)

        # ------------------------------
        # DATOS
        # ------------------------------

        self.etiqueta_datos = QLabel("")

        self.etiqueta_datos.setTextFormat(
            Qt.RichText
        )

        self.etiqueta_datos.setWordWrap(True)

        self.etiqueta_datos.setObjectName(
            "subtitulo"
        )

        layout.addWidget(self.etiqueta_datos)

        # ------------------------------
        # SALDO
        # ------------------------------

        self.etiqueta_saldo = QLabel("")

        self.etiqueta_saldo.setTextFormat(
            Qt.RichText
        )

        self.etiqueta_saldo.setWordWrap(True)

        layout.addWidget(self.etiqueta_saldo)

        # ------------------------------
        # TABLA DE PAGOS
        # ------------------------------

        self.tabla = crear_tabla(
            self.COLUMNAS_PAGO
        )

        self.tabla.setColumnWidth(1, 120)
        self.tabla.setColumnWidth(2, 160)
        self.tabla.setColumnWidth(3, 120)

        layout.addWidget(self.tabla)

        # ------------------------------
        # BOTONES
        # ------------------------------

        botones = QHBoxLayout()

        botones.setSpacing(10)

        self.boton_pago = crear_boton_principal(
            "Registrar pago",
            self.registrar_pago
        )

        botones.addWidget(self.boton_pago)

        botones.addWidget(crear_boton_secundario(
            "Cerrar",
            self.reject
        ))

        botones.addStretch()

        layout.addLayout(botones)

        self.cargar()

    # =============================
    # CARGA
    # =============================

    def cargar(self):
        """
        Relee todo. Se llama al abrir y después de
        cada cambio, para que la tabla y el saldo no
        se puedan desincronizar.
        """

        self.pintar_datos()

        self.pintar_saldo()

        self.pintar_pagos()

    def pintar_datos(self):

        self.etiqueta_datos.setText(
            f"<b>Venta {self.id_venta}</b> &nbsp;&nbsp; "
            f"<b>{self.dinero(self.precio)}</b><br>"
            f"Fecha: {self.fecha}<br>"
            f"Cliente: {self.cliente}<br>"
            f"Vehículo: {self.vehiculo}<br>"
            "Vendedor: "
            + (self.vendedor or "Sin registrar")
        )

    def pintar_saldo(self):

        saldo = self.funcion_saldo(self.id_venta)

        if saldo is None:

            self.etiqueta_saldo.setText(
                "No se pudo leer el saldo."
            )

            self.boton_pago.setEnabled(False)

            return

        precio, pagado, pendiente = saldo

        if pendiente <= 0.005:

            self.etiqueta_saldo.setObjectName(
                "estado_ok"
            )

            self.etiqueta_saldo.setText(
                f"<b>Saldada.</b> "
                f"{self.dinero(pagado)} cobrados de "
                f"{self.dinero(precio)}."
            )

            self.boton_pago.setEnabled(False)

            return

        self.etiqueta_saldo.setObjectName("aviso")

        porcentaje = (
            float(pagado) / float(precio) * 100
            if float(precio) > 0
            else 0
        )

        self.etiqueta_saldo.setText(
            f"<b>Pendiente "
            f"{self.dinero(pendiente)}</b> de "
            f"{self.dinero(precio)} "
            f"({porcentaje:.0f}% cobrado)"
        )

        self.boton_pago.setEnabled(True)

    def pintar_pagos(self):

        self.tabla.setRowCount(0)

        pagos = obtener_pagos(self.id_venta)

        puede_borrar = tiene_permiso(
            GESTIONAR_VENTAS
        )

        for numero, pago in enumerate(pagos):

            (
                id_pago,
                fecha,
                importe,
                forma,
                referencia,
                concepto,
                usuario
            ) = pago

            self.tabla.insertRow(numero)

            self.tabla.setItem(
                numero, 0, celda(str(fecha))
            )

            self.tabla.setItem(
                numero, 1,
                celda(
                    self.dinero(importe),
                    centrar=True
                )
            )

            self.tabla.setItem(
                numero, 2, celda(forma)
            )

            self.tabla.setItem(
                numero, 3,
                celda(referencia or "")
            )

            self.tabla.setItem(
                numero, 4,
                celda(concepto or "")
            )

            self.tabla.setItem(
                numero, 5,
                celda(usuario or "Sin registrar")
            )

            if puede_borrar:

                self.poner_boton_borrar(
                    numero, id_pago
                )

        ajustar_alto_tabla(self.tabla)

    def poner_boton_borrar(self, numero, id_pago):
        """
        El botón va con setCellWidget, y su celda
        necesita una altura fija: Qt calcula la
        altura de la fila desde el texto e ignora
        el widget, así que sin esto el botón
        saldría cortado.
        """

        boton = crear_boton_peligro(
            "Borrar",
            lambda _=None, p=id_pago:
                self.borrar_pago(p)
        )

        boton.setFixedWidth(self.ANCHO_BORRAR)

        contenedor = QWidget()

        caja = QHBoxLayout(contenedor)

        caja.setContentsMargins(0, 0, 0, 0)

        caja.setAlignment(Qt.AlignCenter)

        caja.addWidget(boton)

        contenedor.setFixedHeight(34)

        self.tabla.setCellWidget(
            numero, 6, contenedor
        )

    # =============================
    # ACCIONES
    # =============================

    def registrar_pago(self):

        saldo = self.funcion_saldo(self.id_venta)

        if saldo is None:

            return

        PagoForm(
            self,
            venta_id=self.id_venta,
            saldo=saldo[2]
        ).exec()

        self.cargar()

    def dinero(self, valor):
        """
        Un importe de ESTA venta, con la moneda de
        ESTA venta.

        ------------------------------
        # POR QUÉ NO LA MONEDA EN CURSO
        # ------------------------------

        Porque una venta de 25.000 dólares tiene que
        seguir enseñándose en dólares aunque el
        concesionario haya pasado la aplicación a
        guaraníes. El importe no se ha convertido, así
        que ponerlo con otro símbolo sería mentir dos
        veces: sobre la cifra y sobre lo que significa.

        Sin moneda (una venta anterior a la migración, o
        una que se pasa a mano) se usa la que hay ahora,
        que es lo mejor que se puede hacer sin inventar.
        """

        return formato_dinero(valor, moneda=self.moneda)

    def borrar_pago(self, id_pago):

        respuesta = QMessageBox.question(
            self,
            "Borrar el pago",
            "¿Seguro que quieres borrar este pago?"
            "\n\nUn pago no se edita: si está mal, "
            "se borra y se vuelve a registrar.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if respuesta != QMessageBox.Yes:

            return

        ok, motivo = eliminar_pago(id_pago)

        if not ok:

            QMessageBox.warning(
                self,
                "No se pudo borrar",
                motivo
            )

            return

        self.cargar()
