from database.conexion import obtener_conexion


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

    cursor.close()
    conexion.close()

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