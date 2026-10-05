# ==========================================
# GARANTÍAS DE UN CONTRATO
# ==========================================
# Dos formularios en un archivo, porque son las dos
# caras de la misma pregunta: qué se ofreció como
# respaldo, y qué se hizo con ello.
#
#
# ----------------------------------------------------
# LO QUE ESTOS FORMULARIOS NO HACEN
# ----------------------------------------------------
# Un gravamen es una INSCRIPCIÓN REGISTRAL. Su
# procedencia, sus datos, su forma y su rato de
# eficacia dependen de lo que establezca el Registro
# Público y de lo que corresponda legalmente en cada
# caso.
#
# Estos formularios REGISTRAN lo que el concesionario
# afirma. No tramitan nada, no generan el documento
# registral y no certifican nada ante nadie. Marcar
# aquí una garantía como "inscrita" dice que alguien se
# hizo cargo del trámite fuera del programa; no lo
# inscribe en ninguna parte.
#
# Por eso el aviso sale SIEMPRE, con garantías o sin
# ellas, y por eso no se calcula el importe de la
# garantía ni se decide si una garantía es suficiente:
# eso no lo puede decidir un programa.
#
# Revise el procedimiento con un abogado y con el
# escribano antes de dar de alta un gravamen.


from datetime import date

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout
)

from database.contratos import obtener_contrato

import database.garantias as garantias

from errores import PermisoDenegado

from utils.helpers import (
    crear_boton_principal,
    crear_boton_secundario,
    conectar_enter_guardar
)

from utils.moneda import formato_dinero

from utils.registro import registrar_error_inesperado


class FormularioGarantia(QDialog):
    """
    La base de los dos formularios.

    Va por partes porque comparten medio archivo: el
    aviso registral, la disposición de los botones, el
    tratamiento del error y el pedir motivo. Duplicado,
    el día que cambie el aviso habrá que acordarse de
    cambiarlo en los dos sitios, y uno de los dos se
    quedará viejo sin que nadie lo note.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setModal(True)

        self.setMinimumWidth(520)

        self.layout_principal = QVBoxLayout()

        self.layout_principal.setSpacing(14)

        self.setLayout(self.layout_principal)

        self.etiqueta_error = QLabel("")

        self.etiqueta_error.setObjectName("aviso_error")

        self.etiqueta_error.setWordWrap(True)

        # Las etiquetas de error empiezan ocultas: si
        # no, queda un recuadro rojo vacío que parece
        # un error que ya ocurrió.

        self.etiqueta_error.setVisible(False)

    # ------------------------------
    # AVISO REGISTRAL
    # ------------------------------

    def poner_aviso(self):

        etiqueta = QLabel(garantias.AVISO_GRAVAMEN)

        etiqueta.setObjectName("aviso")

        etiqueta.setWordWrap(True)

        self.layout_principal.addWidget(etiqueta)

        return etiqueta

    def poner_botonera(self, texto_guardar, al_guardar):

        fila = QHBoxLayout()

        fila.setSpacing(10)

        fila.addStretch()

        fila.addWidget(crear_boton_secundario(
            "Cancelar", self.reject
        ))

        self.boton_guardar = crear_boton_principal(
            texto_guardar, al_guardar
        )

        fila.addWidget(self.boton_guardar)

        self.layout_principal.addLayout(fila)

    # ------------------------------
    # ERROR
    # ------------------------------

    def mostrar_error(self, mensaje):

        self.etiqueta_error.setText(mensaje)

        self.etiqueta_error.setVisible(True)

    def ocultar_error(self):

        self.etiqueta_error.setText("")

        self.etiqueta_error.setVisible(False)

    def avisar_error_insperado(self, error, que):

        registrar_error_inesperado(error)

        self.mostrar_error(
            f"Ocurrió un problema al {que}. No se "
            "guardó nada. El detalle está en "
            "registro_errores.log."
        )


# ==========================================
# DAR DE ALTA UNA GARANTÍA
# ==========================================

class GarantiaForm(FormularioGarantia):
    """
    Registrar qué respalda una venta financiada.
    """

    def __init__(self, parent=None, id_contrato=None):
        super().__init__(parent)

        self.id_contrato = id_contrato

        self.contrato = None

        self.setWindowTitle("Registrar garantía")

        self.crear_interfaz()

        self.cargar()

    def crear_interfaz(self):

        # ------------------------------
        # DE QUIÉN ES
        # ------------------------------

        self.etiqueta_contrato = QLabel("")

        self.etiqueta_contrato.setObjectName("aviso")

        self.etiqueta_contrato.setWordWrap(True)

        self.layout_principal.addWidget(
            self.etiqueta_contrato
        )

        # ------------------------------
        # QUÉ ES
        # ------------------------------

        formulario = QFormLayout()

        formulario.setSpacing(10)

        self.campo_tipo = QComboBox()

        for clave, texto in garantias.TIPOS.items():

            self.campo_tipo.addItem(texto, clave)

        formulario.addRow("Tipo:", self.campo_tipo)

        self.campo_descripcion = QLineEdit()

        self.campo_descripcion.setPlaceholderText(
            "Qué se ofreció y en qué condiciones"
        )

        formulario.addRow(
            "Descripción:", self.campo_descripcion
        )

        self.campo_institucion = QLineEdit()

        self.campo_institucion.setPlaceholderText(
            "Banco, notaría, aseguradora... "
            "(si lo hay)"
        )

        formulario.addRow(
            "Institución:", self.campo_institucion
        )

        self.campo_observaciones = QPlainTextEdit()

        self.campo_observaciones.setPlaceholderText(
            "Cualquier cosa que deba saber quien "
            "lea esto dentro de dos años"
        )

        self.campo_observaciones.setMaximumHeight(80)

        formulario.addRow(
            "Observaciones:", self.campo_observaciones
        )

        # ------------------------------
        # EL GRAVAMEN
        # ------------------------------
        # Casilla aparte, y NO marcada de serie.

        # Un gravamen sin querer marcado cambia lo que
        # el programa afirma: convierte un aval en un
        # gravamen registral. Que el usuario lo decida
        # cada vez.

        self.campo_gravamen = QCheckBox(
            "Es un gravamen (inscripción registral)"
        )

        formulario.addRow("", self.campo_gravamen)

        # ------------------------------
        # EN QUÉ ESTÁ
        # ------------------------------

        self.campo_estado = QComboBox()

        # Solo los estados a los que se puede dar de
        # alta. "Liberada" no está: una garantía
        # nace sin liberar o pendiente de inscribir.

        for clave in ("pendiente", "inscrita"):

            self.campo_estado.addItem(
                garantias.ESTADOS[clave], clave
            )

        formulario.addRow("Estado:", self.campo_estado)

        # ------------------------------
        # LOS DATOS DE LA INSCRIPCIÓN
        # ------------------------------
        # Se rellenan y se habilitan cuando el estado es
        # "inscrita". "Pendiente" significa pendiente,
        # y guardar un número de inscripción con ella
        # pondría en la base algo que no ha pasado.

        self.campo_numero = QLineEdit()

        self.campo_numero.setPlaceholderText(
            "Nº que figura en el registro"
        )

        formulario.addRow(
            "Nº de inscripción:", self.campo_numero
        )

        self.campo_fecha_inscripcion = QDateEdit()

        self.campo_fecha_inscripcion.setCalendarPopup(True)

        self.campo_fecha_inscripcion.setDisplayFormat(
            "dd/MM/yyyy"
        )

        formulario.addRow(
            "Fecha de inscripción:",
            self.campo_fecha_inscripcion
        )

        self.campo_estado.currentIndexChanged.connect(
            self.al_cambiar_estado
        )

        self.layout_principal.addLayout(formulario)

        # ------------------------------
        # EL AVISO
        # ------------------------------
        # Siempre. Ver la cabecera del archivo.

        self.etiqueta_aviso = self.poner_aviso()

        self.layout_principal.addWidget(
            self.etiqueta_error
        )

        self.poner_botonera(
            "Registrar garantía", self.guardar
        )

        conectar_enter_guardar(
            [
                self.campo_descripcion,
                self.campo_institucion,
                self.campo_numero
            ],
            self.guardar
        )

        self.al_cambiar_estado()

    def cargar(self):

        self.contrato = self.leer_contrato()

        if not self.contrato:

            self.boton_guardar.setEnabled(False)

            self.mostrar_error(
                "No se pudo leer el contrato."
            )

            return

        self.etiqueta_contrato.setText(
            f"<b>Contrato {self.contrato['numero']}</b> · "
            f"{self.contrato['cliente']}<br>"
            f"Saldo financiado: "
            f"{formato_dinero(self.contrato['saldo_financiado'])}"
        )

    def leer_contrato(self):

        try:

            return obtener_contrato(self.id_contrato)

        except PermisoDenegado:

            return None

        except Exception:

            registrar_error_inesperado(
                Exception(
                    "No se pudo leer el contrato "
                    f"{self.id_contrato} para dar de alta "
                    "una garantía."
                )
            )

            return None

    # ------------------------------
    # EL ESTADO MANDA
    # ------------------------------

    def al_cambiar_estado(self, _indice=None):

        inscrita = (
            self.campo_estado.currentData() == "inscrita"
        )

        self.campo_numero.setEnabled(inscrita)

        self.campo_fecha_inscripcion.setEnabled(inscrita)

        if inscrita:

            self.etiqueta_aviso.setText(
                "<b>Va a guardar una garantía como "
                "INSCRITA.</b> Eso no la inscribe: deja "
                "constancia de que alguien afirma que ya "
                "se hizo. Si no es así, márquela como "
                "pendiente."
            )

            return

        self.etiqueta_aviso.setText(garantias.AVISO_GRAVAMEN)

    # ------------------------------
    # GUARDAR
    # ------------------------------

    def guardar(self):

        self.ocultar_error()

        estado = self.campo_estado.currentData()

        if estado == "inscrita" and (
            not self.campo_numero.text().strip()
        ):

            self.mostrar_error(
                "Si la garantía está inscrita, hace "
                "falta el número de inscripción."
            )

            return

        try:

            id_garantia, motivo = garantias.registrar_garantia(
                id_contrato=self.id_contrato,
                tipo=self.campo_tipo.currentData(),
                descripcion=(
                    self.campo_descripcion.text().strip()
                    or None
                ),
                es_gravamen=(
                    1 if self.campo_gravamen.isChecked()
                    else 0
                ),
                institucion=(
                    self.campo_institucion.text().strip()
                    or None
                ),
                numero_inscripcion=(
                    self.campo_numero.text().strip() or None
                ),
                fecha_inscripcion=(
                    self.campo_fecha_inscripcion
                    .date().toString("yyyy-MM-dd")
                    if estado == "inscrita"
                    else None
                ),
                observaciones=(
                    self.campo_observaciones
                    .toPlainText().strip() or None
                ),
                estado=estado
            )

        except PermisoDenegado as error:

            self.mostrar_error(error.mensaje)

            return

        except Exception as error:

            self.avisar_error_insperado(
                error, "registrar la garantía"
            )

            return

        if id_garantia is None:

            self.mostrar_error(motivo)

            return

        self.accept()


# ==========================================
# ANOTAR LA INSCRIPCIÓN
# ==========================================

class FormularioInscripcion(FormularioGarantia):
    """
    Poner los datos registrales de una garantía que
    ya está pendiente.

    Va aparte del alta porque son dos momentos
    distintos: se ofrece la garantía el día de la
    venta, y se inscriben días o semanas después,
    cuando alguien se acerca al Registro. Encajarlos
    en un formulario obligaría a esperar con la
    garantía sin registrar, y lo que se acaba
    haciendo es saltarse el paso.
    """

    def __init__(self, parent=None, id_garantia=None):
        super().__init__(parent)

        self.id_garantia = id_garantia

        self.garantia = None

        self.setWindowTitle("Anotar la inscripción")

        self.crear_interfaz()

        self.cargar()

    def crear_interfaz(self):

        self.etiqueta_garantia = QLabel("")

        self.etiqueta_garantia.setObjectName("aviso")

        self.etiqueta_garantia.setWordWrap(True)

        self.layout_principal.addWidget(
            self.etiqueta_garantia
        )

        formulario = QFormLayout()

        formulario.setSpacing(10)

        self.campo_institucion = QLineEdit()

        formulario.addRow(
            "Institución:", self.campo_institucion
        )

        self.campo_numero = QLineEdit()

        self.campo_numero.setPlaceholderText(
            "Nº que figura en el registro"
        )

        formulario.addRow(
            "Nº de inscripción:", self.campo_numero
        )

        self.campo_fecha = QDateEdit()

        self.campo_fecha.setCalendarPopup(True)

        self.campo_fecha.setDisplayFormat("dd/MM/yyyy")

        formulario.addRow("Fecha:", self.campo_fecha)

        self.campo_observaciones = QPlainTextEdit()

        self.campo_observaciones.setMaximumHeight(80)

        formulario.addRow(
            "Observaciones:", self.campo_observaciones
        )

        self.layout_principal.addLayout(formulario)

        self.etiqueta_aviso = self.poner_aviso()

        self.layout_principal.addWidget(
            self.etiqueta_error
        )

        self.poner_botonera(
            "Anotar como inscrita", self.guardar
        )

        conectar_enter_guardar(
            [self.campo_institucion, self.campo_numero],
            self.guardar
        )

    def cargar(self):

        self.garantia = self.leer_garantia()

        if not self.garantia:

            self.boton_guardar.setEnabled(False)

            self.mostrar_error(
                "No se pudo leer la garantía."
            )

            return

        garantia = self.garantia

        self.etiqueta_garantia.setText(
            f"<b>"
            f"{garantias.TIPOS.get(garantia['tipo'], garantia['tipo'])}"
            f"</b><br>"
            f"Contrato {garantia['contrato_numero']} · "
            f"{garantia['cliente']}<br>"
            f"Estado actual: "
            f"{garantias.ESTADOS.get(garantia['estado'], garantia['estado'])}"
        )

        if garantia["institucion"]:

            self.campo_institucion.setText(
                garantia["institucion"]
            )

        if garantia["numero_inscripcion"]:

            self.campo_numero.setText(
                garantia["numero_inscripcion"]
            )

        if garantia["observaciones"]:

            self.campo_observaciones.setPlainText(
                garantia["observaciones"]
            )

        self.campo_fecha.setDate(
            self.campo_fecha.date().fromString(
                date.today().isoformat(), "yyyy-MM-dd"
            )
        )

        # ------------------------------
        # SI YA ESTÁ INSCRITA
        # ------------------------------

        if garantia["estado"] != "pendiente":

            self.boton_guardar.setEnabled(False)

            self.mostrar_error(
                f"Esta garantía ya está en estado "
                f"'{garantias.ESTADOS.get(garantia['estado'])}' "
                "y no se puede volver a inscribir."
            )

    def leer_garantia(self):

        try:

            return garantias.obtener_garantia(
                self.id_garantia
            )

        except PermisoDenegado:

            return None

        except Exception:

            registrar_error_inesperado(
                Exception(
                    "No se pudo leer la garantía "
                    f"{self.id_garantia}."
                )
            )

            return None

    def guardar(self):

        self.ocultar_error()

        if not self.campo_numero.text().strip():

            self.mostrar_error(
                "El número de inscripción es "
                "obligatorio: sin él, la garantía queda "
                "como una promesa sin respaldo."
            )

            return

        if not self.confirmar():

            return

        try:

            correcto, resultado = garantias.\
                cambiar_estado_garantia(
                    self.id_garantia,
                    "inscrita",
                    numero_inscripcion=(
                        self.campo_numero.text().strip()
                    ),
                    fecha_inscripcion=self.campo_fecha
                    .date().toString("yyyy-MM-dd"),
                    institucion=(
                        self.campo_institucion.text().strip()
                        or None
                    ),
                    observaciones=(
                        self.campo_observaciones
                        .toPlainText().strip() or None
                    )
                )

        except PermisoDenegado as error:

            self.mostrar_error(error.mensaje)

            return

        except Exception as error:

            self.avisar_error_insperado(
                error, "anotar la inscripción"
            )

            return

        if not correcto:

            self.mostrar_error(resultado)

            return

        self.accept()

    def confirmar(self):
        """
        Se pregunta antes de anotar.

        Marcar una garantía como inscrita es la acción
        que hace que este programa afirme ante el
        historial que el gravamen existe. Es la más
        fácil de verdad sin querer, porque parece un
        trámite de oficina.
        """

        respuesta = QMessageBox.question(
            self,
            "Anotar como inscrita",
            "Se guardará que esta garantía está "
            "inscrita con el número "
            f"{self.campo_numero.text().strip()} "
            f"del {self.campo_fecha.date().toString('dd/MM/yyyy')}.\n\n"
            "Esto NO inscribe nada en ningún registro: "
            "deja constancia de que alguien afirma que "
            "ya se hizo.\n\n"
            "¿Es así?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        return respuesta == QMessageBox.Yes
