#include "env_sensors.h"
#include "pzem.h"   // shares g_node + Serial2
#include "config.h"

void envSensors_init() {
    // UART2 is already started by pzem_init().  Nothing extra needed.
}

// XY-MD02 SHT20 — input registers FC=0x04
// 0x0001  Temperature × 10  (signed 16-bit, °C × 10 → e.g. 256 = 25.6 °C)
// 0x0002  Humidity    × 10  (unsigned, e.g. 615 = 61.5 %)
bool tempHum_read(uint8_t slaveId, TempHumData &out) {
    for (int attempt = 0; attempt < 2; ++attempt) {
        g_node.begin(slaveId, Serial2);
        delay(10);
        uint8_t result = g_node.readInputRegisters(0x0001, 2);
        if (result == ModbusMaster::ku8MBSuccess) {
            // Temperature is signed — cast through int16_t
            int16_t rawT     = (int16_t)g_node.getResponseBuffer(0);
            out.temperature_c = rawT * 0.1f;
            out.humidity_pct  = g_node.getResponseBuffer(1) * 0.1f;
            return true;
        }
        Serial.printf("[temp_hum] slave=%d err=0x%02X attempt=%d\n",
                      slaveId, result, attempt + 1);
        delay(50);
    }
    return false;
}

// Generic H₂ gas detector — input registers FC=0x04
// 0x0000  PPM   (0–10000)
// 0x0001  Alarm flag (0 = OK, 1 = alarm)
// Adjust start address if your specific module differs.
bool gasH2_read(uint8_t slaveId, GasH2Data &out) {
    for (int attempt = 0; attempt < 2; ++attempt) {
        g_node.begin(slaveId, Serial2);
        delay(10);
        uint8_t result = g_node.readInputRegisters(0x0000, 2);
        if (result == ModbusMaster::ku8MBSuccess) {
            out.ppm   = (float)g_node.getResponseBuffer(0);
            out.alarm = g_node.getResponseBuffer(1) != 0;
            return true;
        }
        Serial.printf("[gas_h2] slave=%d err=0x%02X attempt=%d\n",
                      slaveId, result, attempt + 1);
        delay(50);
    }
    return false;
}

// ── Future sensor template ───────────────────────────────────────────────────
// bool newSensor_read(uint8_t slaveId, NewSensorData &out) {
//     g_node.begin(slaveId, Serial2);
//     delay(10);
//     uint8_t result = g_node.readInputRegisters(0x0000, N);
//     if (result != ModbusMaster::ku8MBSuccess) return false;
//     out.field = g_node.getResponseBuffer(0) * SCALE;
//     return true;
// }
