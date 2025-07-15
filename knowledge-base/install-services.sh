#!/bin/bash

# Knowledge Base Agent Service Installation Script
# Run this script with sudo to install the systemd services

set -e

echo "🚀 Installing Knowledge Base Agent Services..."

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use sudo)"
   exit 1
fi

# Define service files
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKER_SERVICE="$SCRIPT_DIR/knowledge-base-worker.service"
WEB_SERVICE="$SCRIPT_DIR/knowledge-base-web.service"

# Check if service files exist
if [[ ! -f "$WORKER_SERVICE" ]]; then
    echo "❌ Worker service file not found: $WORKER_SERVICE"
    exit 1
fi

if [[ ! -f "$WEB_SERVICE" ]]; then
    echo "❌ Web service file not found: $WEB_SERVICE"
    exit 1
fi

# Stop existing services if running
echo "🛑 Stopping existing services (if running)..."
systemctl stop knowledge-base-web.service 2>/dev/null || true
systemctl stop knowledge-base-worker.service 2>/dev/null || true

# Copy service files to systemd directory
echo "📁 Installing service files..."
cp "$WORKER_SERVICE" /etc/systemd/system/
cp "$WEB_SERVICE" /etc/systemd/system/

# Set proper permissions
chmod 644 /etc/systemd/system/knowledge-base-worker.service
chmod 644 /etc/systemd/system/knowledge-base-web.service

# Reload systemd daemon
echo "🔄 Reloading systemd daemon..."
systemctl daemon-reload

# Enable services
echo "✅ Enabling services..."
systemctl enable knowledge-base-worker.service
systemctl enable knowledge-base-web.service

# Start services
echo "🚀 Starting services..."
systemctl start knowledge-base-worker.service
sleep 3
systemctl start knowledge-base-web.service

# Check status
echo ""
echo "📊 Service Status:"
echo "=================="
systemctl status knowledge-base-worker.service --no-pager -l
echo ""
systemctl status knowledge-base-web.service --no-pager -l

echo ""
echo "✅ Installation complete!"
echo ""
echo "📋 Useful commands:"
echo "  View logs:         sudo journalctl -fu knowledge-base-worker"
echo "                     sudo journalctl -fu knowledge-base-web"
echo "  Restart services:  sudo systemctl restart knowledge-base-worker"
echo "                     sudo systemctl restart knowledge-base-web"
echo "  Stop services:     sudo systemctl stop knowledge-base-web knowledge-base-worker"
echo "  Start services:    sudo systemctl start knowledge-base-worker knowledge-base-web"
echo "  Check status:      sudo systemctl status knowledge-base-worker knowledge-base-web"
echo "" 