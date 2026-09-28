from django.urls import path

from patients import views
from patients.appointments import AppointmentDetail, AppointmentList
from patients.billing import PatientBilling
from patients.matching import MatchPayments

urlpatterns = [
    path("", views.PatientList.as_view()),
    path("contacts/", views.ContactSearch.as_view()),
    path("growth/", views.Growth.as_view()),
    path("spend/", views.Spend.as_view()),
    path("<uuid:pk>/", views.PatientDetail.as_view()),
    path("<uuid:pk>/billing/", PatientBilling.as_view()),
    path("<uuid:pk>/billing/matches/", MatchPayments.as_view()),
    path("<uuid:pk>/tasks/", views.FollowupList.as_view()),
    path("<uuid:pk>/tasks/<uuid:task_pk>/", views.FollowupStatus.as_view()),
    path("<uuid:pk>/appointments/", AppointmentList.as_view()),
    path("<uuid:pk>/appointments/<uuid:appointment_pk>/", AppointmentDetail.as_view()),
    path("<uuid:pk>/events/", views.EventList.as_view()),
    path("<uuid:pk>/receipts/", views.ReceiptList.as_view()),
]
