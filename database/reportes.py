# ==========================================
# REPORTES Y ESTADÍSTICAS
# ==========================================
# Capa de agregados. Tanto el panel principal
# como la pantalla de reportes leen de aquí, de
# forma que una misma cifra no se calcula de dos
# maneras distintas.
#
# Dos niveles de permiso:
#
#   VER_TABLERO   lo ve cualquier usuario con
#                 sesión (el vendedor también)
#   VER_REPORTES  solo el administrador
#
# Mezclarlos rompería al vendedor, que sí puede
# entrar al panel.
#
# Los filtros de venta se construyen una sola
# vez, en _condiciones_ventas(), para que todas
# las consultas respeten exactamente los mismos
# criterios.
# ==========================================


from database.conexion import obtener_conexion

from database.configuracion import obtener_stock_minimo

from permisos import (
    requiere_permiso,
    VER_TABLERO,
    VER_REPORTES
)


# ==========================================
# FILTROS COMPARTIDOS
# ==========================================

def _condiciones_ventas(
    desde=None,
    hasta=None,
    cliente_id=None,
    marca_id=None,
    auto_id=None
):
    """
    Devuelve (fragmento_where, valores) con los
    filtros de venta ya aplicados.

    Se usa en todas las consultas de reportes
    para que "por cliente"signifique lo mismo
    en el conteo, en el importe y en el
    detalle.
    """

    condiciones = []
    valores = []

    if desde:
        condiciones.append("ventas.fecha >= %s")
        valores.append(desde)

    if hasta:
        condiciones.append("ventas.fecha <= %s")
        valores.append(hasta)

    if cliente_id:
        condiciones.append("ventas.cliente_id = %s")
        valores.append(cliente_id)

    if auto_id:
        condiciones.append("ventas.auto_id = %s")
        valores.append(auto_id)

    if marca_id:
        condiciones.append("autos.marca_id = %s")
        valores.append(marca_id)

    return condiciones, valores


def _where(condiciones):
    return (
        " WHERE " + " AND ".join(condiciones)
        if condiciones else ""
    )


# ==========================================
# PANEL PRINCIPAL
# ==========================================

@requiere_permiso(VER_TABLERO)
def obtener_resumen():
    """
    Conteos del panel. Una sola ida y vuelta a
    la base de datos mediante subconsultas.
    """

    umbral = obtener_stock_minimo()

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    consulta = """
        SELECT
            (
                SELECT COUNT(*)
                FROM autos
            ) AS total_autos,
            (
                SELECT COUNT(*)
                FROM marcas
            ) AS total_marcas,
            (
                SELECT COUNT(*)
                FROM clientes
            ) AS total_clientes,
            (
                SELECT COUNT(*)
                FROM ventas
            ) AS total_ventas,
            (
                SELECT COUNT(*)
                FROM autos
                WHERE stock > 0
                    AND stock <= %s
            ) AS stock_bajo,
            (
                SELECT COUNT(*)
                FROM autos
                WHERE stock = 0
            ) AS sin_stock,
            (
                SELECT COALESCE(SUM(stock), 0)
                FROM autos
            ) AS unidades,
            (
                SELECT COALESCE(SUM(precio), 0)
                FROM ventas
            ) AS ingresos
    """

    cursor.execute(consulta, (umbral,))

    resumen = cursor.fetchone()

    cursor.close()
    conexion.close()

    return resumen


@requiere_permiso(VER_TABLERO)
def obtener_ultima_venta():
    """
    Fecha de la venta más reciente.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT MAX(fecha)
        FROM ventas
    """

    cursor.execute(consulta)

    fecha = cursor.fetchone()[0]

    cursor.close()
    conexion.close()

    return fecha


@requiere_permiso(VER_TABLERO)
def obtener_ventas_del_dia():
    """
    (cantidad, importe) de hoy.

    Se compara contra CURDATE(), que es el reloj
    del servidor: el mismo que ve el usuario al
    entrar.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            COUNT(*),
            COALESCE(SUM(precio), 0)
        FROM ventas
        WHERE fecha = CURDATE()
    """

    cursor.execute(consulta)

    total, importe = cursor.fetchone()

    cursor.close()
    conexion.close()

    return total, importe


@requiere_permiso(VER_TABLERO)
def obtener_ventas_del_mes():
    """
    (cantidad, importe) del mes en curso.

    FIRST_DAY() es de MariaDB y no existe en
    MySQL: se retroceden los días del mes con
    DATE_SUB. Tampoco se usa DATE_FORMAT con
    '%Y-%m-01' para no depender de cómo el
    conector interpreta los signos de tanto por
    tanto en el texto SQL.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            COUNT(*),
            COALESCE(SUM(precio), 0)
        FROM ventas
        WHERE fecha >= DATE_SUB(
            CURDATE(),
            INTERVAL (DAYOFMONTH(CURDATE()) - 1) DAY
        )
    """

    cursor.execute(consulta)

    total, importe = cursor.fetchone()

    cursor.close()
    conexion.close()

    return total, importe


@requiere_permiso(VER_TABLERO)
def obtener_top_vehiculos(limite=5):
    """
    Vehículos más vendidos por unidades.

    Devuelve (vehiculo, unidades, importe). Usa
    el importe real de las ventas, no
    autos.precio: si el precio cambió después,
    el ranking debe reflejar lo que se cobró.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            CONCAT(marcas.nombre, ' ', autos.modelo)
                AS vehiculo,
            COUNT(*) AS unidades,
            COALESCE(SUM(ventas.precio), 0) AS importe
        FROM ventas
        INNER JOIN autos
            ON ventas.auto_id = autos.id
        INNER JOIN marcas
            ON autos.marca_id = marcas.id
        GROUP BY vehiculo
        ORDER BY unidades DESC, importe DESC
        LIMIT %s
    """

    cursor.execute(consulta, (limite,))

    filas = cursor.fetchall()

    cursor.close()
    conexion.close()

    return filas


@requiere_permiso(VER_TABLERO)
def obtener_ventas_por_cliente(limite=5):
    """
    Clientes con más compras.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            CONCAT(clientes.nombre, ' ', clientes.apellido)
                AS cliente,
            COUNT(*) AS compras,
            COALESCE(SUM(ventas.precio), 0) AS importe
        FROM ventas
        INNER JOIN clientes
            ON ventas.cliente_id = clientes.id
        GROUP BY cliente
        ORDER BY compras DESC, importe DESC
        LIMIT %s
    """

    cursor.execute(consulta, (limite,))

    filas = cursor.fetchall()

    cursor.close()
    conexion.close()

    return filas


# ==========================================
# REPORTES DETALLADOS
# ==========================================
# A partir de aquí, solo administrador.
# ==========================================

@requiere_permiso(VER_REPORTES)
def obtener_detalle_ventas(
    desde=None,
    hasta=None,
    cliente_id=None,
    marca_id=None,
    auto_id=None
):
    """
    Detalle de ventas que cumplen los filtros.
    Mismo contrato que obtener_ventas().
    """

    condiciones, valores = _condiciones_ventas(
        desde, hasta, cliente_id, marca_id, auto_id
    )

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            ventas.id,
            ventas.fecha,
            CONCAT(clientes.nombre, ' ', clientes.apellido)
                AS cliente,
            CONCAT(marcas.nombre, ' ', autos.modelo)
                AS vehiculo,
            ventas.precio
        FROM ventas
        INNER JOIN clientes
            ON ventas.cliente_id = clientes.id
        INNER JOIN autos
            ON ventas.auto_id = autos.id
        INNER JOIN marcas
            ON autos.marca_id = marcas.id
    """ + _where(condiciones) + " ORDER BY ventas.id DESC"

    cursor.execute(consulta, tuple(valores))

    filas = cursor.fetchall()

    cursor.close()
    conexion.close()

    return filas


@requiere_permiso(VER_REPORTES)
def obtener_metricas(
    desde=None,
    hasta=None,
    cliente_id=None,
    marca_id=None,
    auto_id=None
):
    """
    Cifras del reporte, todas con el mismo
    filtro: cantidad de ventas, total vendido,
    vehículos distintos vendidos, unidades y
    clientes con compras.
    """

    condiciones, valores = _condiciones_ventas(
        desde, hasta, cliente_id, marca_id, auto_id
    )

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    consulta = """
        SELECT
            COUNT(*) AS ventas,
            COALESCE(SUM(ventas.precio), 0) AS importe,
            COUNT(DISTINCT ventas.auto_id) AS vehiculos,
            COUNT(DISTINCT ventas.cliente_id) AS clientes
        FROM ventas
        INNER JOIN autos
            ON ventas.auto_id = autos.id
    """ + _where(condiciones)

    cursor.execute(consulta, tuple(valores))

    metricas = cursor.fetchone()

    cursor.close()
    conexion.close()

    return metricas


@requiere_permiso(VER_REPORTES)
def obtener_vehiculos_vendidos(
    desde=None,
    hasta=None,
    cliente_id=None,
    marca_id=None,
    auto_id=None
):
    """
    Un renglón por vehículo vendido, con las
    unidades que salieron y lo que
    generaron.
    """

    condiciones, valores = _condiciones_ventas(
        desde, hasta, cliente_id, marca_id, auto_id
    )

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            autos.id,
            marcas.nombre,
            autos.modelo,
            autos.anio,
            COUNT(*) AS unidades,
            COALESCE(SUM(ventas.precio), 0) AS importe,
            autos.stock
        FROM ventas
        INNER JOIN autos
            ON ventas.auto_id = autos.id
        INNER JOIN marcas
            ON autos.marca_id = marcas.id
    """ + _where(condiciones) + """
        GROUP BY autos.id, marcas.nombre, autos.modelo,
                 autos.anio, autos.stock
        ORDER BY unidades DESC, importe DESC
    """

    cursor.execute(consulta, tuple(valores))

    filas = cursor.fetchall()

    cursor.close()
    conexion.close()

    return filas


@requiere_permiso(VER_REPORTES)
def obtener_clientes_con_compras(
    desde=None,
    hasta=None,
    cliente_id=None,
    marca_id=None,
    auto_id=None
):
    """
    Un renglón por cliente que compró algo en el
    rango, con su total.
    """

    condiciones, valores = _condiciones_ventas(
        desde, hasta, cliente_id, marca_id, auto_id
    )

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = """
        SELECT
            clientes.id,
            clientes.nombre,
            clientes.apellido,
            COUNT(*) AS compras,
            COALESCE(SUM(ventas.precio), 0) AS importe
        FROM ventas
        INNER JOIN clientes
            ON ventas.cliente_id = clientes.id
        INNER JOIN autos
            ON ventas.auto_id = autos.id
    """ + _where(condiciones) + """
        GROUP BY clientes.id, clientes.nombre, clientes.apellido
        ORDER BY compras DESC, importe DESC
    """

    cursor.execute(consulta, tuple(valores))

    filas = cursor.fetchall()

    cursor.close()
    conexion.close()

    return filas


@requiere_permiso(VER_REPORTES)
def obtener_stock_actual():
    """
    Inventario global, independiente del filtro
    de fechas: el stock no tiene fecha.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor(dictionary=True)

    consulta = """
        SELECT
            COALESCE(SUM(stock), 0) AS unidades,
            COUNT(*) AS vehiculos,
            SUM(stock = 0) AS sin_stock,
            SUM(stock > 0) AS con_stock,
            COALESCE(SUM(stock * precio), 0) AS valor
        FROM autos
    """

    cursor.execute(consulta)

    stock = cursor.fetchone()

    cursor.close()
    conexion.close()

    return stock
