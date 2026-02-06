import uuid
from datetime import datetime

from django.db import models, transaction
from django.contrib.auth.models import AbstractUser


# =========================================================
# Utilities
# =========================================================

def generate_appointment_id():
    return uuid.uuid4().hex[:12].upper()


# ============================================
# CORE USER MODEL (extends AbstractUser)
# ============================================
class User(AbstractUser):
    """
    Custom User model with role-based permissions.
    """
    
    STAFF = "staff"
    DENTIST = "dentist"
    PATIENT = "patient"
    
    ROLE_CHOICES = [
        (STAFF, "Staff Member"),
        (DENTIST, "Dentist"),
        (PATIENT, "Patient"),
    ]
    
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        db_index=True,
        help_text="Determines dashboard access and permissions"
    )
    
    phone_number = models.CharField(
        max_length=15, 
        blank=True, 
        null=True,
        help_text="Primary contact number"
    )
    
    specialty = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Dental specialty (for dentists only)"
    )
    
    class Meta:
        ordering = ['last_name', 'first_name']
    
    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"
    
    def is_staff_member(self):
        return self.role == self.STAFF
    
    def is_dentist(self):
        return self.role == self.DENTIST
    
    def save(self, *args, **kwargs):
        if self.email and not self.username:
            self.username = self.email
        super().save(*args, **kwargs)


# =========================================================
# Service
# =========================================================

class Service(models.Model):
    """
    Dental services offered
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# =========================================================
# Visitor (pre-booking analytics)
# =========================================================

class Visitor(models.Model):
    """
    Anonymous visitor tracking before booking
    """
    session_id = models.CharField(max_length=100, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.session_id


# =========================================================
# Dentist Schedule
# =========================================================

class DentistSchedule(models.Model):
    """
    Available time slots for dentists
    """
    dentist = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="schedules"
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_available = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("dentist", "date", "start_time")
        ordering = ["date", "start_time"]

    def __str__(self):
        return f"{self.dentist.username} | {self.date} {self.start_time}"


# =========================================================
# Appointment
# =========================================================

class Appointment(models.Model):
    """
    Core appointment booking model
    """

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("confirmed", "Confirmed"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("no_show", "No Show"),
    ]

    # Booking info
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="appointments"
    )

    schedule_slot = models.OneToOneField(
        DentistSchedule,
        on_delete=models.PROTECT,
        related_name="appointment"
    )

    # Patient info
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(db_index=True)
    date_of_birth = models.DateField()
    mobile_number = models.CharField(max_length=15, db_index=True)
    gender = models.CharField(max_length=20)
    zip_code = models.CharField(max_length=10)

    # Internal state
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="scheduled",
        db_index=True
    )

    notes = models.TextField(blank=True)

    # Public reference
    appointment_id = models.CharField(
        max_length=12,
        unique=True,
        default=generate_appointment_id,
        editable=False
    )

    # Staff audit
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_appointments"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["schedule_slot__date", "schedule_slot__start_time"]
        indexes = [
            models.Index(fields=["email", "mobile_number"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.appointment_id} | {self.patient_name}"

    # -------------------------
    # Computed properties
    # -------------------------

    @property
    def patient_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def appointment_datetime(self):
        return datetime.combine(
            self.schedule_slot.date,
            self.schedule_slot.start_time
        )

    @property
    def dentist(self):
        return self.schedule_slot.dentist

    # -------------------------
    # Persistence logic
    # -------------------------

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.pk is None:
                self.schedule_slot.is_available = False
                self.schedule_slot.save(update_fields=["is_available"])
            super().save(*args, **kwargs)

    def cancel(self):
        with transaction.atomic():
            self.status = "cancelled"
            self.schedule_slot.is_available = True
            self.schedule_slot.save(update_fields=["is_available"])
            self.save(update_fields=["status"])


# =========================================================
# Booking Analytics
# =========================================================

class BookingAnalytics(models.Model):
    """
    Funnel and conversion analytics per appointment
    """
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        related_name="analytics"
    )

    source = models.CharField(max_length=100)
    device_type = models.CharField(max_length=50)
    conversion_time_seconds = models.PositiveIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Analytics | {self.appointment.appointment_id}"
