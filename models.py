from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy.ext.declarative import declarative_base
from geopy.geocoders import Nominatim
db = SQLAlchemy()
Base = declarative_base()

class MaxPatient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    time_slot = db.Column(db.String(50), nullable=False)
    max_patients = db.Column(db.Integer, nullable=False, default=30)
    doctor = db.relationship('Doctor', back_populates='max_patients')





class Query(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String(20), nullable=False)
    Email = db.Column(db.String(25), nullable=False)
    Message = db.Column(db.String(120), nullable=False)
    Phone_number = db.Column(db.String(12), nullable=False)

class Posts(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(80), nullable=False)
    id = db.Column(db.String(21), nullable=False)
    content = db.Column(db.String(120), nullable=False)
    date = db.Column(db.String(12), nullable=True)
    img_file = db.Column(db.String(60), nullable=True)

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    company = db.Column(db.String(150))
    profile_image = db.Column(db.String(100), default='images/default_profile.png')
    job = db.Column(db.String(150))
    country = db.Column(db.String(150))
    address = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    age = db.Column(db.Integer)
    twitter = db.Column(db.String(255))
    facebook = db.Column(db.String(255))
    instagram = db.Column(db.String(255))
    linkedin = db.Column(db.String(255))
    role = db.Column(db.String(50), nullable=False)  # Could be 'patient', 'hospital_admin', or 'ambulance_driver'
    location = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    prefers_ambulance = db.Column(db.Boolean, default=False)  # Optional user preference
    # Relationships
    notifications = db.relationship('Notification', back_populates='user', lazy=True)
    posts = db.relationship('Post', backref='author', lazy=True)
    cart = db.relationship('Cart', back_populates='user', uselist=False)
    comments = db.relationship('Comment', backref='comment_author', lazy=True)
    likes = db.relationship('Like', backref='like_author', lazy=True)
    bookings = db.relationship('Booking', backref='booked_by', lazy=True)  # Renamed backref
    ratings = db.relationship('Rating', backref='user', lazy=True)
    hospitals = db.relationship('Hospital', back_populates='admin', lazy=True)
    opd_appointments = db.relationship('OPDAppointment', back_populates='user', lazy=True)
      # Add this line to complete the relationship
    lab_test_bookings = db.relationship('LabTestBooking', back_populates='user')
      # Relationship to the MedicalData model
    medical_data = db.relationship('MedicalData', back_populates='user', lazy=True)
    

class Userfg(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=True)
    oauth_provider = db.Column(db.String(50), nullable=True)
    oauth_id = db.Column(db.String(200), unique=True, nullable=True)

class Hospital(db.Model):
    __tablename__ = 'hospital'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(255))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    total_beds = db.Column(db.Integer)
    icu_beds = db.Column(db.Integer)
    opd_beds = db.Column(db.Integer)
    general_beds = db.Column(db.Integer)
    vacant_icu_beds = db.Column(db.Integer)
    vacant_opd_beds = db.Column(db.Integer)
    vacant_general_beds = db.Column(db.Integer)
    contact_info = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    admin = db.relationship('User', back_populates='hospitals', lazy=True)
    wards = db.relationship('Ward', backref='hospital', lazy=True)
    bookings = db.relationship('Booking', backref='booked_hospital', lazy=True)
    notifications = db.relationship('Notification', back_populates='hospital', lazy=True)
    departments = db.relationship('Department', back_populates='hospital', lazy=True)
    diagnostic_departments = db.relationship('DiagnosticDepartment', back_populates='hospital', lazy=True)  # New relationship for diagnostic departments
    ambulances = db.relationship('Ambulance', back_populates='hospital')
    medicines = db.relationship('Medicine', back_populates='hospital', lazy=True)
    



class Ward(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    managed_by = db.Column(db.String(100))
    head_wardboy_name = db.Column(db.String(100))
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)  # Link to Hospital
    
    # Relationships
    beds = db.relationship('Bed', backref='ward', lazy=True)
    staff = db.relationship('HealthStaff', back_populates='ward', lazy=True)

class HealthStaff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50))  # Nurse, Doctor, etc.
    status = db.Column(db.String(50), default='active')  # active, on leave
    ward_id = db.Column(db.Integer, db.ForeignKey('ward.id'))  # Link to Ward
    
    # Relationships
    ward = db.relationship('Ward', back_populates='staff')
    timeline = db.relationship('StaffStatusChange', back_populates='staff', lazy=True)

class StaffStatusChange(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('health_staff.id'), nullable=False)
    old_status = db.Column(db.String(50), nullable=False)
    new_status = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    staff = db.relationship('HealthStaff', back_populates='timeline')

class Bed(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ward_id = db.Column(db.Integer, db.ForeignKey('ward.id'), nullable=False)  # Link to Ward
    bed_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='ready')
    last_status_change = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    status_changes = db.relationship('BedStatusChange', back_populates='bed', lazy=True)

class BedStatusChange(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bed_id = db.Column(db.Integer, db.ForeignKey('bed.id'), nullable=False)
    old_status = db.Column(db.String(50), nullable=False)
    new_status = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    bed = db.relationship('Bed', back_populates='status_changes')



class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)
    ambulance_id = db.Column(db.Integer, db.ForeignKey('ambulance.id'), nullable=True)  # Track ambulance
    bed_type = db.Column(db.String(50), nullable=False)  # ICU, OPD, General
    status = db.Column(db.String(20), default='Pending')  # Pending, Confirmed, CheckedIn
    distance = db.Column(db.Float, nullable=False)
    admission_code = db.Column(db.String(4), nullable=False)  # 4-digit admission code
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_bed_number = db.Column(db.String(10))  # Store the assigned bed number
    ambulance_id = db.Column(db.Integer, db.ForeignKey('ambulance.id'), nullable=True)

    # Relationships
    user = db.relationship('User', backref='booked_by', lazy=True)
    hospital = db.relationship('Hospital', backref='assigned_hospital', lazy=True)
    ambulance = db.relationship('Ambulance', backref='bookings', lazy=True)  # Add relationship to ambulance
    
    




class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=True)
    rating = db.Column(db.Integer, nullable=False)
    feedback = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    price = db.Column(db.Float, nullable=False)
    discount_price = db.Column(db.Float, nullable=True)
    image_file = db.Column(db.String(100), nullable=False)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    cart_items = db.relationship('CartItem', back_populates='item')

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', back_populates='cart')
    items = db.relationship('CartItem', back_populates='cart', lazy=True)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('cart.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    cart = db.relationship('Cart', back_populates='items')
    item = db.relationship('Item', back_populates='cart_items')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    mobile = db.Column(db.String(15), nullable=False)
    total_amount = db.Column(db.Integer, nullable=False)
    payment_status = db.Column(db.String(50), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    likes = db.relationship('Like', backref='post', lazy=True)
    comments = db.relationship('Comment', backref='post', lazy=True)
    media = db.relationship('Media', backref='post', lazy=True)

    def liked_by_user(self, user):
        return Like.query.filter_by(post_id=self.id, user_id=user.id).first() is not None

class Media(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(150), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)  # 'image' or 'video'
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'))
    message = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

    # Relationships
    user = db.relationship('User', back_populates='notifications')
    hospital = db.relationship('Hospital', back_populates='notifications')

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)
    image = db.Column(db.String(100), nullable=True)  # New field for the department image
    # Relationships
    hospital = db.relationship('Hospital', back_populates='departments')
    doctors = db.relationship('Doctor', backref='department', lazy=True)



class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    expertise = db.Column(db.String(100), nullable=False)
    chamber_timings = db.Column(db.String(100), nullable=False)  # e.g., "10:00-12:00"
    availability_days = db.Column(db.String(50), nullable=False)  # e.g., "Mon,Wed,Fri"
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)
    
    # Relationships
    max_patients = db.relationship('MaxPatient', back_populates='doctor', lazy=True)





class OPDAppointment(db.Model):
    __tablename__ = 'opd_appointment'  # Ensure this matches your actual table name
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    time_slot = db.Column(db.String(50), nullable=False)
    appointment_code = db.Column(db.String(4), nullable=False)
    queue_number = db.Column(db.Integer)
    status = db.Column(db.String(20), default='Pending')  # Pending, CheckedIn, Done
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)
    is_emergency = db.Column(db.Boolean, default=False)  # New field for emergency status
    is_on_spot = db.Column(db.Boolean, default=False)  # New field for on-spot registration

    # Relationships
    user = db.relationship('User', back_populates='opd_appointments')
    doctor = db.relationship('Doctor', backref='appointments')
    hospital = db.relationship('Hospital', backref='opd_appointments')



class OPDQueue(db.Model):
    __tablename__ = 'opd_queue'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('opd_appointment.id'))
    onsite_name = db.Column(db.String(50), nullable=True)  # Temporary name for on-site patients
    onsite_email = db.Column(db.String(100), nullable=True)  # Temporary email for onsite patients
    onsite_age = db.Column(db.Integer, nullable=True)        # Temporary age for onsite patients
    queue_number = db.Column(db.Integer, nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    time_slot = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='Pending')  # e.g., Pending, Done
    
    patient = db.relationship('OPDAppointment', backref='opd_queues')


# models.py

class LabTestBooking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    test_category = db.Column(db.String(50), nullable=False)
    test_name = db.Column(db.String(100), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)
    prescription = db.Column(db.String(255), nullable=True)  # Path to the uploaded file
    booking_code = db.Column(db.String(4), nullable=False)
    booking_date = db.Column(db.Date, nullable=False)  # New column to store the booking date
    status = db.Column(db.String(20), default='Pending')  # Pending, Confirmed, Cancelled

    user = db.relationship('User', back_populates='lab_test_bookings')
    hospital = db.relationship('Hospital', backref='lab_test_bookings')

class Queue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)
    test_booking_id = db.Column(db.Integer, db.ForeignKey('lab_test_booking.id'), nullable=False)
    queue_number = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    booking = db.relationship('LabTestBooking', backref='queue')
# models.py

class DiagnosticDepartment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)
    image = db.Column(db.String(100), nullable=True)  # Image for the diagnostic department (optional)
    
      # Relationships
    hospital = db.relationship('Hospital', back_populates='diagnostic_departments')
    tests = db.relationship('DiagnosticTest', back_populates='diagnostic_department', lazy=True)


class DiagnosticTest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('diagnostic_department.id'), nullable=False)

    # Relationship with Diagnostic Department
    diagnostic_department = db.relationship('DiagnosticDepartment', back_populates='tests')



class Ambulance(db.Model):
    __tablename__ = 'ambulance'
    id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)
    driver_name = db.Column(db.String(100), nullable=False)
    driver_phone = db.Column(db.String(15), nullable=False)
    driver_email = db.Column(db.String(150), nullable=False)
    vehicle_number = db.Column(db.String(20), nullable=False)
    location_lat = db.Column(db.Float, nullable=True)
    location_lng = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default='available', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # Relationships
    hospital = db.relationship('Hospital', back_populates='ambulances')
    current_booking = db.relationship('Booking', backref='assigned_ambulance', uselist=False)



class MedicalData(db.Model):
    __tablename__ = 'medical_data'
    
    # Primary key - unique ID for each medical data entry
    id = db.Column(db.Integer, primary_key=True)
    
    # User ID of the person who uploaded the data, foreign key linking to the 'User' model
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # IPFS hash for the prescription file
    prescription_hash = db.Column(db.String(255), nullable=False)
    
    # IPFS hash for the test results file
    test_results_hash = db.Column(db.String(255), nullable=False)
    
    # Transaction hash for the blockchain transaction
    tx_hash = db.Column(db.String(255), nullable=False)
    
    # Timestamp of when the data was uploaded
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to the User model (back-populating the 'medical_data' field)
    user = db.relationship('User', back_populates='medical_data')








class LabTestQueue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lab_test_booking_id = db.Column(db.Integer, db.ForeignKey('lab_test_booking.id'), nullable=False)
    queue_number = db.Column(db.Integer, nullable=False)
    booking_date = db.Column(db.Date, nullable=False)  # Date for queue
    test_name = db.Column(db.String(100), nullable=False)  # Name of the test
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)

    lab_test_booking = db.relationship('LabTestBooking', backref='queue_entries')
    hospital = db.relationship('Hospital', backref='test_queues')





class Medicine(db.Model):
    __tablename__ = 'medicines'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(500), nullable=True)
    threshold = db.Column(db.Integer, nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)

    # Relationships
    batches = db.relationship('MedicineBatch', backref='medicine', lazy=True)
    hospital = db.relationship('Hospital', back_populates='medicines')

    @property
    def total_stock(self):
        """Calculate total stock by summing added stock minus sold stock for all batches."""
        total_added = sum(batch.stock_added for batch in self.batches)
        total_sold = sum(batch.stock_sold for batch in self.batches)
        return total_added - total_sold


class MedicineBatch(db.Model):
    __tablename__ = 'medicine_batches'

    id = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicines.id'), nullable=False)
    supplier = db.Column(db.String(100), nullable=False)
    expiration_date = db.Column(db.Date, nullable=False)
    stock_added = db.Column(db.Integer, nullable=False)
    stock_sold = db.Column(db.Integer, nullable=True, default=0)
    note = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to Medicine Logs, updated to avoid conflict
    logs = db.relationship('MedicineLog', back_populates='batch', lazy=True)


class MedicineLog(db.Model):
    __tablename__ = 'medicine_logs'

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('medicine_batches.id'), nullable=False)
    change_amount = db.Column(db.Integer, nullable=False)
    change_type = db.Column(db.String(20), nullable=False)  # "added" or "sold"
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    note = db.Column(db.String(255), nullable=True)

    # Relationship to Medicine Batch, updated to avoid conflict
    batch = db.relationship('MedicineBatch', back_populates='logs')