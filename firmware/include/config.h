#pragma once

// ─────────────────────────────────────────────────────────────────────────────
//  batmonai firmware — compile-time hardware constants
//
//  Device-specific values (WiFi, broker, UIDs, device secret) are NOT here.
//  They are stored in NVS and written via the browser provisioning tool.
//  This binary is identical for every unit of the same board revision.
// ─────────────────────────────────────────────────────────────────────────────

// ── Firmware version ─────────────────────────────────────────────────────────
#define FW_VERSION "1.0.0"

// ── Provisioning trigger ──────────────────────────────────────────────────────
// Hold this pin LOW at boot to force re-provisioning (GPIO0 = BOOT button).
#define PROV_TRIGGER_PIN    0

// ── RS485 / UART2 pins (fixed by PCB layout) ─────────────────────────────────
#define RS485_RX_PIN        16   // RX2 → RO on RS485 module
#define RS485_TX_PIN        17   // TX2 → DI on RS485 module
#define RS485_DE_RE_PIN      4   // DE + RE tied → direction control
#define RS485_BAUD        9600

// ── Modbus slave IDs — match server .env and DB modbus_addr columns ───────────
//
//   Server .env key       Slave ID   Device
//   INVERTER_SLAVE_ID        1       PZEM-004T  (AC inverter)
//   BATTERY1_SLAVE_ID        2       PZEM-017   (DC battery 1)
//   BATTERY2_SLAVE_ID        3       PZEM-017   (DC battery 2)
//   TEMPERATURE_SLAVE_ID     4       XY-MD02    (SHT20 temp/humidity)
//   HYDROGEN_SLAVE_ID        5       H2 gas sensor
//
// Set any ID to 0 to disable that sensor at compile time.
#define SLAVE_ID_INVERTER    1
#define SLAVE_ID_BATTERY1    2
#define SLAVE_ID_BATTERY2    3
#define SLAVE_ID_TEMP_HUM    4   // 0 = not installed
#define SLAVE_ID_GAS_H2      5   // 0 = not installed

// ── Future sensor ─────────────────────────────────────────────────────────────
// 1. Add SLAVE_ID_XXX here  (0 to disable)
// 2. Add struct + read fn   in env_sensors.h / env_sensors.cpp
// 3. Add JSON block          in main.cpp  under  #if SLAVE_ID_XXX != 0

// ── PZEM-017 shunt settings (board-revision specific, same for all units) ─────
#define BATTERY1_SHUNT_A          100
#define BATTERY2_SHUNT_A          100

// Current sign (+1 or -1).  Discharge must be negative per MQTT contract.
// Flip to -1 if the shunt is wired so PZEM reports positive on discharge.
#define BATTERY1_CURRENT_SIGN     1
#define BATTERY2_CURRENT_SIGN     1

// ── MQTT CA certificate (deployment-wide, same broker for all units) ──────────
// Dev: leave this commented out; set tls_insecure=true during provisioning.
// Prod: uncomment and paste the broker's CA PEM string.
// #define MQTT_CA_CERT "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----\n"

// ── Store-and-forward buffer ──────────────────────────────────────────────────
#define BUFFER_MAX_FRAMES   60   // ~10 min at 10 s interval
#define PUBLISH_INTERVAL_MS 10000
