from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from services.ai_engine import analyze_conditions

from config import (
    MYSQL_HOST,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DATABASE
)

app = Flask(__name__)

# Secret key for user sessions
app.secret_key = "agriguard-development-key"


# -----------------------------------
# DATABASE CONNECTION
# -----------------------------------

def get_db_connection():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )


# -----------------------------------
# TEST DATABASE CONNECTION
# -----------------------------------

def test_database_connection():
    try:
        connection = get_db_connection()

        if connection.is_connected():
            print("===================================")
            print("       AGRIGUARD AI")
            print("   Database connection: SUCCESS")
            print("===================================")

        connection.close()

    except mysql.connector.Error as error:
        print("Database connection failed:")
        print(error)


# -----------------------------------
# HOME / LOGIN
# -----------------------------------

@app.route("/")
def home():
    return redirect(url_for("login"))


# -----------------------------------
# LOGIN
# -----------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute(
                "SELECT * FROM users WHERE email = %s",
                (email,)
            )

            user = cursor.fetchone()

            cursor.close()
            connection.close()

            if user and check_password_hash(
                user["password_hash"],
                password
            ):

                session["user_id"] = user["id"]
                session["user_name"] = user["full_name"]

                return redirect(url_for("dashboard"))

            else:
                flash("Incorrect email or password.")

        except mysql.connector.Error as error:
            flash("Database error occurred.")
            print(error)

    return render_template("login.html")


# -----------------------------------
# REGISTER
# -----------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        full_name = request.form["full_name"]
        email = request.form["email"]
        password = request.form["password"]

        password_hash = generate_password_hash(password)

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT INTO users
                (full_name, email, password_hash, role)
                VALUES (%s, %s, %s, %s)
                """,
                (full_name, email, password_hash, "farmer")
            )

            connection.commit()

            cursor.close()
            connection.close()

            flash("Registration successful. You can now login.")

            return redirect(url_for("login"))

        except mysql.connector.Error as error:

            if error.errno == 1062:
                flash("This email is already registered.")
            else:
                flash("Registration failed.")
                print(error)

    return render_template("register.html")


# -----------------------------------
# DASHBOARD
# -----------------------------------

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        user_name=session.get("user_name")
    )


# -----------------------------------
# FARMS
# -----------------------------------

@app.route("/farms")
def farms():

    if "user_id" not in session:
        return redirect(url_for("login"))

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM farms
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (session["user_id"],)
        )

        farms = cursor.fetchall()

        cursor.close()
        connection.close()

        return render_template(
            "farms.html",
            farms=farms
        )

    except mysql.connector.Error as error:

        print(error)

        return "Database error occurred."


# -----------------------------------
# ADD FARM
# -----------------------------------

@app.route("/farms/add", methods=["GET", "POST"])
def add_farm():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        farm_name = request.form["farm_name"]
        location = request.form["location"]
        farm_size = request.form["farm_size"]

        try:

            connection = get_db_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT INTO farms
                (user_id, farm_name, location, farm_size)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    session["user_id"],
                    farm_name,
                    location,
                    farm_size
                )
            )

            connection.commit()

            cursor.close()
            connection.close()

            return redirect(url_for("farms"))

        except mysql.connector.Error as error:

            print(error)

            return "Unable to add farm."

    return render_template("add_farm.html")


# -----------------------------------
# VIEW CROPS FOR A FARM
# -----------------------------------

@app.route("/farms/<int:farm_id>/crops")
def farm_crops(farm_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Get the farm
        cursor.execute(
            """
            SELECT *
            FROM farms
            WHERE id = %s AND user_id = %s
            """,
            (farm_id, session["user_id"])
        )

        farm = cursor.fetchone()

        if not farm:
            cursor.close()
            connection.close()
            return "Farm not found."

        # Get crops belonging to this farm
        cursor.execute(
            """
            SELECT *
            FROM crops
            WHERE farm_id = %s
            ORDER BY created_at DESC
            """,
            (farm_id,)
        )

        crops = cursor.fetchall()

        cursor.close()
        connection.close()

        return render_template(
            "crops.html",
            farm=farm,
            crops=crops
        )

    except mysql.connector.Error as error:

        print(error)

        return "Database error occurred."


# -----------------------------------
# ADD CROP
# -----------------------------------

@app.route(
    "/farms/<int:farm_id>/crops/add",
    methods=["GET", "POST"]
)
def add_crop(farm_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Check that the farm belongs to the logged-in farmer
        cursor.execute(
            """
            SELECT *
            FROM farms
            WHERE id = %s AND user_id = %s
            """,
            (farm_id, session["user_id"])
        )

        farm = cursor.fetchone()

        if not farm:
            cursor.close()
            connection.close()
            return "Farm not found."

        if request.method == "POST":

            crop_name = request.form["crop_name"]
            variety = request.form["variety"]
            planting_date = request.form["planting_date"]
            growth_stage = request.form["growth_stage"]

            cursor.execute(
                """
                INSERT INTO crops
                (
                    farm_id,
                    crop_name,
                    variety,
                    planting_date,
                    growth_stage
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    farm_id,
                    crop_name,
                    variety,
                    planting_date,
                    growth_stage
                )
            )

            connection.commit()

            cursor.close()
            connection.close()

            return redirect(
                url_for(
                    "farm_crops",
                    farm_id=farm_id
                )
            )

        cursor.close()
        connection.close()

        return render_template(
            "add_crop.html",
            farm=farm
        )

    except mysql.connector.Error as error:

        print(error)

        return "Unable to add crop."


# -----------------------------------
# CROP MONITORING
# -----------------------------------

@app.route("/crops/<int:crop_id>/monitoring")
def crop_monitoring(crop_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Get crop and make sure it belongs to the logged-in farmer
        cursor.execute(
            """
            SELECT crops.*, farms.farm_name
            FROM crops
            JOIN farms ON crops.farm_id = farms.id
            WHERE crops.id = %s
            AND farms.user_id = %s
            """,
            (crop_id, session["user_id"])
        )

        crop = cursor.fetchone()

        if not crop:

            cursor.close()
            connection.close()

            return "Crop not found."

        # Get monitoring records
        cursor.execute(
            """
            SELECT *
            FROM monitoring_records
            WHERE crop_id = %s
            ORDER BY recorded_at DESC
            """,
            (crop_id,)
        )

        records = cursor.fetchall()

        cursor.close()
        connection.close()

        return render_template(
            "monitoring.html",
            crop=crop,
            records=records
        )

    except mysql.connector.Error as error:

        print(error)

        return "Database error occurred."


# -----------------------------------
# ADD MONITORING RECORD
# -----------------------------------

@app.route(
    "/crops/<int:crop_id>/monitoring/add",
    methods=["GET", "POST"]
)
def add_monitoring(crop_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Confirm crop belongs to logged-in farmer
        cursor.execute(
            """
            SELECT crops.*, farms.farm_name
            FROM crops
            JOIN farms ON crops.farm_id = farms.id
            WHERE crops.id = %s
            AND farms.user_id = %s
            """,
            (crop_id, session["user_id"])
        )

        crop = cursor.fetchone()

        if not crop:

            cursor.close()
            connection.close()

            return "Crop not found."

        if request.method == "POST":

            soil_moisture = request.form["soil_moisture"]
            temperature = request.form["temperature"]
            humidity = request.form["humidity"]
            rainfall = request.form["rainfall"]
            health_status = request.form["health_status"]

            cursor.execute(
                """
                INSERT INTO monitoring_records
                (
                    crop_id,
                    soil_moisture,
                    temperature,
                    humidity,
                    rainfall,
                    health_status
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    crop_id,
                    soil_moisture,
                    temperature,
                    humidity,
                    rainfall,
                    health_status
                )
            )

            connection.commit()

            cursor.close()
            connection.close()

            return redirect(
                url_for(
                    "crop_monitoring",
                    crop_id=crop_id
                )
            )

        cursor.close()
        connection.close()

        return render_template(
            "add_monitoring.html",
            crop=crop
        )

    except mysql.connector.Error as error:

        print(error)

        return "Unable to save monitoring data."


# -----------------------------------
# SIMULATE SENSOR DATA
# -----------------------------------

@app.route(
    "/crops/<int:crop_id>/monitoring/simulate",
    methods=["POST"]
)
def simulate_monitoring(crop_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    try:

        import random

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Check that crop belongs to logged-in farmer
        cursor.execute(
            """
            SELECT crops.*, farms.farm_name
            FROM crops
            JOIN farms ON crops.farm_id = farms.id
            WHERE crops.id = %s
            AND farms.user_id = %s
            """,
            (crop_id, session["user_id"])
        )

        crop = cursor.fetchone()

        if not crop:

            cursor.close()
            connection.close()

            return "Crop not found."

        # Generate simulated sensor readings

        soil_moisture = round(
            random.uniform(15, 70), 1
        )

        temperature = round(
            random.uniform(20, 35), 1
        )

        humidity = round(
            random.uniform(40, 85), 1
        )

        rainfall = round(
            random.uniform(0, 15), 1
        )

        # Basic simulated crop health assessment

        if soil_moisture < 20:

            health_status = "High Risk"

        elif soil_moisture < 30:

            health_status = "Moderate Risk"

        else:

            health_status = "Healthy"

        # Save generated reading

        cursor.execute(
            """
            INSERT INTO monitoring_records
            (
                crop_id,
                soil_moisture,
                temperature,
                humidity,
                rainfall,
                health_status
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                crop_id,
                soil_moisture,
                temperature,
                humidity,
                rainfall,
                health_status
            )
        )

        connection.commit()

        cursor.close()
        connection.close()

        return redirect(
            url_for(
                "crop_monitoring",
                crop_id=crop_id
            )
        )

    except mysql.connector.Error as error:

        print(error)

        return "Unable to generate sensor data." 

# -----------------------------------
# AGRIGUARD AI ANALYSIS
# -----------------------------------

@app.route("/crops/<int:crop_id>/ai-analysis")
def ai_analysis(crop_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    try:

        connection = get_db_connection()

        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT crops.*, farms.farm_name
            FROM crops
            JOIN farms ON crops.farm_id = farms.id
            WHERE crops.id = %s
            AND farms.user_id = %s
            """,
            (crop_id, session["user_id"])
        )

        crop = cursor.fetchone()

        if not crop:

            cursor.close()
            connection.close()

            return "Crop not found."

        cursor.execute(
            """
            SELECT *
            FROM monitoring_records
            WHERE crop_id = %s
            ORDER BY recorded_at DESC
            LIMIT 1
            """,
            (crop_id,)
        )

        record = cursor.fetchone()

        cursor.close()
        connection.close()

        if not record:

            return "No monitoring data available for AI analysis."

        analysis = analyze_conditions(
            record["soil_moisture"],
            record["temperature"],
            record["humidity"],
            record["rainfall"]
        )

        return render_template(
            "ai_analysis.html",
            crop=crop,
            record=record,
            analysis=analysis
        )

    except mysql.connector.Error as error:

        print(error)

        return "AI analysis could not be completed."

@app.route("/crop-scanner")
def crop_scanner():

    return render_template("crop_scanner.html")

# -----------------------------------
# LOGOUT
# -----------------------------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))

# -----------------------------------
# AGRILEARN
# -----------------------------------

@app.route("/agrilearn")
def agrilearn():

    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("agrilearn.html")

# -----------------------------------
# START APPLICATION
# -----------------------------------

if __name__ == "__main__":

    test_database_connection()

    app.run(debug=True)
    