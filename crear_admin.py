# ==========================================
# CREAR EL PRIMER ADMINISTRADOR
# ==========================================
# Uso:
#
#     venv\Scripts\python.exe crear_admin.py
#
# Solo funciona si no hay ningún administrador
# activo. Para crear cuentas después, entrar al
# sistema como administrador y usar la sección
# Usuarios.
# ==========================================


import getpass
import sys

from database.usuarios import (
    crear_primer_usuario,
    contar_administradores_activos,
    hay_usuarios
)

from utils.validaciones import (
    es_nombre_usuario,
    es_nombre_persona,
    es_contrasena,
    contrasenas_coinciden,
    primer_error
)

from errores import ErrorSistema


def pedir(etiqueta, oculto=False):

    while True:

        if oculto:

            valor = getpass.getpass(etiqueta)

        else:

            valor = input(etiqueta)

        valor = valor.strip()

        if valor:
            return valor

        print("  El valor no puede estar vacío.")


def main():

    print("")
    print("  CREACIÓN DEL PRIMER ADMINISTRADOR")
    print("  " + "-" * 34)
    print("")

    try:

        if contar_administradores_activos() > 0:

            print(
                "  Ya existe un administrador activo.\n"
                "  Entra al sistema y usa la sección "
                "Usuarios."
            )

            return 1

        if hay_usuarios():

            print(
                "  Hay cuentas creadas, pero ninguna "
                "administrador activa.\n"
                "  Reactiva una desde la base de datos "
                "o revisa la tabla usuarios."
            )

            return 1

        print("  Nombre de usuario:")
        nombre_usuario = pedir("    > ")

        print("")
        print("  Nombre completo:")
        nombre_completo = pedir("    > ")

        print("")
        print("  Contraseña:")
        print(
            "  Mínimo 8 caracteres, con letras "
            "y números."
        )

        contrasena = pedir("    > ", oculto=True)

        repetir = pedir(
            "  Repite la contraseña: ",
            oculto=True
        )

        error = primer_error([
            es_nombre_usuario(nombre_usuario),
            es_nombre_persona(
                nombre_completo,
                "El nombre completo"
            ),
            es_contrasena(contrasena),
            contrasenas_coinciden(
                contrasena,
                repetir
            )
        ])

        if error:

            print("")
            print(f"  {error}")

            return 1

        id_usuario, motivo = crear_primer_usuario(
            nombre_usuario,
            nombre_completo,
            contrasena
        )

        if id_usuario is None:

            print(f"  {motivo}")

            return 1

    except ErrorSistema as error:

        print("")
        print(f"  {error.mensaje}")

        return 1

    except KeyboardInterrupt:

        print("")
        print("  Cancelado.")

        return 1

    print("")
    print(f"  Administrador '{nombre_usuario}' creado.")
    print("  Ya puedes iniciar sesión.")
    print("")

    return 0


sys.exit(main())
