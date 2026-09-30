from database.conexion import obtener_conexion

from database.ventas import contar_ventas_de_auto


def obtener_autos():

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            autos.id,
            marcas.nombre,
            autos.modelo,
            autos.anio,
            autos.precio,
            autos.color,
            autos.stock
        FROM autos
        INNER JOIN marcas
            ON autos.marca_id = marcas.id
        ORDER BY autos.id DESC
    """

    cursor.execute(consulta)

    autos = cursor.fetchall()

    cursor.close()
    conexion.close()

    return autos


def insertar_auto(marca_id, modelo, anio, precio, color, stock):

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        INSERT INTO autos
        (marca_id, modelo, anio, precio, color, stock)
        VALUES (%s, %s, %s, %s, %s, %s)
    """

    valores = (
        marca_id,
        modelo,
        anio,
        precio,
        color,
        stock
    )

    cursor.execute(consulta, valores)

    conexion.commit()

    id_auto = cursor.lastrowid

    cursor.close()
    conexion.close()

    return id_auto


def actualizar_auto(
    id_auto,
    marca_id,
    modelo,
    anio,
    precio,
    color,
    stock
):

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        UPDATE autos
        SET
            marca_id = %s,
            modelo = %s,
            anio = %s,
            precio = %s,
            color = %s,
            stock = %s
        WHERE id = %s
    """

    valores = (
        marca_id,
        modelo,
        anio,
        precio,
        color,
        stock,
        id_auto
    )

    cursor.execute(consulta, valores)

    conexion.commit()

    cursor.close()
    conexion.close()


def eliminar_auto(id_auto):
    """
    Elimina un vehículo.

    Devuelve False si tiene ventas
    registradas: la clave foránea lo impide y
    no se debe perder el histórico.
    """

    if contar_ventas_de_auto(id_auto) > 0:
        return False

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        DELETE FROM autos
        WHERE id = %s
    """

    cursor.execute(consulta, (id_auto,))

    conexion.commit()

    cursor.close()
    conexion.close()

    return True

def buscar_autos(texto):

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            autos.id,
            marcas.nombre,
            autos.modelo,
            autos.anio,
            autos.precio,
            autos.color,
            autos.stock
        FROM autos
        INNER JOIN marcas
            ON autos.marca_id = marcas.id
        WHERE
            marcas.nombre LIKE %s
            OR autos.modelo LIKE %s
        ORDER BY autos.id DESC
    """

    parametro = f"%{texto}%"

    cursor.execute(
        consulta,
        (parametro, parametro)
    )

    autos = cursor.fetchall()

    cursor.close()
    conexion.close()

    return autos


# =============================
# STOCK
# =============================
# Las siguientes consultas devuelven las mismas
# 7 columnas y en el mismo orden que obtener_autos
# para que las vistas puedan reutilizar la misma
# tabla sin transformaciones.
# =============================

def obtener_autos_disponibles():

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            autos.id,
            marcas.nombre,
            autos.modelo,
            autos.anio,
            autos.precio,
            autos.color,
            autos.stock
        FROM autos
        INNER JOIN marcas
            ON autos.marca_id = marcas.id
        WHERE autos.stock > 0
        ORDER BY autos.id DESC
    """

    cursor.execute(consulta)

    autos = cursor.fetchall()

    cursor.close()
    conexion.close()

    return autos


def obtener_autos_sin_stock():

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            autos.id,
            marcas.nombre,
            autos.modelo,
            autos.anio,
            autos.precio,
            autos.color,
            autos.stock
        FROM autos
        INNER JOIN marcas
            ON autos.marca_id = marcas.id
        WHERE autos.stock = 0
        ORDER BY autos.id DESC
    """

    cursor.execute(consulta)

    autos = cursor.fetchall()

    cursor.close()
    conexion.close()

    return autos


def obtener_autos_stock_bajo(limite):

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            autos.id,
            marcas.nombre,
            autos.modelo,
            autos.anio,
            autos.precio,
            autos.color,
            autos.stock
        FROM autos
        INNER JOIN marcas
            ON autos.marca_id = marcas.id
        WHERE autos.stock > 0
            AND autos.stock <= %s
        ORDER BY autos.stock ASC, autos.id DESC
    """

    cursor.execute(consulta, (limite,))

    autos = cursor.fetchall()

    cursor.close()
    conexion.close()

    return autos


# =============================
# VENTAS
# =============================

def obtener_autos_para_venta():
    """
    Lista para el ComboBox del formulario de
    venta: id, etiqueta, precio y stock actual.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            autos.id,
            CONCAT(
                marcas.nombre,
                ' ',
                autos.modelo
            ) AS vehiculo,
            autos.precio,
            autos.stock
        FROM autos
        INNER JOIN marcas
            ON autos.marca_id = marcas.id
        ORDER BY marcas.nombre, autos.modelo
    """

    cursor.execute(consulta)

    autos = cursor.fetchall()

    cursor.close()
    conexion.close()

    return autos