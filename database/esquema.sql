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

    precio DECIMAL(15, 2) NOT NULL,

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
-- LOS IMPORTES
-- ==========================================
-- Todas las columnas de dinero son DECIMAL(15, 2):
-- 13 cifras enteras y dos decimales.
--
-- Antes eran DECIMAL(10, 2), cuyo techo son
-- 99.999.999,99. Ese numero estaba pensado para
-- dolares y en guaranies es un caso corriente
-- superado: un vehiculo de 100.000.000 no cabia.
--
-- El fallo era doble, y por eso importa mas que el
-- numero en si:
--
--   - La validacion de la aplicacion daba por bueno
--     hasta 999.999.999, que es mas de lo que MySQL
--     acepta. En esa ventana el formulario dejaba
--     guardar y la base rechazaba con "Out of range".
--
--   - Los campos de escritura se quedaban en
--     999.999.999, y en vez de avisar recortaban el
--     precio en silencio: se tecleaba 150.000.000 y
--     se guardaba 999.999.999.
--
-- Ampliar la columna no altera ni un valor ya
-- guardado: DECIMAL(10,2) y DECIMAL(15,2) guardan
-- el mismo 25.000,00. Solo caben mas cifras.
--
-- ------------------------------
-- LA MONEDA NO SE CONVIERTE
-- ------------------------------
-- Cambiar el ajuste de moneda cambia COMO SE MUESTRA
-- un importe, no su valor. No hay tipo de cambio en
-- ninguna parte, y no se calcula ninguno.
--
-- Para eso estan `ventas.moneda` y `contratos.moneda`:
-- guardan con que moneda se hizo cada operacion, para
-- que un contrato firmado no cambie de "$ 25,000.00"
-- a "Gs. 25.000" porque alguien toco un ajuste. El
-- numero seria el mismo y estaria mal.


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

    -- 15,2 y no 10,2: con 10,2 el techo son
    -- 99.999.999,99, y en guaranies un vehiculo
    -- normal cuesta 30-100 millones. Con el tope
    -- viejo, un precio de 100.000.000 lo rechazaba
    -- MySQL con "Out of range" DESPUES de que la
    -- validacion de la aplicacion lo habia
    -- aceptado: la ventana entre lo que se puede
    -- escribir y lo que se puede guardar.
    --
    -- Ampliar la columna no altera ni un valor
    -- guardado: solo caben mas cifras.
    precio DECIMAL(15, 2) NOT NULL,

    -- Moneda con la que se registro la venta.
    --
    -- Sin esta columna, una venta de 25.000 dolares
    -- se reenseñaria como "Gs. 25.000" en cuanto el
    -- concesionario cambiara el ajuste de moneda, y el
    -- numero no se habria convertido: seria un
    -- documento que dice una cantidad y significa
    -- otra.
    --
    -- Es la MISMA cosa que contratos.moneda, y por el
    -- mismo motivo. Se escribe al registrar la venta,
    -- con la moneda que hay en ese momento, y no se
    -- toca nunca mas.
    --
    -- No hay conversion: el valor es el que es, en la
    -- moneda que dice la columna.
    moneda VARCHAR(10) NOT NULL DEFAULT 'USD',

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

    -- Las tres siguientes las escribe
    -- registrar_cambio(), que es registrar_accion()
    -- con los valores de antes y después.
    --
    -- Están aquí y no en la fila de la cuota porque
    -- un pago anulado deja de sumar al saldo pero su
    -- fila sigue ahí para siempre: si su historia
    -- viviera en la fila, la fila tendría que
    -- guardar su propio pasado.
    --
    -- Sin esto, una modificación se puede registrar
    -- sin decir qué cambió, y quien la lea no sabe si
    -- el saldo era 200.000 o 2.000.000 antes de que
    -- alguien lo tocara.

    valor_anterior VARCHAR(255) DEFAULT NULL,

    valor_nuevo VARCHAR(255) DEFAULT NULL,

    -- Recibo, número de cuota, número de contrato:
    -- lo que permite encontrar en la tabla lo que
    -- cambió sin tener que buscar por texto en la
    -- descripción.

    referencia VARCHAR(255) DEFAULT NULL,

    fecha_hora DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    KEY ix_auditoria_fecha (fecha_hora),

    -- Buscar "todos los cambios de este contrato" o
    -- "todos los de este recibo": sin índice, la
    -- búsqueda de un historial es un recorrido
    -- completo por toda la tabla.

    KEY ix_auditoria_referencia (referencia),

    -- Y filtrar por tipo de acción: un usuario
    -- mirando el historial de una cuota quiere ver
    -- pagos y anulaciones, no los 200 accesos
    --다만 lo que pasó.

    KEY ix_auditoria_accion (accion, fecha_hora),

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

    precio_venta DECIMAL(15, 2) NOT NULL,

    forma_pago VARCHAR(40) NOT NULL
        DEFAULT 'Contado',

    anticipo DECIMAL(15, 2) NOT NULL DEFAULT 0.00,

    cantidad_cuotas INT NOT NULL DEFAULT 0,

    observaciones TEXT DEFAULT NULL,

    estado VARCHAR(20) NOT NULL DEFAULT 'borrador',

    archivo_pdf VARCHAR(255) DEFAULT NULL,

    fecha_creacion DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    -- Lo que se financia de verdad: precio menos
    -- entrega inicial. Se guarda en vez de calcularse
    -- porque es una condición PACTADA: si alguien
    -- toca un valor de arriba, el contrato ya
    -- firmado tiene que seguir diciendo lo que
    -- decía.

    saldo_financiado DECIMAL(15, 2)
        NOT NULL DEFAULT 0.00,

    -- Tasa en porcentaje anual. 0 es una venta sin
    -- interés, que también es válida.

    tasa_interes DECIMAL(6, 3)
        NOT NULL DEFAULT 0.000,

    gastos_administrativos DECIMAL(15, 2)
        NOT NULL DEFAULT 0.00,

    -- El importe de cada cuota, congelado: el PDF
    -- que se firmó decía esta cifra.

    monto_cuota DECIMAL(15, 2) DEFAULT NULL,

    -- Cómo vencen las cuotas.

    periodicidad VARCHAR(20)
        NOT NULL DEFAULT 'mensual',

    primer_vencimiento DATE DEFAULT NULL,

    dia_vencimiento INT DEFAULT NULL,

    -- Moneda pactada. Importes y moneda van juntos:
    -- un contrato en dólares con el símbolo de pesos
    -- puesto al día siguiente es un documento que no
    -- se puede defender.

    moneda VARCHAR(10) NOT NULL DEFAULT 'USD',

    -- Retención sobre la venta.
    --
    -- REVISAR CON ASESOR FISCAL: el porcentaje y la
    -- base de cálculo NO están validados. El campo
    -- existe para que el dato quede registrado, no
    -- para que la aplicación resuelva una
    -- obligación fiscal.

    retencion DECIMAL(6, 3) NOT NULL DEFAULT 0.000,

    -- Retención en guaraníes, cuando es importe fijo
    -- y no porcentaje.

    retencion_monto DECIMAL(15, 2)
        NOT NULL DEFAULT 0.00,

    -- Fotografía del vehículo al momento de firmar.
    -- Antes se leía en vivo con un JOIN, así que
    -- corregir el vehículo cambiaba un contrato ya
    -- firmado.

    marca VARCHAR(50) DEFAULT NULL,

    modelo VARCHAR(100) DEFAULT NULL,

    anio INT DEFAULT NULL,

    color VARCHAR(50) DEFAULT NULL,

    precio_lista DECIMAL(15, 2) DEFAULT NULL,

    fecha_financiacion DATE DEFAULT NULL,

    -- Cláusulas pactadas, como texto: su redacción
    -- depende de lo que firme cada parte.

    clausulas TEXT DEFAULT NULL,

    -- Cuándo se tocó por última vez una condición
    -- económica del contrato. Permite saber si el
    -- contrato que se está leyendo es el que se
    -- firmó, o si alguien lo cambió después.

    fecha_modificacion DATETIME DEFAULT NULL,

    PRIMARY KEY (id),

    UNIQUE KEY uq_contratos_numero (numero),

    UNIQUE KEY uq_contratos_venta (venta_id),

    KEY ix_contratos_cliente (cliente_id),

    KEY ix_contratos_auto (auto_id),

    KEY ix_contratos_usuario (usuario_id),

    KEY ix_contratos_estado (estado),

    -- La cartera pregunta por "contratos con saldo y
    -- activos": sin índice, un recorrido completo.

    KEY ix_contratos_saldo (saldo_financiado, estado),

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
-- CUOTAS
-- ==========================================
-- El cronograma de una venta financiada: una fila
-- por vencimiento. Se genera automáticamente al
-- firmar el contrato.
--
-- Es lo que permite saber, sin recorrer todos los
-- pagos, qué se debe en cada fecha y qué está
-- vencido.
--
-- "saldo" lo mantiene registrar_pago_cuota() dentro
-- de la misma transacción que inserta el pago, y es
-- el ÚNICO sitio que lo escribe. Nunca se calcula
-- sumando en Python: si se calculara en el cliente,
-- un pago anulado o de otra cuota se colaría en la
-- suma.
--
-- "estado" no lo pone alguien a mano: lo mueven
-- registrar_pago_cuota() y procesar_vencidas(),
-- según el orden de ESTADOS_CUOTA de
-- database/financiera.py.
--
-- VENCIDA es un estado DERIVADO de la fecha, no una
-- decisión: una cuota que pasó su vencimiento y
-- sigue con saldo es vencida, diga lo que diga.
-- ==========================================

CREATE TABLE cuotas (

    id INT NOT NULL AUTO_INCREMENT,

    contrato_id INT NOT NULL,

    -- 1..cantidad_cuotas. UNIQUE con contrato_id:
    -- dos cuotas con el mismo número en el mismo
    -- contrato son un cronograma corrupto.

    numero INT NOT NULL,

    fecha_vencimiento DATE NOT NULL,

    importe DECIMAL(15, 2) NOT NULL,

    -- Lo que queda por cobrar de ESTA cuota. No es
    -- el saldo del contrato: cada cuota tiene el
    -- suyo.

    saldo DECIMAL(15, 2) NOT NULL,

    estado VARCHAR(20) NOT NULL DEFAULT 'pendiente',

    -- Cuántas veces se le registró un pago. Cuenta
    -- informativa para la cabecera; el saldo sigue
    -- mandando.

    cantidad_pagos INT NOT NULL DEFAULT 0,

    fecha_creacion DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE KEY uq_cuotas_numero (contrato_id, numero),

    -- La cartera pregunta constantemente por
    -- vencimientos: qué vence en 15 días, qué está
    -- vencido. Sin índice sería un recorrido
    -- completo cada vez.

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


-- ==========================================
-- GARANTÍAS Y GRAVÁMENES
-- ==========================================
-- Qué respalda la venta financiada y en qué estado
-- está.
--
-- REVISAR CON ABOGADO Y ESCRIBANO antes de usar esto
-- como documento registral: esta tabla REGISTRA lo que
-- el concesionario afirma, no certifica que sea cierto
-- ante el Registro Público. Que aquí diga "inscrita"
-- no la inscribe allí. El procedimiento de
-- inscripción, sus datos y su ratificación dependen
-- de lo que corresponda legalmente en cada caso.
-- ==========================================

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


-- ==========================================
-- CONVENIOS DE PAGO
-- ==========================================
-- Cuando un cliente no paga, lo habitual es acordar un
-- plan y no romper la relación. Se registra aquí para
-- que quede constancia de lo acordado.
--
-- REVISAR CON ABOGADO ANTES DE USARLO COMO
-- DOCUMENTO: un convenio de pago puede tener efectos
-- ante un juzgado, y eso depende de cómo esté
-- redactado, de si se homologa y de la legislación
-- vigente. Este módulo SOLO guarda el registro interno
-- de lo que se acordó: no genera el documento ni lo
-- homologa.
--
-- Lo que sí hace es dejar constancia de QUIén acordó
-- QUÉ y CUÁNDO, que ya es útil aunque el documento
-- legal se gestione por otro lado.
-- ==========================================

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

    monto_original DECIMAL(15, 2) NOT NULL,

    monto_acordado DECIMAL(15, 2) NOT NULL,

    cantidad_cuotas INT NOT NULL DEFAULT 1,

    monto_cuota DECIMAL(15, 2) DEFAULT NULL,

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

    -- Cuando el pago se imputa a una cuota concreta
    -- del cronograma. NULL cuando no: la entrega
    -- inicial, un pago a cuenta, el pago de una
    -- venta al contado.
    --
    -- No hay tabla aparte de pagos de cuota a
    -- propósito: el mismo dinero tiene que contar
    -- para el saldo de la venta, y con dos tablas
    -- habría que sumar las dos en cada consulta, con
    -- el riesgo de que una se olvide.

    cuota_id INT DEFAULT NULL,

    fecha DATE NOT NULL,

    importe DECIMAL(15, 2) NOT NULL,

    forma VARCHAR(40) NOT NULL,

    -- Número de operación, cheque, etc. Lo que
    -- haga falta para localizar el movimiento
    -- en un extracto bancario.

    referencia VARCHAR(100) DEFAULT NULL,

    -- Número de recibo: lo que el cliente se lleva
    -- en la mano y lo que se necesita para reclamar.
    -- Lo imprime utils/recibo_pdf.py.

    recibo VARCHAR(50) DEFAULT NULL,

    concepto VARCHAR(255) DEFAULT NULL,

    -- Un pago NO se borra: se anula. Un DELETE deja
    -- el mismo hueco que dejaría no haber cobrado, y
    -- no se distingue de un error de teclear.
    --
    -- "estado" = 'convalidado' | 'anulado'

    estado VARCHAR(20)
        NOT NULL DEFAULT 'convalidado',

    anulado_motivo VARCHAR(255) DEFAULT NULL,

    anulado_usuario VARCHAR(50) DEFAULT NULL,

    anulado_fecha DATETIME DEFAULT NULL,



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

    -- Listar los pagos de una cuota es lo más
    -- frecuente que se hace, y hay que mirar su
    -- estado para saber si alguno está anulado.

    KEY ix_pagos_cuota (cuota_id, estado),

    KEY ix_pagos_estado (estado),

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

    -- RESTRICT y no CASCADE: si ya se pagó, la cuota
    -- no se puede borrar. Se anula, con motivo y con
    -- rastro.

    CONSTRAINT pagos_cuota_fk
        FOREIGN KEY (cuota_id)
        REFERENCES cuotas (id)
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

-- Ajustes de la financiación.
--
-- Las descripciones con "REVISAR CON ASESOR" están
-- ahí porque hay cosas que la aplicación NO puede
-- decidir por sí sola: que un ajuste exista no
-- significa que su valor sea el correcto.
--
-- Insert IGNORE y no INSERT: el archivo se puede
-- reaplicar sin pisar un ajuste que el administrador
-- haya cambiado desde Configuración.

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



CREATE TABLE auto_fichas (
    auto_id INT NOT NULL PRIMARY KEY,
    combustible VARCHAR(40) NOT NULL DEFAULT '',
    transmision VARCHAR(40) NOT NULL DEFAULT '',
    observaciones TEXT,
    FOREIGN KEY (auto_id) REFERENCES autos(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE auto_fotos (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    auto_id INT NOT NULL,
    contenido MEDIUMBLOB NOT NULL,
    nombre VARCHAR(255) NOT NULL,
    creado DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_fotos_auto (auto_id),
    FOREIGN KEY (auto_id) REFERENCES autos(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE unidades_vehiculo (
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

CREATE TABLE venta_unidades (
    venta_id INT NOT NULL PRIMARY KEY,
    unidad_id INT NOT NULL UNIQUE,
    FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE CASCADE,
    FOREIGN KEY (unidad_id) REFERENCES unidades_vehiculo(id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE seguimiento_cobranza (
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
