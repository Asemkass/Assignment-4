"""
Unified Teams Alert Script for Prometheus/Grafana Monitoring
Combines alert sending, monitoring, and webhook server in one file
"""

import requests
import json
import logging
import time
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from prometheus_client import start_http_server, Gauge, Counter, Histogram
import random

TEAMS_WEBHOOK_URL = "https://astanait.webhook.office.com/webhookb2/47a779b8-7654-4969-91bf-0162d83b896e@158f15f3-83e0-4906-824c-69bdc50d9d61/IncomingWebhook/53b1f915bdfc4ff08f9da231728ce39e/51e05013-f5aa-4430-a905-d90b3eb8ca29/V2JGriaxmwjVhEsu6hPgu65ITcmbnhtuCtsP5Y4W9oUe81"
PROMETHEUS_URL = "http://localhost:9090"
ALERT_SERVER_PORT = 5000
MONITORING_INTERVAL = 30  # seconds

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TeamsAlerter:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
        self.headers = {'Content-Type': 'application/json'}
        self.alert_history = []
    
    def send_alert(self, title, message, alert_type="info", facts=None):
        """Отправляет алерт в Teams"""
        colors = {"info": "0076D7", "warning": "FF8C00", "error": "D83B01", "success": "107C10"}
        color = colors.get(alert_type, "0076D7")
        
        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color,
            "summary": title,
            "sections": [{
                "activityTitle": title,
                "activitySubtitle": f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "text": message,
                "facts": [{"name": k, "value": str(v)} for k, v in (facts or {}).items()],
                "markdown": True
            }],
            "potentialAction": [
                {"@type": "OpenUri", "name": "📊 Open Grafana", "targets": [{"os": "default", "uri": "http://localhost:3000"}]},
                {"@type": "OpenUri", "name": "📈 Open Prometheus", "targets": [{"os": "default", "uri": "http://localhost:9090"}]}
            ]
        }
        
        try:
            response = requests.post(self.webhook_url, headers=self.headers, data=json.dumps(payload), timeout=10)
            if response.status_code == 200:
                logger.info(f"✅ Alert sent: {title}")
                self.alert_history.append({"title": title, "time": datetime.now(), "status": "sent"})
                return True
            else:
                logger.error(f"❌ Failed to send alert: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Error sending alert: {e}")
            return False
    
    def database_alert(self, metric, value, threshold, message):
        return self.send_alert(
            "🚨 Database Alert",
            message,
            "error",
            {"Metric": metric, "Current Value": value, "Threshold": threshold, "Component": "PostgreSQL"}
        )
    
    def system_alert(self, metric, value, threshold, message):
        return self.send_alert(
            "⚠️ System Alert", 
            message,
            "warning",
            {"Metric": metric, "Current Value": value, "Threshold": threshold, "Component": "System Resources"}
        )
    
    def api_alert(self, metric, value, message):
        return self.send_alert(
            "🌐 API Alert",
            message,
            "info",
            {"Metric": metric, "Current Value": value, "Component": "External APIs"}
        )
    
    def success_alert(self, service, message):
        return self.send_alert(
            "✅ Service Recovered",
            message,
            "success",
            {"Service": service, "Status": "Recovered", "Time": datetime.now().strftime("%H:%M:%S")}
        )
class MetricMonitor:
    def __init__(self, prometheus_url, alerter):
        self.prometheus_url = prometheus_url
        self.alerter = alerter
        self.alert_states = {}  # Для отслеживания состояния алертов
    
    def query_prometheus(self, query):
        """Выполняет запрос к Prometheus"""
        try:
            response = requests.get(f"{self.prometheus_url}/api/v1/query", params={'query': query}, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data['data']['result']:
                return float(data['data']['result'][0]['value'][1])
            return None
        except Exception as e:
            logger.error(f"Error querying Prometheus: {e}")
            return None
    
    def check_alerts(self):
        """Проверяет все метрики и отправляет алерты"""
        logger.info("🔍 Checking metrics for alerts...")
        
        # 1. Database Alerts
        connections = self.query_prometheus('pg_stat_activity_count{datname="postgres"}')
        if connections and connections > 50:
            self.alerter.database_alert("Active Connections", connections, 50, 
                                      f"High database connections: {connections}")
        
        db_size = self.query_prometheus('pg_database_size{datname="postgres"} / 1024 / 1024 / 1024')
        if db_size and db_size > 1:
            self.alerter.database_alert("Database Size", f"{db_size:.2f} GB", "1 GB", 
                                      f"Database size is large: {db_size:.2f} GB")
        
        # 2. System Alerts
        cpu_usage = self.query_prometheus('100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)')
        if cpu_usage and cpu_usage > 80:
            self.alerter.system_alert("CPU Usage", f"{cpu_usage:.1f}%", "80%", 
                                    f"High CPU usage: {cpu_usage:.1f}%")
        
        memory_usage = self.query_prometheus('(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100')
        if memory_usage and memory_usage > 85:
            self.alerter.system_alert("Memory Usage", f"{memory_usage:.1f}%", "85%", 
                                    f"High memory usage: {memory_usage:.1f}%")
        
        # 3. Custom API Alerts
        temperature = self.query_prometheus('weather_temperature_celsius{city="Astana"}')
        if temperature and temperature > 30:
            self.alerter.api_alert("Weather Temperature", f"{temperature}°C", 
                                 f"High temperature in Astana: {temperature}°C")
        
        btc_price = self.query_prometheus('crypto_bitcoin_price_usd')
        if btc_price and btc_price < 40000:
            self.alerter.api_alert("Bitcoin Price", f"${btc_price:,.2f}", 
                                 f"Bitcoin price dropped: ${btc_price:,.2f}")
        
        # 4. Service Status Alerts
        postgres_up = self.query_prometheus('pg_up')
        if postgres_up == 0:
            self.alerter.database_alert("PostgreSQL Status", "DOWN", "UP", "PostgreSQL database is down!")
        
        node_up = self.query_prometheus('up{job="node"}')
        if node_up == 0:
            self.alerter.system_alert("Node Exporter", "DOWN", "UP", "Node Exporter is not running!")
    
    def start_monitoring(self):
        """Запускает непрерывный мониторинг"""
        logger.info("🚀 Starting continuous monitoring...")
        while True:
            try:
                self.check_alerts()
                time.sleep(MONITORING_INTERVAL)
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                time.sleep(10)

# ========== WEB SERVER ДЛЯ PROMETHEUS ALERTS ==========
def create_alert_server(alerter):
    """Создает Flask сервер для обработки алертов от Prometheus"""
    app = Flask(__name__)
    
    @app.route('/alert', methods=['POST'])
    def handle_alert():
        try:
            data = request.json
            if not data or 'alerts' not in data:
                return jsonify({"error": "Invalid alert data"}), 400
            
            for alert in data['alerts']:
                process_prometheus_alert(alert, alerter)
            
            return jsonify({"status": "success"}), 200
        except Exception as e:
            logger.error(f"Error processing alert: {e}")
            return jsonify({"error": str(e)}), 500
    
    def process_prometheus_alert(alert, alerter):
        """Обрабатывает алерт от Prometheus"""
        alertname = alert['labels'].get('alertname', 'Unknown')
        status = alert['status']
        description = alert['annotations'].get('description', '')
        
        if status == 'resolved':
            alerter.success_alert(alertname, f"Alert resolved: {description}")
        else:
            if 'database' in alertname.lower():
                alerter.database_alert(alertname, "Problem detected", "Normal", description)
            elif 'cpu' in alertname.lower() or 'memory' in alertname.lower():
                alerter.system_alert(alertname, "Problem detected", "Normal", description)
            else:
                alerter.api_alert(alertname, "Problem detected", description)
    
    return app

def start_alert_server(app, port=5000):
    """Запускает сервер алертов"""
    logger.info(f"🚀 Starting alert server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def test_all_alerts(alerter):
    """Тестирует все типы алертов"""
    logger.info("🧪 Testing all alert types...")
    
    # Database alerts
    alerter.database_alert("Active Connections", 95, 50, "Database connections are above threshold")
    time.sleep(2)
    
    # System alerts  
    alerter.system_alert("CPU Usage", "85%", "80%", "High CPU usage detected")
    time.sleep(2)
    
    # API alerts
    alerter.api_alert("Weather Temperature", "35°C", "High temperature in Astana")
    time.sleep(2)
    alerter.success_alert("PostgreSQL", "Database connections returned to normal")
    
    logger.info("✅ All test alerts sent!")

def start_simple_exporter():
    """Запускает простой экспортер для демонстрации"""
    logger.info("📊 Starting simple metrics exporter on port 8000...")
    
    test_temperature = Gauge('test_temperature', 'Test temperature metric')
    test_connections = Gauge('test_connections', 'Test connections metric')
    
    start_http_server(8000)
    
    while True:
        test_temperature.set(random.uniform(15, 40))
        test_connections.set(random.randint(10, 100))
        time.sleep(20)
def main():
    """Основная функция запуска всей системы"""
    logger.info("🚀 Starting Unified Alert System...")
    
    alerter = TeamsAlerter(TEAMS_WEBHOOK_URL)
    
    test_all_alerts(alerter)
    
    monitor = MetricMonitor(PROMETHEUS_URL, alerter)
    monitoring_thread = threading.Thread(target=monitor.start_monitoring, daemon=True)
    monitoring_thread.start()
    
    app = create_alert_server(alerter)
    server_thread = threading.Thread(target=lambda: start_alert_server(app, ALERT_SERVER_PORT), daemon=True)
    server_thread.start()
    
    exporter_thread = threading.Thread(target=start_simple_exporter, daemon=True)
    exporter_thread.start()
    
    logger.info("✅ All systems started! Press Ctrl+C to stop.")
    logger.info("📊 Monitoring URL: http://localhost:9090")
    logger.info("📈 Grafana URL: http://localhost:3000") 
    logger.info("🔔 Alert server: http://localhost:5000")
    logger.info("📋 Test alerts sent to Teams!")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 System stopped by user")

if __name__ == "__main__":
    try:
        import flask
        import prometheus_client
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.info("Install required packages: pip install flask prometheus-client requests")
        exit(1)
    
    main()