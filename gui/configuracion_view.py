# ==========================================
# CONFIGURACIÓN
# ==========================================
# Tres bloques:
#
#   Sistema      nombre y versión
#   Sesión       quién está dentro y con qué rol
#   Herramientas ajustes, estado de MySQL y
#                diagnóstico (solo administrador)
#
# Ninguna credencial se puede cambiar desde aquí.
# Editar el usuario o la contraseña de MySQL es
# tarea de quien administra el servidor, no de
# quien tiene abierta la aplicación.
# ==========================================


from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QFrame,
    QSpinBox,
    QComboBox,
    QLineEdit,
    QTableWidgetItem,
    QPushButton,
    QTabWidget,
    QWidget
)

from database.configuracion import (
    NOMBRE_SISTEMA,
    VERSION_SISTEMA,
    estado_conexion,
    obtener_stock_minimo,
    actualizar_stock_minimo,
    obtener_moneda,
    actualizar_moneda
)

import sesion as modulo_sesion

from permisos import (
    tiene_permiso,
    GESTIONAR_CONFIGURACION
)

from utils.moneda import (
    FORMATOS as FORMATOS_MONEDA,
    validar_config,
    formato_dinero
)

from utils.validaciones import (
    es_stock,
    primer_error
)

from utils.helpers import (
    crear_tabla,
    crear_boton_principal,
    crear_titulo,
    ajustar_alto_tabla
)

from gui.vista_base import VistaBase

from gui.diagnostico import (
    obtener_entorno,
    obtener_dependencias,
    obtener_conexion_configurada,
    obtener_archivos,
    comprobar_conexion,
    comprobar_python,
    obtener_base_datos,
    obtener_tablas
)


class ConfiguracionView(VistaBase):

    def __init__(self):
        super().__init__()

        self.crear_interfaz()

    # =============================
    # INTERFAZ
    # =============================

    def crear_interfaz(self):

        layout = QVBoxLayout()

        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(18)

        self.setLayout(layout)

        layout.addWidget(
            crear_titulo("Configuración")
        )

        self.etiqueta_subtitulo = QLabel(
            "Información del sistema, sesión activa "
            "y estado de la base de datos"
        )

        self.etiqueta_subtitulo.setObjectName(
            "subtitulo"
        )

        layout.addWidget(
            self.etiqueta_subtitulo
        )

        self.es_administrador = tiene_permiso(
            GESTIONAR_CONFIGURACION
        )

        # ------------------------------
        # SISTEMA
        # ------------------------------

        layout.addWidget(
            self.crear_panel_sistema()
        )

        # ------------------------------
        # SESIÓN
        # ------------------------------

        layout.addWidget(
            self.crear_panel_sesion()
        )

        # ------------------------------
        # AJUSTES
        # ------------------------------

        layout.addWidget(
            self.crear_panel_ajustes()
        )

        # ------------------------------
        # BASE DE DATOS
        # ------------------------------

        layout.addWidget(
            self.crear_panel_conexion()
        )

        # ------------------------------
        # DIAGNÓSTICO
        # ------------------------------

        if self.es_administrador:

            layout.addWidget(
                self.crear_panel_diagnostico()
            )

        layout.addStretch()

        self.cargar_datos()

    def crear_panel_simple(self, titulo):

        panel = QFrame()
        panel.setObjectName("tarjeta")

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        panel.setLayout(layout)

        etiqueta = QLabel(titulo)
        etiqueta.setObjectName("subtitulo")

        layout.addWidget(etiqueta)

        return panel, layout

    # =============================
    # SISTEMA
    # =============================

    def crear_panel_sistema(self):

        panel, layout = self.crear_panel_simple(
            "Sistema"
        )

        self.tabla_sistema = crear_tabla(
            ["Campo", "Valor"],
            anchos_fijos={0: 200}
        )


        layout.addWidget(self.tabla_sistema)

        return panel

    # =============================
    # SESIÓN
    # =============================

    def crear_panel_sesion(self):

        panel, layout = self.crear_panel_simple(
            "Sesión actual"
        )

        self.tabla_sesion = crear_tabla(
            ["Campo", "Valor"],
            anchos_fijos={0: 200}
        )


        layout.addWidget(self.tabla_sesion)

        return panel

    # =============================
    # AJUSTES
    # =============================

    def crear_panel_ajustes(self):

        panel, layout = self.crear_panel_simple(
            "Ajustes"
        )

        self.etiqueta_ajuste_error = QLabel("")

        self.etiqueta_ajuste_error.setObjectName(
            "aviso_error"
        )

        self.etiqueta_ajuste_error.setWordWrap(True)

        self.etiqueta_ajuste_error.setVisible(False)

        layout.addWidget(
            self.etiqueta_ajuste_error
        )

        fila = QHBoxLayout()
        fila.setSpacing(10)

        self.campo_stock_minimo = QSpinBox()

        self.campo_stock_minimo.setRange(0, 999)

        etiqueta = QLabel(
            "Un vehículo se marca como stock bajo "
            "a partir de:"
        )

        self.boton_guardar_ajuste = (
            crear_boton_principal(
                "Guardar",
                self.guardar_stock_minimo
            )
        )

        fila.addWidget(etiqueta)
        fila.addWidget(self.campo_stock_minimo)
        fila.addStretch()
        fila.addWidget(self.boton_guardar_ajuste)

        layout.addLayout(fila)

        # ------------------------------
        # MONEDA
        # ------------------------------
        # El símbolo de la moneda no vive en el
        # código: sale de aquí. Antes estaba escrito
        # dentro de cuatro funciones distintas y
        # cambiarlo obligaba a tocar cuatro
        # archivos.

        separador = QLabel("Moneda")

        separador.setObjectName("subtitulo")

        layout.addWidget(separador)

        formulario = QFormLayout()

        self.campo_moneda_codigo = QLineEdit()

        self.campo_moneda_codigo.setMaxLength(10)

        self.campo_moneda_codigo.setPlaceholderText(
            "USD"
        )

        self.campo_moneda_simbolo = QLineEdit()

        self.campo_moneda_simbolo.setMaxLength(5)

        self.campo_moneda_simbolo.setPlaceholderText(
            "$"
        )

        self.campo_moneda_formato = QComboBox()

        for formato in FORMATOS_MONEDA:

            self.campo_moneda_formato.addItem(
                formato
            )

        self.campo_moneda_miles = QComboBox()

        for separador_texto in (",", ".", " ", "'"):

            self.campo_moneda_miles.addItem(
                separador_texto
            )

        self.campo_moneda_decimales = QComboBox()

        for separador_texto in (".", ",", " ' "):

            self.campo_moneda_decimales.addItem(
                separador_texto
            )

        formulario.addRow(
            "Código:", self.campo_moneda_codigo
        )

        formulario.addRow(
            "Símbolo:", self.campo_moneda_simbolo
        )

        formulario.addRow(
            "Formato:", self.campo_moneda_formato
        )

        formulario.addRow(
            "Separador de miles:",
            self.campo_moneda_miles
        )

        formulario.addRow(
            "Separador de decimales:",
            self.campo_moneda_decimales
        )

        layout.addLayout(formulario)

        self.etiqueta_ejemplo_moneda = QLabel("")

        self.etiqueta_ejemplo_moneda.setObjectName(
            "pie"
        )

        layout.addWidget(
            self.etiqueta_ejemplo_moneda
        )

        fila_moneda = QHBoxLayout()

        fila_moneda.setSpacing(10)

        self.boton_guardar_moneda = (
            crear_boton_principal(
                "Guardar moneda",
                self.guardar_moneda
            )
        )

        fila_moneda.addStretch()

        fila_moneda.addWidget(
            self.boton_guardar_moneda
        )

        layout.addLayout(fila_moneda)

        # Cada cambio enseña cómo quedaría, para
        # no tener que guardar y cerrar para
        # comprobar si el formato sirve.

        self.campo_moneda_codigo.textChanged.connect(
            self.previsualizar_moneda
        )

        self.campo_moneda_simbolo.textChanged.connect(
            self.previsualizar_moneda
        )

        self.campo_moneda_formato.currentTextChanged.connect(
            self.previsualizar_moneda
        )

        self.campo_moneda_miles.currentTextChanged.connect(
            self.previsualizar_moneda
        )

        self.campo_moneda_decimales.currentTextChanged.connect(
            self.previsualizar_moneda
        )

        if not self.es_administrador:

            self.campo_stock_minimo.setEnabled(False)

            self.boton_guardar_ajuste.setEnabled(
                False
            )

            for campo in (
                self.campo_moneda_codigo,
                self.campo_moneda_simbolo,
                self.campo_moneda_formato,
                self.campo_moneda_miles,
                self.campo_moneda_decimales
            ):

                campo.setEnabled(False)

            self.boton_guardar_moneda.setEnabled(False)

            ayuda = QLabel(
                "Solo un administrador puede cambiar "
                "los ajustes."
            )

            ayuda.setObjectName("pie")

            layout.addWidget(ayuda)

        return panel

    # =============================
    # CONEXIÓN
    # =============================

    def crear_panel_conexion(self):

        panel, layout = self.crear_panel_simple(
            "Base de datos"
        )

        self.etiqueta_estado = QLabel("Comprobando...")

        self.etiqueta_estado.setObjectName(
            "estado_conexion"
        )

        layout.addWidget(
            self.etiqueta_estado
        )

        self.tabla_conexion = crear_tabla(
            ["Detalle", "Valor"],
            anchos_fijos={0: 200}
        )


        layout.addWidget(self.tabla_conexion)

        botones = QHBoxLayout()

        boton_probar = crear_boton_principal(
            "Probar conexión",
            self.comprobar_conexion
        )

        self.boton_probar = boton_probar

        botones.addWidget(boton_probar)

        botones.addStretch()

        layout.addLayout(botones)

        return panel

    # =============================
    # DIAGNÓSTICO
    # =============================

    def crear_panel_diagnostico(self):

        panel, layout = self.crear_panel_simple(
            "Diagnóstico"
        )

        self.pestanas_diagnostico = self._crear_pestanas()

        layout.addWidget(
            self.pestanas_diagnostico
        )

        botones = QHBoxLayout()

        boton_actualizar = QPushButton(
            "🔄  Actualizar diagnóstico"
        )

        boton_actualizar.setObjectName(
            "boton_secundario"
        )

        boton_actualizar.clicked.connect(
            self.cargar_diagnostico
        )

        botones.addWidget(boton_actualizar)

        botones.addStretch()

        layout.addLayout(botones)

        return panel

    def _crear_pestanas(self):

        pestanas = QTabWidget()

        self.tablas_diagnostico = {}

        hojas = [
            ("Entorno", self._hoja_diagnostico),
            ("Dependencias", self._hoja_diagnostico),
            ("Conexión", self._hoja_diagnostico),
            ("Tablas", self._hoja_tablas),
            ("Archivos", self._hoja_diagnostico)
        ]

        for nombre, constructor in hojas:

            hoja, tabla = constructor()

            self.tablas_diagnostico[nombre] = tabla

            pestanas.addTab(hoja, nombre)

        return pestanas

    def _hoja_diagnostico(self):
        """
        Pestaña con una tabla de campo/valor.
        """

        marco = QWidget()

        layout = QVBoxLayout(marco)
        layout.setContentsMargins(12, 12, 12, 12)

        tabla = crear_tabla(
            ["Campo", "Valor"],
            anchos_fijos={0: 200}
        )

        layout.addWidget(tabla)

        return marco, tabla

    def _hoja_tablas(self):

        marco = QWidget()

        layout = QVBoxLayout(marco)
        layout.setContentsMargins(12, 12, 12, 12)

        tabla = crear_tabla(
            ["Tabla", "Filas", "Tamaño"]
        )

        layout.addWidget(tabla)

        return marco, tabla

    # =============================
    # DATOS
    # =============================

    def cargar_datos(self):

        self.cargar_sistema()
        self.cargar_sesion()
        self.cargar_ajustes()
        self.comprobar_conexion()

        if self.es_administrador:

            self.cargar_diagnostico()

    def cargar_sistema(self):

        self.pintar_datos(
            self.tabla_sistema,
            [
                ("Nombre del sistema", NOMBRE_SISTEMA),
                ("Versión", VERSION_SISTEMA)
            ]
        )

    def cargar_sesion(self):

        sesion = modulo_sesion.obtener_sesion()

        filas = [
            ("Usuario", sesion.nombre_usuario or "—"),
            ("Nombre completo",
             sesion.nombre_completo or "—"),
            (
                "Rol",
                "Administrador"
                if sesion.es_administrador
                else "Vendedor"
            ),
            ("Id de sesión", str(sesion.id_usuario or "—"))
        ]

        self.pintar_datos(
            self.tabla_sesion,
            filas
        )

    def cargar_ajustes(self):

        valor = self.proteger(obtener_stock_minimo)

        if valor is not None:

            self.campo_stock_minimo.setValue(valor)

        moneda = self.proteger(obtener_moneda)

        if moneda is None:

            return

        # Se rellena con señales bloqueadas: al
        # asignar cada campo dispara la
        # previsualización, y así se vería un
        # ejemplo a medias cinco veces.

        bloqueado = self.campos_moneda()

        try:

            for campo in bloqueado:

                campo.blockSignals(True)

            self.campo_moneda_codigo.setText(
                moneda["codigo"]
            )

            self.campo_moneda_simbolo.setText(
                moneda["simbolo"]
            )

            indice = (
                self.campo_moneda_formato.findText(
                    moneda["formato"]
                )
            )

            if indice >= 0:

                self.campo_moneda_formato.setCurrentIndex(
                    indice
                )

            indice = self.campo_moneda_miles.findText(
                moneda["separador_miles"]
            )

            if indice >= 0:

                self.campo_moneda_miles.setCurrentIndex(
                    indice
                )

            indice = (
                self.campo_moneda_decimales.findText(
                    moneda["separador_decimales"]
                )
            )

            if indice >= 0:

                self.campo_moneda_decimales.setCurrentIndex(
                    indice
                )

        finally:

            for campo in bloqueado:

                campo.blockSignals(False)

        self.previsualizar_moneda()

    def campos_moneda(self):

        return (
            self.campo_moneda_codigo,
            self.campo_moneda_simbolo,
            self.campo_moneda_formato,
            self.campo_moneda_miles,
            self.campo_moneda_decimales
        )

    def comprobar_conexion(self):

        conectado, detalle = estado_conexion()

        if conectado:

            self.etiqueta_estado.setText(
                "🟢  Conectado con MySQL"
            )

            self.etiqueta_estado.setObjectName(
                "estado_ok"
            )

        else:

            self.etiqueta_estado.setText(
                "🔴  Sin conexión con MySQL"
            )

            self.etiqueta_estado.setObjectName(
                "estado_error"
            )

        self.reaplicar_estilo(
            self.etiqueta_estado
        )

        filas = [("Servidor MySQL", detalle)]

        # Solo el administrador ve el detalle de
        # a dónde se está conectando.

        if self.es_administrador:

            filas.extend(
                obtener_conexion_configurada()
            )

        self.pintar_datos(
            self.tabla_conexion,
            filas
        )

    def cargar_diagnostico(self):

        ok_python, mensaje = comprobar_python()

        self.pintar_datos(
            self.tablas_diagnostico["Entorno"],
            obtener_entorno()
            + [("Python suficiente", mensaje)]
        )

        self.pintar_datos(
            self.tablas_diagnostico["Dependencias"],
            obtener_dependencias()
        )

        conexion_ok, detalle_conexion = (
            comprobar_conexion()
        )

        base = self.proteger(obtener_base_datos)

        filas = [
            (
                "Prueba de conexión",
                "Correcta" if conexion_ok
                else f"Fallida: {detalle_conexion}"
            )
        ]

        if base:

            filas.extend([
                ("Versión de MySQL", base["version"]),
                ("Juego de caracteres", base["charset"]),
                ("Ordenación", base["collation"]),
                ("Conexiones máximas",
                 base["conexiones_max"]),
                ("Espera de conexión", f"{base['espera']} s"),
                ("Latencia", f"{base['latencia_ms']} ms")
            ])

        self.pintar_datos(
            self.tablas_diagnostico["Conexión"],
            filas
        )

        tablas = self.proteger(obtener_tablas)

        self.pintar_datos(
            self.tablas_diagnostico["Tablas"],
            tablas
        )

        self.pintar_datos(
            self.tablas_diagnostico["Archivos"],
            obtener_archivos()
        )

    # =============================
    # AJUSTES
    # =============================

    def guardar_stock_minimo(self):

        valor = self.campo_stock_minimo.value()

        error = primer_error([
            es_stock(valor, "El umbral de stock bajo")
        ])

        if error:

            self.mostrar_ajuste_error(error)

            return

        self.ocultar_ajuste_error()

        resultado = self.proteger(
            actualizar_stock_minimo,
            valor
        )

        if resultado is None:

            return

        self.mostrar_exito(
            f"El umbral de stock bajo ahora es "
            f"{resultado}."
        )

        self.cargar_ajustes()

    # =============================
    # MONEDA
    # =============================

    def moneda_del_formulario(self):
        """
        Lo que hay ahora mismo en los campos, como
        diccionario. Se usa para validar y para la
        vista previa.
        """

        return {
            "codigo": (
                self.campo_moneda_codigo.text().strip()
            ),
            "simbolo": (
                self.campo_moneda_simbolo.text().strip()
            ),
            "formato": (
                self.campo_moneda_formato.currentText()
            ),
            "separador_miles": (
                self.campo_moneda_miles.currentText()
            ),
            "separador_decimales": (
                self.campo_moneda_decimales.currentText()
            )
        }

    def previsualizar_moneda(self):
        """
        Muestra cómo quedarían los importes con lo
        que hay tecleado, sin guardar nada.

        Si la configuración no es válida, avisa en
        vez de enseñar un importe que no podría
        leerse.
        """

        propuesta = self.moneda_del_formulario()

        valido, mensaje = validar_config(propuesta)

        if not valido:

            self.etiqueta_ejemplo_moneda.setText(
                "Así no se puede: " + mensaje
            )

            return

        self.etiqueta_ejemplo_moneda.setText(
            "Se vería así: "
            + formato_dinero(1234.5, propuesta)
            + "  ·  un importe grande: "
            + formato_dinero(9876543.21, propuesta)
        )

    def guardar_moneda(self):

        propuesta = self.moneda_del_formulario()

        valido, mensaje = validar_config(propuesta)

        if not valido:

            self.mostrar_ajuste_error(mensaje)

            return

        self.ocultar_ajuste_error()

        resultado = self.proteger(
            actualizar_moneda,
            propuesta["codigo"],
            propuesta["simbolo"],
            propuesta["formato"],
            propuesta["separador_miles"],
            propuesta["separador_decimales"]
        )

        if resultado is None:

            return

        ok, motivo = resultado

        if not ok:

            self.mostrar_ajuste_error(motivo)

            return

        # La moneda queda aplicada en memoria, así
        # que los importes del resto de la
        # aplicación cambian sin reiniciar.

        self.mostrar_exito(
            f"Moneda actualizada. Ahora los "
            f"importes se ven como "
            f"{formato_dinero(1234.5)}."
        )

        self.cargar_ajustes()

    def mostrar_ajuste_error(self, mensaje):

        self.etiqueta_ajuste_error.setText(mensaje)

        self.etiqueta_ajuste_error.setVisible(True)

    def ocultar_ajuste_error(self):

        self.etiqueta_ajuste_error.setText("")

        self.etiqueta_ajuste_error.setVisible(False)

    # =============================
    # UTILIDADES
    # =============================

    def pintar_datos(self, tabla, filas):
        """
        Vuelca listas de valores en una tabla de
        diagnóstico. Cada fila puede traer 2 o 3
        columnas (campo/valor, o tabla/filas/
        tamaño), así que se recorre entera.
        """

        tabla.setRowCount(len(filas))

        for indice, fila in enumerate(filas):

            for columna, valor in enumerate(fila):

                item = QTableWidgetItem(str(valor))

                item.setToolTip(str(valor))

                tabla.setItem(
                    indice, columna, item
                )

        # La altura se ajusta a las filas: con una
        # altura fija, las tablas cortas se
        # quedaban con barra de desplazamiento y
        # solo mostraban la primera fila.
        ajustar_alto_tabla(tabla)

    def reaplicar_estilo(self, widget):
        """
        Cambiar el objectName no reestila el widget
        hasta que se lo pide uno.
        """

        widget.style().unpolish(widget)
        widget.style().polish(widget)
