from flask import Flask, render_template, request, url_for, flash, redirect, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
import os
from dotenv import load_dotenv
from datetime import datetime
import json
import re
import psycopg2
from openai import OpenAI


load_dotenv()

# Core configuration from environment (for local dev, see env_template.txt)
model = os.getenv("MODEL")
api_key = os.getenv("API_KEY")

# Support for multiple providers:
# - Groq (FREE, no credit card required): https://console.groq.com/
# - Ollama (FREE, local): http://localhost:11434
# - OpenAI: Leave API_BASE_URL empty
# - Together AI: https://api.together.xyz/v1 (requires $5 deposit)
api_base_url = os.getenv("API_BASE_URL", None)
if api_base_url:
    client = OpenAI(api_key=api_key, base_url=api_base_url)
else:
    client = OpenAI(api_key=api_key)

google_client_id = os.getenv("GOOGLE_CLIENT_ID")

# Database URLs:
# - DATABASE_URL: used by SQLAlchemy (e.g. postgresql+psycopg2://user:pass@host:5432/dbname)
# - DATABASE_URL_PG: used by psycopg2 directly (e.g. postgresql://user:pass@host:5432/dbname)
sqlalchemy_db_url = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:root@localhost:5432/gpt_prompt-responses",
)
psycopg_db_url = os.getenv("DATABASE_URL_PG", None)

# Control whether we try to auto-create the database (useful only for local dev)
AUTO_CREATE_DB = os.getenv("AUTO_CREATE_DB", "true").lower() == "true"

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = sqlalchemy_db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

SECRET_KEY = os.getenv("SECRET_KEY", "many random bytes")
app.secret_key = SECRET_KEY

# Initialize database tables on app startup (critical for production)
# This ensures tables exist when running with gunicorn
def initialize_database():
    """Initialize database tables - called on app startup"""
    with app.app_context():
        # First, test database connection
        try:
            print("Testing database connection...")
            db.engine.connect()
            print("✓ Database connection successful")
        except Exception as conn_error:
            print(f"✗ Database connection failed: {conn_error}")
            print("⚠ Cannot create tables without database connection")
            return False
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"Attempting to create database tables (attempt {attempt + 1}/{max_retries})...")
                print(f"  Database URL: {sqlalchemy_db_url[:50]}...")  # Show first 50 chars
                
                # Create all tables defined by SQLAlchemy models
                db.create_all()
                print("✓ Database tables initialized successfully!")
                
                # Verify table exists
                from sqlalchemy import inspect
                inspector = inspect(db.engine)
                tables = inspector.get_table_names()
                print(f"  Found tables: {tables}")
                
                if 'new_user_creds' in tables:
                    print("✓ Verified 'new_user_creds' table exists")
                    return True
                else:
                    print(f"⚠ Warning: 'new_user_creds' table not found after creation (attempt {attempt + 1}/{max_retries})")
                    print(f"  Available tables: {tables}")
                    
                    # Try to create table manually using raw SQL as fallback
                    if attempt == max_retries - 1:
                        print("  Attempting to create table manually using raw SQL...")
                        try:
                            from sqlalchemy import text
                            # Drop table if exists (for testing)
                            # db.session.execute(text("DROP TABLE IF EXISTS new_user_creds"))
                            # db.session.commit()
                            
                            create_table_sql = text("""
                                CREATE TABLE IF NOT EXISTS new_user_creds (
                                    "sNo" SERIAL PRIMARY KEY,
                                    name VARCHAR(200) NOT NULL,
                                    email VARCHAR(200) UNIQUE NOT NULL,
                                    password VARCHAR(200),
                                    google_id VARCHAR(200) UNIQUE
                                )
                            """)
                            db.session.execute(create_table_sql)
                            db.session.commit()
                            print("✓ Executed manual CREATE TABLE statement")
                            
                            # Verify again
                            inspector = inspect(db.engine)
                            tables = inspector.get_table_names()
                            print(f"  Tables after manual creation: {tables}")
                            if 'new_user_creds' in tables:
                                print("✓ Verified 'new_user_creds' table exists after manual creation")
                                return True
                            else:
                                print("✗ Table still not found after manual creation")
                        except Exception as manual_error:
                            print(f"✗ Failed to create table manually: {manual_error}")
                            import traceback
                            traceback.print_exc()
                    
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(2)  # Wait 2 seconds before retry
            except Exception as e:
                print(f"✗ Error initializing database tables (attempt {attempt + 1}/{max_retries}): {e}")
                import traceback
                traceback.print_exc()
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2)  # Wait 2 seconds before retry
                else:
                    print("⚠ Failed to initialize database tables after retries. App will continue but may have issues.")
        return False

# Initialize on startup
initialize_database()


# Create database if it doesn't exist (for local PostgreSQL only)
def create_database_if_not_exists():
    """Create the database if it doesn't exist (local dev helper)."""
    # In hosted environments like Render/Neon, the database is managed
    # by the provider and this function should be disabled via AUTO_CREATE_DB.
    try:
        # First, connect to the default 'postgres' database
        admin_conn = psycopg2.connect(
            database="postgres",
            user="postgres",
            password="root",
            host="localhost",
        )
        admin_conn.autocommit = True
        admin_cursor = admin_conn.cursor()

        # Check if database exists
        admin_cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = 'gpt_prompt-responses'"
        )
        exists = admin_cursor.fetchone()

        if not exists:
            # Create the database
            admin_cursor.execute('CREATE DATABASE "gpt_prompt-responses"')
            print("✓ Database 'gpt_prompt-responses' created successfully!")
        else:
            print("✓ Database 'gpt_prompt-responses' already exists.")

        admin_cursor.close()
        admin_conn.close()
        return True
    except psycopg2.OperationalError as e:
        print(f"✗ Error connecting to PostgreSQL (local dev): {e}")
        print("\nTroubleshooting:")
        print("1. Make sure PostgreSQL is installed and running")
        print("2. Check if the credentials (user: postgres, password: root) are correct")
        print("3. Verify PostgreSQL is listening on localhost:5432")
        print('\nTo create the database manually, run:')
        print('  psql -U postgres -c "CREATE DATABASE \\"gpt_prompt-responses\\";"')
        return False
    except psycopg2.Error as e:
        print(f"✗ Error creating database: {e}")
        return False


# Create database if needed (local dev only)
if AUTO_CREATE_DB:
    db_created = create_database_if_not_exists()
else:
    db_created = True

# Now connect to the actual database
try:
    if psycopg_db_url:
        # Hosted or custom database URL
        conn = psycopg2.connect(psycopg_db_url)
    else:
        # Local default database
        conn = psycopg2.connect(
            database="gpt_prompt-responses",
            user="postgres",
            password="root",
            host="localhost",
        )
    cursor = conn.cursor()
    print("✓ Connected to database successfully!")
except psycopg2.OperationalError as e:
    print(f"✗ Failed to connect to database: {e}")
    print("Please ensure PostgreSQL is running and the database exists.")
    conn = None
    cursor = None


class UserCreds(db.Model):
    __tablename__ = 'new_user_creds'
    sNo = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=True)
    google_id = db.Column(db.String(200), unique=True)

    def __init__(self, name, email, password=None, google_id=None):
        self.name = name
        self.email = email
        self.password = password
        self.google_id = google_id


# creates db table based on the email
def create_db_table(email):
    table_name = f"{email.replace('@', '_').replace('.', '_')}_data"

    class Table(db.Model):
        __tablename__ = table_name
        sNo = db.Column(db.Integer, primary_key=True)
        prompt = db.Column(db.String(5000))
        responses = db.Column(db.String(8000))
        history = db.Column(db.JSON)
        timestamp = db.Column(db.DateTime, default=datetime.now())

        __table_args__ = {'extend_existing': True}

        def __init__(self, prompt, responses, history, timestamp):
            self.prompt = prompt
            self.responses = responses
            self.history = history
            self.timestamp = timestamp

    return Table


@app.route("/", methods=['POST', 'GET'])
def signup_page():
    if request.method == 'POST':
        if request.is_json:
            data = request.json
            email = data.get("email")
            name = data.get("given_name")
            google_id = data.get("sub")

            # Check for existing email using SQLAlchemy (no raw cursor)
            try:
                existing_user = UserCreds.query.filter_by(email=email).first()
            except Exception as e:
                print(f"Database query error: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({"success": False, "error": f"Database error: {str(e)}"})

            if existing_user is not None:
                # flash('USER ALREADY EXISTS!', 'error')
                # Construct absolute URL using request
                redirect_url = url_for('user_endpoint', username=name, _external=True)
                if not redirect_url.startswith('http'):
                    # Fallback if _external doesn't work
                    redirect_url = f"{request.scheme}://{request.host}{url_for('user_endpoint', username=name)}"
                return jsonify({"success": True, "redirect_url": redirect_url})
            else:
                cred_table = UserCreds(name=name, email=email, google_id=google_id)
                db.session.add(cred_table)
                db.session.commit()

                # Create user-specific table
                create_user_table(email)

                flash('Login Successful!', 'success')
                # Construct absolute URL using request
                redirect_url = url_for('user_endpoint', username=name, _external=True)
                if not redirect_url.startswith('http'):
                    # Fallback if _external doesn't work
                    redirect_url = f"{request.scheme}://{request.host}{url_for('user_endpoint', username=name)}"
                return jsonify({"success": True, "redirect_url": redirect_url})
        else:
            name = request.form.get("name")
            email = request.form.get("email")
            unhashed_password = request.form.get("password")
            password = bcrypt.generate_password_hash(unhashed_password).decode('utf-8')

            # Check for existing email using SQLAlchemy (no raw cursor)
            try:
                existing_user = UserCreds.query.filter_by(email=email).first()
            except Exception as e:
                print(f"Database query error: {e}")
                import traceback
                traceback.print_exc()
                flash(f'Database error: {str(e)}', 'error')
                return redirect(url_for('signup_page'))

            if existing_user is not None:
                flash("USER ALREADY EXISTS!", "error")
                return redirect(url_for('signup_page'))
            else:
                cred_table = UserCreds(name=name, email=email, password=password)
                db.session.add(cred_table)
                db.session.commit()

                # Create user-specific table
                create_user_table(email)
                flash('Registered Successfully!', 'success')
                return redirect(url_for('login_page'))
    return render_template('signup.html', google_client_id=google_client_id or '')


@app.route("/login", methods=["POST", "GET"])
def login_page():
    if request.method == 'POST':
        if request.is_json:
            data = request.json
            email = data.get("email")
            password = data.get("ud")

            user = UserCreds.query.filter_by(email=email).first()
            # print(email, user.email)
            if user is not None and email == user.email:
                username = user.name
                flash('Login Successful!', 'error')
                # Construct absolute URL using request
                redirect_url = url_for('user_endpoint', username=username, _external=True)
                if not redirect_url.startswith('http'):
                    # Fallback if _external doesn't work
                    redirect_url = f"{request.scheme}://{request.host}{url_for('user_endpoint', username=username)}"
                return jsonify({"success": True, "redirect_url": redirect_url})
            elif user is None:
                flash('USER NOT FOUND!', 'error')
                redirect_url = url_for('signup_page', _external=True)
                if not redirect_url.startswith('http'):
                    redirect_url = f"{request.scheme}://{request.host}/"
                return jsonify({"success": True, "redirect_url": redirect_url})
        else:
            email = request.form.get("email")
            password = request.form.get("password")

            user = UserCreds.query.filter_by(email=email).first()

            if user and bcrypt.check_password_hash(user.password, password):
                username = user.name
                flash('Login Successful!', 'success')
                return redirect(url_for('user_endpoint', username=username))
            else:
                flash('Invalid Credentials, Please try again!', 'error')

    return render_template('login.html', google_client_id=google_client_id or '')


@app.route("/<username>", methods=['POST', 'GET'])
def user_endpoint(username):
    user = UserCreds.query.filter_by(name=username).first()
    if not user:
        return "User not found", 404

    email = user.email
    table_model = create_db_table(email)

    if request.method == 'POST':
        prompt_data = request.form["prompt_data"]
        history = request.form.get("history")
        if history:
            history = json.loads(history)
        else:
            history = []
        history.append({"role": "user", "content": prompt_data})

        # Enhanced system prompt for generating interactive form JSON
        system_prompt = """You are an assistant designed to extract key indicators and trading conditions from user queries and generate a JSON structure that will be used to create an interactive jQuery form.

IMPORTANT: You must return ONLY valid JSON (no markdown, no explanations, no code blocks).

Example input: "buy nifty when rsi<30 and ema<vwap. squareoff buying at 3pm. Sell when reverse conditions. Squareoff selling at 4."

Example output format:
{
  "Config": {
    "BuyCondition": {
      "conditionOperator": "AND",
      "conditions": [
        {
          "condition": "RSI",
          "Operator": "<",
          "Value": "30"
        },
        {
          "condition": "EMA",
          "Operator": "<",
          "Value": "VWAP"
        }
      ]
    },
    "SellCondition": {
      "conditionOperator": "AND",
      "conditions": [
        {
          "condition": "RSI",
          "Operator": ">",
          "Value": "70"
        }
      ]
    },
    "Buy_squareoff_condition": {
      "conditionOperator": "AND",
      "conditions": [
        {
          "condition": "TimeBased",
          "Operator": "=",
          "Value": "3:00pm"
        }
      ]
    },
    "Sell_squareoff_condition": {
      "conditionOperator": "AND",
      "conditions": [
        {
          "condition": "TimeBased",
          "Operator": "=",
          "Value": "4:00pm"
        }
      ]
    }
  }
}

Available conditions include: RSI, EMA, SMA, VWAP, MACD, Bollinger Bands, SuperTrend, TimeBased, Candle, CandlePattern, etc.
Operators: "<", ">", "=", "<=", ">=", "=="

Rules:
- Extract buy conditions from phrases like "buy when", "buy if", "enter long when"
- Extract sell conditions from phrases like "sell when", "sell if", "exit when", "reverse conditions"
- Extract squareoff conditions from phrases like "squareoff at", "exit at", "close at"
- Convert "reverse conditions" to opposite operators (e.g., < becomes >, > becomes <)
- Time formats: Use "3:00pm", "4:00pm", etc. for TimeBased conditions
- IMPORTANT: Only include conditions that are actually mentioned in the user's query. Do NOT include empty conditions or conditions with empty arrays. If a condition type (like Buy_squareoff_condition) is not mentioned, omit it entirely from the JSON.
- Return ONLY the JSON object, no markdown formatting, no explanations, no code blocks."""

        response = client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                *history
            ],
            max_tokens=2000,
            temperature=0.3
        )
        result = response.choices[0].message.content
        
        # Extract JSON from response (handle markdown code blocks and text)
        # Try to extract JSON from markdown code blocks first
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', result, re.DOTALL)
        if json_match:
            result = json_match.group(1).strip()
        else:
            # Try to find JSON object directly (match from first { to last })
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                result = json_match.group(0).strip()
        
        # Validate and fix JSON structure
        try:
            parsed_json = json.loads(result)
            # Ensure it has the Config structure
            if 'Config' not in parsed_json:
                # If the response is already in the right format but missing Config wrapper
                if any(key in parsed_json for key in ['BuyCondition', 'SellCondition', 'Buy_squareoff_condition', 'Sell_squareoff_condition']):
                    result = json.dumps({"Config": parsed_json})
                else:
                    # Create a basic structure if missing - but only include what was actually requested
                    config_dict = {}
                    if isinstance(parsed_json, dict) and parsed_json:
                        config_dict["BuyCondition"] = parsed_json
                    else:
                        # Only create empty structures if we have no data at all
                        config_dict = {
                            "BuyCondition": {"conditionOperator": "AND", "conditions": []},
                            "SellCondition": {"conditionOperator": "AND", "conditions": []},
                            "Buy_squareoff_condition": {"conditionOperator": "AND", "conditions": []},
                            "Sell_squareoff_condition": {"conditionOperator": "AND", "conditions": []}
                        }
                    result = json.dumps({"Config": config_dict})
            else:
                # Remove empty conditions to avoid showing empty sections
                config = parsed_json.get('Config', {})
                # Only keep conditions that have actual data
                cleaned_config = {}
                for key in ['BuyCondition', 'SellCondition', 'Buy_squareoff_condition', 'Sell_squareoff_condition']:
                    if key in config:
                        condition = config[key]
                        # Check if condition has data
                        if condition and isinstance(condition, dict):
                            if condition.get('conditions') and isinstance(condition.get('conditions'), list) and len(condition.get('conditions', [])) > 0:
                                # Check if any condition has actual data
                                has_data = any(
                                    c and isinstance(c, dict) and c.get('condition') and str(c.get('condition', '')).strip() != ''
                                    for c in condition.get('conditions', [])
                                )
                                if has_data:
                                    cleaned_config[key] = condition
                            elif condition.get('condition') and str(condition.get('condition', '')).strip() != '':
                                cleaned_config[key] = condition
                parsed_json['Config'] = cleaned_config
                result = json.dumps(parsed_json)
        except json.JSONDecodeError as e:
            # If JSON is invalid, log error but keep original result
            print(f"JSON parsing error: {e}")
            print(f"Raw result: {result[:200]}...")
            # Try to create a minimal valid structure
            result = json.dumps({
                "Config": {
                    "BuyCondition": {"conditionOperator": "AND", "conditions": []},
                    "SellCondition": {"conditionOperator": "AND", "conditions": []},
                    "Buy_squareoff_condition": {"conditionOperator": "AND", "conditions": []},
                    "Sell_squareoff_condition": {"conditionOperator": "AND", "conditions": []}
                }
            })

        history.append({"role": 'assistant', "content": result})

        timestamp = datetime.now()

        create_table = table_model(prompt=prompt_data, responses=result, history=history, timestamp=timestamp)
        db.session.add(create_table)
        db.session.commit()

        return redirect(url_for('user_endpoint', username=username, result=result, history=json.dumps(history)))

    result = request.args.get('result')
    history = request.args.get('history', '[]')
    chat_history = table_model.query.all()
    return render_template('interfaceTesting.html', result=result, username=username, history=history,
                           chat_history=chat_history, timestamp=(datetime.now()).strftime('%d-%m-%Y %H:%M:%S'))


@app.route('/dbshow/<username>', methods=["POST", "GET"])
def show_database(username):
    user = UserCreds.query.filter_by(name=username).first()
    if not user:
        return "User not found", 404

    email = user.email
    data_name = f"{email.replace('@', '_').replace('.', '_')}_data"
    
    # Use SQLAlchemy instead of raw cursor for better transaction handling
    try:
        table_model = create_db_table(email)
        chat_history = table_model.query.all()
        
        output = []
        for row in chat_history:
            output.append({
                'prompt': row.prompt,
                'responses': row.responses,
                'timestamp': row.timestamp
            })
    except Exception as e:
        print(f"Error fetching database: {e}")
        import traceback
        traceback.print_exc()
        output = []
    
    timestamp = datetime.now()
    return render_template('db.html', output=output, username=username, timestamp=timestamp)


@app.route("/navigate_pages", methods=['POST'])
def navigate_pages():
    selected_users = request.form.get("users")
    return redirect(url_for('user_endpoint', username=selected_users))


def create_user_table(email):
    table_model = create_db_table(email)
    with app.app_context():
        db.create_all()


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon',
    )


if __name__ == "__main__":
    # Ensure tables exist for all users
    with app.app_context():
        db.create_all()
        existing_users = UserCreds.query.all()
        for user in existing_users:
            create_user_table(user.email)

    # In production (e.g. Render), PORT is provided by the platform.
    # Locally this will default to 5000.
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, port=port, host="0.0.0.0")
