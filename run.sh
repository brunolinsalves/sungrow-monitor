#!/usr/bin/with-contenv bashio
CONFIG_PATH=/data/options.json

echo "Initializing addon sungrow_monitor"
echo "Configuration parameters:"
MQTT_Broker="$(bashio::config 'MQTT_Broker')"
echo "  - MQTT Broker: $MQTT_Broker"
MQTT_Port="$(bashio::config 'MQTT_Port')"
echo "  - MQTT Port: $MQTT_Port"
MQTT_Username="$(bashio::config 'MQTT_Username')"
echo "  - MQTT Username: $MQTT_Username"
MQTT_Password="$(bashio::config 'MQTT_Password')"
echo "  - MQTT Password: $MQTT_Password"
Inverter_IP="$(bashio::config 'Inverter_IP')"
echo "  - Sungrow Inverter IP: $Inverter_IP"
Inverter_Port="$(bashio::config 'Inverter_Port')"
echo "  - Sungrow Inverter Port: $Inverter_Port"
PVOutput_API="$(bashio::config 'PVOutput_API')"
echo "  - PV Output API: $PVOutput_API"
PVOutput_SID="$(bashio::config 'PVOutput_SID')"
echo "  - PV Output SID: $PVOutput_SID"

python3 -c "print('Initializing sungrow monitoring script...')"
python3 /sungrow_monitor.py $MQTT_Broker $MQTT_Port $MQTT_Username $MQTT_Password $Inverter_IP $Inverter_Port $PVOutput_API $PVOutput_SID
