/*
 * =========================================================================================
 * PROYECTO: Hexápodo Secundario - Telemetría de Gases MiCS-5524 (Tesis UTEC 2026)
 * MODALIDAD: Modo Estación (STA) vinculado al Hotspot de Raspberry Pi 5 ("aleskypi-5")
 * 
 * Hardware: ESP32-S3 (DevKitC-1 N16R8) + Sensor Semiconductor MiCS-5524
 * - OUT (A0): GPIO 4 (ADC1_CH3)
 * - EN (Power): GPIO 5 (o desconectado con pull-down)
 * - VCC: 5.0V (Alimentación externa de calefactor)
 * - GND: Común con ESP32-S3
 * 
 * Protocolos de Comunicación:
 * - UDP Port 5005: Transmisión cíclica a 20 Hz hacia Raspberry Pi (10.42.0.1:5005)
 * - HTTP Port 80: Endpoints /data (JSON), /gas (Resumen), /calibrate (Auto-cero R0)
 * =========================================================================================
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <WebServer.h>

// Credenciales del Hotspot emitido por la Raspberry Pi 5
const char* WIFI_SSID     = "aleskypi-5";
const char* WIFI_PASSWORD = "alesky69";

// Destino de Telemetría UDP (Raspberry Pi 5)
const char* RPI_TARGET_IP = "10.42.0.1";
const int   UDP_PORT      = 5005;

// Pines de Hardware
const int PIN_SENSOR = 4;    // GPIO 4 (ADC1_CH3)
const int PIN_EN     = 5;    // GPIO 5 (Active-LOW para encendido de calefactor)

// Constantes físicas del sensor MiCS-5524
const float VCC = 5.00;      // Voltaje de alimentación del sensor
const float RL  = 820.0;     // Resistencia de carga (820 Ohms en módulo Adafruit/CJMCU)

// Parámetros de Calibración
float R0 = 26000.0;          // Línea base en aire limpio (Ohms). Ajustable con /calibrate
bool  calibrando = false;

// Filtros Digitales
const int VENTANA_MEDIANA = 5;
float bufferMediana[VENTANA_MEDIANA];
int   indiceMediana = 0;
bool  bufferLleno = false;

float valorEMA = 0.0;
const float ALFA_EMA = 0.20; // Filtro paso bajo IIR

// Objetos de Red
WiFiUDP udp;
WebServer server(80);

unsigned long ultimoEnvioUDP = 0;
const unsigned long INTERVALO_UDP_MS = 50; // 20 Hz (cada 50 ms)

// Función para ordenar y obtener la mediana
float obtenerMediana(float nuevoValor) {
  bufferMediana[indiceMediana] = nuevoValor;
  indiceMediana = (indiceMediana + 1) % VENTANA_MEDIANA;
  if (indiceMediana == 0) bufferLleno = true;

  int n = bufferLleno ? VENTANA_MEDIANA : indiceMediana;
  float copia[VENTANA_MEDIANA];
  for (int i = 0; i < n; i++) copia[i] = bufferMediana[i];

  for (int i = 0; i < n - 1; i++) {
    for (int j = i + 1; j < n; j++) {
      if (copia[i] > copia[j]) {
        float temp = copia[i];
        copia[i] = copia[j];
        copia[j] = temp;
      }
    }
  }
  return copia[n / 2];
}

// Variables globales de la última medición
float g_v_raw = 0.0;
float g_v_med = 0.0;
float g_v_ema = 0.0;
float g_rs    = 0.0;
float g_ratio = 1.0;
float g_gas_pct = 0.0;

// Construir JSON de telemetría
String generarJSON() {
  char buf[300];
  snprintf(buf, sizeof(buf),
    "{\"ip\":\"%s\",\"v_raw\":%.3f,\"v_med\":%.3f,\"v_ema\":%.3f,"
    "\"rs\":%.1f,\"r0\":%.1f,\"ratio\":%.3f,\"gas_pct\":%.1f,"
    "\"calibrating\":%s,\"fps\":0.0,\"width\":0,\"height\":0,"
    "\"cam_connected\":false,\"cam_streaming\":false,\"light\":false}",
    WiFi.localIP().toString().c_str(),
    g_v_raw, g_v_med, g_v_ema,
    g_rs, R0, g_ratio, g_gas_pct,
    calibrando ? "true" : "false"
  );
  return String(buf);
}

// Calibrar R0 en aire limpio
void ejecutarCalibracion() {
  calibrando = true;
  Serial.println("[CALIB] Iniciando calibración de R0 en aire limpio...");
  float sumaRs = 0.0;
  const int MUESTRAS = 30;
  for (int i = 0; i < MUESTRAS; i++) {
    float v = analogReadMilliVolts(PIN_SENSOR) / 1000.0;
    if (v > 0.01 && v < (VCC - 0.01)) {
      sumaRs += RL * ((VCC - v) / v);
    } else {
      sumaRs += 26000.0;
    }
    delay(50);
  }
  R0 = sumaRs / MUESTRAS;
  calibrando = false;
  Serial.printf("[CALIB] Nueva R0 fijada en: %.1f Ohms\n", R0);
}

// Endpoints HTTP
void handleRoot() {
  server.send(200, "application/json", generarJSON());
}

void handleCalibrate() {
  ejecutarCalibracion();
  server.send(200, "application/json", "{\"status\":\"ok\",\"r0\":" + String(R0, 1) + "}");
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=== INICIANDO SUBISTEMA DE GASES - MODO STA (RPi 5) ===");

  // Configuración de pines
  pinMode(PIN_SENSOR, INPUT);
  pinMode(PIN_EN, OUTPUT);
  digitalWrite(PIN_EN, LOW); // Active-LOW: enciende calefactor MEMS

  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);

  // Inicializar buffers
  for (int i = 0; i < VENTANA_MEDIANA; i++) bufferMediana[i] = 0.0;
  valorEMA = analogReadMilliVolts(PIN_SENSOR) / 1000.0;

  // Conexión Wi-Fi Modo Estación (STA)
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("[WIFI] Conectando a red Hotspot: %s ", WIFI_SSID);

  int intentos = 0;
  while (WiFi.status() != WL_CONNECTED && intentos < 30) {
    delay(500);
    Serial.print(".");
    intentos++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WIFI] ¡CONECTADO CON ÉXITO!");
    Serial.printf("[WIFI] IP asignada por RPi: %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("[WIFI] Gateway (RPi): %s\n", WiFi.gatewayIP().toString().c_str());
  } else {
    Serial.println("\n[WIFI] Advertencia: No se pudo conectar de inmediato. Reintentará en bucle...");
  }

  // Iniciar servidor HTTP y socket UDP
  server.on("/", handleRoot);
  server.on("/data", handleRoot);
  server.on("/gas", handleRoot);
  server.on("/calibrate", handleCalibrate);
  server.begin();
  Serial.println("[HTTP] Servidor activo en puerto 80");

  udp.begin(UDP_PORT);
  Serial.printf("[UDP] Transmisor activo hacia %s:%d\n", RPI_TARGET_IP, UDP_PORT);

  // Auto-calibración inicial tras precalentamiento breve
  Serial.println("[SENSOR] Esperando estabilización inicial del sensor (3 seg)...");
  delay(3000);
  ejecutarCalibracion();
  Serial.println("=== SISTEMA OPERATIVO Y TRANSMITIENDO A RPi ===");
}

void loop() {
  // Manejo de peticiones HTTP entrantes (calibración / lectura)
  server.handleClient();

  // Reconexión automática si se pierde Wi-Fi
  if (WiFi.status() != WL_CONNECTED) {
    static unsigned long lastReconnect = 0;
    if (millis() - lastReconnect > 3000) {
      lastReconnect = millis();
      WiFi.reconnect();
    }
    delay(10);
    return;
  }

  // Muestreo analógico con calibración de fábrica
  g_v_raw = analogReadMilliVolts(PIN_SENSOR) / 1000.0;
  g_v_med = obtenerMediana(g_v_raw);

  // Filtro EMA
  valorEMA = (ALFA_EMA * g_v_med) + ((1.0 - ALFA_EMA) * valorEMA);
  g_v_ema = valorEMA;

  // Resistencia del sensor Rs (Ohms)
  if (g_v_ema > 0.01 && g_v_ema < (VCC - 0.01)) {
    g_rs = RL * ((VCC - g_v_ema) / g_v_ema);
  } else if (g_v_ema >= (VCC - 0.01)) {
    g_rs = 10.0; // Saturación alta
  } else {
    g_rs = 100000.0; // Sin conducción
  }

  // Ratio R0 / Rs e Intensidad Porcentual
  if (g_rs > 0.1 && R0 > 0.1) {
    g_ratio = R0 / g_rs;
  } else {
    g_ratio = 1.0;
  }

  if (g_ratio > 1.0) {
    g_gas_pct = (1.0 - (g_rs / R0)) * 100.0;
  } else {
    g_gas_pct = 0.0;
  }
  if (g_gas_pct < 0.0) g_gas_pct = 0.0;
  if (g_gas_pct > 100.0) g_gas_pct = 100.0;

  // Enviar datagrama UDP a la Raspberry Pi a 20 Hz
  unsigned long ahora = millis();
  if (ahora - ultimoEnvioUDP >= INTERVALO_UDP_MS) {
    ultimoEnvioUDP = ahora;

    String jsonStr = generarJSON();

    udp.beginPacket(RPI_TARGET_IP, UDP_PORT);
    udp.write((const uint8_t*)jsonStr.c_str(), jsonStr.length());
    udp.endPacket();

    // Imprimir por Serial para monitoreo local
    Serial.println(jsonStr);
  }

  // Lectura de comandos por Serial
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'c' || c == 'C') {
      ejecutarCalibracion();
    }
  }

  delay(5);
}
