import socket
import json
from lib.picozero import pico_led
from lib.tinydb import TinyDB

db = TinyDB('data.json')

def serve_page():
    try:
        with open('lib/web_page/index.html', 'r') as f:
            return f.read()
    except:
        return '<html><body>Errore caricamento pagina</body></html>'

def start_server(dht_sensor, wind_speed):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 80))
    s.listen(5)
    print('Server web avviato')
    
    while True:
        conn, addr = s.accept()
        print('Connessione da', addr)
        request = conn.recv(1024).decode()
        
        if 'GET / ' in request or '?led=' in request:
            if 'led=on' in request:
                pico_led.on()
            elif 'led=off' in request:
                pico_led.off()
            response = serve_page()
            content_type = 'text/html'
        elif 'GET /data' in request:
            dht_sensor.measure()
            temp = dht_sensor.temperature
            hum = dht_sensor.humidity
            data = f'{{"temp": {temp}, "hum": {hum}, "wind": {wind_speed}}}'
            response = data
            content_type = 'application/json'
        elif 'GET /history' in request:
            history = db.all()
            response = json.dumps(history)
            content_type = 'application/json'
        else:
            response = '404 Not Found'
            content_type = 'text/plain'
        
        conn.send('HTTP/1.1 200 OK\r\n')
        conn.send(f'Content-Type: {content_type}\r\n')
        conn.send('Connection: close\r\n\r\n')
        conn.send(response)
        conn.close()