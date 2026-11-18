# Registro de Decisiones de Arquitectura e Ingeniería (ADR)
## Proyecto de Tesis Mecatrónica UTEC 2026

Este documento recopila las justificaciones técnicas, normativas y metodológicas de cada decisión de diseño tomada en el proyecto. Sirve como fuente de consulta para la redacción de la memoria (metodología VDI 2225) y la defensa ante el jurado.

---

### Decisión 1: Arquitectura Cooperativa Heterogénea (A2) vs. Robot Único Masivo
- **Contexto:** La minería subterránea presenta zonas colapsadas y conductos de ventilación estrechos inaccesibles para robots pesados convencionales.
- **Alternativas evaluadas:**
  1. *Robot único multipropósito:* Elevado peso (>8 kg), consumo alto, incapacidad de penetrar en hendiduras estrechas.
  2. *Sistema Cooperativo Primario-Secundario (A2):* Hexápodo primario robusto actúa como nodo base/mapeador SLAM y hexápodo secundario de mínima envolvente actúa como explorador avanzado.
- **Justificación:** Se seleccionó A2 bajo el enfoque de **inspección sin ingreso (*no-entry*)** y normativa **D.S. N° 024-2016-EM**. Permite mantener la antena de comunicación y el procesamiento pesado (Raspberry Pi 5 + Orbbec Gemini 2) en zona segura mientras la unidad ligera (motores N20 + ESP32) ingresa en espacios confinados con riesgo de gas.

---

### Decisión 2: Unidad Central del Primario (Raspberry Pi 5 + Pololu Mini Maestro 18)
- **Contexto:** Se requiere coordinar 18 servomotores MG996R, procesar nubes de puntos RGB-D y ejecutar SLAM 3D.
- **Alternativas evaluadas:**
  1. *Raspberry Pi 5 controlando los servos directamente por GPIO/PWM software.*
  2. *Raspberry Pi 5 + Arduino Mega / PCA9685 por I2C.*
  3. *Raspberry Pi 5 + Pololu Mini Maestro 18 canales vía USB CDC.*
- **Justificación:** La alternativa 3 fue la ganadora en la matriz VDI 2225. El Pololu cuenta con microcontrolador interno dedicado que genera pulsos PWM por hardware con resolución de $0.25\,\mu\text{s}$, aceleración y límites de velocidad internos. Esto desacopla a la Raspberry Pi 5 del jitter de temporización en Linux, permitiéndole dedicar el 100% de sus 4 núcleos ARM Cortex-A76 a ROS 2 Jazzy, RTAB-Map y Nav2.

---

### Decisión 3: Cámara RGB-D Primaria (Orbbec Gemini 2 vs. Intel RealSense D435 vs. LIDAR 2D)
- **Contexto:** Mapeo 3D en túneles mineros no estructurados con iluminación irregular y polvo en suspensión.
- **Justificación:**
  - El LIDAR 2D solo entrega un plano horizontal y no detecta rocas sueltas o desniveles por encima o debajo del chasis.
  - La Orbbec Gemini 2 integra tecnología de luz estructurada activa con sensor de profundidad (0.15 a 10.0 m), FOV amplio ($91^\circ \times 66^\circ$) y una **IMU de 6 DoF integrada** en el mismo cuerpo. Esto permite fusión de odometría visual-inercial (VIO) con un único cable USB 3.0, garantizando el cierre de lazo en RTAB-Map sin deriva acumulativa.

---

### Decisión 4: Actuadores del Robot Secundario (Micromotores DC N20 1:300 vs. Micro Servos Analógicos)
- **Contexto:** La unidad secundaria debe tener una envolvente mínima y extremidades delgadas capaces de caminar en tuberías o grietas.
- **Justificación:**
  - Los micro servos tipo SG90 poseen piñonería plástica de baja durabilidad y no admiten control de par ni lectura continua de posición/velocidad por hardware.
  - Los micromotores N20 metálicos con reducción 1:300 ofrecen torque elevado ($\approx 3.2\text{ kg}\cdot\text{cm}$ a 12V), dimensiones microscópicas ($12 \times 10 \times 36\text{ mm}$) y encoders magnéticos de efecto Hall en cuadratura montados en el eje del motor antes de la caja reductora (resolución de pulsos multiplicada por 300x).

---

### Decisión 5: Electrónica Modular Distribuida en el Secundario (6x PCBs idénticas vs. Tarjeta Madre Central)
- **Contexto:** Cablear 18 motores N20 con sus respectivos encoders hacia una sola placa central exigiría un mazo de $>100$ cables pasando por las articulaciones, provocando rigidez y fallas por fatiga mecánica.
- **Justificación:**
  - Se diseñó una arquitectura distribuida: una PCB idéntica e intercambiable montada sobre cada pata.
  - Cada PCB contiene su propio ESP32-WROOM-32E y 3 puentes H DRV8876 con monitoreo de corriente (`IPROPI`).
  - Beneficios: Mantenimiento modular (si falla una pata, se reemplaza la tarjeta completa en 2 minutos), reducción del 80% en longitud de cableado y balance térmico descentralizado.

---

### Decisión 6: Control Articular en Cascada de 3 Lazos Anidados
- **Contexto:** El contacto con rocas y piedras en terreno accidentado produce impactos dinámicos que descalibran la posición y pueden quemar los devanados del motor si se traba la articulación.
- **Justificación:**
  1. **Lazo interno de corriente (1 kHz):** Limita la corriente a $1.1\text{ A}$ por hardware y absorbe sobrecargas en microsegundos, protegiendo mecánicamente la reductora N20.
  2. **Lazo intermedio de velocidad (100 Hz):** Suprime el efecto de fricción seca y variaciones de carga en la fase de apoyo (*stance phase*).
  3. **Lazo externo de posición (50 Hz):** Garantiza el seguimiento cinemático de la trayectoria del pie según el generador de marcha en trípode.

---

### Decisión 7: Procesamiento del Sensor de Gases MiCS-5524 (Filtro de Mediana vs. EMA)
- **Contexto:** El sensor semiconductor de óxido metálico ($\text{SnO}_2$) presenta ruido de alta frecuencia por convección térmica y pulsos espurios en el ADC.
- **Justificación:**
  - El filtro exponencial EMA ($\alpha=0.20$) suaviza la señal pero introduce un retardo de $\sim 1\text{ s}$, lo que a una velocidad de marcha de $8\text{ cm/s}$ desplazaría el mapa de gases en casi $8\text{ cm}$.
  - El **Filtro de Mediana con ventana móvil $N=5$** demostró en pruebas experimentales eliminar el 100% de los picos de ruido sin alterar la amplitud de cresta ($2.72\text{ V}$ frente a $2.80\text{ V}$) y con un retardo temporal casi nulo ($\approx 200\text{ ms}$).
  - *Estrategia adoptada:* Modo dual. Filtro de Mediana durante navegación continua del robot y EMA durante mediciones estáticas de alta precisión (*Stop-and-Measure*).

---

### Decisión 8: Enlace de Red Autónomo (SoftAP Wi-Fi + UDP Telemetría + TCP Video)
- **Contexto:** En una galería colapsada no existe infraestructura Wi-Fi ni routers intermedios disponibles.
- **Justificación:**
  - El ESP32-S3 actúa como punto de acceso autónomo (**SoftAP 2.4 GHz**) sin necesidad de router externo.
  - **Video por TCP (puerto 81):** La fragmentación de tramas JPEG sobre UDP puro saturaba la cola DMA de transmisión del chip Wi-Fi ante pérdidas de paquetes. TCP con HTTP multipart garantiza integridad frame a frame sin congelamientos.
  - **Gas por UDP (puerto 5005):** Como los paquetes de gas son ligeros (50 bytes a 20 Hz), UDP garantiza entrega de mínima latencia ($<5\text{ ms}$) sin bloquear el procesador ni esperar confirmaciones ACK.
  - **Standby Frame (Hot-Plug):** Si la cámara UVC no está conectada físicamente al arrancar, el servidor HTTP despacha un frame JPEG dummy de $16 \times 16\text{ px}$ a 2 Hz, manteniendo la sesión HTTP activa y permitiendo la reconexión instantánea en caliente sin reiniciar el microcontrolador.

---

### Decisión 9: Topología de Red Cooperativa: Modo Estación (STA) en Secundario hacia Hotspot del Primario (Raspberry Pi 5)
- **Contexto:** En la operación de campo en túneles mineros colapsados, la Raspberry Pi 5 del robot primario actúa como la estación base y pasarela central de procesamiento. Mantener al secundario como SoftAP obligaba al primario a desconectarse de su propia red o requería doble interfaz en el primario.
- **Alternativas evaluadas:**
  1. *Secundario como Access Point (SoftAP) y Primario como cliente:* Inviable si el primario necesita coordinar múltiples robots o dar acceso al operador.
  2. *Router externo intermedio:* Agrega peso, batería adicional y punto único de fallo en la mina.
  3. *Primario como Hotspot (`aleskypi-5`, IP `10.42.0.1`) y Secundario como Estación (STA, IP `10.42.0.53`):* Ganadora unánime.
- **Justificación:** Centraliza la red en el robot con mayor potencia de cómputo y batería (Li-ion 3S 4500 mAh). El ESP32-S3 se asocia automáticamente al arrancar (tiempo de conexión 6–10 s con bucle de reconexión infinito) y emite los datagramas UDP directo a `10.42.0.1:5005`, permitiendo además que la laptop del operador se conecte a la misma red mediante un adaptador USB dedicado (TP-Link TL-WN725N) con latencia de 6 ms, sin interferir con la conexión a internet institucional.

---

### Decisión 10: Localización Cooperativa del Secundario: Relocalización Visual Monocular 2D-to-3D (PnP-RANSAC) vs. SLAM Monocular Independiente
- **Contexto:** El robot secundario debe ubicarse dentro de la mina para georreferenciar las concentraciones de gases tóxicos ($CO$, $CO_2$) en el mapa 3D, pero sus restricciones de peso ($<650\text{ g}$) y volumen le impiden cargar una cámara de profundidad RGB-D o LIDAR.
- **Alternativas evaluadas:**
  1. *SLAM Monocular a bordo del secundario (ej. ORB-SLAM3 monocular):* Alta ambigüedad de escala métrica (*scale drift*), consumo computacional prohibitivo para microcontroladores y pérdida de trayectoria en giros cerrados.
  2. *Marcadores fiduciales pasivos (AprilTag / ArUco en el secundario):* Requieren que el robot primario mantenga al secundario permanentemente dentro de su campo visual directo (línea de vista). Si el explorador penetra una hendidura colapsada o dobla una esquina, se pierde la localización.
  3. *Relocalización Visual Monocular sobre Mapa Previo 3D (2D-to-3D PnP-RANSAC):* Seleccionada.
- **Justificación:** 
  - El robot primario mapea previamente el túnel en 3D métrico con la Orbbec Gemini 2 y almacena los Keyframes con descriptores ORB y coordenadas métricas $(X,Y,Z)$ en RTAB-Map.
  - Cuando el secundario penetra la zona con su cámara monocular UVC ligera ($<15\text{ g}$), la Raspberry Pi 5 procesa sus fotogramas 2D, encuentra correspondencias con la base de datos visual previa mediante *Bag of Words* (BoW) y resuelve la pose 6-DoF mediante **PnP con RANSAC** utilizando la matriz intrínseca $\mathbf{K}$ de la cámara.
  - Esto proporciona escala métrica absoluta sin deriva, no requiere sensores pesados en el explorador y permite mapear con precisión tridimensional la dispersión de gases contaminantes en la mina.

