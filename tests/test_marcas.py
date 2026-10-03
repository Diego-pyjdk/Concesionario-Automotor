# ==========================================
# MARCAS
# ==========================================
# CRUD y la restricción de nombre único.
# ==========================================

import pytest

from database.marcas import (
    obtener_marcas,
    buscar_marcas,
    marca_existe,
    insertar_marca,
    actualizar_marca,
    eliminar_marca,
    contar_autos_por_marca
)

from database.autos import insertar_auto

from errores import ErrorBaseDatos


class TestLectura:

    def test_no_hay_marcas_en_una_limpia(
        self, como_administrador, limpiar_tablas
    ):
        assert obtener_marcas() == []

    def test_devuelve_id_y_nombre(
        self, como_administrador, limpiar_tablas
    ):
        id_marca = insertar_marca("Toyota")

        filas = obtener_marcas()

        assert len(filas) == 1
        assert filas[0][0] == id_marca
        assert filas[0][1] == "Toyota"

    def test_ordena_alfabetico(
        self, como_administrador, limpiar_tablas
    ):
        insertar_marca("Volkswagen")
        insertar_marca("Audi")
        insertar_marca("BMW")

        nombres = [f[1] for f in obtener_marcas()]

        assert nombres == ["Audi", "BMW", "Volkswagen"]

    def test_buscar_encuentra(
        self, como_administrador, limpiar_tablas
    ):
        insertar_marca("Mercedes-Benz")

        assert len(buscar_marcas("merc")) == 1

    def test_buscar_sin_resultados_devuelve_vacio(
        self, como_administrador, limpiar_tablas
    ):
        insertar_marca("Toyota")

        assert buscar_marcas("zzz") == []


class TestDuplicados:

    def test_marca_existe_detecta(
        self, como_administrador, limpiar_tablas
    ):
        insertar_marca("Toyota")

        assert marca_existe("Toyota") is True

    def test_marca_existe_ignora_mayusculas(
        self, como_administrador, limpiar_tablas
    ):
        insertar_marca("Toyota")

        # MySQL con utf8mb4_0900_ai_ci compara sin
        # distinguir mayusculas, asi que el UNIQUE
        # tambien las rechaza.

        assert marca_existe("TOYOTA") is True

    def test_marca_existe_excluye_la_propia(
        self, como_administrador, limpiar_tablas
    ):
        id_marca = insertar_marca("Toyota")

        # Editar sin cambiar el nombre no puede
        # detectar duplicado consigo misma.

        assert marca_existe("Toyota", id_marca) is False

    def test_el_uniche_bloquea_el_duplicado(
        self, como_administrador, limpiar_tablas
    ):
        insertar_marca("Toyota")

        # El formulario ya avisa antes de llegar
        # aqui, pero si dos ventanas se pisan a
        # la vez la base es la que frena.

        with pytest.raises(ErrorBaseDatos) as fallo:

            insertar_marca("Toyota")

        assert "Ya existe" in fallo.value.mensaje

    def test_no_deja_duplicados(
        self, como_administrador, limpiar_tablas
    ):
        insertar_marca("Toyota")

        with pytest.raises(ErrorBaseDatos):

            insertar_marca("Toyota")

        assert len(obtener_marcas()) == 1


class TestEscritura:

    def test_insertar_devuelve_el_id(
        self, como_administrador, limpiar_tablas
    ):
        assert isinstance(
            insertar_marca("Kia"), int
        )

    def test_actualizar_cambia_el_nombre(
        self, como_administrador, limpiar_tablas
    ):
        id_marca = insertar_marca("Chevrolet")

        actualizar_marca(id_marca, "Chevrolet Otro")

        assert obtener_marcas()[0][1] == "Chevrolet Otro"

    def test_renombrar_a_uno_que_existe_falla(
        self, como_administrador, limpiar_tablas
    ):
        insertar_marca("Toyota")
        id_kia = insertar_marca("Kia")

        with pytest.raises(ErrorBaseDatos):

            actualizar_marca(id_kia, "Toyota")

    def test_eliminar_borra(
        self, como_administrador, limpiar_tablas
    ):
        id_marca = insertar_marca("Nissan")

        assert eliminar_marca(id_marca) is True
        assert obtener_marcas() == []

    def test_no_se_puede_borrar_con_vehiculos(
        self, como_administrador, limpiar_tablas
    ):
        id_marca = insertar_marca("Ford")

        insertar_auto(
            id_marca, "Mustang", 2023, 40000.0, "Rojo", 1
        )

        # Devuelve False en vez de lanzar: la
        # clave foranea lo impide y la vista
        # explica el motivo.

        assert eliminar_marca(id_marca) is False
        assert len(obtener_marcas()) == 1

    def test_contar_autos_por_marca(
        self, como_administrador, limpiar_tablas
    ):
        id_marca = insertar_marca("Honda")

        insertar_auto(
            id_marca, "Civic", 2024, 30000.0, "Azul", 2
        )
        insertar_auto(
            id_marca, "Fit", 2022, 22000.0, "Rojo", 1
        )

        assert contar_autos_por_marca(id_marca) == 2


class TestAuditoria:

    def test_crear_deja_rastro(
        self, como_administrador, limpiar_tablas
    ):
        from database.auditoria import obtener_auditoria

        insertar_marca("Toyota")

        acciones = [a[3] for a in obtener_auditoria()]

        assert "CREAR" in acciones

    def test_el_rastro_guarda_el_usuario(
        self, como_administrador, limpiar_tablas
    ):
        """
        obtener_auditoria devuelve
        id, fecha_hora, usuario_nombre, accion,
        modulo, descripcion. Ojo con el orden: el
        usuario va en el indice 2, no en el 4.
        """

        from database.auditoria import obtener_auditoria

        insertar_marca("Toyota")

        registros = obtener_auditoria()

        assert registros
        assert registros[0][2] == "admin"
        assert registros[0][3] == "CREAR"
        assert registros[0][4] == "marcas"


class TestPermisos:

    def test_vendedor_no_gestiona_marcas(
        self, como_vendedor, limpiar_tablas
    ):
        from errores import PermisoDenegado

        with pytest.raises(PermisoDenegado):

            insertar_marca("Toyota")

    def test_el_intento_queda_registrado(
        self, como_administrador, limpiar_tablas
    ):
        """
        El vendedor intenta algo y se registra.
        """

        from database.usuarios import insertar_usuario
        from database.auditoria import obtener_auditoria
        from errores import PermisoDenegado

        import sesion as modulo_sesion

        # El vendedor no puede ni leer el rastro:
        # VER_AUDITORIA es solo del administrador.
        # Eso es lo correcto, asi que la lectura
        # se hace volviendo a admin despues.

        id_vendedor = insertar_usuario(
            "vendedor_test",
            "Vendedor de pruebas",
            "VendedorDePruebas2026",
            "vendedor",
            True
        )

        modulo_sesion.iniciar_sesion((
            id_vendedor, "vendedor_test",
            "Vendedor", "vendedor"
        ))

        with pytest.raises(PermisoDenegado):

            insertar_marca("Toyota")

        with pytest.raises(PermisoDenegado):

            obtener_auditoria()

        # Vuelve al administrador y comprueba
        # que el intento quedo escrito.

        modulo_sesion.iniciar_sesion((
            como_administrador, "admin",
            "Administrador", "administrador"
        ))

        registros = obtener_auditoria()

        negaciones = [
            r for r in registros
            if r[3] == "ACCESO_DENEGADO"
            and "insertar_marca" in (r[5] or "")
        ]

        assert negaciones
