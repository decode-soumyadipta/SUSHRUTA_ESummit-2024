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


@user_bp.route('/save_phone_number', methods=['POST'])
@login_required
def save_phone_number():
    data = request.json
    phone = data.get('phone')

    if phone:
        current_user.phone = phone
        db.session.commit()
        return jsonify({'success': True}), 200
    else:
        return jsonify({'success': False, 'message': 'Phone number is required.'}), 400

def is_whatsapp_number(phone_number):
    try:
        lookup = client.lookup(phone_number, {'type': 'whatsapp'})
        return lookup and lookup.whatsapp
    except messagebird.client.ErrorException as e:
        print(f"Error checking WhatsApp number: {e}")
        return False

def send_whatsapp_message(phone_number, message):
    try:
        msg = client.message_create(
            originator='918240575718',
            recipients=[phone_number],
            body=message,
            messaging_type='whatsapp'
        )
        print(f"WhatsApp message sent successfully: {msg.id}")
        return msg.id
    except messagebird.client.ErrorException as e:
        print(f"Failed to send WhatsApp message: {e}")
        return None


@user_bp.route('/update_whatsapp_number', methods=['POST'])
@login_required
def update_whatsapp_number():
    new_whatsapp_number = request.form.get('whatsapp_number')
    if not new_whatsapp_number:
        return jsonify({'success': False, 'message': 'Please enter a valid WhatsApp number.'}), 400

    if not is_whatsapp_number(new_whatsapp_number):
        return jsonify({'success': False, 'message': 'The entered number is not registered with WhatsApp.'}), 400

    current_user.phone = new_whatsapp_number
    db.session.commit()
    return jsonify({'success': True, 'message': 'WhatsApp number updated successfully.'}), 200


@user_bp.route('/booking_history')
@login_required
def booking_history():
    past_bookings = Booking.query.filter(
        Booking.user_id == current_user.id,
        Booking.created_at < datetime.utcnow() - timedelta(hours=24)
    ).all()
    return render_template('user_dashboard/booking_history.html', bookings=past_bookings)

@user_bp.route('/save_address', methods=['POST'])
@login_required
def save_address():
    data = request.json
    location = data.get('location')
    address = data.get('address')

    if location and address:
        current_user.location = location
        current_user.address = address
        db.session.commit()
        return jsonify({'success': True}), 200
    else:
        return jsonify({'success': False, 'message': 'Invalid data.'}), 400

@user_bp.route('/cancel_booking/<int:booking_id>', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    booking = Booking.query.get(booking_id)
    
    if not booking or booking.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Booking not found or access denied.'}), 404
    
    # Check if the booking has an assigned ambulance
    if booking.ambulance_id:
        ambulance = Ambulance.query.get(booking.ambulance_id)
        if ambulance:
            ambulance.status = 'available'  # Make the ambulance available again

    # Mark the booking as cancelled
    booking.status = 'Cancelled'
    
    db.session.commit()
    
    return jsonify({'success': True}), 200



@user_bp.route('/book_opd', methods=['GET', 'POST'])
@login_required
def book_opd():
    if request.method == 'POST':
        appointment_date = request.form.get('appointment_date')
        doctor_id = request.form.get('doctor_id')
        time_slot = request.form.get('time_slot')
        hospital_id = request.form.get('hospital_id')  # Capture the hospital_id from the form
        appointment_code = str(random.randint(1000, 9999))

        # Ensure the current user hasn't already booked this slot
        existing_appointment = OPDAppointment.query.filter_by(
            user_id=current_user.id,
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            time_slot=time_slot
        ).first()

        if existing_appointment:
            flash('You have already booked this time slot.', 'warning')
            return redirect(url_for('user_bp.view_appointments'))

        # Update user details if provided
        current_user.phone = request.form.get('phone') or current_user.phone
        current_user.age = request.form.get('age') or current_user.age
        current_user.address = request.form.get('address') or current_user.address

        # Create the OPDAppointment with the hospital_id
        appointment = OPDAppointment(
            user_id=current_user.id,
            doctor_id=doctor_id,
            hospital_id=hospital_id,  # Ensure hospital_id is saved
            appointment_date=appointment_date,
            time_slot=time_slot,
            appointment_code=appointment_code
        )
        db.session.add(appointment)
        db.session.commit()

        # Send confirmation email
        doctor = Doctor.query.get(doctor_id)
        hospital = Hospital.query.get(hospital_id)
        msg = Message('Your OPD Appointment Details', recipients=[current_user.email])
        msg.body = f"""
        Dear {current_user.name},

        Your appointment is confirmed with Dr. {doctor.name} at {hospital.name} on {appointment_date} at {time_slot}.
        Appointment Code: {appointment_code}

        Thank you for choosing our hospital.
        """
        mail.send(msg)

        flash('Appointment booked successfully', 'success')
        return redirect(url_for('user_bp.view_appointments'))

    hospitals = Hospital.query.all()
    return render_template('user_dashboard/book_opd.html', hospitals=hospitals)



@user_bp.route('/view_appointments', methods=['GET'])
@login_required
def view_appointments():
    today = datetime.today().date()
    end_date = today + timedelta(days=10)
    appointments = OPDAppointment.query.filter(
        OPDAppointment.user_id == current_user.id,
        OPDAppointment.appointment_date.between(today, end_date)
    ).all()
    return render_template('user_dashboard/view_appointments.html', appointments=appointments)



@user_bp.route('/get_doctors/<int:department_id>', methods=['GET'])
def get_doctors(department_id):
    appointment_date = request.args.get('date')
    
    if not appointment_date:
        return jsonify({'doctors': []})

    date_obj = datetime.strptime(appointment_date, '%Y-%m-%d')
    weekday_name = date_obj.strftime('%A')

    doctors = Doctor.query.filter_by(department_id=department_id).all()
    available_doctors = []

    for doctor in doctors:
        availability_days = [day.strip().capitalize() for day in doctor.availability_days.split(',')]
        if weekday_name in availability_days:
            available_doctors.append({
                'id': doctor.id,
                'name': doctor.name
            })

    return jsonify({'doctors': available_doctors})

@user_bp.route('/get_time_slots/<int:doctor_id>/<string:appointment_date>', methods=['GET'])
@login_required
def get_time_slots(doctor_id, appointment_date):
    appointment_date = datetime.strptime(appointment_date, '%Y-%m-%d').date()

    # Fetch all appointments for the selected doctor and date
    existing_appointments = OPDAppointment.query.filter_by(
        doctor_id=doctor_id, 
        appointment_date=appointment_date
    ).all()

    occupied_slots = set(appointment.time_slot for appointment in existing_appointments if appointment.user_id == current_user.id)
    
    all_slots = Doctor.query.get(doctor_id).chamber_timings.split(',')
    available_slots = [slot for slot in all_slots if slot not in occupied_slots]

    return jsonify({'time_slots': available_slots})



@user_bp.route('/get_departments/<int:hospital_id>', methods=['GET'])
def get_departments(hospital_id):
    departments = Department.query.filter_by(hospital_id=hospital_id).all()
    return jsonify({'departments': [{'id': dept.id, 'name': dept.name} for dept in departments]})

@user_bp.route('/doctor_details/<int:doctor_id>', methods=['GET'])
@login_required
def doctor_details(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    return render_template('user_dashboard/doctor_details.html', doctor=doctor)




@user_bp.route('/upload_medical_data', methods=['GET', 'POST'])
@login_required
def upload_medical_data():
    if request.method == 'POST':
        # Get files from the form
        prescription = request.files.get('prescription')
        test_results = request.files.get('test_results')

        if prescription and test_results:
            try:
                # Save files temporarily
                prescription_filename = secure_filename(prescription.filename)
                test_results_filename = secure_filename(test_results.filename)

                prescription_path = os.path.join('medical_records_temp', prescription_filename)
                test_results_path = os.path.join('medical_records_temp', test_results_filename)

                prescription.save(prescription_path)
                test_results.save(test_results_path)

                # Upload files to IPFS
                prescription_hash = upload_to_ipfs(prescription_path)
                test_results_hash = upload_to_ipfs(test_results_path)

                # Clean up the temporary files
                os.remove(prescription_path)
                os.remove(test_results_path)

                if prescription_hash and test_results_hash:
                    # Blockchain transaction: Store IPFS hashes on the blockchain
                    try:
                        tx_hash = store_data_on_blockchain(prescription_hash, test_results_hash)

                        if tx_hash:
                            # Save the data to the local database only if the transaction was successful
                            medical_data = MedicalData(
                                user_id=current_user.id,
                                prescription_hash=prescription_hash,
                                test_results_hash=test_results_hash,
                                tx_hash=tx_hash
                            )
                            db.session.add(medical_data)
                            db.session.commit()

                            flash('Medical data uploaded successfully!', 'success')
                        else:
                            flash('Failed to store data on the blockchain. Please try again.', 'danger')

                    except Exception as e:
                        db.session.rollback()
                        flash(f'Blockchain transaction failed: {str(e)}', 'danger')
                        traceback.print_exc()

                else:
                    flash('Failed to upload files to IPFS. Please try again.', 'danger')

            except Exception as e:
                flash(f"An error occurred: {str(e)}", 'danger')
                traceback.print_exc()

        else:
            flash('Please upload both files.', 'danger')

    # Fetch the current user's uploaded medical data history to display
    medical_data = MedicalData.query.filter_by(user_id=current_user.id).order_by(MedicalData.timestamp.desc()).all()
    
    return render_template('user_dashboard/upload_medical_data.html', medical_data=medical_data)



#@user_bp.route('/upload_medical_data', methods=['GET', 'POST'])
#@login_required
#def upload_medical_data():
#    if request.method == 'POST':
#        # Get files from the form
#        prescription = request.files.get('prescription')
#        test_results = request.files.get('test_results')
#
#        if prescription and test_results:
#            # Save files temporarily
#            prescription_filename = secure_filename(prescription.filename)
#            test_results_filename = secure_filename(test_results.filename)
#            prescription_path = os.path.join('medical_records_temp', prescription_filename)
#            test_results_path = os.path.join('medical_records_temp', test_results_filename)
#            prescription.save(prescription_path)
#            test_results.save(test_results_path)
#
#            # Upload files to IPFS (via Kaleido or local IPFS)
#            prescription_hash = upload_to_ipfs(prescription_path)
#            test_results_hash = upload_to_ipfs(test_results_path)
#
#            if prescription_hash and test_results_hash:
#                # Store the IPFS hashes on the Kaleido blockchain
#                private_key = os.getenv("PRIVATE_KEY")
#                user_wallet_address = os.getenv("ETH_ADDRESS")  # This is your Ethereum address that will sign the transaction
#
#                try:
#                    # Store the hashes on the blockchain
#                    tx_hash = store_data_on_blockchain(user_wallet_address, prescription_hash, test_results_hash, private_key)
#
#                    # Save the hashes and transaction hash in the local database
#                    medical_data = MedicalData(
#                        user_id=current_user.id,
#                        prescription_hash=prescription_hash,
#                        test_results_hash=test_results_hash,
#                        tx_hash=tx_hash
#                    )
#                    db.session.add(medical_data)
#                    db.session.commit()
#
#                    flash('Medical data uploaded successfully!', 'success')
#                    return redirect(url_for('user_bp.dashboard'))
#                except Exception as e:
#                    flash(f'Blockchain transaction failed: {str(e)}', 'danger')
#            else:
#                flash('Failed to upload files to IPFS.', 'danger')
#        else:
#            flash('Please upload both files.', 'danger')
#
#    return render_template('user_dashboard/upload_medical_data.html')
@user_bp.route('/filter_hospitals', methods=['POST'])
@login_required
def filter_hospitals():
    bed_type = request.json.get('bed_type')

    # Query hospitals and sort them by the selected bed type
    if bed_type == 'icu':
        hospitals = Hospital.query.order_by(Hospital.vacant_icu_beds.desc()).all()
    elif bed_type == 'opd':
        hospitals = Hospital.query.order_by(Hospital.vacant_opd_beds.desc()).all()
    else:
        hospitals = Hospital.query.order_by(Hospital.vacant_general_beds.desc()).all()

    # Convert the hospital data to JSON format to send back to the frontend
    hospital_list = [{
        'id': hospital.id,
        'name': hospital.name,
        'distance': 0,  # You can calculate this if you have user location
        'vacant_icu_beds': hospital.vacant_icu_beds,
        'vacant_opd_beds': hospital.vacant_opd_beds,
        'vacant_general_beds': hospital.vacant_general_beds,
        'contact_info': hospital.contact_info
    } for hospital in hospitals]

    return jsonify(hospital_list), 200