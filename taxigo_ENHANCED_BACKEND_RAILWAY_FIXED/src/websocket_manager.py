"""
WebSocket Manager for Real-Time Features
Handles live updates, GPS tracking, and push notifications
"""

from flask_socketio import SocketIO, emit, join_room, leave_room
import json
import time
from datetime import datetime
import threading
import queue

class WebSocketManager:
    def __init__(self, app=None):
        self.socketio = None
        self.connected_users = {}
        self.active_rides = {}
        self.driver_locations = {}
        self.notification_queue = queue.Queue()
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize SocketIO with Flask app"""
        self.socketio = SocketIO(
            app, 
            cors_allowed_origins="*",
            async_mode='threading',
            logger=True,
            engineio_logger=True
        )
        self.setup_events()
        
        # Start background tasks
        self.start_background_tasks()
    
    def setup_events(self):
        """Setup WebSocket event handlers"""
        
        @self.socketio.on('connect')
        def handle_connect():
            print(f'Client connected: {request.sid}')
            emit('connected', {'status': 'Connected to TaxiGo Pro'})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            print(f'Client disconnected: {request.sid}')
            # Remove user from connected users
            for user_id, session_id in list(self.connected_users.items()):
                if session_id == request.sid:
                    del self.connected_users[user_id]
                    break
        
        @self.socketio.on('user_login')
        def handle_user_login(data):
            """Handle user login for real-time tracking"""
            user_id = data.get('user_id')
            user_type = data.get('user_type')
            
            self.connected_users[user_id] = {
                'session_id': request.sid,
                'user_type': user_type,
                'connected_at': datetime.now().isoformat()
            }
            
            # Join user-specific room
            join_room(f'user_{user_id}')
            
            # Join type-specific room
            join_room(f'{user_type}_users')
            
            emit('login_confirmed', {
                'user_id': user_id,
                'status': 'Real-time connection established'
            })
        
        @self.socketio.on('driver_location_update')
        def handle_driver_location(data):
            """Handle real-time driver location updates"""
            driver_id = data.get('driver_id')
            location = data.get('location')
            
            self.driver_locations[driver_id] = {
                'latitude': location.get('lat'),
                'longitude': location.get('lng'),
                'heading': location.get('heading', 0),
                'speed': location.get('speed', 0),
                'timestamp': datetime.now().isoformat()
            }
            
            # Broadcast to passengers in nearby area
            self.broadcast_driver_location(driver_id, location)
        
        @self.socketio.on('book_ride')
        def handle_ride_booking(data):
            """Handle real-time ride booking"""
            ride_data = {
                'ride_id': data.get('ride_id'),
                'passenger_id': data.get('passenger_id'),
                'pickup_location': data.get('pickup_location'),
                'destination': data.get('destination'),
                'ride_type': data.get('ride_type', 'standard'),
                'status': 'searching_driver',
                'created_at': datetime.now().isoformat()
            }
            
            self.active_rides[ride_data['ride_id']] = ride_data
            
            # Notify nearby drivers
            self.notify_nearby_drivers(ride_data)
            
            # Send confirmation to passenger
            emit('ride_booked', {
                'ride_id': ride_data['ride_id'],
                'status': 'Searching for nearby drivers...'
            })
        
        @self.socketio.on('driver_response')
        def handle_driver_response(data):
            """Handle driver accepting/declining ride"""
            ride_id = data.get('ride_id')
            driver_id = data.get('driver_id')
            response = data.get('response')  # 'accept' or 'decline'
            
            if ride_id in self.active_rides:
                ride = self.active_rides[ride_id]
                
                if response == 'accept':
                    # Update ride status
                    ride['driver_id'] = driver_id
                    ride['status'] = 'driver_assigned'
                    ride['driver_assigned_at'] = datetime.now().isoformat()
                    
                    # Notify passenger
                    passenger_id = ride['passenger_id']
                    self.send_to_user(passenger_id, 'driver_assigned', {
                        'ride_id': ride_id,
                        'driver_id': driver_id,
                        'driver_location': self.driver_locations.get(driver_id),
                        'estimated_arrival': '5-8 minutes'
                    })
                    
                    # Notify other drivers that ride is taken
                    self.socketio.emit('ride_taken', {
                        'ride_id': ride_id
                    }, room='driver_users')
        
        @self.socketio.on('ride_status_update')
        def handle_ride_status_update(data):
            """Handle ride status updates (arriving, started, completed)"""
            ride_id = data.get('ride_id')
            status = data.get('status')
            
            if ride_id in self.active_rides:
                ride = self.active_rides[ride_id]
                ride['status'] = status
                ride['last_updated'] = datetime.now().isoformat()
                
                # Notify both passenger and driver
                passenger_id = ride['passenger_id']
                driver_id = ride.get('driver_id')
                
                status_messages = {
                    'driver_arriving': 'Your driver is arriving',
                    'driver_arrived': 'Your driver has arrived',
                    'ride_started': 'Your ride has started',
                    'ride_completed': 'Ride completed successfully'
                }
                
                update_data = {
                    'ride_id': ride_id,
                    'status': status,
                    'message': status_messages.get(status, f'Ride status: {status}'),
                    'timestamp': datetime.now().isoformat()
                }
                
                if passenger_id:
                    self.send_to_user(passenger_id, 'ride_update', update_data)
                
                if driver_id:
                    self.send_to_user(driver_id, 'ride_update', update_data)
    
    def broadcast_driver_location(self, driver_id, location):
        """Broadcast driver location to relevant passengers"""
        # Find rides where this driver is assigned
        for ride_id, ride in self.active_rides.items():
            if ride.get('driver_id') == driver_id and ride['status'] in ['driver_assigned', 'driver_arriving', 'ride_started']:
                passenger_id = ride['passenger_id']
                self.send_to_user(passenger_id, 'driver_location_update', {
                    'driver_id': driver_id,
                    'location': location,
                    'ride_id': ride_id
                })
    
    def notify_nearby_drivers(self, ride_data):
        """Notify nearby drivers about new ride request"""
        # In a real implementation, you would calculate distance based on GPS
        # For now, notify all online drivers
        self.socketio.emit('new_ride_request', {
            'ride_id': ride_data['ride_id'],
            'pickup_location': ride_data['pickup_location'],
            'destination': ride_data['destination'],
            'ride_type': ride_data['ride_type'],
            'estimated_fare': self.calculate_estimated_fare(ride_data)
        }, room='driver_users')
    
    def send_to_user(self, user_id, event, data):
        """Send message to specific user"""
        if user_id in self.connected_users:
            self.socketio.emit(event, data, room=f'user_{user_id}')
    
    def send_push_notification(self, user_id, notification):
        """Send push notification to user"""
        notification_data = {
            'title': notification.get('title'),
            'body': notification.get('body'),
            'type': notification.get('type', 'info'),
            'timestamp': datetime.now().isoformat(),
            'data': notification.get('data', {})
        }
        
        # Send via WebSocket
        self.send_to_user(user_id, 'push_notification', notification_data)
        
        # Queue for other notification services (FCM, APNS, etc.)
        self.notification_queue.put({
            'user_id': user_id,
            'notification': notification_data
        })
    
    def calculate_estimated_fare(self, ride_data):
        """Calculate estimated fare for ride"""
        # Simple fare calculation - in production, use real distance/time
        base_fare = 5.00
        per_km = 2.50
        estimated_distance = 10  # km - would be calculated from GPS
        
        return round(base_fare + (estimated_distance * per_km), 2)
    
    def start_background_tasks(self):
        """Start background tasks for notifications and cleanup"""
        def notification_worker():
            while True:
                try:
                    # Process notification queue
                    if not self.notification_queue.empty():
                        notification = self.notification_queue.get(timeout=1)
                        # Here you would send to FCM, APNS, etc.
                        print(f"Processing notification: {notification}")
                    
                    time.sleep(1)
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"Notification worker error: {e}")
        
        def cleanup_worker():
            while True:
                try:
                    # Clean up old rides and inactive connections
                    current_time = datetime.now()
                    
                    # Remove completed rides older than 1 hour
                    for ride_id in list(self.active_rides.keys()):
                        ride = self.active_rides[ride_id]
                        if ride['status'] == 'ride_completed':
                            # In production, move to completed_rides table
                            del self.active_rides[ride_id]
                    
                    time.sleep(300)  # Run every 5 minutes
                except Exception as e:
                    print(f"Cleanup worker error: {e}")
        
        # Start background threads
        threading.Thread(target=notification_worker, daemon=True).start()
        threading.Thread(target=cleanup_worker, daemon=True).start()

# Global WebSocket manager instance
websocket_manager = WebSocketManager()

