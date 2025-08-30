"""
Database Optimization and Scaling for TaxiGo Pro
Handles database performance, indexing, caching, and backup systems
"""

import sqlite3
import json
import time
import threading
import os
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import hashlib
import pickle

class DatabaseOptimizer:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.cache = {}
        self.cache_ttl = {}
        self.cache_lock = threading.Lock()
        
        # Performance monitoring
        self.query_stats = {}
        self.slow_queries = []
        
        # Backup configuration
        self.backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # Start background tasks
        self.start_background_tasks()
    
    def optimize_database(self):
        """Optimize database performance with indexes and cleanup"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create performance indexes
            indexes = [
                # User table indexes
                "CREATE INDEX IF NOT EXISTS idx_user_email ON user(email)",
                "CREATE INDEX IF NOT EXISTS idx_user_type ON user(user_type)",
                "CREATE INDEX IF NOT EXISTS idx_user_created ON user(created_at)",
                
                # Ride table indexes (if exists)
                "CREATE INDEX IF NOT EXISTS idx_ride_passenger ON rides(passenger_id)",
                "CREATE INDEX IF NOT EXISTS idx_ride_driver ON rides(driver_id)",
                "CREATE INDEX IF NOT EXISTS idx_ride_status ON rides(status)",
                "CREATE INDEX IF NOT EXISTS idx_ride_created ON rides(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_ride_location ON rides(pickup_latitude, pickup_longitude)",
                
                # Payment table indexes (if exists)
                "CREATE INDEX IF NOT EXISTS idx_payment_user ON payments(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_payment_ride ON payments(ride_id)",
                "CREATE INDEX IF NOT EXISTS idx_payment_status ON payments(status)",
                "CREATE INDEX IF NOT EXISTS idx_payment_created ON payments(created_at)",
                
                # Location tracking indexes
                "CREATE INDEX IF NOT EXISTS idx_location_driver ON driver_locations(driver_id)",
                "CREATE INDEX IF NOT EXISTS idx_location_timestamp ON driver_locations(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_location_coords ON driver_locations(latitude, longitude)"
            ]
            
            for index_sql in indexes:
                try:
                    cursor.execute(index_sql)
                except sqlite3.Error as e:
                    print(f"Index creation warning: {e}")
            
            # Analyze tables for query optimization
            cursor.execute("ANALYZE")
            
            # Vacuum database to reclaim space
            cursor.execute("VACUUM")
            
            conn.commit()
            conn.close()
            
            return {
                'success': True,
                'message': 'Database optimized successfully',
                'indexes_created': len(indexes)
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_enhanced_tables(self):
        """Create enhanced tables for production features"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Enhanced rides table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rides (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ride_id TEXT UNIQUE NOT NULL,
                    passenger_id INTEGER NOT NULL,
                    driver_id INTEGER,
                    pickup_latitude REAL NOT NULL,
                    pickup_longitude REAL NOT NULL,
                    pickup_address TEXT,
                    destination_latitude REAL NOT NULL,
                    destination_longitude REAL NOT NULL,
                    destination_address TEXT,
                    ride_type TEXT DEFAULT 'standard',
                    status TEXT DEFAULT 'requested',
                    fare REAL,
                    distance_km REAL,
                    duration_minutes INTEGER,
                    payment_method TEXT,
                    payment_status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    cancelled_at TIMESTAMP,
                    cancellation_reason TEXT,
                    rating INTEGER,
                    review TEXT,
                    FOREIGN KEY (passenger_id) REFERENCES user (id),
                    FOREIGN KEY (driver_id) REFERENCES user (id)
                )
            ''')
            
            # Driver locations table for GPS tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS driver_locations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    driver_id INTEGER NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    heading REAL DEFAULT 0,
                    speed REAL DEFAULT 0,
                    accuracy REAL DEFAULT 0,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (driver_id) REFERENCES user (id)
                )
            ''')
            
            # Payments table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payment_id TEXT UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL,
                    ride_id TEXT,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'AUD',
                    payment_method TEXT NOT NULL,
                    payment_type TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    stripe_payment_intent_id TEXT,
                    paypal_payment_id TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user (id)
                )
            ''')
            
            # Payment methods table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payment_methods (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    method_type TEXT NOT NULL,
                    stripe_payment_method_id TEXT,
                    last_four TEXT,
                    brand TEXT,
                    exp_month INTEGER,
                    exp_year INTEGER,
                    is_default BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user (id)
                )
            ''')
            
            # Notifications table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    type TEXT DEFAULT 'info',
                    data TEXT,
                    read BOOLEAN DEFAULT FALSE,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user (id)
                )
            ''')
            
            # Business employees table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS business_employees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_id INTEGER NOT NULL,
                    employee_name TEXT NOT NULL,
                    employee_email TEXT NOT NULL,
                    department TEXT,
                    status TEXT DEFAULT 'active',
                    monthly_limit REAL DEFAULT 1000.00,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (business_id) REFERENCES user (id)
                )
            ''')
            
            # Analytics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analytics_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    user_id INTEGER,
                    ride_id TEXT,
                    data TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            
            # Optimize after creating tables
            self.optimize_database()
            
            return {
                'success': True,
                'message': 'Enhanced tables created successfully'
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def cache_query_result(self, query_key: str, result: Any, ttl_seconds: int = 300):
        """Cache query result with TTL"""
        with self.cache_lock:
            self.cache[query_key] = result
            self.cache_ttl[query_key] = time.time() + ttl_seconds
    
    def get_cached_result(self, query_key: str) -> Optional[Any]:
        """Get cached query result if not expired"""
        with self.cache_lock:
            if query_key in self.cache:
                if time.time() < self.cache_ttl[query_key]:
                    return self.cache[query_key]
                else:
                    # Remove expired cache
                    del self.cache[query_key]
                    del self.cache_ttl[query_key]
        return None
    
    def execute_cached_query(self, query: str, params: tuple = (), ttl_seconds: int = 300) -> List[Dict]:
        """Execute query with caching"""
        # Create cache key
        query_key = hashlib.md5(f"{query}{params}".encode()).hexdigest()
        
        # Check cache first
        cached_result = self.get_cached_result(query_key)
        if cached_result is not None:
            return cached_result
        
        # Execute query
        start_time = time.time()
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # Convert to list of dicts
            result = [dict(row) for row in rows]
            
            conn.close()
            
            # Record query performance
            execution_time = time.time() - start_time
            self.record_query_performance(query, execution_time)
            
            # Cache result
            self.cache_query_result(query_key, result, ttl_seconds)
            
            return result
        
        except Exception as e:
            print(f"Query execution error: {e}")
            return []
    
    def record_query_performance(self, query: str, execution_time: float):
        """Record query performance for monitoring"""
        query_hash = hashlib.md5(query.encode()).hexdigest()[:8]
        
        if query_hash not in self.query_stats:
            self.query_stats[query_hash] = {
                'query': query[:100] + '...' if len(query) > 100 else query,
                'count': 0,
                'total_time': 0,
                'avg_time': 0,
                'max_time': 0
            }
        
        stats = self.query_stats[query_hash]
        stats['count'] += 1
        stats['total_time'] += execution_time
        stats['avg_time'] = stats['total_time'] / stats['count']
        stats['max_time'] = max(stats['max_time'], execution_time)
        
        # Track slow queries (> 1 second)
        if execution_time > 1.0:
            self.slow_queries.append({
                'query': query,
                'execution_time': execution_time,
                'timestamp': datetime.now().isoformat()
            })
            
            # Keep only last 100 slow queries
            if len(self.slow_queries) > 100:
                self.slow_queries = self.slow_queries[-100:]
    
    def get_performance_stats(self) -> Dict:
        """Get database performance statistics"""
        return {
            'cache_size': len(self.cache),
            'query_stats': dict(list(self.query_stats.items())[:20]),  # Top 20 queries
            'slow_queries_count': len(self.slow_queries),
            'recent_slow_queries': self.slow_queries[-10:] if self.slow_queries else []
        }
    
    def create_backup(self, backup_name: str = None) -> Dict:
        """Create database backup"""
        try:
            if not backup_name:
                backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            # Create backup using SQLite backup API
            source_conn = sqlite3.connect(self.db_path)
            backup_conn = sqlite3.connect(backup_path)
            
            source_conn.backup(backup_conn)
            
            source_conn.close()
            backup_conn.close()
            
            # Get backup file size
            backup_size = os.path.getsize(backup_path)
            
            return {
                'success': True,
                'backup_name': backup_name,
                'backup_path': backup_path,
                'backup_size_mb': round(backup_size / (1024 * 1024), 2),
                'created_at': datetime.now().isoformat()
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def restore_backup(self, backup_name: str) -> Dict:
        """Restore database from backup"""
        try:
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            if not os.path.exists(backup_path):
                return {
                    'success': False,
                    'error': 'Backup file not found'
                }
            
            # Create backup of current database
            current_backup = self.create_backup(f"pre_restore_{int(time.time())}.db")
            
            # Replace current database with backup
            shutil.copy2(backup_path, self.db_path)
            
            return {
                'success': True,
                'message': f'Database restored from {backup_name}',
                'current_backup': current_backup
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def cleanup_old_data(self, days_to_keep: int = 90) -> Dict:
        """Clean up old data to maintain performance"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cleanup_stats = {}
            
            # Clean up old driver locations (keep only last 7 days)
            location_cutoff = datetime.now() - timedelta(days=7)
            cursor.execute(
                "DELETE FROM driver_locations WHERE timestamp < ?",
                (location_cutoff.isoformat(),)
            )
            cleanup_stats['driver_locations_deleted'] = cursor.rowcount
            
            # Clean up old notifications (keep only last 30 days)
            notification_cutoff = datetime.now() - timedelta(days=30)
            cursor.execute(
                "DELETE FROM notifications WHERE sent_at < ? AND read = 1",
                (notification_cutoff.isoformat(),)
            )
            cleanup_stats['notifications_deleted'] = cursor.rowcount
            
            # Clean up old analytics events (keep only last 90 days)
            cursor.execute(
                "DELETE FROM analytics_events WHERE timestamp < ?",
                (cutoff_date.isoformat(),)
            )
            cleanup_stats['analytics_events_deleted'] = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            # Vacuum database after cleanup
            self.optimize_database()
            
            return {
                'success': True,
                'cleanup_stats': cleanup_stats,
                'cutoff_date': cutoff_date.isoformat()
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def start_background_tasks(self):
        """Start background maintenance tasks"""
        def maintenance_worker():
            while True:
                try:
                    # Clean cache every 10 minutes
                    current_time = time.time()
                    with self.cache_lock:
                        expired_keys = [
                            key for key, expiry in self.cache_ttl.items()
                            if current_time >= expiry
                        ]
                        for key in expired_keys:
                            del self.cache[key]
                            del self.cache_ttl[key]
                    
                    # Create daily backup at 2 AM
                    now = datetime.now()
                    if now.hour == 2 and now.minute < 10:
                        self.create_backup()
                    
                    # Weekly cleanup on Sunday at 3 AM
                    if now.weekday() == 6 and now.hour == 3 and now.minute < 10:
                        self.cleanup_old_data()
                    
                    time.sleep(600)  # Run every 10 minutes
                
                except Exception as e:
                    print(f"Maintenance worker error: {e}")
                    time.sleep(300)  # Wait 5 minutes on error
        
        # Start background thread
        threading.Thread(target=maintenance_worker, daemon=True).start()

# Global database optimizer instance
db_optimizer = None

def initialize_db_optimizer(db_path: str):
    """Initialize database optimizer"""
    global db_optimizer
    db_optimizer = DatabaseOptimizer(db_path)
    
    # Create enhanced tables
    result = db_optimizer.create_enhanced_tables()
    print(f"Database initialization: {result}")
    
    return db_optimizer

