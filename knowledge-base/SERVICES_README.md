# Knowledge Base Agent Systemd Services

This directory contains systemd service files to run your Knowledge Base Agent as system services instead of manually running commands.

## 📁 Files

- `knowledge-base-worker.service` - Systemd service for the worker process
- `knowledge-base-web.service` - Systemd service for the web server
- `install-services.sh` - Installation script (run with sudo)
- `manage-services.sh` - Management script for controlling services
- `SERVICES_README.md` - This documentation

## 🚀 Quick Start

### 1. Install Services

```bash
# Make sure you're in the knowledge-base directory
cd /home/nepenthe/git_repos/agents/knowledge-base

# Run the installation script with sudo
sudo ./install-services.sh
```

The installation script will:
- Copy service files to `/etc/systemd/system/`
- Enable the services to start on boot
- Start both services
- Show their status

### 2. Manage Services

Use the management script for easy control:

```bash
# Check status
./manage-services.sh status

# Start services
sudo ./manage-services.sh start

# Stop services
sudo ./manage-services.sh stop

# Restart services
sudo ./manage-services.sh restart

# View logs
./manage-services.sh logs

# Follow logs in real-time
./manage-services.sh logs-follow
```

## 📋 Manual systemctl Commands

If you prefer using systemctl directly:

```bash
# Start services
sudo systemctl start knowledge-base-worker
sudo systemctl start knowledge-base-web

# Stop services
sudo systemctl stop knowledge-base-web
sudo systemctl stop knowledge-base-worker

# Check status
sudo systemctl status knowledge-base-worker
sudo systemctl status knowledge-base-web

# View logs
sudo journalctl -fu knowledge-base-worker
sudo journalctl -fu knowledge-base-web

# Enable/disable on boot
sudo systemctl enable knowledge-base-worker knowledge-base-web
sudo systemctl disable knowledge-base-worker knowledge-base-web
```

## 🔧 Service Details

### Worker Service (`knowledge-base-worker.service`)
- **Description**: Runs the Celery worker processes
- **Command**: `python -m knowledge_base_agent.cli worker`
- **Dependencies**: Network
- **Resources**: 2GB memory limit, 65536 file descriptors

### Web Service (`knowledge-base-web.service`)
- **Description**: Runs the Flask web server
- **Command**: `python -m knowledge_base_agent.cli web`
- **Dependencies**: Network, Worker Service
- **Resources**: 1GB memory limit, 65536 file descriptors

## 🛠️ Configuration

### Environment Variables
Both services use:
- `PATH=/home/nepenthe/git_repos/agents/knowledge-base/venv/bin`
- `FLASK_ENV=production` (web service only)

### Security Features
- Run as `nepenthe` user (not root)
- Private temporary directories
- Read-only system protection
- No new privileges allowed

### Auto-Restart
- Both services restart automatically on failure
- Worker restarts after 10 seconds
- Web server restarts after 5 seconds

## 📝 Logging

Logs are sent to the systemd journal and can be viewed with:

```bash
# All logs for both services
sudo journalctl -u knowledge-base-worker -u knowledge-base-web

# Follow logs in real-time
sudo journalctl -fu knowledge-base-worker -fu knowledge-base-web

# Logs for specific time range
sudo journalctl -u knowledge-base-worker --since "1 hour ago"

# Export logs to file
sudo journalctl -u knowledge-base-worker --since today > worker-logs.txt
```

## 🔍 Troubleshooting

### Services Won't Start
1. Check if the Python virtual environment exists:
   ```bash
   ls -la /home/nepenthe/git_repos/agents/knowledge-base/venv/bin/python
   ```

2. Verify the working directory exists and is accessible:
   ```bash
   ls -la /home/nepenthe/git_repos/agents/knowledge-base/
   ```

3. Check service logs for errors:
   ```bash
   sudo journalctl -u knowledge-base-worker -n 50
   ```

### Permission Issues
- Ensure `nepenthe` user has read/write access to the project directory
- Check that the venv is owned by `nepenthe`:
  ```bash
  sudo chown -R nepenthe:nepenthe /home/nepenthe/git_repos/agents/knowledge-base/
  ```

### Port Conflicts
- Web service runs on the default Flask port (usually 5000 or 8080)
- Check if another service is using the port:
  ```bash
  sudo netstat -tlnp | grep :8080
  ```

## 📦 Uninstall Services

To remove the services:

```bash
# Stop and disable services
sudo systemctl stop knowledge-base-web knowledge-base-worker
sudo systemctl disable knowledge-base-web knowledge-base-worker

# Remove service files
sudo rm /etc/systemd/system/knowledge-base-worker.service
sudo rm /etc/systemd/system/knowledge-base-web.service

# Reload systemd
sudo systemctl daemon-reload
```

## 🔄 Updating Services

When you update the service files:

1. Stop the services:
   ```bash
   sudo ./manage-services.sh stop
   ```

2. Run the installation script again:
   ```bash
   sudo ./install-services.sh
   ```

This will update the service files and restart the services with the new configuration. 