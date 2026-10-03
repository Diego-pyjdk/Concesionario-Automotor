-- ============================================================
-- MIGRACIÓN: PAGOS DE LAS VENTAS
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
--     mysql -u root -p concesionario < database/migracion_pagos.sql
--
-- Es NO DESTRUCTIVA: solo crea una tabla nueva. No
-- toca ninguna fila de las que ya tienes.
-- ============================================================


-- ------------------------------------------------------------
-- La tabla
-- ------------------------------------------------------------
-- Cada entrada de dinero de una venta.
--
-- ON DELETE RESTRICT sobre ventas: si ya se cobró
-- algo, la venta no se puede anular en silencio.
-- Habría que deshacer antes el pago.
--
-- "importe" no tiene restricción de positividad en
-- la base, pero la aplicación no deja guardar uno
-- menor o igual a cero: un importe negativo no es un
-- pago, es un reembolso, y para eso hay que
-- registrarlo de otra forma.
--
-- "usuario_nombre" es una copia del nombre del
-- usuario, igual que en ventas y auditoria: si se
-- borra la cuenta, queda NULL en usuario_id pero
-- el nombre se conserva.

CREATE TABLE pagos (

    id INT NOT NULL AUTO_INCREMENT,

    venta_id INT NOT NULL,

    contrato_id INT DEFAULT NULL,

    fecha DATE NOT NULL,

    importe DECIMAL(10, 2) NOT NULL,

    forma VARCHAR(40) NOT NULL,

    referencia VARCHAR(100) DEFAULT NULL,

    concepto VARCHAR(255) DEFAULT NULL,

    usuario_id INT DEFAULT NULL,

    usuario_nombre VARCHAR(50) DEFAULT NULL,

    fecha_registro DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    KEY ix_pagos_venta (venta_id),

    KEY ix_pagos_fecha (fecha),

    CONSTRAINT pagos_venta_fk
        FOREIGN KEY (venta_id)
        REFERENCES ventas (id)
        ON DELETE RESTRICT,

    CONSTRAINT pagos_contrato_fk
        FOREIGN KEY (contrato_id)
        REFERENCES contratos (id)
        ON DELETE RESTRICT,

    CONSTRAINT pagos_usuario_fk
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios (id)
        ON DELETE SET NULL

);


-- ============================================================
-- QUÉ PASA CON LAS VENTAS QUE YA TENÍAS
-- ============================================================
-- Ninguna. Se quedan con saldo pendiente de
-- cobrar, que es lo correcto: hasta que se
-- registre un pago, no conste ninguno.
--
-- Si son ventas ya cobradas y quieres que salgan a
-- saldadas, registra el pago una vez por venta
-- desde la aplicación, no a mano con UPDATE: así
-- queda en el rastro quién lo registró y cuándo.
--
-- ============================================================
-- COMPROBACIÓN
-- ============================================================
--
--   SHOW TABLES LIKE 'pagos';
--   SHOW INDEX FROM pagos;
--
-- Si da error 1822 al crear la tabla, es que ya
-- existe una relación con ese nombre: quítala
-- antes.
-- ============================================================