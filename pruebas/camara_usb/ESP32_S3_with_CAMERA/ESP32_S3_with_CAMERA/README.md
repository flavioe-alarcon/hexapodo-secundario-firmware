# ESP32-S3 UVC Camera

Firmware ESP-IDF 5.4.4 para recibir la cámara UVC USB 349C:3307 y retransmitir sus cuadros MJPEG por Wi-Fi.

## Conexión

1. Conecta el PC al puerto COM de la placa y la cámara UVC al puerto USB-OTG con VBUS de 5 V.
2. Desde el PC, conéctate a la red Wi-Fi ESP32S3-CAM. La clave inicial es camara123.
3. Abre http://192.168.4.1:81/ para la página de prueba. El vídeo está en http://192.168.4.1/stream y el estado JSON en http://192.168.4.1:81/status.
4. Al terminar, desconecta el cliente del flujo antes de iniciar otro. El firmware admite un cliente MJPEG simultáneo.

La clave se cambia en las definiciones CAMERA_AP_SSID y CAMERA_AP_PASSWORD de main/main.c.

## Protocolo

GET /stream responde como multipart/x-mixed-replace; boundary=frame. Cada parte contiene un JPEG completo y estos encabezados:

- Content-Type: image/jpeg
- Content-Length: tamaño JPEG en bytes
- X-Sequence: contador de cuadros desde el arranque
- X-Timestamp-Us: microsegundos del temporizador del ESP32 cuando llegó el cuadro al callback UVC
- X-Width y X-Height: dimensiones negociadas

La marca de tiempo es de recepción en el ESP32, no el instante físico de exposición de la cámara y no está sincronizada con el reloj de Windows ni con la Gemini 2. Si el cliente recibe más lento que la cámara, se envía el cuadro más nuevo y se omiten cuadros antiguos para evitar latencia creciente.

El flujo de vídeo usa el puerto 80. La página y GET /status usan el puerto 81, así se puede consultar el estado mientras el cliente MJPEG mantiene abierta la conexión de vídeo.

## Compilar y grabar

Con ESP-IDF 5.4.4 activado, ejecuta idf.py build y luego idf.py -p COMx flash monitor.

El proyecto está configurado para flash de 16 MB y requiere PSRAM. La captura actual intenta MJPEG 480×320 a 15 FPS y 640×480 a 15 FPS.

Ver ESTADO_FIRMWARE.md para el alcance implementado, el formato y lo que falta validar.
