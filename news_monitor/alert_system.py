"""
Alert System for News Monitoring
Handles keyword matching and notifications
"""

import re
import logging
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional
import threading
import queue
import time
from datetime import datetime

from config import ALERTS_CONFIG
from database import NewsDatabase

class AlertSystem:
    """
    Alert system for monitoring news content
    Handles keyword detection and various notification methods
    """
    
    def __init__(self, database: NewsDatabase):
        self.database = database
        self.keywords = ALERTS_CONFIG['keywords']
        self.notification_queue = queue.Queue()
        self.notification_thread = None
        self.is_running = False
        
        # Compile keyword patterns for efficient matching
        self.keyword_patterns = self._compile_keyword_patterns()
        
        # Initialize notification handlers
        self.notification_handlers = {
            'web': self._handle_web_notification,
            'email': self._handle_email_notification,
            'webhook': self._handle_webhook_notification
        }
        
        # Statistics
        self.stats = {
            'total_alerts': 0,
            'keyword_matches': {},
            'notifications_sent': 0,
            'notification_failures': 0
        }
        
        self._start_notification_processor()
        logging.info("Alert system initialized")
    
    def _compile_keyword_patterns(self) -> Dict[str, re.Pattern]:
        """Compile keyword patterns for efficient matching"""
        patterns = {}
        
        for keyword in self.keywords:
            try:
                # Create case-insensitive pattern that matches whole words
                pattern = re.compile(rf'\b{re.escape(keyword)}\b', re.IGNORECASE | re.UNICODE)
                patterns[keyword] = pattern
            except re.error as e:
                logging.warning(f"Invalid regex pattern for keyword '{keyword}': {e}")
        
        return patterns
    
    def _start_notification_processor(self):
        """Start background thread for processing notifications"""
        if self.is_running:
            return
        
        self.is_running = True
        self.notification_thread = threading.Thread(
            target=self._notification_processor_loop,
            daemon=True
        )
        self.notification_thread.start()
        logging.info("Notification processor started")
    
    def _notification_processor_loop(self):
        """Background loop for processing notification queue"""
        while self.is_running:
            try:
                # Get notification from queue
                notification = self.notification_queue.get(timeout=1.0)
                
                # Process notification
                self._process_notification(notification)
                
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"Error in notification processor: {e}")
                time.sleep(1.0)
    
    def check_keywords(self, text: str) -> List[str]:
        """
        Check text for alert keywords
        
        Args:
            text: Text to check for keywords
        
        Returns:
            List of matched keywords
        """
        if not text:
            return []
        
        matched_keywords = []
        
        # Check each compiled pattern
        for keyword, pattern in self.keyword_patterns.items():
            if pattern.search(text):
                matched_keywords.append(keyword)
                
                # Update statistics
                if keyword not in self.stats['keyword_matches']:
                    self.stats['keyword_matches'][keyword] = 0
                self.stats['keyword_matches'][keyword] += 1
        
        return matched_keywords
    
    def trigger_notifications(self, alert_uuid: str, text: str, matched_keywords: List[str]):
        """
        Trigger notifications for an alert
        
        Args:
            alert_uuid: UUID of the alert
            text: The text that triggered the alert
            matched_keywords: List of keywords that matched
        """
        if not ALERTS_CONFIG['enabled']:
            return
        
        notification_data = {
            'alert_uuid': alert_uuid,
            'text': text,
            'matched_keywords': matched_keywords,
            'timestamp': datetime.now(),
            'methods': ALERTS_CONFIG['notification_methods']
        }
        
        # Add to processing queue
        try:
            self.notification_queue.put(notification_data, timeout=0.1)
            self.stats['total_alerts'] += 1
        except queue.Full:
            logging.warning("Notification queue full, dropping alert")
    
    def _process_notification(self, notification_data: Dict):
        """Process a single notification"""
        methods = notification_data['methods']
        
        for method in methods:
            if method in self.notification_handlers:
                try:
                    success = self.notification_handlers[method](notification_data)
                    if success:
                        self.stats['notifications_sent'] += 1
                    else:
                        self.stats['notification_failures'] += 1
                except Exception as e:
                    logging.error(f"Error sending {method} notification: {e}")
                    self.stats['notification_failures'] += 1
    
    def _handle_web_notification(self, notification_data: Dict) -> bool:
        """Handle web-based notifications (WebSocket, Server-Sent Events, etc.)"""
        try:
            # In a real implementation, this would push to WebSocket connections
            # or update a real-time dashboard
            
            alert_info = {
                'type': 'keyword_alert',
                'uuid': notification_data['alert_uuid'],
                'text': notification_data['text'][:200] + '...' if len(notification_data['text']) > 200 else notification_data['text'],
                'keywords': notification_data['matched_keywords'],
                'timestamp': notification_data['timestamp'].isoformat()
            }
            
            # For now, just log the web notification
            logging.info(f"Web notification: {alert_info}")
            
            return True
            
        except Exception as e:
            logging.error(f"Web notification failed: {e}")
            return False
    
    def _handle_email_notification(self, notification_data: Dict) -> bool:
        """Handle email notifications"""
        email_config = ALERTS_CONFIG.get('email_config', {})
        
        if not email_config.get('sender_email') or not email_config.get('recipient_emails'):
            logging.warning("Email configuration incomplete, skipping email notification")
            return False
        
        try:
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = email_config['sender_email']
            msg['To'] = ', '.join(email_config['recipient_emails'])
            msg['Subject'] = f"News Alert: {', '.join(notification_data['matched_keywords'])}"
            
            # Email body
            body = self._create_email_body(notification_data)
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Send email
            with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
                server.starttls()
                server.login(email_config['sender_email'], email_config['sender_password'])
                server.send_message(msg)
            
            logging.info(f"Email notification sent for alert {notification_data['alert_uuid']}")
            return True
            
        except Exception as e:
            logging.error(f"Email notification failed: {e}")
            return False
    
    def _handle_webhook_notification(self, notification_data: Dict) -> bool:
        """Handle webhook notifications"""
        webhook_url = ALERTS_CONFIG.get('webhook_url')
        
        if not webhook_url:
            logging.warning("Webhook URL not configured, skipping webhook notification")
            return False
        
        try:
            payload = {
                'alert_uuid': notification_data['alert_uuid'],
                'text': notification_data['text'][:500],  # Limit text length
                'matched_keywords': notification_data['matched_keywords'],
                'timestamp': notification_data['timestamp'].isoformat(),
                'source': 'news_monitor'
            }
            
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                logging.info(f"Webhook notification sent for alert {notification_data['alert_uuid']}")
                return True
            else:
                logging.warning(f"Webhook returned status {response.status_code}")
                return False
            
        except Exception as e:
            logging.error(f"Webhook notification failed: {e}")
            return False
    
    def _create_email_body(self, notification_data: Dict) -> str:
        """Create email body for alert notifications"""
        keywords_str = ', '.join(notification_data['matched_keywords'])
        timestamp_str = notification_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
        
        body = f"""
News Alert Triggered

Matched Keywords: {keywords_str}
Timestamp: {timestamp_str}
Alert UUID: {notification_data['alert_uuid']}

Content:
{notification_data['text']}

---
Automated News Monitoring System
"""
        return body.strip()
    
    def add_keywords(self, keywords: List[str]):
        """Add new keywords to monitor"""
        for keyword in keywords:
            if keyword not in self.keywords:
                self.keywords.append(keyword)
                
                # Compile pattern for new keyword
                try:
                    pattern = re.compile(rf'\b{re.escape(keyword)}\b', re.IGNORECASE | re.UNICODE)
                    self.keyword_patterns[keyword] = pattern
                    logging.info(f"Added keyword: {keyword}")
                except re.error as e:
                    logging.warning(f"Invalid regex pattern for keyword '{keyword}': {e}")
    
    def remove_keywords(self, keywords: List[str]):
        """Remove keywords from monitoring"""
        for keyword in keywords:
            if keyword in self.keywords:
                self.keywords.remove(keyword)
                self.keyword_patterns.pop(keyword, None)
                logging.info(f"Removed keyword: {keyword}")
    
    def get_keywords(self) -> List[str]:
        """Get current list of monitored keywords"""
        return self.keywords.copy()
    
    def get_statistics(self) -> Dict:
        """Get alert system statistics"""
        return {
            'total_alerts': self.stats['total_alerts'],
            'keyword_matches': self.stats['keyword_matches'].copy(),
            'notifications_sent': self.stats['notifications_sent'],
            'notification_failures': self.stats['notification_failures'],
            'active_keywords': len(self.keywords),
            'queue_size': self.notification_queue.qsize() if hasattr(self, 'notification_queue') else 0
        }
    
    def test_notifications(self) -> Dict[str, bool]:
        """Test all configured notification methods"""
        results = {}
        
        test_notification = {
            'alert_uuid': 'test-alert-123',
            'text': 'This is a test notification from the news monitoring system.',
            'matched_keywords': ['test'],
            'timestamp': datetime.now(),
            'methods': ALERTS_CONFIG['notification_methods']
        }
        
        for method in ALERTS_CONFIG['notification_methods']:
            if method in self.notification_handlers:
                try:
                    success = self.notification_handlers[method](test_notification)
                    results[method] = success
                except Exception as e:
                    logging.error(f"Test notification failed for {method}: {e}")
                    results[method] = False
            else:
                results[method] = False
        
        return results
    
    def cleanup(self):
        """Clean up alert system resources"""
        self.is_running = False
        
        if self.notification_thread and self.notification_thread.is_alive():
            self.notification_thread.join(timeout=5.0)
        
        # Clear notification queue
        while not self.notification_queue.empty():
            try:
                self.notification_queue.get_nowait()
            except queue.Empty:
                break
        
        logging.info("Alert system cleaned up")


class KeywordMatcher:
    """
    Advanced keyword matching with support for:
    - Fuzzy matching
    - Synonyms
    - Context-aware matching
    """
    
    def __init__(self, keywords: List[str], language: str = 'urdu'):
        self.keywords = keywords
        self.language = language
        self.synonym_map = self._load_synonyms()
    
    def _load_synonyms(self) -> Dict[str, List[str]]:
        """Load synonym mappings for better keyword matching"""
        # Basic Urdu synonyms for common news terms
        synonyms = {
            'خبر': ['اطلاع', 'معلومات', 'تازہ خبر'],
            'عاجل': ['فوری', 'اہم', 'تیز'],
            'breaking': ['urgent', 'important', 'latest'],
            'news': ['update', 'report', 'information']
        }
        return synonyms
    
    def match_with_synonyms(self, text: str) -> List[str]:
        """Match keywords including synonyms"""
        matched = []
        text_lower = text.lower()
        
        for keyword in self.keywords:
            # Direct match
            if keyword.lower() in text_lower:
                matched.append(keyword)
                continue
            
            # Synonym match
            if keyword in self.synonym_map:
                for synonym in self.synonym_map[keyword]:
                    if synonym.lower() in text_lower:
                        matched.append(keyword)  # Return original keyword
                        break
        
        return matched
    
    def fuzzy_match(self, text: str, threshold: float = 0.8) -> List[str]:
        """Fuzzy matching for keywords (requires additional dependencies)"""
        # This would implement fuzzy string matching
        # For now, return empty list
        return []


# Utility functions
def create_alert_system(database: NewsDatabase) -> AlertSystem:
    """Create and return configured alert system"""
    return AlertSystem(database)

def validate_email_config(config: Dict) -> bool:
    """Validate email configuration"""
    required_fields = ['smtp_server', 'smtp_port', 'sender_email', 'sender_password', 'recipient_emails']
    
    for field in required_fields:
        if field not in config or not config[field]:
            return False
    
    return True