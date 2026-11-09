#include <Arduino.h>
#include <WiFi.h>
#include "esp_http_server.h"
#include "USB_STREAM.h"

// ==============================================================================
// CONFIGURACIÓN DE RED WI-FI (MODO ACCESO DIRECTO - SOFT AP)
// ==============================================================================
// El ESP32 crea su propia red Wi-Fi directamente para conectarte desde tu laptop.
const char* AP_SSID     = "ESP32-CAM-TEST";
const char* AP_PASSWORD = "12345678";

// ==============================================================================
// GESTIÓN DE MEMORIA Y BUFFERS PARA UVC (SRAM INTERNA COMPATIBLE CON USB DMA)
// ==============================================================================
// 55 KB es el tamaño estándar óptimo validado por Espressif para UVC en SRAM interna
#define UVC_BUF_SIZE (55 * 1024)

static uint8_t *s_xfer_buffer_a = NULL;
static uint8_t *s_xfer_buffer_b = NULL;
static uint8_t *s_frame_buffer  = NULL;

// Buffer protegido para servir fotogramas a la interfaz Web sin colisiones
static uint8_t *s_web_frame_buf = NULL;
static size_t   s_web_frame_len = 0;
static uint32_t s_frame_width   = 0;
static uint32_t s_frame_height  = 0;
static uint32_t s_frame_seq     = 0;
static SemaphoreHandle_t s_frame_mutex = NULL;

// Estado de la cámara y telemetría
static volatile bool s_camera_connected = false;
static uint32_t s_frame_count   = 0;
static uint32_t s_last_fps_time = 0;
static float    s_fps           = 0.0f;

static USB_STREAM *s_usb = NULL;
static httpd_handle_t s_http_server = NULL;

// ==============================================================================
// INTERFAZ WEB EMBEBIDA (HTML5 / CSS / JS)
// ==============================================================================
static const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ESP32-S3 | Monitor Cámara USB</title>
  <style>
    :root {
      --bg: #090d16;
      --card-bg: #131b2e;
      --panel-border: #1e293b;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --success: #22c55e;
      --danger: #ef4444;
      --text: #f8fafc;
      --text-muted: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { background-color: var(--bg); color: var(--text); min-height: 100vh; display: flex; flex-direction: column; align-items: center; padding: 24px 16px; }
    header { text-align: center; margin-bottom: 20px; }
    header h1 { font-size: 1.8rem; color: var(--accent); margin-bottom: 6px; }
    header p { color: var(--text-muted); font-size: 0.9rem; }
    
    .container { width: 100%; max-width: 820px; background: var(--card-bg); border: 1px solid var(--panel-border); border-radius: 12px; box-shadow: 0 12px 30px rgba(0,0,0,0.6); overflow: hidden; }
    .status-bar { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); background: #0d1424; padding: 12px 16px; border-bottom: 1px solid var(--panel-border); text-align: center; gap: 8px; }
    .stat-item span { display: block; font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
    .stat-item strong { font-size: 1.05rem; color: var(--text); display: inline-block; margin-top: 2px; }
    
    .badge { padding: 4px 12px; border-radius: 999px; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; display: inline-block; }
    .badge-ok { background: rgba(34, 197, 94, 0.2); color: var(--success); border: 1px solid var(--success); }
    .badge-err { background: rgba(239, 68, 68, 0.2); color: var(--danger); border: 1px solid var(--danger); }
    
    .viewer { position: relative; width: 100%; min-height: 420px; background: #020617; display: flex; align-items: center; justify-content: center; overflow: hidden; }
    .viewer img { width: 100%; height: auto; max-height: 560px; object-fit: contain; display: block; }
    
    .overlay-msg {
      position: absolute; top: 0; left: 0; width: 100%; height: 100%;
      background: rgba(9, 13, 22, 0.94);
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      padding: 30px 20px; text-align: center; gap: 12px; z-index: 10;
    }
    .overlay-icon { font-size: 3rem; }
    .overlay-title { font-size: 1.3rem; font-weight: 700; color: #f87171; }
    .overlay-desc { font-size: 0.92rem; color: #cbd5e1; max-width: 480px; line-height: 1.5; }
    .overlay-tip { font-size: 0.8rem; color: #64748b; background: #131b2e; padding: 8px 14px; border-radius: 6px; border: 1px solid #1e293b; margin-top: 6px; }

    .controls { display: flex; flex-wrap: wrap; justify-content: center; gap: 12px; padding: 14px 18px; background: #0d1424; border-top: 1px solid var(--panel-border); }
    button { background: #1e293b; color: var(--text); border: 1px solid #334155; padding: 10px 18px; border-radius: 8px; font-size: 0.88rem; font-weight: 600; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 6px; }
    button:hover { background: var(--accent); color: #090d16; border-color: var(--accent); }
    footer { margin-top: 20px; color: #64748b; font-size: 0.78rem; text-align: center; }
  </style>
</head>
<body>
  <header>
    <h1>📷 ESP32-S3 | Visor de Cámara USB UVC</h1>
    <p>Red Wi-Fi Directa: <strong>ESP32-CAM-TEST</strong> (IP: 192.168.4.1)</p>
  </header>

  <div class="container">
    <div class="status-bar">
      <div class="stat-item">
        <span>Hardware</span>
        <div style="margin-top: 3px;"><span id="cam-badge" class="badge badge-err">Desconectada</span></div>
      </div>
      <div class="stat-item">
        <span>Tasa de Cuadros</span>
        <strong id="fps-val" style="color: var(--accent);">0.0 FPS</strong>
      </div>
      <div class="stat-item">
        <span>Resolución</span>
        <strong id="res-val">-- x --</strong>
      </div>
      <div class="stat-item">
        <span>Fotograma</span>
        <strong id="size-val">0 KB</strong>
      </div>
    </div>

    <div class="viewer">
      <img id="stream-img" src="" alt="Transmisión UVC">
      
      <!-- Mensaje cuando la cámara no está conectada -->
      <div id="overlay" class="overlay-msg">
        <div class="overlay-icon">🔌</div>
        <div class="overlay-title">Cámara USB No Detectada</div>
        <div class="overlay-desc">
          El ESP32-S3 y la red inalámbrica están funcionando correctamente.<br>
          Para ver el video, conecta el módulo de cámara USB Tipo-C al <strong>puerto USB nativo (izquierdo)</strong>.
        </div>
        <div class="overlay-tip">
          💡 La transmisión se iniciará automáticamente en cuanto conectes la cámara, sin necesidad de reiniciar la placa.
        </div>
      </div>
    </div>

    <div class="controls">
      <button onclick="toggleStream()" id="btn-pause">⏸️ Pausar</button>
      <button onclick="reloadStream()">🔄 Recargar Stream</button>
      <button onclick="downloadSnapshot()">📸 Capturar Foto (JPEG)</button>
    </div>
  </div>

  <footer>UTEC 2026 | Arquitectura Robótica Cooperativa</footer>

  <script>
    let isStreaming = false;
    let cameraWasConnected = false;
    const img = document.getElementById('stream-img');
    const overlay = document.getElementById('overlay');
    const camBadge = document.getElementById('cam-badge');
    const fpsVal = document.getElementById('fps-val');
    const resVal = document.getElementById('res-val');
    const sizeVal = document.getElementById('size-val');
    const btnPause = document.getElementById('btn-pause');

    function startVideo() {
      img.src = "/stream?t=" + Date.now();
      isStreaming = true;
      btnPause.innerText = "⏸️ Pausar";
    }

    function stopVideo() {
      img.src = "";
      isStreaming = false;
      btnPause.innerText = "▶️ Reanudar";
    }

    function toggleStream() {
      if (isStreaming) {
        stopVideo();
      } else {
        startVideo();
      }
    }

    function reloadStream() {
      stopVideo();
      setTimeout(startVideo, 250);
    }

    function downloadSnapshot() {
      const a = document.createElement('a');
      a.href = '/snapshot?t=' + Date.now();
      a.download = 'captura_esp32_' + Date.now() + '.jpg';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }

    // Monitoreo periódico del estado del ESP32 cada 700 ms
    setInterval(async () => {
      try {
        const res = await fetch('/status', { signal: AbortSignal.timeout(1000) });
        if (!res.ok) throw new Error();
        const data = await res.json();

        if (data.connected) {
          camBadge.className = "badge badge-ok";
          camBadge.innerText = "Conectada";
          overlay.style.display = "none";

          if (!cameraWasConnected) {
            cameraWasConnected = true;
            startVideo();
          }
        } else {
          camBadge.className = "badge badge-err";
          camBadge.innerText = "Desconectada";
          overlay.style.display = "flex";

          if (cameraWasConnected) {
            cameraWasConnected = false;
            stopVideo();
          }
        }

        fpsVal.innerText = data.fps.toFixed(1) + " FPS";
        resVal.innerText = (data.width > 0) ? (data.width + "x" + data.height) : "-- x --";
        sizeVal.innerText = (data.size_bytes / 1024).toFixed(1) + " KB";
      } catch (e) {
        camBadge.className = "badge badge-err";
        camBadge.innerText = "Sin Enlace";
      }
    }, 700);
  </script>
</body>
</html>
)rawliteral";

// ==============================================================================
// CALLBACKS DE LA CÁMARA USB (UVC)
// ==============================================================================

static void onCameraFrameCallback(uvc_frame *frame, void *user_ptr) {
    if (!frame || !frame->data || frame->data_bytes == 0) return;

    if (xSemaphoreTake(s_frame_mutex, pdMS_TO_TICKS(15)) == pdTRUE) {
        if (s_web_frame_buf != NULL && frame->data_bytes <= UVC_BUF_SIZE) {
            memcpy(s_web_frame_buf, frame->data, frame->data_bytes);
            s_web_frame_len = frame->data_bytes;
            s_frame_width   = frame->width;
            s_frame_height  = frame->height;
            s_frame_seq     = frame->sequence;
            s_frame_count++;
        }
        xSemaphoreGive(s_frame_mutex);
    }
}

static void onUsbStateChange(usb_stream_state_t event, void *arg) {
    if (event == STREAM_CONNECTED) {
        s_camera_connected = true;
        Serial.println("\n[UVC HOST] >> Cámara USB detectada y conectada!");
    } else if (event == STREAM_DISCONNECTED) {
        s_camera_connected = false;
        Serial.println("\n[UVC HOST] >> Cámara USB desconectada. Esperando reconexión...");
    }
}

// ==============================================================================
// HANDLERS DEL SERVIDOR WEB HTTP
// ==============================================================================

static esp_err_t index_handler(httpd_req_t *req) {
    httpd_resp_set_type(req, "text/html");
    return httpd_resp_send(req, INDEX_HTML, HTTPD_RESP_USE_STRLEN);
}

static esp_err_t stream_handler(httpd_req_t *req) {
    if (!s_camera_connected) {
        httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "Camara no conectada");
        return ESP_FAIL;
    }

    char part_buf[128];
    static const char* _STREAM_CONTENT_TYPE = "multipart/x-mixed-replace; boundary=frame";
    static const char* _STREAM_BOUNDARY = "\r\n--frame\r\n";
    static const char* _STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

    httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

    uint8_t *temp_buf = (uint8_t *)malloc(UVC_BUF_SIZE);
    if (!temp_buf) {
        httpd_resp_send_500(req);
        return ESP_FAIL;
    }

    esp_err_t res = ESP_OK;
    uint32_t last_seq = 0;

    while (s_camera_connected) {
        size_t current_len = 0;
        bool is_new = false;

        if (xSemaphoreTake(s_frame_mutex, pdMS_TO_TICKS(25)) == pdTRUE) {
            if (s_frame_seq != last_seq && s_web_frame_len > 0) {
                memcpy(temp_buf, s_web_frame_buf, s_web_frame_len);
                current_len = s_web_frame_len;
                last_seq = s_frame_seq;
                is_new = true;
            }
            xSemaphoreGive(s_frame_mutex);
        }

        if (is_new && current_len > 0) {
            res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY, strlen(_STREAM_BOUNDARY));
            if (res != ESP_OK) break;

            size_t hlen = snprintf(part_buf, sizeof(part_buf), _STREAM_PART, current_len);
            res = httpd_resp_send_chunk(req, part_buf, hlen);
            if (res != ESP_OK) break;

            res = httpd_resp_send_chunk(req, (const char *)temp_buf, current_len);
            if (res != ESP_OK) break;
        }

        vTaskDelay(pdMS_TO_TICKS(20));
    }

    free(temp_buf);
    return res;
}

static esp_err_t snapshot_handler(httpd_req_t *req) {
    if (!s_camera_connected || s_web_frame_len == 0) {
        httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "Camara no conectada o sin imagen");
        return ESP_FAIL;
    }

    httpd_resp_set_type(req, "image/jpeg");
    httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

    if (xSemaphoreTake(s_frame_mutex, pdMS_TO_TICKS(100)) == pdTRUE) {
        httpd_resp_send(req, (const char *)s_web_frame_buf, s_web_frame_len);
        xSemaphoreGive(s_frame_mutex);
        return ESP_OK;
    }

    httpd_resp_send_500(req);
    return ESP_FAIL;
}

static esp_err_t status_handler(httpd_req_t *req) {
    char json_buf[160];
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

    snprintf(json_buf, sizeof(json_buf),
             "{\"connected\":%s,\"fps\":%.1f,\"width\":%" PRIu32 ",\"height\":%" PRIu32 ",\"size_bytes\":%u,\"seq\":%" PRIu32 "}",
             s_camera_connected ? "true" : "false",
             s_fps, s_frame_width, s_frame_height, (unsigned int)s_web_frame_len, s_frame_seq);

    return httpd_resp_send(req, json_buf, HTTPD_RESP_USE_STRLEN);
}

static void start_webserver() {
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = 80;
    config.ctrl_port = 32768;
    config.max_open_sockets = 4;

    httpd_uri_t uri_index = { .uri = "/", .method = HTTP_GET, .handler = index_handler, .user_ctx = NULL };
    httpd_uri_t uri_stream = { .uri = "/stream", .method = HTTP_GET, .handler = stream_handler, .user_ctx = NULL };
    httpd_uri_t uri_snapshot = { .uri = "/snapshot", .method = HTTP_GET, .handler = snapshot_handler, .user_ctx = NULL };
    httpd_uri_t uri_status = { .uri = "/status", .method = HTTP_GET, .handler = status_handler, .user_ctx = NULL };

    if (httpd_start(&s_http_server, &config) == ESP_OK) {
        httpd_register_uri_handler(s_http_server, &uri_index);
        httpd_register_uri_handler(s_http_server, &uri_stream);
        httpd_register_uri_handler(s_http_server, &uri_snapshot);
        httpd_register_uri_handler(s_http_server, &uri_status);
        Serial.println("[HTTP] Servidor Web activo en el puerto 80");
    } else {
        Serial.println("[HTTP] Error al inicializar servidor Web");
    }
}

// ==============================================================================
// SETUP Y LOOP PRINCIPAL
// ==============================================================================
void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.println("\n==========================================");
    Serial.println("  ESP32-S3 USB UVC Camera Wi-Fi Streamer  ");
    Serial.println("==========================================");

    s_frame_mutex = xSemaphoreCreateMutex();

    // 1. Asignación de memoria en SRAM interna (compatible al 100% con USB DMA)
    Serial.println("[MEM] Asignando buffers UVC en memoria interna...");
    s_xfer_buffer_a = (uint8_t *)malloc(UVC_BUF_SIZE);
    s_xfer_buffer_b = (uint8_t *)malloc(UVC_BUF_SIZE);
    s_frame_buffer  = (uint8_t *)malloc(UVC_BUF_SIZE);
    s_web_frame_buf = (uint8_t *)malloc(UVC_BUF_SIZE);

    assert(s_xfer_buffer_a && s_xfer_buffer_b && s_frame_buffer && s_web_frame_buf);

    // 2. Creación directa e instantánea de la red Wi-Fi propia (SoftAP)
    Serial.printf("[WIFI] Creando red Wi-Fi propia (AP): '%s'...\n", AP_SSID);
    WiFi.mode(WIFI_AP);
    WiFi.softAPConfig(IPAddress(192, 168, 4, 1), IPAddress(192, 168, 4, 1), IPAddress(255, 255, 255, 0));
    WiFi.softAP(AP_SSID, AP_PASSWORD);

    Serial.println("[WIFI] >> Red Wi-Fi lista:");
    Serial.printf("        SSID: %s\n", AP_SSID);
    Serial.printf("        Clave: %s\n", AP_PASSWORD);
    Serial.println("        URL:  http://192.168.4.1/\n");

    // 3. Iniciar Servidor Web
    start_webserver();

    // 4. Inicializar subsistema USB Host UVC (opera en segundo plano)
    Serial.println("[USB] Inicializando USB Stream Host...");
    s_usb = new USB_STREAM();

    s_usb->uvcConfiguration(FRAME_RESOLUTION_ANY, FRAME_RESOLUTION_ANY, FRAME_INTERVAL_FPS_15,
                            UVC_BUF_SIZE, s_xfer_buffer_a, s_xfer_buffer_b,
                            UVC_BUF_SIZE, s_frame_buffer);

    s_usb->uvcCamRegisterCb(onCameraFrameCallback, NULL);
    s_usb->registerState(onUsbStateChange, NULL);

    s_usb->start();
    Serial.println("[USB] Controlador USB Host activo.");
    Serial.println("      (Puedes conectar o desconectar la camara en cualquier momento)\n");

    s_last_fps_time = millis();
}

void loop() {
    uint32_t now = millis();
    if (now - s_last_fps_time >= 1000) {
        s_fps = (float)s_frame_count * 1000.0f / (float)(now - s_last_fps_time);
        s_frame_count = 0;
        s_last_fps_time = now;

        if (s_camera_connected) {
            Serial.printf("[TELEMETRIA] FPS: %.1f | Res: %" PRIu32 "x%" PRIu32 " | Tamano: %u KB\n",
                          s_fps, s_frame_width, s_frame_height, (unsigned int)(s_web_frame_len / 1024));
        }
    }
    vTaskDelay(pdMS_TO_TICKS(100));
}
