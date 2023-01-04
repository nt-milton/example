import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

DESTINATIONS = {
    'local': 'http://localhost:8000',
    'dev': 'https://api-dev.heylaika.com',
    'stg': 'https://api-staging.heylaika.com',
    'rc': 'https://api-rc.heylaika.com',
}
PORT = 88

if len(sys.argv) != 2:
    print(f'Usage: {sys.argv[0]}  <env>')
    sys.exit()

env = sys.argv[1]
print(f'Bridge pointing to {DESTINATIONS[env]}')


class Redirect(BaseHTTPRequestHandler):
    def do_GET(self):
        print(self.path)
        self.send_response(302)
        self.send_header('Location', DESTINATIONS[env] + self.path)
        self.end_headers()


if __name__ == '__main__':
    HTTPServer(('', PORT), Redirect).serve_forever()
