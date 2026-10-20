-- Uruchom ten plik w SQL Server Management Studio tylko wtedy,
-- gdy w config.json ustawisz "engine": "sqlserver".

IF DB_ID(N'TransportOrders') IS NULL
    CREATE DATABASE TransportOrders;
GO

USE TransportOrders;
GO

IF OBJECT_ID('dbo.places', 'U') IS NULL
CREATE TABLE dbo.places (
    id INT IDENTITY(1,1) PRIMARY KEY,
    kind NVARCHAR(30) NOT NULL,
    name NVARCHAR(250) NOT NULL,
    address NVARCHAR(1000) NOT NULL DEFAULT '',
    updated_at DATETIME2 NOT NULL,
    CONSTRAINT UQ_places_kind_name_address UNIQUE(kind, name, address)
);
GO

IF OBJECT_ID('dbo.carriers', 'U') IS NULL
CREATE TABLE dbo.carriers (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(250) NOT NULL UNIQUE,
    address NVARCHAR(MAX) NOT NULL DEFAULT '',
    nip NVARCHAR(30) NOT NULL DEFAULT '',
    email NVARCHAR(250) NOT NULL DEFAULT '',
    phone NVARCHAR(80) NOT NULL DEFAULT '',
    updated_at DATETIME2 NOT NULL
);
GO

IF OBJECT_ID('dbo.drivers', 'U') IS NULL
CREATE TABLE dbo.drivers (
    id INT IDENTITY(1,1) PRIMARY KEY,
    carrier_id INT NULL,
    full_name NVARCHAR(250) NOT NULL,
    id_card NVARCHAR(80) NOT NULL DEFAULT '',
    pesel NVARCHAR(20) NOT NULL DEFAULT '',
    truck_registration NVARCHAR(30) NOT NULL DEFAULT '',
    trailer_registration NVARCHAR(30) NOT NULL DEFAULT '',
    phone NVARCHAR(80) NOT NULL DEFAULT '',
    updated_at DATETIME2 NOT NULL,
    CONSTRAINT FK_drivers_carriers FOREIGN KEY(carrier_id)
        REFERENCES dbo.carriers(id) ON DELETE SET NULL
);
GO

IF OBJECT_ID('dbo.orders', 'U') IS NULL
CREATE TABLE dbo.orders (
    id INT IDENTITY(1,1) PRIMARY KEY,
    order_ordinal INT NOT NULL,
    order_month INT NOT NULL,
    order_year INT NOT NULL,
    order_number NVARCHAR(50) NOT NULL UNIQUE,
    order_date DATE NOT NULL,
    internal_notes NVARCHAR(MAX) NOT NULL DEFAULT '',
    carrier_name NVARCHAR(250) NOT NULL DEFAULT '',
    carrier_details NVARCHAR(MAX) NOT NULL DEFAULT '',
    load_place_name NVARCHAR(250) NOT NULL DEFAULT '',
    load_address NVARCHAR(MAX) NOT NULL DEFAULT '',
    load_date NVARCHAR(100) NULL,
    unload_place_name NVARCHAR(250) NOT NULL DEFAULT '',
    unload_address NVARCHAR(MAX) NOT NULL DEFAULT '',
    unload_date NVARCHAR(100) NULL,
    service_value NVARCHAR(80) NOT NULL DEFAULT '',
    payment NVARCHAR(250) NOT NULL DEFAULT '',
    cargo_type NVARCHAR(250) NOT NULL DEFAULT '',
    cargo_tons DECIMAL(12,3) NOT NULL DEFAULT 0,
    driver_full_name NVARCHAR(250) NOT NULL DEFAULT '',
    driver_id_card NVARCHAR(80) NOT NULL DEFAULT '',
    driver_pesel NVARCHAR(20) NOT NULL DEFAULT '',
    truck_registration NVARCHAR(30) NOT NULL DEFAULT '',
    trailer_registration NVARCHAR(30) NOT NULL DEFAULT '',
    driver_phone NVARCHAR(80) NOT NULL DEFAULT '',
    pdf_path NVARCHAR(1000) NOT NULL DEFAULT '',
    created_at DATETIME2 NOT NULL,
    updated_at DATETIME2 NOT NULL
);
GO


-- Aktualizacja bazy utworzonej przez starszą wersję aplikacji.
IF COL_LENGTH('dbo.orders', 'internal_notes') IS NULL
    ALTER TABLE dbo.orders ADD internal_notes NVARCHAR(MAX) NOT NULL
        CONSTRAINT DF_orders_internal_notes DEFAULT '';
GO

IF EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'orders'
      AND COLUMN_NAME = 'load_date' AND DATA_TYPE = 'date'
)
    ALTER TABLE dbo.orders ALTER COLUMN load_date NVARCHAR(100) NULL;
GO

IF EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = 'orders'
      AND COLUMN_NAME = 'unload_date' AND DATA_TYPE = 'date'
)
    ALTER TABLE dbo.orders ALTER COLUMN unload_date NVARCHAR(100) NULL;
GO


-- Starsza wersja ograniczała firmę do jednego adresu.
IF EXISTS (
    SELECT 1 FROM sys.key_constraints
    WHERE [type] = 'UQ' AND [name] = 'UQ_places_kind_name'
)
    ALTER TABLE dbo.places DROP CONSTRAINT UQ_places_kind_name;
GO
