-- ============================================================
-- MIGRACIÓN: MÓDULO DE CONTRATOS
-- ============================================================
-- Para bases de datos YA existentes.
--
-- Para una instalación nueva no hace falta:
-- database/esquema.sql ya incluye todo esto.
--
-- Cómo aplicarla
-- --------------
--   MySQL Workbench:
--     File > Open SQL Script > este archivo > flecha
--
--   Consola:
--     mysql -u root -p concesionario < database/migracion_contratos.sql
--
-- Es NO DESTRUCTIVA:
--   - no borra ni modifica filas existentes
--   - añade una columna opcional a clientes
--   - añade una tabla nueva
-- Se puede ejecutar más de una vez: los
-- CREATE y el ALTER comprueban si ya existen.
--
-- DESPUÉS DE APLICARLA, la base tendrá 8
-- tablas. Puedes comprobarlo con:
--   SHOW TABLES;
-- ============================================================


-- ------------------------------------------------------------
-- 1. Documento del cliente
-- ------------------------------------------------------------
-- Lo necesita el contrato de compraventa. Es
-- opcional: los clientes que ya existen se
-- quedan con NULL y el PDF muestra "No
-- registrado" hasta que se rellene.

ALTER TABLE clientes
    ADD COLUMN documento VARCHAR(50) DEFAULT NULL
    AFTER email;


-- ------------------------------------------------------------
-- 2. Tabla de contratos
-- ------------------------------------------------------------
-- Un contrato por venta (uq_contratos_venta).
-- El número se arma con el año y el id del
-- propio contrato: único por construcción.

CREATE TABLE IF NOT EXISTS contratos (

    id INT NOT NULL AUTO_INCREMENT,

    numero VARCHAR(30) DEFAULT NULL,

    venta_id INT NOT NULL,

    cliente_id INT NOT NULL,

    auto_id INT NOT NULL,

    usuario_id INT DEFAULT NULL,

    fecha DATE NOT NULL,

    precio_venta DECIMAL(10, 2) NOT NULL,

    forma_pago VARCHAR(40) NOT NULL
        DEFAULT 'Contado',

    anticipo DECIMAL(10, 2) NOT NULL DEFAULT 0.00,

    cantidad_cuotas INT NOT NULL DEFAULT 0,

    observaciones TEXT DEFAULT NULL,

    estado VARCHAR(20) NOT NULL DEFAULT 'borrador',

    archivo_pdf VARCHAR(255) DEFAULT NULL,

    fecha_creacion DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE KEY uq_contratos_numero (numero),

    UNIQUE KEY uq_contratos_venta (venta_id),

    KEY ix_contratos_cliente (cliente_id),

    KEY ix_contratos_auto (auto_id),

    KEY ix_contratos_usuario (usuario_id),

    KEY ix_contratos_estado (estado),

    CONSTRAINT contratos_venta_fk
        FOREIGN KEY (venta_id)
        REFERENCES ventas (id)
        ON DELETE RESTRICT,

    CONSTRAINT contratos_cliente_fk
        FOREIGN KEY (cliente_id)
        REFERENCES clientes (id)
        ON DELETE RESTRICT,

    CONSTRAINT contratos_auto_fk
        FOREIGN KEY (auto_id)
        REFERENCES autos (id)
        ON DELETE RESTRICT,

    CONSTRAINT contratos_usuario_fk
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios (id)
        ON DELETE SET NULL

);


-- ============================================================
-- COMPROBACIÓN
-- ============================================================
-- Lo siguiente debería mostrar 8 tablas y la
-- columna "documento" en clientes.
--
--   SHOW TABLES;
--   DESCRIBE clientes;
-- ============================================================
