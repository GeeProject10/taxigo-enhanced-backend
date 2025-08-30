"""
Payment Processor for TaxiGo Pro
Handles Stripe, PayPal, and other payment methods
"""

import stripe
import paypalrestsdk
import os
import json
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import hmac

class PaymentProcessor:
    def __init__(self):
        # Initialize Stripe
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY', 'sk_test_...')
        
        # Initialize PayPal
        paypalrestsdk.configure({
            "mode": os.getenv('PAYPAL_MODE', 'sandbox'),  # sandbox or live
            "client_id": os.getenv('PAYPAL_CLIENT_ID', 'your_paypal_client_id'),
            "client_secret": os.getenv('PAYPAL_CLIENT_SECRET', 'your_paypal_client_secret')
        })
        
        # Cancellation fee
        self.cancellation_fee = Decimal('10.00')  # AUD 10
    
    def create_stripe_payment_intent(self, amount, currency='aud', customer_id=None, metadata=None):
        """Create Stripe payment intent for ride payment"""
        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency,
                customer=customer_id,
                metadata=metadata or {},
                automatic_payment_methods={
                    'enabled': True,
                },
                capture_method='automatic'
            )
            
            return {
                'success': True,
                'payment_intent_id': payment_intent.id,
                'client_secret': payment_intent.client_secret,
                'status': payment_intent.status
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': 'stripe_error'
            }
    
    def confirm_stripe_payment(self, payment_intent_id, payment_method_id=None):
        """Confirm Stripe payment"""
        try:
            if payment_method_id:
                payment_intent = stripe.PaymentIntent.confirm(
                    payment_intent_id,
                    payment_method=payment_method_id
                )
            else:
                payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            return {
                'success': True,
                'status': payment_intent.status,
                'payment_intent': payment_intent
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_stripe_customer(self, email, name, phone=None):
        """Create Stripe customer"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                phone=phone,
                metadata={'source': 'taxigo_pro'}
            )
            
            return {
                'success': True,
                'customer_id': customer.id,
                'customer': customer
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def add_stripe_payment_method(self, customer_id, payment_method_id):
        """Attach payment method to customer"""
        try:
            payment_method = stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )
            
            return {
                'success': True,
                'payment_method': payment_method
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_paypal_payment(self, amount, currency='AUD', description='TaxiGo Pro Ride'):
        """Create PayPal payment"""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {
                    "payment_method": "paypal"
                },
                "redirect_urls": {
                    "return_url": os.getenv('PAYPAL_RETURN_URL', 'http://localhost:3000/payment/success'),
                    "cancel_url": os.getenv('PAYPAL_CANCEL_URL', 'http://localhost:3000/payment/cancel')
                },
                "transactions": [{
                    "item_list": {
                        "items": [{
                            "name": description,
                            "sku": "ride_payment",
                            "price": str(amount),
                            "currency": currency,
                            "quantity": 1
                        }]
                    },
                    "amount": {
                        "total": str(amount),
                        "currency": currency
                    },
                    "description": description
                }]
            })
            
            if payment.create():
                # Get approval URL
                approval_url = None
                for link in payment.links:
                    if link.rel == "approval_url":
                        approval_url = link.href
                        break
                
                return {
                    'success': True,
                    'payment_id': payment.id,
                    'approval_url': approval_url
                }
            else:
                return {
                    'success': False,
                    'error': payment.error
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def execute_paypal_payment(self, payment_id, payer_id):
        """Execute PayPal payment after approval"""
        try:
            payment = paypalrestsdk.Payment.find(payment_id)
            
            if payment.execute({"payer_id": payer_id}):
                return {
                    'success': True,
                    'payment': payment,
                    'status': payment.state
                }
            else:
                return {
                    'success': False,
                    'error': payment.error
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def process_ride_payment(self, ride_data, payment_method='stripe'):
        """Process payment for a ride"""
        amount = Decimal(str(ride_data.get('fare', 0)))
        ride_id = ride_data.get('ride_id')
        user_id = ride_data.get('user_id')
        
        metadata = {
            'ride_id': ride_id,
            'user_id': str(user_id),
            'payment_type': 'ride_fare',
            'timestamp': datetime.now().isoformat()
        }
        
        if payment_method == 'stripe':
            return self.create_stripe_payment_intent(
                amount=amount,
                metadata=metadata
            )
        elif payment_method == 'paypal':
            return self.create_paypal_payment(
                amount=amount,
                description=f'TaxiGo Pro Ride #{ride_id}'
            )
        else:
            return {
                'success': False,
                'error': 'Unsupported payment method'
            }
    
    def process_cancellation_fee(self, ride_data, payment_method='stripe'):
        """Process cancellation fee"""
        ride_id = ride_data.get('ride_id')
        user_id = ride_data.get('user_id')
        
        metadata = {
            'ride_id': ride_id,
            'user_id': str(user_id),
            'payment_type': 'cancellation_fee',
            'timestamp': datetime.now().isoformat()
        }
        
        if payment_method == 'stripe':
            return self.create_stripe_payment_intent(
                amount=self.cancellation_fee,
                metadata=metadata
            )
        elif payment_method == 'paypal':
            return self.create_paypal_payment(
                amount=self.cancellation_fee,
                description=f'TaxiGo Pro Cancellation Fee - Ride #{ride_id}'
            )
    
    def process_split_payment(self, ride_data, split_details):
        """Process split payment between multiple users"""
        total_amount = Decimal(str(ride_data.get('fare', 0)))
        ride_id = ride_data.get('ride_id')
        
        results = []
        
        for split in split_details:
            user_id = split.get('user_id')
            amount = Decimal(str(split.get('amount', 0)))
            payment_method = split.get('payment_method', 'stripe')
            
            metadata = {
                'ride_id': ride_id,
                'user_id': str(user_id),
                'payment_type': 'split_payment',
                'total_amount': str(total_amount),
                'split_amount': str(amount),
                'timestamp': datetime.now().isoformat()
            }
            
            if payment_method == 'stripe':
                result = self.create_stripe_payment_intent(
                    amount=amount,
                    metadata=metadata
                )
            elif payment_method == 'paypal':
                result = self.create_paypal_payment(
                    amount=amount,
                    description=f'TaxiGo Pro Split Payment - Ride #{ride_id}'
                )
            
            result['user_id'] = user_id
            result['amount'] = amount
            results.append(result)
        
        return {
            'success': all(r.get('success', False) for r in results),
            'split_payments': results
        }
    
    def refund_payment(self, payment_intent_id, amount=None, reason='requested_by_customer'):
        """Process refund for Stripe payment"""
        try:
            refund_data = {
                'payment_intent': payment_intent_id,
                'reason': reason
            }
            
            if amount:
                refund_data['amount'] = int(amount * 100)  # Convert to cents
            
            refund = stripe.Refund.create(**refund_data)
            
            return {
                'success': True,
                'refund_id': refund.id,
                'status': refund.status,
                'amount': refund.amount / 100  # Convert back to dollars
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_payment_methods(self, customer_id):
        """Get customer's saved payment methods"""
        try:
            payment_methods = stripe.PaymentMethod.list(
                customer=customer_id,
                type="card"
            )
            
            return {
                'success': True,
                'payment_methods': payment_methods.data
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def validate_webhook(self, payload, signature, endpoint_secret):
        """Validate Stripe webhook signature"""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, endpoint_secret
            )
            return {
                'success': True,
                'event': event
            }
        except ValueError:
            return {
                'success': False,
                'error': 'Invalid payload'
            }
        except stripe.error.SignatureVerificationError:
            return {
                'success': False,
                'error': 'Invalid signature'
            }
    
    def handle_webhook_event(self, event):
        """Handle Stripe webhook events"""
        event_type = event['type']
        
        if event_type == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            # Update ride status, send notifications, etc.
            return self.handle_payment_success(payment_intent)
        
        elif event_type == 'payment_intent.payment_failed':
            payment_intent = event['data']['object']
            return self.handle_payment_failure(payment_intent)
        
        elif event_type == 'customer.subscription.created':
            subscription = event['data']['object']
            return self.handle_subscription_created(subscription)
        
        return {'success': True, 'message': 'Event processed'}
    
    def handle_payment_success(self, payment_intent):
        """Handle successful payment"""
        metadata = payment_intent.get('metadata', {})
        ride_id = metadata.get('ride_id')
        user_id = metadata.get('user_id')
        payment_type = metadata.get('payment_type')
        
        # Update database, send notifications, etc.
        return {
            'success': True,
            'ride_id': ride_id,
            'user_id': user_id,
            'payment_type': payment_type,
            'amount': payment_intent['amount'] / 100
        }
    
    def handle_payment_failure(self, payment_intent):
        """Handle failed payment"""
        metadata = payment_intent.get('metadata', {})
        ride_id = metadata.get('ride_id')
        
        # Handle payment failure, notify user, etc.
        return {
            'success': False,
            'ride_id': ride_id,
            'error': 'Payment failed'
        }

# Global payment processor instance
payment_processor = PaymentProcessor()

