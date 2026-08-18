/**
 * mqttConfig.js — Cấu hình MQTT WebSocket cho Web Frontend
 *
 * Thay đổi MQTT_BROKER_WS_PRIMARY nếu địa chỉ broker khác.
 * Web frontend dùng WebSocket (ws://) để kết nối MQTT.
 * Broker phải bật WebSocket listener (thường port 9001 trên Mosquitto).
 */

export const MQTT_CONFIG = {

  BROKER_WS_PRIMARY: 'ws://192.168.100.234:9001',

  BROKER_WS_FALLBACK: 'ws://192.168.100.234:9001',
 
  CONNECT_TIMEOUT_MS: 5000,

  KEEPALIVE_SECONDS: 60,


  CLIENT_ID: `WebMap_${Math.random().toString(16).slice(2, 8)}`,

  TOPICS: {
    RESULT: 'location/result',

    ROOM: 'location/result',

    POSITION: 'location/result',
  },

  QOS: 0,
};
