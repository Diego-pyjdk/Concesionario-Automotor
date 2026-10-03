# ==========================================
# INSTALACIÓN DESDE CERO
# ==========================================
# La base contra la que corren estas pruebas la
# levanta tests/conftest.py a partir de
# database/esquema.sql y nada más. Es decir: cada
# vez que se ejecuta la batería se rehace una
# instalación completa y limpia. Si el esquema
# tuviera un error de sintaxis, una tabla que no
# cuadra o una dependencia mal declarada, aquí se
# vería.
#
# Lo que se comprueba:
#
#   - las nueve tablas existen
#   - ventas.usuario_id tiene su clave foránea
#     declarada EN LÍNEA, con ON DELETE SET NULL
#   - el esquema NO usa ALTER TABLE: el orden de
#     las tablas es el de dependencias
#   - la moneda viene sembrada con los valores de
#     siempre
#   - la aplicación opera contra esa base recién
#     creada: administrador, venta con vendedor,
#     contrato, pago, saldo y PDF
# ==========================================


import pathlib
import re

from database.conexion import obtener_conexion

RAIZ = pathlib.Path(
    "C:/Users/Tucan-Programmer/Desktop/concesionario"
)

ESQUEMA = RAIZ / "database" / "esquema.sql"

TABLAS = [
    "marcas", "autos", "clientes", "usuarios",
    "ventas", "configuracion", "auditoria",
    "contratos", "pagos"
]

# De quién depende cada tabla.

DEPENDENCIAS = {
    "autos": {"marcas"},
    "ventas": {"clientes", "autos", "usuarios"},
    "auditoria": {"usuarios"},
    "contratos": {"ventas", "clientes", "autos",
                  "usuarios"},
    "pagos": {"ventas", "contratos", "usuarios"}
}


def texto_del_esquema():
    return ESQUEMA.read_text(encoding="utf-8")


def orden_del_esquema():
    contenido = texto_del_esquema()

    return [
        m.group(1)
        for m in re.finditer(
            r"CREATE TABLE (\w+)", contenido
        )
        if m.group(1) != "IF"
    ]


class TestEstructura:

    def test_las_nueve_tablas_existen(self):
        """
        Esta base la construyó conftest.py
        ejecutando esquema.sql entero, así que si
        falta una tabla es que el esquema no la
        crea.
        """

        conexion = obtener_conexion()

        cursor = conexion.cursor()

        cursor.execute("SHOW TABLES")

        existentes = {
            fila[0] for fila in cursor.fetchall()
        }

        cursor.close()
        conexion.close()

        faltan = [
            t for t in TABLAS if t not in existentes
        ]

        assert not faltan, f"faltan {faltan}"

    def test_el_esquema_declara_las_nueve(
        self
    ):
        orden = orden_del_esquema()

        assert len(orden) == len(TABLAS), orden

        for tabla in TABLAS:

            assert tabla in orden, tabla

    def test_no_usa_alter_table(self):
        """
        Si el esquema usara ALTER TABLE, la
        instalación dependería del orden en que se
        ejecutan las sentencias. Sin él, el archivo
        se lee en orden de dependencias y basta con
        ejecutarlo entero.
        """

        contenido = texto_del_esquema()

        sin_comentarios = "\n".join(
            linea for linea in contenido.splitlines()
            if not linea.strip().startswith("--")
        )

        assert "ALTER TABLE" not in sin_comentarios.upper()

    def test_el_orden_respeta_las_dependencias(
        self
    ):
        """
        Cada tabla tiene que ir después de las que
        referencia. Con la clave foránea declarada en
        línea, MySQL no acepta el orden inverso: la
        instalación limpia fallaría.
        """

        orden = orden_del_esquema()

        posicion = {
            tabla: indice
            for indice, tabla in enumerate(orden)
        }

        for tabla, padres in DEPENDENCIAS.items():

            for padre in padres:

                assert posicion[padre] < posicion[tabla], (
                    f"{tabla} se crea antes que {padre}"
                )


class TestClaveForaneaDeVentas:

    def test_existe_sobre_usuario_id(self):
        conexion = obtener_conexion()

        cursor = conexion.cursor()

        cursor.execute("""
            SELECT rc.CONSTRAINT_NAME, rc.DELETE_RULE,
                   kcu.COLUMN_NAME,
                   kcu.REFERENCED_TABLE_NAME
            FROM information_schema.REFERENTIAL_CONSTRAINTS rc
            JOIN information_schema.KEY_COLUMN_USAGE kcu
                ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
                AND kcu.CONSTRAINT_SCHEMA = rc.CONSTRAINT_SCHEMA
            WHERE rc.CONSTRAINT_SCHEMA = DATABASE()
              AND rc.TABLE_NAME = 'ventas'
              AND kcu.REFERENCED_TABLE_NAME = 'usuarios'
        """)

        filas = cursor.fetchall()

        cursor.close()
        conexion.close()

        assert len(filas) == 1, filas

        nombre, regla, columna, referida = filas[0]

        assert nombre == "ventas_usuario_fk"
        assert columna == "usuario_id"
        assert referida == "usuarios"

    def test_es_set_null(self):
        """
        SET NULL y no CASCADE: borrar la cuenta de
        un vendedor no puede borrar sus ventas.

        Es la diferencia entre que un empleado se
        vaya y que se borren las ventas que hizo.
        """

        conexion = obtener_conexion()

        cursor = conexion.cursor()

        cursor.execute("""
            SELECT rc.DELETE_RULE
            FROM information_schema.REFERENTIAL_CONSTRAINTS rc
            WHERE rc.CONSTRAINT_SCHEMA = DATABASE()
              AND rc.CONSTRAINT_NAME = 'ventas_usuario_fk'
        """)

        fila = cursor.fetchone()

        cursor.close()
        conexion.close()

        assert fila[0] == "SET NULL"

    def test_la_columna_admite_nulo(self):
        """
        Las ventas anteriores a la migración no
        tienen vendedor.
        """

        conexion = obtener_conexion()

        cursor = conexion.cursor()

        cursor.execute("""
            SELECT IS_NULLABLE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'ventas'
              AND COLUMN_NAME = 'usuario_id'
        """)

        fila = cursor.fetchone()

        cursor.close()
        conexion.close()

        assert fila[0] == "YES"

    def test_esta_declarada_en_linea(self):
        """
        La clave está dentro del bloque CREATE TABLE
        de ventas, no añadida después.
        """

        contenido = texto_del_esquema()

        inicio = contenido.index("CREATE TABLE ventas")

        fin = contenido.index("CREATE TABLE", inicio + 10)

        bloque = contenido[inicio:fin]

        assert "ventas_usuario_fk" in bloque

        assert "ON DELETE SET NULL" in bloque


class TestDatosIniciales:

    def test_hay_marcas_sembradas(self):
        """
        Sin marcas no se puede crear un vehiculo: el
        desplegable saldria vacio.

        Se comprueba en el ARCHIVO y no en la tabla,
        porque las pruebas borran las marcas al
        vaciar. Lo que importa para una instalacion
        nueva es que el esquema las traiga.
        """

        contenido = texto_del_esquema()

        sin_comentarios = chr(10).join(
            l for l in contenido.splitlines()
            if not l.strip().startswith("--")
        )

        assert "INSERT INTO marcas" in sin_comentarios

        bloque = sin_comentarios.split(
            "INSERT INTO marcas"
        )[1].split(";")[0]

        nombres = re.findall(r"'([^']+)'", bloque)

        assert len(nombres) >= 10, nombres

        # Y ninguna repetida: el UNIQUE de
        # marcas.nombre rechazaria la instalacion.

        assert len(set(nombres)) == len(nombres)
        from database.configuracion import (
            obtener_stock_minimo
        )

        assert obtener_stock_minimo() >= 0

    def test_la_moneda_esta_sembrada(self):
        """
        Con los valores de siempre, para que
        instalar desde cero no mueva un solo importe
        de los que se ven.
        """

        from database.configuracion import leer_moneda

        moneda = leer_moneda()

        assert moneda["codigo"] == "USD"
        assert moneda["simbolo"] == "$"
        assert moneda["formato"] == "simbolo_espacio"
        assert moneda["separador_miles"] == ","
        assert moneda["separador_decimales"] == "."

    def test_no_hay_usuarios_sembrados(self):
        """
        Una contraseña en el repositorio sería una
        puerta abierta. El primer administrador se
        crea con crear_admin.py.
        """

        from database.usuarios import hay_usuarios

        # conftest crea uno para las pruebas, pero
        # en el esquema no hay ninguno sembrado.

        contenido = texto_del_esquema()

        sin_comentarios = "\n".join(
            l for l in contenido.splitlines()
            if not l.strip().startswith("--")
        )

        assert "INSERT INTO usuarios" not in (
            sin_comentarios
        )

        assert hay_usuarios() is True


class TestLaAplicacionSobreLaBaseNueva:

    """
    La prueba de que una instalación limpia vale
    para algo: la aplicación opera entera contra
    ella, desde el administrador inicial hasta el
    PDF del contrato.
    """

    def test_el_recorrido_completo(
        self, como_administrador, datos_base
    ):
        import os
        import tempfile

        from database.ventas import registrar_venta
        from database.contratos import (
            crear_contrato,
            obtener_contrato
        )
        from database.pagos import (
            registrar_pago,
            saldo_venta
        )
        from utils.contrato_pdf import generar_contrato
        from utils import moneda

        _, id_auto, id_cliente = datos_base

        # 1. Una venta, que guarda el vendedor.

        id_venta, numero = registrar_venta(
            id_cliente, id_auto, "2026-10-03", 50000.0
        )

        assert numero == ""

        from database.ventas import obtener_ventas

        assert obtener_ventas()[0][5] == "admin"

        # 2. Un contrato con cuotas.

        id_contrato, cnumero = crear_contrato(
            venta_id=id_venta,
            forma_pago="Anticipo + cuotas",
            anticipo=10000.0,
            cantidad_cuotas=10
        )

        assert cnumero.startswith("CTR-2026-")

        # 3. Un pago, y el saldo baja.

        id_pago, motivo = registrar_pago(
            id_venta, 20000.0, "2026-10-03", "Efectivo"
        )

        assert id_pago is not None, motivo

        precio, pagado, saldo = saldo_venta(id_venta)

        assert float(pagado) == 20000.0
        assert float(saldo) == 30000.0

        # 4. El PDF sale.

        contrato = obtener_contrato(id_contrato)

        destino = os.path.join(
            tempfile.gettempdir(),
            "contrato_prueba_instalacion.pdf"
        )

        ruta = generar_contrato(contrato, destino)

        assert os.path.exists(ruta)
        assert os.path.getsize(ruta) > 1000

        os.remove(ruta)

        # 5. Y el importe sale con la moneda.

        assert moneda.formato_dinero(
            36500
        ) == "$ 36,500.00"
