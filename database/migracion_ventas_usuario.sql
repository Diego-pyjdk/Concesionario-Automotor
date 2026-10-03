-- ============================================================
-- MIGRACIÓN: QUIÉN REGISTRÓ CADA VENTA
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
--     mysql -u root -p concesionario < database/migracion_ventas_usuario.sql
--
-- Es NO DESTRUCTIVA: solo añade dos columnas y un
-- índice. No toca ninguna fila.
-- ============================================================


-- ------------------------------------------------------------
-- 1. Las dos columnas
-- ------------------------------------------------------------
-- usuario_id es la clave foranea: si borras la
-- cuenta del vendedor, se queda a NULL.
--
-- usuario_nombre es una COPIA del nombre, por lo
-- mismo que hace auditoria. Sin ella, borrar la
-- cuenta perdería el dato de quién vendió cada
-- vehículo, y las ventas anteriores a esta
-- migración se quedarían sin vendedor conocido.

ALTER TABLE ventas
    ADD COLUMN usuario_id INT NULL AFTER auto_id;

ALTER TABLE ventas
    ADD COLUMN usuario_nombre VARCHAR(50) NULL
        AFTER usuario_id;


-- ------------------------------------------------------------
-- 2. Índice para el reporte de ventas por vendedor
-- ------------------------------------------------------------

ALTER TABLE ventas
    ADD INDEX ix_ventas_usuario (usuario_id);


-- ------------------------------------------------------------
-- 3. La clave foránea, con SET NULL
-- ------------------------------------------------------------
-- SET NULL y no CASCADE: borrar una cuenta de
-- usuario no puede borrar ventas. Son dos cosas
-- distintas.

ALTER TABLE ventas
    ADD CONSTRAINT ventas_usuario_fk
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios (id)
        ON DELETE SET NULL;


-- ============================================================
-- QUÉ PASA CON LAS VENTAS QUE YA TENÍAS
-- ============================================================
-- Se quedan con usuario_id NULL y usuario_nombre NULL.
--
-- No se inventan datos: no hay forma de saber
-- quién registró cada venta anterior. El listado
-- y los reportes mostrarán "Sin registrar" para
-- esas filas, y solo las ventas nuevas guardan
-- el nombre del vendedor.
--
-- Si necesitas conservar el nombre de las
-- anteriores, actualiza a mano:
--
--     UPDATE ventas
--     SET usuario_id = 1,
--         usuario_nombre = 'admin'
--     WHERE usuario_id IS NULL;
--
-- ============================================================
-- COMPROBACIÓN
-- ============================================================
-- Lo siguiente debería mostrar usuario_id,
-- usuario_nombre, el índice ix_ventas_usuario y
-- la restricción ventas_usuario_fk:
--
--   DESCRIBE ventas;
--   SHOW INDEX FROM ventas;
--
-- Si aparece un error 1822 al añadir la clave
-- foránea, es que ya existe una relación con ese
-- nombre: quítala antes.
-- ============================================================