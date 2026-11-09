# Estado del firmware ESP32-S3-CAM

Fecha: 2026-10-09

## Objetivo de esta versión

Capturar la cámara USB UVC 349C:3307 en el ESP32-S3 y entregar los cuadros JPEG por Wi-Fi a una aplicación que se ejecuta en Windows. El procesamiento de mapa 3D y localización se hará en Windows; no se ejecuta SLAM en el microcontrolador.

## Implementado

- Host USB y controlador UVC nativo espressif/usb_host_uvc 2.6.0.
- Negociación MJPEG: intenta 480×320 a 15 FPS primero y 640×480 a 15 FPS como alternativa.
- Punto de acceso Wi-Fi del ESP32:
  - SSID: ESP32S3-CAM
  - Clave de prueba: camara123
  - IP: 192.168.4.1
- Servidor HTTP con estas rutas:
  - Puerto 80, GET /stream: flujo continuo MJPEG multipart.
  - Puerto 81, GET /status: estado y metadatos JSON.
  - Puerto 81, GET /: página sencilla con vídeo y estado.
- Un cliente MJPEG simultáneo. Si la red no consume los cuadros a tiempo, el firmware descarta los antiguos y entrega el cuadro más reciente.
- Copia del JPEG al buffer de PSRAM antes de liberar el buffer UVC.
- Contador por cuadro y marca de tiempo en microsegundos desde el arranque del ESP32.
- Flash configurada en 16 MB; requiere PSRAM.

## Formato de transmisión

La respuesta HTTP de GET /stream usa:

    Content-Type: multipart/x-mixed-replace;boundary=frame

Cada parte está formada por los siguientes encabezados, una línea vacía, los bytes JPEG y CRLF:

    --frame
    Content-Type: image/jpeg
    Content-Length: <tamaño en bytes>
    X-Sequence: <contador uint32>
    X-Timestamp-Us: <microsegundos int64>
    X-Width: <ancho>
    X-Height: <alto>

    <bytes JPEG>

X-Sequence empieza en 1, aumenta por cada cuadro y vuelve a cero al reiniciar. X-Timestamp-Us se toma con esp_timer_get_time() cuando el cuadro ya llegó al callback del ESP32. No es la hora de exposición del sensor ni un reloj sincronizado con Windows/Orbbec. Para correlacionar streams en Windows habrá que estimar el desfase o añadir un protocolo de sincronización.

GET /status responde JSON similar a:

    {
      "protocol": "esp32-uvc-mjpeg-v1",
      "camera_connected": true,
      "streaming": true,
      "width": 480,
      "height": 320,
      "fps": 14.9,
      "sequence": 127,
      "jpeg_bytes": 9300,
      "timestamp_source": "esp_timer_us_at_frame_callback"
    }

## Prueba en Windows

1. Grabar el firmware y abrir el monitor serie en el puerto COM.
2. Conectar Windows a la red ESP32S3-CAM y abrir http://192.168.4.1:81/status.
3. Abrir http://192.168.4.1/stream en un navegador para confirmar vídeo en vivo.
4. Para la aplicación de localización, consumir cada parte MJPEG y conservar X-Sequence, X-Timestamp-Us, ancho y alto junto al JPEG.

Al conectar Windows al AP, el acceso a Internet puede cambiar según la configuración de red del PC. Se puede apagar el AP de prueba en favor de modo estación cuando se defina la red de destino.

## Pendiente de validación

- Compilar con ESP-IDF 5.4.4.
- Grabar en la placa y confirmar que el SoftAP arranca junto al host USB.
- Confirmar el flujo sostenido desde Windows, el tamaño de JPEG y los FPS reales por Wi-Fi.
- Confirmar en Windows que puerto 81 responde durante la transmisión continua del puerto 80.
- Medir el uso restante de PSRAM con UVC y el buffer HTTP activos.
- Probar reconexión tras desconectar y volver a conectar la cámara.
- Reemplazar la clave de demostración antes de usar el AP fuera de una prueba local.
- Diseñar el transporte de timestamps entre el reloj del ESP32 y el reloj monotónico de Windows/Orbbec.

El firmware de captura UVC anterior sí fue probado en la placa y entregó aproximadamente 14.9 FPS a 480×320. La transmisión Wi-Fi añadida en esta versión aún requiere prueba física.
