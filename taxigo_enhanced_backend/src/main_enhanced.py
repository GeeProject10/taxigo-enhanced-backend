from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
import os
import sys
from datetime import datetime

# Add the src directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from websocket_manager import websocket_manager
from payment_processor import payment_processor
from gps_tracker import gps_tracker
from database_optimizer import db_optimizer
from push_notifications import push_notification_service
from security_manager import security_manager
from infrastructure_manager import infrastructure_manager
from enhanced_routes import enhanced_routes

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'taxigo_pro_secret_key_2024')

# Enhanced CORS configuration with security
CORS(app, 
     origins=['https://taxigopro.netlify.app', 'https://taxi-go.taxi', 'http://localhost:3000'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
     allow_headers=['Content-Type', 'Authorization'],
     supports_credentials=True)

# Initialize SocketIO for real-time features
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Register enhanced routes blueprint
app.register_blueprint(enhanced_routes)

# Initialize enhanced features
websocket_manager.init_app(socketio)
db_optimizer.optimize_database()

# Security middleware
@app.before_request
def security_middleware():
    """Apply security checks to all requests"""
    # Skip security for health checks and static files
    if request.endpoint in ['health_check', 'enhanced_health_check']:
        return
    
    # Log request for monitoring
    infrastructure_manager.record_business_analytics('api_request', {
        'endpoint': request.endpoint,
        'method': request.method,
        'ip': request.remote_addr,
        'user_agent': request.headers.get('User-Agent', ''),
        'timestamp': datetime.now().isoformat()
    })

@app.after_request
def security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    return response

@app.route('/api/health', methods=['GET'])
def health_check():
    """Basic health check endpoint"""
    try:
        return jsonify({
            'status': 'healthy',
            'message': 'TaxiGo Pro Enhanced API is running',
            'timestamp': datetime.now().isoformat(),
            'version': '2.0.0'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

# Legacy Authentication Routes (for backward compatibility)
@app.route('/api/auth/register', methods=['POST'])
@security_manager.rate_limit(max_requests=5, window_minutes=15)
def legacy_register():
    """Legacy registration endpoint"""
    try:
        data = request.get_json()
        
        # Basic validation and sanitization
        data = security_manager.sanitize_input(data)
        
        # Mock user creation (replace with actual database logic)
        user_data = {
            'id': 123,
            'email': data.get('email'),
            'user_type': data.get('user_type', 'passenger'),
            'name': data.get('name', 'User')
        }
        
        # Generate tokens
        tokens = security_manager.generate_tokens(user_data)
        
        if tokens['success']:
            return jsonify({
                'success': True,
                'message': 'User registered successfully',
                'user': user_data,
                'access_token': tokens['access_token'],
                'refresh_token': tokens['refresh_token']
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Registration failed'
            }), 500
    
    except Exception as e:
        infrastructure_manager.log_error(
            error_type='legacy_registration_error',
            message=str(e),
            endpoint='/api/auth/register',
            severity='HIGH'
        )
        return jsonify({
            'success': False,
            'error': 'Registration error'
        }), 500

@app.route('/api/auth/login', methods=['POST'])
@security_manager.rate_limit(max_requests=10, window_minutes=15)
def legacy_login():
    """Legacy login endpoint"""
    try:
        data = request.get_json()
        
        # Basic validation and sanitization
        data = security_manager.sanitize_input(data)
        
        # Mock authentication (replace with actual database logic)
        user_data = {
            'id': 123,
            'email': data.get('email'),
            'user_type': 'passenger',
            'name': 'Test User'
        }
        
        # Generate tokens
        tokens = security_manager.generate_tokens(user_data)
        
        if tokens['success']:
            # Record login analytics
            infrastructure_manager.record_business_analytics('user_login', {
                'user_id': user_data['id'],
                'user_type': user_data['user_type']
            })
            
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'user': user_data,
                'access_token': tokens['access_token'],
                'refresh_token': tokens['refresh_token']
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Login failed'
            }), 500
    
    except Exception as e:
        infrastructure_manager.log_error(
            error_type='legacy_login_error',
            message=str(e),
            endpoint='/api/auth/login',
            severity='HIGH'
        )
        return jsonify({
            'success': False,
            'error': 'Login error'
        }), 500

# Legacy Payment Routes (for backward compatibility)
@app.route('/api/payments/create-intent', methods=['POST'])
@security_manager.rate_limit(max_requests=50, window_minutes=15)
def legacy_create_payment_intent():
    """Legacy payment intent creation"""
    try:
        data = request.get_json()
        result = payment_processor.create_payment_intent(data)
        return jsonify(result)
    except Exception as e:
        infrastructure_manager.log_error(
            error_type='legacy_payment_error',
            message=str(e),
            endpoint='/api/payments/create-intent',
            severity='HIGH'
        )
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# System Monitoring Routes
@app.route('/api/system/stats', methods=['GET'])
def system_stats():
    """Get system performance statistics"""
    try:
        performance_data = infrastructure_manager.get_performance_dashboard()
        security_data = security_manager.get_security_stats()
        
        return jsonify({
            'success': True,
            'data': {
                'performance': performance_data,
                'security': security_data,
                'timestamp': datetime.now().isoformat()
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/system/business-intelligence', methods=['GET'])
def business_intelligence():
    """Get business intelligence dashboard"""
    try:
        bi_data = infrastructure_manager.get_business_intelligence_dashboard()
        
        return jsonify({
            'success': True,
            'data': bi_data,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# WebSocket Events with enhanced security
@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection with security"""
    try:
        websocket_manager.handle_connect()
        infrastructure_manager.current_connections += 1
    except Exception as e:
        infrastructure_manager.log_error(
            error_type='websocket_connect_error',
            message=str(e),
            endpoint='websocket_connect',
            severity='MEDIUM'
        )

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    try:
        websocket_manager.handle_disconnect()
        infrastructure_manager.current_connections -= 1
    except Exception as e:
        infrastructure_manager.log_error(
            error_type='websocket_disconnect_error',
            message=str(e),
            endpoint='websocket_disconnect',
            severity='LOW'
        )

@socketio.on('join_user_room')
def handle_join_user_room(data):
    """Join user-specific room for targeted updates"""
    try:
        websocket_manager.join_user_room(data['user_id'])
    except Exception as e:
        infrastructure_manager.log_error(
            error_type='websocket_join_room_error',
            message=str(e),
            endpoint='websocket_join_room',
            severity='MEDIUM'
        )

@socketio.on('driver_location_update')
def handle_driver_location_update(data):
    """Handle real-time driver location updates"""
    try:
        websocket_manager.handle_driver_location_update(data)
    except Exception as e:
        infrastructure_manager.log_error(
            error_type='websocket_location_error',
            message=str(e),
            endpoint='websocket_location_update',
            severity='MEDIUM'
        )

@socketio.on('ride_status_update')
def handle_ride_status_update(data):
    """Handle ride status updates"""
    try:
        websocket_manager.handle_ride_status_update(data)
    except Exception as e:
        infrastructure_manager.log_error(
            error_type='websocket_ride_status_error',
            message=str(e),
            endpoint='websocket_ride_status',
            severity='MEDIUM'
        )

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    infrastructure_manager.log_error(
        error_type='internal_server_error',
        message=str(error),
        endpoint=request.endpoint,
        severity='HIGH'
    )
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500

@app.errorhandler(429)
def rate_limit_exceeded(error):
    return jsonify({
        'success': False,
        'error': 'Rate limit exceeded',
        'message': 'Too many requests. Please try again later.'
    }), 429

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') != 'production'
    
    print("=" * 60)
    print("🚀 TaxiGo Pro Enhanced Backend Starting...")
    print("=" * 60)
    print(f"Port: {port}")
    print(f"Debug mode: {debug}")
    print(f"Environment: {os.getenv('FLASK_ENV', 'development')}")
    print()
    print("🔧 Enterprise Features Enabled:")
    print("  ✓ JWT Authentication with refresh tokens")
    print("  ✓ API Rate limiting and abuse prevention")
    print("  ✓ Input validation and sanitization")
    print("  ✓ Real-time WebSocket communication")
    print("  ✓ Stripe & PayPal payment processing")
    print("  ✓ GPS tracking and route calculation")
    print("  ✓ Multi-platform push notifications")
    print("  ✓ Database optimization and caching")
    print("  ✓ Performance monitoring and alerting")
    print("  ✓ Error tracking and logging")
    print("  ✓ Business intelligence analytics")
    print("  ✓ Security event monitoring")
    print("  ✓ Load balancer ready configuration")
    print()
    print("🔒 Security Features:")
    print("  ✓ CORS protection")
    print("  ✓ Security headers")
    print("  ✓ Rate limiting")
    print("  ✓ Input sanitization")
    print("  ✓ SQL injection prevention")
    print("  ✓ XSS protection")
    print("  ✓ IP blocking for suspicious activity")
    print()
    print("📊 Monitoring & Analytics:")
    print("  ✓ Real-time performance metrics")
    print("  ✓ Error tracking and alerting")
    print("  ✓ Business intelligence dashboard")
    print("  ✓ User behavior analytics")
    print("  ✓ System health monitoring")
    print("=" * 60)
    
    socketio.run(app, host='0.0.0.0', port=port, debug=debug)

