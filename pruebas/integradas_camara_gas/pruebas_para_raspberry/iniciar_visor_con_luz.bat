@echo off
title Visor Laptop V2 (Camara UVC + Gas + Control Luz LED WS2812)
echo ============================================================
echo  Visor Laptop V2 con Control de Luz LED WS2812 (Tesis UTEC)
echo  Conectate a la red Wi-Fi: ESP32S3-CAM  (Clave: camara123)
echo  IP de destino ESP32-S3: 192.168.4.1
echo ============================================================
echo  Atajos en Pantalla:
echo    [L] Encender / Apagar Luz LED (GPIO 48)
echo    [C] Calibrar R0 en Aire Limpio
echo    [S] Captura de Pantalla
echo    [E] Exportar Telemetria CSV
echo    [Q] Salir
echo ============================================================
cd /d "%~dp0"
python V2_visor_laptop_con_luz.py http://192.168.4.1
pause
