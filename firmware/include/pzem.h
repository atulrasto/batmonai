#pragma once
#include <Arduino.h>
#include <ModbusMaster.h>

// Shared ModbusMaster node — one node, swap slave ID per read.
extern ModbusMaster g_node;

struct Pzem017Data {
    float    voltage;      // V  (0.01 V resolution)
    float    current;      // A  (0.01 A) — raw magnitude, sign applied in caller
    float    power;        // W  (0.1 W)
    float    energy_wh;    // Wh (1 Wh)
    uint16_t alarm_flags;  // bits: [0]=high-V alarm, [1]=low-V alarm
};

struct Pzem004tData {
    float    voltage;       // V   (0.1 V)
    float    current;       // A   (0.001 A)
    float    power;         // W   (0.1 W)
    float    energy_wh;     // Wh  (1 Wh)
    float    frequency;     // Hz  (0.1 Hz)
    float    power_factor;  // 0–1 (0.01)
    uint16_t alarm;
};

// Call once in setup() — initialises UART2 and DE/RE pin.
void pzem_init(HardwareSerial &serial);

// Returns true on successful read.  Retries once on failure.
bool pzem017_read(uint8_t slaveId, Pzem017Data &out);
bool pzem004t_read(uint8_t slaveId, Pzem004tData &out);
