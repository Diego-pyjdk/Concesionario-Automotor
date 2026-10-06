-- Actualización aditiva para la versión enviada en concesionario (2).zip.
-- Hacer una copia de seguridad antes. No borra tablas ni registros.
USE concesionario;

CREATE TABLE IF NOT EXISTS auto_fichas (
    auto_id INT NOT NULL PRIMARY KEY,
    combustible VARCHAR(40) NOT NULL DEFAULT '',
    transmision VARCHAR(40) NOT NULL DEFAULT '',
    observaciones TEXT,
    FOREIGN KEY (auto_id) REFERENCES autos(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS auto_fotos (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    auto_id INT NOT NULL,
    contenido MEDIUMBLOB NOT NULL,
    nombre VARCHAR(255) NOT NULL,
    creado DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_fotos_auto (auto_id),
    FOREIGN KEY (auto_id) REFERENCES autos(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS unidades_vehiculo (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    auto_id INT NOT NULL,
    vin VARCHAR(40) NOT NULL UNIQUE,
    matricula VARCHAR(30) DEFAULT NULL,
    kilometraje INT NOT NULL DEFAULT 0,
    estado ENUM('disponible','reservado','taller') NOT NULL DEFAULT 'disponible',
    observaciones TEXT,
    INDEX ix_unidades_auto_estado (auto_id, estado),
    FOREIGN KEY (auto_id) REFERENCES autos(id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS venta_unidades (
    venta_id INT NOT NULL PRIMARY KEY,
    unidad_id INT NOT NULL UNIQUE,
    FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE CASCADE,
    FOREIGN KEY (unidad_id) REFERENCES unidades_vehiculo(id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS seguimiento_cobranza (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    contrato_id INT NOT NULL,
    usuario_id INT DEFAULT NULL,
    usuario_nombre VARCHAR(100) NOT NULL,
    fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    canal ENUM('llamada','whatsapp','presencial','otro') NOT NULL DEFAULT 'llamada',
    notas TEXT NOT NULL,
    proximo_contacto DATE DEFAULT NULL,
    promesa_fecha DATE DEFAULT NULL,
    promesa_importe DECIMAL(15,2) DEFAULT NULL,
    completado BOOLEAN NOT NULL DEFAULT FALSE,
    INDEX ix_seguimiento_agenda (completado, proximo_contacto),
    INDEX ix_seguimiento_contrato (contrato_id, fecha),
    FOREIGN KEY (contrato_id) REFERENCES contratos(id) ON DELETE CASCADE,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB;
