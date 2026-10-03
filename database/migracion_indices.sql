-- ============================================================
-- MIGRACIÓN: ÍNDICES Y RESTRICCIÓN DE MARCAS
-- ============================================================
-- Para bases de datos YA existentes.
--
-- Para una instalación nueva no hace falta:
-- database/esquema.sql ya incluye esto.
--
-- Cómo aplicarla
-- --------------
--   MySQL Workbench:
--     File > Open SQL Script > este archivo > flecha
--
--   Consola:
--     mysql -u root -p concesionario < database/migracion_indices.sql
--
-- Es NO DESTRUCTIVA: solo añade índices y una
-- restricción de unicidad. No toca ninguna fila.
-- ============================================================


-- ------------------------------------------------------------
-- 1. Índice en ventas.fecha
-- ------------------------------------------------------------
-- Los reportes filtran por rango de fechas y el
-- panel busca las ventas de HOY:
--
--     WHERE ventas.fecha >= %s
--     WHERE fecha = CURDATE()
--
-- Sin índice, MySQL recorre la tabla entera en
-- cada consulta. Con unos miles de ventas se
-- nota; con decenas de miles, molesta.

ALTER TABLE ventas
    ADD INDEX ix_ventas_fecha (fecha);


-- ------------------------------------------------------------
-- 2. Índice en contratos.fecha
-- ------------------------------------------------------------
-- El listado de contratos ordena por fecha y el
-- detalle la muestra.

ALTER TABLE contratos
    ADD INDEX ix_contratos_fecha (fecha);


-- ------------------------------------------------------------
-- 3. marcas.nombre no puede repetirse
-- ------------------------------------------------------------
-- Antes se podían dar de alta "BMW", "bmw" y
-- "Bmw" como tres marcas distintas: el mismo
-- vehículo aparecía escrito de tres formas.
--
-- ANTES de aplicar esto, mira si ya hay
-- duplicados, porque el UNIQUE los rechazará:
--
--     SELECT nombre, COUNT(*) c
--     FROM marcas
--     GROUP BY LOWER(TRIM(nombre))
--     HAVING c > 1;
--
-- Si la consulta no devuelve nada, puedes
-- seguir. Si devuelve algo,Borras o fusionas
-- primero las repetidas desde la aplicación.

ALTER TABLE marcas
    ADD CONSTRAINT uq_marcas_nombre UNIQUE (nombre);


-- ============================================================
-- COMPROBACIÓN
-- ============================================================
-- Lo siguiente debería mostrar un índice
-- "ix_ventas_fecha" en ventas y la restricción
-- "uq_marcas_nombre" en marcas:
--
--   SHOW INDEX FROM ventas;
--   SHOW INDEX FROM marcas;
-- ============================================================