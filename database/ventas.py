import mysql.connector

from database.conexion import obtener_conexion

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
            ventas.precio
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
# TOTALES
# =============================

def obtener_total_vendido(desde=None, hasta=None):

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            COUNT(*),
            COALESCE(SUM(precio), 0)
        FROM ventas
        WHERE 1 = 1
    """

    valores = []

    if desde:
        consulta += " AND fecha >= %s"

        valores.append(desde)

    if hasta:
        consulta += " AND fecha <= %s"

        valores.append(hasta)

    cursor.execute(consulta, tuple(valores))

    total, importe = cursor.fetchone()

    cursor.close()
    conexion.close()

    return total, importe


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

        consulta_venta = """
            INSERT INTO ventas
            (cliente_id, auto_id, fecha, precio)
            VALUES (%s, %s, %s, %s)
        """

        cursor.execute(
            consulta_venta,
            (cliente_id, auto_id, fecha, precio)
        )

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

        cursor.close()
        conexion.close()

        return True, ""

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

        cursor.close()
        conexion.close()

        return True

    except mysql.connector.Error:

        conexion.rollback()

        cursor.close()
        conexion.close()

        return False
