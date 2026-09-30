import sys

from PySide6.QtWidgets import QApplication

from gui.ventana_principal import VentanaPrincipal


app = QApplication(sys.argv)

with open("gui/estilo.css", "r", encoding="utf-8") as archivo:
    app.setStyleSheet(archivo.read())

ventana = VentanaPrincipal()
ventana.show()

sys.exit(app.exec())