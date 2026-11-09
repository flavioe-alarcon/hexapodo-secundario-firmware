#include <assert.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "esp_err.h"
#include "esp_heap_caps.h"
#include "esp_http_server.h"
#include "esp_intr_alloc.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_psram.h"
#include "esp_timer.h"
#include "esp_event.h"
#include "esp_wifi.h"
#include "driver/uart.h"
#include "nvs_flash.h"
#include "usb/usb_host.h"
#include "usb/uvc_host.h"

#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/semphr.h"
#include "freertos/task.h"

#define CAMERA_STREAM_INDEX     0
#define CAMERA_AP_SSID          "ESP32S3-CAM"
#define CAMERA_AP_PASSWORD      "camara123"
#define CAMERA_JPEG_MAX_BYTES   (512 * 1024)

#define CAMERA_CONNECTED_BIT    BIT0
#define CAMERA_DISCONNECTED_BIT BIT1
#define CAMERA_TRANSFER_ERROR_BIT BIT2

static const char *TAG = "usb_cam_wifi";

static EventGroupHandle_t s_camera_events;
static SemaphoreHandle_t s_frame_mutex;
static SemaphoreHandle_t s_frame_ready;
static SemaphoreHandle_t s_stream_client;

static uint8_t *s_latest_jpeg;
static size_t s_latest_jpeg_len;
static uint32_t s_frame_sequence;
static int64_t s_frame_timestamp_us;
static uint16_t s_frame_width;
static uint16_t s_frame_height;
static float s_measured_fps;
static bool s_camera_present;
static bool s_camera_streaming;

static httpd_handle_t s_http_server = NULL;
static httpd_handle_t s_status_server = NULL;

static void init_nvs(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
}

static void usb_host_events_task(void *arg)
{
    (void)arg;
    while (true) {
        uint32_t event_flags = 0;
        esp_err_t err = usb_host_lib_handle_events(portMAX_DELAY, &event_flags);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "Error eventos USB: %s", esp_err_to_name(err));
            continue;
        }
        if (event_flags & USB_HOST_LIB_EVENT_FLAGS_NO_CLIENTS) {
            ESP_ERROR_CHECK(usb_host_device_free_all());
        }
    }
}

static const char *format_name(enum uvc_host_stream_format format)
{
    switch (format) {
    case UVC_VS_FORMAT_MJPEG: return "MJPEG";
    case UVC_VS_FORMAT_YUY2:  return "YUY2";
    case UVC_VS_FORMAT_H264:  return "H.264";
    case UVC_VS_FORMAT_H265:  return "H.265";
    case UVC_VS_FORMAT_NV12:  return "NV12";
    default:                  return "desconocido";
    }
}

static void log_camera_modes(uint8_t dev_addr, uint8_t stream_index, size_t reported_count)
{
    size_t count = reported_count;
    if (count == 0) return;

    uvc_host_frame_info_t *modes = calloc(count, sizeof(*modes));
    if (modes == NULL) return;

    esp_err_t err = uvc_host_get_frame_list(
        dev_addr, stream_index, (uvc_host_frame_info_t (*)[])modes, &count);
    if (err != ESP_OK) {
        free(modes);
        return;
    }

    ESP_LOGI(TAG, "Cámara anuncia %u modos:", (unsigned)count);
    for (size_t i = 0; i < count; ++i) {
        float fps = modes[i].default_interval ? 10000000.0f / modes[i].default_interval : 0.0f;
        ESP_LOGI(TAG, "  %s %ux%u, fps %.1f",
                 format_name(modes[i].format), modes[i].h_res, modes[i].v_res, fps);
    }
    free(modes);
}

static void uvc_driver_event_callback(const uvc_host_driver_event_data_t *event, void *user_ctx)
{
    (void)user_ctx;
    if (event->type == UVC_HOST_DRIVER_EVENT_DEVICE_CONNECTED) {
        s_camera_present = true;
        ESP_LOGI(TAG, "Cámara UVC conectada: USB addr=%u, stream=%u",
                 event->device_connected.dev_addr,
                 event->device_connected.uvc_stream_index);

        log_camera_modes(event->device_connected.dev_addr,
                         event->device_connected.uvc_stream_index,
                         event->device_connected.frame_info_num);
        xEventGroupSetBits(s_camera_events, CAMERA_CONNECTED_BIT);
    }
}

static bool frame_callback(const uvc_host_frame_t *frame, void *user_ctx)
{
    (void)user_ctx;
    static int64_t last_report_us = 0;
    static unsigned frames = 0;

    if (frame == NULL || frame->data == NULL || frame->data_len == 0) {
        return true;
    }

    if (frame->data_len <= CAMERA_JPEG_MAX_BYTES) {
        xSemaphoreTake(s_frame_mutex, portMAX_DELAY);
        memcpy(s_latest_jpeg, frame->data, frame->data_len);
        s_latest_jpeg_len = frame->data_len;
        s_frame_sequence++;
        s_frame_timestamp_us = esp_timer_get_time();
        s_frame_width = frame->vs_format.h_res;
        s_frame_height = frame->vs_format.v_res;
        xSemaphoreGive(s_frame_mutex);

        // Despertar tarea del servidor HTTP
        xSemaphoreGive(s_frame_ready);
    }

    frames++;
    const int64_t now = esp_timer_get_time();
    if (last_report_us == 0) {
        last_report_us = now;
    } else if (now - last_report_us >= 1000000) {
        const float fps = frames * 1000000.0f / (now - last_report_us);
        xSemaphoreTake(s_frame_mutex, portMAX_DELAY);
        s_measured_fps = fps;
        xSemaphoreGive(s_frame_mutex);
        frames = 0;
        last_report_us = now;
    }

    return true;
}

static void uvc_stream_event_callback(const uvc_host_stream_event_data_t *event, void *user_ctx)
{
    (void)user_ctx;
    switch (event->type) {
    case UVC_HOST_TRANSFER_ERROR:
        ESP_LOGE(TAG, "Error de transferencia UVC: %s", esp_err_to_name(event->transfer_error.error));
        xEventGroupSetBits(s_camera_events, CAMERA_TRANSFER_ERROR_BIT);
        break;

    case UVC_HOST_DEVICE_DISCONNECTED:
        ESP_LOGW(TAG, "Cámara UVC desconectada físicamente");
        s_camera_present = false;
        s_camera_streaming = false;
        xEventGroupClearBits(s_camera_events, CAMERA_CONNECTED_BIT);
        xEventGroupSetBits(s_camera_events, CAMERA_DISCONNECTED_BIT);
        break;

    default:
        break;
    }
}

// Handler de la página web principal (http://192.168.4.1/)
static esp_err_t root_handler(httpd_req_t *req)
{
    static const char page[] =
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>ESP32-S3 Camara UVC Wi-Fi</title>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<style>"
        "body{background:#0f172a;color:#f8fafc;font-family:system-ui;text-align:center;padding:20px;}"
        "h1{color:#38bdf8;margin-bottom:10px;}"
        ".container{max-width:800px;margin:0 auto;background:#1e293b;padding:15px;border-radius:12px;border:1px solid #334155;}"
        "img{max-width:100%;height:auto;border-radius:8px;border:2px solid #0284c7;background:#020617;}"
        ".badge{display:inline-block;padding:6px 12px;background:#22c55e22;color:#22c55e;border:1px solid #22c55e;border-radius:20px;margin-top:10px;font-weight:600;}"
        "</style></head><body>"
        "<div class='container'>"
        "<h1>ESP32-S3 · Stream Wi-Fi UVC</h1>"
        "<p>Transmisión inalámbrica en tiempo real para Hexápodo Secundario</p>"
        "<br><img src='/stream' alt='Cargando video...'><br>"
        "<div class='badge'>Conexión Activa: 192.168.4.1/stream</div>"
        "</div></body></html>";

    httpd_resp_set_type(req, "text/html; charset=utf-8");
    return httpd_resp_send(req, page, HTTPD_RESP_USE_STRLEN);
}

// Handler de estado JSON (http://192.168.4.1:81/status o :80/status)
static esp_err_t status_handler(httpd_req_t *req)
{
    uint32_t sequence;
    uint16_t width, height;
    size_t jpeg_len;
    float fps;
    bool connected, streaming;

    xSemaphoreTake(s_frame_mutex, portMAX_DELAY);
    sequence = s_frame_sequence;
    width = s_frame_width;
    height = s_frame_height;
    jpeg_len = s_latest_jpeg_len;
    fps = s_measured_fps;
    connected = s_camera_present;
    streaming = s_camera_streaming;
    xSemaphoreGive(s_frame_mutex);

    char json[256];
    snprintf(json, sizeof(json),
             "{\"connected\":%s,\"streaming\":%s,\"fps\":%.1f,\"width\":%u,\"height\":%u,\"size_bytes\":%zu,\"seq\":%" PRIu32 "}",
             connected ? "true" : "false",
             streaming ? "true" : "false",
             fps, width, height, jpeg_len, sequence);

    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    return httpd_resp_send(req, json, HTTPD_RESP_USE_STRLEN);
}

// Handler del flujo continuo MJPEG (http://192.168.4.1/stream)
static esp_err_t stream_handler(httpd_req_t *req)
{
    if (xSemaphoreTake(s_stream_client, 0) != pdTRUE) {
        httpd_resp_set_status(req, "503 Service Unavailable");
        return httpd_resp_sendstr(req, "Solo se permite un cliente MJPEG simultaneo");
    }

    uint8_t *snapshot = heap_caps_malloc(CAMERA_JPEG_MAX_BYTES, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (snapshot == NULL) {
        xSemaphoreGive(s_stream_client);
        httpd_resp_set_status(req, "503 Service Unavailable");
        return httpd_resp_sendstr(req, "Sin memoria PSRAM para snapshot");
    }

    httpd_resp_set_type(req, "multipart/x-mixed-replace;boundary=frame");
    httpd_resp_set_hdr(req, "Cache-Control", "no-store, no-cache, must-revalidate");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

    uint32_t last_sequence = 0;
    esp_err_t result = ESP_OK;

    while (true) {
        xSemaphoreTake(s_frame_ready, pdMS_TO_TICKS(1000));

        size_t jpeg_len = 0;
        uint32_t sequence = 0;

        xSemaphoreTake(s_frame_mutex, portMAX_DELAY);
        if (s_latest_jpeg_len > 0 && s_latest_jpeg_len <= CAMERA_JPEG_MAX_BYTES &&
            s_frame_sequence != last_sequence) {
            jpeg_len = s_latest_jpeg_len;
            sequence = s_frame_sequence;
            memcpy(snapshot, s_latest_jpeg, jpeg_len);
        }
        xSemaphoreGive(s_frame_mutex);

        if (jpeg_len == 0 || sequence == last_sequence) {
            continue;
        }

        char part_header[128];
        int header_len = snprintf(part_header, sizeof(part_header),
                                  "--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %zu\r\n\r\n",
                                  jpeg_len);
        if (header_len <= 0 || header_len >= sizeof(part_header)) {
            result = ESP_FAIL;
            break;
        }

        result = httpd_resp_send_chunk(req, part_header, header_len);
        if (result == ESP_OK) {
            result = httpd_resp_send_chunk(req, (const char *)snapshot, jpeg_len);
        }
        if (result == ESP_OK) {
            result = httpd_resp_send_chunk(req, "\r\n", 2);
        }
        if (result != ESP_OK) {
            break; // Cliente cerro la conexion
        }
        last_sequence = sequence;
    }

    httpd_resp_send_chunk(req, NULL, 0);
    free(snapshot);
    xSemaphoreGive(s_stream_client);
    return result;
}

static esp_err_t start_wifi_ap(void)
{
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_t *ap_netif = esp_netif_create_default_wifi_ap();
    if (ap_netif == NULL) {
        return ESP_FAIL;
    }

    wifi_init_config_t init_config = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init_config));

    wifi_config_t ap_config = {0};
    memcpy(ap_config.ap.ssid, CAMERA_AP_SSID, sizeof(CAMERA_AP_SSID) - 1);
    memcpy(ap_config.ap.password, CAMERA_AP_PASSWORD, sizeof(CAMERA_AP_PASSWORD) - 1);
    ap_config.ap.ssid_len = sizeof(CAMERA_AP_SSID) - 1;
    ap_config.ap.channel = 6;
    ap_config.ap.max_connection = 4;
    ap_config.ap.authmode = WIFI_AUTH_WPA2_PSK;
    ap_config.ap.pmf_cfg.required = false;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &ap_config));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_set_ps(WIFI_PS_NONE));

    ESP_LOGI(TAG, "Wi-Fi AP LISTO! SSID: '%s' | Clave: '%s' | IP: 192.168.4.1",
             CAMERA_AP_SSID, CAMERA_AP_PASSWORD);
    return ESP_OK;
}

static esp_err_t start_http_server(void)
{
    httpd_config_t stream_config = HTTPD_DEFAULT_CONFIG();
    stream_config.server_port = 80;
    stream_config.max_open_sockets = 4;
    stream_config.stack_size = 8192;
    stream_config.lru_purge_enable = true;
    ESP_ERROR_CHECK(httpd_start(&s_http_server, &stream_config));

    const httpd_uri_t stream_uri = {.uri = "/stream", .method = HTTP_GET,
                                    .handler = stream_handler, .user_ctx = NULL};
    ESP_ERROR_CHECK(httpd_register_uri_handler(s_http_server, &stream_uri));

    const httpd_uri_t root_uri = {.uri = "/", .method = HTTP_GET,
                                  .handler = root_handler, .user_ctx = NULL};
    ESP_ERROR_CHECK(httpd_register_uri_handler(s_http_server, &root_uri));

    const httpd_uri_t status_uri = {.uri = "/status", .method = HTTP_GET,
                                    .handler = status_handler, .user_ctx = NULL};
    ESP_ERROR_CHECK(httpd_register_uri_handler(s_http_server, &status_uri));

    ESP_LOGI(TAG, "Servidor HTTP iniciado en puerto 80 (/stream y /status)");
    return ESP_OK;
}

static void camera_stream_task(void *arg)
{
    (void)arg;

    static const struct {
        unsigned width;
        unsigned height;
        float fps;
    } profiles[] = {
        {480, 320, 15.0f},
        {640, 480, 15.0f},
        {320, 240, 25.0f},
        {1280, 720, 10.0f},
    };

    while (true) {
        ESP_LOGI(TAG, "Esperando conexión de la cámara UVC...");
        xEventGroupWaitBits(s_camera_events, CAMERA_CONNECTED_BIT,
                            pdFALSE, pdFALSE, portMAX_DELAY);

        xEventGroupClearBits(s_camera_events,
                             CAMERA_DISCONNECTED_BIT | CAMERA_TRANSFER_ERROR_BIT);

        uvc_host_stream_hdl_t stream = NULL;

        for (size_t i = 0; i < sizeof(profiles) / sizeof(profiles[0]); ++i) {
            if (!s_camera_present) break;

            const uvc_host_stream_config_t stream_config = {
                .event_cb = uvc_stream_event_callback,
                .frame_cb = frame_callback,
                .user_ctx = NULL,
                .usb = {
                    .dev_addr = UVC_HOST_ANY_DEV_ADDR,
                    .vid = UVC_HOST_ANY_VID,
                    .pid = UVC_HOST_ANY_PID,
                    .uvc_stream_index = CAMERA_STREAM_INDEX,
                },
                .vs_format = {
                    .h_res = profiles[i].width,
                    .v_res = profiles[i].height,
                    .fps = profiles[i].fps,
                    .format = UVC_VS_FORMAT_MJPEG,
                },
                .advanced = {
                    .number_of_frame_buffers = 3,
                    .frame_size = 0,
                    .frame_heap_caps = MALLOC_CAP_SPIRAM,
                    .number_of_urbs = 4,
                    .urb_size = 4 * 1024,
                },
            };

            ESP_LOGI(TAG, "Intentando modo MJPEG %ux%u a %.0f fps...",
                     profiles[i].width, profiles[i].height, profiles[i].fps);
            esp_err_t err = uvc_host_stream_open(&stream_config, pdMS_TO_TICKS(3000), &stream);
            if (err != ESP_OK) {
                ESP_LOGW(TAG, "Modo %ux%u no admitido: %s",
                         profiles[i].width, profiles[i].height, esp_err_to_name(err));
                continue;
            }

            err = uvc_host_stream_start(stream);
            if (err != ESP_OK) {
                ESP_LOGW(TAG, "Fallo al iniciar stream: %s", esp_err_to_name(err));
                uvc_host_stream_close(stream);
                stream = NULL;
                continue;
            }

            ESP_LOGI(TAG, ">> Captura ACTIVA en MJPEG %ux%u a %.0f fps -> Wi-Fi Stream listo",
                     profiles[i].width, profiles[i].height, profiles[i].fps);
            s_camera_streaming = true;

            EventBits_t result = xEventGroupWaitBits(
                s_camera_events,
                CAMERA_DISCONNECTED_BIT | CAMERA_TRANSFER_ERROR_BIT,
                pdTRUE, pdFALSE, portMAX_DELAY);

            s_camera_streaming = false;

            if (result & CAMERA_DISCONNECTED_BIT) {
                ESP_LOGW(TAG, "Cámara desconectada físicamente");
                uvc_host_stream_close(stream);
                stream = NULL;
                break;
            }

            if (result & CAMERA_TRANSFER_ERROR_BIT) {
                ESP_LOGW(TAG, "Error USB; reintentando en 500 ms...");
                uvc_host_stream_stop(stream);
                uvc_host_stream_close(stream);
                stream = NULL;
                vTaskDelay(pdMS_TO_TICKS(500));
                break;
            }
            break;
        }

        if (stream != NULL) {
            uvc_host_stream_stop(stream);
            uvc_host_stream_close(stream);
            stream = NULL;
        }

        if (!s_camera_present) {
            xEventGroupClearBits(s_camera_events, CAMERA_CONNECTED_BIT);
        }
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}

void app_main(void)
{
    ESP_LOGI(TAG, "--- Iniciando ESP32-S3 Wi-Fi UVC Camera Server ---");

    if (!esp_psram_is_initialized()) {
        ESP_LOGE(TAG, "PSRAM no detectada");
        return;
    }

    s_camera_events = xEventGroupCreate();
    assert(s_camera_events != NULL);
    s_frame_mutex = xSemaphoreCreateMutex();
    assert(s_frame_mutex != NULL);
    s_frame_ready = xSemaphoreCreateBinary();
    assert(s_frame_ready != NULL);
    s_stream_client = xSemaphoreCreateMutex();
    assert(s_stream_client != NULL);

    s_latest_jpeg = heap_caps_malloc(CAMERA_JPEG_MAX_BYTES, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (s_latest_jpeg == NULL) {
        ESP_LOGE(TAG, "Error reservando buffer JPEG en PSRAM");
        return;
    }

    init_nvs();

    // 1. Iniciar Punto de Acceso Wi-Fi y Servidor HTTP
    ESP_ERROR_CHECK(start_wifi_ap());
    ESP_ERROR_CHECK(start_http_server());

    // 2. Iniciar USB Host UVC
    const usb_host_config_t host_config = {
        .skip_phy_setup = false,
        .intr_flags = ESP_INTR_FLAG_LEVEL1,
    };
    ESP_ERROR_CHECK(usb_host_install(&host_config));
    ESP_LOGI(TAG, "USB Host iniciado. Esperando cámara...");

    if (xTaskCreate(usb_host_events_task, "usb_host_events", 4096, NULL, 5, NULL) != pdPASS) {
        ESP_LOGE(TAG, "Error creando usb_host_events");
        abort();
    }

    if (xTaskCreate(camera_stream_task, "camera_stream", 6144, NULL, 4, NULL) != pdPASS) {
        ESP_LOGE(TAG, "Error creando camera_stream");
        abort();
    }

    const uvc_host_driver_config_t uvc_config = {
        .driver_task_stack_size = 5 * 1024,
        .driver_task_priority = 6,
        .xCoreID = tskNO_AFFINITY,
        .create_background_task = true,
        .event_cb = uvc_driver_event_callback,
        .user_ctx = NULL,
    };
    ESP_ERROR_CHECK(uvc_host_install(&uvc_config));
    ESP_LOGI(TAG, "Driver UVC instalado. Servidor Wi-Fi activo.");
}
