"""
Enhanced Custom API Exporter with 10+ metrics
Collecting data from multiple external APIs
"""

from prometheus_client import start_http_server, Gauge, Counter, Histogram, Info
import requests
import time
import logging
import json
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

weather_temperature = Gauge('weather_temperature_celsius', 'Current temperature', ['city', 'country'])
weather_windspeed = Gauge('weather_windspeed_kmh', 'Current wind speed', ['city', 'country'])
weather_humidity = Gauge('weather_humidity_percent', 'Current humidity percentage', ['city', 'country'])
weather_visibility = Gauge('weather_visibility_km', 'Visibility distance', ['city', 'country'])

crypto_bitcoin_price = Gauge('crypto_bitcoin_price_usd', 'Bitcoin price in USD')
crypto_ethereum_price = Gauge('crypto_ethereum_price_usd', 'Ethereum price in USD')
crypto_market_cap = Gauge('crypto_total_market_cap', 'Total crypto market cap in USD')

exchange_rate_usd = Gauge('exchange_rate_usd_kzt', 'USD to KZT exchange rate')
exchange_rate_eur = Gauge('exchange_rate_eur_kzt', 'EUR to KZT exchange rate')

weather_api_status = Gauge('weather_api_status', 'Weather API status (1=up, 0=down)')
crypto_api_status = Gauge('crypto_api_status', 'Crypto API status (1=up, 0=down)')

exporter_uptime = Gauge('exporter_uptime_seconds', 'Exporter uptime in seconds')
api_response_time = Histogram('api_response_time_seconds', 'API response time', ['api_name'])
error_counter = Counter('api_errors_total', 'Total API errors', ['api_name'])

astana_population = Gauge('city_population', 'City population', ['city', 'country'])
current_timestamp = Gauge('current_unix_timestamp', 'Current UNIX timestamp')
random_metric = Gauge('random_metric_value', 'Random metric for testing')

start_time = time.time()

def fetch_weather_data():
    """Get comprehensive weather data for Astana"""
    try:
        start_time = time.time()
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            'latitude': 51.1694,
            'longitude': 71.4491,
            'current_weather': 'true',
            'hourly': 'relativehumidity_2m,visibility',
            'timezone': 'Asia/Almaty'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        current = data['current_weather']
        hourly = data['hourly']
        
        weather_temperature.labels(city='Astana', country='Kazakhstan').set(current['temperature'])
        weather_windspeed.labels(city='Astana', country='Kazakhstan').set(current['windspeed'])
        weather_humidity.labels(city='Astana', country='Kazakhstan').set(hourly['relativehumidity_2m'][0])
        weather_visibility.labels(city='Astana', country='Kazakhstan').set(hourly['visibility'][0] / 1000)  # convert to km
        
        weather_api_status.set(1)
        api_response_time.labels(api_name='weather').observe(time.time() - start_time)
        logger.info("✅ Weather data fetched successfully")
        return True
        
    except Exception as e:
        weather_api_status.set(0)
        error_counter.labels(api_name='weather').inc()
        logger.error(f"❌ Weather API error: {e}")
        return False

def fetch_crypto_data():
    """Get cryptocurrency data from multiple sources"""
    try:
        start_time = time.time()
        
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_market_cap=true",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        crypto_bitcoin_price.set(data['bitcoin']['usd'])
        crypto_ethereum_price.set(data['ethereum']['usd'])
        
        total_market_cap = data['bitcoin']['usd_market_cap'] + data['ethereum']['usd_market_cap']
        crypto_market_cap.set(total_market_cap)
        
        crypto_api_status.set(1)
        api_response_time.labels(api_name='crypto').observe(time.time() - start_time)
        logger.info("✅ Crypto data fetched successfully")
        return True
        
    except Exception as e:
        crypto_api_status.set(0)
        error_counter.labels(api_name='crypto').inc()
        logger.error(f"❌ Crypto API error: {e}")
        return False

def fetch_exchange_rates():
    """Get USD/KZT and EUR/KZT exchange rates"""
    try:
        start_time = time.time()
        response = requests.get(
            "https://api.exchangerate.host/latest?base=USD&symbols=KZT",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        usd_rate = data['rates']['KZT']
        exchange_rate_usd.set(usd_rate)
        
        response_eur = requests.get(
            "https://api.exchangerate.host/latest?base=EUR&symbols=KZT",
            timeout=10
        )
        response_eur.raise_for_status()
        data_eur = response_eur.json()
        
        eur_rate = data_eur['rates']['KZT']
        exchange_rate_eur.set(eur_rate)
        
        api_response_time.labels(api_name='exchange').observe(time.time() - start_time)
        logger.info("✅ Exchange rates fetched successfully")
        return True
        
    except Exception as e:
        error_counter.labels(api_name='exchange').inc()
        logger.error(f"❌ Exchange rates API error: {e}")
        return False

def fetch_static_data():
    """Static data that doesn't change often"""
    try:
        astana_population.labels(city='Astana', country='Kazakhstan').set(1300000)
        
        current_timestamp.set(time.time())
        
        random_metric.set(time.time() % 100)
        
        logger.info("✅ Static data updated")
        return True
        
    except Exception as e:
        logger.error(f"❌ Static data error: {e}")
        return False

def main_loop():
    """Main metrics collection loop"""
    while True:
        try:
            exporter_uptime.set(time.time() - start_time)
            
            fetch_weather_data()
            fetch_crypto_data()
            fetch_exchange_rates()
            fetch_static_data()
            
            logger.info("✅ All metrics updated successfully")
            
        except KeyboardInterrupt:
            logger.info("🛑 Exporter stopped by user")
            break
        except Exception as e:
            logger.error(f"❌ Unexpected error in main loop: {e}")
        
        time.sleep(20)

if __name__ == '__main__':
   
    start_http_server(8000)
    logger.info(" Enhanced Custom Exporter started on port 8000")
    logger.info(" Available metrics:")
    logger.info("   - Weather: temperature, windspeed, humidity, visibility")
    logger.info("   - Crypto: BTC price, ETH price, market cap")
    logger.info("   - Exchange: USD/KZT, EUR/KZT")
    logger.info("   - System: uptime, response time, errors")
    
    main_loop()