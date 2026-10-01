import os
import json
from typing import Optional, Dict, Any
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv
from .utils import generate_device_fingerprint, get_public_ip_address, get_user_agent, generate_nonce, current_timestamp_ms
from .build_guard import BUILD_ID
from .session_token_service import SessionTokenService
try:
    # Periodic integrity re-check before critical RPCs (defense-in-depth)
    from security.bootstrap import ensure_integrity_before_critical  # type: ignore
except Exception:
    ensure_integrity_before_critical = None

load_dotenv()

class SupabaseAuthService:
    """Supabase authentication service"""
    
    def __init__(self):
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment variables")
        
        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        self.current_user = None
        self.session = None
        self.session_token_service: SessionTokenService = SessionTokenService(self.client)
    
    def sign_up(self, email: str, password: str, username: str) -> Dict[str, Any]:
        """Register a new user"""
        try:
            # Create user with email and password
            response = self.client.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "username": username
                    }
                }
            })
            
            if response.user:
                # Create profile in profiles table
                profile_data = {
                    "id": response.user.id,
                    "username": username,
                    "email": email,
                    "is_active": True
                }

                self.client.table("profiles").insert(profile_data).execute()

                
                return {
                    "success": True,
                    "user": response.user,
                    "message": "User created successfully. Please verify your email address."
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to create user"
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Registration error: {str(e)}"
            }
    
    def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        """Sign in user with email and password"""
        try:
            response = self.client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user:
                # last_login handled server-side (trigger/RPC)

                # Get user profile
                profile_response = self.client.table("profiles").select("*").eq("id", response.user.id).execute()
                profile = profile_response.data[0] if profile_response.data else None
                
                self.current_user = response.user
                self.session = response.session
                try:
                    # Prime short-lived session token context (non-blocking failure)
                    device_fp = generate_device_fingerprint()
                    ip_addr = get_public_ip_address()
                    ua = get_user_agent()
                    self.session_token_service.set_context(
                        user_id=response.user.id,
                        build_id=BUILD_ID,
                        device_fp=device_fp,
                        ip=ip_addr,
                        user_agent=ua,
                    )
                    self.session_token_service.get_or_refresh()
                except Exception:
                    pass
                
                return {
                    "success": True,
                    "user": response.user,
                    "profile": profile,
                    "session": response.session
                }
            else:
                return {
                    "success": False,
                    "message": "Login failed"
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Login error: {str(e)}"
            }
    
    def sign_out(self) -> Dict[str, Any]:
        """Sign out current user"""
        try:
            self.client.auth.sign_out()
            self.current_user = None
            self.session = None
            
            return {
                "success": True,
                "message": "Successfully signed out"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Sign out error: {str(e)}"
            }
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Get current authenticated user"""
        try:
            user = self.client.auth.get_user()
            if user.user:
                # Get profile data
                profile_response = self.client.table("profiles").select("*").eq("id", user.user.id).execute()
                profile = profile_response.data[0] if profile_response.data else None
                
                return {
                    "user": user.user,
                    "profile": profile
                }
            return None
        except Exception:
            return None

    def get_access_token(self) -> Optional[str]:
        """Return the current session access token for authenticated API calls"""
        try:
            # Prefer live session from client
            session = self.client.auth.get_session()
            if session and getattr(session, "access_token", None):
                return session.access_token
        except Exception:
            pass
        # Fallback to stored session if available
        try:
            if self.session and getattr(self.session, "access_token", None):
                return self.session.access_token
        except Exception:
            pass
        return None

    def get_short_lived_session_token(self) -> Optional[str]:
        """Return a valid short-lived session token (<= 15 min), refreshing if needed."""
        try:
            token, _ = self.session_token_service.get_or_refresh()
            return token
        except Exception:
            return None

    def secure_rpc(self, fn_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call an RPC with short-lived session token + nonce + timestamp automatically.

        Returns a dict with keys: success (bool), data (any), message (str|None)
        """
        try:
            # Hard integrity re-check before critical RPCs (always required in production)
            if ensure_integrity_before_critical is not None:
                try:
                    ensure_integrity_before_critical(max_age_seconds=300)
                except Exception:
                    return {"success": False, "message": "integrity_failed"}
            token = self.get_short_lived_session_token()
            if not token:
                # Try one refresh attempt, then fail closed
                try:
                    token, _ = self.session_token_service.get_or_refresh()
                except Exception:
                    pass
                if not token:
                    return {"success": False, "message": "auth_required"}

            # Attach anti-replay headers as params (RPC-level). If you later move to HTTP headers
            # via edge functions, you can adapt accordingly.
            p = dict(params or {})
            p["p_token"] = token
            p["p_build_id"] = BUILD_ID
            # Some RPCs do not accept p_fp; avoid passing it to prevent parameter-mismatch errors
            try:
                # Some RPCs do not accept p_fp; avoid passing it to prevent parameter-mismatch errors
                # Keep p_fp for analysis-related RPCs as their SQL signature requires it.
                skip_fp_for = {
                    "decrement_ai_image_count_secure",
                    "decrement_ai_credits_secure",
                }
                if fn_name not in skip_fp_for:
                    p["p_fp"] = generate_device_fingerprint()
            except Exception:
                # Best-effort; if fingerprint fails, skip silently
                pass
            p["p_nonce"] = generate_nonce()
            p["p_ts"] = current_timestamp_ms()

            # Ensure PostgREST uses the user's JWT (not the short-lived session token)
            auth_jwt = None
            try:
                auth_jwt = self.get_access_token()
            except Exception:
                auth_jwt = None
            if not auth_jwt:
                # As a fallback, try to read from supabase client session
                try:
                    sess = self.client.auth.get_session()
                    if sess and getattr(sess, "access_token", None):
                        auth_jwt = sess.access_token
                except Exception:
                    pass
            if not auth_jwt:
                return {"success": False, "message": "auth_jwt_missing"}
            try:
                self.client.postgrest.auth(auth_jwt)
            except Exception:
                pass
            # Keep Authorization set to the user JWT for subsequent table operations
            resp = self.client.rpc(fn_name, p).execute()
            return {"success": True, "data": getattr(resp, "data", None)}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _ensure_postgrest_user_auth(self) -> bool:
        """Ensure PostgREST client uses the current user's JWT for table queries."""
        try:
            token = self.get_access_token()
            if not token:
                sess = self.client.auth.get_session()
                if sess and getattr(sess, "access_token", None):
                    token = sess.access_token
            if token:
                try:
                    self.client.postgrest.auth(token)
                except Exception:
                    pass
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _normalize_rpc_data(raw: Any) -> Optional[Dict[str, Any]]:
        """Make various RPC return shapes look like a dict with at least 'success'."""
        try:
            # Already a dict
            if isinstance(raw, dict):
                if 'success' not in raw and ('remaining' in raw or 'remaining_count' in raw):
                    raw = {**raw, 'success': True, 'remaining': raw.get('remaining', raw.get('remaining_count'))}
                # Map device restriction flags even if success missing
                msg_lower = str(raw.get('message', '')).lower()
                if ('restricted' in raw and raw.get('restricted') is True) or ('device_ip_already_used' in msg_lower or 'device_or_ip_already_used' in msg_lower):
                    raw = {**raw, 'success': False, 'restricted': True, 'message': 'device_ip_already_used'}
                return raw
            # Single-element list with dict
            if isinstance(raw, list) and raw and isinstance(raw[0], dict):
                return raw[0]
            # JSON string
            if isinstance(raw, str):
                import json as _json
                try:
                    obj = _json.loads(raw)
                    if isinstance(obj, dict):
                        return obj
                    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
                        return obj[0]
                except Exception:
                    pass
                s = raw.lower()
                if 'device_ip_already_used' in s or 'device_or_ip_already_used' in s:
                    return {"success": False, "restricted": True, "message": "device_ip_already_used"}
            # Primitive remaining count
            if isinstance(raw, int):
                return {"success": True, "remaining": raw}
            # Boolean success
            if isinstance(raw, bool):
                return {"success": bool(raw)}
        except Exception:
            pass
        return None
    
    def reset_password(self, email: str) -> Dict[str, Any]:
        """Send password reset email"""
        try:
            self.client.auth.reset_password_email(email)
            return {
                "success": True,
                "message": "Password reset email sent"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Password reset error: {str(e)}"
            }
    
    def update_profile(self, user_id: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user profile"""
        try:
            response = self.client.table("profiles").update(profile_data).eq("id", user_id).execute()
            return {
                "success": True,
                "data": response.data
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Profile update error: {str(e)}"
            }
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return self.get_current_user() is not None
    
    def get_plan_definition(self, plan_name: str) -> Dict[str, Any]:
        """Get plan definition from plan_definitions table"""
        try:
            response = self.client.table("plan_definitions").select("*").eq("name", plan_name).execute()
            if response.data:
                return {
                    "success": True,
                    "plan": response.data[0]
                }
            else:
                return {
                    "success": False,
                    "message": f"Plan '{plan_name}' not found"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error getting plan definition: {str(e)}"
            }
    
    def get_user_plan(self, user_id: str) -> Dict[str, Any]:
        """Get user's plan information"""
        try:
            # Ensure user JWT is attached for table read under RLS
            try:
                self._ensure_postgrest_user_auth()
            except Exception:
                pass
            # Try to get existing plan from database
            response = self.client.table("plans").select("*").eq("user_id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                plan_data = response.data[0]
                return {
                    "success": True,
                    "plan": plan_data
                }
            else:
                # Plan not found and no RPC result; do not fabricate a default
                return {
                    "success": False,
                    "message": "User plan not found in Supabase"
                }
        except Exception as e:
            print(f"Error getting user plan: {e}")
            return {
                "success": False,
                "message": f"Error getting user plan: {str(e)}"
            }
    
    def get_user_analysis_count(self, user_id: str) -> int:
        """Get user's remaining analysis count"""
        try:
            # Prefer authoritative server-side remaining count via secure RPC (source of truth)
            try:
                secure = self.secure_rpc('get_remaining_analysis_count_secure', {})
                if secure.get('success'):
                    norm = self._normalize_rpc_data(secure.get('data'))
                    if norm is not None:
                        remaining = norm.get('remaining', norm.get('remaining_count'))
                        try:
                            return int(0 if remaining is None else remaining)
                        except Exception:
                            pass
            except Exception:
                # Fallback below to plan table
                pass

            # Fallback: read from user's plan row (may be stale if server tracks usage elsewhere)
            plan_result = self.get_user_plan(user_id)
            if plan_result["success"]:
                raw_count = plan_result["plan"].get("analysis_count", 0)
                try:
                    return int(0 if raw_count is None else raw_count)
                except Exception:
                    return 0
            return 0
        except Exception as e:
            print(f"Error getting analysis count: {e}")
            return 0

    def get_remaining_analysis_count_secure_only(self) -> int | None:
        """Return remaining analysis credits strictly from secure RPC, without table fallback.

        Returns None if the secure RPC does not provide a parsable remaining value.
        """
        try:
            secure = self.secure_rpc('get_remaining_analysis_count_secure', {})
            if secure.get('success'):
                norm = self._normalize_rpc_data(secure.get('data'))
                if norm is not None:
                    remaining = norm.get('remaining', norm.get('remaining_count'))
                    try:
                        return int(0 if remaining is None else remaining)
                    except Exception:
                        return None
        except Exception:
            return None
        return None
    
    def can_use_ai_image(self, user_id: str) -> bool:
        """Check if user can use AI Image feature"""
        try:
            plan_result = self.get_user_plan(user_id)
            if plan_result["success"]:
                plan_type = plan_result["plan"].get("plan_type", "Free")
                # Plus and Elite plans can use AI Image
                return plan_type in ["Plus", "Elite"]
            return False
        except Exception as e:
            print(f"Error checking AI Image permission: {e}")
            return False
    
    def can_use_ai_review(self, user_id: str) -> bool:
        """Check if user can use AI Review feature"""
        try:
            plan_result = self.get_user_plan(user_id)
            if plan_result["success"]:
                plan_type = plan_result["plan"].get("plan_type", "Free")
                # Essential, Plus and Elite plans can use AI Review
                return plan_type in ["Essential", "Plus", "Elite"]
            return False
        except Exception as e:
            print(f"Error checking AI Review permission: {e}")
            return False
    
    def get_user_ai_image_count(self, user_id: str) -> int:
        """Get user's AI image count from plan"""
        try:
            plan_result = self.get_user_plan(user_id)
            if plan_result["success"]:
                raw_count = plan_result["plan"].get("ai_image_count", 0)
                try:
                    return int(0 if raw_count is None else raw_count)
                except Exception:
                    return 0
            return 0
        except Exception as e:
            print(f"Error getting AI image count: {e}")
            return 0
    
    def get_user_ai_credits(self, user_id: str) -> int:
        """Get user's AI credits from plan"""
        try:
            plan_result = self.get_user_plan(user_id)
            if plan_result["success"]:
                return plan_result["plan"].get("ai_credits", 0)
            return 0
        except Exception as e:
            print(f"Error getting AI credits: {e}")
            return 0
    
    def decrement_ai_image_count(self, user_id: str) -> Dict[str, Any]:
        """Decrement user's AI image count via secure server-side RPC (atomic)."""
        try:
            secure = self.secure_rpc('decrement_ai_image_count_secure', {})
            data = secure.get('data') if secure.get('success') else None
            norm = self._normalize_rpc_data(data)
            if norm is not None:
                if norm.get('success') is True:
                    remaining = norm.get('remaining', norm.get('remaining_count'))
                    return {"success": True, "message": "AI image count decremented", "remaining_count": remaining}
                return {"success": False, "message": norm.get('message', secure.get('message', 'Failed'))}
            if secure.get('success'):
                return {"success": False, "message": "Unknown RPC response"}
            return {"success": False, "message": secure.get('message', 'RPC call failed')}
        except Exception as e:
            return {"success": False, "message": f"Error decrementing AI image count: {str(e)}"}
    
    def decrement_ai_credits(self, user_id: str) -> Dict[str, Any]:
        """Decrement user's AI credits via secure server-side RPC (atomic)."""
        try:
            secure = self.secure_rpc('decrement_ai_credits_secure', {})
            data = secure.get('data') if secure.get('success') else None
            norm = self._normalize_rpc_data(data)
            if norm is not None:
                if norm.get('success') is True:
                    remaining = norm.get('remaining', norm.get('remaining_credits'))
                    return {"success": True, "message": "AI credits decremented", "remaining_credits": remaining}
                return {"success": False, "message": norm.get('message', secure.get('message', 'Failed'))}
            if secure.get('success'):
                return {"success": False, "message": "Unknown RPC response"}
            return {"success": False, "message": secure.get('message', 'RPC call failed')}
        except Exception as e:
            return {"success": False, "message": f"Error decrementing AI credits: {str(e)}"}
    
    def add_ai_image_count(self, user_id: str, amount: int) -> Dict[str, Any]:
        """Add AI image credits via secure server-side RPC (atomic, RLS-safe)."""
        try:
            secure = self.secure_rpc('add_ai_image_count_secure', {'p_amount': amount})
            data = secure.get('data') if secure.get('success') else None
            norm = self._normalize_rpc_data(data)
            if norm is not None:
                if norm.get('success') is True:
                    return {"success": True, "message": f"Added {amount} AI image count", "new_count": norm.get('new_count')}
                return {"success": False, "message": norm.get('message', secure.get('message', 'Failed'))}
            if secure.get('success'):
                return {"success": False, "message": "Unknown RPC response"}
            return {"success": False, "message": secure.get('message', 'RPC call failed')}
        except Exception as e:
            return {"success": False, "message": f"Error adding AI image count: {str(e)}"}
    
    def get_plan_restrictions(self, user_id: str) -> Dict[str, Any]:
        """Get all plan restrictions for a user"""
        try:
            plan_result = self.get_user_plan(user_id)
            
            if plan_result["success"]:
                plan_data = plan_result["plan"]
                
                # Plan type sütunu
                plan_type = plan_data.get("plan_type", "Free")
                
                restrictions = {
                    "plan_type": plan_type,
                    "analysis_count": plan_data.get("analysis_count", 0),
                    "ai_image_enabled": self.can_use_ai_image(user_id),
                    "ai_review_enabled": self.can_use_ai_review(user_id)
                }
                
                return {
                    "success": True,
                    "restrictions": restrictions
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to get plan restrictions"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error getting plan restrictions: {str(e)}"
            }
    
    def decrement_analysis_count(self, user_id: str) -> Dict[str, Any]:
        """Decrement user's analysis count via secure server-side RPC (atomic)."""
        return self.decrement_analysis_count_with_device_check(user_id)
    
    def update_user_plan(self, user_id: str, plan_type: str) -> Dict[str, Any]:
        """Update user's plan via secure server-side RPC (atomic, RLS-safe)."""
        try:
            secure = self.secure_rpc('update_user_plan_secure', {'p_plan_type': plan_type})
            data = secure.get('data') if secure.get('success') else None
            norm = self._normalize_rpc_data(data)
            if norm is not None:
                if norm.get('success') is True:
                    return {"success": True, "message": f"Plan updated to {plan_type}", "plan": norm.get('plan')}
                return {"success": False, "message": norm.get('message', secure.get('message', 'Failed'))}
            if secure.get('success'):
                return {"success": False, "message": "Unknown RPC response"}
            return {"success": False, "message": secure.get('message', 'RPC call failed')}
        except Exception as e:
            return {"success": False, "message": f"Error updating plan: {str(e)}"}
    
    def check_device_restriction(self, user_id: str) -> Dict[str, Any]:
        """Check if free user is restricted due to device/IP tracking"""
        try:
            ip_address = get_public_ip_address()
            user_agent = get_user_agent()
            device_fp = generate_device_fingerprint()
            secure = self.secure_rpc('check_device_restriction_secure', {
                'p_ip': ip_address,
                'p_user_agent': user_agent,
                'p_fp': device_fp,
            })
            data = secure.get('data') if secure.get('success') else None
            norm = self._normalize_rpc_data(data)
            if norm is not None:
                if norm.get('success') is True:
                    return {"success": True, "restricted": bool(norm.get('restricted', False)), "message": norm.get('message', 'OK')}
                return {"success": False, "restricted": bool(norm.get('restricted', False)), "message": norm.get('message', 'restricted')}
            # Server did not return a normalized shape; surface RPC error only
            return {"success": False, "message": secure.get('message', 'rpc_failed')}
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error checking device restriction: {str(e)}"
            }
    
    def record_device_usage(self, user_id: str) -> Dict[str, Any]:
        """Record device usage for tracking"""
        try:
            device_fingerprint = generate_device_fingerprint()
            ip_address = get_public_ip_address()
            user_agent = get_user_agent()

            try:
                secure = self.secure_rpc('record_device_usage_secure', {
                    'p_ip': ip_address,
                    'p_user_agent': user_agent,
                    'p_fp': device_fingerprint,
                })
                if secure.get('success'):
                    return {"success": True, "message": "Device usage recorded (secure)"}
            except Exception:
                pass
            return {"success": False, "message": "Failed to record device usage"}
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Error recording device usage: {str(e)}"
            }
    
    def decrement_analysis_count_with_device_check(self, user_id: str) -> Dict[str, Any]:
        """Decrement analysis count with server-side device restriction (atomically via RPC)"""
        try:
            # Her plan için SECURE RPC çağır: Sunucu paid/free ayrımını kendisi yapsın
            ip_address = get_public_ip_address()
            user_agent = get_user_agent()

            # Önce free abuse enforcement yapan RPC'yi çağır
            secure = self.secure_rpc(
                'enforce_free_device_and_decrement_secure',
                {
                    'p_ip': ip_address,
                    'p_user_agent': user_agent
                }
            )

            try:
                print(f"[RPC] enforce_free_device_and_decrement_secure success={secure.get('success')} message={secure.get('message')} type={type(secure.get('data')).__name__}")
            except Exception:
                pass

            # Eğer enforcement başarısızsa: Free kullanıcılar için asla fallback yapma.
            # Paid plan ise server-side generic decrement RPC'ye güvenli fallback yap.
            if not secure.get('success') or secure.get('data') is None:
                err_msg = str(secure.get('message', '')).lower()
                if 'device_ip_already_used' in err_msg or 'device_or_ip_already_used' in err_msg or 'restricted": true' in err_msg:
                    return {"success": False, "message": "device_ip_already_used", "restricted": True}
                # Planı RLS ile serverdan oku; yalnızca Non-Free için fallback uygula
                try:
                    plan_result = self.get_user_plan(user_id)
                    if plan_result.get('success') and str(plan_result['plan'].get('plan_type', 'Free')) != 'Free':
                        fallback = self.secure_rpc(
                            'decrement_analysis_count_secure',
                            {
                                'p_ip': ip_address,
                                'p_user_agent': user_agent
                            }
                        )
                        if fallback.get('success'):
                            secure = fallback
                        else:
                            return {"success": False, "message": fallback.get('message', 'rpc_failed')}
                    else:
                        return {"success": False, "message": secure.get('message', 'rpc_failed')}
                except Exception:
                    return {"success": False, "message": secure.get('message', 'rpc_failed')}

            data = secure.get('data') if secure.get('success') else None
            norm = self._normalize_rpc_data(data)
            if norm is not None:
                if norm.get('success') is True:
                    # Prefer 'remaining'; some deployments may return success without remaining value
                    remaining = norm.get('remaining', norm.get('remaining_count'))
                    if remaining is None:
                        # Follow-up: attempt generic decrement to obtain authoritative remaining (no double-decrement risk
                        # if enforce RPC was only a validator). If it fails, continue without overriding.
                        try:
                            fallback_after_ok = self.secure_rpc(
                                'decrement_analysis_count_secure',
                                {
                                    'p_ip': ip_address,
                                    'p_user_agent': user_agent
                                }
                            )
                            if fallback_after_ok.get('success'):
                                norm2 = self._normalize_rpc_data(fallback_after_ok.get('data'))
                                if norm2 is not None and norm2.get('success') is True:
                                    remaining = norm2.get('remaining', norm2.get('remaining_count'))
                        except Exception:
                            pass

                    # Best-effort device usage record to strengthen future checks
                    try:
                        self.record_device_usage(user_id)
                    except Exception:
                        pass
                    return {"success": True, "message": f"Analysis started. {remaining} credits remaining.", "remaining_count": remaining}
                return {"success": False, "message": norm.get('message', secure.get('message', 'Analysis blocked')), "restricted": norm.get('restricted', False)}

            # Surface server-returned message if available
            if not secure.get('success'):
                msg = secure.get('message')
                if isinstance(msg, str) and msg.strip():
                    return {"success": False, "message": msg}
            # If message indicates device restriction, surface it explicitly
            msg = str(secure.get('message', '')).lower()
            if 'device_ip_already_used' in msg or 'device_or_ip_already_used' in msg:
                return {"success": False, "message": "device_ip_already_used", "restricted": True}
            # Last resort: actively check device restriction via table query (server-enforced logic)
            try:
                check = self.check_device_restriction(user_id)
                if check.get('success') and check.get('restricted'):
                    return {"success": False, "message": check.get('message', 'device_ip_already_used'), "restricted": True}
            except Exception:
                pass
            # If user is Free, treat unknown failure as device restriction to surface the proper dialog
            try:
                plan_result = self.get_user_plan(user_id)
                if plan_result.get('success') and plan_result['plan'].get('plan_type') == 'Free':
                    return {"success": False, "message": "device_ip_already_used", "restricted": True}
            except Exception:
                pass
            return {"success": False, "message": "Unexpected response from server"}

        except Exception as e:
            return {
                "success": False,
                "message": f"Error in analysis with device check: {str(e)}"
            }
    
    def get_openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key via secure RPC only."""
        try:
            secure = self.secure_rpc('get_api_key_secure', {'key_name_param': 'OPENAI_API_KEY'})
            api_key = secure.get('data') if secure.get('success') else None
            if isinstance(api_key, str) and api_key.strip():
                return api_key.strip()
            return None
        except Exception:
            return None