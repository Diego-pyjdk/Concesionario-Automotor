# Comprobaciones de interfaz sin acceder a la base del usuario.
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

# ------------------------------
# LA BASE REAL NO SE TOCA NI POR ERROR
# ------------------------------
#
# Estas pruebas viven FUERA de `tests/`, así que pytest
# no carga el `conftest` que levanta la base de
# pruebas. Sin esto, si alguna se escapara y leyera o
# escribiera, lo haría contra la base del `.env`: la
# de trabajo.
#
# Por eso la base se fija AQUÍ, antes de importar
# cualquier módulo de la aplicación (que es cuando
# `cargar_env()` lee el entorno):
#
#   - Si `pruebas_concesionario` existe, se usa: es
#     desechable.
#   - Si no existe, la conexión falla ruidosamente, que
#     es justo lo que tiene que pasar antes que tocar
#     la base de trabajo.
#
# Un conftest.py aquí resolvería lo mismo, pero se
# llamaría `conftest` y taparía a `tests/conftest.py`
# en el `from conftest import leer_pdf` de otras
# pruebas.
os.environ['DB_NAME'] = 'pruebas_concesionario'
from datetime import date
from decimal import Decimal
import json
import zipfile
import hashlib
import time
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication,QMessageBox
from database import fichas
import sesion
from errores import PermisoDenegado,ErrorSistema,ErrorValidacion
from utils.respaldo import codificar,decodificar,identificador,verificar_respaldo
from gui.tema import aplicar_tema
from gui.vista_base import VistaBase
from gui.vista_listado import VistaListado
from gui.fichas_dialog import AutoFichaDialog,ClienteFichaDialog,UnidadForm
from gui.seguimiento_dialog import SeguimientoDialog,ContactoForm
from gui.respaldo_dialog import RespaldoDialog
from gui.trabajos import Trabajos


@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def entorno(monkeypatch,app):
    sesion.iniciar_sesion((1,'admin','Administrador','administrador'))
    monkeypatch.setattr('permisos.registrar_intento',lambda *args: None)
    for nombre in ('warning','critical','information','question'):
        monkeypatch.setattr(QMessageBox,nombre,lambda *args,**kwargs: QMessageBox.No)
    yield
    sesion.cerrar_sesion()
    VistaBase.diferir_carga = False


def test_codificacion_respaldo_exacta():
    datos = [Decimal('150000000.00'),b'foto\x00\xff',date(2026,10,6)]
    assert json.loads(json.dumps(datos,default=codificar),object_hook=decodificar) == datos


def test_respaldo_detecta_corrupcion(tmp_path):
    ruta = tmp_path/'mal.zip'
    with zipfile.ZipFile(ruta,'w') as z:
        z.writestr('datos.json','{}')
        z.writestr('manifest.json',json.dumps({'version':1,'sha256':'incorrecto'}))
    with pytest.raises(ErrorSistema):
        verificar_respaldo(ruta)


@pytest.mark.parametrize('nombre',['a; DROP DATABASE x','../test','mysql-base',''])
def test_identificadores_invalidos(nombre):
    with pytest.raises(ErrorSistema):
        identificador(nombre)


def test_vendedor_no_lee_cobranza():
    sesion.iniciar_sesion((2,'vendedor','Vendedor','vendedor'))
    with pytest.raises(PermisoDenegado):
        fichas.pagos_cliente(1)
    with pytest.raises(PermisoDenegado):
        fichas.seguimiento()
    with pytest.raises(PermisoDenegado):
        fichas.guardar_unidad(1,'ABC','',0,'disponible','')


def test_fichas_y_formularios(monkeypatch,app):
    monkeypatch.setattr(fichas,'ficha_auto',lambda _:dict(marca='Toyota',modelo='Corolla',anio=2026,color='Blanco',stock=2,precio=Decimal('50000000'),combustible='Nafta',transmision='Manual',observaciones=''))
    monkeypatch.setattr(fichas,'fotos_auto',lambda _:[])
    monkeypatch.setattr(fichas,'unidades_auto',lambda _:[])
    monkeypatch.setattr(fichas,'ficha_cliente',lambda _:(dict(nombre='Ana',apellido='Prueba',documento='123',telefono='0991',email=''),[dict(id=1,fecha=date.today(),vehiculo='Toyota',precio=Decimal('10'),moneda='USD',contrato_id=None,numero=None,estado=None)]))
    monkeypatch.setattr(fichas,'pagos_cliente',lambda _:([],[]))
    monkeypatch.setattr(fichas,'seguimiento',lambda *args:[])
    monkeypatch.setattr('gui.seguimiento_dialog.contratos_seguimiento',lambda:[])
    ventanas = [AutoFichaDialog(None,1),ClienteFichaDialog(None,1),UnidadForm(None,1),SeguimientoDialog(),ContactoForm(),RespaldoDialog()]
    for oscuro in [False,True]:
        aplicar_tema(oscuro)
        for ventana in ventanas:
            ventana.show()
            app.processEvents()
            assert ventana.minimumSizeHint().width() < 1050
            ventana.hide()
    for ventana in ventanas:
        ventana.deleteLater()


def test_cliente_vendedor_no_construye_pagos(monkeypatch):
    sesion.iniciar_sesion((2,'vendedor','Vendedor','vendedor'))
    monkeypatch.setattr(fichas,'ficha_cliente',lambda _:(dict(nombre='Ana',apellido='Prueba'),[]))
    monkeypatch.setattr(fichas,'pagos_cliente',lambda _:pytest.fail('El vendedor no debe consultar pagos'))
    dialogo = ClienteFichaDialog(None,1)
    assert dialogo.pestanas.count() == 1


class ListadoPrueba(VistaListado):
    columnas = ['ID','Precio','Acciones']
    columna_acciones = 2
    def nuevo_registro(self):
        pass
    def cargar_datos(self):
        self.mostrar_filas([(i,Decimal(str(200-i))) for i in range(120)])
    def pintar_fila(self,fila,registro):
        self.marcar_columnas(fila,registro)


def test_paginacion_y_orden_numerico():
    vista = ListadoPrueba()
    assert vista.tabla.rowCount() == 50
    vista.ordenar_por(1)
    assert vista.tabla.item(0,1).text() == '81'
    vista.cambiar_pagina(1)
    assert vista.tabla.item(0,1).text() == '131'
    vista.cambiar_tamano('100')
    assert vista.tabla.rowCount() == 100
    vista.mostrar_filas([])
    assert vista.tabla.rowCount() == 0


def test_trabajo_devuelve_en_hilo_de_ui(app):
    controlador = Trabajos(app)
    resultados = []
    controlador.ejecutar(lambda:(sesion.obtener_sesion().rol,Decimal('1.25')),resultados.append,lambda e:pytest.fail(str(e)))
    limite = time.monotonic()+5
    while not resultados and time.monotonic()<limite:
        app.processEvents()
        time.sleep(.01)
    assert resultados == [('administrador',Decimal('1.25'))]


def test_resultado_de_sesion_cerrada_se_descarta(app):
    controlador = Trabajos(app)
    resultados = []
    controlador.ejecutar(lambda: 1,resultados.append,resultados.append)
    sesion.cerrar_sesion()
    limite=time.monotonic()+1
    while time.monotonic()<limite:
        app.processEvents()
        time.sleep(.01)
    assert resultados == []


def test_tema_oscuro_cubre_fondo_y_texto_de_botones(app):
    from PySide6.QtWidgets import QWidget, QVBoxLayout
    from PySide6.QtGui import QPalette
    from utils.helpers import crear_boton_secundario
    aplicar_tema(True)
    contenedor = QWidget()
    layout = QVBoxLayout(contenedor)
    boton = crear_boton_secundario('Consultar', lambda: None)
    layout.addWidget(boton)
    contenedor.resize(300,150)
    contenedor.show()
    app.processEvents()
    assert contenedor.grab().toImage().pixelColor(2,2).lightness() < 70
    assert boton.palette().color(QPalette.ButtonText).lightness() > 140
    contenedor.close()
    aplicar_tema(False)
