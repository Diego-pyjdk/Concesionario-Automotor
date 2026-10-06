# Verificación de la entrega

- Batería conjunta: 605 pruebas aprobadas en MySQL 8.0.46 y Qt sin pantalla.
- Dependencias: PySide6 6.11.2, mysql-connector-python 26.7.0 y Python 3.12.14.
- Primera batería completa con ReportLab 4.4.9; se instaló después ReportLab 5.0.1,
  la versión fijada en requirements.txt, y se repitieron 91 pruebas de contratos,
  pagos, instalación, fotos, unidades y respaldos: todas aprobadas.
- Tras los ajustes visuales finales: 13 pruebas de interfaz aprobadas.
- Recorrido de las 11 secciones de administración y 6 de vendedor, temas claro
  y oscuro y ventanas de 1440×900, 1024×768 y 900×650. Fichas construidas y sin
  avisos de error. Se inspeccionaron capturas de Inicio y Cartera.
- Migración SQL repetida sin pérdida de registros; 17 tablas verificadas.
- Respaldo verificado por hash y restaurado en una base nueva, preservando
  conteos, decimales y fotos binarias. Se rechaza sobrescribir la base original.

Las verificaciones se hicieron en Linux con Qt sin pantalla y una base de prueba;
no se accedió a tu Windows ni a tu base real. Después de instalar, comprueba tus
operaciones habituales con una copia de tus datos antes de reemplazar tu carpeta.
La paginación de listados es local y las consultas principales de lectura se
hacen en segundo plano; las escrituras y formularios conservan operaciones síncronas.
