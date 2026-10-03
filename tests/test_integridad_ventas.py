# ==========================================
# INTEGRIDAD DE LAS VENTAS
# ==========================================
# Lo que comprueba aquí es que la base TIENE
# que decir la verdad aunque el código no la
#custodie:
#
#   - ventas.usuario_id tiene su clave foránea
#   - es ON DELETE SET NULL, no CASCADE: borrar
#     la cuenta de un vendedor no puede borrar
#     sus ventas
#   - usuario_nombre es una COPIA, así que al
#     borrar la cuenta el histórico sigue
#     diciendo quién vendió
#   - una venta sin vendedor es válida y se
#     puede ver
#   - el saldo y el pago se deshacen si algo
#     falla a mitad
# ==========================================


import pytest

from database.usuarios import insertar_usuario

from database.contratos import crear_contrato

from database.ventas import registrar_venta

from database.pagos import (
    registrar_pago,
    obtener_pagos,
    saldo_venta,
    eliminar_pago
)

from database.conexion import obtener_conexion


def cruda():
    """Conexión propia, para leer lo que la
    aplicación no expone."""

    return obtener_conexion()


class TestClaveForanea:

    def test_la_columna_existe(
        self, como_administrador, datos_base
    ):
        _, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente, id_auto, "2026-06-01", 1000.0
        )

        conexion = cruda()

        cursor = conexion.cursor()

        cursor.execute("""
            SELECT COLUMN_NAME, IS_NULLABLE,
                   DATA_TYPE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'ventas'
              AND COLUMN_NAME IN ('usuario_id',
                                  'usuario_nombre')
            ORDER BY ORDINAL_POSITION
        """)

        filas = cursor.fetchall()

        cursor.close()
        conexion.close()

        assert len(filas) == 2

        # usuario_id admite NULL: las ventas
        # antiguas no tienen vendedor.

        assert filas[0][0] == "usuario_id"
        assert filas[0][1] == "YES"

        assert filas[1][0] == "usuario_nombre"
        assert filas[1][2] == "varchar"

    def test_la_relacion_existe_y_es_set_null(
        self, como_administrador
    ):
        """
        La relación tiene que existir de verdad,
        con SET NULL. Si alguien la cambiara a
        CASCADE, borrar una cuenta se llevaría
        por delante las ventas de esa persona sin
        avisar.
        """

        conexion = cruda()

        cursor = conexion.cursor()

        cursor.execute("""
            SELECT rc.CONSTRAINT_NAME, rc.DELETE_RULE,
                   kcu.COLUMN_NAME
            FROM information_schema.REFERENTIAL_CONSTRAINTS rc
            JOIN information_schema.KEY_COLUMN_USAGE kcu
                ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
                AND kcu.CONSTRAINT_SCHEMA = rc.CONSTRAINT_SCHEMA
            WHERE rc.CONSTRAINT_SCHEMA = DATABASE()
              AND rc.TABLE_NAME = 'ventas'
              AND kcu.REFERENCED_TABLE_NAME = 'usuarios'
        """)

        filas = cursor.fetchall()

        cursor.close()
        conexion.close()

        assert len(filas) == 1, filas

        nombre, regla, columna = filas[0]

        assert nombre == "ventas_usuario_fk"
        assert columna == "usuario_id"
        assert regla == "SET NULL"

    def test_no_admite_un_usuario_inexistente(
        self, como_administrador, datos_base
    ):
        """
        La clave foránea tiene que impedir
        inventarse un vendedor. Un UPDATE directo
        es la vía que no pasa por la aplicación, y
        por eso la base tiene que guardarla.
        """

        from database.marcas import insertar_marca
        from database.autos import insertar_auto
        from database.clientes import insertar_cliente

        id_auto = insertar_auto(
            insertar_marca("Marca FK"),
            "Modelo FK", 2024, 1000.0, "Rojo", 1
        )

        id_cliente = insertar_cliente(
            "Cliente", "FK", None, None, None
        )

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-06-01", 1000.0
        )

        conexion = cruda()

        cursor = conexion.cursor()

        import mysql.connector

        with pytest.raises(
            mysql.connector.IntegrityError
        ):

            cursor.execute(
                "UPDATE ventas SET usuario_id = 99999 "
                "WHERE id = %s",
                (id_venta,)
            )

        conexion.rollback()

        cursor.close()
        conexion.close()


class TestBorrarLaCuenta:

    def test_la_venta_no_se_borra(
        self, como_administrador, datos_base
    ):
        """
        Lo importante: borrar la cuenta de un
        vendedor NO puede borrar sus ventas.
        """

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-06-01", 1000.0
        )

        # El usuario de la venta es el admin de la
        # prueba, que no se puede borrar a uno
        # mismo. Se crea otro para el caso.

        id_vendedor = insertar_usuario(
            "vendedor_borrable",
            "Vendedor que se va",
            "ClaveBorrable2026",
            "vendedor"
        )

        conexion = cruda()

        cursor = conexion.cursor()

        cursor.execute(
            "UPDATE ventas SET usuario_id = %s, "
            "usuario_nombre = 'vendedor_borrable' "
            "WHERE id = %s",
            (id_vendedor, id_venta)
        )

        conexion.commit()

        cursor.execute(
            "DELETE FROM usuarios WHERE id = %s",
            (id_vendedor,)
        )

        conexion.commit()

        cursor.execute(
            "SELECT COUNT(*) FROM ventas WHERE id = %s",
            (id_venta,)
        )

        sigue = cursor.fetchone()[0]

        # Y el nombre copiado se conserva.

        cursor.execute(
            "SELECT usuario_id, usuario_nombre "
            "FROM ventas WHERE id = %s",
            (id_venta,)
        )

        usuario_id, usuario_nombre = cursor.fetchone()

        cursor.close()
        conexion.close()

        assert sigue == 1, "borrar la cuenta arrastró la venta"

        assert usuario_id is None

        assert usuario_nombre == (
            "vendedor_borrable"
        ), "el nombre copiado se perdió"

    def test_el_listado_lo_dice(
        self, como_administrador, datos_base
    ):
        """
        Cuando usuario_id queda a NULL pero el
        nombre se conserva, el listado debe
        seguir enseñando el nombre: para eso está
        la copia.
        """

        from database.ventas import obtener_ventas

        _, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente, id_auto, "2026-06-01", 1000.0
        )

        id_vendedor = insertar_usuario(
            "otro_borrable",
            "Otro Vendedor",
            "ClaveOtro2026",
            "vendedor"
        )

        conexion = cruda()

        cursor = conexion.cursor()

        cursor.execute(
            "UPDATE ventas SET usuario_id = %s, "
            "usuario_nombre = 'otro_borrable'",
            (id_vendedor,)
        )

        conexion.commit()

        cursor.execute(
            "DELETE FROM usuarios WHERE id = %s",
            (id_vendedor,)
        )

        conexion.commit()

        cursor.close()
        conexion.close()

        filas = obtener_ventas()

        # La sexta columna es el nombre del
        # vendedor.

        assert filas[0][5] == "otro_borrable"


class TestVentasAntiguas:

    def test_sin_vendedor_es_valido(
        self, como_administrador, datos_base
    ):
        """
        Las ventas anteriores a la migración no
        tienen vendedor. tienen que seguir siendo
        válidas y visibles, no desaparecer.
        """

        from database.ventas import obtener_ventas
        from database.reportes import (
            obtener_ventas_por_vendedor
        )

        _, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente, id_auto, "2026-06-01", 1000.0
        )

        conexion = cruda()

        cursor = conexion.cursor()

        cursor.execute(
            "UPDATE ventas SET usuario_id = NULL, "
            "usuario_nombre = NULL"
        )

        conexion.commit()

        cursor.close()
        conexion.close()

        # Se ve en el listado.

        assert len(obtener_ventas()) == 1

        # Y sale en el reporte como grupo propio,
        # para que el total cuadre.

        filas = obtener_ventas_por_vendedor()

        assert len(filas) == 1
        assert filas[0][0] == "Sin registrar"
        assert filas[0][1] == 1

    def test_el_listado_no_deja_un_hueco(
        self, como_administrador, datos_base
    ):
        """
        Donde el nombre es None, la vista tiene que
        poner algo legible. Un hueco en blanco en
        una columna parece un fallo.
        """

        from database.ventas import obtener_ventas

        _, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente, id_auto, "2026-06-01", 1000.0
        )

        conexion = cruda()

        cursor = conexion.cursor()

        cursor.execute(
            "UPDATE ventas SET usuario_id = NULL, "
            "usuario_nombre = NULL"
        )

        conexion.commit()

        cursor.close()
        conexion.close()

        fila = obtener_ventas()[0]

        assert fila[5] is None

        # Lo que la vista tiene que poner:

        assert (fila[5] or "Sin registrar") == (
            "Sin registrar"
        )


class TestTransacciones:

    def test_el_pago_no_se_parte(
        self, como_administrador, datos_base
    ):
        """
        Si el pago falla, no queda ni el pago ni
        el saldo movido.
        """

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-06-01", 1000.0
        )

        _, _, saldo_antes = saldo_venta(id_venta)

        # Un importe que no pasa la validación.

        id_pago, motivo = registrar_pago(
            id_venta, 99999.0, "2026-06-02", "Efectivo"
        )

        assert id_pago is None

        _, _, saldo_despues = saldo_venta(id_venta)

        assert float(saldo_despues) == float(saldo_antes)
        assert obtener_pagos(id_venta) == []

    def test_fallo_a_medio_hace_rollback(
        self, como_administrador, datos_base
    ):
        """
        Si algo revienta cuando ya se esta dentro de
        la transaccion, tiene que haber rollback y
        no commit.

        Se comprueba con un doble: la conexion es
        fingida, asi que se puede ver que metodos
        llamo la funcion. El estado de verdad se
        comprueba despues, en la base real.
        """

        from unittest.mock import MagicMock

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-06-01", 1000.0
        )

        registrar_pago(
            id_venta, 400.0, "2026-06-02", "Efectivo"
        )

        _, _, antes = saldo_venta(id_venta)

        conexion = MagicMock()

        cursor = conexion.cursor.return_value

        cursor.fetchone.side_effect = [
            {"id": id_venta, "precio": 1000.0},
            {"pagado": 400.0},
            None
        ]

        def ejecutar(sentencia, valores=None):

            if "INSERT INTO pagos" in sentencia:

                raise RuntimeError("fallo simulado")

        cursor.execute.side_effect = ejecutar

        import database.pagos as modulo

        original = modulo.obtener_conexion

        modulo.obtener_conexion = lambda: conexion

        try:

            with pytest.raises(RuntimeError):

                registrar_pago(
                    id_venta, 100.0, "2026-06-03",
                    "Efectivo"
                )

        finally:

            modulo.obtener_conexion = original

        # Lo que importa: rollback, y NUNCA commit.

        assert conexion.rollback.called

        assert not conexion.commit.called

        # Y en la base real no ha cambiado nada.

        assert len(obtener_pagos(id_venta)) == 1

        _, _, despues = saldo_venta(id_venta)

        assert float(despues) == float(antes)

    def test_el_saldo_usa_la_base_y_no_python(
        self, como_administrador, datos_base
    ):
        """
        El saldo se calcula con SUM() en SQL. Si
        se calculara trayendo los pagos a Python, un
        pago de otra venta se colaría en la suma.
        """

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-06-01", 1000.0
        )

        otra, _ = registrar_venta(
            id_cliente, id_auto, "2026-06-02", 2000.0
        )

        registrar_pago(
            id_venta, 300.0, "2026-06-03", "Efectivo"
        )

        registrar_pago(
            otra, 1500.0, "2026-06-03", "Efectivo"
        )

        precio, pagado, saldo = saldo_venta(id_venta)

        assert float(pagado) == 300.0
        assert float(saldo) == 700.0

        precio, pagado, saldo = saldo_venta(otra)

        assert float(pagado) == 1500.0
        assert float(saldo) == 500.0

    def test_el_anticipo_no_cuenta_como_pago(
        self, como_administrador, datos_base
    ):
        """
        Un contrato con anticipo dice QUE se debe
        pagar de menos, no que ya se pagó. El saldo
        tiene que salir entero hasta que se
        registre el pago de verdad.
        """

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-06-01", 25000.0
        )

        crear_contrato(
            venta_id=id_venta,
            forma_pago="Anticipo + cuotas",
            anticipo=5000.0,
            cantidad_cuotas=10
        )

        precio, pagado, saldo = saldo_venta(id_venta)

        assert float(pagado) == 0
        assert float(saldo) == 25000.0

        # Y cuando se registra el pago del
        # anticipo, ya sí descuenta.

        registrar_pago(
            id_venta, 5000.0, "2026-06-02", "Efectivo",
            concepto="Anticipo"
        )

        precio, pagado, saldo = saldo_venta(id_venta)

        assert float(pagado) == 5000.0
        assert float(saldo) == 20000.0

    def test_la_venta_no_se_anula_con_dinero(
        self, como_administrador, datos_base
    ):
        from database.ventas import eliminar_venta

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-06-01", 1000.0
        )

        registrar_pago(
            id_venta, 100.0, "2026-06-02", "Efectivo"
        )

        assert eliminar_venta(id_venta) is False

        # Y tras deshacer el pago, sí se puede.

        id_pago = obtener_pagos(id_venta)[0][0]

        eliminar_pago(id_pago)

        assert eliminar_venta(id_venta) is True
