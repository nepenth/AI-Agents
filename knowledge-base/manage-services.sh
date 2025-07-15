#!/bin/bash

# Knowledge Base Agent Service Management Script
# Simple script to manage the systemd services

set -e

WORKER_SERVICE="knowledge-base-worker.service"
WEB_SERVICE="knowledge-base-web.service"

show_usage() {
    echo "📋 Knowledge Base Agent Service Manager"
    echo "========================================="
    echo ""
    echo "Usage: $0 {start|stop|restart|status|logs|logs-follow|enable|disable}"
    echo ""
    echo "Commands:"
    echo "  start        Start both services"
    echo "  stop         Stop both services"
    echo "  restart      Restart both services"
    echo "  status       Show status of both services"
    echo "  logs         Show recent logs for both services"
    echo "  logs-follow  Follow logs in real-time"
    echo "  logs-worker  Show worker logs only"
    echo "  logs-web     Show web server logs only"
    echo "  enable       Enable services to start on boot"
    echo "  disable      Disable services from starting on boot"
    echo ""
}

check_sudo() {
    if [[ $EUID -ne 0 ]]; then
        echo "❌ This command requires sudo privileges"
        echo "   Run: sudo $0 $1"
        exit 1
    fi
}

case "${1:-}" in
    start)
        check_sudo $1
        echo "🚀 Starting Knowledge Base Agent services..."
        systemctl start $WORKER_SERVICE
        sleep 2
        systemctl start $WEB_SERVICE
        echo "✅ Services started!"
        ;;
    
    stop)
        check_sudo $1
        echo "🛑 Stopping Knowledge Base Agent services..."
        systemctl stop $WEB_SERVICE
        systemctl stop $WORKER_SERVICE
        echo "✅ Services stopped!"
        ;;
    
    restart)
        check_sudo $1
        echo "🔄 Restarting Knowledge Base Agent services..."
        systemctl stop $WEB_SERVICE
        systemctl restart $WORKER_SERVICE
        sleep 2
        systemctl start $WEB_SERVICE
        echo "✅ Services restarted!"
        ;;
    
    status)
        echo "📊 Knowledge Base Agent Service Status"
        echo "======================================"
        echo ""
        echo "🔧 Worker Service:"
        systemctl status $WORKER_SERVICE --no-pager -l
        echo ""
        echo "🌐 Web Service:"
        systemctl status $WEB_SERVICE --no-pager -l
        ;;
    
    logs)
        echo "📝 Recent logs for both services:"
        echo "================================="
        echo ""
        echo "🔧 Worker Service Logs:"
        journalctl -u $WORKER_SERVICE --no-pager -l -n 20
        echo ""
        echo "🌐 Web Service Logs:"
        journalctl -u $WEB_SERVICE --no-pager -l -n 20
        ;;
    
    logs-follow)
        echo "📝 Following logs for both services (Ctrl+C to exit):"
        journalctl -fu $WORKER_SERVICE -fu $WEB_SERVICE
        ;;
    
    logs-worker)
        echo "📝 Worker service logs (Ctrl+C to exit):"
        journalctl -fu $WORKER_SERVICE
        ;;
    
    logs-web)
        echo "📝 Web service logs (Ctrl+C to exit):"
        journalctl -fu $WEB_SERVICE
        ;;
    
    enable)
        check_sudo $1
        echo "✅ Enabling services to start on boot..."
        systemctl enable $WORKER_SERVICE
        systemctl enable $WEB_SERVICE
        echo "✅ Services enabled!"
        ;;
    
    disable)
        check_sudo $1
        echo "❌ Disabling services from starting on boot..."
        systemctl disable $WORKER_SERVICE
        systemctl disable $WEB_SERVICE
        echo "✅ Services disabled!"
        ;;
    
    *)
        show_usage
        exit 1
        ;;
esac 