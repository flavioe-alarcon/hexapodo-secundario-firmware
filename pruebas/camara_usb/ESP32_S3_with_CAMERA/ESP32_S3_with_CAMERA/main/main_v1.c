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

#define CAMERA_STREAM_INDEX     0
#define CAMERA_JPEG_MAX_BYTES   (512 * 1024)
#define SERIAL_BAUD_RATE        921600

#define CAMERA_CONNECTED_BIT    BIT0
#define CAMERA_DISCONNECTED_BIT BIT1
#define CAMERA_TRANSFER_ERROR_BIT BIT2

static const char *TAG = "usb_camera_serial";
static EventGroupHandle_t s_camera_events;
static SemaphoreHandle_t s_frame_mutex;
static uint8_t *s_latest_jpeg;
static size_t s_latest_jpeg_len;
static uint32_t s_frame_sequence;
static int64_t s_frame_timestamp_us;
static uint16_t s_frame_width;
static uint16_t s_frame_height;
static float s_measured_fps;
static bool s_camera_present;
static bool s_camera_streaming;

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
    case UVC_VS_FORMAT_MJPEG:
        return "MJPEG";
    case UVC_VS_FORMAT_YUY2:
        return "YUY2";
    case UVC_VS_FORMAT_H264:
        return "H.264";
    case UVC_VS_FORMAT_H265:
        return "H.265";
    case UVC_VS_FORMAT_NV12:
        return "NV12";
    default:
        return "desconocido";
    }
}

static void log_camera_modes(uint8_t dev_addr, uint8_t stream_index,
                             size_t reported_count)
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
        float fps = modes[i].default_interval
                        ? 10000000.0f / modes[i].default_interval
                        : 0.0f;
        ESP_LOGI(TAG, "  %s %ux%u, fps predeterminado %.1f",
                 format_name(modes[i].format), modes[i].h_res,
                 modes[i].v_res, fps);
    }
    free(modes);
}

static void uvc_driver_event_callback(const uvc_host_driver_event_data_t *event,
                                      void *user_ctx)
{
    (void)user_ctx;

    if (event->type != UVC_HOST_DRIVER_EVENT_DEVICE_CONNECTED) {
        return;
    }

    xSemaphoreTake(s_frame_mutex, portMAX_DELAY);
    s_camera_present = true;
    xSemaphoreGive(s_frame_mutex);

    ESP_LOGI(TAG, "Cámara UVC conectada: USB addr=%u, stream=%u",
             event->device_connected.dev_addr,
             event->device_connected.uvc_stream_index);

    log_camera_modes(event->device_connected.dev_addr,
                     event->device_connected.uvc_stream_index,
                     event->device_connected.frame_info_num);
    xEventGroupSetBits(s_camera_events, CAMERA_CONNECTED_BIT);
}

// Callback cuando un fotograma completo JPEG llega desde la cámara
static bool frame_callback(const uvc_host_frame_t *frame, void *user_ctx)
{
    (void)user_ctx;

    static int64_t last_report_us = 0;
    static unsigned frames = 0;
    static size_t bytes = 0;

    if (frame == NULL || frame->data == NULL || frame->data_len == 0) {
        return true;
    }

    if (frame->data_len <= CAMERA_JPEG_MAX_BYTES) {
        // Protocolo binario de alta velocidad por UART (Puerto COM):
        // Encabezado (4B): 0xFF 0xAA 0x55 0xFF
        // Longitud (4B): uint32 little-endian
        // Ancho (2B): uint16
        // Alto (2B): uint16
        // Secuencia (4B): uint32
        // Datos JPEG (N bytes)
        // Pie (2B): 0x00 0xFF
        static uint32_t s_tx_seq = 0;
        s_tx_seq++;

        uint8_t header[16];
        header[0] = 0xFF; header[1] = 0xAA; header[2] = 0x55; header[3] = 0xFF;
        uint32_t dlen = (uint32_t)frame->data_len;
        memcpy(&header[4], &dlen, 4);
        uint16_t w = frame->vs_format.h_res;
        uint16_t h = frame->vs_format.v_res;
        memcpy(&header[8], &w, 2);
        memcpy(&header[10], &h, 2);
        memcpy(&header[12], &s_tx_seq, 4);

        uart_write_bytes(UART_NUM_0, (const char *)header, sizeof(header));
        uart_write_bytes(UART_NUM_0, (const char *)frame->data, frame->data_len);
        
        uint8_t footer[2] = {0x00, 0xFF};
        uart_write_bytes(UART_NUM_0, (const char *)footer, sizeof(footer));
    }

    frames++;
    bytes += frame->data_len;

    const int64_t now = esp_timer_get_time();
    if (last_report_us == 0) {
        last_report_us = now;
    } else if (now - last_report_us >= 1000000) {
        const float fps = frames * 1000000.0f / (now - last_report_us);
        xSemaphoreTake(s_frame_mutex, portMAX_DELAY);
        s_measured_fps = fps;
        xSemaphoreGive(s_frame_mutex);
        frames = 0;
        bytes = 0;
        last_report_us = now;
    }

    return true;
}

static void uvc_stream_event_callback(const uvc_host_stream_event_data_t *event,
                                      void *user_ctx)
{
    (void)user_ctx;

    switch (event->type) {
    case UVC_HOST_TRANSFER_ERROR:
        ESP_LOGE(TAG, "Error de transferencia UVC: %s",
                 esp_err_to_name(event->transfer_error.error));
        xEventGroupSetBits(s_camera_events, CAMERA_TRANSFER_ERROR_BIT);
        break;

    case UVC_HOST_DEVICE_DISCONNECTED: {
        ESP_LOGW(TAG, "Cámara desconectada");
        xSemaphoreTake(s_frame_mutex, portMAX_DELAY);
        s_camera_present = false;
        s_camera_streaming = false;
        s_latest_jpeg_len = 0;
        xSemaphoreGive(s_frame_mutex);
        esp_err_t err = uvc_host_stream_close(event->device_disconnected.stream_hdl);
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "Error cerrando el stream: %s", esp_err_to_name(err));
        }
        xEventGroupClearBits(s_camera_events, CAMERA_CONNECTED_BIT);
        xEventGroupSetBits(s_camera_events, CAMERA_DISCONNECTED_BIT);
        break;
    }

    case UVC_HOST_FRAME_BUFFER_OVERFLOW:
        ESP_LOGW(TAG, "Cuadro descartado: excedió el buffer; aumenta frame_size");
        break;

    case UVC_HOST_FRAME_BUFFER_UNDERFLOW:
        ESP_LOGW(TAG, "Cuadro descartado: no había buffer libre");
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
        {320, 240, 15.0f},
        {1280, 720, 10.0f},
    };

    while (true) {
        xEventGroupWaitBits(s_camera_events, CAMERA_CONNECTED_BIT,
                            pdTRUE, pdFALSE, portMAX_DELAY);
        xEventGroupClearBits(s_camera_events,
                             CAMERA_DISCONNECTED_BIT | CAMERA_TRANSFER_ERROR_BIT);

        bool streaming = false;
        for (size_t i = 0; i < sizeof(profiles) / sizeof(profiles[0]); ++i) {
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

            uvc_host_stream_hdl_t stream = NULL;
            ESP_LOGI(TAG, "Intentando MJPEG %ux%u a %.0f fps...",
                     profiles[i].width, profiles[i].height, profiles[i].fps);
            esp_err_t err = uvc_host_stream_open(
                &stream_config, pdMS_TO_TICKS(5000), &stream);
            if (err != ESP_OK) {
                ESP_LOGW(TAG, "No se pudo abrir ese modo: %s", esp_err_to_name(err));
                continue;
            }

            uvc_host_desc_print(stream);
            err = uvc_host_stream_start(stream);
            if (err != ESP_OK) {
                ESP_LOGW(TAG, "No se pudo iniciar ese modo: %s", esp_err_to_name(err));
                uvc_host_stream_close(stream);
                continue;
            }

            ESP_LOGI(TAG, "Captura iniciada en MJPEG %ux%u a %.0f fps -> Transmitiendo por COM",
                     profiles[i].width, profiles[i].height, profiles[i].fps);
            xSemaphoreTake(s_frame_mutex, portMAX_DELAY);
            s_camera_streaming = true;
            xSemaphoreGive(s_frame_mutex);
            streaming = true;

            EventBits_t result = xEventGroupWaitBits(
                s_camera_events,
                CAMERA_DISCONNECTED_BIT | CAMERA_TRANSFER_ERROR_BIT,
                pdTRUE, pdFALSE, portMAX_DELAY);

            if (result & CAMERA_TRANSFER_ERROR_BIT) {
                ESP_LOGW(TAG, "Se detuvo el stream por error USB");
                xSemaphoreTake(s_frame_mutex, portMAX_DELAY);
                s_camera_streaming = false;
                s_latest_jpeg_len = 0;
                xSemaphoreGive(s_frame_mutex);
                uvc_host_stream_stop(stream);
                uvc_host_stream_close(stream);
            }
            break;
        }

        if (!streaming &&
            (xEventGroupGetBits(s_camera_events) & CAMERA_CONNECTED_BIT)) {
            ESP_LOGE(TAG, "No se pudo iniciar ningún modo UVC; reconecta la cámara");
        }
    }
}

void app_main(void)
{
    // 1. Configuración de UART0 a 921600 baudios para transmisión rápida de video
    uart_config_t uart_config = {
        .baud_rate = SERIAL_BAUD_RATE,
        .data_bits = UART_DATA_8_BITS,
        .parity    = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    uart_param_config(UART_NUM_0, &uart_config);
    uart_driver_install(UART_NUM_0, 4096, 4096, 0, NULL, 0);

    // 2. Verificación de Octal PSRAM
    if (!esp_psram_is_initialized()) {
        ESP_LOGE(TAG, "No se detectó PSRAM; se requiere para los buffers UVC");
        return;
    }

    s_camera_events = xEventGroupCreate();
    assert(s_camera_events != NULL);
    s_frame_mutex = xSemaphoreCreateMutex();
    assert(s_frame_mutex != NULL);

    s_latest_jpeg = heap_caps_malloc(CAMERA_JPEG_MAX_BYTES, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (s_latest_jpeg == NULL) {
        ESP_LOGE(TAG, "No se pudo reservar buffer JPEG en PSRAM");
        return;
    }

    init_nvs();

    // 3. Inicialización del Host USB (OTG)
    const usb_host_config_t host_config = {
        .skip_phy_setup = false,
        .intr_flags = ESP_INTR_FLAG_LEVEL1,
    };
    ESP_ERROR_CHECK(usb_host_install(&host_config));
    ESP_LOGI(TAG, "USB Host iniciado. Conecta la camara al puerto USB nativo (con VBUS 5V).");

    if (xTaskCreate(usb_host_events_task, "usb_host_events", 4096, NULL, 5, NULL) != pdPASS) {
        ESP_LOGE(TAG, "No se pudo crear la tarea de eventos USB");
        abort();
    }

    if (xTaskCreate(camera_stream_task, "camera_stream", 6144, NULL, 4, NULL) != pdPASS) {
        ESP_LOGE(TAG, "No se pudo crear la tarea de captura UVC");
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
    ESP_LOGI(TAG, "Driver UVC nativo instalado; transmitiendo directamente por COM a %d baud", SERIAL_BAUD_RATE);
}
