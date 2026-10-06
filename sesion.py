from contextvars import ContextVar

contexto_trabajo = ContextVar("sesion_trabajo", default=None)
generacion = 0

# ==========================================
# CONTEXTO DE SESIÓN
# ==========================================
# Guarda quién está usando el sistema.
#
# Es un singleton a propósito: el login, la
# ventana principal y la capa de datos
# necesitan ver la misma sesión.
#
# La capa de datos consulta la sesión para
# decidir si una operación está permitida, así
# que un permiso nunca depende solo de que el
# botón esté oculto.
# ==========================================


class Sesion:
    """
    Estado del usuario conectado.
    """

    def __init__(self):

        self.id_usuario = None

        self.nombre_usuario = None

        self.nombre_completo = None

        self.rol = None

        self.nombre = None

    # ------------------------------
    # CICLO DE VIDA
    # ------------------------------

    def iniciar(self, datos):
        """
        Abre sesión con la fila de usuarios.

        datos: (id, nombre_usuario, nombre_completo, rol)
        """

        (
            self.id_usuario,
            self.nombre_usuario,
            self.nombre_completo,
            self.rol
        ) = datos

        self.nombre = self.nombre_completo

    def cerrar(self):
        """
        Destruye la sesión. Tras esto ninguna
        operación protegida puede ejecutarse,
        aunque la interfaz siga visible.
        """

        self.id_usuario = None

        self.nombre_usuario = None

        self.nombre_completo = None

        self.rol = None

        self.nombre = None

    # ------------------------------
    # CONSULTAS
    # ------------------------------

    @property
    def activa(self):
        return self.id_usuario is not None

    @property
    def es_administrador(self):
        return self.rol == "administrador"

    def __repr__(self):

        if not self.activa:
            return "<Sesion sin usuario>"

        return (
            f"<Sesion {self.nombre_usuario} "
            f"({self.rol})>"
        )


# ==========================================
# INSTANCIA ÚNICA
# ==========================================

_sesion = Sesion()


def iniciar_sesion(datos):
    global generacion
    generacion += 1
    _sesion.iniciar(datos)


def cerrar_sesion():
    global generacion
    generacion += 1
    _sesion.cerrar()


def obtener_sesion():
    return contexto_trabajo.get() or _sesion


def hay_sesion():
    return obtener_sesion().activa


def usuario_actual():
    return obtener_sesion().nombre_usuario


def rol_actual():
    return obtener_sesion().rol
