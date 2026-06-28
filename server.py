#!/usr/bin/env python3
"""
AI Trend Tracker — Local Dev Server
Serves static dashboard files and handles refresh requests via `/api/refresh`.
"""

import http.server
import socketserver
import sys
import os

PORT = 8765

class MyHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/refresh':
            try:
                # Add support for executing fetch_ai_news
                print("\n🔄 Refresh requested from client. Fetching latest AI news...")
                
                # Import fetch_ai_news locally and call its main function
                # This runs synchronously and writes output to articles_data.js
                import fetch_ai_news
                
                # We reload the module to make sure any imports/configurations are fresh
                import importlib
                importlib.reload(fetch_ai_news)
                
                fetch_ai_news.main()
                
                print("✅ Refresh successful.")
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(b'{"status": "success", "message": "News refreshed successfully."}')
            except Exception as e:
                print(f"❌ Error refreshing news: {e}", file=sys.stderr)
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                error_msg = f'{{"status": "error", "message": "{str(e)}"}}'
                self.wfile.write(error_msg.encode('utf-8'))
        else:
            # Delegate other POST requests
            super().do_POST()

    def do_GET(self):
        # We redirect GET /api/refresh to the POST handler just in case
        if self.path == '/api/refresh':
            self.do_POST()
        else:
            # Serve static files for standard GET requests
            super().do_GET()

# Ensure server runs from the directory of server.py to serve static files correctly
os.chdir(os.path.dirname(os.path.abspath(__file__)))

if __name__ == '__main__':
    port = PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    # Allow immediate reuse of the port to prevent "Address already in use" errors
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), MyHandler) as httpd:
        print(f"Serving AI Trend Tracker dashboard at http://localhost:{port}")
        print(f"Press Ctrl+C to stop the server.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")
