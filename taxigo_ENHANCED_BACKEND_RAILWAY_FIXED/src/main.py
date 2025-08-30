import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
from src.models.user import db
from src.routes.user import user_bp
from src.websocket_manager import websocket_manager
from src.payment_processor import payment_processor
from src.gps_tracker import gps_tracker, Location
from datetime import datetime

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'taxigo_pro_enhanced_secret_key_2024'

# Enable CORS for all routes
CORS(app, origins="*")

# Initialize WebSocket manager
websocket_manager.init_app(app)
socketio = websocket_manager.socketio

# Register blueprints
app.register_blueprint(user_bp, url_prefix='/api')

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'database', 'app.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Create enhanced database tables
with app.app_context():
    db.create_all()

# Enhanced API Routes

@app.route('/api/health', methods=['GET'])
def health_check():
    """Enhanced health check with system status"""
    return jsonify({
        'status': 'healthy',
        'message': 'TaxiGo Pro Enhanced API is running',
        'features': {
            'websockets': True,
            'payments': True,
            'gps_tracking': True,
            'real_time_updates': True
        },
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/payments/create-intent', methods=['POST'])
def create_payment_intent():
    """Create payment intent for ride"""
    try:
        data = request.get_json()
        amount = data.get('amount')
        ride_id = data.get('ride_id')
        user_id = data.get('user_id')
        
        result = payment_processor.create_stripe_payment_intent(
            amount=amount,
            metadata={
                'ride_id': ride_id,
                'user_id': str(user_id),
                'payment_type': 'ride_fare'
            }
        )
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/payments/confirm', methods=['POST'])
def confirm_payment():
    """Confirm payment intent"""
    try:
        data = request.get_json()
        payment_intent_id = data.get('payment_intent_id')
        payment_method_id = data.get('payment_method_id')
        
        result = payment_processor.confirm_stripe_payment(
            payment_intent_id=payment_intent_id,
            payment_method_id=payment_method_id
        )
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/payments/split', methods=['POST'])
def process_split_payment():
    """Process split payment between multiple users"""
    try:
        data = request.get_json()
        ride_data = data.get('ride_data')
        split_details = data.get('split_details')
        
        result = payment_processor.process_split_payment(ride_data, split_details)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/payments/cancel-fee', methods=['POST'])
def process_cancellation_fee():
    """Process cancellation fee"""
    try:
        data = request.get_json()
        ride_data = data.get('ride_data')
        payment_method = data.get('payment_method', 'stripe')
        
        result = payment_processor.process_cancellation_fee(ride_data, payment_method)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/gps/update-location', methods=['POST'])
def update_location():
    """Update driver or passenger location"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        user_type = data.get('user_type')
        location_data = data.get('location')
        
        location = Location(
            latitude=location_data.get('latitude'),
            longitude=location_data.get('longitude'),
            timestamp=datetime.now(),
            accuracy=location_data.get('accuracy', 0),
            heading=location_data.get('heading', 0),
            speed=location_data.get('speed', 0)
        )
        
        if user_type == 'driver':
            result = gps_tracker.update_driver_location(user_id, location)
        else:
            result = gps_tracker.update_passenger_location(user_id, location)
        
        # Broadcast location update via WebSocket
        websocket_manager.send_to_user(user_id, 'location_updated', result)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/gps/nearby-drivers', methods=['POST'])
def find_nearby_drivers():
    """Find nearby drivers for passenger"""
    try:
        data = request.get_json()
        location_data = data.get('location')
        radius_km = data.get('radius_km', 5.0)
        
        passenger_location = Location(
            latitude=location_data.get('latitude'),
            longitude=location_data.get('longitude'),
            timestamp=datetime.now()
        )
        
        nearby_drivers = gps_tracker.find_nearby_drivers(passenger_location, radius_km)
        
        return jsonify({
            'success': True,
            'nearby_drivers': nearby_drivers,
            'count': len(nearby_drivers)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/gps/calculate-route', methods=['POST'])
def calculate_route():
    """Calculate route between two locations"""
    try:
        data = request.get_json()
        start_data = data.get('start_location')
        end_data = data.get('end_location')
        
        start_location = Location(
            latitude=start_data.get('latitude'),
            longitude=start_data.get('longitude'),
            timestamp=datetime.now()
        )
        
        end_location = Location(
            latitude=end_data.get('latitude'),
            longitude=end_data.get('longitude'),
            timestamp=datetime.now()
        )
        
        route = gps_tracker.calculate_route(start_location, end_location)
        
        return jsonify({
            'success': True,
            'route': {
                'distance_km': route.distance_km,
                'duration_minutes': route.duration_minutes,
                'estimated_fare': route.estimated_fare,
                'waypoints': [
                    {
                        'latitude': wp.latitude,
                        'longitude': wp.longitude
                    } for wp in route.waypoints
                ]
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/rides/book', methods=['POST'])
def book_ride():
    """Book a new ride with real-time matching"""
    try:
        data = request.get_json()
        
        # Create ride booking
        ride_data = {
            'ride_id': f"ride_{int(datetime.now().timestamp())}",
            'passenger_id': data.get('passenger_id'),
            'pickup_location': data.get('pickup_location'),
            'destination': data.get('destination'),
            'ride_type': data.get('ride_type', 'standard'),
            'estimated_fare': data.get('estimated_fare'),
            'status': 'searching_driver'
        }
        
        # Store in WebSocket manager for real-time updates
        websocket_manager.active_rides[ride_data['ride_id']] = ride_data
        
        # Find nearby drivers
        pickup_location = Location(
            latitude=data.get('pickup_location').get('latitude'),
            longitude=data.get('pickup_location').get('longitude'),
            timestamp=datetime.now()
        )
        
        nearby_drivers = gps_tracker.find_nearby_drivers(pickup_location)
        
        # Notify nearby drivers via WebSocket
        websocket_manager.notify_nearby_drivers(ride_data)
        
        # Send confirmation to passenger
        websocket_manager.send_to_user(
            ride_data['passenger_id'], 
            'ride_booked', 
            {
                'ride_id': ride_data['ride_id'],
                'status': 'Searching for nearby drivers...',
                'nearby_drivers_count': len(nearby_drivers)
            }
        )
        
        return jsonify({
            'success': True,
            'ride_id': ride_data['ride_id'],
            'status': 'searching_driver',
            'nearby_drivers_count': len(nearby_drivers)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/notifications/send', methods=['POST'])
def send_notification():
    """Send push notification to user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        notification = data.get('notification')
        
        websocket_manager.send_push_notification(user_id, notification)
        
        return jsonify({
            'success': True,
            'message': 'Notification sent'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    try:
        payload = request.get_data()
        signature = request.headers.get('Stripe-Signature')
        endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET', 'whsec_...')
        
        # Validate webhook
        validation_result = payment_processor.validate_webhook(
            payload, signature, endpoint_secret
        )
        
        if not validation_result['success']:
            return jsonify({'error': validation_result['error']}), 400
        
        # Process webhook event
        event = validation_result['event']
        result = payment_processor.handle_webhook_event(event)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# Serve frontend files
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

if __name__ == '__main__':
    # Run with SocketIO for real-time features
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=5000, 
        debug=True,
        allow_unsafe_werkzeug=True
    )

