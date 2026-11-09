# Instrucciones y Contexto del Proyecto: Tesis Mecatrónica UTEC 2026

Este archivo (`AGENTS.md`) define el contexto maestro y las directrices obligatorias para cualquier agente, subagente o sesión de chat activa dentro de este espacio de trabajo.

---

## 📌 Resumen Ejecutivo del Proyecto

- **Título Oficial:** *DESARROLLO DE UN SISTEMA ROBÓTICO COOPERATIVO INSPIRADO EN INSECTOS PARA EL MONITOREO DE TERRENOS ACCIDENTADOS*
- **Grado Académico:** Proyecto Final de Carrera (Tesis de Ingeniería Mecatrónica)
- **Institución:** Universidad de Ingeniería y Tecnología (UTEC), Lima - Perú, 2026.
- **Autores:** Aleskyjubinsl Alcarraz Jaime, Flavio Alarcon Muñoz, Alfredo Francisco Erazo Yalopalin.
- **Asesor:** Dante Inga Narváez.
- **Documento Detallado de Especificaciones:** Consulta siempre [`CONTEXTO_TESIS.md`](./CONTEXTO_TESIS.md) para detalles numéricos, funciones de transferencia, matrices VDI 2225 y cronograma.

---

## 🤖 Arquitectura del Sistema Cooperativo (A2)

El sistema opera bajo el concepto de **inspección sin ingreso (no-entry)** en minería subterránea y zonas colapsadas (mitigando riesgos de gases letales $CO$, $CO_2$, $NO_x$, $H_2S$, y deficiencia de $O_2$ bajo la normativa **D.S. N° 024-2016-EM** y directivas internacionales):

1. **Hexápodo Primario (Unidad Central de Mapeo y Supervisión):**
   - **Mecánica:** Arquitectura bioinspirada de código abierto (*Chipo / MakeYourPet*), 18 servomotores metálicos **MG996R** ($\approx 10\text{ kg}\cdot\text{cm}$ a 6V), tornillería M3, sensor de contacto en pata con pulsador y goma elastomérica.
   - **Cómputo y Control:** **Raspberry Pi 5 (8 GB RAM)** + controlador de servos dedicado **Pololu Mini Maestro de 18 canales** (conectado por USB).
   - **Percepción:** Cámara RGB-D **Orbbec Gemini 2** (USB 3.0, rango 0.15 a 10.0 m, FOV $91^\circ \times 66^\circ$, IMU 6 DoF integrada), IMU secundaria BMI160, ToF VL53L5CX.
   - **Sensado Ambiental:** Sensor de gases **MQ-9** (CO y combustibles) vía convertidor ADC hacia la Raspberry Pi.
   - **Potencia:** Batería Li-ion / LiPo 3S 4500 mAh (25C), regulador Buck 5.1V 5A (lógica/cámara) y Buck 6.0V 10A cont / 15A pico (servos). Potencia nominal: 34.85 W, pico: 85.55 W.
   - **Software (ROS 2):** Árbol TF (`map` $\to$ `odom` $\to$ `base_link` $\to$ `camera_link`), odometría visual-inercial fusionada con EKF (`robot_localization`), RTAB-Map SLAM 2D/3D con cierre de lazo, planificador `Nav2` y generador de marcha en trípode.

2. **Hexápodo Secundario (Unidad Exploradora Ligera de Mínima Envolvente):**
   - **Mecánica:** Chasis hexagonal en PLA (8% grid infill, 3 perímetros), extremidades 3 DoF con proporción biomimética 1x:2x:3x (Coxa 30 mm, Fémur 60 mm, Tibia 90 mm; relación Fémur-Tibia 4:6).
   - **Actuadores:** 18 micromotores **DC N20 con reductora metálica 1:300 (12V, 300 RPM)** y encoders de cuadratura magnéticos integrados. Doble soporte en eje N20 con acople cúbico en PLA.
   - **Electrónica Modular Distribuida:** 6 placas PCB idénticas e intercambiables (una por pata).
     - Cada placa integra: **ESP32-WROOM-32E (16 MB)**, 3x puentes H **DRV8876** (límite por HW 1.1A, sensado analógico IPROPI al ADC, nFAULT a IO4), puente USB-UART CP2102N con auto-programación, LDO AMS1117-3.3 y conectores JST-SH de 6 pines.
   - **Control Articular en Cascada (3 Lazos Anidados):**
     1. Lazo de corriente (1 kHz PWM, ADC DMA continuo a 200 kS/s en bloques de 1 ms).
     2. Lazo de velocidad a 100 Hz (ventana de 50 ms).
     3. Lazo de posición a 50 Hz (20 ms) con conteo de pulsos por hardware (**PCNT** del ESP32).
   - **Plantas y Controladores Identificados:**
     - Corriente: $G_{22}(s) = \frac{0.001184s^2 + 1.441s + 2.325}{s^2 + 904.4s + 3996}$ $\implies$ $PI_{current}(s) = \frac{8.832s + 80090}{s}$
     - Velocidad: $G_{10}(s) = \frac{998.5}{s + 1.545}$ $\implies$ $PI_{vel}(s) = \frac{0.0284s + 0.01392}{s}$
     - Posición: $G_{10}(s)$ $\implies$ $PI_{pos}(s) = \frac{6.166s + 3192}{s}$

---

## 📅 Estado de Avance y Cronograma (Semana 13 de 16)

- **Completado (S1-S11):** 
  - EDT 1 (Revisión y Requisitos ISO 29148 / D.S. 024-2016-EM).
  - EDT 2 (Diseño CAD/ECAD, simulación Gazebo).
  - EDT 3 (Fabricación preliminar 3D/PCB, identificación de plantas y sintonización de control en cascada).
  - EDT 4 (Locomoción, ensamble integral y control de actuadores).
- **En curso (S11-S14 - EDT 5):** Cierre de sensado ambiental (MiCS-5524), streaming visual UVC MJPEG, telemetría Wi-Fi/UDP con Raspberry Pi 5 y SLAM cooperativo en ROS 2.
- **Próximo (S14-S16 - EDT 6):** Ensayos integrales de campo, consolidación de la memoria final en Overleaf y sustentación formal en S16.

---

## 📁 Estructura del Proyecto en Disco

```text
RedaccionTesis/
├── AGENTS.md                  ← Reglas maestras, pines validados y bitácora técnica
├── CONTEXTO_TESIS.md          ← Requisitos ISO 29148, matrices VDI 2225 y plantas identificadas G(s)
│
├── docs/                      ← Documentación de gestión y defensa
│   ├── PROGRESO.md            ← Semana actual (S9), hitos completados y siguientes pasos
│   ├── DECISIONES.md          ← Matriz de justificación de decisiones para el jurado (ADR)
│   └── CorreccionInformeParcial/ ← Observaciones y correcciones del informe parcial
│
├── firmware/                  ← Firmware para microcontroladores (Robot Secundario)
│   ├── CHANGELOG.md           ← Trazabilidad: Versión ESP32 ↔ pruebas ↔ bugs resueltos
│   ├── esp32_patas_modular/   ← Código C++/Arduino de las 6 patas (N20 + Encoders + DRV8876)
│   └── esp32s3_camara_gas/    ← Código C ESP-IDF (Cámara UVC + Gas MiCS-5524 + Wi-Fi)
│
├── pruebas/                   ← Validación experimental y herramientas de diagnóstico
│   ├── motores_encoders/      ← Scripts Python, pruebas de inversión y visor WebSerial
│   ├── sensor_gas/            ← Calibración R0/Rs, ensayos de analitos y visores
│   ├── camara_usb/            ← Visores OpenCV serial y Wi-Fi
│   ├── integradas_camara_gas/ ← Firmware ESP-IDF, telemetría y visores integrados con luz
│   └── datos_mision/          ← CSVs de telemetría (registro_mision_hexapodo.csv)
│
├── ros2_ws/                   ← [Git de Alesky] Robot Primario (ROS 2 Jazzy, Gazebo, Pololu, Gemini 2)
│
└── tesis_overleaf/            ← [Git de Overleaf] Documento LaTeX oficial sincronizado
```

---

## 🛠️ Directrices de Redacción y Asistencia Técnica

Cuando el usuario solicite redactar, corregir, ampliar o estructurar secciones de la tesis:
1. **Mantener rigor académico e ingenieril:** Citar y basar los argumentos en las metodologías **VDI 2206**, **ISO/IEC/IEEE 29148** y **VDI 2225 Blatt 3**, y en el marco legal peruano (**D.S. 024-2016-EM**).
2. **Consistencia técnica:** No contradecir los componentes seleccionados (ej. Raspberry Pi 5 con Pololu Mini Maestro para el primario; 6x ESP32 con DRV8876 y motores N20 para el secundario).
3. **Tono y formato:** Estilo formal técnico en español, alineado con el estándar de tesis de la carrera de Ingeniería Mecatrónica de UTEC.

---

## ⚡ Bitácora de Pruebas Físicas en Prototipo Secundario (ESP32 DevKit V1 + DRV8876 + N20)

Esta sección documenta la validación experimental de bajo nivel realizada en protoboard antes de la integración total:

### 1. Mapa de Pines Validado y Corregido (Pata Individual - 3 Motores N20)
| Señal | Motor 1 (Coxa) | Motor 2 (Fémur) | Motor 3 (Tibia) | Notas / Configuración |
| :--- | :---: | :---: | :---: | :--- |
| **IN1 (PWM)** | **GPIO 21 (D21)** | **GPIO 18 (D18)** | **GPIO 16 (D16)** | Salida PWM LEDC |
| **IN2 (PWM)** | **GPIO 5 (D5)** | **GPIO 17 (D17)** | **GPIO 4 (D4)** | *M1 migrado de D19 a D5 por buffer dañado* |
| **CS (Corriente ADC)** | **GPIO 36 (VP)** | **GPIO 39 (VN)** | **GPIO 34 (D34)** | Solo Entrada / Canales ADC1 (compatibles con Wi-Fi) |
| **Encoder C1 (Canal A)**| **GPIO 32 (D32)** | **GPIO 25 (D25)** | **GPIO 27 (D27)** | Entrada digital con interrupción por flanco |
| **Encoder C2 (Canal B)**| **GPIO 33 (D33)** | **GPIO 13 (D13)** | **GPIO 14 (D14)** | *M2 migrado de D26 a D13 por diafonía capacitiva* |
| **Gestión Hardware** | `SLEEP` puenteado a 3.3V | `PMODE` puenteado a 3.3V | `FLT` sin conectar (pruebas) | Modo PWM/PWM activo |

### 2. Lecciones Aprendidas y Solución de Errores Críticos
1. **Diferencias Placa Verde vs Placa Roja (`DRV887*` MJKDZ):**
   - La placa roja carece del MOSFET P de protección contra polaridad inversa (si se invierte VM/GND se destruye al instante).
   - **¡OUT1 y OUT2 están invertidos físicamente en la serigrafía roja!** En la roja, OUT1 es el pin 4 y OUT2 es el pin 3 (en la verde están al revés).
2. **Falla de inversión de giro en Motor 1:**
   - Causa: El pin `D19` del ESP32 no modulaba el nivel lógico alto.
   - Solución: Se reasignó `IN2` a **GPIO 5 (D5)**, logrando inversión de giro limpia y simétrica.
3. **Falla de cuadratura en Motor 2 (Encoder solo aumentaba o solo disminuía):**
   - Causa: Diafonía capacitiva (*crosstalk*) por jumpers paralelos contiguos en D25 y D26. La señal de C1 se acoplaba a C2, eliminando el desfase de 90° eléctrico.
   - Solución: Se separó físicamente C2 llevándolo a **GPIO 13 (D13)** con pull-up interno. La lectura bidireccional se restableció al 100%.
4. **Herramientas de automatización instaladas en el entorno:**
   - `arduino-cli.exe` (v1.5.2) instalado en la raíz del proyecto. Permite compilar y subir firmware por `COM11` o `COM12` sin usar la GUI de Arduino.
   - `pyserial` configurado en Python para tests automáticos y telemetría por línea de comandos.
   - Interfaz web interactiva `visor_encoders.html` mediante WebSerial API para diagnóstico manual.

---

## 🧪 Bitácora de Pruebas Físicas del Sensor de Gases (MiCS-5524 + ESP32-S3)

Esta sección documenta la validación experimental y de filtrado digital del subsistema de sensado de gases:

### 1. Configuración de Hardware y Mapa de Pines Validado
- **Tarjeta Controladora:** ESP32-S3-DevKitC-1 (Módulo Sparkle IoT XH-S3E, versión **N16R8**: 16 MB Flash, 8 MB Octal PSRAM).
- **Sensor:** Módulo semiconductor MEMS de gases **MiCS-5524** (SGX Sensortech / breakout Adafruit/CJMCU).
- **Alimentación Auxiliar:** 5.0V suministrados externamente desde un ESP32 DevKit V1 para alimentar el micro-calefactor MEMS ($32\text{ mA}$).

| Pin del Sensor MiCS-5524 | Conexión en el ESP32-S3 / Sistema | Justificación Técnica / Configuración |
| :--- | :--- | :--- |
| **VCC** | **Pin 5V** (Fuente externa / DevKit V1) | Alimentación de 5.0V requerida por el micro-calefactor de silicio. |
| **GND** | **GND común** (DevKit V1 + ESP32-S3) | **CRÍTICO:** Puente obligatorio entre ambas tierras para cerrar la referencia del ADC. |
| **OUT / A0** | **GPIO 4 (ADC1_CH3)** | Entrada analógica con atenuación de 11 dB ($0 - 3.14\text{ V}$). Compatible con Wi-Fi. |
| **EN (Enable)** | **DESCONECTADO (al aire)** o **GPIO 5** | Pin **Active-LOW** (nivel bajo enciende el calefactor; pull-down interno por defecto). |

### 2. Lecciones Aprendidas y Errores Críticos Resueltos
1. **Lógica Invertida del Pin `EN` (Active-LOW):**
   - El circuito del módulo breakout apaga el sensor cuando `EN = HIGH` y lo enciende cuando `EN = LOW` o se deja al aire.
   - Al dejarlo desconectado, la resistencia pull-down de la placa enciende el calefactor automáticamente, alcanzando la temperatura de catálisis ($\sim 300^\circ\text{C}$) y entibiando la cápsula metálica.
2. **Falla de Tierra Común (GND Flotante):**
   - Síntoma: La lectura arrancaba saturada en el techo del ADC ($3.142\text{ V}$) con caídas violentas y ruidosas a $2.5\text{V}$ en milisegundos, sin gas presente.
   - Causa: Al alimentar el sensor desde otra placa sin puentear los pines GND, el pin GPIO 4 quedaba eléctricamente flotante actuando como antena de ruido.
   - Solución: Se colocó un puente directo entre el GND de la fuente de 5V y el GND del ESP32-S3, estabilizando de inmediato la línea base en aire limpio a $\approx 0.5\text{V} - 0.6\text{V}$.
3. **Validación Experimental de Filtros Digitales y Telemetría Inalámbrica Wi-Fi:**
   - **Enlace Wi-Fi SoftAP Autónomo (Arquitectura idéntica a Raspberry Pi 5):**
     - El ESP32-S3 genera la red `ESP32-GasSensor` (IP `192.168.4.1`) sirviendo endpoints HTTP JSON (`/data` a 10-12 Hz y `/calibrate`).
     - Esta arquitectura inalámbrica desacoplada valida experimentalmente la telemetría que recibirá la **Raspberry Pi 5** en el hexápodo primario sin dependencia de cables.
   - **Señal Cruda (*Raw*):** Presenta alta variabilidad y valles de ruido transitorio por conmutación y corrientes de convección térmica.
   - **Filtro de Mediana ($N=5$):** Elimina al 100% los picos espurios y preserva el 97% de la amplitud de pico ($2.72\text{V}$ vs $2.80\text{V}$) con un retardo temporal casi nulo ($\approx 200\text{ ms}$, equivalente a $< 2\text{ cm}$ de desfase espacial a velocidad de marcha de $8\text{ cm/s}$). **Seleccionado para navegación continua.**
   - **Filtro Exponencial EMA ($\alpha=0.20$):** Suprime el ruido de alta frecuencia pero aplana picos transitorios rápidos ($2.20\text{V}$) y genera un retardo de $\sim 1\text{ s}$. **Seleccionado para el régimen *Stop-and-Measure*.**
4. **Mapeo Intuitivo y Fundamentación Teórica para la Tesis:**
   - **Proporción de Gas Ascendente ($\mathbf{R_0 / R_s}$):** Físicamente, el semiconductor $\text{SnO}_2$ reduce su resistencia $R_s$ ante gases reductores. Para ergonomía visual del operador, se calibró la escala ascendente $\frac{R_0}{R_s}$ (1.000 en aire limpio $\to$ sube a $>1.5 - 10.0$ con gas) y porcentaje de intensidad $I_{gas} = (1 - R_s/R_0) \times 100\%$.
   - **Modelo Físico-Matemático (Cadena de Transducción):**
     1. Quimisorción y Ley de Potencias de Wolkenstein-Clifford: $\frac{R_s}{R_0} = A \cdot C^{-B}$.
     2. Divisor de tensión: $V_{out} = V_{CC} \cdot \frac{R_L}{R_s + R_L} \implies R_s = R_L \left(\frac{V_{CC} - V_{out}}{V_{out}}\right)$.
     3. Concentración: $C(\text{ppm}) = \left[ \frac{R_L}{A \cdot R_0} \left( \frac{V_{CC} - V_{out}}{V_{out}} \right) \right]^{-\frac{1}{B}}$.
   - **Sustento Académico de Calibración $R_0$ en Aire Limpio:**
     - *SGX Sensortech (DS-0098 / AAN-004):* Dispersión de fabricación de $100\text{ k}\Omega$ a $1500\text{ k}\Omega$, requiriendo calibración *in-situ*.
     - *Bârsan & Weimar (2001, J. Electroceramics):* El único invariante granulométrico en $\text{SnO}_2$ es el ratio relativo $R_s/R_0$.
     - *Burgués & Marco (2018, Sensors & Actuators B):* Demuestra que en robótica móvil la calibración de $R_0$ al inicio de misión en zona limpia (*zero-gas reference*) elimina el error sistemático por temperatura y tolerancias.
   - **Ensayos con Analitos Reales:** Detección comprobada ante vapores de Etanol y Monóxido de Carbono ($\text{CO}$) por combustión incompleta (ascua/brasa de fósforo en micro-cámara).
5. **Límites de Saturación del Sistema:**
   - *Saturación Química (Datasheet DS-0098):* Rango de etanol de $10\text{ a }500\text{ ppm}$ y $\text{CO}$ de $1\text{ a }1000\text{ ppm}$.
   - *Saturación Eléctrica del ADC:* Con $V_{CC}=5\text{V}$ y $R_L=820\,\Omega$, cuando $R_s \le 485\,\Omega$, el voltaje supera los $3.14\text{ V}$ saturando el ADC.
6. **Estructura de Archivos del Módulo:**
   - Código firmware: `pruebas/sensor_gas/firmware_mics5524/firmware_mics5524.ino`
   - Interfaz web: `pruebas/sensor_gas/visor_gas_mics5524.html`
   - Visor OpenCV en Python (Serial y Wi-Fi): [`visor_gas_python.py`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/sensor_gas/visor_gas_python.py)
   - Lanzador Serial (.bat): [`iniciar_visor_gas_serial.bat`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/sensor_gas/iniciar_visor_gas_serial.bat)
   - Lanzador Wi-Fi (.bat): [`iniciar_visor_gas_wifi.bat`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/sensor_gas/iniciar_visor_gas_wifi.bat)
   - Registro en Notion: Documentado en `Universidad / 2026-2 / Tesis 2 / Avances / Sensor de gases`.

---

## 📷 Bitácora de Pruebas Físicas del Subsistema de Visión UVC (ESP32-S3 + Cámara Mini USB Type-C)

Esta sección documenta la validación experimental del streaming de video desde la cámara mini UVC Type-C hacia el ESP32-S3 (Host USB nativo) y su transmisión hacia la laptop/Raspberry Pi 5:

### 1. Hardware y Requerimientos Eléctricos
- **Controlador:** ESP32-S3-DevKitC-1 (Módulo Sparkle IoT N16R8: 16 MB Flash, 8 MB Octal PSRAM).
- **Cámara:** Módulo Mini USB Type-C UVC 720p (sensor CMOS 1 MP, DSP con compresión hardware MJPEG integrada).
- **Alimentación y Condición de Host USB (VBUS):**
  - El puerto USB nativo del ESP32-S3 cuenta con un diodo Schottky que bloquea la salida de 5V hacia afuera cuando se alimenta por el puerto COM.
  - La cámara requiere alimentación forzosa de 5V en su pin VBUS para encender su sensor y microprocesador DSP. Se resolvió alimentando el pin `5Vin` y puenteando/inyectando 5V a la línea VBUS del conector USB.
- **Temperatura Operativa:** El procesador DSP y los reguladores LDO internos de la cámara concentran $\sim 0.75\text{ W}$ en $2.5\text{ cm}^2$, alcanzando temperaturas de $50^\circ\text{C}-60^\circ\text{C}$ en régimen continuo (normal para silicio de compresión MJPEG sin disipador).

### 2. Prueba 1: Transmisión Serial por Cable (Puerto COM / UART0)
- **Firmware:** `pruebas/camara_usb/ESP32_S3_with_CAMERA/ESP32_S3_with_CAMERA/main/main_v2.c` (V2 Desacoplada).
- **Tasa de Baudios:** $1,500,000\text{ baudios}$ ($\approx 150\text{ KB/s}$ teóricos).
- **Protocolo de Trama:** Encabezado binario de 16 bytes:
  $$\text{Header (4B: } \mathtt{0xFF\,0xAA\,0x55\,0xFF}) + \text{Len (4B, } \mathtt{<I}) + \text{Width (2B, } \mathtt{<H}) + \text{Height (2B, } \mathtt{<H}) + \text{Seq (4B, } \mathtt{<I}) + \text{JPEG} + \text{Footer (2B: } \mathtt{0x00\,0xFF})$$
- **Rendimiento Obtenido:** **$8.7\text{ FPS}$ estables a $480 \times 320$ MJPEG** ($\approx 14.9\text{ KB/frame}$, flujo de $\approx 130\text{ KB/s}$).
- **Lecciones y Errores Resueltos:**
  1. *Bloqueo de tareas USB:* En V1, `uart_write_bytes` dentro de `frame_callback` congelaba el bus USB, provocando desbordamiento de URBs y congelamiento de pantalla. En V2 se desacopló la arquitectura: `frame_callback` copia en microsegundos a un doble buffer en Octal PSRAM (`MALLOC_CAP_SPIRAM`) con mecanismo de descarte (*drop-frame*) no bloqueante, y una tarea independiente despacha por la UART.
  2. *Corrección del desempaquetador Python:* Se corrigió el formato de `struct.unpack` de `'<IIHI'` (14 bytes) a `'<IHHI'` (12 bytes de metadatos), resolviendo el crash inicial de OpenCV.
- **Archivos:** Visor OpenCV [`visor_camara_serial.py`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/camara_usb/visor_camara_serial.py) y lanzador [`iniciar_visor_opencv.bat`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/camara_usb/iniciar_visor_opencv.bat).

### 3. Prueba 2: Transmisión Inalámbrica Wi-Fi (Modo SoftAP 2.4 GHz)
- **Firmware:** `pruebas/camara_usb/ESP32_S3_with_CAMERA/ESP32_S3_with_CAMERA/main/main_v3_wifi.c` (V3 Wi-Fi).
- **Configuración de Red:** SoftAP $802.11\text{ b/g/n}$ en $2.4\text{ GHz}$, canal 6, IP estática `192.168.4.1`, SSID: `ESP32S3-CAM`, clave: `camara123`.
- **Servidor Web y Streaming:** Servidor HTTP en puerto 80 con endpoint MJPEG multipart `/stream` (`multipart/x-mixed-replace;boundary=frame`) y telemetría JSON `/status`.
- **Rendimiento Obtenido:**
  - Mayor resolución y fluidez notable frente al enlace serie (ancho de banda disponible $> 1.5\text{ MB/s}$ frente a los $\approx 0.25\text{ MB/s}$ requeridos por el video).
  - Latencia promedio de $\approx 1.0\text{ s}$ debida al buffer de paquetes TCP/HTTP en el receptor, perfectamente admisible para monitoreo y telemetría de inspección.
- **Archivos:** Visor OpenCV [`visor_camara_wifi.py`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/camara_usb/visor_camara_wifi.py) y lanzador [`iniciar_visor_wifi.bat`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/camara_usb/iniciar_visor_wifi.bat).

---

## 🔬 Bitácora de Pruebas Físicas Integradas: Cámara UVC + Sensor de Gases MiCS-5524 (ESP32-S3 Wi-Fi)

Esta sección documenta la operación concurrente en tiempo real del subsistema visual y ambiental sobre un único chip ESP32-S3:

### 1. Arquitectura de Firmware Multihilo y Separación por Núcleos (FreeRTOS)
- **Núcleo 0 (Core 0 - Control Ambiental y Red):**
  - Muestreo analógico ADC1 canal 3 (GPIO 4) a 20 Hz con calibración por eFuse.
  - Filtro de mediana ($N=5$) y filtro exponencial EMA ($\alpha=0.20$).
  - Pila TCP/IP LwIP y servidor HTTP multipart (`/stream`, `/data`, `/gas`, `/calibrate`).
- **Núcleo 1 (Core 1 - Visión y Host USB UVC):**
  - Driver UVC Host nativo conectado por USB D+/D-.
  - Desempaquetado MJPEG no bloqueante en Octal PSRAM (`s_latest_jpeg`, hasta 65 KB).
- **Consumo Energético Total:** $\approx 500-600\text{ mA}$ a 5V (Cámara $\sim 150\text{ mA}$, Calefactor MEMS $\sim 32\text{ mA}$, ESP32 Wi-Fi TX bursts $\sim 300\text{ mA}$).

### 2. Estructura de Archivos del Módulo Integrado
- **Carpeta dedicada:** `pruebas/integradas_camara_gas/`
  - Firmware C (ESP-IDF v5.4.4): [`main_v4_camara_gas.c`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/integradas_camara_gas/firmware_camara_gas/main_v4_camara_gas.c)
  - Visor en Python (OpenCV): [`visor_integrado_python.py`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/integradas_camara_gas/visor_integrado_python.py)
  - Lanzador de un clic: [`iniciar_visor_integrado.bat`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/integradas_camara_gas/iniciar_visor_integrado.bat)

### 3. Lecciones Aprendidas y Solución de Errores Críticos
1. **Falla de sintaxis en archivo `.bat` (Cierre inmediato en < 1 s):**
   - *Causa:* Uso de paréntesis anidados o texto con puntos `(ESP32-S3: 192.168.4.1)` dentro de un bloque `if (...) else (...)` en `cmd.exe`.
   - *Solución:* Simplificación estructural del script `.bat` sin anidamientos de paréntesis, usando ejecución secuencial directa `cd /d "%~dp0"` y `pause` al final para preservar la consola.
2. **Robustez ante Cámara Desconectada y Conexión en Caliente (*Hot-Plug*):**
   - *Causa:* Si la cámara no estaba conectada al arrancar, el endpoint `/stream` entraba en espera pasiva sin despachar bytes, provocando un *timeout* en el cliente Python (3.5 s) y bloqueando permanentemente el semáforo `s_stream_client` (`503 Service Unavailable`).
   - *Solución:* Implementación de un **cuadro de espera (*Standby Frame*) JPEG estándar de 16x16 px (631 bytes) a 2 Hz**. Esto responde `HTTP 200 OK` de inmediato, mantiene activo el canal, libera memoria si el cliente se desconecta, y permite la conmutación instantánea al video real en cuanto se enchufa la cámara al puerto USB nativo, sin que el sensor de gas ni el servidor se interrumpan en ningún momento.

---

## 📡 Bitácora de Integración y Pruebas para Raspberry Pi 5 (Hexápodo Primario - Ubuntu 22.04 LTS)

Esta sección documenta la estandarización del firmware maestro del ESP32-S3 y la arquitectura de software desplegada para la Raspberry Pi 5 en modo autónomo (*Headless*):

### 1. Validación de Transporte de Datos (TCP vs UDP/RTP)
- **Evaluación Experimental de UDP Puro para Video:** Al fragmentar fotogramas JPEG de $\sim 15\text{ KB}$ en paquetes UDP y emitirlos sin espaciamiento a la velocidad del procesador ($240\text{ MHz}$), se saturaba la cola DMA de transmisión del chip Wi-Fi del ESP32 (límite de 8-12 buffers TX). Como en UDP la pérdida de un solo paquete corrompe el cuadro JPEG entero, el visor receptor descartaba las tramas dañadas, resultando en saltos y tasa de cuadros irregular.
- **Estandarización de Versiones Maestras del Proyecto:**
  - **Versión Maestra 1 (V1 Base - `main_v4_camara_gas.c` / `V1_firmware_esp32_camara_gas.c`):**
    - Video UVC MJPEG dedicado por **TCP en puerto 81** (`/stream`).
    - Telemetría de gas continua por **UDP en puerto 5005** a 20 Hz.
    - Servidor HTTP auxiliar en **puerto 80** (`/data` y `/calibrate`). Luz LED desactivada.
  - **Segunda Versión Maestra (V2 Completa con Iluminación LED - `main_v8_camara_gas_luz.c` / `V2_firmware_esp32_camara_gas_luz.c`):**
    - **Control Integral de Luz:** Incorpora el encendido y apagado de la luz de inspección en **GPIO 48** (LED direccionable WS2812/SK6812) mediante el **periférico por hardware RMT** a $10\text{ MHz}$.
    - **Canales de Control:** Endpoint HTTP `/light` en puerto 80 (`?state=1`, `?state=0`, `?state=toggle`), botón interactivo en interfaz Web `/`, atajo de teclado **`[L]`** en visualizador OpenCV y tópico ROS 2 `/hexapodo/cmd_luz` en el nodo de Raspberry Pi 5.
    - **Arranque Seguro:** La luz inicia apagada por defecto ($0\text{ lux}$) y conmuta a blanco puro al 100% para inspección en túneles mineros.

### 2. Estructura del Módulo Estandarizado (`pruebas_para_raspberry/`)
Ubicación: `pruebas/integradas_camara_gas/pruebas_para_raspberry/`

| Archivo | Versión Maestra | Plataforma | Descripción y Rol Funcional |
| :--- | :---: | :--- | :--- |
| **`V1_firmware_esp32_camara_gas.c`** | **V1** | ESP32-S3 | Firmware maestro base C (ESP-IDF v5.4.4). TCP p81 + UDP p5005 + Hot-Plug standby frame. |
| **`V1_nodo_raspberry_headless.py`** | **V1** | Raspberry Pi 5 | Nodo Central Sin Monitor V1: Recibe TCP/UDP, evalúa D.S. 024-2016-EM, caja negra CSV a 5 Hz y puente ROS 2. |
| **`V1_visor_laptop_con_pantalla.py`** | **V1** | Laptop / Base | Visor OpenCV V1 con osciloscopio en vivo, telemetría y HUD táctico. |
| **`iniciar_visor_laptop.bat`** | **V1** | Laptop (Win) | Lanzador de un clic para el visor V1. |
| **`V2_firmware_esp32_camara_gas_luz.c`** | **V2** | ESP32-S3 | **Segunda Versión Maestra:** Firmware completo con driver RMT para luz LED (GPIO 48), TCP p81 + UDP p5005 + HTTP `/light`. |
| **`V2_visor_laptop_con_luz.py`** | **V2** | Laptop / Base | **Segunda Versión Maestra:** Visor OpenCV con atajo interactivo `[L]`, badge en pantalla `[LUZ: ON/OFF]` y osciloscopio. |
| **`V2_nodo_raspberry_headless_con_luz.py`** | **V2** | Raspberry Pi 5 | **Segunda Versión Maestra:** Supervisor headless con control HTTP de luz y suscriptor ROS 2 `/hexapodo/cmd_luz`. |
| **`iniciar_visor_con_luz.bat`** | **V2** | Laptop (Win) | Lanzador de un clic para la Segunda Versión Maestra con control de iluminación. |
| **`ejecutar_en_raspberry.sh`** | V1 / V2 | Raspberry Pi 5 | Script bash de arranque rápido para Linux Ubuntu 22.04 LTS. |

### 3. Operación Autónoma de la Raspberry Pi 5 (Sin Monitor)
- **Auto-conexión de Red:** En Ubuntu 22.04 LTS, NetworkManager auto-enlaza la red del ESP32 al encender el robot:
  ```bash
  nmcli dev wifi connect "ESP32S3-CAM" password "camara123"
  ```
- **Supervisor y Caja Negra en `V1_nodo_raspberry_headless.py` / `V2_nodo_raspberry_headless_con_luz.py`:**
  - Consume el stream TCP con filtro de tamaño de cuadro (detecta `is_standby` si es cuadro de 16x16 px).
  - Escucha datagramas UDP de gas en `0.0.0.0:5005`.
  - Registra a 5 Hz en disco el archivo `registro_mision_hexapodo.csv` (ISO timestamp, voltajes, Rs, R0, Ratio, % de gas y estado de seguridad minera).
  - Si el entorno tiene activo **ROS 2 Humble (`rclpy`)**, publica de forma automática en los tópicos:
    - `/secondary_robot/camera/compressed` (`sensor_msgs/msg/CompressedImage`)
    - `/secondary_robot/gas_telemetry` (`std_msgs/msg/Float32MultiArray`)
    - `/secondary_robot/safety_alert` (`std_msgs/msg/String`)
    - Control de luz mediante suscripción a `/hexapodo/cmd_luz` (`std_msgs/msg/Bool`).
  - En consola SSH, refresca cada segundo una tabla limpia ANSI con métricas de FPS, tasa de datos KB/s, impedancia del gas y nivel de riesgo.

---

## 💡 Bitácora del Subsistema de Iluminación de Inspección (LED RGB WS2812 en GPIO 48)

Esta sección documenta la integración del control de iluminación para ambientes oscuros y túneles mineros sobre el hexápodo secundario:

### 1. Hardware y Driver por Periférico Dedicado RMT (Remote Control Transceiver)
- **Actuador:** LED RGB inteligente direccionable WS2812/SK6812 integrado en la placa Sparkle IoT N16R8 en **GPIO 48**.
- **Driver de Hardware:** Implementación mediante el periférico nativo de hardware **RMT** (`driver/rmt_tx.h` y `driver/rmt_encoder.h`) a $10\text{ MHz}$ ($100\text{ ns}$ de resolución por tick de hardware).
  - Emite símbolos RMT con temporización de reloj de cuarzo: Bit 0 ($300\text{ ns}$ HIGH, $900\text{ ns}$ LOW), Bit 1 ($900\text{ ns}$ HIGH, $300\text{ ns}$ LOW), Reset Latch ($500\,\mu\text{s}$ LOW).
  - Trama de 32 bits (formato compatible GRBW) para garantizar extinción total tanto en WS2812 de 24 bits como en SK6812 de 32 bits, eliminando cualquier encendido espurio en verde por fallos de caché o jitter de CPU.
- **Comportamiento por Defecto:** Al iniciar el sistema (`app_main`), la luz se fuerza a estado **APAGADA (`R=0, G=0, B=0, W=0`)** mediante RMT.
- **Modo Iluminación:** Encendido en **blanco puro al 100% (`R=255, G=255, B=255, W=255`)** para maximizar la visibilidad del sensor UVC en ductos o galerías subterráneas.

### 2. Canales de Control Disponibles
1. **Endpoint HTTP (Puerto 80):**
   - `GET /light?state=1` (o `state=on`) $\to$ Enciende la luz.
   - `GET /light?state=0` (o `state=off`) $\to$ Apaga la luz.
   - `GET /light?state=toggle` (o `/light` sin parámetros) $\to$ Alterna entre encendido y apagado.
   - Respuesta JSON: `{"light": true/false, "status": "ok"}`.
2. **Dashboard Web Integrado (Navegador):**
   - Accediendo a `http://192.168.4.1/` se dispone de un botón interactivo para alternar la luz en tiempo real con indicador dinámico de estado.
3. **Visor de Laptop (`V2_visor_laptop_con_luz.py`):**
   - Presionando la tecla **`L`** se conmuta la luz al instante de forma asíncrona (hilo no bloqueante).
   - HUD visualiza badge táctico: `[LUZ: ENCENDIDA]` (amarillo) / `[LUZ: APAGADA]` (gris).
4. **Nodo Raspberry Pi 5 (`V2_nodo_raspberry_headless_con_luz.py`):**
   - Integrado con ROS 2 mediante el tópico `/hexapodo/cmd_luz` (`std_msgs/msg/Bool`), permitiendo a algoritmos autónomos de navegación o inspección encender la luz al ingresar a zonas de baja luminosidad.

### 3. Lecciones Aprendidas y Solución de Errores Críticos
1. **Falla de Apertura de Socket UDP antes de Inicializar TCP/IP (`assert Invalid mbox`):**
   - *Causa:* Si en `app_main` se lanza la tarea `gas_sensor_task` antes de `start_wifi_ap()`, la tarea intenta abrir el socket BSD `socket(AF_INET, SOCK_DGRAM, IPPROTO_IP)` antes de que `esp_netif_init()` inicialice el hilo y el mailbox de LwIP (`tcpip_mbox`). Esto provocaba un panic kernel instantáneo (`assert failed: tcpip_send_msg_wait_sem (Invalid mbox)`), reiniciando el ESP32 en bucle cada 900 ms e impidiendo que el Wi-Fi `ESP32S3-CAM` llegara a encenderse.
   - *Solución:* Se reordenó `app_main` para inicializar obligatoriamente primero el SoftAP Wi-Fi y los servidores HTTP (`start_wifi_ap()`), seguido del hardware de gas y el lanzamiento de la tarea con un retardo preventivo de 1 segundo (`vTaskDelay`).
2. **Luz Verde Espuria al Apagar el LED WS2812 (Sobreduración de $T_{0H}$ por `gpio_set_level`):**
   - *Causa:* El protocolo WS2812 transmite en orden GRB (Green, Red, Blue). Un bit '0' exige un pulso en alto $T_{0H} \le 350\text{ ns}$. La función `gpio_set_level()` de ESP-IDF introduce una sobrecarga de validación y salto de $\sim 120-150\text{ ciclos}$ ($\sim 500-600\text{ ns}$ a $240\text{ MHz}$). Por tanto, al intentar enviar ceros para apagar (`R=0, G=0, B=0`), el LED decodificaba los pulsos anchos como '1's. Al ser el primer byte el canal Verde, el LED se fijaba en color verde puro en lugar de apagarse.
   - *Solución:* Se implementó acceso directo a registros de hardware (`GPIO.out1_w1ts.val = (1UL << 16)` y `GPIO.out1_w1tc.val = (1UL << 16)` para GPIO 48). El cambio de estado ocurre en 1 solo ciclo de reloj ($4.167\text{ ns}$), logrando un $T_{0H}$ exacto de $283\text{ ns}$ (68 ciclos) y garantizando que el LED se apague por completo ($0\text{ lux}$).
3. **Robustez ante Sensor de Gas Desconectado:**
   - La desconexión física del sensor MiCS-5524 deja el pin GPIO 4 (ADC) flotante; el firmware lo maneja con clamp seguro entre $0.05\text{ V}$ y $3.10\text{ V}$ sin interrumpir el streaming de video ni el control de la luz.




