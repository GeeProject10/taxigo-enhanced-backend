"""
Enterprise Security Manager for TaxiGo Pro
Handles JWT authentication, rate limiting, input validation, and security monitoring
"""

import jwt
import time
import hashlib
import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from functools import wraps
from flask import request, jsonify, current_app
import threading
import os
from collections import defaultdict, deque

class SecurityManager:
    def __init__(self):
        # JWT Configuration
        self.jwt_secret_key = os.getenv('JWT_SECRET_KEY', 'taxigo_pro_jwt_secret_2024')
        self.jwt_algorithm = 'HS256'
        self.access_token_expiry = timedelta(hours=1)
        self.refresh_token_expiry = timedelta(days=30)
        
        # Rate Limiting
        self.rate_limits = defaultdict(lambda: deque())
        self.rate_limit_lock = threading.Lock()
        
        # Security Monitoring
        self.security_events = []
        self.blocked_ips = set()
        self.suspicious_activities = defaultdict(int)
        
        # Input Validation Patterns
        self.validation_patterns = {
            'email': re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
            'phone': re.compile(r'^\+?[1-9]\d{1,14}$'),
            'password': re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'),
            'ride_id': re.compile(r'^ride_[a-zA-Z0-9_-]+$'),
            'user_id': re.compile(r'^\d+$'),
            'coordinates': re.compile(r'^-?([1-8]?\d(\.\d+)?|90(\.0+)?)$'),
            'amount': re.compile(r'^\d+(\.\d{1,2})?$')
        }
        
        # Start security monitoring
        self.start_security_monitoring()
    
    def generate_tokens(self, user_data: Dict) -> Dict:
        """Generate JWT access and refresh tokens"""
        try:
            current_time = datetime.utcnow()
            
            # Access token payload
            access_payload = {
                'user_id': user_data['id'],
                'email': user_data['email'],
                'user_type': user_data.get('user_type', 'passenger'),
                'iat': current_time,
                'exp': current_time + self.access_token_expiry,
                'type': 'access'
            }
            
            # Refresh token payload
            refresh_payload = {
                'user_id': user_data['id'],
                'email': user_data['email'],
                'iat': current_time,
                'exp': current_time + self.refresh_token_expiry,
                'type': 'refresh'
            }
            
            # Generate tokens
            access_token = jwt.encode(access_payload, self.jwt_secret_key, algorithm=self.jwt_algorithm)
            refresh_token = jwt.encode(refresh_payload, self.jwt_secret_key, algorithm=self.jwt_algorithm)
            
            return {
                'success': True,
                'access_token': access_token,
                'refresh_token': refresh_token,
                'expires_in': int(self.access_token_expiry.total_seconds()),
                'token_type': 'Bearer'
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def verify_token(self, token: str, token_type: str = 'access') -> Dict:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(token, self.jwt_secret_key, algorithms=[self.jwt_algorithm])
            
            # Check token type
            if payload.get('type') != token_type:
                return {
                    'success': False,
                    'error': 'Invalid token type'
                }
            
            # Check expiration
            if datetime.utcnow() > datetime.fromtimestamp(payload['exp']):
                return {
                    'success': False,
                    'error': 'Token expired'
                }
            
            return {
                'success': True,
                'payload': payload
            }
        
        except jwt.ExpiredSignatureError:
            return {
                'success': False,
                'error': 'Token expired'
            }
        except jwt.InvalidTokenError:
            return {
                'success': False,
                'error': 'Invalid token'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def refresh_access_token(self, refresh_token: str) -> Dict:
        """Generate new access token using refresh token"""
        try:
            # Verify refresh token
            verification = self.verify_token(refresh_token, 'refresh')
            if not verification['success']:
                return verification
            
            payload = verification['payload']
            
            # Generate new access token
            user_data = {
                'id': payload['user_id'],
                'email': payload['email'],
                'user_type': payload.get('user_type', 'passenger')
            }
            
            tokens = self.generate_tokens(user_data)
            
            return {
                'success': True,
                'access_token': tokens['access_token'],
                'expires_in': tokens['expires_in']
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def require_auth(self, required_roles: List[str] = None):
        """Decorator for routes requiring authentication"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                # Get token from header
                auth_header = request.headers.get('Authorization')
                if not auth_header or not auth_header.startswith('Bearer '):
                    return jsonify({
                        'success': False,
                        'error': 'Missing or invalid authorization header'
                    }), 401
                
                token = auth_header.split(' ')[1]
                
                # Verify token
                verification = self.verify_token(token)
                if not verification['success']:
                    return jsonify({
                        'success': False,
                        'error': verification['error']
                    }), 401
                
                payload = verification['payload']
                
                # Check user role if required
                if required_roles:
                    user_type = payload.get('user_type', 'passenger')
                    if user_type not in required_roles:
                        return jsonify({
                            'success': False,
                            'error': 'Insufficient permissions'
                        }), 403
                
                # Add user info to request context
                request.current_user = payload
                
                return f(*args, **kwargs)
            
            return decorated_function
        return decorator
    
    def rate_limit(self, max_requests: int = 100, window_minutes: int = 15):
        """Decorator for rate limiting API endpoints"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                # Get client identifier
                client_ip = request.remote_addr
                user_agent = request.headers.get('User-Agent', '')
                client_id = hashlib.md5(f"{client_ip}:{user_agent}".encode()).hexdigest()
                
                # Check if IP is blocked
                if client_ip in self.blocked_ips:
                    self.log_security_event('blocked_ip_attempt', {
                        'ip': client_ip,
                        'endpoint': request.endpoint,
                        'timestamp': datetime.now().isoformat()
                    })
                    return jsonify({
                        'success': False,
                        'error': 'IP address blocked due to suspicious activity'
                    }), 429
                
                current_time = time.time()
                window_start = current_time - (window_minutes * 60)
                
                with self.rate_limit_lock:
                    # Clean old requests
                    client_requests = self.rate_limits[client_id]
                    while client_requests and client_requests[0] < window_start:
                        client_requests.popleft()
                    
                    # Check rate limit
                    if len(client_requests) >= max_requests:
                        # Log rate limit violation
                        self.log_security_event('rate_limit_exceeded', {
                            'client_id': client_id,
                            'ip': client_ip,
                            'endpoint': request.endpoint,
                            'requests_count': len(client_requests),
                            'timestamp': datetime.now().isoformat()
                        })
                        
                        # Increase suspicious activity counter
                        self.suspicious_activities[client_ip] += 1
                        
                        # Block IP if too many violations
                        if self.suspicious_activities[client_ip] >= 5:
                            self.blocked_ips.add(client_ip)
                            self.log_security_event('ip_blocked', {
                                'ip': client_ip,
                                'reason': 'Multiple rate limit violations',
                                'timestamp': datetime.now().isoformat()
                            })
                        
                        return jsonify({
                            'success': False,
                            'error': 'Rate limit exceeded. Please try again later.',
                            'retry_after': window_minutes * 60
                        }), 429
                    
                    # Add current request
                    client_requests.append(current_time)
                
                return f(*args, **kwargs)
            
            return decorated_function
        return decorator
    
    def validate_input(self, data: Dict, validation_rules: Dict) -> Dict:
        """Validate input data against rules"""
        errors = {}
        
        for field, rules in validation_rules.items():
            value = data.get(field)
            
            # Check required fields
            if rules.get('required', False) and not value:
                errors[field] = 'This field is required'
                continue
            
            if value is None:
                continue
            
            # Check data type
            expected_type = rules.get('type')
            if expected_type and not isinstance(value, expected_type):
                errors[field] = f'Expected {expected_type.__name__}, got {type(value).__name__}'
                continue
            
            # Check string length
            if isinstance(value, str):
                min_length = rules.get('min_length')
                max_length = rules.get('max_length')
                
                if min_length and len(value) < min_length:
                    errors[field] = f'Minimum length is {min_length} characters'
                    continue
                
                if max_length and len(value) > max_length:
                    errors[field] = f'Maximum length is {max_length} characters'
                    continue
            
            # Check numeric ranges
            if isinstance(value, (int, float)):
                min_value = rules.get('min_value')
                max_value = rules.get('max_value')
                
                if min_value is not None and value < min_value:
                    errors[field] = f'Minimum value is {min_value}'
                    continue
                
                if max_value is not None and value > max_value:
                    errors[field] = f'Maximum value is {max_value}'
                    continue
            
            # Check pattern matching
            pattern_name = rules.get('pattern')
            if pattern_name and isinstance(value, str):
                pattern = self.validation_patterns.get(pattern_name)
                if pattern and not pattern.match(value):
                    errors[field] = f'Invalid {pattern_name} format'
                    continue
            
            # Custom validation function
            custom_validator = rules.get('validator')
            if custom_validator and callable(custom_validator):
                try:
                    if not custom_validator(value):
                        errors[field] = rules.get('validator_message', 'Invalid value')
                except Exception as e:
                    errors[field] = f'Validation error: {str(e)}'
        
        return {
            'success': len(errors) == 0,
            'errors': errors
        }
    
    def sanitize_input(self, data: Any) -> Any:
        """Sanitize input data to prevent injection attacks"""
        if isinstance(data, dict):
            return {key: self.sanitize_input(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self.sanitize_input(item) for item in data]
        elif isinstance(data, str):
            # Remove potentially dangerous characters
            sanitized = data.strip()
            
            # Remove SQL injection patterns
            sql_patterns = [
                r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)",
                r"(--|#|/\*|\*/)",
                r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
                r"(\bOR\s+\d+\s*=\s*\d+)",
                r"(\'\s*(OR|AND)\s*\')",
            ]
            
            for pattern in sql_patterns:
                sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
            
            # Remove XSS patterns
            xss_patterns = [
                r"<script[^>]*>.*?</script>",
                r"javascript:",
                r"on\w+\s*=",
                r"<iframe[^>]*>.*?</iframe>",
            ]
            
            for pattern in xss_patterns:
                sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
            
            return sanitized
        else:
            return data
    
    def log_security_event(self, event_type: str, data: Dict):
        """Log security events for monitoring"""
        event = {
            'event_type': event_type,
            'timestamp': datetime.now().isoformat(),
            'data': data,
            'severity': self.get_event_severity(event_type)
        }
        
        self.security_events.append(event)
        
        # Keep only last 1000 events
        if len(self.security_events) > 1000:
            self.security_events = self.security_events[-1000:]
        
        # Log to console (in production, send to logging service)
        print(f"SECURITY EVENT [{event['severity']}]: {event_type} - {data}")
    
    def get_event_severity(self, event_type: str) -> str:
        """Get severity level for security events"""
        high_severity = [
            'ip_blocked', 'multiple_failed_logins', 'sql_injection_attempt',
            'xss_attempt', 'unauthorized_access_attempt'
        ]
        
        medium_severity = [
            'rate_limit_exceeded', 'invalid_token_usage', 'suspicious_activity'
        ]
        
        if event_type in high_severity:
            return 'HIGH'
        elif event_type in medium_severity:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def get_security_stats(self) -> Dict:
        """Get security statistics and monitoring data"""
        current_time = datetime.now()
        last_24h = current_time - timedelta(hours=24)
        
        # Count events in last 24 hours
        recent_events = [
            event for event in self.security_events
            if datetime.fromisoformat(event['timestamp']) > last_24h
        ]
        
        event_counts = defaultdict(int)
        severity_counts = defaultdict(int)
        
        for event in recent_events:
            event_counts[event['event_type']] += 1
            severity_counts[event['severity']] += 1
        
        return {
            'total_events_24h': len(recent_events),
            'event_types': dict(event_counts),
            'severity_breakdown': dict(severity_counts),
            'blocked_ips_count': len(self.blocked_ips),
            'suspicious_ips_count': len(self.suspicious_activities),
            'rate_limit_clients': len(self.rate_limits),
            'recent_high_severity_events': [
                event for event in recent_events[-10:]
                if event['severity'] == 'HIGH'
            ]
        }
    
    def unblock_ip(self, ip_address: str) -> Dict:
        """Manually unblock an IP address"""
        try:
            if ip_address in self.blocked_ips:
                self.blocked_ips.remove(ip_address)
                
                # Reset suspicious activity counter
                if ip_address in self.suspicious_activities:
                    del self.suspicious_activities[ip_address]
                
                self.log_security_event('ip_unblocked', {
                    'ip': ip_address,
                    'timestamp': datetime.now().isoformat()
                })
                
                return {
                    'success': True,
                    'message': f'IP {ip_address} has been unblocked'
                }
            else:
                return {
                    'success': False,
                    'error': 'IP address is not blocked'
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def start_security_monitoring(self):
        """Start background security monitoring tasks"""
        def security_worker():
            while True:
                try:
                    current_time = time.time()
                    
                    # Clean old rate limit data (every 5 minutes)
                    with self.rate_limit_lock:
                        for client_id in list(self.rate_limits.keys()):
                            client_requests = self.rate_limits[client_id]
                            # Remove requests older than 1 hour
                            cutoff_time = current_time - 3600
                            while client_requests and client_requests[0] < cutoff_time:
                                client_requests.popleft()
                            
                            # Remove empty entries
                            if not client_requests:
                                del self.rate_limits[client_id]
                    
                    # Reset suspicious activity counters (daily)
                    reset_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    if datetime.now() - reset_time < timedelta(minutes=5):
                        self.suspicious_activities.clear()
                    
                    time.sleep(300)  # Run every 5 minutes
                
                except Exception as e:
                    print(f"Security monitoring error: {e}")
                    time.sleep(60)
        
        # Start background thread
        threading.Thread(target=security_worker, daemon=True).start()

# Global security manager instance
security_manager = SecurityManager()

