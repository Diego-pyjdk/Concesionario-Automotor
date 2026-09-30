from database.conexion import obtener_conexion


# =============================
# LISTAR
# =============================

def obtener_clientes():

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            id,
            nombre,
            apellido,
            telefono,
            email
        FROM clientes
        ORDER BY id DESC
    """

    cursor.execute(consulta)

    clientes = cursor.fetchall()

    cursor.close()
    conexion.close()

    return clientes


# =============================
# BUSCAR
# =============================

def buscar_clientes(texto):

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            id,
            nombre,
            apellido,
            telefono,
            email
        FROM clientes
        WHERE
            nombre LIKE %s
            OR apellido LIKE %s
            OR telefono LIKE %s
            OR email LIKE %s
        ORDER BY id DESC
    """

    parametro = f"%{texto}%"

    cursor.execute(
        consulta,
        (
            parametro,
            parametro,
            parametro,
            parametro
        )
    )

    clientes = cursor.fetchall()

    cursor.close()
    conexion.close()

    return clientes


def obtener_clientes_para_venta():
    """
    Lista mínima para armar el ComboBox del
    formulario de venta.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            id,
            nombre,
            apellido
        FROM clientes
        ORDER BY nombre, apellido
    """

    cursor.execute(consulta)

    clientes = cursor.fetchall()

    cursor.close()
    conexion.close()

    return clientes


# =============================
# EXISTENCIA
# =============================

def contar_ventas_de_cliente(id_cliente):

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT COUNT(*)
        FROM ventas
        WHERE cliente_id = %s
    """

    cursor.execute(consulta, (id_cliente,))

    total = cursor.fetchone()[0]

    cursor.close()
    conexion.close()

    return total


# =============================
# INSERTAR
# =============================

def insertar_cliente(
    nombre,
    apellido,
    telefono,
    email
):

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        INSERT INTO clientes
        (nombre, apellido, telefono, email)
        VALUES (%s, %s, %s, %s)
    """

    valores = (
        nombre,
        apellido,
        telefono,
        email
    )

    cursor.execute(consulta, valores)

    conexion.commit()

    id_cliente = cursor.lastrowid

    cursor.close()
    conexion.close()

    return id_cliente


# =============================
# ACTUALIZAR
# =============================

def actualizar_cliente(
    id_cliente,
    nombre,
    apellido,
    telefono,
    email
):

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        UPDATE clientes
        SET
            nombre = %s,
            apellido = %s,
            telefono = %s,
            email = %s
        WHERE id = %s
    """

    valores = (
        nombre,
        apellido,
        telefono,
        email,
        id_cliente
    )

    cursor.execute(consulta, valores)

    conexion.commit()

    cursor.close()
    conexion.close()


# =============================
# ELIMINAR
# =============================

def eliminar_cliente(id_cliente):
    """
    Elimina un cliente.

    Devuelve False si tiene ventas
    registradas: la clave foránea lo impide y
    no se debe perder el historial.
    """

    if contar_ventas_de_cliente(id_cliente) > 0:
        return False

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        DELETE FROM clientes
        WHERE id = %s
    """

    cursor.execute(consulta, (id_cliente,))

    conexion.commit()

    cursor.close()
    conexion.close()

    return True
