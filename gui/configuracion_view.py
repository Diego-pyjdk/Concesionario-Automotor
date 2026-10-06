from gui.respaldo_dialog import RespaldoDialog
from utils.helpers import crear_boton_secundario
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
    MONEDAS,
    nombre_de,
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

        layout.addWidget(crear_boton_secundario('Copias de seguridad', self.abrir_respaldos))
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

    def abrir_respaldos(self):
        RespaldoDialog(self).exec()

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
        # Un desplegable con las dos monedas, y nada
        # más. El símbolo, el formato, los dos
        # separadores y los decimales salen del
        # catálogo: se elige UNA moneda, no cinco
        # caracteres sueltos.
        #
        # Antes había cinco campos: un código, un
        # símbolo y tres desplegables. Se podían
        # combinar en cosas que no son monedas: guaraníes
        # con dos decimales (el guaraní no tiene
        # subunitario), o dólares con punto de miles.
        # Nada de eso da un error al guardarlo; sale un
        # importe ilegible y se descubre leyendo un
        # contrato.
        #
        # Con el desplegable no se puede. Y nadie
        # teclea un símbolo.

        separador = QLabel("Moneda")

        separador.setObjectName("subtitulo")

        layout.addWidget(separador)

        formulario = QFormLayout()

        self.campo_moneda = QComboBox()

        for codigo in MONEDAS:

            self.campo_moneda.addItem(
                self.etiqueta_de_moneda(codigo),
                codigo
            )

        formulario.addRow(
            "Moneda de la aplicación:",
            self.campo_moneda
        )

        # ------------------------------
        # LO QUE SE VE
        # ------------------------------
        # Se enseña el resultado, no la configuración:
        # al usuario le importa qué sale en pantalla, no
        # qué separador hay guardado.

        self.etiqueta_detalle_moneda = QLabel("")

        self.etiqueta_detalle_moneda.setObjectName(
            "pie"
        )

        self.etiqueta_detalle_moneda.setWordWrap(True)

        layout.addLayout(formulario)

        layout.addWidget(
            self.etiqueta_detalle_moneda
        )

        # ------------------------------
        # LOS EJEMPLOS
        # ------------------------------
        # Con los importes que de verdad se usan: un
        # vehículo, un cobro grande y uno enorme. Con un
        # solo ejemplo de 1.234,50 no se distingue un
        # formato de otro.

        self.etiqueta_ejemplo_moneda = QLabel("")

        self.etiqueta_ejemplo_moneda.setObjectName(
            "aviso"
        )

        self.etiqueta_ejemplo_moneda.setWordWrap(True)

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

        # ------------------------------
        # LO QUE NO PASA
        # ------------------------------
        # Avisar de que cambiar la moneda NO convierte
        # nada es parte de la pantalla, no un comentario
        # al pie del código: es la duda que va a
        # aparecer, y si no está escrita aquí alguien la
        # resuelve como le parezca.

        self.aviso_conversion = QLabel(
            "Cambiar la moneda NO convierte los "
            "importes ya registrados: no hay tipo de "
            "cambio. Solo cambia cómo se muestran a "
            "partir de ahora. Los contratos ya "
            "firmados siguen con la moneda con la que "
            "se hicieron."
        )

        self.aviso_conversion.setObjectName("pie")

        self.aviso_conversion.setWordWrap(True)

        layout.addWidget(self.aviso_conversion)

        # Cada cambio enseña cómo quedaría, para no
        # tener que guardar y cerrar para comprobar.

        self.campo_moneda.currentTextChanged.connect(
            self.previsualizar_moneda
        )

        if not self.es_administrador:

            self.campo_stock_minimo.setEnabled(False)

            self.boton_guardar_ajuste.setEnabled(
                False
            )

            self.campo_moneda.setEnabled(False)

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

        # Se rellena con la señal bloqueada: al
        # asignar el elemento dispara la
        # previsualización, y así se vería un ejemplo
        # a medias de la moneda ANTERIOR.

        self.campo_moneda.blockSignals(True)

        try:

            indice = self.campo_moneda.findData(
                moneda["codigo"]
            )

            if indice < 0:

                # La moneda guardada no está en el
                # catálogo. Puede venir de una versión
                # anterior que admítía cualquier código.
                # Se añade al desplegable en vez de
                # quedarse con la primera opción sin
                # avisar, porque cambiar sin que nadie
                # lo haya pedido es peor que no poder
                # elegir.

                self.campo_moneda.addItem(
                    self.etiqueta_de_moneda(
                        moneda["codigo"], conocida=False
                    ),
                    moneda["codigo"]
                )

                indice = self.campo_moneda.count() - 1

            self.campo_moneda.setCurrentIndex(indice)

        finally:

            self.campo_moneda.blockSignals(False)

        self.previsualizar_moneda()

    def etiqueta_de_moneda(self, codigo, conocida=True):
        """
        Lo que se lee en el desplegable.

        Lleva el símbolo al lado del nombre porque
        "Guaraní paraguayo" solo, sin "Gs.", no dice
        cómo se van a ver los importes; y al revés,
        el símbolo solo no dice en qué país se está.

        El símbolo oficial del guaraní (₲, U+20B2) no
        se usa aquí por el mismo motivo que en los PDF:
        no está en cp1252 y sale como "?" en cualquier
        fuente base-14. Va "Gs.", que además es como
        se escribe en un documento de este país.
        """

        entrada = MONEDAS.get(codigo)

        if not entrada:

            return (
                f"{codigo} (moneda desconocida)"
            )

        return (
            f"{entrada['nombre']}  "
            f"({entrada['simbolo']} {codigo})"
        )

    def moneda_elegida(self):
        """
        El código de la moneda seleccionada ahora
        mismo.
        """

        return self.campo_moneda.currentData()

    def campos_moneda(self):

        return (self.campo_moneda,)

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

    def previsualizar_moneda(self):
        """
        Muestra cómo quedarían los importes con la
        moneda elegida, sin guardar nada.

        ------------------------------
        # CON QUÉ IMPORTES
        # ------------------------------

        Con los que de verdad aparecen en la
        aplicación: un vehículo de gama media, un cobro
        grande y uno enorme. Un solo ejemplo de
        "1.234,50" no distingue un formato de otro, y
        el punto es justo el que se quiere ver: si el
        separador de miles aparece donde toca y los
        decimales donde toca.

        El último importa porque es el que rompe: con
        separadores de siempre, 1.500.000,00 cabe en
        una columna y 150.000.000 no, y el recorte se
        ve aquí y no en la tabla de clientes.
        """

        codigo = self.moneda_elegida()

        if not codigo:

            return

        self.etiqueta_detalle_moneda.setText(
            f"{nombre_de(codigo)} ({codigo})  ·  "
            f"se muestran "
            f"{self.decimales_de(codigo)} decimales"
            + (
                "  ·  no usa decimales"
                if self.decimales_de(codigo) == 0
                else ""
            )
        )

        ejemplos = [
            ("un vehículo", 45000000),
            ("un cobro", 2500000),
            ("una venta grande", 150000000)
        ]

        partes = []

        for etiqueta, valor in ejemplos:

            partes.append(
                f"{etiqueta}: "
                f"{formato_dinero(valor, moneda=codigo)}"
            )

        self.etiqueta_ejemplo_moneda.setText(
            "Se vería así  —  "
            + "  ·  ".join(partes)
        )

    def decimales_de(self, codigo):
        """
        Cuántos decimales muestra una moneda.
        """

        entrada = MONEDAS.get(codigo)

        if not entrada:

            return 2

        return entrada["decimales"]

    def guardar_moneda(self):

        codigo = self.moneda_elegida()

        if not codigo:

            return

        self.ocultar_ajuste_error()

        resultado = self.proteger(
            actualizar_moneda,
            codigo
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
            f"Ahora la aplicación trabaja en "
            f"{nombre_de(codigo)}. Los importes se "
            f"ven como {formato_dinero(1500000)}. "
            "No se ha convertido ningún valor."
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
