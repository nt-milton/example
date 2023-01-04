import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

# This file must be executed inside the docker container
# docker exec -it laika-app /bin/sh
# python3 integration/tests/fake_api_error_code.py <error_code>: int

PORT = 888

if len(sys.argv) != 2:
    print(f'Usage: {sys.argv[0]}  <error_code>')
    sys.exit()

try:
    int(sys.argv[1])
except ValueError:
    print(f'Usage: {sys.argv[1]} in not a valid input. <error_code> must be an integer')
    sys.exit()


error_code = sys.argv[1]
print(f'Error code to be executed = {error_code}')


class Redirect(BaseHTTPRequestHandler):
    def do_GET(self):
        print(self.path)
        self.send_response(int(error_code))
        self.end_headers()


if __name__ == '__main__':
    HTTPServer(('', PORT), Redirect).serve_forever()
