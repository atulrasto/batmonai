#include "pzem.h"
#include "config.h"

ModbusMaster g_node;
static HardwareSerial *g_serial = nullptr;

static void preTx()  { digitalWrite(RS485_DE_RE_PIN, HIGH); }
static void postTx() { digitalWrite(RS485_DE_RE_PIN, LOW);  }

void pzem_init(HardwareSerial &serial) {
    g_serial = &serial;
    serial.begin(RS485_BAUD, SERIAL_8N1, RS485_RX_PIN, RS485_TX_PIN);
    pinMode(RS485_DE_RE_PIN, OUTPUT);
    digitalWrite(RS485_DE_RE_PIN, LOW);
    g_node.preTransmission(preTx);
    g_node.postTransmission(postTx);
}

// PZEM-017 DC — input registers FC=0x04
// 0x0000 voltage  0.01 V
// 0x0001 current  0.01 A
// 0x0002-3 power  0.1 W  (32-bit, low word first)
// 0x0004-5 energy 1 Wh   (32-bit, low word first)
// 0x0006 high-V alarm
// 0x0007 low-V  alarm
bool pzem017_read(uint8_t slaveId, Pzem017Data &out) {
    for (int attempt = 0; attempt < 2; ++attempt) {
        g_node.begin(slaveId, *g_serial);
        delay(10);
        uint8_t result = g_node.readInputRegisters(0x0000, 8);
        if (result == ModbusMaster::ku8MBSuccess) {
            out.voltage    = g_node.getResponseBuffer(0) * 0.01f;
            out.current    = g_node.getResponseBuffer(1) * 0.01f;
            uint32_t pRaw  = (uint32_t)g_node.getResponseBuffer(2) |
                             ((uint32_t)g_node.getResponseBuffer(3) << 16);
            out.power      = pRaw * 0.1f;
            uint32_t eRaw  = (uint32_t)g_node.getResponseBuffer(4) |
                             ((uint32_t)g_node.getResponseBuffer(5) << 16);
            out.energy_wh  = (float)eRaw;
            out.alarm_flags = g_node.getResponseBuffer(6) |
                              (g_node.getResponseBuffer(7) << 8);
            return true;
        }
        Serial.printf("[pzem017] slave=%d err=0x%02X attempt=%d\n",
                      slaveId, result, attempt + 1);
        delay(50);
    }
    return false;
}

// PZEM-004T v3.0 RS485 — input registers FC=0x04
// 0x0000 voltage  0.1 V
// 0x0001 current_L + 0x0002 current_H   0.001 A  (32-bit)
// 0x0003 power_L  + 0x0004 power_H      0.1 W    (32-bit)
// 0x0005 energy_L + 0x0006 energy_H     1 Wh     (32-bit)
// 0x0007 frequency 0.1 Hz
// 0x0008 power factor 0.01
// 0x0009 alarm status
bool pzem004t_read(uint8_t slaveId, Pzem004tData &out) {
    for (int attempt = 0; attempt < 2; ++attempt) {
        g_node.begin(slaveId, *g_serial);
        delay(10);
        uint8_t result = g_node.readInputRegisters(0x0000, 10);
        if (result == ModbusMaster::ku8MBSuccess) {
            out.voltage      = g_node.getResponseBuffer(0) * 0.1f;
            uint32_t iRaw    = (uint32_t)g_node.getResponseBuffer(1) |
                               ((uint32_t)g_node.getResponseBuffer(2) << 16);
            out.current      = iRaw * 0.001f;
            uint32_t pRaw    = (uint32_t)g_node.getResponseBuffer(3) |
                               ((uint32_t)g_node.getResponseBuffer(4) << 16);
            out.power        = pRaw * 0.1f;
            uint32_t eRaw    = (uint32_t)g_node.getResponseBuffer(5) |
                               ((uint32_t)g_node.getResponseBuffer(6) << 16);
            out.energy_wh    = (float)eRaw;
            out.frequency    = g_node.getResponseBuffer(7) * 0.1f;
            out.power_factor = g_node.getResponseBuffer(8) * 0.01f;
            out.alarm        = g_node.getResponseBuffer(9);
            return true;
        }
        Serial.printf("[pzem004t] slave=%d err=0x%02X attempt=%d\n",
                      slaveId, result, attempt + 1);
        delay(50);
    }
    return false;
}
