-- ============================================================
-- MIGRACIÓN: VALOR ANTERIOR Y VALOR NUEVO EN LA AUDITORÍA
-- ============================================================
-- Para bases de datos YA existentes.
--
-- Para una instalación nueva NO hace falta:
-- database/esquema.sql ya trae estas columnas.
--
-- Cómo aplicarla
-- --------------
--   MySQL Workbench:
--     File > Open SQL Script > este archivo > flecha
--
--   Consola:
--     mysql -u root -p concesionario <
--       database/migracion_auditoria_cambios.sql
--
--
-- ES NO DESTRUCTIVA
-- -----------------
-- Las tres columnas nuevas son NULL para toda la
-- fila que ya exista: la auditoría antigua se queda
-- como está. No se inventa ningún valor anterior
-- para algo que pasó hace meses, porque no se sabe
-- cuál era.
--
-- Solo las filas nuevas los llevan, y los lleva
-- database/auditoria.py: registrar_cambio(), que es
-- registrar_accion() con los valores de antes y
-- después.
-- ============================================================


-- ------------------------------------------------------------
-- 1. Las tres columnas
-- ------------------------------------------------------------
-- Sin NOT NULL DEFAULT: una fila de auditoría que no
-- tiene valor anterior debe decirlo con NULL, no con
-- la cadena vacía, que parecería un valor anterior que
-- era "".

ALTER TABLE auditoria

    -- Qué había antes de la modificación.

    ADD COLUMN valor_anterior VARCHAR(255)
        DEFAULT NULL AFTER descripcion,

    -- Qué hay ahora.

    ADD COLUMN valor_nuevo VARCHAR(255)
        DEFAULT NULL AFTER valor_anterior,

    -- Recibo, número de cuota, número de contrato: lo
    -- que permite encontrar en la tabla lo que cambió
    -- sin tener que buscar por texto dentro de la
    -- descripción.

    ADD COLUMN referencia VARCHAR(255)
        DEFAULT NULL AFTER valor_nuevo;


-- ------------------------------------------------------------
-- 2. Índices
-- ------------------------------------------------------------
-- Buscar "todos los cambios de este contrato" o
-- "todos los de este recibo": sin índice, la búsqueda
-- de un historial es un recorrido completo por toda
-- la tabla, y la tabla de auditoría es la que más
-- crece sin que nadie se dé cuenta.

CREATE INDEX ix_auditoria_referencia
    ON auditoria (referencia);

-- Y filtrar por tipo de acción junto con la fecha:
-- quien mira el historial de una cuota quiere ver
-- pagos y anulaciones, no los accesos al sistema.

-- Si ya existe un indice llamado
-- ix_auditoria_accion de SOLO una columna, MySQL
-- avisa del nombre duplicado y esta sentencia no se
-- aplica. No es un fallo grave (lo que se busca ya
-- tiene indice), pero conviene saberlo:
--
--   SHOW INDEX FROM auditoria
--    WHERE Key_name = 'ix_auditoria_accion';
--
-- Para dejarlo como esta migracion propone, con el
-- nombre libre:
--
--   ALTER TABLE auditoria
--    DROP INDEX ix_auditoria_accion;
--
--   CREATE INDEX ix_auditoria_accion_fecha
--    ON auditoria (accion, fecha_hora);
--
-- Es opcional: buscar por accion ya funciona.

CREATE INDEX ix_auditoria_accion_fecha
    ON auditoria (accion, fecha_hora);


-- ============================================================
-- COMPROBACIÓN
-- ============================================================
-- Las tres columnas:
--
--   SHOW COLUMNS FROM auditoria
--    LIKE 'valor_anterior';
--
-- Los índices:
--
--   SHOW INDEX FROM auditoria
--    WHERE Key_name LIKE 'ix_auditoria%';
--
-- Las filas antiguas siguen intactas, con las tres
-- columnas a NULL:
--
--   SELECT COUNT(*)
--   FROM auditoria
--   WHERE valor_anterior IS NULL;
--
-- ============================================================
--
-- NOTA
-- ============================================================
-- Desde que el módulo de financiación existe, la
-- aplicación escribe estas columnas. Las entradas de
-- auditoría anteriores a esta migración las tendrán a
-- NULL, y eso es lo correcto: nadie puede saber a
-- esta distancia cuál era el valor de antes.
--
-- La vista de auditoría enseña "(sin dato)" donde no
-- las hay, en vez de una celda vacía, para que se
-- distinga "no se registró" de "se registró vacío".
--
-- ============================================================
