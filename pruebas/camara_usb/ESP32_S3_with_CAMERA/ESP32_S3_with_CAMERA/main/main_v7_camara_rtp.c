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

#define TAG "robot_rtp_v7"

// -------------------------------------------------------------
// Configuracion de Red y Puertos UDP / RTP
// -------------------------------------------------------------
#define CAMERA_AP_SSID          "ESP32S3-CAM"
#define CAMERA_AP_PASSWORD      "camara123"
#define CAMERA_STREAM_INDEX     0
#define CAMERA_JPEG_MAX_BYTES   (512 * 1024)

#define GAS_UDP_PORT            5005
#define VIDEO_RTP_PORT          5004
#define GAS_UDP_BROADCAST_IP    "192.168.4.255"
#define DEFAULT_CLIENT_IP       "192.168.4.2"

#define RTP_CHUNK_PAYLOAD_MAX   1180
#define RTP_PAYLOAD_TYPE_JPEG   26

#pragma pack(push, 1)
// Cabecera RFC 3550 RTP (12 bytes)
typedef struct {
    uint8_t  csrc_len:4;
    uint8_t  extension:1;
    uint8_t  padding:1;
    uint8_t  version:2;      // 2
    uint8_t  payload_type:7; // 26 (JPEG)
    uint8_t  marker:1;       // 1 en el ultimo paquete del cuadro
    uint16_t seq_num;        // Big-endian: numero secuencial
    uint32_t timestamp;      // Big-endian: timestamp 90kHz
    uint32_t ssrc;           // Big-endian: identificador SSRC
} rtp_hdr_t;

// Extension para reconstruccion determinista (8 bytes)
typedef struct {
    uint32_t frame_id;       // Big-endian: contador unico de cuadro
    uint16_t chunk_idx;      // Big-endian: indice (0..total_chunks - 1)
    uint16_t total_chunks;   // Big-endian: cantidad total de fragmentos
} rtp_jpeg_ext_t;
#pragma pack(pop)

#define CAMERA_CONNECTED_BIT    BIT0
#define CAMERA_DISCONNECTED_BIT BIT1
#define CAMERA_TRANSFER_ERROR_BIT BIT2

// -------------------------------------------------------------
// Configuracion Hardware del Sensor de Gas MiCS-5524
// -------------------------------------------------------------
#define PIN_GAS_ADC_CHAN        ADC_CHANNEL_3   // GPIO 4 (ADC1_CH3)
#define PIN_GAS_ADC_UNIT        ADC_UNIT_1
#define PIN_GAS_EN              GPIO_NUM_5      // Active-LOW para calentar

#define VCC_VOLTAGE             5.00f
#define RL_LOAD_RESISTOR        820.0f          // 820 Ohms

// -------------------------------------------------------------
// Variables del Subsistema de Camara
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

// Servidor HTTP en Puerto 80 para UI y Calibracion
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
    ESP_LOGI(TAG, "LED RGB WS2812 en GPIO %d apagado exitosamente.", pin);
}

// -------------------------------------------------------------
// Inicializacion ADC y Sensor de Gas
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
// Tarea 1: Adquisicion y Emision UDP del Sensor de Gases (20 Hz)
// -------------------------------------------------------------
static void gas_sensor_task(void *arg)
{
    (void)arg;
    vTaskDelay(pdMS_TO_TICKS(1000));

    int udp_sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if (udp_sock < 0) {
        ESP_LOGE(TAG, "Error creando socket UDP de gases: errno %d", errno);
    } else {
        int broadcast = 1;
        setsockopt(udp_sock, SOL_SOCKET, SO_BROADCAST, &broadcast, sizeof(broadcast));
    }

    struct sockaddr_in dest_addr;
    memset(&dest_addr, 0, sizeof(dest_addr));
    dest_addr.sin_family = AF_INET;
    dest_addr.sin_port = htons(GAS_UDP_PORT);
    dest_addr.sin_addr.s_addr = inet_addr(GAS_UDP_BROADCAST_IP);

    float ema_filtered = 0.5f;
    const float alpha = 0.20f;
    float r0 = 7500.0f;

    ESP_LOGI(TAG, "Iniciando bucle de sensado de gases a 20 Hz (UDP Port %d)...", GAS_UDP_PORT);

    while (true) {
        int raw_adc = 0;
        int voltage_mv = 0;
        float v_raw = 0.0f;

        if (adc_oneshot_read(s_adc_handle, PIN_GAS_ADC_CHAN, &raw_adc) == ESP_OK) {
            if (s_adc_calibrated) {
                adc_cali_raw_to_voltage(s_adc_cali_handle, raw_adc, &voltage_mv);
                v_raw = voltage_mv / 1000.0f;
            } else {
                v_raw = (raw_adc / 4095.0f) * 3.14f;
            }
        }

        if (v_raw < 0.05f) v_raw = 0.05f;
        if (v_raw > 3.10f) v_raw = 3.10f;

        float v_med = calc_median(v_raw);
        ema_filtered = (alpha * v_med) + ((1.0f - alpha) * ema_filtered);

        float rs = RL_LOAD_RESISTOR * ((VCC_VOLTAGE - ema_filtered) / ema_filtered);
        if (rs < 100.0f) rs = 100.0f;

        if (s_calibrate_requested) {
            r0 = rs;
            s_calibrate_requested = false;
            ESP_LOGI(TAG, "Calibracion manual completada: Nueva R0 = %.1f Ohms", r0);
        }

        float ratio = r0 / rs;
        float gas_pct = (1.0f - (rs / r0)) * 100.0f;
        if (gas_pct < 0.0f) gas_pct = 0.0f;
        if (gas_pct > 100.0f) gas_pct = 100.0f;

        xSemaphoreTake(s_gas_mutex, portMAX_DELAY);
        s_gas_telemetry.v_raw = v_raw;
        s_gas_telemetry.v_med = v_med;
        s_gas_telemetry.v_ema = ema_filtered;
        s_gas_telemetry.rs = rs;
        s_gas_telemetry.r0 = r0;
        s_gas_telemetry.ratio = ratio;
        s_gas_telemetry.gas_pct = gas_pct;
        s_gas_telemetry.calibrating = false;
        xSemaphoreGive(s_gas_mutex);

        if (udp_sock >= 0) {
            char udp_payload[192];
            int payload_len = snprintf(udp_payload, sizeof(udp_payload),
                "{\"v_raw\":%.3f,\"v_med\":%.3f,\"v_ema\":%.3f,\"rs\":%.1f,\"r0\":%.1f,\"ratio\":%.3f,\"gas_pct\":%.1f}",
                v_raw, v_med, ema_filtered, rs, r0, ratio, gas_pct);

            if (payload_len > 0) {
                sendto(udp_sock, udp_payload, payload_len, 0,
                       (struct sockaddr *)&dest_addr, sizeof(dest_addr));
            }
        }

        vTaskDelay(pdMS_TO_TICKS(50)); // 20 Hz
    }
}

// -------------------------------------------------------------
// Tarea 2: Servidor RTP / UDP de Video con Packet Pacing (Puerto 5004)
// -------------------------------------------------------------
static void video_rtp_stream_task(void *arg)
{
    (void)arg;
    vTaskDelay(pdMS_TO_TICKS(1800));

    int udp_video_sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if (udp_video_sock >= 0) {
        struct sockaddr_in bind_addr;
        memset(&bind_addr, 0, sizeof(bind_addr));
        bind_addr.sin_family = AF_INET;
        bind_addr.sin_port = htons(VIDEO_RTP_PORT);
        bind_addr.sin_addr.s_addr = htonl(INADDR_ANY);
        bind(udp_video_sock, (struct sockaddr *)&bind_addr, sizeof(bind_addr));

        struct timeval tv = { .tv_sec = 0, .tv_usec = 2000 };
        setsockopt(udp_video_sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

        int sndbuf = 64 * 1024;
        setsockopt(udp_video_sock, SOL_SOCKET, SO_SNDBUF, &sndbuf, sizeof(sndbuf));
        ESP_LOGI(TAG, "Socket RTP de Video listo en puerto %d", VIDEO_RTP_PORT);
    } else {
        ESP_LOGE(TAG, "Error creando socket RTP video: errno %d", errno);
    }

    struct sockaddr_in dest_video_addr;
    memset(&dest_video_addr, 0, sizeof(dest_video_addr));
    dest_video_addr.sin_family = AF_INET;
    dest_video_addr.sin_port = htons(VIDEO_RTP_PORT);
    dest_video_addr.sin_addr.s_addr = inet_addr(DEFAULT_CLIENT_IP);

    const size_t max_packet_size = sizeof(rtp_hdr_t) + sizeof(rtp_jpeg_ext_t) + RTP_CHUNK_PAYLOAD_MAX;
    uint8_t *packet_buf = heap_caps_malloc(max_packet_size, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    assert(packet_buf != NULL);

    uint8_t *local_snapshot = heap_caps_malloc(CAMERA_JPEG_MAX_BYTES, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    assert(local_snapshot != NULL);

    uint32_t current_frame_id = 0;
    uint16_t rtp_seq_num = 0;
    uint32_t rtp_timestamp = 0;
    const uint32_t rtp_ts_step = 90000 / 15;
    const uint32_t ssrc_id = 0x20261105;
    uint32_t last_seq = 0;

    while (true) {
        if (udp_video_sock >= 0) {
            char rx_buf[32];
            struct sockaddr_in from_addr;
            socklen_t from_len = sizeof(from_addr);
            int rx_len = recvfrom(udp_video_sock, rx_buf, sizeof(rx_buf) - 1, 0,
                                  (struct sockaddr *)&from_addr, &from_len);
            if (rx_len > 0) {
                dest_video_addr.sin_addr = from_addr.sin_addr;
                dest_video_addr.sin_port = from_addr.sin_port;
                ESP_LOGI(TAG, "Cliente RTP vinculado dinamicamente: %s:%d",
                         inet_ntoa(from_addr.sin_addr), ntohs(from_addr.sin_port));
            }
        }

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
                rtp_timestamp += rtp_ts_step;

                uint16_t total_chunks = (uint16_t)((jpeg_len + RTP_CHUNK_PAYLOAD_MAX - 1) / RTP_CHUNK_PAYLOAD_MAX);
                size_t offset = 0;

                for (uint16_t chunk_idx = 0; chunk_idx < total_chunks; chunk_idx++) {
                    size_t chunk_size = jpeg_len - offset;
                    if (chunk_size > RTP_CHUNK_PAYLOAD_MAX) {
                        chunk_size = RTP_CHUNK_PAYLOAD_MAX;
                    }

                    bool is_last = (chunk_idx == (total_chunks - 1));

                    // 1. Cabecera RTP RFC 3550
                    rtp_hdr_t *rtp = (rtp_hdr_t *)packet_buf;
                    rtp->version = 2;
                    rtp->padding = 0;
                    rtp->extension = 0;
                    rtp->csrc_len = 0;
                    rtp->marker = is_last ? 1 : 0;
                    rtp->payload_type = RTP_PAYLOAD_TYPE_JPEG;
                    rtp->seq_num = htons(rtp_seq_num++);
                    rtp->timestamp = htonl(rtp_timestamp);
                    rtp->ssrc = htonl(ssrc_id);

                    // 2. Extension de fotograma
                    rtp_jpeg_ext_t *ext = (rtp_jpeg_ext_t *)(packet_buf + sizeof(rtp_hdr_t));
                    ext->frame_id = htonl(current_frame_id);
                    ext->chunk_idx = htons(chunk_idx);
                    ext->total_chunks = htons(total_chunks);

                    // 3. Payload JPEG
                    uint8_t *payload_ptr = packet_buf + sizeof(rtp_hdr_t) + sizeof(rtp_jpeg_ext_t);
                    memcpy(payload_ptr, local_snapshot + offset, chunk_size);

                    size_t packet_size = sizeof(rtp_hdr_t) + sizeof(rtp_jpeg_ext_t) + chunk_size;

                    sendto(udp_video_sock, packet_buf, packet_size, 0,
                           (struct sockaddr *)&dest_video_addr, sizeof(dest_video_addr));

                    offset += chunk_size;

                    // 4. PACKET PACING: Micro-pausa obligatoria de 350 us
                    esp_rom_delay_us(350);
                }
            }
        }
    }
}

// -------------------------------------------------------------
// Servidor HTTP en Puerto 80 (/data, /calibrate, /)
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
             "\"cam_connected\":%s,\"cam_streaming\":%s,\"protocol\":\"RTP_UDP_5004\"}",
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

static esp_err_t start_http_server(void)
{
    httpd_config_t config_data = HTTPD_DEFAULT_CONFIG();
    config_data.server_port = 80;
    config_data.ctrl_port = 32768;
    config_data.max_open_sockets = 4;
    config_data.stack_size = 4096;
    config_data.lru_purge_enable = true;
    ESP_ERROR_CHECK(httpd_start(&s_http_server, &config_data));

    const httpd_uri_t data_uri = {
        .uri = "/data", .method = HTTP_GET, .handler = data_handler, .user_ctx = NULL
    };
    ESP_ERROR_CHECK(httpd_register_uri_handler(s_http_server, &data_uri));

    const httpd_uri_t calib_uri = {
        .uri = "/calibrate", .method = HTTP_GET, .handler = calibrate_handler, .user_ctx = NULL
    };
    ESP_ERROR_CHECK(httpd_register_uri_handler(s_http_server, &calib_uri));

    ESP_LOGI(TAG, "Servidor HTTP Puerto 80 listo (/data, /calibrate).");
    return ESP_OK;
}

// -------------------------------------------------------------
// Driver USB Host UVC (Identico y 100% probado en V4)
// -------------------------------------------------------------
static void usb_host_events_task(void *arg)
{
    (void)arg;
    while (true) {
        uint32_t event_flags;
        esp_err_t err = usb_host_lib_handle_events(portMAX_DELAY, &event_flags);
        if (err != ESP_OK && err != ESP_ERR_TIMEOUT) {
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
    static uint32_t frames = 0;

    if (frame->data_len > CAMERA_JPEG_MAX_BYTES) {
        ESP_LOGW(TAG, "Frame JPEG excede buffer (%zu > %d)", frame->data_len, CAMERA_JPEG_MAX_BYTES);
        return true;
    }

    if (frame->data_len > 0) {
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

            ESP_LOGI(TAG, ">> Captura UVC ACTIVA en MJPEG %ux%u a %.0f fps",
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
// Configuracion Wi-Fi SoftAP
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
    ESP_LOGI(TAG, "=== ESP32-S3 V7: Protocolo RTP / UDP con Packet Pacing & Gas MiCS-5524 ===");

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

    // 1. Iniciar Hardware del Sensor de Gas
    init_gas_sensor_hardware();

    // 2. Iniciar Tarea de Muestreo de Gas y Emision UDP (Core 0, 20 Hz en puerto 5005)
    xTaskCreatePinnedToCore(gas_sensor_task, "gas_task", 4096, NULL, 4, NULL, 0);

    // 3. Iniciar Wi-Fi SoftAP y Servidor HTTP auxiliar (Puerto 80)
    ESP_ERROR_CHECK(start_wifi_ap());
    ESP_ERROR_CHECK(start_http_server());

    // 4. Iniciar Tarea de Emision RTP / UDP de Video con Packet Pacing (Core 0 en puerto 5004)
    xTaskCreatePinnedToCore(video_rtp_stream_task, "vid_rtp_task", 6144, NULL, 5, NULL, 0);

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

    ESP_LOGI(TAG, "Sistema V7 RTP Activo: Video RTP -> UDP 5004 | Gas -> UDP 5005.");
}
