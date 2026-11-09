idf_component_register(SRCS "main_camara_solo.c"
                    INCLUDE_DIRS "."
                    PRIV_REQUIRES
                        usb
                        usb_host_uvc
                        esp_timer
                        esp_psram
                        esp_wifi
                        esp_http_server
                        esp_netif
                        esp_event
                        nvs_flash)
