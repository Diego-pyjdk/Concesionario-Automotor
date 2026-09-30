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


# =============================
# BUSCAR
# =============================

def buscar_marcas(texto):

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT id, nombre
        FROM marcas
        WHERE nombre LIKE %s
        ORDER BY nombre
    """

    parametro = f"%{texto}%"

    cursor.execute(
        consulta,
        (parametro,)
    )

    marcas = cursor.fetchall()

    cursor.close()
    conexion.close()

    return marcas


# =============================
# EXISTENCIA
# =============================

def marca_existe(nombre, id_marca=None):
    """
    Verifica si ya existe una marca con ese
    nombre. La comparación ignora mayúsculas.

    id_marca permite excluir la propia marca
    al estar editando.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT COUNT(*)
        FROM marcas
        WHERE LOWER(nombre) = LOWER(%s)
    """

    valores = (nombre,)

    if id_marca:
        consulta += " AND id <> %s"

        valores = valores + (id_marca,)

    cursor.execute(consulta, valores)

    total = cursor.fetchone()[0]

    cursor.close()
    conexion.close()

    return total > 0


def contar_autos_por_marca(id_marca):

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT COUNT(*)
        FROM autos
        WHERE marca_id = %s
    """

    cursor.execute(consulta, (id_marca,))

    total = cursor.fetchone()[0]

    cursor.close()
    conexion.close()

    return total


# =============================
# INSERTAR
# =============================

def insertar_marca(nombre):

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        INSERT INTO marcas
        (nombre)
        VALUES (%s)
    """

    cursor.execute(consulta, (nombre,))

    conexion.commit()

    id_marca = cursor.lastrowid

    cursor.close()
    conexion.close()

    return id_marca


# =============================
# ACTUALIZAR
# =============================

def actualizar_marca(id_marca, nombre):

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        UPDATE marcas
        SET nombre = %s
        WHERE id = %s
    """

    cursor.execute(
        consulta,
        (nombre, id_marca)
    )

    conexion.commit()

    cursor.close()
    conexion.close()


# =============================
# ELIMINAR
# =============================

def eliminar_marca(id_marca):
    """
    Elimina una marca.

    Devuelve False si tiene vehículos
    asociados: la clave foránea lo impide y
    no se debe perder el historial.
    """

    if contar_autos_por_marca(id_marca) > 0:
        return False

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        DELETE FROM marcas
        WHERE id = %s
    """

    cursor.execute(consulta, (id_marca,))

    conexion.commit()

    cursor.close()
    conexion.close()

    return True
