CREATE DATABASE IF NOT EXISTS concesionario;

USE concesionario;


-- ============================================
-- TABLA: MARCAS
-- ============================================

CREATE TABLE IF NOT EXISTS marcas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL
);


-- ============================================
-- TABLA: AUTOS
-- ============================================

CREATE TABLE IF NOT EXISTS autos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    marca_id INT NOT NULL,
    modelo VARCHAR(100) NOT NULL,
    anio INT NOT NULL,
    precio DECIMAL(10,2) NOT NULL,
    color VARCHAR(50),
    stock INT NOT NULL DEFAULT 0,

    FOREIGN KEY (marca_id)
        REFERENCES marcas(id)
);