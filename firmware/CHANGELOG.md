# Historial de Cambios y Versiones de Firmware (CHANGELOG)
## Subsistemas de Control y Telemetría del Hexápodo

Este archivo documenta la trazabilidad de versiones de código para los microcontroladores del proyecto (ESP32 y ESP32-S3), registrando qué se probó, qué errores se descubrieron en el laboratorio y qué versión resolvió el problema.

---

## 🦿 Firmware de Patas Modulares (ESP32 DevKit V1 / ESP32-WROOM-32E + DRV8876 + N20)

### [v1.4] - 2026-10-31 (Versión Validada de 3 Motores)
- **Cambio crítico (Encoder M2):** Se migró el canal B del encoder del Motor 2 de `GPIO 26` a `GPIO 13`.
  - *Causa:* Diafonía capacitiva (*crosstalk*) por jumpers paralelos contiguos en D25 y D26 que eliminaba el desfase de 90° eléctrico, provocando conteo unidireccional. La reubicación a D13 con pull-up interno restableció la lectura bidireccional limpia al 100%.
- **Cambio crítico (Puente H M1):** Se migró `IN2` del Motor 1 de `GPIO 19` a `GPIO 5`.
  - *Causa:* El pin `D19` del ESP32 no modulaba el nivel lógico alto.
- **Resultado:** Operación simultánea y simétrica de los 3 motores (Coxa, Fémur, Tibia) con lectura analógica de corriente en ADC1 (`GPIO 36`, `GPIO 39`, `GPIO 34`).

### [v1.0 - v1.3] - 2026-10-30
- Ensayos iniciales en protoboard de 1 solo motor N20.
- Identificación de diferencias entre placa verde y roja MJKDZ del DRV8876: `OUT1` y `OUT2` invertidos en serigrafía de la placa roja; ausencia de MOSFET de protección en la roja.

---

## 🔬 Firmware de Inspección y Gas (ESP32-S3-DevKitC-1 N16R8)

### ⭐ [VALIDADO_EXITOSO] - 2026-11-09 (Módulo Standalone de Visión UVC Robusto para Raspberry Pi 5 / ROS 2 Jazzy)
- **Estado:** **100% FUNCIONAL Y VERIFICADO EXPERIMENTALMENTE EN ROBOT**
- **Archivos Destacados:**
  - Firmware ESP32-S3: `firmware/esp32s3_camara_gas/VALIDADO_EXITOSO_firmware_esp32s3_camara_solo.c`
  - Nodo Raspberry Pi 5: `pruebas/integradas_camara_gas/pruebas_para_raspberry/VALIDADO_EXITOSO_nodo_camara_solo_raspberry.py`
  - Lanzador Bash Raspberry: `pruebas/integradas_camara_gas/pruebas_para_raspberry/ejecutar_camara_solo_en_raspberry.sh`
  - Visor Laptop OpenCV: `pruebas/camara_usb/VALIDADO_EXITOSO_visor_camara_solo_laptop.py`
- **Resultados de Validación Física:**
  - Enlace Wi-Fi SoftAP `ESP32S3-CAM` (`192.168.4.1`) transmitiendo stream MJPEG por TCP en **puerto 81 (`/stream`)**.
  - **Prueba de Robustez Ante Desconexión/Apagado de Cámara:**
    - Al desconectar o desenergizar la cámara, el firmware emite el cuadro de espera (*Standby Frame*) de 16x16 px a 2 Hz, manteniendo la conexión TCP activa sin provocar *socket timeout* ni bloquear el semáforo del ESP32.
    - Al volver a enchufar la cámara (*Hot-Plug*), el ESP32 detecta el dispositivo USB y conmuta de inmediato a la transmisión de video real a 480x320 px sin reiniciar el microcontrolador.
  - **Integración con ROS 2 Jazzy en Raspberry Pi 5:**
    - El nodo en la Raspberry recibe los fotogramas y los publica con éxito en `/secondary_robot/camera/compressed` (`sensor_msgs/msg/CompressedImage`).
    - Visualización validada en tiempo real mediante **RViz 2** (`Fixed Frame: camera_link_secondary`) y **`rqt_image_view`**.

### [V2 Maestro - v8] - 2026-11-06 (Versión Completa con Control de Luz LED)
- **Ubicación:** `pruebas/integradas_camara_gas/firmware_camara_gas/` y `firmware/esp32s3_camara_gas/`
- **Control de Iluminación en GPIO 48:** 
  - Control de LED direccionable WS2812/SK6812 mediante el periférico por hardware **RMT** a 10 MHz.
  - Endpoint HTTP `/light` en puerto 80 (`?state=1`, `?state=0`, `?state=toggle`).
  - Atajo de teclado `[L]` en visor OpenCV de laptop y tópico ROS 2 `/hexapodo/cmd_luz`.
- **Rendimiento:** Streaming UVC MJPEG estable en puerto 81 TCP y telemetría UDP en puerto 5005 a 20 Hz.
- **Mecanismo Hot-Plug:** Standby frame de 16x16 px a 2 Hz cuando la cámara USB no está enchufada, evitando desconexiones de clientes HTTP.

### [V1 Maestro - v4] - 2026-11-04 (Versión Base Cámara UVC + Gas)
- Separación de núcleos en FreeRTOS:
  - **Core 0:** Muestreo analógico ADC1 CH3 (GPIO 4) a 20 Hz con filtro de mediana ($N=5$) y servidor HTTP.
  - **Core 1:** Driver UVC Host USB nativo y desempaquetado MJPEG en Octal PSRAM.
- Corrección de tierra común (GND flotante) entre la fuente externa de 5V y el ESP32-S3.

### [v2.0 - v3.0] - 2026-11-03 (Cámara UVC Serial y Wi-Fi)
- **v3.0:** Migración a SoftAP Wi-Fi 2.4 GHz (`192.168.4.1`) con endpoint multipart `/stream`.
- **v2.0:** Desacoplamiento de UART mediante doble buffer en Octal PSRAM (`MALLOC_CAP_SPIRAM`), alcanzando 8.7 FPS estables a 480x320 px y 1.5 MBaud.
- **v1.0:** Versión bloqueante que congelaba el bus USB por esperas de transmisión serial.
