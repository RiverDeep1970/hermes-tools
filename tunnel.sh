#!/bin/bash
# Cloudflare Tunnel for Mood Tracker
# Logs the URL to a file so we can check it
exec > /home/ubuntu/.hermes/tunnel-url.log 2>&1
echo "Starting tunnel at $(date)"
cloudflared tunnel --url http://localhost:8080