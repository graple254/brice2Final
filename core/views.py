from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, authenticate, login
from django.contrib import messages

from .utils import redirect_user_by_role
from .decorators import role_required
from .models import *
from django.http import HttpResponse
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.utils import timezone
from .email import *

# Create your views here.

def index(request):
    context = {}
    return render(request, 'files/booking_flow_templates/index.html', context)

def service_selection(request):
    """Step 1: Show all available services"""
    services = Service.objects.order_by('name') 
    
    # Track in analytics if you want
    # visitor_tracking(request, 'service_selection_viewed')
    
    return render(request, 'files/booking_flow_templates/service_selection.html', {
        'services': services
    })

def book_appointment(request, service_id):
    """Step 2: Show first available slot for selected service"""
    service = get_object_or_404(Service, id=service_id)
    
    # Get first available slot (next 30 days)
    today = timezone.now().date()
    future_date = today + timedelta(days=30)
    
    first_available = DentistSchedule.objects.filter(
        date__gte=today,
        date__lte=future_date,
        is_available=True
    ).order_by('date', 'start_time').first()
    
    # Track step
    # visitor_tracking(request, 'first_availability_viewed', service_id=service_id)
    
    return render(request, 'files/booking_flow_templates/book_appointment.html', {
        'service': service,
        'first_available': first_available,
    })

def time_slots(request, service_id):
    """Step 3: Show alternative time options"""
    service = get_object_or_404(Service, id=service_id)
    
    # Get available slots for next 14 days
    today = timezone.now().date()
    end_date = today + timedelta(days=14)
    
    available_slots = DentistSchedule.objects.filter(
        date__gte=today,
        date__lte=end_date,
        is_available=True
    ).order_by('date', 'start_time')
    
    # Group by date for display
    slots_by_date = {}
    for slot in available_slots:
        date_str = slot.date.strftime('%Y-%m-%d')
        if date_str not in slots_by_date:
            slots_by_date[date_str] = {
                'date': slot.date,
                'day_name': slot.date.strftime('%A'),
                'slots': []
            }
        slots_by_date[date_str]['slots'].append(slot)
    
    # Track step
    # visitor_tracking(request, 'time_options_viewed', service_id=service_id)
    
    return render(request, 'files/booking_flow_templates/time_slots.html', {
        'service': service,
        'slots_by_date': slots_by_date,
        'today': today,
    })

def confirm_booking(request, schedule_id, service_id):
    """Step 4: Patient information form"""
    schedule = get_object_or_404(DentistSchedule, id=schedule_id, is_available=True)
    service = get_object_or_404(Service, id=service_id)
    
    if request.method == 'POST':
        # Create appointment
        appointment = Appointment.objects.create(
            service=service,
            schedule_slot=schedule,
            first_name=request.POST.get('first_name'),
            last_name=request.POST.get('last_name'),
            email=request.POST.get('email'),
            date_of_birth=request.POST.get('date_of_birth'),
            mobile_number=request.POST.get('mobile_number'),
            gender=request.POST.get('gender'),
            zip_code=request.POST.get('zip_code'),
            status='scheduled'
        )
        
        # Track completion
        # visitor_tracking(request, 'booking_completed', appointment_id=appointment.id)
           # Send confirmation email
        send_appointment_confirmation(appointment)
        
        # Redirect to confirmation page
        return redirect('appointment_confirmation', appointment_id=appointment.appointment_id)
    
    return render(request, 'files/booking_flow_templates/confirm_booking.html', {
        'service': service,
        'schedule': schedule,
    })

def appointment_confirmation(request, appointment_id):
    """Step 5: Show confirmation with appointment details"""
    appointment = get_object_or_404(Appointment, appointment_id=appointment_id)
    
    return render(request, 'files/booking_flow_templates/appointment_confirmation.html', {
        'appointment': appointment
    })

def find_appointment(request):
    """Look up appointment by phone or email"""
    appointment = None
    search_performed = False
    
    if request.method == 'POST':
        search_term = request.POST.get('search_term', '').strip()
        search_performed = True
        
        if search_term:
            # Search by email or phone
            appointment = Appointment.objects.filter(
                Q(email__iexact=search_term) | 
                Q(mobile_number__iexact=search_term)
            ).first()
    
    return render(request, 'files/booking_flow_templates/find_appointment.html', {
        'appointment': appointment,
        'search_performed': search_performed,
    })


# Authentication Views

# ---------------------------
# LOGIN
# ---------------------------


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, "Invalid login credentials.")
            return render(request, "files/auth_templates/login.html")

        if not user.is_active:
            messages.error(request, "Account inactive.")
            return render(request, "files/auth_templates/login.html")

        login(request, user)
        return redirect(redirect_user_by_role(user))

    return render(request, "files/auth_templates/login.html")



@login_required
def logout_view(request):
    """
    Handle user logout.
    """
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("login")

#End of Authentication Views


# ========== DASHBOARD VIEWS ==========
#======================STAFF VIEWS========================
# These views allow staff members to manage schedules and appointments. They are protected by the @role_required decorator to ensure only users with the 'staff' role can access them.

@login_required
@role_required(['staff'])
def staff_dashboard(request):
    today = timezone.now().date()

    today_appointments = Appointment.objects.filter(
        schedule_slot__date=today
    ).select_related("schedule_slot", "service") \
     .order_by("schedule_slot__start_time")

    upcoming_qs = Appointment.objects.filter(
        schedule_slot__date__gt=today
    ).select_related("schedule_slot", "service") \
     .order_by("schedule_slot__date", "schedule_slot__start_time")

    paginator = Paginator(upcoming_qs, 10)  # 10 per page
    page_number = request.GET.get("page")
    upcoming_appointments = paginator.get_page(page_number)

    return render(
        request,
        "files/staff_templates/staff_dashboard.html",
        {
            "today_appointments": today_appointments,
            "upcoming_appointments": upcoming_appointments,
            "today": today,
        },
    )

@login_required
@role_required(['staff'])
def staff_create_schedules(request):
    """Staff dashboard - manage dentists and bulk create schedules"""

    dentists = User.objects.filter(role=User.DENTIST).order_by("username")

    schedules_qs = DentistSchedule.objects.select_related("dentist") \
        .order_by("created_at")

    paginator = Paginator(schedules_qs, 10)
    page_number = request.GET.get("page")
    recent_schedules = paginator.get_page(page_number)

    if request.method == "POST":
        action = request.POST.get("action")

        # =================================
        # ADD NEW DENTIST
        # =================================
        if action == "add_dentist":
            username = request.POST.get("username")
            email = request.POST.get("email")
            specialty = request.POST.get("specialty")
            password = request.POST.get("password")

            if not username or not password:
                messages.error(request, "Username and password required.")
                return redirect("staff_create_schedules")

            if User.objects.filter(username=username).exists():
                messages.error(request, "Dentist already exists.")
                return redirect("staff_create_schedules")

            User.objects.create_user(
                username=username,
                email=email,
                password=password,
                role=User.DENTIST,
                specialty=specialty
            )

            messages.success(request, "Dentist added successfully.")
            return redirect("staff_create_schedules")

        # =================================
        # DELETE DENTIST
        # =================================
        if action == "delete_dentist":
            dentist_id = request.POST.get("dentist_id")

            dentist = get_object_or_404(User, id=dentist_id, role=User.DENTIST)
            dentist.delete()

            messages.success(request, "Dentist removed successfully.")
            return redirect("staff_create_schedules")

        # =================================
        # CREATE SCHEDULES
        # =================================
        if action == "create_schedule":

            dentist_id = request.POST.get("dentist_id")
            start_date_str = request.POST.get("start_date")
            end_date_str = request.POST.get("end_date")
            start_time_str = request.POST.get("start_time")
            end_time_str = request.POST.get("end_time")

            dentist = get_object_or_404(User, id=dentist_id, role=User.DENTIST)

            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                start_time = datetime.strptime(start_time_str, "%H:%M").time()
                end_time = datetime.strptime(end_time_str, "%H:%M").time()
            except ValueError:
                messages.error(request, "Invalid date or time format.")
                return redirect("staff_create_schedules")

            if start_date > end_date:
                messages.error(request, "Start date cannot be after end date.")
                return redirect("staff_create_schedules")

            created, skipped = 0, 0
            current_date = start_date

            while current_date <= end_date:

                if DentistSchedule.objects.filter(
                    dentist=dentist,
                    date=current_date,
                    start_time=start_time
                ).exists():
                    skipped += 1
                else:
                    DentistSchedule.objects.create(
                        dentist=dentist,
                        date=current_date,
                        start_time=start_time,
                        end_time=end_time,
                        is_available=True
                    )
                    created += 1

                current_date += timedelta(days=1)

            messages.success(
                request,
                f"{created} schedules created. {skipped} skipped due to conflicts."
            )

            return redirect("staff_create_schedules")

    return render(
        request,
        "files/staff_templates/staff_create_schedules.html",
        {
            "dentists": dentists,
            "recent_schedules": recent_schedules,
            "today": timezone.now().date(),
        },
    )

@login_required
@role_required(['staff'])
def view_all_appointments(request):
    """Staff dashboard - view all appointments with filtering and search"""

    appointments = Appointment.objects.select_related(
        "schedule_slot",
        "schedule_slot__dentist",
        "service",
    ).order_by("-schedule_slot__date", "-schedule_slot__start_time")

    total_appointments = appointments.count()

    status_counts = {
        "scheduled": appointments.filter(status="scheduled").count(),
        "confirmed": appointments.filter(status="confirmed").count(),
        "completed": appointments.filter(status="completed").count(),
        "cancelled": appointments.filter(status="cancelled").count(),
        "no_show": appointments.filter(status="no_show").count(),
    }

    unique_dentists = appointments.values(
        "schedule_slot__dentist_id"
    ).distinct().count()

    status_filter = request.GET.get("status")
    if status_filter and status_filter != "all":
        appointments = appointments.filter(status=status_filter)

    search_query = request.GET.get("search")
    if search_query:
        appointments = appointments.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(mobile_number__icontains=search_query) |
            Q(appointment_id__icontains=search_query) |
            Q(schedule_slot__dentist__first_name__icontains=search_query) |
            Q(schedule_slot__dentist__last_name__icontains=search_query)
        )

    paginator = Paginator(appointments, 15)
    page_number = request.GET.get("page")
    appointments_page = paginator.get_page(page_number)

    context = {
        "appointments": appointments_page,
        "total_appointments": total_appointments,
        "status_counts": status_counts,
        "unique_dentists": unique_dentists,
        "status_filter": status_filter or "all",
        "search_query": search_query or "",
    }

    return render(
        request,
        "files/staff_templates/view_all_appointments.html",
        context,
    )



@login_required
@role_required(['staff'])
@require_POST
def update_appointment_status(request):
    appointment_id = request.POST.get("appointment_id")
    new_status = request.POST.get("status")

    if new_status not in dict(Appointment.STATUS_CHOICES):
        return JsonResponse({"error": "Invalid status"}, status=400)

    appointment = get_object_or_404(Appointment, appointment_id=appointment_id)

    appointment.status = new_status
    appointment.save(update_fields=["status", "updated_at"])

    return JsonResponse({
        "success": True,
        "appointment_id": appointment.appointment_id,
        "new_status": appointment.get_status_display(),
    })


#===============END OF STAFF VIEWS========================


# ---------- Dentist Views ----------
# These views allow dentists to see their schedules and appointments. They are protected by the @role_required decorator to ensure only users with the 'dentist' role can access them.
# The dentist dashboard shows both the schedule and appointments, while the other two views allow dentists to see just their schedule or just their appointments.


@login_required
@role_required(['dentist'])
def dentist_dashboard(request):
    """Dentist dashboard - view schedule"""
    if not request.user.is_dentist():
        return redirect('index')
    
    # Dentist's schedule
    today = timezone.now().date()
    schedule = DentistSchedule.objects.filter(
        dentist=request.user,
        date__gte=today
    ).order_by('date', 'start_time')
    
    # Dentist's appointments
    appointments = Appointment.objects.filter(
        schedule_slot__dentist=request.user,
        schedule_slot__date__gte=today
    ).order_by('schedule_slot__date', 'schedule_slot__start_time')
    
    return render(request, 'files/dentist_templates/dentist_dashboard.html', {
        'schedule': schedule,
        'appointments': appointments,
        'today': today,
    })



@login_required
@role_required(['dentist'])
def dentist_view_schedule(request):
    """Dentist dashboard - view schedule"""
    if not request.user.is_dentist():
        return redirect('index')
    
    # Dentist's schedule
    today = timezone.now().date()
    schedule = DentistSchedule.objects.filter(
        dentist=request.user,
        date__gte=today
    ).order_by('date', 'start_time')
    
    return render(request, 'files/dentist_templates/dentist_schedule.html', {
        'schedule': schedule,
        'today': today,
    }) 



@login_required
@role_required(['dentist'])
def dentist_view_appointments(request):
    """Dentist dashboard - view appointments"""
    if not request.user.is_dentist():
        return redirect('index')
    
    # Dentist's appointments
    today = timezone.now().date()
    appointments = Appointment.objects.filter(
        schedule_slot__dentist=request.user,
        schedule_slot__date__gte=today
    ).order_by('schedule_slot__date', 'schedule_slot__start_time')
    
    return render(request, 'files/dentist_templates/dentist_appointments.html', {
        'appointments': appointments,
        'today': today,
    })
