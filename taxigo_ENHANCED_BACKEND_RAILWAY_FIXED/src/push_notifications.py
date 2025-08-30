"""
Push Notification System for TaxiGo Pro
Handles FCM (Firebase Cloud Messaging), APNS (Apple Push Notification Service), and Web Push
"""

import json
import requests
import time
from datetime import datetime
from typing import Dict, List, Optional
import threading
import queue
import os

class PushNotificationService:
    def __init__(self):
        # Firebase Cloud Messaging configuration
        self.fcm_server_key = os.getenv('FCM_SERVER_KEY', 'your_fcm_server_key')
        self.fcm_url = 'https://fcm.googleapis.com/fcm/send'
        
        # Apple Push Notification Service configuration
        self.apns_key_id = os.getenv('APNS_KEY_ID', 'your_apns_key_id')
        self.apns_team_id = os.getenv('APNS_TEAM_ID', 'your_apns_team_id')
        self.apns_bundle_id = os.getenv('APNS_BUNDLE_ID', 'com.taxigopro.app')
        
        # Web Push configuration
        self.vapid_public_key = os.getenv('VAPID_PUBLIC_KEY', 'your_vapid_public_key')
        self.vapid_private_key = os.getenv('VAPID_PRIVATE_KEY', 'your_vapid_private_key')
        
        # Notification queue and processing
        self.notification_queue = queue.Queue()
        self.device_tokens = {}  # Store user device tokens
        
        # Start notification processor
        self.start_notification_processor()
    
    def register_device_token(self, user_id: str, device_token: str, platform: str) -> Dict:
        """Register device token for push notifications"""
        try:
            if user_id not in self.device_tokens:
                self.device_tokens[user_id] = {}
            
            self.device_tokens[user_id][platform] = {
                'token': device_token,
                'registered_at': datetime.now().isoformat(),
                'active': True
            }
            
            return {
                'success': True,
                'message': f'Device token registered for {platform}',
                'user_id': user_id
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def send_notification(self, user_id: str, notification: Dict, immediate: bool = False) -> Dict:
        """Send push notification to user across all platforms"""
        try:
            notification_data = {
                'user_id': user_id,
                'title': notification.get('title', 'TaxiGo Pro'),
                'body': notification.get('body', ''),
                'data': notification.get('data', {}),
                'type': notification.get('type', 'info'),
                'priority': notification.get('priority', 'normal'),
                'timestamp': datetime.now().isoformat()
            }
            
            if immediate:
                return self._process_notification(notification_data)
            else:
                # Queue for background processing
                self.notification_queue.put(notification_data)
                return {
                    'success': True,
                    'message': 'Notification queued for delivery'
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def send_ride_notification(self, user_id: str, ride_event: str, ride_data: Dict) -> Dict:
        """Send ride-specific notifications"""
        notifications = {
            'ride_booked': {
                'title': 'Ride Booked Successfully',
                'body': 'Searching for nearby drivers...',
                'type': 'ride_update',
                'data': {'ride_id': ride_data.get('ride_id'), 'status': 'searching'}
            },
            'driver_assigned': {
                'title': 'Driver Assigned',
                'body': f"Your driver is on the way. ETA: {ride_data.get('eta', '5-8')} minutes",
                'type': 'ride_update',
                'data': {'ride_id': ride_data.get('ride_id'), 'driver_id': ride_data.get('driver_id')}
            },
            'driver_arriving': {
                'title': 'Driver Arriving',
                'body': 'Your driver is arriving at the pickup location',
                'type': 'ride_update',
                'data': {'ride_id': ride_data.get('ride_id')}
            },
            'driver_arrived': {
                'title': 'Driver Arrived',
                'body': 'Your driver has arrived at the pickup location',
                'type': 'ride_update',
                'data': {'ride_id': ride_data.get('ride_id')}
            },
            'ride_started': {
                'title': 'Ride Started',
                'body': 'Your ride has started. Enjoy your trip!',
                'type': 'ride_update',
                'data': {'ride_id': ride_data.get('ride_id')}
            },
            'ride_completed': {
                'title': 'Ride Completed',
                'body': f"Trip completed. Fare: ${ride_data.get('fare', '0.00')}",
                'type': 'ride_completed',
                'data': {'ride_id': ride_data.get('ride_id'), 'fare': ride_data.get('fare')}
            },
            'payment_processed': {
                'title': 'Payment Processed',
                'body': f"Payment of ${ride_data.get('amount', '0.00')} processed successfully",
                'type': 'payment_update',
                'data': {'payment_id': ride_data.get('payment_id')}
            },
            'ride_cancelled': {
                'title': 'Ride Cancelled',
                'body': 'Your ride has been cancelled',
                'type': 'ride_cancelled',
                'data': {'ride_id': ride_data.get('ride_id')}
            }
        }
        
        if ride_event in notifications:
            return self.send_notification(user_id, notifications[ride_event], immediate=True)
        else:
            return {
                'success': False,
                'error': f'Unknown ride event: {ride_event}'
            }
    
    def send_driver_notification(self, driver_id: str, notification_type: str, data: Dict) -> Dict:
        """Send driver-specific notifications"""
        notifications = {
            'new_ride_request': {
                'title': 'New Ride Request',
                'body': f"Pickup: {data.get('pickup_address', 'Unknown location')}",
                'type': 'ride_request',
                'data': data
            },
            'ride_cancelled_by_passenger': {
                'title': 'Ride Cancelled',
                'body': 'The passenger has cancelled the ride',
                'type': 'ride_cancelled',
                'data': data
            },
            'payment_received': {
                'title': 'Payment Received',
                'body': f"You earned ${data.get('earnings', '0.00')} from this ride",
                'type': 'payment_received',
                'data': data
            },
            'weekly_summary': {
                'title': 'Weekly Earnings Summary',
                'body': f"This week you earned ${data.get('weekly_earnings', '0.00')} from {data.get('rides_count', 0)} rides",
                'type': 'earnings_summary',
                'data': data
            }
        }
        
        if notification_type in notifications:
            return self.send_notification(driver_id, notifications[notification_type], immediate=True)
        else:
            return {
                'success': False,
                'error': f'Unknown driver notification type: {notification_type}'
            }
    
    def send_business_notification(self, business_id: str, notification_type: str, data: Dict) -> Dict:
        """Send business-specific notifications"""
        notifications = {
            'monthly_report': {
                'title': 'Monthly Business Report',
                'body': f"Total spending: ${data.get('total_spending', '0.00')} | Rides: {data.get('total_rides', 0)}",
                'type': 'business_report',
                'data': data
            },
            'employee_added': {
                'title': 'New Employee Added',
                'body': f"{data.get('employee_name')} has been added to your business account",
                'type': 'employee_update',
                'data': data
            },
            'budget_alert': {
                'title': 'Budget Alert',
                'body': f"Monthly budget limit reached: ${data.get('budget_limit', '0.00')}",
                'type': 'budget_alert',
                'data': data
            },
            'delivery_completed': {
                'title': 'Delivery Completed',
                'body': f"Document delivery to {data.get('destination')} completed successfully",
                'type': 'delivery_update',
                'data': data
            }
        }
        
        if notification_type in notifications:
            return self.send_notification(business_id, notifications[notification_type], immediate=True)
        else:
            return {
                'success': False,
                'error': f'Unknown business notification type: {notification_type}'
            }
    
    def _process_notification(self, notification_data: Dict) -> Dict:
        """Process and send notification to all user devices"""
        user_id = notification_data['user_id']
        results = []
        
        if user_id not in self.device_tokens:
            return {
                'success': False,
                'error': 'No device tokens registered for user'
            }
        
        user_devices = self.device_tokens[user_id]
        
        # Send to Android devices (FCM)
        if 'android' in user_devices and user_devices['android']['active']:
            fcm_result = self._send_fcm_notification(
                user_devices['android']['token'],
                notification_data
            )
            results.append({'platform': 'android', 'result': fcm_result})
        
        # Send to iOS devices (APNS)
        if 'ios' in user_devices and user_devices['ios']['active']:
            apns_result = self._send_apns_notification(
                user_devices['ios']['token'],
                notification_data
            )
            results.append({'platform': 'ios', 'result': apns_result})
        
        # Send to web browsers (Web Push)
        if 'web' in user_devices and user_devices['web']['active']:
            web_push_result = self._send_web_push_notification(
                user_devices['web']['token'],
                notification_data
            )
            results.append({'platform': 'web', 'result': web_push_result})
        
        success_count = sum(1 for r in results if r['result'].get('success', False))
        
        return {
            'success': success_count > 0,
            'results': results,
            'success_count': success_count,
            'total_platforms': len(results)
        }
    
    def _send_fcm_notification(self, device_token: str, notification_data: Dict) -> Dict:
        """Send notification via Firebase Cloud Messaging (Android)"""
        try:
            headers = {
                'Authorization': f'key={self.fcm_server_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'to': device_token,
                'notification': {
                    'title': notification_data['title'],
                    'body': notification_data['body'],
                    'icon': 'ic_notification',
                    'sound': 'default',
                    'click_action': 'FLUTTER_NOTIFICATION_CLICK'
                },
                'data': {
                    **notification_data['data'],
                    'type': notification_data['type'],
                    'timestamp': notification_data['timestamp']
                },
                'priority': 'high' if notification_data['priority'] == 'high' else 'normal'
            }
            
            response = requests.post(self.fcm_url, headers=headers, json=payload)
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'platform': 'android',
                    'response': response.json()
                }
            else:
                return {
                    'success': False,
                    'platform': 'android',
                    'error': f'FCM error: {response.status_code}',
                    'response': response.text
                }
        
        except Exception as e:
            return {
                'success': False,
                'platform': 'android',
                'error': str(e)
            }
    
    def _send_apns_notification(self, device_token: str, notification_data: Dict) -> Dict:
        """Send notification via Apple Push Notification Service (iOS)"""
        try:
            # Note: This is a simplified implementation
            # In production, you would use proper APNS libraries like PyAPNs2
            
            payload = {
                'aps': {
                    'alert': {
                        'title': notification_data['title'],
                        'body': notification_data['body']
                    },
                    'sound': 'default',
                    'badge': 1
                },
                'data': {
                    **notification_data['data'],
                    'type': notification_data['type'],
                    'timestamp': notification_data['timestamp']
                }
            }
            
            # For production, implement proper APNS HTTP/2 API calls
            # This is a placeholder implementation
            
            return {
                'success': True,
                'platform': 'ios',
                'message': 'APNS notification queued (implement proper APNS client)'
            }
        
        except Exception as e:
            return {
                'success': False,
                'platform': 'ios',
                'error': str(e)
            }
    
    def _send_web_push_notification(self, subscription_info: str, notification_data: Dict) -> Dict:
        """Send notification via Web Push (Browser)"""
        try:
            # Note: This is a simplified implementation
            # In production, you would use proper Web Push libraries like pywebpush
            
            payload = {
                'title': notification_data['title'],
                'body': notification_data['body'],
                'icon': '/icon-192x192.png',
                'badge': '/badge-72x72.png',
                'data': {
                    **notification_data['data'],
                    'type': notification_data['type'],
                    'timestamp': notification_data['timestamp']
                }
            }
            
            # For production, implement proper Web Push protocol
            # This is a placeholder implementation
            
            return {
                'success': True,
                'platform': 'web',
                'message': 'Web Push notification queued (implement proper Web Push client)'
            }
        
        except Exception as e:
            return {
                'success': False,
                'platform': 'web',
                'error': str(e)
            }
    
    def send_bulk_notification(self, user_ids: List[str], notification: Dict) -> Dict:
        """Send notification to multiple users"""
        results = []
        
        for user_id in user_ids:
            result = self.send_notification(user_id, notification, immediate=True)
            results.append({
                'user_id': user_id,
                'result': result
            })
        
        success_count = sum(1 for r in results if r['result'].get('success', False))
        
        return {
            'success': success_count > 0,
            'results': results,
            'success_count': success_count,
            'total_users': len(user_ids)
        }
    
    def get_notification_stats(self) -> Dict:
        """Get notification delivery statistics"""
        return {
            'queue_size': self.notification_queue.qsize(),
            'registered_devices': {
                user_id: list(devices.keys())
                for user_id, devices in self.device_tokens.items()
            },
            'total_registered_users': len(self.device_tokens)
        }
    
    def start_notification_processor(self):
        """Start background notification processor"""
        def notification_worker():
            while True:
                try:
                    # Process notifications from queue
                    notification_data = self.notification_queue.get(timeout=1)
                    result = self._process_notification(notification_data)
                    
                    # Log result (in production, store in database)
                    print(f"Notification processed: {result}")
                    
                    self.notification_queue.task_done()
                
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"Notification worker error: {e}")
                    time.sleep(1)
        
        # Start background thread
        threading.Thread(target=notification_worker, daemon=True).start()

# Global push notification service instance
push_notification_service = PushNotificationService()

