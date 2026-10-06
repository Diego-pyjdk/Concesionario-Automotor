from database.conexion import conexiones_libres
import mysql.connector

from database.conexion import obtener_conexion

from database.auditoria import registrar_accion

from utils.moneda import formato_dinero

import sesion as modulo_sesion

from permisos import (
    requiere_permiso,
    REGISTRAR_VENTAS,
    GESTIONAR_VENTAS
)


# =============================
# LISTAR


# =============================

def moneda_de_venta(id_venta):
    """
    La moneda con la que se registró una venta, o None.

    ------------------------------
    # POR QUÉ UNA CONSULTA SUELTA Y
    # NO UNA COLUMNA MÁS EN
    # obtener_ventas()
    # ------------------------------

    Porque `obtener_ventas()` tiene un contrato de seis
    columnas que está escrito en tres sitios más
    (`VentasView.pintar_fila`, `VentasView.ver_venta` y
    el ancho de columna), y todas lo leen por posición.
    Añadir una séptima no rompe la vista: rompe el
    `pintar_fila` que compara contra el número de
    columnas, y el fallo sale en pantalla, no en los
    datos.

    Y la moneda solo hace falta en un sitio: al abrir
    el detalle de la venta. Una consulta de más ahí,
    y las 6 columnas siguen siendo 6 para todos los
    demás.

    Devuelve el código tal cual está, aunque no sea una
    moneda del catálogo: es un dato, no una opinión.
    Si no existe la venta, None.
    """

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT moneda
        FROM ventas
        WHERE id = %s
        """,
        (id_venta,)
    )

    fila = cursor.fetchone()

    cursor.close()
    conexion.close()

    if not fila:

        return None

    return fila[0]


def obtener_ventas(desde=None, hasta=None, texto=None):
    """
    Lista las ventas con el nombre del cliente y
    el vehículo ya resueltos por JOIN.

    desde / hasta son fechas opcionales (YYYY-MM-DD).
    texto filtra por cliente o vehículo.

    Contrato de columnas: id, fecha, cliente,
    vehiculo, precio, usuario_nombre. La última
    puede venir a None en las ventas anteriores a
    la migración del vendedor; quien la pinte debe
    poner algo legible en su lugar, no un hueco.

    Está escrito en tres sitios más:
    VentasView.pintar_fila, VentasView.ver_venta
    y el ancho de columna en VentasView.columnas.
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
            ventas.precio,
            ventas.usuario_nombre
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

@conexiones_libres
@requiere_permiso(REGISTRAR_VENTAS)
def registrar_venta(
    cliente_id, auto_id, fecha, precio, moneda=None, unidad_id=None
):
    """
    Registra una venta dentro de una transacción.

    La transacción es obligatoria: si el INSERT
    falla, el stock no debe quedar descontado.

    Pasos dentro de la transacción:
      1. Bloquear el vehículo y verificar stock.
      2. Insertar la venta.
      3. Descontar una unidad.

    moneda es el código con el que se hace ESTA venta,
    no una conversión: el importe es el que es y se
    guarda dicho en la moneda que diga. Si no se pasa,
    es la que hay configurada ahora, que es lo que
    quiere decir una venta que alguien está
    registrar en este momento.

    Se guarda por lo mismo que `contratos.moneda`: una
    venta de 25.000 dólares tiene que seguir siendo una
    venta de 25.000 dólares cuando el concesionario
    cambie la moneda de la aplicación dentro de seis
    meses. Sin esta columna, el mismo documento pasa a
    decir "Gs. 25.000" sin que nadie haya convertido
    nada, y las dos cosas son falsas a la vez.

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

        cursor.execute("""SELECT COUNT(*) FROM unidades_vehiculo u
            LEFT JOIN venta_unidades vu ON vu.unidad_id=u.id
            WHERE u.auto_id=%s AND vu.venta_id IS NULL""", (auto_id,))
        identificadas = cursor.fetchone()[0]
        if unidad_id is not None:
            cursor.execute("""SELECT u.estado,vu.venta_id FROM unidades_vehiculo u
                LEFT JOIN venta_unidades vu ON vu.unidad_id=u.id
                WHERE u.id=%s AND u.auto_id=%s FOR UPDATE""", (unidad_id, auto_id))
            unidad = cursor.fetchone()
            if not unidad or unidad[0] != 'disponible' or unidad[1] is not None:
                conexion.rollback()
                cursor.close()
                conexion.close()
                return False, "La unidad seleccionada ya no está disponible."
        elif identificadas >= stock:
            conexion.rollback()
            cursor.close()
            conexion.close()
            return False, "Selecciona una unidad disponible por su chasis/VIN."

        # ------------------------------
        # 2. INSERTAR VENTA
        # ------------------------------
        # Se guarda QUIÉN registró la venta, no solo
        # el cliente y el vehículo.
        #
        # usuario_nombre es una copia, igual que en
        # auditoria: si luego se borra la cuenta,
        # usuario_id pasa a NULL pero el nombre se
        # queda y el histórico sigue diciendo quién
        # vendió cada vehículo.

        usuario = modulo_sesion.obtener_sesion()

        # ------------------------------
        # 2b. LA MONEDA DE LA VENTA
        # ------------------------------
        # Se escribe AHORA, con la moneda que hay en
        # este momento, y no se vuelve a tocar. Es la
        # cifra que se acaba de pactar en una moneda
        # concreta: eso es un hecho, no un ajuste.

        if not moneda:

            from utils.moneda import config_actual

            moneda = config_actual()["codigo"]

        consulta_venta = """
            INSERT INTO ventas
            (
                cliente_id,
                auto_id,
                usuario_id,
                usuario_nombre,
                fecha,
                precio,
                moneda
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        cursor.execute(
            consulta_venta,
            (
                cliente_id,
                auto_id,
                usuario.id_usuario,
                usuario.nombre_usuario,
                fecha,
                precio,
                str(moneda)
            )
        )

        id_venta = cursor.lastrowid

        # ------------------------------
        # 3. DESCONTAR STOCK
        # ------------------------------

        consulta_stock = """
            UPDATE autos
            SET stock = stock - 1
            WHERE id = %s
        """

        cursor.execute(consulta_stock, (auto_id,))

        if unidad_id is not None:
            cursor.execute("INSERT INTO venta_unidades (venta_id,unidad_id) VALUES (%s,%s)",
                           (id_venta, unidad_id))

        conexion.commit()

        # Se registra DESPUÉS del commit: si la
        # transacción se revirtiera, el rastro
        # mentiría.

        registrar_accion(
            "ventas",
            "VENTA",
            f"Venta por {formato_dinero(float(precio))} del "
            f"vehículo {auto_id} a cliente {cliente_id}"
        )

        cursor.close()
        conexion.close()

        # Se devuelve el id, no True. Quien llama
        # solo mira si es cierto, así que sigue
        # funcionando igual, pero con el id puede
        # ofrecer crear el contrato de esta venta
        # sin tener que volver a buscarla.

        return id_venta, ""

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

@conexiones_libres
@requiere_permiso(GESTIONAR_VENTAS)
def eliminar_venta(id_venta):
    """
    Elimina una venta y devuelve la unidad al
    stock del vehículo, en la misma transacción.

    Sin la devolución de stock, el inventario
    quedaría descuadrado respecto del histórico.

    Si la venta tiene un contrato no se anula:
    el contrato es un documento firmado y no
    puede quedarse colgando de una venta que ya
    no existe. Se devuelve False, como con
    cualquier otra clave foránea.
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

        # ------------------------------
        # CONTRATO VIVO
        # ------------------------------
        # La clave foránea de contratos ya lo
        # impediría (ON DELETE RESTRICT), pero
        # llegar aquí saltándose esa excepción
        # perdería el motivo: se avisaría de un
        # "no se pudo anular" sin decir por qué.

        consulta_contrato = """
            SELECT numero, estado
            FROM contratos
            WHERE venta_id = %s
        """

        cursor.execute(
            consulta_contrato, (id_venta,)
        )

        contrato = cursor.fetchone()

        if contrato and contrato[1] != "cancelado":
            conexion.rollback()

            cursor.close()
            conexion.close()

            return False

        # Un contrato cancelado no surte efecto, pero
        # su fila sigue apuntando a la venta y la
        # clave foranea (ON DELETE RESTRICT) impediría
        # el DELETE. Hay que llevárselo delante, en la
        # misma transacción.
        #
        # Es lo mismo que hace crear_contrato() cuando
        # rehace uno cancelado. Si aquí no se borrara,
        # la promesa de "cancelado no bloquea" sería
        # falsa y el DELETE saltaría por la excepción
        # devolviendo un False sin motivo aparente.

        if contrato:
            cursor.execute(
                """
                DELETE FROM contratos
                WHERE venta_id = %s
                    AND estado = 'cancelado'
                """,
                (id_venta,)
            )

        # ------------------------------
        # PAGOS COBRADOS
        # ------------------------------
        # Si ya entró dinero, la venta no se anula
        # en silencio. La clave foránea de pagos
        # (ON DELETE RESTRICT) también lo impediría,
        # pero saltar por esa excepción daría un
        # False sin explicación.
        #
        # A diferencia del contrato cancelado, aquí
        # no hay nada que borrar antes: un pago es
        # un hecho económico y deshacerlo es una
        # operación aparte, y por eso la decide
        # pagos.eliminar_pago(), que exige permiso
        # de administrador y deja rastro.

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM pagos
            WHERE venta_id = %s
            """,
            (id_venta,)
        )

        if cursor.fetchone()[0] > 0:
            conexion.rollback()

            cursor.close()
            conexion.close()

            return False

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

        registrar_accion(
            "ventas",
            "VENTA_ANULADA",
            f"Venta {id_venta} anulada; "
            f"devuelta 1 unidad al vehículo {auto_id}"
        )

        cursor.close()
        conexion.close()

        return True

    except mysql.connector.Error:

        conexion.rollback()

        cursor.close()
        conexion.close()

        return False
