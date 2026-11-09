# Base de Conocimiento y Contexto del Proyecto de Tesis

> **Documento de Contexto Compartido para Agentes y Sesiones de Chat**  
> **Ubicación:** Raíz del proyecto `RedaccionTesis`  
> **Fecha de actualización:** Octubre 2026 (Semana 9 de ejecución)

---

## 1. Identificación del Proyecto Académico

- **Institución:** Universidad de Ingeniería y Tecnología (UTEC)
- **Carrera Profesional:** Ingeniería Mecatrónica
- **Título de la Tesis:** *DESARROLLO DE UN SISTEMA ROBÓTICO COOPERATIVO INSPIRADO EN INSECTOS PARA EL MONITOREO DE TERRENOS ACCIDENTADOS*
- **Modalidad:** Proyecto Final de Carrera (Tesis de Pregrado)
- **Autores:**
  - Aleskyjubinsl Alcarraz Jaime
  - Flavio Alarcon Muñoz
  - Alfredo Francisco Erazo Yalopalin
- **Asesor:** Dante Inga Narváez
- **Año / Ubicación:** Lima - Perú, 2026

---

## 2. Problemática, Justificación y Marco Normativo

### 2.1 Problemática
En entornos subterráneos y espacios confinados (galerías mineras subterráneas, estructuras colapsadas por sismos, incendios o derrumbes), el personal técnico se expone a atmósferas potencialmente letales debido a:
- Deficiencia de ventilación y falta de oxígeno ($O_2$).
- Acumulación de gases nocivos provenientes de voladuras y motores diésel de maquinaria pesada (*jumbos*, *scooptrams*, camiones): Monóxido de Carbono ($CO$), Dióxido de Carbono ($CO_2$), Óxidos de Nitrógeno ($NO$, $NO_2$, $NO_x$) y Sulfuro de Hidrógeno ($H_2S$).
- Terrenos irregulares, inestables y con pendientes de hasta el 12 %, con secciones transversales reducidas.
- Prácticas actuales de inspección humana presencial con detectores portátiles, que exponen vidas humanas a intoxicaciones agudas y accidentes fatales (ej. accidente en mina Yanaquihua, Arequipa).

### 2.2 Justificación Técnica y Social
- **Concepto "No-Entry":** Evitar el ingreso de seres humanos a zonas ciegas no ventiladas antes de una verificación certera y segura.
- **Enfoque Cooperativo Multirrobot:** Combinar una plataforma principal de procesamiento/mapeo con un agente explorador ligero de envolvente mínima capaz de penetrar en ramales y oquedades estrechas inaccesibles para robots convencionales o personas.
- **Compromiso Ético y ODS:** Alineado con la Ley N° 29783 (Seguridad y Salud en el Trabajo), el ODS 3 (Salud y Bienestar) y democratización tecnológica para la pequeña minería mediante prototipado de bajo costo.

### 2.3 Marco Normativo y Estándares
- **D.S. N° 024-2016-EM (MINEM):** Reglamento de Seguridad y Salud Ocupacional en Minería (Art. 30, 246, 250, 254; límites del Anexo 15).
- **Directiva Europea 2017/164:** Valores límite indicativos de exposición profesional (IOELVs).
- **Supervisión OSINERGMIN / SUNAFIL:** Criterios de trazabilidad, registro auditable con sello de tiempo y posición espacial.
- **IEC 60529:** Estanqueidad requerida objetivo de IP65 contra polvo y humedad.

---

## 3. Metodología de Desarrollo Mecatrónico

1. **VDI 2206 (Modelo en V):**
   - Macro-ciclo que rige el proyecto: Nivel de Sistema (clarificación de requerimientos) $\to$ Descomposición en Subsistemas (mecánico, electrónico, software) $\to$ Base (diseño de detalle, simulación, prototipado) $\to$ Fase ascendente de integración, verificación progresiva y validación funcional en laboratorio.
2. **ISO/IEC/IEEE 29148:**
   - Estandarización de requerimientos cuantitativos, unívocos y verificables con márgenes de tolerancia numéricos.
3. **VDI 2225 Blatt 3 (Evaluación Multicriterio Técnico-Económica):**
   - Matriz ponderada de valor de uso ($g \in [1, 5]$, calificación $p \in [0, 4]$, índice adimensional $X_i \le 1.0$).
   - **Selección de Arquitectura Global:** Se evaluaron tres variantes:
     - A1: UGV único (Puntaje: 0.7875)
     - **A2: Configuración Cooperativa UGV + Explorador Terrestre Ligero (Puntaje: 0.7988) — SELECCIONADA**
     - A3: UGV + Explorador Ligero Aéreo/otro (Puntaje: 0.7245)

---

## 4. Requerimientos Numéricos del Sistema (ISO 29148)

| Parámetro | Valor Límite / Requerimiento | Justificación / Norma |
| :--- | :--- | :--- |
| **Ancho operativo en reposo** | $< 0.50\text{ m}$ | Maniobrabilidad en pasos peatonales mineros (norma exige mínimo $1.0\text{ m}$) |
| **Despeje vertical del suelo** | $\ge 15.0\text{ cm}$ | Franquear escombros y desniveles sin colisión de panza |
| **Distribución de masa de patas** | $< 45\text{ \%}$ de la masa total | Evitar desestabilización del centro de masa en la marcha |
| **Torque de motor secundario** | No exceder $\tau_{stall} = 0.0765\text{ N}\cdot\text{m}$ | Límite del motor DC N20 (12V, 1:300) para evitar bloqueo |
| **Tolerancia dimensional CAD/FDM**| $\pm 0.2\text{ mm}$ | Ajustes precisos en articulaciones y ejes |
| **Tiempo de iteración de piezas** | $< 24.0\text{ horas}$ | Velocidad de prototipado rápido en laboratorio |
| **Presupuesto de manufactura física**| $\le \text{S/. } 75.00\text{ PEN}$ | $< 15\text{ \%}$ del presupuesto asignado al proyecto |
| **Autonomía continua mínima** | $T_{op} \ge 1.0\text{ hora}$ ($FS = 1.25$) | Capacidad de ejecutar misiones completas desconectadas |

---

## 5. Diseño y Arquitectura de las Unidades Robóticas

El sistema está compuesto por dos unidades hexápodas complementarias con marcha en trípode (*tripod gait* con polígonos de estabilidad triangular simétricos):

### 5.1 Hexápodo Primario (Unidad Principal de Procesamiento y Cartografía)

- **Propósito:** Nodo seguro, cartografía 3D, navegación autónoma, supervisión y almacenamiento de bitácoras.
- **Base Mecánica:** Arquitectura open-source *Chipo* (*MakeYourPet/hexapod*), con adaptaciones de rigidización y ensamble en PLA.
- **Actuadores:** 18 servomotores metálicos de alto torque **MG996R** ($\approx 10\text{ kg}\cdot\text{cm}$ a 6V).
- **Extremidades Distales (Foot tip):** Cavidad articulada con un interruptor pulsador (*push button*) como final de carrera para contacto discreto, cubierto con funda elastomérica de goma.
- **Computador de a Bordo:** **Raspberry Pi 5 (8 GB RAM)**.
- **Controlador de Servos:** **Pololu Mini Maestro de 18 canales** (comunicación USB con la Raspberry Pi).
  > *Nota de diseño crítica:* Se reemplazó el combo original ESP32 + 2x PCA9685 debido a severo *jitter*, falta de torque e inestabilidad de pulsos PWM.
- **Sistema de Percepción y Mapeo:**
  - Cámara de profundidad **Orbbec Gemini 2** (USB 3.0, profundidad 0.15 a 10.0 m, FOV $91^\circ \times 66^\circ$, IMU de 6 DoF integrada).
  - IMU secundaria BMI160, sensor de distancia ToF VL53L5CX.
- **Sensores Ambientales:** Sensor electroquímico de gases **MQ-9** (CO y gases combustibles) acondicionado a través de un conversor ADC hacia la Raspberry Pi.
- **Sistema de Potencia:**
  - Batería LiPo / Li-ion **3S (11.1V nominal, 12.6V máx), 4500 mAh, 25C**.
  - Potencia continua: $34.85\text{ W}$, potencia pico: $85.55\text{ W}$.
  - Convertidor Buck DC-DC 1 (11.1V $\to$ 5.1V, 5A continuo, $\eta \ge 92\%$) para Raspberry Pi 5 y cámara Orbbec.
  - Convertidor Buck DC-DC 2 (11.1V $\to$ 6.0V, 10A continuo / 15A pico, $\eta \ge 90\%$) exclusivo para los servos MG996R.
- **Pila de Software (ROS 2 Humble / Jazzy):**
  - **Árbol TF:** `map` $\xrightarrow{RTAB-Map}$ `odom` $\xrightarrow{EKF}$ `base_link` $\xrightarrow{URDF}$ `camera_link`.
  - **Odometría:** `rgbd_odometry` + IMU fusionadas con Filtro de Kalman Extendido (`robot_localization`).
  - **SLAM 2D/3D:** `rtabmap_ros` con cierre de lazo (*loop closure*).
  - **Navegación:** `Nav2` (costmaps globales y locales, Behavior Trees, tópicos `/cmd_vel`).
  - **Locomoción:** Nodo cinemático generador de patrón trípode hacia Pololu Maestro.

---

### 5.2 Hexápodo Secundario (Unidad Exploradora de Envolvente Mínima)

- **Propósito:** Acceso a cavidades estrechas, grietas y ramales ciegos de alto riesgo.
- **Estructura y Chasis:**
  - **Chasis hexagonal** en PLA (infill 8% grid, 3 perímetros).
  - *Nota de diseño crítica:* Se migró de un chasis rectangular inicial a uno hexagonal para eliminar las interferencias y colisiones mecánicas interarticulares entre patas contiguas.
  - Cunas de soporte con doble apoyo mecánico para motores N20 (frontal y auxiliar posterior) y barrenos de 2.8 mm para autorroscado de pernos M3x18.
- **Cinemática Articular (3 DoF por pata):**
  - Relación paramétrica biomimética: Coxa ($1x = 30\text{ mm}$), Fémur ($2x = 60\text{ mm}$), Tibia ($3x = 90\text{ mm}$).
  - Relación Fémur:Tibia de 4:6 (2:3), evaluada como óptima para compacidad y elevación.
- **Actuadores:** 18 micromotores **DC N20 con reductora 1:300 (12V, 300 RPM)** con encoders de cuadratura magnéticos integrados.
- **Acople:** Cubo intermedio en PLA con tolerancia de interferencia de $0.1\text{ mm}$ respecto al eje tipo "D" de 3 mm.
- **Electrónica Modular Distribuida:**
  - **1 placa PCB a medida por cada pata (total: 6 placas modulares idénticas e independientes):**
    - **Microcontrolador:** **ESP32-WROOM-32E (16 MB Flash)** por pata.
    - **Puente H:** 3x **DRV8876** (HTSSOP-16 con *thermal pad* soldado a plano de tierra; límite por hardware a 1.1A; pin `IPROPI` a entradas analógicas ADC; señal `nFAULT` unificada a `IO4`).
    - **Interfaz de programación:** Puerto USB-C con puente USB-UART **CP2102N** (QFN-28) y circuito de auto-flasheo (transistores a EN/IO0).
    - **Alimentación:** LDO AMS1117-3.3 (lógica) y bornera de potencia de 12V aislada para los motores (`V_MOT`).
    - **Conectores:** 3x conectores JST-SH de 6 pines para encoders y motor.
- **Control Articular en Cascada (3 Lazos Anidados):**
  1. **Lazo interno de corriente (1 kHz PWM):**
     - Muestreo ADC DMA continuo a $200\text{ kS/s}$ en bloques de 200 muestras ($1\text{ ms}$).
     - Consumido a $\approx 100\text{ Hz}$.
  2. **Lazo intermedio de velocidad:** Actualización a $100\text{ Hz}$ sobre ventana de $50\text{ ms}$.
  3. **Lazo externo de posición:** Actualización a $50\text{ Hz}$ ($20\text{ ms}$) empleando el periférico por hardware **PCNT** (*Pulse Counter*) del ESP32 sin carga para el CPU.
  - **Telemetría:** Salida UART/USB a $460800\text{ baudios}$ a $100\text{ Hz}$ para sintonización en tiempo real.

---

## 6. Resultados Preliminares y Modelado Dinámico (Al Cierre de Semana 9)

### 6.1 Identificación de Plantas Experimentales (Motor N20)

| Lazo | Función de Transferencia Seleccionada | Ajuste (\%) | Criterio de Selección |
| :--- | :--- | :--- | :--- |
| **Corriente** | $G_{22}(s) = \frac{0.001184s^2 + 1.441s + 2.325}{s^2 + 904.4s + 3996}$ | **86.5 %** | Superior al modelo alternativo $G_{21}$ (71.1 %). |
| **Velocidad** | $G_{10}(s) = \frac{998.5}{s + 1.545}$ | **97.5 %** | Primer orden; casi idéntico ajuste que segundo orden (97.9 %) pero con drástica reducción de operaciones en microcontrolador. |
| **Posición** | $G_{10}(s)$ (Primer orden) | **99.1 %** | Óptimo para implementación digital en ESP32 frente al modelo de segundo orden (100 %). |

### 6.2 Controladores PI Sintonizados y Parámetros Dinámicos

| Controlador | Ecuación $PI(s)$ | $t_r$ (subida) | $t_s$ (asentamiento) | $M_p$ (sobreimpulso) | $e_{ss}$ (error estacionario) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Corriente / Duty Cycle** | $PI_{current}(s) = \frac{8.832s + 80090}{s}$ | $0.0181\text{ s}$ | $0.0671\text{ s}$ | **0 %** | $1.38\text{ \%}$ |
| **Velocidad / Corriente** | $PI_{vel}(s) = \frac{0.0284s + 0.01392}{s}$ | $0.0630\text{ s}$ | — | **0 %** | $2.79\text{ \%}$ |
| **Posición / Velocidad** | $PI_{pos}(s) = \frac{6.166s + 3192}{s}$ | $0.0170\text{ s}$ | $0.0998\text{ s}$ | $13.53\text{ \%}$ | $0.40\text{ \%}$ |

- **Desempeño en Pruebas Físicas:**
  - El triple lazo en cascada demostró alta estabilidad en lazo cerrado sobre los motores N20 físicos.
  - El lazo de corriente modula con picos de PWM de hasta $\approx 40\text{ \%}$.
  - El lazo de posición absorbe el ruido de cuantificación de los encoders y tolerancias mecánicas de la reductora, garantizando fidelidad postural sin sobrecalentamiento.

---

## 7. Plan de Trabajo, Cronograma (16 Semanas) y Ruta Crítica

### 7.1 Estado de las EDT (Estructura de Desglose de Trabajo)

- **EDT 1: Planificación, marco regulatorio y requisitos (S1-S3):** ✅ **Ejecutado (100 %)**
- **EDT 2: Diseño tecnológico y simulación de subsistemas (S4-S6):** ✅ **Ejecutado (100 %)**
- **EDT 3: Manufactura preliminar, prototipado y sintonización de bajo nivel (S7-S9):** ✅ **Ejecutado (100 %)**
- **EDT 4: Pruebas de locomoción, ensamble integral y control (S9-S11):** 🟡 **En curso / Próximo hito**
  - S9-S10: Pruebas dinámicas de locomoción del primario con Pololu y ensamble completo del secundario sobre chasis hexagonal.
  - S10-S11: Despliegue de firmware en las 6 placas ESP32 y sintonización en contacto con terreno.
- **EDT 5: Sensado ambiental, integración cooperativa y pruebas de laboratorio (S11-S14):** ⏳ **Programado**
  - S11-S12: Conexión y calibración de cámara de gases del sensor MQ-9 vía ADC.
  - S12-S13: Enlace Wi-Fi / UDP, odometría visual-inercial y RTAB-Map SLAM en ROS 2.
- **EDT 6: Consolidación de resultados, memoria final y sustentación (S14-S16):** ⏳ **Programado**
  - S14-S15: Campaña experimental completa de exploración en laboratorio y redacción de memoria final.
  - S16: Sustentación y defensa oral formal de la tesis.

### 7.2 Diagrama de la Ruta Crítica
$$\text{Ensamble (S9–S10)} \longrightarrow \text{Control (S10–S11)} \longrightarrow \text{Sensado MQ-9 (S11–S12)}$$
$$\downarrow$$
$$\text{Sustentación (S16)} \longleftarrow \text{Validación (S14–S15)} \longleftarrow \text{Integración SLAM/Wi-Fi (S12–S13)}$$

### 7.3 Estrategias de Mitigación de Riesgos
1. **Ejecución en paralelo en S9:** Concluir pruebas de locomoción del primario en paralelo al ensamble del secundario.
2. **Modularidad 100 % de la PCB del secundario:** Al tener 6 placas idénticas (una por pata), cualquier daño en un DRV8876 o ESP32 se repara de inmediato sustituyendo la placa sin paralizar las pruebas globales.
3. **Holgura en Semana 15:** Buffer temporal para absorber desvíos de calibración, blindando la Semana 16 para la sustentación.

---

## 8. Bitácora de Validación Experimental de Motores N20 y DRV8876 (Semana 9)

### 8.1 Asignación de Pines Validada en Prototipo Físico (ESP32 DevKit V1)
| Articulación | Motor N20 | Señales PWM (LEDC) | Corriente (ADC1) | Encoders (Cuadratura) |
| :--- | :--- | :--- | :--- | :--- |
| **Coxa** | Motor 1 | IN1: **GPIO 21 (D21)**<br>IN2: **GPIO 5 (D5)** *(Migrado de D19)* | CS: **GPIO 36 (VP)** | C1: **GPIO 32 (D32)**<br>C2: **GPIO 33 (D33)** |
| **Fémur** | Motor 2 | IN1: **GPIO 18 (D18)**<br>IN2: **GPIO 17 (D17)** | CS: **GPIO 39 (VN)** | C1: **GPIO 25 (D25)**<br>C2: **GPIO 13 (D13)** *(Migrado de D26)* |
| **Tibia** | Motor 3 | IN1: **GPIO 16 (D16)**<br>IN2: **GPIO 4 (D4)** | CS: **GPIO 34 (D34)** | C1: **GPIO 27 (D27)**<br>C2: **GPIO 14 (D14)** |

### 8.2 Lecciones y Errores Críticos Resueltos en Laboratorio
- **Falla en D19:** El pin GPIO 19 del ESP32 no suministraba nivel alto hacia el DRV8876. Se reasignó a **D5**, logrando conmutación de puente H simétrica y freno activo.
- **Diafonía por Encoders en Paralelo (D25 y D26):** Los jumpers paralelos provocaban acoplamiento capacitivo entre las señales de alta frecuencia de la reductora 1:300, eliminando el desfase de 90° e impidiendo distinguir el sentido de giro. Se resolvió separando físicamente el canal B hacia **D13**, restableciendo la lectura bidireccional x4 perfecta.
- **Diferencia entre DRV8876 Verde y Rojo (`DRV887*` MJKDZ):**
  - La placa verde integra MOSFET P de protección contra inversión de polaridad en VM; la roja carece de él.
  - La serigrafía de salidas de potencia está invertida entre ambas placas: en la verde `OUT1` es el pin 3 y `OUT2` el pin 4; en la roja `OUT2` es el pin 3 y `OUT1` el pin 4.
- **Herramientas de automatización integradas:** Se configuró `arduino-cli` en la raíz para compilación y carga automática por terminal en `COM11`, junto con scripts Python (`pyserial`) e interfaz visual web (`visor_encoders.html`) vía WebSerial API.

---

## 9. Bitácora de Validación Experimental del Sensor de Gases MiCS-5524 y Filtrado Digital (Semana 9)

### 9.1 Configuración de Hardware y Asignación de Pines (ESP32-S3 N16R8)
Para mitigar el consumo excesivo de corriente y masa de los sensores cerámicos tradicionales (MQ-9), se validó el microsensor MEMS semiconductor **MiCS-5524** (SGX Sensortech) montado sobre placa de desarrollo **ESP32-S3-DevKitC-1** (Módulo Sparkle IoT XH-S3E, 16 MB Flash, 8 MB Octal PSRAM):

| Señal del Sensor | Pin Conectado | Configuración / Justificación Eléctrica |
| :--- | :--- | :--- |
| **VCC** | **Pin 5V** (DevKit V1 externo) | Suministro de 5.0 V estables para el micro-calefactor MEMS ($\sim 32\text{ mA}$, $\sim 160\text{ mW}$). |
| **GND** | **GND común** (Puente físico) | **CRÍTICO:** Tierra compartida obligatoria entre la fuente de 5V y el ESP32-S3 para cerrar el lazo del ADC. |
| **OUT / A0** | **GPIO 4 (ADC1_CH3)** | Entrada analógica con atenuación de 11 dB ($0 - 3.14\text{ V}$ fondo de escala). Inmune a cortes por Wi-Fi. |
| **EN (Enable)** | **DESCONECTADO** o **GPIO 5** | Pin **Active-LOW** (resistencia pull-down interna mantiene el calefactor encendido al dejarlo al aire). |

### 9.2 Hallazgos Experimentales y Solución de Problemas
1. **Lógica Active-LOW del Pin `EN`:**
   - La placa breakout integra un transistor inversor con resistencia pull-down.
   - Poner `EN = HIGH` (o a 5V/3.3V) fuerza el apagado del calefactor.
   - Poner `EN = LOW` o dejarlo desconectado (al aire) activa el calefactor permanentemente, alcanzando $\sim 300^\circ\text{C}$ de catálisis en la membrana de $\text{SnO}_2$ (cápsula templada al tacto).
2. **Falla por Falta de Tierra Común (GND Flotante):**
   - Síntoma: Señal analógica saturada en el límite digital del ADC ($3.142\text{ V}$) con ruido impulsivo masivo hacia valles de $2.5\text{V}$, sin presencia de analito.
   - Diagnóstico: Entrada analógica de alta impedancia actuando como antena de ruido electrostático al no existir referencia común entre el ESP32 de potencia y el ESP32-S3 de procesamiento.
   - Solución: Se colocó el jumper de tierra común entre ambas placas, estabilizando de inmediato la línea base en aire limpio a $V_{\text{clean}} \approx 0.5\text{V} - 0.6\text{V}$.
3. **Respuesta Transitoria a Impulso y Exposición Prolongada:**
   - En aire limpio: $V_{\text{clean}} \approx 0.55\text{ V}$, $R_s > 100\text{ k}\Omega$, Ratio $R_s/R_0 \approx 1.000$.
   - Ante vapor de etanol: El voltaje se eleva a $2.5\text{V} - 2.8\text{V}$ y $R_s$ cae a $\approx 550\,\Omega$ ($Ratio \approx 0.055$, detección al 100%).
4. **Validación Comparativa de Filtros Digitales y Telemetría Wi-Fi Inalámbrica:**
   - **Enlace Wi-Fi SoftAP Autónomo (Arquitectura Primario-Secundario):**
     - El ESP32-S3 actúa como SoftAP (`ESP32-GasSensor`, IP `192.168.4.1`) exponiendo endpoints JSON `/data` y `/calibrate` a 10–12 Hz.
     - Esta arquitectura inalámbrica desacoplada valida experimentalmente la recepción continua de telemetría hacia la **Raspberry Pi 5** (Unidad Central del hexápodo primario) o PC de supervisión sin cables.
   - **Señal Cruda (*Raw*):** Ruidosa, con oscilaciones continuas por conmutación y turbulencia térmica ambiental.
   - **Filtro de Mediana ($N=5$):** Elimina ruidos atípicos y picos espurios preservando el 97% de la amplitud de pico con un retardo insignificante ($\approx 200\text{ ms} \equiv < 2\text{ cm}$ de error espacial a $8\text{ cm/s}$). **Óptimo para mapeo continuo en marcha.**
   - **Filtro Exponencial EMA ($\alpha=0.20$):** Atenúa picos transitorios rápidos (reduce pico de 2.8V a 2.2V) con un retardo de $\sim 1\text{ s}$. **Óptimo para régimen *Stop-and-Measure* (robot estático durante la lectura).**
5. **Fundamentación Teórica del Modelo de Sensado y Escala Ascendente:**
   - **Proporción de Gas Ascendente ($\mathbf{R_0 / R_s}$):** Físicamente, el óxido de estaño ($\text{SnO}_2$) reduce su resistencia ante gases reductores. Para la interfaz del operador y telemetría de monitoreo, se estableció la proporción ascendente $\frac{R_0}{R_s}$ (arranca en $1.000$ en aire limpio y asciende a $>1.5 - 10.0$ ante presencia de gas) y el porcentaje de intensidad $I_{gas} = (1 - R_s/R_0) \times 100\%$.
   - **Cadena de Transducción en 3 Etapas:**
     1. Quimisorción y Ley de Potencias de Wolkenstein-Clifford: $\frac{R_s}{R_0} = A \cdot C^{-B}$.
     2. Circuito divisor de tensión: $V_{out} = V_{CC} \cdot \frac{R_L}{R_s + R_L} \implies R_s = R_L \left(\frac{V_{CC} - V_{out}}{V_{out}}\right)$.
     3. Inferencia de concentración en ppm: $C(\text{ppm}) = \left[ \frac{R_L}{A \cdot R_0} \left( \frac{V_{CC} - V_{out}}{V_{out}} \right) \right]^{-\frac{1}{B}}$.
   - **Respaldo Académico para la Calibración de $R_0$ en Aire Limpio:**
     - *SGX Sensortech (Datasheet DS-0098 / AAN-004):* Dispersión de fabricación en $R_0$ de $100\text{ k}\Omega$ a $1500\text{ k}\Omega$ (un orden de magnitud), exigiendo calibración de línea base en campo.
     - *Bârsan & Weimar (2001, Journal of Electroceramics):* Demuestran que el único invariante físico frente a variaciones granulométricas de la película es el ratio normalizado $R_s/R_0$.
     - *Burgués & Marco (2018, Sensors and Actuators B):* Justifican que en robótica móvil de exploración la calibración diferencial al inicio de la misión en zona ventilada (*zero-gas reference*) elimina el error sistemático por temperatura y tolerancias.
   - **Ensayos con Analitos Reales:** Validación comprobada ante vapores de Etanol y Monóxido de Carbono ($\text{CO}$) por combustión incompleta (ascua/brasa de fósforo en micro-cámara controlada con ventilación cruzada).
6. **Condición de Saturación Práctica:**
   - Saturación química: Por encima de $500\text{ ppm}$ en etanol y $1000\text{ ppm}$ en $\text{CO}$ según datasheet SGX DS-0098.
   - Saturación eléctrica: Con $V_{CC}=5\text{V}$ y $R_L=820\,\Omega$, cuando $R_s \le 485\,\Omega$, $V_{OUT} \ge 3.14\text{ V}$, alcanzando el fondo de escala del ADC del ESP32-S3.
7. **Ecosistema de Software y Documentación:**
   - Firmware dual (Wi-Fi SoftAP + Serial JSON) en `pruebas_sensor_gas/firmware_mics5524/firmware_mics5524.ino`.
   - Visor OpenCV en Python (Serial y Wi-Fi): [`visor_gas_python.py`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas_sensor_gas/visor_gas_python.py).
   - Lanzadores ejecutables: [`iniciar_visor_gas_serial.bat`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas_sensor_gas/iniciar_visor_gas_serial.bat) e [`iniciar_visor_gas_wifi.bat`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas_sensor_gas/iniciar_visor_gas_wifi.bat).
   - Interfaz web interactiva con WebSerial API: `pruebas_sensor_gas/visor_gas_mics5524.html`.
   - Procedimiento de ensayo de saturación por microinyección volumétrica registrado en Notion (`Universidad / 2026-2 / Tesis 2 / Avances / Sensor de gases`).

---

## 10. Bitácora de Validación Experimental del Subsistema de Visión UVC (ESP32-S3 + Cámara Mini USB Type-C)

### 10.1 Requerimientos Eléctricos y Modo Host USB (VBUS 5V)
Para dotar al hexápodo secundario de inspección visual en galerías mineras estrechas, se integró una cámara mini USB Type-C (sensor CMOS 1 MP, compresión de hardware MJPEG integrada) controlada directamente por el ESP32-S3 a través de su periférico Host USB nativo:
- **Alimentación Forzada de VBUS:** El microcontrolador ESP32-S3 DevKitC cuenta con un diodo Schottky de aislamiento que impide energizar el conector USB hacia afuera. La cámara requiere alimentación externa de 5.0 V inyectada forzosamente a su línea VBUS para energizar el procesador de compresión DSP y sensor óptico.
- **Disipación Térmica:** La micro-cámara concentra $\sim 0.75\text{ W}$ en un área reducida ($2.5\text{ cm}^2$), estabilizándose en régimen estacionario entre $50^\circ\text{C}$ y $60^\circ\text{C}$ (comportamiento térmico admisible para silicio DSP sin disipador pasivo).

### 10.2 Comparativa Experimental: Transmisión Serial vs Wi-Fi SoftAP
1. **Transmisión Serial (UART0 a 1.5 MBaud):**
   - **Protocolo de Trama Binaria:** Encabezado de 16 bytes con sincronismo `0xFFAA55FF`, longitud, resolución y CRC.
   - **Rendimiento:** **8.7 FPS estables a $480 \times 320$ MJPEG** ($\approx 14.9\text{ KB/frame}$, ancho de banda $\approx 130\text{ KB/s}$).
   - **Lección Aprendida (Desacoplamiento de Tareas):** En la versión preliminar V1, el envío bloqueante por UART dentro del callback USB congelaba las transferencias URB. Se desacopló en la V2 mediante doble buffer en Octal PSRAM (`MALLOC_CAP_SPIRAM`) y descarte no bloqueante de cuadros.
2. **Transmisión Inalámbrica Wi-Fi (Modo SoftAP 2.4 GHz):**
   - **Configuración de Red:** SoftAP $802.11\text{ b/g/n}$ (SSID `ESP32S3-CAM`, IP `192.168.4.1`).
   - **Protocolo:** Servidor HTTP en puerto 80 con endpoint MJPEG multipart `/stream` (`multipart/x-mixed-replace;boundary=frame`).
   - **Rendimiento:** Fluidez continua ($15\text{ FPS}$ a $480 \times 320$) y ancho de banda holgado ($> 1.5\text{ MB/s}$ frente a $\approx 0.25\text{ MB/s}$ requeridos), con latencia promedio de $\approx 1.0\text{ s}$ por buffering TCP en el cliente receptor, óptima para monitoreo de seguridad.

---

## 11. Bitácora de Validación Experimental del Subsistema Integrado: Cámara UVC + Sensor de Gases MiCS-5524 Simultáneos (ESP32-S3 Wi-Fi)

Esta sección consolida la operación concurrente en tiempo real de los subsistemas visual y ambiental sobre un único procesador ESP32-S3 (N16R8):

### 11.1 Arquitectura Concurrente Multihilo y Asignación por Núcleos (FreeRTOS)
Para garantizar cero interferencias entre la adquisición de datos de seguridad y la compresión/transmisión de video, se implementó una estricta segregación por núcleos de hardware:
- **Núcleo 0 (Core 0 - Control Ambiental y Servicios de Red):**
  - Muestreo analógico del MiCS-5524 a 20 Hz en **GPIO 4** (`ADC1_CH3`, completamente compatible e independiente del transceptor Wi-Fi).
  - Filtrado digital dual: Mediana ($N=5$) para eliminación de espurios y filtro exponencial EMA ($\alpha=0.20$) para estabilidad de línea base.
  - Pila TCP/IP LwIP y servidor HTTP multipart multiconexión en puerto 80 (`/stream`, `/data`, `/gas`, `/calibrate`, `/`).
- **Núcleo 1 (Core 1 - Percepción Visual y Host USB UVC):**
  - Driver UVC Host nativo conectado a pines USB D+/D-.
  - Desempaquetado MJPEG continuo en Octal PSRAM de 8 MB con buffer de cuadros de 512 KB (`MALLOC_CAP_SPIRAM`).
  - Tarea de streaming a 15 FPS en resolución $480 \times 320$.

### 11.2 Mecanismo de Tolerancia a Desconexión en Caliente (*Hot-Plug / Hot-Unplug Robustness*)
1. **Problema Detectado en Pruebas Físicas:**
   - Si la cámara no estaba conectada al energizar el sistema o si se desconectaba durante la marcha, el manejador HTTP entraba en espera pasiva sin despachar bytes al socket TCP.
   - El cliente (Python/Navegador) sufría *timeout* a los 3.5 s, cerraba el socket en su extremo y dejaba el semáforo `s_stream_client` del ESP32 bloqueado permanentemente (`503 Service Unavailable`).
2. **Solución Implementada: *Standby Frame* Dinámico:**
   - Se diseñó un cuadro JPEG estándar de reserva (standby frame de 16x16 px, 631 bytes) transmitido a 2 Hz cuando la cámara no está conectada o está inicializando.
   - **Beneficios Comprobados:**
     - El cliente recibe confirmación inmediata `HTTP 200 OK` sin desbordar el socket.
     - Si el visor se cierra, `httpd_resp_send_chunk` detecta el cierre del socket al instante y libera el semáforo `s_stream_client`.
     - **El sensor de gases y su osciloscopio en tiempo real continúan operando al 100 % en el Núcleo 0 sin alteración.**
     - Apenas el usuario conecta la cámara física al puerto USB, el Núcleo 1 levanta la negociación UVC y el stream conmuta al video real sin requerir reinicio del ESP32 ni del software de monitoreo.

### 11.3 Ecosistema de Software y Carpeta Dedicada (`pruebas/integradas_camara_gas/`)
Todos los recursos desarrollados para esta etapa se encuentran centralizados en el espacio de trabajo:
- **Firmware C (ESP-IDF v5.4.4):** [`pruebas/integradas_camara_gas/firmware_camara_gas/main_v4_camara_gas.c`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/integradas_camara_gas/firmware_camara_gas/main_v4_camara_gas.c).
- **Visor Unificado OpenCV en Python:** [`pruebas/integradas_camara_gas/visor_integrado_python.py`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/integradas_camara_gas/visor_integrado_python.py):
  - Panel izquierdo (640x480): Video UVC en vivo a 15 FPS con telemetría superpuesta (resolución, framerate, KB/s, contador de tramas) y conmutación visual a recuadro de espera informativo si la cámara está desconectada.
  - Panel derecho (430 px): Barra de nivel de gas con código de alerta cromático (Verde <15%, Amarillo >15%, Naranja >40%, Rojo >70%), voltajes EMA/Mediana/Raw, resistencias $R_s$ y $R_0$, ratio adimensional $R_0/R_s$ y osciloscopio de voltaje dinámico de 120 muestras.
  - Funciones interactivas por teclado: Calibración remota de $R_0$ (`C`), captura fotográfica combinada (`S`) y exportación masiva de telemetría a formato CSV (`E`).
- **Lanzador de un Clic (.bat):** [`pruebas/integradas_camara_gas/iniciar_visor_integrado.bat`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/integradas_camara_gas/iniciar_visor_integrado.bat).

### 11.4 Despliegue en Hexápodo Primario (Raspberry Pi 5 - Ubuntu 22.04 LTS Headless) y Módulo Estandarizado (`pruebas_para_raspberry/`)
Para la operación autónoma dentro de la arquitectura cooperativa multirrobot, todos los entregables de enlace se encuentran organizados y versionados en `pruebas/integradas_camara_gas/pruebas_para_raspberry/`:
- **`V1_firmware_esp32_camara_gas.c`:** Firmware definitivo del ESP32-S3 (Secundario). Servidor TCP puerto 81 (`/stream`), emisor UDP de gas a 20 Hz en puerto 5005 y soporte Hot-Plug.
- **`V1_nodo_raspberry_headless.py`:** Nodo de supervisión y caja negra para Raspberry Pi 5 **sin monitor**.
  - Operación continua sin interfaz gráfica: elimina el consumo de GPU/X11 y corre nativamente sobre Ubuntu 22.04 LTS.
  - Registro auditable continuo en caja negra CSV (`registro_mision_hexapodo.csv`) a 5 Hz.
  - Clasificación de seguridad según D.S. N° 024-2016-EM (Aire limpio, Detección moderada, Alta toxicidad, Evacuación crítica).
  - Integración híbrida con **ROS 2 Humble**: publica automáticamente en los tópicos `/secondary_robot/camera/compressed` y `/secondary_robot/gas_telemetry` si `rclpy` está disponible, o funciona en modo autónomo si no se usa ROS.
  - Telemetría en tiempo real formateada en consola SSH mediante secuencias ANSI.
- **`ejecutar_en_raspberry.sh`:** Script ejecutable de lanzamiento para Linux en Raspberry Pi 5.
- **`V1_visor_laptop_con_pantalla.py` y `iniciar_visor_laptop.bat`:** Herramientas para estación de control en laptop con pantalla gráfica.

### 11.5 Segunda Versión Maestra: Control de Iluminación de Inspección por Hardware RMT (V2)
Para responder a los requerimientos de inspección visual en galerías y ductos mineros en penumbra absoluta, se desarrolló e integró la **Segunda Versión Maestra (V2)** del subsistema sensorial:

1. **Firmware Maestro V2 (`V2_firmware_esp32_camara_gas_luz.c` / `main_v8_camara_gas_luz.c`):**
   - **Actuador:** LED RGB inteligente direccionable WS2812/SK6812 integrado en la tarjeta Sparkle IoT N16R8 en **GPIO 48**.
   - **Driver Dedicado de Hardware RMT:** Implementado mediante el periférico nativo **RMT (Remote Control Transceiver)** a $10\text{ MHz}$ ($100\text{ ns}$ de resolución temporal fija por tick).
     - Bit `'0'`: Pulso en alto de $300\text{ ns}$ (3 ticks) y bajo de $900\text{ ns}$ (9 ticks).
     - Bit `'1'`: Pulso en alto de $900\text{ ns}$ (9 ticks) y bajo de $300\text{ ns}$ (3 ticks).
     - Reset Latch: Nivel bajo de $500\,\mu\text{s}$ (5000 ticks) garantizando extinción total.
     - **Inmunidad Total a Jitter:** La transmisión se ejecuta por hardware DMA sin depender de la CPU ni sufrir demoras por fallos de memoria caché en Flash, eliminando el encendido espurio en verde.
   - **Canales de Control Remoto:**
     - Endpoint HTTP en puerto 80: `GET /light?state=1` (encender), `GET /light?state=0` (apagar), `GET /light?state=toggle` (alternar).
     - Dashboard Web integrado en `http://192.168.4.1/` con botón interactivo.
     - Estado por defecto al encendido: **Apagada ($0\text{ lux}$)**. Al activarse: **Blanco puro al 100% ($R=255, G=255, B=255, W=255$)**.

2. **Visualizador de Estación Terrena V2 (`V2_visor_laptop_con_luz.py` / `visor_integrado_con_luz.py`):**
   - Incorpora control interactivo de luz en caliente mediante la pulsación de la tecla **`[L]`**.
   - HUD táctico con indicación en tiempo real: badge `[ LUZ: ENCENDIDA ] (100% Blanco)` en amarillo brillante o `[ LUZ: APAGADA ]` en gris, más indicador de estado en la barra superior.
   - Lanzador rápido de un clic: [`iniciar_visor_con_luz.bat`](file:///c:/Users/ASUS/OneDrive/Escritorio/Todo/Propio/Agentes_Antigravity/RedaccionTesis/pruebas/integradas_camara_gas/iniciar_visor_con_luz.bat).

3. **Nodo Supervisor para Hexápodo Primario V2 (`V2_nodo_raspberry_headless_con_luz.py`):**
   - Opera en Raspberry Pi 5 (Ubuntu 22.04 LTS) en modo headless.
   - Incluye cliente HTTP asíncrono para encender/apagar la luz del robot secundario a distancia.
   - Habilita la suscripción al tópico ROS 2 `/hexapodo/cmd_luz` (`std_msgs/msg/Bool`), permitiendo a los algoritmos de navegación y exploración autónoma activar la iluminación al detectar zonas de baja visibilidad.



