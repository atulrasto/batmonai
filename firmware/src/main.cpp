#include <Arduino.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <time.h>

#include "config.h"
#include "pzem.h"
#include "env_sensors.h"
#include "buffer.h"

// ── Runtime config (loaded from NVS at boot) ──────────────────────────────────
static String g_wifiSsid, g_wifiPass;
static String g_applianceUid, g_deviceSecret;
static String g_brokerHost;
static int    g_brokerPort   = 8883;
static bool   g_tlsInsecure  = true;

// Derived UIDs — built from g_applianceUid after NVS load
static String g_battery1Uid, g_battery2Uid;
static String g_inverterUid;
static String g_tempHumUid;
static String g_gasH2Uid;

static char s_telemetryTopic[96];
static char s_statusTopic[96];

// ── MQTT + TLS ────────────────────────────────────────────────────────────────
static WiFiClientSecure tlsClient;
static PubSubClient     mqtt(tlsClient);
static PayloadBuffer    txBuffer;

static unsigned long s_lastPublish     = 0;
static unsigned long s_lastMqttAttempt = 0;

// ─────────────────────────────────────────────────────────────────────────────
//  Provisioning mode
//
//  Protocol (plain text, newline terminated, 115200 baud):
//    Device → Host : "PROV:READY\n"
//    Host   → Device : JSON config + "\n"
//    Device → Host : "PROV:OK\n"   or   "PROV:ERR:<reason>\n"
//
//  JSON keys:
//    wifi_ssid, wifi_pass, appliance_uid, device_secret,
//    broker_host, broker_port, tls_insecure
// ─────────────────────────────────────────────────────────────────────────────
static void runProvisioningMode() {
    Serial.println("\n[prov] Provisioning mode — waiting for config JSON (60 s)...");
    Serial.println("PROV:READY");

    String line;
    uint32_t t0 = millis();
    while (millis() - t0 < 60000) {
        while (Serial.available()) {
            char c = Serial.read();
            if (c == '\n') goto got_line;
            if (c != '\r') line += c;
        }
        delay(5);
    }
    Serial.println("PROV:ERR:TIMEOUT");
    return;

got_line:
    Serial.printf("[prov] Received %u bytes\n", line.length());
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, line);
    if (err) {
        Serial.printf("PROV:ERR:JSON(%s)\n", err.c_str());
        return;
    }

    const char *ssid     = doc["wifi_ssid"]     | "";
    const char *pass     = doc["wifi_pass"]     | "";
    const char *appUid   = doc["appliance_uid"] | "";
    const char *secret   = doc["device_secret"] | "";
    const char *broker   = doc["broker_host"]   | "batmon.energymonai.com";
    int         port     = doc["broker_port"]   | 8883;
    bool        insecure = doc["tls_insecure"]  | true;

    if (strlen(ssid) == 0 || strlen(appUid) == 0 || strlen(secret) == 0) {
        Serial.println("PROV:ERR:MISSING_FIELDS");
        return;
    }

    Preferences prefs;
    prefs.begin("batmonai", false);
    prefs.putString("wifi_ssid",      ssid);
    prefs.putString("wifi_pass",      pass);
    prefs.putString("appliance_uid",  appUid);
    prefs.putString("device_secret",  secret);
    prefs.putString("broker_host",    broker);
    prefs.putInt   ("broker_port",    port);
    prefs.putBool  ("tls_insecure",   insecure);
    prefs.putBool  ("provisioned",    true);
    prefs.end();

    Serial.println("PROV:OK");
    delay(500);
    ESP.restart();
}

// ─────────────────────────────────────────────────────────────────────────────
//  Load NVS config + derive UIDs
// ─────────────────────────────────────────────────────────────────────────────
static bool loadConfig() {
    Preferences prefs;
    prefs.begin("batmonai", true);   // read-only
    bool provisioned = prefs.getBool("provisioned", false);
    if (!provisioned) { prefs.end(); return false; }

    g_wifiSsid      = prefs.getString("wifi_ssid",      "");
    g_wifiPass      = prefs.getString("wifi_pass",      "");
    g_applianceUid  = prefs.getString("appliance_uid",  "");
    g_deviceSecret  = prefs.getString("device_secret",  "");
    g_brokerHost    = prefs.getString("broker_host",    "batmon.energymonai.com");
    g_brokerPort    = prefs.getInt   ("broker_port",    8883);
    g_tlsInsecure   = prefs.getBool  ("tls_insecure",   true);
    prefs.end();

    if (g_wifiSsid.isEmpty() || g_applianceUid.isEmpty()) return false;

    // Derive child UIDs from appliance_uid — same naming convention as the server
    g_battery1Uid = g_applianceUid + "-bat1";
    g_battery2Uid = g_applianceUid + "-bat2";
    g_inverterUid = g_applianceUid + "-inv1";
    g_tempHumUid  = g_applianceUid + "-env1";
    g_gasH2Uid    = g_applianceUid + "-gas1";

    snprintf(s_telemetryTopic, sizeof(s_telemetryTopic),
             "batmon/%s/telemetry", g_applianceUid.c_str());
    snprintf(s_statusTopic, sizeof(s_statusTopic),
             "batmon/%s/status", g_applianceUid.c_str());

    return true;
}

// ── WiFi ──────────────────────────────────────────────────────────────────────
static void wifiConnect() {
    if (WiFi.status() == WL_CONNECTED) return;
    Serial.printf("[wifi] Connecting to %s", g_wifiSsid.c_str());
    WiFi.begin(g_wifiSsid.c_str(), g_wifiPass.c_str());
    uint32_t t0 = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) {
        delay(500);
        Serial.print('.');
    }
    Serial.printf("\n[wifi] %s\n",
        WiFi.status() == WL_CONNECTED
            ? WiFi.localIP().toString().c_str()
            : "Failed — will retry");
}

// ── MQTT ──────────────────────────────────────────────────────────────────────
static bool mqttConnect() {
    if (mqtt.connected()) return true;
    Serial.printf("[mqtt] Connecting to %s:%d\n", g_brokerHost.c_str(), g_brokerPort);
    bool ok = mqtt.connect(
        g_applianceUid.c_str(),
        g_applianceUid.c_str(),
        g_deviceSecret.c_str(),
        s_statusTopic, 0, true, "offline", true
    );
    if (ok) {
        mqtt.publish(s_statusTopic, "online", true);
        Serial.println("[mqtt] Connected");
    } else {
        Serial.printf("[mqtt] Failed rc=%d\n", mqtt.state());
    }
    return ok;
}

// ── Payload builder ───────────────────────────────────────────────────────────
static String buildPayload() {
    time_t now = time(nullptr);
    struct tm *utc = gmtime(&now);
    char ts[24];
    strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%SZ", utc);

    JsonDocument doc;
    doc["appliance_uid"] = g_applianceUid;
    doc["ts"]  = ts;
    doc["fw"]  = FW_VERSION;

    JsonArray dc = doc["dc"].to<JsonArray>();

    Pzem017Data b1;
    if (pzem017_read(SLAVE_ID_BATTERY1, b1)) {
        JsonObject o   = dc.add<JsonObject>();
        o["battery_uid"] = g_battery1Uid;
        o["addr"]  = SLAVE_ID_BATTERY1;
        o["v"]     = roundf(b1.voltage * 100.0f) / 100.0f;
        float i1   = b1.current * (float)BATTERY1_CURRENT_SIGN;
        o["i"]     = roundf(i1 * 100.0f) / 100.0f;
        o["p"]     = roundf(b1.power * 10.0f) / 10.0f;
        o["e"]     = b1.energy_wh;
        o["shunt"] = BATTERY1_SHUNT_A;
        o["alarm"] = b1.alarm_flags;
    }

    Pzem017Data b2;
    if (pzem017_read(SLAVE_ID_BATTERY2, b2)) {
        JsonObject o   = dc.add<JsonObject>();
        o["battery_uid"] = g_battery2Uid;
        o["addr"]  = SLAVE_ID_BATTERY2;
        o["v"]     = roundf(b2.voltage * 100.0f) / 100.0f;
        float i2   = b2.current * (float)BATTERY2_CURRENT_SIGN;
        o["i"]     = roundf(i2 * 100.0f) / 100.0f;
        o["p"]     = roundf(b2.power * 10.0f) / 10.0f;
        o["e"]     = b2.energy_wh;
        o["shunt"] = BATTERY2_SHUNT_A;
        o["alarm"] = b2.alarm_flags;
    }

    JsonArray ac = doc["ac"].to<JsonArray>();
    Pzem004tData inv;
    if (pzem004t_read(SLAVE_ID_INVERTER, inv)) {
        JsonObject o     = ac.add<JsonObject>();
        o["channel_uid"] = g_inverterUid;
        o["addr"]  = SLAVE_ID_INVERTER;
        o["v"]     = roundf(inv.voltage      * 10.0f)  / 10.0f;
        o["i"]     = roundf(inv.current      * 100.0f) / 100.0f;
        o["p"]     = roundf(inv.power        * 10.0f)  / 10.0f;
        o["e"]     = inv.energy_wh;
        o["freq"]  = roundf(inv.frequency    * 10.0f)  / 10.0f;
        o["pf"]    = roundf(inv.power_factor * 100.0f) / 100.0f;
    }

    JsonArray env = doc["env"].to<JsonArray>();

#if SLAVE_ID_TEMP_HUM != 0
    TempHumData th;
    if (tempHum_read(SLAVE_ID_TEMP_HUM, th)) {
        JsonObject o       = env.add<JsonObject>();
        o["sensor_uid"]    = g_tempHumUid;
        o["type"]          = "temp_humidity";
        o["addr"]          = SLAVE_ID_TEMP_HUM;
        o["temperature_c"] = roundf(th.temperature_c * 10.0f) / 10.0f;
        o["humidity_pct"]  = roundf(th.humidity_pct  * 10.0f) / 10.0f;
    }
#endif

#if SLAVE_ID_GAS_H2 != 0
    GasH2Data gas;
    if (gasH2_read(SLAVE_ID_GAS_H2, gas)) {
        JsonObject o    = env.add<JsonObject>();
        o["sensor_uid"] = g_gasH2Uid;
        o["type"]       = "gas_h2";
        o["addr"]       = SLAVE_ID_GAS_H2;
        o["ppm"]        = gas.ppm;
        o["alarm"]      = gas.alarm;
    }
#endif

    // ── Future sensor block — add here ────────────────────────────────────────
    // #if SLAVE_ID_NEW_SENSOR != 0
    //     NewSensorData ns;
    //     if (newSensor_read(SLAVE_ID_NEW_SENSOR, ns)) {
    //         JsonObject o    = env.add<JsonObject>();
    //         o["sensor_uid"] = g_applianceUid + "-xxx1";
    //         o["type"]       = "new_type";
    //         o["addr"]       = SLAVE_ID_NEW_SENSOR;
    //         o["field"]      = ns.field;
    //     }
    // #endif

    String out;
    serializeJson(doc, out);
    return out;
}

// ── Arduino setup ─────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.println("\n[boot] batmonai firmware " FW_VERSION);

    pzem_init(Serial2);
    envSensors_init();

    // Check provisioning trigger: BOOT button held LOW or NVS not yet provisioned
    pinMode(PROV_TRIGGER_PIN, INPUT_PULLUP);
    delay(100);
    bool triggerHeld = (digitalRead(PROV_TRIGGER_PIN) == LOW);
    bool configOk    = loadConfig();

    if (!configOk || triggerHeld) {
        if (triggerHeld) Serial.println("[boot] BOOT button held — entering provisioning");
        else             Serial.println("[boot] Not provisioned — entering provisioning");
        runProvisioningMode();
        // If provisioning times out or fails, continue with whatever is in NVS
        loadConfig();
    }

    if (g_applianceUid.isEmpty()) {
        Serial.println("[boot] FATAL: no appliance_uid — halting. Re-provision the device.");
        while (true) delay(1000);
    }

    Serial.printf("[boot] Appliance: %s\n", g_applianceUid.c_str());
    Serial.printf("[boot] Broker:    %s:%d\n", g_brokerHost.c_str(), g_brokerPort);

    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    wifiConnect();

    Serial.print("[ntp] Syncing");
    configTime(0, 0, "pool.ntp.org", "time.google.com");
    uint32_t t0 = millis();
    while (time(nullptr) < 1000000000UL && millis() - t0 < 15000) {
        delay(200);
        Serial.print('.');
    }
    Serial.printf("\n[ntp] %s\n",
        time(nullptr) > 1000000000UL ? "OK" : "TIMEOUT");

    if (g_tlsInsecure) {
        tlsClient.setInsecure();
        Serial.println("[tls] WARNING: cert validation disabled (dev mode)");
    } else {
#ifdef MQTT_CA_CERT
        tlsClient.setCACert(MQTT_CA_CERT);
        Serial.println("[tls] CA cert loaded");
#else
        Serial.println("[tls] WARNING: tls_insecure=false but no CA cert compiled in — falling back to insecure");
        tlsClient.setInsecure();
#endif
    }

    mqtt.setServer(g_brokerHost.c_str(), g_brokerPort);
    mqtt.setBufferSize(2048);
    mqttConnect();

    Serial.println("[setup] Ready");
}

// ── Arduino loop ──────────────────────────────────────────────────────────────
void loop() {
    if (WiFi.status() != WL_CONNECTED) {
        wifiConnect();
        delay(1000);
        return;
    }

    if (!mqtt.connected()) {
        unsigned long now = millis();
        if (now - s_lastMqttAttempt >= 5000) {
            s_lastMqttAttempt = now;
            mqttConnect();
        }
    }

    mqtt.loop();

    unsigned long now = millis();
    if (now - s_lastPublish >= PUBLISH_INTERVAL_MS) {
        s_lastPublish = now;
        String payload = buildPayload();
        Serial.printf("[pub] %u bytes | buf=%u\n", payload.length(), txBuffer.size());

        if (mqtt.connected()) {
            while (!txBuffer.empty()) {
                String frame = txBuffer.pop();
                if (!mqtt.publish(s_telemetryTopic, frame.c_str())) {
                    txBuffer.pushFront(frame);
                    break;
                }
            }
            if (!mqtt.publish(s_telemetryTopic, payload.c_str())) {
                txBuffer.push(payload);
            }
        } else {
            txBuffer.push(payload);
            Serial.printf("[buf] Offline — %u frames buffered\n", txBuffer.size());
        }
    }
}
