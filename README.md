# Hexápodo Secundario: Firmware Embebido, Control en Cascada y Percepción Ambiental

> **Proyecto Final de Carrera — Tesis de Ingeniería Mecatrónica (UTEC, 2026)**  
> **Tema:** *Desarrollo de un sistema robótico cooperativo inspirado en insectos para el monitoreo de terrenos accidentados*  
> **Autores:** Flavio Alarcón Muñoz, Alesky Alcarraz Jaime, Alfredo Francisco Erazo Yalopalin  
> **Asesor:** Dante Inga Narváez  

---

## 📌 Descripción del Proyecto

Este repositorio contiene el desarrollo del **Hexápodo Secundario (Unidad Exploradora Ligera de Mínima Envolvente)**, concebido para operar bajo el enfoque de **inspección sin ingreso (*no-entry*)** en minería subterránea y zonas colapsadas (conforme a los estándares de seguridad del **D.S. N° 024-2016-EM**).

A diferencia de la unidad primaria de supervisión y mapeo central (Raspberry Pi 5 + Orbbec Gemini 2), la unidad secundaria prioriza dimensiones mínimas, locomoción ágil sobre terreno quebrado y acceso a conductos o hendiduras estrechas donde existe riesgo de atmósferas tóxicas o deficientes de oxígeno.

```
       [Hexápodo Primario (Base)]
         (Raspberry Pi 5 / ROS 2)
                 ▲
                 │ Enlace Wi-Fi SoftAP (2.4 GHz)
                 │ Telemetría UDP (p5005) + Streaming MJPEG (p81)
                 ▼
     [Hexápodo Secundario (Explorador)]
  ├── Cabeza: ESP32-S3 (Cámara UVC + Gas MiCS-5524 + Luz WS2812)
  └── Chasis: 6x Placas Modulares (ESP32 + 3x DRV8876 + N20 1:300)
```

---

## ⚙️ Arquitectura del Sistema

### 1. Mecánica Biomimética y Actuación
* **Chasis:** Estructura hexagonal ligera en PLA (8% grid infill, 3 perímetros).
* **Extremidades 3 DoF:** Proporción biomimética 1x:2x:3x (Coxa: 30 mm, Fémur: 60 mm, Tibia: 90 mm; relación Fémur-Tibia 4:6).
* **Actuadores:** 18 micromotores **DC N20 con reductora metálica 1:300 (12V, 300 RPM)** y encoders magnéticos de cuadratura de efecto Hall.

### 2. Electrónica Modular Distribuida
* **6 Placas PCB Modulares e Intercambiables (una por extremidad):**
  - Microcontrolador: **ESP32-WROOM-32E (16 MB)**.
  - Drivers: 3x puentes H integrados **DRV8876** (límite por hardware de 1.1 A, sensado analógico de corriente `IPROPI`, salida de diagnóstico `nFAULT` en `IO4`).
  - Conectores JST-SH de 6 pines y regulador LDO AMS1117-3.3.

### 3. Control Articular en Cascada (3 Lazos Anidados)
1. **Lazo de Corriente (1 kHz):** Muestreo continuo por ADC DMA a 200 kS/s con protección contra sobrecorriente y absorción de impactos mecánicos.
2. **Lazo de Velocidad (100 Hz):** Compensación de fricción no lineal y carga variable en fase de apoyo.
3. **Lazo de Posición (50 Hz):** Conteo de pulsos de cuadratura por hardware mediante el periférico **PCNT** del ESP32.

### 4. Módulo de Inspección Visual y Ambiental (ESP32-S3 N16R8)
* **Sensor de Gases MEMS MiCS-5524:** Detección de $CO$ (1 a 1000 ppm), etanol y gases reductores.
  - Cadena de transducción con divisor de tensión calibrado en aire limpio ($R_0$) y modelo de Wolkenstein-Clifford.
  - Filtro de Mediana ($N=5$) para navegación continua y filtro exponencial EMA ($\alpha=0.20$) para punto fijo.
* **Cámara Mini USB Type-C UVC:** Conexión nativa como Host USB con descompresión/streaming MJPEG sin dependencias de routers externos.
* **Mecanismo Hot-Plug:** Cuadro de espera (*Standby Frame*) de 16x16 px a 2 Hz que previene desconexiones del cliente si la cámara no está enchufada al arrancar.
* **Iluminación de Inspección:** LED direccionable WS2812 (GPIO 48) controlado por hardware mediante el periférico **RMT** a 10 MHz con comando HTTP `/light`.

---

## 📁 Estructura del Repositorio

```text
├── docs/                      ← Documentación técnica de diseño
│   ├── DECISIONES.md          ← Registro de Decisiones de Arquitectura (ADR)
│   ├── PROGRESO.md            ← Bitácora semanal de avance (Semana 13 de 16)
│   └── CorreccionInformeParcial/
│
├── firmware/                  ← Firmware embebido para microcontroladores
│   ├── CHANGELOG.md           ← Trazabilidad de versiones y bugs resueltos
│   ├── esp32_patas_modular/   ← Código Arduino/C++ para control de extremidades
│   └── esp32s3_camara_gas/    ← Firmware ESP-IDF (Cámara UVC + Gas + Wi-Fi)
│
├── pruebas/                   ← Validación experimental y herramientas de diagnóstico
│   ├── motores_encoders/      ← Scripts de test, inversión y visor WebSerial
│   ├── sensor_gas/            ← Calibración R0/Rs, curvas de analitos y visores
│   ├── camara_usb/            ← Visores OpenCV serial y Wi-Fi
│   ├── integradas_camara_gas/ ← Entorno integrado de visión, gas, lanzadores .bat y nodo ROS 2 simulado
│   └── datos_mision/          ← CSVs de telemetría de misiones de prueba
│
├── CONTEXTO_TESIS.md          ← Especificaciones cuantitativas ISO 29148 y funciones G(s)
├── LICENSE.txt                ← Licencia de código
└── README.md                  ← Este archivo
```

---

## 🚀 Puesta en Marcha y Diagnóstico

### ⭐ Módulo Validado y Exitoso: Streaming de Cámara UVC y Publicador ROS 2 Jazzy
Este módulo ha sido **probado físicamente con éxito** conectando el ESP32-S3 y la Raspberry Pi 5 con visualización en tiempo real en RViz 2 y rqt_image_view:

* **Firmware ESP32-S3:** [`firmware/esp32s3_camara_gas/VALIDADO_EXITOSO_firmware_esp32s3_camara_solo.c`](firmware/esp32s3_camara_gas/VALIDADO_EXITOSO_firmware_esp32s3_camara_solo.c)
* **Nodo Receptor Raspberry Pi 5:** [`pruebas/integradas_camara_gas/pruebas_para_raspberry/VALIDADO_EXITOSO_nodo_camara_solo_raspberry.py`](pruebas/integradas_camara_gas/pruebas_para_raspberry/VALIDADO_EXITOSO_nodo_camara_solo_raspberry.py)
* **Lanzador rápido en Raspberry:**
  ```bash
  cd pruebas/integradas_camara_gas/pruebas_para_raspberry
  ./ejecutar_camara_solo_en_raspberry.sh
  ```
* **Visualización en ROS 2:**
  ```bash
  ros2 run rqt_image_view rqt_image_view /secondary_robot/camera/compressed
  ```
  *(O en RViz 2 configurando `Fixed Frame: camera_link_secondary` y agregando el display `Image` con `Transport Hint: compressed`).*

### Visores de Telemetría en Tiempo Real (Python)
Para monitorear el subsistema de visión y gas desde una laptop conectada a la red Wi-Fi `ESP32S3-CAM`:

```bash
# Navegar a la carpeta integrada
cd pruebas/integradas_camara_gas

# Ejecutar el visor de telemetría con control de iluminación
python visor_integrado_con_luz.py http://192.168.4.1
```
*(Atajo: Presiona `[L]` en la ventana OpenCV para conmutar la luz LED).*

### Diagnóstico de Encoders y Motores N20 (WebSerial)
Para validar el sentido de giro y la cuadratura de los encoders sin necesidad de software instalado:
1. Abre el navegador Google Chrome o Edge.
2. Carga el archivo [`pruebas/motores_encoders/visor_encoders.html`](pruebas/motores_encoders/visor_encoders.html).
3. Conecta el ESP32 por USB y presiona **Conectar Puerto Serie**.

---

## 📄 Licencia

Este proyecto está bajo la Licencia GNU General Public License v3.0 — consulta el archivo [LICENSE.txt](LICENSE.txt) para más detalles.
