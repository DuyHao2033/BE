import re
import logging
from typing import Optional
from ldap3 import Server, Connection, ALL, Tls, SUBTREE
import ssl
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.models.organization import Organization
from app.core.security import hash_password
import uuid

logger = logging.getLogger(__name__)

class AuthService:
    @staticmethod
    def verify_google_token(token: str) -> dict:
        """Verify Google ID token and check constraints."""
        try:
            # Verify the token
            id_info = id_token.verify_oauth2_token(
                token, 
                google_requests.Request(), 
                settings.GOOGLE_CLIENT_ID
            )

            email = id_info.get("email")
            if not email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email not provided in Google token"
                )

            # Check domain
            domain = email.split("@")[-1]
            allowed_domains = settings.OAUTH_ALLOWED_DOMAINS.split(",")
            if domain not in allowed_domains:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Domain {domain} is not allowed. Please use your @{settings.OAUTH_ALLOWED_DOMAINS} account."
                )

            # Check for 'k+digit' constraint
            # Pattern: k followed by one or more digits before the @
            local_part = email.split("@")[0]
            if re.search(r"k\d+", local_part.lower()):
                 raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Student accounts (k+number) are not authorized to access this dashboard."
                )

            return id_info
        except ValueError as e:
            logger.error(f"Google token verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google token"
            )

    @staticmethod
    def verify_ldap_credentials(username_or_email: str, password: str) -> dict:
        """Verify credentials against LDAP server."""
        if not settings.LDAP_SERVER_HOST:
            raise HTTPException(status_code=500, detail="LDAP is not configured")

        try:
            tls = None
            if settings.LDAP_USE_TLS:
                tls = Tls(
                    validate=ssl.CERT_NONE if not settings.LDAP_VALIDATE_CERT else ssl.CERT_REQUIRED, 
                    version=ssl.PROTOCOL_TLS_CLIENT if hasattr(ssl, 'PROTOCOL_TLS_CLIENT') else ssl.PROTOCOL_TLSv1_2
                )

            # Direct SSL (LDAPS) is typically on 636. StartTLS is on 389.
            is_ldaps = settings.LDAP_USE_TLS and settings.LDAP_SERVER_PORT == 636
            use_start_tls = settings.LDAP_USE_TLS and not is_ldaps
            
            server = Server(
                settings.LDAP_SERVER_HOST, 
                port=settings.LDAP_SERVER_PORT, 
                use_ssl=is_ldaps, 
                tls=tls,
                get_info=ALL
            )

            # Use context manager for the main app connection
            with Connection(
                server, 
                user=settings.LDAP_APP_DN, 
                password=settings.LDAP_APP_PASSWORD,
                authentication='SIMPLE',
                raise_exceptions=False
            ) as conn:
                
                if use_start_tls:
                    if not conn.start_tls():
                        logger.error(f"LDAP StartTLS failed: {conn.result}")
                        raise HTTPException(status_code=500, detail="LDAP TLS initiation failed")

                if not conn.bind():
                    logger.error(f"LDAP app bind failed: {conn.result}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="LDAP authentication system error"
                    )

                # Search for user by email or username
                search_filter = f"(|({settings.LDAP_ATTRIBUTE_FOR_MAIL}={username_or_email})({settings.LDAP_ATTRIBUTE_FOR_USERNAME}={username_or_email}))"
                conn.search(
                    search_base=settings.LDAP_SEARCH_BASE,
                    search_filter=search_filter,
                    search_scope=SUBTREE,
                    attributes=[settings.LDAP_ATTRIBUTE_FOR_MAIL, 'displayName', 'cn']
                )

                if not conn.entries:
                    logger.warning(f"LDAP user not found: {username_or_email}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid LDAP credentials"
                    )

                entry = conn.entries[0]
                user_dn = entry.entry_dn
                entry_attrs = entry.entry_attributes_as_dict
                
                # Extract email safely
                email_attr = settings.LDAP_ATTRIBUTE_FOR_MAIL
                user_email = ""
                if email_attr in entry_attrs and entry_attrs[email_attr]:
                    user_email = str(entry_attrs[email_attr][0])
                elif "@" in username_or_email:
                    user_email = username_or_email
                else:
                    # Generic fallback if no email attribute
                    user_email = f"{username_or_email}@siu.edu.vn" if "@" not in username_or_email else username_or_email
                
                # Extract full name safely
                user_full_name = 'LDAP User'
                if 'displayName' in entry_attrs and entry_attrs['displayName']:
                    user_full_name = str(entry_attrs['displayName'][0])
                elif 'cn' in entry_attrs and entry_attrs['cn']:
                    user_full_name = str(entry_attrs['cn'][0])

                # Now try to bind with user's own credentials
                with Connection(server, user=user_dn, password=password, raise_exceptions=False) as user_conn:
                    if use_start_tls:
                        user_conn.start_tls()
                    
                    if user_conn.bind():
                        return {
                            "email": user_email,
                            "full_name": user_full_name
                        }
                    else:
                        logger.warning(f"LDAP bind failed for user {user_dn}: {user_conn.result}")
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid LDAP credentials"
                        )

        except Exception as e:
            logger.error(f"LDAP error: {e}")
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=500, detail="LDAP authentication service error")

    @staticmethod
    def get_or_create_external_user(db: Session, email: str, full_name: str) -> User:
        """Find user by email. If not found, provision them."""
        user = db.query(User).filter(User.email == email).first()
        if not user:
            # Auto-create for first-time use
            logger.info(f"Auto-provisioning user: {email} ({full_name})")
            
            # Use 'siu' organization as default, or fallback to the first one available
            org = db.query(Organization).filter(Organization.slug == "siu-university").first()
            if not org:
                from sqlalchemy import asc
                org = db.query(Organization).order_by(asc(Organization.created_at)).first()
            
            org_id = org.id if org else None

            # For LDAP/OIDC users, we set a random password as they won't use it.
            user = User(
                email=email,
                full_name=full_name,
                role="issuer",  # Default role
                password_hash=hash_password(str(uuid.uuid4())),
                is_active=True,
                organization_id=org_id
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user
        
        if not user.is_active:
             raise HTTPException(status_code=403, detail="User account is deactivated")
             
        return user
