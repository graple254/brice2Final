from django.urls import path
from .views import *

urlpatterns = [
      path('', index, name='index'),
      path('services/step1/', service_selection, name='service_selection'),
      path('book/<int:service_id>/step2/', book_appointment, name='book_appointment'),
      path('time-slots/<int:service_id>/step3/', time_slots, name='time_slots'),
      path('confirm/<int:schedule_id>/<int:service_id>/step4/', confirm_booking, name='confirm_booking'),
      path('appointment-confirmation/<str:appointment_id>/step5/', appointment_confirmation, name='appointment_confirmation'),


      # Appointment lookup
      path('find-appointment/', find_appointment, name='find_appointment'),


      path('login/', login_view, name='login'),
      path('logout/', logout_view, name='logout'),

      path('staff/dashboard/', staff_dashboard, name='staff_dashboard'),
      path('staff/create-schedules/', staff_create_schedules, name='staff_create_schedules'),
      path('staff/all-appointments/', view_all_appointments, name='view_all_appointments'),
      path('staff/update-appointment-status/', update_appointment_status, name='update_appointment_status'),

      path('dentist/dashboard/', dentist_dashboard, name='dentist_dashboard'),
      path('dentist/view-schedule/', dentist_view_schedule, name='dentist_view_schedule'),
      path('dentist/view-appointments/', dentist_view_appointments, name='dentist_view_appointments'),
]