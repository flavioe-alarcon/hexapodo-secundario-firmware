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

## 🤖 Arquitectura del Sistema Cooperativo (A2) y Ámbito de Aplicación

El sistema opera bajo el concepto de **inspección sin ingreso (no-entry)** en una gama amplia de **entornos confinados y de difícil acceso**:
1. **Minería subterránea:** Galerías ciegas, chimeneas, tajos y zonas de ventilación restringida.
2. **Zonas de derrumbe y colapso estructural:** Estructuras colapsadas por sismos, fallas geológicas o deslizamientos donde el terreno es inestable para cuadrillas de rescate.
3. **Escenarios post-incendio y siniestros industriales:** Espacios confinados con acumulación de gases tóxicos y combustibles, humo residual y pérdida de soporte estructural.

En estos entornos, el sistema mitiga la exposición humana a atmósferas peligrosas (gases letales $CO$, $CO_2$, $NO_x$, $H_2S$, vapores combustibles y deficiencia de $O_2$) bajo la normativa **D.S. N° 024-2016-EM**, estándares NFPA y directivas internacionales de seguridad y rescate:

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
   - Graficador y Analizador de CSV en Python: [`graficar_csv_gas.py`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/sensor_gas/graficar_csv_gas.py)
   - Lanzador Graficador CSV (.bat): [`graficar_datos_gas.bat`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/graficar_datos_gas.bat)
   - Lanzador Serial (.bat): [`iniciar_visor_gas_serial.bat`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/sensor_gas/iniciar_visor_gas_serial.bat)
   - Lanzador Wi-Fi (.bat): [`iniciar_visor_gas_wifi.bat`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/iniciar_visor_gas_wifi.bat)
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

---

## 📷 Bitácora de Validación Física Exitosa: Módulo Standalone de Visión UVC (ESP32-S3 + Raspberry Pi 5 + ROS 2 Jazzy)

Esta sección documenta la prueba física **100% exitosa** del módulo standalone de cámara UVC realizada en laboratorio el **09/11/2026**:

### 1. Componentes y Código Validado
- **Firmware ESP32-S3:** [`firmware/esp32s3_camara_gas/VALIDADO_EXITOSO_firmware_esp32s3_camara_solo.c`](firmware/esp32s3_camara_gas/VALIDADO_EXITOSO_firmware_esp32s3_camara_solo.c)
- **Receptor Raspberry Pi 5:** [`pruebas/integradas_camara_gas/pruebas_para_raspberry/VALIDADO_EXITOSO_nodo_camara_solo_raspberry.py`](pruebas/integradas_camara_gas/pruebas_para_raspberry/VALIDADO_EXITOSO_nodo_camara_solo_raspberry.py)
- **Lanzador Bash Raspberry:** [`pruebas/integradas_camara_gas/pruebas_para_raspberry/ejecutar_camara_solo_en_raspberry.sh`](pruebas/integradas_camara_gas/pruebas_para_raspberry/ejecutar_camara_solo_en_raspberry.sh)
- **Visor Laptop OpenCV:** [`pruebas/camara_usb/VALIDADO_EXITOSO_visor_camara_solo_laptop.py`](pruebas/camara_usb/VALIDADO_EXITOSO_visor_camara_solo_laptop.py)

### 2. Resultados de la Prueba Física
1. **Enlace de Red y Streaming TCP:**
   - SoftAP Wi-Fi `ESP32S3-CAM` (`192.168.4.1`) en canal 6.
   - Stream MJPEG dedicado por TCP en puerto 81 (`/stream`), logrando tasa fluida y sostenida.
2. **Robustez ante Desconexión o Apagado de Cámara (*Standby Frame*):**
   - Cuando la cámara USB no está conectada o está sin energía, el ESP32 transmite un micro-frame JPEG negro estándar de 16x16 px (631 bytes) a 2 Hz.
   - Esto mantiene la conexión HTTP/TCP activa sin causar desconexiones ni bloquear el semáforo `s_stream_client`.
   - Al conectar la cámara (*Hot-Plug*), el ESP32 la detecta y conmuta automáticamente a la señal de video real a 480x320 px sin reiniciar el microcontrolador.
3. **Publicación y Visualización en ROS 2 Jazzy:**
   - El nodo en Raspberry Pi 5 publica sin latencia en el tópico `/secondary_robot/camera/compressed` (`sensor_msgs/msg/CompressedImage`).
   - Imagen visualizada con éxito en tiempo real en **`rqt_image_view`** y en **RViz 2** configurando `Fixed Frame: camera_link_secondary` y `Transport Hint: compressed`.







---

## 🦾 Bitácora de Análisis Estructural y de Fuerzas del Fémur (Cálculo Analítico y Justificación de Sección Crítica)

Esta sección documenta el modelo analítico estructural completo, los parámetros geométricos, los cálculos de flexión y deflexión, y la justificación de la sección crítica para la extremidad (fémur,  = 60\text{ mm}$) del robot hexápodo secundario.

### 1. Parámetros Geométricos y Propiedades de Sección Crítica (Pieza Ocre)
- **Componente evaluado:** Acople central rígido (pieza ocre) que une el soporte proximal (motor Coxa, blanco) con el soporte distal (motor Tibia, rosado).
- **Dimensiones exteriores:** Ancho  = 18.90\text{ mm}$, Altura  = 9.00\text{ mm}$ (dirección de flexión vertical).
- **Alivios / Taladros pasantes:** 2 orificios cilíndricos de diámetro  = 5.975\text{ mm}$.
- **Ancho neto resistente:** {\text{neto}} = B - 2d = 18.90 - 2(5.975) = 6.95\text{ mm}$.
- **Espesor de nervaduras:** 3 paredes paralelas de {\text{pared}} \approx 2.31\text{ mm}$.
- **Validación de manufactura aditiva (100% sólido real):**
  - Configuración: Boquilla de .40\text{ mm}$, 3 perímetros de pared exteriores e interiores.
  - Espesor macizo de perímetros: {\text{sol}} = 2 \times (3 \times 0.40\text{ mm}) = 2.40\text{ mm} > 2.31\text{ mm}$.
  - Las 3 paredes son **100% macizas** sin depender del relleno (*infill*), validando el modelo de viga elástica continua.
- **Momento de Inercia Neto:**
  I_{x,\text{neto}} = \frac{B_{\text{neto}} \cdot H^3}{12} = \frac{6.95 \cdot (9.00)^3}{12} = 422.21\text{ mm}^4
- **Módulo de Sección Elástico:**
  c = \frac{H}{2} = 4.50\text{ mm} \implies Z = \frac{I_{x,\text{neto}}}{c} = \frac{422.21}{4.50} = \mathbf{93.82\text{ mm}^3}

### 2. Factor de Concentración de Esfuerzos ($) y Orientación de Impresión
- **Discontinuidad geométrica:** Relación /B = 5.975 / 18.90 \approx 0.316$.
- **Sustento teórico:** Peterson's Stress Concentration Factors y Roark's Formulas para placas con orificios transversales bajo flexión $\implies \mathbf{K_t = 2.00}$.
- **Esfuerzo máximo concentrado:** $\sigma_{\text{max}} = K_t \cdot \sigma_{\text{nom}} = 2.00 \cdot (M / Z)$.
- **Orientación de impresión:** Fabricación sobre cara lateral, alineando los filamentos continuos de PLA con el eje longitudinal de tracción por flexión ( \approx 40\text{ MPa}$), eliminando el riesgo de falla por delaminación interlaminar Z.

### 3. Casos de Carga y Factores de Seguridad ($)
- **Caso 1: Reacción al Stall del Motor N20 (300:1):**
  - Torque límite: {\text{stall}} \approx 3.5\text{ kg}\cdot\text{cm} = 350\text{ N}\cdot\text{mm}$.
  - $\sigma_{\text{nom}} = 3.73\text{ MPa}$, $\sigma_{\text{max}} = 7.46\text{ MPa} \implies \mathbf{FoS = 5.36}$ (Ampliamente seguro).
- **Caso 2: Marcha Normal en Postura Agachada ({\text{pie}} = 10\text{ N}$):**
  - Peso del robot: .5\text{ kg}$ (.7\text{ N}$), distribuido en 3 patas ($\sim 5\text{ N}$ estático), factor dinámico .0\times \implies F_{\text{pie}} = 10\text{ N}$.
  - Brazo horizontal efectivo al empotramiento: {\text{arm}} \approx 50\text{ mm} \implies M = 500\text{ N}\cdot\text{mm}$.
  - $\sigma_{\text{nom}} = 5.33\text{ MPa}$, $\sigma_{\text{max}} = 10.66\text{ MPa} \implies \mathbf{FoS = 3.75}$ (Óptimo / Fatiga nula).
- **Caso 3: Impacto Severo / Extensión Máxima ({\text{pie}} = 10\text{ N}$, {\text{arm}} = 100\text{ mm}$):**
  - Momento flector:  = 1000\text{ N}\cdot\text{mm}$.
  - $\sigma_{\text{nom}} = 10.66\text{ MPa}$, $\sigma_{\text{max}} = 21.32\text{ MPa} \implies \mathbf{FoS = 1.88}$ (Seguro, cumple norma  \ge 1.50$).

### 4. Rigidez y Deflexión Elástica ($\delta$)
- Ecuación de flecha máxima en voladizo:
  \delta = \frac{F_{\text{pie}} \cdot L^3}{3 \cdot E \cdot I_{x,\text{neto}}} = \frac{10 \times (60)^3}{3 \times 3500 \times 422.21} = \frac{2\,160\,000}{4\,433\,205} \approx \mathbf{0.49\text{ mm}}
- Flecha $< 0.82\%$ de la longitud del eslabón, garantizando precisión cinemática articular.

### 5. Justificación Metodológica de la Sección Crítica (Pieza Ocre vs. Ensamble)
Ante preguntas del jurado sobre por qué no se modelaron las piezas blanca y rosada:
1. **Método de la Sección Crítica (*Shigley*, Cap. 1 & 3):** La integridad global de un ensamble está gobernada por la sección que minimiza el Factor de Seguridad local ({\text{global}} = \min \{ FoS(x) \}$).
2. **Comparativa dimensional ( = 9.00\text{ mm}$ común):**
   - **Pieza Ocre (Central):** {\text{neto}} = 6.95\text{ mm} \implies Z = 93.82\text{ mm}^3$ (Base).
   - **Pieza Rosada (Distal):** {\text{efectivo}} = 9.90\text{ mm} \implies Z = 133.65\text{ mm}^3$ (**+42.5% más resistente**).
   - **Pieza Blanca (Proximal):** {\text{efectivo}} = 10.40\text{ mm} \implies Z = 140.40\text{ mm}^3$ (**+49.6% más resistente**).
3. **Severidad por Concentración ($\psi = K_t / Z$):**
   - Ocre ( = 2.00$ por 2 taladros pasantes): $\psi = 0.0213\text{ mm}^{-3}$.
   - Rosada y Blanca ( \approx 1.15$, perfiles continuos): $\psi = 0.0086\text{ mm}^{-3}$ y .0082\text{ mm}^{-3}$.
   - **La pieza ocre soporta un esfuerzo pico concentrado $\mathbf{\approx 2.5\times\text{ a }2.6\times}$ mayor** que las demás piezas.
4. **Acotamiento Inferior:** Como la pieza ocre cumple con  = 3.75$ (marcha) y  = 1.88$ (impacto), las piezas blanca y rosada operan con  > 4.5$ y $> 9.0$, haciendo redundante su cálculo detallado.

### 6. Referencias Académicas Formales
1. **Budynas, R. G., & Nisbett, J. K. (2020).** *Shigley's Mechanical Engineering Design* (11th ed.). McGraw-Hill Education. (Cap. 1 y 3: Critical Section Method, stress analysis).
2. **Beer, F. P., Johnston, E. R., DeWolf, J. T., & Mazurek, D. F. (2020).** *Mecánica de Materiales* (8.ª ed.). McGraw-Hill Interamericana. (Cap. 4 y 5: Flexión pura, módulo de sección $).
3. **Pilkey, W. D., Pilkey, D. F., & Bi, Z. (2020).** *Peterson's Stress Concentration Factors* (4th ed.). John Wiley & Sons. (Sección 3.3.3: Placas en flexión con orificios transversales).
4. **Norton, R. L. (2020).** *Diseño de Máquinas: Un enfoque integrado* (5.ª ed.). Pearson Educación. (Cap. 3 y 4: Concentración de esfuerzos y teorías de falla estática).
- **Documentación en Notion:** Registrado en la página Universidad / 2026-2 / Tesis 2 / Avances / Analisis de fuerzas (ID: 41a28ed0-9985-805f-8b7a-f30da3455050).


---

## 🦿 Bitácora de Análisis Estructural y de Pandeo de la Tibia (Cálculo Analítico y Matriz Maestra Fémur vs. Tibia)

Esta sección documenta el modelo analítico estructural completo para el eslabón distal de la extremidad (**tibia**, {	ext{total}} = 114.11\text{ mm}$) del robot hexápodo secundario.

### 1. Geometría y Parámetros Dimensionales Reales
- **Orientación:** Vista Lateral = plano de flexión vertical ( = 10.20\text{ mm}$); Vista Superior = plano de celosía aligerada ({\text{neto}} = 4.00\text{ mm}$).
- **Tramos:**  = 89.00\text{ mm}$ (recto) y  = 29.00\text{ mm}$ (punta inclinada) con ángulo interno de codo $\alpha = 150^\circ$ ($	heta = 30^\circ$).
- **Proyecciones:**  = 114.11\text{ mm}$,  = 14.50\text{ mm}$.
- **Propiedades de Sección:**
  - {\text{vertical}} = \frac{4.00 \cdot (10.20)^3}{12} = 353.74\text{ mm}^4$
  -  = 5.10\text{ mm} \implies Z_v = 69.36\text{ mm}^3$
  - {\text{mín}} = \frac{10.20 \cdot (4.00)^3}{12} = 54.40\text{ mm}^4$ (eje débil lateral)

### 2. Resultados de Esfuerzos, Pandeo y Deflexión
- **Flexión Vertical en Marcha (\text{ N}$, \text{ N}\cdot\text{mm}$):** $\sigma_{\text{nom}} = 7.21\text{ MPa}$, $\sigma_{\text{max}} = 10.82\text{ MPa}$ ( = 1.50$) $\implies \mathbf{FoS = 3.70}$.
- **Extensión / Choque Severo (.1\text{ N}\cdot\text{mm}$):** $\sigma_{\text{max}} = 24.68\text{ MPa} \implies \mathbf{FoS = 1.62}$ ($> 1.50$ normativo).
- **Carga Crítica de Pandeo de Euler ( = 0.8$,  = 91.29\text{ mm}$):**
  P_{\text{cr}} = \frac{\pi^2 \cdot 3500 \cdot 54.40}{(91.29)^2} = 225.48\text{ N} \implies \mathbf{FoS_{\text{pandeo}} = 22.55} (Totalmente inmune al pandeo lateral).
- **Flecha Elástica en Punta:** $\delta = 0.40\text{ mm}$ ($< 0.35\%$ de $).

### 3. Matriz Comparativa Maestra: Fémur vs. Tibia
| Métrica Estructural | Fémur (Pieza Ocre) | Tibia (Pieza Amarilla) | Evaluación del Ensamble |
| :--- | :---: | :---: | :--- |
| **Longitud ($)** | .00\text{ mm}$ | .11\text{ mm}$ | Proporción biomimética 1:2 |
| **Peralte Vertical ($)** | .00\text{ mm}$ | .20\text{ mm}$ | Compensación geométrica por esbeltez |
| **Ancho Neto ({\text{neto}}$)** | .95\text{ mm}$ | .00\text{ mm}$ | Aligeramiento progresivo |
| **Módulo Elástico ($)** | .82\text{ mm}^3$ | .36\text{ mm}^3$ | Diseñados según gradiente flector |
| **$ en Marcha Normal** | **.75$** | **.70$** | **Equilibrio estructural idóneo ( \approx 3.7$)** |
| **$ en Impacto Severo** | **.88$** | **.62$** | Ambos superan el mínimo normativo ($> 1.50$) |
| **$ frente a Pandeo** | No aplica | **.55$** | Seguro ante inestabilidad elástica |
| **Flecha Relativa ($\% L$)** | .82\%$ | .35\%$ | Cadena cinemática de alta rigidez |

---

## 📡 Bitácora de Validación del Enlace Cooperativo Wi-Fi STA, Actuadores y Relocalización Visual 3D

Esta sección documenta la validación experimental del sistema de comunicación en modo Estación (STA), la telemetría simultánea hacia la Raspberry Pi 5 y la arquitectura de relocalización cooperativa sobre el mapa tridimensional.

### 1. Enlace Inalámbrico en Modo Estación (STA) - Red de Misión Autónoma
- **Hotspot de la Raspberry Pi 5:** SSID: `aleskypi-5`, Contraseña: `alesky69`, Gateway: `10.42.0.1`.
- **Configuración Persistente en NetworkManager (`nmcli`):**
  ```bash
  sudo nmcli connection modify Hotspot connection.autoconnect yes
  sudo nmcli connection modify Hotspot connection.autoconnect-priority 100
  sudo nmcli connection modify Hotspot connection.id aleskypi-5
  ```
- **Adaptador USB Wi-Fi TP-Link TL-WN725N (Realtek RTL8188EU):**
  - Permite enlace multirred en la laptop de supervisión: `Wi-Fi` (Intel AX101) conectado a Internet (`UTEC-Alumnos`), mientras `Wi-Fi 2` (TP-Link) se enlaza a `aleskypi-5` (`10.42.0.178`).
  - Ping medido a Raspberry Pi 5 (`10.42.0.1`): **6 ms**.
  - Ping medido a Internet (`8.8.8.8`): **34 ms** simultáneo.
- **Acceso por Terminal SSH a la Raspberry Pi 5 desde Laptop (Wi-Fi):**
  - Comando directo (PowerShell / Terminal):
    ```powershell
    ssh alesky@10.42.0.1
    ```
    *(Contraseña de usuario SSH: **`alesky`** [sin el 69] | Contraseña del Wi-Fi: **`alesky69`** | Alternativa mDNS: `ssh alesky@aleskypi-5.local`)*
  - Transferencia de archivos (`scp`):
    ```powershell
    scp script.py alesky@10.42.0.1:~/
    ```
  - Ejecutar monitor TUI de telemetría:
    ```bash
    python3 monitor_hexapodo.py
    ```

### 2. Códigos de Éxito Validados en GitHub (`hexapodo-secundario-firmware`)
- **`VALIDADO_EXITOSO_firmware_esp32s3_sta_camara_gas_luz.c` (ESP-IDF v5.4.4):**
  - **Streaming UVC (Core 1):** $480 \times 320$ px MJPEG a **$14.9\text{ FPS}$ y $220\text{ KB/s}$ estables** en puerto 81 TCP (`/stream`). Mecanismo de cuadro de espera (*Standby Frame*) de 16x16 px a 2 Hz ante desconexión física de cámara.
  - **Sensor de Gas MiCS-5524 (Core 0):** Muestreo en GPIO 4 a 20 Hz con filtros Mediana ($N=5$) y EMA ($\alpha=0.20$), emitiendo datagramas UDP JSON continuos hacia `10.42.0.1:5005`.
  - **Luz de Inspección LED WS2812 (GPIO 48):** Driver nativo por hardware **RMT** a 10 MHz. Conmutación remota por HTTP (`/light?state=1`, `0`, `toggle`).
  - **Calibración Remota de $R_0$:** Endpoint `/calibrate` para auto-cero en aire limpio.
  - **Operación Móvil Autónoma:** Validado con banco de batería portátil USB (arranque en frío en 6–10 s con reconexión persistente infinita).
- **`firmware_arduino_solo_gas_sta_rpi.ino`:** Firmware alternativo ligero para ensayos ambientales exclusivos sin video.
- **`monitor_hexapodo.py`:** Tablero TUI para consola SSH en Raspberry Pi 5 (offline, sin GUI). Muestra nivel de gas a 20 Hz, mide FPS reales del video y permite conmutar la luz con `[L]` y calibrar con `[C]`.

### 3. Arquitectura de Localización Visual Monocular sobre Mapa Previo 3D (2D-to-3D Relocalization / PnP-RANSAC)
- **Concepto:** El robot primario genera un mapa métrico 3D (`hexapod_mapa.db`) con su cámara RGB-D Orbbec Gemini 2 y RTAB-Map SLAM (Keyframes con descriptores ORB y coordenadas métricas $X,Y,Z$ globales). El robot secundario (sin cámara de profundidad por restricciones de peso $<650\text{ g}$) transmite fotogramas 2D monocular UVC a 15 FPS.
- **Formulación:** La Raspberry Pi 5 reconoce la escena mediante Bag of Words (BoW), empareja los puntos 2D del secundario $(u, v)$ con los puntos 3D del mapa $(X, Y, Z)$ y resuelve la pose 6-DoF mediante el algoritmo **Perspective-n-Point con RANSAC (`solvePnPRansac`)**:
  $$\min_{\mathbf{R}, \mathbf{t}} \sum_{i} \left\| \begin{bmatrix} u_i \\ v_i \end{bmatrix} - \pi(\mathbf{K} \cdot (\mathbf{R} \mathbf{P}_{3D, i} + \mathbf{t})) \right\|^2$$
- **Salida:** Publicación de la transformada TF `map -> secondary_robot/base_link` y generación del mapa de calor de gases tridimensional en RViz 2.
- **Requisitos Críticos:** Calibración geométrica intrínseca de la cámara monocular $\mathbf{K}$, e iluminación activa obligatoria mediante el LED WS2812 en GPIO 48 para extracción de características en túneles oscuros.

---

## ⚡ Bitácora de Validación del Sensor de Corriente (Allegro ACS758LCB-050B + Arduino Nano)

Esta sección documenta la puesta en marcha, calibración metrológica y arquitectura de adquisición del sensor de consumo total de potencia para el robot primario Chipo (batería LiPo 3S 4500 mAh):

### 1. Hardware, Encapsulado y Mapa de Pines Validado
- **Módulo:** Placa de circuito impreso morada (tipo CJMCU-758 / HW-525).
- **Sensor Principal:** Circuito integrado de efecto Hall lineal **Allegro MicroSystems ACS758LCB-050B** (montado en el reverso, encapsulado de potencia CB de 5 pines, aislamiento galvánico $> 3000\text{ V}_{\text{RMS}}$, resistencia del conductor primario $\sim 100\,\mu\Omega$).
- **Acondicionamiento Superior:** Amplificador operacional doble de 8 pines (TLC2272 o equivalente) en configuración buffer seguidor de tensión ($A_v = 1$).
- **Tarjeta Adquisidora:** Arduino Nano (ATmega328P @ 16 MHz, chip USB FTDI FT232RL reconocido en Windows como `USB Serial Port (COM15)` a 115200 baudios).

| Pin del Sensor (Placa Morada) | Conexión en Arduino Nano / Sistema | Función y Justificación Técnica |
| :--- | :--- | :--- |
| **`IP+` (Terminal grueso)** | En serie con cable rojo (+ Batería LiPo 3S) | Entrada de corriente de la batería hacia el bus de potencia del robot. |
| **`IP-` (Terminal grueso)** | En serie hacia interruptor general y Buck converters | Retorno/salida de corriente hacia los reguladores Buck (5.1V RPi y 6.0V Servos). |
| **`VCC` (Pad 4, junto a LED D1)** | **Pin 5V** del Arduino Nano | Alimentación ratiométrica de 5.0 V para el núcleo Hall y el op-amp. |
| **`GND` (Pad 3)** | **Pin GND** del Arduino Nano | **CRÍTICO:** Tierra lógica de referencia. **NO unir a la tierra de la batería ni a los motores** para preservar el aislamiento galvánico de 3 kV y evitar bucles de masa (*ground loops*). |
| **`OU1` (Pad 2, central)** | **Pin A1** del Arduino Nano | **Salida analógica directa** del pin 3 ($V_{IOUT}$) del ACS758 con filtro pasivo RC. Señal pura, libre de saturación activa. |
| **`OU2` (Pad 1, extremo superior)**| **DESCONECTADO (sin uso)** | Salida bufferizada por el amplificador operacional. Se descartó por saturación y oscilaciones espurias ante caídas de tensión en el riel USB de 5V. |

### 2. Lecciones Aprendidas y Solución de Errores Críticos
1. **Fenómeno del Pin Flotante y Ondas Senoidales Espurias:**
   - *Síntoma:* Al inicio, la pantalla mostraba oscilaciones suaves continuas en forma de onda senoidal de baja frecuencia (~0.33 Hz) entre $-1.5\text{ A}$ y $+2.5\text{ A}$, sin importar si la batería estaba apagada o encendida, e incluso al desconectar el cable de señal.
   - *Causa:* El pin analógico del microcontrolador quedó en alta impedancia (flotante / circuito abierto), actuando como una antena CMOS que captaba el ruido electromagnético ambiental y cargaba/descargaba el condensador interno de muestreo del ADC.
   - *Solución:* Se reasignó el canal en firmware al **Pin A1**, asegurando continuidad de cables con multímetro y conectándolo firmemente al pin **`OU1`** (salida directa de baja impedancia del sensor).
2. **Validación Metrológica con Multímetro (Ground-Truth):**
   - Con la batería apagada y el sensor alimentado a 5V desde el Nano, la medición física con multímetro DC entre `GND` y `OU1` confirmó una tensión fija y constante de **$2.50\text{ V} \pm 0.01\text{ V}$**, verificando que el sensor físico está 100% operativo y en reposo absoluto.
3. **Protocolo Estricto de Calibración de Cero (`[C]` - Zero Tare):**
   - **Condición obligatoria:** La calibración de cero debe ejecutarse con la **batería APAGADA** y la Raspberry Pi sin enviar señales PWM parásitas a los servos (corriente real = $0.00\text{ A}$).
   - Si se calibra con el robot encendido, se ignora el consumo base del sistema, falseando el cálculo de autonomía de la batería LiPo.
   - Al pulsar `[C]`, el sistema fija el offset ($V_{offset} \approx 2.505\text{ V}$) y centra la corriente exactamente en **$0.00\text{ A}$**.

### 3. Frecuencias de Muestreo, Digitalización y Resolución Efectiva
- **Frecuencia de Muestreo Físico Interno (Burst Sampling):** **$\approx 4.7\text{ kHz}$**.
  - Cada 50 ms, el firmware ejecuta un ciclo de **50 muestras analógicas sucesivas**:
    $$t_{\text{muestra}} = t_{\text{conv}} (\sim 112\,\mu\text{s}) + t_{\text{delay}} (100\,\mu\text{s}) \approx 212\,\mu\text{s} \implies f_s = \frac{1}{212\,\mu\text{s}} \approx \mathbf{4716\text{ Hz}}$$
  - Este sobremuestreo promedia y cancela en hardware el rizado de conmutación de alta frecuencia generado por el PWM de los 18 servomotores MG996R.
- **Frecuencia de Telemetría y Grabación CSV:** **$20\text{ Hz}$ ($\Delta t = 50\text{ ms}$)**.
  - Tasa de refresco a la que se emiten las tramas JSON por serial y se graban las filas en el archivo de misión.
- **Resolución Efectiva de Corriente:**
  - Resolución teórica del ADC (10 bits a 5V): $\Delta V = \frac{5.0\text{V}}{1023} \approx 4.887\text{ mV} \implies \Delta I = \frac{4.887\text{ mV}}{40\text{ mV/A}} = 0.122\text{ A}$ ($122\text{ mA}$).
  - Con el sobremuestreo de 50 muestras, la resolución efectiva mejora a **$< 35\text{ mA}$**.
- **Protocolo de Validación contra Osciloscopio:**
  - Acoplamiento DC, base de tiempo de 20 ms/div o 50 ms/div, promedio de trazas (`Average 16x/64x`) activado en el osciloscopio para comparar la componente media DC.
  - Error relativo esperado respecto a osciloscopio de banco calibrado: **$< 2.5\%$**.

### 4. Arquitectura de Software y Herramientas del Módulo
- **Firmware C++ (Arduino Nano):** [`firmware_acs758_nano.ino`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/sensor_corriente/firmware_acs758_nano/firmware_acs758_nano.ino)
  - Configurado en Pin A1 a 115200 baudios, calibración en caliente por comando serial `'c'`, tramas JSON con marca de tiempo milimétrica, voltaje $V_{out}$, offset $V_0$, corriente instantánea $I$ y potencia instantánea $P$ (11.1V).
- **Visor Gráfico en Tiempo Real (OpenCV):** [`visor_corriente_python.py`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/sensor_corriente/visor_corriente_python.py)
  - Osciloscopio con eje de cero centralizado, selector dinámico de escalas mediante tecla **`[E]`** ($\pm 50\text{ A}$, $\pm 20\text{ A}$ y $\pm 5\text{ A}$), tecla **`[C]`** para tara de cero, tecla **`[I]`** para invertir signo, tecla **`[R]`** para iniciar/pausar grabación CSV y **`[S]`** para capturas PNG.
- **Lanzador de un Clic (.bat):** [`iniciar_visor_corriente.bat`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/iniciar_visor_corriente.bat)
- **Generador de Gráficas de Publicación para Tesis:** [`graficar_datos_corriente.bat`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/graficar_datos_corriente.bat) y [`graficar_csv_corriente.py`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/sensor_corriente/graficar_csv_corriente.py). Genera figuras de 3 subplots (Corriente, Potencia y Consumo en mAh) a 300 DPI.
- **Registros de Ensayos:** Guardados automáticamente en `pruebas/datos_mision/registro_corriente_<fecha_hora>.csv`.

### 5. ADVERTENCIA CRÍTICA: Prohibición de Conexión Directa a GPIO de Raspberry Pi 5
- **REGLA DE SEGURIDAD ABSOLUTA:** **Queda estrictamente PROHIBIDO conectar la salida analógica del sensor (`OU1` o `OU2`) de forma directa a los pines GPIO de la Raspberry Pi 5.**
- **Justificación Física y de Hardware:**
  1. **Incompatibilidad de Voltaje (Riesgo de Destrucción del Silicio):** Los 40 pines GPIO de la Raspberry Pi 5 operan exclusivamente a niveles lógicos de **$3.3\text{ V}$** con un límite máximo absoluto de **$3.6\text{ V}$** (NO son tolerantes a 5V). La salida analógica del ACS758 entrega $2.5\text{V}$ en reposo y hasta **$5.0\text{ V}$** ante picos de corriente o arranques. Conectar $> 3.3\text{V}$ directo al GPIO inyecta sobretensión que destruye de forma irreversible el chip controlador de I/O **RP1** o el SoC de la Raspberry Pi 5 (\$80+ USD).
  2. **Ausencia de ADC en Raspberry Pi 5:** La Raspberry Pi 5 carece de convertidor analógico-digital interno (todos sus pines son estrictamente digitales: `HIGH`/`LOW`).
- **Arquitectura Oficial de Integración (Co-procesador USB en Chipo / ROS 2):**
  - El **Arduino Nano se mantiene permanentemente como co-procesador esclavo de adquisición analógica** (operando nativamente a 5.0 V seguro con inmunidad total a sobretensiones).
  - El Arduino Nano se conecta a la Raspberry Pi 5 **exclusivamente mediante cable USB** (`/dev/ttyUSB0` a 115200 baudios).
  - Esta topología aísla galvánicamente la Raspberry Pi, delega el sobremuestreo rápido ($4.7\text{ kHz}$) fuera del CPU principal, y permite que un nodo ROS 2 en la Pi 5 publique la telemetría en el tópico estándar `/battery_state` (`sensor_msgs/msg/BatteryState`).
  - *Alternativa secundaria autorizada (sin Arduino):* Convertidor ADC externo I2C de 16 bits **ADS1115** con divisor de tensión resistivo $10\text{ k}\Omega / 20\text{ k}\Omega$ en la entrada de señal.

---

## 🧪 Bitácora de Validación: Sensor de Gases MQ-9 + Corriente ACS758 (Arduino Nano + RPi 5)

Esta sección documenta la arquitectura integrada para la adquisición concurrente del sensor de gas **MQ-9** y el sensor de corriente **ACS758LCB-050B** sobre un único Arduino Nano esclavo:

### 1. Mapa de Pines Validado y Conexiones
```text
                        ┌────────────────────────┐
                        │      ARDUINO NANO      │
                        │                        │
  [MQ-9 Gas]            │                        │   [ACS758 Corriente]
  VCC ──────────────────┤ 5V                  5V ├── VCC
  GND ──────────────────┤ GND                GND ├── GND
  A0 (Voltaje Gas) ─────┤ A0                  A1 ├── OUT / OU1 (Voltaje Corriente)
  D0 (Alarma Digital) ──┤ D2                     │
                        └────────────────────────┘
```
- **MQ-9 (Gas):** VCC a 5V (consumo calefactor $\approx 150-180\text{ mA}$), GND común, A0 a **Pin A0**, D0 a **Pin D2** (umbral digital LM393).
- **ACS758 (Corriente):** VCC a 5V, GND común, OUT a **Pin A1** ($40\text{ mV/A}$).
- **Regla Eléctrica en Estrella:** Conectar VCC y GND de ambos sensores de forma independiente desde los pines 5V y GND del Arduino para evitar que la corriente del calefactor genere caídas de tensión parásitas sobre la medición ratiométrica del ACS758.

### 2. Modelo Matemático de Transducción a PPM (Wolkenstein-Clifford) y Extracción de Constantes $A$ y $B$
- **Divisor y Resistencia:** $V_{out} = \text{ADC} \times \frac{5.0\text{V}}{1023} \implies R_s = R_L \left(\frac{V_{CC} - V_{out}}{V_{out}}\right)$ con $R_L = 10\text{ k}\Omega$.
- **Calibración $R_0$ en Aire Limpio:** Según datasheet MQ-9 (Hanwei Electronics), $(R_s/R_0)_{\text{aire}} = 9.80 \implies R_0 = R_{s,\text{aire}} / 9.80$.
- **Ley de Potencias Linealizada en Escala Log-Log:**
  $$\text{ppm} = A \cdot \left(\frac{R_s}{R_0}\right)^B \iff \log_{10}(\text{ppm}) = \log_{10}(A) + B \cdot \log_{10}\left(\frac{R_s}{R_0}\right)$$
  - **Significado de $B$ (Pendiente logarítmica / Velocidad catalítica):** Inclinación de la recta en la gráfica log-log del datasheet; cuantifica la sensibilidad con que cae $R_s$ ante un incremento de gas reductor (negativa porque a mayor ppm, menor $R_s$). Se calcula entre dos puntos $(P_1, P_2)$ de la curva:
    $$B = \frac{\log_{10}(\text{ppm}_2) - \log_{10}(\text{ppm}_1)}{\log_{10}(\text{Ratio}_2) - \log_{10}(\text{Ratio}_1)}$$
  - **Significado de $A$ (Factor de escala / Intercepto en $R_s/R_0 = 1$):** Concentración en $\text{ppm}$ necesaria para que la resistencia del sensor iguale a la referencia ($R_s = R_0$):
    $$A = \frac{\text{ppm}_1}{(\text{Ratio}_1)^B}$$
  - **Deducción Numérica para Etanol (Alcohol):** Con $P_1 = (1000\text{ ppm}, 2.40)$ y $P_2 = (5000\text{ ppm}, 1.20)$:
    $$B = \frac{\log_{10}(5000) - \log_{10}(1000)}{\log_{10}(1.20) - \log_{10}(2.40)} = \frac{0.69897}{-0.30103} = \mathbf{-2.322}, \quad A = 1000 \times (2.40)^{2.322} = \mathbf{7630.0}$$
    $$\implies \text{ppm}_{\text{alc}} = 7630.0 \cdot \left(\frac{R_s}{R_0}\right)^{-2.322}$$
  - **Otros Gases del Datasheet MQ-9:**
    - **Monóxido de Carbono ($\text{CO}$):** $A = 599.65$, $B = -2.244 \implies \text{ppm}_{\text{CO}} = 599.65 \cdot (R_s/R_0)^{-2.244}$.
    - **GLP (LPG):** $A = 1000.5$, $B = -2.186 \implies \text{ppm}_{\text{LPG}} = 1000.5 \cdot (R_s/R_0)^{-2.186}$.
    - **Metano ($\text{CH}_4$):** $A = 4269.6$, $B = -2.648 \implies \text{ppm}_{\text{CH4}} = 4269.6 \cdot (R_s/R_0)^{-2.648}$.
- **Estrategia de Calibración para la Tesis (Sin Cámara Hermética):**
  1. **Calibración Basal Unipuntual ($R_0$):** Sustentada en **Bârsan & Weimar (2001)** (la pendiente $B$ es un invariante estequiométrico del $\text{SnO}_2$ y la dispersión de lote se concentra en $R_0$) y **Burgués & Marco (2018)** (*Zero-Gas In-Situ Reference*).
  2. **Intercalibración Cruzada por Co-localización (*Co-located Cross-Calibration*):** El sensor MEMS **MiCS-5524** (del robot secundario, fabricado por fotolitografía de alta repetibilidad) se emplea como transductor de referencia de transferencia colocado a $1-2\text{ cm}$ del **MQ-9** (del robot primario) ante gradientes de vapor de etanol ($2\text{ a }20\text{ cm}$), garantizando coherencia escalar entre ambos robots en ROS 2.
- **Archivos de Gráficas y Datasheet en Repositorio:**
  - Datasheet oficial Hanwei MQ-9: [`MQ-9_Datasheet.pdf`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/sensor_gas/firmware_mq9_corriente_nano/MQ-9_Datasheet.pdf)
  - Curva original extraída del datasheet (Fig. 1): [`fig1_curva_sensibilidad_mq9_original.png`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/sensor_gas/firmware_mq9_corriente_nano/fig1_curva_sensibilidad_mq9_original.png)
  - Figura compuesta con regresión potencial a 300 DPI: [`grafica_regresion_mq9_datasheet.png`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/sensor_gas/firmware_mq9_corriente_nano/grafica_regresion_mq9_datasheet.png)

### 3. Software y Herramientas del Módulo
- **Firmware C++ (Arduino Nano):** [`firmware_mq9_corriente_nano.ino`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/sensor_gas/firmware_mq9_corriente_nano/firmware_mq9_corriente_nano.ino)
  - Emite JSON a 115200 baudios (20 Hz): `{"t":1227,"gas_v":0.850,"gas_raw":174.0,"gas_ratio":1.000,"rs_r0":9.800,"ppm_alc":38.2,"ppm_co":0.0,"gas_alerta":0,"i_amp":0.00,"i_v":2.500,"pot_w":0.00}`.
- **Monitor en Consola para Raspberry Pi 5:** [`monitor_sensores_rpi.py`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/sensor_gas/monitor_sensores_rpi.py)
  - Conexión por USB (`/dev/ttyUSB0`) a 115200 baudios, visualización de PPM Etanol, PPM CO y alertas.
- **Visor Gráfico en Tiempo Real (OpenCV en PC):** [`visor_gas_mq9.py`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/sensor_gas/visor_gas_mq9.py) y lanzador [`iniciar_visor_gas_mq9.bat`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/iniciar_visor_gas_mq9.bat).
- **Documentación Técnica para el Equipo:** [`README.md`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/sensor_gas/firmware_mq9_corriente_nano/README.md).

---

## 🦾 Bitácora de Locomoción del Hexápodo Primario: Control de Servos (Pololu Maestro), Marcha HOME3 y Acceso SSH

Esta sección documenta el control físico y la cinemática del robot primario operado desde la Raspberry Pi 5:

### 1. Conectividad y Control Autónomo por SSH
- **Enlace de Red:** Punto de acceso Wi-Fi autónomo generado por la Raspberry Pi 5 (SSID: `aleskypi-5`, IP Gateway: `10.42.0.1`).
  - *Clave de Wi-Fi:* `alesky69`
  - *Usuario Linux / Sudo:* `alesky` (clave del SO: `alesky`).
- **Autenticación sin Contraseña:** Par de llaves SSH ed25519 instalado en `~/.ssh/id_ed25519` (PC) y `~/.ssh/authorized_keys` (RPi 5). El agente y los scripts ejecutan comandos de forma no interactiva con `ssh alesky@10.42.0.1`.

### 2. Mapeo Físico de Canales Pololu Mini Maestro (18 Servomotores MG996R)
- **Controlador:** Pololu Mini Maestro 18 canales conectado por USB nativo (`/dev/ttyACM0` comando, `/dev/ttyACM1` TTL).
- **Riel de Potencia:** Batería 3S con convertidor Buck a 6.0V (10A cont / 15A pico), monitoreado en corriente por el Arduino Nano en `/dev/ttyUSB0`.
- **Mapeo Articular por Pata:**
  | Extremidad | Coxa | Fémur | Tibia | Sensor Contacto Pie (BCM) |
  | :--- | :---: | :---: | :---: | :---: |
  | **Pata 1 (Trasera Derecha)** | CH0 | CH1 | CH2 | GPIO 17 |
  | **Pata 2 (Media Derecha)** | CH3 | CH4 | CH5 | GPIO 27 |
  | **Pata 3 (Delantera Derecha)** | CH6 | CH7 | CH8 | GPIO 22 |
  | **Pata 4 (Delantera Izquierda)** | CH9 | CH10 | CH11 | GPIO 25 |
  | **Pata 5 (Media Izquierda)** | CH12 | CH13 | CH14 | GPIO 24 |
  | **Pata 6 (Trasera Izquierda)** | CH15 | CH16 | CH17 | GPIO 23 |
- **Parámetros de Calibración:**
  - Pulso neutro ($0^\circ$): $1504\,\mu\text{s}$ (6016 en cuartos de microsegundo).
  - Factor de escala angular: $631.5268\,\mu\text{s/rad} \approx 11.02\,\mu\text{s/grado}$.

### 3. Evolución Cinemática de la Marcha: De HOME2 a HOME3 (Postura Semi-extendida)
- **Problema Crítico de Torque en HOME2 (Postura Agachada):**
  - En HOME2, los fémures estaban a $\approx +30^\circ$ y las tibias muy flexionadas a $\approx -81^\circ$ (casi $90^\circ$).
  - La distancia horizontal efectiva (brazo de palanca) entre el eje articular del fémur y la punta de apoyo del pie alcanzaba los **$153\text{ mm}$**.
  - Con una masa total de $3\text{ kg}$ en marcha trípode ($12.5\text{ N}$ en la pata central), el par estático requerido en el fémur llegaba a **$1.89\text{ N}\cdot\text{m}$ ($19.3\text{ kgf}\cdot\text{cm}$)**.
  - El servomotor **MG996R a 6V** especifica un par de bloqueo (*stall torque*) de $1.08\text{ N}\cdot\text{m}$ ($11\text{ kgf}\cdot\text{cm}$), siendo el par continuo admisible muy inferior. Como resultado, los servos de los fémures operaban en sobrecarga extrema, recalentándose y perdiendo retención (falla detectada en Fémur 6).
- **Solución Implementada: HOME3 (Postura Semi-extendida):**
  - **Ángulos de Articulación:** Fémur a $\approx -50.7^\circ / +49.3^\circ$ y Tibia a $\approx -46.0^\circ / +48.0^\circ$ (ambos eslabones semi-extendidos de forma equilibrada).
  - **Reducción del Brazo de Palanca:** Eleva el cuerpo (despeje de $194\text{ mm}$ bajo `base_link`) y recoge los pies hacia adentro, reduciendo el brazo horizontal efectivo del fémur de $153\text{ mm}$ a solo **$36 - 37\text{ mm}$**.
  - **Impacto en el Torque:**
    - Par estático pico en Fémur: Reducido de $1.89\text{ N}\cdot\text{m} \to \mathbf{0.46\text{ N}\cdot\text{m}}$ ($\approx 4.7\text{ kgf}\cdot\text{cm}$, **reducción del $75.6\%$**).
    - Par estático pico en Tibia: Reducido de $1.04\text{ N}\cdot\text{m} \to \mathbf{0.20\text{ N}\cdot\text{m}}$ ($\approx 2.0\text{ kgf}\cdot\text{cm}$, **reducción del $80.8\%$**).
  - **Beneficio Operativo:** Permite que los MG996R operen holgadamente dentro de su rango térmico y dinámico seguro, eliminando el riesgo de desconexión o desgranamiento de piñones metálicos durante la marcha trípode continua.

### 4. Bitácora de Pruebas Físicas de Locomoción Ejecutadas en el Robot Primario (21/11/2026)
- **Infraestructura de Prueba:** Raspberry Pi 5 conectada por USB al Pololu Mini Maestro 18 (`/dev/ttyACM0`) y al Arduino Nano (`/dev/ttyUSB0` con ACS758/ACS712 a 115200 baud). Riel de 6V alimentado y supervisado.
- **Pruebas Completadas con Éxito:**
  1. **Movimiento Articular Coxa 2:** Rotación angular suave de $+20^\circ$ ($1504\,\mu\text{s} \to 1724\,\mu\text{s} \to 1504\,\mu\text{s}$) con velocidad limitada a 25 y aceleración a 8 para mitigar estrés en engranajes.
  2. **Ensayo de Articulaciones Pata 6 (Trasera Izquierda):**
     - Movimiento amplio de Fémur 6 ($1504\,\mu\text{s} \to 1700\,\mu\text{s} \to 1200\,\mu\text{s} \to 1504\,\mu\text{s}$).
     - Movimiento amplio de Tibia 6 ($1504\,\mu\text{s} \to 1300\,\mu\text{s} \to 1850\,\mu\text{s} \to 1504\,\mu\text{s}$).
     - Picos de corriente registrados por el sensor Hall: $0.37\text{ A}$ a $0.57\text{ A}$.
  3. **Simulación de Marcha en el Aire Pata 6 con Interrupción de Seguridad:**
     - 3 ciclos completos de marcha (Vuelo $\to$ Avance $\to$ Descenso $\to$ Propulsión).
     - Supervisión continua a 100 Hz del sensor de contacto en punta en **GPIO 23 BCM**.
     - Comprobada la lógica de parada inmediata de emergencia si el switch se activa durante el movimiento.
  4. **Retracción y Desenergización de Pata 6:**
     - Comprobación de imposibilidad de lectura de potenciómetro en servos estándar MG996R (Maestro devuelve $0.0\,\mu\text{s}$ en canales apagados como Pata 5: CH12, CH13, CH14).
     - Repliegue suave de Pata 6 hacia el chasis y corte de pulsos PWM (`target = 0`) para dejar la pata libre y sin consumo eléctrico.
  5. **Simulación de Marcha en el Aire Pata 1 (Trasera Derecha):**
     - Canales: Coxa (CH0), Fémur (CH1), Tibia (CH2).
     - 3 ciclos completos de marcha coordinada:
       - Vuelo: Fémur arriba ($1750\,\mu\text{s}$), Tibia recogida ($1400\,\mu\text{s}$).
       - Avance: Coxa adelante ($1350\,\mu\text{s}$).
       - Descenso: Apoyo simulado ($1550\,\mu\text{s}$ / $1600\,\mu\text{s}$).
       - Propulsión: Coxa empujando hacia atrás ($1650\,\mu\text{s}$).
     - Supervisión de seguridad activa a 100 Hz en el switch de pie en **GPIO 17 BCM**.
     - Retorno suave a neutral ($1504\,\mu\text{s}$). Ejecución 100% exitosa.
  6. **Extensión Global (Postura Estrella) y Liberación PWM:**
     - Validación de consigna a 18 canales simultáneos con rampa escalonada ($1504\,\mu\text{s}$) y posterior corte de pulsos (`target = 0`) para desenergización completa ($I = 0.00\text{ A}$, $P = 0.00\text{ W}$).
  7. **Diagnóstico y Reemplazo de Servomotor en Fémur 3 (Canal 7):**
     - *Falla identificada:* Pata 3 no mantenía rigidez en prueba de extensión. La inspección física reveló que el servo instalado poseía engranajes internos de nylon/plástico blanco que se habían desgranado/robado bajo carga.
     - *Solución:* Sustitución por servomotor con piñonería íntegramente metálica.
     - *Verificación:* Extensión y energización activa de Pata 3 (CH6, CH7, CH8 a $1504\,\mu\text{s}$) para validación táctil de rigidez y par de retención.
  8. **Ensayo de Marcha Suavizada Anti-Temblor en Pata 3:**
     - *Ajuste Dinámico:* Rampa trapezoidal por hardware en Pololu Maestro (`accel = 6` en Fémur 7 y Tibia 8; `accel = 8` en Coxa 6; `speed = 22 - 24`), control de jerk y ajuste mecánico de tornillo en cuerno del servo.
     - *Resultado:* 3 ciclos completos de marcha (vuelo suave $\to$ avance en aire $\to$ descenso $\to$ propulsión) ejecutados sin temblor ni resonancia elástica en voladizo. Corriente basal controlada ($0.00\text{ A}$ a $0.35\text{ A}$, pico transitorio de $1.15\text{ A}$ en despegue).
  9. **Marcha Bioinspirada con Plegado de Tibia (Tipo Insecto) en Pata 3:**
     - *Diagnóstico Físico:* El temblor residual en el aire se concentraba al detenerse en la cota de vuelo por caza en la zona muerta del servo debido al par de gravedad ejercido por la pata estirada ($L \approx 180\text{ mm}$).
     - *Ajustes Combinados:*
       1. *Recomendación A (Controlador):* Rampa ultra-progresiva con `accel = 3` y `speed = 14` en Fémur y Tibia (`accel = 4`, `speed = 16` en Coxa).
       2. *Recomendación B (Cinemática):* Plegado pronunciado de tibia a $1240\,\mu\text{s}$ ($\approx -24^\circ$) durante el despegue y avance en el aire, reduciendo el brazo de palanca y la inercia angular ($J \propto m L^2$) en un $75\%$. Extensión coordinada a $1560\,\mu\text{s}$ en la fase de descenso.
     - *Resultado:* Ejecución de 3 ciclos completos con despegue sedoso, avance en vuelo compacto y aterrizaje amortiguado.







---

## 📐 Análisis Estructural Analítico y Validación FEA de la Extremidad del Hexápodo Secundario (Fémur, Tibia y Coxa)

Esta sección consolida el marco analítico de resistencia de materiales, la evolución morfológica del diseño CAD y la validación por Elementos Finitos (FEA en Autodesk Fusion 360) de la pata del robot secundario:

### 1. Parámetros de Manufactura Aditiva y Criterio de Sólido Continuo (FDM)
- **Material de Fabricación Real:** PLA ($S_y = 40.0\text{ MPa}$ paralelo a capas, $E = 3500.0\text{ MPa}$).
- **Configuración de Laminado:** Relleno volumétrico del $8\%$ (*grid infill*) con **3 perímetros sólidos de pared** (boquilla de $0.40\text{ mm}$).
- **Criterio de Consolidación Maciza:** Tres perímetros por cara aportan $2 \times (3 \times 0.40\text{ mm}) = \mathbf{2.40\text{ mm}}$ de pared sólida continua. En todas las nervaduras críticas del fémur ($t_{\text{pared}} \approx 2.31\text{ mm}$) y de la tibia ($t_{\text{pared}} = 2.00\text{ mm}$ a cada lado de la ventana), las paredes opuestas se fusionan al **$100\%$ como sólido macizo**, validando el uso riguroso de la teoría clásica de vigas continuas de Navier (*Budynas & Nisbett, 2020*; *Beer et al., 2020*).

### 2. Cálculo Analítico de Secciones Críticas (Fémur vs. Tibia)
- **Solicitaciones de Diseño:** Reacción vertical máxima en punta de pata $F_{\text{pie}} = 10.0\text{ N}$ y par de bloqueo del micromotor N20 1:300 $T_{\text{stall}} = 350.0\text{ N}\cdot\text{mm}$.
- **Eslabón del Fémur ($L = 60.00\text{ mm}$):**
  - *Sección crítica gobernante (Pieza central ocre `Femursoporte`):* Ancho total $B = 18.90\text{ mm}$, peralte vertical $H = 9.00\text{ mm}$, $2\times$ taladros transversales $\varnothing 5.975\text{ mm} \implies B_{\text{neto}} = 6.95\text{ mm}$.
  - *Propiedades resistentes:* $I_v = \frac{6.95 \cdot 9.00^3}{12} = \mathbf{422.21\text{ mm}^4}$, $Z_v = \frac{I_v}{4.50} = \mathbf{93.82\text{ mm}^3}$, factor de concentración elástica $K_t = \mathbf{2.00}$ ($d/B = 0.316$, *Pilkey et al., 2020*).
  - *Demostración frente a piezas blanca (`Femursup`, $Z = 140.40\text{ mm}^3$) y rosada (`Femurinf`, $Z = 133.65\text{ mm}^3$):* El índice de severidad $\psi = K_t / Z$ en la pieza ocre ($0.0213\text{ mm}^{-3}$) es **$2.6\times$ superior** al de los soportes extremos ($0.0082\text{ mm}^{-3}$).
  - *Factores de Seguridad y Rigidez:*
    - Stall motor ($350\text{ N}\cdot\text{mm}$): $\sigma_{\text{max}} = 7.46\text{ MPa} \implies \mathbf{FoS = 5.36}$.
    - Marcha normal ($M = 500\text{ N}\cdot\text{mm}$): $\sigma_{\text{max}} = 10.66\text{ MPa} \implies \mathbf{FoS = 3.75}$.
    - Extensión máxima / impacto ($M = 1000\text{ N}\cdot\text{mm}$): $\sigma_{\text{max}} = 21.32\text{ MPa} \implies \mathbf{FoS = 1.88} > 1.50$.
    - Flecha en voladizo: $\delta_{\text{fémur}} = \mathbf{0.49\text{ mm}}$ ($0.82\%$ de $L$).
- **Eslabón de la Tibia ($L_{\text{total}} = 114.11\text{ mm}$):**
  - *Cinemática del codo bioinspirado a $\alpha = 150^\circ$ ($\theta = 30^\circ$):* Tramo proximal $L_1 = 89.00\text{ mm}$, punta distal $L_2 = 29.00\text{ mm}$ (ancho de suela $14.90\text{ mm}$) $\implies L_x = 89 + 29\cos(30^\circ) = \mathbf{114.11\text{ mm}}$, $e_y = 29\sin(30^\circ) = \mathbf{14.50\text{ mm}}$.
  - *Propiedades de sección (celosía amarilla `Tibiamed`):* Peralte en vista lateral $H = 10.20\text{ mm}$ ($c_v = 5.10\text{ mm}$), ancho sólido neto en vista superior $B_{\text{neto}} = 4.00\text{ mm}$.
  - *Inercias y concentrador:* $I_{\text{vertical}} = \frac{4.00 \cdot 10.20^3}{12} = \mathbf{353.74\text{ mm}^4}$, $Z_v = \mathbf{69.36\text{ mm}^3}$, inercia mínima lateral (pandeo out-of-plane) $I_{\text{mín}} = \frac{10.20 \cdot 4.00^3}{12} = \mathbf{54.40\text{ mm}^4}$, concentrador en ranura ovalada $K_t \approx \mathbf{1.50}$ (*Pilkey et al., 2020*).
  - *Factores de Seguridad, Pandeo y Rigidez:*
    - Marcha normal ($M = 500\text{ N}\cdot\text{mm}$): $\sigma_{\text{max}} = 10.82\text{ MPa} \implies \mathbf{FoS = 3.70}$ (equilibrio estructural armónico con el fémur).
    - Extensión horizontal máxima ($M = 1141.1\text{ N}\cdot\text{mm}$): $\sigma_{\text{max}} = 24.68\text{ MPa} \implies \mathbf{FoS = 1.62} > 1.50$.
    - Pandeo elástico de Euler ($L_e = 0.80 L_x = 91.29\text{ mm}$): $P_{\text{cr}} = \frac{\pi^2 E I_{\text{mín}}}{L_e^2} = \mathbf{225.48\text{ N}} \implies \mathbf{FoS_{\text{pandeo}} = 22.55}$.
    - Flecha elástica: $\delta_{\text{tibia}} = \mathbf{0.40\text{ mm}}$ ($0.35\%$ de $L_x$).

### 3. Validación Numérica por Elementos Finitos (FEA - Autodesk Fusion 360) y Evolución de Diseño

Se ejecutaron tres estudios estáticos lineales con elementos tetraédricos parabólicos de segundo orden para validar la evolución desde el penúltimo prototipo hasta el diseño definitivo en dos posturas extremas:

| Parámetro / Resultado FEA | Penúltimo Diseño (Posición Retraída - Estudio 4) | Último Diseño: Posición Extendida (Estudio 1) | Último Diseño: Posición Retraída (Estudio 2) |
| :--- | :---: | :---: | :---: |
| **Archivo CAD / Componentes** | `Analisispata1Alesky` (9 cuerpos) | `AnalisisPata1Alfred` (13 cuerpos) | `AnalisisPata1Alfred` (13 cuerpos) |
| **Material de Librería Simulado** | ABS ($E = 2240\text{ MPa}$, $S_y = 20.0\text{ MPa}$) | PET ($E = 2757.9\text{ MPa}$, $S_y = 54.4\text{ MPa}$) | PET ($E = 2757.9\text{ MPa}$, $S_y = 54.4\text{ MPa}$) |
| **Malla (Elementos / Nodos)** | $112\,985$ elem. / $163\,314$ nodos | $116\,115$ elem. / $192\,017$ nodos (2% curvo) | $187\,896$ elem. / $310\,629$ nodos (4% escalado) |
| **Fuerza Vertical en Punta ($F_z$)** | $6.00\text{ N}$ ($15^\circ$) + Gravedad | $7.00\text{ N}$ ($+Z$) + Gravedad | $5.95\text{ N}$ ($F = 6.00\text{ N}$) + Gravedad |
| **Estado Estructural de Fémur y Tibia** | Esfuerzos moderados ($8 - 19.7\text{ MPa}$) en `Femur_Med1` y cuello `coxa_femur` | **100% Azul Oscuro ($FoS \ge 4.00 - 8.00$, $\sigma < 13.6\text{ MPa}$)** | **100% Azul Oscuro ($FoS \ge 4.00 - 8.00$, $\sigma < 13.6\text{ MPa}$)** |
| **Zona de Singularidad Puntual** | Arista de cuello `coxa_femur` ($\sigma_{VM} = 79.18\text{ MPa}$, $\sigma_1 = 19.69\text{ MPa}$) | Borde anular superior `J0sup` $\parallel$ `Coxasup` ($\sigma_{VM} = 833.6\text{ MPa}$, $\sigma_1 = 163.8\text{ MPa}$) | Borde anular superior `J0sup` $\parallel$ `Coxasup` ($\sigma_{VM} = 595.9\text{ MPa}$, $\sigma_1 = 121.9\text{ MPa}$) |
| **Desplazamiento Total en Punta** | $3.946\text{ mm}$ ($\approx 2.53\text{ mm}$ en PLA) | $14.623\text{ mm}$ (rotación en junta $J_0$) | $22.071\text{ mm}$ (fijación solo en pestaña inferior de $J_0$) |

#### Conclusiones Mecánicas Fundamentales de los Estudios FEA:
1. **Validación Definitiva de Fémur y Tibia ($FoS > 4.0$ en todo el cuerpo):** En el último diseño (`AnalisisPata1Alfred`), tanto en posición extendida como retraída, el **100% de la Tibia (`Tibiamed`, `Tibiapunta`) y el 100% del Fémur (`Femursup`, `Femursoporte`, `Femurinf`) permanecen en la región azul de máxima seguridad ($FoS \in [4.0, 8.0]$, esfuerzos reales $< 13.6\text{ MPa}$)**, coincidiendo de forma exacta con el cálculo analítico ($\sigma_{\text{max}} \approx 10.7 - 10.8\text{ MPa}$, $FoS \approx 3.70 - 3.75$).
2. **Impacto de la Postura Extendida vs. Retraída (+39.9% de Momento Flector):** Comparando el Estudio 1 (Extendida, $7\text{ N}$) frente al Estudio 2 (Retraída, $6\text{ N}$), el esfuerzo concentrado en la articulación proximal de la coxa (`Coxasup`) aumenta un **$39.9\%$ en Von Mises** ($833.6\text{ MPa}$ vs. $595.9\text{ MPa}$) y un **$34.3\%$ en tracción principal $\sigma_1$** ($163.8\text{ MPa}$ vs. $121.9\text{ MPa}$), comprobando numéricamente que la postura extendida es el caso crítico de momento flector por el incremento del brazo de palanca horizontal.
3. **Diagnóstico de la Singularidad en `J0sup` $\parallel$ `Coxasup` e Importancia del Doble Apoyo del Motor N20:**
   - En el CAD simplificado sin motores, la brida inferior de la horquilla (`J0inf` con 4 pines) queda sin contacto mecánico con `CoxaInf`, dejando a toda la pata suspendida únicamente de un borde anular superior de espesor infinitesimal entre `J0sup` y `Coxasup`.
   - Esa ausencia del eje pasante inferior provoca: (a) una singularidad numérica puntual de contacto ($596 - 833\text{ MPa}$) en 1–2 elementos de borde sin refinado adaptativo (`pasos = 0`), y (b) un giro angular rígido en la junta $J_0$ que explica los desplazamientos en la punta ($14.6\text{ mm}$ cuando `Fijo1` sujeta el respaldo vertical de `J0sup`, y $22.1\text{ mm}$ cuando `Fijo1` sujeta solo la pestaña horizontal inferior de `J0sup`, haciendo que la horquilla en C flecte como un resorte).
   - **Justificación de Ingeniería para la Tesis:** Este resultado demuestra por qué en el ensamble físico real es **obligatorio el montaje de doble soporte axial** (eje del motor N20 arriba + pivote/acople inferior en `J0inf`/`CoxaInf`), el cual cierra el circuito de fuerzas en **corte doble**, elimina el voladizo en la horquilla `J0sup` y restituye la rigidez cinemática ($\delta < 0.5\text{ mm}$ por eslabón).
4. **Evolución del Penúltimo al Último Diseño:**
   - Se eliminó el cuello en voladizo `coxa_femur` y los tambores tipo bisagra multi-disco del penúltimo diseño (donde se concentraban $19.7\text{ MPa}$ de tracción), reemplazándolos por horquillas simétricas robustas (`Coxamed1`/`Coxamed2` y `Femursup`/`Femurinf`).
   - Se optimizaron las ventanas de la tibia (`Tibiamed`) pasando de 2 ranuras pequeñas a una celosía aligerada con codo de $150^\circ$ y puntera redondeada (`Tibiapunta`), reduciendo la inercia rotacional distal sin comprometer la resistencia ($FoS > 4.0$).

### 4. Referencias Bibliográficas del Análisis Mecánico
1. **Budynas, R. G., & Nisbett, J. K. (2020).** *Shigley's Mechanical Engineering Design* (11th ed.). McGraw-Hill.
2. **Beer, F. P., Johnston, E. R., DeWolf, J. T., & Mazurek, D. F. (2020).** *Mecánica de Materiales* (8.ª ed.). McGraw-Hill.
3. **Pilkey, W. D., Pilkey, D. F., & Bi, Z. (2020).** *Peterson's Stress Concentration Factors* (4th ed.). John Wiley & Sons.
4. **Norton, R. L. (2020).** *Diseño de Máquinas: Un enfoque integrado* (5.ª ed.). Pearson.
5. **Young, W. C., Budynas, R. G., & Sadegh, A. M. (2012).** *Roark's Formulas for Stress and Strain* (8th ed.). McGraw-Hill.
