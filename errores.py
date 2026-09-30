# ==========================================
# ERRORES DEL SISTEMA
# ==========================================
# Los módulos de datos lanzan excepciones de
# este archivo en lugar de dejar escapar las de
# mysql.connector.
#
# Regla de la casa:
#   - lo que ve el usuario va en .mensaje
#   - lo que ve el técnico va en .tecnico
#
# La interfaz solo muestra .mensaje. La traza
# completa se guarda en registro_errores.log.
# ==========================================


# ==========================================
# EXCEPCIONES
# ==========================================

class ErrorSistema(Exception):
    """
    Base de todos los errores controlados.
    """

    def __init__(self, mensaje, tecnico=None):
        super().__init__(mensaje)

        self.mensaje = mensaje
        self.tecnico = tecnico


class ErrorBaseDatos(ErrorSistema):
    """
    Fallo de MySQL: conexión perdida, error de
    sintaxis, violación de clave foránea, etc.
    """


class ErrorValidacion(ErrorSistema):
    """
    Dato incorrecto introducido por el usuario.
    """


class PermisoDenegado(ErrorSistema):
    """
    El rol en sesión no puede ejecutar la
    operación solicitada.
    """

    def __init__(self, permiso):
        super().__init__(
            "No tienes permisos para realizar "
            "esta acción.",
            f"Permiso requerido: {permiso}"
        )

        self.permiso = permiso


# ==========================================
# TRADUCCIÓN DE ERRORES DE MYSQL
# ==========================================
# errno -> mensaje apto para el usuario final.
# Se evita exponer nombres de tablas ni
# sintaxis SQL.
# ==========================================

MENSAJES_MYSQL = {

    # Acceso
    1045: "No se pudo conectar con MySQL. "
          "Revisa el usuario y la contraseña "
          "en el archivo .env.",

    1044: "La base de datos configurada no "
          "existe.",

    1049: "No se encontró la base de datos. "
          "Ejecuta database/esquema.sql para "
          "crearla.",

    2002: "No se puede conectar con el servidor "
          "MySQL. Comprueba que esté encendido.",

    2003: "No se puede conectar con el servidor "
          "MySQL. Comprueba que esté encendido.",

    # Sesión perdida
    2006: "El servidor MySQL cerró la conexión. "
          "Intenta de nuevo.",

    2013: "Se perdió la conexión con MySQL "
          "durante la operación.",

    # Integridad
    1062: "Ya existe un registro con esos datos.",

    1451: "No se puede eliminar: hay registros "
          "que dependen de este.",

    1452: "No se puede guardar: el registro "
          "relacionado no existe.",

    # Otros
    1054: "La base de datos no tiene la "
          "estructura esperada. Ejecuta "
          "database/esquema.sql.",

    1146: "No se encontró la tabla esperada. "
          "Ejecuta database/esquema.sql.",

    1140: "No se pudo leer el registro.",

    1213: "Dos operaciones chocaron a la vez. "
          "Intenta de nuevo.",

    1205: "La operación tardó demasiado y se "
          "canceló. Intenta de nuevo."
}


# ==========================================
# CONVERSIÓN
# ==========================================

def traducir_error(error):
    """
    Convierte una excepción de mysql.connector en
    ErrorBaseDatos con un mensaje legible.
    """

    codigo = getattr(error, "errno", None)

    mensaje = MENSAJES_MYSQL.get(codigo)

    if not mensaje:
        mensaje = (
            "Ocurrió un problema al acceder a la "
            "base de datos."
        )

    return ErrorBaseDatos(
        mensaje,
        tecnico=str(error)
    )
