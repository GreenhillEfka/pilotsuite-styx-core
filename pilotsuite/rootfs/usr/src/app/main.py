import http.server
import socketserver

PORT = 8909
Handler = http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"PilotSuite Core running on port {PORT}")
    httpd.serve_forever()
