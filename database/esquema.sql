-- ==========================================
-- CONCESIONARIO - ESQUEMA DE BASE DE DATOS
-- ==========================================
--
-- Levantar el proyecto desde cero:
--
--   mysql -u root -p < database/esquema.sql
--
-- Desde MySQL Workbench:
--   File > Open SQL Script > database/esquema.sql
--
-- ADVERTENCIA:
--   El DROP DATABASE borra todos los datos
--   existentes de la base "concesionario".
--   Si solo quieres crear lo que falta, quita
--   las dos sentencias DROP y usa
--   "CREATE TABLE IF NOT EXISTS".
--
-- ==========================================


-- ==========================================
-- BASE DE DATOS
-- ==========================================

DROP DATABASE IF EXISTS concesionario;

CREATE DATABASE concesionario
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

USE concesionario;


-- ==========================================
-- MARCAS
-- ==========================================
-- Tabla de consulta. Un vehículo siempre
-- pertenece a una marca (1:N).
-- ==========================================

CREATE TABLE marcas (

    id INT NOT NULL AUTO_INCREMENT,

    nombre VARCHAR(50) NOT NULL,

    PRIMARY KEY (id),

    -- Sin esto se pueden dar de alta "BMW",
    -- "bmw" y "Bmw" como tres marcas distintas
    -- y el mismo vehiculo aparece con nombres
    -- diferentes en cada pantalla.
    UNIQUE KEY uq_marcas_nombre (nombre)

);


-- ==========================================
-- AUTOS
-- ==========================================
-- Pertenece a una marca (N:1).
-- "stock" es la cantidad de unidades
-- disponibles; se reduce en cada venta.
-- ==========================================

CREATE TABLE autos (

    id INT NOT NULL AUTO_INCREMENT,

    marca_id INT NOT NULL,

    modelo VARCHAR(100) NOT NULL,

    anio INT NOT NULL,

    precio DECIMAL(10, 2) NOT NULL,

    color VARCHAR(50) DEFAULT NULL,

    stock INT NOT NULL DEFAULT 0,

    PRIMARY KEY (id),

    CONSTRAINT autos_marca_fk
        FOREIGN KEY (marca_id)
        REFERENCES marcas (id)

);


-- ==========================================
-- CLIENTES
-- ==========================================
-- Un cliente puede tener muchas ventas (1:N).
-- ==========================================

CREATE TABLE clientes (

    id INT NOT NULL AUTO_INCREMENT,

    nombre VARCHAR(50) NOT NULL,

    apellido VARCHAR(50) NOT NULL,

    telefono VARCHAR(20) DEFAULT NULL,

    email VARCHAR(100) DEFAULT NULL,

    documento VARCHAR(50) DEFAULT NULL,

    PRIMARY KEY (id)

);


-- ==========================================
-- USUARIOS
-- ==========================================
-- Acceso al sistema.
--
-- "password_hash" guarda sal y hash separados
-- por dos puntos, en hexadecimal. NUNCA la
-- contraseña: no es recuperable, solo se
-- puede comprobar.
--
-- "rol" es 'administrador' o 'vendedor'.
-- "activo" = 0 deja la cuenta sin acceso sin
-- borrarla.
--
-- Los dos últimos campos son para el bloqueo
-- por intentos fallidos de login.
--
-- El primer administrador se crea con:
--   venv\Scripts\python.exe crear_admin.py
-- ==========================================

CREATE TABLE usuarios (

    id INT NOT NULL AUTO_INCREMENT,

    nombre_usuario VARCHAR(50) NOT NULL,

    nombre_completo VARCHAR(120) NOT NULL,

    password_hash VARCHAR(255) NOT NULL,

    rol VARCHAR(20) NOT NULL DEFAULT 'vendedor',

    activo TINYINT(1) NOT NULL DEFAULT 1,

    fecha_creacion DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    ultimo_acceso DATETIME DEFAULT NULL,

    intentos_fallidos INT NOT NULL DEFAULT 0,

    bloqueado_hasta DATETIME DEFAULT NULL,

    PRIMARY KEY (id),

    UNIQUE KEY uq_usuarios_nombre (nombre_usuario)

);


-- ==========================================
-- VENTAS
-- ==========================================
-- Une cliente y vehículo (1:N con ambos).
-- "precio" guarda el valor de la venta en el
-- momento de realizarla, para que un cambio
-- posterior en autos.precio no altere el
-- histórico.
-- ==========================================

CREATE TABLE ventas (

    id INT NOT NULL AUTO_INCREMENT,

    cliente_id INT NOT NULL,

    auto_id INT NOT NULL,

    usuario_id INT NULL,

    -- Copia del nombre, igual que en auditoria.
    -- Borrar la cuenta de un vendedor pone
    -- usuario_id a NULL, pero el nombre se queda:
    -- si no, perderias el dato de quien hizo la
    -- venta.
    usuario_nombre VARCHAR(50) NULL,

    fecha DATE NOT NULL,

    precio DECIMAL(10, 2) NOT NULL,

    PRIMARY KEY (id),

    -- Los reportes filtran por rango de fechas
    -- y el resumen del panel busca las ventas de
    -- HOY. Sin este indice, cada reporte es un
    -- recorrido completo de la tabla y se nota
    -- a partir de unos miles de ventas.
    KEY ix_ventas_fecha (fecha),

    -- Para el reporte de ventas por vendedor.
    KEY ix_ventas_usuario (usuario_id),

    CONSTRAINT ventas_cliente_fk
        FOREIGN KEY (cliente_id)
        REFERENCES clientes (id),

    CONSTRAINT ventas_auto_fk
        FOREIGN KEY (auto_id)
        REFERENCES autos (id),

    -- SET NULL y no CASCADE: borrar la cuenta de
    -- un vendedor no puede borrar sus ventas. El
    -- nombre copiado mas arriba se queda, asi que
    -- el historico sigue diciendo quien vendio
    -- cada vehiculo aunque la cuenta desaparezca.

    CONSTRAINT ventas_usuario_fk
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios (id)
        ON DELETE SET NULL

);


-- ==========================================
-- CONFIGURACIÓN
-- ==========================================
-- Ajustes del sistema en clave/valor.
--
-- "stock_minimo" es el umbral por debajo del
-- cual un vehículo aparece como stock bajo en el
-- panel principal.
--
-- Cualquier cambio aquí queda registrado en
-- la tabla auditoria.
-- ==========================================

CREATE TABLE configuracion (

    clave VARCHAR(50) NOT NULL,

    valor VARCHAR(255) NOT NULL,

    descripcion VARCHAR(255) DEFAULT NULL,

    PRIMARY KEY (clave)

);


-- ==========================================
-- AUDITORÍA
-- ==========================================
-- Rastro de las acciones importantes.
--
-- Se guardan DOS cosas del usuario a propósito:
--
--   usuario_id     referencia al usuario. Con
--                  ON DELETE SET NULL, si se
--                  borra la cuenta, el registro
--                  sobrevive.
--   usuario_nombre copia del nombre en el
--                  momento de la acción, para que
--                  el rastro siga siendo legible
--                  aunque la cuenta ya no exista.
--
-- "accion" es un código corto y estable; el
-- texto legible sale de ACCIONES en
-- database/auditoria.py.
-- ==========================================

CREATE TABLE auditoria (

    id BIGINT NOT NULL AUTO_INCREMENT,

    usuario_id INT DEFAULT NULL,

    usuario_nombre VARCHAR(50) DEFAULT NULL,

    accion VARCHAR(30) NOT NULL,

    modulo VARCHAR(30) NOT NULL,

    descripcion VARCHAR(255) DEFAULT NULL,

    fecha_hora DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    KEY ix_auditoria_fecha (fecha_hora),

    KEY ix_auditoria_accion (accion),

    KEY ix_auditoria_modulo (modulo),

    KEY ix_auditoria_usuario (usuario_id),

    CONSTRAINT auditoria_usuario_fk
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios (id)
        ON DELETE SET NULL
);


-- ==========================================
-- CONTRATOS DE COMPRAVENTA
-- ==========================================
-- Un contrato por venta. Se genera después de
-- cerrar la venta.
--
-- El número (CTR-2026-00001) se forma con el
-- año y el id del propio contrato, así que es
-- único por construcción y no depende de
-- contar filas.
--
-- "venta_id" es UNIQUE: impide crear dos
-- contratos vivos para la misma venta. Si hace
-- falta rehacerlo, se cancela el anterior (un
-- contrato cancelado no surte efecto) y se crea
-- uno nuevo.
--
-- Las cuatro relaciones van en RESTRICT salvo
-- el usuario, que se anula a NULL si se borra
-- la cuenta: el contrato tiene que sobrevivir
-- al vendedor.
--
-- "cantidad_cuotas" queda guardado por si más
-- adelante se quiere un módulo de financiación;
-- hoy solo se usa para calcular el importe de
-- la cuota al mostrar el contrato.
-- ==========================================

CREATE TABLE contratos (

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


-- ==========================================
-- PAGOS
-- ==========================================
-- Cada entrada de dinero que entra por una venta.
--
-- Un contrato dice QUÉ se debe pagar; esta tabla
-- dice QUÉ se ha pagado. Son cosas distintas y
-- no se mezclan: el contrato se firma una vez,
-- los pagos se registran uno a uno.
--
-- "importe" siempre positivo: un pago que
-- devuelve dinero no es un pago negativo, es otro
-- movimiento, y así el saldo nunca se explica por
-- una resta rara.
--
-- "contrato_id" es opcional: una venta en
-- efectivo puede cobrarse sin llegar a firmar
-- contrato. Cuando hay contrato, se guarda el
-- suyo para poder consultarlo sin tener que
-- buscarlo.
--
-- usuario_nombre es una copia, como en ventas y
-- auditoria: borrar la cuenta no borra quién
-- cobró.
-- ==========================================

CREATE TABLE pagos (

    id INT NOT NULL AUTO_INCREMENT,

    venta_id INT NOT NULL,

    contrato_id INT DEFAULT NULL,

    fecha DATE NOT NULL,

    importe DECIMAL(10, 2) NOT NULL,

    forma VARCHAR(40) NOT NULL,

    -- Número de operación, cheque, etc. Lo que
    -- haga falta para localizar el movimiento
    -- en un extracto bancario.

    referencia VARCHAR(100) DEFAULT NULL,

    concepto VARCHAR(255) DEFAULT NULL,

    usuario_id INT DEFAULT NULL,

    usuario_nombre VARCHAR(50) DEFAULT NULL,

    fecha_registro DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    -- El saldo de una venta se calcula sumando sus
    -- pagos: sin índice, cada consulta es un
    -- recorrido completo.

    KEY ix_pagos_venta (venta_id),

    -- Para el reporte de cobros por periodo.

    KEY ix_pagos_fecha (fecha),

    -- ON DELETE RESTRICT, no CASCADE: si ya se
    -- cobró algo, la venta ya no se puede anular
    -- en silencio. Habría que deshacer antes el
    -- pago, que es justo lo que no se quiere.

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


-- ==========================================
-- DATOS INICIALES
-- ==========================================
-- Sin marcas no se puede crear un vehículo:
-- el ComboBox del formulario quedaría vacío.
--
-- No se siembran usuarios a propósito: una
-- contraseña por defecto en el repositorio
-- sería una puerta abierta. El primer
-- administrador se crea con crear_admin.py.
-- ==========================================

INSERT INTO marcas (nombre) VALUES
    ('Toyota'),
    ('Ford'),
    ('Chevrolet'),
    ('Volkswagen'),
    ('Hyundai'),
    ('Kia'),
    ('Nissan'),
    ('Honda'),
    ('BMW'),
    ('Audi');

INSERT INTO configuracion (clave, valor, descripcion) VALUES
    ('stock_minimo',
     '3',
     'Un vehículo con stock menor o igual a este valor aparece como stock bajo.');

-- Moneda.
--
-- Estos valores reproducen exactamente lo que
-- mostraba la aplicación cuando el "$ " estaba
-- escrito dentro del código: "USD", "$",
-- "simbolo_espacio", "," y ".". Por eso
-- instalar desde cero no cambia ni un importe de
-- los que se ven.
--
-- Cambiarlos aquí es solo el valor inicial: se
-- cambian de verdad desde Configuración, que
-- además los aplica sin reiniciar.

INSERT INTO configuracion (clave, valor, descripcion) VALUES
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
