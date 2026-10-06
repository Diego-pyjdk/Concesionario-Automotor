# ==========================================
# PDF DEL CONTRATO


# ==========================================
# Maqueta el documento con los datos que ya
# trae database/contratos.py.
#
# No se hace nada de lógica aquí: ni consultas,
# ni cálculos de negocio. Solo se coloca texto.
#
# Se usa Platypus (reportlab.platypus), que
# compone el documento en flujo: cada bloque
# mide su alto, el texto se ajusta solo al
# ancho de la columna y salta de página sin
# partir nada a la mitad. Con esto ya no hay
# que calcular posiciones ni anchos de glifo a
# mano, que es donde se|colocaban los errores.
#
# La banda superior y el pie se dibujan en
# _pintar_cabecera y _pintar_pie, que reportlab
# llama una vez por hoja.


# ==========================================


import datetime
import os

import utils.moneda as _moneda

from database.configuracion import NOMBRE_SISTEMA

from database.contratos import (
    ESTADOS,
    nombre_archivo
)

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    ParagraphStyle,
    getSampleStyleSheet
)
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)


# ==========================================
# RUTAS


# ==========================================
# Los PDF se guardan junto al proyecto para que
# el usuario los encuentre sin buscar.

RAIZ = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

CARPETA = os.path.join(RAIZ, "documentos", "contratos")

NO_REGISTRADO = "No registrado"

# Márgenes. Arriba deja sitio a la banda azul
# que dibuja _pintar_cabecera.

MARGEN = 18 * mm

MARGEN_SUPERIOR = 34 * mm

MARGEN_INFERIOR = 20 * mm

# Ancho con el que se compone el texto.

ANCHO_UTIL = A4[0] - MARGEN * 2

# Alto de la banda azul de la cabecera.

ALTO_BANDA = 27 * mm


def ruta_documento(numero):
    """
    Ruta absoluta del PDF de un contrato.
    """

    return os.path.join(
        CARPETA, nombre_archivo(numero)
    )


def ruta_relativa(numero):
    """
    Ruta guardada en la base: relativa al
    proyecto, para que no se rompa al mover la
    carpeta.
    """

    return os.path.join(
        "documentos", "contratos",
        nombre_archivo(numero)
    )


def formato_fecha(valor):
    """
    Fecha legible en español.
    """

    if valor is None:

        return NO_REGISTRADO

    if isinstance(valor, (datetime.date, datetime.datetime)):

        return valor.strftime("%d/%m/%Y")

    return str(valor)


def formato_dinero(valor, moneda=None):
    """
    Importe con separador de miles.

    El símbolo de la moneda sale de
    utils.moneda, que es el único sitio donde vive.
    Se mantiene esta función porque el PDF, los
    reportes y las vistas la usan por todas partes.

    ------------------------------
    # POR QUÉ `moneda` Y NO SOLO EL
    # VALOR
    # ------------------------------

    Porque un contrato ya firmado dice una moneda, y esa
    no tiene por qué ser la que hay configurada ahora.

    Si el concesionario pasa de dólares a guaraníes y el
    PDF del contrato se imprimiera con la moneda en
    curso, un contrato de $ 25.000 saldría en el papel
    como "Gs. 25.000". Eso no es un detalle de
    presentación: es un documento firmado que dice otra
    cosa que la que se pactó, y que además está mal
    porque el número no se ha convertido.

    Con `moneda=contrato["moneda"]` el PDF sale
    siempre como se firmó.

    Sin el argumento se usa la moneda en curso, que es
    lo que quieren las vistas que muestran un número
    suelto.
    """

    return _moneda.formato_dinero(valor, moneda=moneda)


def cuota_importe(contrato):
    """
    Importe de cada cuota.

    Solo se usa para mostrar. Si anticipo es 0 y
    no hay cuotas, no hay nada que calcular.
    """

    cantidad = contrato["cantidad_cuotas"]

    if not cantidad or cantidad < 1:

        return None

    try:

        precio = float(contrato["precio_venta"])

        anticipo = float(contrato["anticipo"] or 0)

    except (TypeError, ValueError):

        return None

    resto = precio - anticipo

    if resto < 0:
        resto = 0.0

    return resto / cantidad


def color_estado(estado):
    """
    Color del estado, discreto: el documento se
    imprime en blanco y negro.
    """

    if estado == "activo":
        return colors.HexColor("#15803d")

    if estado == "finalizado":
        return colors.HexColor("#2563eb")

    if estado == "cancelado":
        return colors.HexColor("#b91c1c")

    return colors.HexColor("#64748b")


# ==========================================
# PALETA


# ==========================================
# La misma del gui/estilo.css, para que el PDF
# se parezca a la aplicación.

TINTA = colors.HexColor("#0f172a")

GRIS = colors.HexColor("#64748b")

CLARO = colors.HexColor("#e2e8f0")

AZUL = colors.HexColor("#2563eb")


# ==========================================
# ESTILOS


# ==========================================

def construir_estilos():
    """
    Los estilos del documento.

    Se construyen aquí y no como constantes de
    módulo porque getSampleStyleSheet() toca el
    registro global de reportlab: llamarlo al
    importar el módulo lo modificaría aunque
    nadie genere ningún PDF.
    """

    base = getSampleStyleSheet()

    estilos = {}

    estilos["seccion"] = ParagraphStyle(
        "seccion",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=TINTA,
        backColor=CLARO,
        # El padding va en el Table, no aquí:
        # reportlab no lo soporta en el estilo.
        spaceBefore=10,
        spaceAfter=0
    )

    estilos["etiqueta"] = ParagraphStyle(
        "etiqueta",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=GRIS
    )

    estilos["valor"] = ParagraphStyle(
        "valor",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=TINTA
    )

    estilos["valor_derecha"] = ParagraphStyle(
        "valor_derecha",
        parent=estilos["valor"],
        alignment=TA_RIGHT
    )

    estilos["cabecera_nombre"] = ParagraphStyle(
        "cabecera_nombre",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.white
    )

    estilos["cabecera_sub"] = ParagraphStyle(
        "cabecera_sub",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#dbeafe")
    )

    estilos["cabecera_etiqueta"] = ParagraphStyle(
        "cabecera_etiqueta",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#dbeafe")
    )

    estilos["cabecera_numero"] = ParagraphStyle(
        "cabecera_numero",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        alignment=TA_RIGHT,
        textColor=colors.white
    )

    estilos["firma_nombre"] = ParagraphStyle(
        "firma_nombre",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=TINTA
    )

    estilos["firma_detalle"] = ParagraphStyle(
        "firma_detalle",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=GRIS
    )

    estilos["parrafo"] = ParagraphStyle(
        "parrafo",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13.5,
        textColor=TINTA
    )

    estilos["pie"] = ParagraphStyle(
        "pie",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=GRIS
    )

    estilos["pie_fuerte"] = ParagraphStyle(
        "pie_fuerte",
        parent=estilos["pie"],
        fontName="Helvetica-Bold"
    )

    estilos["pie_estado"] = ParagraphStyle(
        "pie_estado",
        parent=estilos["pie_fuerte"],
        alignment=TA_RIGHT
    )

    estilos["total"] = ParagraphStyle(
        "total",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=TINTA
    )

    estilos["total_nota"] = ParagraphStyle(
        "total_nota",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=GRIS
    )

    estilos["centrado"] = ParagraphStyle(
        "centrado",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        alignment=TA_CENTER,
        textColor=GRIS
    )

    return estilos


# ==========================================
# PIEZAS


# ==========================================

def tabla_una_columna(contenido, estilos):
    """
    Una franja de color con un texto: el
    título de cada bloque del documento.
    """

    tabla = Table(
        [[Paragraph(contenido, estilos["seccion"])]],
        colWidths=[ANCHO_UTIL]
    )

    tabla.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0), (-1, -1),
                CLARO
            ),
            (
                "LEFTPADDING",
                (0, 0), (-1, -1),
                8
            ),
            (
                "RIGHTPADDING",
                (0, 0), (-1, -1),
                8
            ),
            (
                "TOPPADDING",
                (0, 0), (-1, -1),
                5
            ),
            (
                "BOTTOMPADDING",
                (0, 0), (-1, -1),
                5
            )
        ])
    )

    return tabla


def tabla_datos(filas, estilos, ancho_etiqueta=42 * mm):
    """
    Parejas etiqueta/valor.

    El valor va en negrita y se ajusta al ancho
    que le queda: si es largo (una dirección,
    unas observaciones) pasa a la línea de
    abajo sin salirse de la página.
    """

    filas_maquetadas = []

    for etiqueta, valor in filas:

        filas_maquetadas.append([
            Paragraph(etiqueta, estilos["etiqueta"]),
            Paragraph(str(valor), estilos["valor"])
        ])

    tabla = Table(
        filas_maquetadas,
        colWidths=[
            ancho_etiqueta,
            ANCHO_UTIL - ancho_etiqueta
        ]
    )

    tabla.setStyle(
        TableStyle([
            (
                "VALIGN",
                (0, 0), (-1, -1),
                "TOP"
            ),
            (
                "LEFTPADDING",
                (0, 0), (-1, -1),
                0
            ),
            (
                "RIGHTPADDING",
                (0, 0), (-1, -1),
                0
            ),
            (
                "TOPPADDING",
                (0, 0), (-1, -1),
                2
            ),
            (
                "BOTTOMPADDING",
                (0, 0), (-1, -1),
                5
            )
        ])
    )

    return tabla


def tabla_dos_columnas(filas, estilos):
    """
    Etiqueta y valor en dos columnas para
    aprovechar la página: sirve para los datos
    del vehículo, que son cortos.
    """

    maquetada = []

    for etiqueta, valor in filas:

        maquetada.append([
            Paragraph(f"{etiqueta}:", estilos["etiqueta"]),
            Paragraph(str(valor), estilos["valor"])
        ])

    # Cada par de la izquierda y de la derecha
    # van en una fila, así que la tabla se
    # recorre de dos en dos.

    mitad = ANCHO_UTIL / 2

    # La etiqueta se queda con su ancho justo y
    # el valor se lleva el resto de su mitad.

    ancho_etiqueta = 26 * mm

    tabla = Table(
        maquetada,
        colWidths=[
            ancho_etiqueta,
            mitad - ancho_etiqueta - 6 * mm,
            ancho_etiqueta,
            mitad - ancho_etiqueta
        ],
        hAlign="LEFT"
    )

    tabla.setStyle(
        TableStyle([
            (
                "VALIGN",
                (0, 0), (-1, -1),
                "TOP"
            ),
            (
                "LEFTPADDING",
                (0, 0), (-1, -1),
                0
            ),
            (
                "RIGHTPADDING",
                (0, 0), (-1, -1),
                8
            ),
            (
                "TOPPADDING",
                (0, 0), (-1, -1),
                2
            ),
            (
                "BOTTOMPADDING",
                (0, 0), (-1, -1),
                5
            ),
            # La segunda columna de cada par
            # empieza a media pagina.
            (
                "LINEBEFORE",
                (2, 0), (2, -1),
                0.5,
                CLARO
            )
        ])
    )

    return tabla


def bloque_firmas(contrato, estilos):
    """
    Huecos de firma.

    Van en KeepTogether: si no caben enteros,
    el bloque pasa entero a la página siguiente
    en vez de quedar partido con una línea
    arriba y el nombre abajo.
    """

    ancho_firma = (ANCHO_UTIL - 14 * mm) / 2

    izquierda = [
        Paragraph("EL CLIENTE", estilos["firma_nombre"]),
        Spacer(1, 34),
        Paragraph(
            contrato["cliente"],
            estilos["firma_detalle"]
        )
    ]

    if contrato["documento"]:

        izquierda.append(
            Paragraph(
                f"Doc.: {contrato['documento']}",
                estilos["firma_detalle"]
            )
        )

    derecha = [
        Paragraph("EL VENDEDOR", estilos["firma_nombre"]),
        Spacer(1, 34),
        Paragraph(
            contrato["vendedor"] or "",
            estilos["firma_detalle"]
        ),
        Paragraph(
            NOMBRE_SISTEMA,
            estilos["firma_detalle"]
        )
    ]

    tabla = Table(
        [[izquierda, derecha]],
        colWidths=[ancho_firma, ancho_firma]
    )

    tabla.setStyle(
        TableStyle([
            # La línea de firma, por encima de
            # cada nombre.
            (
                "LINEABOVE",
                (0, 0), (-1, -1),
                0.9,
                TINTA
            ),
            (
                "VALIGN",
                (0, 0), (-1, -1),
                "BOTTOM"
            ),
            (
                "LEFTPADDING",
                (0, 0), (-1, -1),
                0
            ),
            (
                "RIGHTPADDING",
                (0, 0), (-1, -1),
                14
            ),
            (
                "TOPPADDING",
                (0, 0), (-1, -1),
                4
            ),
            (
                "BOTTOMPADDING",
                (0, 0), (-1, -1),
                2
            )
        ])
    )

    return tabla


# ==========================================
# HOJA Y PLANTILLA


# ==========================================

def _pintar_cabecera(lienzo, documento):
    """
    Banda superior: nombre del concesionario y
    número de contrato. Se dibuja en todas las
    hojas, no solo en la primera: en un
    contrato de dos páginas la segunda también
    tiene que decir de qué contrato es.
    """

    contrato = documento.contrato

    ancho, alto = A4

    lienzo.saveState()

    lienzo.setFillColor(AZUL)

    lienzo.rect(
        0,
        alto - ALTO_BANDA,
        ancho,
        ALTO_BANDA,
        stroke=0,
        fill=1
    )

    lienzo.setFont("Helvetica-Bold", 15)

    lienzo.setFillColor(colors.white)

    lienzo.drawString(
        MARGEN,
        alto - 17 * mm,
        NOMBRE_SISTEMA.upper()
    )

    lienzo.setFont("Helvetica", 9)

    lienzo.setFillColor(
        colors.HexColor("#dbeafe")
    )

    lienzo.drawString(
        MARGEN,
        alto - 22.5 * mm,
        "Contrato de compraventa de vehículo"
    )

    lienzo.setFont("Helvetica", 8)

    lienzo.drawRightString(
        ancho - MARGEN,
        alto - 17 * mm,
        "CONTRATO N.º"
    )

    lienzo.setFont("Helvetica-Bold", 13)

    lienzo.setFillColor(colors.white)

    lienzo.drawRightString(
        ancho - MARGEN,
        alto - 22.5 * mm,
        contrato["numero"] or ""
    )

    lienzo.restoreState()


def _pintar_pie(lienzo, documento):
    """
    Pie con los datos del contrato y la
    etiqueta de estado.
    """

    contrato = documento.contrato

    ancho, alto = A4

    lienzo.saveState()

    # Línea de separación.

    lienzo.setStrokeColor(CLARO)

    lienzo.setLineWidth(0.8)

    lienzo.line(
        MARGEN,
        15 * mm,
        ancho - MARGEN,
        15 * mm
    )

    lienzo.setFont("Helvetica", 8)

    lienzo.setFillColor(GRIS)

    lienzo.drawString(
        MARGEN,
        11.5 * mm,
        f"{contrato['numero']}  ·  "
        f"Venta {contrato['venta_id']}  ·  "
        f"{NOMBRE_SISTEMA}"
    )

    lienzo.drawString(
        MARGEN,
        8 * mm,
        "Documento generado automáticamente. "
        "El contrato original firmado por las "
        "partes prevalece sobre este."
    )

    lienzo.setFont("Helvetica-Bold", 8)

    lienzo.setFillColor(
        color_estado(contrato["estado"])
    )

    lienzo.drawRightString(
        ancho - MARGEN,
        11.5 * mm,
        ESTADOS.get(
            contrato["estado"],
            contrato["estado"]
        ).upper()
    )

    lienzo.restoreState()


def _pintar_hoja(lienzo, documento):
    """
    Lo que se dibuja en el papel, por hoja.

    reportlab llama a esto una vez por cada
    página. Va aquí la banda superior y el pie,
    no en el flujo del documento: son decoración,
    no contenido, y así no ocupan hueco ni se
    repiten en el historial.
    """

    _pintar_cabecera(lienzo, documento)

    _pintar_pie(lienzo, documento)


def construir_documento(ruta, contrato):
    """
    El documento con su plantilla de página.

    _pintar_cabecera y _pintar_pie leen
    documento.contrato, así que el número se
    conoce sin recalcularlo por hoja.
    """

    documento = BaseDocTemplate(
        ruta,
        pagesize=A4,
        leftMargin=MARGEN,
        rightMargin=MARGEN,
        topMargin=MARGEN_SUPERIOR,
        bottomMargin=MARGEN_INFERIOR,
        title=(
            f"Contrato {contrato['numero']}"
        ),
        author=NOMBRE_SISTEMA
    )

    # Las funciones de cabecera y pie necesitan
    # los datos del contrato para dibujar el
    # número y el estado, y reportlab no se las
    # pasa: se guardan aquí.

    documento.contrato = contrato

    marco = Frame(
        MARGEN,
        MARGEN_INFERIOR,
        ANCHO_UTIL,
        A4[1] - MARGEN_SUPERIOR
        - MARGEN_INFERIOR,
        id="contenido"
    )

    documento.addPageTemplates(
        [
            PageTemplate(
                id="contrato",
                frames=[marco],
                onPage=_pintar_hoja
            )
        ]
    )

    return documento


# ==========================================
# GENERACIÓN


# ==========================================

def generar_contrato(contrato, ruta=None):
    """
    Crea el PDF del contrato.

    contrato: una fila de database/contratos.py
    ruta: dónde guardarlo. Por defecto
          documentos/contratos/contrato_<n>.pdf

    Devuelve la ruta del archivo.
    """

    if not contrato:

        raise ValueError(
            "No hay datos de contrato para generar "
            "el PDF."
        )

    estilos = construir_estilos()

    destino = ruta or ruta_documento(contrato["numero"])

    carpeta = os.path.dirname(destino)

    if carpeta and not os.path.exists(carpeta):

        os.makedirs(carpeta, exist_ok=True)

    documento = construir_documento(destino, contrato)

    historia = construir_historia(contrato, estilos)

    documento.build(historia)

    return destino


def construir_historia(contrato, estilos):
    """
    Los bloques del documento, en orden.

    Va en su propia función aparte de
    generar_contrato() porque es la parte que
    describe el documento: el resto es papel,
    márgenes y marco.
    """

    historia = []

    # ------------------------------
    # VEHÍCULO
    # ------------------------------

    historia.append(
        tabla_una_columna(
            "DATOS DEL VEHÍCULO", estilos
        )
    )

    historia.append(
        Spacer(1, 4)
    )

    historia.append(
        tabla_dos_columnas(
            [
                ("Marca", contrato["marca"]),
                ("Modelo", contrato["modelo"]),
                ("Año", contrato["anio"]),
                ("Chasis / VIN", contrato.get('vin') or NO_REGISTRADO),
                ("Matrícula", contrato.get('matricula') or NO_REGISTRADO),
                ("Color", contrato["color"] or NO_REGISTRADO),
                (
                    "Precio de lista",
                    formato_dinero(
                        contrato["precio_lista"],
                        moneda=contrato.get("moneda")
                    )
                )
            ],
            estilos
        )
    )

    # ------------------------------
    # CLIENTE
    # ------------------------------

    historia.append(
        KeepTogether(
            tabla_una_columna(
                "DATOS DEL CLIENTE", estilos
            )
        )
    )

    historia.append(
        Spacer(1, 4)
    )

    historia.append(
        tabla_datos(
            [
                ("Nombre:", contrato["cliente"]),
                (
                    "Documento:",
                    contrato["documento"] or NO_REGISTRADO
                ),
                (
                    "Teléfono:",
                    contrato["telefono"] or NO_REGISTRADO
                ),
                (
                    "Email:",
                    contrato["email"] or NO_REGISTRADO
                )
            ],
            estilos
        )
    )

    # ------------------------------
    # CONDICIONES DE PAGO
    # ------------------------------
    # Es la parte con valor legal: viaja junta,
    # precio y condiciones no se separan entre
    # dos hojas.

    bloque_pago = [
        tabla_una_columna(
            "CONDICIONES DE PAGO", estilos
        ),
        Spacer(1, 4)
    ]

    filas_pago = [
        (
            "Fecha de la operación:",
            formato_fecha(contrato["fecha"])
        ),
        (
            "Precio de venta:",
            formato_dinero(
                contrato["precio_venta"],
                moneda=contrato.get("moneda")
            )
        ),
        ("Forma de pago:", contrato["forma_pago"]),
        (
            "Anticipo:",
            formato_dinero(
                contrato["anticipo"],
                moneda=contrato.get("moneda")
            )
        )
    ]

    cuota = cuota_importe(contrato)

    if cuota is not None:

        filas_pago.append((
            f"Importe de cada cuota "
            f"({contrato['cantidad_cuotas']} cuotas):",
            formato_dinero(
                cuota,
                moneda=contrato.get("moneda")
            )
        ))

    bloque_pago.append(
        tabla_datos(filas_pago, estilos)
    )

    bloque_pago.append(
        bloque_total(contrato, cuota, estilos)
    )

    historia.append(
        KeepTogether(bloque_pago)
    )

    # ------------------------------
    # OBSERVACIONES
    # ------------------------------

    texto = (contrato["observaciones"] or "").strip()

    if texto:

        historia.append(
            tabla_una_columna(
                "OBSERVACIONES", estilos
            )
        )

        historia.append(
            Spacer(1, 5)
        )

        historia.append(
            Paragraph(
                escapar(texto),
                estilos["parrafo"]
            )
        )

    # ------------------------------
    # FIRMAS
    # ------------------------------

    historia.append(
        Spacer(1, 10)
    )

    historia.append(
        Paragraph(
            "En fe de lo acordado, firman las partes:",
            estilos["centrado"]
        )
    )

    historia.append(
        Spacer(1, 6)
    )

    historia.append(
        bloque_firmas(contrato, estilos)
    )

    return historia


def bloque_total(contrato, cuota, estilos):
    """
    Caja con el total pendiente y, si hay,
    el detalle de las cuotas.

    El total sale con la moneda del CONTRATO, no con
    la que haya configurada ahora: es la cifra que se
    pactó, y un contrato firmado que se reimprime
    diciendo otra moneda es un documento que ya no
    sirve para nada.
    """

    try:

        precio = float(contrato["precio_venta"])

        anticipo = float(contrato["anticipo"] or 0)

    except (TypeError, ValueError):

        precio = 0.0

        anticipo = 0.0

    saldo = max(0.0, precio - anticipo)

    moneda = contrato.get("moneda")

    if cuota is not None:

        # Tres celdas y tres anchos: si se pasa
        # menos, reportlab calcula el ultimo por
        # su cuenta, la fila se pasa de ancha y
        # la tabla se centra saliendose por la
        # izquierda.

        anchos = [
            ANCHO_UTIL - 78 * mm,
            34 * mm,
            44 * mm
        ]

        contenido = [
            [
                Paragraph(
                    "Total pendiente:",
                    estilos["total"]
                ),
                Paragraph(
                    formato_dinero(saldo, moneda=moneda),
                    estilos["total"]
                ),
                Paragraph(
                    f"en {contrato['cantidad_cuotas']} "
                    "cuotas",
                    estilos["total_nota"]
                )
            ]
        ]

    else:

        anchos = [
            ANCHO_UTIL - 70 * mm,
            70 * mm
        ]

        contenido = [
            [
                Paragraph(
                    "Total pendiente:",
                    estilos["total"]
                ),
                Paragraph(
                    formato_dinero(saldo, moneda=moneda),
                    estilos["valor_derecha"]
                )
            ]
        ]

    tabla = Table(
        contenido,
        colWidths=anchos
    )

    tabla.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0), (-1, -1),
                CLARO
            ),
            (
                "VALIGN",
                (0, 0), (-1, -1),
                "MIDDLE"
            ),
            (
                "LEFTPADDING",
                (0, 0), (-1, -1),
                10
            ),
            (
                "RIGHTPADDING",
                (0, 0), (-1, -1),
                10
            ),
            (
                "TOPPADDING",
                (0, 0), (-1, -1),
                7
            ),
            (
                "BOTTOMPADDING",
                (0, 0), (-1, -1),
                7
            ),
            # La celda de la nota se encoge a
            # lo que necesita el texto.
            (
                "ALIGN",
                (2, 0), (2, -1),
                "RIGHT"
            )
        ])
    )

    tabla.hAlign = "LEFT"

    return tabla


def escapar(texto):
    """
    Prepara un texto para que vaya dentro de un
    Paragraph.

    Son dos cosas distintas:

      - reportlab lee <b>, <i> y & como marcado.
        Un precio con "<" o una observacion con
        "&" rompen el parrafo, asi que se
        neutralizan siempre, no solo cuando
        "parece" que hacen falta.

      - Las fuentes base-14 no tienen todos los
        caracteres. reportlab sustituye en
        silencio lo que no sabe dibujar por su
        glifo .notdef, que en Helvetica es una
        "n": un emoji pegado en unas
        observaciones salia como "nn", que parece
        una palabra y no un signo ilegible. Se
        cambia por "?" a proposito, que se ve que
        falta algo.

    Lo que sí está en cp1252 se conserva: la
    "€" es 0x80 en WinAnsi y sale bien.
    """

    texto = texto.replace("&", "&amp;")

    texto = texto.replace("<", "&lt;")

    texto = texto.replace(">", "&gt;")

    return sustituir_no_mapeables(texto)


def sustituir_no_mapeables(texto):
    """
    Cambia por "?" lo que la fuente no puede
    dibujar.

    Se prueba a convertir a cp1252, que es lo
    que hay detrás de WinAnsiEncoding: todo lo
    que se convierta limpio se queda, y lo demás
    se marca. No se puede comprobar con el
    listado de caracteres de la fuente porque
    eso no cubre los equivalentes.
    """

    limpio = []

    for caracter in texto:

        try:

            caracter.encode("cp1252")

            limpio.append(caracter)

        except UnicodeEncodeError:

            limpio.append("?")

    return "".join(limpio)
