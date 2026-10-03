# ==========================================
# USUARIOS Y CONTRASEÑAS
# ==========================================
# Lo que se protege aquí:
#   - la contraseña nunca se guarda en claro
#   - usuario inexistente y contraseña incorrecta
#     dan el mismo mensaje y tardan lo mismo
#   - bloqueo tras 5 intentos durante 15 minutos
#   - no se puede borrar ni degradar al último
#     administrador activo
# ==========================================


import pytest

import sesion as modulo_sesion

from database.usuarios import (
    autenticar,
    minutos_restantes,
    contar_administradores_activos,
    es_administrador,
    hay_usuarios,
    crear_primer_usuario,
    insertar_usuario,
    obtener_usuarios,
    actualizar_usuario,
    cambiar_contrasena,
    eliminar_usuario
)

from utils.seguridad import (
    hashear_contrasena,
    separar_hash,
    verificar_contrasena
)

from database.conexion import obtener_conexion


ADMIN = (
    "admin",
    "Administrador de pruebas",
    "Concesionario2026"
)


def hash_guardado_de(nombre_usuario):
    """
    Lee el hash directamente.

    obtener_usuarios() no lo expone a propósito:
    la lista no necesita verlo y así no viaja por
    la interfaz. Para comprobar el formato hay
    que leer la fila cruda.
    """

    conexion = obtener_conexion()

    cursor = conexion.cursor()

    cursor.execute(
        """
        SELECT password_hash
        FROM usuarios
        WHERE nombre_usuario = %s
        """,
        (nombre_usuario,)
    )

    fila = cursor.fetchone()

    cursor.close()
    conexion.close()

    return fila[0] if fila else None


class TestHash:

    def test_no_guarda_el_texto_plano(
        self, como_administrador
    ):
        """
        Se guarda sal_hex:hash_hex. El texto plano
        no se guarda, no se registra y no se
        recupera.
        """

        guardado = hash_guardado_de("admin")

        assert guardado
        assert "Concesionario2026" not in guardado

    def test_sal_y_hash_separados_por_dos_puntos(
        self, como_administrador
    ):
        guardado = hash_guardado_de("admin")

        partes = guardado.split(":")

        assert len(partes) == 2
        assert all(partes)

    def test_separar_hash_descompone(
        self, como_administrador
    ):
        sal, hash = hashear_contrasena("secreto")

        partes = separar_hash(f"{sal.hex()}:{hash.hex()}")

        assert partes == (sal, hash)

    def test_separar_hash_con_basura_no_revienta(
        self, como_administrador
    ):
        """
        Una fila con el formato viejo no puede
        tumbar el login.
        """

        assert separar_hash("basura") == (None, None)

    def test_la_misma_clave_da_distinta_sal(
        self, como_administrador
    ):
        """
        La sal es nueva en cada hash: dos usuarios
        con la misma contraseña no pueden
        reconocerse comparando el hash.
        """

        sal_uno, hash_uno = hashear_contrasena("igual")

        sal_otro, hash_otro = hashear_contrasena("igual")

        assert sal_uno != sal_otro
        assert hash_uno != hash_otro

    def test_verificar_acepta_la_correcta(
        self, como_administrador
    ):
        sal, hash = hashear_contrasena("secreto")

        assert verificar_contrasena(
            "secreto", f"{sal.hex()}:{hash.hex()}"
        ) is True

    def test_verificar_rechaza_otra(
        self, como_administrador
    ):
        sal, hash = hashear_contrasena("secreto")

        assert verificar_contrasena(
            "otro", f"{sal.hex()}:{hash.hex()}"
        ) is False

    def test_verificar_con_basura_no_revienta(
        self, como_administrador
    ):
        """
        Un hash corrupto en la base no puede
        tumbar el login.
        """

        assert verificar_contrasena(
            "secreto", "no-es-un-hash"
        ) is False

    def test_el_hash_de_la_base_verifica(
        self, como_administrador
    ):
        """
        Prueba de extremo a extremo: lo que hay
        escrito en la tabla sirve para
        autenticarse.
        """

        assert verificar_contrasena(
            "Concesionario2026", hash_guardado_de("admin")
        ) is True


class TestAutenticar:

    def test_credenciales_correctas(
        self, como_administrador
    ):
        ok, mensaje, datos = autenticar(
            "admin", "Concesionario2026"
        )

        assert ok is True
        assert mensaje == ""
        assert datos is not None
        assert datos[1] == "admin"

    def test_contrasena_incorrecta(
        self, como_administrador
    ):
        ok, mensaje, datos = autenticar(
            "admin", "equivocada"
        )

        assert ok is False
        assert datos is None
        assert mensaje

    def test_el_mensaje_es_identico(
        self, como_administrador
    ):
        """
        Usuario inexistente y contraseña incorrecta
        dan EXACTAMENTE el mismo mensaje.

        Antes se le añadía "Te quedan N intento(s)"
        cuando la cuenta existía, y ese añadido
        bastaba para averiguar qué cuentas hay con
        un solo intento fallido. Ahora el contador
        no aparece nunca: quien se equivoca cinco
        veces ya recibe el aviso de cuenta
        bloqueada, que es el que de verdad importa.
        """

        base = "Usuario o contraseña incorrectos."

        _, inexistente, _ = autenticar(
            "no_existe", "lo_que_sea"
        )

        assert inexistente == base

        # Se repite el fallo contra la misma cuenta:
        # el mensaje no debe cambiar ni al
        # acumular intentos.

        for _ in range(3):

            _, incorrecta, _ = autenticar(
                "admin", "lo_que_sea"
            )

            assert incorrecta == base

    def test_el_bloqueo_si_avisa(
        self, como_administrador
    ):
        """
        El aviso de cuenta bloqueada sí menciona la
        cuenta: para entonces ya se han gastado
        cinco intentos y no se averigua nada nuevo.
        """

        for _ in range(5):

            autenticar("admin", "equivocada")

        ok, mensaje, _ = autenticar(
            "admin", "Concesionario2026"
        )

        assert ok is False
        assert "bloqueada" in mensaje.lower()

    def test_verifica_un_hash_senuelo(
        self, como_administrador
    ):
        """
        El caso inexistente verifica un hash
        señuelo para que el tiempo de respuesta no
        revele qué cuentas existen: si el usuario
        no está, se responde igual de rápido que
        si está con la contraseña mal.
        """

        import time

        import database.usuarios as usuarios
        import utils.seguridad as seguridad

        llamadas = []

        usuarios_original = usuarios.verificar_contrasena

        def contando(contrasena, hash_guardado):
            llamadas.append(hash_guardado)
            return usuarios_original(contrasena, hash_guardado)

        # Se sustituye en database.usuarios, no en
        # utils.seguridad: usuarios hizo "from
        # utils.seguridad import verificar_contrasena"
        # al importar, así que tiene su propio
        # nombre en su espacio. Parchear el módulo
        # de origen no cambiaría nada aquí.

        usuarios.verificar_contrasena = contando

        try:

            inicio = time.perf_counter()

            autenticar("no_existe", "lo_que_sea")

            transcurrido = (
                time.perf_counter() - inicio
            )

        finally:

            usuarios.verificar_contrasena = (
                usuarios_original
            )

        # Verificó algo aunque el usuario no exista:
        # si no verificara nada, sería más rápido
        # y el tiempo lo delataría.

        assert llamadas

        # Y el coste es el de una verificación real.

        assert transcurrido > 0.05

    def test_registra_el_acceso(
        self, como_administrador
    ):
        from database.auditoria import obtener_auditoria

        autenticar("admin", "Concesionario2026")

        acciones = [r[3] for r in obtener_auditoria()]

        assert "LOGIN" in acciones

    def test_registra_el_fallo_con_el_nombre_introducido(
        self, como_administrador
    ):
        """
        Un login fallido se guarda con usuario_id
        NULL y con el nombre que se escribió. No
        con el id de quien está sentado delante: si
        no, el rastro atribuiría el intento a un
        usuario que no lo hizo.
        """

        from database.auditoria import obtener_auditoria

        autenticar("no_existe", "lo_que_sea")

        fallidos = [
            r for r in obtener_auditoria()
            if r[3] == "LOGIN_FALLIDO"
        ]

        assert fallidos
        assert fallidos[0][2] == "no_existe"


class TestBloqueo:

    def test_bloquea_despues_de_cinco_intentos(
        self, como_administrador
    ):
        for _ in range(5):

            ok, _, _ = autenticar(
                "admin", "equivocada"
            )

            assert ok is False

        ok, mensaje, _ = autenticar(
            "admin", "Concesionario2026"
        )

        assert ok is False
        assert "bloque" in mensaje.lower()

    def test_la_contrasena_correcta_no_salta_el_bloqueo(
        self, como_administrador
    ):
        """
        Aunque la contraseña sea correcta, la
        cuenta bloqueada no entra. Si se saltara,
        el bloqueo no serviría para nada.
        """

        for _ in range(5):

            autenticar("admin", "equivocada")

        ok, _, _ = autenticar(
            "admin", "Concesionario2026"
        )

        assert ok is False

    def test_minutos_restantes_calcula(
        self, como_administrador
    ):
        import datetime

        from datetime import timedelta

        futuro = datetime.datetime.now() + timedelta(
            minutes=10
        )

        assert 9 <= minutos_restantes(futuro) <= 10

    def test_minutos_restantes_de_pasado(
        self, como_administrador
    ):
        import datetime

        from datetime import timedelta

        pasado = datetime.datetime.now() - timedelta(
            minutes=1
        )

        assert minutos_restantes(pasado) == 0


class TestAlta:

    def test_crear_primer_usuario_devuelve_id_y_mensaje(
        self, limpiar_tablas
    ):
        """
        Camino feliz: sin ningún administrador
        activo se puede crear el primero.

        Devuelve (id_usuario, ""), no el id suelto:
        si se pasa la tupla entera como id_usuario,
        la sesión apuntaría a una tupla y la clave
        foránea de auditoría fallaría al escribir.
        """

        nuevo, motivo = crear_primer_usuario(
            "primer_admin",
            "Primer Administrador",
            "ClavePrimerAdmin2026"
        )

        assert isinstance(nuevo, int)
        assert motivo == ""

        ok, _, _ = autenticar(
            "primer_admin", "ClavePrimerAdmin2026"
        )

        assert ok is True

    def test_no_hay_un_segundo_administrador_inicial(
        self, como_administrador
    ):
        nuevo, motivo = crear_primer_usuario(
            "otro_admin",
            "Otro Administrador",
            "OtraClave2026"
        )

        assert nuevo is None
        assert "administrador" in motivo.lower()

    def test_el_rol_se_guarda(
        self, como_administrador
    ):
        """
        El rol es obligatorio en la capa de datos.
        Que las cuentas nuevas sean de vendedor es
        cosa del formulario (UsuarioForm), no de
        aquí: si el rol no viene, es un fallo de
        quien llama, no algo que se deba adivinar.
        """

        id_nuevo = insertar_usuario(
            "nuevo", "Nuevo Vendedor",
            "ClaveNuevo2026", "vendedor"
        )

        filas = obtener_usuarios()

        fila = next(
            f for f in filas if f[0] == id_nuevo
        )

        assert fila[3] == "vendedor"

    def test_no_deja_duplicar_nombre_usuario(
        self, como_administrador
    ):
        from errores import ErrorBaseDatos

        insertar_usuario(
            "nuevo", "Nuevo Vendedor",
            "ClaveNuevo2026", "vendedor"
        )

        with pytest.raises(ErrorBaseDatos):

            insertar_usuario(
                "nuevo", "Otro",
                "ClaveNuevo2026", "vendedor"
            )


class TestProteccionDelUltimoAdmin:

    def test_no_se_borra_uno_mismo(
        self, como_administrador
    ):
        ok, motivo = eliminar_usuario(
            como_administrador
        )

        assert ok is False
        assert motivo

    def test_no_se_borra_el_ultimo_admin(
        self, como_administrador
    ):
        """
        Hay dos defensas y la que se puede
        comprobar desde aquí es la de no borrar la
        propia cuenta.

        La otra ("no dejar el sistema sin
        administradores activos") no se puede
        provocar por esta vía: para que saltara
        habría que intentar borrar al único
        administrador vivo, y ese siempre es el
        que está sentado delante, que cae antes en
        la primera defensa. Queda como red de
        seguridad para llamadas internas, y se
        comprueba con contar_administradores_activos.
        """

        ok, motivo = eliminar_usuario(
            como_administrador
        )

        assert ok is False
        assert "tu propia" in motivo.lower()

        # Y la cuenta sigue ahí.

        assert contar_administradores_activos() == 1

        assert es_administrador(
            como_administrador
        ) is True

    def test_se_puede_borrar_otro_admin(
        self, como_administrador
    ):
        """
        Con dos administradores, uno sí se puede
        quitar: si no, no habría forma de
        deshacerse de una cuenta.
        """

        otro = insertar_usuario(
            "otro_admin", "Otro Administrador",
            "ClaveOtroAdmin2026", "administrador"
        )

        ok, motivo = eliminar_usuario(otro)

        assert ok is True, motivo

    def test_no_se_degrada_al_ultimo_admin(
        self, como_administrador
    ):
        # Devuelve un booleano pelado, no una
        # tupla con el motivo.

        ok = actualizar_usuario(
            como_administrador,
            "admin",
            "Administrador de pruebas",
            "vendedor",
            True
        )

        assert ok is False

        # Y el rol sigue siendo el de antes.

        filas = obtener_usuarios()

        fila = next(
            f for f in filas
            if f[0] == como_administrador
        )

        assert fila[3] == "administrador"

    def test_no_se_desactiva_al_ultimo_admin(
        self, como_administrador
    ):
        ok = actualizar_usuario(
            como_administrador,
            "admin",
            "Administrador de pruebas",
            "administrador",
            False
        )

        assert ok is False

    def test_contar_administradores_activos(
        self, como_administrador
    ):
        assert contar_administradores_activos() == 1

    def test_es_administrador(
        self, como_administrador
    ):
        assert es_administrador(
            como_administrador
        ) is True


class TestCambiarContrasena:

    def test_cambia_y_sirve_la_nueva(
        self, como_administrador
    ):
        nuevo = insertar_usuario(
            "temporal", "Temporal",
            "ClaveTemporal2026", "vendedor"
        )

        cambiar_contrasena(nuevo, "ClaveNueva2026")

        ok, _, _ = autenticar(
            "temporal", "ClaveNueva2026"
        )

        assert ok is True

        ok, _, _ = autenticar(
            "temporal", "ClaveTemporal2026"
        )

        assert ok is False

    def test_cambiar_resetea_el_bloqueo(
        self, como_administrador
    ):
        """
        Si una cuenta quedó bloqueada y se le
        cambia la contraseña, entra: el bloqueo
        era por intentos fallidos, no una condena.
        """

        nuevo = insertar_usuario(
            "temporal", "Temporal",
            "ClaveTemporal2026", "vendedor"
        )

        for _ in range(5):

            autenticar("temporal", "equivocada")

        ok, mensaje, _ = autenticar(
            "temporal", "ClaveTemporal2026"
        )

        assert ok is False

        cambiar_contrasena(nuevo, "ClaveNueva2026")

        ok, _, _ = autenticar(
            "temporal", "ClaveNueva2026"
        )

        assert ok is True

    def test_vendedor_no_cambia_contrasenas(
        self, como_vendedor
    ):
        from errores import PermisoDenegado

        with pytest.raises(PermisoDenegado):

            cambiar_contrasena(
                como_vendedor, "Otra2026"
            )


class TestSesion:

    def test_cerrar_deja_sin_permisos(
        self, como_administrador
    ):
        """
        Sin sesión, ningún permiso vale: la interfaz
        puede seguir visible, pero la capa de datos
        no cede nada.
        """

        modulo_sesion.cerrar_sesion()

        from database.marcas import insertar_marca
        from errores import PermisoDenegado

        with pytest.raises(PermisoDenegado):

            insertar_marca("Toyota")

    def test_hay_usuarios(
        self, como_administrador
    ):
        assert hay_usuarios() is True
