/*
 * =========================================================================================
 * Proyecto: Monitoreo Inalámbrico de Gases con MiCS-5524 y ESP32-S3 (Tesis UTEC 2026)
 * Tarjeta: ESP32-S3-DevKitC-1 (Módulo Sparkle IoT XH-S3E N16R8)
 * 
 * Modo de Operación: Servidor Web Wi-Fi Autónomo (Punto de Acceso SoftAP)
 * Red Wi-Fi: ESP32-GasSensor (Sin contraseña)
 * IP de Acceso: http://192.168.4.1
 * 
 * Distribución de pines validada:
 * - OUT (A0): GPIO 4 (ADC1 canal 3)
 * - EN (Power): Desconectado (al aire) o GPIO 5 en LOW
 * - VCC: 5.0V (DevKit V1 externo)
 * - GND: GND común compartido
 * =========================================================================================
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>

const int PIN_SENSOR = 4;    // GPIO 4 (ADC1_CH3)
const int PIN_EN     = 5;    // GPIO 5 (Active-LOW)

const float VCC = 5.00;      // Voltaje de alimentación del sensor
const float RL  = 820.0;     // Resistencia de carga (820 Ohms)

// Variables de medición y calibración
float R0 = 10000.0;          // Valor basal de referencia inicial en Ohms
bool sensorHabilitado = true;

// Filtros digitales
const int VENTANA_MEDIANA = 5;
float bufferMediana[VENTANA_MEDIANA];
int indiceMediana = 0;
bool bufferLleno = false;

float valorEMA = 0.0;
const float ALFA_EMA = 0.20; // Suavizado exponencial

float vRawGlobal = 0.0;
float vMedianaGlobal = 0.0;
float vEmaGlobal = 0.0;
float rsGlobal = 0.0;
float ratioGlobal = 1.0;

// Servidor Web en puerto 80
WebServer server(80);

// Función para ordenar arreglo (mediana móvil)
void ordenar(float a[], int n) {
  for (int i = 0; i < n - 1; ++i) {
    for (int j = 0; j < n - 1 - i; ++j) {
      if (a[j] > a[j + 1]) {
        float temp = a[j];
        a[j] = a[j + 1];
        a[j + 1] = temp;
      }
    }
  }
}

float obtenerMediana(float nuevoValor) {
  bufferMediana[indiceMediana] = nuevoValor;
  indiceMediana = (indiceMediana + 1) % VENTANA_MEDIANA;
  if (indiceMediana == 0) bufferLleno = true;

  int elementos = bufferLleno ? VENTANA_MEDIANA : indiceMediana;
  float copia[VENTANA_MEDIANA];
  for (int i = 0; i < elementos; i++) copia[i] = bufferMediana[i];
  
  ordenar(copia, elementos);
  return copia[elementos / 2];
}

void calibrarR0() {
  const int MUESTRAS = 60;
  long sumaMV = 0;
  for (int i = 0; i < MUESTRAS; i++) {
    sumaMV += analogReadMilliVolts(PIN_SENSOR);
    delay(25);
  }
  float vProm = (sumaMV / (float)MUESTRAS) / 1000.0;
  if (vProm < 0.01) vProm = 0.01;
  
  R0 = RL * ((VCC - vProm) / vProm);
  Serial.printf("{\"status\":\"calibrado\",\"r0\":%.2f,\"v_clean\":%.3f}\n", R0, vProm);
}

// HTML Dashboard integrado en la memoria Flash
const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Telemetría Inalámbrica MiCS-5524 | ESP32-S3</title>
  <style>
    :root {
      --bg-primary: #0f172a;
      --bg-card: #1e293b;
      --border-color: #334155;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --accent-blue: #38bdf8;
      --accent-green: #4ade80;
      --accent-purple: #c084fc;
      --accent-orange: #fb923c;
      --accent-red: #f87171;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, sans-serif; }
    body { background-color: var(--bg-primary); color: var(--text-main); min-height: 100vh; padding: 15px; }
    header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 15px; border-bottom: 1px solid var(--border-color); margin-bottom: 15px; flex-wrap: wrap; gap: 10px; }
    .title-group h1 { font-size: 1.3rem; color: var(--accent-blue); }
    .title-group p { font-size: 0.8rem; color: var(--text-muted); }
    .badge { background: rgba(74, 222, 128, 0.15); color: var(--accent-green); border: 1px solid var(--accent-green); padding: 4px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }
    button { background: #334155; color: white; border: 1px solid var(--border-color); padding: 8px 14px; border-radius: 6px; font-size: 0.85rem; cursor: pointer; transition: 0.2s; }
    button:hover { background: #475569; }
    button.btn-success { background: #166534; border-color: #4ade80; font-weight: 600; }
    button.btn-success:hover { background: #14532d; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 15px; }
    .card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 8px; padding: 12px; }
    .card .label { font-size: 0.7rem; text-transform: uppercase; color: var(--text-muted); }
    .card .value { font-size: 1.6rem; font-weight: 700; margin: 4px 0; }
    .card .subtext { font-size: 0.75rem; color: var(--text-muted); }
    .chart-box { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 8px; padding: 12px; margin-bottom: 15px; }
    .legend { display: flex; gap: 15px; font-size: 0.8rem; margin-bottom: 8px; }
    .legend-item { display: flex; align-items: center; gap: 5px; }
    .legend-color { width: 10px; height: 10px; border-radius: 2px; }
    canvas { width: 100%; height: 320px; background: #090d16; border-radius: 4px; display: block; }
    .meter { height: 8px; background: #334155; border-radius: 4px; overflow: hidden; margin-top: 6px; }
    .meter-fill { height: 100%; width: 0%; background: linear-gradient(90deg, #4ade80, #facc15, #f87171); transition: width 0.1s; }
  </style>
</head>
<body>
  <header>
    <div class="title-group">
      <h1>Telemetría Inalámbrica MiCS-5524 (Wi-Fi)</h1>
      <p>ESP32-S3 SoftAP | Monitoreo de Gases Tesis UTEC 2026</p>
    </div>
    <div style="display:flex; gap:10px; align-items:center;">
      <div class="badge">● Wi-Fi Conectado</div>
      <button id="btnCalib" class="btn-success">🎯 Calibrar R0</button>
      <button id="btnCSV">📥 Descargar CSV</button>
    </div>
  </header>

  <div class="grid">
    <div class="card">
      <div class="label">Voltaje EMA</div>
      <div id="txtVEma" class="value" style="color:var(--accent-blue)">0.000 V</div>
      <div id="txtVRaw" class="subtext">Raw: 0.000 V | Med: 0.000 V</div>
    </div>
    <div class="card">
      <div class="label">Resistencia Rs</div>
      <div id="txtRs" class="value" style="color:var(--accent-purple)">0.0 kΩ</div>
      <div class="subtext">R_L: 820 Ω</div>
    </div>
    <div class="card">
      <div class="label">Línea Base R0</div>
      <div id="txtR0" class="value" style="color:var(--accent-green)">10.0 kΩ</div>
      <div class="subtext">Referencia Aire Limpio</div>
    </div>
    <div class="card">
      <div class="label">Ratio Rs / R0</div>
      <div id="txtRatio" class="value" style="color:var(--accent-orange)">1.000</div>
      <div class="meter"><div id="meterFill" class="meter-fill"></div></div>
      <div id="txtDeteccion" class="subtext" style="margin-top:3px">Detección: 0%</div>
    </div>
  </div>

  <div class="chart-box">
    <div class="legend">
      <div class="legend-item"><div class="legend-color" style="background:#f87171"></div> Señal Cruda (Raw)</div>
      <div class="legend-item"><div class="legend-color" style="background:#facc15"></div> Mediana (N=5)</div>
      <div class="legend-item"><div class="legend-color" style="background:#38bdf8"></div> EMA (α=0.20)</div>
    </div>
    <canvas id="cvs"></canvas>
  </div>

  <script>
    const MAX_PTS = 300;
    let history = [];
    let csvData = [];
    const canvas = document.getElementById('cvs');
    const ctx = canvas.getContext('2d');

    function resize() {
      canvas.width = canvas.clientWidth * window.devicePixelRatio;
      canvas.height = canvas.clientHeight * window.devicePixelRatio;
    }
    window.addEventListener('resize', resize);
    resize();

    function draw() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const w = canvas.width, h = canvas.height, pad = 35 * window.devicePixelRatio;
      const maxV = 3.5;

      ctx.strokeStyle = '#1e293b';
      ctx.lineWidth = 1;
      ctx.font = `${10 * window.devicePixelRatio}px monospace`;
      ctx.fillStyle = '#64748b';

      for (let v = 0; v <= maxV; v += 0.5) {
        const y = h - pad - (v / maxV) * (h - 2 * pad);
        ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(w - pad, y); ctx.stroke();
        ctx.fillText(v.toFixed(1) + ' V', 4, y + 4);
      }

      if (history.length < 2) return;
      const stepX = (w - 2 * pad) / (MAX_PTS - 1);

      function plot(k, col, lw) {
        ctx.strokeStyle = col;
        ctx.lineWidth = lw * window.devicePixelRatio;
        ctx.beginPath();
        for (let i = 0; i < history.length; i++) {
          const x = pad + i * stepX;
          const y = h - pad - (Math.min(Math.max(history[i][k], 0), maxV) / maxV) * (h - 2 * pad);
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();
      }

      plot('v_raw', '#f87171', 1.0);
      plot('v_med', '#facc15', 1.5);
      plot('v_ema', '#38bdf8', 2.5);
    }

    async function pollData() {
      try {
        const res = await fetch('/data');
        if (!res.ok) return;
        const d = await res.json();

        document.getElementById('txtVEma').innerText = d.v_ema.toFixed(3) + ' V';
        document.getElementById('txtVRaw').innerText = `Raw: ${d.v_raw.toFixed(3)} V | Med: ${d.v_med.toFixed(3)} V`;
        document.getElementById('txtRs').innerText = (d.rs / 1000.0).toFixed(2) + ' kΩ';
        document.getElementById('txtR0').innerText = (d.r0 / 1000.0).toFixed(2) + ' kΩ';
        document.getElementById('txtRatio').innerText = d.ratio.toFixed(3);

        let det = Math.max(0, Math.min(100, Math.round((1.0 - d.ratio) * 125)));
        document.getElementById('txtDeteccion').innerText = `Detección: ${det}%`;
        document.getElementById('meterFill').style.width = det + '%';

        history.push({ v_raw: d.v_raw, v_med: d.v_med, v_ema: d.v_ema });
        if (history.length > MAX_PTS) history.shift();

        csvData.push({ t: new Date().toISOString(), ...d });
        draw();
      } catch (e) {}
    }

    setInterval(pollData, 100);

    document.getElementById('btnCalib').onclick = async () => {
      await fetch('/calibrate');
      alert('R0 Calibrado en Aire Limpio');
    };

    document.getElementById('btnCSV').onclick = () => {
      if (!csvData.length) return alert('Sin datos');
      let csv = 'Timestamp,V_Raw,V_Mediana,V_EMA,Rs,R0,Ratio\n';
      csvData.forEach(r => csv += `${r.t},${r.v_raw},${r.v_med},${r.v_ema},${r.rs},${r.r0},${r.ratio}\n`);
      const blob = new Blob([csv], { type: 'text/csv' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `datos_gas_wifi_${Date.now()}.csv`;
      a.click();
    };
  </script>
</body>
</html>
)rawliteral";

void handleRoot() {
  server.send_P(200, "text/html", INDEX_HTML);
}

void handleData() {
  String json = "{";
  json += "\"v_raw\":" + String(vRawGlobal, 3) + ",";
  json += "\"v_med\":" + String(vMedianaGlobal, 3) + ",";
  json += "\"v_ema\":" + String(vEmaGlobal, 3) + ",";
  json += "\"rs\":" + String(rsGlobal, 1) + ",";
  json += "\"r0\":" + String(R0, 1) + ",";
  json += "\"ratio\":" + String(ratioGlobal, 3);
  json += "}";
  server.send(200, "application/json", json);
}

void handleCalibrate() {
  calibrarR0();
  server.send(200, "application/json", "{\"status\":\"ok\",\"r0\":" + String(R0, 1) + "}");
}

void setup() {
  Serial.begin(115200);

  pinMode(PIN_EN, OUTPUT);
  digitalWrite(PIN_EN, LOW); // Active-LOW encendido
  sensorHabilitado = true;

  pinMode(PIN_SENSOR, INPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(PIN_SENSOR, ADC_11db);

  for (int i = 0; i < VENTANA_MEDIANA; i++) bufferMediana[i] = 0.0;
  delay(300);
  float primerV = analogReadMilliVolts(PIN_SENSOR) / 1000.0;
  valorEMA = primerV;
  for (int i = 0; i < VENTANA_MEDIANA; i++) bufferMediana[i] = primerV;
  bufferLleno = true;

  // Iniciar Punto de Acceso Wi-Fi propio (SoftAP)
  Serial.println("\nIniciando punto de acceso Wi-Fi...");
  WiFi.mode(WIFI_AP);
  WiFi.softAP("ESP32-GasSensor"); // Red abierta sin contrasena

  IPAddress myIP = WiFi.softAPIP();
  Serial.print("Punto de Acceso listo. IP: ");
  Serial.println(myIP);

  // Configurar rutas del Servidor Web
  server.on("/", HTTP_GET, handleRoot);
  server.on("/data", HTTP_GET, handleData);
  server.on("/calibrate", HTTP_GET, handleCalibrate);
  server.begin();
  Serial.println("Servidor Web HTTP iniciado en puerto 80.");
}

unsigned long ultimoMuestreo = 0;
const unsigned long INTERVALO_MS = 100; // 10 Hz

void loop() {
  // Comandos recibidos por puerto Serial (ej. tecla [C] desde el visor Python)
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.equalsIgnoreCase("CALIBRATE") || cmd.equalsIgnoreCase("C")) {
      calibrarR0();
    }
  }

  // Atender peticiones de clientes Wi-Fi
  server.handleClient();

  // Muestreo analógico y filtros digitales a 10 Hz
  unsigned long ahora = millis();
  if (ahora - ultimoMuestreo >= INTERVALO_MS) {
    ultimoMuestreo = ahora;

    int rawADC = analogRead(PIN_SENSOR);
    float vRaw = analogReadMilliVolts(PIN_SENSOR) / 1000.0;

    if (vRaw <= 0.001 && rawADC > 0) {
      vRaw = (rawADC / 4095.0) * 3.1;
    }

    float vMediana = obtenerMediana(vRaw);
    valorEMA = (ALFA_EMA * vMediana) + ((1.0 - ALFA_EMA) * valorEMA);

    float vEfectivo = valorEMA;
    if (vEfectivo < 0.01) vEfectivo = 0.01;
    if (vEfectivo > (VCC - 0.02)) vEfectivo = VCC - 0.02;

    float rs = RL * ((VCC - vEfectivo) / vEfectivo);
    float ratio = rs / (R0 > 0 ? R0 : 10000.0);

    // Actualizar variables globales para el servidor Web
    vRawGlobal = vRaw;
    vMedianaGlobal = vMediana;
    vEmaGlobal = valorEMA;
    rsGlobal = rs;
    ratioGlobal = ratio;

    // Tambien transmitir por serial para depuracion
    Serial.printf("{\"v_raw\":%.3f,\"v_med\":%.3f,\"v_ema\":%.3f,\"rs\":%.1f,\"r0\":%.1f,\"ratio\":%.3f}\n",
                  vRaw, vMediana, valorEMA, rs, R0, ratio);
  }
}
