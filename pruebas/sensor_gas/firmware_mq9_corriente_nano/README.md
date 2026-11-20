# Módulo Integrado de Gas (MQ-9) y Corriente (ACS758LCB) con Arduino Nano

Este directorio contiene el firmware y la documentación técnica para la adquisición simultánea del sensor de gases **MQ-9** (Etanol / Monóxido de Carbono / Combustibles) y el sensor de corriente **ACS758LCB-050B** (Monitoreo de consumo de batería LiPo 3S del Robot Primario Chipo), procesados mediante un **Arduino Nano** y transmitidos vía USB a la **Raspberry Pi 5** (o PC).

---

## 📌 1. Mapeo de Conexiones Físicas

### Esquemático Rápido

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

### Tabla de Pines

| Sensor | Pin del Sensor | Pin en Arduino Nano | Descripción de la Señal |
| :--- | :--- | :--- | :--- |
| **MQ-9 (Gas)** | **VCC** | **5V** | Alimentación del micro-calefactor de silicio ($\approx 150-180\text{ mA}$). |
| | **GND** | **GND** | Masa de referencia común. |
| | **A0** | **Pin A0** | Entrada analógica con sobremuestreo (Voltaje proporcional a concentración de gas). |
| | **D0** | **Pin D2** | Entrada digital de interrupción/alarma (Active-LOW, regulada por el potenciómetro LM393). |
| **ACS758 (Corriente)** | **VCC** | **5V** | Alimentación lógica del sensor ($5.00\text{ V}$). |
| | **GND** | **GND** | Tierra de referencia para el cero de reposo ($V_{offset} \approx 2.50\text{ V}$). |
| | **OUT / OU1** | **Pin A1** | Salida analógica proporcional a la corriente ($40\text{ mV/A}$). |
| | **IP+ / IP-** | *En serie con la carga* | Terminales de potencia en serie con la batería LiPo 3S del robot. |

> **IMPORTANTE (Conexión en Estrella):** Llevar cables independientes de 5V y GND desde el Nano hacia el MQ-9 y hacia el ACS758. Evitar puentear la alimentación de un sensor a través del otro en el protoboard para que el consumo del calefactor del MQ-9 no introduzca caídas de tensión en la medición de corriente ratiométrica.

---

## ⚡ 2. Especificaciones del Firmware (`firmware_mq9_corriente_nano.ino`)

* **Microcontrolador:** ATmega328P @ 16 MHz (Arduino Nano).
* **Velocidad Serial:** `115200` baudios.
* **Frecuencia de Muestreo:** $20\text{ Hz}$ (cada $50\text{ ms}$).
* **Filtrado:** Sobremuestreo de 20 muestras en A0 y 25 muestras en A1, con lecturas *dummy* intermedias para estabilizar el multiplexor ADC del ATmega328P al conmutar entre canales.
* **Comandos en Vivo:** Enviar el caracter `'c'` o `'C'` por el puerto serie para forzar la recalibración del cero en caliente ($R_0$ de gas y $V_{offset}$ de corriente).

### Estructura de la Trama JSON Emitida
```json
{"t":1227,"gas_v":0.850,"gas_raw":174.0,"gas_ratio":1.000,"gas_alerta":0,"i_amp":0.00,"i_v":2.500,"pot_w":0.00}
```

* `t`: Tiempo transcurrido en milisegundos (`millis()`).
* `gas_v`: Voltaje analógico leído en A0 ($0.0\text{ V} - 5.0\text{ V}$).
* `gas_raw`: Valor directo del convertidor ADC ($0 - 1023$).
* `gas_ratio`: Razón de concentración relativa $R_0 / R_s$ (1.00x en aire limpio; $> 2.0\text{x}$ ante presencia de etanol/gases).
* `gas_alerta`: Estado digital del pin D2 (1 = umbral superado, 0 = normal).
* `i_amp`: Corriente calculada en Amperios.
* `i_v`: Voltaje analógico medido en A1 ($V$).
* `pot_w`: Potencia instantánea estimada en Vatios ($I \times 11.1\text{ V}$).

---

## 🍓 3. Integración en Raspberry Pi 5 (Robot Primario Chipo)

### A. Detección y Permisos
Al conectar el Arduino Nano al puerto USB de la Raspberry Pi:
1. Identificar el puerto asignado:
   ```bash
   ls /dev/ttyUSB* /dev/ttyACM*
   # Usualmente /dev/ttyUSB0
   ```
2. Dar permisos de lectura/escritura al usuario sin requerir `sudo`:
   ```bash
   sudo usermod -aG dialout $USER
   # O temporalmente: sudo chmod 666 /dev/ttyUSB0
   ```

### B. Ejecución del Monitor en Consola
Se incluye el script `pruebas/sensor_gas/monitor_sensores_rpi.py`:
```bash
python3 pruebas/sensor_gas/monitor_sensores_rpi.py /dev/ttyUSB0
```

### C. Mapeo a Tópicos de ROS 2 (Jazzy)
En el nodo puente de telemetría de ROS 2 (`ros2_ws`), publicar este flujo JSON en los siguientes tópicos estándar:
* `/ambiente/gas_mq9/voltaje` (`std_msgs/msg/Float32`)
* `/ambiente/gas_mq9/ratio` (`std_msgs/msg/Float32`)
* `/ambiente/gas_mq9/alerta` (`std_msgs/msg/Bool`)
* `/potencia/corriente_bateria` (`sensor_msgs/msg/BatteryState` o `std_msgs/msg/Float32`)

Esto permite vincular la presencia de gases combustibles/alcohol directamente con las nubes de puntos 3D y el mapa de ocupación en **RTAB-Map SLAM**.

---

## 💻 4. Visualizador Gráfico en PC (Windows)

Para monitoreo en vivo con osciloscopio interactivo en OpenCV:
* Ejecutar: **`iniciar_visor_gas_mq9.bat`** (en la raíz del proyecto).
* Controles:
  * `C`: Recalibrar cero de sensores.
  * `R`: Iniciar/Detener guardado de datos en CSV (`pruebas/datos_mision/`).
  * `S`: Tomar captura de pantalla en PNG (`pruebas/imagenes_experimentos/`).
  * `Q` / `ESC`: Salir.
