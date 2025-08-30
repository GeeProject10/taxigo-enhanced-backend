"""
GPS Tracking System for TaxiGo Pro
Handles real-time location tracking, route optimization, and geofencing
"""

import math
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import requests
import threading
from dataclasses import dataclass

@dataclass
class Location:
    latitude: float
    longitude: float
    timestamp: datetime
    accuracy: float = 0.0
    heading: float = 0.0
    speed: float = 0.0

@dataclass
class Route:
    start_location: Location
    end_location: Location
    waypoints: List[Location]
    distance_km: float
    duration_minutes: float
    estimated_fare: float

class GPSTracker:
    def __init__(self):
        self.driver_locations = {}
        self.passenger_locations = {}
        self.active_routes = {}
        self.geofences = {}
        
        # Google Maps API key (replace with your actual key)
        self.google_maps_api_key = "YOUR_GOOGLE_MAPS_API_KEY"
        
        # Start background location processing
        self.start_location_processor()
    
    def update_driver_location(self, driver_id: str, location: Location) -> Dict:
        """Update driver's real-time location"""
        try:
            # Store location with timestamp
            if driver_id not in self.driver_locations:
                self.driver_locations[driver_id] = []
            
            # Keep only last 100 locations for performance
            self.driver_locations[driver_id].append(location)
            if len(self.driver_locations[driver_id]) > 100:
                self.driver_locations[driver_id] = self.driver_locations[driver_id][-100:]
            
            # Calculate speed if we have previous location
            if len(self.driver_locations[driver_id]) > 1:
                prev_location = self.driver_locations[driver_id][-2]
                speed = self.calculate_speed(prev_location, location)
                location.speed = speed
            
            # Check for geofence events
            geofence_events = self.check_geofences(driver_id, location)
            
            return {
                'success': True,
                'driver_id': driver_id,
                'location': {
                    'latitude': location.latitude,
                    'longitude': location.longitude,
                    'timestamp': location.timestamp.isoformat(),
                    'accuracy': location.accuracy,
                    'heading': location.heading,
                    'speed': location.speed
                },
                'geofence_events': geofence_events
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def update_passenger_location(self, passenger_id: str, location: Location) -> Dict:
        """Update passenger's location for pickup"""
        try:
            self.passenger_locations[passenger_id] = location
            
            return {
                'success': True,
                'passenger_id': passenger_id,
                'location': {
                    'latitude': location.latitude,
                    'longitude': location.longitude,
                    'timestamp': location.timestamp.isoformat()
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def find_nearby_drivers(self, passenger_location: Location, radius_km: float = 5.0) -> List[Dict]:
        """Find drivers within specified radius of passenger"""
        nearby_drivers = []
        
        for driver_id, locations in self.driver_locations.items():
            if not locations:
                continue
            
            latest_location = locations[-1]
            distance = self.calculate_distance(passenger_location, latest_location)
            
            if distance <= radius_km:
                # Calculate ETA
                eta_minutes = self.calculate_eta(latest_location, passenger_location)
                
                nearby_drivers.append({
                    'driver_id': driver_id,
                    'location': {
                        'latitude': latest_location.latitude,
                        'longitude': latest_location.longitude,
                        'timestamp': latest_location.timestamp.isoformat()
                    },
                    'distance_km': round(distance, 2),
                    'eta_minutes': eta_minutes,
                    'heading': latest_location.heading,
                    'speed': latest_location.speed
                })
        
        # Sort by distance
        nearby_drivers.sort(key=lambda x: x['distance_km'])
        return nearby_drivers
    
    def calculate_route(self, start_location: Location, end_location: Location, waypoints: List[Location] = None) -> Route:
        """Calculate optimal route between locations"""
        try:
            # Build Google Maps Directions API request
            origin = f"{start_location.latitude},{start_location.longitude}"
            destination = f"{end_location.latitude},{end_location.longitude}"
            
            url = f"https://maps.googleapis.com/maps/api/directions/json"
            params = {
                'origin': origin,
                'destination': destination,
                'key': self.google_maps_api_key,
                'mode': 'driving',
                'traffic_model': 'best_guess',
                'departure_time': 'now'
            }
            
            # Add waypoints if provided
            if waypoints:
                waypoint_str = "|".join([f"{wp.latitude},{wp.longitude}" for wp in waypoints])
                params['waypoints'] = waypoint_str
            
            response = requests.get(url, params=params)
            data = response.json()
            
            if data['status'] == 'OK':
                route_data = data['routes'][0]
                leg = route_data['legs'][0]
                
                # Extract route information
                distance_km = leg['distance']['value'] / 1000  # Convert to km
                duration_minutes = leg['duration']['value'] / 60  # Convert to minutes
                
                # Calculate estimated fare
                estimated_fare = self.calculate_fare(distance_km, duration_minutes)
                
                # Extract waypoints from route
                route_waypoints = []
                for step in leg['steps']:
                    start_loc = step['start_location']
                    route_waypoints.append(Location(
                        latitude=start_loc['lat'],
                        longitude=start_loc['lng'],
                        timestamp=datetime.now()
                    ))
                
                return Route(
                    start_location=start_location,
                    end_location=end_location,
                    waypoints=route_waypoints,
                    distance_km=distance_km,
                    duration_minutes=duration_minutes,
                    estimated_fare=estimated_fare
                )
            else:
                # Fallback to straight-line calculation
                distance_km = self.calculate_distance(start_location, end_location)
                duration_minutes = distance_km * 2  # Rough estimate: 30 km/h average
                estimated_fare = self.calculate_fare(distance_km, duration_minutes)
                
                return Route(
                    start_location=start_location,
                    end_location=end_location,
                    waypoints=[start_location, end_location],
                    distance_km=distance_km,
                    duration_minutes=duration_minutes,
                    estimated_fare=estimated_fare
                )
        
        except Exception as e:
            # Fallback calculation
            distance_km = self.calculate_distance(start_location, end_location)
            duration_minutes = distance_km * 2
            estimated_fare = self.calculate_fare(distance_km, duration_minutes)
            
            return Route(
                start_location=start_location,
                end_location=end_location,
                waypoints=[start_location, end_location],
                distance_km=distance_km,
                duration_minutes=duration_minutes,
                estimated_fare=estimated_fare
            )
    
    def calculate_distance(self, loc1: Location, loc2: Location) -> float:
        """Calculate distance between two locations using Haversine formula"""
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(loc1.latitude)
        lat2_rad = math.radians(loc2.latitude)
        delta_lat = math.radians(loc2.latitude - loc1.latitude)
        delta_lon = math.radians(loc2.longitude - loc1.longitude)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def calculate_speed(self, loc1: Location, loc2: Location) -> float:
        """Calculate speed between two locations"""
        distance_km = self.calculate_distance(loc1, loc2)
        time_diff = (loc2.timestamp - loc1.timestamp).total_seconds() / 3600  # Convert to hours
        
        if time_diff > 0:
            return distance_km / time_diff  # km/h
        return 0.0
    
    def calculate_eta(self, driver_location: Location, destination: Location) -> int:
        """Calculate estimated time of arrival"""
        distance_km = self.calculate_distance(driver_location, destination)
        
        # Assume average city speed of 25 km/h with traffic
        average_speed = 25.0
        eta_hours = distance_km / average_speed
        eta_minutes = int(eta_hours * 60)
        
        # Add buffer time
        return max(eta_minutes + 2, 3)  # Minimum 3 minutes
    
    def calculate_fare(self, distance_km: float, duration_minutes: float) -> float:
        """Calculate ride fare based on distance and time"""
        # TaxiGo Pro fare structure (AUD)
        base_fare = 5.00
        per_km_rate = 2.50
        per_minute_rate = 0.50
        
        distance_cost = distance_km * per_km_rate
        time_cost = duration_minutes * per_minute_rate
        
        total_fare = base_fare + distance_cost + time_cost
        
        # Apply surge pricing if needed (simplified)
        surge_multiplier = self.get_surge_multiplier()
        total_fare *= surge_multiplier
        
        return round(total_fare, 2)
    
    def get_surge_multiplier(self) -> float:
        """Calculate surge pricing multiplier based on demand"""
        # Simplified surge pricing - in production, this would be more sophisticated
        current_hour = datetime.now().hour
        
        # Peak hours: 7-9 AM, 5-7 PM
        if (7 <= current_hour <= 9) or (17 <= current_hour <= 19):
            return 1.5
        # Late night: 11 PM - 3 AM
        elif current_hour >= 23 or current_hour <= 3:
            return 1.3
        else:
            return 1.0
    
    def create_geofence(self, name: str, center_location: Location, radius_meters: float) -> str:
        """Create a geofence for location-based triggers"""
        geofence_id = f"geofence_{int(time.time())}"
        
        self.geofences[geofence_id] = {
            'name': name,
            'center': center_location,
            'radius_meters': radius_meters,
            'created_at': datetime.now()
        }
        
        return geofence_id
    
    def check_geofences(self, driver_id: str, location: Location) -> List[Dict]:
        """Check if driver entered/exited any geofences"""
        events = []
        
        for geofence_id, geofence in self.geofences.items():
            distance_meters = self.calculate_distance(location, geofence['center']) * 1000
            
            if distance_meters <= geofence['radius_meters']:
                events.append({
                    'type': 'geofence_enter',
                    'geofence_id': geofence_id,
                    'geofence_name': geofence['name'],
                    'driver_id': driver_id,
                    'timestamp': datetime.now().isoformat()
                })
        
        return events
    
    def track_ride_progress(self, ride_id: str, driver_id: str, route: Route) -> Dict:
        """Track progress of an active ride"""
        if driver_id not in self.driver_locations or not self.driver_locations[driver_id]:
            return {'success': False, 'error': 'No driver location available'}
        
        current_location = self.driver_locations[driver_id][-1]
        
        # Calculate progress along route
        total_distance = route.distance_km
        distance_to_destination = self.calculate_distance(current_location, route.end_location)
        
        progress_percentage = max(0, min(100, ((total_distance - distance_to_destination) / total_distance) * 100))
        
        # Estimate remaining time
        remaining_distance = distance_to_destination
        estimated_remaining_minutes = self.calculate_eta(current_location, route.end_location)
        
        return {
            'success': True,
            'ride_id': ride_id,
            'driver_id': driver_id,
            'current_location': {
                'latitude': current_location.latitude,
                'longitude': current_location.longitude,
                'timestamp': current_location.timestamp.isoformat()
            },
            'progress_percentage': round(progress_percentage, 1),
            'remaining_distance_km': round(remaining_distance, 2),
            'estimated_remaining_minutes': estimated_remaining_minutes,
            'current_speed': current_location.speed
        }
    
    def start_location_processor(self):
        """Start background thread for processing location updates"""
        def location_processor():
            while True:
                try:
                    # Clean up old location data
                    cutoff_time = datetime.now() - timedelta(hours=24)
                    
                    for driver_id in list(self.driver_locations.keys()):
                        locations = self.driver_locations[driver_id]
                        # Keep only locations from last 24 hours
                        self.driver_locations[driver_id] = [
                            loc for loc in locations if loc.timestamp > cutoff_time
                        ]
                        
                        # Remove driver if no recent locations
                        if not self.driver_locations[driver_id]:
                            del self.driver_locations[driver_id]
                    
                    # Clean up old passenger locations
                    for passenger_id in list(self.passenger_locations.keys()):
                        location = self.passenger_locations[passenger_id]
                        if location.timestamp < cutoff_time:
                            del self.passenger_locations[passenger_id]
                    
                    time.sleep(300)  # Run every 5 minutes
                
                except Exception as e:
                    print(f"Location processor error: {e}")
                    time.sleep(60)
        
        # Start background thread
        threading.Thread(target=location_processor, daemon=True).start()

# Global GPS tracker instance
gps_tracker = GPSTracker()

