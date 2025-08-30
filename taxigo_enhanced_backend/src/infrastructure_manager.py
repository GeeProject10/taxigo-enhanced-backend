"""
Enterprise Infrastructure Manager for TaxiGo Pro
Handles load balancing, auto-scaling, performance monitoring, and error tracking
"""

import time
import psutil
import threading
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict, deque
import sqlite3
import requests
from dataclasses import dataclass

@dataclass
class PerformanceMetric:
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    disk_usage: float
    active_connections: int
    response_time: float
    error_rate: float

@dataclass
class ErrorEvent:
    timestamp: datetime
    error_type: str
    message: str
    endpoint: str
    user_id: Optional[str]
    stack_trace: Optional[str]
    severity: str

class InfrastructureManager:
    def __init__(self):
        # Performance monitoring
        self.metrics_history = deque(maxlen=1440)  # 24 hours of minute-by-minute data
        self.current_connections = 0
        self.response_times = deque(maxlen=1000)
        self.error_events = deque(maxlen=10000)
        
        # Auto-scaling configuration
        self.scaling_config = {
            'cpu_threshold_scale_up': 80.0,
            'cpu_threshold_scale_down': 30.0,
            'memory_threshold_scale_up': 85.0,
            'memory_threshold_scale_down': 40.0,
            'min_instances': 1,
            'max_instances': 10,
            'scale_up_cooldown': 300,  # 5 minutes
            'scale_down_cooldown': 600,  # 10 minutes
        }
        
        # Load balancing
        self.server_instances = []
        self.health_checks = {}
        self.load_balancer_stats = defaultdict(int)
        
        # Alerting
        self.alert_thresholds = {
            'high_cpu': 90.0,
            'high_memory': 90.0,
            'high_error_rate': 5.0,  # 5% error rate
            'slow_response': 2000.0,  # 2 seconds
            'low_disk_space': 90.0
        }
        
        self.alert_channels = []
        self.last_alerts = {}
        
        # Business Intelligence
        self.analytics_data = {
            'daily_active_users': defaultdict(int),
            'ride_statistics': defaultdict(int),
            'revenue_metrics': defaultdict(float),
            'geographic_data': defaultdict(int),
            'user_behavior': defaultdict(int)
        }
        
        # Start monitoring
        self.start_monitoring()
    
    def collect_system_metrics(self) -> PerformanceMetric:
        """Collect current system performance metrics"""
        try:
            # CPU and Memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage = (disk.used / disk.total) * 100
            
            # Calculate current error rate
            recent_errors = [
                error for error in self.error_events
                if error.timestamp > datetime.now() - timedelta(minutes=5)
            ]
            error_rate = len(recent_errors) / max(1, len(self.response_times)) * 100
            
            # Average response time
            avg_response_time = sum(self.response_times) / max(1, len(self.response_times))
            
            metric = PerformanceMetric(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_usage=disk_usage,
                active_connections=self.current_connections,
                response_time=avg_response_time,
                error_rate=error_rate
            )
            
            return metric
        
        except Exception as e:
            print(f"Error collecting metrics: {e}")
            return None
    
    def record_request_metrics(self, response_time: float, endpoint: str, status_code: int):
        """Record metrics for individual requests"""
        self.response_times.append(response_time)
        
        # Record error if status code indicates failure
        if status_code >= 400:
            severity = 'HIGH' if status_code >= 500 else 'MEDIUM'
            self.log_error(
                error_type='http_error',
                message=f'HTTP {status_code} error',
                endpoint=endpoint,
                severity=severity
            )
    
    def log_error(self, error_type: str, message: str, endpoint: str = None, 
                  user_id: str = None, stack_trace: str = None, severity: str = 'MEDIUM'):
        """Log error events for tracking and analysis"""
        error_event = ErrorEvent(
            timestamp=datetime.now(),
            error_type=error_type,
            message=message,
            endpoint=endpoint,
            user_id=user_id,
            stack_trace=stack_trace,
            severity=severity
        )
        
        self.error_events.append(error_event)
        
        # Check if alert should be sent
        self.check_error_rate_alerts()
        
        # Log to console (in production, send to logging service)
        print(f"ERROR [{severity}]: {error_type} - {message}")
    
    def get_performance_dashboard(self) -> Dict:
        """Get comprehensive performance dashboard data"""
        current_metric = self.collect_system_metrics()
        
        # Calculate trends (last hour vs previous hour)
        now = datetime.now()
        last_hour_metrics = [
            m for m in self.metrics_history
            if now - timedelta(hours=1) <= m.timestamp <= now
        ]
        prev_hour_metrics = [
            m for m in self.metrics_history
            if now - timedelta(hours=2) <= m.timestamp <= now - timedelta(hours=1)
        ]
        
        def avg_metric(metrics, attr):
            if not metrics:
                return 0
            return sum(getattr(m, attr) for m in metrics) / len(metrics)
        
        # Error analysis
        recent_errors = [
            error for error in self.error_events
            if error.timestamp > now - timedelta(hours=24)
        ]
        
        error_breakdown = defaultdict(int)
        for error in recent_errors:
            error_breakdown[error.error_type] += 1
        
        return {
            'current_metrics': {
                'cpu_percent': current_metric.cpu_percent if current_metric else 0,
                'memory_percent': current_metric.memory_percent if current_metric else 0,
                'disk_usage': current_metric.disk_usage if current_metric else 0,
                'active_connections': self.current_connections,
                'avg_response_time': avg_metric(last_hour_metrics, 'response_time'),
                'error_rate': avg_metric(last_hour_metrics, 'error_rate')
            },
            'trends': {
                'cpu_trend': avg_metric(last_hour_metrics, 'cpu_percent') - avg_metric(prev_hour_metrics, 'cpu_percent'),
                'memory_trend': avg_metric(last_hour_metrics, 'memory_percent') - avg_metric(prev_hour_metrics, 'memory_percent'),
                'response_time_trend': avg_metric(last_hour_metrics, 'response_time') - avg_metric(prev_hour_metrics, 'response_time'),
                'error_rate_trend': avg_metric(last_hour_metrics, 'error_rate') - avg_metric(prev_hour_metrics, 'error_rate')
            },
            'error_analysis': {
                'total_errors_24h': len(recent_errors),
                'error_breakdown': dict(error_breakdown),
                'top_error_endpoints': self.get_top_error_endpoints(),
                'recent_critical_errors': [
                    {
                        'timestamp': error.timestamp.isoformat(),
                        'type': error.error_type,
                        'message': error.message,
                        'endpoint': error.endpoint
                    }
                    for error in recent_errors[-10:] if error.severity == 'HIGH'
                ]
            },
            'system_health': {
                'status': self.get_system_health_status(),
                'uptime': self.get_system_uptime(),
                'load_balancer_stats': dict(self.load_balancer_stats),
                'active_alerts': self.get_active_alerts()
            }
        }
    
    def get_top_error_endpoints(self) -> List[Dict]:
        """Get endpoints with most errors in last 24 hours"""
        recent_errors = [
            error for error in self.error_events
            if error.timestamp > datetime.now() - timedelta(hours=24)
        ]
        
        endpoint_errors = defaultdict(int)
        for error in recent_errors:
            if error.endpoint:
                endpoint_errors[error.endpoint] += 1
        
        return [
            {'endpoint': endpoint, 'error_count': count}
            for endpoint, count in sorted(endpoint_errors.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
    
    def get_system_health_status(self) -> str:
        """Determine overall system health status"""
        current_metric = self.collect_system_metrics()
        if not current_metric:
            return 'UNKNOWN'
        
        # Check critical thresholds
        if (current_metric.cpu_percent > self.alert_thresholds['high_cpu'] or
            current_metric.memory_percent > self.alert_thresholds['high_memory'] or
            current_metric.error_rate > self.alert_thresholds['high_error_rate']):
            return 'CRITICAL'
        
        # Check warning thresholds
        if (current_metric.cpu_percent > 70 or
            current_metric.memory_percent > 70 or
            current_metric.response_time > 1000):
            return 'WARNING'
        
        return 'HEALTHY'
    
    def get_system_uptime(self) -> Dict:
        """Get system uptime information"""
        try:
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time
            
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            
            return {
                'uptime_seconds': uptime_seconds,
                'uptime_formatted': f"{days}d {hours}h {minutes}m",
                'boot_time': datetime.fromtimestamp(boot_time).isoformat()
            }
        except:
            return {
                'uptime_seconds': 0,
                'uptime_formatted': 'Unknown',
                'boot_time': 'Unknown'
            }
    
    def get_active_alerts(self) -> List[Dict]:
        """Get currently active system alerts"""
        alerts = []
        current_metric = self.collect_system_metrics()
        
        if not current_metric:
            return alerts
        
        # Check each threshold
        if current_metric.cpu_percent > self.alert_thresholds['high_cpu']:
            alerts.append({
                'type': 'high_cpu',
                'severity': 'HIGH',
                'message': f'CPU usage is {current_metric.cpu_percent:.1f}%',
                'threshold': self.alert_thresholds['high_cpu']
            })
        
        if current_metric.memory_percent > self.alert_thresholds['high_memory']:
            alerts.append({
                'type': 'high_memory',
                'severity': 'HIGH',
                'message': f'Memory usage is {current_metric.memory_percent:.1f}%',
                'threshold': self.alert_thresholds['high_memory']
            })
        
        if current_metric.error_rate > self.alert_thresholds['high_error_rate']:
            alerts.append({
                'type': 'high_error_rate',
                'severity': 'HIGH',
                'message': f'Error rate is {current_metric.error_rate:.1f}%',
                'threshold': self.alert_thresholds['high_error_rate']
            })
        
        if current_metric.response_time > self.alert_thresholds['slow_response']:
            alerts.append({
                'type': 'slow_response',
                'severity': 'MEDIUM',
                'message': f'Average response time is {current_metric.response_time:.0f}ms',
                'threshold': self.alert_thresholds['slow_response']
            })
        
        return alerts
    
    def check_error_rate_alerts(self):
        """Check if error rate alerts should be sent"""
        now = datetime.now()
        recent_errors = [
            error for error in self.error_events
            if error.timestamp > now - timedelta(minutes=5)
        ]
        
        if len(recent_errors) > 10:  # More than 10 errors in 5 minutes
            alert_key = 'high_error_rate'
            last_alert = self.last_alerts.get(alert_key)
            
            # Send alert if none sent in last 15 minutes
            if not last_alert or now - last_alert > timedelta(minutes=15):
                self.send_alert(
                    alert_type='high_error_rate',
                    message=f'High error rate detected: {len(recent_errors)} errors in 5 minutes',
                    severity='HIGH'
                )
                self.last_alerts[alert_key] = now
    
    def send_alert(self, alert_type: str, message: str, severity: str = 'MEDIUM'):
        """Send alert through configured channels"""
        alert_data = {
            'type': alert_type,
            'message': message,
            'severity': severity,
            'timestamp': datetime.now().isoformat(),
            'system': 'TaxiGo Pro Backend'
        }
        
        # Log alert
        print(f"ALERT [{severity}]: {alert_type} - {message}")
        
        # In production, send to:
        # - Slack/Discord webhook
        # - Email notifications
        # - SMS alerts for critical issues
        # - PagerDuty/OpsGenie
        
        # Example webhook notification (uncomment and configure in production)
        # for webhook_url in self.alert_channels:
        #     try:
        #         requests.post(webhook_url, json=alert_data, timeout=10)
        #     except Exception as e:
        #         print(f"Failed to send alert to {webhook_url}: {e}")
    
    def record_business_analytics(self, event_type: str, data: Dict):
        """Record business intelligence data"""
        try:
            current_date = datetime.now().date().isoformat()
            
            if event_type == 'user_login':
                self.analytics_data['daily_active_users'][current_date] += 1
            
            elif event_type == 'ride_completed':
                self.analytics_data['ride_statistics'][current_date] += 1
                if 'fare' in data:
                    self.analytics_data['revenue_metrics'][current_date] += float(data['fare'])
            
            elif event_type == 'ride_booked':
                location = data.get('pickup_location', {})
                if 'city' in location:
                    self.analytics_data['geographic_data'][location['city']] += 1
            
            elif event_type == 'user_action':
                action = data.get('action', 'unknown')
                self.analytics_data['user_behavior'][action] += 1
        
        except Exception as e:
            print(f"Error recording analytics: {e}")
    
    def get_business_intelligence_dashboard(self) -> Dict:
        """Get business intelligence dashboard data"""
        current_date = datetime.now().date()
        
        # Calculate date ranges
        last_7_days = [(current_date - timedelta(days=i)).isoformat() for i in range(7)]
        last_30_days = [(current_date - timedelta(days=i)).isoformat() for i in range(30)]
        
        # Daily active users trend
        dau_trend = [
            self.analytics_data['daily_active_users'].get(date, 0)
            for date in last_7_days
        ]
        
        # Revenue trend
        revenue_trend = [
            self.analytics_data['revenue_metrics'].get(date, 0.0)
            for date in last_7_days
        ]
        
        # Ride statistics
        rides_trend = [
            self.analytics_data['ride_statistics'].get(date, 0)
            for date in last_7_days
        ]
        
        return {
            'user_metrics': {
                'daily_active_users': sum(dau_trend),
                'dau_trend_7d': dau_trend,
                'total_users_30d': sum(
                    self.analytics_data['daily_active_users'].get(date, 0)
                    for date in last_30_days
                )
            },
            'revenue_metrics': {
                'daily_revenue': sum(revenue_trend),
                'revenue_trend_7d': revenue_trend,
                'total_revenue_30d': sum(
                    self.analytics_data['revenue_metrics'].get(date, 0.0)
                    for date in last_30_days
                ),
                'average_ride_value': sum(revenue_trend) / max(1, sum(rides_trend))
            },
            'ride_metrics': {
                'daily_rides': sum(rides_trend),
                'rides_trend_7d': rides_trend,
                'total_rides_30d': sum(
                    self.analytics_data['ride_statistics'].get(date, 0)
                    for date in last_30_days
                )
            },
            'geographic_distribution': dict(
                sorted(self.analytics_data['geographic_data'].items(), 
                      key=lambda x: x[1], reverse=True)[:10]
            ),
            'user_behavior': dict(
                sorted(self.analytics_data['user_behavior'].items(), 
                      key=lambda x: x[1], reverse=True)[:10]
            )
        }
    
    def get_load_balancer_config(self) -> Dict:
        """Get load balancer configuration for deployment"""
        return {
            'nginx_config': '''
upstream taxigo_backend {
    least_conn;
    server backend1:5000 max_fails=3 fail_timeout=30s;
    server backend2:5000 max_fails=3 fail_timeout=30s;
    server backend3:5000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name api.taxigopro.com;
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
    location / {
        proxy_pass http://taxigo_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
    
    location /health {
        access_log off;
        proxy_pass http://taxigo_backend/api/health;
    }
}
            ''',
            'docker_compose': '''
version: '3.8'
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - backend1
      - backend2
      - backend3
  
  backend1:
    build: .
    environment:
      - FLASK_ENV=production
      - DATABASE_URL=postgresql://user:pass@db:5432/taxigo
    depends_on:
      - db
      - redis
  
  backend2:
    build: .
    environment:
      - FLASK_ENV=production
      - DATABASE_URL=postgresql://user:pass@db:5432/taxigo
    depends_on:
      - db
      - redis
  
  backend3:
    build: .
    environment:
      - FLASK_ENV=production
      - DATABASE_URL=postgresql://user:pass@db:5432/taxigo
    depends_on:
      - db
      - redis
  
  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=taxigo
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
            '''
        }
    
    def start_monitoring(self):
        """Start background monitoring tasks"""
        def monitoring_worker():
            while True:
                try:
                    # Collect and store metrics
                    metric = self.collect_system_metrics()
                    if metric:
                        self.metrics_history.append(metric)
                    
                    # Check for alerts
                    alerts = self.get_active_alerts()
                    for alert in alerts:
                        alert_key = f"{alert['type']}_{alert['severity']}"
                        last_alert = self.last_alerts.get(alert_key)
                        now = datetime.now()
                        
                        # Send alert if none sent in last 15 minutes
                        if not last_alert or now - last_alert > timedelta(minutes=15):
                            self.send_alert(
                                alert_type=alert['type'],
                                message=alert['message'],
                                severity=alert['severity']
                            )
                            self.last_alerts[alert_key] = now
                    
                    time.sleep(60)  # Collect metrics every minute
                
                except Exception as e:
                    print(f"Monitoring error: {e}")
                    time.sleep(60)
        
        # Start background thread
        threading.Thread(target=monitoring_worker, daemon=True).start()

# Global infrastructure manager instance
infrastructure_manager = InfrastructureManager()

