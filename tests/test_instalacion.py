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
#   - las doce tablas existen
#   - ventas.usuario_id tiene su clave foránea
#     declarada EN LÍNEA, con ON DELETE SET NULL
#   - el esquema NO usa ALTER TABLE: el orden de
#     las tablas es el de dependencias
#   - la moneda viene sembrada con los valores de
#     siempre
#   - la aplicación opera contra esa base recién
#     creada: administrador, venta con vendedor,
#     contrato financiado con su cronograma, cobro de
#     una cuota, saldos, PDF del contrato y PDF del
#     recibo
# ==========================================


import pathlib
import re

from datetime import date
from decimal import Decimal

from database.conexion import obtener_conexion

RAIZ = pathlib.Path(__file__).resolve().parents[1]

ESQUEMA = RAIZ / "database" / "esquema.sql"

TABLAS = [
    "marcas", "autos", "clientes", "usuarios",
    "ventas", "configuracion", "auditoria",
    "contratos", "cuotas", "garantias",
    "convenios", "pagos", "auto_fichas", "auto_fotos", "unidades_vehiculo", "venta_unidades", "seguimiento_cobranza"
]

# De quién depende cada tabla.

DEPENDENCIAS = {
    "auto_fichas": {"autos"}, "auto_fotos": {"autos"},
    "unidades_vehiculo": {"autos"}, "venta_unidades": {"ventas", "unidades_vehiculo"},
    "seguimiento_cobranza": {"contratos", "usuarios"},
    "autos": {"marcas"},
    "ventas": {"clientes", "autos", "usuarios"},
    "auditoria": {"usuarios"},
    "contratos": {"ventas", "clientes", "autos",
                  "usuarios"},
    "cuotas": {"contratos"},
    "pagos": {"ventas", "contratos", "cuotas",
              "usuarios"},
    "garantias": {"contratos"},
    "convenios": {"contratos", "cuotas"}
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

    def test_no_hay_usuarios_sembrados(
        self, como_administrador
    ):
        """
        Una contraseña en el repositorio sería una
        puerta abierta. El primer administrador se
        crea con crear_admin.py.

        Y se PIDE la fixture como_administrador, que
        antes no se pedía. La comprobación de que en
        el esquema no hay ninguno va contra el ARCHIVO,
        así que no necesita la base; pero la de que hay
        un administrador de verdad sí, y antes se
        apoyaba en que ALGUNA prueba anterior hubiera
        dejado una cuenta.

        Eso no es una comprobación: es una casualidad
        del orden. Con este archivo ejecutado solo, o
        con la suite reordenada, la cuenta no estaba y
        la prueba fallaba sin que hubiera pasado nada.
        Pedir la fixture hace que la prueba diga lo que
        dice: tras crear el administrador, hay uno.
        """

        from database.usuarios import hay_usuarios

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
            cantidad_cuotas=10,
            periodicidad="mensual",
            primer_vencimiento=date(2026, 11, 3)
        )

        assert id_contrato is not None, cnumero

        assert cnumero.startswith("CTR-2026-")

        # ------------------------------
        # 2b. EL CRONOGRAMA
        # ------------------------------
        # Se genera nada más firmar, porque es lo que
        # hace el formulario. Contra una instalación
        # nueva, sin esto no se llegaría ni a la
        # cartera: el módulo de financiación es
        # precisamente esto.

        from database.financiera import (
            generar_cronograma,
            obtener_cuota,
            obtener_cuotas,
            registrar_pago_cuota
        )

        total, motivo = generar_cronograma(id_contrato)

        assert total == 10, motivo

        cuotas = obtener_cuotas(id_contrato)

        # La suma tiene que cuadrar con el saldo
        # financiado hasta el céntimo: es lo que
        # sostiene la cartera entera.

        suma = sum(
            (cuota["importe"] for cuota in cuotas),
            Decimal("0.00")
        )

        contrato_visto = obtener_contrato(id_contrato)

        assert suma == contrato_visto["saldo_financiado"]

        # ------------------------------
        # 3. UN COBRO CONTRA UNA CUOTA
        # ------------------------------
        # Con lo cobrado, el saldo de la cuota baja y
        # la de la venta también. Son las dos cosas
        # que tienen que cuadrar a la vez.

        id_pago_cuota, motivo = registrar_pago_cuota(
            cuotas[0]["id"],
            cuotas[0]["importe"],
            "2026-11-03",
            "Efectivo"
        )

        assert id_pago_cuota is not None, motivo

        assert obtener_cuota(cuotas[0]["id"])["saldo"] == (
            Decimal("0.00")
        )

        # ------------------------------
        # 4. UN PAGO SUELTO
        # ------------------------------

        id_pago, motivo = registrar_pago(
            id_venta, 20000.0, "2026-10-03", "Efectivo"
        )

        assert id_pago is not None, motivo

        # El pago de la cuota cuenta para el saldo de
        # la venta, y el suelto también: los dos van a
        # la misma tabla.

        precio, pagado, saldo = saldo_venta(id_venta)

        float_pagado = float(pagado)

        assert float_pagado == (
            20000.0 + float(cuotas[0]["importe"])
        ), (
            "el cobro de una cuota tiene que bajar el "
            "saldo de la venta como cualquier otro pago"
        )

        assert float(saldo) == 50000.0 - float_pagado

        # 5. El PDF sale.

        contrato = obtener_contrato(id_contrato)

        destino = os.path.join(
            tempfile.gettempdir(),
            "contrato_prueba_instalacion.pdf"
        )

        ruta = generar_contrato(contrato, destino)

        assert os.path.exists(ruta)
        assert os.path.getsize(ruta) > 1000

        os.remove(ruta)

        # 6. Y el recibo del cobro sale.

        from database.pagos import obtener_pagos_detalle
        from utils.recibo_pdf import generar_recibo

        pagos = obtener_pagos_detalle(id_venta)

        assert len(pagos) == 2

        recibo_pago = next(
            p for p in pagos
            if p["cuota_id"] == cuotas[0]["id"]
        )

        assert recibo_pago["recibo"], (
            "un cobro de cuota se guarda con número de "
            "recibo: es lo que se le lleva el cliente"
        )

        destino_recibo = os.path.join(
            tempfile.gettempdir(),
            "recibo_prueba_instalacion.pdf"
        )

        ruta_recibo = generar_recibo(
            recibo_pago,
            contrato,
            obtener_cuota(cuotas[0]["id"])
        )

        assert os.path.exists(ruta_recibo)
        assert os.path.getsize(ruta_recibo) > 500

        os.remove(ruta_recibo)

        # 7. Y el importe sale con la moneda.

        assert moneda.formato_dinero(
            36500
        ) == "$ 36,500.00"
