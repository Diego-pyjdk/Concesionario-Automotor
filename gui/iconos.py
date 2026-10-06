# Iconos vectoriales locales; no requiere fuentes ni acceso a Internet.
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen

TRAZOS = {
    'Inicio': [(4,11,12,4),(12,4,20,11),(6,10,6,20),(6,20,18,20),(18,20,18,10)],
    'Vehículos': [(4,9,7,5),(7,5,17,5),(17,5,20,9),(3,10,21,10),(3,10,3,18),(3,18,21,18),(21,18,21,10),(6,17,6,21),(18,17,18,21)],
    'Clientes': [(5,20,5,16),(5,16,19,16),(19,16,19,20)],
    'Ventas': [(4,5,20,5),(20,5,20,20),(20,20,4,20),(4,20,4,5),(8,10,16,10),(8,15,16,15)],
    'Reportes': [(5,20,5,12),(12,20,12,5),(19,20,19,9)],
    'Cartera': [(3,6,21,6),(21,6,21,19),(21,19,3,19),(3,19,3,6),(3,10,21,10)],
}


def icono(nombre, color="#b8c8dd"):
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor(color), 1.8))
    if nombre in ('Clientes', 'Usuarios'):
        painter.drawEllipse(8, 3, 8, 8)
    trazos = TRAZOS.get(nombre, [(6,3,18,3),(18,3,18,21),(18,21,6,21),(6,21,6,3),(9,8,15,8),(9,13,15,13)])
    for puntos in trazos:
        painter.drawLine(*puntos)
    painter.end()
    return QIcon(pixmap)
