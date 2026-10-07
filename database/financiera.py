# ==========================================
# FINANCIERA: CRONOGRAMAS Y CUOTAS
# ==========================================
# Lo que hace este módulo:
#
#   1. Calcular el cronograma de una venta
#      financiada: cuántas cuotas, de qué importe y
#      con qué fecha de vencimiento cada una.
#
#   2. Guardarlo en la tabla cuotas, una fila por
#      vencimiento.
#
#   3. Registrar pagos contra una cuota, manteniendo
#      su saldo y su estado al día SIEMPRE en la
#      misma transacción que inserta el pago.
#
#   4. Detectar vencidas por la fecha, sin que nadie
#      tenga que acordarse de hacerlo.
#
#
# ----------------------------------------------------
# POR QUÉ "saldo" ES UNA COLUMNA Y NO UN SUM()
# ----------------------------------------------------
# Podría calcularse con
#
#     SELECT importe - COALESCE(SUM(importe), 0)
#
# sobre los pagos. Se optó por guardarlo, y la razón
# es que el estado de una cuota y su saldo tienen que
# cambiar SIEMPRE juntos:
#
#   - Si el saldo se calculara al vuelo, el estado
#     guardado ("pagada", "parcial") podría no
#     coincidir con lo que dicen los pagos, y habría
#     dos verdades.
#
#   - Al guardarlo, registrar_pago_cuota() es el
#     ÚNICO sitio que lo escribe, y lo hace dentro de
#     la misma transacción que el INSERT del pago.
#     O se guardan los dos, o no se guarda ninguno.
#
# El precio de esa decisión es que hay que
# recalcular_saldo_cuota() para auditar que nada se
# ha descolocado. existe precisely por eso, y
# tests/test_financiera.py lo comprueba.
#
#
# ----------------------------------------------------
# VENCIDA ES UN ESTADO DERIVADO
# ----------------------------------------------------
# Una cuota que pasó su fecha de vencimiento y sigue
# con saldo está vencida. No es una decisión de
# alguien: se deduce de la fecha. Por eso
# procesar_vencidas() existe, y por eso se puede
# llamar cada vez que se abre la cartera.
#
# Al revés, una cuota vencida a la que se le cobra
# vuelve a estar al día y deja de estar vencida:
# dejar "vencida" una cuota ya cobrada sería
# mentirse a uno mismo en la propia cartera.
#
#
# ----------------------------------------------------
# LO QUE ESTE MÓDULO NO HACE
# ----------------------------------------------------
# No calcula intereses moratorios. La tasa y su tope
# dependen de la normativa vigente y de lo que
# establezca el contrato, así que el ajuste existe en
# la configuración pero el cálculo NO está hecho: que
# haya un porcentaje guardado no significa que sea el
# que corresponde. Eso lo tiene que revisar un
# asesor.
#
# Tampoco genera ni homologa convenios de pago, ni
# inscribe gravámenes. Registro lo que el
# concesionario afirma; no certifica nada ante el
# Registro Público.


import calendar

from datetime import date
from datetime import timedelta
from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_HALF_UP
)

import mysql.connector

from database.auditoria import (
    registrar_accion,
    registrar_cambio
)

from database.configuracion import obtener_configuracion

from database.conexion import (
    conexiones_libres,
    obtener_conexion
)

from errores import (
    ErrorBaseDatos,
    ErrorValidacion
)

from utils.moneda import formato_dinero

import sesion as modulo_sesion

from permisos import (
    requiere_permiso,
    VER_CONTRATOS,
    CREAR_CONTRATOS,
    GESTIONAR_CONTRATOS,
    GESTIONAR_FINANCIERA
)

from database.pagos import registrar_pago


# ==========================================
# CONSTANTES
# ==========================================

# Dos decimales: es lo que guardan las columnas
# DECIMAL(10,2). Ver _a_importe().

DECIMALES = Decimal("0.01")

CERO = Decimal("0.00")


# ==========================================
# ESTADOS DE CUOTA
# ==========================================
# Código estable, texto en pantalla desde aquí.

ESTADOS = {
    "pendiente": "Pendiente",
    "pagada": "Pagada",
    "parcial": "Parcial",
    "vencida": "Vencida",
    "anulada": "Anulada"
}

ESTADO_PENDIENTE = "pendiente"
ESTADO_PAGADA = "pagada"
ESTADO_PARCIAL = "parcial"
ESTADO_VENCIDA = "vencida"
ESTADO_ANULADA = "anulada"

# Estado inicial de toda cuota recién generada.
# VENCIDA y ANULADA no se generan: vencida la decide
# la fecha, y anulada es una decisión posterior sobre
# una cuota concreta.

ESTADOS_GENERABLES = [
    ESTADO_PENDIENTE,
    ESTADO_PAGADA,
    ESTADO_PARCIAL
]

# Estado al que pasa una cuota con saldo al pasar su
# fecha. El orden importa: se evalúa de arriba abajo
# y gana el primero que cumple.

ORDEN_VENCIMIENTO = [
    ESTADO_ANULADA,
    ESTADO_PAGADA,
    ESTADO_VENCIDA,
    ESTADO_PARCIAL
]


# ==========================================
# PERIODICIDADES
# ==========================================
# Dos formas de avanzar una fecha, y no son
# intercambiables:
#
#   - EN DÍAS, para los plazos fijos: semanal y
#     quincenal. Siete y quince días son siete y
#     quince días, sin discusión.
#
#   - EN MESES DE CALENDARIO, para mensual y
#     superiores. Un crédito mensual tiene que caer
#     el mismo día del mes que el primero, no 30 días
#     después. Sumando 30 días, un crédito que empieza
#     el 1 de noviembre vencería el 1 de diciembre, el
#     31 de diciembre, el 30 de enero, el 1 de marzo... y
#     al undécimo mes el cliente está pagando ONCE DÍAS
#     ANTES de lo pactado, y el siguiente, un mes y un
#     día tarde.
#
#     Con meses de calendario, el día 31 es un caso
#     aparte: de enero a marzo hay 28 o 29 días, así
#     que hay que añadir meses conservando el día y
#     limitando al último del mes destino. Un crédito
#     que vence todos los 31 cae el 28 de febrero y
#     vuelve al 31 de marzo, en lugar de perderse.

PERIODICIDADES = {
    "semanal": 7,
    "quincenal": 15
}

PERIODICIDADES_MENSUALES = {
    "mensual": 1,
    "bimestral": 2,
    "trimestral": 3,
    "semestral": 6,
    "anual": 12
}

PERIODICIDAD_POR_DEFECTO = "mensual"

TODAS_LAS_PERIODICIDADES = (
    list(PERIODICIDADES) + list(PERIODICIDADES_MENSUALES)
)


# ==========================================
# AJUSTES
# ==========================================
# Claves en la tabla configuracion. Los valores por
# defecto están en el propio esquema.sql y en
# migracion_financiera.sql.

CLAVE_DIAS_AVISO = "financiera_dias_aviso"
CLAVE_DIAS_GRACIA = "financiera_dias_gracia"
CLAVE_MAXIMO_CUOTAS = "financiera_maximo_cuotas"
CLAVE_MORA_TIPO = "financiera_interes_mora_tipo"
CLAVE_MORA_PORCENTAJE = "financiera_interes_mora_porcentaje"
CLAVE_RETENCION = "financiera_retencion_porcentaje"
CLAVE_ESCRIBANO = "financiera_exigir_escribano"

DIAS_AVISO_POR_DEFECTO = 15
DIAS_GRACIA_POR_DEFECTO = 0
MAXIMO_CUOTAS_POR_DEFECTO = 72


def leer_ajustes():
    """
    Los ajustes de la financiación, ya convertidos a
    su tipo.

    Un ajuste con basura no rompe nada: cae al valor
    por defecto de ese ajuste. Formatear un importe
    o leer un umbral nunca debe ser el motivo de que
    una pantalla no se abra.
    """

    valores = {
        "dias_aviso": DIAS_AVISO_POR_DEFECTO,
        "dias_gracia": DIAS_GRACIA_POR_DEFECTO,
        "maximo_cuotas": MAXIMO_CUOTAS_POR_DEFECTO,
        "mora_tipo": "ninguno",
        "mora_porcentaje": Decimal("0.000"),
        "retencion_porcentaje": Decimal("0.000"),
        "exigir_escribano": False
    }

    try:

        guardados = obtener_configuracion()

    except mysql.connector.Error:

        return valores

    entero = lambda clave, defecto: _a_entero(
        guardados.get(clave),
        defecto
    )

    valores["dias_aviso"] = entero(
        CLAVE_DIAS_AVISO,
        DIAS_AVISO_POR_DEFECTO
    )

    valores["dias_gracia"] = entero(
        CLAVE_DIAS_GRACIA,
        DIAS_GRACIA_POR_DEFECTO
    )

    valores["maximo_cuotas"] = entero(
        CLAVE_MAXIMO_CUOTAS,
        MAXIMO_CUOTAS_POR_DEFECTO
    )

    valores["mora_tipo"] = (
        guardados.get(CLAVE_MORA_TIPO) or "ninguno"
    )

    valores["mora_porcentaje"] = _a_decimal(
        guardados.get(CLAVE_MORA_PORCENTAJE),
        Decimal("0.000")
    )

    valores["retencion_porcentaje"] = _a_decimal(
        guardados.get(CLAVE_RETENCION),
        Decimal("0.000")
    )

    valores["exigir_escribano"] = (
        (guardados.get(CLAVE_ESCRIBANO) or "").strip()
        in ("1", "true", "si", "sí")
    )

    return valores


def _a_entero(valor, defecto):

    try:

        return int(str(valor).strip())

    except (TypeError, ValueError):

        return defecto


def _a_decimal(valor, defecto):

    try:

        return Decimal(str(valor).strip())

    except (InvalidOperation, TypeError, ValueError):

        return defecto


# ==========================================
# CONVERSIONES
# ==========================================
# Todo el dinero pasa por aquí y sale siempre como
# Decimal con dos decimales.
#
# Decimal y no float por el motivo de siempre:
# precio y pagado son DECIMAL(10,2) en la base, así
# que el saldo es múltiplo de un céntimo y se puede
# comparar con exactitud. Con float, 0.1 + 0.2 no es
# 0.3, y una comparación con tolerancia deja pasar
# pagos que la base guarda redondeados.

def _a_importe(valor):
    """
    Devuelve (Decimal con 2 decimales, "") o
    (None, motivo).
    """

    if valor is None:

        return (None, "Falta el importe.")

    try:

        numero = Decimal(str(valor).strip())

    except (InvalidOperation, TypeError, ValueError):

        return (None, "El importe no es un número.")

    if not numero.is_finite():

        return (None, "El importe no es un número.")

    if numero != numero.quantize(DECIMALES):

        # Más de dos decimales. Redondear en silencio
        # haría que el importe cobrado no fuera el
        # que se escribió, y la diferencia no aparecería
        # en ningún sitio.

        return (
            None,
            "El importe no puede tener más de dos "
            "decimales."
        )

    return (numero.quantize(DECIMALES), "")


# ==========================================
# CÁLCULO DEL CRONOGRAMA
# ==========================================
# Es una función PURA: no toca la base. Devuelve la
# lista de (numero, fecha, importe) para que el
# formulario pueda enseñarla ANTES de guardar, y para
# que las pruebas puedan comprobarla sin base de
# datos.
#
# El reparto del saldo entre las cuotas es lo más
# delicado. Ver _repartir().

def calcular_cronograma(
    cantidad,
    periodicidad,
    primer_vencimiento,
    saldo,
    fecha_financiacion=None
):
    """
    El cronograma de una venta financiada.

    Devuelve una lista de diccionarios con numero,
    fecha_vencimiento e importe.

    Lanza ErrorValidacion si los datos no sirven.
    """

    if periodicidad not in TODAS_LAS_PERIODICIDADES:

        raise ErrorValidacion(
            f"Periodicidad '{periodicidad}' no válida."
        )

    try:

        total_cuotas = int(cantidad)

    except (TypeError, ValueError):

        raise ErrorValidacion(
            "La cantidad de cuotas tiene que ser "
            "un número."
        )

    if total_cuotas < 1:

        raise ErrorValidacion(
            "Un contrato financiado necesita al menos "
            "una cuota."
        )

    ajustes = leer_ajustes()

    if total_cuotas > ajustes["maximo_cuotas"]:

        raise ErrorValidacion(
            f"Un contrato no puede tener más de "
            f"{ajustes['maximo_cuotas']} cuotas."
        )

    importe_total, motivo = _a_importe(saldo)

    if importe_total is None:

        raise ErrorValidacion(motivo)

    if importe_total < CERO:

        raise ErrorValidacion(
            "El saldo a financiar no puede ser "
            "negativo."
        )

    if importe_total == CERO:

        raise ErrorValidacion(
            "No hay saldo que financiar: si la entrega "
            "inicial es igual al precio, la venta es a "
            "contado."
        )

    if not primer_vencimiento:

        raise ErrorValidacion(
            "Falta la fecha del primer vencimiento."
        )

    if isinstance(primer_vencimiento, str):

        try:

            primer_vencimiento = date.fromisoformat(
                primer_vencimiento
            )

        except ValueError:

            raise ErrorValidacion(
                "La fecha del primer vencimiento no es "
                "una fecha válida."
            )

    fechas = _fechas_vencimiento(
        total_cuotas,
        periodicidad,
        primer_vencimiento
    )

    importes = _repartir(importe_total, total_cuotas)

    cronograma = []

    for indice in range(total_cuotas):

        cronograma.append({
            "numero": indice + 1,
            "fecha_vencimiento": fechas[indice],
            "importe": importes[indice]
        })

    return cronograma


def _fechas_vencimiento(cantidad, periodicidad, primera):
    """
    Las fechas de vencimiento.

    El primer vencimiento es el que dijo el usuario, no
    la fecha de financiación más un periodo: puede
    pactarse que la primera cuota se paga al mes de la
    entrega, y eso es legítimo.

    Los siguientes avanzan según la periodicidad: por
    días si es semanal o quincenal, y por meses de
    calendario si es mensual o mayor. Ver la nota de
    PERIODICIDADES para por qué no es lo mismo.
    """

    if periodicidad in PERIODICIDADES:

        paso = PERIODICIDADES[periodicidad]

        fechas = [primera]

        for _ in range(cantidad - 1):

            fechas.append(
                fechas[-1] + timedelta(days=paso)
            )

        return fechas

    meses = PERIODICIDADES_MENSUALES[periodicidad]

    # El día de referencia es el del PRIMER vencimiento,
    # y se lleva a todos los meses. No se recalcula cada
    # vez desde la fecha anterior, porque eso produce una
    # deriva silenciosa: un crédito que empieza el 31
    # caería el 28 de febrero y SE QUEDARÍA en el 28 para
    # siempre (28/03, 28/04, 28/05...), con el cliente
    # pagando una semana antes de lo pactado a partir de
    # marzo y sin que nadie se dé cuenta.

    dia_referencia = primera.day

    fechas = [primera]

    for _ in range(cantidad - 1):

        fechas.append(
            _sumar_meses(
                fechas[-1], meses, dia_referencia
            )
        )

    return fechas


def _sumar_meses(fecha, meses, dia_referencia):
    """
    Fecha + N meses de calendario, con el día de
    referencia recortado al último del mes destino.

    Del 15 de enero + 1 mes es 15 de febrero.

    Del 31 de enero + 1 mes es 28 de febrero, porque el
    31 no existe ahí. Y el mes siguiente vuelve a ser 31
    de marzo, porque el día de referencia sigue siendo
    31: el recorte es solo del mes que no tiene 31, no
    una decisión que se arrastra.

    Con años bisiestos no hace falta caso especial:
    monthrange da 29 en febrero de 2028 y 28 en el de
    2027.
    """

    # Mes de destino, teniendo en cuenta el año.

    total_meses = (fecha.year * 12 + fecha.month - 1) + meses

    anio = total_meses // 12

    mes = total_meses % 12 + 1

    ultimo = calendar.monthrange(anio, mes)[1]

    return date(anio, mes, min(dia_referencia, ultimo))


def _repartir(total, cantidad):
    """
    Reparte el total entre las cuotas.

    Aquí está el detalle que más importa: la última
    cuota absorbe el residuo.

    Repartir 10.000 en 3 da 3.333,33 + 3.333,33 +
    3.333,34. Las dos primeras son el resultado de
    dividir, y la última se ajusta para que la suma
    cuadre EXACTAMENTE con el total.

    La alternativa de redondear cada una a dos
    decimales perdería o inventaría céntimos, y un
    contrato firmado con un céntimo de diferencia es
    un contrato que no cuadra cuando el cliente llega
    con la calculadora.
    """

    base = (total / cantidad).quantize(
        DECIMALES,
        rounding=ROUND_HALF_UP
    )

    importes = [base] * cantidad

    # El residuo va a la última. No se reparte entre
    # todas: repartirlo entre varias cambiaría el
    # importe que el cliente vio pactado en cada una.

    diferencia = total - (base * cantidad)

    importes[-1] = (importes[-1] + diferencia).quantize(
        DECIMALES,
        rounding=ROUND_HALF_UP
    )

    return importes


# ==========================================
# GENERAR EL CRONOGRAMA
# ==========================================

@conexiones_libres
@requiere_permiso(CREAR_CONTRATOS)
def generar_cronograma(id_contrato):
    """
    Crea las cuotas de un contrato.

    Devuelve (numero_de_cuotas, "") o
    (0, motivo).

    NO se puede hacer si el contrato ya tiene cuotas.
    Un cronograma es un documento pactado: cambiarlo
    después de que haya dinero cobrado dejaría el saldo
    descuadrado de lo que el cliente pagó. Para
    rehacerlo hay que anular antes los pagos.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:

        conexion.start_transaction()

        cursor.execute(
            """
            SELECT
                id, numero, saldo_financiado,
                cantidad_cuotas, periodicidad,
                primer_vencimiento, estado
            FROM contratos
            WHERE id = %s
            FOR UPDATE
            """,
            (id_contrato,)
        )

        contrato = cursor.fetchone()

        if not contrato:

            conexion.rollback()

            return (0, "El contrato no existe.")

        if contrato["estado"] == "cancelado":

            conexion.rollback()

            return (
                0,
                "El contrato está cancelado: no tiene "
                "sentido darle un cronograma."
            )

        # ------------------------------
        # 1. NO SOBRA UN CRONOGRAMA
        # ------------------------------

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM cuotas
            WHERE contrato_id = %s
            """,
            (id_contrato,)
        )

        if cursor.fetchone()["total"] > 0:

            conexion.rollback()

            return (
                0,
                "El contrato ya tiene un cronograma. "
                "Para cambiarlo hay que anular antes "
                "los pagos."
            )

        # ------------------------------
        # 2. LO QUE HAY QUE FINANCIAR
        # ------------------------------

        saldo = Decimal(
            str(contrato["saldo_financiado"])
        )

        if saldo <= CERO:

            conexion.rollback()

            return (
                0,
                "No hay saldo financiado: la entrega "
                "inicial cubre el precio."
            )

        # ------------------------------
        # 3. EL CRONOGRAMA
        # ------------------------------

        try:

            cronograma = calcular_cronograma(
                contrato["cantidad_cuotas"],
                contrato["periodicidad"],
                contrato["primer_vencimiento"],
                saldo
            )

        except ErrorValidacion as error:

            conexion.rollback()

            return (0, error.mensaje)

        # ------------------------------
        # 4. INSERTAR
        # ------------------------------

        for cuota in cronograma:

            cursor.execute(
                """
                INSERT INTO cuotas
                (
                    contrato_id, numero,
                    fecha_vencimiento, importe,
                    saldo, estado
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    id_contrato,
                    cuota["numero"],
                    cuota["fecha_vencimiento"],
                    cuota["importe"],
                    cuota["importe"],
                    ESTADO_PENDIENTE
                )
            )

        # El monto de la cuota queda congelado en el
        # contrato: es lo que dice el PDF que se
        # firmó.

        monto = cronograma[0]["importe"]

        cursor.execute(
            """
            UPDATE contratos
            SET monto_cuota = %s
            WHERE id = %s
            """,
            (monto, id_contrato)
        )

        conexion.commit()

    except ErrorValidacion as error:

        conexion.rollback()

        return (0, error.mensaje)

    except mysql.connector.Error as error:

        conexion.rollback()

        cursor.close()
        conexion.close()

        raise ErrorBaseDatos(str(error)) from error

    total = len(cronograma)

    numero = contrato["numero"]

    cursor.close()

    conexion.close()

    # Después del commit: si la transacción se
    # revirtiese, el rastro mentiría.

    registrar_accion(
        "financiera",
        "CRONOGRAMA",
        f"Cronograma de {total} cuotas generado para "
        f"el contrato {numero}, cuota de "
        f"{formato_dinero(monto)}"
    )

    return (total, "")


# ==========================================
# CONSULTAS
# ==========================================

@requiere_permiso(VER_CONTRATOS)
def obtener_cuotas(id_contrato):
    """
    Las cuotas de un contrato, en orden de número.

    Contrato de columnas: id, numero,
    fecha_vencimiento, importe, saldo, estado,
    cantidad_pagos, dias_atraso.

    "dias_atraso" sale calculado con la fecha de
    hoy: es lo que hace falta para pintar la columna
    sin tener que hacerlo en la vista.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            id,
            numero,
            fecha_vencimiento,
            importe,
            saldo,
            estado,
            cantidad_pagos
        FROM cuotas
        WHERE contrato_id = %s
        ORDER BY numero
        """,
        (id_contrato,)
    )

    cuotas = cursor.fetchall()

    cursor.close()
    conexion.close()

    hoy = date.today()

    for cuota in cuotas:

        cuota["dias_atraso"] = max(
            0,
            (hoy - cuota["fecha_vencimiento"]).days
        )

    return cuotas


@requiere_permiso(VER_CONTRATOS)
def obtener_cuota(id_cuota):
    """
    Una cuota con su contrato resuelto.

    Devuelve None si no existe.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            cuotas.id,
            cuotas.numero,
            cuotas.fecha_vencimiento,
            cuotas.importe,
            cuotas.saldo,
            cuotas.estado,
            cuotas.cantidad_pagos,
            cuotas.contrato_id,
            contratos.numero AS contrato_numero,
            contratos.venta_id,
            contratos.estado AS contrato_estado,
            contratos.precio_venta,
            contratos.saldo_financiado,
            contratos.moneda,
            clientes.nombre AS cliente_nombre,
            clientes.apellido AS cliente_apellido,
            clientes.documento AS cliente_documento,
            marcas.nombre AS marca,
            autos.modelo AS modelo,
            autos.anio,
            autos.color
        FROM cuotas
        INNER JOIN contratos
            ON cuotas.contrato_id = contratos.id
        INNER JOIN clientes
            ON contratos.cliente_id = clientes.id
        INNER JOIN autos
            ON contratos.auto_id = autos.id
        INNER JOIN marcas
            ON autos.marca_id = marcas.id
        WHERE cuotas.id = %s
        """,
        (id_cuota,)
    )

    cuota = cursor.fetchone()

    cursor.close()
    conexion.close()

    if not cuota:

        return None

    hoy = date.today()

    cuota["dias_atraso"] = max(
        0,
        (hoy - cuota["fecha_vencimiento"]).days
    )

    return cuota


@requiere_permiso(VER_CONTRATOS)
def resumen_de_cuotas(id_contrato):
    """
    Los totales de un cronograma, para la cabecera.

    Devuelve un diccionario con total_cuotas,
    pendientes, pagadas, parciales, vencidas,
    anuladas, saldo_total y pagado_total.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    ajustes = leer_ajustes()

    hoy = date.today()

    # El corte de "próxima a vencer" y de "vencida"
    # se hace con las fechas, no con el estado: si se
    # usara el estado, una cuota pendiente cuya fecha
    # ya pasó contaría como "próxima a vencer", que es
    # justo lo que no es.

    limite_aviso = hoy + timedelta(
        days=ajustes["dias_aviso"]
    )

    limite_vencida = hoy - timedelta(
        days=ajustes["dias_gracia"]
    )

    cursor.execute(
        """
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(importe), 0) AS importe_total,
            COALESCE(SUM(saldo), 0) AS saldo_total,
            SUM(estado = 'pagada') AS pagadas,
            SUM(estado = 'parcial') AS parciales,
            SUM(estado = 'anulada') AS anuladas,
            SUM(
                estado <> 'anulada'
                AND saldo > 0
                AND fecha_vencimiento < %s
            ) AS vencidas,
            COALESCE(SUM(
                CASE
                    WHEN estado <> 'anulada'
                     AND saldo > 0
                     AND fecha_vencimiento < %s
                    THEN saldo
                END
            ), 0) AS importe_vencido,
            SUM(
                estado <> 'anulada'
                AND saldo > 0
                AND fecha_vencimiento BETWEEN %s AND %s
            ) AS por_vencer,
            MIN(
                CASE
                    WHEN estado <> 'anulada'
                     AND saldo > 0
                    THEN fecha_vencimiento
                END
            ) AS proximo_vencimiento
        FROM cuotas
        WHERE contrato_id = %s
        """,
        (
            limite_vencida,
            limite_vencida,
            hoy,
            limite_aviso,
            id_contrato
        )
    )

    fila = cursor.fetchone()

    cursor.close()
    conexion.close()

    if not fila or not fila["total"]:

        return {
            "total_cuotas": 0,
            "pendientes": 0,
            "pagadas": 0,
            "parciales": 0,
            "vencidas": 0,
            "anuladas": 0,
            "por_vencer": 0,
            "importe_total": CERO,
            "saldo_total": CERO,
            "pagado_total": CERO,
            "importe_vencido": CERO,
            "proximo_vencimiento": None
        }

    pendientes = (
        fila["total"]
        - fila["pagadas"]
        - fila["parciales"]
        - fila["anuladas"]
    )

    importe_total = Decimal(str(fila["importe_total"]))
    saldo_total = Decimal(str(fila["saldo_total"]))

    return {
        "total_cuotas": fila["total"],
        "pendientes": pendientes,
        "pagadas": fila["pagadas"] or 0,
        "parciales": fila["parciales"] or 0,
        "vencidas": fila["vencidas"] or 0,
        "anuladas": fila["anuladas"] or 0,
        "por_vencer": fila["por_vencer"] or 0,
        "importe_total": importe_total,
        "saldo_total": saldo_total,
        # Pagado = importe menos lo que queda. Se
        # calcula aquí y no como SUM de los pagos para
        # que las cuotas anuladas no cuenten como
        # cobradas.
        "pagado_total": importe_total - saldo_total,
        "importe_vencido": Decimal(
            str(fila["importe_vencido"])
        ),
        "proximo_vencimiento": fila["proximo_vencimiento"]
    }


# ==========================================
# REGISTRAR UN PAGO CONTRA UNA CUOTA
# ==========================================
# El pago va a la tabla pagos (que es la de la venta)
# con cuota_id apuntando a esta cuota. Ver pagos.py
# para por qué no hay tabla aparte.
#
# ------------------------------
# POR QUÉ GESTIONAR_FINANCIERA Y NO
# REGISTRAR_VENTAS
# ------------------------------
# Cobrar una cuota es ENTRAR dinero por la puerta de
# atrás de una venta. Registrar una venta lo puede
# hacer el vendedor porque es su trabajo; quedarse con
# el cobro de las cuotas de un crédito es de la
# administración, que es quien responde de que ese
# dinero arrivedó.
#
# Antes llevaba VER_CONTRATOS, que el vendedor
# tiene: bastaba con llamar a registrar_pago_cuota()
# desde un script para cobrarle a un cliente sin
# haber pasado por ninguna caja. Ocultar el botón no
# protege nada.

@conexiones_libres
@requiere_permiso(GESTIONAR_FINANCIERA)
def registrar_pago_cuota(
    id_cuota,
    importe,
    fecha,
    forma,
    recibo=None,
    referencia=None,
    concepto=None
):
    """
    Cobra una cuota, total o parcialmente.

    Devuelve (id_pago, "") o (None, motivo).

    Va DENTRO de registrar_pago() a propósito:
    registrar_pago() valida el saldo de la venta, y
    el saldo de la cuota es otra comprobación que no
    puede hacer. Encadenarlas sería tener que
    duplicar aquí toda la lógica de la venta.
    """

    # ------------------------------
    # 1. ¿QUÉ CUOTA ES?
    # ------------------------------

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                cuotas.id,
                cuotas.saldo,
                cuotas.estado,
                cuotas.contrato_id,
                cuotas.numero,
                cuotas.fecha_vencimiento,
                contratos.estado AS contrato_estado,
                contratos.venta_id
            FROM cuotas
            INNER JOIN contratos
                ON cuotas.contrato_id = contratos.id
            WHERE cuotas.id = %s
            FOR UPDATE
            """,
            (id_cuota,)
        )

        cuota = cursor.fetchone()

    finally:

        cursor.close()
        conexion.close()

    if not cuota:

        return (None, "La cuota indicada no existe.")

    if cuota["estado"] == "anulada":

        return (
            None,
            "La cuota está anulada: no admite pagos."
        )

    if cuota["contrato_estado"] == "cancelado":

        return (
            None,
            "El contrato está cancelado: no admite "
            "pagos."
        )

    # ------------------------------
    # 2. NO PASAR DEL SALDO DE LA CUOTA
    # ------------------------------
    # Es una comprobación DISTINTA de la del saldo
    # de la venta, y ninguna de las dos sustituye a
    # la otra. Cobrar 500.000 de una cuota de
    # 200.000 deja el saldo de la venta correcto y el
    # de la cuota en negativo: un -200.000 que nadie
    # sabe qué significa.

    importe, motivo = _a_importe(importe)

    if importe is None:

        return (None, motivo)

    if importe <= CERO:

        return (
            None,
            "El importe tiene que ser mayor que cero."
        )

    saldo_cuota = Decimal(str(cuota["saldo"]))

    if importe > saldo_cuota:

        return (
            None,
            f"El importe es mayor que el saldo de la "
            f"cuota ({formato_dinero(float(saldo_cuota))})."
        )

    # ------------------------------
    # 3. EL PAGO
    # ------------------------------
    # Concepto por defecto: dejar claro a qué cuota
    # se imputó. Sin esto, un listado de pagos de la
    # venta no dice qué parte de la deuda se cubrió.

    if concepto is None:

        concepto = f"Cuota {cuota['numero']}"

    id_pago, motivo = registrar_pago(
        venta_id=cuota["venta_id"],
        importe=importe,
        fecha=fecha,
        forma=forma,
        referencia=referencia,
        concepto=concepto
    )

    if id_pago is None:

        return (None, motivo)

    # ------------------------------
    # 4. IMPUTARLO A LA CUOTA
    # ------------------------------
    # registrar_pago() ya confirmed su propia
    # transacción. Ésta es otra, para el UPDATE del
    # saldo. Si aquí fallara, el pago ya está
    # escrito: por eso el paso 5 se ocupa de que el
    # pago no quede huérfano.

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:

        conexion.start_transaction()

        # Se vuelve a leer la cuota con FOR UPDATE: lo
        # que se leyó antes ya puede estar viejo, si
        # alguien cobró entre medias.

        cursor.execute(
            """
            SELECT saldo, estado, cantidad_pagos
            FROM cuotas
            WHERE id = %s
            FOR UPDATE
            """,
            (id_cuota,)
        )

        actual = cursor.fetchone()

        saldo_actual = Decimal(str(actual["saldo"]))

        if importe > saldo_actual:

            # Otro cobro entró mientras tanto. La
            # transacción de registrar_pago() ya pasó
            # y este pago está escrito: hay que
            # deshacerlo aquí, no dejar un saldo
            # negativo que nadie sabe explicar.

            conexion.rollback()

            cursor.close()
            conexion.close()

            anular_pago_interno(
                id_pago,
                "Imputado a una cuota que ya estaba "
                "cancelada por otro cobro."
            )

            return (
                None,
                "La cuota se pagó mientras se "
                "registraba este pago. Revise la "
                "cuota e inténtelo otra vez."
            )

        saldo_nuevo = (saldo_actual - importe).quantize(
            DECIMALES,
            rounding=ROUND_HALF_UP
        )

        # ------------------------------
        # 5. EL ESTADO
        # ------------------------------
        # Lo decide el saldo, no la fecha: una cuota
        # con saldo a cero está pagada, esté vencida o
        # no. Y una cuota con saldo que ya pasó su
        # fecha está vencida aunque nunca se haya
        # marcado: por eso se llama a _estado_real().

        nuevo_estado = _estado_real(
            saldo_nuevo,
            actual["estado"],
            fecha,
            tiene_pagos=True
        )

        # ------------------------------
        # 6. GUARDAR
        # ------------------------------

        # ------------------------------
        # EL NÚMERO DE RECIBO
        # ------------------------------
        # Se arma AQUÍ, con el id del pago que ya
        # existe, y no antes de insertarlo con
        # MAX(id) + 1.
        #
        # La diferencia no se nota en un solo cajero y
        # se nota con dos: MAX(id) + 1 lo calculan
        # los dos antes de que ninguno inserte, así
        # que los dos cobran el mismo número de
        # recibo. Y el recibo es lo que se le lleva el
        # cliente y lo que busca el que contabiliza:
        # dos recibos iguales rompen la conciliación
        # sin que nada avise.
        #
        # Con el id no hay carrera posible: es único
        # por construcción, igual que el número de
        # contrato.

        recibo = recibo or (
            f"REC-{str(fecha)[:4]}-{id_pago:06d}"
        )

        cursor.execute(
            """
            UPDATE pagos
            SET cuota_id = %s, recibo = %s
            WHERE id = %s
            """,
            (id_cuota, recibo, id_pago)
        )

        cursor.execute(
            """
            UPDATE cuotas
            SET saldo = %s,
                estado = %s,
                cantidad_pagos = cantidad_pagos + 1
            WHERE id = %s
            """,
            (saldo_nuevo, nuevo_estado, id_cuota)
        )

        conexion.commit()

        estado_anterior = actual["estado"]

    except mysql.connector.Error as error:

        conexion.rollback()

        cursor.close()
        conexion.close()

        raise ErrorBaseDatos(str(error)) from error

    cursor.close()
    conexion.close()

    # ------------------------------
    # 7. RASTRO
    # ------------------------------
    # Con el valor anterior y el nuevo. Un pago sin
    # eso no se puede auditar: nadie sabe si la cuota
    # estaba pagada antes o si se acaba de cerrar.

    from database.auditoria import registrar_cambio

    registrar_cambio(
        "financiera",
        "PAGO_CUOTA",
        f"Cuota {cuota['numero']} del contrato "
        f"{cuota['contrato_id']}: "
        f"{formato_dinero(float(importe))} por {forma}",
        valor_anterior=(
            f"saldo {formato_dinero(float(saldo_actual))} "
            f"[{ESTADOS.get(estado_anterior, estado_anterior)}]"
        ),
        valor_nuevo=(
            f"saldo {formato_dinero(float(saldo_nuevo))} "
            f"[{ESTADOS.get(nuevo_estado, nuevo_estado)}]"
        ),
        referencia=recibo
    )

    return (id_pago, "")


def _estado_real(
    saldo,
    estado_actual,
    fecha_vencimiento,
    tiene_pagos=False,
    hoy=None
):
    """
    El estado que le corresponde a una cuota por su
    saldo, su fecha de vencimiento y si se le ha
    pagado algo.

    Es el UNICO sitio que decide el estado de una
    cuota. Si otro calculase el suyo por su cuenta,
    los dos podrian discrepar y la cartera mostraria
    una cosa mientras el saldo dice otra.

    Reglas, en orden:

      1. Una cuota anulada sigue anulada. Cobrar a una
         cuota anulada no la resucita: hay que
         reactivarla a proposito.

      2. Saldo a cero: pagada. Vencida o no, esta
         pagada.

      3. Saldo positivo y retraso que SUPERA los dias de
         gracia: vencida. Da igual que el campo diga
         "pendiente": la fecha la convierte en vencida
         sola.

      4. Saldo positivo, a tiempo y con pagos: parcial.

      5. Resto: pendiente.

    Por que el paso 4 necesita "tiene_pagos" y no
    basta con mirar el saldo: una cuota a la que se le
    anulo el unico pago que tenia vuelve a tener saldo
    entero, pero NO es una cuota pendiente: es una cuota
    a la que se le cobro y se le devolvio. Si se marcara
    "pendiente", la cartera la trataria como si el
    cliente no hubiera pagado nunca, que es exactamente
    lo que paso.

    Por que "hoy" es un parametro y no date.today(): para
    que las pruebas puedan fijar la fecha. La
    aplicacion no lo pasa nunca, y usa el dia de hoy.
    """

    if estado_actual == ESTADO_ANULADA:

        return ESTADO_ANULADA

    if saldo <= CERO:

        return ESTADO_PAGADA

    ajustes = leer_ajustes()

    if hoy is None:

        hoy = date.today()

    vencimiento = _a_fecha(fecha_vencimiento)

    dias_retraso = (
        (hoy - vencimiento).days if vencimiento else 0
    )

    # ">" y no ">=": pagar el mismo dia del vencimiento
    # no es tarde, ni con cero dias de margen. Con
    # ">=" una cuota con cero de gracia seria vencida
    # desde la medianoche de su vencimiento, que es
    # otra cosa.
    #
    # Y el "> " es lo que hace que con cero dias de
    # gracia las cuotas vencidas se marcen: con ">="
    # comparando contra hoy, o con "<" contra hoy -
    # cero, el resultado seria False siempre y la
    # cartera mostraria cero morosos para siempre.

    if dias_retraso > ajustes["dias_gracia"]:

        return ESTADO_VENCIDA

    if tiene_pagos:

        return ESTADO_PARCIAL

    return ESTADO_PENDIENTE


def _a_fecha(valor):

    if isinstance(valor, date):

        return valor

    if isinstance(valor, str):

        try:

            return date.fromisoformat(valor.strip()[:10])

        except ValueError:

            return None

    return None


def anular_pago_interno(id_pago, motivo):
    """
    Anula un pago sin comprobar el permiso.

    Existe para un caso concreto: una transacción ya
    confirmada que hay que deshacer porque la cuota
    que iba a cubrir ya estaba pagada. Es una
    corrección interna, no una operación de usuario,
    y no debe pedir permiso de administrador para
    poder ejecutarse.

    Aun así, deja rastro: un pago anulado sin
    explicación es un agujero.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:

        conexion.start_transaction()

        cursor.execute(
            """
            SELECT
                pagos.id,
                pagos.importe,
                pagos.cuota_id,
                pagos.forma,
                usuarios.nombre_usuario
            FROM pagos
            LEFT JOIN usuarios
                ON pagos.usuario_id = usuarios.id
            WHERE pagos.id = %s
            FOR UPDATE
            """,
            (id_pago,)
        )

        pago = cursor.fetchone()

        if not pago:

            conexion.rollback()

            return False

        usuario = modulo_sesion.obtener_sesion()

        cursor.execute(
            """
            UPDATE pagos
            SET estado = 'anulado',
                anulado_motivo = %s,
                anulado_usuario = %s,
                anulado_fecha = NOW()
            WHERE id = %s
            """,
            (
                motivo[:255],
                usuario.nombre_usuario,
                id_pago
            )
        )

        # Si el pago iba a una cuota, hay que
        # devolverle el importe. Si no, el saldo de la
        # cuota se queda corto para siempre.

        if pago["cuota_id"]:

            _devolver_a_cuota(
                cursor,
                pago["cuota_id"],
                pago["importe"],
                pago["forma"]
            )

        conexion.commit()

    except mysql.connector.Error as error:

        conexion.rollback()

        raise ErrorBaseDatos(str(error)) from error

    cursor.close()
    conexion.close()

    registrar_accion(
        "financiera",
        "PAGO_ANULADO",
        f"Pago de {formato_dinero(float(pago['importe']))} "
        f"anulado automáticamente: {motivo}"
    )

    return True


def _devolver_a_cuota(cursor, id_cuota, importe, forma):
    """
    Devuelve a una cuota lo que se le cobró de más,
    y recalcula su estado.

    Va DENTRO de la transacción del pago: si se
    hiciera aparte, un fallo en medio dejaría el
    saldo de la cuota y el estado del pago
    discrepando.
    """

    cursor.execute(
        """
        SELECT
            saldo, estado, cantidad_pagos,
            fecha_vencimiento
        FROM cuotas
        WHERE id = %s
        FOR UPDATE
        """,
        (id_cuota,)
    )

    cuota = cursor.fetchone()

    if not cuota:

        return

    saldo_nuevo = (
        Decimal(str(cuota["saldo"])) + Decimal(str(importe))
    ).quantize(DECIMALES, rounding=ROUND_HALF_UP)

    # Tras devolver el importe, la cuota se queda con
    # los pagos que le quedaban, que son uno menos que
    # antes: este acaba de dejar de contar. Por eso se
    # resta uno ANTES de decidir el estado.
    #
    # Si no se restara, una cuota a la que se le anula
    # su único pago volvería a "parcial", y la cartera
    # la trataría como si el cliente hubiera pagado algo.
    # Volver a "pendiente" es lo correcto: no se le
    # cobra nada y no se le ha cobrado nada.

    tiene_pagos = (cuota["cantidad_pagos"] or 0) > 1

    nuevo_estado = _estado_real(
        saldo_nuevo,
        cuota["estado"],
        date.today(),
        tiene_pagos=tiene_pagos
    )

    cursor.execute(
        """
        UPDATE cuotas
        SET saldo = %s,
            estado = %s,
            cantidad_pagos = GREATEST(
                cantidad_pagos - 1, 0
            )
        WHERE id = %s
        """,
        (saldo_nuevo, nuevo_estado, id_cuota)
    )


# ==========================================
# COBRO ADELANTADO
# ==========================================
# Un cliente paga dos meses seguidos de una vez. Es
# normal, y no es un "pago a cuenta": es dinero que
# tiene destino concreto y se sabe a qué cuotas se
# imputa.
#
# Lo que NO se hace:
#
#   - Guardarlo como un pago suelto sin imputar. El
#     dinero entra y el saldo del contrato baja, pero
#     las cuotas siguen con su saldo entero: la
#     cartera seguiría diciendo que debe dos meses que
#     ya pagó, y el cobro pendiente se le repetiría al
#     cliente cada mes.
#
#   - Imputarlo todo a una cuota y que su saldo quede
#     NEGATIVO. Un saldo negativo rompe todas las
#     cuentas de la cartera, que comparan contra cero,
#     y un "-3.208.333,33" no significa nada.
#
# Lo que sí: un pago por cuota, con el mismo número de
# recibo. El cliente entrega una suma, se guarda como
# N imputaciones a N cuotas, y cada una con su cuota.
# Los pagos no se editan ni se agrupan, pero compartir
# un número de recibo NO es editarlos: es la forma de
# decir "esto entró junto".


def repartir_adelanto(cuotas, importe):
    """
    Reparte un importe entre las cuotas, de la más
    antigua a la más reciente.

    PURE: no toca la base y no sabe nada de ella.
    Recibe las cuotas ya leidas (filas de
    obtener_cuotas()) y devuelve el plan de imputación.
    Por eso se puede probar con listas escritas a mano
    y sin base de datos, y por eso la vista previa del
    formulario y lo que luego se guarda no pueden
    discrepar: salen de la misma llamada.

    ------------------------------
    # LA REGLA
    # ------------------------------

    Cada cuota se paga ENTERA antes de pasar a la
    siguiente, y nunca al revés.

    La tentación es llenar de a poco: diez mil en la
    cuota 3, que quedan veinte mil, y seguir a la 4.
    Eso deja un resto pequeño en una cuota vieja y el
    cliente "debiendo" la 3 mientras paga la 4, para
    siempre. El resto pequeño nunca se salta porque
    siempre hay una cuota más antigua detrás. Un
    cliente que paga de a poco así acumula residuos
    invisibles.

    Con la regla de "entera o nada", o la cuota queda
    saldada, o el dinero se queda sin repartir y se le
    avisa al usuario. Nunca queda un residuo escondido.

    ------------------------------
    # LO QUE DEVUELVE
    # ------------------------------

    Una lista de diccionarios, en orden:

        {
            "id_cuota": id,
            "numero": numero de cuota,
            "fecha_vencimiento": fecha,
            "importe": lo que le toca a esta,
            "saldo_antes": lo que tenía,
            "saldo_despues": lo que le queda
        }

    Y un entero: el sobrante, lo que no ha cabido en
    ninguna cuota.

    ------------------------------
    # LAS ANULADAS SE SALTAN
    # ------------------------------

    Una cuota anulada no es exigible, así que no se
    cobra. Si el dinero no cabe en las que quedan, se
    devuelve como sobrante y el usuario decide.

    ------------------------------
    # LO QUE NO HACE
    # ------------------------------

    No comprueba que el importe quepa en el saldo de
    la VENTA. Eso lo comprueba registrar_pago(), que
    es quien inserta, y lo comprueba mejor: dentro de
    una transacción con la venta bloqueada.
    """

    try:

        total = Decimal(str(importe))

    except (InvalidOperation, TypeError, ValueError):

        raise ErrorValidacion(
            "El importe tiene que ser un número."
        ) from None

    total = total.quantize(DECIMALES, rounding=ROUND_HALF_UP)

    if total <= CERO:

        raise ErrorValidacion(
            "El importe tiene que ser mayor que cero."
        )

    plan = []

    queda = total

    for cuota in cuotas:

        if queda <= CERO:

            break

        if cuota["estado"] == ESTADO_ANULADA:

            continue

        saldo = Decimal(str(cuota["saldo"]))

        if saldo <= CERO:

            continue

        if saldo > queda:

            # La última que se toca: se queda con lo
            # que hay y el resto no cabe. El sobrante
            # se devuelve para que el usuario lo sepa.

            saldo_despues = saldo - queda

            queda = CERO

        else:

            saldo_despues = Decimal("0.00")

            queda -= saldo

        plan.append({
            "id_cuota": cuota["id"],
            "numero": cuota["numero"],
            "fecha_vencimiento": cuota["fecha_vencimiento"],
            "importe": saldo - saldo_despues,
            "saldo_antes": saldo,
            "saldo_despues": saldo_despues
        })

    if not plan:

        raise ErrorValidacion(
            "No hay cuotas pendientes de cobro en este "
            "contrato."
        )

    return (plan, queda.quantize(
        DECIMALES, rounding=ROUND_HALF_UP
    ))


@conexiones_libres
@requiere_permiso(GESTIONAR_FINANCIERA)
def registrar_pago_adelantado(
    id_contrato,
    importe,
    fecha,
    forma,
    recibo=None,
    referencia=None,
    concepto=None
):
    """
    Cobra de una vez varias cuotas seguidas.

    Devuelve (ids_de_pago, "") o (None, motivo).

    Devuelve la LISTA de ids porque un cobro adelantado
    son varios pagos con el mismo recibo. Quien solo
    quiere saber si salió bien mira la veracidad, como
    siempre.

    ------------------------------
    # POR QUÉ UNA SOLA TRANSACCIÓN
    # ------------------------------

    Es la diferencia entre esto y encadenar N llamadas
    a registrar_pago_cuota() por fuera:

    - Si la tercera cuota falla, las dos primeras ya
      están cobradas. El cliente entregó 30.000 y solo
      20.000 están aplicados, y el resto está en un pago
      suelto que nadie sabe a qué corresponde. La
      cartera vuelve a pedirle 10.000 que ya entregó.

    - Con una sola transacción, o entran todas las
      imputaciones o no entra ninguna.

    ------------------------------
    # POR QUÉ REUTILIZA registrar_pago()
    # ------------------------------

    No podría, en serio: registrar_pago() abre su
    propia conexión y su propia transacción, y anidar
    transacciones en la misma conexión no es transaccional
    en MySQL (un START TRANSACTION anula el anterior de
    forma silenciosa).

    La comprobación que falta es una sola, y va ANTES de
    abrir: que el total quepa en el saldo de la venta. Se
    hace con saldo_venta(), que es un SELECT, y con las
    cuotas leídas con FOR UPDATE para que el reparto no
    cambie entre el plan y la escritura. Si alguien cobra
    a la vez, el bloqueo salta: el FOR UPDATE del primer
    SELECT ya lo ha tomado, y el segundo la espera.

    ------------------------------
    # Y LA CONCILIACIÓN
    # ------------------------------

    Lo que entra es la suma exacta de las partes, y sale
    una fila de pagos por parte. La suma de `pagos`
    cuadra con el total de `cuotas.saldo` antes y después,
    que es lo que comprueba
    test_cuotas_sin_descuadre(): es la misma propiedad
    para un cobro de una cuota y para uno de seis.
    """

    # ------------------------------
    # 1. EL PLAN, SIN ESCRIBIR NADA
    # ------------------------------

    try:

        total = Decimal(str(importe)).quantize(
            DECIMALES, rounding=ROUND_HALF_UP
        )

    except (InvalidOperation, TypeError, ValueError):

        return (None, "El importe tiene que ser un número.")

    if total <= CERO:

        return (
            None,
            "El importe tiene que ser mayor que cero."
        )

    # ------------------------------
    # 2. EL CONTRATO, PARA SABER SU VENTA
    # ------------------------------

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id, venta_id, saldo_financiado,
                estado, numero
            FROM contratos
            WHERE id = %s
            FOR UPDATE
            """,
            (id_contrato,)
        )

        contrato = cursor.fetchone()

        if not contrato:

            conexion.rollback()

            return (None, "El contrato no existe.")

        if contrato["estado"] == "cancelado":

            conexion.rollback()

            return (
                None,
                "El contrato está cancelado: no admite "
                "cobros."
            )

        # ------------------------------
        # 3. LAS CUOTAS, BLOQUEADAS
        # ------------------------------
        # El bloqueo va AQUÍ y no al final porque el
        # reparto se calcula sobre lo que sale de este
        # SELECT. Si otro cobraro entra entre medias y
        # su UPDATE espera al lock, es este el que va
        # primero; al revés, el reparto se haria sobre
        # saldos viejos y se escribiria sobre nuevos.

        cursor.execute(
            """
            SELECT
                id, numero, fecha_vencimiento,
                importe, saldo, estado, cantidad_pagos
            FROM cuotas
            WHERE contrato_id = %s
            ORDER BY numero
            FOR UPDATE
            """,
            (id_contrato,)
        )

        cuotas = cursor.fetchall()

        if not cuotas:

            conexion.rollback()

            return (
                None,
                "Este contrato no tiene cronograma. "
                "Genérelo antes de cobrar."
            )

        # ------------------------------
        # 4. QUE NO SE PASE DEL SALDO
        # ------------------------------
        # Aqui se comprueba contra la VENTA, no contra
        # las cuotas, y por un motivo concreto: el dinero
        # entra por la puerta de la venta y es el saldo
        # de la venta el que no puede quedar en negativo.
        #
        # Y se comprueba el TOTAL, no cada parte: un
        # cobro adelantado de 30.000 repartido en tres
        # de 10.000 passaria parte a parte y fallaria
        # en la tercera, dejando las dos primeras
        # cobradas de un total que no cabia.

        cursor.execute(
            """
            SELECT
                ventas.precio,
                COALESCE((
                    SELECT SUM(pagos.importe)
                    FROM pagos
                    WHERE pagos.venta_id = ventas.id
                      AND pagos.estado = 'convalidado'
                ), 0) AS pagado
            FROM ventas
            WHERE ventas.id = %s
            """,
            (contrato["venta_id"],)
        )

        venta = cursor.fetchone()

        if venta:

            saldo_venta = (
                Decimal(str(venta["precio"]))
                - Decimal(str(venta["pagado"]))
            )

            if total > saldo_venta:

                conexion.rollback()

                return (
                    None,
                    f"El importe es mayor que el saldo "
                    f"de la venta. Quedan "
                    f"{formato_dinero(float(saldo_venta))} por cobrar."
                )

        # ------------------------------
        # 5. EL REPARTO
        # ------------------------------

        try:

            plan, sobrante = repartir_adelanto(
                cuotas, total
            )

        except ErrorValidacion as error:

            conexion.rollback()

            return (None, error.mensaje)

        if sobrante > CERO:

            conexion.rollback()

            return (
                None,
                f"El importe no cabe en las cuotas "
                f"pendientes: sobran "
                f"{formato_dinero(float(sobrante))}.\n\n"
                "Un cobro adelantado se imputa a cuotas "
                "completas, de la más antigua a la más "
                "reciente. Si el cliente entrega de más, "
                "eso es otro pago y se registra aparte."
            )

        # ------------------------------
        # 6. LOS PAGOS, SIN RECIBO TODAVÍA
        # ------------------------------
        # UN número para todos los pagos, como el del
        # contrato. Viene del id del PRIMER pago, que
        # MySQL ya ha asignado al insertar: único por
        # construcción, sin MAX(id) + 1 y sin carrera.

        if concepto is None:

            concepto = (
                f"Adelantado: {len(plan)} cuota(s) del "
                f"contrato {contrato['numero']}"
            )

        ids = []

        # ------------------------------
        # QUIÉN COBRA
        # ------------------------------
        # De la sesión, una sola vez. Los N pagos
        # llevan el mismo usuario, y el rastro de la
        # acción también: es una acción.

        usuario = modulo_sesion.obtener_sesion()

        # El estado de cada cuota ANTES de tocarla. Se
        # lee aquí y no dentro del bucle porque las
        # partes son sobre filas distintas: cada una
        # parte del estado que tenía al empezar, que es
        # el que _estado_real() espera.

        estado_global = {
            c["id"]: c["estado"] for c in cuotas
        }

        for parte in plan:

            cursor.execute(
                """
                INSERT INTO pagos
                (
                    venta_id, cuota_id, usuario_id,
                    fecha, importe, forma,
                    referencia, concepto,
                    recibo, estado
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, 'convalidado'
                )
                """,
                (
                    contrato["venta_id"],
                    parte["id_cuota"],
                    usuario.id_usuario,
                    fecha,
                    parte["importe"],
                    forma,
                    referencia,
                    concepto,
                    None
                )
            )

            ids.append({
                "id": cursor.lastrowid,
                "id_cuota": parte["id_cuota"],
                "cuota": parte["numero"],
                "importe": parte["importe"],
                "recibo": None
            })

        # ------------------------------
        # 7. EL RECIBO, UNO PARA TODOS
        # ------------------------------
        # Se asigna DESPUES de insertar las N partes,
        # y se toma del id de la primera.
        #
        # Si se calculara dentro del bucle, cada pago
        # saldría con el suyo y el cliente que entregó
        # una sola suma se llevaría N recibos. Y el
        # rastro, que se guarda por recibo, quedaría
        # repartido en N entradas que no dicen que
        # salieron del mismo acto: en junio, quien audite
        # vería tres cobros y no sabría que el cliente
        # vino una vez.
        #
        # Del id del primer INSERT, que MySQL ya ha
        # asignado: único por construcción, sin
        # MAX(id) + 1 y sin carrera entre dos cajas.

        recibo_compartido = recibo or (
            f"REC-{str(fecha)[:4]}-{ids[0]['id']:06d}"
        )

        for parte in ids:

            cursor.execute(
                "UPDATE pagos SET recibo = %s WHERE id = %s",
                (recibo_compartido, parte["id"])
            )

            parte["recibo"] = recibo_compartido

        # ------------------------------
        # 8. LAS CUOTAS
        # ------------------------------

        for parte, reparto in zip(ids, plan):

            nuevo_estado = _estado_real(
                reparto["saldo_despues"],
                estado_global[reparto["id_cuota"]],
                fecha,
                tiene_pagos=True
            )

            cursor.execute(
                """
                UPDATE cuotas
                SET saldo = %s,
                    estado = %s,
                    cantidad_pagos = cantidad_pagos + 1
                WHERE id = %s
                """,
                (
                    reparto["saldo_despues"],
                    nuevo_estado,
                    reparto["id_cuota"]
                )
            )

        conexion.commit()

        # ------------------------------
        # 9. EL RASTRO
        # ------------------------------
        # UNO, con el antes y el después EN CONJUNTO.
        #
        # N entradas, una por cuota, se leen como N
        # operaciones distintas y no dejan ver que fue
        # una: alguien que audite en junio ve tres
        # cobros y no sabe que el cliente vino una vez.
        # Con una entrada que dice "cuotas 3, 4 y 5 de
        # un pago" se ve.

        saldo_total_antes = sum(
            (Decimal(str(c["saldo"])) for c in cuotas),
            Decimal("0.00")
        )

        saldo_total_despues = (
            saldo_total_antes - total
        )

        registrar_cambio(
            "financiera",
            "PAGO_ADELANTADO",
            f"Cobro adelantado de "
            f"{formato_dinero(total)} que cubre "
            f"{len(plan)} cuota(s) del contrato "
            f"{contrato['numero']}: "
            + ", ".join(str(p["numero"]) for p in plan)
            + f" por {forma}",
            valor_anterior=(
                "saldo pendiente "
                f"{formato_dinero(saldo_total_antes)}"
            ),
            valor_nuevo=(
                "saldo pendiente "
                f"{formato_dinero(saldo_total_despues)}"
            ),
            referencia=ids[0]["recibo"] if ids else recibo
        )

        return (ids, "")

    except mysql.connector.Error as error:

        conexion.rollback()

        cursor.close()
        conexion.close()

        raise ErrorBaseDatos(str(error)) from error


# ==========================================
# ANULAR UN PAGO
# ==========================================
# Un pago NO se borra ni se edita. Se anula, con
# motivo, y el saldo de la cuota vuelve a subir.
# Queda el rastro.
#
# Editar un pago sería cambiar un hecho económico
# después de los hechos: nadie podría saber qué se
# cobró en realidad. Anularlo deja la verdad
# intacta y añade un movimiento que la explica.

@conexiones_libres
@requiere_permiso(GESTIONAR_CONTRATOS)
def anular_pago(id_pago, motivo):
    """
    Anula un pago ya registrado.

    Devuelve (True, "") o (False, motivo).
    """

    if not motivo or not motivo.strip():

        return (
            False,
            "Hace falta un motivo: un pago anulado sin "
            "explicación es un cobro que desapareció."
        )

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:

        conexion.start_transaction()

        cursor.execute(
            """
            SELECT
                pagos.id,
                pagos.importe,
                pagos.forma,
                pagos.cuota_id,
                pagos.estado AS pago_estado,
                pagos.recibo,
                cuotas.numero AS cuota_numero,
                cuotas.saldo AS cuota_saldo,
                cuotas.estado AS cuota_estado,
                contratos.id AS contrato_id,
                contratos.numero AS contrato_numero
            FROM pagos
            LEFT JOIN cuotas
                ON pagos.cuota_id = cuotas.id
            LEFT JOIN contratos
                ON pagos.contrato_id = contratos.id
            WHERE pagos.id = %s
            FOR UPDATE
            """,
            (id_pago,)
        )

        pago = cursor.fetchone()

        if not pago:

            conexion.rollback()

            return (False, "El pago indicado no existe.")

        if pago["pago_estado"] == "anulado":

            conexion.rollback()

            return (
                False,
                "El pago ya estaba anulado."
            )

        # ------------------------------
        # EL ESTADO DE LA CUOTA, ANTES
        # ------------------------------

        estado_cuota_antes = pago["cuota_estado"]

        saldo_cuota_antes = pago["cuota_saldo"]

        # ------------------------------
        # ANULAR EL PAGO
        # ------------------------------

        usuario = modulo_sesion.obtener_sesion()

        cursor.execute(
            """
            UPDATE pagos
            SET estado = 'anulado',
                anulado_motivo = %s,
                anulado_usuario = %s,
                anulado_fecha = NOW()
            WHERE id = %s
            """,
            (
                motivo.strip()[:255],
                usuario.nombre_usuario,
                id_pago
            )
        )

        # ------------------------------
        # DEVOLVERLO A LA CUOTA
        # ------------------------------

        if pago["cuota_id"]:

            _devolver_a_cuota(
                cursor,
                pago["cuota_id"],
                pago["importe"],
                pago["forma"]
            )

        conexion.commit()

        # Se relee la cuota para el rastro: el estado
        # nuevo no se conoce hasta después del UPDATE.

        cursor.execute(
            "SELECT saldo, estado FROM cuotas WHERE id = %s",
            (pago["cuota_id"],)
        )

        cuota_despues = cursor.fetchone()

    except mysql.connector.Error as error:

        conexion.rollback()

        raise ErrorBaseDatos(str(error)) from error

    texto_cuota = ""

    if pago["cuota_id"] and cuota_despues:

        texto_cuota = (
            f" Cuota {pago['cuota_numero']}: "
            f"{formato_dinero(float(saldo_cuota_antes or 0))} "
            f"-> {formato_dinero(float(cuota_despues['saldo']))} "
            f"[{ESTADOS.get(estado_cuota_antes, '?')} -> "
            f"{ESTADOS.get(cuota_despues['estado'], '?')}]"
        )

    from database.auditoria import registrar_cambio

    registrar_cambio(
        "financiera",
        "PAGO_ANULADO",
        f"Pago de {formato_dinero(float(pago['importe']))} "
        f"anulado. Motivo: {motivo.strip()}",
        valor_anterior=(
            f"convalidado"
            + (
                " | cuota saldo "
                f"{formato_dinero(saldo_cuota_antes or 0)}"
                if pago["cuota_id"] else ""
            )
        ),
        valor_nuevo=(
            f"anulado"
            + (
                " | cuota saldo "
                f"{formato_dinero(cuota_despues['saldo'])}"
                if cuota_despues else ""
            )
        ),
        referencia=pago["recibo"]
    )

    del texto_cuota

    return (True, "")


# ==========================================
# ANULAR UNA CUOTA
# ==========================================

@conexiones_libres
@requiere_permiso(GESTIONAR_CONTRATOS)
def anular_cuota(id_cuota, motivo):
    """
    Anula una cuota del cronograma.

    Devuelve (True, "") o (False, motivo).

    Solo tiene sentido con una cuota que NO se ha
    cobrado. Una cuota con saldo puesto a cero
    aparecería como pagada, y el total del contrato
    ya no cuadraría con el dinero de verdad.
    """

    if not motivo or not motivo.strip():

        return (False, "Hace falta un motivo.")

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:

        conexion.start_transaction()

        cursor.execute(
            """
            SELECT
                cuotas.id,
                cuotas.importe,
                cuotas.saldo,
                cuotas.estado,
                cuotas.numero,
                cuotas.cantidad_pagos,
                contratos.numero AS contrato_numero
            FROM cuotas
            INNER JOIN contratos
                ON cuotas.contrato_id = contratos.id
            WHERE cuotas.id = %s
            FOR UPDATE
            """,
            (id_cuota,)
        )

        cuota = cursor.fetchone()

        if not cuota:

            conexion.rollback()

            return (False, "La cuota indicada no existe.")

        if cuota["estado"] == "anulada":

            conexion.rollback()

            return (False, "La cuota ya estaba anulada.")

        if Decimal(str(cuota["saldo"])) != Decimal(
            str(cuota["importe"])
        ):

            conexion.rollback()

            return (
                False,
                "La cuota tiene pagos registrados. "
                "Anúlelos antes de anular la cuota, o "
                "el saldo del contrato dejaría de "
                "cuadrar."
            )

        estado_anterior = cuota["estado"]

        cursor.execute(
            "UPDATE cuotas SET estado = %s WHERE id = %s",
            (ESTADO_ANULADA, id_cuota)
        )

        conexion.commit()

    except mysql.connector.Error as error:

        conexion.rollback()

        raise ErrorBaseDatos(str(error)) from error

    cursor.close()
    conexion.close()

    from database.auditoria import registrar_cambio

    registrar_cambio(
        "financiera",
        "CUOTA_ANULADA",
        f"Cuota {cuota['numero']} del contrato "
        f"{cuota['contrato_numero']} anulada. "
        f"Motivo: {motivo.strip()}",
        valor_anterior=(
            f"{ESTADOS.get(estado_anterior, estado_anterior)}"
        ),
        valor_nuevo=f"{ESTADOS[ESTADO_ANULADA]}"
    )

    return (True, "")


@conexiones_libres
@requiere_permiso(GESTIONAR_CONTRATOS)
def reactivar_cuota(id_cuota, motivo):
    """
    Devuelve una cuota anulada al cronograma.

    Devuelve (True, "") o (False, motivo).
    """

    if not motivo or not motivo.strip():

        return (False, "Hace falta un motivo.")

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:

        conexion.start_transaction()

        cursor.execute(
            """
            SELECT
                cuotas.id,
                cuotas.estado,
                cuotas.saldo,
                cuotas.importe,
                cuotas.numero,
                cuotas.cantidad_pagos,
                cuotas.fecha_vencimiento,
                contratos.numero AS contrato_numero
            FROM cuotas
            INNER JOIN contratos
                ON cuotas.contrato_id = contratos.id
            WHERE cuotas.id = %s
            FOR UPDATE
            """,
            (id_cuota,)
        )

        cuota = cursor.fetchone()

        if not cuota:

            conexion.rollback()

            return (False, "La cuota indicada no existe.")

        if cuota["estado"] != "anulada":

            conexion.rollback()

            return (
                False,
                "La cuota no está anulada."
            )

        # El estado al que vuelve depende de su saldo:
        # si tiene pagos, parcial; si no, pendiente.

        nuevo_estado = _estado_real(
            Decimal(str(cuota["saldo"])),
            ESTADO_PENDIENTE,
            date.today(),
            tiene_pagos=bool(cuota.get("cantidad_pagos"))
        )

        cursor.execute(
            "UPDATE cuotas SET estado = %s WHERE id = %s",
            (nuevo_estado, id_cuota)
        )

        conexion.commit()

    except mysql.connector.Error as error:

        conexion.rollback()

        raise ErrorBaseDatos(str(error)) from error

    cursor.close()
    conexion.close()

    from database.auditoria import registrar_cambio

    registrar_cambio(
        "financiera",
        "CUOTA_REACTIVADA",
        f"Cuota {cuota['numero']} del contrato "
        f"{cuota['contrato_numero']} reactivada. "
        f"Motivo: {motivo.strip()}",
        valor_anterior=ESTADOS[ESTADO_ANULADA],
        valor_nuevo=ESTADOS[nuevo_estado]
    )

    return (True, "")


# ==========================================
# DETECTAR VENCIDAS
# ==========================================
# No es un proceso de fondo: se llama al abrir la
# cartera y al registrar un pago. Con eso basta,
# porque una cuota vencida no cambia de estado sola:
# cambia porque alguien mira.

@conexiones_libres
def procesar_vencidas(hoy=None):
    """
    Marca como vencidas las cuotas que pasaron su
    fecha y siguen con saldo.

    Devuelve cuántas cambiaron.

    Marca lo que está MAL, nunca lo que está bien.
    Una cuota pagada que quedara en "vencida" sería
    mentira, así que el UPDATE tiene las tres
    condiciones: no anulada, con saldo, y fecha
    pasada.

    Y una cuota que vuelve a la vida porque se le
    pagó: también se corrige aquí. Si solo marcara,
    una cuota cobrada con retraso seguiría figurando
    como vencida en la cartera.
    """

    if hoy is None:

        hoy = date.today()

    ajustes = leer_ajustes()

    limite = hoy - timedelta(days=ajustes["dias_gracia"])

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:

        conexion.start_transaction()

        # Poner vencida.

        cursor.execute(
            """
            UPDATE cuotas
            SET estado = %s
            WHERE estado IN (%s, %s)
              AND saldo > 0
              AND fecha_vencimiento < %s
            """,
            (
                ESTADO_VENCIDA,
                ESTADO_PENDIENTE,
                ESTADO_PARCIAL,
                limite
            )
        )

        marcadas = cursor.rowcount

        # Sacar de vencida lo que ya se cobró.

        cursor.execute(
            """
            UPDATE cuotas
            SET estado = %s
            WHERE estado = %s
              AND saldo <= 0
            """,
            (ESTADO_PAGADA, ESTADO_VENCIDA)
        )

        corregidas = cursor.rowcount

        conexion.commit()

    except mysql.connector.Error as error:

        conexion.rollback()

        raise ErrorBaseDatos(str(error)) from error

    cursor.close()
    conexion.close()

    total = marcadas + corregidas

    # El rastro va DESPUÉS del commit, y solo si
    # algo cambió: registrar "0 vencidas marcadas"
    # cada vez que se abre la cartera llenaría la
    # tabla de auditoría de ruido.

    if total:

        registrar_accion(
            "financiera",
            "VENCIDAS",
            f"{marcadas} cuotas marcadas como "
            f"vencidas y {corregidas} corregidas "
            f"(pagadas con retraso)"
        )

    return total


# ==========================================
# RECALCULAR
# ==========================================
# Para auditar que el saldo guardado sigue
# cuadrando con los pagos. Solo para pruebas y para
# una comprobación manual: si un saldo se
# descuadrara, la causa es un pago escrito sin
# actualizar su cuota, y THIS es lo que lo
# encontraría.

def recalcular_saldo_cuota(id_cuota):
    """
    Devuelve (saldo_guardado, saldo_calculado) para
    una cuota.

    Si no coinciden, hay un pago que se escribió sin
    tocar el saldo. Devolver los dos en vez de
    corregir en silencio: un descuadre es un
    problema que hay que ver, no tapar.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            cuotas.importe,
            cuotas.saldo AS guardado,
            COALESCE(SUM(pagos.importe), 0) AS pagado
        FROM cuotas
        LEFT JOIN pagos
            ON pagos.cuota_id = cuotas.id
           AND pagos.estado = 'convalidado'
        WHERE cuotas.id = %s
        GROUP BY cuotas.id, cuotas.importe, cuotas.saldo
        """,
        (id_cuota,)
    )

    fila = cursor.fetchone()

    cursor.close()
    conexion.close()

    if not fila:

        return (None, None)

    importe = Decimal(str(fila["importe"]))
    pagado = Decimal(str(fila["pagado"]))

    return (
        Decimal(str(fila["guardado"])),
        (importe - pagado).quantize(DECIMALES)
    )


def recalcular_saldos_de_contrato(id_contrato):
    """
    Lo mismo para todas las cuotas de un contrato.

    Devuelve la lista de id_cuota que NO cuadran.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        "SELECT id FROM cuotas WHERE contrato_id = %s",
        (id_contrato,)
    )

    ids = [f[0] for f in cursor.fetchall()]

    cursor.close()
    conexion.close()

    descuadradas = []

    for id_cuota in ids:

        guardado, calculado = recalcular_saldo_cuota(
            id_cuota
        )

        if guardado is None:

            continue

        if guardado != calculado:

            descuadradas.append(id_cuota)

    return descuadradas


# ==========================================
# RECIBOS
# ==========================================

@requiere_permiso(VER_CONTRATOS)
def siguiente_numero_recibo():
    """
    El próximo número de recibo, como CANDIDATO.

    Devuelve el número que le tocaría al siguiente
    pago: el año y MAX(id) + 1.

    OJO: es una vista previa, no un número que se
    pueda guardar. Se calcula antes de insertar, así
    que dos pagos hechos a la vez saldrían con el
    mismo. Para guardar hay que dejarlo en None y
    que lo arme el propio INSERT, con el id que le
    toque: registrar_pago_cuota() ya lo hace así.

    Esto se queda para lo que sí lo necesita: el
    recibo que se le enseña al usuario antes de
    guardar, y el PDF de un pago antiguo al que no
    se le puso número.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT COALESCE(MAX(id), 0) + 1
        FROM pagos
        """
    )

    siguiente = cursor.fetchone()[0]

    cursor.close()
    conexion.close()

    return f"REC-{date.today().year}-{siguiente:06d}"


@requiere_permiso(VER_CONTRATOS)
def pagos_de_cuota(id_cuota):
    """
    Los pagos de una cuota, con su estado.

    Contrato de columnas: id, fecha, importe, forma,
    referencia, recibo, concepto, estado,
    anulado_motivo, usuario_nombre.

    Incluye los anulados: hay que verlos para
    entender por qué una cuota no cuadra. Ocultarlos
    haría que el saldo pareciera un error.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            id, fecha, importe, forma, referencia,
            recibo, concepto, estado,
            anulado_motivo, anulado_usuario,
            anulado_fecha, usuario_nombre
        FROM pagos
        WHERE cuota_id = %s
        ORDER BY fecha, id
        """,
        (id_cuota,)
    )

    pagos = cursor.fetchall()

    cursor.close()
    conexion.close()

    return pagos


