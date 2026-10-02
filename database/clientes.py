from database.conexion import obtener_conexion

from database.auditoria import registrar_accion

from permisos import (
    requiere_permiso,
    GESTIONAR_CLIENTES
)


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
            email,
            documento
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
            email,
            documento
        FROM clientes
        WHERE
            nombre LIKE %s
            OR apellido LIKE %s
            OR telefono LIKE %s
            OR email LIKE %s
            OR documento LIKE %s
        ORDER BY id DESC
    """

    parametro = f"%{texto}%"

    cursor.execute(
        consulta,
        (
            parametro,
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
# DUPLICADOS
# =============================

def cliente_duplicado(
    nombre,
    apellido,
    telefono,
    email,
    id_cliente=None
):
    """
    Detecta un cliente repetido.

    Se considera duplicado si coincide el
    correo, o si coinciden nombre, apellido y
    teléfono a la vez.

    id_cliente excluye al propio cliente del
    resultado, para que al editar no se detecte
    a sí mismo.
    """

    condiciones = []

    valores = []

    if email:

        condiciones.append(
            "(email IS NOT NULL AND "
            "LOWER(email) = LOWER(%s))"
        )

        valores.append(email)

    if nombre and apellido:

        # <=> compara también NULL con NULL
        condiciones.append(
            "(LOWER(nombre) = LOWER(%s) AND "
            "LOWER(apellido) = LOWER(%s) AND "
            "telefono <=> %s)"
        )

        valores.append(nombre)
        valores.append(apellido)
        valores.append(telefono)

    if not condiciones:

        return False

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = (
        "SELECT COUNT(*) FROM clientes WHERE ("
        + " OR ".join(condiciones)
        + ")"
    )

    if id_cliente:

        consulta += " AND id <> %s"

        valores.append(id_cliente)

    cursor.execute(consulta, tuple(valores))

    total = cursor.fetchone()[0]

    cursor.close()
    conexion.close()

    return total > 0


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

@requiere_permiso(GESTIONAR_CLIENTES)
def insertar_cliente(
    nombre,
    apellido,
    telefono,
    email,
    documento=None
):
    """
    Alta de cliente.

    "documento" es opcional y se añadió para
    el contrato de compraventa. Lleva valor
    por defecto para no romper a quien llame
    a esta función con los cuatro datos de
    siempre.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        INSERT INTO clientes
        (
            nombre,
            apellido,
            telefono,
            email,
            documento
        )
        VALUES (%s, %s, %s, %s, %s)
    """

    valores = (
        nombre,
        apellido,
        telefono,
        email,
        documento
    )

    cursor.execute(consulta, valores)

    conexion.commit()

    id_cliente = cursor.lastrowid

    cursor.close()
    conexion.close()

    registrar_accion(
        "clientes",
        "CREAR",
        f"Cliente {nombre} {apellido} registrado"
    )

    return id_cliente


# =============================
# ACTUALIZAR
# =============================

@requiere_permiso(GESTIONAR_CLIENTES)
def actualizar_cliente(
    id_cliente,
    nombre,
    apellido,
    telefono,
    email,
    documento=None
):
    """
    Edición de cliente.

    "documento" tiene valor por defecto igual
    que en el alta, por el mismo motivo.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        UPDATE clientes
        SET
            nombre = %s,
            apellido = %s,
            telefono = %s,
            email = %s,
            documento = %s
        WHERE id = %s
    """

    valores = (
        nombre,
        apellido,
        telefono,
        email,
        documento,
        id_cliente
    )

    cursor.execute(consulta, valores)

    conexion.commit()

    cursor.close()
    conexion.close()

    registrar_accion(
        "clientes",
        "MODIFICAR",
        f"Cliente {id_cliente} actualizado "
        f"({nombre} {apellido})"
    )


# =============================
# ELIMINAR
# =============================

@requiere_permiso(GESTIONAR_CLIENTES)
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

    registrar_accion(
        "clientes",
        "ELIMINAR",
        f"Cliente {id_cliente} eliminado"
    )

    return True
