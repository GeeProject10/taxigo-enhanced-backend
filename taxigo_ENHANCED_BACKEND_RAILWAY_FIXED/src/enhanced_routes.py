"""
Enhanced API Routes for TaxiGo Pro
Includes security, monitoring, and enterprise features
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import time
import json

from .security_manager import security_manager
from .infrastructure_manager import infrastructure_manager
from .payment_processor import payment_processor
from .websocket_manager import websocket_manager
from .gps_tracker import gps_tracker
from .push_notifications import push_notification_service

# Create blueprint for enhanced routes
enhanced_routes = Blueprint('enhanced_routes', __name__)

# Middleware for request monitoring
@enhanced_routes.before_request
def before_request():
    request.start_time = time.time()
    infrastructure_manager.current_connections += 1

@enhanced_routes.after_request
def after_request(response):
    # Calculate response time
    response_time = (time.time() - request.start_time) * 1000
    
    # Record metrics
    infrastructure_manager.record_request_metrics(
        response_time=response_time,
        endpoint=request.endpoint,
        status_code=response.status_code
    )
    
    infrastructure_manager.current_connections -= 1
    
    # Add security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    return response

# Enhanced Authentication Routes
@enhanced_routes.route('/api/auth/register', methods=['POST'])
@security_manager.rate_limit(max_requests=5, window_minutes=15)  # Prevent spam registration
def enhanced_register():
    try:
        data = request.get_json()
        
        # Sanitize input
        data = security_manager.sanitize_input(data)
        
        # Validate input
        validation_rules = {
            'name': {
                'required': True,
                'type': str,
                'min_length': 2,
                'max_length': 100
            },
            'email': {
                'required': True,
                'type': str,
                'pattern': 'email'
            },
            'phone': {
                'required': True,
                'type': str,
                'pattern': 'phone'
            },
            'password': {
                'required': True,
                'type': str,
                'min_length': 8,
                'pattern': 'password'
            },
            'user_type': {
                'required': True,
                'type': str,
                'validator': lambda x: x in ['passenger', 'driver', 'business']
            }
        }
        
        validation_result = security_manager.validate_input(data, validation_rules)
        if not validation_result['success']:
            return jsonify({
                'success': False,
                'errors': validation_result['errors']
            }), 400
        
        # Check if user already exists (implement your user check logic here)
        # existing_user = check_existing_user(data['email'])
        # if existing_user:
        #     return jsonify({
        #         'success': False,
        #         'error': 'User already exists'
        #     }), 409
        
        # Create user (implement your user creation logic here)
        user_data = {
            'id': 123,  # Replace with actual user ID from database
            'email': data['email'],
            'user_type': data['user_type'],
            'name': data['name']
        }
        
        # Generate JWT tokens
        tokens = security_manager.generate_tokens(user_data)
        
        if tokens['success']:
            # Record analytics
            infrastructure_manager.record_business_analytics('user_registration', {
                'user_type': data['user_type'],
                'timestamp': datetime.now().isoformat()
            })
            
            # Send welcome notification
            push_notification_service.send_welcome_notification(user_data['id'])
            
            return jsonify({
                'success': True,
                'message': 'User registered successfully',
                'user': {
                    'id': user_data['id'],
                    'email': user_data['email'],
                    'name': user_data['name'],
                    'user_type': user_data['user_type']
                },
                'tokens': {
                    'access_token': tokens['access_token'],
                    'refresh_token': tokens['refresh_token'],
                    'expires_in': tokens['expires_in']
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to generate authentication tokens'
            }), 500
    
    except Exception as e:
        infrastructure_manager.log_error(
            error_type='registration_error',
            message=str(e),
            endpoint='/api/auth/register',
            severity='HIGH'
        )
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@enhanced_routes.route('/api/auth/login', methods=['POST'])
@security_manager.rate_limit(max_requests=10, window_minutes=15)  # Prevent brute force
def enhanced_login():
    try:
        data = request.get_json()
        
        # Sanitize input
        data = security_manager.sanitize_input(data)
        
        # Validate input
        validation_rules = {
            'email': {
                'required': True,
                'type': str,
                'pattern': 'email'
            },
            'password': {
                'required': True,
                'type': str,
                'min_length': 1
            }
        }
        
        validation_result = security_manager.validate_input(data, validation_rules)
        if not validation_result['success']:
            return jsonify({
                'success': False,
                'errors': validation_result['errors']
            }), 400
        
        # Authenticate user (implement your authentication logic here)
        # user = authenticate_user(data['email'], data['password'])
        # if not user:
        #     security_manager.log_security_event('failed_login_attempt', {
        #         'email': data['email'],
        #         'ip': request.remote_addr,
        #         'timestamp': datetime.now().isoformat()
        #     })
        #     return jsonify({
        #         'success': False,
        #         'error': 'Invalid credentials'
        #     }), 401
        
        # Mock user data (replace with actual authentication)
        user_data = {
            'id': 123,
            'email': data['email'],
            'user_type': 'passenger',  # Get from database
            'name': 'Test User'
        }
        
        # Generate JWT tokens
        tokens = security_manager.generate_tokens(user_data)
        
        if tokens['success']:
            # Record analytics
            infrastructure_manager.record_business_analytics('user_login', {
                'user_id': user_data['id'],
                'user_type': user_data['user_type'],
                'timestamp': datetime.now().isoformat()
            })
            
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'user': {
                    'id': user_data['id'],
                    'email': user_data['email'],
                    'name': user_data['name'],
                    'user_type': user_data['user_type']
                },
                'tokens': {
                    'access_token': tokens['access_token'],
                    'refresh_token': tokens['refresh_token'],
                    'expires_in': tokens['expires_in']
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to generate authentication tokens'
            }), 500
    
    except Exception as e:
        infrastructure_manager.log_error(
            error_type='login_error',
            message=str(e),
            endpoint='/api/auth/login',
            severity='HIGH'
        )
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@enhanced_routes.route('/api/auth/refresh', methods=['POST'])
@security_manager.rate_limit(max_requests=20, window_minutes=15)
def refresh_token():
    try:
        data = request.get_json()
        refresh_token = data.get('refresh_token')
        
        if not refresh_token:
            return jsonify({
                'success': False,
                'error': 'Refresh token required'
            }), 400
        
        # Refresh access token
        result = security_manager.refresh_access_token(refresh_token)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 401
    
    except Exception as e:
        infrastructure_manager.log_error(
            error_type='token_refresh_error',
            message=str(e),
            endpoint='/api/auth/refresh',
            severity='MEDIUM'
        )
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

# Enhanced Payment Routes
@enhanced_routes.route('/api/payments/create-intent', methods=['POST'])
@security_manager.require_auth()
@security_manager.rate_limit(max_requests=50, window_minutes=15)
def create_payment_intent():
    try:
        data = request.get_json()
        user_id = request.current_user['user_id']
        
        # Sanitize and validate input
        data = security_manager.sanitize_input(data)
        
        validation_rules = {
            'amount': {
                'required': True,
                'type': (int, float),
                'min_value': 0.50,  # Minimum 50 cents
                'max_value': 1000.00  # Maximum $1000
            },
            'currency': {
                'required': False,
                'type': str,
                'validator': lambda x: x in ['AUD', 'USD', 'EUR', 'GBP']
            },
            'ride_id': {
                'required': False,
                'type': str,
                'pattern': 'ride_id'
            }
        }
        
        validation_result = security_manager.validate_input(data, validation_rules)
        if not validation_result['success']:
            return jsonify({
                'success': False,
                'errors': validation_result['errors']
            }), 400
        
        # Create payment intent
        payment_data = {
            'amount': data['amount'],
            'currency': data.get('currency', 'AUD'),
            'user_id': user_id,
            'ride_id': data.get('ride_id'),
            'metadata': {
                'user_id': str(user_id),
                'timestamp': datetime.now().isoformat()
            }
        }
        
        result = payment_processor.create_payment_intent(payment_data)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    
    except Exception as e:
        infrastructure_manager.log_error(
            error_type='payment_intent_error',
            message=str(e),
            endpoint='/api/payments/create-intent',
            user_id=str(request.current_user.get('user_id')),
            severity='HIGH'
        )
        return jsonify({
            'success': False,
            'error': 'Payment processing error'
        }), 500

@enhanced_routes.route('/api/payments/split', methods=['POST'])
@security_manager.require_auth()
@security_manager.rate_limit(max_requests=20, window_minutes=15)
def process_split_payment():
    try:
        data = request.get_json()
        user_id = request.current_user['user_id']
        
        # Sanitize input
        data = security_manager.sanitize_input(data)
        
        # Process split payment
        result = payment_processor.process_split_payment(data, user_id)
        
        if result['success']:
            # Send notifications to all participants
            for participant in data.get('participants', []):
                push_notification_service.send_payment_notification(
                    participant['user_id'],
                    'split_payment_processed',
                    {
                        'amount': participant['amount'],
                        'ride_id': data.get('ride_id')
                    }
                )
            
            return jsonify(result)
        else:
            return jsonify(result), 400
    
    except Exception as e:
        infrastructure_manager.log_error(
            error_type='split_payment_error',
            message=str(e),
            endpoint='/api/payments/split',
            user_id=str(request.current_user.get('user_id')),
            severity='HIGH'
        )
        return jsonify({
            'success': False,
            'error': 'Split payment processing error'
        }), 500

# Enhanced GPS and Location Routes
@enhanced_routes.route('/api/gps/update-location', methods=['POST'])
@security_manager.require_auth(['driver'])
@security_manager.rate_limit(max_requests=200, window_minutes=15)  # High limit for frequent updates
def update_driver_location():
    try:
        data = request.get_json()
        user_id = request.current_user['user_id']
        
        # Sanitize input
        data = security_manager.sanitize_input(data)
        
        # Validate GPS coordinates
        validation_rules = {
            'latitude': {
                'required': True,
                'type': (int, float),
                'min_value': -90.0,
                'max_value': 90.0
            },
            'longitude': {
                'required': True,
                'type': (int, float),
                'min_value': -180.0,
                'max_value': 180.0
            },
            'accuracy': {
                'required': False,
                'type': (int, float),
                'min_value': 0.0
            },
            'heading': {
                'required': False,
                'type': (int, float),
                'min_value': 0.0,
                'max_value': 360.0
            },
            'speed': {
                'required': False,
                'type': (int, float),
                'min_value': 0.0
            }
        }
        
        validation_result = security_manager.validate_input(data, validation_rules)
        if not validation_result['success']:
            return jsonify({
                'success': False,
                'errors': validation_result['errors']
            }), 400
        
        # Update location
        location_data = {
            'user_id': user_id,
            'latitude': data['latitude'],
            'longitude': data['longitude'],
            'accuracy': data.get('accuracy', 10.0),
            'heading': data.get('heading'),
            'speed': data.get('speed'),
            'timestamp': datetime.now()
        }
        
        result = gps_tracker.update_location(location_data)
        
        if result['success']:
            # Broadcast location update via WebSocket
            websocket_manager.broadcast_location_update(user_id, location_data)
            
            return jsonify(result)
        else:
            return jsonify(result), 400
    
    except Exception as e:
        infrastructure_manager.log_error(
            error_type='gps_update_error',
            message=str(e),
            endpoint='/api/gps/update-location',
            user_id=str(request.current_user.get('user_id')),
            severity='MEDIUM'
        )
        return jsonify({
            'success': False,
            'error': 'Location update error'
        }), 500

@enhanced_routes.route('/api/gps/nearby-drivers', methods=['POST'])
@security_manager.require_auth(['passenger', 'business'])
@security_manager.rate_limit(max_requests=30, window_minutes=15)
def find_nearby_drivers():
    try:
        data = request.get_json()
        user_id = request.current_user['user_id']
        
        # Sanitize and validate input
        data = security_manager.sanitize_input(data)
        
        validation_rules = {
            'latitude': {
                'required': True,
                'type': (int, float),
                'min_value': -90.0,
                'max_value': 90.0
            },
            'longitude': {
                'required': True,
                'type': (int, float),
                'min_value': -180.0,
                'max_value': 180.0
            },
            'radius_km': {
                'required': False,
                'type': (int, float),
                'min_value': 0.5,
                'max_value': 50.0
            }
        }
        
        validation_result = security_manager.validate_input(data, validation_rules)
        if not validation_result['success']:
            return jsonify({
                'success': False,
                'errors': validation_result['errors']
            }), 400
        
        # Find nearby drivers
        search_params = {
            'latitude': data['latitude'],
            'longitude': data['longitude'],
            'radius_km': data.get('radius_km', 5.0),
            'max_results': 20
        }
        
        result = gps_tracker.find_nearby_drivers(search_params)
        
        return jsonify(result)
    
    except Exception as e:
        infrastructure_manager.log_error(
            error_type='nearby_drivers_error',
            message=str(e),
            endpoint='/api/gps/nearby-drivers',
            user_id=str(request.current_user.get('user_id')),
            severity='MEDIUM'
        )
        return jsonify({
            'success': False,
            'error': 'Driver search error'
        }), 500

# Enhanced Notification Routes
@enhanced_routes.route('/api/notifications/register-device', methods=['POST'])
@security_manager.require_auth()
@security_manager.rate_limit(max_requests=10, window_minutes=15)
def register_device_token():
    try:
        data = request.get_json()
        user_id = request.current_user['user_id']
        
        # Sanitize input
        data = security_manager.sanitize_input(data)
        
        validation_rules = {
            'device_token': {
                'required': True,
                'type': str,
                'min_length': 10
            },
            'platform': {
                'required': True,
                'type': str,
                'validator': lambda x: x in ['ios', 'android', 'web']
            }
        }
        
        validation_result = security_manager.validate_input(data, validation_rules)
        if not validation_result['success']:
            return jsonify({
                'success': False,
                'errors': validation_result['errors']
            }), 400
        
        # Register device token
        result = push_notification_service.register_device_token(
            user_id=user_id,
            device_token=data['device_token'],
            platform=data['platform']
        )
        
        return jsonify(result)
    
    except Exception as e:
        infrastructure_manager.log_error(
            error_type='device_registration_error',
            message=str(e),
            endpoint='/api/notifications/register-device',
            user_id=str(request.current_user.get('user_id')),
            severity='MEDIUM'
        )
        return jsonify({
            'success': False,
            'error': 'Device registration error'
        }), 500

# Enhanced System Monitoring Routes
@enhanced_routes.route('/api/admin/dashboard', methods=['GET'])
@security_manager.require_auth(['admin'])
@security_manager.rate_limit(max_requests=60, window_minutes=15)
def admin_dashboard():
    try:
        # Get comprehensive system data
        performance_data = infrastructure_manager.get_performance_dashboard()
        security_data = security_manager.get_security_stats()
        business_data = infrastructure_manager.get_business_intelligence_dashboard()
        
        return jsonify({
            'success': True,
            'data': {
                'performance': performance_data,
                'security': security_data,
                'business_intelligence': business_data,
                'timestamp': datetime.now().isoformat()
            }
        })
    
    except Exception as e:
        infrastructure_manager.log_error(
            error_type='admin_dashboard_error',
            message=str(e),
            endpoint='/api/admin/dashboard',
            user_id=str(request.current_user.get('user_id')),
            severity='MEDIUM'
        )
        return jsonify({
            'success': False,
            'error': 'Dashboard data error'
        }), 500

@enhanced_routes.route('/api/health/enhanced', methods=['GET'])
def enhanced_health_check():
    """Enhanced health check with detailed system status"""
    try:
        # Basic health check
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '2.0.0',
            'environment': 'production'
        }
        
        # Add system metrics
        performance_data = infrastructure_manager.get_performance_dashboard()
        health_data['system_metrics'] = performance_data['current_metrics']
        health_data['system_health'] = performance_data['system_health']['status']
        
        # Add feature status
        health_data['features'] = {
            'authentication': 'operational',
            'payments': 'operational',
            'gps_tracking': 'operational',
            'notifications': 'operational',
            'websockets': 'operational',
            'monitoring': 'operational'
        }
        
        return jsonify(health_data)
    
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

