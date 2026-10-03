import mysql.connector

from database.conexion import obtener_conexion

from database.auditoria import registrar_accion

import sesion as modulo_sesion

from permisos import (
    requiere_permiso,
    REGISTRAR_VENTAS,
    GESTIONAR_VENTAS
)


# =============================
# LISTAR


# =============================

def obtener_ventas(desde=None, hasta=None, texto=None):
    """
    Lista las ventas con el nombre del cliente y
    el vehículo ya resueltos por JOIN.

    desde / hasta son fechas opcionales (YYYY-MM-DD).
    texto filtra por cliente o vehículo.

    Contrato de columnas: id, fecha, cliente,
    vehiculo, precio, usuario_nombre. La última
    puede venir a None en las ventas anteriores a
    la migración del vendedor; quien la pinte debe
    poner algo legible en su lugar, no un hueco.

    Está escrito en tres sitios más:
    VentasView.pintar_fila, VentasView.ver_venta
    y el ancho de columna en VentasView.columnas.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            ventas.id,
            ventas.fecha,
            CONCAT(
                clientes.nombre,
                ' ',
                clientes.apellido
            ) AS cliente,
            CONCAT(
                marcas.nombre,
                ' ',
                autos.modelo
            ) AS vehiculo,
            ventas.precio,
            ventas.usuario_nombre
        FROM ventas
        INNER JOIN clientes
            ON ventas.cliente_id = clientes.id
        INNER JOIN autos
            ON ventas.auto_id = autos.id
        INNER JOIN marcas
            ON autos.marca_id = marcas.id
        WHERE 1 = 1
    """

    condiciones = []

    valores = []

    if desde:
        condiciones.append(
            "ventas.fecha >= %s"
        )

        valores.append(desde)

    if hasta:
        condiciones.append(
            "ventas.fecha <= %s"
        )

        valores.append(hasta)

    if texto:
        condiciones.append("""
            (
                CONCAT(
                    clientes.nombre,
                    ' ',
                    clientes.apellido
                ) LIKE %s
                OR CONCAT(
                    marcas.nombre,
                    ' ',
                    autos.modelo
                ) LIKE %s
            )
        """)

        parametro = f"%{texto}%"

        valores.append(parametro)
        valores.append(parametro)

    if condiciones:
        consulta += " AND " + " AND ".join(condiciones)

    consulta += " ORDER BY ventas.id DESC"

    cursor.execute(
        consulta,
        tuple(valores)
    )

    ventas = cursor.fetchall()

    cursor.close()
    conexion.close()

    return ventas


def obtener_ventas_recientes(limite=5):

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            ventas.id,
            ventas.fecha,
            CONCAT(
                clientes.nombre,
                ' ',
                clientes.apellido
            ) AS cliente,
            CONCAT(
                marcas.nombre,
                ' ',
                autos.modelo
            ) AS vehiculo,
            ventas.precio
        FROM ventas
        INNER JOIN clientes
            ON ventas.cliente_id = clientes.id
        INNER JOIN autos
            ON ventas.auto_id = autos.id
        INNER JOIN marcas
            ON autos.marca_id = marcas.id
        ORDER BY ventas.id DESC
        LIMIT %s
    """

    cursor.execute(consulta, (limite,))

    ventas = cursor.fetchall()

    cursor.close()
    conexion.close()

    return ventas


# =============================
# EXISTENCIA


# =============================

def contar_ventas_de_auto(id_auto):

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT COUNT(*)
        FROM ventas
        WHERE auto_id = %s
    """

    cursor.execute(consulta, (id_auto,))

    total = cursor.fetchone()[0]

    cursor.close()
    conexion.close()

    return total


# =============================
# REGISTRAR VENTA


# =============================

@requiere_permiso(REGISTRAR_VENTAS)
def registrar_venta(cliente_id, auto_id, fecha, precio):
    """
    Registra una venta dentro de una transacción.

    La transacción es obligatoria: si el INSERT
    falla, el stock no debe quedar descontado.

    Pasos dentro de la transacción:
      1. Bloquear el vehículo y verificar stock.
      2. Insertar la venta.
      3. Descontar una unidad.

    Devuelve (True, "") o (False, mensaje).
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:
        conexion.start_transaction()

        # ------------------------------
        # 1. VERIFICAR VEHÍCULO Y STOCK
        # ------------------------------

        consulta_auto = """
            SELECT stock
            FROM autos
            WHERE id = %s
            FOR UPDATE
        """

        cursor.execute(consulta_auto, (auto_id,))

        auto = cursor.fetchone()

        if not auto:
            conexion.rollback()

            return (
                False,
                "El vehículo seleccionado no existe."
            )

        stock = auto[0]

        if stock <= 0:
            conexion.rollback()

            return (
                False,
                "El vehículo seleccionado no tiene stock."
            )

        # ------------------------------
        # 2. INSERTAR VENTA
        # ------------------------------
        # Se guarda QUIÉN registró la venta, no solo
        # el cliente y el vehículo.
        #
        # usuario_nombre es una copia, igual que en
        # auditoria: si luego se borra la cuenta,
        # usuario_id pasa a NULL pero el nombre se
        # queda y el histórico sigue diciendo quién
        # vendió cada vehículo.

        usuario = modulo_sesion.obtener_sesion()

        consulta_venta = """
            INSERT INTO ventas
            (
                cliente_id,
                auto_id,
                usuario_id,
                usuario_nombre,
                fecha,
                precio
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        cursor.execute(
            consulta_venta,
            (
                cliente_id,
                auto_id,
                usuario.id_usuario,
                usuario.nombre_usuario,
                fecha,
                precio
            )
        )

        id_venta = cursor.lastrowid

        # ------------------------------
        # 3. DESCONTAR STOCK
        # ------------------------------

        consulta_stock = """
            UPDATE autos
            SET stock = stock - 1
            WHERE id = %s
        """

        cursor.execute(consulta_stock, (auto_id,))

        conexion.commit()

        # Se registra DESPUÉS del commit: si la
        # transacción se revirtiera, el rastro
        # mentiría.

        registrar_accion(
            "ventas",
            "VENTA",
            f"Venta por {float(precio):,.2f} del "
            f"vehículo {auto_id} a cliente {cliente_id}"
        )

        cursor.close()
        conexion.close()

        # Se devuelve el id, no True. Quien llama
        # solo mira si es cierto, así que sigue
        # funcionando igual, pero con el id puede
        # ofrecer crear el contrato de esta venta
        # sin tener que volver a buscarla.

        return id_venta, ""

    except mysql.connector.Error as error:

        conexion.rollback()

        cursor.close()
        conexion.close()

        return (
            False,
            f"No se pudo registrar la venta: {error}"
        )


# =============================
# ELIMINAR


# =============================

@requiere_permiso(GESTIONAR_VENTAS)
def eliminar_venta(id_venta):
    """
    Elimina una venta y devuelve la unidad al
    stock del vehículo, en la misma transacción.

    Sin la devolución de stock, el inventario
    quedaría descuadrado respecto del histórico.

    Si la venta tiene un contrato no se anula:
    el contrato es un documento firmado y no
    puede quedarse colgando de una venta que ya
    no existe. Se devuelve False, como con
    cualquier otra clave foránea.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:
        conexion.start_transaction()

        consulta_venta = """
            SELECT auto_id
            FROM ventas
            WHERE id = %s
            FOR UPDATE
        """

        cursor.execute(consulta_venta, (id_venta,))

        venta = cursor.fetchone()

        if not venta:
            conexion.rollback()

            cursor.close()
            conexion.close()

            return False

        auto_id = venta[0]

        # ------------------------------
        # CONTRATO VIVO
        # ------------------------------
        # La clave foránea de contratos ya lo
        # impediría (ON DELETE RESTRICT), pero
        # llegar aquí saltándose esa excepción
        # perdería el motivo: se avisaría de un
        # "no se pudo anular" sin decir por qué.

        consulta_contrato = """
            SELECT numero, estado
            FROM contratos
            WHERE venta_id = %s
        """

        cursor.execute(
            consulta_contrato, (id_venta,)
        )

        contrato = cursor.fetchone()

        if contrato and contrato[1] != "cancelado":
            conexion.rollback()

            cursor.close()
            conexion.close()

            return False

        # Un contrato cancelado no surte efecto, pero
        # su fila sigue apuntando a la venta y la
        # clave foranea (ON DELETE RESTRICT) impediría
        # el DELETE. Hay que llevárselo delante, en la
        # misma transacción.
        #
        # Es lo mismo que hace crear_contrato() cuando
        # rehace uno cancelado. Si aquí no se borrara,
        # la promesa de "cancelado no bloquea" sería
        # falsa y el DELETE saltaría por la excepción
        # devolviendo un False sin motivo aparente.

        if contrato:
            cursor.execute(
                """
                DELETE FROM contratos
                WHERE venta_id = %s
                    AND estado = 'cancelado'
                """,
                (id_venta,)
            )

        # ------------------------------
        # PAGOS COBRADOS
        # ------------------------------
        # Si ya entró dinero, la venta no se anula
        # en silencio. La clave foránea de pagos
        # (ON DELETE RESTRICT) también lo impediría,
        # pero saltar por esa excepción daría un
        # False sin explicación.
        #
        # A diferencia del contrato cancelado, aquí
        # no hay nada que borrar antes: un pago es
        # un hecho económico y deshacerlo es una
        # operación aparte, y por eso la decide
        # pagos.eliminar_pago(), que exige permiso
        # de administrador y deja rastro.

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM pagos
            WHERE venta_id = %s
            """,
            (id_venta,)
        )

        if cursor.fetchone()[0] > 0:
            conexion.rollback()

            cursor.close()
            conexion.close()

            return False

        consulta_borrar = """
            DELETE FROM ventas
            WHERE id = %s
        """

        cursor.execute(consulta_borrar, (id_venta,))

        consulta_stock = """
            UPDATE autos
            SET stock = stock + 1
            WHERE id = %s
        """

        cursor.execute(consulta_stock, (auto_id,))

        conexion.commit()

        registrar_accion(
            "ventas",
            "VENTA_ANULADA",
            f"Venta {id_venta} anulada; "
            f"devuelta 1 unidad al vehículo {auto_id}"
        )

        cursor.close()
        conexion.close()

        return True

    except mysql.connector.Error:

        conexion.rollback()

        cursor.close()
        conexion.close()

        return False
