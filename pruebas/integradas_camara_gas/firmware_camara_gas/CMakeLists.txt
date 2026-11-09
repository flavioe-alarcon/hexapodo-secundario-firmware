idf_component_register(SRCS "main_v4_camara_gas.c"
                    INCLUDE_DIRS "."
                    PRIV_REQUIRES
                        usb
                        usb_host_uvc
                        esp_timer
                        esp_psram
                        esp_driver_uart
                        esp_wifi
                        esp_http_server
                        esp_netif
                        esp_event
                        esp_adc
                        esp_driver_gpio
                        nvs_flash)
