import mysql.connector

from database.conexion import (
    conexiones_libres,
    obtener_conexion
)

from database.auditoria import registrar_accion

from errores import traducir_error

from permisos import (
    requiere_permiso,
    GESTIONAR_MARCAS
)


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

@requiere_permiso(GESTIONAR_MARCAS)
def insertar_marca(nombre):

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        INSERT INTO marcas
        (nombre)
        VALUES (%s)
    """

    # marcas.nombre es UNIQUE. MarcaForm ya
    # avisa antes de llegar aqui, pero dos
    # ventanas abiertas a la vez pueden pasar
    # el control y chocar en la base: ese
    # error se traduce para que se lea, en vez
    # de dejar escapar el de MySQL.

    try:

        cursor.execute(consulta, (nombre,))

        conexion.commit()

        id_marca = cursor.lastrowid

    except mysql.connector.Error as error:

        conexion.rollback()

        cursor.close()
        conexion.close()

        raise traducir_error(error) from error

    cursor.close()
    conexion.close()

    registrar_accion(
        "marcas",
        "CREAR",
        f"Marca '{nombre}' creada"
    )

    return id_marca


# =============================
# ACTUALIZAR
# =============================

@requiere_permiso(GESTIONAR_MARCAS)
def actualizar_marca(id_marca, nombre):

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        UPDATE marcas
        SET nombre = %s
        WHERE id = %s
    """

    # Mismo motivo que en el alta: el UNIQUE
    # de marcas.nombre puede saltar si dos
    # ventanas editan a la vez.

    try:

        cursor.execute(
            consulta,
            (nombre, id_marca)
        )

        conexion.commit()

    except mysql.connector.Error as error:

        conexion.rollback()

        cursor.close()
        conexion.close()

        raise traducir_error(error) from error

    cursor.close()
    conexion.close()

    registrar_accion(
        "marcas",
        "MODIFICAR",
        f"Marca {id_marca} renombrada a '{nombre}'"
    )


# =============================
# ELIMINAR
# =============================

@conexiones_libres
@requiere_permiso(GESTIONAR_MARCAS)
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

    registrar_accion(
        "marcas",
        "ELIMINAR",
        f"Marca {id_marca} eliminada"
    )

    return True
