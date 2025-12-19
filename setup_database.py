"""
Manual database setup script
Run this if automatic database creation fails
"""

import psycopg2
import sys

def setup_database():
    """Manually create the database"""
    try:
        # Connect to default postgres database
        print("Connecting to PostgreSQL...")
        conn = psycopg2.connect(
            database="postgres",
            user="postgres",
            password="root",
            host="localhost"
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = 'gpt_prompt-responses'"
        )
        exists = cursor.fetchone()
        
        if exists:
            print("Database 'gpt_prompt-responses' already exists!")
            return True
        
        # Create database
        print("Creating database 'gpt_prompt-responses'...")
        cursor.execute('CREATE DATABASE "gpt_prompt-responses"')
        print("✓ Database created successfully!")
        
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.OperationalError as e:
        print(f"✗ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure PostgreSQL is installed and running")
        print("2. Check if the credentials are correct:")
        print("   - User: postgres")
        print("   - Password: root")
        print("   - Host: localhost")
        print("3. On Windows, make sure PostgreSQL service is running")
        print("4. Try running this command manually:")
        print('   psql -U postgres -c "CREATE DATABASE \\"gpt_prompt-responses\\";"')
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("PostgreSQL Database Setup")
    print("=" * 50)
    success = setup_database()
    if success:
        print("\n✓ Setup complete! You can now run app.py")
    else:
        print("\n✗ Setup failed. Please check the errors above.")
        sys.exit(1)

