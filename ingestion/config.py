from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Postgres (direct — ingestion connects as superuser to bypass RLS)
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_user: str = "batmonai"
    postgres_password: str
    postgres_db: str = "batmonai"

    # MQTT
    mqtt_host: str = "mosquitto"
    mqtt_port_tls: int = 8883
    mqtt_username: str = "ingestion"
    mqtt_password: str = ""
    mqtt_ca_cert: str = "/mosquitto/certs/ca.crt"
    # Set true in dev if cert hostname doesn't match (should not be needed with SANs)
    mqtt_tls_insecure: bool = False

    # Timing
    publish_interval_seconds: int = 10
    offline_multiplier: int = 3

    # SMTP (for event notifications — mirrors backend .env)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_tls: bool = True

    @property
    def offline_threshold_seconds(self) -> int:
        return self.publish_interval_seconds * self.offline_multiplier
