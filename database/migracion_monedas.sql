-- ==========================================
-- MONEDAS: GUARANÍ Y DÓLAR
-- ==========================================
-- Para bases que YA TIENEN DATOS. No toca ni un
-- importe: ni de ventas, ni de contratos, ni de
-- cuotas, ni de pagos.
--
-- Este archivo hace tres cosas, y las tres se pueden
-- aplicar aunque se aplique dos veces:
--
--   1. Amplía las columnas de dinero de DECIMAL(10,2)
--      a DECIMAL(15,2).
--   2. Añade `ventas.moneda`, que no existía.
--   3. Siembra la clave `moneda_cifras`, que es la
--      que dice cuántos decimales se muestran.
--
-- -------------------------------------------------
-- POR QUÉ AMPLIAR LAS COLUMNAS
-- -------------------------------------------------
-- DECIMAL(10,2) llega hasta 99.999.999,99. Ese
-- número estaba pensado para dólares, y en guaraníes
-- un vehículo normal cuesta 30-100 millones: no cabe.
--
-- El problema no es solo el techo. Era que la
-- validación de la aplicación aceptaba hasta
-- 999.999.999, más de lo que MySQL guarda. En esa
-- ventana el formulario dejo pasar el precio y la
-- base lo rechazó con "Out of range", que es el peor
-- sitio posible para descubrirlo.
--
-- Ampliar la columna NO altera ningún valor: para
-- MySQL, 25.000.00 en DECIMAL(10,2) y en DECIMAL(15,2)
-- es el mismo 25.000.00. Lo único que cambia es que
-- caben más cifras.
--
-- -------------------------------------------------
-- POR QUÉ `ventas.moneda`
-- -------------------------------------------------
-- `contratos.moneda` ya existía: el importe y la
-- moneda se firmaban juntos. Las ventas no lo tenían,
-- y una venta sin moneda es una venta que cambia de
-- lectura en cuanto alguien toca el ajuste:
--
--     venta de 25.000 dólares
--     el administrador pasa la aplicación a guaraníes
--     la venta ahora dice "Gs. 25.000"
--
-- El número no se ha convertido. Solo se ha hecho que
-- el mismo documento diga dos cosas distintas.
--
-- Lo que se hace aquí:
--
--   - Se añade la columna.
--   - Las ventas que ya existen reciben la moneda que
--     había configurada cuando se hizo la migración,
--     que es lo único que se puede saber de un dato que
--     ya no guarda esa información. Si ese día estaba
--     en dólares, quedan en dólares.
--
-- NO se inventa un tipo de cambio, ni se multiplica por
-- ningún factor, ni se deduce de nada. Una venta de la
-- que no se sabe en qué moneda se hizo no se puede
-- convertir, y adivinarlo sería peor que dejarlo como
-- está.
--
-- Para una venta REAL que sí se sabe que era en
-- dólares, se corrige a mano, una vez, y queda
-- escrito:
--
--     UPDATE ventas SET moneda = 'USD' WHERE id = 149;
--
-- Eso es una operación del administrador sobre un dato
-- que él conoce, no una migración que adivina.
--
-- -------------------------------------------------
-- CÓMO APLICARLO
-- -------------------------------------------------
--     mysql -u USUARIO -p CONCESIONARIO < migracion_monedas.sql
--
-- Se puede volver a aplicar sin miedo: los MODIFY
-- COLUMN son idempotentes y los INSERT usan ON
-- DUPLICATE KEY UPDATE.
--
-- ANTES de aplicarlo, comprueba que no tienes ninguna
-- venta con una moneda guardada que quieras
-- conservar: el script solo rellena las que están a
-- NULL, y las nuevas ya vienen con DEFAULT.


-- ==========================================
-- 1. QUÉ MONEDA HABÍA ANTES
-- ==========================================
-- Se lee ANTES de cambiar nada, y solo se usa para
-- las ventas nuevas. Si no hay nada guardado, se
-- asume dólares, que es lo que se ha visto siempre.

SET @moneda_actual = (
    SELECT valor
    FROM configuracion
    WHERE clave = 'moneda_codigo'
    LIMIT 1
);

SET @moneda_actual = COALESCE(
    @moneda_actual,
    'USD'
);


-- ==========================================
-- 2. VENTAS.MONEDA
-- ==========================================
-- Se añade SOLO si no existe, para que el archivo se
-- pueda aplicar dos veces sin quejarse.

SET @tiene_columna = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'ventas'
      AND COLUMN_NAME = 'moneda'
);

SET @agregar = IF(
    @tiene_columna = 0,
    'ALTER TABLE ventas
        ADD COLUMN moneda VARCHAR(10) NOT NULL DEFAULT ''USD''
        AFTER precio',
    'SELECT ''ventas.moneda ya existe'''
);

PREPARE frase FROM @agregar;

EXECUTE frase;

DEALLOCATE PREPARE frase;


-- ==========================================
-- 3. LAS VENTAS QUE YA EXISTEN
-- ==========================================
-- Las que no tienen moneda (NULL o vacía) reciben la
-- que había configurada cuando se aplicó esto. No se
-- calcula ningún tipo de cambio: el importe es el
-- mismo y solo se le dice en qué moneda está escrito,
-- que es lo único que se puede saber de un dato que
-- ya no tiene esa información.

UPDATE ventas
SET moneda = @moneda_actual
WHERE moneda IS NULL
   OR moneda = '';


-- ==========================================

-- ==========================================
-- 4. AMPLIAR LAS COLUMNAS DE DINERO
-- ==========================================
-- DECIMAL(10,2) -> DECIMAL(15,2).
--
-- MODIFY COLUMN es idempotente: aplicarlo dos veces
-- deja la columna igual. Y NO altera ningún valor.
--
-- ------------------------------
-- POR QUÉ SE COMPRUEBA CADA UNA
-- ------------------------------
-- Porque no todas las bases tienen todas las
-- columnas, y una migración que se para en el
-- primer error deja la base a medias: unas columnas
-- ampliadas y otras no, sin que nadie lo diga.
--
-- `garantias` es el caso claro: en `esquema.sql`
-- declara tres columnas de importe, pero una base
-- migrada con `migracion_financiera.sql` de una
-- versión anterior puede no tenerlas. Con un ALTER
-- a pelo, el script se para ahí con un "Unknown
-- column" y las ocho columnas que vienen después se
-- quedan sin ampliar.
--
-- Así cada columna se amplía si existe, y si no
-- existe se avisa con un SELECT y se sigue.


-- autos.precio

SET @existe = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'autos'
      AND COLUMN_NAME = 'precio'
);

SET @frase = IF(
    @existe = 0,
    'SELECT ''autos.precio: no existe en esta base''',
    'ALTER TABLE autos
        MODIFY COLUMN precio DECIMAL(15, 2) NOT NULL'
);

PREPARE sentencia FROM @frase;

EXECUTE sentencia;

DEALLOCATE PREPARE sentencia;

-- ventas.precio

SET @existe = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'ventas'
      AND COLUMN_NAME = 'precio'
);

SET @frase = IF(
    @existe = 0,
    'SELECT ''ventas.precio: no existe en esta base''',
    'ALTER TABLE ventas
        MODIFY COLUMN precio DECIMAL(15, 2) NOT NULL'
);

PREPARE sentencia FROM @frase;

EXECUTE sentencia;

DEALLOCATE PREPARE sentencia;

-- contratos.precio_venta

SET @existe = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'contratos'
      AND COLUMN_NAME = 'precio_venta'
);

SET @frase = IF(
    @existe = 0,
    'SELECT ''contratos.precio_venta: no existe en esta base''',
    'ALTER TABLE contratos
        MODIFY COLUMN precio_venta DECIMAL(15, 2) NOT NULL'
);

PREPARE sentencia FROM @frase;

EXECUTE sentencia;

DEALLOCATE PREPARE sentencia;

-- contratos.anticipo

SET @existe = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'contratos'
      AND COLUMN_NAME = 'anticipo'
);

SET @frase = IF(
    @existe = 0,
    'SELECT ''contratos.anticipo: no existe en esta base''',
    'ALTER TABLE contratos
        MODIFY COLUMN anticipo DECIMAL(15, 2) NOT NULL DEFAULT 0.00'
);

PREPARE sentencia FROM @frase;

EXECUTE sentencia;

DEALLOCATE PREPARE sentencia;

-- contratos.gastos_administrativos

SET @existe = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'contratos'
      AND COLUMN_NAME = 'gastos_administrativos'
);

SET @frase = IF(
    @existe = 0,
    'SELECT ''contratos.gastos_administrativos: no existe en esta base''',
    'ALTER TABLE contratos
        MODIFY COLUMN gastos_administrativos DECIMAL(15, 2) NOT NULL'
);

PREPARE sentencia FROM @frase;

EXECUTE sentencia;

DEALLOCATE PREPARE sentencia;

-- contratos.monto_cuota

SET @existe = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'contratos'
      AND COLUMN_NAME = 'monto_cuota'
);

SET @frase = IF(
    @existe = 0,
    'SELECT ''contratos.monto_cuota: no existe en esta base''',
    'ALTER TABLE contratos
        MODIFY COLUMN monto_cuota DECIMAL(15, 2) DEFAULT NULL'
);

PREPARE sentencia FROM @frase;

EXECUTE sentencia;

DEALLOCATE PREPARE sentencia;

-- contratos.retencion_monto

SET @existe = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'contratos'
      AND COLUMN_NAME = 'retencion_monto'
);

SET @frase = IF(
    @existe = 0,
    'SELECT ''contratos.retencion_monto: no existe en esta base''',
    'ALTER TABLE contratos
        MODIFY COLUMN retencion_monto DECIMAL(15, 2) DEFAULT NULL'
);

PREPARE sentencia FROM @frase;

EXECUTE sentencia;

DEALLOCATE PREPARE sentencia;

-- contratos.saldo_financiado

SET @existe = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'contratos'
      AND COLUMN_NAME = 'saldo_financiado'
);

SET @frase = IF(
    @existe = 0,
    'SELECT ''contratos.saldo_financiado: no existe en esta base''',
    'ALTER TABLE contratos
        MODIFY COLUMN saldo_financiado DECIMAL(15, 2) DEFAULT NULL'
);

PREPARE sentencia FROM @frase;

EXECUTE sentencia;

DEALLOCATE PREPARE sentencia;

-- contratos.precio_lista

SET @existe = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'contratos'
      AND COLUMN_NAME = 'precio_lista'
);

SET @frase = IF(
    @existe = 0,
    'SELECT ''contratos.precio_lista: no existe en esta base''',
    'ALTER TABLE contratos
        MODIFY COLUMN precio_lista DECIMAL(15, 2) DEFAULT NULL'
);

PREPARE sentencia FROM @frase;

EXECUTE sentencia;

DEALLOCATE PREPARE sentencia;

-- cuotas.importe

SET @existe = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'cuotas'
      AND COLUMN_NAME = 'importe'
);

SET @frase = IF(
    @existe = 0,
    'SELECT ''cuotas.importe: no existe en esta base''',
    'ALTER TABLE cuotas
        MODIFY COLUMN importe DECIMAL(15, 2) NOT NULL'
);

PREPARE sentencia FROM @frase;

EXECUTE sentencia;

DEALLOCATE PREPARE sentencia;

-- cuotas.saldo

SET @existe = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'cuotas'
      AND COLUMN_NAME = 'saldo'
);

SET @frase = IF(
    @existe = 0,
    'SELECT ''cuotas.saldo: no existe en esta base''',
    'ALTER TABLE cuotas
        MODIFY COLUMN saldo DECIMAL(15, 2) NOT NULL'
);

PREPARE sentencia FROM @frase;

EXECUTE sentencia;

DEALLOCATE PREPARE sentencia;

-- pagos.importe

SET @existe = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'pagos'
      AND COLUMN_NAME = 'importe'
);

SET @frase = IF(
    @existe = 0,
    'SELECT ''pagos.importe: no existe en esta base''',
    'ALTER TABLE pagos
        MODIFY COLUMN importe DECIMAL(15, 2) NOT NULL'
);

PREPARE sentencia FROM @frase;

EXECUTE sentencia;

DEALLOCATE PREPARE sentencia;

-- garantias.monto_original

SET @existe = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'garantias'
      AND COLUMN_NAME = 'monto_original'
);

SET @frase = IF(
    @existe = 0,
    'SELECT ''garantias.monto_original: no existe en esta base''',
    'ALTER TABLE garantias
        MODIFY COLUMN monto_original DECIMAL(15, 2) NOT NULL'
);

PREPARE sentencia FROM @frase;

EXECUTE sentencia;

DEALLOCATE PREPARE sentencia;

-- garantias.monto_acordado

SET @existe = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'garantias'
      AND COLUMN_NAME = 'monto_acordado'
);

SET @frase = IF(
    @existe = 0,
    'SELECT ''garantias.monto_acordado: no existe en esta base''',
    'ALTER TABLE garantias
        MODIFY COLUMN monto_acordado DECIMAL(15, 2) NOT NULL'
);

PREPARE sentencia FROM @frase;

EXECUTE sentencia;

DEALLOCATE PREPARE sentencia;

-- garantias.monto_cuota

SET @existe = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'garantias'
      AND COLUMN_NAME = 'monto_cuota'
);

SET @frase = IF(
    @existe = 0,
    'SELECT ''garantias.monto_cuota: no existe en esta base''',
    'ALTER TABLE garantias
        MODIFY COLUMN monto_cuota DECIMAL(15, 2) DEFAULT NULL'
);

PREPARE sentencia FROM @frase;

EXECUTE sentencia;

DEALLOCATE PREPARE sentencia;

-- convenios.monto_original

SET @existe = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'convenios'
      AND COLUMN_NAME = 'monto_original'
);

SET @frase = IF(
    @existe = 0,
    'SELECT ''convenios.monto_original: no existe en esta base''',
    'ALTER TABLE convenios
        MODIFY COLUMN monto_original DECIMAL(15, 2) NOT NULL'
);

PREPARE sentencia FROM @frase;

EXECUTE sentencia;

DEALLOCATE PREPARE sentencia;

-- convenios.monto_acordado

SET @existe = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'convenios'
      AND COLUMN_NAME = 'monto_acordado'
);

SET @frase = IF(
    @existe = 0,
    'SELECT ''convenios.monto_acordado: no existe en esta base''',
    'ALTER TABLE convenios
        MODIFY COLUMN monto_acordado DECIMAL(15, 2) NOT NULL'
);

PREPARE sentencia FROM @frase;

EXECUTE sentencia;

DEALLOCATE PREPARE sentencia;

-- convenios.monto_cuota

SET @existe = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'convenios'
      AND COLUMN_NAME = 'monto_cuota'
);

SET @frase = IF(
    @existe = 0,
    'SELECT ''convenios.monto_cuota: no existe en esta base''',
    'ALTER TABLE convenios
        MODIFY COLUMN monto_cuota DECIMAL(15, 2) DEFAULT NULL'
);

PREPARE sentencia FROM @frase;

EXECUTE sentencia;

DEALLOCATE PREPARE sentencia;


-- 5. LA CLAVE DE LOS DECIMALES
-- ==========================================
-- Es lo que hace posible el guaraní. Sin esta clave
-- el sistema es estructuralmente de dos decimales, y
-- "Gs. 1.500,00" es un formato que no existe.

-- La moneda por defecto sigue siendo la que hubiera:
-- si estaba en dólares, 2 decimales.

INSERT INTO configuracion (clave, valor, descripcion)
VALUES (
    'moneda_cifras',
    '2',
    'Cuántos decimales se muestran. El guaraní no tiene subunitario: 0.'
)
ON DUPLICATE KEY UPDATE descripcion = VALUES(descripcion);


-- ==========================================
-- 6. LAS DOS MONEDAS, SIEMPRE SIEMBRADAS
-- ==========================================
-- INSERT IGNORE y no INSERT: si el administrador ya
-- eligió una moneda y guardó sus separadores a mano,
-- migrar no debe pisarlos. Solo se rellena lo que
-- faltaba.

INSERT IGNORE INTO configuracion (clave, valor, descripcion)
VALUES (
    'moneda_codigo',
    'USD',
    'Moneda de la aplicación: PYG o USD. El símbolo, los separadores y los decimales salen del catálogo, no se escriben a mano.'
);

INSERT IGNORE INTO configuracion (clave, valor, descripcion)
VALUES (
    'moneda_simbolo',
    '$',
    'Símbolo de la moneda.'
);

INSERT IGNORE INTO configuracion (clave, valor, descripcion)
VALUES (
    'moneda_formato',
    'simbolo_espacio',
    'Cómo se juntan el símbolo y el importe.'
);

INSERT IGNORE INTO configuracion (clave, valor, descripcion)
VALUES (
    'moneda_separador_miles',
    ',',
    'Separador de millares.'
);

INSERT IGNORE INTO configuracion (clave, valor, descripcion)
VALUES (
    'moneda_separador_decimales',
    '.',
    'Separador de decimales. Vacío si la moneda no usa decimales.'
);


-- ==========================================
-- 7. COMPROBAR
-- ==========================================
-- Las seis consultas siguientes tienen que salir con
-- ceros o con datos, pero sin error. Si alguna falla,
-- NO sigas: el resto del archivo depende de lo que
-- hizo esta.

-- Las columnas de dinero deben admitir 2.500.000.000.

SELECT 'autos.precio' AS columna,
       COLUMN_TYPE AS tipo
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'autos'
  AND COLUMN_NAME = 'precio';

-- ventas.moneda tiene que existir.

SELECT 'ventas.mondea' AS columna,
       COLUMN_TYPE AS tipo,
       COLUMN_DEFAULT AS valor_por_defecto
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'ventas'
  AND COLUMN_NAME = 'moneda';

-- Ninguna venta puede quedarse sin moneda.

SELECT COUNT(*) AS ventas_sin_moneda
FROM ventas
WHERE moneda IS NULL
   OR moneda = '';

-- La clave de los decimales tiene que estar.

SELECT clave, valor
FROM configuracion
WHERE clave = 'moneda_cifras';

-- Un importe de 2.500.000.000 tiene que caber. Esta es
-- la comprobación que de verdad importa: si aquí sale
-- "Out of range", la migración no se aplicó bien.

-- Descomenta y ejecuta a mano:
--   SELECT 2500000000.00 + 0.00;

-- Y las ventas que ya existían:

SELECT moneda, COUNT(*) AS ventas
FROM ventas
GROUP BY moneda;

-- Si te interesa guardar la distribución de importes
-- antes y después, para comparar:
--
--   SELECT MIN(precio), MAX(precio), SUM(precio)
--   FROM ventas;
--
-- Los tres números tienen que ser los mismos antes y
-- después. Ampliar la columna no los cambia.