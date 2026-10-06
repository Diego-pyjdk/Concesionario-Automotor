# ==========================================
# PDF DEL RECIBO
# ==========================================
# El comprobante de un cobro.
#
# No es el contrato con otra portada: es un
# documento DISTINTO, para un uso distinto. El
# contrato se firma una vez y se guarda; el recibo se
# le entrega al cliente en el momento y a veces lo
# necesita al día siguiente. Por eso va en media
# carta, sin historiales ni cláusulas, con el importe
# en grande y un apartado para la firma de quien
# entrega.
#
# Lo que el recibo SÍ dice, y por qué:
#
#   Número de recibo. Es lo que el cliente usa para
#   reclamar y lo que usa quien contabiliza para
#   conciliar. Por eso se imprime aunque no se haya
#   escrito a mano: un cobro sin número escrito no
#   se puede impugnar.
#
#   Importe en letras. "Cien mil guaraníes" y
#   "$ 100.000,00". Un número mal leído en un
#   cheque es un problema; una cantidad escrita es
#   la que manda, y por eso va en el documento.
#
#   Qué cuota cubre. Para el cliente es lo que
#   importa saber: no solo cuánto pagó, sino por
#   qué se lo descuenta de lo que debe.
#
# Lo que NO dice, a propósito:
#
#   El saldo del contrato entero. Un recibo de
#   500.000 que al lado dice "saldo 4.200.000" se
#   lee como una afirmación sobre la deuda total, y
#   el saldo es una foto de HOY. Va el saldo de la
#   cuota, que es lo que ese recibo resuelve, y
#   quedó saldada o quedó pendiente.
#
# Los helpers de texto se importan de
# contrato_pdf.py en vez de repetirse: escapar() y
# sustituir_no_mapeables() tienen que hacer lo mismo
# en los dos documentos, y una copia es una copia
# que algún día se queda vieja sin que nadie lo note.


import datetime
import os

from decimal import Decimal

import utils.moneda as _moneda

from utils.moneda import formato_dinero

from database.configuracion import NOMBRE_SISTEMA

from database.financiera import ESTADOS as ESTADOS_CUOTA

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)

from utils.contrato_pdf import (
    AZUL,
    CLARO,
    GRIS,
    TINTA,
    escapar,
    sustituir_no_mapeables
)


# ==========================================
# RUTAS
# ==========================================

RAIZ = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

CARPETA = os.path.join(RAIZ, "documentos", "recibos")

# Media carta: un recibo grande no cabe en un cajero
# y se doblega de una manera que acaba con la
# cantidad dentro.

PAGINA = A5

MARGEN = 12 * mm

MARGEN_SUPERIOR = 26 * mm

ANCHO_UTIL = PAGINA[0] - MARGEN * 2

ALTO_BANDA = 20 * mm

NUMEROS = [
    "cero", "uno", "dos", "tres", "cuatro",
    "cinco", "seis", "siete", "ocho", "nueve",
    "diez", "once", "doce", "trece", "catorce",
    "quince", "dieciséis", "diecisiete",
    "dieciocho", "diecinueve", "veinte",
    "veintiuno", "veintidós", "veintitrés",
    "veinticuatro", "veinticinco", "veintiséis",
    "veintisiete", "veintiocho", "veintinueve"
]

DECENAS = {
    2: "veinti", 3: "treinta", 4: "cuarenta",
    5: "cincuenta", 6: "sesenta", 7: "setenta",
    8: "ochenta", 9: "noventa"
}

CENTENAS = {
    100: "cien", 200: "doscientos", 300: "trescientos",
    400: "cuatrocientos", 500: "quinientos",
    600: "seiscientos", 700: "setecientos",
    800: "ochocientos", 900: "novecientos"
}


# ==========================================
# EL IMPORTE EN LETRAS
# ==========================================

def en_letras(valor, decimales=2):
    """
    El importe escrito, para el recibo.

    Se escribe porque el número se puede leer mal y
    una cantidad escrita no tiene dos lecturas. Y se
    escribe por costumbre en un recibo, no por otra
    razón: es lo que el cliente espera ver y lo que
    sirve si el papel se rompe.

    Con los céntimos al final, como "/100": el
    separador de miles que se haya configurado puede
    ser el punto o la coma según el país, y "un millón
    con 56/100" se lee igual en los dos casos.
    Redondear el
    importe a entero también es una opción, pero
    echaba del recibo los 56.

    Hasta el millón. Un cobro de dos millones en
    letras son treinta y pico de palabras, y a partir
    de ahí el recibo lleva el número y una nota:
    escribirlo entero en letras taparía media hoja.

    ------------------------------
    # `decimales`
    # ------------------------------

    Cuántos decimales tiene la MONEDA, no el número.

    En guaraníes son 0 y no hay céntimos que escribir:
    un recibo que dijera "Gs. 1.500 con cero/100" está
    inventando una precisión que no existe. Con 0 sale
    "Gs. 1.500".

    Por eso no se mira el número: un cobro de 1.500,50
    en guaraníes son 1.501 enteros redondeados, y las
    letras tienen que decir eso y no "1.500 con
    cincuenta/100".

    Devuelve "" si el valor no es un número: es
    preferible un recibo sin la cantidad en letras
    que uno con "None" escrito donde va el dinero.
    """

    try:

        numero = float(valor)

    except (TypeError, ValueError):

        return ""

    # ------------------------------
    # ENTEROS Y CÉNTIMOS
    # ------------------------------
    # Se redondea a los decimales de la MONEDA, no a
    # dos fijos: en guaraníes el medio no se puede
    # pagar porque no existe, y 1.500,50 son 1.501.

    factor = 10 ** int(decimales)

    # Medio arriba y no `round()`, que empata al par:
    # en un recibo, un medio siempre se suma. Con
    # guaraníes esto es el redondeo al entero entero.

    escalado = int(abs(numero) * factor + 0.5)

    entero = escalado // factor

    centimos = escalado - entero * factor

    negativo = numero < 0

    if entero == 0 and centimos == 0:

        return "cero"

    millones, resto = divmod(entero, 1000000)

    miles, resto = divmod(resto, 1000)

    centenas, unidades = divmod(resto, 100)

    partes = []

    if millones:

        # "un millón", no "uno millón", y "millones"
        # sin tilde cuando no van con el uno.

        if millones == 1:

            partes.append("un millón")

        else:

            partes.append(
                f"{_centena(millones)} millones"
            )

    if miles:

        # "mil", no "uno mil".

        if miles == 1:

            partes.append("mil")

        else:

            partes.append(f"{_centena(miles)} mil")

    if resto:

        partes.append(
            _hasta_novecientos(centenas, unidades)
        )

    # ------------------------------
    # MENOS DE UNO
    # ------------------------------
    # 0,50 son cincuenta céntimos, no "con
    # cincuenta/100" a secas: el "con" sin nada
    # delante queda con un hueco al principio y se
    # lee como si faltara una palabra. Con "cero"
    # delante la frase entera tiene sentido, y
    # "cero con cincuenta/100" es como lo escribe
    # cualquiera.

    if not partes:

        partes.append("cero")

    texto = " y ".join(p for p in partes if p)

    if centimos:

        texto += (
            f" con {_hasta_noventa_y_nueve(centimos)}/100"
        )

    return ("menos " + texto) if negativo else texto


def _hasta_noventa_y_nueve(valor):
    """
    Para los céntimos: de 1 a 99, con la misma regla
    que las decenas ("con 50/100", "con 7/100").
    """

    return _hasta_novecientos(0, valor)


def _centena(valor):
    """
    De 1 a 999999 para las partes grandes.
    """

    miles, resto = divmod(valor, 1000)

    centenas, unidades = divmod(resto, 100)

    partes = []

    if miles:

        partes.append(f"{_hasta_novecientos(miles % 1000, 0)} mil")

    partes.append(_hasta_novecientos(centenas, unidades))

    return " ".join(p for p in partes if p)


def _hasta_novecientos(centenas, unidades):
    """
    De 1 a 999, sin el "mil".

    El "y" va entre las decenas y las unidades
    (treinta y cinco) y NO entre la centena y la
    decena: es "ciento treinta y cinco", no "ciento y
    treinta". Es la norma en español, y escribirlo
    bien no cuesta nada.
    """

    partes = []

    if centenas:

        # "centenas" llega como el dígito de la
        # centena (1..9), y CENTENAS está indexada
        # por el valor completo (100, 200...). Por
        # eso el 1 es aparte: se dice "ciento", no
        # "unocientos".

        partes.append(
            "ciento"
            if centenas == 1
            else CENTENAS[centenas * 100]
        )

        if unidades and unidades >= 10:

            partes.append("y")

    if unidades:

        if unidades < 30:

            partes.append(NUMEROS[unidades])

        else:

            decena, resto = divmod(unidades, 10)

            palabra = (
                DECENAS[decena]
                + (" y " if resto else "")
                + (NUMEROS[resto] if resto else "")
            )

            partes.append(palabra)

    return " ".join(p for p in partes if p) or "cero"


# ==========================================
# ESTILOS
# ==========================================

def construir_estilos():
    """
    Los estilos del recibo.

    Se construyen aquí y no como constantes de
    módulo por lo mismo que en contrato_pdf.py:
    getSampleStyleSheet() toca el registro global de
    reportlab y llamarlo al importar modificaría el
    proceso aunque nadie genere un recibo.
    """

    return {
        "recibo": ParagraphStyle(
            "recibo",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13,
            textColor=TINTA,
            alignment=TA_CENTER
        ),
        "numero": ParagraphStyle(
            "numero",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=GRIS,
            alignment=TA_CENTER
        ),
        "rotulo": ParagraphStyle(
            "rotulo",
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.5,
            textColor=GRIS
        ),
        "valor": ParagraphStyle(
            "valor",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=TINTA
        ),
        "grande": ParagraphStyle(
            "grande",
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=20,
            textColor=AZUL,
            alignment=TA_CENTER
        ),
        "letras": ParagraphStyle(
            "letras",
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=TINTA,
            alignment=TA_CENTER
        ),
        "nota": ParagraphStyle(
            "nota",
            fontName="Helvetica",
            fontSize=6.5,
            leading=8,
            textColor=GRIS
        )
    }


# ==========================================
# BLOQUES
# ==========================================

def texto(valor, estilo):
    """
    Un Paragraph con el texto ya preparado.

    SIEMPRE pasa por escapar() y sustituir_no_mapeables().
    Sin eso, un "&" en el nombre del cliente o un
    emoji en un concepto rompen el párrafo entero, y
    un emoji sale como "nn", que parece una palabra.
    """

    return Paragraph(
        escapar(sustituir_no_mapeables(valor)),
        estilo
    )


def bloque_cabecera(pago, contrato, estilos,
                   moneda=None):
    """
    Qué se cobró, de quién y a qué cuenta.
    """

    filas = [
        ("Recibo",
         pago["recibo"] or "sin número"),
        ("Fecha",
         _fecha(pago["fecha"])),
        ("Cliente",
         contrato["cliente"]),
        ("Documento",
         contrato["documento"] or "—"),
        ("Contrato",
         contrato["numero"]),
        (
            "Cubre",
            (
                f"Cuota {pago['numero_cuota']}"
                if pago["numero_cuota"] is not None
                else "pago a cuenta (sin imputar a "
                     "ninguna cuota)"
            )
        ),
        ("Forma de pago",
         pago["forma"]),
        (
            "Referencia",
            pago["referencia"] or "—"
        ),
        ("Concepto",
         pago["concepto"] or "—")
    ]

    if pago["estado"] == "anulado":

        filas.append((
            "ESTADO",
            "ANULADO. Este cobro no suma al saldo "
            "y no sirve para pagar."
        ))

    if pago["anulado_motivo"]:

        filas.append((
            "Motivo de la anulación",
            pago["anulado_motivo"]
        ))

    datos = []

    for rotulo, valor in filas:

        datos.append([
            texto(rotulo, estilos["rotulo"]),
            texto(str(valor), estilos["valor"])
        ])

    tabla = Table(
        datos,
        colWidths=[32 * mm, ANCHO_UTIL - 32 * mm]
    )

    tabla.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, CLARO)
    ]))

    return tabla


def bloque_importe(pago, estilos, moneda=None):
    """
    El importe, en grande y en letras.

    ------------------------------
    # LA MONEDA DEL CONTRATO
    # ------------------------------

    Un recibo de un cobro en dólares sale en dólares
    aunque hoy la aplicación esté en guaraníes: el
    importe y las letras van con la del contrato.

    Y las letras respetan sus decimales: en guaraníes
    no hay céntimos que escribir, así que no sale un
    "con 56/100" que no existe.
    """

    ajustes = _moneda.config_de(moneda)

    return [
        Spacer(1, 4 * mm),
        texto("IMPORTE COBRADO", estilos["rotulo"]),
        texto(
            formato_dinero(
                pago["importe"], moneda=moneda
            ),
            estilos["grande"]
        ),
        texto(
            en_letras(
                pago["importe"],
                ajustes["decimales"]
            )
            + " " + codigo_moneda(moneda),
            estilos["letras"]
        )
    ]


def codigo_moneda(moneda=None):
    """
    El código de la moneda, para las letras.

    Sin argumento, la que hay configurada ahora. Con
    argumento, la del contrato: el recibo de un cobro
    en dólares no puede llevar "PYG" detrás del
    importe porque el concesionario haya cambiado de
    moneda mientras tanto.

    Y en MAYÚSCULAS, porque es un código. En
    minúsculas, "mil con cincuenta usd" parece el
    final de una frase y no una unidad monetaria, que
    es justo lo que un recibo no puede parecer.
    """

    if moneda:

        return str(moneda).upper()

    return _moneda.config_actual()["codigo"] or ""


def bloque_cuota(pago, cuota, estilos,
                 moneda=None):
    """
    Qué queda de la cuota que este recibo cubre.

    Y aquí SÍ se dice el saldo de la cuota: es lo que
    este recibo resuelve, y va acompañado del estado
    para que "parcial" no se lea como "todo".
    """

    if cuota is None:

        return []

    filas = [
        ["Cuota", f"{cuota['numero']}"],
        [
            "Importe de la cuota",
            formato_dinero(
                cuota["importe"], moneda=moneda
            )
        ],
        [
            "Saldo tras este cobro",
            formato_dinero(
                cuota["saldo"], moneda=moneda
            )
        ],
        ["Estado de la cuota", _estado(cuota["estado"])]
    ]

    datos = [
        [
            texto(rotulo, estilos["rotulo"]),
            texto(valor, estilos["valor"])
        ]
        for rotulo, valor in filas
    ]

    tabla = Table(
        datos,
        colWidths=[42 * mm, ANCHO_UTIL - 42 * mm]
    )

    tabla.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOX", (0, 0), (-1, -1), 0.4, CLARO),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("LINEABOVE", (0, 0), (-1, 0), 1.2, AZUL)
    ]))

    return [Spacer(1, 3 * mm), tabla]


def bloque_firma(estilos):
    """
    La firma de quien entrega y el sello.

    Va al final y con un interlineado grande porque
    un recibo se firma a mano: sin sitio, se firma
    encima del importe.
    """

    linea = Table(
        [["", ""]],
        colWidths=[(ANCHO_UTIL - 8 * mm) / 2] * 2,
        rowHeights=[14 * mm]
    )

    linea.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, -1), 0.4, GRIS),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM")
    ]))

    rotulos = Table(
        [
            [
                texto("Firma", estilos["rotulo"]),
                texto("Sello", estilos["rotulo"])
            ]
        ],
        colWidths=[(ANCHO_UTIL - 8 * mm) / 2] * 2
    )

    rotulos.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1)
    ]))

    return [Spacer(1, 7 * mm), linea, rotulos]


def bloque_imputacion(pagos, cuotas, estilos,
                        moneda=None):
    """
    El reparto, cuando el cobro cubre varias cuotas.

    Es la parte que hace falta cuando el cliente paga
    dos meses de una vez. En el papel se ve el total
    arriba y debajo, una línea por cuota, qué parte
    del dinero va a cada una. El cajero y el cliente
    pueden confrontarlo con el cronograma, y si
    alguien dice "yo no debí esa cuota" se ve en una
    hoja.

    Y la última línea va marcada cuando queda a medias,
    que es la única forma de que el papel diga lo mismo
    que el cronograma.
    """

    ajustes = _moneda.config_de(moneda)

    total = sum(
        (Decimal(str(p["importe"])) for p in pagos),
        Decimal("0.00")
    )

    filas = [
        ["Importe cobrado", formato_dinero(total)],
        ["", ""],
        ["Cuota", "Imputado"]
    ]

    ultima = len(pagos) - 1

    for indice, pago in enumerate(pagos):

        numero = (
            str(pago["numero_cuota"])
            if pago["numero_cuota"] is not None
            else "pago a cuenta"
        )

        filas.append([
            numero,
            formato_dinero(pago["importe"])
        ])

        # ------------------------------
        # QUEDA A MEDIAS
        # ------------------------------

        if (
            indice == ultima
            and cuotas
            and len(cuotas) == len(pagos)
            and Decimal(str(cuotas[-1]["saldo"])) > 0
        ):

            filas.append([
                "",
                "queda un resto pendiente"
            ])

    cuerpo = [
        [
            texto(izq, estilos["rotulo"]),
            texto(der, estilos["valor"])
        ]
        for izq, der in filas
    ]

    tabla = Table(
        cuerpo,
        colWidths=[46 * mm, ANCHO_UTIL - 46 * mm]
    )

    tabla.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("LINEABOVE", (0, 2), (-1, 2), 0.4, CLARO),
        ("LINEBELOW", (0, -1), (-1, -1), 0.4, CLARO)
    ]))

    return [
        Spacer(1, 4 * mm),
        texto("IMPORTE COBRADO", estilos["rotulo"]),
        texto(
            formato_dinero(total, moneda=moneda),
            estilos["grande"]
        ),
        texto(
            en_letras(total, ajustes["decimales"])
            + " " + codigo_moneda(moneda),
            estilos["letras"]
        ),
        Spacer(1, 2 * mm),
        tabla
    ]


def bloque_pie(pago, estilos):
    """
    Lo que hay que decir abajo, y lo que no.

    El "no" es importante: NO se imprime el saldo
    total del contrato. Un recibo de 500.000 con un
    "saldo pendiente: 4.200.000" al lado se lee como
    una afirmación sobre la deuda entera, y el saldo
    es una foto de hoy. Este documento resuelve las
    cuotas que lista.
    """

    return [
        Spacer(1, 5 * mm),
        texto(
            "Este comprobante acredita el cobro de "
            "la suma indicada contra el contrato "
            "citado. No modifica las condiciones "
            "pactadas ni el cronograma, y no sustituye "
            "al contrato.",
            estilos["nota"]
        ),
        Spacer(1, 1.5 * mm),
        texto(
            f"Registró: "
            f"{pago['usuario_nombre'] or 'sin registro'}"
            f"  ·  Generado el "
            f"{datetime.date.today().strftime('%d/%m/%Y')}",
            estilos["nota"]
        )
    ]


# ==========================================
# LA HOJA
# ==========================================

def _pintar_hoja(lienzo, documento):
    """
    La banda y el pie, dibujados en onPage.

    Son decoración: si fueran flowables ocuparían hueco
    en el marco y se podrían partir. Se llama una vez
    por hoja.
    """

    receipt = documento.recibo

    lienzo.saveState()

    # ------------------------------
    # BANDA
    # ------------------------------

    lienzo.setFillColor(AZUL)

    lienzo.rect(
        0,
        PAGINA[1] - ALTO_BANDA,
        PAGINA[0],
        ALTO_BANDA,
        stroke=0,
        fill=1
    )

    lienzo.setFillColor(colors.white)

    lienzo.setFont("Helvetica-Bold", 11)

    lienzo.drawString(
        MARGEN,
        PAGINA[1] - 14 * mm,
        NOMBRE_SISTEMA
    )

    lienzo.setFont("Helvetica", 7.5)

    lienzo.drawRightString(
        PAGINA[0] - MARGEN,
        PAGINA[1] - 13.5 * mm,
        "Recibo de pago"
    )

    numero = receipt["recibo"] or "sin número"

    lienzo.setFont("Helvetica-Bold", 10)

    lienzo.drawRightString(
        PAGINA[0] - MARGEN,
        PAGINA[1] - 18 * mm,
        numero
    )

    # ------------------------------
    # PIE
    # ------------------------------

    lienzo.setFillColor(GRIS)

    lienzo.setFont("Helvetica", 6.5)

    lienzo.drawString(
        MARGEN,
        8 * mm,
        f"{NOMBRE_SISTEMA}  ·  "
        f"{contrato_numero(receipt)}"
    )

    lienzo.drawRightString(
        PAGINA[0] - MARGEN,
        8 * mm,
        "Documento sin valor fiscal"
    )

    lienzo.restoreState()


def contrato_numero(receipt):
    return receipt.get("numero") or ""


# ==========================================
# CONSTRUCCIÓN
# ==========================================

def ruta_documento(numero_recibo):
    """
    Dónde va el PDF de un recibo.
    """

    seguro = "".join(
        c for c in str(numero_recibo or "sinnumero")
        if c.isalnum() or c in ("-", "_")
    )

    return os.path.join(
        CARPETA, f"recibo_{seguro or 'sinnumero'}.pdf"
    )


def ruta_relativa(numero_recibo):
    """
    La misma, guardada en la base: relativa al
    proyecto, para que no se rompa al mover la
    carpeta.
    """

    return os.path.join(
        "documentos", "recibos",
        os.path.basename(ruta_documento(numero_recibo))
    )


def generar_recibo(pagos, contrato, cuotas=None):
    """
    Crea el PDF de un cobro.

    pagos: una LISTA de filas de obtener_pagos_detalle()
    contrato: una fila de obtener_contrato()
    cuotas: las filas de obtener_cuota() a las que se
             imputaron, EN EL MISMO ORDEN. None si el
             cobro no va a ninguna cuota.

    ------------------------------
    # POR QUÉ UNA LISTA Y NO UN PAGO
    # ------------------------------

    Porque un cobro adelantado son N pagos con el MISMO
    número de recibo, y el cliente se lleva UN papel.

    Con un solo `pago` por parámetro habría que
    imprimir N recibos de un solo acto, o peor, elegir
    uno y dejar los demás sin papel: el cliente pagó
    30.000 y le dicen que su recibo es de 10.000. La
    lista convierte eso en un recibo con una tabla de
    imputación, que es lo que ocurrió.

    Un cobro de una cuota es una lista de uno, y sale
    exactamente igual que antes.

    ------------------------------
    # LA MONEDA
    # ------------------------------

    La del CONTRATO, no la que haya configurada ahora:
    el papel de un cobro tiene que decir la misma
    moneda que el cobro. Se saca de `contrato[
    "moneda"]`, que es donde está escrito.

    El recibo se guarda como
    documentos/recibos/recibo_<n>.pdf, con el número
    de recibo, y devuelve la ruta.

    No hay `ruta` a propósito, al revés que en otros
    sitios: el nombre del archivo lo decide el número
    de recibo, que es único, y pedirle a quien llama
    que invente una ruta solo abriría la puerta a
    sobrescribir el recibo de otro cobro.
    """

    if not pagos:

        raise ValueError(
            "No hay datos de pago para generar el "
            "recibo."
        )

    if isinstance(pagos, dict):

        # Se acepta uno suelto por comodidad: un cobro
        # de una cuota es el caso normal y no tiene por
        # que obligar a envolverlo en una lista. Se
        # normaliza aqui y no en el cuerpo, para que
        # abajo no haya que mirar de dos maneras.

        pagos = [pagos]

    if isinstance(cuotas, dict):

        # Lo mismo, y por el mismo motivo.

        cuotas = [cuotas]

    if not contrato:

        raise ValueError(
            "No hay datos de contrato para generar "
            "el recibo."
        )

    primero = pagos[0]

    # ------------------------------
    # LA MONEDA DEL CONTRATO
    # ------------------------------
    # Un recibo de un cobro en dólares sale en dólares
    # aunque hoy la aplicación esté en guaraníes. El
    # papel que el cliente se lleva dice lo mismo que
    # el cobro, y no lo que se haya configurado después.

    # Se lee del contrato y no del pago: el pago no
    # tiene columna de moneda, y el contrato sí, y es
    # donde está escrito.

    moneda = contrato.get("moneda")

    estilos = construir_estilos()

    destino = ruta_documento(primero["recibo"])

    carpeta = os.path.dirname(destino)

    if carpeta and not os.path.exists(carpeta):

        os.makedirs(carpeta, exist_ok=True)

    marco = Frame(
        MARGEN,
        MARGEN,
        ANCHO_UTIL,
        PAGINA[1] - MARGEN - MARGEN_SUPERIOR,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        id="recibo"
    )

    documento = BaseDocTemplate(
        destino,
        pagesize=PAGINA,
        leftMargin=MARGEN,
        rightMargin=MARGEN,
        topMargin=MARGEN_SUPERIOR,
        bottomMargin=MARGEN,
        title=(
            f"Recibo {primero['recibo'] or ''} "
            f"{contrato['cliente']}"
        ).strip(),
        author=NOMBRE_SISTEMA
    )

    documento.addPageTemplates([
        PageTemplate(
            id="recibo",
            frames=[marco],
            onPage=_pintar_hoja
        )
    ])

    # ------------------------------
    # LO QUE SE LLEVA DENTRO
    # ------------------------------
    # reportlab no le pasa los datos a la función de
    # página, así que se cuelgan en el documento: sin
    # esto, _pintar_hoja no sabría qué recibo está
    # imprimiendo.

    documento.recibo = dict(primero)
    documento.recibo["numero"] = contrato["numero"]

    historia = [
        texto("RECIBO DE PAGO", estilos["recibo"]),
        Spacer(1, 4 * mm),
        bloque_cabecera(
            primero, contrato, estilos,
            moneda=moneda
        )
    ]

    if len(pagos) > 1:

        # ------------------------------
        # VARIAS CUOTAS: HAY QUE
        # DECIR CUÁLES
        # ------------------------------
        # El cliente necesita ver el reparto en el
        # papel, no solo el total. Es la diferencia
        # entre "cobré 30.000" y "cobré 30.000, de los
        # cuales 10.000 son de marzo".

        historia += bloque_imputacion(
            pagos, cuotas, estilos,
            moneda=moneda
        )

    else:

        historia += bloque_importe(
            primero, estilos, moneda=moneda
        )

        if cuotas:

            historia += bloque_cuota(
                primero, cuotas[0], estilos,
                moneda=moneda
            )

    historia += bloque_firma(estilos)

    historia += bloque_pie(primero, estilos)

    # ------------------------------
    # NUNCA PARTIDO
    # ------------------------------
    # El bloque de la cuota y el de la firma no se
    # parten entre dos páginas. Un recibo con la
    # cantidad en una hoja y la firma en otra no
    # sirve para nada.

    documento.build(historia)

    return destino


def _fecha(valor):
    """
    Fecha en español.
    """

    if valor is None:

        return "—"

    if isinstance(valor, (datetime.date, datetime.datetime)):

        return valor.strftime("%d/%m/%Y")

    return str(valor)


def _estado(estado):
    return ESTADOS_CUOTA.get(estado, estado or "—")
