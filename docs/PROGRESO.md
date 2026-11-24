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
* **Control Articular Físico, Mapeo y Pruebas de Marcha (Validado 21/11/2026):**
  - **Acceso Remoto Autónomo:** Configurado acceso SSH no interactivo mediante par de llaves criptográficas `ed25519` desde PC hacia la Raspberry Pi 5 (`alesky@10.42.0.1`) sobre el hotspot `aleskypi-5`.
  - **Mapeo Físico de Canales Pololu Mini Maestro (18 Servomotores MG996R):**
    - Pata 1: CH0 (Coxa), CH1 (Fémur), CH2 (Tibia) | Contacto: GPIO 17 BCM.
    - Pata 2: CH3 (Coxa), CH4 (Fémur), CH5 (Tibia) | Contacto: GPIO 27 BCM.
    - Pata 3: CH6 (Coxa), CH7 (Fémur), CH8 (Tibia) | Contacto: GPIO 22 BCM.
    - Pata 4: CH9 (Coxa), CH10 (Fémur), CH11 (Tibia) | Contacto: GPIO 25 BCM.
    - Pata 5: CH12 (Coxa), CH13 (Fémur), CH14 (Tibia) | Contacto: GPIO 24 BCM.
    - Pata 6: CH15 (Coxa), CH16 (Fémur), CH17 (Tibia) | Contacto: GPIO 23 BCM.
  - **Ensayos Articulares Físicos Ejecutados con Éxito:**
    1. *Prueba Coxa 2:* Giro controlado de $+20^\circ$ ($1504\,\mu\text{s} \to 1724\,\mu\text{s} \to 1504\,\mu\text{s}$).
    2. *Prueba de Extensión Amplia Pata 6:* Movimientos independientes y amplios de Fémur 6 ($1700\,\mu\text{s} \to 1200\,\mu\text{s}$) y Tibia 6 ($1300\,\mu\text{s} \to 1850\,\mu\text{s}$) registrando picos de corriente controlados ($0.37\text{ A} - 0.57\text{ A}$).
    3. *Simulación de Marcha en el Aire Pata 6:* 3 ciclos completos de caminata (Vuelo $\to$ Avance $\to$ Descenso $\to$ Propulsión) con monitoreo en tiempo real a 100 Hz del switch de contacto de pie en **GPIO 23 BCM**.
    4. *Retracción y Relajación de Pata 6:* Repliegue hacia el chasis y desenergización de PWM (`target = 0`) para evitar esfuerzos y dejarla libre.
    5. *Simulación de Marcha en el Aire Pata 1:* 3 ciclos completos de caminata en Pata 1 (CH0, CH1, CH2) con supervisión en tiempo real a 100 Hz del switch de contacto de pie en **GPIO 17 BCM** y retorno a neutral.
    6. *Extensión Global y Desenergización:* Prueba de rigidez en postura estrella (18 canales a $1504\,\mu\text{s}$) y posterior corte de pulsos (`target = 0`) para dejar patas libres sin consumo ($0.00\text{ A}$).
    7. *Reemplazo de Servomotor en Fémur 3 (Canal 7):* Detección de pérdida de retención por piñones de nylon blanco desgastados/robados; sustitución por servo metálico y extensión dedicada a $1504\,\mu\text{s}$ para validación de rigidez.
    8. *Marcha Suavizada Anti-Temblor en Pata 3:* Validación experimental de rampa trapezoidal por hardware (`accel = 6`, `speed = 22-24`) y ajuste del tornillo del horn, erradicando la resonancia en la fase de vuelo aéreo en 3 ciclos completos.
    9. *Marcha Bioinspirada con Plegado de Rodilla (Tipo Insecto):* Implementación conjunta de rampa ultra-suave (`accel = 3`, `speed = 14`) y retracción activa de tibia a $1240\,\mu\text{s}$ en vuelo, reduciendo el momento de inercia un $75\%$ y suprimiendo el temblor de parada en el aire.
  - **Fundamentación Cinemática de la Marcha HOME 3 (Postura Semi-extendida):**
    - Identificada y documentada la transición de HOME 2 (agachada, brazo de momento de $153\text{ mm}$, torque de $1.89\text{ N}\cdot\text{m}$ sobrecargando los MG996R) a HOME 3 (semi-extendida, brazo reducido a $36 - 37\text{ mm}$, torque pico en fémur aliviado a $0.46\text{ N}\cdot\text{m}$, reducción de $>75\%$ de esfuerzo).

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

---

## 📐 Estado de Ecuaciones y Modelos Matemáticos en Overleaf (`tesis_overleaf/`)

### 1. Ecuaciones ya integradas en Overleaf
- **Cinemática del Hexápodo Primario (integrado el 24/11/2026 desde informe técnico `d929673`):**
  - **Capítulo 3 (`capitulo3NEW1.tex`, Sec. 3.1.1):** Espacio articular $\mathcal{Q}$, configuración de base flotante $\mathcal{C} = SE(3)\times\mathcal{Q}$ (24 DoF), transformaciones homogéneas de cadena abierta, discriminante geométrico de IK, Jacobiano geométrico de posición, trabajo virtual ($\boldsymbol{\tau} = \mathbf{J}^\top\mathbf{f}_p$), número de condición $\kappa_2$, inversa amortiguada DLS y restricciones cinemáticas de contacto puntual en trípode.
  - **Capítulo 6 (`capitulo6NEW1.tex`, Sec. 6.1.5):** Parámetros reales del Xacro (`tab:parametros_xacro_primario`) con desplazamiento lateral de ensamble $b \approx \pm 0.7\text{ mm}$, FK/IK analítica cerrada, Jacobiano factorizado y determinante ($\det \mathbf{J} = -ALM\sin\delta$), familias singulares, comparativa Cero URDF ($\kappa_2 > 615$) vs. `HOME2` ($\kappa_2 \approx 4.06$), aclaración entre cota de simulación ($100\text{ N}\cdot\text{m}$) y límite físico MG996R ($0.98\text{ N}\cdot\text{m}$), volumen alcanzable ($16.23\text{ L}$) y mapeo a pulsos del Pololu Mini Maestro.
  - **Capítulo 7 (`capitulo7NEW1.tex`, Sec. 7.1.2.1):** Validación numérica frente a `RobotModel` ($1.6\times 10^{-16}\text{ m}$ en FK, $2.0\times 10^{-16}\text{ m/rad}$ en Jacobiano, convergencia $100\%$ de IK en 1500 puntos y rango 2 en singularidades).
  - *Nota de coherencia (HOME2 vs. HOME3):* El informe `d929673` analizó `HOME2` (resolviendo el condicionamiento cinemático respecto al Cero URDF), pero físicamente en campo el robot primario evolucionó a `HOME3` (Cap. 7 y Sec. 14 de `CONTEXTO_TESIS.md`) para reducir el brazo de palanca de $153\text{ mm}$ a $36\text{–}37\text{ mm}$ y evitar sobrecarga de torque en los MG996R.
- **Control en Cascada del Secundario (ya presente en Cap. 7):** Funciones de transferencia identificadas ($G_{21}, G_{22}, G_{10}, G_{20}$) y controladores continuos ($PI_{\text{current}}, PI_{\text{vel}}, PI_{\text{pos}}$).
- **Potencia del Primario (ya presente en Cap. 6):** Energía requerida ($43.56\text{ Wh}$) y capacidad mínima ($3924\text{ mAh}$).

### 2. Ecuaciones y modelos pendientes por añadir (Total: 21 + PnP)
1. **Subsistema Mecánico y Locomoción (4 pendientes):**
   - Cinemática directa e inversa instanciada del **Hexápodo Secundario** ($L_1=30\text{ mm}, L_2=60\text{ mm}, L_3=90\text{ mm}$).
   - Margen de Estabilidad Estática (ESM) en polígono de apoyo trípode (incluyendo efecto de pendiente del $12\%$).
   - Generador de trayectoria en fase de oscilación (*swing*: curva quíntica / cicloide / Bézier).
   - Cálculo de torque estático en peor caso ($\tau_{\text{femur, max}}$) justificando tanto el paso a **HOME3** en el Primario ($0.46\text{ N}\cdot\text{m}$ vs. $1.89\text{ N}\cdot\text{m}$ en HOME2) como la selección del N20 ($0.0765\text{ N}\cdot\text{m}$) en el Secundario.
2. **Subsistema de Control en Cascada — Secundario (5 pendientes en Cap. 3 y Cap. 6):**
   - Modelo electromecánico canónico del motor DC con reductora.
   - Arquitectura acoplada del triple lazo en cascada.
   - Ecuación en diferencias del controlador PI discreto con *anti-windup* ($1\text{ kHz}, 100\text{ Hz}, 50\text{ Hz}$).
   - Conversión de pulsos de encoder magnético por periférico PCNT a ángulo y velocidad (cuadratura $\times 4$, reducción $1:300$).
   - Conversión de corriente por espejo `IPROPI` del puente H DRV8876.
3. **Subsistema de Sensado Ambiental y Señales — MiCS-5524 y MQ-9 (7 pendientes en Cap. 3, 6 y 7):**
   - Ley de potencias de quimisorción (Wolkenstein--Clifford: $R_s/R_0 = A \cdot C^{-B}$).
   - Ecuación del divisor de voltaje y despeje de $R_s$.
   - Inferencia analítica de concentración $C(\text{ppm})$ (con constantes empíricas en MQ-9 y formulación paramétrica en MiCS-5524).
   - Proporción ascendente $R_0/R_s$ e intensidad porcentual $I_{\text{gas}} = (1 - R_s/R_0)\times 100\%$.
   - Filtro digital de mediana móvil ($N=5$).
   - Filtro exponencial IIR (EMA, $\alpha = 0.20$).
   - Calibración dinámica *Zero-Gas Reference* ($R_0$) en aire limpio.
4. **Subsistema de Navegación, Percepción y Cooperación — Primario / UVC (3 pendientes + PnP):**
   - Ecuaciones de predicción, ganancia y actualización del Filtro de Kalman Extendido (EKF - `robot_localization`).
   - Modelo cinemático de odometría en el plano $(\dot{x}, \dot{y}, \dot{\theta})$.
   - Modelo *Pinhole* de proyección 3D (Orbbec Gemini 2 y cámara UVC monocular).
   - *(Adicional según alcance)* Formulación PnP-RANSAC de relocalización cooperativa 2D-to-3D (documentada en `CONTEXTO_TESIS.md` Sec. 13.2).
5. **Subsistema Eléctrico y Potencia (2 pendientes):**
   - Balance de potencia y autonomía del Hexápodo Secundario (18 N20 + 6 ESP32 + ESP32-S3 + cámara UVC + calefactor MiCS-5524).
   - Eficiencia y disipación térmica en reguladores Buck DC-DC y LDO.
