# ==========================================
# VENTAS
# ==========================================
# Lo importante aquí es la transacción:
#   - bloquea el vehículo con SELECT ... FOR
#     UPDATE
#   - comprueba el stock
#   - inserta y descuenta
#   - al anular, devuelve la unidad
# ==========================================


import pytest

from database.marcas import insertar_marca
from database.clientes import insertar_cliente
from database.autos import (
    obtener_autos,
    insertar_auto,
    actualizar_auto
)

from database.ventas import (
    obtener_ventas,
    obtener_ventas_recientes,
    contar_ventas_de_auto,
    registrar_venta,
    eliminar_venta
)


def stock_de(id_auto):
    for fila in obtener_autos():

        if fila[0] == id_auto:

            return fila[6]


class TestRegistrar:

    def test_devuelve_el_id_de_la_venta(
        self, como_administrador, datos_base
    ):
        """
        Devuelve el id, no True: con el id el
        formulario puede ofrecer el contrato sin
        volver a buscarla. (Antes devolvía True y
        eso también funcionaba porque solo se
        miraba la veracidad.)

        Al fallar devuelve False, no None: por eso
        las pruebas comprueban la veracidad y no
        la identidad.
        """

        _, id_auto, id_cliente = datos_base

        resultado, mensaje = registrar_venta(
            id_cliente, id_auto, "2026-01-15", 25000.0
        )

        assert isinstance(resultado, int)
        assert resultado > 0
        assert mensaje == ""

    def test_descuenta_una_unidad(
        self, como_administrador, datos_base
    ):
        _, id_auto, id_cliente = datos_base

        assert stock_de(id_auto) == 3

        registrar_venta(
            id_cliente, id_auto, "2026-01-15", 25000.0
        )

        assert stock_de(id_auto) == 2

    def test_no_deja_vender_sin_stock(
        self, como_administrador
    ):
        id_marca = insertar_marca("Kia")

        id_auto = insertar_auto(
            id_marca, "Rio", 2023, 18000.0, "Gris", 0
        )

        id_cliente = insertar_cliente(
            "Ana", "García", None, None
        )

        resultado, mensaje = registrar_venta(
            id_cliente, id_auto, "2026-01-15", 18000.0
        )

        assert not resultado
        assert "stock" in mensaje.lower()

    def test_no_deja_quedarse_sin_stock(
        self, como_administrador, datos_base
    ):
        """
        Con stock 1, la segunda venta falla y la
        primera sigue intacta.
        """

        id_marca, id_auto, id_cliente = datos_base

        actualizar_auto(
            id_auto, id_marca, "Corolla", 2024,
            25000.0, "Blanco", 1
        )

        registrar_venta(
            id_cliente, id_auto, "2026-01-15", 25000.0
        )

        resultado, _ = registrar_venta(
            id_cliente, id_auto, "2026-01-16", 25000.0
        )

        assert not resultado
        assert stock_de(id_auto) == 0

    def test_congela_el_precio(
        self, como_administrador, datos_base
    ):
        """
        ventas.precio guarda el precio del
        momento. Si después sube el del vehículo,
        la venta antigua no cambia.
        """

        id_marca, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente, id_auto, "2026-01-15", 25000.0
        )

        actualizar_auto(
            id_auto, id_marca, "Corolla", 2024,
            99000.0, "Blanco", 3
        )

        fila = obtener_ventas()[0]

        # La venta sale con el precio del
        # momento: 25000, no 99000.

        assert float(fila[4]) == 25000.0

    def test_rechaza_cliente_inexistente(
        self, como_administrador, datos_base
    ):
        _, id_auto, _ = datos_base

        resultado, mensaje = registrar_venta(
            99999, id_auto, "2026-01-15", 25000.0
        )

        assert not resultado
        assert mensaje

    def test_rechaza_vehiculo_inexistente(
        self, como_administrador, datos_base
    ):
        _, _, id_cliente = datos_base

        resultado, mensaje = registrar_venta(
            id_cliente, 99999, "2026-01-15", 25000.0
        )

        assert not resultado
        assert mensaje


class TestListado:

    def test_devuelve_texto_concatenado(
        self, como_administrador, datos_base
    ):
        """
        Los dos campos de texto son CONCAT, no
        ids: VentasView los pinta directamente. La
        sexta columna es el nombre del vendedor y
        puede venir a None en las ventas antiguas.
        """

        _, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente, id_auto, "2026-01-15", 25000.0
        )

        fila = obtener_ventas()[0]

        assert len(fila) == 6
        assert "Ana" in fila[2]
        assert "Corolla" in fila[3]

    def test_filtra_por_rango_de_fechas(
        self, como_administrador, datos_base
    ):
        _, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente, id_auto, "2026-01-10", 25000.0
        )
        registrar_venta(
            id_cliente, id_auto, "2026-02-10", 25000.0
        )

        enero = obtener_ventas(
            desde="2026-01-01",
            hasta="2026-01-31"
        )

        febrero = obtener_ventas(
            desde="2026-02-01",
            hasta="2026-02-28"
        )

        assert len(enero) == 1
        assert len(febrero) == 1

    def test_filtra_por_texto(
        self, como_administrador, datos_base
    ):
        _, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente, id_auto, "2026-01-15", 25000.0
        )

        assert len(buscar_por("Corolla")) == 1
        assert len(buscar_por("zzzz")) == 0

    def test_recientes_respeta_el_limite(
        self, como_administrador, datos_base
    ):
        _, id_auto, id_cliente = datos_base

        for dia in range(1, 6):

            registrar_venta(
                id_cliente, id_auto,
                f"2026-01-0{dia}", 25000.0
            )

        assert len(obtener_ventas_recientes(3)) == 3

    def test_contar_ventas_de_auto(
        self, como_administrador, datos_base
    ):
        _, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente, id_auto, "2026-01-15", 25000.0
        )

        assert contar_ventas_de_auto(id_auto) == 1


def buscar_por(texto):
    from database.ventas import obtener_ventas

    return obtener_ventas(texto=texto)


class TestAnular:

    def test_devuelve_la_unidad_al_stock(
        self, como_administrador, datos_base
    ):
        _, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente, id_auto, "2026-01-15", 25000.0
        )

        assert stock_de(id_auto) == 2

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-01-16", 25000.0
        )

        assert eliminar_venta(id_venta) is True
        assert stock_de(id_auto) == 2

    def test_quita_la_venta_del_listado(
        self, como_administrador, datos_base
    ):
        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-01-15", 25000.0
        )

        eliminar_venta(id_venta)

        assert obtener_ventas() == []

    def test_venta_inexistente_no_revienta(
        self, como_administrador, datos_base
    ):
        """
        Devuelve False en vez de lanzar, para que
        la vista pueda explicar que la venta ya no
        está.
        """

        assert eliminar_venta(99999) is False


class TestPermisos:

    def test_cualquiera_registra_ventas(
        self, como_vendedor, datos_base
    ):
        """
        El vendedor registra ventas: es su trabajo.
        """

        _, id_auto, id_cliente = datos_base

        resultado, _ = registrar_venta(
            id_cliente, id_auto, "2026-01-15", 25000.0
        )

        assert isinstance(resultado, int)

    def test_vendedor_no_anula(
        self, como_vendedor, datos_base
    ):
        from errores import PermisoDenegado

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-01-15", 25000.0
        )

        with pytest.raises(PermisoDenegado):

            eliminar_venta(id_venta)


class TestVendedor:

    def test_guarda_quien_registro(
        self, como_administrador, datos_base
    ):
        """
        La venta dice quién la hizo. usuario_nombre
        es una copia: si la cuenta se borra,
        usuario_id pasa a NULL pero el nombre se
        queda.
        """

        _, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente, id_auto, "2026-01-15", 25000.0
        )

        fila = obtener_ventas()[0]

        assert fila[5] == "admin"

    def test_el_vendedor_tambien_queda(
        self, como_vendedor, datos_base
    ):
        _, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente, id_auto, "2026-01-15", 25000.0
        )

        assert obtener_ventas()[0][5] == (
            "vendedor_test"
        )

class TestAuditoria:

    def test_crear_deja_rastro(
        self, como_administrador, datos_base
    ):
        from database.auditoria import obtener_auditoria

        _, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente, id_auto, "2026-01-15", 25000.0
        )

        registros = obtener_auditoria()

        assert registros[0][3] == "VENTA"
        assert registros[0][4] == "ventas"

    def test_el_rastro_no_se_pierde_al_anular(
        self, como_administrador, datos_base
        ):
        """
        Anular no borra el rastro anterior: el
        histórico dice que la venta existió y
        luego se anuló.
        """

        from database.auditoria import obtener_auditoria

        _, id_auto, id_cliente = datos_base

        id_venta, _ = registrar_venta(
            id_cliente, id_auto, "2026-01-15", 25000.0
        )

        eliminar_venta(id_venta)

        acciones = [r[3] for r in obtener_auditoria()]

        assert "CREAR" in acciones
        assert "VENTA_ANULADA" in acciones
