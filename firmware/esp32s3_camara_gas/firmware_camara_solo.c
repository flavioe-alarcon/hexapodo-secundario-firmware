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
#include "nvs_flash.h"
#include "usb/usb_host.h"
#include "usb/uvc_host.h"

#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/semphr.h"
#include "freertos/task.h"

#define TAG "esp32s3_cam_solo"

// -------------------------------------------------------------
// Configuracion de Red Wi-Fi SoftAP
// -------------------------------------------------------------
#define CAMERA_AP_SSID          "ESP32S3-CAM"
#define CAMERA_AP_PASSWORD      "camara123"
#define CAMERA_STREAM_INDEX     0
#define CAMERA_JPEG_MAX_BYTES   (512 * 1024)

#define CAMERA_CONNECTED_BIT    BIT0
#define CAMERA_DISCONNECTED_BIT BIT1
#define CAMERA_TRANSFER_ERROR_BIT BIT2

// -------------------------------------------------------------
// Variables del Subsistema de Camara
// -------------------------------------------------------------
static EventGroupHandle_t s_camera_events;
static SemaphoreHandle_t s_frame_mutex;
static SemaphoreHandle_t s_frame_ready;
static SemaphoreHandle_t s_stream_client;

static uint8_t *s_latest_jpeg = NULL;
static size_t s_latest_jpeg_len = 0;
static uint32_t s_frame_sequence = 0;
static int64_t s_frame_timestamp_us = 0;
static uint16_t s_frame_width = 0;
static uint16_t s_frame_height = 0;
static float s_measured_fps = 0.0f;
static bool s_camera_present = false;
static bool s_camera_streaming = false;

// Servidores HTTP desacoplados
static httpd_handle_t s_http_server = NULL;    // Puerto 80: Status JSON y Dashboard Web
static httpd_handle_t s_stream_server = NULL;  // Puerto 81: Streaming MJPEG dedicado (TCP)

// -------------------------------------------------------------
// Frame Standby (16x16 px JPEG estandar negro de 631 bytes)
// Se transmite si la camara esta apagada o desconectada para mantener
// la conexion TCP viva y no generar timeouts en el receptor.
// -------------------------------------------------------------
static const uint8_t s_standby_jpeg[] = {
    0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01,
    0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43, 0x00, 0x0D, 0x09, 0x0A, 0x0B, 0x0A, 0x08, 0x0D,
    0x0B, 0x0A, 0x0B, 0x0E, 0x0E, 0x0D, 0x0F, 0x13, 0x20, 0x15, 0x13, 0x12, 0x12, 0x13, 0x27, 0x1C,
    0x1E, 0x17, 0x20, 0x2E, 0x29, 0x31, 0x30, 0x2E, 0x29, 0x2D, 0x2C, 0x33, 0x3A, 0x4A, 0x3E, 0x33,
    0x36, 0x46, 0x37, 0x2C, 0x2D, 0x40, 0x57, 0x41, 0x46, 0x4C, 0x4E, 0x52, 0x53, 0x52, 0x32, 0x3E,
    0x5A, 0x61, 0x5A, 0x50, 0x60, 0x4A, 0x51, 0x52, 0x4F, 0xFF, 0xDB, 0x00, 0x43, 0x01, 0x0E, 0x0E,
    0x0E, 0x13, 0x11, 0x13, 0x26, 0x15, 0x15, 0x26, 0x4F, 0x35, 0x2D, 0x35, 0x4F, 0x4F, 0x4F, 0x4F,
    0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F,
    0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F,
    0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0x4F, 0xFF, 0xC0, 0x00, 0x11, 0x08, 0x00, 0x10, 0x00,
    0x10, 0x03, 0x01, 0x22, 0x00, 0x02, 0x11, 0x01, 0x03, 0x11, 0x01, 0xFF, 0xC4, 0x00, 0x1F, 0x00,
    0x00, 0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5,
    0x10, 0x00, 0x02, 0x01, 0x03, 0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01,
    0x7D, 0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06, 0x13, 0x51, 0x61,
    0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08, 0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1,
    0xF0, 0x24, 0x33, 0x62, 0x72, 0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27,
    0x28, 0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48,
    0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68,
    0x69, 0x6A, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88,
    0x89, 0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3, 0xA4, 0xA5, 0xA6,
    0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4,
    0xC5, 0xC6, 0xC7, 0xC8, 0xC9, 0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1,
    0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7,
    0xF8, 0xF9, 0xFA, 0xFF, 0xC4, 0x00, 0x1F, 0x01, 0x00, 0x03, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
    0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
    0x08, 0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x11, 0x00, 0x02, 0x01, 0x02, 0x04, 0x04, 0x03,
    0x04, 0x07, 0x05, 0x04, 0x04, 0x00, 0x01, 0x02, 0x77, 0x00, 0x01, 0x02, 0x03, 0x11, 0x04, 0x05,
    0x21, 0x31, 0x06, 0x12, 0x41, 0x51, 0x07, 0x61, 0x71, 0x13, 0x22, 0x32, 0x81, 0x08, 0x14, 0x42,
    0x91, 0xA1, 0xB1, 0xC1, 0x09, 0x23, 0x33, 0x52, 0xF0, 0x15, 0x62, 0x72, 0xD1, 0x0A, 0x16, 0x24,
    0x34, 0xE1, 0x25, 0xF1, 0x17, 0x18, 0x19, 0x1A, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x35, 0x36, 0x37,
    0x38, 0x39, 0x3A, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57,
    0x58, 0x59, 0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75, 0x76, 0x77,
    0x78, 0x79, 0x7A, 0x82, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89, 0x8A, 0x92, 0x93, 0x94, 0x95,
    0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3,
    0xB4, 0xB5, 0xB6, 0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9, 0xCA,
    0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8,
    0xE9, 0xEA, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x0C, 0x03,
    0x01, 0x00, 0x02, 0x11, 0x03, 0x11, 0x00, 0x3F, 0x00, 0xF3, 0x0A, 0x28, 0xA2, 0x80, 0x3F, 0xFF,
    0xD9
};

// -------------------------------------------------------------
// Callbacks y Tareas de Captura USB UVC
// -------------------------------------------------------------
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

static void uvc_driver_event_callback(const uvc_host_driver_event_data_t *event, void *user_ctx)
{
    (void)user_ctx;
    if (event->type == UVC_HOST_DRIVER_EVENT_DEVICE_CONNECTED) {
        s_camera_present = true;
        ESP_LOGI(TAG, "Camara UVC conectada fisicamente: USB addr=%u, stream=%u",
                 event->device_connected.dev_addr,
                 event->device_connected.uvc_stream_index);
        xEventGroupSetBits(s_camera_events, CAMERA_CONNECTED_BIT);
    }
}

static bool frame_callback(const uvc_host_frame_t *frame, void *user_ctx)
{
    (void)user_ctx;
    static int64_t last_report_us = 0;
    static unsigned frames = 0;

    if (frame == NULL || frame->data == NULL || frame->data_len == 0) return true;

    if (frame->data_len <= CAMERA_JPEG_MAX_BYTES) {
        xSemaphoreTake(s_frame_mutex, portMAX_DELAY);
        memcpy(s_latest_jpeg, frame->data, frame->data_len);
        s_latest_jpeg_len = frame->data_len;
        s_frame_sequence++;
        s_frame_timestamp_us = esp_timer_get_time();
        s_frame_width = frame->vs_format.h_res;
        s_frame_height = frame->vs_format.v_res;
        s_camera_streaming = true;
        xSemaphoreGive(s_frame_mutex);

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
        ESP_LOGE(TAG, "Error transferencia UVC: %s", esp_err_to_name(event->transfer_error.error));
        xEventGroupSetBits(s_camera_events, CAMERA_TRANSFER_ERROR_BIT);
        break;
    case UVC_HOST_DEVICE_DISCONNECTED:
        ESP_LOGW(TAG, "Camara UVC desconectada fisicamente.");
        s_camera_present = false;
        s_camera_streaming = false;
        xEventGroupClearBits(s_camera_events, CAMERA_CONNECTED_BIT);
        xEventGroupSetBits(s_camera_events, CAMERA_DISCONNECTED_BIT);
        break;
    default:
        break;
    }
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
        ESP_LOGI(TAG, "Esperando deteccion de camara UVC...");
        xEventGroupWaitBits(s_camera_events, CAMERA_CONNECTED_BIT, pdFALSE, pdFALSE, portMAX_DELAY);
        xEventGroupClearBits(s_camera_events, CAMERA_DISCONNECTED_BIT | CAMERA_TRANSFER_ERROR_BIT);

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
                    .number_of_urbs = 6,
                    .urb_size = 4 * 1024,
                },
            };

            esp_err_t err = uvc_host_stream_open(&stream_config, pdMS_TO_TICKS(3000), &stream);
            if (err != ESP_OK) continue;

            err = uvc_host_stream_start(stream);
            if (err != ESP_OK) {
                uvc_host_stream_close(stream);
                stream = NULL;
                continue;
            }

            ESP_LOGI(TAG, ">> Captura ACTIVA en MJPEG %ux%u a %.0f fps",
                     profiles[i].width, profiles[i].height, profiles[i].fps);

            EventBits_t result = xEventGroupWaitBits(
                s_camera_events,
                CAMERA_DISCONNECTED_BIT | CAMERA_TRANSFER_ERROR_BIT,
                pdTRUE, pdFALSE, portMAX_DELAY);

            s_camera_streaming = false;

            if (result & CAMERA_DISCONNECTED_BIT) {
                uvc_host_stream_close(stream);
                stream = NULL;
                break;
            }
            if (result & CAMERA_TRANSFER_ERROR_BIT) {
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

// -------------------------------------------------------------
// Servidor HTTP 2 (Puerto 81): Streaming MJPEG Dedicado (TCP)
// -------------------------------------------------------------
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
        if (xSemaphoreTake(s_frame_ready, pdMS_TO_TICKS(200)) == pdTRUE) {
            size_t jpeg_len = 0;
            uint32_t sequence = 0;
            bool streaming = false;

            xSemaphoreTake(s_frame_mutex, portMAX_DELAY);
            streaming = s_camera_streaming;
            if (streaming && s_latest_jpeg_len > 0 && s_latest_jpeg_len <= CAMERA_JPEG_MAX_BYTES &&
                s_frame_sequence != last_sequence) {
                jpeg_len = s_latest_jpeg_len;
                sequence = s_frame_sequence;
                memcpy(snapshot, s_latest_jpeg, jpeg_len);
            }
            xSemaphoreGive(s_frame_mutex);

            if (jpeg_len > 0 && sequence != last_sequence) {
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
                    break;
                }
                last_sequence = sequence;
            }
        } else {
            bool streaming = false;
            xSemaphoreTake(s_frame_mutex, portMAX_DELAY);
            streaming = s_camera_streaming;
            xSemaphoreGive(s_frame_mutex);

            if (!streaming) {
                char part_header[128];
                int header_len = snprintf(part_header, sizeof(part_header),
                                          "--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %zu\r\n\r\n",
                                          sizeof(s_standby_jpeg));
                result = httpd_resp_send_chunk(req, part_header, header_len);
                if (result == ESP_OK) {
                    result = httpd_resp_send_chunk(req, (const char *)s_standby_jpeg, sizeof(s_standby_jpeg));
                }
                if (result == ESP_OK) {
                    result = httpd_resp_send_chunk(req, "\r\n", 2);
                }
                if (result != ESP_OK) {
                    break;
                }
                vTaskDelay(pdMS_TO_TICKS(500));
            }
        }
    }

    free(snapshot);
    xSemaphoreGive(s_stream_client);
    ESP_LOGI(TAG, "Cliente MJPEG desconectado de puerto 81.");
    return result;
}

// -------------------------------------------------------------
// Servidor HTTP 1 (Puerto 80): Dashboard y Telemetria JSON
// -------------------------------------------------------------
static esp_err_t status_handler(httpd_req_t *req)
{
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

    xSemaphoreTake(s_frame_mutex, portMAX_DELAY);
    bool present = s_camera_present;
    bool streaming = s_camera_streaming;
    float fps = s_measured_fps;
    uint16_t w = s_frame_width;
    uint16_t h = s_frame_height;
    uint32_t seq = s_frame_sequence;
    size_t len = s_latest_jpeg_len;
    xSemaphoreGive(s_frame_mutex);

    char json[256];
    int len_json = snprintf(json, sizeof(json),
        "{\"camera_present\":%s,\"streaming\":%s,\"fps\":%.1f,\"width\":%u,\"height\":%u,\"sequence\":%lu,\"bytes\":%zu}",
        present ? "true" : "false",
        streaming ? "true" : "false",
        fps, w, h, (unsigned long)seq, len);

    return httpd_resp_send(req, json, len_json);
}

static esp_err_t stream_redirect_handler(httpd_req_t *req)
{
    httpd_resp_set_status(req, "302 Found");
    httpd_resp_set_hdr(req, "Location", "http://192.168.4.1:81/stream");
    return httpd_resp_send(req, NULL, 0);
}

static esp_err_t root_handler(httpd_req_t *req)
{
    static const char page[] =
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Robot Hexapodo · Vision UVC Solo</title>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<style>"
        "body{background:#0f172a;color:#f8fafc;font-family:system-ui;margin:0;padding:20px;text-align:center;}"
        "h1{color:#38bdf8;margin-bottom:6px;font-size:22px;}"
        ".card{background:#1e293b;border-radius:12px;padding:16px;max-width:640px;margin:12px auto;box-shadow:0 4px 6px -1px rgba(0,0,0,0.3);}"
        ".badge{display:inline-block;padding:4px 12px;border-radius:9999px;font-size:12px;font-weight:700;margin-bottom:10px;}"
        ".badge-ok{background:#166534;color:#4ade80;}"
        ".badge-warn{background:#854d0e;color:#facc15;}"
        "#videoBox{border-radius:8px;border:2px solid #334155;max-width:100%;height:auto;background:#000;display:block;margin:0 auto;}"
        ".stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px;text-align:left;font-size:13px;}"
        ".stat-item{background:#0f172a;padding:8px 12px;border-radius:6px;}"
        ".stat-val{font-weight:700;color:#38bdf8;float:right;}"
        "</style></head><body>"
        "<h1>Robot Hexapodo · Servidor de Vision UVC</h1>"
        "<div class='card'>"
        "<span id='badgeCam' class='badge badge-warn'>INICIALIZANDO...</span>"
        "<img id='videoBox' src='http://192.168.4.1:81/stream' alt='Stream MJPEG' width='480' height='320'>"
        "<div class='stat-grid'>"
        "  <div class='stat-item'>Camara Presente: <span id='txtPresent' class='stat-val'>--</span></div>"
        "  <div class='stat-item'>Transmitiendo: <span id='txtStreaming' class='stat-val'>--</span></div>"
        "  <div class='stat-item'>FPS Medido: <span id='txtFps' class='stat-val'>--</span></div>"
        "  <div class='stat-item'>Resolucion: <span id='txtRes' class='stat-val'>--</span></div>"
        "  <div class='stat-item'>Cuadros Enviados: <span id='txtSeq' class='stat-val'>--</span></div>"
        "  <div class='stat-item'>Bytes Frame: <span id='txtBytes' class='stat-val'>--</span></div>"
        "</div>"
        "</div>"
        "<script>"
        "setInterval(async()=>{"
        "  try{"
        "    const r=await fetch('/status');"
        "    if(!r.ok)return;"
        "    const d=await r.json();"
        "    const b=document.getElementById('badgeCam');"
        "    if(d.streaming){"
        "      b.className='badge badge-ok'; b.innerText='EN VIVO (UVC ACTIVA)';"
        "    } else if(d.camera_present){"
        "      b.className='badge badge-warn'; b.innerText='CAMARA DETECTADA (STANDBY)';"
        "    } else {"
        "      b.className='badge badge-warn'; b.innerText='STANDBY (DESCONECTADA / APAGADA)';"
        "    }"
        "    document.getElementById('txtPresent').innerText=d.camera_present?'SI':'NO';"
        "    document.getElementById('txtStreaming').innerText=d.streaming?'SI':'STANDBY';"
        "    document.getElementById('txtFps').innerText=d.fps.toFixed(1)+' fps';"
        "    document.getElementById('txtRes').innerText=d.width+'x'+d.height;"
        "    document.getElementById('txtSeq').innerText=d.sequence;"
        "    document.getElementById('txtBytes').innerText=(d.bytes/1024).toFixed(1)+' KB';"
        "  }catch(e){}"
        "},500);"
        "</script></body></html>";

    httpd_resp_set_type(req, "text/html; charset=utf-8");
    return httpd_resp_send(req, page, HTTPD_RESP_USE_STRLEN);
}

// -------------------------------------------------------------
// Configuracion de Red y Servidores HTTP
// -------------------------------------------------------------
static esp_err_t start_wifi_ap(void)
{
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_t *ap_netif = esp_netif_create_default_wifi_ap();
    if (ap_netif == NULL) return ESP_FAIL;

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

    ESP_LOGI(TAG, "Wi-Fi AP Iniciado: SSID '%s' | Clave '%s' | IP: 192.168.4.1",
             CAMERA_AP_SSID, CAMERA_AP_PASSWORD);
    return ESP_OK;
}

static esp_err_t start_http_servers(void)
{
    // Servidor de Estado / Dashboard (Puerto 80)
    httpd_config_t config_data = HTTPD_DEFAULT_CONFIG();
    config_data.server_port = 80;
    config_data.ctrl_port = 32768;
    config_data.max_open_sockets = 4;
    config_data.stack_size = 4096;
    config_data.lru_purge_enable = true;
    ESP_ERROR_CHECK(httpd_start(&s_http_server, &config_data));

    const httpd_uri_t root_uri = {
        .uri = "/", .method = HTTP_GET, .handler = root_handler, .user_ctx = NULL
    };
    ESP_ERROR_CHECK(httpd_register_uri_handler(s_http_server, &root_uri));

    const httpd_uri_t status_uri = {
        .uri = "/status", .method = HTTP_GET, .handler = status_handler, .user_ctx = NULL
    };
    ESP_ERROR_CHECK(httpd_register_uri_handler(s_http_server, &status_uri));

    const httpd_uri_t stream_redir_uri = {
        .uri = "/stream", .method = HTTP_GET, .handler = stream_redirect_handler, .user_ctx = NULL
    };
    ESP_ERROR_CHECK(httpd_register_uri_handler(s_http_server, &stream_redir_uri));

    // Servidor Dedicado de Streaming MJPEG TCP (Puerto 81)
    httpd_config_t config_stream = HTTPD_DEFAULT_CONFIG();
    config_stream.server_port = 81;
    config_stream.ctrl_port = 32769;
    config_stream.max_open_sockets = 2;
    config_stream.stack_size = 8192;
    config_stream.lru_purge_enable = true;
    ESP_ERROR_CHECK(httpd_start(&s_stream_server, &config_stream));

    const httpd_uri_t stream_uri = {
        .uri = "/stream", .method = HTTP_GET, .handler = stream_handler, .user_ctx = NULL
    };
    ESP_ERROR_CHECK(httpd_register_uri_handler(s_stream_server, &stream_uri));

    ESP_LOGI(TAG, "Servidores HTTP listos:");
    ESP_LOGI(TAG, "  Puerto 80: Dashboard Web y API /status");
    ESP_LOGI(TAG, "  Puerto 81: Stream MJPEG dedicado /stream (TCP)");
    return ESP_OK;
}

// -------------------------------------------------------------
// Punto de Entrada Principal (app_main)
// -------------------------------------------------------------
void app_main(void)
{
    ESP_LOGI(TAG, "=== ESP32-S3: Servidor de Camara UVC Host Standalone (Robusto) ===");

    if (!esp_psram_is_initialized()) {
        ESP_LOGE(TAG, "Error: Memoria PSRAM requerida.");
        return;
    }

    s_camera_events = xEventGroupCreate();
    s_frame_mutex = xSemaphoreCreateMutex();
    s_frame_ready = xSemaphoreCreateBinary();
    s_stream_client = xSemaphoreCreateMutex();

    s_latest_jpeg = heap_caps_malloc(CAMERA_JPEG_MAX_BYTES, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    assert(s_latest_jpeg != NULL);

    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // 1. Iniciar Wi-Fi SoftAP y Servidores HTTP
    ESP_ERROR_CHECK(start_wifi_ap());
    ESP_ERROR_CHECK(start_http_servers());

    // 2. Iniciar USB Host UVC (Core 1)
    const usb_host_config_t host_config = {
        .skip_phy_setup = false,
        .intr_flags = ESP_INTR_FLAG_LEVEL1,
    };
    ESP_ERROR_CHECK(usb_host_install(&host_config));

    xTaskCreate(usb_host_events_task, "usb_events", 4096, NULL, 5, NULL);
    xTaskCreatePinnedToCore(camera_stream_task, "cam_stream", 6144, NULL, 4, NULL, 1);

    const uvc_host_driver_config_t uvc_config = {
        .driver_task_stack_size = 5 * 1024,
        .driver_task_priority = 6,
        .xCoreID = 1,
        .create_background_task = true,
        .event_cb = uvc_driver_event_callback,
        .user_ctx = NULL,
    };
    ESP_ERROR_CHECK(uvc_host_install(&uvc_config));

    ESP_LOGI(TAG, "Subsistema de Vision UVC Standalone listo y esperando conexiones.");
}
