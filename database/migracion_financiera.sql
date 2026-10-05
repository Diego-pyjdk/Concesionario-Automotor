-- ============================================================
-- MIGRACIÓN: FINANCIACIÓN, CUOTAS Y GARANTÍAS
-- ============================================================
-- Para bases de datos YA existentes con ventas y
-- contratos.
--
-- Para una instalación nueva NO hace falta: este
-- contenido ya está en database/esquema.sql.
--
-- Cómo aplicarla
-- --------------
--   MySQL Workbench:
--     File > Open SQL Script > este archivo > flecha
--
--   Consola:
--     mysql -u root -p concesionario <
--       database/migracion_financiera.sql
--
--
-- ES NO DESTRUCTIVA
-- -----------------
--   - No borra ninguna fila.
--   - No actualiza ninguna fila existente.
--   - Las columnas nuevas de contratos y pagos son
--     NULL o con valor por defecto, así que las
--     filas que ya existen siguen siendo válidas.
--   - Los contratos ya firmados NO se tocan: sus
--     pagos siguen siendo los de siempre.
--
-- Los contratos que ya existían no tienen
-- cronograma. Se les puede generar después desde
-- la pantalla de Cartera, que solo lo ofrece si no
-- hay ni un céntimo cobrado: un contrato con pagos
-- ya hechos no puede recalcular sus cuotas sin
-- dejar de cuadrar con el dinero cobrado.
-- ============================================================


-- ------------------------------------------------------------
-- 1. CONTRATOS: las condiciones económicas, congeladas
-- ------------------------------------------------------------
-- "precio_venta" y "anticipo" ya estaban. Lo que se
-- añade es lo que hace falta para que un contrato
-- firmado se pueda leer y auditar sin recalcular nada.

ALTER TABLE contratos

    -- Lo que se financia de verdad: precio menos
    -- entrega inicial. Se guarda en vez de calcularse
    -- porque es una condición PACTADA: si algún día
    -- alguien toca un valor de arriba, el contrato ya
    -- firmado tiene que seguir diciendo lo que decía.

    ADD COLUMN saldo_financiado DECIMAL(10, 2)
        NOT NULL DEFAULT 0.00 AFTER anticipo,

    -- Tasa en porcentaje anual. 0 es una venta sin
    -- interés, que también es válida.

    ADD COLUMN tasa_interes DECIMAL(6, 3)
        NOT NULL DEFAULT 0.000 AFTER saldo_financiado,

    ADD COLUMN gastos_administrativos DECIMAL(10, 2)
        NOT NULL DEFAULT 0.00 AFTER tasa_interes,

    -- El importe de cada cuota. Se congela por la
    -- misma razón que el resto: el PDF que se firmó
    -- decía esta cifra.

    ADD COLUMN monto_cuota DECIMAL(10, 2)
        DEFAULT NULL AFTER gastos_administrativos,

    -- Cómo vencen las cuotas.

    ADD COLUMN periodicidad VARCHAR(20)
        NOT NULL DEFAULT 'mensual' AFTER cantidad_cuotas,

    ADD COLUMN primer_vencimiento DATE
        DEFAULT NULL AFTER periodicidad,

    ADD COLUMN dia_vencimiento INT
        DEFAULT NULL AFTER primer_vencimiento,

    -- Moneda pactada. Importes y moneda van juntos:
    -- un contrato en dólares con el símbolo de pesos
    -- puesto al día siguiente es un documento que no
    -- se puede defender.

    ADD COLUMN moneda VARCHAR(10)
        NOT NULL DEFAULT 'USD' AFTER dia_vencimiento,

    -- Retención sobre la venta. El porcentaje lo fija
    -- la configuración, no el código, porque su
    -- cálculo y su tratamiento cambian según el tipo
    -- de operación.
    --
    -- REVISAR CON ASESOR FISCAL: no se ha validado
    -- aquí el porcentaje ni la base de cálculo que
    -- corresponde a cada caso. El campo existe para
    -- que el dato quede registrado, no para que la
    -- aplicación resuelva una obligación fiscal.

    ADD COLUMN retencion DECIMAL(6, 3)
        NOT NULL DEFAULT 0.000 AFTER moneda,

    -- Retención en guaraníes, cuando la retención es
    -- un importe fijo y no un porcentaje.

    ADD COLUMN retencion_monto DECIMAL(10, 2)
        NOT NULL DEFAULT 0.00 AFTER retencion,

    -- Fotografía del vehículo en el momento de firmar.
    -- Antes se leía en vivo con un JOIN, así que
    -- corregir el vehículo cambiaba un contrato ya
    -- firmado.

    ADD COLUMN marca VARCHAR(50) DEFAULT NULL
        AFTER cliente_id,

    ADD COLUMN modelo VARCHAR(100) DEFAULT NULL
        AFTER auto_id,

    ADD COLUMN anio INT DEFAULT NULL AFTER modelo,

    ADD COLUMN color VARCHAR(50) DEFAULT NULL AFTER anio,

    ADD COLUMN precio_lista DECIMAL(10, 2)
        DEFAULT NULL AFTER color,

    ADD COLUMN fecha_financiacion DATE
        DEFAULT NULL AFTER fecha,

    -- Cláusulas pactadas. Se guardan como texto
    -- porque su redacción depende de lo que firme
    -- cada parte.

    ADD COLUMN clausulas TEXT DEFAULT NULL
        AFTER observaciones,

    -- Cuándo se tocó por última vez una condición
    -- económica. Permite saber si el contrato que se
    -- está leyendo es el que se firmó.

    ADD COLUMN fecha_modificacion DATETIME
        DEFAULT NULL AFTER fecha_creacion;

-- La cartera pregunta por "contratos con saldo y
-- activos": sin índice es un recorrido completo.

CREATE INDEX ix_contratos_saldo
    ON contratos (saldo_financiado, estado);


-- ------------------------------------------------------------
-- 2. CUOTAS: el cronograma
-- ------------------------------------------------------------
-- Una fila por vencimiento. Es lo que se genera
-- automáticamente al firmar un contrato financiado,
-- y lo que permite saber, sin recorrer todos los
-- pagos, qué se debe en cada fecha.

-- "saldo" se mantiene dentro de la misma transacción
-- que registra el pago, y registrar_pago_cuota() es
-- el ÚNICO sitio que lo escribe. Nunca se calcula
-- sumando en Python.
--
-- "estado" no lo pone alguien a mano: lo mueven
-- registrar_pago_cuota() y procesar_vencidas(),
-- según el orden de ESTADOS_CUOTA de
-- database/financiera.py.
--
-- VENCIDA es un estado DERIVADO de la fecha, no una
-- decisión: una cuota que pasó su vencimiento y sigue
-- con saldo es vencida, diga lo que diga.

CREATE TABLE cuotas (

    id INT NOT NULL AUTO_INCREMENT,

    contrato_id INT NOT NULL,

    -- 1..cantidad_cuotas. UNIQUE con contrato_id:
    -- dos cuotas con el mismo número en el mismo
    -- contrato son un cronograma corrupto.

    numero INT NOT NULL,

    fecha_vencimiento DATE NOT NULL,

    importe DECIMAL(10, 2) NOT NULL,

    -- Lo que queda por cobrar de ESTA cuota. No es
    -- el saldo del contrato: cada cuota tiene el suyo.

    saldo DECIMAL(10, 2) NOT NULL,

    estado VARCHAR(20) NOT NULL DEFAULT 'pendiente',

    -- Cuántas veces se le registró un pago. Cuenta
    -- informativa para la cabecera; el saldo sigue
    -- mandando.

    cantidad_pagos INT NOT NULL DEFAULT 0,

    fecha_creacion DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE KEY uq_cuotas_numero (contrato_id, numero),

    -- La cartera pregunta constantly por vencimientos:
    -- qué vence en 15 días, qué está vencido. Sin
    -- índice sería un recorrido completo cada vez.

    KEY ix_cuotas_vencimiento (fecha_vencimiento, estado),

    KEY ix_cuotas_contrato (contrato_id),

    KEY ix_cuotas_estado (estado),

    -- RESTRICT y no CASCADE: un contrato con dinero
    -- cobrado no se borra por la puerta de atrás. Se
    -- cancela, que conserva el documento.

    CONSTRAINT cuotas_contrato_fk
        FOREIGN KEY (contrato_id)
        REFERENCES contratos (id)
        ON DELETE RESTRICT

);


-- ------------------------------------------------------------
-- 3. PAGOS: ahora pueden imputarse a una cuota
-- ------------------------------------------------------------
-- No se crea una tabla nueva de pagos. Sería una
-- trampa: el mismo dinero aplicado a una cuota tiene
-- que contar para el saldo de la venta, y con dos
-- tablas habría que sumar las dos en cada consulta,
-- con el riesgo de que una de las dos se olvide y el
-- saldo de la venta deje de cuadrar.
--
-- "cuota_id" es NULL cuando el pago no imputa a una
-- cuota concreta: la entrega inicial, un pago a
-- cuenta, el pago de una venta al contado.

ALTER TABLE pagos

    ADD COLUMN cuota_id INT DEFAULT NULL AFTER contrato_id,

    -- Número de recibo. Es lo que el cliente se lleva
    -- en la mano y lo que se necesita para reclamar.
    -- Lo imprime utils/recibo_pdf.py.

    ADD COLUMN recibo VARCHAR(50) DEFAULT NULL
        AFTER referencia,

    -- Un pago NO se borra: se anula. Un DELETE deja
    -- el mismo hueco que dejaría no haber cobrado, y
    -- no se distingue de un error de teclear.
    --
    -- "estado" = 'convalidado' | 'anulado'

    ADD COLUMN estado VARCHAR(20)
        NOT NULL DEFAULT 'convalidado' AFTER concepto,

    ADD COLUMN anulado_motivo VARCHAR(255)
        DEFAULT NULL AFTER estado,

    ADD COLUMN anulado_usuario VARCHAR(50)
        DEFAULT NULL AFTER anulado_motivo,

    ADD COLUMN anulado_fecha DATETIME
        DEFAULT NULL AFTER anulado_usuario;

-- El saldo de una venta suma sus pagos CONVALIDADOS.
-- Un pago anulado no suma, igual que si no existiera,
-- pero se conserva la fila y el motivo.

ALTER TABLE pagos

    ADD CONSTRAINT pagos_cuota_fk
        FOREIGN KEY (cuota_id)
        REFERENCES cuotas (id)
        ON DELETE RESTRICT;

-- Anular un pago exige mirar su estado, y listar los
-- de una cuota es lo más frecuente que se hace.

CREATE INDEX ix_pagos_cuota
    ON pagos (cuota_id, estado);

CREATE INDEX ix_pagos_estado
    ON pagos (estado);


-- ------------------------------------------------------------
-- 4. GARANTÍAS Y GRAVÁMENES
-- ------------------------------------------------------------
-- Qué respalda la venta financiada y en qué estado
-- está. Un gravamen es una inscripción registral: su
-- RATIFICACIÓN, sus datos y el procedimiento dependen
-- de lo que diga el Registro Público y del criterio
-- del escribano.
--
-- REVISAR CON ABOGADO Y ESCRIBANO antes de usar esto
-- como documento registral: esta tabla REGISTRA lo que
-- el concesionario afirma, no certifica que sea cierto
-- ante el Registro Público. Que aquí diga "inscrita"
-- no la inscribe allí.

CREATE TABLE garantias (

    id INT NOT NULL AUTO_INCREMENT,

    contrato_id INT NOT NULL,

    -- Lo que respalda la operación. Texto controlado
    -- para poder agrupar, con "otro" para lo que no
    -- entre en la lista.

    tipo VARCHAR(30) NOT NULL DEFAULT 'otro',

    descripcion VARCHAR(255) DEFAULT NULL,

    -- PENDIENTE   lo que la administración todavía no
    --             hizo
    -- INSCRITA    se presentó y se inscribió
    -- LIBERADA    el crédito terminó y se liberó
    -- RECHAZADA    no prosperó

    estado VARCHAR(20) NOT NULL DEFAULT 'pendiente',

    -- Datos registrales. Los rellena quien tramita.

    institucion VARCHAR(100) DEFAULT NULL,

    numero_inscripcion VARCHAR(60) DEFAULT NULL,

    fecha_inscripcion DATE DEFAULT NULL,

    fecha_liberacion DATE DEFAULT NULL,

    -- 1 cuando esta garantía es un gravamen. Lo que
    -- hace es que la cartera avise cuando un contrato
    -- vencido tiene garantía sin liberar.

    es_gravamen TINYINT(1) NOT NULL DEFAULT 0,

    observaciones TEXT DEFAULT NULL,

    fecha_creacion DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    fecha_modificacion DATETIME DEFAULT NULL,

    PRIMARY KEY (id),

    KEY ix_garantias_contrato (contrato_id),

    KEY ix_garantias_estado (estado, es_gravamen),

    CONSTRAINT garantias_contrato_fk
        FOREIGN KEY (contrato_id)
        REFERENCES contratos (id)
        ON DELETE RESTRICT

);


-- ------------------------------------------------------------
-- 5. CONVENIOS DE PAGO
-- ------------------------------------------------------------
-- Cuando un cliente no paga, lo habitual es acordar
-- un plan y no romper la relación. Se registra aquí
-- para que quede constancia de lo acordado.
--
-- REVISAR CON ABOGADO ANTES DE USARLO COMO DOCUMENTO:
-- un convenio de pago puede tener efectos ante un
-- juzgado, y eso depende de cómo esté redactado, de
-- si se homologa y de la legislación vigente. Este
-- módulo SOLO guarda el registro interno de lo que se
-- acordó: no genera el documento ni lo homologa.
--
-- Lo que sí hace es dejar constancia de QUIén acordó
-- QUÉ y CUÁNDO, que ya es útil aunque el documento
-- legal se gestione por otro lado.

CREATE TABLE convenios (

    id INT NOT NULL AUTO_INCREMENT,

    contrato_id INT NOT NULL,

    -- NULL cuando el convenio es sobre todo el saldo,
    -- no sobre una cuota concreta.

    cuota_id INT DEFAULT NULL,

    fecha_acuerdo DATE NOT NULL,

    -- Lo que se debía cuando se acordó, y lo que se
    -- acordó pagar. La diferencia es la reducción de
    -- deuda (condonada o financiada) y por eso se
    -- guarda: sin los dos importes no se puede
    -- después justificar por qué se cobró menos.

    monto_original DECIMAL(10, 2) NOT NULL,

    monto_acordado DECIMAL(10, 2) NOT NULL,

    cantidad_cuotas INT NOT NULL DEFAULT 1,

    monto_cuota DECIMAL(10, 2) DEFAULT NULL,

    fecha_ultimo_cuota DATE DEFAULT NULL,

    estado VARCHAR(20) NOT NULL DEFAULT 'activo',

    -- Si existe documento firmado u homologado. NO es
    -- una verificación: es lo que alguien anotó.

    documento_ref VARCHAR(100) DEFAULT NULL,

    observaciones TEXT DEFAULT NULL,

    fecha_creacion DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    KEY ix_convenios_contrato (contrato_id),

    KEY ix_convenios_cuota (cuota_id),

    KEY ix_convenios_estado (estado),

    CONSTRAINT convenios_contrato_fk
        FOREIGN KEY (contrato_id)
        REFERENCES contratos (id)
        ON DELETE RESTRICT,

    CONSTRAINT convenios_cuota_fk
        FOREIGN KEY (cuota_id)
        REFERENCES cuotas (id)
        ON DELETE RESTRICT

);


-- ============================================================
-- 6. Ajustes de la financiación
-- ============================================================
-- INSERT IGNORE y no INSERT: si una clave ya existe,
-- esta sentencia no hace nada. Así el archivo se
-- puede volver a aplicar sin pisar un ajuste que el
-- administrador haya cambiado desde Configuración.
--
-- OJO CON EL PUNTO Y COMA DENTRO DE LAS DESCRIPCIONES:
-- no se pone ninguno. Una descripción es un literal
-- de texto, pero cualquier herramienta que trocee
-- este archivo por ";" partiría la sentencia por la
-- mitad y MySQL se quejaría de sintaxis. Con
-- Workbench o por consola no hay problema; con un
-- script propio, sí.
--
-- Las descripciones con "REVISAR CON ASESOR" están
-- ahí porque hay cosas que la aplicación NO puede
-- decidir por sí sola. Que un ajuste exista no
-- significa que su valor sea el correcto.

INSERT IGNORE INTO configuracion
    (clave, valor, descripcion) VALUES

    ('financiera_dias_aviso',
     '15',
     'Días antes del vencimiento a partir de los cuales una cuota entra en "próximas a vencer".'),

    ('financiera_dias_gracia',
     '0',
     'Días de tolerancia tras el vencimiento antes de marcar la cuota como VENCIDA. Con 0, vence el día exacto. Ponerlo aquí NO cambia ninguna obligación legal: es un criterio interno.'),

    ('financiera_maximo_cuotas',
     '72',
     'Máximo de cuotas que admite un contrato. Corta un contrato de 200 plazos, que casi siempre es un error de teclear.'),

    ('financiera_interes_mora_tipo',
     'ninguno',
     'Qué se aplica a una cuota vencida: "ninguno" o "porcentaje_mensual". REVISAR CON ASESOR: la normativa de intereses moratorios y su tope cambian, y este ajuste NO los valida.'),

    ('financiera_interes_mora_porcentaje',
     '0.000',
     'Porcentaje mensual de mora, solo si el tipo no es "ninguno". Se informa para poder mostrarlo. El cálculo del interés debe validarlo un asesor.'),

    ('financiera_retencion_porcentaje',
     '0.000',
     'Retención por defecto sobre ventas a terceros. REVISAR CON ASESOR FISCAL: el porcentaje y la base de cálculo no están validados.'),

    ('financiera_exigir_escribano',
     '0',
     'Si vale 1, la aplicación avisa (no bloquea) cuando se firma una venta financiada, señalando que el contrato puede necesitar escribano público.');


-- ------------------------------------------------------------
-- SI AL PEGAR ESTO A MANO SALEN ACENTOS RAROS
-- ------------------------------------------------------------
-- Ejecuta esto antes:
--
--   SET NAMES utf8mb4;
--
-- ------------------------------------------------------------


-- ============================================================
-- COMPROBACIÓN
-- ============================================================
-- Debe devolver 0 filas la primera vez:
--
--   SELECT * FROM cuotas;
--
-- Las columnas nuevas de contratos:
--
--   SHOW COLUMNS FROM contratos
--    LIKE 'saldo_financiado';
--
-- Las nuevas de pagos:
--
--   SHOW COLUMNS FROM pagos LIKE 'cuota_id';
--
-- Las tres tablas nuevas:
--
--   SHOW TABLES LIKE 'cuotas';
--   SHOW TABLES LIKE 'garantias';
--   SHOW TABLES LIKE 'convenios';
--
-- ============================================================