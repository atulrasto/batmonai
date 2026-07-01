"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-30
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _x(sql: str) -> None:
    op.execute(sql)


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    # ── 1. Enums ────────────────────────────────────────────────────────────
    _x("CREATE TYPE user_role AS ENUM ('superuser', 'client')")
    _x("CREATE TYPE ac_channel_role AS ENUM ('inverter_input', 'inverter_output', 'load')")
    _x("""
        CREATE TYPE event_kind AS ENUM (
            'discharge_start', 'discharge_end', 'mains_outage',
            'charging', 'float',
            'low_voltage', 'high_voltage',
            'device_offline',
            'high_temperature', 'high_humidity', 'h2_gas_alarm'
        )
    """)
    _x("CREATE TYPE event_severity AS ENUM ('info', 'warning', 'critical')")

    # ── 2. Reference tables ─────────────────────────────────────────────────
    _x("""
        CREATE TABLE clients (
            id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            name        TEXT        NOT NULL,
            primary_email TEXT      NOT NULL UNIQUE,
            is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    _x("""
        CREATE TABLE users (
            id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            email                TEXT        NOT NULL UNIQUE,
            password_hash        TEXT        NOT NULL,
            role                 user_role   NOT NULL,
            client_id            UUID        REFERENCES clients(id) ON DELETE RESTRICT,
            must_change_password BOOLEAN     NOT NULL DEFAULT TRUE,
            is_active            BOOLEAN     NOT NULL DEFAULT TRUE,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    _x("CREATE INDEX idx_users_email ON users (email)")

    _x("""
        CREATE TABLE sites (
            id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            client_id  UUID        NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            name       TEXT        NOT NULL,
            slug       TEXT        NOT NULL,
            location   TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (client_id, slug)
        )
    """)

    _x("""
        CREATE TABLE appliances (
            id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            client_id         UUID        NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            site_id           UUID        NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            appliance_uid     TEXT        NOT NULL UNIQUE,
            name              TEXT        NOT NULL,
            device_secret_hash TEXT       NOT NULL,
            fw_version        TEXT,
            last_seen_at      TIMESTAMPTZ,
            is_active         BOOLEAN     NOT NULL DEFAULT TRUE,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    _x("CREATE INDEX idx_appliances_uid ON appliances (appliance_uid)")

    _x("""
        CREATE TABLE batteries (
            id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            client_id      UUID        NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            appliance_id   UUID        NOT NULL REFERENCES appliances(id) ON DELETE CASCADE,
            battery_uid    TEXT        NOT NULL UNIQUE,
            modbus_addr    SMALLINT    NOT NULL,
            shunt_rating_a SMALLINT    NOT NULL DEFAULT 100,
            capacity_ah    NUMERIC(8,2),
            chemistry      TEXT        NOT NULL DEFAULT 'flooded_lead_acid',
            nominal_v      NUMERIC(5,2) NOT NULL DEFAULT 12.0,
            is_active      BOOLEAN     NOT NULL DEFAULT TRUE,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (appliance_id, modbus_addr)
        )
    """)
    _x("CREATE INDEX idx_batteries_uid ON batteries (battery_uid)")

    _x("""
        CREATE TABLE ac_channels (
            id           UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
            client_id    UUID            NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            appliance_id UUID            NOT NULL REFERENCES appliances(id) ON DELETE CASCADE,
            channel_uid  TEXT            NOT NULL UNIQUE,
            name         TEXT            NOT NULL,
            modbus_addr  SMALLINT        NOT NULL,
            role         ac_channel_role NOT NULL,
            is_active    BOOLEAN         NOT NULL DEFAULT TRUE,
            created_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
            UNIQUE (appliance_id, modbus_addr)
        )
    """)
    _x("CREATE INDEX idx_ac_channels_uid ON ac_channels (channel_uid)")

    _x("""
        CREATE TABLE rs485_sensors (
            id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            client_id    UUID        NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            appliance_id UUID        NOT NULL REFERENCES appliances(id) ON DELETE CASCADE,
            sensor_uid   TEXT        NOT NULL UNIQUE,
            sensor_type  TEXT        NOT NULL,
            modbus_addr  SMALLINT    NOT NULL,
            name         TEXT        NOT NULL,
            config       JSONB,
            is_active    BOOLEAN     NOT NULL DEFAULT TRUE,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (appliance_id, modbus_addr)
        )
    """)
    _x("CREATE INDEX idx_rs485_sensors_uid ON rs485_sensors (sensor_uid)")

    # ── 3. Hypertables ──────────────────────────────────────────────────────
    _x("""
        CREATE TABLE dc_readings (
            time        TIMESTAMPTZ NOT NULL,
            battery_id  UUID        NOT NULL REFERENCES batteries(id) ON DELETE RESTRICT,
            client_id   UUID        NOT NULL,
            voltage     NUMERIC(6,3)  NOT NULL,
            current     NUMERIC(8,3)  NOT NULL,
            power       NUMERIC(10,3) NOT NULL,
            energy_wh   NUMERIC(12,3) NOT NULL,
            alarm_flags SMALLINT    NOT NULL DEFAULT 0,
            ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    _x("SELECT create_hypertable('dc_readings', 'time', chunk_time_interval => INTERVAL '1 day')")

    _x("""
        CREATE TABLE ac_readings (
            time           TIMESTAMPTZ  NOT NULL,
            ac_channel_id  UUID         NOT NULL REFERENCES ac_channels(id) ON DELETE RESTRICT,
            client_id      UUID         NOT NULL,
            voltage        NUMERIC(6,3)  NOT NULL,
            current        NUMERIC(8,3)  NOT NULL,
            power          NUMERIC(10,3) NOT NULL,
            energy_wh      NUMERIC(12,3) NOT NULL,
            frequency      NUMERIC(5,2)  NOT NULL DEFAULT 0,
            power_factor   NUMERIC(4,3)  NOT NULL DEFAULT 0,
            ingested_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
        )
    """)
    _x("SELECT create_hypertable('ac_readings', 'time', chunk_time_interval => INTERVAL '1 day')")

    _x("""
        CREATE TABLE sensor_readings (
            time        TIMESTAMPTZ NOT NULL,
            sensor_id   UUID        NOT NULL REFERENCES rs485_sensors(id) ON DELETE RESTRICT,
            client_id   UUID        NOT NULL,
            payload     JSONB       NOT NULL,
            ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    _x("SELECT create_hypertable('sensor_readings', 'time', chunk_time_interval => INTERVAL '1 day')")

    # ── 4. Events ────────────────────────────────────────────────────────────
    _x("""
        CREATE TABLE events (
            id           UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
            client_id    UUID           NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            appliance_id UUID           NOT NULL REFERENCES appliances(id) ON DELETE CASCADE,
            kind         event_kind     NOT NULL,
            severity     event_severity NOT NULL DEFAULT 'info',
            detail       JSONB,
            started_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
            resolved_at  TIMESTAMPTZ,
            created_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW()
        )
    """)

    # ── 5. Indexes ──────────────────────────────────────────────────────────
    _x("CREATE INDEX idx_dc_readings_battery_time  ON dc_readings  (battery_id,    time DESC)")
    _x("CREATE INDEX idx_dc_readings_client_time   ON dc_readings  (client_id,     time DESC)")
    _x("CREATE INDEX idx_ac_readings_channel_time  ON ac_readings  (ac_channel_id, time DESC)")
    _x("CREATE INDEX idx_ac_readings_client_time   ON ac_readings  (client_id,     time DESC)")
    _x("CREATE INDEX idx_sensor_readings_sensor_time ON sensor_readings (sensor_id, time DESC)")
    _x("CREATE INDEX idx_events_client       ON events (client_id,    started_at DESC)")
    _x("CREATE INDEX idx_events_appliance    ON events (appliance_id, started_at DESC)")
    _x("CREATE INDEX idx_events_open         ON events (client_id, kind) WHERE resolved_at IS NULL")

    # ── 6. Row-Level Security ────────────────────────────────────────────────
    # users table is intentionally NOT subject to RLS; API layer enforces access.
    #
    # TimescaleDB hard constraint: continuous aggregates cannot be created on
    # hypertables that have RLS enabled. dc_readings, ac_readings, and
    # sensor_readings are therefore excluded from RLS. Tenant isolation for these
    # tables is enforced at the application level via explicit
    # WHERE client_id = ... clauses in all queries against them.
    for tbl in (
        "clients", "sites", "appliances", "batteries", "ac_channels",
        "rs485_sensors", "events",
    ):
        _x(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
        _x(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")

    # bypass_rls='true' is SET LOCAL by the API for superuser sessions.
    # clients INSERT/UPDATE: only superusers can create/modify client records.
    # Other tables INSERT/UPDATE: superuser OR own-tenant client_id allowed.
    _x("""
        CREATE POLICY clients_tenant ON clients
            FOR ALL
            USING (
                current_setting('app.bypass_rls', TRUE) = 'true'
                OR id = current_setting('app.current_client_id', TRUE)::UUID
            )
            WITH CHECK (
                current_setting('app.bypass_rls', TRUE) = 'true'
            )
    """)

    for tbl in (
        "sites", "appliances", "batteries", "ac_channels", "rs485_sensors", "events",
    ):
        _x(f"""
            CREATE POLICY {tbl}_tenant ON {tbl}
                FOR ALL
                USING (
                    current_setting('app.bypass_rls', TRUE) = 'true'
                    OR client_id = current_setting('app.current_client_id', TRUE)::UUID
                )
                WITH CHECK (
                    current_setting('app.bypass_rls', TRUE) = 'true'
                    OR client_id = current_setting('app.current_client_id', TRUE)::UUID
                )
        """)

    # ── 7. Continuous aggregates ─────────────────────────────────────────────

    # DC — hourly
    _x("""
        CREATE MATERIALIZED VIEW dc_readings_hourly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', time) AS bucket,
            battery_id,
            client_id,
            MIN(voltage)    AS min_voltage,
            MAX(voltage)    AS max_voltage,
            AVG(voltage)    AS avg_voltage,
            MIN(current)    AS min_current,
            MAX(current)    AS max_current,
            AVG(current)    AS avg_current,
            MAX(energy_wh) - MIN(energy_wh) AS energy_delta_wh,
            COUNT(*)        AS reading_count
        FROM dc_readings
        GROUP BY bucket, battery_id, client_id
        WITH NO DATA
    """)
    _x("""
        SELECT add_continuous_aggregate_policy('dc_readings_hourly',
            start_offset     => INTERVAL '3 hours',
            end_offset       => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour')
    """)

    # DC — daily
    _x("""
        CREATE MATERIALIZED VIEW dc_readings_daily
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 day', time) AS bucket,
            battery_id,
            client_id,
            MIN(voltage)    AS min_voltage,
            MAX(voltage)    AS max_voltage,
            AVG(voltage)    AS avg_voltage,
            MIN(current)    AS min_current,
            MAX(current)    AS max_current,
            AVG(current)    AS avg_current,
            MAX(energy_wh) - MIN(energy_wh) AS energy_delta_wh,
            COUNT(*)        AS reading_count
        FROM dc_readings
        GROUP BY bucket, battery_id, client_id
        WITH NO DATA
    """)
    _x("""
        SELECT add_continuous_aggregate_policy('dc_readings_daily',
            start_offset     => INTERVAL '3 days',
            end_offset       => INTERVAL '1 day',
            schedule_interval => INTERVAL '1 day')
    """)

    # AC — hourly
    _x("""
        CREATE MATERIALIZED VIEW ac_readings_hourly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', time) AS bucket,
            ac_channel_id,
            client_id,
            MIN(voltage)      AS min_voltage,
            MAX(voltage)      AS max_voltage,
            AVG(voltage)      AS avg_voltage,
            AVG(current)      AS avg_current,
            AVG(power)        AS avg_power,
            MAX(energy_wh) - MIN(energy_wh) AS energy_delta_wh,
            AVG(frequency)    AS avg_frequency,
            AVG(power_factor) AS avg_power_factor,
            COUNT(*)          AS reading_count
        FROM ac_readings
        GROUP BY bucket, ac_channel_id, client_id
        WITH NO DATA
    """)
    _x("""
        SELECT add_continuous_aggregate_policy('ac_readings_hourly',
            start_offset     => INTERVAL '3 hours',
            end_offset       => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour')
    """)

    # AC — daily
    _x("""
        CREATE MATERIALIZED VIEW ac_readings_daily
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 day', time) AS bucket,
            ac_channel_id,
            client_id,
            MIN(voltage)      AS min_voltage,
            MAX(voltage)      AS max_voltage,
            AVG(voltage)      AS avg_voltage,
            AVG(current)      AS avg_current,
            AVG(power)        AS avg_power,
            MAX(energy_wh) - MIN(energy_wh) AS energy_delta_wh,
            AVG(frequency)    AS avg_frequency,
            AVG(power_factor) AS avg_power_factor,
            COUNT(*)          AS reading_count
        FROM ac_readings
        GROUP BY bucket, ac_channel_id, client_id
        WITH NO DATA
    """)
    _x("""
        SELECT add_continuous_aggregate_policy('ac_readings_daily',
            start_offset     => INTERVAL '3 days',
            end_offset       => INTERVAL '1 day',
            schedule_interval => INTERVAL '1 day')
    """)


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------

def downgrade() -> None:
    _x("DROP MATERIALIZED VIEW IF EXISTS ac_readings_daily     CASCADE")
    _x("DROP MATERIALIZED VIEW IF EXISTS ac_readings_hourly    CASCADE")
    _x("DROP MATERIALIZED VIEW IF EXISTS dc_readings_daily     CASCADE")
    _x("DROP MATERIALIZED VIEW IF EXISTS dc_readings_hourly    CASCADE")
    _x("DROP TABLE IF EXISTS events          CASCADE")
    _x("DROP TABLE IF EXISTS sensor_readings CASCADE")
    _x("DROP TABLE IF EXISTS ac_readings     CASCADE")
    _x("DROP TABLE IF EXISTS dc_readings     CASCADE")
    _x("DROP TABLE IF EXISTS rs485_sensors   CASCADE")
    _x("DROP TABLE IF EXISTS ac_channels     CASCADE")
    _x("DROP TABLE IF EXISTS batteries       CASCADE")
    _x("DROP TABLE IF EXISTS appliances      CASCADE")
    _x("DROP TABLE IF EXISTS sites           CASCADE")
    _x("DROP TABLE IF EXISTS users           CASCADE")
    _x("DROP TABLE IF EXISTS clients         CASCADE")
    _x("DROP TYPE IF EXISTS event_severity   CASCADE")
    _x("DROP TYPE IF EXISTS event_kind       CASCADE")
    _x("DROP TYPE IF EXISTS ac_channel_role  CASCADE")
    _x("DROP TYPE IF EXISTS user_role        CASCADE")
