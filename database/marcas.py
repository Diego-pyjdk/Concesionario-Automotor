from database.conexion import obtener_conexion


def obtener_marcas():

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT id, nombre
        FROM marcas
        ORDER BY nombre
    """

    cursor.execute(consulta)

    marcas = cursor.fetchall()

    cursor.close()
    conexion.close()

    return marcas