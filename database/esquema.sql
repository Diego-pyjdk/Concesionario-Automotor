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

    PRIMARY KEY (id)

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

    PRIMARY KEY (id)

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

    fecha DATE NOT NULL,

    precio DECIMAL(10, 2) NOT NULL,

    PRIMARY KEY (id),

    CONSTRAINT ventas_cliente_fk
        FOREIGN KEY (cliente_id)
        REFERENCES clientes (id),

    CONSTRAINT ventas_auto_fk
        FOREIGN KEY (auto_id)
        REFERENCES autos (id)

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
