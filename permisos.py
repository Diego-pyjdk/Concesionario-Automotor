# ==========================================
# PERMISOS POR ROL
# ==========================================
# Fuente única de verdad sobre qué puede hacer
# cada rol.
#
# Se aplica en dos capas:
#
#   1. Interfaz: la ventana principal solo crea
#      las secciones permitidas y las vistas
#      ocultan los botones de escritura.
#
#   2. Datos: @requiere_permiso sobre las
#      funciones de database/*.py.
#
# Ocultar un botón NO es la protección: la
# capa de datos vuelve a comprobarlo.
# ==========================================


import functools

import sesion as modulo_sesion

from errores import PermisoDenegado


# ==========================================
# ROLES
# ==========================================

ROL_ADMINISTRADOR = "administrador"

ROL_VENDEDOR = "vendedor"

ROLES = [
    ROL_ADMINISTRADOR,
    ROL_VENDEDOR
]


# ==========================================
# PERMISOS
# ==========================================

VER_TABLERO = "ver_tablero"

VER_VEHICULOS = "ver_vehiculos"
GESTIONAR_VEHICULOS = "gestionar_vehiculos"

VER_MARCAS = "ver_marcas"
GESTIONAR_MARCAS = "gestionar_marcas"

VER_CLIENTES = "ver_clientes"
GESTIONAR_CLIENTES = "gestionar_clientes"

VER_VENTAS = "ver_ventas"
REGISTRAR_VENTAS = "registrar_ventas"
GESTIONAR_VENTAS = "gestionar_ventas"

VER_REPORTES = "ver_reportes"

GESTIONAR_USUARIOS = "gestionar_usuarios"

VER_CONFIGURACION = "ver_configuracion"
GESTIONAR_CONFIGURACION = "gestionar_configuracion"


# ==========================================
# MATRIZ DE PERMISOS
# ==========================================

PERMISOS_POR_ROL = {

    ROL_ADMINISTRADOR: {
        VER_TABLERO,
        VER_VEHICULOS,
        GESTIONAR_VEHICULOS,
        VER_MARCAS,
        GESTIONAR_MARCAS,
        VER_CLIENTES,
        GESTIONAR_CLIENTES,
        VER_VENTAS,
        REGISTRAR_VENTAS,
        GESTIONAR_VENTAS,
        VER_REPORTES,
        GESTIONAR_USUARIOS,
        VER_CONFIGURACION,
        GESTIONAR_CONFIGURACION
    },

    # El vendedor consulta el inventario y los
    # clientes, y registra ventas. No borra nada,
    # no administra usuarios y no entra a
    # configuración ni reportes.
    ROL_VENDEDOR: {
        VER_TABLERO,
        VER_VEHICULOS,
        VER_MARCAS,
        VER_CLIENTES,
        VER_VENTAS,
        REGISTRAR_VENTAS
    }
}


# ==========================================
# CONSULTAS
# ==========================================

def es_administrador():
    return modulo_sesion.obtener_sesion().es_administrador


def rol_actual():
    return modulo_sesion.rol_actual()


def permisos_actuales():
    """
    Permisos del usuario en sesión.

    Sin sesión activa no hay permisos.
    """

    sesion = modulo_sesion.obtener_sesion()

    if not sesion.activa:
        return set()

    return PERMISOS_POR_ROL.get(sesion.rol, set())


def tiene_permiso(permiso):
    return permiso in permisos_actuales()


def puede_ver(permiso):
    return tiene_permiso(permiso)


def puede_gestionar(permiso):
    return tiene_permiso(permiso)


def exigir(permiso):
    """
    Comprueba un permiso sin lanzar excepción.
    Pensado para la interfaz.
    """

    return tiene_permiso(permiso)


# ==========================================
# DECORADOR
# ==========================================

def requiere_permiso(permiso):
    """
    Protege una función de database/*.py.

    Sin sesión activa o sin el permiso, lanza
    PermisoDenegado antes de tocar la base de
    datos.
    """

    def envoltorio(funcion):

        @functools.wraps(funcion)
        def protegida(*args, **kwargs):

            if not tiene_permiso(permiso):

                raise PermisoDenegado(permiso)

            return funcion(*args, **kwargs)

        return protegida

    return envoltorio
