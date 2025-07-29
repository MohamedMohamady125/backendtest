# app/config.py - FIXED VERSION for Railway deployment
import os

# Only load .env file in development (when .env file exists)
# Railway injects environment variables directly, no .env file needed
if os.path.exists('.env'):
    from dotenv import load_dotenv
    load_dotenv()
    print("🔧 Loaded .env file for development")
else:
    print("🔧 Using Railway environment variables (production)")

class Settings:
    def __init__(self):
        # Database Configuration
        self.DB_HOST = "crossover.proxy.rlwy.net"
        self.DB_USER = "root"
        self.DB_PASSWORD = "omqxUvCPxFkGeCYjMYzfylckhYzcFwWV"
        self.DB_NAME = "railway"
        self.DB_PORT = 42459
        
        # JWT Configuration
        self.JWT_SECRET = os.getenv("JWT_SECRET", "my-local-super-secret-key-123")
        self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
        
        # Email Configuration
        self.SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
        self.FROM_EMAIL = os.getenv("FROM_EMAIL")
        
        # VAPID Configuration
        self.VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY")
        self.VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY")
        self.VAPID_EMAIL = os.getenv("VAPID_EMAIL")
        
        # Debug output
        print("=" * 50)
        print("🔧 FASTAPI CONFIGURATION")
        print("=" * 50)
        print(f"🔍 DB_HOST: {self.DB_HOST}")
        print(f"🔍 DB_PORT: {self.DB_PORT}")
        print(f"🔍 JWT_SECRET: {self.JWT_SECRET}")
        print(f"🔍 JWT_ALGORITHM: {self.JWT_ALGORITHM}")
        print(f"🔍 JWT_SECRET length: {len(self.JWT_SECRET)}")
        print("=" * 50)
        
        # VAPID Debug output
        vapid_private_preview = self.VAPID_PRIVATE_KEY[:20] + "..." if self.VAPID_PRIVATE_KEY else "None"
        vapid_public_preview = self.VAPID_PUBLIC_KEY[:20] + "..." if self.VAPID_PUBLIC_KEY else "None"
        
        print(f"🔧 Debug VAPID_PRIVATE_KEY: {vapid_private_preview}")
        print(f"🔧 Debug VAPID_PUBLIC_KEY: {vapid_public_preview}")
        print(f"🔧 Debug VAPID_EMAIL: {self.VAPID_EMAIL}")
        print(f"🔧 Environment has {len(os.environ)} variables")
        
        # Additional debug - show all VAPID-related env vars
        print("🔧 All environment variables containing 'VAPID':")
        for key, value in os.environ.items():
            if 'VAPID' in key:
                preview = value[:20] + "..." if len(value) > 20 else value
                print(f"   {key}: {preview}")

# Create global settings instance
settings = Settings()