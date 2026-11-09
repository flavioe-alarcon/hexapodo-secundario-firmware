#include <assert.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "esp_err.h"
#include "esp_heap_caps.h"
#include "esp_intr_alloc.h"
#include "esp_log.h"
#include "esp_psram.h"
#include "esp_timer.h"
#include "driver/uart.h"
#include "nvs_flash.h"
#include "usb/usb_host.h"
#include "usb/uvc_host.h"

#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/semphr.h"
#include "freertos/task.h"

#define CAMERA_STREAM_INDEX       0
#define CAMERA_JPEG_MAX_BYTES     (256 * 1024)
#define SERIAL_BAUD_RATE          1500000

#define CAMERA_CONNECTED_BIT      BIT0
#define CAMERA_DISCONNECTED_BIT   BIT1
#define CAMERA_TRANSFER_ERROR_BIT BIT2

static const char *TAG = "usb_camera_v2";

static EventGroupHandle_t s_camera_events;
static SemaphoreHandle_t s_buf_mutex;
static TaskHandle_t s_tx_task_hdl;

// Doble buffer en Octal PSRAM para desacoplar captura USB de envio serial
static uint8_t *s_tx_buf[2];
static size_t s_tx_len[2];
static uint16_t s_tx_w[2];
static uint16_t s_tx_h[2];
static uint32_t s_tx_seq[2];

static volatile int s_ready_idx = -1;
static volatile int s_writing_idx = 0;

static volatile bool s_camera_present = false;
static volatile bool s_camera_streaming = false;

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
            ESP_LOGE(TAG, "Error atendiendo eventos USB: %s", esp_err_to_name(err));
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
    if (count == 0) {
        ESP_LOGW(TAG, "La cámara no reportó modos de video para el stream %u", stream_index);
        return;
    }

    uvc_host_frame_info_t *modes = calloc(count, sizeof(*modes));
    if (modes == NULL) {
        ESP_LOGE(TAG, "Sin memoria para leer los modos UVC");
        return;
    }

    esp_err_t err = uvc_host_get_frame_list(
        dev_addr, stream_index, (uvc_host_frame_info_t (*)[])modes, &count);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "No se pudieron leer los modos UVC: %s", esp_err_to_name(err));
        free(modes);
        return;
    }

    ESP_LOGI(TAG, "La cámara anuncia %u modos:", (unsigned)count);
    for (size_t i = 0; i < count; ++i) {
        float fps = modes[i].default_interval ? 10000000.0f / modes[i].default_interval : 0.0f;
        ESP_LOGI(TAG, "  %s %ux%u, fps predeterminado %.1f",
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

// Callback de recepción UVC ultrarrápido y NO bloqueante (Drop-Frame inteligente)
static bool frame_callback(const uvc_host_frame_t *frame, void *user_ctx)
{
    (void)user_ctx;

    if (frame == NULL || frame->data == NULL || frame->data_len == 0) {
        return true;
    }
    if (frame->data_len > CAMERA_JPEG_MAX_BYTES) {
        return true;
    }

    // Intentar tomar el mutex sin bloquear (0 ticks).
    // Si la tarea UART está transmitiendo, no bloqueamos el bus USB: descartamos este cuadro.
    if (xSemaphoreTake(s_buf_mutex, 0) == pdTRUE) {
        int idx = s_writing_idx;
        memcpy(s_tx_buf[idx], frame->data, frame->data_len);
        s_tx_len[idx] = frame->data_len;
        s_tx_w[idx] = frame->vs_format.h_res;
        s_tx_h[idx] = frame->vs_format.v_res;
        static uint32_t s_seq = 0;
        s_tx_seq[idx] = ++s_seq;

        s_ready_idx = idx;
        // Alternar buffer de escritura
        s_writing_idx = 1 - idx;

        xSemaphoreGive(s_buf_mutex);

        // Notificar a la tarea de transmisión UART
        if (s_tx_task_hdl != NULL) {
            xTaskNotifyGive(s_tx_task_hdl);
        }
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
        ESP_LOGW(TAG, "Cámara desconectada físicamente");
        s_camera_present = false;
        s_camera_streaming = false;
        xEventGroupClearBits(s_camera_events, CAMERA_CONNECTED_BIT);
        xEventGroupSetBits(s_camera_events, CAMERA_DISCONNECTED_BIT);
        break;

    case UVC_HOST_FRAME_BUFFER_OVERFLOW:
        ESP_LOGW(TAG, "Cuadro UVC descartado por desbordamiento");
        break;

    case UVC_HOST_FRAME_BUFFER_UNDERFLOW:
        ESP_LOGW(TAG, "Cuadro UVC descartado por buffer no disponible");
        break;

    default:
        break;
    }
}

// Tarea dedicada a transmitir cuadros por la UART sin bloquear la captura USB
static void serial_tx_task(void *arg)
{
    (void)arg;
    static const uint8_t magic_header[4] = {0xFF, 0xAA, 0x55, 0xFF};
    static const uint8_t magic_footer[2] = {0x00, 0xFF};
    uint8_t packet_header[16];
    memcpy(packet_header, magic_header, 4);

    int64_t last_heartbeat_us = 0;

    while (true) {
        // Esperar notificación de nuevo cuadro disponible (hasta 1 segundo)
        uint32_t count = ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(1000));
        if (count > 0 && s_ready_idx != -1) {
            int idx = -1;
            size_t len = 0;
            uint16_t w = 0, h = 0;
            uint32_t seq = 0;

            if (xSemaphoreTake(s_buf_mutex, portMAX_DELAY) == pdTRUE) {
                idx = s_ready_idx;
                s_ready_idx = -1; // Cuadro consumido
                if (idx >= 0 && idx < 2) {
                    len = s_tx_len[idx];
                    w = s_tx_w[idx];
                    h = s_tx_h[idx];
                    seq = s_tx_seq[idx];
                }
                xSemaphoreGive(s_buf_mutex);
            }

            if (idx >= 0 && len > 0 && len <= CAMERA_JPEG_MAX_BYTES) {
                uint32_t dlen = (uint32_t)len;
                memcpy(&packet_header[4], &dlen, 4);
                memcpy(&packet_header[8], &w, 2);
                memcpy(&packet_header[10], &h, 2);
                memcpy(&packet_header[12], &seq, 4);

                uart_write_bytes(UART_NUM_0, (const char *)packet_header, sizeof(packet_header));
                uart_write_bytes(UART_NUM_0, (const char *)s_tx_buf[idx], len);
                uart_write_bytes(UART_NUM_0, (const char *)magic_footer, sizeof(magic_footer));
            }
        } else {
            // Heartbeat cuando no hay cuadros
            int64_t now = esp_timer_get_time();
            if (now - last_heartbeat_us >= 2500000) {
                last_heartbeat_us = now;
                if (!s_camera_present) {
                    ESP_LOGI(TAG, "Esperando conexión de cámara UVC (puerto USB nativo con 5V VBUS)...");
                } else if (!s_camera_streaming) {
                    ESP_LOGI(TAG, "Cámara detectada; iniciando stream...");
                }
            }
        }
    }
}

// Tarea principal de supervisión y gestión UVC
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
        {320, 240, 20.0f},
        {1280, 720, 10.0f},
    };

    while (true) {
        ESP_LOGI(TAG, "Esperando que la cámara esté conectada...");
        xEventGroupWaitBits(s_camera_events, CAMERA_CONNECTED_BIT,
                            pdFALSE, pdFALSE, portMAX_DELAY);

        xEventGroupClearBits(s_camera_events,
                             CAMERA_DISCONNECTED_BIT | CAMERA_TRANSFER_ERROR_BIT);

        bool streaming = false;
        uvc_host_stream_hdl_t stream = NULL;

        for (size_t i = 0; i < sizeof(profiles) / sizeof(profiles[0]); ++i) {
            if (!s_camera_present) {
                break;
            }

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
                ESP_LOGW(TAG, "No se pudo iniciar captura: %s", esp_err_to_name(err));
                uvc_host_stream_close(stream);
                stream = NULL;
                continue;
            }

            ESP_LOGI(TAG, ">> Captura ACTIVA en MJPEG %ux%u a %.0f fps -> UART @ %d baud",
                     profiles[i].width, profiles[i].height, profiles[i].fps, SERIAL_BAUD_RATE);
            s_camera_streaming = true;
            streaming = true;

            // Esperar desconexión física o error USB
            EventBits_t result = xEventGroupWaitBits(
                s_camera_events,
                CAMERA_DISCONNECTED_BIT | CAMERA_TRANSFER_ERROR_BIT,
                pdTRUE, pdFALSE, portMAX_DELAY);

            s_camera_streaming = false;

            if (result & CAMERA_DISCONNECTED_BIT) {
                ESP_LOGW(TAG, "Cámara desconectada físicamente del puerto USB");
                uvc_host_stream_close(stream);
                stream = NULL;
                break;
            }

            if (result & CAMERA_TRANSFER_ERROR_BIT) {
                ESP_LOGW(TAG, "Error USB transitorio; reintentando en 500 ms...");
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
    // 1. Configuración de UART0 de alta velocidad (1,500,000 baudios)
    uart_config_t uart_config = {
        .baud_rate = SERIAL_BAUD_RATE,
        .data_bits = UART_DATA_8_BITS,
        .parity    = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    uart_param_config(UART_NUM_0, &uart_config);
    uart_driver_install(UART_NUM_0, 8192, 8192, 0, NULL, 0);

    // 2. Comprobar memoria Octal PSRAM de 8 MB
    if (!esp_psram_is_initialized()) {
        ESP_LOGE(TAG, "No se detectó PSRAM; se requiere para buffers UVC");
        return;
    }

    s_camera_events = xEventGroupCreate();
    assert(s_camera_events != NULL);
    s_buf_mutex = xSemaphoreCreateMutex();
    assert(s_buf_mutex != NULL);

    // Reservar 2 buffers en PSRAM para intercambio ultrarrápido
    s_tx_buf[0] = heap_caps_malloc(CAMERA_JPEG_MAX_BYTES, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    s_tx_buf[1] = heap_caps_malloc(CAMERA_JPEG_MAX_BYTES, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (s_tx_buf[0] == NULL || s_tx_buf[1] == NULL) {
        ESP_LOGE(TAG, "Error reservando buffers en PSRAM");
        return;
    }

    init_nvs();

    // 3. Crear tarea de transmisión UART desacoplada
    if (xTaskCreatePinnedToCore(serial_tx_task, "serial_tx", 4096, NULL, 5, &s_tx_task_hdl, 1) != pdPASS) {
        ESP_LOGE(TAG, "No se pudo crear la tarea serial_tx");
        abort();
    }

    // 4. Instalar USB Host nativo
    const usb_host_config_t host_config = {
        .skip_phy_setup = false,
        .intr_flags = ESP_INTR_FLAG_LEVEL1,
    };
    ESP_ERROR_CHECK(usb_host_install(&host_config));
    ESP_LOGI(TAG, "USB Host iniciado. Esperando cámara...");

    if (xTaskCreate(usb_host_events_task, "usb_host_events", 4096, NULL, 5, NULL) != pdPASS) {
        ESP_LOGE(TAG, "No se pudo crear tarea eventos USB");
        abort();
    }

    if (xTaskCreate(camera_stream_task, "camera_stream", 6144, NULL, 4, NULL) != pdPASS) {
        ESP_LOGE(TAG, "No se pudo crear tarea captura UVC");
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
    ESP_LOGI(TAG, "Firmware V2 activo; transmisión desacoplada a %d baudios", SERIAL_BAUD_RATE);
}
