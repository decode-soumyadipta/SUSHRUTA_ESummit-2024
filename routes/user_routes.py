from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
import json
from flask_login import login_required, current_user
from models import Hospital, Booking, Rating, Bed, Ward, db, Department, Doctor, OPDAppointment, LabTestBooking, Hospital, Queue, DiagnosticDepartment, DiagnosticTest, Ambulance, MedicalData
from sqlalchemy.orm import aliased
from geopy.distance import great_circle
import random
from werkzeug.utils import secure_filename
import messagebird
from flask_mail import Mail, Message  # Import Message here
import os
from datetime import datetime, timedelta
from routes.hospital_routes import hospital_bp
from utils.blockchain import store_data_on_blockchain
from utils.ipfs import upload_to_ipfs
from dotenv import load_dotenv
import traceback
load_dotenv()  # Load the .env file
# Initialize Flask Blueprint
user_bp = Blueprint('user_bp', __name__)
# Initialize Flask-Mail
mail = Mail()
# Your MessageBird API key
MESSAGEBIRD_API_KEY = '8XOUzqZZ0uxGo4GSKYkTMSFQCSvxQW0JoqtB'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
UPLOAD_FOLDER = 'static/images/'
# Initialize the MessageBird client
client = messagebird.Client(MESSAGEBIRD_API_KEY)
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Load configuration from config.json
with open('config.json') as config_file:
    config = json.load(config_file)
hospital_bp = Blueprint('hospital_bp', __name__)

# Lab test booking page
# Function for booking a lab test
# Function for booking a lab test
@user_bp.route('/book_lab_test', methods=['GET', 'POST'])
@login_required
def book_lab_test():
    if request.method == 'POST':
        department_id = request.form.get('department')
        test_id = request.form.get('test')
        hospital_id = request.form.get('hospital')  # From the hidden field
        price = request.form.get('price')
        booking_date = request.form.get('booking_date')

        # Debugging log statements
        print(f"department_id: {department_id}")
        print(f"test_id: {test_id}")
        print(f"hospital_id: {hospital_id}")
        print(f"booking_date: {booking_date}")

        # Validate hospital_id is not null
        if not hospital_id:
            flash('Invalid hospital selection.', 'danger')
            return redirect(url_for('user_bp.book_lab_test'))

        # Handle file upload for prescription
        file = request.files['prescription']
        if not file.filename or not allowed_file(file.filename):
            flash('Invalid file format or missing file.', 'danger')
            return redirect(url_for('user_bp.book_lab_test'))

        filename = secure_filename(file.filename)
        prescription_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(prescription_path)

        # Generate booking code
        booking_code = str(random.randint(1000, 9999))

        # Save booking in the database
        try:
            booking = LabTestBooking(
                user_id=current_user.id,
                test_category=DiagnosticDepartment.query.get(department_id).name,
                test_name=DiagnosticTest.query.get(test_id).name,
                hospital_id=hospital_id,  # Now it's retrieved from the hidden field
                booking_date=booking_date,
                prescription=prescription_path,
                booking_code=booking_code,
                status='Pending'
            )
            db.session.add(booking)
            db.session.commit()

            flash('Lab test booked successfully!', 'success')

        except Exception as e:
            # If there is any error in saving, rollback the transaction and log the error
            db.session.rollback()
            print(f"Error saving booking: {e}")
            flash('Error booking lab test. Please try again.', 'danger')
            return redirect(url_for('user_bp.book_lab_test'))

        # Send confirmation email (optional)
        hospital = Hospital.query.get(hospital_id)
        test = DiagnosticTest.query.get(test_id)
        msg = Message('Lab Test Booking Confirmation', recipients=[current_user.email])
        msg.body = (f"Dear {current_user.name},\n\nYour lab test booking is confirmed:\n"
                        f"Test: {test.name}\n"
                        f"Price: ₹{price}\n"
                        f"Hospital: {hospital.name}\n"
                        f"Booking Code: {booking_code}\n\nThank you!")
        mail.send(msg)

        return redirect(url_for('user_bp.lab_test_booking_history'))

    # Fetch unique departments with hospital names
    departments = db.session.query(
        DiagnosticDepartment.id,
        DiagnosticDepartment.name,
        Hospital.name.label('hospital_name')
    ).join(Hospital).all()

    unique_departments = [{
        'id': department.id,
        'name': department.name,
        'hospital_name': department.hospital_name
    } for department in departments]

    return render_template('user_dashboard/book_lab_test.html', unique_departments=unique_departments)




# Fetch hospitals offering the selected department (by department ID)
@user_bp.route('/get_hospital_by_department/<int:department_id>', methods=['GET'])
@login_required
def get_hospital_by_department(department_id):
    # Fetch the hospital associated with the department
    department = DiagnosticDepartment.query.get(department_id)
    if department:
        return jsonify({'hospital_id': department.hospital_id})
    return jsonify({'error': 'Department not found'}), 404



@user_bp.route('/get_tests_by_department/<int:department_id>', methods=['GET'])
@login_required
def get_tests_by_department(department_id):
    tests = DiagnosticTest.query.filter_by(department_id=department_id).all()

    return jsonify({
        'tests': [{'id': test.id, 'name': test.name} for test in tests]
    })


# Fetch test price by test ID
@user_bp.route('/get_test_price/<int:test_id>', methods=['GET'])
@login_required
def get_test_price(test_id):
    test = DiagnosticTest.query.get(test_id)
    return jsonify({'price': test.price})

# Lab test booking history
@user_bp.route('/lab_test_booking_history')
@login_required
def lab_test_booking_history():
    # Fetch the current user's lab test bookings
    bookings = LabTestBooking.query.filter_by(user_id=current_user.id).all()
    return render_template('user_dashboard/lab_test_booking_history.html', bookings=bookings)
@user_bp.route('/view_check_ins', methods=['GET'])
@login_required
def view_check_ins():
    test_id = request.args.get('test_id')
    booking_date = request.args.get('booking_date')

    # Fetch bookings for the specific date and test
    bookings = LabTestBooking.query.filter_by(test_id=test_id, booking_date=booking_date, status='Verified').all()

    return render_template('user_dashboard/view_check_ins.html', bookings=bookings)



@user_bp.route('/search_tests/<string:query>', methods=['GET'])
@login_required
def search_tests(query):
    # Search for tests by name (simple search query)
    tests = DiagnosticTest.query.join(DiagnosticDepartment, DiagnosticTest.department_id == DiagnosticDepartment.id)\
                                .join(Hospital, DiagnosticDepartment.hospital_id == Hospital.id)\
                                .filter(DiagnosticTest.name.ilike(f'%{query}%')).all()

    results = []
    for test in tests:
        results.append({
            'test_id': test.id,
            'name': test.name,
            'price': test.price,
            'department_id': test.diagnostic_department.id,
            'hospital_id': test.diagnostic_department.hospital.id,  # Include hospital_id
            'hospital_name': test.diagnostic_department.hospital.name
        })
    return jsonify(results)


@user_bp.route('/cancel_labtest_booking/<int:booking_id>', methods=['POST'])
@login_required
def cancel_labtest_booking(booking_id):
    booking = LabTestBooking.query.get_or_404(booking_id)

    # Ensure the booking belongs to the current user
    if booking.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    # Update booking status to 'Cancelled'
    booking.status = 'Cancelled'
    db.session.commit()

    return jsonify({'success': True})



@user_bp.route('/dashboard')
@login_required
def dashboard():
    
    current_bookings = Booking.query.filter_by(user_id=current_user.id, status='Confirmed').all()
    return render_template('user_dashboard/index.html', current_bookings=current_bookings)

@user_bp.route('/book_bed', methods=['POST'])
@login_required
def book_bed():

    data = request.json
    hospital_id = data.get('hospital_id')
    ambulance_required = data.get('ambulance_required')
    user_phone = data.get('phone')
    # Add logic to skip the most recent booking if passed from the frontend
    recent_booking_id = data.get('recent_booking_id')

    existing_booking = Booking.query.filter(
        Booking.user_id == current_user.id,
        Booking.status == 'Confirmed',
        Booking.id != recent_booking_id  # Skip the recent booking
    ).first()

    if existing_booking:
        return jsonify({'success': False, 'message': 'You already have an active booking.'}), 400

   

    # Log incoming data for debugging
    current_app.logger.info(f"Booking data: hospital_id={hospital_id}, ambulance_required={ambulance_required}, phone={user_phone}")

    if not hospital_id or ambulance_required is None or not user_phone:
        return jsonify({'success': False, 'message': 'Missing required data.'}), 400

    hospital = Hospital.query.get(hospital_id)
    if not hospital:
        return jsonify({'success': False, 'message': 'Hospital not found.'}), 404

    if hospital.vacant_general_beds <= 0:
        return jsonify({'success': False, 'message': 'No General beds available.'}), 400

    # Calculate distance and generate admission code
    user_lat, user_lng = map(float, current_user.location.split(','))
    distance = great_circle((user_lat, user_lng), (hospital.latitude, hospital.longitude)).kilometers
    admission_code = str(random.randint(1000, 9999))

    # Create new booking
    booking = Booking(
        user_id=current_user.id,
        hospital_id=hospital_id,
        bed_type='General',
        distance=distance,
        status='Confirmed',  # Set to Confirmed by default
        admission_code=admission_code
    )
    db.session.add(booking)
    db.session.commit()

    if ambulance_required:
        ambulance = Ambulance.query.filter_by(hospital_id=hospital_id, status='available').first()

        if not ambulance:
            return jsonify({'success': False, 'message': 'No ambulances available. Would you like to proceed without an ambulance?'}), 400

        # Mark the ambulance as "in use"
        ambulance.status = 'in use'
        booking.ambulance_id = ambulance.id
        db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Bed booked successfully.',
        'booking': {
            'id': booking.id,
            'hospital_name': hospital.name,
            'bed_type': booking.bed_type,
            'admission_code': booking.admission_code,
            'distance': booking.distance,
            'created_at': booking.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
    }), 200



@user_bp.route('/rate_service', methods=['POST'])
@login_required
def rate_service():
    rating = Rating(user_id=current_user.id, hospital_id=request.form.get('hospital_id'), driver_id=request.form.get('driver_id'), rating=request.form.get('rating'), feedback=request.form.get('feedback'))
    db.session.add(rating)
    db.session.commit()
    flash("Thank you for your feedback!", "success")
    return redirect(url_for('user_bp.dashboard'))

@user_bp.route('/nearby_hospitals', methods=['POST'])
@login_required
def nearby_hospitals():
    user_lat = request.json.get('latitude')
    user_lng = request.json.get('longitude')
    bed_type = request.json.get('bed_type')

    if not user_lat or not user_lng:
        return jsonify({'error': 'Missing latitude or longitude'}), 400

    hospitals = Hospital.query.all()
    nearby_hospitals = []
    for hospital in hospitals:
        hospital_location = (hospital.latitude, hospital.longitude)
        user_location = (float(user_lat), float(user_lng))
        distance = great_circle(user_location, hospital_location).kilometers

        if distance <= 5:
            # Sum all ready beds across all wards for this hospital
            icu_beds_ready = Bed.query.join(Ward).filter(
                Bed.bed_type == 'ICU',
                Bed.status == 'ready',
                Ward.hospital_id == hospital.id
            ).count()

            opd_beds_ready = Bed.query.join(Ward).filter(
                Bed.bed_type == 'OPD',
                Bed.status == 'ready',
                Ward.hospital_id == hospital.id
            ).count()

            general_beds_ready = Bed.query.join(Ward).filter(
                Bed.bed_type == 'General',
                Bed.status == 'ready',
                Ward.hospital_id == hospital.id
            ).count()

            nearby_hospitals.append({
                'id': hospital.id,
                'name': hospital.name,
                'address': hospital.address,
                'distance': round(distance, 2),
                'vacant_icu_beds': icu_beds_ready,
                'vacant_opd_beds': opd_beds_ready,
                'vacant_general_beds': general_beds_ready,
                'contact_info': hospital.contact_info,
                'latitude': hospital.latitude,
                'longitude': hospital.longitude,
            })

    return jsonify(nearby_hospitals), 200

