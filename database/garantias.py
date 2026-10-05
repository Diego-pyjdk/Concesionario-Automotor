# ==========================================
# GARANTÍAS Y GRAVÁMENES
# ==========================================
# Qué respalda una venta financiada y en qué
# estado está la gestión de esa garantía.
#
#
# ----------------------------------------------------
# LO QUE ESTE MÓDULO NO ES
# ----------------------------------------------------
# Un gravamen es una INSCRIPCIÓN REGISTRAL. Su
# procedencia, sus datos, su forma y su rato de
# eficacia dependen de lo que establezca el Registro
# Público y de lo que corresponda legalmente en cada
# caso.
#
# Esta tabla REGISTRA lo que el concesionario
# afirma. No certifica nada ante el Registro Público.
# Que aquí diga "inscrita" no la inscribe allí, y una
# fecha de inscripción escrita a mano no es una
# inscripción.
#
# Por eso todo lo que este módulo guarda lleva, en
# su sitio, la advertencia de que hay que validarlo
# con el abogado y el escribano correspondientes. Y
# por eso NO hay ninguna función que genere el
# documento registral, ni que calcule el importe de la
# garantía, ni que decida si una garantía es
# suficiente: eso no lo puede decidir un programa.
#
# Lo que sí hace, y es útil de verdad:
#
#   1. Dejar constancia de qué se ofreció como
#      respaldo y de qué se está haciendo con ello.
#
#   2. Avisar en la cartera cuando una venta
#      financiada vencida tiene una garantía sin
#      liberar, que es cuando la garantía deja de
#      proteger al concesionario.
#
#   3. Impedir que se dé por liberada una garantía de
#      un contrato que aún tiene saldo pendiente.


from datetime import date
from decimal import Decimal

import mysql.connector

from database.auditoria import registrar_cambio

from database.conexion import (
    conexiones_libres,
    obtener_conexion
)

from errores import ErrorBaseDatos

from permisos import (
    requiere_permiso,
    VER_CONTRATOS,
    GESTIONAR_CONTRATOS
)


# ==========================================
# CATÁLOGOS
# ==========================================
# El código es estable; el texto sale de aquí al
# mostrarlo.

TIPOS = {
    "tipo_mora": "Titular del bien (tipo de mora)",
    "prenda": "Prenda sin desapoderamiento",
    "fiacion": "Fijación",
    "hipoteca": "Hipoteca",
    "aval": "Aval personal o de tercero",
    "garantia_tercero": "Garante tercero",
    "seguro": "Seguro",
    "otro": "Otro"
}

ESTADOS = {
    "pendiente": "Pendiente",
    "inscrita": "Inscrita",
    "liberada": "Liberada",
    "rechazada": "Rechazada"
}

# Estados desde los que se puede pasar a "liberada".
#
# Liberar una garantía es el paso con consecuencias
# serias: es lo que devuelve al cliente su garantía.
# Desde "rechazada" no tiene sentido liberar (nunca
# llegó a estar), y desde "liberada" no tiene sentido
# volver a liberar.

TRANSICIONES = {
    "pendiente": ["inscrita", "rechazada"],
    "inscrita": ["liberada", "rechazada"],
    "liberada": [],
    "rechazada": []
}

ESTADO_INICIAL = "pendiente"


# ==========================================
# SALUDAR LA GARANTÍA
# ==========================================
# Aviso para la interfaz. No bloquea nada: la
# aplicación no puede impedir que alguien inscriba
# una garantía. Solo puede avisar de lo que hay que
# tener en cuenta al hacerlo.

AVISO_GRAVAMEN = (
    "Un gravamen es una inscripción registral. "
    "Lo que registre aquí es lo que el concesionario "
    "afirma: no certifica nada ante el Registro "
    "Público. La forma de la inscripción, sus datos, "
    "su ratificación y su rato de eficacia "
    "corresponden verificarlos con un abogado y con "
    "el escribano. Revise con ellos antes de dar de "
    "alta una garantía de este tipo."
)


# ==========================================
# CONSULTAS
# ==========================================

@requiere_permiso(VER_CONTRATOS)
def obtener_garantias(id_contrato=None):
    """
    Las garantías de un contrato, o todas si no se
    dice cuál.

    Devuelve una lista de diccionarios con id,
    contrato_id, tipo, descripcion, estado,
    institucion, numero_inscripcion,
    fecha_inscripcion, fecha_liberacion,
    es_gravamen, observaciones.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    consulta = """
        SELECT
            id,
            contrato_id,
            tipo,
            descripcion,
            estado,
            institucion,
            numero_inscripcion,
            fecha_inscripcion,
            fecha_liberacion,
            es_gravamen,
            observaciones
        FROM garantias
    """

    valores = []

    if id_contrato is not None:

        consulta += " WHERE contrato_id = %s"

        valores.append(id_contrato)

    consulta += " ORDER BY id DESC"

    cursor.execute(consulta, tuple(valores))

    garantias = cursor.fetchall()

    cursor.close()
    conexion.close()

    return garantias


@requiere_permiso(VER_CONTRATOS)
def obtener_garantia(id_garantia):
    """
    Una garantía con su contrato resuelto, o None.

    El saldo del contrato viene en "saldo_contrato"
    porque sin él no se puede decir si tiene sentido
    liberar la garantía.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            garantias.id,
            garantias.contrato_id,
            garantias.tipo,
            garantias.descripcion,
            garantias.estado,
            garantias.institucion,
            garantias.numero_inscripcion,
            garantias.fecha_inscripcion,
            garantias.fecha_liberacion,
            garantias.es_gravamen,
            garantias.observaciones,
            contratos.numero AS contrato_numero,
            contratos.saldo_financiado,
            contratos.estado AS contrato_estado,
            CONCAT(
                clientes.nombre, ' ', clientes.apellido
            ) AS cliente,
            marcas.nombre AS marca,
            autos.modelo AS modelo
        FROM garantias
        INNER JOIN contratos
            ON garantias.contrato_id = contratos.id
        INNER JOIN clientes
            ON contratos.cliente_id = clientes.id
        INNER JOIN autos
            ON contratos.auto_id = autos.id
        INNER JOIN marcas
            ON autos.marca_id = marcas.id
        WHERE garantias.id = %s
        """,
        (id_garantia,)
    )

    garantia = cursor.fetchone()

    cursor.close()
    conexion.close()

    if garantia:

        # El saldo pendiente REAL, que no es el
        # saldo_financiado del contrato: es lo que
        # queda por cobrar contando lo ya pagado.

        conexion = obtener_conexion()

        cursor = conexion.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                COALESCE(SUM(pagos.importe), 0) AS pagado
            FROM pagos
            WHERE venta_id = (
                SELECT venta_id FROM contratos
                WHERE id = %s
            )
            AND estado = 'convalidado'
            """,
            (garantia["contrato_id"],)
        )

        pagado = Decimal(
            str(cursor.fetchone()["pagado"])
        )

        cursor.close()
        conexion.close()

        garantia["saldo_contrato"] = (
            Decimal(str(garantia["saldo_financiado"]))
            - pagado
        )

    return garantia


@requiere_permiso(VER_CONTRATOS)
def resumen_de_garantias(id_contrato):
    """
    Los totales de garantías de un contrato.

    Devuelve total, inscritas, liberadas,
    pendientes, y gravamenes_no_liberados.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(estado = 'inscrita') AS inscritas,
            SUM(estado = 'liberada') AS liberadas,
            SUM(estado = 'pendiente') AS pendientes,
            SUM(
                es_gravamen = 1
                AND estado <> 'liberada'
            ) AS gravamenes_no_liberados
        FROM garantias
        WHERE contrato_id = %s
        """,
        (id_contrato,)
    )

    fila = cursor.fetchone()

    cursor.close()
    conexion.close()

    if not fila or not fila["total"]:

        return {
            "total": 0,
            "inscritas": 0,
            "liberadas": 0,
            "pendientes": 0,
            "gravamenes_no_liberados": 0
        }

    return {
        "total": fila["total"],
        "inscritas": fila["inscritas"] or 0,
        "liberadas": fila["liberadas"] or 0,
        "pendientes": fila["pendientes"] or 0,
        "gravamenes_no_liberados": (
            fila["gravamenes_no_liberados"] or 0
        )
    }


# ==========================================
# DAR DE ALTA
# ==========================================

@conexiones_libres
@requiere_permiso(GESTIONAR_CONTRATOS)
def registrar_garantia(
    id_contrato,
    tipo,
    descripcion=None,
    es_gravamen=0,
    institucion=None,
    numero_inscripcion=None,
    fecha_inscripcion=None,
    observaciones=None,
    estado=ESTADO_INICIAL
):
    """
    Registra una garantía de un contrato.

    Devuelve (id_garantia, "") o (None, motivo).

    Se puede dar de alta directamente como "inscrita"
    si ya se hizo, que es lo normal: se tramita fuera
    del programa y aquí se deja constancia. Lo que no
    hace es ENVIARLO a ningún sitio.

    Un gravamen es una inscripción registral: lo que
    se registre aquí es lo que el concesionario
    afirma, no un documento ante el Registro Público.
    Verificar la forma y el procedimiento
    corresponde al abogado y al escribano.
    """

    if tipo not in TIPOS:

        return (
            None,
            f"Tipo de garantía '{tipo}' no válido."
        )

    if estado not in ESTADOS:

        return (
            None,
            f"Estado '{estado}' no válido."
        )

    if estado != ESTADO_INICIAL and estado not in (
        TRANSICIONES[ESTADO_INICIAL]
    ):

        return (
            None,
            f"No se puede dar de alta una garantía "
            f"'{ESTADOS[estado]}' sin pasar antes por "
            f"'{ESTADOS[ESTADO_INICIAL]}'."
        )

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:

        conexion.start_transaction()

        cursor.execute(
            """
            SELECT
                id, numero, estado, saldo_financiado
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
                "El contrato está cancelado: no tiene "
                "sentido garantizarlo."
            )

        # ------------------------------
        # UNA GARANTÍA LIBERADA Y OTRA
        # GRAVAMEN DEL MISMO TIPO
        # ------------------------------
        # No tiene sentido tener dos "^aval"
        # inscribed del mismo contrato: o hay uno, o
        # hay que explicar cuál vale. Impide además
        # que un doble clic cree dos.

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM garantias
            WHERE contrato_id = %s
              AND tipo = %s
              AND estado <> 'liberada'
            """,
            (id_contrato, tipo)
        )

        if cursor.fetchone()["total"]:

            conexion.rollback()

            return (
                None,
                f"El contrato ya tiene una garantía de "
                f"tipo '{TIPOS[tipo]}' sin liberar."
            )

        # ------------------------------
        # INSERTAR
        # ------------------------------

        cursor.execute(
            """
            INSERT INTO garantias
            (
                contrato_id, tipo, descripcion, estado,
                institucion, numero_inscripcion,
                fecha_inscripcion, es_gravamen,
                observaciones
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                id_contrato,
                tipo,
                (descripcion or "").strip() or None,
                estado,
                (institucion or "").strip() or None,
                (numero_inscripcion or "").strip() or None,
                fecha_inscripcion,
                1 if es_gravamen else 0,
                (observaciones or "").strip() or None
            )
        )

        id_garantia = cursor.lastrowid

        conexion.commit()

    except mysql.connector.Error as error:

        conexion.rollback()

        raise ErrorBaseDatos(str(error)) from error

    numero = contrato["numero"]

    cursor.close()
    conexion.close()

    texto = (
        f"Garantía {TIPOS[tipo]} registrada en el "
        f"contrato {numero}"
    )

    if es_gravamen:

        texto += " (gravamen)"

    registrar_cambio(
        "garantias",
        "GARANTIA",
        texto,
        valor_anterior="sin garantía",
        valor_nuevo=f"{ESTADOS[estado]}",
        referencia=numero
    )

    if es_gravamen:

        # El aviso se deja en la descripción de la
        # operación para que quede en el rastro, no
        # solo en pantalla: quien lea la auditoría
        # dentro de seis meses tiene que ver que la
        # inscripción no está verificada.

        registrar_cambio(
            "garantias",
            "GARANTIA",
            f"Gravamen registrado sin verificación "
            f"registral. {AVISO_GRAVAMEN}",
            referencia=numero
        )

    return (id_garantia, "")


# ==========================================
# CAMBIAR EL ESTADO
# ==========================================

@conexiones_libres
@requiere_permiso(GESTIONAR_CONTRATOS)
def cambiar_estado_garantia(
    id_garantia,
    estado,
    numero_inscripcion=None,
    fecha_inscripcion=None,
    fecha_liberacion=None,
    institucion=None,
    observaciones=None
):
    """
    Pasa una garantía a otro estado.

    Devuelve (True, "") o (False, motivo).

    Liberar una garantía NO es un cambio de estado
    cualquiera: es devolverle al cliente su respaldo.
    Por eso exige que el contrato NO tenga saldo
    pendiente. Liberar la garantía de una venta
    financiada que se debe es perder el respaldo de
    una deuda viva.

    Y sigue exigiendo autorización del
    administrador, que es quien responde de ello.
    """

    if estado not in ESTADOS:

        return (False, f"Estado '{estado}' no válido.")

    if not numero_inscripcion and not fecha_liberacion:

        if estado == "inscrita":

            return (
                False,
                "Para dar por inscrita una garantía hace "
                "falta el número de inscripción y la fecha."
            )

        if estado == "liberada":

            return (
                False,
                "Para dar por liberada una garantía hace "
                "falta la fecha en que se liberó."
            )

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    try:

        conexion.start_transaction()

        cursor.execute(
            """
            SELECT
                garantias.id,
                garantias.estado,
                garantias.tipo,
                garantias.es_gravamen,
                garantias.numero_inscripcion,
                garantias.fecha_inscripcion,
                garantias.fecha_liberacion,
                garantias.institucion,
                garantias.contrato_id,
                contratos.numero AS contrato_numero,
                contratos.saldo_financiado,
                contratos.estado AS contrato_estado,
                COALESCE(
                    (
                        SELECT SUM(pagos.importe)
                        FROM pagos
                        WHERE pagos.venta_id = (
                            SELECT venta_id
                            FROM contratos
                            WHERE id = garantias.contrato_id
                        )
                        AND pagos.estado = 'convalidado'
                    ),
                    0
                ) AS pagado
            FROM garantias
            INNER JOIN contratos
                ON garantias.contrato_id = contratos.id
            WHERE garantias.id = %s
            FOR UPDATE
            """,
            (id_garantia,)
        )

        garantia = cursor.fetchone()

        if not garantia:

            conexion.rollback()

            return (False, "La garantía no existe.")

        actual = garantia["estado"]

        if actual == estado:

            conexion.rollback()

            return (
                False,
                "La garantía ya está en ese estado."
            )

        permitidos = TRANSICIONES.get(actual, [])

        if estado not in permitidos:

            conexion.rollback()

            return (
                False,
                f"No se puede pasar de "
                f"'{ESTADOS[actual]}' a "
                f"'{ESTADOS[estado]}'."
            )

        # ------------------------------
        # LIBERAR CON DEUDA VIVA
        # ------------------------------

        if estado == "liberada":

            if garantia["contrato_estado"] == "cancelado":

                conexion.rollback()

                return (
                    False,
                    "El contrato está cancelado: sus "
                    "garantías se liberan por el proceso "
                    "de cancelación, no una a una."
                )

            # El saldo pendiente sale del MISMO SELECT
            # que ya trae la garantía, en la misma
            # transacción y con la fila bloqueada.
            #
            # Antes se consultaba con una segunda
            # conexión: eso dejaba la primera abierta
            # sin cerrar, perdía el bloqueo, y después
            # se seguía usando la variable "conexion"
            # apuntando a la conexión ya cerrada, así
            # que el UPDATE final fallaba con "MySQL
            # server has gone away".

            saldo = (
                Decimal(str(garantia["saldo_financiado"]))
                - Decimal(str(garantia["pagado"]))
            )

            if saldo > Decimal("0.00"):

                conexion.rollback()

                return (
                    False,
                    f"No se puede liberar la garantía: el "
                    f"contrato {garantia['contrato_numero']} "
                    f"tiene {float(saldo):,.2f} pendientes."
                )

        # ------------------------------
        # GUARDAR
        # ------------------------------

        cursor = conexion.cursor()

        cursor.execute(
            """
            UPDATE garantias
            SET estado = %s,
                numero_inscripcion = COALESCE(%s,
                    numero_inscripcion),
                fecha_inscripcion = COALESCE(%s,
                    fecha_inscripcion),
                fecha_liberacion = COALESCE(%s,
                    fecha_liberacion),
                institucion = COALESCE(%s, institucion),
                observaciones = COALESCE(%s,
                    observaciones),
                fecha_modificacion = NOW()
            WHERE id = %s
            """,
            (
                estado,
                (numero_inscripcion or "").strip() or None,
                fecha_inscripcion,
                fecha_liberacion,
                (institucion or "").strip() or None,
                (observaciones or "").strip() or None,
                id_garantia
            )
        )

        conexion.commit()

    except mysql.connector.Error as error:

        conexion.rollback()

        raise ErrorBaseDatos(str(error)) from error

    numero = garantia["contrato_numero"]

    tipo = garantia["tipo"]

    cursor.close()
    conexion.close()

    registrar_cambio(
        "garantias",
        "GARANTIA",
        f"Garantía {TIPOS.get(tipo, tipo)} del "
        f"contrato {numero}: "
        f"{ESTADOS[actual]} -> {ESTADOS[estado]}",
        valor_anterior=ESTADOS[actual],
        valor_nuevo=ESTADOS[estado],
        referencia=numero
    )

    if estado == "liberada" and garantia["es_gravamen"]:

        registrar_cambio(
            "garantias",
            "GARANTIA",
            f"Gravamen liberado del contrato {numero}. "
            f"Compruebe que la baja se hizo efectiva "
            f"ante el Registro Público: aquí solo queda "
            f"constancia de lo que se anotó.",
            referencia=numero
        )

    return (True, "")


# ==========================================
# QUÉ FALTA LIBERAR
# ==========================================
# Para la cartera: qué garantías están inscritas y
# su contrato ya está saldado, o sea que hay que dar
# de baja, y cuáles respaldan un contrato que debe
# dinero y ya pasó su vencimiento.

def garantias_pendientes_de_liberar(hoy=None):
    """
    Las garantías inscritas cuyo contrato ya está
    pagado, más las de contratos vencidos que siguen
    sin liberar.

    Devuelve dos listas: por cobrar y por vencer.

    No lleva permiso: es una lectura y los dos roles
    leen. Quien la vea en pantalla lo decide la
    vista.
    """

    if hoy is None:

        hoy = date.today()

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            garantias.id,
            garantias.tipo,
            garantias.estado,
            garantias.numero_inscripcion,
            garantias.institucion,
            garantias.es_gravamen,
            contratos.numero AS contrato_numero,
            contratos.saldo_financiado,
            CONCAT(
                clientes.nombre, ' ', clientes.apellido
            ) AS cliente,
            COALESCE(cobrado.total, 0) AS pagado,
            (
                SELECT COUNT(*)
                FROM cuotas
                WHERE contrato_id = contratos.id
                  AND estado = 'vencida'
            ) AS cuotas_vencidas
        FROM garantias
        INNER JOIN contratos
            ON garantias.contrato_id = contratos.id
        INNER JOIN clientes
            ON contratos.cliente_id = clientes.id
        LEFT JOIN (
            SELECT
                pagos.contrato_id,
                SUM(pagos.importe) AS total
            FROM pagos
            WHERE pagos.estado = 'convalidado'
              AND pagos.contrato_id IS NOT NULL
            GROUP BY pagos.contrato_id
        ) AS cobrado
            ON cobrado.contrato_id = contratos.id
        WHERE contratos.estado <> 'cancelado'
          AND garantias.estado IN ('pendiente',
                                   'inscrita')
        ORDER BY contratos.saldo_financiado DESC
    """
    )

    filas = cursor.fetchall()

    cursor.close()
    conexion.close()

    por_liberar = []
    por_urgente = []

    for fila in filas:

        saldo = (
            Decimal(str(fila["saldo_financiado"]))
            - Decimal(str(fila["pagado"]))
        )

        fila["saldo"] = saldo

        if saldo <= Decimal("0.00"):

            # El contrato está saldado y la garantía
            # sigue inscrita: hay que dar de baja.

            por_liberar.append(fila)

            continue

        # Debe dinero y la garantía sigue puesta:
        # es lo que más urge mirar.

        if fila["cuotas_vencidas"] > 0:

            fila["motivo"] = (
                f"{fila['cuotas_vencidas']} cuota(s) "
                f"vencida(s) y la garantía sin liberar"
            )

            por_urgente.append(fila)

    return por_urgente, por_liberar


