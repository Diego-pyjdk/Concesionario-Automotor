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

VER_CONTRATOS = "ver_contratos"
CREAR_CONTRATOS = "crear_contratos"
GESTIONAR_CONTRATOS = "gestionar_contratos"

GESTIONAR_USUARIOS = "gestionar_usuarios"

VER_AUDITORIA = "ver_auditoria"

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
        VER_CONTRATOS,
        CREAR_CONTRATOS,
        GESTIONAR_CONTRATOS,
        GESTIONAR_USUARIOS,
        VER_AUDITORIA,
        VER_CONFIGURACION,
        GESTIONAR_CONFIGURACION
    },

    # El vendedor consulta el inventario y los
    # clientes, registra ventas y crea contratos.
    # No borra nada, no administra usuarios y no
    # entra a configuración ni reportes.
    #
    # Los contratos los crea porque son parte de
    # la venta, pero no los cancela ni los borra:
    # eso es de la administración.
    ROL_VENDEDOR: {
        VER_TABLERO,
        VER_VEHICULOS,
        VER_MARCAS,
        VER_CLIENTES,
        VER_VENTAS,
        REGISTRAR_VENTAS,
        VER_CONTRATOS,
        CREAR_CONTRATOS
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


# Antes había aquí tres alias de tiene_permiso()
# (puede_ver, puede_gestionar y exigir) que no
# usaba nadie y solo ocultaban que la
# comprobación es una sola. El atributo
# self.puede_gestionar de las vistas no tiene
# nada que ver con ellos: es un parámetro.
#
# A partir de aquí se escribe tiene_permiso()
# siempre.


# ==========================================
# DECORADOR
# ==========================================

def requiere_permiso(permiso):
    """
    Protege una función de database/*.py.

    Sin sesión activa o sin el permiso, deja una
    entrada ACCESO_DENEGADO en la auditoría y
    lanza PermisoDenegado antes de tocar la base
    de datos.
    """

    def envoltorio(funcion):

        @functools.wraps(funcion)
        def protegida(*args, **kwargs):

            if not tiene_permiso(permiso):

                registrar_intento(
                    permiso,
                    funcion.__name__
                )

                raise PermisoDenegado(permiso)

            return funcion(*args, **kwargs)

        return protegida

    return envoltorio


def registrar_intento(permiso, operacion):
    """
    Deja constancia de un intento no autorizado.

    El import es diferido a propósito: el módulo
    de auditoría usa la sesión, y cargarlo en
    el encabezado cerraría un círculo.
    """

    from database.auditoria import registrar_accion

    sesion = modulo_sesion.obtener_sesion()

    rol = sesion.rol or "sin sesión"

    registrar_accion(
        "acceso",
        "ACCESO_DENEGADO",
        f"{rol} intentó {operacion} "
        f"(requiere {permiso})"
    )
