from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QMessageBox
)

from database.usuarios import (
    obtener_usuarios,
    buscar_usuarios,
    eliminar_usuario as eliminar_usuario_db,
    reiniciar_bloqueo,
    minutos_restantes
)

import sesion as modulo_sesion

from utils.helpers import (
    crear_tabla,
    celda,
    crear_botones_accion,
    crear_boton_principal,
    crear_titulo
)

from gui.vista_base import VistaBase

from gui.formularios.usuario_form import UsuarioForm


class UsuariosView(VistaBase):

    def __init__(self):
        super().__init__()

        self.crear_interfaz()

    def crear_interfaz(self):

        layout_principal = QVBoxLayout()

        layout_principal.setContentsMargins(
            30, 25, 30, 25
        )

        layout_principal.setSpacing(20)

        self.setLayout(layout_principal)

        # ------------------------------
        # ENCABEZADO
        # ------------------------------

        encabezado = QHBoxLayout()

        encabezado.addWidget(
            crear_titulo("Usuarios")
        )

        encabezado.addStretch()

        encabezado.addWidget(
            crear_boton_principal(
                "+ Nuevo usuario",
                self.nuevo_usuario
            )
        )

        layout_principal.addLayout(encabezado)

        # ------------------------------
        # AVISO DE CONTRASEÑAS
        # ------------------------------

        aviso = QLabel(
            "Las contraseñas se guardan cifradas "
            "con PBKDF2 y no se pueden recuperar: "
            "solo se pueden restablecer."
        )

        aviso.setObjectName(
            "aviso"
        )

        aviso.setWordWrap(True)

        layout_principal.addWidget(aviso)

        # ------------------------------
        # BÚSQUEDA
        # ------------------------------

        busqueda_layout = QHBoxLayout()

        self.campo_busqueda = QLineEdit()

        self.campo_busqueda.setPlaceholderText(
            "Buscar por usuario, nombre o rol..."
        )

        self.campo_busqueda.setFixedHeight(40)

        self.campo_busqueda.returnPressed.connect(
            self.buscar
        )

        boton_buscar = QPushButton("🔍 Buscar")

        boton_buscar.setObjectName(
            "boton_filtro"
        )

        boton_buscar.setFixedHeight(40)

        boton_buscar.clicked.connect(
            self.buscar
        )

        busqueda_layout.addWidget(
            self.campo_busqueda
        )

        busqueda_layout.addWidget(
            boton_buscar
        )

        layout_principal.addLayout(busqueda_layout)

        # ------------------------------
        # TABLA
        # ------------------------------
        # Contrato con obtener_usuarios():
        # id, nombre_usuario, nombre_completo,
        # rol, activo, ultimo_acceso.
        # ------------------------------

        self.tabla = crear_tabla(
            [
                "ID",
                "Usuario",
                "Nombre completo",
                "Rol",
                "Estado",
                "Último acceso",
                "Acciones"
            ],
            columna_acciones=6,
            ancho_acciones=148
        )

        layout_principal.addWidget(self.tabla)

        # ------------------------------
        # CARGAR
        # ------------------------------

        self.cargar_datos()

    # =============================
    # NUEVO USUARIO
    # =============================

    def nuevo_usuario(self):

        formulario = UsuarioForm(self)

        if formulario.exec():

            self.cargar_datos()

    # =============================
    # CARGAR
    # =============================

    def cargar_datos(self):

        usuarios = self.proteger(
            obtener_usuarios
        )

        if usuarios is None:

            return

        self.mostrar_usuarios(usuarios)

    # =============================
    # MOSTRAR
    # =============================

    def mostrar_usuarios(self, usuarios):

        self.tabla.setRowCount(len(usuarios))

        sesion = modulo_sesion.obtener_sesion()

        for fila, usuario in enumerate(usuarios):

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

            self.tabla.setItem(
                fila,
                0,
                celda(id_usuario, centrar=True)
            )

            texto_usuario = nombre_usuario

            # Marca la cuenta con la que se
            # inició sesión para no confundirla
            # con las demás.

            if id_usuario == sesion.id_usuario:

                texto_usuario = f"{nombre_usuario}  ●"

            self.tabla.setItem(
                fila,
                1,
                celda(texto_usuario)
            )

            self.tabla.setItem(
                fila,
                2,
                celda(nombre_completo)
            )

            self.tabla.setItem(
                fila,
                3,
                celda(self.texto_rol(rol))
            )

            self.tabla.setItem(
                fila,
                4,
                celda(
                    self.texto_estado(
                        activo,
                        intentos_fallidos,
                        bloqueado_hasta
                    )
                )
            )

            self.tabla.setItem(
                fila,
                5,
                celda(
                    "Nunca"
                    if ultimo_acceso is None
                    else str(ultimo_acceso),
                    centrar=True
                )
            )

            botones = crear_botones_accion(
                lambda _, f=fila: self.editar_usuario(f),
                lambda _, f=fila: self.eliminar_usuario(f)
            )

            self.tabla.setCellWidget(
                fila,
                6,
                botones
            )

    def texto_rol(self, rol):

        if rol == "administrador":
            return "Administrador"

        if rol == "vendedor":
            return "Vendedor"

        return rol

    def texto_estado(
        self,
        activo,
        intentos_fallidos,
        bloqueado_hasta
    ):
        """
        El bloqueo aparece en la columna Estado
        para que el administrador entienda por qué
        alguien no puede entrar.
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
    # EDITAR
    # =============================

    def editar_usuario(self, fila):

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

        valores = []

        for columna in range(6):

            item = self.tabla.item(fila, columna)

            if item is None:

                return

            valores.append(item.text())

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
    # DESBLOQUEAR
    # =============================

    def desbloquear(self, fila):

        item = self.tabla.item(fila, 0)

        if not item:
            return

        id_usuario = int(item.text())

        self.proteger(
            reiniciar_bloqueo,
            id_usuario
        )

        self.cargar_datos()

    # =============================
    # ELIMINAR
    # =============================

    def eliminar_usuario(self, fila):

        item = self.tabla.item(fila, 0)

        item_usuario = self.tabla.item(fila, 1)

        if not item or not item_usuario:

            return

        id_usuario = int(item.text())

        nombre = item_usuario.text().replace(
            "  ●",
            ""
        )

        if not self.confirmar(
            "Eliminar usuario",
            f"¿Eliminar la cuenta '{nombre}'?\n\n"
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

            QMessageBox.warning(
                self,
                "No se puede eliminar",
                motivo
            )

            return

        self.cargar_datos()

    # =============================
    # BUSCAR
    # =============================

    def buscar(self):

        texto = self.campo_busqueda.text().strip()

        if not texto:

            self.cargar_datos()

            return

        usuarios = self.proteger(
            buscar_usuarios,
            texto
        )

        if usuarios is None:

            return

        self.mostrar_usuarios(usuarios)
