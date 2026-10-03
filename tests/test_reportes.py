# ==========================================
# REPORTES
# ==========================================
# Lo importante aquí es que todos los reportes de
# ventas usen el MISMO filtro. Si cada uno armara
# el suyo, dos pestañas con las mismas fechas
# acabarían contando cosas distintas y nadie lo
# notaría.
# ==========================================


import pytest

from database.marcas import insertar_marca

from database.autos import insertar_auto

from database.ventas import registrar_venta

from database.reportes import (
    obtener_resumen,
    obtener_ventas_del_dia,
    obtener_top_vehiculos,
    obtener_ventas_por_cliente,
    obtener_detalle_ventas,
    obtener_metricas,
    obtener_clientes_con_compras,
    obtener_ventas_por_vendedor
)


class TestPanel:

    def test_resumen_cuadra_con_las_tablas(
        self, como_administrador, datos_base
    ):
        """
        El resumen cuenta lo mismo que el listado:
        si no, el panel y el reporte darían cifras
        distintas sin que nada avise.
        """

        _, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente, id_auto, "2026-01-15", 25000.0
        )

        resumen = obtener_resumen()

        assert resumen["total_ventas"] == 1
        assert resumen["total_autos"] == 1
        assert resumen["total_clientes"] == 1

    def test_unidades_es_el_stock(
        self, como_administrador, datos_base
    ):
        """
        Ojo con el nombre: "unidades" es el stock
        total de vehículos, no las ventas.
        """

        resumen = obtener_resumen()

        assert resumen["unidades"] == 3

    def test_stock_bajo_usa_el_umbral(
        self, como_administrador
    ):
        from database.configuracion import (
            obtener_stock_minimo,
            actualizar_stock_minimo
        )

        antes = obtener_stock_minimo()

        try:

            id_marca = insertar_marca("Marca Poca")

            insertar_auto(
                id_marca, "Poco", 2024,
                1000.0, "Blanco", 1
            )

            actualizar_stock_minimo(1)

            assert obtener_resumen()["stock_bajo"] == 1

        finally:

            actualizar_stock_minimo(antes)

    def test_ventas_del_dia(
        self, como_administrador, datos_base
    ):
        import datetime

        _, id_auto, id_cliente = datos_base

        hoy = datetime.date.today().isoformat()

        registrar_venta(
            id_cliente, id_auto, hoy, 25000.0
        )

        # Devuelve (cantidad, importe), no un
        # número suelto.

        cantidad, importe = obtener_ventas_del_dia()

        assert cantidad == 1
        assert float(importe) == 25000.0


class TestFiltroCompartido:

    """
    La comprobación que de verdad importa: con el
    mismo filtro, "por cliente" y "por vendedor"
    tienen que contar lo mismo.
    """

    def test_las_cifras_coinciden(
        self, como_administrador, datos_base
    ):
        import datetime

        _, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente, id_auto, "2026-03-01", 25000.0
        )
        registrar_venta(
            id_cliente, id_auto, "2026-03-02", 25000.0
        )
        registrar_venta(
            id_cliente, id_auto, "2026-07-15", 25000.0
        )

        filtros = {
            "desde": "2026-03-01",
            "hasta": "2026-03-31"
        }

        metricas = obtener_metricas(**filtros)

        por_cliente = obtener_clientes_con_compras(
            **filtros
        )

        por_vendedor = obtener_ventas_por_vendedor(
            **filtros
        )

        detalle = obtener_detalle_ventas(**filtros)

        assert metricas["ventas"] == 2
        assert len(detalle) == 2

        # Los tres tienen que sumar lo mismo.

        assert (
            sum(f[1] for f in por_vendedor) == 2
        )

        # obtener_clientes_con_compras devuelve
        # (id, nombre, apellido, compras, importe):
        # el conteo va en el índice 3, no en el 1.

        assert (
            sum(f[3] for f in por_cliente) == 2
        )

    def test_filtrar_por_marca_necesita_el_join(
        self, como_administrador, datos_base
    ):
        """
        El filtro por marca se arma contra
        autos.marca_id. Una consulta que lo use sin
        el JOIN a autos falla con "Unknown column".
        """

        id_marca, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente, id_auto, "2026-03-01", 25000.0
        )

        assert obtener_ventas_por_vendedor(
            marca_id=id_marca
        )

        assert obtener_ventas_por_vendedor(
            marca_id=99999
        ) == []


class TestPorVendedor:

    def test_agrupa_por_cuenta(
        self, como_administrador, datos_base
    ):
        _, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente, id_auto, "2026-03-01", 25000.0
        )
        registrar_venta(
            id_cliente, id_auto, "2026-03-02", 25000.0
        )

        filas = obtener_ventas_por_vendedor()

        assert len(filas) == 1

        vendedor, numero, importe = filas[0]

        assert vendedor == "admin"
        assert numero == 2
        assert float(importe) == 50000.0

    def test_las_ventas_sin_vendedor_su_propio_grupo(
        self, como_administrador, datos_base
    ):
        """
        Las ventas anteriores a la migración del
        vendedor se agrupan como "Sin registrar",
        para que el total cuadre con el número de
        ventas y no parezca que faltan.
        """

        from database.conexion import obtener_conexion

        _, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente, id_auto, "2026-03-01", 25000.0
        )

        conexion = obtener_conexion()

        cursor = conexion.cursor()

        cursor.execute(
            """
            UPDATE ventas
            SET usuario_id = NULL,
                usuario_nombre = NULL
            """
        )

        conexion.commit()
        cursor.close()
        conexion.close()

        filas = obtener_ventas_por_vendedor()

        assert len(filas) == 1
        assert filas[0][0] == "Sin registrar"

    def test_dos_cuentas_se_paran(
        self, como_vendedor, como_administrador,
        datos_base
    ):
        """
        El vendedor registra una venta y el
        administrador otra: dos grupos distintos,
        aunque las dos se hayan hecho desde la misma
        pantalla y con el mismo cliente y vehículo.

        El reporte solo lo ve el administrador, así
        que la sesión se cambia antes de
        consultarlo.
        """

        _, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente, id_auto, "2026-03-01", 1000.0
        )

        import sesion as modulo

        modulo.iniciar_sesion((
            como_administrador,
            "admin",
            "Administrador de pruebas",
            "administrador"
        ))

        registrar_venta(
            id_cliente, id_auto, "2026-03-02", 2000.0
        )

        filas = obtener_ventas_por_vendedor()

        assert len(filas) == 2

        por_nombre = {
            f[0]: (f[1], float(f[2])) for f in filas
        }

        assert por_nombre["vendedor_test"] == (1, 1000.0)
        assert por_nombre["admin"] == (1, 2000.0)

    def test_respeta_el_limite(
        self, como_administrador, datos_base
    ):
        _, id_auto, id_cliente = datos_base

        for dia in range(1, 6):

            registrar_venta(
                id_cliente, id_auto,
                f"2026-03-0{dia}", 100.0
            )

        assert len(obtener_ventas_por_vendedor()) == 1
        assert obtener_ventas_por_vendedor(
            limite=0
        ) == []


class TestPermisos:

    def test_el_vendedor_no_ve_el_por_vendedor(
        self, como_vendedor
    ):
        """
        Es una medida del trabajo de cada persona,
        no un dato comercial: solo el
        administrador.
        """

        from errores import PermisoDenegado

        with pytest.raises(PermisoDenegado):

            obtener_ventas_por_vendedor()

    def test_el_vendedor_si_ve_el_panel(
        self, como_vendedor
    ):
        """
        El resumen del panel pide VER_TABLERO, no
        VER_REPORTES: si se unificaran los
        permisos, el vendedor se quedaría sin
        panel.
        """

        assert obtener_resumen() is not None

        assert obtener_ventas_por_cliente() is not None
