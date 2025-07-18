#!/usr/bin/env python3
"""
Deployment script for ES Agent to university infrastructure.
Handles deployment preparation and configuration.
"""

import os
import sys
import argparse
import shutil
import json
from pathlib import Path
from typing import Dict, Any

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class UniversityDeployment:
    """Handles deployment to university infrastructure."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.project_root = Path(__file__).parent.parent
        self.deploy_dir = Path(config.get('deploy_dir', './deploy'))
    
    def prepare_deployment(self):
        """Prepare deployment directory with all necessary files."""
        print("📦 Preparing deployment...")
        
        # Create deployment directory
        self.deploy_dir.mkdir(exist_ok=True)
        
        # Copy application files
        self._copy_application_files()
        
        # Create configuration files
        self._create_config_files()
        
        # Create deployment scripts
        self._create_deployment_scripts()
        
        print(f"✅ Deployment prepared in: {self.deploy_dir}")
    
    def _copy_application_files(self):
        """Copy necessary application files to deployment directory."""
        files_to_copy = [
            'api/',
            'src/',
            'requirements.txt',
            'scripts/run_server.py'
        ]
        
        for file_path in files_to_copy:
            src = self.project_root / file_path
            dst = self.deploy_dir / file_path
            
            if src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
    
    def _create_config_files(self):
        """Create configuration files for deployment."""
        # Create environment file
        env_content = f"""# ES Agent Production Environment
ENVIRONMENT=production
CORS_ORIGINS={self.config.get('cors_origins', 'https://your-domain.se')}
ALLOWED_HOSTS={self.config.get('allowed_hosts', 'your-domain.se')}

# Elasticsearch Configuration
ES_HOST={self.config.get('es_host', 'localhost')}
ES_PORT={self.config.get('es_port', '9200')}
ES_USE_SSL={self.config.get('es_use_ssl', 'true')}
ES_VERIFY_CERTS={self.config.get('es_verify_certs', 'true')}

# LLM Configuration (set these in your environment)
# LITELLM_API_KEY=your_api_key_here
# LITELLM_BASE_URL=your_base_url_here

# Optional: Redis for session management
# REDIS_URL=redis://localhost:6379
"""
        
        with open(self.deploy_dir / '.env.production', 'w') as f:
            f.write(env_content)
        
        # Create systemd service file
        service_content = f"""[Unit]
Description=ES Agent API Server
After=network.target

[Service]
Type=simple
User={self.config.get('user', 'www-data')}
Group={self.config.get('group', 'www-data')}
WorkingDirectory={self.config.get('install_dir', '/opt/es-agent')}
Environment=PATH={self.config.get('install_dir', '/opt/es-agent')}/venv/bin
EnvironmentFile={self.config.get('install_dir', '/opt/es-agent')}/.env.production
ExecStart={self.config.get('install_dir', '/opt/es-agent')}/venv/bin/python scripts/run_server.py --host 0.0.0.0 --port {self.config.get('port', '8000')}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
        
        with open(self.deploy_dir / 'es-agent.service', 'w') as f:
            f.write(service_content)
        
        # Create nginx configuration
        nginx_content = f"""server {{
    listen 80;
    server_name {self.config.get('domain', 'your-domain.se')};
    
    location / {{
        proxy_pass http://localhost:{self.config.get('port', '8000')};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
    
    location /api/ws {{
        proxy_pass http://localhost:{self.config.get('port', '8000')};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}
"""
        
        with open(self.deploy_dir / 'nginx.conf', 'w') as f:
            f.write(nginx_content)
    
    def _create_deployment_scripts(self):
        """Create deployment and management scripts."""
        # Installation script
        install_script = f"""#!/bin/bash
# ES Agent Installation Script

set -e

INSTALL_DIR="{self.config.get('install_dir', '/opt/es-agent')}"
SERVICE_NAME="es-agent"

echo "🚀 Installing ES Agent..."

# Create installation directory
sudo mkdir -p $INSTALL_DIR
sudo cp -r * $INSTALL_DIR/

# Create virtual environment
cd $INSTALL_DIR
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set permissions
sudo chown -R {self.config.get('user', 'www-data')}:{self.config.get('group', 'www-data')} $INSTALL_DIR

# Install systemd service
sudo cp es-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME

# Install nginx configuration (optional)
if [ -f /etc/nginx/sites-available/ ]; then
    sudo cp nginx.conf /etc/nginx/sites-available/es-agent
    sudo ln -sf /etc/nginx/sites-available/es-agent /etc/nginx/sites-enabled/
    sudo nginx -t && sudo systemctl reload nginx
fi

echo "✅ ES Agent installed successfully!"
echo "   Configuration: $INSTALL_DIR/.env.production"
echo "   Service: sudo systemctl start $SERVICE_NAME"
echo "   Logs: sudo journalctl -u $SERVICE_NAME -f"
"""
        
        install_path = self.deploy_dir / 'install.sh'
        with open(install_path, 'w') as f:
            f.write(install_script)
        install_path.chmod(0o755)
        
        # Management script
        manage_script = """#!/bin/bash
# ES Agent Management Script

SERVICE_NAME="es-agent"

case "$1" in
    start)
        sudo systemctl start $SERVICE_NAME
        echo "✅ ES Agent started"
        ;;
    stop)
        sudo systemctl stop $SERVICE_NAME
        echo "🛑 ES Agent stopped"
        ;;
    restart)
        sudo systemctl restart $SERVICE_NAME
        echo "🔄 ES Agent restarted"
        ;;
    status)
        sudo systemctl status $SERVICE_NAME
        ;;
    logs)
        sudo journalctl -u $SERVICE_NAME -f
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
"""
        
        manage_path = self.deploy_dir / 'manage.sh'
        with open(manage_path, 'w') as f:
            f.write(manage_script)
        manage_path.chmod(0o755)
    
    def create_deployment_guide(self):
        """Create deployment guide documentation."""
        guide_content = f"""# ES Agent Deployment Guide

## Quick Start

1. **Upload deployment files to server:**
   ```bash
   scp -r deploy/* user@{self.config.get('domain', 'your-server.se')}:/tmp/es-agent/
   ```

2. **Install on server:**
   ```bash
   cd /tmp/es-agent
   sudo ./install.sh
   ```

3. **Configure environment:**
   ```bash
   sudo nano {self.config.get('install_dir', '/opt/es-agent')}/.env.production
   # Set your LITELLM_API_KEY and LITELLM_BASE_URL
   ```

4. **Start the service:**
   ```bash
   sudo systemctl start es-agent
   ```

## Configuration

### Environment Variables
- `LITELLM_API_KEY`: Your LLM API key (required)
- `LITELLM_BASE_URL`: Your LLM base URL (required)
- `ES_HOST`: Elasticsearch host (default: localhost)
- `CORS_ORIGINS`: Allowed CORS origins (default: https://your-domain.se)

### Service Management
```bash
# Start service
sudo systemctl start es-agent

# Stop service
sudo systemctl stop es-agent

# Restart service
sudo systemctl restart es-agent

# Check status
sudo systemctl status es-agent

# View logs
sudo journalctl -u es-agent -f
```

### Web Server Integration
The deployment includes nginx configuration for reverse proxy setup.

## Monitoring

### Health Checks
- Basic: `curl http://localhost:{self.config.get('port', '8000')}/api/health`
- Detailed: `curl http://localhost:{self.config.get('port', '8000')}/api/health/detailed`

### Logs
- Application logs: `sudo journalctl -u es-agent -f`
- Nginx logs: `sudo tail -f /var/log/nginx/access.log`

## Troubleshooting

### Common Issues
1. **Service won't start**: Check environment variables in `.env.production`
2. **WebSocket connection fails**: Ensure nginx WebSocket proxy is configured
3. **CORS errors**: Update `CORS_ORIGINS` in environment file

### Debug Mode
To run in debug mode:
```bash
cd {self.config.get('install_dir', '/opt/es-agent')}
source venv/bin/activate
python scripts/run_server.py --log-level debug
```

## Security Considerations

1. **CORS**: Restrict `CORS_ORIGINS` to your domain only
2. **SSL**: Use HTTPS in production (configure nginx with SSL)
3. **Firewall**: Limit access to port {self.config.get('port', '8000')} from localhost only
4. **Environment**: Keep API keys in environment file with restricted permissions

## University Integration

The ES Agent can be integrated into existing university web applications:

1. **API Integration**: Use REST endpoints for backend integration
2. **WebSocket Integration**: Use WebSocket for real-time updates
3. **Static Files**: Serve demo interface alongside existing applications
4. **CORS**: Configure for your university domain

For questions or support, refer to the project documentation.
"""
        
        with open(self.deploy_dir / 'DEPLOYMENT_GUIDE.md', 'w') as f:
            f.write(guide_content)

def main():
    """Main function for deployment preparation."""
    parser = argparse.ArgumentParser(description='ES Agent Deployment Preparation')
    parser.add_argument('--config', help='Path to deployment configuration file')
    parser.add_argument('--domain', help='Domain name for deployment')
    parser.add_argument('--port', type=int, default=8000, help='Port for the service')
    parser.add_argument('--install-dir', default='/opt/es-agent', help='Installation directory')
    parser.add_argument('--user', default='www-data', help='System user for the service')
    parser.add_argument('--deploy-dir', default='./deploy', help='Deployment preparation directory')
    
    args = parser.parse_args()
    
    # Load configuration
    config = {}
    if args.config and Path(args.config).exists():
        with open(args.config, 'r') as f:
            config = json.load(f)
    
    # Override with command line arguments
    if args.domain:
        config['domain'] = args.domain
    if args.port:
        config['port'] = args.port
    if args.install_dir:
        config['install_dir'] = args.install_dir
    if args.user:
        config['user'] = args.user
    if args.deploy_dir:
        config['deploy_dir'] = args.deploy_dir
    
    # Set defaults
    config.setdefault('cors_origins', f"https://{config.get('domain', 'your-domain.se')}")
    config.setdefault('allowed_hosts', config.get('domain', 'your-domain.se'))
    
    # Create deployment
    deployment = UniversityDeployment(config)
    deployment.prepare_deployment()
    deployment.create_deployment_guide()
    
    print("\n📋 Deployment Summary:")
    print(f"   Domain: {config.get('domain', 'your-domain.se')}")
    print(f"   Port: {config.get('port', '8000')}")
    print(f"   Install Directory: {config.get('install_dir', '/opt/es-agent')}")
    print(f"   Deploy Directory: {config.get('deploy_dir', './deploy')}")
    print(f"   User: {config.get('user', 'www-data')}")
    print("\n📖 Next Steps:")
    print("   1. Review the deployment guide: deploy/DEPLOYMENT_GUIDE.md")
    print("   2. Transfer files to your server")
    print("   3. Run the installation script")
    print("   4. Configure environment variables")
    print("   5. Start the service")

if __name__ == '__main__':
    main()