# Concesionario: actualización de interfaz y gestión

Esta entrega parte de `concesionario (2).zip`. Conserva los módulos de ventas,
contratos, cuotas, pagos, garantías, monedas, usuarios y auditoría.

## Actualizar tu proyecto actual en Windows

1. Guarda una copia de tu carpeta actual y un respaldo de MySQL.
2. Extrae este ZIP en una carpeta nueva. Copia a ella tu `.env` actual.
   El paquete no incluye credenciales, tu entorno virtual ni documentos de clientes.
   Conserva también tu carpeta `documentos/` original.
3. En MySQL Workbench abre `sql/actualizar_mejoras.sql` y ejecuta el archivo completo.
   Usa la conexión de tu base actual. El script selecciona `concesionario`;
   cambia únicamente esa línea `USE` si tu base tiene otro nombre.
   No ejecutes `database/esquema.sql` sobre tu base actual: contiene `DROP DATABASE`.
4. En PowerShell, dentro de la carpeta nueva:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe verificar_instalacion.py
.\venv\Scripts\python.exe main.py
```

Tus usuarios y contraseñas de acceso a la aplicación siguen siendo los mismos.
No necesitas volver a ejecutar `crear_admin.py` si ya tienes administrador.
Cuando verifiques todo, puedes trabajar con la carpeta nueva o copiar sus archivos
sobre la original conservando `.env`, `venv/` y `documentos/`.

## Instalación nueva, sin datos existentes

Abre `sql/instalacion_nueva.sql` en Workbench y ejecuta el archivo completo.
Crea las 17 tablas, los índices y la configuración inicial. Exige que la base
`concesionario` no exista: no se utiliza para actualizar una instalación.

Después copia `.env.example` a `.env`, configura MySQL, instala las dependencias y
crea el primer administrador:

```powershell
.\venv\Scripts\python.exe crear_admin.py
.\venv\Scripts\python.exe main.py
```

## Cómo usar las mejoras

- **Tema:** botón ◐ al pie del menú; el equipo recuerda la preferencia.
- **Menú:** botón ☰ para contraerlo; se agrupa en Operaciones, Finanzas y Administración.
- **Inicio:** accesos a registrar ventas e inventario; cobranza solo para administración.
  Los nuevos importes de cobranza se muestran separados por moneda.
- **Listados:** pulsa una cabecera para ordenar. Usa Anterior/Siguiente y 25/50/100
  filas por página. La paginación de estos listados es local sobre el resultado de
  la búsqueda; reduce lo que se dibuja, pero no limita aún la consulta SQL.
- **Vehículos:** filtro con/sin stock; selecciona una fila y pulsa Ver ficha o doble clic.
  Datos ampliados, fotos y unidades están en pestañas. El menú Más reúne las acciones.
- **Fotos:** formatos JPG, PNG y WebP, hasta 5 MB y 40 megapíxeles. Se guardan en MySQL,
  incluidas en sus respaldos, sin depender de rutas de Windows.
- **Unidades:** identifica vehículos que YA forman parte del stock. Registra chasis/VIN,
  matrícula, kilometraje, observaciones y estado disponible/reservado/taller.
  Esto no aumenta el stock. Si ingresó otro vehículo, aumenta el stock primero.
  El chasis es único y las unidades vendidas no se pueden editar.
- **Venta:** selecciona el chasis disponible. El stock antiguo sin identificar conserva
  la opción Stock sin individualizar. Una unidad reservada, en taller o vendida no se
  vende por este camino. Anular una venta permitida libera su unidad y repone el stock.
- **Contratos:** el PDF incluye chasis y matrícula cuando la venta tiene una unidad.
- **Clientes:** Ver ficha reúne ventas, contratos y, para administración, pagos y saldos.
  No se suman dólares y guaraníes. Doble clic en una venta abre su contrato.
- **Cartera:** tarjetas de resumen y botón Agenda de cobranza para registrar contactos,
  próxima visita/llamada y promesas de pago. Marcar atendido cierra el seguimiento;
  una promesa nunca registra un cobro ni cambia el saldo.
- **Configuración:** Copias de seguridad crea y verifica un ZIP con las tablas y las fotos.
  Guarda los respaldos en un lugar seguro: contienen datos de clientes y usuarios.

## Recuperar una copia

La recuperación SOLO crea una base nueva. Rechaza nombres existentes y la base activa.
Los respaldos son archivos generados por esta aplicación; no son un ZIP de código.

Verificar:

```powershell
.\venv\Scripts\python.exe restaurar_respaldo.py "C:\Respaldos\respaldo_20261006.zip"
```

Recuperar:

```powershell
.\venv\Scripts\python.exe restaurar_respaldo.py "C:\Respaldos\respaldo_20261006.zip" --base concesionario_recuperado
```

Comprueba esa base en Workbench antes de cambiar `DB_NAME` en `.env` y reiniciar.
El usuario de MySQL necesita permiso para crear la nueva base. Los documentos PDF
externos y `.env` se conservan aparte; el respaldo cubre las tablas y las fotos.
No ejecutes migraciones mientras se genera un respaldo.

## Pruebas

Las pruebas existentes y las de nuevas funciones trabajan exclusivamente en una base
`pruebas_concesionario`, independiente de tu base de negocio. El usuario de pruebas
necesita permisos para crear/eliminar esa base. Nunca le asignes el nombre de tu base real.

```powershell
.\venv\Scripts\python.exe -m pip install pytest
.\venv\Scripts\python.exe -m pytest
.\venv\Scripts\python.exe -m pytest pruebas_mejoras
```

Las nuevas pruebas cubren unidades, stock, VIN en contratos, fotos, promesas, saldos,
permisos, integridad de respaldos y recuperación exacta de datos y binarios.
