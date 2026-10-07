# ==========================================
# PAGOS DE UNA VENTA
# ==========================================
# Cada entrada de dinero que entra por una venta.
#
# Un contrato dice QUÉ se debe pagar; esta tabla
# dice QUÉ se ha pagado. Son cosas distintas y no
# se mezclan: el contrato se firma una vez, los
# pagos se registran uno a uno.
#
# Un pago NO se edita, igual que una venta o un
# contrato: es un hecho económico. Si está mal,
# se elimina y se vuelve a registrar. Queda el
# rastro en auditoria.
#
# Un pago tampoco se "anula con signo contrario":
# se borra. Un importe negativo aquí sería
# imposible de explicar a un cliente y haría que
# el saldo pareciera un error de cálculo.


from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_HALF_UP
)

from database.conexion import (
    obtener_conexion,
    conexiones_libres
)

from database.auditoria import registrar_accion

from utils.moneda import formato_dinero

import sesion as modulo_sesion

from permisos import (
    requiere_permiso,
    REGISTRAR_VENTAS,
    GESTIONAR_VENTAS
)


# =============================
# FORMAS DE PAGO
# =============================
# Etiquetas, no códigos: es lo que ve el usuario y
# lo que se guarda. La capa de datos valida contra
# esta lista para que no entren valores inventados
# que luego el PDF y los reportes no sabrían
# pintar.

# Dos decimales: es lo que guarda pagos.importe
# (DECIMAL(10,2)). Ver registrar_pago().
DECIMALES = Decimal("0.01")


FORMAS_PAGO = [
    "Efectivo",
    "Transferencia bancaria",
    "Tarjeta de débito",
    "Tarjeta de crédito",
    "Cheque",
    "Financiación de terceros"
]


# =============================
# LISTAR
# =============================

def obtener_pagos(venta_id):
    """
    Pagos de una venta, del más reciente al más
    antiguo. Contrato de columnas:

        id, fecha, importe, forma, referencia,
        concepto, usuario_nombre

    "usuario_nombre" puede ser None en pagos muy
    antiguos: quien lo pinte debe poner algo
    legible en su lugar.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            id,
            fecha,
            importe,
            forma,
            referencia,
            concepto,
            usuario_nombre
        FROM pagos
        WHERE venta_id = %s
        ORDER BY fecha DESC, id DESC
    """

    cursor.execute(consulta, (venta_id,))

    filas = cursor.fetchall()

    cursor.close()
    conexion.close()

    return filas


# ==========================================
# LOS MISMOS PAGOS, CON MÁS COLUMNAS
# ==========================================

def obtener_pagos_detalle(venta_id):
    """
    Los pagos de una venta como diccionarios, con el
    estado de anulación, el recibo y a qué cuota se
    imputó cada uno.

    No sustituye a obtener_pagos(): aquella es la
    consulta del listado, con siete columnas y como
    tuplas. Esta es para las pantallas que necesitan
    saber MÁS de cada pago, sobre todo si está
    anulado y por qué.

    Existe porque la alternativa era que el detalle
    del contrato escribiera su propia consulta. Y
    una consulta escrita en la interfaz se queda
    desfasada sin avisar: cuando se añadió
    pagos.cuota_id, la copia sigue preguntando por
    las siete columnas de antes y funciona, pero
    muestra todos los pagos juntos sin poder decir
    cuál cubrió qué cuota. El fallo es silencioso,
    que es la peor clase.

    Contrato de columnas: id, fecha, importe, forma,
    referencia, concepto, usuario_nombre, recibo,
    cuota_id, numero_cuota, estado, anulado_motivo,
    anulado_usuario, anulado_fecha.

    "numero_cuota" es None en un pago que no se
    imputó a ninguna cuota (la entrega inicial, un
    pago a cuenta), y quien lo pinte tiene que
    distinguirlo de la cuota 0.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            pagos.id,
            pagos.fecha,
            pagos.importe,
            pagos.forma,
            pagos.referencia,
            pagos.concepto,
            pagos.usuario_nombre,
            pagos.recibo,
            pagos.cuota_id,
            cuotas.numero AS numero_cuota,
            pagos.estado,
            pagos.anulado_motivo,
            pagos.anulado_usuario,
            pagos.anulado_fecha
        FROM pagos
        LEFT JOIN cuotas
            ON pagos.cuota_id = cuotas.id
        WHERE pagos.venta_id = %s
        ORDER BY pagos.fecha DESC, pagos.id DESC
        """,
        (venta_id,)
    )

    pagos = cursor.fetchall()

    cursor.close()
    conexion.close()

    return pagos


def saldo_venta(venta_id):
    """
    Devuelve (precio, pagado, saldo) de la venta.

    Se calcula con SUM() en SQL y no trayendo los
    pagos a Python para sumarlos aquí: es una ida
    y vuelta menos y no depende de que elDecimal
    se sume igual en los dos sitios.

    ------------------------------
    # SOLO CUENTA LO CONVALIDADO
    # ------------------------------

    Un pago NO se borra: se anula. Un anulado sigue
    en la tabla con estado='anulado', y si la suma no
    lo excluye el saldo de la venta BAJA igual: la
    venta aparece pagada con dinero que se anuló,
    que es justo la cifra que el cajero mira antes de
    decir que el auto está pagado.

    El filtro va en el SUM y no en el WHERE a proposito:
    un WHERE sobre la tabla unida convierte el LEFT
    JOIN en uno interior y las ventas sin pagos
    desaparecerian en vez de salir con pagado 0.

    Todas las demas sumas de la aplicacion (cobranza,
    garantias, fichas, financiera) filtran por estado.
    Esta era la unica que se habia quedado fuera, y por
    eso no se veia al comparar dos pantallas.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    consulta = """
        SELECT
            ventas.precio AS precio,
            COALESCE(
                SUM(
                    CASE
                        WHEN pagos.estado = 'convalidado'
                        THEN pagos.importe
                    END
                ),
                0
            ) AS pagado
        FROM ventas
        LEFT JOIN pagos
            ON pagos.venta_id = ventas.id
        WHERE ventas.id = %s
        GROUP BY ventas.id, ventas.precio
    """

    cursor.execute(consulta, (venta_id,))

    fila = cursor.fetchone()

    cursor.close()
    conexion.close()

    if not fila:

        return None

    precio = fila["precio"]
    pagado = fila["pagado"]

    return precio, pagado, precio - pagado


def pagos_de_venta(venta_id):
    """
    Cuántos pagos tiene la venta. Se usa para
    decidir si la venta se puede anular, igual que
    se hace con el contrato.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM pagos
        WHERE venta_id = %s
        """,
        (venta_id,)
    )

    total = cursor.fetchone()[0]

    cursor.close()
    conexion.close()

    return total


def venta_bloqueada_por_pagos(venta_id):
    """
    Devuelve (True, numero_de_pagos) si la venta
    ya tiene dinero registrado, o (False, 0).

    Es el mismo patrón que venta_bloqueada_por_contrato:
    devuelve el dato que hay que enseñar, no solo un
    booleano.
    """

    total = pagos_de_venta(venta_id)

    if total > 0:

        return True, total

    return False, 0


# =============================
# REGISTRAR
# =============================

@conexiones_libres
@requiere_permiso(REGISTRAR_VENTAS)
def registrar_pago(
    venta_id,
    importe,
    fecha,
    forma,
    referencia=None,
    concepto=None
):
    """
    Registra un pago.

    Devuelve (id_pago, "") o (None, motivo).

    El importe no puede pasar del saldo: si lo
    hiciera, la venta quedaría con saldo negativo
    y nadie sabría qué hacer con eso. La
    comprobación va DENTRO de la transacción, con
    la venta bloqueada, porque si dos personas
    cobran a la vez sin bloquearse, las dos pasarían
    la comprobación y el saldo se iría al
    negativo.
    """

    # ------------------------------
    # COMPROBACIONES BARATAS
    # ------------------------------
    # Estas no necesitan transacción: no dependen
    # de lo que haya en la base y así se evita
    # abrir una conexión para nada.

    if forma not in FORMAS_PAGO:

        return (
            None,
            f"Forma de pago '{forma}' no válida."
        )

    # ------------------------------
    # EL IMPORTE TIENE QUE PODER GUARDARSE
    # ------------------------------
    # pagos.importe es DECIMAL(10,2): dos decimales.
    #
    # Un importe con más se guardaría redondeado, y
    # el dinero se perdería sin avisar: un pago de
    # 0.004 se guardaría como 0.00 y el saldo no se
    # movería.
    #
    # Con un margen de tolerancia en la comparación
    # del saldo, eso era un agujero sin fondo: el
    # pago de medio céntimo pasaba la comprobación,
    # se guardaba como cero, el saldo no cambiaba y
    # el siguiente medio céntimo volvía a pasar. Se
    # acumulaban filas de 0.00 que no.moveían nada.
    #
    # Por eso se rechaza en vez de redondear: es
    # preferible un "el importe no puede tener más
    # de dos decimales" a un cobro que se pierde.
    # El formulario usa QDoubleSpinBox con dos
    # decimales, así que desde la interfaz es
    # imposible llegar aquí.

    try:

        decimal_importe = Decimal(str(importe))

    except (InvalidOperation, TypeError, ValueError):

        return (
            None,
            "El importe no es un número."
        )

    if not decimal_importe.is_finite():

        return (None, "El importe no es un número.")

    redondeado = decimal_importe.quantize(
        DECIMALES,
        rounding=ROUND_HALF_UP
    )

    if redondeado != decimal_importe:

        return (
            None,
            "El importe no puede tener más de dos "
            "decimales."
        )

    importe = redondeado

    if importe <= 0:

        return (
            None,
            "El importe tiene que ser mayor que cero."
        )

    if not fecha:

        return (None, "Falta la fecha del pago.")

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:

        conexion.start_transaction()

        # ------------------------------
        # 1. LA VENTA TIENE QUE EXISTIR
        # ------------------------------

        cursor.execute(
            """
            SELECT id, precio
            FROM ventas
            WHERE id = %s
            FOR UPDATE
            """,
            (venta_id,)
        )

        venta = cursor.fetchone()

        if not venta:

            conexion.rollback()

            return (
                None,
                "La venta indicada no existe."
            )

        # ------------------------------
        # 2. EL SALDO
        # ------------------------------

        cursor.execute(
            """
            SELECT COALESCE(SUM(importe), 0) AS pagado
            FROM pagos
            WHERE venta_id = %s
            """,
            (venta_id,)
        )

        pagado = Decimal(
            str(cursor.fetchone()["pagado"])
        )

        # Todo en Decimal, no en float: precio y
        # pagado son DECIMAL(10,2) en la base, así
        # que el saldo es siempre un múltiplo de un
        # céntimo y se puede comparar con exactitud.
        #
        # Con float, 0.1 + 0.2 no es 0.3 y un saldo
        # que "es cero" puede salir 0.0000001. Con
        # un margen de tolerancia para tapar eso, un
        # pago de medio céntimo pasaba la
        # comprobación, se guardaba como 0.00 (el
        # DECIMAL redondea) y el saldo no se movía:
        # el siguiente volvía a pasar, y así hasta
        # que se llenaba la tabla de pagos de cero.
        #
        # Sin margen y en Decimal, no hay sitio por
        # donde se cuele un céntimo de más. Y el
        # residuo que deja dividir 20.000 en 7
        # cuotas (2 céntimos) sí se puede cobrar,
        # porque 0.02 es un importe representable.

        precio_venta = Decimal(str(venta["precio"]))

        saldo = precio_venta - pagado

        if importe > saldo:

            conexion.rollback()

            return (
                None,
                "El importe es mayor que el saldo "
                f"pendiente ({formato_dinero(saldo)})."
            )

        # ------------------------------
        # 3. EL CONTRATO, SI LO HAY
        # ------------------------------
        # No es obligatorio: una venta en efectivo
        # puede cobrarse sin firmar contrato. Pero si
        # existe, se guarda para poder consultarlo
        # sin buscarlo.

        cursor.execute(
            """
            SELECT id
            FROM contratos
            WHERE venta_id = %s
                AND estado <> 'cancelado'
            """,
            (venta_id,)
        )

        contrato = cursor.fetchone()

        contrato_id = contrato["id"] if contrato else None

        # ------------------------------
        # 4. INSERTAR
        # ------------------------------

        usuario = modulo_sesion.obtener_sesion()

        cursor.execute(
            """
            INSERT INTO pagos
            (
                venta_id, contrato_id, fecha, importe,
                forma, referencia, concepto,
                usuario_id, usuario_nombre
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                venta_id,
                contrato_id,
                fecha,
                importe,
                forma,
                referencia or None,
                concepto or None,
                usuario.id_usuario,
                usuario.nombre_usuario
            )
        )

        id_pago = cursor.lastrowid

        conexion.commit()

    except BaseException:

        # El rollback va en "except BaseException", no
        # solo en "except mysql.connector.Error".
        #
        # Con la versión anterior, un fallo que no
        # fuese de MySQL (un error de código al
        # construir una consulta, un TypeError, un
        # fallo de memoria) salía de la función sin
        # deshacer la transacción. El decorador
        # @conexiones_libres cerraba la conexión y al
        # cerrarla MySQL haría rollback igualmente,
        # así que no se perdía dinero... pero
        # dependía de que el cierre funcionara, y
        # sobre un pool de conexiones podría no
        # ser inmediato.
        #
        # Con rollback explícito, la garantía no
        # depende de nada más.

        conexion.rollback()

        cursor.close()
        conexion.close()

        raise

    cursor.close()
    conexion.close()

    # Después del commit: si la transacción se
    # revirtiese, el rastro mentiría.

    registrar_accion(
        "pagos",
        "PAGO",
        f"Pago de {formato_dinero(importe)} en la venta "
        f"{venta_id} por {forma}"
    )

    return id_pago, ""


# =============================
# ELIMINAR
# =============================

@conexiones_libres
@requiere_permiso(GESTIONAR_VENTAS)
def eliminar_pago(id_pago):
    """
    Borra un pago mal registrado.

    Solo el administrador: es un movimiento de
    dinero, y deshacerlo debería ser raro y
    consciente.

    Devuelve (True, "") o (False, motivo).

    ------------------------------
    # UN PAGO DE CUOTA NO SE BORRA
    # ------------------------------

    Si el pago esta imputado a una cuota, al pagarlo
    se le resto el importe a `cuotas.saldo`. Borrar la
    fila sin devolver ese importe deja la cuota con un
    saldo mas bajo que la realidad: el dinero se fue y
    el sistema sigue creyendo que el cliente lo debe.

    Por eso aqui se rechaza y se manda al camino
    correcto, que es `anular_pago()` en
    database/financiera.py: ese si devuelve el importe
    a la cuota y recalcula su estado, dentro de la
    misma transaccion.

    Borrar queda para los pagos sueltos (cuota_id
    NULL), donde no hay nada que reconciliar.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT id, venta_id, importe, forma, cuota_id
        FROM pagos
        WHERE id = %s
        """,
        (id_pago,)
    )

    pago = cursor.fetchone()

    if not pago:

        cursor.close()
        conexion.close()

        return (False, "El pago indicado no existe.")

    if pago["cuota_id"]:

        cursor.close()
        conexion.close()

        return (
            False,
            "Este pago está asignado a una cuota y no "
            "se puede borrar: al pagarlo se le quitó el "
            "importe del saldo de esa cuota. Anúlalo "
            "desde el detalle del contrato, que es la "
            "forma de devolverlo sin descuadrar el "
            "cronograma."
        )

    cursor.execute(
        "DELETE FROM pagos WHERE id = %s",
        (id_pago,)
    )

    conexion.commit()

    cursor.close()
    conexion.close()

    registrar_accion(
        "pagos",
        "ELIMINAR",
        f"Pago de {formato_dinero(float(pago['importe']))} "
        f"eliminado de la venta {pago['venta_id']}"
    )

    return (True, "")


# =============================
# REPORTE
# =============================

def obtener_cobros(desde=None, hasta=None):
    """
    Cobros por periodo, para el reporte.

    Devuelve el total cobrado y cuántas entradas
    hubo. No aplica permiso: es una lectura y los
    dos roles leen. Quien quiera verlo en pantalla
    lo decide la vista.

    ------------------------------
    # LO ANULADO NO ES COBRO
    # ------------------------------

    El filtro de estado va SIEMPRE, aunque no se
    pida ningun periodo: un reporte que suma lo
    anulado enseña dinero que nunca se cobró, y es
    la clase de cifra que se descubre comparando el
    banco.
    """

    condiciones = ["estado = 'convalidado'"]
    valores = []

    if desde:
        condiciones.append("fecha >= %s")
        valores.append(desde)

    if hasta:
        condiciones.append("fecha <= %s")
        valores.append(hasta)

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    consulta = (
        "SELECT COUNT(*) AS entradas, "
        "COALESCE(SUM(importe), 0) AS total "
        "FROM pagos"
    )

    if condiciones:
        consulta += " WHERE " + " AND ".join(condiciones)

    cursor.execute(consulta, tuple(valores))

    fila = cursor.fetchone()

    cursor.close()
    conexion.close()

    return fila["entradas"], fila["total"]
