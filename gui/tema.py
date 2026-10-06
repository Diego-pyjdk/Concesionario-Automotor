import re
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget
# Preferencias visuales por equipo, independientes de la moneda y los datos.
from pathlib import Path
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

AJUSTES = QSettings('Tucan', 'Concesionario')
RUTA = Path(__file__).with_name('estilo.css')
OSCURO = {
    '#f1f5f9': '#10151e', '#ffffff': '#192230', '#fff': '#192230',
    '#0f172a': '#e5edf6', '#475569': '#b0bdce', '#64748b': '#9aabc0',
    '#e2e8f0': '#334155', '#f8fafc': '#202c3d', '#f3f4f6': '#202c3d',
    '#dbeafe': '#193656', '#eff6ff': '#193656', '#fee2e2': '#492631',
    '#fef2f2': '#492631', '#dcfce7': '#163e32', '#f0fdf4': '#163e32',
    '#fef3c7': '#473b22', '#fffbeb': '#473b22'
}


def aplicar_tema(oscuro=None):
    app = QApplication.instance()
    if oscuro is None:
        oscuro = AJUSTES.value('tema', 'claro') == 'oscuro'
    texto = RUTA.read_text(encoding='utf-8')
    # Sustitución simultánea: evita recolorear dos veces un mismo valor.
    if oscuro:
        texto = re.sub(r'#[0-9a-fA-F]{3,6}\b', lambda m: OSCURO.get(m[0].lower(), m[0]), texto)
        # La barra lateral conserva texto claro, independiente del tema.
        texto = 'QWidget {background-color:#10151e;color:#e5edf6;}\n' + texto
        texto += '\nQLabel {background:transparent;} QPushButton#boton_secundario, QPushButton#boton_editar, QPushButton#boton_filtro {color:#e5edf6;} QLabel#aviso {color:#93c5fd;} QLabel#aviso_error {color:#fecdd3;} QMenu::item:selected {color:#e5edf6;} QPushButton#boton_principal, QPushButton#boton_peligro, QPushButton#boton_login {color:#ffffff;} QHeaderView::section {color:#e5edf6;} QFrame#sidebar {background:#0b111b;} QWidget#menu_sidebar {background:#0b111b;} QFrame#sidebar QLabel {color:#dbe5f2;}\n'
    app.setStyleSheet(texto)
    paleta = QPalette()
    colores = {
        QPalette.Window: '#10151e' if oscuro else '#f1f5f9',
        QPalette.Base: '#192230' if oscuro else '#ffffff',
        QPalette.AlternateBase: '#202c3d' if oscuro else '#f8fafc',
        QPalette.Text: '#e5edf6' if oscuro else '#0f172a',
        QPalette.WindowText: '#e5edf6' if oscuro else '#0f172a',
        QPalette.Button: '#192230' if oscuro else '#ffffff',
        QPalette.ButtonText: '#e5edf6' if oscuro else '#0f172a',
        QPalette.Highlight: '#2563eb', QPalette.HighlightedText: '#ffffff'
    }
    for rol, valor in colores.items():
        paleta.setColor(rol, QColor(valor))
    app.setPalette(paleta)
    app.setProperty('tema_oscuro', oscuro)
    AJUSTES.setValue('tema', 'oscuro' if oscuro else 'claro')
    # Recolorear filas con estados ya creadas.
    for widget in app.allWidgets():
        if isinstance(widget, QTableWidget):
            for fila in range(widget.rowCount()):
                for columna in range(widget.columnCount()):
                    item = widget.item(fila,columna)
                    if item and item.data(Qt.UserRole):
                        tono = item.data(Qt.UserRole)
                        claros = {'tono_ok':'#dcfce7','tono_fuerte_ok':'#16a34a','tono_info':'#dbeafe','tono_aviso':'#fef3c7','tono_peligro':'#fee2e2'}
                        oscuros = {'tono_ok':'#163e32','tono_fuerte_ok':'#166534','tono_info':'#193656','tono_aviso':'#473b22','tono_peligro':'#492631'}
                        if tono in claros:
                            item.setBackground(QColor((oscuros if oscuro else claros)[tono]))
                            item.setForeground(QColor('#ffffff' if tono == 'tono_fuerte_ok' else ('#e5edf6' if oscuro else '#0f172a')))
    return oscuro
