from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils import timezone
from datetime import timedelta

from .models import (
    User,
    Visitor,
    Service,
    DentistSchedule,
    Appointment,
    BookingAnalytics,
)

# =====================================================
# User Admin
# =====================================================

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User

    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "is_staff",
        "is_active",
    )

    list_filter = (
        "role",
        "is_staff",
        "is_superuser",
        "is_active",
    )

    search_fields = (
        "username",
        "email",
        "first_name",
        "last_name",
        "phone_number",
    )

    ordering = ("username",)

    # 🔴 THIS IS THE IMPORTANT PART
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal Info", {
            "fields": (
                "first_name",
                "last_name",
                "email",
                "phone_number",
            )
        }),
        ("Role Information", {
            "fields": (
                "role",
                "specialty",
            )
        }),
        ("Permissions", {
            "fields": (
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            )
        }),
        ("Important Dates", {
            "fields": ("last_login", "date_joined")
        }),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "username",
                "email",
                "password1",
                "password2",
                "role",          # ✅ REQUIRED
                "is_staff",
                "is_superuser",
            ),
        }),
    )


# =====================================================
# Visitor Admin
# =====================================================

@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ("ip_address", "session_id", "created_at")
    search_fields = ("ip_address", "session_id")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


# =====================================================
# Service Admin
# =====================================================

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "duration_minutes", "price", "created_at")
    search_fields = ("name", "description")
    ordering = ("name",)
    readonly_fields = ("created_at",)


# =====================================================
# Dentist Schedule Admin
# =====================================================
@admin.register(DentistSchedule)
class DentistScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "dentist",
        "date",
        "time_slot",
        "is_available",
    )

    list_filter = ("dentist", "date", "is_available")
    search_fields = (
        "dentist__username",
        "dentist__first_name",
        "dentist__last_name",
    )

    date_hierarchy = "date"
    ordering = ("date", "start_time")

    actions = ["duplicate_to_next_days"]

    def time_slot(self, obj):
        return f"{obj.start_time.strftime('%I:%M %p')} – {obj.end_time.strftime('%I:%M %p')}"
    time_slot.short_description = "Time Slot"

    # =====================================================
    # Admin Actions
    # =====================================================

    def duplicate_to_next_days(self, request, queryset):
        """
        Duplicate selected schedules across the next N days.
        """
        DAYS_TO_DUPLICATE = 7  # ← change this to 14 / 30 if needed

        created_count = 0
        skipped_count = 0

        for schedule in queryset:
            for day_offset in range(1, DAYS_TO_DUPLICATE + 1):
                new_date = schedule.date + timedelta(days=day_offset)

                exists = DentistSchedule.objects.filter(
                    dentist=schedule.dentist,
                    date=new_date,
                    start_time=schedule.start_time,
                ).exists()

                if exists:
                    skipped_count += 1
                    continue

                DentistSchedule.objects.create(
                    dentist=schedule.dentist,
                    date=new_date,
                    start_time=schedule.start_time,
                    end_time=schedule.end_time,
                    is_available=True,
                )
                created_count += 1

        self.message_user(
            request,
            f"{created_count} schedules created, {skipped_count} skipped (already existed).",
            level=messages.SUCCESS,
        )

    duplicate_to_next_days.short_description = "Duplicate selected schedules to next 7 days"

# =====================================================
# Appointment Admin
# =====================================================

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "appointment_id",
        "patient_name",
        "service",
        "appointment_date",
        "appointment_time",
        "dentist_name",
        "status_colored",
        "created_at",
    )

    list_filter = (
        "status",
        "schedule_slot__dentist",
        "created_at",
    )

    search_fields = (
        "appointment_id",
        "first_name",
        "last_name",
        "email",
        "mobile_number",
    )

    date_hierarchy = "schedule_slot__date"

    readonly_fields = (
        "appointment_id",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("Appointment", {
            "fields": ("appointment_id", "service", "schedule_slot", "status", "notes")
        }),
        ("Patient", {
            "fields": (
                ("first_name", "last_name"),
                "email",
                "date_of_birth",
                ("mobile_number", "gender", "zip_code"),
            )
        }),
        ("Audit", {
            "fields": ("created_by", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    # ---------- display helpers ----------

    def appointment_date(self, obj):
        return obj.schedule_slot.date

    def appointment_time(self, obj):
        return obj.schedule_slot.start_time.strftime("%I:%M %p")

    def dentist_name(self, obj):
        dentist = obj.schedule_slot.dentist
        return dentist.get_full_name() or dentist.username

    def status_colored(self, obj):
        colors = {
            "scheduled": "blue",
            "confirmed": "green",
            "completed": "gray",
            "cancelled": "red",
            "no_show": "orange",
        }
        return format_html(
            '<strong style="color:{};">{}</strong>',
            colors.get(obj.status, "black"),
            obj.get_status_display(),
        )

    status_colored.short_description = "Status"

    # ---------- actions ----------

    actions = ("mark_confirmed", "mark_completed", "mark_cancelled")

    def mark_confirmed(self, request, queryset):
        queryset.update(status="confirmed")

    def mark_completed(self, request, queryset):
        queryset.update(status="completed")

    def mark_cancelled(self, request, queryset):
        for appointment in queryset:
            appointment.cancel()

    mark_confirmed.short_description = "Mark as confirmed"
    mark_completed.short_description = "Mark as completed"
    mark_cancelled.short_description = "Cancel appointments"


# =====================================================
# Booking Analytics Admin
# =====================================================

@admin.register(BookingAnalytics)
class BookingAnalyticsAdmin(admin.ModelAdmin):
    list_display = (
        "appointment",
        "source",
        "device_type",
        "conversion_time_seconds",
        "created_at",
    )

    list_filter = ("source", "device_type", "created_at")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
