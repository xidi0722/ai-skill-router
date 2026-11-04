"""Start a loopback-only server and send one request; no external service required."""
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.request import ProxyHandler, Request, build_opener

from umr.http_api import make_handler


def main():
    profiles = Path(__file__).resolve().parents[1] / 'profiles'
    server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(profiles))
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        body = {'task_id': 'math.solve_equation', 'inputs': {'equation': 'x**2 - 4 = 0'}, 'execute': True}
        url = f'http://127.0.0.1:{server.server_port}/route'
        request = Request(url, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        with build_opener(ProxyHandler({})).open(request, timeout=15) as reply:
            response = json.load(reply)
        print(json.dumps(response, ensure_ascii=False, indent=2))
        if response['decision']['status'] != 'selected' or response['execution']['status'] != 'completed':
            raise RuntimeError('HTTP example did not complete')
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


if __name__ == '__main__':
    main()
