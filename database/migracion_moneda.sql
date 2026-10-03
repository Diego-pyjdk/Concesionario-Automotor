-- ============================================================
-- MIGRACIÓN: MONEDA CONFIGURABLE
-- ============================================================
-- Para bases de datos YA existentes.
--
-- Para una instalación nueva no hace falta:
-- database/esquema.sql ya siembra estos valores.
--
-- Cómo aplicarla
-- --------------
--   MySQL Workbench:
--     File > Open SQL Script > este archivo > flecha
--
--   Consola:
--     mysql -u root -p concesionario <
--       database/migracion_moneda.sql
--
-- Es NO DESTRUCTIVA: solo añade cinco claves de
-- configuración. No toca ninguna otra fila ni
-- ninguna tabla.
-- ============================================================


-- ------------------------------------------------------------
-- Las cinco claves
-- ------------------------------------------------------------
-- Estos valores son los que reproducian
-- exactamente el "$ " que estaba escrito dentro
-- del código, así que migrar no cambia un solo
-- importe de los que se ven.
--
-- INSERT IGNORE y no INSERT: si la clave ya
-- existe (porque el administrador ya cambió la
-- moneda desde Configuración), no se pisa con el
-- valor por defecto. Perder la configuración que
-- alguien ya ajustó sería peor que no migrar.
--
-- Para cambiar la moneda de verdad está
-- Configuración, que además la aplica sin
-- reiniciar.

INSERT IGNORE INTO configuracion
    (clave, valor, descripcion) VALUES

    ('moneda_codigo',
     'USD',
     'Código de la moneda (USD, EUR, MXN...). Se muestra en los formatos que usan código en vez de símbolo.'),

    ('moneda_simbolo',
     '$',
     'Símbolo de la moneda, como $ o €.'),

    ('moneda_formato',
     'simbolo_espacio',
     'Cómo se juntan el símbolo y el importe: simbolo_espacio, simbolo_pegado, simbolo_despues, codigo_espacio, codigo_pegado o codigo_despues.'),

    ('moneda_separador_miles',
     ',',
     'Separador de millares. Con ''.'' son 1.500,00.'),

    ('moneda_separador_decimales',
     '.',
     'Separador de decimales. Con '','' son 1.500,00.');


-- ============================================================
-- QUÉ PASA SI NO LA APLICAS
-- ============================================================
-- Nada. La aplicación lee estos ajustes y, si no
-- están, usa los mismos valores por defecto.
--
-- Se recomienda aplicarla de todos modos para
-- que la base sea igual que una recién instalada
-- y los valores se vean y se cambien desde
-- Configuración.
--
-- ============================================================
-- COMPROBACIÓN
-- ============================================================
-- Debe devolver cinco filas:
--
--     SELECT clave, valor
--     FROM configuracion
--     WHERE clave LIKE 'moneda%'
--     ORDER BY clave;
--
-- ============================================================