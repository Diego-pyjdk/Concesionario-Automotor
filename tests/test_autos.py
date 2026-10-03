# ==========================================
# VEHÍCULOS
# ==========================================
# CRUD y el contrato de columnas que comparten
# AutosView, AutoForm y ReportesView.
# ==========================================


import pytest

from database.marcas import insertar_marca

from database.autos import (
    obtener_autos,
    buscar_autos,
    obtener_autos_para_venta,
    insertar_auto,
    actualizar_auto,
    eliminar_auto
)

from database.ventas import registrar_venta


class TestOrdenDeColumnas:
    """
    obtener_autos devuelve exactamente 7 columnas
    en un orden fijo. Ese orden está escrito en
    tres sitios más (AutosView, AutoForm y las
    consultas de stock), así que hay que
    comprobarlo: reordenar aquí rompe la
    interfaz sin que la capa de datos se entere.
    """

    def test_devuelve_siete_columnas(
        self, como_administrador, datos_base
    ):
        assert len(obtener_autos()[0]) == 7

    def test_primera_es_id_ultima_es_stock(
        self, como_administrador, datos_base
    ):
        id_marca, id_auto, _ = datos_base

        fila = obtener_autos()[0]

        assert fila[0] == id_auto
        assert fila[1] == "Toyota"
        assert fila[2] == "Corolla"
        assert fila[3] == 2024
        assert float(fila[4]) == 25000.0
        assert fila[5] == "Blanco"
        assert fila[6] == 3

    def test_stock_para_venta_son_cuatro(
        self, como_administrador, datos_base
    ):
        """
        El ComboBox del formulario de venta usa
        otra forma: id, etiqueta, precio, stock.
        """

        filas = obtener_autos_para_venta()

        assert len(filas[0]) == 4

    def test_para_venta_incluye_los_agotados(
        self, como_administrador
    ):
        """
        El ComboBox de la venta los enseña igual,
        con el stock a 0. No los filtra: el
        formulario es quien avisa de que no hay
        unidades, y así el vendedor ve que el
        modelo existe aunque ahora no haya.
        """

        id_marca = insertar_marca("Kia Agotado")

        id_auto = insertar_auto(
            id_marca, "Rio", 2023, 18000.0, "Gris", 0
        )

        filas = obtener_autos_para_venta()

        assert len(filas) == 1
        assert filas[0][0] == id_auto
        assert filas[0][3] == 0


class TestBusqueda:

    def test_encuentra_por_modelo(
        self, como_administrador, datos_base
    ):
        assert len(buscar_autos("corolla")) == 1

    def test_encuentra_por_marca(
        self, como_administrador, datos_base
        ):
        assert len(buscar_autos("toyota")) == 1

    def test_sin_resultados_devuelve_vacio(
        self, como_administrador, datos_base
    ):
        assert buscar_autos("ferrari") == []


class TestEscritura:

    def test_insertar_devuelve_el_id(
        self, como_administrador
    ):
        id_marca = insertar_marca("Kia")

        assert isinstance(
            insertar_auto(
                id_marca, "Rio", 2023,
                18000.0, "Gris", 5
            ),
            int
        )

    def test_actualizar_cambia_los_datos(
        self, como_administrador, datos_base
    ):
        id_marca, id_auto, _ = datos_base

        actualizar_auto(
            id_auto, id_marca, "Corolla Hybrid",
            2025, 28000.0, "Negro", 7
        )

        fila = obtener_autos()[0]

        assert fila[2] == "Corolla Hybrid"
        assert fila[3] == 2025
        assert fila[6] == 7

    def test_eliminar_borra(
        self, como_administrador
    ):
        id_marca = insertar_marca("Kia")

        id_auto = insertar_auto(
            id_marca, "Rio", 2023, 18000.0, "Gris", 1
        )

        assert eliminar_auto(id_auto) is True
        assert obtener_autos() == []

    def test_no_se_puede_borrar_con_ventas(
        self, como_administrador, datos_base
    ):
        _, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente, id_auto, "2026-01-15", 25000.0
        )

        # Igual que con marcas y clientes: False
        # en vez de excepción, para que la vista
        # pueda explicarlo.

        assert eliminar_auto(id_auto) is False
        assert len(obtener_autos()) == 1


class TestAuditoria:

    def test_crear_deja_rastro(
        self, como_administrador
    ):
        from database.auditoria import obtener_auditoria

        id_marca = insertar_marca("Kia")

        insertar_auto(
            id_marca, "Rio", 2023, 18000.0, "Gris", 1
        )

        registros = obtener_auditoria()

        assert registros[0][3] == "CREAR"
        assert registros[0][4] == "vehiculos"

    def test_el_precio_no_deja_rastro_del_valor(
        self, como_administrador
    ):
        """
        El rastro guarda nombres, no el valor del
        campo: cambiar un precio no debe quedar
        escrito con el importe nuevo.
        """

        from database.auditoria import obtener_auditoria

        id_marca = insertar_marca("Kia")

        id_auto = insertar_auto(
            id_marca, "Rio", 2023, 18000.0, "Gris", 1
        )

        actualizar_auto(
            id_auto, id_marca, "Rio",
            2023, 99999.0, "Gris", 1
        )

        descripciones = " ".join(
            r[5] or "" for r in obtener_auditoria()
        )

        assert "99999" not in descripciones


class TestPermisos:

    def test_vendedor_no_gestiona_vehiculos(
        self, como_vendedor, datos_base
    ):
        from errores import PermisoDenegado

        id_marca, _, _ = datos_base

        with pytest.raises(PermisoDenegado):

            insertar_auto(
                id_marca, "Rio", 2023,
                18000.0, "Gris", 1
            )

    def test_vendedor_si_puede_leer(
        self, como_vendedor, datos_base
    ):
        assert len(obtener_autos()) == 1
