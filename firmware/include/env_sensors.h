#pragma once
#include <Arduino.h>

// ─────────────────────────────────────────────────────────────────────────────
//  Optional RS485 environmental sensors (same bus, same ModbusMaster node).
//  Each sensor type has its own struct + read function.
//  Adding a new type: add struct here, add read fn in env_sensors.cpp,
//  wire it in main.cpp under  #if SLAVE_ID_XXX != 0.
// ─────────────────────────────────────────────────────────────────────────────

// XY-MD02 / SHT20  — temperature & humidity
struct TempHumData {
    float temperature_c;
    float humidity_pct;
};

// Generic H₂ gas detector
struct GasH2Data {
    float ppm;
    bool  alarm;
};

// Call once in setup() — no hardware init needed (UART2 already started by pzem_init).
void envSensors_init();

bool tempHum_read(uint8_t slaveId, TempHumData &out);
bool gasH2_read(uint8_t slaveId, GasH2Data &out);

// ── Future sensor template ───────────────────────────────────────────────────
// struct NewSensorData { ... };
// bool newSensor_read(uint8_t slaveId, NewSensorData &out);
