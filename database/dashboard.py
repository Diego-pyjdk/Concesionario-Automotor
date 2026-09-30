from database.conexion import obtener_conexion


# =============================
# UMBRAL DE STOCK BAJO
# =============================
# Un vehículo con stock menor o igual a este
# valor se muestra como "stock bajo" en el
# panel principal.
# =============================

STOCK_MINIMO = 3


# =============================
# RESUMEN
# =============================

def obtener_resumen():
    """
    Conteos del panel principal.

    Usa subconsultas para resolverlo en una
    sola ida y vuelta a la base de datos.
    """

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
                SELECT COALESCE(SUM(precio), 0)
                FROM ventas
            ) AS ingresos
    """

    cursor.execute(consulta, (STOCK_MINIMO,))

    resumen = cursor.fetchone()

    cursor.close()
    conexion.close()

    return resumen


def obtener_ultima_venta():
    """
    Fecha de la venta más reciente, para el
    panel principal.
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
