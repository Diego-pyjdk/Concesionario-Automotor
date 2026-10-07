# ==========================================
# CONTRATOS DE COMPRAVENTA
# ==========================================
# Un contrato por venta. Se genera después de
# cerrar la venta y no se puede editar una vez
# firmado: se cancela y se vuelve a hacer.
#
# El número (CTR-2026-00001) se forma con el
# año y el id del propio contrato. Se calcula
# DESPUÉS del INSERT, dentro de la misma
# transacción: así el número no depende de
# contar filas ni de que dos usuarios creen
# contratos a la vez.
#
# La unicidad de venta_id la impone la base
# (uq_contratos_venta). El código la
# comprueba antes para poder dar un mensaje
# claro en vez de un error de clave duplicada.
# ==========================================


import datetime

from decimal import Decimal, InvalidOperation

import mysql.connector

from database.conexion import (
    conexiones_libres,
    obtener_conexion
)

from database.auditoria import (
    registrar_accion,
    registrar_cambio
)

import database.financiera as financiera

import sesion as modulo_sesion

from permisos import (
    requiere_permiso,
    VER_CONTRATOS,
    CREAR_CONTRATOS,
    GESTIONAR_CONTRATOS
)

from errores import traducir_error

from utils.moneda import formato_dinero


# ==========================================
# ESTADOS
# ==========================================
# El código es estable; el texto sale de aquí
# al mostrarlo.

ESTADOS = {
    "borrador": "Borrador",
    "activo": "Activo",
    "finalizado": "Finalizado",
    "cancelado": "Cancelado"
}

# Estados a los que se puede pasar desde el
# que tenga el contrato.
#
# "finalizado" no es una puerta de salida: un
# contrato ya firmado se puede anular si la
# operación se cae, pero no volver a "activo".
# Cancelado sí se puede reactivar, porque no
# surte efecto.

TRANSICIONES = {
    "borrador": ["activo", "cancelado"],
    "activo": ["finalizado", "cancelado"],
    "finalizado": ["cancelado"],
    "cancelado": ["activo"]
}

ESTADO_INICIAL = "activo"


def _a_importe(valor, nombre):
    """
    Un importe a Decimal, o (None, motivo).

    El dinero entra como float desde los formularios y
    sale como Decimal de la base, y "Decimal menos
    float" es un TypeError que no dice nada del
    contrato. Aquí se normaliza todo una vez, antes de
    tocar la base.

    Se convierte por la CADENA y no con float(): el
    float() de un número con más de 15 dígitos ya ha
    perdido precisión al entrar, y convertirlo a
    Decimal después no lo recupera.
    """

    if valor is None:

        return (Decimal("0.00"), "")

    if isinstance(valor, Decimal):

        return (valor, "")

    try:

        return (Decimal(str(valor)), "")

    except (InvalidOperation, TypeError, ValueError):

        return (
            None,
            f"{nombre} tiene que ser un número."
        )


# ==========================================
# LO QUE SE FINANCIARÍA
# ==========================================

def _validar_financiacion(
    cantidad_cuotas,
    tasa_interes,
    periodicidad,
    primer_vencimiento,
    gastos_administrativos,
    retencion,
    retencion_monto
):
    """
    Comprueba y normaliza las condiciones económicas
    de un contrato.

    Devuelve un diccionario con todo ya limpio, o un
    STRING con el motivo del rechazo.

    Devuelve la cadena y no una tupla tipo
    (ok, valor) porque el valor es un diccionario de
    siete campos y no cabe bien en una tupla: se
    acabaría desempacando con un *resultado que
    mezcla el "ok" con la primera clave.

    ------------------------------
    POR QUÉ AQUÍ Y NO EN EL FORMULARIO
    ------------------------------
    Porque las tres guardas duras son de un
    documento firmado. Un contrato es papel que va
    a un juez, y si queda guardado con una retención
    del 400 % o una periodicidad que no existe, eso
    ya no lo arregla nadie.

    El formulario avisa antes, que es más cómodo, pero
    lo que decide es esto.

    ------------------------------
    LO QUE NO SE COMPRUEBA
    ------------------------------
    Que la tasa sea la del mercado, que los gastos
    sean razonables o que la retención sea la que
    manda. Eso depende de la legislación y de un
    asesor, y un programa no puede resolverlo. El
    campo de retención existe para que el dato quede
    REGISTRADO, no para que la aplicación calcule una
    obligación fiscal.
    """

    ajustes = {
        "cantidad_cuotas": 0,
        "tasa_interes": Decimal("0.000"),
        "periodicidad": financiera.PERIODICIDAD_POR_DEFECTO,
        "gastos_administrativos": Decimal("0.00"),
        "retencion": Decimal("0.000"),
        "retencion_monto": Decimal("0.00")
    }

    # ------------------------------
    # NÚMEROS
    # ------------------------------

    try:

        ajustes["tasa_interes"] = Decimal(
            str(tasa_interes or 0)
        )

        ajustes["gastos_administrativos"] = Decimal(
            str(gastos_administrativos or 0)
        )

        ajustes["retencion"] = Decimal(
            str(retencion or 0)
        )

        ajustes["retencion_monto"] = Decimal(
            str(retencion_monto or 0)
        )

    except (InvalidOperation, TypeError, ValueError):

        return (
            "Los importes de la financiación tienen "
            "que ser números."
        )

    try:

        ajustes["cantidad_cuotas"] = int(
            cantidad_cuotas or 0
        )

    except (TypeError, ValueError):

        return "La cantidad de cuotas tiene que ser un número."

    # ------------------------------
    # NEGATIVOS
    # ------------------------------

    if ajustes["cantidad_cuotas"] < 0:

        return "La cantidad de cuotas no puede ser negativa."

    if ajustes["tasa_interes"] < 0:

        return "La tasa de interés no puede ser negativa."

    if ajustes["gastos_administrativos"] < 0:

        return (
            "Los gastos administrativos no pueden "
            "ser negativos."
        )

    if ajustes["retencion"] < 0:

        return "La retención no puede ser negativa."

    if ajustes["retencion_monto"] < 0:

        return (
            "La retención en importe no puede ser "
            "negativa."
        )

    # ------------------------------
    # LÍMITES
    # ------------------------------

    ajustes_financiera = financiera.leer_ajustes()

    maximo = ajustes_financiera["maximo_cuotas"]

    if ajustes["cantidad_cuotas"] > maximo:

        return (
            f"No se admiten más de {maximo} cuotas. "
            "Un crédito a más de seis años tiene que "
            "hacerse con un contrato aparte, no con "
            "una lista interminable."
        )

    if ajustes["retencion"] > 100:

        return (
            "La retención no puede pasar del 100 %: "
            "entonces no cobraría nada."
        )

    if (
        ajustes["retencion"] > 0
        and ajustes["retencion_monto"] > 0
    ):

        return (
            "La retención va en porcentaje o en "
            "importe, no en las dos cosas a la vez: "
            "no se sabe cuál manda."
        )

    # ------------------------------
    # CUOTAS
    # ------------------------------

    if ajustes["cantidad_cuotas"] == 0:

        # Sin cuotas no hay nada que repartir, y por
        # eso no se exige periodicidad ni primer
        # vencimiento: un contrato de contado lleva
        # los dos a NULL y es correcto.

        return ajustes

    if (
        periodicidad is not None
        and periodicidad not in
        financiera.TODAS_LAS_PERIODICIDADES
    ):

        return (
            f"Periodicidad '{periodicidad}' no válida. "
            f"Vale: "
            f"{', '.join(financiera.TODAS_LAS_PERIODICIDADES)}."
        )

    if periodicidad:

        ajustes["periodicidad"] = periodicidad

    if primer_vencimiento is None:

        return (
            "Con cuotas hay que decir cuándo vence "
            "la primera: sin fecha no hay cronograma."
        )

    if not isinstance(primer_vencimiento, datetime.date):

        return (
            "La fecha del primer vencimiento no es "
            "una fecha válida."
        )

    # ------------------------------
    # UN VENCIMIENTO EN EL PASADO
    # ------------------------------
    # No se rechaza: hay contratos nuevos con
    # vencimientos que ya pasaron, y se corrigen a
    # mano desde la base. Lo que no se puede es
    # dejar pasar un cronograma entero, y eso lo
    # comprueba generar_cronograma() cuando ve que
    # todas las fechas ya pasaron.
    #
    # Se avisa aquí, en vez de callar, porque un
    # vencimiento pasado suele ser un error de
    # tecleo y es mejor enterarse al firmar que al
    # primer cobro.

    if primer_vencimiento < datetime.date.today():

        ajustes["vencimiento_en_pasado"] = True

    return ajustes


def formato_decimal(valor):
    """
    Un Decimal con los decimales que tenga, sin
    ceros de más.

    La tasa va a tres decimales en la tabla
    (DECIMAL(6,3)) y a dos en las cuotas, así que
    str() a secas saldría "12.000" donde la
    pantalla muestra "12". En el rastro eso parece
    una tasa distinta de la que se firmó.
    """

    try:

        numero = Decimal(str(valor))

    except (InvalidOperation, TypeError, ValueError):

        return str(valor)

    if numero == numero.to_integral_value():

        return f"{numero:.0f}"

    return f"{numero:f}".rstrip("0").rstrip(".")


# ==========================================
# FORMAS DE PAGO
# ==========================================

FORMAS_PAGO = [
    "Contado",
    "Crédito",
    "Anticipo + cuotas",
    "Transferencia bancaria",
    "Financiado con terceros"
]


# ==========================================
# NÚMERO
# ==========================================

def formatear_numero(id_contrato, anio=None):
    """
    CTR-2026-00001
    """

    if anio is None:

        anio = datetime.date.today().year

    return f"CTR-{anio}-{id_contrato:05d}"


def nombre_archivo(numero):
    """
    contrato_CTR-2026-00001.pdf
    """

    return f"contrato_{numero}.pdf"


# ==========================================
# LOS DATOS DE UNA VENTA PARA EL CONTRATO
# ==========================================
# El SELECT de las dos consultas siguientes, en un
# solo sitio.
#
# Está aquí y no repetido en cada función porque las
# dos TIENEN que devolver la misma forma: si una
# añadiera una columna y la otra no, el formulario
# desempaquetaría un número distinto según por dónde
# se abriera. Y eso no falla al escribir el código:
# falla cuando alguien crea un contrato desde Ventas,
# que es el camino normal.
#
# Es el mismo contrato de columnas que
# obtener_ventas(), menos el vendedor: el contrato lo
# copia al crearse y el detalle lo lee de
# contratos.usuario_nombre.

DATOS_VENTA = """
    SELECT
        ventas.id,
        ventas.fecha,
        CONCAT(
            clientes.nombre, ' ', clientes.apellido
        ) AS cliente,
        CONCAT(
            marcas.nombre, ' ', autos.modelo
        ) AS vehiculo,
        ventas.precio
    FROM ventas
    INNER JOIN clientes
        ON ventas.cliente_id = clientes.id
    INNER JOIN autos
        ON ventas.auto_id = autos.id
    INNER JOIN marcas
        ON autos.marca_id = marcas.id
"""


# ==========================================
# CONSULTA
# ==========================================

CONTRATO_BASE = """
    SELECT
        contratos.id,
        contratos.numero,
        contratos.venta_id,
        contratos.fecha,
        contratos.precio_venta,
        contratos.forma_pago,
        contratos.anticipo,
        contratos.saldo_financiado,
        contratos.tasa_interes,
        contratos.gastos_administrativos,
        contratos.monto_cuota,
        contratos.cantidad_cuotas,
        contratos.periodicidad,
        contratos.primer_vencimiento,
        contratos.dia_vencimiento,
        contratos.moneda,
        contratos.retencion,
        contratos.retencion_monto,
        contratos.clausulas,
        contratos.observaciones,
        contratos.estado,
        contratos.archivo_pdf,
        contratos.fecha_creacion,
        contratos.fecha_modificacion,
        contratos.cliente_id,
        CONCAT(
            clientes.nombre, ' ', clientes.apellido
        ) AS cliente,
        clientes.documento,
        clientes.telefono,
        clientes.email,
        contratos.auto_id,
        CONCAT(
            marcas.nombre, ' ', autos.modelo
        ) AS vehiculo,
        -- El vehículo se lee de la FOTOGRAFÍA del
        -- contrato (marcas.nombre y autos.modelo son
        -- el dato actual, no el de la firma). Un
        -- contrato ya firmado no puede cambiar solo
        -- porque alguien corrija el vehículo después.
        contratos.marca,
        contratos.modelo,
        contratos.anio,
        contratos.color,
        contratos.precio_lista,
        marcas.nombre AS marca_actual,
        autos.modelo AS modelo_actual,
        contratos.usuario_id,
        COALESCE(usuarios.nombre_usuario, '(eliminado)')
            AS usuario,
        COALESCE(
            usuarios.nombre_completo,
            '(cuenta eliminada)'
        ) AS vendedor
    FROM contratos
    INNER JOIN clientes
        ON contratos.cliente_id = clientes.id
    INNER JOIN autos
        ON contratos.auto_id = autos.id
    INNER JOIN marcas
        ON autos.marca_id = marcas.id
    LEFT JOIN usuarios
        ON contratos.usuario_id = usuarios.id
"""


@requiere_permiso(VER_CONTRATOS)
def obtener_contratos(estado=None, texto=None):
    """
    Lista los contratos con todos los datos ya
    resueltos, que es lo que necesita el PDF.

    Devuelve filas con el contrato completo.
    """

    condiciones = []
    valores = []

    if estado:

        condiciones.append("contratos.estado = %s")

        valores.append(estado)

    if texto:

        condiciones.append("""
            (
                contratos.numero LIKE %s
                OR CONCAT(
                    clientes.nombre, ' ', clientes.apellido
                ) LIKE %s
                OR CONCAT(
                    marcas.nombre, ' ', autos.modelo
                ) LIKE %s
            )
        """)

        parametro = f"%{texto}%"

        valores.extend([
            parametro, parametro, parametro
        ])

    consulta = CONTRATO_BASE

    if condiciones:

        consulta += " WHERE " + " AND ".join(condiciones)

    consulta += " ORDER BY contratos.id DESC"

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute(consulta, tuple(valores))

    contratos = cursor.fetchall()

    cursor.close()
    conexion.close()

    return contratos


@requiere_permiso(VER_CONTRATOS)
def obtener_contrato(id_contrato):
    """
    Un contrato concreto, o None.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    consulta = CONTRATO_BASE + " WHERE contratos.id = %s"

    cursor.execute(consulta, (id_contrato,))

    contrato = cursor.fetchone()

    if contrato:
        cursor.execute("""SELECT u.vin,u.matricula FROM venta_unidades vu
            JOIN unidades_vehiculo u ON u.id=vu.unidad_id WHERE vu.venta_id=%s""",
            (contrato['venta_id'],))
        unidad = cursor.fetchone()
        contrato['vin'] = unidad['vin'] if unidad else None
        contrato['matricula'] = unidad['matricula'] if unidad else None

    cursor.close()
    conexion.close()

    return contrato


@requiere_permiso(VER_CONTRATOS)
def ventas_sin_contrato():
    """
    Ventas que aún no tienen contrato.

    Es la lista desde la que se crea: la venta
    es el punto de partida del contrato, no al
    revés.

    Contrato de columnas: id, fecha, cliente,
    vehiculo, precio. Las MISMAS que devuelve
    venta_para_contrato(), para que quien pinta la
    lista y quien abre el formulario trabajen con
    la misma forma.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = (
        DATOS_VENTA + """
        LEFT JOIN contratos
            ON contratos.venta_id = ventas.id
        WHERE contratos.id IS NULL
        ORDER BY ventas.id DESC
        """
    )

    cursor.execute(consulta)

    ventas = cursor.fetchall()

    cursor.close()
    conexion.close()

    return ventas


def venta_para_contrato(id_venta):
    """
    Los datos de UNA venta, en la misma forma que
    ventas_sin_contrato().

    Devuelve la tupla, o None si la venta no existe
    o ya tiene un contrato vivo.

    ------------------------------
    # POR QUÉ EXISTE
    # ------------------------------

    Porque el formulario de contrato se abría desde
    dos sitios con DOS formas distintas de fila:

      - desde Contratos, una fila de
        ventas_sin_contrato(): 5 columnas.
      - desde Ventas, una fila de obtener_ventas():
        6 columnas, porque esa trae el vendedor.

    El formulario desempaquetaba 5 en ambos casos, así
    que el camino de Ventas —crear el contrato al
    confirmar una venta, que es el flujo principal— salía
    con "too many values to unpack" y la aplicación se
    caía de espaldas.

    Y no se arregla con que el formulario acepte las
    dos: eso deja un constructor que adivina cuántas
    columnas le han pasado, y el día que obtener_ventas()
    devuelva otra cosa, vuelve a caer.

    Aquí solo hay una forma, y es la que necesita.

    ------------------------------
    # Y EL VENDEDOR
    # ------------------------------

    No se trae aquí a propósito: el contrato ya lo
    copia al crearse, y el detalle lo lee de
    contratos.usuario_nombre. Meterlo aquí solo
    haría que las dos consultas dejaran de parecerse.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        DATOS_VENTA + """
        WHERE ventas.id = %s
        """,
        (id_venta,)
    )

    fila = cursor.fetchone()

    if not fila:

        cursor.close()
        conexion.close()

        return None

    # ------------------------------
    # ¿YA TIENE CONTRATO VIVO?
    # ------------------------------
    # Se pregunta aparte y no con un JOIN: un
    # contrato cancelado no cuenta, y un JOIN con
    # "estado <> cancelado" devolvería la fila
    # aunque el único contrato fuera cancelado.
    #
    # Y que lo compruebe la capa de datos, y no el
    # formulario, es lo mismo que hace
    # crear_contrato(): que la garantía la pongas
    # donde la pongas, no se pueda firmar dos.

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM contratos
        WHERE venta_id = %s
          AND estado <> 'cancelado'
        """,
        (id_venta,)
    )

    if cursor.fetchone()[0]:

        cursor.close()
        conexion.close()

        return None

    cursor.close()
    conexion.close()

    return fila


@requiere_permiso(VER_CONTRATOS)
def contrato_de_venta(venta_id):
    """
    El contrato de una venta, o None si no tiene.

    El estado se filtra aparte: uno cancelado no
    impide rehacer el contrato, así que la
    comprobación que busca "algo que bloquee"
    tiene que mirar este campo.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    consulta = CONTRATO_BASE + " WHERE contratos.venta_id = %s"

    cursor.execute(consulta, (venta_id,))

    contrato = cursor.fetchone()

    cursor.close()
    conexion.close()

    return contrato


@requiere_permiso(VER_CONTRATOS)
def venta_bloqueada_por_contrato(venta_id):
    """
    Número del contrato que impide anular una
    venta, o None si no hay ninguno.

    Un contrato cancelado no bloquea: no
    surte efecto y se puede rehacer.
    """

    contrato = contrato_de_venta(venta_id)

    if contrato and contrato["estado"] != "cancelado":

        return contrato["numero"]

    return None


# ==========================================
# CREAR
# ==========================================

@requiere_permiso(CREAR_CONTRATOS)
def crear_contrato(
    venta_id,
    forma_pago,
    anticipo=0,
    cantidad_cuotas=0,
    observaciones=None,
    estado=ESTADO_INICIAL,
    saldo_financiado=None,
    tasa_interes=0,
    periodicidad=None,
    primer_vencimiento=None,
    gastos_administrativos=0,
    retencion=0,
    retencion_monto=0,
    clausulas=None,
    moneda=None,
    fecha_financiacion=None
):
    """
    Crea el contrato de una venta.

    Los datos de cliente, vehículo, usuario y
    precio se COPIAN de la venta: el contrato
    es el documento que firmó el cliente y no
    puede cambiar solo porque alguien edite el
    vehículo después.

    Lo mismo con el vehículo: se guarda la marca,
    el modelo, el año, el color y el precio de
    lista TAL COMO ESTÁN al firmar, y de ahí en
    adelante se leen de ahí y no de un JOIN. Sin
    esa fotografía, corregir el precio de un auto
    cambiaría el contrato ya firmado por el
    cliente.

    Y las condiciones económicas se congelan aquí:
    saldo financiado, tasa, gastos, retención,
    periodicidad, primer vencimiento, moneda y
    cláusulas. Un contrato firmado dice lo que
    decía, aunque alguien toque los valores de los
    que se calculó.

    Devuelve (id_contrato, numero) o
    (None, motivo).

    ------------------------------
    LO QUE NO SE CALCULA AQUÍ
    ------------------------------
    Las cuotas NO se generan aquí. Se generan con
    generar_cronograma() (database/financiera.py),
    que es la única que sabe repartir un total en
    cuotas sin que la última se lleve el residuo.

    Y por eso el contrato se puede firmar con
    "12 cuotas" y quedarse sin cronograma: la
    cartera avisa de eso y el detalle ofrece
    generarlo. Meterlo en la misma transacción
    dejaría un contrato a medias si el reparto
    fallara, y un contrato sin cronograma se
    arregla; un contrato con la mitad de las
    cuotas, no.
    """

    # ------------------------------
    # EL DINERO, EN DECIMAL
    # ------------------------------
    # Antes de nada, porque el precio sale de la base
    # como Decimal y el anticipo suele llegar como
    # float desde un formulario: Decimal menos float
    # revienta con un TypeError que no dice nada
    # sobre el contrato.
    #
    # Se normaliza aquí y no en quien llama porque hay
    # dos llamadas distintas (el formulario y quien
    # use la función desde un script) y convertirlas
    # en un sitio y no en el otro es como aparece un
    # bug que solo se da por un camino.

    anticipo, motivo = _a_importe(anticipo, "El anticipo")

    if anticipo is None:

        return (None, motivo)

    if saldo_financiado is not None:

        saldo_financiado, motivo = _a_importe(
            saldo_financiado, "El saldo financiado"
        )

        if saldo_financiado is None:

            return (None, motivo)

    # ------------------------------
    # COMPROBACIONES
    # ------------------------------

    if estado not in ESTADOS:

        return (
            None,
            f"Estado '{estado}' no válido."
        )

    if forma_pago not in FORMAS_PAGO:

        return (
            None,
            f"Forma de pago '{forma_pago}' no válida."
        )

    if anticipo < 0:

        return (
            None,
            "El anticipo no puede ser negativo."
        )

    # En contado el pago es completo: no hay
    # anticipo ni cuotas que repartir. El formulario
    # lo avisa, pero un contrato guardado con
    # "Contado" y 12 cuotas imprimiría una
    # contradicción en un documento firmado.

    if forma_pago == "Contado" and (
        anticipo > 0 or cantidad_cuotas > 0
    ):

        return (
            None,
            "En contado no hay anticipo ni "
            "cuotas: el pago es completo."
        )

    # ------------------------------
    # LO QUE SE FINANCIARÍA
    # ------------------------------
    # Antes de abrir la conexión, porque solo
    # hacen falta los números que ya trae quien
    # llama. Si alguno no cuadra, se devuelve sin
    # haber tocado nada en la base.

    ajustes = _validar_financiacion(
        cantidad_cuotas=cantidad_cuotas,
        tasa_interes=tasa_interes,
        periodicidad=periodicidad,
        primer_vencimiento=primer_vencimiento,
        gastos_administrativos=gastos_administrativos,
        retencion=retencion,
        retencion_monto=retencion_monto
    )

    if isinstance(ajustes, str):

        return (None, ajustes)

    # ------------------------------
    # EL SALDO, SI NO SE DIJO
    # ------------------------------
    # No aquí: sale del precio de la VENTA, que se
    # lee dentro de la transacción, y no de lo que
    # trae quien llama.

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:

        conexion.start_transaction()

        # ------------------------------
        # 1. LA VENTA TIENE QUE EXISTIR
        # ------------------------------

        consulta_venta = """
            SELECT
                ventas.id,
                ventas.cliente_id,
                ventas.auto_id,
                ventas.precio,
                ventas.fecha
            FROM ventas
            WHERE ventas.id = %s
            FOR UPDATE
        """

        cursor.execute(consulta_venta, (venta_id,))

        venta = cursor.fetchone()

        if not venta:

            conexion.rollback()

            return (
                None,
                "La venta indicada no existe."
            )

        precio = Decimal(str(venta["precio"]))

        # ------------------------------
        # 1b. EL ANTICIPO NO PUEDE PASARSE
        # ------------------------------
        # El formulario ya avisa de esto, pero el
        # contrato es un documento legal y aquí no
        # puede quedar guardado uno con un anticipo
        # mayor que el precio: el PDF imprimiría una
        # cuota en negativo y el saldo no cuadraría.
        #
        # Solo se rechaza lo que el formulario ya
        # rechaza, así que ninguna vía que antes
        # funcionaba deja de funcionar.

        if anticipo > precio:

            conexion.rollback()

            return (
                None,
                "El anticipo no puede ser mayor que "
                "el precio de la venta."
            )

        # ------------------------------
        # 1c. EL SALDO FINANCIADO, AHORA
        # QUE SE SABE EL PRECIO
        # ------------------------------
        # El saldo sale del precio de la VENTA, no
        # del de lista, y no del usuario: si no se
        # dice, es la resta, que es lo que se firma
        # el 99 % de las veces. Si se dice, se usa el
        # que se dice, porque hay financieras que
        # financian el precio de lista y el cliente
        # pone la diferencia.
        #
        # Y "Contado" NO financia nada. Ya se ha
        # comprobado arriba que no lleva anticipo ni
        # cuotas, así que el saldo es cero por
        # definición. Sin esta línea, una venta de
        # contado a 10.000 salía con saldo
        # financiado de 10.000 y el mensaje de que
        # faltaban las cuotas: el sistema decía que
        # estaba financiando un pago que ya se
        # había hecho entero.

        if saldo_financiado is None:

            saldo_financiado = (
                Decimal("0.00")
                if forma_pago == "Contado"
                else (
                    precio
                    - anticipo
                    - ajustes["gastos_administrativos"]
                )
            )

        if saldo_financiado < 0:

            conexion.rollback()

            return (
                None,
                "El saldo financiado no puede ser "
                "negativo: el precio menos la "
                "entrega inicial y los gastos "
                "no da negativo."
            )

        if saldo_financiado == 0 and (
            cantidad_cuotas > 0
        ):

            conexion.rollback()

            return (
                None,
                "No hay nada que financiar: el "
                "saldo es cero y no se pueden "
                "generar cuotas."
            )

        if saldo_financiado > 0 and (
            cantidad_cuotas < 1
        ):

            conexion.rollback()

            return (
                None,
                "Si queda saldo por financiar, "
                "hay que decir en cuántas cuotas "
                "se paga."
            )

        # ------------------------------
        # 1d. EL DÍA DE VENCIMIENTO
        # ------------------------------
        # Se guarda aparte porque el cronograma
        # avanza por meses de calendario con un día
        # de referencia: sin el, cada cuota caería
        # el día del mes en que se generó, y un
        # crédito firmado el día 31 se movería al
        # 28 para siempre.

        dia_vencimiento = None

        if primer_vencimiento:

            dia_vencimiento = int(primer_vencimiento.day)

        # ------------------------------
        # 1e. LA MONEDA
        # ------------------------------
        # Si no se dice, la que hay configurada. El
        # importe y la moneda van juntos: un contrato
        # en dólares con el símbolo de pesos puesto al
        # día siguiente es un documento que no se
        # puede defender.

        if moneda is None:

            from utils.moneda import config_actual

            moneda = config_actual()["codigo"]

        # ------------------------------
        # 2. NO HABER CONTRATO VIVO
        # ------------------------------
        # Un contrato cancelado no surte efecto,
        # así que sí permite rehacerse.

        consulta_existente = """
            SELECT numero, estado
            FROM contratos
            WHERE venta_id = %s
        """

        cursor.execute(consulta_existente, (venta_id,))

        existente = cursor.fetchone()

        if existente and existente["estado"] != "cancelado":

            conexion.rollback()

            return (
                None,
                f"La venta ya tiene el contrato "
                f"{existente['numero']}. Si necesita "
                f"rehacerlo, cancélelo primero."
            )

        # ------------------------------
        # 3. REHACER UNO CANCELADO
        # ------------------------------
        # Las cuotas y los pagos cuelgan del
        # contrato. Un contrato cancelado con dinero
        # cobrado no se puede borrar sin más: primero
        # hay que deshacer los pagos, que es una
        # operación aparte y con su rastro. Si quedara
        # alguno, el DELETE de abajo reventaría con la
        # clave foránea y el motivo sería un error
        # de MySQL en vez de una explicación.

        cursor.execute(
            """
            SELECT COUNT(*) AS pagos_vigentes
            FROM pagos
            WHERE venta_id = %s
              AND estado = 'convalidado'
            """,
            (venta_id,)
        )

        if cursor.fetchone()["pagos_vigentes"]:

            conexion.rollback()

            return (
                None,
                "La venta tiene pagos registrados. "
                "Para rehacer el contrato hay que "
                "anularlos antes: no se puede borrar "
                "un cobro del historial."
            )

        cursor.execute(
            """
            SELECT id
            FROM contratos
            WHERE venta_id = %s
              AND estado = 'cancelado'
            """,
            (venta_id,)
        )

        para_borrar = cursor.fetchall()

        for fila in para_borrar:

            cursor.execute(
                "DELETE FROM cuotas WHERE contrato_id = %s",
                (fila["id"],)
            )

            cursor.execute(
                "DELETE FROM garantias WHERE contrato_id = %s",
                (fila["id"],)
            )

            cursor.execute(
                "DELETE FROM convenios WHERE contrato_id = %s",
                (fila["id"],)
            )

            cursor.execute(
                "DELETE FROM contratos WHERE id = %s",
                (fila["id"],)
            )

        # ------------------------------
        # 3b. EL VEHÍCULO, DE FOTOGRAFÍA
        # ------------------------------

        cursor.execute(
            """
            SELECT
                marcas.nombre AS marca,
                autos.modelo,
                autos.anio,
                autos.color,
                autos.precio
            FROM autos
            INNER JOIN marcas
                ON autos.marca_id = marcas.id
            WHERE autos.id = %s
            """,
            (venta["auto_id"],)
        )

        auto = cursor.fetchone()

        if not auto:

            conexion.rollback()

            return (
                None,
                "El vehículo de la venta no existe."
            )

        # ------------------------------
        # 4. INSERTAR
        # ------------------------------
        # "numero" va NULL a propósito: se
        # calcula con el id que MySQL acaba de
        # asignar y se escribe en el mismo paso.
        # Así nunca puede colisionar con otro
        # contrato creado a la vez.

        usuario = modulo_sesion.obtener_sesion()

        consulta_insertar = """
            INSERT INTO contratos
            (
                numero,
                venta_id,
                cliente_id,
                auto_id,
                usuario_id,
                fecha,
                precio_venta,
                forma_pago,
                anticipo,
                cantidad_cuotas,
                observaciones,
                estado,
                saldo_financiado,
                tasa_interes,
                gastos_administrativos,
                periodicidad,
                primer_vencimiento,
                dia_vencimiento,
                moneda,
                retencion,
                retencion_monto,
                fecha_financiacion,
                clausulas,
                marca,
                modelo,
                anio,
                color,
                precio_lista
            )
            VALUES (
                NULL,
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s
            )
        """

        valores = (
            venta_id,
            venta["cliente_id"],
            venta["auto_id"],
            usuario.id_usuario,
            venta["fecha"],
            precio,
            forma_pago,
            anticipo,
            cantidad_cuotas,
            observaciones,
            estado,
            saldo_financiado,
            ajustes["tasa_interes"],
            ajustes["gastos_administrativos"],
            ajustes["periodicidad"],
            primer_vencimiento,
            dia_vencimiento,
            moneda,
            ajustes["retencion"],
            ajustes["retencion_monto"],
            fecha_financiacion or (
                venta["fecha"] if saldo_financiado > 0
                else None
            ),
            clausulas,
            auto["marca"],
            auto["modelo"],
            auto["anio"],
            auto["color"],
            auto["precio"]
        )

        cursor.execute(consulta_insertar, valores)

        id_contrato = cursor.lastrowid

        # ------------------------------
        # 5. NÚMERO
        # ------------------------------

        numero = formatear_numero(
            id_contrato, venta["fecha"].year
        )

        cursor.execute(
            "UPDATE contratos SET numero = %s WHERE id = %s",
            (numero, id_contrato)
        )

        conexion.commit()

        cursor.close()
        conexion.close()

        # ------------------------------
        # 6. RASTRO
        # ------------------------------
        # Con el valor anterior y el nuevo de lo que
        # se pacta. Un contrato firmado sin rastro de
        # sus condiciones económicas no se puede
        # defender después.

        if saldo_financiado > 0:

            registrar_cambio(
                "financiera",
                "FINANCIACION",
                f"Contrato {numero} firmado con "
                f"financiación de {formato_dinero(saldo_financiado)}"
                + (
                    f" en {cantidad_cuotas} cuotas "
                    f"{ajustes['periodicidad']}es desde "
                    f"{primer_vencimiento}"
                    if primer_vencimiento
                    else ""
                )
                + (
                    f" al {formato_decimal(ajustes['tasa_interes'])} % "
                    "de interés anual"
                    if ajustes["tasa_interes"]
                    else " sin interés"
                ),
                valor_anterior="pago de contado",
                valor_nuevo=(
                    f"saldo financiado "
                    f"{formato_dinero(saldo_financiado)}"
                ),
                referencia=numero
            )

        registrar_accion(
            "contratos",
            "CREAR",
            f"Contrato {numero} creado para la "
            f"venta {venta_id}"
        )

        return id_contrato, numero

    except mysql.connector.Error as error:

        conexion.rollback()

        cursor.close()
        conexion.close()

        return (
            None,
            traducir_error(error).mensaje
        )


# ==========================================
# CAMBIAR ESTADO
# ==========================================

@conexiones_libres
@requiere_permiso(GESTIONAR_CONTRATOS)
def cambiar_estado(id_contrato, estado):
    """
    Pasa el contrato a otro estado.

    Devuelve (True, "") o (False, motivo).
    """

    if estado not in ESTADOS:

        return (
            False,
            f"Estado '{estado}' no válido."
        )

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    consulta_actual = """
        SELECT numero, estado
        FROM contratos
        WHERE id = %s
    """

    cursor.execute(consulta_actual, (id_contrato,))

    contrato = cursor.fetchone()

    cursor.close()
    conexion.close()

    if not contrato:

        return (False, "El contrato no existe.")

    actual = contrato["estado"]

    if actual == estado:

        return (
            False,
            "El contrato ya está en ese estado."
        )

    permitidos = TRANSICIONES.get(actual, [])

    if estado not in permitidos:

        return (
            False,
            f"No se puede pasar de "
            f"'{ESTADOS[actual]}' a "
            f"'{ESTADOS[estado]}'."
        )

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        "UPDATE contratos SET estado = %s WHERE id = %s",
        (estado, id_contrato)
    )

    conexion.commit()

    cursor.close()
    conexion.close()

    registrar_accion(
        "contratos",
        "MODIFICAR",
        f"Contrato {contrato['numero']}: "
        f"{ESTADOS[actual]} -> {ESTADOS[estado]}"
    )

    return True, ""


# ==========================================
# PDF
# ==========================================

@conexiones_libres
@requiere_permiso(VER_CONTRATOS)
def registrar_pdf(id_contrato, ruta_relativa):
    """
    Anota dónde quedó el PDF generado.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        "UPDATE contratos SET archivo_pdf = %s "
        "WHERE id = %s",
        (ruta_relativa, id_contrato)
    )

    conexion.commit()

    cursor.close()
    conexion.close()


# ==========================================
# ELIMINAR
# ==========================================

def contrato_bloqueado_por(id_contrato):
    """
    Qué impide borrar un contrato, o None si no hay
    nada.

    ------------------------------
    # POR QUÉ SE COMPRUEBA ANTES
    # ------------------------------

    Las claves foráneas de `cuotas`, `pagos`,
    `garantias` y `convenios` están en ON DELETE
    RESTRICT: MySQL impide el borrado, pero lo
    hace saltando una excepción de la capa de
    datos. La pantalla recibía entonces un error de
    base de datos en vez de una frase, y el rastro
    lleno de "Fallo inesperado" por algo que el
    usuario puede evitar.

    Es el mismo motivo por el que `eliminar_venta()`
    consulta `venta_bloqueada_por_contrato()` y
    `venta_bloqueada_por_pagos()` antes de borrar.

    ------------------------------
    # QUÉ SE ENSEÑA
    # ------------------------------

    El motivo, no un sí o un no pelado: "tiene 30
    cuotas" dice qué hacer (anular el cobro o
    cancelar el contrato) y "no se puede" solo
    dice que no.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    # (tabla, singular, plural, que hay que hacer)

    bloqueos = [
        (
            "cuotas",
            "una cuota del cronograma",
            "cuotas del cronograma",
            "Cancela el contrato en vez de borrarlo: "
            "así queda constancia de lo que se cobró."
        ),
        (
            "pagos",
            "un pago registrado",
            "pagos registrados",
            "Anula el cobro equivocado y después "
            "ya se podrá borrar."
        ),
        (
            "garantias",
            "una garantía o un gravamen",
            "garantías o gravámenes",
            "Libera la garantía antes de borrar."
        ),
        (
            "convenios",
            "un convenio de pago",
            "convenios de pago",
            "Resuelve el convenio antes de borrar."
        )
    ]

    for tabla, uno, varios, consejo in bloqueos:

        # El nombre de la tabla va en la consulta, no en
        # un valor: es una constante de esta lista, nunca
        # viene de fuera.

        cursor.execute(
            f"SELECT COUNT(*) FROM {tabla} "
            "WHERE contrato_id = %s",
            (id_contrato,)
        )

        total = cursor.fetchone()[0]

        if not total:

            continue

        cursor.close()
        conexion.close()

        return (
            f"El contrato tiene {total} "
            f"{uno if total == 1 else varios} "
            f"y no se puede borrar. {consejo}"
        )

    cursor.close()
    conexion.close()

    return None


@conexiones_libres
@requiere_permiso(GESTIONAR_CONTRATOS)
def eliminar_contrato(id_contrato):
    """
    Borrado físico. Lo normal es cancelar, que
    conserva el documento.

    Devuelve (True, "") o (False, motivo).
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute(
        "SELECT numero FROM contratos WHERE id = %s",
        (id_contrato,)
    )

    contrato = cursor.fetchone()

    cursor.close()
    conexion.close()

    if not contrato:

        return (False, "El contrato no existe.")

    # ------------------------------
    # LO QUE DEPENDE DE EL
    # ------------------------------

    bloqueo = contrato_bloqueado_por(id_contrato)

    if bloqueo:

        return (False, bloqueo)

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    # ------------------------------
    # Y SI ENTRE TANTO ALGO SE
    # CUELGA, NO SUBE LA EXCEPCION
    # ------------------------------

    # La comprobación de arriba y el borrado no son
    # atómicos: entre los dos, otro usuario puede
    # registrar un cobro. Por eso el DELETE tambien
    # cae al suelo con una frase y no con un error de
    # MySQL.

    try:

        cursor.execute(
            "DELETE FROM contratos WHERE id = %s",
            (id_contrato,)
        )

        conexion.commit()

    except mysql.connector.IntegrityError:

        conexion.rollback()

        cursor.close()
        conexion.close()

        return (
            False,
            "El contrato tiene movimientos "
            "asociados y no se puede borrar. "
            "Consúltalo de nuevo: alguien pudo "
            "registrar un cobro mientras lo "
            "borrabas."
        )

    cursor.close()
    conexion.close()

    registrar_accion(
        "contratos",
        "ELIMINAR",
        f"Contrato {contrato['numero']} eliminado"
    )

    return True, ""
