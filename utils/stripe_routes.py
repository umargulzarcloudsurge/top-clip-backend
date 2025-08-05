import os
import stripe
import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Initialize Stripe - Use Supabase Vault in production
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Log Stripe environment for debugging
if stripe.api_key:
    if stripe.api_key.startswith('sk_test_'):
        logger.info("🗺️ Stripe initialized in TEST mode")
    elif stripe.api_key.startswith('sk_live_'):
        logger.info("🗺️ Stripe initialized in LIVE mode")
    else:
        logger.warning("⚠️ Stripe key format not recognized")
else:
    logger.error("❌ No Stripe secret key found in environment variables")

# Initialize Supabase
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

router = APIRouter(prefix="/api/stripe", tags=["stripe"])

# Stripe Price IDs from environment
STRIPE_HOBBY_MONTHLY_PRICE_ID = os.getenv("STRIPE_HOBBY_MONTHLY_PRICE_ID")
STRIPE_HOBBY_ANNUAL_PRICE_ID = os.getenv("STRIPE_HOBBY_ANNUAL_PRICE_ID")
STRIPE_STARTER_MONTHLY_PRICE_ID = os.getenv("STRIPE_STARTER_MONTHLY_PRICE_ID")
STRIPE_STARTER_ANNUAL_PRICE_ID = os.getenv("STRIPE_STARTER_ANNUAL_PRICE_ID")
STRIPE_EXPERT_MONTHLY_PRICE_ID = os.getenv("STRIPE_EXPERT_MONTHLY_PRICE_ID")
STRIPE_EXPERT_ANNUAL_PRICE_ID = os.getenv("STRIPE_EXPERT_ANNUAL_PRICE_ID")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

class CheckoutRequest(BaseModel):
    price_id: str
    user_id: str
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None
    referral: Optional[str] = None  # Rewardful referral UUID

class PortalRequest(BaseModel):
    user_id: str

class UpgradeRequest(BaseModel):
    user_id: str
    new_price_id: str

class CancelRequest(BaseModel):
    user_id: str
    immediate: Optional[bool] = False

class ReactivateRequest(BaseModel):
    user_id: str

@router.post("/create-checkout-session")
async def create_checkout_session(request: CheckoutRequest):
    """Create a Stripe checkout session"""
    try:
        logger.info(f"💳 Creating checkout session for user {request.user_id} with price {request.price_id}")
        
        # Get or create customer (with improved error handling)
        customer = await get_or_create_customer(request.user_id, request.referral)
        logger.info(f"👤 Customer ID: {customer.id}")
        
        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=customer.id,
            payment_method_types=['card'],
            line_items=[{
                'price': request.price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=request.success_url or f"{FRONTEND_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=request.cancel_url or f"{FRONTEND_URL}/pricing",
            metadata={
                'user_id': request.user_id
            }
        )
        
        logger.info(f"✅ Created checkout session for user {request.user_id}: {session.id}")
        return {"checkout_url": session.url}
        
    except stripe.error.InvalidRequestError as stripe_error:
        error_msg = str(stripe_error)
        logger.error(f"❌ Stripe InvalidRequestError: {error_msg}")
        
        if "No such customer" in error_msg:
            # Customer doesn't exist, try to recreate
            logger.info(f"🔄 Customer doesn't exist, forcing recreation for user {request.user_id}")
            try:
                # Clear customer ID from database and retry once
                supabase.table("user_profiles").update({
                    "stripe_customer_id": None
                }).eq("id", request.user_id).execute()
                
                # Retry with fresh customer
                customer = await get_or_create_customer(request.user_id)
                session = stripe.checkout.Session.create(
                    customer=customer.id,
                    payment_method_types=['card'],
                    line_items=[{
                        'price': request.price_id,
                        'quantity': 1,
                    }],
                    mode='subscription',
                    success_url=request.success_url or f"{FRONTEND_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
                    cancel_url=request.cancel_url or f"{FRONTEND_URL}/pricing",
                    metadata={
                        'user_id': request.user_id
                    }
                )
                logger.info(f"✅ Retry successful - created checkout session: {session.id}")
                return {"checkout_url": session.url}
                
            except Exception as retry_error:
                logger.error(f"❌ Retry failed: {str(retry_error)}")
                raise HTTPException(status_code=500, detail=f"Failed to create checkout session after retry: {str(retry_error)}")
        
        elif "No such price" in error_msg:
            raise HTTPException(status_code=400, detail=f"Invalid price ID: {request.price_id}")
        else:
            raise HTTPException(status_code=400, detail=f"Stripe error: {error_msg}")
            
    except Exception as e:
        logger.error(f"❌ Error creating checkout session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create checkout session: {str(e)}")

@router.post("/create-portal-session")
async def create_portal_session(request: PortalRequest):
    """Create a Stripe customer portal session"""
    try:
        logger.info(f"🔄 Creating portal session for user: {request.user_id}")
        
        # Validate user_id format
        if not request.user_id:
            raise HTTPException(status_code=400, detail="User ID is required")
        
        # Get customer
        customer = await get_or_create_customer(request.user_id)
        logger.info(f"👤 Found/created customer: {customer.id} for user: {request.user_id}")
        
        # Create portal session
        session = stripe.billing_portal.Session.create(
            customer=customer.id,
            return_url=f"{FRONTEND_URL}/dashboard"
        )
        
        logger.info(f"✅ Created portal session for user {request.user_id}, URL: {session.url}")
        return {"portal_url": session.url}
        
    except stripe.error.InvalidRequestError as stripe_error:
        error_msg = str(stripe_error)
        logger.error(f"❌ Stripe error creating portal session: {error_msg}")
        
        if "No configuration provided" in error_msg:
            raise HTTPException(
                status_code=500, 
                detail="Billing portal is not configured. Please configure the customer portal in your Stripe dashboard at https://dashboard.stripe.com/test/settings/billing/portal"
            )
        elif "does not have a billing portal configuration" in error_msg:
            raise HTTPException(
                status_code=500,
                detail="Customer portal configuration missing. Please set up billing portal settings in Stripe dashboard."
            )
        else:
            raise HTTPException(status_code=500, detail=f"Stripe configuration error: {error_msg}")
    
    except Exception as e:
        logger.error(f"❌ Error creating portal session for user {request.user_id}: {str(e)}")
        
        # Handle UUID format errors specifically
        if "invalid input syntax for type uuid" in str(e):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid user ID format. Expected UUID format, got: {request.user_id}"
            )
        
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/subscription/{user_id}")
async def get_user_subscription(user_id: str):
    """Get user's current subscription details"""
    try:
        # Get user profile with subscription info
        response = supabase.table("user_profiles").select("*").eq("id", user_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_profile = response.data[0]
        
        # If user has a subscription, get details from Stripe
        if user_profile.get("stripe_subscription_id"):
            subscription = stripe.Subscription.retrieve(user_profile["stripe_subscription_id"])
            price_id = subscription['items']['data'][0]['price']['id']
            
            return {
                "has_subscription": True,
                "plan": user_profile.get("plan", "free"),
                "status": subscription["status"],
                "current_period_end": user_profile.get("subscription_current_period_end"),
                "cancel_at_period_end": subscription.get("cancel_at_period_end", False),
                "price_id": price_id
            }
        else:
            return {
                "has_subscription": False,
                "plan": "free",
                "status": None,
                "current_period_end": None,
                "cancel_at_period_end": False,
                "price_id": None
            }
            
    except Exception as e:
        logger.error(f"❌ Error getting subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upgrade-subscription")
async def upgrade_subscription(request: UpgradeRequest):
    """Upgrade user's subscription to a new plan"""
    try:
        user_id = request.user_id
        new_price_id = request.new_price_id
        
        # Get user's current subscription
        response = supabase.table("user_profiles").select("stripe_subscription_id").eq("id", user_id).execute()
        
        if not response.data or not response.data[0].get("stripe_subscription_id"):
            raise HTTPException(status_code=400, detail="User has no active subscription to upgrade")
        
        subscription_id = response.data[0]["stripe_subscription_id"]
        
        # Get current subscription
        subscription = stripe.Subscription.retrieve(subscription_id)
        current_item_id = subscription['items']['data'][0]['id']
        
        # Update the subscription with new price
        updated_subscription = stripe.Subscription.modify(
            subscription_id,
            items=[{
                'id': current_item_id,
                'price': new_price_id,
            }],
            proration_behavior='immediate_with_adjustment'
        )
        
        logger.info(f"✅ Upgraded subscription for user {user_id} to price {new_price_id}")
        
        return {
            "success": True,
            "subscription_id": subscription_id,
            "message": "Subscription upgraded successfully"
        }
        
    except Exception as e:
        logger.error(f"❌ Error upgrading subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cancel-subscription")
async def cancel_subscription(request: CancelRequest):
    """Cancel user's subscription (at period end)"""
    try:
        user_id = request.user_id
        immediate = request.immediate
        
        # Get user's current subscription
        response = supabase.table("user_profiles").select("stripe_subscription_id").eq("id", user_id).execute()
        
        if not response.data or not response.data[0].get("stripe_subscription_id"):
            raise HTTPException(status_code=400, detail="User has no active subscription to cancel")
        
        subscription_id = response.data[0]["stripe_subscription_id"]
        
        if immediate:
            # Cancel immediately
            stripe.Subscription.delete(subscription_id)
            logger.info(f"✅ Immediately canceled subscription for user {user_id}")
            message = "Subscription canceled immediately"
        else:
            # Cancel at period end
            stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            logger.info(f"✅ Scheduled cancellation at period end for user {user_id}")
            message = "Subscription will be canceled at the end of the current period"
        
        return {
            "success": True,
            "subscription_id": subscription_id,
            "message": message,
            "immediate": immediate
        }
        
    except Exception as e:
        logger.error(f"❌ Error canceling subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reactivate-subscription")
async def reactivate_subscription(request: ReactivateRequest):
    """Reactivate a subscription that's set to cancel at period end"""
    try:
        user_id = request.user_id
        
        # Get user's current subscription
        response = supabase.table("user_profiles").select("stripe_subscription_id").eq("id", user_id).execute()
        
        if not response.data or not response.data[0].get("stripe_subscription_id"):
            raise HTTPException(status_code=400, detail="User has no subscription to reactivate")
        
        subscription_id = response.data[0]["stripe_subscription_id"]
        
        # Remove the cancellation
        stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=False
        )
        
        logger.info(f"✅ Reactivated subscription for user {user_id}")
        
        return {
            "success": True,
            "subscription_id": subscription_id,
            "message": "Subscription reactivated successfully"
        }
        
    except Exception as e:
        logger.error(f"❌ Error reactivating subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    try:
        payload = await request.body()
        sig_header = request.headers.get('stripe-signature')
        webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        
        logger.info(f"🔔 Webhook received: {len(payload)} bytes, signature present: {bool(sig_header)}")
        
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        
        logger.info(f"✅ Webhook verified successfully: {event['type']}")
        
        # Handle the event
        if event['type'] == 'checkout.session.completed':
            await handle_checkout_completed(event['data']['object'])
        elif event['type'] == 'customer.subscription.updated':
            await handle_subscription_updated(event['data']['object'])
        elif event['type'] == 'customer.subscription.deleted':
            await handle_subscription_deleted(event['data']['object'])
        elif event['type'] == 'payment_intent.succeeded':
            await handle_payment_intent_succeeded(event['data']['object'])
        elif event['type'] == 'payment_intent.payment_failed':
            await handle_payment_intent_failed(event['data']['object'])
        elif event['type'] == 'customer.subscription.created':
            await handle_subscription_created(event['data']['object'])
        elif event['type'] == 'invoice.payment_succeeded':
            await handle_invoice_payment_succeeded(event['data']['object'])
        elif event['type'] == 'invoice.payment_failed':
            await handle_invoice_payment_failed(event['data']['object'])
        else:
            logger.info(f"🔔 Unhandled event type: {event['type']}")
        
        return JSONResponse(content={"status": "success"})
        
    except ValueError as e:
        logger.error(f"❌ Invalid payload: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"❌ Invalid signature: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"❌ Webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_or_create_customer(user_id: str, referral_id: str = None):
    """Get existing Stripe customer or create new one"""
    try:
        # Check if user already has a customer ID
        response = supabase.table("user_profiles").select("stripe_customer_id, email").eq("id", user_id).execute()
        
        if response.data and response.data[0]["stripe_customer_id"]:
            # Try to retrieve existing customer, but handle if it doesn't exist
            try:
                customer = stripe.Customer.retrieve(response.data[0]["stripe_customer_id"])
                # If a referral ID is provided and the customer doesn't have one, update the customer
                if referral_id and 'referral' not in customer.get('metadata', {}):
                    stripe.Customer.modify(
                        customer.id,
                        metadata={'referral': referral_id}
                    )
                    logger.info(f"✅ Added referral ID to existing customer {customer.id}")
                return customer
            except stripe.error.InvalidRequestError as e:
                logger.warning(f"⚠️ Stored customer ID doesn't exist in Stripe: {str(e)}")
                logger.info(f"🔄 Creating new customer for user {user_id}")
                # Clear the invalid customer ID from database
                supabase.table("user_profiles").update({
                    "stripe_customer_id": None
                }).eq("id", user_id).execute()
                # Continue to create new customer below
        
        # Get user email
        user_email = response.data[0]["email"] if response.data else f"user-{user_id}@clipforge.ai"
        
        # Create new customer
        customer_params = {
            'email': user_email,
            'metadata': {'user_id': user_id}
        }
        if referral_id:
            customer_params['metadata']['referral'] = referral_id

        customer = stripe.Customer.create(**customer_params)
        
        # Update user profile with customer ID
        supabase.table("user_profiles").update({
            "stripe_customer_id": customer.id
        }).eq("id", user_id).execute()
        
        logger.info(f"✅ Created Stripe customer for user {user_id}")
        return customer
        
    except Exception as e:
        logger.error(f"❌ Error getting/creating customer: {str(e)}")
        raise e

@router.post("/create-test-user")
async def create_test_user(user_id: str = None, email: str = None):
    """Create a test user for Stripe integration testing"""
    try:
        import uuid
        
        # Generate test user ID and email if not provided
        test_user_id = user_id or str(uuid.uuid4())
        test_email = email or f"test-{test_user_id[:8]}@example.com"
        
        # Insert test user into user_profiles table
        response = supabase.table("user_profiles").insert({
            "id": test_user_id,
            "email": test_email,
            "plan": "hobby"  # Using lowercase "hobby" to match existing data
        }).execute()
        
        if response.data:
            logger.info(f"✅ Created test user: {test_user_id} with email: {test_email}")
            return {
                "status": "success",
                "message": "Test user created successfully",
                "user_id": test_user_id,
                "email": test_email
            }
        else:
            return {
                "status": "error",
                "message": "Failed to create test user",
                "response": response
            }
            
    except Exception as e:
        logger.error(f"❌ Error creating test user: {str(e)}")
        return {
            "status": "error",
            "message": f"Error creating test user: {str(e)}"
        }

@router.get("/get-test-user")
async def get_test_user():
    """Get an existing user for testing Stripe integration"""
    try:
        # Get a user without Stripe customer ID for testing
        response = supabase.table("user_profiles").select("id, email, plan").is_("stripe_customer_id", "null").limit(1).execute()
        
        if response.data:
            user = response.data[0]
            return {
                "status": "success",
                "user_id": user["id"],
                "email": user["email"],
                "plan": user["plan"],
                "message": "Found user without Stripe customer for testing"
            }
        else:
            # If no users without Stripe customer, get any user
            response = supabase.table("user_profiles").select("id, email, plan").limit(1).execute()
            if response.data:
                user = response.data[0]
                return {
                    "status": "success",
                    "user_id": user["id"],
                    "email": user["email"],
                    "plan": user["plan"],
                    "message": "Found existing user for testing"
                }
            
        return {
            "status": "error",
            "message": "No users found in database"
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting test user: {str(e)}")
        return {
            "status": "error",
            "message": f"Error getting test user: {str(e)}"
        }

@router.get("/check-plan-values")
async def check_plan_values():
    """Check what plan values exist in the database"""
    try:
        # Get sample plans to see valid values
        response = supabase.table("user_profiles").select("plan").limit(10).execute()
        
        plans_found = []
        if response.data:
            plans_found = list(set([user.get("plan") for user in response.data if user.get("plan")]))
        
        return {
            "status": "success",
            "existing_plans": plans_found,
            "sample_count": len(response.data) if response.data else 0
        }
        
    except Exception as e:
        logger.error(f"❌ Error checking plan values: {str(e)}")
        return {
            "status": "error",
            "message": f"Error checking plan values: {str(e)}"
        }

@router.get("/test-db-connection")
async def test_database_connection():
    """Test Supabase database connection and user_profiles table access"""
    try:
        logger.info("Testing Supabase database connection...")
        
        # Test basic connection
        try:
            response = supabase.table("user_profiles").select("count", count="exact").execute()
            table_count = response.count
            logger.info(f"✅ Successfully connected to user_profiles table. Row count: {table_count}")
        except Exception as table_error:
            logger.error(f"❌ Error accessing user_profiles table: {str(table_error)}")
            return {
                "status": "error",
                "message": f"Cannot access user_profiles table: {str(table_error)}",
                "supabase_url": supabase_url,
                "table_accessible": False
            }
        
        # Test table structure
        try:
            # Try to select just one row to check table structure
            response = supabase.table("user_profiles").select("*").limit(1).execute()
            logger.info(f"✅ Table structure test passed. Data: {response.data}")
        except Exception as structure_error:
            logger.error(f"❌ Table structure error: {str(structure_error)}")
            return {
                "status": "error",
                "message": f"Table structure issue: {str(structure_error)}",
                "supabase_url": supabase_url,
                "table_accessible": True,
                "structure_test": False
            }
        
        return {
            "status": "success",
            "message": "Database connection and table access working correctly",
            "supabase_url": supabase_url,
            "table_accessible": True,
            "table_count": table_count,
            "structure_test": True
        }
        
    except Exception as e:
        logger.error(f"❌ Database test failed: {str(e)}")
        return {
            "status": "error",
            "message": f"Database test failed: {str(e)}",
            "supabase_url": supabase_url
        }

@router.get("/debug-prices")
async def debug_stripe_prices():
    """Debug endpoint to check configured price IDs and verify they exist in Stripe"""
    try:
        # Get configured price IDs
        configured_prices = {
            "STRIPE_HOBBY_MONTHLY_PRICE_ID": STRIPE_HOBBY_MONTHLY_PRICE_ID,
            "STRIPE_HOBBY_ANNUAL_PRICE_ID": STRIPE_HOBBY_ANNUAL_PRICE_ID,
            "STRIPE_STARTER_MONTHLY_PRICE_ID": STRIPE_STARTER_MONTHLY_PRICE_ID,
            "STRIPE_STARTER_ANNUAL_PRICE_ID": STRIPE_STARTER_ANNUAL_PRICE_ID,
            "STRIPE_EXPERT_MONTHLY_PRICE_ID": STRIPE_EXPERT_MONTHLY_PRICE_ID,
            "STRIPE_EXPERT_ANNUAL_PRICE_ID": STRIPE_EXPERT_ANNUAL_PRICE_ID,
        }
        
        # Check which ones exist in Stripe
        price_status = {}
        for env_var, price_id in configured_prices.items():
            if not price_id:
                price_status[env_var] = {"price_id": None, "status": "NOT_CONFIGURED"}
                continue
                
            try:
                price = stripe.Price.retrieve(price_id)
                price_status[env_var] = {
                    "price_id": price_id,
                    "status": "EXISTS",
                    "active": price.active,
                    "currency": price.currency,
                    "unit_amount": price.unit_amount,
                    "recurring": price.recurring
                }
            except stripe.error.InvalidRequestError as e:
                price_status[env_var] = {
                    "price_id": price_id,
                    "status": "INVALID",
                    "error": str(e)
                }
        
        # Check Stripe environment
        stripe_env = "UNKNOWN"
        if stripe.api_key:
            if stripe.api_key.startswith('sk_test_'):
                stripe_env = "TEST"
            elif stripe.api_key.startswith('sk_live_'):
                stripe_env = "LIVE"
        
        return {
            "stripe_environment": stripe_env,
            "configured_prices": price_status,
            "frontend_url": FRONTEND_URL
        }
        
    except Exception as e:
        logger.error(f"❌ Error debugging prices: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup-invalid-customers")
async def cleanup_invalid_customers():
    """Admin endpoint to clean up invalid customer IDs - useful when switching Stripe environments"""
    try:
        # Get all users with customer IDs
        response = supabase.table("user_profiles").select("id, stripe_customer_id, email").execute()
        
        if not response.data:
            return {"message": "No users found"}
        
        cleaned_count = 0
        
        for user in response.data:
            if user.get("stripe_customer_id"):
                try:
                    # Try to retrieve customer from Stripe
                    stripe.Customer.retrieve(user["stripe_customer_id"])
                    logger.info(f"✅ Customer {user['stripe_customer_id']} exists for user {user['id']}")
                except stripe.error.InvalidRequestError:
                    # Customer doesn't exist, clear it
                    logger.info(f"🧹 Clearing invalid customer ID for user {user['id']}")
                    supabase.table("user_profiles").update({
                        "stripe_customer_id": None
                    }).eq("id", user["id"]).execute()
                    cleaned_count += 1
        
        return {
            "message": f"Cleaned up {cleaned_count} invalid customer IDs",
            "total_users_checked": len(response.data),
            "cleaned_count": cleaned_count
        }
        
    except Exception as e:
        logger.error(f"❌ Error cleaning up customers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def handle_checkout_completed(session):
    """Handle successful checkout"""
    try:
        logger.info(f"🔄 Processing checkout.session.completed: {session['id']}")
        
        # Get user_id from metadata
        user_id = session.get('metadata', {}).get('user_id')
        if not user_id:
            # Try to find user by customer email as fallback
            customer_id = session['customer']
            customer = stripe.Customer.retrieve(customer_id)
            customer_email = customer.email
            
            # Find user in Supabase by email
            response = supabase.table("user_profiles").select("id").eq("email", customer_email).execute()
            if response.data:
                user_id = response.data[0]["id"]
                logger.info(f"📧 Found user by email: {customer_email} -> {user_id}")
            else:
                logger.error(f"❌ No user found for customer email: {customer_email}")
                return
        
        subscription_id = session['subscription']
        customer_id = session['customer']
        
        logger.info(f"👤 Processing for user: {user_id}, customer: {customer_id}, subscription: {subscription_id}")
        
        # Get subscription details
        subscription = stripe.Subscription.retrieve(subscription_id)
        price_id = subscription['items']['data'][0]['price']['id']
        
        # Determine plan and limits based on price ID
        plan = "hobby"  # Default to hobby
        clips_limit = 50
        
        if price_id in [STRIPE_HOBBY_MONTHLY_PRICE_ID, STRIPE_HOBBY_ANNUAL_PRICE_ID]:
            plan = "hobby"
            clips_limit = 50
        elif price_id in [STRIPE_STARTER_MONTHLY_PRICE_ID, STRIPE_STARTER_ANNUAL_PRICE_ID]:
            plan = "starter"
            clips_limit = 150
        elif price_id in [STRIPE_EXPERT_MONTHLY_PRICE_ID, STRIPE_EXPERT_ANNUAL_PRICE_ID]:
            plan = "expert"
            clips_limit = 250
        
        # Convert timestamps to ISO format
        subscription_item = subscription['items']['data'][0]
        current_period_start = subscription_item['current_period_start']
        current_period_end = subscription_item['current_period_end']
        
        from datetime import datetime
        start_date = datetime.fromtimestamp(current_period_start).isoformat()
        end_date = datetime.fromtimestamp(current_period_end).isoformat()
        
        # Update user profile with full subscription details
        logger.info(f"📝 Updating user_profiles for user {user_id} with plan: {plan}")
        profile_response = supabase.table("user_profiles").update({
            "plan": plan,
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": subscription_id,
            "subscription_status": subscription['status'],
            "subscription_current_period_start": start_date,
            "subscription_current_period_end": end_date,
            "updated_at": datetime.now().isoformat()
        }).eq("id", user_id).execute()
        
        if profile_response.data:
            logger.info(f"✅ Successfully updated user_profiles for {user_id}")
        else:
            logger.error(f"❌ Failed to update user_profiles for {user_id}")
        
        # Update or create user usage for current month
        logger.info(f"📊 Updating user_usage for user {user_id} with {clips_limit} clips")
        await update_user_usage_limits(user_id, plan, clips_limit)
        
        logger.info(f"✅ Updated user {user_id} to {plan} plan with {clips_limit} clips limit")
        
    except Exception as e:
        logger.error(f"❌ Error handling checkout completed: {str(e)}")

async def handle_subscription_updated(subscription):
    """Handle subscription updates"""
    try:
        customer_id = subscription['customer']
        
        # Find user by customer ID
        response = supabase.table("user_profiles").select("id").eq("stripe_customer_id", customer_id).execute()
        
        if not response.data:
            logger.warning(f"⚠️ No user found for customer {customer_id}")
            return
        
        user_id = response.data[0]["id"]
        price_id = subscription['items']['data'][0]['price']['id']
        
        # Determine plan and limits
        plan = "hobby"  # Default to hobby
        clips_limit = 50
        
        if price_id in [STRIPE_HOBBY_MONTHLY_PRICE_ID, STRIPE_HOBBY_ANNUAL_PRICE_ID]:
            plan = "hobby"
            clips_limit = 50
        elif price_id in [STRIPE_STARTER_MONTHLY_PRICE_ID, STRIPE_STARTER_ANNUAL_PRICE_ID]:
            plan = "starter"
            clips_limit = 150
        elif price_id in [STRIPE_EXPERT_MONTHLY_PRICE_ID, STRIPE_EXPERT_ANNUAL_PRICE_ID]:
            plan = "expert"
            clips_limit = 250
        
        # Convert timestamps to ISO format
        subscription_item = subscription['items']['data'][0]
        current_period_start = subscription_item['current_period_start']
        current_period_end = subscription_item['current_period_end']
        
        from datetime import datetime
        start_date = datetime.fromtimestamp(current_period_start).isoformat()
        end_date = datetime.fromtimestamp(current_period_end).isoformat()
        
        # Update user profile with full subscription details
        supabase.table("user_profiles").update({
            "plan": plan,
            "subscription_status": subscription['status'],
            "subscription_current_period_start": start_date,
            "subscription_current_period_end": end_date,
            "updated_at": datetime.now().isoformat()
        }).eq("id", user_id).execute()
        
        # Update user usage limits for current month
        await update_user_usage_limits(user_id, plan, clips_limit)
        
        logger.info(f"✅ Updated subscription for user {user_id} to {plan} with {clips_limit} clips limit")
        
    except Exception as e:
        logger.error(f"❌ Error handling subscription updated: {str(e)}")

async def handle_subscription_deleted(subscription):
    """Handle subscription cancellation"""
    try:
        customer_id = subscription['customer']
        
        # Find user by customer ID
        response = supabase.table("user_profiles").select("id").eq("stripe_customer_id", customer_id).execute()
        
        if not response.data:
            logger.warning(f"⚠️ No user found for customer {customer_id}")
            return
        
        user_id = response.data[0]["id"]
        
        from datetime import datetime
        
        # Downgrade to free plan and clear subscription data
        supabase.table("user_profiles").update({
            "plan": "free",
            "subscription_status": "canceled",
            "stripe_subscription_id": None,
            "subscription_current_period_start": None,
            "subscription_current_period_end": None,
            "updated_at": datetime.now().isoformat()
        }).eq("id", user_id).execute()
        
        # Update user usage limits to free tier
        await update_user_usage_limits(user_id, "free", 3)
        
        logger.info(f"✅ Downgraded user {user_id} to free plan")
        
    except Exception as e:
        logger.error(f"❌ Error handling subscription deleted: {str(e)}")

async def update_user_usage_limits(user_id: str, plan: str, clips_limit: int):
    """Update user usage limits for current month"""
    try:
        from datetime import datetime
        current_month = datetime.now().strftime("%Y-%m")
        
        # Check if usage record exists for current month
        response = supabase.table("user_usage").select("*").eq("user_id", user_id).eq("month", current_month).execute()
        
        if response.data:
            # Update existing record
            supabase.table("user_usage").update({
                "clips_limit": clips_limit,
                "plan": plan,
                "updated_at": datetime.now().isoformat()
            }).eq("user_id", user_id).eq("month", current_month).execute()
            
            logger.info(f"✅ Updated usage limits for user {user_id} - {current_month}: {clips_limit} clips")
        else:
            # Create new usage record for current month
            supabase.table("user_usage").insert({
                "user_id": user_id,
                "month": current_month,
                "clips_created": 0,
                "clips_limit": clips_limit,
                "plan": plan,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }).execute()
            
            logger.info(f"✅ Created usage record for user {user_id} - {current_month}: {clips_limit} clips")
            
    except Exception as e:
        logger.error(f"❌ Error updating user usage limits: {str(e)}")
        # Don't raise - this is not critical enough to fail the webhook

async def handle_payment_intent_succeeded(payment_intent):
    """Handle successful one-time payment"""
    try:
        logger.info(f"💳 Payment succeeded: {payment_intent['id']}")
        # Log successful payment - you might want to send confirmation email
        # Usually handled by checkout.session.completed for subscriptions
        
    except Exception as e:
        logger.error(f"❌ Error handling payment_intent.succeeded: {str(e)}")

async def handle_payment_intent_failed(payment_intent):
    """Handle failed one-time payment"""
    try:
        logger.info(f"💳 Payment failed: {payment_intent['id']}")
        # Log failed payment, send notification to user
        # You might want to update user about payment failure
        
    except Exception as e:
        logger.error(f"❌ Error handling payment_intent.payment_failed: {str(e)}")

async def handle_subscription_created(subscription):
    """Handle new subscription creation - similar to checkout.session.completed"""
    try:
        logger.info(f"🎉 New subscription created: {subscription['id']}")
        # This is essentially the same as checkout.session.completed
        # You can reuse the same logic or call handle_checkout_completed
        # For now, just log it since checkout.session.completed handles the main logic
        
    except Exception as e:
        logger.error(f"❌ Error handling customer.subscription.created: {str(e)}")

async def handle_invoice_payment_succeeded(invoice):
    """Handle successful recurring payment"""
    try:
        logger.info(f"📄 Invoice payment succeeded: {invoice['id']}")
        subscription_id = invoice.get('subscription')
        
        if subscription_id:
            # This is a subscription renewal
            # Reset monthly usage if it's a new billing period
            customer_id = invoice['customer']
            
            # Find user by customer ID
            response = supabase.table("user_profiles").select("id, plan").eq("stripe_customer_id", customer_id).execute()
            
            if response.data:
                user_id = response.data[0]["id"]
                current_plan = response.data[0]["plan"]
                
                # Determine clips limit based on plan
                clips_limit = 50 if current_plan == "hobby" else 150 if current_plan == "pro" else 250
                
                # Reset usage for new billing period
                await update_user_usage_limits(user_id, current_plan, clips_limit)
                logger.info(f"✅ Reset usage limits for user {user_id} - new billing period")
        
    except Exception as e:
        logger.error(f"❌ Error handling invoice.payment_succeeded: {str(e)}")

async def handle_invoice_payment_failed(invoice):
    """Handle failed recurring payment"""
    try:
        logger.info(f"📄 Invoice payment failed: {invoice['id']}")
        customer_id = invoice['customer']
        
        # Find user by customer ID
        response = supabase.table("user_profiles").select("id").eq("stripe_customer_id", customer_id).execute()
        
        if response.data:
            user_id = response.data[0]["id"]
            
            # Update subscription status to past_due
            from datetime import datetime
            supabase.table("user_profiles").update({
                "subscription_status": "past_due",
                "updated_at": datetime.now().isoformat()
            }).eq("id", user_id).execute()
            
            logger.info(f"⚠️ Marked user {user_id} subscription as past_due")
            # You might want to send email notification here
        
    except Exception as e:
        logger.error(f"❌ Error handling invoice.payment_failed: {str(e)}")
