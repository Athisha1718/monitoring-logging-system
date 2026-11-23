@echo off
title DevOps Monitoring & Logging Platform
cls
echo =======================================================
echo    Starting DevOps Monitoring & Logging Platform...
echo =======================================================
echo.

docker compose up -d

echo.
echo =======================================================
echo    DevOps Monitoring Platform is Ready!
echo =======================================================
echo.
echo    [Dashboard]   http://localhost:5000
echo    [Grafana]     http://localhost:3000
echo    [Prometheus]  http://localhost:9090
echo    [Alerts]      http://localhost:9093
echo    [cAdvisor]    http://localhost:8888
echo.
echo  * Hold Ctrl and Click any link above in CMD to open.
echo =======================================================
echo.
echo Opening Dashboard in your browser...
start http://localhost:5000
