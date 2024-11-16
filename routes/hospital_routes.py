from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app, session
from flask_login import login_required, current_user
from models import db, Hospital, Ward, Bed, Booking, Notification, User, Department, Doctor, OPDAppointment, MaxPatient, LabTestBooking, Queue, DiagnosticDepartment, DiagnosticTest, Ambulance, LabTestQueue, OPDQueue, Medicine, MedicineLog, MedicineBatch
from flask_mail import Message, Mail
from datetime import datetime
import os
from sqlalchemy import func

from werkzeug.utils import secure_filename
import logging
logging.basicConfig(level=logging.DEBUG)
mail = Mail()
hospital_bp = Blueprint('hospital_bp', __name__)

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@hospital_bp.route('/hospital_dashboard', methods=['GET'])
@login_required
def hospital_dashboard():
    hospital = current_user.hospitals[0]  # Assuming the current user is associated with only one hospital
    wards = Ward.query.filter_by(hospital_id=hospital.id).all()
    return render_template('HOSPITAL/hospital_dashboard.html', hospital=hospital, wards=wards)

@hospital_bp.route('/get_beds/<int:ward_id>', methods=['GET'])
@login_required
def get_beds(ward_id):
    ward = Ward.query.get_or_404(ward_id)
    beds = Bed.query.filter_by(ward_id=ward_id).all()

    bed_counts = {
        "icu_beds": sum(1 for bed in beds if bed.bed_type == "ICU" and bed.status == 'ready'),
        "opd_beds": sum(1 for bed in beds if bed.bed_type == "OPD" and bed.status == 'ready'),
        "general_beds": sum(1 for bed in beds if bed.bed_type == "General" and bed.status == 'ready')
    }

    return jsonify(bed_counts)

@hospital_bp.route('/update_bed_counts', methods=['POST'])
@login_required
def update_bed_counts():
    logging.debug('Received data: %s', request.json)
    data = request.json
    ward_id = data.get('ward_id')

    if ward_id:
        ward = Ward.query.get(ward_id)
        if not ward:
            return jsonify(success=False, message="Ward not found"), 404

        icu_beds = int(data.get('icu_beds') or 0)
        opd_beds = int(data.get('opd_beds') or 0)
        general_beds = int(data.get('general_beds') or 0)

        # Clear old bed data
        Bed.query.filter_by(ward_id=ward_id, bed_type='ICU').delete()
        Bed.query.filter_by(ward_id=ward_id, bed_type='OPD').delete()
        Bed.query.filter_by(ward_id=ward_id, bed_type='General').delete()

        # Add new bed data
        for _ in range(icu_beds):
            new_bed = Bed(ward_id=ward_id, bed_type='ICU', status='ready')
            db.session.add(new_bed)

        for _ in range(opd_beds):
            new_bed = Bed(ward_id=ward_id, bed_type='OPD', status='ready')
            db.session.add(new_bed)

        for _ in range(general_beds):
            new_bed = Bed(ward_id=ward_id, bed_type='General', status='ready')
            db.session.add(new_bed)

        db.session.commit()

        # Update the hospital's vacant bed counts
        update_vacant_beds(ward.hospital_id)

        return jsonify(success=True)

    return jsonify(success=False, message="Invalid ward ID"), 400



@hospital_bp.route('/get_bed_matrix/<int:ward_id>', methods=['GET'])
@login_required
def get_bed_matrix(ward_id):
    beds = Bed.query.filter_by(ward_id=ward_id).all()

    bed_matrix = [{
        'id': bed.id,
        'status': bed.status,
        'bed_type': bed.bed_type
    } for bed in beds]

    return jsonify(bed_matrix)

@hospital_bp.route('/update_bed_status', methods=['POST'])
@login_required
def update_bed_status():
    data = request.json
    bed_id = data.get('bed_id')
    new_status = data.get('status')

    bed = Bed.query.get(bed_id)
    if bed and new_status in ['ready', 'cleaning', 'occupied']:
        bed.status = new_status
        db.session.commit()

        # Update the hospital's vacant bed counts
        update_vacant_beds(bed.ward.hospital_id)

        return jsonify(success=True)
    
    return jsonify(success=False), 400

@hospital_bp.route('/update_info', methods=['GET', 'POST'])
@login_required
def update_info():
    hospital = Hospital.query.filter_by(admin_id=current_user.id).first()
    if not hospital:
        flash('Hospital not found for this admin user.', 'danger')
        return redirect(url_for('signin'))

    if request.method == 'POST':
        hospital.name = request.form.get('name', '')
        hospital.contact_info = request.form.get('contact_info', '')
        hospital.address = request.form.get('address', '')
        hospital.latitude = request.form.get('latitude', '')
        hospital.longitude = request.form.get('longitude', '')

        db.session.commit()

        flash("Hospital information updated successfully.", "success")
        return redirect(url_for('hospital_bp.hospital_dashboard'))

    return render_template('HOSPITAL/update_info.html', hospital=hospital)

@hospital_bp.route('/wards', methods=['GET', 'POST'])
@login_required
def manage_wards():
    hospital = current_user.hospitals[0]
    if request.method == 'POST':
        name = request.form.get('name')
        managed_by = request.form.get('managed_by')
        head_wardboy_name = request.form.get('head_wardboy_name')

        ward = Ward(name=name, managed_by=managed_by, head_wardboy_name=head_wardboy_name, hospital_id=hospital.id)

        db.session.add(ward)
        db.session.commit()
        flash('Ward added successfully.', 'success')
        return redirect(url_for('hospital_bp.manage_wards'))

    wards = Ward.query.filter_by(hospital_id=hospital.id).all()
    return render_template('HOSPITAL/manage_wards.html', hospital=hospital, wards=wards)

@hospital_bp.route('/hospital/wards/<int:ward_id>/manage_beds', methods=['GET'])
@login_required
def manage_beds(ward_id):
    ward = Ward.query.get_or_404(ward_id)
    beds = Bed.query.filter_by(ward_id=ward_id).all()
    return render_template('HOSPITAL/hospital_dashboard.html', ward=ward, beds=beds)

@hospital_bp.route('/hospital/manage_staff', methods=['GET', 'POST'])
@login_required
def manage_staff():
    hospital = current_user.hospitals[0]
    staff_members = HealthStaff.query.filter_by(ward_id=hospital.id).all()

    return render_template('HOSPITAL/manage_staff.html', staff_members=staff_members)

def update_vacant_beds(hospital_id):
    icu_beds_ready = Bed.query.join(Ward).filter(
        Bed.bed_type == 'ICU',
        Bed.status == 'ready',
        Ward.hospital_id == hospital_id
    ).count()

    opd_beds_ready = Bed.query.join(Ward).filter(
        Bed.bed_type == 'OPD',
        Bed.status == 'ready',
        Ward.hospital_id == hospital_id
    ).count()

    general_beds_ready = Bed.query.join(Ward).filter(
        Bed.bed_type == 'General',
        Bed.status == 'ready',
        Ward.hospital_id == hospital_id
    ).count()

    hospital = Hospital.query.get(hospital_id)
    if hospital:
        hospital.vacant_icu_beds = icu_beds_ready
        hospital.vacant_opd_beds = opd_beds_ready
        hospital.vacant_general_beds = general_beds_ready

        db.session.commit()

# Display current bookings
@hospital_bp.route('/show_bed_booking')
@login_required
def show_bed_booking():
    # Fetch the current hospital associated with the user
    if not current_user.hospitals:
        # Handle the case where the user has no associated hospitals
        return render_template('HOSPITAL/show_bed_booking.html', bookings=[], wards=[], hospital=None)
    
    hospital = current_user.hospitals[0]  # Assuming one hospital per user
    wards = Ward.query.filter_by(hospital_id=hospital.id).all()
    bookings = Booking.query.filter_by(hospital_id=hospital.id).all()
    
    # Debug: Print booking statuses to the console
    for booking in bookings:
        print(f"Booking ID: {booking.id}, Status: {booking.status}")
    
    return render_template('HOSPITAL/show_bed_booking.html', bookings=bookings, wards=wards, hospital=hospital)

# Verify admission code
@hospital_bp.route('/verify_admission_code/<int:booking_id>', methods=['POST'])
@login_required
def verify_admission_code(booking_id):
    data = request.json
    admission_code = data.get('admission_code')

    booking = Booking.query.get_or_404(booking_id)

    if booking.admission_code == admission_code:
        return jsonify(success=True)
    else:
        return jsonify(success=False)

# Complete check-in process
@hospital_bp.route('/complete_check_in/<int:booking_id>', methods=['POST'])
@login_required
def complete_check_in(booking_id):
    data = request.json
    patient_name = data.get('patient_name')
    ward_id = data.get('ward_id')
    bed_type = data.get('bed_type')

    booking = Booking.query.get_or_404(booking_id)

    # Fetch the next available bed in the selected ward
    bed = Bed.query.filter_by(ward_id=ward_id, bed_type=bed_type, status='ready').order_by(Bed.id).first()
    if not bed:
        return jsonify(success=False, message='No available beds found'), 400

    # Assign the bed and update its status to 'occupied'
    bed.status = 'occupied'
    bed_number = generate_bed_number(bed)
    db.session.commit()

    # Store the assigned bed number in the booking
    booking.status = 'CheckedIn'
    booking.assigned_bed_number = bed_number
    booking.user.name = patient_name
    db.session.commit()

    # If the booking had an ambulance, mark the ambulance as available again
    if booking.ambulance_id:
        ambulance = Ambulance.query.get(booking.ambulance_id)
        ambulance.status = 'available'
        db.session.commit()

    # Send an email to the user with the bed number
    msg = Message('Admission Details', recipients=[booking.user.email])
    msg.body = f"""
    Dear {booking.user.name},

    Your admission process at {booking.hospital.name} is complete. Below are your details:
    Ward: {Ward.query.get(ward_id).name}
    Bed Type: {bed_type}
    Assigned Bed Number: {bed_number}

    Thank you for choosing our services.

    Best regards,
    Hospital Management System
    Supercharged by HospiTell.
    """
    mail.send(msg)

    return jsonify(success=True, bed_number=bed_number)




# Fetch notifications
@hospital_bp.route('/notifications')
@login_required
def notifications():
    hospital_notifications = Notification.query.filter_by(hospital_id=current_user.hospitals[0].id).order_by(Notification.timestamp.desc()).all()
    return render_template('HOSPITAL/notifications.html', notifications=hospital_notifications)

@hospital_bp.route('/clear_notifications')
@login_required
def clear_notifications():
    notifications = Notification.query.filter_by(hospital_id=current_user.hospitals[0].id).all()
    for notification in notifications:
        db.session.delete(notification)
    db.session.commit()
    return redirect(url_for('hospital_bp.notifications'))

@hospital_bp.route('/get_wards_by_bed_type/<string:bed_type>', methods=['GET'])
@login_required
def get_wards_by_bed_type(bed_type):
    hospital = current_user.hospitals[0]  # Assuming the current user is associated with only one hospital
    wards = Ward.query.filter_by(hospital_id=hospital.id).all()

    ward_list = []
    for ward in wards:
        available_beds = Bed.query.filter_by(ward_id=ward.id, bed_type=bed_type, status='ready').count()
        if available_beds > 0:
            ward_list.append({'id': ward.id, 'name': ward.name, 'available_beds': available_beds})

    return jsonify({'wards': ward_list})

def generate_bed_number(bed):
    bed_type_prefix = {
        'General': 'GB',
        'ICU': 'IB',
        'OPD': 'OB'
    }
    # Count the number of already assigned beds of this type in the ward
    bed_count = Bed.query.filter_by(ward_id=bed.ward_id, bed_type=bed.bed_type).filter(Bed.status != 'ready').count()
    return f"{bed_type_prefix[bed.bed_type]}{bed_count + 1}"


@hospital_bp.route('/manage_opd', methods=['GET', 'POST'])
@login_required
def manage_opd():
    hospital = current_user.hospitals[0]  # Assuming the current user is associated with only one hospital

    if request.method == 'POST':
        name = request.form.get('name')
        expertise = request.form.get('expertise')
        chamber_timings = request.form.get('chamber_timings')
        availability_days = request.form.get('availability_days')
        department_id = request.form.get('department_id')

        doctor = Doctor(name=name, expertise=expertise, chamber_timings=chamber_timings,
                        availability_days=availability_days, department_id=department_id,
                        hospital_id=hospital.id)
        db.session.add(doctor)
        db.session.commit()
        flash('Doctor registered successfully', 'success')

    departments = Department.query.filter_by(hospital_id=hospital.id).all()
    doctors = Doctor.query.filter_by(hospital_id=hospital.id).all()

    return render_template('HOSPITAL/manage_opd.html', doctors=doctors, departments=departments, hospital=hospital)


@hospital_bp.route('/show_opd_bookings', methods=['GET'])
@login_required
def show_opd_bookings():
    hospital = current_user.hospitals[0]

    selected_date = request.args.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
    appointments = OPDAppointment.query.join(Doctor).join(Department).filter(
        Department.hospital_id == hospital.id,
        OPDAppointment.appointment_date == selected_date
    ).all()

    return render_template('HOSPITAL/show_opd_bookings.html', appointments=appointments, hospital=hospital, selected_date=selected_date)

@hospital_bp.route('/verify_booking', methods=['POST'])
@login_required
def verify_booking():
    booking_id = request.form.get('booking_id')
    booking = LabTestBooking.query.get(booking_id)
    
    if booking:
        booking.status = 'checked in'
        db.session.commit()
        
        # Send email to patient with queue number here
        # Example: send_email(booking.patient.email, queue_number)
        
        flash('Booking successfully checked in!', 'success')
    else:
        flash('Booking not found.', 'error')
    
    return redirect(url_for('hospital_bp.show_lab_test_bookings'))



@hospital_bp.route('/fetch_checked_in_patients', methods=['GET'])
@login_required
def fetch_checked_in_patients():
    date = request.args.get('date')
    doctor_id = request.args.get('doctor_id')
    time_slot = request.args.get('time_slot')
    hospital = current_user.hospitals[0]

    # Fetch checked-in patients
    patients = OPDAppointment.query.filter_by(
        hospital_id=hospital.id,
        appointment_date=date,
        doctor_id=doctor_id,
        time_slot=time_slot
    ).all()

    # Check for an existing queue
    existing_queue = OPDQueue.query.filter_by(
        doctor_id=doctor_id,
        appointment_date=date,
        time_slot=time_slot,
        status='Pending'
    ).order_by(OPDQueue.queue_number).all()

    # Prepare patient data with status
    patients_data = [
        {
            'name': patient.user.name,
            'age': patient.user.age,
            'status': patient.status
        } for patient in patients
    ]

    # Prepare queue data, handling both regular and on-site registrations
    queue_data = []
    for entry in existing_queue:
        if entry.patient_id and entry.patient:
            # Regular patient with an OPDAppointment entry
            queue_data.append({
                'id': entry.patient_id,
                'name': entry.patient.user.name,
                'queue_number': entry.queue_number,
                'type': 'Emergency' if entry.patient.is_emergency else 'Senior' if entry.patient.user.age >= 60 else 'Regular'
            })
        elif entry.onsite_name:
            # On-site registered patient without an OPDAppointment
            queue_data.append({
                'id': entry.id,
                'name': entry.onsite_name,
                'queue_number': entry.queue_number,
                'type': 'On-site'
            })

    return jsonify({'patients': patients_data, 'existingQueue': queue_data})









@hospital_bp.route('/manage_virtual_queue', methods=['GET', 'POST'])
@login_required
def manage_virtual_queue():
    hospital = current_user.hospitals[0]
    
    # Set default date to today
    selected_date = datetime.utcnow().strftime('%Y-%m-%d')
    doctor_id = request.args.get('doctor_id')
    time_slot = request.args.get('time_slot')
    
    # Store selections in session
    session['selected_date'] = selected_date
    session['selected_doctor'] = doctor_id
    session['selected_time_slot'] = time_slot

    # Fetch all doctors in the hospital
    doctors = Doctor.query.filter_by(hospital_id=hospital.id).all()
    
    # Prepare time slots based on the selected doctor
    time_slots = []
    selected_doctor = None
    if doctor_id:
        selected_doctor = Doctor.query.get(doctor_id)
        time_slots = selected_doctor.chamber_timings.split(',')
    
    # Fetch the existing queue
    existing_queue = []
    if doctor_id and time_slot:
        existing_queue = OPDQueue.query.filter_by(
            doctor_id=doctor_id,
            appointment_date=selected_date,
            time_slot=time_slot
        ).all()

    # Fetch the patients based on selected date, doctor, and time slot
    patients = []
    if doctor_id and time_slot:
        patients = OPDAppointment.query.filter_by(
            hospital_id=hospital.id,
            appointment_date=selected_date,
            doctor_id=doctor_id,
            time_slot=time_slot,
            status='CheckedIn'
        ).order_by(OPDAppointment.queue_number).all()

    # Render the template with the necessary context
    return render_template('HOSPITAL/manage_virtual_queue.html', 
                           patients=patients, 
                           hospital=hospital, 
                           doctors=doctors,
                           selected_date=selected_date,
                           selected_doctor=doctor_id,  
                           time_slots=time_slots,
                           selected_time_slot=time_slot,
                           existing_queue=existing_queue)  # Pass existing queue


@hospital_bp.route('/create_opd_queue', methods=['POST'])
@login_required
def create_opd_queue():
    data = request.get_json()
    selected_date = data.get('date')
    doctor_id = data.get('doctor_id')
    time_slot = data.get('time_slot')
    hospital = current_user.hospitals[0]

    # Fetch patients with CheckedIn status in OPDAppointment
    checked_in_patients = OPDAppointment.query.filter_by(
        hospital_id=hospital.id,
        appointment_date=selected_date,
        doctor_id=doctor_id,
        time_slot=time_slot,
        status='CheckedIn'
    ).all()

    queue_data = []

    # Create the queue using only CheckedIn patients and avoid duplicates
    for patient in checked_in_patients:
        # Check if this patient is already in the queue to avoid duplicates
        existing_entry = OPDQueue.query.filter_by(patient_id=patient.id, doctor_id=doctor_id, appointment_date=selected_date, time_slot=time_slot).first()
        if not existing_entry:
            queue_data.append({
                'id': patient.id,
                'name': patient.user.name,
                'is_emergency': patient.is_emergency,
                'is_senior': patient.user.age >= 60
            })

    # Sort the queue based on priority
    queue_data.sort(key=lambda x: (not x['is_emergency'], not x['is_senior']))

    # Assign queue numbers based on the sorted order
    for index, patient in enumerate(queue_data, start=1):
        # Add new queue entry
        queue_entry = OPDQueue(
            patient_id=patient['id'],
            queue_number=index,
            doctor_id=doctor_id,
            appointment_date=selected_date,
            time_slot=time_slot,
            status='Pending'  # Initial status set to Pending
        )
        db.session.add(queue_entry)

    db.session.commit()

    # Prepare the response data
    response_queue_data = [{
        'id': patient['id'],
        'queue_number': index,
        'name': patient['name'],
        'type': 'Emergency' if patient['is_emergency'] else 'Senior' if patient['is_senior'] else 'Regular'
    } for index, patient in enumerate(queue_data, start=1)]

    return jsonify(success=True, queue=response_queue_data)

@hospital_bp.route('/update_onsite_patient_status/<int:patient_id>', methods=['POST'])
@login_required
def update_onsite_patient_status(patient_id):
    """
    Update status for onsite registered patients and send a completion email.
    """
    opd_queue_entry = OPDQueue.query.filter_by(id=patient_id, status='Pending').first()
    
    if opd_queue_entry:
        # Capture the queue number of the patient being marked as Done
        completed_queue_number = opd_queue_entry.queue_number

        # Mark the patient status as 'Done'
        opd_queue_entry.status = 'Done'
        db.session.commit()

        # Determine the patient's email and name for sending a thank-you email
        recipient_email = opd_queue_entry.onsite_email if opd_queue_entry.onsite_name else opd_queue_entry.patient.user.email
        recipient_name = opd_queue_entry.onsite_name if opd_queue_entry.onsite_name else opd_queue_entry.patient.user.name

        # Send thank-you email
        if recipient_email:
            msg = Message('Your OPD Appointment Completion', recipients=[recipient_email])
            msg.body = f"Dear {recipient_name}, your appointment registered onsite has been marked as done. Thank you!"
            mail.send(msg)

        # Notify the next patients in line, passing the queue number of the completed patient
        notify_upcoming_patients_internal(
            doctor_id=opd_queue_entry.doctor_id,
            appointment_date=opd_queue_entry.appointment_date,
            time_slot=opd_queue_entry.time_slot,
            completed_queue_number=completed_queue_number
        )

        # Fetch the updated queue, excluding "Done" entries
        updated_queue = get_current_queue(
            doctor_id=opd_queue_entry.doctor_id,
            appointment_date=opd_queue_entry.appointment_date,
            time_slot=opd_queue_entry.time_slot
        )

        # Prepare the queue data for the response
        filtered_queue = [
            {
                'id': entry.id,
                'queue_number': entry.queue_number,
                'name': entry.onsite_name if entry.onsite_name else entry.patient.user.name,
                'type': 'On-site' if entry.onsite_name else 'Regular'
            } for entry in updated_queue
        ]
        return jsonify(success=True, updatedQueue=filtered_queue), 200

    return jsonify(success=False, error="Patient not found or already marked as done."), 400


@hospital_bp.route('/register_patient', methods=['POST'])
@login_required
def register_patient():
    data = request.json
    name = data['name']
    email = data.get('email')
    age = data.get('age')
    date = data['date']
    doctor_id = data['doctor_id']
    time_slot = data['time_slot']

    # Determine the max queue number for this time slot to assign the next one
    max_queue_number = db.session.query(func.max(OPDQueue.queue_number)).filter_by(
        appointment_date=date, doctor_id=doctor_id, time_slot=time_slot
    ).scalar() or 0

    # Create a new OPDQueue entry with the next queue number and onsite information
    queue_entry = OPDQueue(
        onsite_name=name,
        onsite_email=email,  # Store onsite email
        onsite_age=age,      # Store onsite age
        queue_number=max_queue_number + 1,
        doctor_id=doctor_id,
        appointment_date=date,
        time_slot=time_slot,
        status='Pending'
    )
    db.session.add(queue_entry)
    db.session.commit()

    return jsonify({
        'queue_id': queue_entry.id,
        'queue_number': queue_entry.queue_number,
        'onsite_name': queue_entry.onsite_name
    })





@hospital_bp.route('/get_max_queue_number_opd', methods=['GET'])
@login_required
def get_max_queue_number_opd():
    date = request.args.get('date')
    doctor_id = request.args.get('doctor_id')
    time_slot = request.args.get('time_slot')

    max_queue_number = db.session.query(func.max(OPDQueue.queue_number)).filter_by(
        appointment_date=date, doctor_id=doctor_id, time_slot=time_slot
    ).scalar() or 0

    return jsonify({'max_queue_number': max_queue_number})







@hospital_bp.route('/update_patient_status/<int:patient_id>', methods=['POST'])
@login_required
def update_patient_status(patient_id):
    # Only update if the patient is in Pending status in OPDQueue and CheckedIn in OPDAppointment
    opd_queue_entry = OPDQueue.query.filter_by(patient_id=patient_id, status='Pending').first()
    patient = OPDAppointment.query.get(patient_id)

    if opd_queue_entry and patient and patient.status == 'CheckedIn':
        # Capture the queue number of the patient being marked as Done
        completed_queue_number = opd_queue_entry.queue_number

        # Update status to Done in both OPDQueue and OPDAppointment models
        opd_queue_entry.status = 'Done'
        patient.status = 'Done'
        db.session.commit()

        # Send thank-you email to the patient
        msg = Message('Your OPD Appointment Update', recipients=[patient.user.email])
        msg.body = f"Dear {patient.user.name}, your appointment has been marked as done. Thank you!"
        mail.send(msg)

        # Notify the next patients in line, passing the queue number of the completed patient
        notify_upcoming_patients_internal(
            doctor_id=opd_queue_entry.doctor_id,
            appointment_date=opd_queue_entry.appointment_date,
            time_slot=opd_queue_entry.time_slot,
            completed_queue_number=completed_queue_number
        )

        # Fetch the updated queue without the Done status patients
        updated_queue = get_current_queue(
            doctor_id=opd_queue_entry.doctor_id, 
            appointment_date=opd_queue_entry.appointment_date, 
            time_slot=opd_queue_entry.time_slot
        )

        filtered_queue = [
            {
                'id': patient.patient_id,
                'queue_number': patient.queue_number,
                'name': patient.patient.user.name,
                'type': 'Emergency' if patient.patient.is_emergency else 'Senior' if patient.patient.user.age >= 60 else 'Regular'
            }
            for patient in updated_queue
        ]

        return jsonify(success=True, updatedQueue=filtered_queue), 200

    return jsonify(success=False, error="Patient not found in queue or not eligible for update."), 400



def get_current_queue(doctor_id=None, appointment_date=None, time_slot=None):
    """
    Retrieve the current queue with Pending patients only, ordered by queue_number.
    """
    query = OPDQueue.query.filter(OPDQueue.status == 'Pending')
    
    if doctor_id:
        query = query.filter(OPDQueue.doctor_id == doctor_id)
    if appointment_date:
        query = query.filter(OPDQueue.appointment_date == appointment_date)
    if time_slot:
        query = query.filter(OPDQueue.time_slot == time_slot)

    return query.order_by(OPDQueue.queue_number).all()



@hospital_bp.route('/notify_upcoming_patients', methods=['POST'])
@login_required
def notify_upcoming_patients():
    """
    HTTP route to notify the next four patients in line. Calls the internal function.
    """
    notify_upcoming_patients_internal()
    return jsonify(success=True), 200


def notify_upcoming_patients_internal(doctor_id, appointment_date, time_slot, completed_queue_number):
    """
    Internal function to notify the next four patients in line about their updated queue status.
    """
    # Fetch the updated queue, which includes only Pending patients in order
    updated_queue = get_current_queue(
        doctor_id=doctor_id,
        appointment_date=appointment_date,
        time_slot=time_slot
    )

    # Notify the next four patients in line
    for patient_entry in updated_queue[:4]:
        # Determine if the patient is onsite or registered
        if patient_entry.onsite_name:  # Onsite patient
            recipient_email = patient_entry.onsite_email
            recipient_name = patient_entry.onsite_name
        else:  # Registered patient
            recipient_email = patient_entry.patient.user.email
            recipient_name = patient_entry.patient.user.name

        # Send notification email if email exists
        if recipient_email:
            msg = Message('Queue Update Notification', recipients=[recipient_email])
            msg.body = (
                f"Hello {recipient_name},\n\n"
                f"Queue number {completed_queue_number} has completed its appointment.\n"
                f"You are now #{patient_entry.queue_number} in the queue. You will meet the doctor soon.\n\n"
                f"Thank you for your patience."
            )
            mail.send(msg)





@hospital_bp.route('/get_time_slots_opd/<int:doctor_id>', methods=['GET'])
@login_required
def get_time_slots_opd(doctor_id):
    date = request.args.get('date')
    # Assuming you have a method to get available time slots for a doctor on a specific date
    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return jsonify({'time_slots': []})

    # Fetch time slots based on the doctor's schedule
    time_slots = doctor.chamber_timings.split(',')  # Example: Assuming chamber_timings is a comma-separated string
    return jsonify({'time_slots': time_slots})

@hospital_bp.route('/show_lab_test_bookings', methods=['GET'])
@login_required
def show_lab_test_bookings():
    # Get the first associated hospital for the current user
    hospital = current_user.hospitals[0]  # Adjust if user has multiple hospitals

    # Get the selected date from query parameters
    selected_date = request.args.get('filter_date')
    if selected_date:
        # Filter bookings by the selected date
        bookings = LabTestBooking.query.filter_by(hospital_id=hospital.id, booking_date=selected_date).all()
        checked_in_patients = LabTestBooking.query.filter_by(
            hospital_id=hospital.id,
            booking_date=selected_date,
            status='CheckedIn'
        ).all()
    else:
        # If no date selected, show all bookings
        bookings = LabTestBooking.query.filter_by(hospital_id=hospital.id).all()
        checked_in_patients = []

    # Pass the 'hospital' variable to the template
    return render_template('HOSPITAL/show_lab_test_bookings.html', 
                           bookings=bookings, 
                           checked_in_patients=checked_in_patients,
                           selected_date=selected_date or "all dates",
                           hospital=hospital)  # Pass 'hospital' to the template



# routes.py (hospital_bp)
# routes.py (hospital_bp)
@hospital_bp.route('/manage_diagnostic_departments', methods=['GET', 'POST'])
@login_required
def manage_diagnostic_departments():
    hospital = current_user.hospitals[0]  # Assuming one hospital per admin

    # Handle POST request for adding new diagnostic departments and tests
    if request.method == 'POST':
        department_name = request.form.get('department_name')  # Get department name
        test_name = request.form.get('test_name')              # Get test name
        test_price = request.form.get('price')                 # Get test price

        # Validate that all fields are present
        if not department_name or not test_name or not test_price:
            flash('All fields are required', 'danger')
            return redirect(url_for('hospital_bp.manage_diagnostic_departments'))

        # Convert the price to float, and handle conversion error if necessary
        try:
            test_price = float(test_price)
        except ValueError:
            flash('Invalid price format', 'danger')
            return redirect(url_for('hospital_bp.manage_diagnostic_departments'))

        # Check if department already exists
        department = DiagnosticDepartment.query.filter_by(name=department_name, hospital_id=hospital.id).first()

        # If department does not exist, create a new one
        if not department:
            department = DiagnosticDepartment(name=department_name, hospital_id=hospital.id)
            db.session.add(department)
            db.session.commit()

        # Add the diagnostic test to the selected department
        new_test = DiagnosticTest(name=test_name, price=test_price, department_id=department.id)
        db.session.add(new_test)
        db.session.commit()

        flash(f'Diagnostic Department "{department_name}" with test "{test_name}" added successfully.', 'success')
        return redirect(url_for('hospital_bp.manage_diagnostic_departments'))

    # Fetch existing diagnostic departments and tests for display
    departments = DiagnosticDepartment.query.filter_by(hospital_id=hospital.id).all()

    return render_template('HOSPITAL/manage_diagnostic_departments.html', departments=departments, hospital=hospital)


#@hospital_bp.route('/book_lab_test', methods=['POST'])
#@login_required
#def book_lab_test():
#    # Get form data
#    category = request.form.get('category')
#    test_name = request.form.get('test_name')
#    hospital_id = request.form.get('hospital_id')
#
#    # Handle file upload
#    if 'prescription' not in request.files:
#        flash('No file part', 'danger')
#        return redirect(request.url)
#    file = request.files['prescription']
#    if file.filename == '':
#        flash('No selected file', 'danger')
#        return redirect(request.url)
#    if file and allowed_file(file.filename):
#        filename = secure_filename(file.filename)
#        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
#        file.save(filepath)
#    else:
#        flash('Invalid file format. Only PDF, JPG, and PNG are allowed.', 'danger')
#        return redirect(request.url)
#
#    # Generate a unique 4-digit booking code
#    booking_code = str(random.randint(1000, 9999))
#
#    # Save booking to the database
#    booking = LabTestBooking(
#        user_id=current_user.id,
#        test_category=category,
#        test_name=test_name,
#        hospital_id=hospital_id,
#        prescription=filepath,
#        booking_code=booking_code,
#        status='Pending'
#    )
#    db.session.add(booking)
#    db.session.commit()
#
#    # Send email confirmation
#    msg = Message('Lab Test Booking Confirmation', recipients=[current_user.email])
#    msg.body = f"""
#    Dear {current_user.name},
#
#    Your lab test booking has been confirmed:
#    Test: {test_name}
#    Hospital: {Hospital.query.get(hospital_id).name}
#    Booking Code: {booking_code}
#
#    Please show this code at the hospital on arrival.
#
#    Best regards,
#    Hospital Management System
#    """
#    mail.send(msg)
#
#    flash('Lab test booked successfully. A confirmation email has been sent.', 'success')
#    return redirect(url_for('hospital_bp.show_lab_test_bookings'))
#


####################################################################################################################################################################################
#@hospital_bp.route('/manage_lab_tests', methods=['GET', 'POST'])
#@login_required
#def manage_lab_tests():
#    hospital = current_user.hospitals[0]  # Assuming one hospital per admin
#
#    if request.method == 'POST':
#        # Adding new lab test details
#        category = request.form.get('category')
#        test_name = request.form.get('test_name')
#        price = request.form.get('price')
#
#        new_test = DiagnosticTest(hospital_id=hospital.id, test_category=category, test_name=test_name, price=price)
#        db.session.add(new_test)
#        db.session.commit()
#        flash('Lab test added successfully.', 'success')
#    
#    tests = DiagnosticTest.query.filter_by(hospital_id=hospital.id).all()
#    return render_template('HOSPITAL/manage_lab_tests.html', tests=tests, hospital=hospital)
#
####################################################################################################################################################################################
@hospital_bp.route('/manage_lab_test_queue', methods=['GET'])
@login_required
def manage_lab_test_queue():
    hospital = current_user.hospitals[0]
    tests = db.session.query(DiagnosticTest).join(DiagnosticDepartment).filter(
        DiagnosticDepartment.hospital_id == hospital.id
    ).distinct(DiagnosticTest.name).all()
    return render_template('HOSPITAL/manage_lab_test_queue.html', tests=tests, hospital=hospital)


@hospital_bp.route('/create_lab_test_queue', methods=['POST'])
@login_required
def create_lab_test_queue():
    test_name = request.form.get('test_name')
    test_date = request.form.get('test_date')
    hospital = current_user.hospitals[0]

    # Fetch confirmed, checked-in patients for the test and date
    patients = LabTestBooking.query.filter_by(
        hospital_id=hospital.id,
        test_name=test_name,
        status='CheckedIn',
        booking_date=test_date
    ).order_by(LabTestBooking.id).all()

    if not patients:
        return jsonify(success=False, message="No confirmed patients found for the selected test and date."), 404

    # Get the highest existing queue number for the test and date
    max_queue_number = db.session.query(db.func.max(LabTestQueue.queue_number)).filter_by(
        hospital_id=hospital.id,
        test_name=test_name,
        booking_date=test_date
    ).scalar() or 0

    # Add patients who are not already in the queue
    for patient in patients:
        existing_entry = LabTestQueue.query.filter_by(
            hospital_id=hospital.id,
            test_name=test_name,
            booking_date=test_date,
            lab_test_booking_id=patient.id
        ).first()
        
        if not existing_entry:  # Only add if patient is not already in the queue
            max_queue_number += 1
            queue_entry = LabTestQueue(
                lab_test_booking_id=patient.id,
                queue_number=max_queue_number,
                booking_date=test_date,
                test_name=test_name,
                hospital_id=hospital.id
            )
            db.session.add(queue_entry)

    db.session.commit()
    return jsonify(success=True, message="Lab test queue created successfully!")


@hospital_bp.route('/api/mark_done/<int:patient_id>', methods=['POST'])
@login_required
def mark_done(patient_id):
    try:
        # Fetch patient booking entry
        patient = LabTestBooking.query.get_or_404(patient_id)
        test_name = patient.test_name
        test_date = patient.booking_date.strftime('%Y-%m-%d')
        hospital_id = patient.hospital_id

        # Update the booking status to DONE
        patient.status = 'DONE'
        db.session.commit()

        # Fetch and delete the queue entry for the patient
        queue_entry = LabTestQueue.query.filter_by(lab_test_booking_id=patient_id).first()
        if queue_entry:
            current_queue_number = queue_entry.queue_number
            db.session.delete(queue_entry)
            db.session.commit()

            # Send thank-you email after successfully marking as done
            msg = Message("Thank you for visiting", recipients=[patient.user.email])
            msg.body = (f"Dear {patient.user.name},\n\n"
                        f"Thank you for completing your lab test for '{test_name}' on {test_date}.\n"
                        f"We appreciate your visit.\n\nBest regards,\nYour Hospital Team")
            mail.send(msg)

            # Notify the next patients in the queue
            notify_next_users(current_queue_number, test_name, test_date, hospital_id)
        else:
            print(f"Queue number not found for patient_id: {patient_id}")

        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        print(f"Error marking patient as done: {e}")
        return jsonify(success=False, error=str(e))




def notify_next_users(current_queue_number, test_name, test_date, hospital_id):
    """Notify up to five patients behind the current patient in the queue."""
    try:
        # Retrieve up to 5 patients immediately following the current queue number
        next_patients = LabTestQueue.query.filter(
            LabTestQueue.hospital_id == hospital_id,
            LabTestQueue.test_name == test_name,
            LabTestQueue.booking_date == test_date,
            LabTestQueue.queue_number > current_queue_number  # Only those with a greater queue number
        ).order_by(LabTestQueue.queue_number).limit(5).all()

        # Send notification emails to the next patients
        for patient in next_patients:
            msg = Message("Lab Test Queue Update", recipients=[patient.lab_test_booking.user.email])
            msg.body = (f"Dear {patient.lab_test_booking.user.name},\n\n"
                        f"The patient with queue number {current_queue_number} has completed their test. "
                        f"Your queue number is {patient.queue_number}. Please be ready.\n\nThank you.")
            mail.send(msg)

    except Exception as e:
        print(f"Error notifying next patients: {e}")



@hospital_bp.route('/api/get_queue', methods=['GET'])
@login_required
def get_queue():
    test_name = request.args.get('test_name')
    test_date = request.args.get('test_date')
    hospital = current_user.hospitals[0]

    # Fetch queue entries for the test, date, and hospital, ordered by queue number
    queue_entries = LabTestQueue.query.filter_by(
        hospital_id=hospital.id,
        test_name=test_name,
        booking_date=test_date
    ).order_by(LabTestQueue.queue_number).all()

    # Prepare queue data with user name and queue number
    queue_data = [{
        'id': entry.lab_test_booking_id,
        'user_name': entry.lab_test_booking.user.name,
        'queue_number': entry.queue_number
    } for entry in queue_entries]
    
    return jsonify(success=True, patients=queue_data)

@hospital_bp.route('/api/get_patient_counts', methods=['GET'])
@login_required
def get_patient_counts():
    test_name = request.args.get('test_name')
    test_date = request.args.get('test_date')
    hospital = current_user.hospitals[0]

    # Count of CheckedIn patients
    checked_in_count = LabTestBooking.query.filter_by(
        hospital_id=hospital.id,
        test_name=test_name,
        status='CheckedIn',
        booking_date=test_date
    ).count()

    # Count of Done patients
    done_count = LabTestBooking.query.filter_by(
        hospital_id=hospital.id,
        test_name=test_name,
        status='DONE',
        booking_date=test_date
    ).count()

    return jsonify(success=True, checked_in_count=checked_in_count, done_count=done_count)



@hospital_bp.route('/api/check_queue_exists', methods=['GET'])
@login_required
def check_queue_exists():
    test_name = request.args.get('test_name')
    test_date = request.args.get('test_date')
    hospital = current_user.hospitals[0]

    # Check if a queue already exists
    queue_exists = LabTestQueue.query.filter_by(
        hospital_id=hospital.id,
        test_name=test_name,
        booking_date=test_date
    ).first() is not None

    return jsonify(queueExists=queue_exists)


@hospital_bp.route('/api/get_new_check_ins', methods=['GET'])
@login_required
def get_new_check_ins():
    test_name = request.args.get('test_name')
    test_date = request.args.get('test_date')
    hospital = current_user.hospitals[0]

    # Find patients who are checked-in but not in the queue
    queued_patient_ids = [entry.lab_test_booking_id for entry in LabTestQueue.query.filter_by(
        hospital_id=hospital.id, test_name=test_name, booking_date=test_date
    )]
    new_patients = LabTestBooking.query.filter(
        LabTestBooking.hospital_id == hospital.id,
        LabTestBooking.test_name == test_name,
        LabTestBooking.status == 'CheckedIn',
        LabTestBooking.booking_date == test_date,
        ~LabTestBooking.id.in_(queued_patient_ids)
    ).all()

    # Add new check-ins to the LabTestQueue database
    max_queue_number = db.session.query(db.func.max(LabTestQueue.queue_number)).filter_by(
        hospital_id=hospital.id, test_name=test_name, booking_date=test_date
    ).scalar() or 0

    new_patients_data = []
    for patient in new_patients:
        max_queue_number += 1
        new_entry = LabTestQueue(
            lab_test_booking_id=patient.id,
            queue_number=max_queue_number,
            booking_date=test_date,
            test_name=test_name,
            hospital_id=hospital.id
        )
        db.session.add(new_entry)
        new_patients_data.append({'id': patient.id, 'user_name': patient.user.name, 'queue_number': max_queue_number})

    db.session.commit()

    return jsonify(success=True, newPatients=new_patients_data)

@hospital_bp.route('/api/get_max_queue_number', methods=['GET'])
@login_required
def get_max_queue_number():
    test_name = request.args.get('test_name')
    test_date = request.args.get('test_date')
    hospital = current_user.hospitals[0]

    # Fetch the highest queue number for the specified test and date
    max_queue_number = db.session.query(db.func.max(LabTestQueue.queue_number)).filter_by(
        hospital_id=hospital.id,
        test_name=test_name,
        booking_date=test_date
    ).scalar() or 0  # Default to 0 if no queue exists

    return jsonify(success=True, maxQueueNumber=max_queue_number)




@hospital_bp.route('/api/save_queue', methods=['POST'])
@login_required
def save_queue():
    test_name = request.json.get('test_name')
    test_date = request.json.get('test_date')
    queue_data = request.json.get('queue_data')
    hospital = current_user.hospitals[0]

    try:
        for patient in queue_data:
            # Check if the patient already has a queue entry
            existing_entry = LabTestQueue.query.filter_by(
                hospital_id=hospital.id,
                test_name=test_name,
                booking_date=test_date,
                lab_test_booking_id=patient['id']
            ).first()

            # If patient is not already in queue, add them
            if not existing_entry:
                new_entry = LabTestQueue(
                    lab_test_booking_id=patient['id'],
                    queue_number=patient['queue_number'],
                    booking_date=test_date,
                    test_name=test_name,
                    hospital_id=hospital.id
                )
                db.session.add(new_entry)

        db.session.commit()
        return jsonify(success=True, message="Queue saved successfully!")
    except Exception as e:
        return jsonify(success=False, error=str(e))









#@hospital_bp.route('/check_in/<int:booking_id>', methods=['POST'])
#@login_required
#def check_in(booking_id):
#    # Fetch the booking record
#    booking = LabTestBooking.query.get_or_404(booking_id)
#    data = request.json
#    booking_code = data.get('booking_code')
#
#    # Verify the booking code
#    if booking.booking_code != booking_code:
#        return jsonify({'success': False, 'message': 'Invalid booking code'}), 400
#
#    # Ensure the booking is not already checked in
#    if booking.status == 'Verified':
#        return jsonify({'success': False, 'message': 'This booking has already been checked in.'}), 400
#
#    # Update status to 'Verified'
#    booking.status = 'Verified'
#
#    # Assign queue number for the hospital
#    latest_queue_number = Queue.query.filter_by(hospital_id=booking.hospital_id).count() + 1
#    new_queue = Queue(
#        hospital_id=booking.hospital_id,
#        test_booking_id=booking.id,
#        queue_number=latest_queue_number
#    )
#    db.session.add(new_queue)
#    db.session.commit()
#
#    # Send an email to the user with the queue number
#    msg = Message('Queue Confirmation', recipients=[booking.user.email])
#    msg.body = f"""
#    Dear {booking.user.name},
#
#    Your check-in for the lab test {booking.test_name} at {booking.hospital.name} on {booking.booking_date} is confirmed.
#    Your queue number is {latest_queue_number}.
#
#    Thank you,
#    Hospital Management System
#    """
#    mail.send(msg)
#
#    return jsonify({'success': True, 'message': 'Check-in successful. Queue number assigned.'})
#
#
#
#@hospital_bp.route('/complete_lab_test_check_in/<int:booking_id>', methods=['POST'])
#@login_required
#def complete_lab_test_check_in(booking_id):
#    data = request.get_json()  # Again, using get_json for consistency
#    booking = LabTestBooking.query.get_or_404(booking_id)
#
#    # Update the booking status to 'CheckedIn'
#    booking.status = 'CheckedIn'
#
#    # Update patient's name if provided
#    if 'patient_name' in data:
#        booking.user.name = data.get('patient_name')
#
#    # Handle additional information like emergency flag
#    if 'is_emergency' in data:
#        booking.is_emergency = bool(data.get('is_emergency'))  # Ensuring it's converted to a boolean
#
#    db.session.commit()
#
#    # Send confirmation email to the patient
#    msg = Message('Lab Test Check-In Confirmation', recipients=[booking.user.email])
#    msg.body = f"""
#    Dear {booking.user.name},
#
#    You have successfully checked in for your lab test: {booking.test_name} at {booking.hospital.name}.
#
#    You are now in the queue. We will notify you with the current queue status.
#
#    Best regards,
#    Hospital Management System
#    """
#    mail.send(msg)
#
#    return jsonify(success=True)
#
@hospital_bp.route('/register_department', methods=['POST'])
@login_required
def register_department():
    name = request.form.get('name')

    department = Department(name=name)
    db.session.add(department)
    db.session.commit()
    flash('Department registered successfully', 'success')
    return redirect(url_for('hospital_bp.manage_opd'))

@hospital_bp.route('/view_check_ins', methods=['GET'])
@login_required
def view_check_ins():
    test_id = request.args.get('test_id')
    booking_date = request.args.get('booking_date')

    # Fetch bookings for the specific date and test with 'Verified' status
    bookings = LabTestBooking.query.filter_by(test_id=test_id, booking_date=booking_date, status='Verified').all()

    return render_template('hospital_dashboard/view_check_ins.html', bookings=bookings)

@hospital_bp.route('/verify_test_booking_code/<int:booking_id>', methods=['POST'])
@login_required
def verify_test_booking_code(booking_id):
    data = request.json
    booking_code = data.get('booking_code')

    # Fetch the booking
    booking = LabTestBooking.query.get_or_404(booking_id)

    # Verify the booking code and update status if correct
    if booking.booking_code == booking_code:
        booking.status = 'CheckedIn'
        db.session.commit()
        
        # Fetch updated list of checked-in patients for the booking date
        checked_in_patients = LabTestBooking.query.filter_by(
            hospital_id=booking.hospital_id,
            booking_date=booking.booking_date,
            status='CheckedIn'
        ).all()

        # Serialize checked-in patients to JSON
        checked_in_patients_data = [{
            'id': patient.id,
            'user_name': patient.user.name,
            'test_category': patient.test_category,
            'test_name': patient.test_name,
            'booking_date': patient.booking_date.strftime('%Y-%m-%d')
        } for patient in checked_in_patients]

        return jsonify(success=True, checked_in_patients=checked_in_patients_data)
    else:
        return jsonify(success=False)






#@hospital_bp.route('/update_patient_status/<int:appointment_id>', methods=['POST'])
#@login_required
#def update_patient_status(appointment_id):
#    appointment = OPDAppointment.query.get_or_404(appointment_id)
#    completed_queue_number = appointment.queue_number
#
#    if completed_queue_number is None:
#        return jsonify(success=False, error="Queue number is not set for this appointment."), 400
#
#    appointment.status = 'Done'
#    db.session.commit()
#
#    # Send a final confirmation email to the patient
#    msg = Message('OPD Appointment Completed', recipients=[appointment.user.email])
#    msg.body = f"""
#    Dear {appointment.user.name},
#
#    Your OPD appointment with Dr. {appointment.doctor.name} on {appointment.appointment_date} at {appointment.time_slot} is completed.
#    Thank you for using our services.
#
#    Best regards,
#    Hospital Management System
#    """
#    mail.send(msg)
#
#    # Notify all remaining patients in the queue
#    remaining_patients = OPDAppointment.query.filter(
#        OPDAppointment.hospital_id == appointment.hospital_id,
#        OPDAppointment.appointment_date == appointment.appointment_date,
#        OPDAppointment.status == 'CheckedIn',
#        OPDAppointment.queue_number.isnot(None),  # Ensure queue_number is not None
#        OPDAppointment.queue_number > completed_queue_number
#    ).order_by(OPDAppointment.queue_number).all()
#
#    for patient in remaining_patients:
#        send_queue_update_email(patient.queue_number, patient)
#    
#    flash('Patient status updated successfully', 'success')
#    return jsonify(success=True)
#
#def send_queue_update_email(queue_number, patient):
#    msg = Message('Queue Update: Your Position', recipients=[patient.user.email])
#    msg.body = f"""
#    Dear {patient.user.name},
#
#    Your queue number is now {queue_number}.
#
#    Please be prepared to meet the doctor shortly.
#
#    Best regards,
#    Hospital Management System
#    """
#    mail.send(msg)
#

@hospital_bp.route('/get_departments/<int:hospital_id>', methods=['GET'])
@login_required
def get_departments(hospital_id):
    departments = Department.query.filter_by(hospital_id=hospital_id).all()
    return jsonify({'departments': [{'id': dept.id, 'name': dept.name, 'image': dept.image} for dept in departments]})



@hospital_bp.route('/manage_opd_landing')
@login_required
def manage_opd_landing():
    hospital = current_user.hospitals[0]
    return render_template('HOSPITAL/manage_opd_landing.html', hospital=hospital)


@hospital_bp.route('/manage_departments', methods=['GET', 'POST'])
@login_required
def manage_departments():
    hospital = current_user.hospitals[0]

    if request.method == 'POST':
        department_name = request.form.get('department_name')
        image_path = None

        # Handle department image upload
        if 'department_image' in request.files:
            file = request.files['department_image']
            if file and allowed_file(file.filename):  # Ensure the allowed_file function is defined
                filename = secure_filename(file.filename)
                filepath = os.path.join(current_app.config['UPLOAD_LOCATION'], filename)
                file.save(filepath)
                image_path = os.path.join('images/', filename)

        # Create and add department to the database
        department = Department(name=department_name, image=image_path, hospital_id=hospital.id)
        db.session.add(department)
        db.session.commit()
        flash('Department added successfully!', 'success')
        
        # Redirect to prevent form resubmission on refresh
        return redirect(url_for('hospital_bp.manage_departments'))

    # Retrieve all departments for the hospital
    departments = Department.query.filter_by(hospital_id=hospital.id).all()
    return render_template('HOSPITAL/manage_departments.html', departments=departments, hospital=hospital)

@hospital_bp.route('/delete_department/<int:department_id>', methods=['POST'])
@login_required
def delete_department(department_id):
    department = Department.query.get_or_404(department_id)
    hospital = current_user.hospitals[0]

    # Ensure the department belongs to the current user's hospital
    if department.hospital_id != hospital.id:
        return jsonify(success=False, message="Unauthorized action."), 403

    # Check if there are associated doctors
    associated_doctors = department.doctors
    if associated_doctors:
        return jsonify(success=False, message="This department has registered doctors."), 400

    # Proceed to delete the department if no associated doctors
    try:
        # Delete the department image if it exists
        if department.image:
            image_path = os.path.join(current_app.static_folder, department.image)
            if os.path.exists(image_path):
                os.remove(image_path)

        db.session.delete(department)
        db.session.commit()

        return jsonify(success=True, message="Department deleted successfully.")
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message="An error occurred during deletion. Please try again."), 500


@hospital_bp.route('/delete_department_confirm/<int:department_id>', methods=['POST'])
@login_required
def delete_department_confirm(department_id):
    department = Department.query.get_or_404(department_id)
    hospital = current_user.hospitals[0]

    # Ensure the department belongs to the current user's hospital
    if department.hospital_id != hospital.id:
        return jsonify(success=False, message="Unauthorized action."), 403

    try:
        # Delete associated doctors
        for doctor in department.doctors:
            db.session.delete(doctor)

        # Delete the department image if it exists
        if department.image:
            image_path = os.path.join(current_app.static_folder, department.image)
            if os.path.exists(image_path):
                os.remove(image_path)

        db.session.delete(department)
        db.session.commit()

        return jsonify(success=True, message="Department and associated doctors deleted successfully.")
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message="An error occurred during deletion. Please try again."), 500

@hospital_bp.route('/manage_doctors', methods=['GET', 'POST'])
@login_required
def manage_doctors():
    hospital = current_user.hospitals[0]

    if request.method == 'POST':
        name = request.form.get('name')
        expertise = request.form.get('expertise')
        chamber_timings = request.form.get('chamber_timings')
        availability_days = request.form.get('availability_days')
        department_id = request.form.get('department_id')

        doctor = Doctor(name=name, expertise=expertise, chamber_timings=chamber_timings,
                        availability_days=availability_days, department_id=department_id,
                        hospital_id=hospital.id)
        db.session.add(doctor)
        db.session.commit()
        flash('Doctor registered successfully', 'success')

    departments = Department.query.filter_by(hospital_id=hospital.id).all()
    doctors = Doctor.query.filter_by(hospital_id=hospital.id).all()
    return render_template('HOSPITAL/manage_doctors.html', doctors=doctors, departments=departments, hospital=hospital)

@hospital_bp.route('/delete_doctor/<int:doctor_id>', methods=['POST'])
@login_required
def delete_doctor(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    if doctor:
        db.session.delete(doctor)
        db.session.commit()
        flash('Doctor deleted successfully', 'success')
    return redirect(url_for('hospital_bp.manage_doctors'))


@hospital_bp.route('/get_doctors/<int:department_id>', methods=['GET'])
@login_required
def get_doctors(department_id):
    # Fetch all doctors in the selected department
    doctors = Doctor.query.filter_by(department_id=department_id).all()
    
    doctor_list = [{'id': doctor.id, 'name': doctor.name} for doctor in doctors]
    
    return jsonify({'doctors': doctor_list})

@hospital_bp.route('/get_time_slots/<int:doctor_id>', methods=['GET'])
@login_required
def get_time_slots(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    time_slots = doctor.chamber_timings.split(',')  # Assuming chamber_timings is stored as a comma-separated string
    
    return jsonify({'time_slots': time_slots})




@hospital_bp.route('/verify_appointment_code/<int:appointment_id>', methods=['POST'])
@login_required
def verify_appointment_code(appointment_id):
    data = request.json
    appointment_code = data.get('appointment_code')

    # Fetch the appointment
    appointment = OPDAppointment.query.get_or_404(appointment_id)

    # Verify the appointment code
    if appointment.appointment_code == appointment_code:
        return jsonify(success=True)
    else:
        return jsonify(success=False)


@hospital_bp.route('/complete_opd_check_in/<int:appointment_id>', methods=['POST'])
@login_required
def complete_opd_check_in(appointment_id):
    data = request.json
    appointment = OPDAppointment.query.get_or_404(appointment_id)

    # Update the appointment status
    appointment.status = 'CheckedIn'
    if data.get('age'):
        appointment.user.age = data.get('age')
    
    # Update emergency status if provided
    appointment.is_emergency = bool(data.get('is_emergency'))  # Ensure it's saved as a boolean
    
    db.session.commit()

    # Send a notification email to the patient
    msg = Message('OPD Appointment Check-In Confirmation', recipients=[appointment.user.email])
    msg.body = f"""
    Dear {appointment.user.name},

    You have successfully checked in for your OPD appointment with Dr. {appointment.doctor.name} on {appointment.appointment_date}.
    You are in the queue. We will notify you with the current queue status.

    Best regards,
    Hospital Management System
    """
    mail.send(msg)

    return jsonify(success=True)





@hospital_bp.route('/on_spot_registration', methods=['POST'])
@login_required
def on_spot_registration():
    name = request.form.get('name')
    email = request.form.get('email')
    age = request.form.get('age')
    is_emergency = request.form.get('is_emergency') == 'true'

    selected_date = request.args.get('date')
    doctor_id = request.args.get('doctor_id')
    time_slot = request.args.get('time_slot')
    hospital = current_user.hospitals[0]

    if not doctor_id or not time_slot:
        return jsonify(success=False, message='Doctor and Time Slot must be selected for registration.')

    if age is not None and age.isdigit():
        age = int(age)
    else:
        return jsonify(success=False, message='Invalid age entered.')

    temp_user = User(
        name=name,
        email=email,
        password='',
        role='patient',
        age=age
    )
    db.session.add(temp_user)
    db.session.commit()

    total_patients_in_queue = OPDAppointment.query.filter_by(
        hospital_id=hospital.id,
        doctor_id=doctor_id,
        appointment_date=selected_date,
        time_slot=time_slot,
        status='CheckedIn'
    ).count()

    max_patients = MaxPatient.query.filter_by(doctor_id=doctor_id, time_slot=time_slot).first()

    if max_patients and total_patients_in_queue < max_patients.max_patients:
        patient = OPDAppointment(
            user_id=temp_user.id,
            doctor_id=doctor_id,
            appointment_date=datetime.today(),
            time_slot=time_slot,
            hospital_id=hospital.id,
            is_emergency=is_emergency,
            status='CheckedIn'
        )
        db.session.add(patient)
        db.session.commit()
        return jsonify(success=True, message='Patient successfully registered.')
    else:
        return jsonify(success=False, message='Doctor is fully booked for this time slot.')


@hospital_bp.route('/set_max_patients', methods=['POST'])
@login_required
def set_max_patients():
    max_patients = request.form.get('max_patients')

    if max_patients is not None and max_patients.isdigit():
        max_patients = int(max_patients)
        session['max_patients'] = max_patients
        return jsonify(success=True)
    else:
        return jsonify(success=False), 400



@hospital_bp.route('/register_ambulance', methods=['GET', 'POST'])
@login_required
def register_ambulance():
    hospital = current_user.hospitals[0]  # Assuming the hospital linked to the current user

    if request.method == 'POST':
        driver_name = request.form.get('driver_name')
        driver_phone = request.form.get('driver_phone')
        driver_email = request.form.get('driver_email')
        vehicle_number = request.form.get('vehicle_number')

        # Automatically get hospital's location (latitude, longitude)
        location_lat = hospital.latitude
        location_lng = hospital.longitude

        # Add new ambulance to the database
        new_ambulance = Ambulance(
            hospital_id=hospital.id,
            driver_name=driver_name,
            driver_phone=driver_phone,
            driver_email=driver_email,
            vehicle_number=vehicle_number,
            location_lat=location_lat,
            location_lng=location_lng,
            status='available'  # Default status
        )
        db.session.add(new_ambulance)
        db.session.commit()

        flash('Ambulance registered successfully!', 'success')
        return redirect(url_for('hospital_bp.register_ambulance'))

    # Fetch all ambulances for this hospital
    ambulances = Ambulance.query.filter_by(hospital_id=hospital.id).all()
    
    return render_template('HOSPITAL/register_ambulance.html', ambulances=ambulances, hospital=hospital)

# Route to update ambulance status
@hospital_bp.route('/update_ambulance_status/<int:ambulance_id>', methods=['POST'])
@login_required
def update_ambulance_status(ambulance_id):
    data = request.json
    new_status = data.get('status')
    ambulance = Ambulance.query.get_or_404(ambulance_id)

    if ambulance.hospital_id != current_user.hospitals[0].id:
        return jsonify({'success': False, 'message': 'Unauthorized access'}), 403

    ambulance.status = new_status
    db.session.commit()

    return jsonify({'success': True, 'message': 'Status updated successfully'})

# Route to delete ambulance
@hospital_bp.route('/delete_ambulance/<int:ambulance_id>', methods=['GET'])
@login_required
def delete_ambulance(ambulance_id):
    ambulance = Ambulance.query.get_or_404(ambulance_id)

    if ambulance.hospital_id != current_user.hospitals[0].id:
        flash('You are not authorized to delete this ambulance.', 'danger')
        return redirect(url_for('hospital_bp.register_ambulance'))

    db.session.delete(ambulance)
    db.session.commit()

    flash('Ambulance deleted successfully!', 'success')
    return redirect(url_for('hospital_bp.register_ambulance'))



@hospital_bp.route('/medicine_inventory', methods=['GET', 'POST'])
@login_required
def medicine_inventory():
    hospital = current_user.hospitals[0]

    if request.method == 'POST':
        data = request.form
        new_medicine = Medicine(
            name=data['name'],
            description=data.get('description'),
            threshold=int(data['threshold']),
            hospital_id=hospital.id
        )
        db.session.add(new_medicine)
        db.session.commit()
        flash("Medicine type added successfully", "success")
        return redirect(url_for('hospital_bp.medicine_inventory'))

    medicines = Medicine.query.filter_by(hospital_id=hospital.id).all()
    return render_template('HOSPITAL/medicine_inventory.html', medicines=medicines, hospital=hospital)

@hospital_bp.route('/medicine/<int:medicine_id>', methods=['GET', 'POST'])
@login_required
def medicine_detail(medicine_id):
    hospital = current_user.hospitals[0]  # Fetch the current user's hospital

    # Fetch the specified medicine for the current hospital
    medicine = Medicine.query.filter_by(id=medicine_id, hospital_id=hospital.id).first_or_404()

    if request.method == 'POST':
        # Process form submission to add a new batch
        data = request.form
        new_batch = MedicineBatch(
            medicine_id=medicine.id,
            supplier=data.get('supplier'),
            expiration_date=datetime.strptime(data.get('expiration_date'), '%Y-%m-%d'),
            stock_added=int(data.get('stock_added')),
            stock_sold=0,
            note=data.get('note')
        )
        db.session.add(new_batch)
        db.session.commit()
        
        # Create a log entry for the new batch addition
        medicine_log = MedicineLog(
            batch_id=new_batch.id,
            change_amount=new_batch.stock_added,
            change_type='added',
            note=f"Initial stock added for {medicine.name} batch"
        )
        db.session.add(medicine_log)
        db.session.commit()

        flash("New batch added successfully", "success")
        return redirect(url_for('hospital_bp.medicine_detail', medicine_id=medicine.id))

    # Query logs related to all batches of this medicine
    logs = (
        MedicineLog.query.join(MedicineBatch)
        .filter(MedicineBatch.medicine_id == medicine.id)
        .order_by(MedicineLog.timestamp.desc())
        .all()
    )

    # Pass the `hospital` object to the template context
    return render_template('HOSPITAL/medicine_detail.html', medicine=medicine, logs=logs, hospital=hospital)

@hospital_bp.route('/update_medicine_stock/<int:medicine_id>', methods=['POST'])
@login_required
def update_medicine_stock(medicine_id):
    hospital = current_user.hospitals[0]
    
    # Fetch the specified medicine
    medicine = Medicine.query.filter_by(id=medicine_id, hospital_id=hospital.id).first_or_404()
    
    # Get the change amount from the form and validate it's a positive number for sold units
    change_amount = abs(int(request.form['change_amount']))
    note = request.form.get('note', 'Stock update')
    
    # Process the stock deduction (sold units) starting from the oldest batches
    remaining_to_deduct = change_amount
    for batch in sorted(medicine.batches, key=lambda b: b.created_at):
        if remaining_to_deduct <= 0:
            break
        
        available_stock = batch.stock_added - batch.stock_sold
        if available_stock > 0:
            # Deduct from the available stock in this batch
            deduction = min(remaining_to_deduct, available_stock)
            batch.stock_sold += deduction
            remaining_to_deduct -= deduction

            # Log the sale for this batch
            medicine_log = MedicineLog(
                batch_id=batch.id,
                change_amount=-deduction,
                change_type='sold',
                note=note
            )
            db.session.add(medicine_log)
    
    # Commit the updates to the database
    db.session.commit()
    
    # Flash message if below threshold after update
    if medicine.total_stock < medicine.threshold:
        flash(f"Warning: Stock for {medicine.name} is below threshold!", "warning")
    
    return redirect(url_for('hospital_bp.medicine_detail', medicine_id=medicine.id))