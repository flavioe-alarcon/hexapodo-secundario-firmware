@echo off
title Visor Laptop con Pantalla - UTEC 2026
echo ============================================================
echo  Iniciando Visor de Laptop (Con Pantalla Grafica)
echo  Conectate a la red Wi-Fi: ESP32S3-CAM
echo  Clave Wi-Fi: camara123
echo ============================================================
cd /d "%~dp0"
python V1_visor_laptop_con_pantalla.py
pause
