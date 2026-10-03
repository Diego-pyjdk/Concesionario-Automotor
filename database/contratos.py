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

import mysql.connector

from database.conexion import (
    conexiones_libres,
    obtener_conexion
)

from database.auditoria import registrar_accion

import sesion as modulo_sesion

from permisos import (
    requiere_permiso,
    VER_CONTRATOS,
    CREAR_CONTRATOS,
    GESTIONAR_CONTRATOS
)

from errores import traducir_error


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
        contratos.cantidad_cuotas,
        contratos.observaciones,
        contratos.estado,
        contratos.archivo_pdf,
        contratos.fecha_creacion,
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
        autos.anio,
        autos.color,
        autos.precio AS precio_lista,
        marcas.nombre AS marca,
        autos.modelo AS modelo,
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
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
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
        LEFT JOIN contratos
            ON contratos.venta_id = ventas.id
        WHERE contratos.id IS NULL
        ORDER BY ventas.id DESC
    """

    cursor.execute(consulta)

    ventas = cursor.fetchall()

    cursor.close()
    conexion.close()

    return ventas


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
    estado=ESTADO_INICIAL
):
    """
    Crea el contrato de una venta.

    Los datos de cliente, vehículo, usuario y
    precio se COPIAN de la venta: el contrato
    es el documento que firmó el cliente y no
    puede cambiar solo porque alguien edite el
    vehículo después.

    Devuelve (id_contrato, "") o (None, motivo).
    """

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

        if anticipo > float(venta["precio"]):

            conexion.rollback()

            return (
                None,
                "El anticipo no puede ser mayor que "
                "el precio de la venta."
            )

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

        if existente:

            cursor.execute(
                "DELETE FROM contratos "
                "WHERE venta_id = %s AND estado = 'cancelado'",
                (venta_id,)
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
                estado
            )
            VALUES (
                NULL,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """

        valores = (
            venta_id,
            venta["cliente_id"],
            venta["auto_id"],
            usuario.id_usuario,
            venta["fecha"],
            venta["precio"],
            forma_pago,
            anticipo,
            cantidad_cuotas,
            observaciones,
            estado
        )

        cursor.execute(consulta_insertar, valores)

        id_contrato = cursor.lastrowid

        # ------------------------------
        # 5. NÚMERO
        # ------------------------------

        numero = formatear_numero(id_contrato)

        cursor.execute(
            "UPDATE contratos SET numero = %s WHERE id = %s",
            (numero, id_contrato)
        )

        conexion.commit()

        cursor.close()
        conexion.close()

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

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        "DELETE FROM contratos WHERE id = %s",
        (id_contrato,)
    )

    conexion.commit()

    cursor.close()
    conexion.close()

    registrar_accion(
        "contratos",
        "ELIMINAR",
        f"Contrato {contrato['numero']} eliminado"
    )

    return True, ""
