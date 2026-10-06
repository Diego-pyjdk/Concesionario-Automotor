# ==========================================
# ARRANQUE DE LA APLICACIÓN
# ==========================================
# Comprueba que main.py arranca de verdad.
#
# Existe porque durante la FASE 1 se cambió la
# ruta de la hoja de estilo para que no dependiera
# del directorio de trabajo, y se subió un nivel
# de más. La app NO arrancaba:
#
#     _RAIZ = os.path.dirname(
#         os.path.dirname(os.path.abspath(__file__))
#     )
#
# main.py está en la raíz del proyecto, así que
# con dos niveles la ruta apuntaba al escritorio.
#
# Ni compilar ni abrir cada vista lo detecta: el
# error sale solo al ejecutar main.py entero, y eso
# no lo hacía ninguna comprobación.
# ==========================================


import os
import pathlib
import subprocess
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]

VENV_PYTHON = RAIZ / "venv" / "Scripts" / "python.exe"

if not VENV_PYTHON.exists():

    VENV_PYTHON = pathlib.Path(sys.executable)


@pytest.fixture(scope="module")
def qapp():
    """
    Una QApplication para el módulo.

    Sin ella, construir cualquier QWidget tumba el
    proceso con un fallo de segmentación y pytest no
    llega a escribir el informe: se queda en
    pantalla en blanco sin decir por qué.
    """

    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    from PySide6.QtWidgets import QApplication

    aplicacion = QApplication.instance()

    if aplicacion is None:

        aplicacion = QApplication(
            list(sys.argv)
        )

    yield aplicacion


class TestRutas:

    def test_raiz_es_la_del_proyecto(self):
        """
        main.py vive en la raíz, así que la raíz
        del proyecto es SU directorio. Un nivel
        más sería el escritorio.
        """

        import main

        assert pathlib.Path(
            main._RAIZ
        ).resolve() == RAIZ.resolve()

    def test_encuentra_la_hoja_de_estilo(self):
        import main

        assert os.path.exists(
            main.ARCHIVO_ESTILO
        ), (
            f"no se encuentra {main.ARCHIVO_ESTILO}; "
            "la aplicación no arranca"
        )

        assert main.ARCHIVO_ESTILO.endswith(
            os.path.join("gui", "estilo.css")
        )

    def test_arranca_desde_cualquier_directorio(
        self
    ):
        """
        La ruta sale de __file__, así que tiene que
        funcionar igual se arranque desde la raíz
        del proyecto o desde otro sitio.
        """

        codigo = (
            "import sys; sys.path.insert(0, %r);"
            "import main, os;"
            "print(main._RAIZ);"
            "print(os.path.exists(main.ARCHIVO_ESTILO))"
        ) % str(RAIZ)

        proceso = subprocess.run(
            [str(VENV_PYTHON), "-c", codigo],
            cwd=str(RAIZ.parent),
            capture_output=True,
            text=True,
            timeout=90
        )

        salida = proceso.stdout.strip().splitlines()

        assert proceso.returncode == 0, proceso.stderr

        assert salida[-1].strip() == "True", (
            "la hoja de estilo no se encuentra al "
            "arrancar desde fuera de la raíz"
        )


class TestArranqueReal:

    def test_login_cancelado_sale_limpio(self):
        """
        Se ejecuta main.py entero en otro proceso,
        con el login cancelado, y tiene que salir
        sin excepciones.
        """

        codigo = """
import sys
sys.path.insert(0, {raiz!r})

import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import (
    QApplication, QMessageBox
)

for nombre in ("warning", "information",
               "critical", "question"):
    setattr(
        QMessageBox, nombre,
        staticmethod(lambda *a, **k: QMessageBox.Ok)
    )

# El login se cancela: main.ejecutar() tiene que
# devolver sin quedarse esperando.
QApplication.exec = lambda self: 0

import gui.login_view as login

login.LoginView.exec = lambda self: 0

import main

print("CODIGO", main.ejecutar())
""".format(raiz=str(RAIZ))

        proceso = subprocess.run(
            [str(VENV_PYTHON), "-c", codigo],
            cwd=str(RAIZ),
            capture_output=True,
            text=True,
            timeout=180
        )

        assert proceso.returncode == 0, (
            "main.py no arranca:\n"
            f"{proceso.stderr[-1500:]}"
        )

        assert "CODIGO 0" in proceso.stdout, (
            proceso.stdout[-800:]
        )

    # La rama con sesion activa (login entra ->
    # VentanaPrincipal) NO se prueba aqui: lanzar
    # un subproceso con Qt desde dentro de pytest
    # tumba el proceso entero sin informe, y no
    # por un fallo de la aplicacion sino por el
    # cruce de dos entornos de Qt.
    #
    # Esa cobertura esta repartida en dos sitio
    # que si funcionan:
    #
    #   - test_gui_completo.py construye
    #     VentanaPrincipal con los dos roles y
    #     recorre las diez secciones.
    #
    #   - test_login_cancelado_sale_limpio (arriba)
    #     ejecuta main.py entero de verdad y
    #     comprueba que carga estilos y sale.


class TestGuardaDeSesion:

    def test_la_ventana_principal_exige_sesion(
        self, qapp, como_administrador
    ):
        """
        La ventana principal solo se construye con
        sesión. Sin ella, PermissionError a propósito:
        si se construyera, se vería el panel a un
        usuario que no ha entrado.
        """

        from gui.ventana_principal import VentanaPrincipal
        import sesion as modulo_sesion

        modulo_sesion.cerrar_sesion()

        with pytest.raises(PermissionError):

            VentanaPrincipal()
