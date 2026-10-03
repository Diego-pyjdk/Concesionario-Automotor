# ==========================================
# CLIENTES
# ==========================================
# CRUD, detección de duplicados y el campo
# `documento` que se añadió para los contratos.
# ==========================================


import pytest

from database.clientes import (
    obtener_clientes,
    buscar_clientes,
    obtener_clientes_para_venta,
    cliente_duplicado,
    contar_ventas_de_cliente,
    insertar_cliente,
    actualizar_cliente,
    eliminar_cliente
)

from database.ventas import registrar_venta


class TestLectura:

    def test_no_hay_clientes_en_una_limpia(
        self, como_administrador
    ):
        assert obtener_clientes() == []

    def test_devuelve_las_seis_columnas(
        self, como_administrador
    ):
        insertar_cliente(
            "Ana", "García", "0981234567",
            "ana@correo.com", "1712345678"
        )

        fila = obtener_clientes()[0]

        # El orden es un contrato con
        # ClientesView y ClienteForm: id, nombre,
        # apellido, telefono, email, documento.

        assert len(fila) == 6
        assert fila[1] == "Ana"
        assert fila[5] == "1712345678"

    def test_documento_es_opcional(
        self, como_administrador
    ):
        insertar_cliente(
            "Ana", "García", "0981234567",
            "ana@correo.com"
        )

        assert obtener_clientes()[0][5] is None

    def test_guarda_lo_que_le_dan(
        self, como_administrador
    ):
        """
        La capa de datos guarda tal cual. Quien
        convierte "" en NULL es ClienteForm, no
        insertar_cliente(): aqui una cadena vacia
        se queda como cadena vacia.
        """

        insertar_cliente(
            "Ana", "García", "", "", ""
        )

        fila = obtener_clientes()[0]

        assert fila[3] == ""
        assert fila[4] == ""

    def test_el_nulo_si_se_guarda_como_nulo(
        self, como_administrador
    ):
        """
        Es lo que termina haciendo el formulario:
        antes de llamar, convierte el campo vacio
        en None.
        """

        id_cliente = insertar_cliente(
            "Ana", "García", None, None, None
        )

        actualizar_cliente(
            id_cliente,
            "Ana", "García",
            None, None, None
        )

        fila = obtener_clientes()[0]

        assert fila[3] is None
        assert fila[4] is None
        assert fila[5] is None

    def test_buscar_encuentra(
        self, como_administrador
    ):
        insertar_cliente(
            "Mercedes", "Ríos",
            "0991111111", "mercedes@correo.com"
        )

        assert len(buscar_clientes("merce")) == 1

    def test_buscar_sin_resultados_devuelve_vacio(
        self, como_administrador
    ):
        insertar_cliente("Ana", "García", None, None)

        assert buscar_clientes("zzz") == []

    def test_para_venta_trae_id_y_etiqueta(
        self, como_administrador
    ):
        id_cliente = insertar_cliente(
            "Ana", "García", None, None
        )

        clientes = obtener_clientes_para_venta()

        assert clientes[0][0] == id_cliente
        assert "Ana" in clientes[0][1]


class TestDuplicados:

    def test_detecta_por_correo(
        self, como_administrador
    ):
        insertar_cliente(
            "Ana", "García", None, "ana@correo.com"
        )

        assert cliente_duplicado(
            "Otra", "Persona", None, "ana@correo.com"
        ) is True

    def test_detecta_por_nombre_completo_y_telefono(
        self, como_administrador
    ):
        insertar_cliente(
            "Ana", "García", "0981234567", None
        )

        # Correo distinto y nombre completo igual:
        # si el teléfono coincide, es la misma
        # persona.

        assert cliente_duplicado(
            "Ana", "García", "0981234567",
            "otro@correo.com"
        ) is True

    def test_no_confunde_personas_distintas(
        self, como_administrador
    ):
        insertar_cliente(
            "Ana", "García", "0981234567", None
        )

        assert cliente_duplicado(
            "Ana", "García", "0999999999", None
        ) is False

    def test_editar_se_excluye_a_si_mismo(
        self, como_administrador
    ):
        id_cliente = insertar_cliente(
            "Ana", "García", None, "ana@correo.com"
        )

        # Sin el id, detectaría su propio registro
        # y no se podría editar nunca.

        assert cliente_duplicado(
            "Ana", "García", None, "ana@correo.com",
            id_cliente
        ) is False

    def test_ignora_mayusculas_en_el_correo(
        self, como_administrador
    ):
        insertar_cliente(
            "Ana", "García", None, "ana@correo.com"
        )

        assert cliente_duplicado(
            "Otro", "Persona", None, "ANA@correo.com"
        ) is True

    def test_sin_telefono_compara_nulo_con_nulo(
        self, como_administrador
    ):
        """
        La comparacion de telefono es "<=>",
        que en MySQL trata NULL como igual a
        NULL. Dos fichas con el mismo nombre
        completo y sin telefono se consideran la
        misma persona.

        Conviene que quede escrito: es una
        decision, no un accidente. Si prefieres
        solo comparar cuando hay telefono, hay
        que quitar la condicion cuando telefono
        viene vacio.
        """

        insertar_cliente("Ana", "García", None, None)

        assert cliente_duplicado(
            "Ana", "García", None, None
        ) is True

    def test_sin_apellido_no_hay_que_comparar(
        self, como_administrador
    ):
        """
        Sin nombre y apellido completos no hay
        condicion de nombre, asi que solo cuenta
        el correo.
        """

        insertar_cliente("Ana", "García", None, None)

        # El mismo nombre sin apellido no activa
        # la segunda condicion.

        assert cliente_duplicado(
            "Ana", None, None, None
        ) is False


class TestEscritura:

    def test_insertar_devuelve_el_id(
        self, como_administrador
    ):
        assert isinstance(
            insertar_cliente("Ana", "García", None, None),
            int
        )

    def test_actualizar_cambia_los_datos(
        self, como_administrador
    ):
        id_cliente = insertar_cliente(
            "Ana", "García", None, None
        )

        actualizar_cliente(
            id_cliente, "Ana María", "García",
            "0980000000", "nuevo@correo.com", "1712345678"
        )

        fila = obtener_clientes()[0]

        assert fila[1] == "Ana María"
        assert fila[3] == "0980000000"
        assert fila[5] == "1712345678"

    def test_eliminar_borra(
        self, como_administrador
    ):
        id_cliente = insertar_cliente(
            "Ana", "García", None, None
        )

        assert eliminar_cliente(id_cliente) is True
        assert obtener_clientes() == []

    def test_no_se_puede_borrar_con_ventas(
        self, como_administrador, datos_base
    ):
        """
        Devuelve False, no lanza: la vista
        explica el motivo al usuario.
        """

        _, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente,
            id_auto,
            "2026-01-15",
            25000.0
        )

        assert eliminar_cliente(id_cliente) is False
        assert len(obtener_clientes()) == 1

    def test_contar_ventas_de_cliente(
        self, como_administrador, datos_base
    ):
        _, id_auto, id_cliente = datos_base

        registrar_venta(
            id_cliente, id_auto, "2026-01-15", 25000.0
        )
        registrar_venta(
            id_cliente, id_auto, "2026-01-16", 25000.0
        )

        assert contar_ventas_de_cliente(id_cliente) == 2


class TestPermisos:

    def test_vendedor_no_gestiona_clientes(
        self, como_vendedor
    ):
        from errores import PermisoDenegado

        with pytest.raises(PermisoDenegado):

            insertar_cliente("Ana", "García", None, None)

    def test_vendedor_si_puede_leer(
        self, como_vendedor, datos_base
    ):
        """
        Las lecturas no llevan decorador: los dos
        roles pueden consultar clientes. datos_base
        crea el cliente como administrador y
        despues se lee como vendedor.
        """

        assert len(obtener_clientes()) == 1

    def test_vendedor_no_puede_insertar(
        self, como_vendedor, datos_base
    ):
        from errores import PermisoDenegado

        with pytest.raises(PermisoDenegado):

            insertar_cliente("Otro", "Cliente", None, None)
