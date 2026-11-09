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

#define TAG "robot_cam_gas"

// -------------------------------------------------------------
// Configuracion de Red y Servidores HTTP / UDP
// -------------------------------------------------------------
#define CAMERA_AP_SSID          "ESP32S3-CAM"
#define CAMERA_AP_PASSWORD      "camara123"
#define CAMERA_STREAM_INDEX     0
#define CAMERA_JPEG_MAX_BYTES   (512 * 1024)

#define GAS_UDP_PORT            5005
#define GAS_UDP_BROADCAST_IP    "192.168.4.255"

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

// Servidores HTTP independientes (Doble Servidor Desacoplado)
static httpd_handle_t s_http_server = NULL;    // Puerto 80: Web UI y Control de Calibracion
static httpd_handle_t s_stream_server = NULL;  // Puerto 81: Streaming MJPEG dedicado (TCP)

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
    .calibrating = true, // Arranca en fase de precalentamiento/autocalibracion
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
// Inicializacion ADC y Sensor de Gas
// -------------------------------------------------------------
static void init_gas_sensor_hardware(void)
{
    // Pin EN en GPIO 5 (Active-LOW: 0 enciende calefactor)
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << PIN_GAS_EN),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_ENABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&io_conf);
    gpio_set_level(PIN_GAS_EN, 0); // Encender calefactor MEMS

    // Configurar ADC1 Oneshot en GPIO 4 (ADC1_CH3)
    adc_oneshot_unit_init_cfg_t init_config1 = {
        .unit_id = PIN_GAS_ADC_UNIT,
        .ulp_mode = ADC_ULP_MODE_DISABLE,
    };
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&init_config1, &s_adc_handle));

    adc_oneshot_chan_cfg_t config = {
        .bitwidth = ADC_BITWIDTH_DEFAULT,
        .atten = ADC_ATTEN_DB_12, // 0 - 3.14V
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

// Tarea de lectura continua del sensor de gases y emision UDP a 20 Hz (Core 0)
static void gas_sensor_task(void *arg)
{
    (void)arg;
    float ema_val = 0.5f;
    int warmup_ticks = 0;
    uint32_t udp_seq = 0;

    int udp_sock = -1;
    struct sockaddr_in dest_addr;
    memset(&dest_addr, 0, sizeof(dest_addr));
    dest_addr.sin_family = AF_INET;
    dest_addr.sin_port = htons(GAS_UDP_PORT);
    dest_addr.sin_addr.s_addr = inet_addr(GAS_UDP_BROADCAST_IP);

    while (true) {
        // ---------------------------------------------------------
        // 1. Manejo de solicitud de calibracion de R0
        // ---------------------------------------------------------
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
            ema_val = v_clean; // Sincronizar filtro EMA con la linea base limpia

            xSemaphoreTake(s_gas_mutex, portMAX_DELAY);
            s_gas_telemetry.r0 = new_r0;
            s_gas_telemetry.calibrating = false;
            s_gas_telemetry.gas_pct = 0.0f;
            s_gas_telemetry.ratio = 1.0f;
            xSemaphoreGive(s_gas_mutex);

            ESP_LOGI(TAG, "Calibracion completada: V_clean=%.3f V, R0=%.1f Ohms", v_clean, new_r0);
            s_calibrate_requested = false;
        }

        // ---------------------------------------------------------
        // 2. Lectura ADC normal a 20 Hz
        // ---------------------------------------------------------
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

        // Filtro Mediana (N=5)
        float v_med = calc_median(v_raw);

        // Filtro EMA (alfa = 0.20)
        ema_val = (0.20f * v_med) + (0.80f * ema_val);

        // Modelo Fisico: Rs = RL * (Vcc - Vout) / Vout
        float v_calc = ema_val;
        if (v_calc < 0.02f) v_calc = 0.02f;
        if (v_calc > 4.90f) v_calc = 4.90f;

        float rs = RL_LOAD_RESISTOR * ((VCC_VOLTAGE - v_calc) / v_calc);

        // ---------------------------------------------------------
        // 3. Auto-calibracion inicial inteligente al segundo 2.0
        // ---------------------------------------------------------
        if (warmup_ticks < 40) {
            warmup_ticks++;
            if (warmup_ticks == 40) {
                float auto_r0 = RL_LOAD_RESISTOR * ((VCC_VOLTAGE - ema_val) / ema_val);
                if (auto_r0 < 400.0f) auto_r0 = 400.0f;

                xSemaphoreTake(s_gas_mutex, portMAX_DELAY);
                s_gas_telemetry.r0 = auto_r0;
                s_gas_telemetry.calibrating = false;
                xSemaphoreGive(s_gas_mutex);
                ESP_LOGI(TAG, "Auto-calibracion inicial de R0 completada: %.1f Ohms (V=%.3f V)", auto_r0, ema_val);
            }
        }

        xSemaphoreTake(s_gas_mutex, portMAX_DELAY);
        float r0 = s_gas_telemetry.r0;
        bool is_calib = s_gas_telemetry.calibrating;
        float ratio = (r0 > 0.0f) ? (r0 / rs) : 1.0f; // Ratio ascendente R0/Rs

        // Calculo de Intensidad de Gas (%): (1 - Rs/R0) * 100%
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

        // ---------------------------------------------------------
        // 4. Emision Inalambrica de Telemetria por UDP Broadcast
        // ---------------------------------------------------------
        if (udp_sock < 0) {
            udp_sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
            if (udp_sock >= 0) {
                int broadcast = 1;
                setsockopt(udp_sock, SOL_SOCKET, SO_BROADCAST, &broadcast, sizeof(broadcast));
                ESP_LOGI(TAG, "Socket UDP de telemetria listo hacia %s:%d", GAS_UDP_BROADCAST_IP, GAS_UDP_PORT);
            }
        }

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

        vTaskDelay(pdMS_TO_TICKS(50)); // 20 Hz
    }
}

// -------------------------------------------------------------
// Servidor HTTP 1 (Puerto 80): Handlers de Control y Telemetria Fallback
// -------------------------------------------------------------

// Handler JSON de telemetria completa (Video + Gas)
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

// Handler de calibracion de R0
static esp_err_t calibrate_handler(httpd_req_t *req)
{
    s_calibrate_requested = true;
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(req, "Connection", "close");
    return httpd_resp_sendstr(req, "{\"status\":\"calibrating_started\"}");
}

// Redireccion automatica de /stream en puerto 80 hacia el puerto 81
static esp_err_t stream_redirect_handler(httpd_req_t *req)
{
    httpd_resp_set_status(req, "302 Found");
    httpd_resp_set_hdr(req, "Location", "http://192.168.4.1:81/stream");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(req, "Connection", "close");
    return httpd_resp_send(req, NULL, 0);
}

// -------------------------------------------------------------
// Servidor HTTP 2 (Puerto 81): Streaming MJPEG Dedicado (TCP)
// -------------------------------------------------------------

// Frame JPEG estandar 16x16 negro (631 bytes) enviado en modo espera si la camara no esta conectada
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

// Handler del flujo continuo MJPEG (Puerto 81: /stream - TCP)
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
        // Esperar hasta 200 ms por un nuevo frame de la camara
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
                    break; // Cliente desconectado
                }
                last_sequence = sequence;
            }
        } else {
            // Verificar si la camara esta desconectada para enviar standby frame a 2 Hz
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

    httpd_resp_send_chunk(req, NULL, 0);
    free(snapshot);
    xSemaphoreGive(s_stream_client);
    return result;
}

// Handler de pagina web integrada (Puerto 80: /)
static esp_err_t root_handler(httpd_req_t *req)
{
    static const char page[] =
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Robot Hexapodo · Vision & Gas</title>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<style>"
        "body{background:#0f172a;color:#f8fafc;font-family:system-ui;margin:0;padding:20px;text-align:center;}"
        "h1{color:#38bdf8;margin-bottom:6px;}"
        ".grid{display:grid;grid-template-columns:1fr 340px;gap:20px;max-width:1100px;margin:20px auto;text-align:left;}"
        "@media(max-width:800px){.grid{grid-template-columns:1fr;}}"
        ".card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:15px;box-shadow:0 10px 25px rgba(0,0,0,0.5);}"
        "img{width:100%;border-radius:8px;background:#020617;display:block;}"
        ".metric{background:#020617;padding:10px;border-radius:8px;border:1px solid #334155;margin-bottom:10px;}"
        ".metric-lbl{font-size:0.75rem;color:#94a3b8;}"
        ".metric-val{font-size:1.4rem;font-weight:700;color:#38bdf8;font-family:monospace;}"
        ".bar-bg{background:#334155;height:14px;border-radius:7px;overflow:hidden;margin-top:5px;}"
        ".bar-fill{background:#22c55e;height:100%;width:0%;transition:width 0.2s,background 0.2s;}"
        "button{width:100%;padding:10px;background:#0284c7;color:#fff;border:none;border-radius:8px;font-weight:600;cursor:pointer;margin-top:10px;}"
        "button:hover{background:#0369a1;}"
        "</style></head><body>"
        "<h1>Hexapodo Secundario · Camara UVC & Gas MiCS-5524</h1>"
        "<p style='color:#94a3b8;'>Tesis UTEC 2026 · Monitoreo Ambiental en Tiempo Real (Video TCP + Gas UDP)</p>"
        "<div class='grid'>"
        "  <div class='card'>"
        "    <h3 style='margin-top:0;color:#38bdf8;'>Streaming de Video UVC (Puerto 81 - TCP)</h3>"
        "    <img id='uvcStream' src='/stream' alt='Cargando video...'>"
        "  </div>"
        "  <div class='card'>"
        "    <h3 style='margin-top:0;color:#38bdf8;'>Sensor de Gases (UDP 5005)</h3>"
        "    <div class='metric'>"
        "      <div class='metric-lbl'>Intensidad de Gas / Nivel</div>"
        "      <div class='metric-val' id='txtGasPct'>0.0 %</div>"
        "      <div class='bar-bg'><div id='barGas' class='bar-fill'></div></div>"
        "    </div>"
        "    <div class='metric'>"
        "      <div class='metric-lbl'>Voltaje EMA / Mediana</div>"
        "      <div class='metric-val' id='txtVolt'>0.000 V</div>"
        "    </div>"
        "    <div class='metric'>"
        "      <div class='metric-lbl'>Resistencia Rs / R0</div>"
        "      <div class='metric-val' id='txtRsR0'>0.0 / 0.0 kΩ</div>"
        "    </div>"
        "    <div class='metric'>"
        "      <div class='metric-lbl'>Ratio R0 / Rs</div>"
        "      <div class='metric-val' id='txtRatio'>1.000</div>"
        "    </div>"
        "    <button onclick=\"fetch('/calibrate').then(()=>alert('Calibracion R0 solicitada'))\">Calibrar R0 en Aire Limpio</button>"
        "  </div>"
        "</div>"
        "<script>"
        "document.getElementById('uvcStream').src = 'http://' + window.location.hostname + ':81/stream';"
        "setInterval(async()=>{"
        "  try{"
        "    const r=await fetch('/data');"
        "    if(!r.ok)return;"
        "    const d=await r.json();"
        "    if(d.calibrating){"
        "      document.getElementById('txtGasPct').innerText='CALIBRANDO...';"
        "      document.getElementById('barGas').style.width='100%';"
        "      document.getElementById('barGas').style.background='#f59e0b';"
        "    } else {"
        "      document.getElementById('txtGasPct').innerText=d.gas_pct.toFixed(1)+' %';"
        "      const b=document.getElementById('barGas');"
        "      b.style.width=d.gas_pct+'%';"
        "      b.style.background=d.gas_pct>60?'#ef4444':d.gas_pct>30?'#f59e0b':'#22c55e';"
        "    }"
        "    document.getElementById('txtVolt').innerText=d.v_ema.toFixed(3)+' V (Raw: '+d.v_raw.toFixed(3)+')';"
        "    document.getElementById('txtRsR0').innerText=(d.rs/1000).toFixed(2)+' / '+(d.r0/1000).toFixed(2)+' kΩ';"
        "    document.getElementById('txtRatio').innerText=d.ratio.toFixed(3);"
        "  }catch(e){}"
        "},150);"
        "</script></body></html>";

    httpd_resp_set_type(req, "text/html; charset=utf-8");
    return httpd_resp_send(req, page, HTTPD_RESP_USE_STRLEN);
}

// -------------------------------------------------------------
// Callbacks y Tareas de Captura UVC
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

            ESP_LOGI(TAG, ">> Captura ACTIVA en MJPEG %ux%u a %.0f fps",
                     profiles[i].width, profiles[i].height, profiles[i].fps);
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

    ESP_LOGI(TAG, "Wi-Fi AP Listo: SSID '%s' | Clave '%s' | IP: 192.168.4.1",
             CAMERA_AP_SSID, CAMERA_AP_PASSWORD);
    return ESP_OK;
}

static esp_err_t start_http_servers(void)
{
    // -------------------------------------------------------------
    // 1. Servidor de Telemetria y Control (Puerto 80)
    // -------------------------------------------------------------
    httpd_config_t config_data = HTTPD_DEFAULT_CONFIG();
    config_data.server_port = 80;
    config_data.ctrl_port = 32768;
    config_data.max_open_sockets = 4;
    config_data.stack_size = 4096;
    config_data.lru_purge_enable = true;
    ESP_ERROR_CHECK(httpd_start(&s_http_server, &config_data));

    // Dashboard Web en Puerto 80
    const httpd_uri_t root_uri = {
        .uri = "/", .method = HTTP_GET, .handler = root_handler, .user_ctx = NULL
    };
    ESP_ERROR_CHECK(httpd_register_uri_handler(s_http_server, &root_uri));

    // Telemetria JSON fallback en Puerto 80
    const httpd_uri_t data_uri = {
        .uri = "/data", .method = HTTP_GET, .handler = data_handler, .user_ctx = NULL
    };
    ESP_ERROR_CHECK(httpd_register_uri_handler(s_http_server, &data_uri));

    const httpd_uri_t gas_uri = {
        .uri = "/gas", .method = HTTP_GET, .handler = data_handler, .user_ctx = NULL
    };
    ESP_ERROR_CHECK(httpd_register_uri_handler(s_http_server, &gas_uri));

    // Calibracion R0 en Puerto 80
    const httpd_uri_t calib_uri = {
        .uri = "/calibrate", .method = HTTP_GET, .handler = calibrate_handler, .user_ctx = NULL
    };
    ESP_ERROR_CHECK(httpd_register_uri_handler(s_http_server, &calib_uri));

    // Redireccion /stream en Puerto 80 hacia Puerto 81
    const httpd_uri_t stream_redir_uri = {
        .uri = "/stream", .method = HTTP_GET, .handler = stream_redirect_handler, .user_ctx = NULL
    };
    ESP_ERROR_CHECK(httpd_register_uri_handler(s_http_server, &stream_redir_uri));

    // -------------------------------------------------------------
    // 2. Servidor Dedicado de Streaming MJPEG (Puerto 81 - TCP)
    // -------------------------------------------------------------
    httpd_config_t config_stream = HTTPD_DEFAULT_CONFIG();
    config_stream.server_port = 81;
    config_stream.ctrl_port = 32769; // ctrl_port distinto para no colisionar con puerto 80
    config_stream.max_open_sockets = 2;
    config_stream.stack_size = 8192;
    config_stream.lru_purge_enable = true;
    ESP_ERROR_CHECK(httpd_start(&s_stream_server, &config_stream));

    const httpd_uri_t stream_uri = {
        .uri = "/stream", .method = HTTP_GET, .handler = stream_handler, .user_ctx = NULL
    };
    ESP_ERROR_CHECK(httpd_register_uri_handler(s_stream_server, &stream_uri));

    ESP_LOGI(TAG, "Servidores iniciados:");
    ESP_LOGI(TAG, "  Puerto 80: HTTP Dashboard Web y Calibracion R0");
    ESP_LOGI(TAG, "  Puerto 81: HTTP Streaming MJPEG UVC dedicado (TCP)");
    ESP_LOGI(TAG, "  Puerto UDP %d: Telemetria continua de gas (Broadcast)", GAS_UDP_PORT);
    return ESP_OK;
}

// -------------------------------------------------------------
// Punto de Entrada Principal (app_main)
// -------------------------------------------------------------
void app_main(void)
{
    ESP_LOGI(TAG, "=== ESP32-S3: Sistema Integrado Camara UVC (TCP) & Gas MiCS-5524 (UDP) ===");

    if (!esp_psram_is_initialized()) {
        ESP_LOGE(TAG, "Error: Memoria PSRAM requerida.");
        return;
    }

    s_camera_events = xEventGroupCreate();
    s_frame_mutex = xSemaphoreCreateMutex();
    s_frame_ready = xSemaphoreCreateBinary();
    s_stream_client = xSemaphoreCreateMutex();
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

    // 2. Iniciar Tarea de Muestreo de Gas y Emision UDP (Core 0, 20 Hz)
    xTaskCreatePinnedToCore(gas_sensor_task, "gas_task", 4096, NULL, 4, NULL, 0);

    // 3. Iniciar Wi-Fi SoftAP y Servidores HTTP (Puerto 80 + Puerto 81 TCP)
    ESP_ERROR_CHECK(start_wifi_ap());
    ESP_ERROR_CHECK(start_http_servers());

    // 4. Iniciar USB Host UVC (Core 1)
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

    ESP_LOGI(TAG, "Sistema Integrado Hibrido (Video TCP / Gas UDP) operando al 100%%.");
}
