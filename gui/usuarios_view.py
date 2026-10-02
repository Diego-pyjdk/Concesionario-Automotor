from database.usuarios import (
    obtener_usuarios,
    buscar_usuarios,
    eliminar_usuario as eliminar_usuario_db,
    reiniciar_bloqueo,
    minutos_restantes
)

import sesion as modulo_sesion

from utils.helpers import (
    crear_botones_accion
)

from gui.vista_listado import VistaListado

from gui.formularios.usuario_form import UsuarioForm


class UsuariosView(VistaListado):

    titulo = "Usuarios"

    columnas = [
        "ID",
        "Usuario",
        "Nombre completo",
        "Rol",
        "Estado",
        "Último acceso",
        "Acciones"
    ]

    columna_acciones = 6

    texto_nuevo = "+ Nuevo usuario"

    placeholder_busqueda = "Buscar por usuario, nombre o rol..."

    mensaje_vacio = "No hay usuarios"

    detalle_vacio = (
        "Crea el administrador inicial con "
        "crear_admin.py."
    )

    anchos_fijos = {5: 130}

    def cargar_datos(self):

        self.mostrar_de(obtener_usuarios)

    def pintar_fila(self, fila, usuario):

        (
            id_usuario,
            nombre_usuario,
            nombre_completo,
            rol,
            activo,
            ultimo_acceso,
            intentos_fallidos,
            bloqueado_hasta
        ) = usuario

        sesion = modulo_sesion.obtener_sesion()

        # Marca la cuenta con la que se inició
        # sesión para no confundirla.

        texto = nombre_usuario

        if id_usuario == sesion.id_usuario:

            texto = f"{nombre_usuario}  ●"

        self.marcar_columnas(
            fila,
            [
                id_usuario,
                texto,
                nombre_completo,
                self.texto_rol(rol),
                self.texto_estado(
                    activo,
                    intentos_fallidos,
                    bloqueado_hasta
                ),
                self.texto_fecha(ultimo_acceso)
            ],
            centrar={0, 5}
        )

        botones = crear_botones_accion(
            lambda _, f=fila: self.editar_usuario(f),
            lambda _, f=fila: self.eliminar_usuario(f)
        )

        self.poner_acciones(fila, botones)

    # =============================
    # FORMATO
    # =============================

    def texto_rol(self, rol):

        if rol == "administrador":
            return "Administrador"

        if rol == "vendedor":
            return "Vendedor"

        return rol

    def texto_fecha(self, valor):
        """
        '2026-09-30 16:14:14' no cabe en la
        columna y no aporta: día y hora sin
        segundos.
        """

        if valor is None:
            return "Nunca"

        try:
            return valor.strftime("%d/%m/%Y %H:%M")
        except AttributeError:
            return str(valor)

    def texto_estado(
        self,
        activo,
        intentos_fallidos,
        bloqueado_hasta
    ):
        """
        El bloqueo se ve en la columna Estado: si
        no, el administrador no entiende por qué
        alguien no entra.
        """

        if not activo:
            return "Inactivo"

        if bloqueado_hasta is not None:

            minutos = minutos_restantes(
                bloqueado_hasta
            )

            if minutos > 0:

                return f"Bloqueado ({minutos} min)"

        if intentos_fallidos:

            plural = (
                "intento"
                if intentos_fallidos == 1
                else "intentos"
            )

            return (
                f"Activo "
                f"({intentos_fallidos} {plural} fallidos)"
            )

        return "Activo"

    # =============================
    # ALTA
    # =============================

    def nuevo_registro(self):

        formulario = UsuarioForm(self)

        if formulario.exec():

            self.cargar_datos()

    # =============================
    # EDICIÓN
    # =============================

    def editar_usuario(self, fila):

        # Editar una cuenta bloqueada ofrece
        # primero desbloquearla: es lo que el
        # administrador quiere en ese momento.

        item_estado = self.tabla.item(fila, 4)

        if item_estado and "Bloqueado" in item_estado.text():

            if self.confirmar(
                "Cuenta bloqueada",
                "Esta cuenta está bloqueada por "
                "intentos fallidos.\n\n"
                "¿Desbloquearla ahora?"
            ):

                self.desbloquear(fila)

                return

        valores = self.leer_valores(fila, 6)

        if valores is None:

            return

        usuario = (
            int(valores[0]),
            valores[1].replace("  ●", ""),
            valores[2],
            valores[3],
            valores[4],
            valores[5]
        )

        formulario = UsuarioForm(self, usuario)

        if formulario.exec():

            self.cargar_datos()

    # =============================
    # DESBLOQUEO
    # =============================

    def desbloquear(self, fila):

        item = self.tabla.item(fila, 0)

        if not item:

            return

        id_usuario = int(item.text())

        self.proteger(reiniciar_bloqueo, id_usuario)

        self.mostrar_exito(
            f"La cuenta {id_usuario} quedó "
            "desbloqueada."
        )

        self.cargar_datos()

    # =============================
    # BORRADO
    # =============================

    def eliminar_usuario(self, fila):

        item = self.tabla.item(fila, 0)

        item_usuario = self.tabla.item(fila, 1)

        if not item or not item_usuario:

            return

        id_usuario = int(item.text())

        nombre = item_usuario.text().replace(
            "  ●", ""
        )

        if not self.confirmar_borrado(
            f"la cuenta '{nombre}'",
            "El historial de ventas no se borra."
        ):

            return

        resultado = self.proteger(
            eliminar_usuario_db,
            id_usuario
        )

        if resultado is None:

            return

        correcto, motivo = resultado

        if not correcto:

            self.mostrar_mensaje_error(motivo)

            return

        self.mostrar_exito(
            f"La cuenta '{nombre}' se eliminó "
            "correctamente."
        )

        self.cargar_datos()

    # =============================
    # BÚSQUEDA
    # =============================

    def buscar(self, texto):

        if not texto:

            self.cargar_datos()

            return

        self.mostrar_de(buscar_usuarios, texto)
