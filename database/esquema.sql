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
-- DATOS INICIALES
-- ==========================================
-- Sin marcas no se puede crear un vehículo:
-- el ComboBox del formulario quedaría vacío.
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
