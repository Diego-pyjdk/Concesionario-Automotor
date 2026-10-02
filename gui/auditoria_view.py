# ==========================================
# AUDITORÍA
# ==========================================
# Vista de solo lectura del rastro de acciones.
# Solo la abre un administrador: la sección
# exige GESTIONAR_USUARIOS en
# VentanaPrincipal.SECCIONES.
# ==========================================


from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QDateEdit,
    QHeaderView,
    QFrame
)

from PySide6.QtCore import QDate

from database.auditoria import (
    ACCIONES,
    MODULOS,
    obtener_auditoria,
    obtener_resumen,
    vaciar_auditoria
)

from utils.helpers import (
    crear_tabla,
    celda,
    crear_boton_principal,
    crear_boton_secundario,
    crear_boton_peligro,
    crear_titulo
)

from gui.vista_base import VistaBase


# =============================
# ORDEN DE PRIORIDAD
# =============================
# Para colorear la columna Acción. Los colores
# son discretos a propósito.
# =============================

TONOS = {
    "LOGIN": "tono_ok",
    "LOGOUT": "tono_neutro",
    "LOGIN_FALLIDO": "tono_peligro",
    "LOGIN_BLOQUEADO": "tono_peligro",
    "ACCESO_DENEGADO": "tono_peligro",
    "CREAR": "tono_ok",
    "VENTA": "tono_ok",
    "ELIMINAR": "tono_aviso",
    "VENTA_ANULADA": "tono_aviso",
    "MODIFICAR": "tono_info",
    "CONFIGURACION": "tono_info",
    "DESBLOQUEO": "tono_info"
}


class AuditoriaView(VistaBase):

    def __init__(self):
        super().__init__()

        self.crear_interfaz()

        self.cargar_datos()

    def crear_interfaz(self):

        layout_principal = QVBoxLayout()

        layout_principal.setContentsMargins(
            30, 25, 30, 25
        )

        layout_principal.setSpacing(18)

        self.setLayout(layout_principal)

        # ------------------------------
        # ENCABEZADO
        # ------------------------------

        encabezado = QHBoxLayout()

        columna_titulos = QVBoxLayout()
        columna_titulos.setSpacing(2)

        columna_titulos.addWidget(
            crear_titulo("Auditoría")
        )

        self.etiqueta_resumen = QLabel("")

        self.etiqueta_resumen.setObjectName(
            "subtitulo"
        )

        columna_titulos.addWidget(
            self.etiqueta_resumen
        )

        encabezado.addLayout(columna_titulos)

        encabezado.addStretch()

        layout_principal.addLayout(encabezado)

        # ------------------------------
        # FILTROS
        # ------------------------------

        layout_principal.addWidget(
            self.crear_panel_filtros()
        )

        # ------------------------------
        # TABLA
        # ------------------------------

        self.tabla = crear_tabla(
            [
                "Fecha y hora",
                "Usuario",
                "Acción",
                "Módulo",
                "Descripción"
            ]
        )

        self.tabla.horizontalHeader().setSectionResizeMode(
            4,
            QHeaderView.Stretch
        )

        layout_principal.addWidget(self.tabla)

        # ------------------------------
        # PIE
        # ------------------------------

        self.etiqueta_pie = QLabel("")

        self.etiqueta_pie.setObjectName(
            "pie"
        )

        layout_principal.addWidget(
            self.etiqueta_pie
        )

    def crear_panel_filtros(self):

        panel = QFrame()
        panel.setObjectName("filtros")

        exterior = QVBoxLayout()
        exterior.setContentsMargins(20, 16, 20, 16)
        exterior.setSpacing(12)

        panel.setLayout(exterior)

        # ------------------------------
        # FILA DE FILTROS
        # ------------------------------

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)

        # Usuario
        grid.addWidget(
            self.crear_etiqueta_filtro("Usuario"),
            0, 0
        )

        self.campo_usuario = QLineEdit()

        self.campo_usuario.setPlaceholderText(
            "Todos los usuarios"
        )

        self.campo_usuario.returnPressed.connect(
            self.aplicar_filtros
        )

        grid.addWidget(self.campo_usuario, 1, 0)

        # Módulo
        grid.addWidget(
            self.crear_etiqueta_filtro("Módulo"),
            0, 1
        )

        self.combo_modulo = QComboBox()

        self.combo_modulo.addItem("Todos", None)

        for clave, texto in MODULOS.items():

            self.combo_modulo.addItem(texto, clave)

        grid.addWidget(self.combo_modulo, 1, 1)

        # Acción
        grid.addWidget(
            self.crear_etiqueta_filtro("Acción"),
            0, 2
        )

        self.combo_accion = QComboBox()

        self.combo_accion.addItem("Todas", None)

        for clave, texto in ACCIONES.items():

            self.combo_accion.addItem(texto, clave)

        grid.addWidget(self.combo_accion, 1, 2)

        # Desde
        grid.addWidget(
            self.crear_etiqueta_filtro("Desde"),
            0, 3
        )

        self.campo_desde = QDateEdit()

        self.campo_desde.setCalendarPopup(True)

        self.campo_desde.setDisplayFormat("dd/MM/yyyy")

        self.campo_desde.setDate(
            QDate.currentDate().addDays(-30)
        )

        grid.addWidget(self.campo_desde, 1, 3)

        # Hasta
        grid.addWidget(
            self.crear_etiqueta_filtro("Hasta"),
            0, 4
        )

        self.campo_hasta = QDateEdit()

        self.campo_hasta.setCalendarPopup(True)

        self.campo_hasta.setDisplayFormat("dd/MM/yyyy")

        self.campo_hasta.setDate(
            QDate.currentDate()
        )

        grid.addWidget(self.campo_hasta, 1, 4)

        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 2)
        grid.setColumnStretch(2, 2)
        grid.setColumnStretch(3, 1)
        grid.setColumnStretch(4, 1)

        exterior.addLayout(grid)

        # ------------------------------
        # BOTONES
        # ------------------------------

        botones = QHBoxLayout()
        botones.setSpacing(10)

        self.boton_refrescar = crear_boton_principal(
            "🔄  Aplicar filtros",
            self.aplicar_filtros
        )

        boton_limpiar = crear_boton_secundario(
            "Restablecer",
            self.restablecer
        )

        botones.addWidget(
            self.boton_refrescar
        )

        botones.addWidget(boton_limpiar)

        botones.addWidget(
            crear_boton_secundario(
                "⬇  Exportar CSV",
                self.exportar_csv
            )
        )

        botones.addStretch()

        # Única acción destructiva de la vista:
        # borra el rastro y no se puede deshacer.

        botones.addWidget(
            crear_boton_peligro(
                "Vaciar auditoría",
                self.pedir_confirmacion_purga
            )
        )

        exterior.addLayout(botones)

        return panel

    def crear_etiqueta_filtro(self, texto):

        etiqueta = QLabel(texto)

        etiqueta.setObjectName(
            "etiqueta_filtro"
        )

        return etiqueta

    # =============================
    # FILTROS
    # =============================

    def obtener_filtros(self):

        usuario = self.campo_usuario.text().strip()

        return {
            "usuario": usuario or None,
            "modulo": self.combo_modulo.currentData(),
            "accion": self.combo_accion.currentData(),
            "desde": self.campo_desde.date().toString(
                "yyyy-MM-dd"
            ),
            "hasta": self.campo_hasta.date().toString(
                "yyyy-MM-dd"
            )
        }

    def aplicar_filtros(self):

        self.cargar_datos()

    def restablecer(self):

        self.campo_usuario.clear()

        self.combo_modulo.setCurrentIndex(0)

        self.combo_accion.setCurrentIndex(0)

        self.campo_desde.setDate(
            QDate.currentDate().addDays(-30)
        )

        self.campo_hasta.setDate(
            QDate.currentDate()
        )

        self.cargar_datos()

    # =============================
    # CARGAR
    # =============================

    def cargar_datos(self):

        filtros = self.obtener_filtros()

        registros = self.proteger(
            obtener_auditoria,
            **filtros
        )

        if registros is None:

            return

        self.mostrar_registros(registros)

        # ------------------------------
        # RESUMEN
        # ------------------------------

        resumen = self.proteger(
            obtener_resumen
        )

        if resumen:

            self.etiqueta_resumen.setText(
                f"{resumen['total'] or 0} movimientos "
                f"registrados  ·  "
                f"{resumen['accesos'] or 0} accesos  ·  "
                f"{resumen['fallidos'] or 0} intentos fallidos  ·  "
                f"{resumen['denegados'] or 0} accesos denegados"
            )

        plural = (
            "movimiento"
            if len(registros) == 1
            else "movimientos"
        )

        self.etiqueta_pie.setText(
            f"Mostrando {len(registros)} {plural}"
        )

    def mostrar_registros(self, registros):

        self.tabla.setRowCount(len(registros))

        for fila, registro in enumerate(registros):

            (
                id_registro,
                fecha_hora,
                usuario,
                accion,
                modulo,
                descripcion
            ) = registro

            self.tabla.setItem(
                fila,
                0,
                celda(
                    self.texto_fecha(fecha_hora),
                    centrar=True
                )
            )

            self.tabla.setItem(
                fila,
                1,
                celda(usuario or "sistema")
            )

            self.tabla.setItem(
                fila,
                2,
                celda(
                    ACCIONES.get(accion, accion),
                    objeto=TONOS.get(accion, "tono_neutro")
                )
            )

            self.tabla.setItem(
                fila,
                3,
                celda(MODULOS.get(modulo, modulo))
            )

            self.tabla.setItem(
                fila,
                4,
                celda(descripcion or "")
            )

    # =============================
    # FORMATO
    # =============================

    def texto_fecha(self, valor):
        """
        Día y hora sin segundos: cabe en la
        columna y es lo que importa al leer un
        rastro.
        """

        try:
            return valor.strftime("%d/%m/%Y %H:%M:%S")
        except AttributeError:
            return str(valor)

    # =============================
    # EXPORTAR
    # =============================

    def pedir_confirmacion_purga(self):
        """
        Vaciar el rastro no tiene vuelta atrás y
        borra pruebas de seguridad, así que pide
        confirmación dos veces.
        """

        from PySide6.QtWidgets import QInputDialog

        if not self.confirmar(
            "Vaciar auditoría",
            "Se borrará TODO el registro de "
            "acciones.\n\n"
            "No se puede deshacer y se perderán "
            "las pruebas de acceso.\n\n"
            "¿Continuar?"
        ):

            return

        texto, aceptado = QInputDialog.getText(
            self,
            "Confirmación final",
            "Escribe VACIAR en mayúsculas para "
            "confirmar:"
        )

        if not aceptado:

            return

        if texto.strip() != "VACIAR":

            self.mostrar_error(
                "No coincide. El registro se ha "
                "conservado."
            )

            return

        total = self.proteger(vaciar_auditoria)

        if total is None:

            return

        self.mostrar_exito(
            f"Se eliminaron {total} registros."
        )

        self.cargar_datos()

    def exportar_csv(self):

        from PySide6.QtWidgets import QFileDialog

        ruta, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar auditoría",
            "auditoria.csv",
            "CSV (*.csv)"
        )

        if not ruta:

            return

        filtros = self.obtener_filtros()

        registros = self.proteger(
            obtener_auditoria,
            limite=100000,
            **filtros
        )

        if registros is None:

            return

        try:

            with open(
                ruta,
                "w",
                encoding="utf-8-sig",
                newline=""
            ) as archivo:

                archivo.write(
                    "id;fecha;usuario;accion;modulo;"
                    "descripcion\n"
                )

                for registro in registros:

                    (
                        id_registro,
                        fecha_hora,
                        usuario,
                        accion,
                        modulo,
                        descripcion
                    ) = registro

                    archivo.write(
                        ";".join([
                            str(id_registro),
                            str(fecha_hora),
                            usuario or "",
                            ACCIONES.get(accion, accion),
                            MODULOS.get(modulo, modulo),
                            (descripcion or "").replace(
                                ";",
                                ","
                            )
                        ]) + "\n"
                    )

        except OSError as error:

            from utils.registro import registrar_error

            registrar_error(error)

            self.mostrar_error_inesperado()

            return

        self.mostrar_exito(
            f"Se exportaron {len(registros)} "
            f"registros en:\n{ruta}"
        )
