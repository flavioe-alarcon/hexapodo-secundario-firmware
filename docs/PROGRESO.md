# Estado de Avance y Progreso de Tesis (Semana 13 de 16)

**Proyecto:** Desarrollo de un sistema robótico cooperativo inspirado en insectos para el monitoreo de terrenos accidentados  
**Autores:** Alesky Alcarraz Jaime, Flavio Alarcón Muñoz, Alfredo Francisco Erazo Yalopalin  
**Asesor:** Dante Inga Narváez  
**Última actualización:** 06 de Noviembre de 2026 (Semana 13)

---

## 📊 Resumen Ejecutivo del Estado del Proyecto

| Paquete de Trabajo (EDT) | Descripción | Estado | Responsables principales |
| :--- | :--- | :---: | :--- |
| **EDT 1** (S1-S3) | Revisión bibliográfica, requisitos de diseño (ISO 29148) y normatividad minera | **100% (Completado)** | Todos |
| **EDT 2** (S4-S6) | Diseño mecánico (CAD), electrónico (ECAD) y simulación dinámica en Gazebo | **100% (Completado)** | Alesky / Alfredo / Flavio |
| **EDT 3** (S7-S9) | Fabricación preliminar (impresión 3D, PCBs modulares) e identificación de plantas | **100% (Completado)** | Flavio / Alesky |
| **EDT 4** (S9-S11) | Pruebas de locomoción, ensamble integral y control articular | **100% (Completado)** | Flavio / Alesky / Alfredo |
| **EDT 5** (S11-S14) | Sensado ambiental, integración cooperativa Wi-Fi/UDP y ROS 2 | **90% (Validación física exitosa)** | Alesky (Primario) / Flavio (Secundario) |
| **EDT 6** (S14-S16) | Consolidación de resultados, memoria final en Overleaf y sustentación (S16) | **50% (En redacción activa)** | Todos |

---

## 🎯 Avances Específicos por Robot al Cierre de Semana 13

### 1. Hexápodo Primario (Unidad de Mapeo y Supervisión - Alesky)
* **Hardware:**
  - Chasis Chipo operativo con 18 servos metálicos MG996R y batería Li-ion/LiPo 3S 4500 mAh.
  - Raspberry Pi 5 acoplada vía USB a controladora Pololu Mini Maestro de 18 canales.
  - Sensor RGB-D Orbbec Gemini 2 montado y calibrado con soporte de trayectorias.
  - **Subsistema de Telemetría de Potencia y Sensado de Gas (Validado 18-20/11/2026):**
    - Sensor de corriente de efecto Hall Allegro **ACS758LCB-050B** ($\pm 50\text{ A}$, $40\text{ mV/A}$) conectado en serie con la batería LiPo 3S (Pin `A1`).
    - Sensor de gases semiconductores **MQ-9** (Etanol / Monóxido de Carbono / Combustibles) con lectura analógica en Pin `A0` y alarma digital LM393 en Pin `D2`.
    - Firmware integrado en Arduino Nano (`firmware_mq9_corriente_nano.ino`) emitiendo tramas JSON a 115200 baudios (20 Hz) vía USB (`/dev/ttyUSB0`) hacia la **Raspberry Pi 5** y PC.
    - Herramientas validadas: monitor de consola en RPi (`monitor_sensores_rpi.py`), visor interactivo con osciloscopio en OpenCV (`visor_gas_mq9.py`) y documentación completa en `pruebas/sensor_gas/firmware_mq9_corriente_nano/README.md`.
* **Software y ROS 2:**
  - Repositorio `ros2_ws` sincronizado (último commit: `bd419a4`).
  - Drivers de control en `MasterPololu` (perfiles HOME S2, cinemática y trayectorias de 36 s).
  - Submódulo oficial `OrbbecSDK_ROS2` (v2.10.6) operativo.
  - Paquete `hexapod_mapping` con RTAB-Map configurado para cierre de lazo con odometría visual-inercial.
  - Configuración DDS por FastDDS Ethernet (`fastdds_ethernet.xml`) para enlace directo con la laptop de control.

### 2. Hexápodo Secundario (Unidad Exploradora Ligera - Flavio)
* **Mecánica y Hardware:**
  - Chasis hexagonal en PLA de mínima envolvente con 6 patas articuladas (3 DoF cada una).
  - 18 micromotores N20 1:300 12V con reductora metálica y encoders magnéticos de cuadratura.
  - 6 PCBs modulares idénticas e independientes (ESP32-WROOM-32E + 3x DRV8876).
* **Control Articular en Cascada Validado:**
  - Lazo de corriente (1 kHz), velocidad (100 Hz) y posición (50 Hz).
  - Pines validados y filtrados contra diafonía (`D13` para canal B de encoder, `D5` para inversión de giro).
* **Módulo de Percepción y Gas (ESP32-S3 N16R8):**
  - Streaming UVC MJPEG sobre Wi-Fi SoftAP autónomo (TCP p81) a 8-10 FPS.
  - Telemetría analógica del sensor MiCS-5524 por UDP (p5005 a 20 Hz) con filtro de mediana ($N=5$).
  - Mecanismo *Hot-Plug* con cuadro de espera JPEG (*Standby Frame*) que previene caídas del servidor ante desconexión física.
  - Iluminación de inspección LED direccionable WS2812 (GPIO 48) vía periférico hardware RMT a 10 MHz con control remoto `/light`.
  - **Prueba Física Validada y Exitosa con Raspberry Pi 5 (09/11/2026):** Verificación integral del módulo standalone de cámara (`VALIDADO_EXITOSO_firmware_esp32s3_camara_solo.c` y `VALIDADO_EXITOSO_nodo_camara_solo_raspberry.py`), publicando fluidamente en el tópico ROS 2 Jazzy `/secondary_robot/camera/compressed` y comprobado en tiempo real en RViz 2 y `rqt_image_view`. Robustez comprobada: soporta desconexión física de cámara sin interrumpir el socket TCP ni colgar el microcontrolador.
  - **Validación Integral Wi-Fi STA en Red de Misión Autónoma (14/11/2026):** 
    - Firmware Maestro Integral (`VALIDADO_EXITOSO_firmware_esp32s3_sta_camara_gas_luz.c`) operando en modo Estación (STA) asociado al Hotspot del primario (`aleskypi-5`, IP `10.42.0.1`).
    - Flujo simultáneo validado: Video UVC MJPEG 480x320 a **14.9 FPS estables (TCP 81)**, telemetría de gas MiCS-5524 a **20 Hz (UDP 5005)** y conmutación de luz de inspección WS2812 en GPIO 48 por RMT a 10 MHz (`/light`).
    - Tablero TUI para consola SSH en Raspberry Pi 5 (`monitor_hexapodo.py`) con control interactivo por teclado (`[L]` para luz, `[C]` para calibrar $R_0$).
    - Validación de enlace multirred en laptop mediante adaptador USB TP-Link TL-WN725N (6 ms de latencia al RPi 5 sin perder internet en la tarjeta interna).
    - Operación móvil autónoma validada alimentado por banco de baterías USB portátil.
  - **Formulación del Subsistema de Relocalización Visual Cooperativa 2D-to-3D:**
    - Arquitectura multi-agente diseñada: El robot secundario se localiza en el mapa 3D previo del primario (`hexapod_mapa.db` de RTAB-Map) mediante emparejamiento de características 2D (cámara UVC) con landmarks métricos 3D (Orbbec Gemini 2) y resolución de pose 6-DoF mediante optimización PnP-RANSAC.

---

## 🚀 Próximos Pasos Inmediatos (Semanas 13 - 14)
1. **Cierre de EDT 5:**
   - Ensayo de campo conjunto: Hexápodo secundario transmitiendo video + gas vía Wi-Fi mientras el hexápodo primario procesa telemetría y ejecuta mapeo con la Orbbec Gemini 2.
   - Calibración intrínseca de la cámara monocular UVC con patrón de ajedrez para fijar la matriz $\mathbf{K}$ requerida por PnP-RANSAC.
2. **Arranque de EDT 6 (Semana 14 a 16):**
   - Redacción intensiva en Overleaf:
     - Volcar los resultados de control del Capítulo 7 (funciones de transferencia identificadas y sintonización PI).
     - Consolidar en el Capítulo 8/9 los mapas de gases y nubes de puntos 3D.
   - Revisión del documento completo con el asesor Dante Inga para la sustentación oral final en **Semana 16**.
