@echo off
title Visor UDP Puro - ESP32-S3 (Video 5006 + Gas 5005)
color 0b

echo =======================================================================
echo  VISOR INTEGRADO UDP PURO (ESP32-S3)
echo  Video UVC (Puerto UDP 5006) + Gas MiCS-5524 (Puerto UDP 5005)
echo =======================================================================
echo.
echo [1/2] Asegurese de estar conectado a la red Wi-Fi:
echo       SSID:     ESP32S3-CAM
echo       Clave:    camara123
echo.
echo [2/2] Iniciando receptor y simulador UDP en Python...
echo.

cd /d "%~dp0"
python visor_udp_puro.py

echo.
echo Visor finalizado.
pause
