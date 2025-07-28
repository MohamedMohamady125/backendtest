

from passlib.hash import bcrypt
import mysql.connector

def test_bcrypt_basic():
    """Test basic bcrypt functionality"""
    password = "MmmM1234!"
    
    print("=== BCRYPT BASIC TEST ===")
    print(f"Original password: {password}")
    
    # Generate hash
    password_hash = bcrypt.hash(password)
    print(f"Generated hash: {password_hash}")
    print(f"Hash length: {len(password_hash)}")
    
    # Test verification
    is_valid = bcrypt.verify(password, password_hash)
    print(f"Verification result: {is_valid}")
    
    # Test with wrong password
    wrong_verification = bcrypt.verify("wrongpassword", password_hash)
    print(f"Wrong password test: {wrong_verification}")
    
    return password_hash

def test_database_hash(password, stored_hash):
    """Test hash stored in database"""
    print("\n=== DATABASE HASH TEST ===")
    print(f"Password: {password}")
    print(f"Stored hash: {stored_hash}")
    print(f"Stored hash length: {len(stored_hash)}")
    
    # Test verification
    is_valid = bcrypt.verify(password, stored_hash)
    print(f"Database verification result: {is_valid}")
    
    return is_valid

def generate_multiple_hashes(password):
    """Generate multiple hashes to see if they're different"""
    print(f"\n=== MULTIPLE HASH TEST ===")
    print(f"Password: {password}")
    
    for i in range(3):
        hash_result = bcrypt.hash(password)
        verification = bcrypt.verify(password, hash_result)
        print(f"Hash {i+1}: {hash_result}")
        print(f"Verification {i+1}: {verification}")
        print()

def test_with_database_connection():
    """Test with actual database connection"""
    print("\n=== DATABASE CONNECTION TEST ===")
    
    # Your database config
    DB_CONFIG = {
        'host': 'crossover.proxy.rlwy.net',
        'user': 'root',
        'password': 'omqxUvCPxFkGeCYjMYzfylckhYzcFwWV',
        'database': 'railway',
        'port': 42459,
        'charset': 'utf8mb4',
        'use_unicode': True,
    }
    
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor(dictionary=True)
        
        # Get a user's hash from database
        cursor.execute("SELECT email, password_hash FROM users LIMIT 1")
        user = cursor.fetchone()
        
        if user:
            print(f"Found user: {user['email']}")
            print(f"Hash from DB: {user['password_hash']}")
            print(f"Hash length: {len(user['password_hash'])}")
            
            # Test with a known password (you'll need to replace this)
            test_password = "MmmM1234!"  # Replace with actual password
            verification = bcrypt.verify(test_password, user['password_hash'])
            print(f"Verification with '{test_password}': {verification}")
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    # Test 1: Basic bcrypt functionality
    generated_hash = test_bcrypt_basic()
    
    # Test 2: Multiple hashes
    generate_multiple_hashes("MmmM1234!")
    
    # Test 3: Test with a hash you put in the database
    # Replace this with the actual hash you stored in your database
    database_hash = "$2b$12$EXAMPLE_REPLACE_WITH_YOUR_ACTUAL_HASH"
    # test_database_hash("MmmM1234!", database_hash)
    
    # Test 4: Test with actual database
    # test_with_database_connection()
    
    print("\n=== RECOMMENDED SOLUTION ===")
    print("1. Use this exact hash generation method:")
    print("   from passlib.hash import bcrypt")
    print("   password_hash = bcrypt.hash('your_password')")
    print()
    print("2. Store the hash in database exactly as generated")
    print()
    print("3. Use bcrypt.verify('password', stored_hash) for login")
    print()
    print("4. Make sure your database column is VARCHAR(128) or larger")
    print()
    print("=== FRESH HASH FOR 'MmmM1234!' ===")
    fresh_hash = bcrypt.hash("MmmM1234!")
    print(f"Hash: {fresh_hash}")
    print(f"Verification: {bcrypt.verify('MmmM1234!', fresh_hash)}")