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
#include "driver/gpio.h"
#include "esp_cpu.h"
#include "esp_rom_sys.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "nvs_flash.h"
#include "usb/usb_host.h"
#include "usb/uvc_host.h"

#include "lwip/err.h"
#include "lwip/sockets.h"
#include "lwip/sys.h"
#include <lwip/netdb.h>

#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/semphr.h"
#include "freertos/task.h"

#define TAG "robot_udp_puro"

// -------------------------------------------------------------
// Configuración de Red y Puertos UDP
// -------------------------------------------------------------
#define CAMERA_AP_SSID          "ESP32S3-CAM"
#define CAMERA_AP_PASSWORD      "camara123"
#define CAMERA_STREAM_INDEX     0
#define CAMERA_JPEG_MAX_BYTES   (512 * 1024)

#define GAS_UDP_PORT            5005
#define VIDEO_UDP_PORT          5006
#define UDP_BROADCAST_IP        "192.168.4.255"

// Tamaño máximo seguro por fragmento UDP (MTU Ethernet/Wi-Fi = 1500)
#define VIDEO_CHUNK_PAYLOAD_MAX 1400

#pragma pack(push, 1)
typedef struct {
    uint16_t magic;         // 0xAA55 (sincronismo)
    uint16_t frame_id;      // Contador secuencial de fotograma
    uint16_t chunk_id;      // Índice de fragmento (0..total_chunks - 1)
    uint16_t total_chunks;  // Cantidad total de fragmentos de este frame
    uint16_t payload_len;   // Longitud de datos JPEG en este fragmento
} video_chunk_hdr_t;
#pragma pack(pop)

#define CAMERA_CONNECTED_BIT      BIT0
#define CAMERA_DISCONNECTED_BIT   BIT1
#define CAMERA_TRANSFER_ERROR_BIT BIT2

// -------------------------------------------------------------
// Configuración Hardware del Sensor de Gas MiCS-5524
// -------------------------------------------------------------
#define PIN_GAS_ADC_CHAN        ADC_CHANNEL_3   // GPIO 4 (ADC1_CH3)
#define PIN_GAS_ADC_UNIT        ADC_UNIT_1
#define PIN_GAS_EN              GPIO_NUM_5      // Active-LOW para calentar

#define VCC_VOLTAGE             5.00f
#define RL_LOAD_RESISTOR        820.0f          // 820 Ohms

// -------------------------------------------------------------
// Variables del Subsistema de Cámara
// -------------------------------------------------------------
static EventGroupHandle_t s_camera_events;
static SemaphoreHandle_t s_frame_mutex;
static SemaphoreHandle_t s_frame_ready;

static uint8_t *s_latest_jpeg;
static size_t s_latest_jpeg_len;
static uint32_t s_frame_sequence;
static int64_t s_frame_timestamp_us;
static uint16_t s_frame_width;
static uint16_t s_frame_height;
static float s_measured_fps;
static bool s_camera_present;
static bool s_camera_streaming;

// Servidor HTTP ligero solo para Calibración y Dashboard web auxiliar
static httpd_handle_t s_http_server = NULL;

// -------------------------------------------------------------
// Variables del Subsistema de Gases
// -------------------------------------------------------------
typedef struct {
    float v_raw;
    float v_med;
    float v_ema;
    float rs;
    float r0;
    float ratio;
    float gas_pct;
    bool calibrating;
} gas_telemetry_t;

static gas_telemetry_t s_gas_telemetry = {
    .v_raw = 0.5f,
    .v_med = 0.5f,
    .v_ema = 0.5f,
    .rs = 7500.0f,
    .r0 = 7500.0f,
    .ratio = 1.0f,
    .gas_pct = 0.0f,
    .calibrating = true,
};

static SemaphoreHandle_t s_gas_mutex;
static volatile bool s_calibrate_requested = false;
static adc_oneshot_unit_handle_t s_adc_handle = NULL;
static adc_cali_handle_t s_adc_cali_handle = NULL;
static bool s_adc_calibrated = false;

// Filtro de Mediana N=5
#define MEDIAN_WINDOW 5
static float s_med_buf[MEDIAN_WINDOW];
static int s_med_idx = 0;
static bool s_med_filled = false;

static float calc_median(float val)
{
    s_med_buf[s_med_idx] = val;
    s_med_idx = (s_med_idx + 1) % MEDIAN_WINDOW;
    if (s_med_idx == 0) s_med_filled = true;

    int count = s_med_filled ? MEDIAN_WINDOW : s_med_idx;
    float sorted[MEDIAN_WINDOW];
    for (int i = 0; i < count; i++) sorted[i] = s_med_buf[i];

    for (int i = 0; i < count - 1; i++) {
        for (int j = 0; j < count - 1 - i; j++) {
            if (sorted[j] > sorted[j + 1]) {
                float t = sorted[j];
                sorted[j] = sorted[j + 1];
                sorted[j + 1] = t;
            }
        }
    }
    return sorted[count / 2];
}

// -------------------------------------------------------------
// Control del LED RGB WS2812 (GPIO 48) - Apagado Digital Activo
// -------------------------------------------------------------
static inline void ws2812_send_zero(gpio_num_t pin)
{
    uint32_t t0 = esp_cpu_get_cycle_count();
    gpio_set_level(pin, 1);
    while ((esp_cpu_get_cycle_count() - t0) < 72);

    t0 = esp_cpu_get_cycle_count();
    gpio_set_level(pin, 0);
    while ((esp_cpu_get_cycle_count() - t0) < 216);
}

static void ws2812_turn_off(gpio_num_t pin)
{
    gpio_reset_pin(pin);
    gpio_set_direction(pin, GPIO_MODE_OUTPUT);
    gpio_set_level(pin, 0);
    esp_rom_delay_us(300);

    portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;
    portENTER_CRITICAL(&mux);
    for (int i = 0; i < 24; i++) {
        ws2812_send_zero(pin);
    }
    portEXIT_CRITICAL(&mux);

    gpio_set_level(pin, 0);
    esp_rom_delay_us(300);
    ESP_LOGI(TAG, "LED RGB WS2812 en GPIO %d apagado activamente.", pin);
}

// -------------------------------------------------------------
// Inicialización ADC y Sensor de Gas
// -------------------------------------------------------------
static void init_gas_sensor_hardware(void)
{
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << PIN_GAS_EN),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_ENABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&io_conf);
    gpio_set_level(PIN_GAS_EN, 0);

    adc_oneshot_unit_init_cfg_t init_config1 = {
        .unit_id = PIN_GAS_ADC_UNIT,
        .ulp_mode = ADC_ULP_MODE_DISABLE,
    };
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&init_config1, &s_adc_handle));

    adc_oneshot_chan_cfg_t config = {
        .bitwidth = ADC_BITWIDTH_DEFAULT,
        .atten = ADC_ATTEN_DB_12,
    };
    ESP_ERROR_CHECK(adc_oneshot_config_channel(s_adc_handle, PIN_GAS_ADC_CHAN, &config));

#if ADC_CALI_SCHEME_CURVE_FITTING_SUPPORTED
    adc_cali_curve_fitting_config_t cali_config = {
        .unit_id = PIN_GAS_ADC_UNIT,
        .chan = PIN_GAS_ADC_CHAN,
        .atten = ADC_ATTEN_DB_12,
        .bitwidth = ADC_BITWIDTH_DEFAULT,
    };
    if (adc_cali_create_scheme_curve_fitting(&cali_config, &s_adc_cali_handle) == ESP_OK) {
        s_adc_calibrated = true;
        ESP_LOGI(TAG, "Calibracion ADC por curva (eFuse) activada.");
    }
#elif ADC_CALI_SCHEME_LINE_FITTING_SUPPORTED
    adc_cali_line_fitting_config_t cali_config = {
        .unit_id = PIN_GAS_ADC_UNIT,
        .atten = ADC_ATTEN_DB_12,
        .bitwidth = ADC_BITWIDTH_DEFAULT,
    };
    if (adc_cali_create_scheme_line_fitting(&cali_config, &s_adc_cali_handle) == ESP_OK) {
        s_adc_calibrated = true;
        ESP_LOGI(TAG, "Calibracion ADC por linea activada.");
    }
#endif

    ESP_LOGI(TAG, "Hardware de sensor de gas MiCS-5524 inicializado en GPIO 4.");
}

// -------------------------------------------------------------
// Tarea 1: Sensado y Emisión UDP de Gases (Puerto 5005 a 20 Hz)
// -------------------------------------------------------------
static void gas_sensor_task(void *arg)
{
    (void)arg;
    float ema_val = 0.5f;
    int warmup_ticks = 0;
    uint32_t udp_seq = 0;

    vTaskDelay(pdMS_TO_TICKS(1500));

    int udp_sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if (udp_sock >= 0) {
        int broadcast = 1;
        setsockopt(udp_sock, SOL_SOCKET, SO_BROADCAST, &broadcast, sizeof(broadcast));
        ESP_LOGI(TAG, "Socket UDP de gas listo hacia %s:%d", UDP_BROADCAST_IP, GAS_UDP_PORT);
    } else {
        ESP_LOGE(TAG, "Error creando socket UDP gas: errno %d", errno);
    }

    struct sockaddr_in dest_addr;
    memset(&dest_addr, 0, sizeof(dest_addr));
    dest_addr.sin_family = AF_INET;
    dest_addr.sin_port = htons(GAS_UDP_PORT);
    dest_addr.sin_addr.s_addr = inet_addr(UDP_BROADCAST_IP);

    while (true) {
        if (s_calibrate_requested) {
            xSemaphoreTake(s_gas_mutex, portMAX_DELAY);
            s_gas_telemetry.calibrating = true;
            s_gas_telemetry.gas_pct = 0.0f;
            xSemaphoreGive(s_gas_mutex);

            ESP_LOGI(TAG, "Calibrando R0 en aire limpio (30 muestras)...");
            float sum_v = 0.0f;
            for (int i = 0; i < 30; i++) {
                int raw = 0;
                adc_oneshot_read(s_adc_handle, PIN_GAS_ADC_CHAN, &raw);
                float v = 0.0f;
                if (s_adc_calibrated) {
                    int mv = 0;
                    adc_cali_raw_to_voltage(s_adc_cali_handle, raw, &mv);
                    v = mv / 1000.0f;
                } else {
                    v = raw * (3.14f / 4095.0f);
                }
                sum_v += v;
                vTaskDelay(pdMS_TO_TICKS(20));
            }
            float v_clean = sum_v / 30.0f;
            if (v_clean < 0.05f) v_clean = 0.05f;

            float new_r0 = RL_LOAD_RESISTOR * ((VCC_VOLTAGE - v_clean) / v_clean);
            ema_val = v_clean;

            xSemaphoreTake(s_gas_mutex, portMAX_DELAY);
            s_gas_telemetry.r0 = new_r0;
            s_gas_telemetry.calibrating = false;
            s_gas_telemetry.gas_pct = 0.0f;
            s_gas_telemetry.ratio = 1.0f;
            xSemaphoreGive(s_gas_mutex);

            ESP_LOGI(TAG, "Calibracion completada: V_clean=%.3f V, R0=%.1f Ohms", v_clean, new_r0);
            s_calibrate_requested = false;
        }

        int raw = 0;
        adc_oneshot_read(s_adc_handle, PIN_GAS_ADC_CHAN, &raw);

        float v_raw = 0.0f;
        if (s_adc_calibrated) {
            int mv = 0;
            adc_cali_raw_to_voltage(s_adc_cali_handle, raw, &mv);
            v_raw = mv / 1000.0f;
        } else {
            v_raw = raw * (3.14f / 4095.0f);
        }

        float v_med = calc_median(v_raw);
        ema_val = (0.20f * v_med) + (0.80f * ema_val);

        float v_calc = ema_val;
        if (v_calc < 0.02f) v_calc = 0.02f;
        if (v_calc > 4.90f) v_calc = 4.90f;

        float rs = RL_LOAD_RESISTOR * ((VCC_VOLTAGE - v_calc) / v_calc);

        if (warmup_ticks < 40) {
            warmup_ticks++;
            if (warmup_ticks == 40) {
                float auto_r0 = RL_LOAD_RESISTOR * ((VCC_VOLTAGE - ema_val) / ema_val);
                if (auto_r0 < 400.0f) auto_r0 = 400.0f;

                xSemaphoreTake(s_gas_mutex, portMAX_DELAY);
                s_gas_telemetry.r0 = auto_r0;
                s_gas_telemetry.calibrating = false;
                xSemaphoreGive(s_gas_mutex);
                ESP_LOGI(TAG, "Auto-calibracion inicial de R0: %.1f Ohms (V=%.3f V)", auto_r0, ema_val);
            }
        }

        xSemaphoreTake(s_gas_mutex, portMAX_DELAY);
        float r0 = s_gas_telemetry.r0;
        bool is_calib = s_gas_telemetry.calibrating;
        float ratio = (r0 > 0.0f) ? (r0 / rs) : 1.0f;

        float rs_ratio = (r0 > 0.0f) ? (rs / r0) : 1.0f;
        float gas_pct = 0.0f;
        if (!is_calib && rs_ratio < 1.0f) {
            gas_pct = (1.0f - rs_ratio) * 100.0f;
        }
        if (gas_pct > 100.0f) gas_pct = 100.0f;
        if (is_calib) gas_pct = 0.0f;

        s_gas_telemetry.v_raw = v_raw;
        s_gas_telemetry.v_med = v_med;
        s_gas_telemetry.v_ema = ema_val;
        s_gas_telemetry.rs = rs;
        s_gas_telemetry.ratio = ratio;
        s_gas_telemetry.gas_pct = gas_pct;
        xSemaphoreGive(s_gas_mutex);

        if (udp_sock >= 0) {
            char udp_buf[256];
            int len = snprintf(udp_buf, sizeof(udp_buf),
                               "{\"v_raw\":%.3f,\"v_med\":%.3f,\"v_ema\":%.3f,"
                               "\"rs\":%.1f,\"r0\":%.1f,\"ratio\":%.3f,\"gas_pct\":%.1f,"
                               "\"calibrating\":%s,\"seq\":%" PRIu32 "}",
                               v_raw, v_med, ema_val,
                               rs, r0, ratio, gas_pct,
                               is_calib ? "true" : "false", udp_seq++);
            if (len > 0) {
                sendto(udp_sock, udp_buf, len, 0, (struct sockaddr *)&dest_addr, sizeof(dest_addr));
            }
        }

        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

// -------------------------------------------------------------
// Tarea 2: Fragmentador y Emisor UDP de Video (Puerto 5006)
// -------------------------------------------------------------
static void video_udp_stream_task(void *arg)
{
    (void)arg;
    vTaskDelay(pdMS_TO_TICKS(1800));

    int udp_video_sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if (udp_video_sock >= 0) {
        int broadcast = 1;
        setsockopt(udp_video_sock, SOL_SOCKET, SO_BROADCAST, &broadcast, sizeof(broadcast));
        int sndbuf = 64 * 1024;
        setsockopt(udp_video_sock, SOL_SOCKET, SO_SNDBUF, &sndbuf, sizeof(sndbuf));
        ESP_LOGI(TAG, "Socket UDP de Video UVC listo hacia %s:%d", UDP_BROADCAST_IP, VIDEO_UDP_PORT);
    } else {
        ESP_LOGE(TAG, "Error creando socket UDP video: errno %d", errno);
    }

    struct sockaddr_in dest_video_addr;
    memset(&dest_video_addr, 0, sizeof(dest_video_addr));
    dest_video_addr.sin_family = AF_INET;
    dest_video_addr.sin_port = htons(VIDEO_UDP_PORT);
    dest_video_addr.sin_addr.s_addr = inet_addr(UDP_BROADCAST_IP);

    uint8_t *packet_buf = heap_caps_malloc(sizeof(video_chunk_hdr_t) + VIDEO_CHUNK_PAYLOAD_MAX,
                                           MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    assert(packet_buf != NULL);

    uint8_t *local_snapshot = heap_caps_malloc(CAMERA_JPEG_MAX_BYTES, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    assert(local_snapshot != NULL);

    uint16_t current_frame_id = 0;
    uint32_t last_seq = 0;

    while (true) {
        if (xSemaphoreTake(s_frame_ready, pdMS_TO_TICKS(100)) == pdTRUE) {
            size_t jpeg_len = 0;
            uint32_t seq = 0;
            bool streaming = false;

            xSemaphoreTake(s_frame_mutex, portMAX_DELAY);
            streaming = s_camera_streaming;
            if (streaming && s_latest_jpeg_len > 0 && s_latest_jpeg_len <= CAMERA_JPEG_MAX_BYTES &&
                s_frame_sequence != last_seq) {
                jpeg_len = s_latest_jpeg_len;
                seq = s_frame_sequence;
                memcpy(local_snapshot, s_latest_jpeg, jpeg_len);
            }
            xSemaphoreGive(s_frame_mutex);

            if (jpeg_len > 0 && seq != last_seq && udp_video_sock >= 0) {
                last_seq = seq;
                current_frame_id++;

                uint16_t total_chunks = (uint16_t)((jpeg_len + VIDEO_CHUNK_PAYLOAD_MAX - 1) / VIDEO_CHUNK_PAYLOAD_MAX);
                size_t offset = 0;

                for (uint16_t chunk_idx = 0; chunk_idx < total_chunks; chunk_idx++) {
                    size_t chunk_size = jpeg_len - offset;
                    if (chunk_size > VIDEO_CHUNK_PAYLOAD_MAX) {
                        chunk_size = VIDEO_CHUNK_PAYLOAD_MAX;
                    }

                    video_chunk_hdr_t *hdr = (video_chunk_hdr_t *)packet_buf;
                    hdr->magic = 0xAA55;
                    hdr->frame_id = current_frame_id;
                    hdr->chunk_id = chunk_idx;
                    hdr->total_chunks = total_chunks;
                    hdr->payload_len = (uint16_t)chunk_size;

                    memcpy(packet_buf + sizeof(video_chunk_hdr_t), local_snapshot + offset, chunk_size);

                    size_t packet_size = sizeof(video_chunk_hdr_t) + chunk_size;
                    sendto(udp_video_sock, packet_buf, packet_size, 0,
                           (struct sockaddr *)&dest_video_addr, sizeof(dest_video_addr));

                    offset += chunk_size;

                    if ((chunk_idx % 4) == 3) {
                        esp_rom_delay_us(30);
                    }
                }
            }
        }
    }
}

// -------------------------------------------------------------
// Servidor HTTP Auxiliar (Puerto 80: /calibrate y /data)
// -------------------------------------------------------------
static esp_err_t data_handler(httpd_req_t *req)
{
    gas_telemetry_t gas;
    xSemaphoreTake(s_gas_mutex, portMAX_DELAY);
    gas = s_gas_telemetry;
    xSemaphoreGive(s_gas_mutex);

    float fps;
    uint16_t w, h;
    bool cam_conn, cam_stream;
    xSemaphoreTake(s_frame_mutex, portMAX_DELAY);
    fps = s_measured_fps;
    w = s_frame_width;
    h = s_frame_height;
    cam_conn = s_camera_present;
    cam_stream = s_camera_streaming;
    xSemaphoreGive(s_frame_mutex);

    char json[384];
    snprintf(json, sizeof(json),
             "{\"v_raw\":%.3f,\"v_med\":%.3f,\"v_ema\":%.3f,"
             "\"rs\":%.1f,\"r0\":%.1f,\"ratio\":%.3f,\"gas_pct\":%.1f,"
             "\"calibrating\":%s,"
             "\"fps\":%.1f,\"width\":%u,\"height\":%u,"
             "\"cam_connected\":%s,\"cam_streaming\":%s}",
             gas.v_raw, gas.v_med, gas.v_ema,
             gas.rs, gas.r0, gas.ratio, gas.gas_pct,
             gas.calibrating ? "true" : "false",
             fps, w, h,
             cam_conn ? "true" : "false",
             cam_stream ? "true" : "false");

    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(req, "Connection", "close");
    return httpd_resp_send(req, json, HTTPD_RESP_USE_STRLEN);
}

static esp_err_t calibrate_handler(httpd_req_t *req)
{
    s_calibrate_requested = true;
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(req, "Connection", "close");
    return httpd_resp_sendstr(req, "{\"status\":\"calibrating_started\"}");
}

static esp_err_t start_aux_http_server(void)
{
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = 80;
    config.ctrl_port = 32768;
    config.max_open_sockets = 4;
    config.stack_size = 4096;
    config.lru_purge_enable = true;
    ESP_ERROR_CHECK(httpd_start(&s_http_server, &config));

    const httpd_uri_t data_uri = {
        .uri = "/data", .method = HTTP_GET, .handler = data_handler, .user_ctx = NULL
    };
    ESP_ERROR_CHECK(httpd_register_uri_handler(s_http_server, &data_uri));

    const httpd_uri_t calib_uri = {
        .uri = "/calibrate", .method = HTTP_GET, .handler = calibrate_handler, .user_ctx = NULL
    };
    ESP_ERROR_CHECK(httpd_register_uri_handler(s_http_server, &calib_uri));

    ESP_LOGI(TAG, "Servidor auxiliar HTTP en Puerto 80 listo (/data, /calibrate).");
    return ESP_OK;
}

// -------------------------------------------------------------
// Callbacks y Tareas de Captura UVC (Core 1)
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
        ESP_LOGI(TAG, "Camara UVC conectada: USB addr=%u, stream=%u",
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
        ESP_LOGW(TAG, "Camara UVC desconectada fisicamente");
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
        ESP_LOGI(TAG, "Esperando camara UVC...");
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

            ESP_LOGI(TAG, ">> Captura ACTIVA en MJPEG %ux%u a %.0f fps -> Emision UDP Puerto %d",
                     profiles[i].width, profiles[i].height, profiles[i].fps, VIDEO_UDP_PORT);
            s_camera_streaming = true;

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
// Configuración de Wi-Fi SoftAP
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

    ESP_LOGI(TAG, "Wi-Fi AP Listo: SSID '%s' | Clave '%s' | IP: 192.168.4.1",
             CAMERA_AP_SSID, CAMERA_AP_PASSWORD);
    return ESP_OK;
}

// -------------------------------------------------------------
// Punto de Entrada Principal (app_main)
// -------------------------------------------------------------
void app_main(void)
{
    ESP_LOGI(TAG, "=== ESP32-S3 V6: Sistema Integrado UDP PURO (Video UDP 5006 + Gas UDP 5005) ===");

    if (!esp_psram_is_initialized()) {
        ESP_LOGE(TAG, "Error: Memoria PSRAM requerida.");
        return;
    }

    // Apagado digital activo del LED RGB WS2812 (GPIO 48)
    ws2812_turn_off(GPIO_NUM_48);

    s_camera_events = xEventGroupCreate();
    s_frame_mutex = xSemaphoreCreateMutex();
    s_frame_ready = xSemaphoreCreateBinary();
    s_gas_mutex = xSemaphoreCreateMutex();

    s_latest_jpeg = heap_caps_malloc(CAMERA_JPEG_MAX_BYTES, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    assert(s_latest_jpeg != NULL);

    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // 1. Iniciar Wi-Fi SoftAP PRIMERO (Inicializa la pila lwIP y esp_netif)
    ESP_ERROR_CHECK(start_wifi_ap());

    // 2. Iniciar Servidor Auxiliar HTTP en Puerto 80 (/data, /calibrate)
    ESP_ERROR_CHECK(start_aux_http_server());

    // 3. Iniciar Hardware del Sensor de Gas
    init_gas_sensor_hardware();

    // 4. Iniciar Tareas UDP (Core 0: Gas UDP + Video UDP Slicer)
    xTaskCreatePinnedToCore(gas_sensor_task, "gas_task", 4096, NULL, 4, NULL, 0);
    xTaskCreatePinnedToCore(video_udp_stream_task, "vid_udp_task", 6144, NULL, 5, NULL, 0);

    // 5. Iniciar USB Host UVC (Core 1)
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

    ESP_LOGI(TAG, "Arquitectura UDP PURO activa: Gas -> UDP 5005 | Video -> UDP 5006.");
}
