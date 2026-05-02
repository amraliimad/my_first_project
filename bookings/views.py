from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib import messages
from django.db.models import Avg, Q, Sum
from django.core.paginator import Paginator
from django.utils import timezone
from django.utils import timezone as tz
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt
import csv

from .models import (
    Clinic, Doctor, Appointment, AppointmentPayment,
    DoctorReview, UserProfile, SPECIALTY_CHOICES, LOCATION_CHOICES
)
from .forms import ExtendedSignupForm, UserProfileUpdateForm


# ═══════════════════════════════════════════════════════
# دوال مساعدة
# ═══════════════════════════════════════════════════════

def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    return 2 * asin(sqrt(a)) * 6371


def _get_amount_paid_online(appointment):
    try:
        p = appointment.payment_details
        if p.is_verified and p.amount_cents > 0:
            return Decimal(p.amount_cents) / Decimal('100')
    except Exception:
        pass
    return Decimal('0.00')


def _resolve_owner(request):
    if request.user.is_superuser:
        owner_id = request.GET.get('owner_id') or request.POST.get('owner_id')
        if owner_id:
            try:
                return User.objects.get(id=int(owner_id))
            except (User.DoesNotExist, ValueError):
                pass
    return request.user


def _generate_slots(doctor, selected_date):
    """يولّد السلوتات بناءً على slot_duration الدكتور"""
    slots = []
    slot_minutes = doctor.slot_duration
    opening = doctor.opening_hour * 60
    closing  = doctor.closing_hour * 60
    current  = opening
    while current + slot_minutes <= closing:
        h, m = current // 60, current % 60
        slots.append({
            'hour':     h,
            'minute':   m,
            'time_str': f"{h:02d}:{m:02d}",
            'display':  _format_time_arabic(h, m),
        })
        current += slot_minutes
    return slots


def _format_time_arabic(h, m):
    suffix   = "ص" if h < 12 else "م"
    display_h = h if h <= 12 else h - 12
    if display_h == 0:
        display_h = 12
    return f"{display_h}:{m:02d} {suffix}"


def _clean_pending(doctor=None):
    threshold = timezone.now() - timedelta(minutes=30)
    qs = Appointment.objects.filter(status='Pending', created_at__lt=threshold)
    if doctor:
        qs = qs.filter(doctor=doctor)
    qs.update(status='Cancelled')


# ═══════════════════════════════════════════════════════
# الصفحة الرئيسية — قائمة العيادات
# ═══════════════════════════════════════════════════════

def home(request):
    _clean_pending()

    total_appointments = Appointment.objects.filter(
        status__in=['Confirmed', 'Attended']
    ).count()

    clinics_qs = Clinic.objects.filter(is_available=True).prefetch_related('doctors')

    # بحث بالقرب
    user_lat = request.GET.get('lat')
    user_lng = request.GET.get('lng')

    if user_lat and user_lng:
        try:
            user_lat, user_lng = float(user_lat), float(user_lng)
            clinics_list = []
            for c in clinics_qs:
                if c.latitude and c.longitude:
                    c.distance = round(haversine(user_lng, user_lat, c.longitude, c.latitude), 1)
                else:
                    c.distance = 99999
                clinics_list.append(c)
            clinics_list = sorted(clinics_list, key=lambda x: x.distance)
        except ValueError:
            clinics_list = list(clinics_qs.order_by('-id'))
    else:
        clinics_list = list(clinics_qs.order_by('-id'))

    # فلاتر
    location_query  = request.GET.get('location')
    specialty_query = request.GET.get('specialty')
    max_price       = request.GET.get('price')

    if location_query and location_query != 'all':
        clinics_list = [c for c in clinics_list if c.location == location_query]
    if specialty_query and specialty_query != 'all':
        # فلتر العيادات اللي فيها الدكتور بالتخصص ده
        clinics_list = [c for c in clinics_list
                        if c.doctors.filter(specialty=specialty_query, is_active=True).exists()]
    if max_price:
        try:
            max_p = Decimal(max_price)
            clinics_list = [c for c in clinics_list
                            if c.doctors.filter(price__lte=max_p, is_active=True).exists()]
        except Exception:
            pass

    paginator   = Paginator(clinics_list, 9)
    page_number = request.GET.get('page')
    clinics     = paginator.get_page(page_number)

    query_dict = request.GET.copy()
    if 'page' in query_dict:
        del query_dict['page']

    return render(request, 'home.html', {
        'clinics':            clinics,
        'clinics_count':      Clinic.objects.filter(is_available=True).count(),
        'total_appointments': total_appointments,
        'query_string':       query_dict.urlencode(),
        'selected_location':  location_query,
        'selected_specialty': specialty_query,
        'selected_price':     max_price,
        'is_nearest_search':  bool(user_lat),
        'location_choices':   LOCATION_CHOICES,
        'specialty_choices':  SPECIALTY_CHOICES,
    })


# ═══════════════════════════════════════════════════════
# تفاصيل العيادة — بيعرض دكاترتها
# ═══════════════════════════════════════════════════════

def clinic_detail(request, clinic_id):
    clinic  = get_object_or_404(Clinic, id=clinic_id, is_available=True)
    doctors = clinic.doctors.filter(is_active=True).annotate(
        average_rating=Avg('reviews__rating')
    ).order_by('display_order', 'name')

    # فلتر بالتخصص لو المجمع متعدد
    specialty_filter = request.GET.get('specialty')
    if specialty_filter and specialty_filter != 'all':
        doctors = doctors.filter(specialty=specialty_filter)

    # التخصصات المتاحة في العيادة
    available_specialties = clinic.doctors.filter(is_active=True)\
        .values_list('specialty', flat=True).distinct()
    spec_map = dict(SPECIALTY_CHOICES)
    specialties_list = [(s, spec_map.get(s, s)) for s in available_specialties]

    today = timezone.localtime().date()

    return render(request, 'clinic_detail.html', {
        'clinic':             clinic,
        'doctors':            doctors,
        'today':              today.strftime('%Y-%m-%d'),
        'specialties_list':   specialties_list,
        'selected_specialty': specialty_filter,
        'is_multi':           clinic.is_multi_specialty,
    })


# ═══════════════════════════════════════════════════════
# تفاصيل الدكتور — بيعرض سلوتاته
# ═══════════════════════════════════════════════════════

def doctor_detail(request, doctor_id):
    doctor = get_object_or_404(Doctor, id=doctor_id, is_active=True)
    clinic = doctor.clinic
    _clean_pending(doctor)

    # إضافة تقييم
    if request.method == 'POST' and 'rating' in request.POST:
        if request.user.is_authenticated:
            has_attended = Appointment.objects.filter(
                patient=request.user, doctor=doctor,
                status='Attended', date__lte=datetime.now().date()
            ).exists()

            if not has_attended:
                messages.error(request, "لا يمكنك تقييم الدكتور إلا بعد حضور الكشف!")
            elif not DoctorReview.objects.filter(doctor=doctor, patient=request.user).exists():
                rating  = max(1, min(5, int(request.POST.get('rating', 5))))
                comment = request.POST.get('comment', '')
                DoctorReview.objects.create(doctor=doctor, patient=request.user, rating=rating, comment=comment)
                messages.success(request, "تم نشر تقييمك! شكراً ✅")
            else:
                messages.warning(request, "لقد قمت بتقييم هذا الدكتور مسبقاً.")
        return redirect('doctor_detail', doctor_id=doctor.id)

    # اختيار اليوم
    date_str = request.GET.get('date')
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        selected_date = timezone.localtime().date()

    doctor_works = doctor.works_on_day(selected_date.weekday())

    # المواعيد المحجوزة
    booked_times = set(
        Appointment.objects
        .filter(doctor=doctor, date=selected_date)
        .exclude(status__in=['Cancelled', 'No-Show'])
        .values_list('time', flat=True)
    )

    now         = timezone.localtime()
    is_today    = (selected_date == now.date())
    curr_mins   = now.hour * 60 + now.minute
    slots       = _generate_slots(doctor, selected_date)

    slots_schedule = []
    for slot in slots:
        slot_mins = slot['hour'] * 60 + slot['minute']
        slots_schedule.append({
            'time_str':  slot['time_str'],
            'display':   slot['display'],
            'is_booked': slot['time_str'] in booked_times,
            'is_past':   is_today and slot_mins <= curr_mins,
        })

    # 14 يوم للتنقل
    today     = timezone.localtime().date()
    days_list = []
    for i in range(14):
        day = today + timedelta(days=i)
        days_list.append({
            'full_date': day.strftime('%Y-%m-%d'),
            'day_name':  day.strftime('%A'),
            'display':   day.strftime('%d/%m'),
            'works':     doctor.works_on_day(day.weekday()),
        })

    reviews        = doctor.reviews.select_related('patient').all()
    average_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0

    # دكاترة تانيين في نفس العيادة
    related_doctors = clinic.doctors.filter(is_active=True).exclude(id=doctor.id)[:3]

    return render(request, 'doctor_detail.html', {
        'doctor':          doctor,
        'clinic':          clinic,
        'days_list':       days_list,
        'selected_date':   selected_date.strftime('%Y-%m-%d'),
        'slots_schedule':  slots_schedule,
        'doctor_works':    doctor_works,
        'reviews':         reviews,
        'average_rating':  round(average_rating, 1),
        'review_count':    reviews.count(),
        'related_doctors': related_doctors,
    })


# ═══════════════════════════════════════════════════════
# تأكيد الحجز
# ═══════════════════════════════════════════════════════

@login_required(login_url='login')
def appointment_confirm(request, doctor_id, time_str):
    doctor = get_object_or_404(Doctor, id=doctor_id, is_active=True)
    clinic = doctor.clinic

    date_str = request.GET.get('date')
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        selected_date = timezone.localtime().date()

    # التحقق أن الدكتور شغال النهاردة
    if not doctor.works_on_day(selected_date.weekday()):
        messages.error(request, "عذراً، الدكتور لا يعمل في هذا اليوم.")
        return redirect('doctor_detail', doctor_id=doctor.id)

    # التحقق أن السلوت مش محجوز
    _clean_pending(doctor)
    is_taken = Appointment.objects.filter(
        doctor=doctor, date=selected_date, time=time_str
    ).exclude(status__in=['Cancelled', 'No-Show']).exists()

    if is_taken:
        messages.error(request, "عذراً، هذا الموعد تم حجزه للتو!")
        return redirect('doctor_detail', doctor_id=doctor.id)

    if request.method == 'POST':
        payment_type = request.POST.get('payment_type', 'Full')
        complaint    = request.POST.get('complaint', '')

        appointment = Appointment.objects.create(
            doctor=doctor,
            patient=request.user,
            date=selected_date,
            time=time_str,
            status='Pending',
            payment_type=payment_type,
            complaint=complaint,
        )

        AppointmentPayment.objects.create(
            appointment=appointment,
            payment_method='Vodafone',
            amount_cents=int(doctor.price * 100),
        )

        request.session['last_appointment_code'] = appointment.booking_code
        messages.success(
            request,
            f"✅ تم استلام طلبك! برجاء تحويل {doctor.price} ج.م على واتساب وإرسال صورة الإيصال للتأكيد."
        )
        return redirect(reverse('appointment_success') + f'?code={appointment.booking_code}')

    return render(request, 'appointment_confirm.html', {
        'doctor':   doctor,
        'clinic':   clinic,
        'time_str': time_str,
        'date':     selected_date,
        'price':    doctor.price,
        'whatsapp': getattr(settings, 'SUPPORT_WHATSAPP', clinic.whatsapp_number),
    })


# ═══════════════════════════════════════════════════════
# نجاح الحجز
# ═══════════════════════════════════════════════════════

@login_required
def appointment_success(request):
    code = request.GET.get('code') or request.session.get('last_appointment_code')
    appointment = None
    payment     = None

    if code:
        appointment = Appointment.objects.filter(
            booking_code=code, patient=request.user
        ).select_related('doctor__clinic').first()
        if appointment:
            try:
                payment = appointment.payment_details
            except Exception:
                pass

    return render(request, 'appointment_success.html', {
        'appointment': appointment,
        'payment':     payment,
        'code':        code,
        'whatsapp':    getattr(settings, 'SUPPORT_WHATSAPP', ''),
    })


# ═══════════════════════════════════════════════════════
# الملف الشخصي للمريض
# ═══════════════════════════════════════════════════════

@login_required(login_url='login')
def user_profile(request):
    user    = request.user
    profile = user.profile if hasattr(user, 'profile') else UserProfile.objects.create(user=user)

    if request.method == 'POST':
        form = UserProfileUpdateForm(request.POST)
        if form.is_valid():
            user.first_name      = form.cleaned_data['first_name']
            user.last_name       = form.cleaned_data['last_name']
            user.save()
            profile.middle_name  = form.cleaned_data['middle_name']
            profile.phone_number = form.cleaned_data['phone_number']
            profile.save()
            messages.success(request, "تم تحديث بياناتك بنجاح! 💾")
            return redirect('user_profile')
    else:
        form = UserProfileUpdateForm(initial={
            'first_name':   user.first_name,
            'middle_name':  profile.middle_name,
            'last_name':    user.last_name,
            'phone_number': profile.phone_number,
        })

    today    = timezone.now().date()
    upcoming = Appointment.objects.filter(
        patient=user, date__gte=today
    ).exclude(status='Cancelled').select_related('doctor__clinic').order_by('date', 'time')
    past = Appointment.objects.filter(
        patient=user, date__lt=today
    ).select_related('doctor__clinic').order_by('-date', '-time')

    return render(request, 'user_profile.html', {
        'upcoming_appointments': upcoming,
        'past_appointments':     past,
        'user':                  user,
        'form':                  form,
    })


# ═══════════════════════════════════════════════════════
# إلغاء موعد
# ═══════════════════════════════════════════════════════

@login_required
def cancel_appointment(request, appointment_id):
    if request.method != 'POST':
        return redirect('user_profile')
    appointment = get_object_or_404(Appointment, id=appointment_id, patient=request.user)
    if appointment.status not in ['Cancelled', 'Attended', 'No-Show']:
        appointment.status = 'Cancelled'
        appointment.save()
        messages.success(request, "تم إلغاء الموعد بنجاح.")
    else:
        messages.error(request, "لا يمكن إلغاء هذا الموعد.")
    return redirect('user_profile')


# ═══════════════════════════════════════════════════════
# تسجيل + من نحن
# ═══════════════════════════════════════════════════════

def signup(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = ExtendedSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "تم إنشاء الحساب بنجاح!")
            return redirect('home')
    else:
        form = ExtendedSignupForm()
    return render(request, 'registration/signup.html', {'form': form})


def about_us(request):
    return render(request, 'about_us.html')


# ═══════════════════════════════════════════════════════
# داشبورد المالك
# ═══════════════════════════════════════════════════════

@login_required
def owner_dashboard(request):
    clinics = Clinic.objects.filter(owner=request.user).prefetch_related('doctors')

    if not clinics.exists():
        messages.error(request, "ليس لديك عيادات مسجلة في حسابك.")
        return redirect('home')

    today = timezone.now().date()

    # إجمالي الدكاترة في كل عيادات المالك
    all_doctors = Doctor.objects.filter(clinic__in=clinics, is_active=True)

    stats = {
        'total_clinics':  clinics.count(),
        'total_doctors':  all_doctors.count(),
        'today_appointments': Appointment.objects.filter(
            doctor__in=all_doctors, date=today
        ).exclude(status='Cancelled').count(),
        'confirmed_upcoming': Appointment.objects.filter(
            doctor__in=all_doctors, status='Confirmed', date__gte=today
        ).count(),
        'pending_count': Appointment.objects.filter(
            doctor__in=all_doctors, status='Pending'
        ).count(),
    }

    # أرباح آخر 7 أيام
    online_cents = AppointmentPayment.objects.filter(
        appointment__doctor__in=all_doctors,
        appointment__status__in=['Confirmed', 'Attended'],
        appointment__date__gte=today - timedelta(days=7),
        is_verified=True
    ).aggregate(total=Sum('amount_cents'))['total'] or 0
    stats['weekly_earnings'] = Decimal(online_cents) / 100

    # جدول اليوم لكل عيادة
    today_schedule = []
    for clinic in clinics:
        clinic_doctors = clinic.doctors.filter(is_active=True)
        clinic_appts   = Appointment.objects.filter(
            doctor__in=clinic_doctors, date=today
        ).exclude(status='Cancelled').select_related('doctor').order_by('time')

        today_schedule.append({
            'clinic':       clinic,
            'appointments': clinic_appts,
            'count':        clinic_appts.count(),
        })

    return render(request, 'owner/dashboard.html', {
        'clinics':        clinics,
        'stats':          stats,
        'today':          today,
        'today_schedule': today_schedule,
    })


# ═══════════════════════════════════════════════════════
# جدول مواعيد دكتور معين
# ═══════════════════════════════════════════════════════

@login_required
def owner_schedule(request, doctor_id):
    doctor = get_object_or_404(Doctor, id=doctor_id, clinic__owner=request.user)
    clinic = doctor.clinic

    date_str = request.GET.get('date')
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        selected_date = timezone.localtime().date()

    appointments = Appointment.objects.filter(
        doctor=doctor, date=selected_date
    ).exclude(status='Cancelled').order_by('time')

    # تفاصيل الدفع
    appointments_with_details = []
    for appt in appointments:
        paid_online = _get_amount_paid_online(appt)
        appointments_with_details.append({
            'appointment': appt,
            'paid_online': paid_online,
            'remaining':   doctor.price - paid_online,
            'is_verified': getattr(getattr(appt, 'payment_details', None), 'is_verified', False),
        })

    # السلوتات
    booked_times = {a.time: a for a in appointments}
    now          = timezone.localtime()
    is_today     = (selected_date == now.date())
    curr_mins    = now.hour * 60 + now.minute
    slots        = _generate_slots(doctor, selected_date)
    slots_schedule = []
    for slot in slots:
        slot_mins = slot['hour'] * 60 + slot['minute']
        appt_obj  = booked_times.get(slot['time_str'])
        slots_schedule.append({
            'time_str':    slot['time_str'],
            'display':     slot['display'],
            'appointment': appt_obj,
            'is_booked':   appt_obj is not None,
            'is_manual':   appt_obj.is_manual if appt_obj else False,
            'is_past':     is_today and slot_mins <= curr_mins,
        })

    # أيام التنقل
    today     = timezone.localtime().date()
    days_list = []
    for i in range(14):
        day = today + timedelta(days=i)
        days_list.append({
            'full_date': day.strftime('%Y-%m-%d'),
            'day_name':  day.strftime('%A'),
            'display':   day.strftime('%d/%m'),
            'works':     doctor.works_on_day(day.weekday()),
        })

    return render(request, 'owner/schedule.html', {
        'doctor':                    doctor,
        'clinic':                    clinic,
        'appointments_with_details': appointments_with_details,
        'slots_schedule':            slots_schedule,
        'selected_date':             selected_date.strftime('%Y-%m-%d'),
        'days_list':                 days_list,
        'doctor_works':              doctor.works_on_day(selected_date.weekday()),
    })


# ═══════════════════════════════════════════════════════
# حجز يدوي (من السكرتيرة)
# ═══════════════════════════════════════════════════════

@login_required
def owner_block_slot(request, doctor_id):
    doctor = get_object_or_404(Doctor, id=doctor_id, clinic__owner=request.user)

    if request.method == 'POST':
        date_str      = request.POST.get('date')
        time_str      = request.POST.get('time_str')
        patient_name  = request.POST.get('patient_name', '')
        patient_phone = request.POST.get('patient_phone', '')

        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            exists = Appointment.objects.filter(
                doctor=doctor, date=selected_date, time=time_str
            ).exclude(status__in=['Cancelled', 'No-Show']).exists()

            if exists:
                messages.error(request, "هذا الموعد محجوز بالفعل!")
            else:
                Appointment.objects.create(
                    doctor=doctor,
                    patient=request.user,
                    date=selected_date,
                    time=time_str,
                    status='Confirmed',
                    payment_type='PayAtClinic',
                    is_manual=True,
                    patient_name=patient_name,
                    patient_phone=patient_phone,
                )
                messages.success(request, f"تم حجز الموعد {time_str} يدوياً ✅")
        except (ValueError, TypeError):
            messages.error(request, "بيانات غير صحيحة!")

    safe_date = date_str if date_str else timezone.localtime().date().strftime('%Y-%m-%d')
    return redirect(f'/owner/doctor/{doctor.id}/schedule/?date={safe_date}')


# ═══════════════════════════════════════════════════════
# إلغاء موعد يدوي
# ═══════════════════════════════════════════════════════

@login_required
def owner_unblock_slot(request, appointment_id):
    appointment = get_object_or_404(
        Appointment, id=appointment_id,
        doctor__clinic__owner=request.user,
        is_manual=True
    )
    if request.method == 'POST':
        selected_date = appointment.date.strftime('%Y-%m-%d')
        doctor_id     = appointment.doctor.id
        appointment.status = 'Cancelled'
        appointment.save()
        messages.success(request, "تم فتح الموعد ✅")
        return redirect(f'/owner/doctor/{doctor_id}/schedule/?date={selected_date}')
    return redirect('owner_dashboard')


# ═══════════════════════════════════════════════════════
# تحديث حالة الموعد (حضر / لم يحضر)
# ═══════════════════════════════════════════════════════

@login_required
def owner_update_appointment_status(request, appointment_id):
    appointment = get_object_or_404(
        Appointment, id=appointment_id, doctor__clinic__owner=request.user
    )
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in ['Attended', 'No-Show'] and appointment.status == 'Confirmed':
            appointment.status = new_status
            appointment.save()
            if new_status == 'Attended':
                messages.success(request, "تم تسجيل حضور المريض واكتمال الكشف ✅")
            else:
                messages.warning(request, "تم تسجيل غياب المريض ❌")
        elif appointment.status != 'Confirmed':
            messages.error(request, "لا يمكن تعديل موعد تم إغلاقه مسبقاً.")

    selected_date = appointment.date.strftime('%Y-%m-%d')
    return redirect(f'/owner/doctor/{appointment.doctor.id}/schedule/?date={selected_date}')


# ═══════════════════════════════════════════════════════
# تأكيد الدفع (الأونر يأكد إن الفلوس وصلت)
# ═══════════════════════════════════════════════════════

@login_required
def owner_confirm_payment(request, appointment_id):
    appointment = get_object_or_404(
        Appointment, id=appointment_id, doctor__clinic__owner=request.user
    )
    if request.method == 'POST':
        try:
            payment = appointment.payment_details
        except Exception:
            payment = AppointmentPayment.objects.create(
                appointment=appointment,
                payment_method='Vodafone',
                amount_cents=int(appointment.doctor.price * 100),
            )
        payment.is_verified = True
        payment.save()
        appointment.status = 'Confirmed'
        appointment.save()
        messages.success(request, "✅ تم تأكيد الدفع والموعد.")

    selected_date = appointment.date.strftime('%Y-%m-%d')
    return redirect(f'/owner/doctor/{appointment.doctor.id}/schedule/?date={selected_date}')


# ═══════════════════════════════════════════════════════
# الأرباح
# ═══════════════════════════════════════════════════════

@login_required
def owner_earnings(request):
    owner   = _resolve_owner(request)
    clinics = Clinic.objects.filter(owner=owner)

    if not clinics.exists():
        messages.error(request, "ليس لديك عيادات مسجلة.")
        return redirect('home')

    all_doctors = Doctor.objects.filter(clinic__in=clinics, is_active=True)
    today       = timezone.localtime().date()

    # وردية اليوم
    today_appointments = (
        Appointment.objects
        .filter(doctor__in=all_doctors, date=today)
        .exclude(status__in=['Cancelled', 'No-Show'])
        .select_related('doctor__clinic', 'payment_details')
        .order_by('time')
    )
    today_total  = Decimal('0.00')
    today_cash   = Decimal('0.00')
    today_online = Decimal('0.00')
    today_rows   = []

    for appt in today_appointments:
        price     = appt.doctor.price
        paid      = _get_amount_paid_online(appt)
        cash_part = price - paid
        today_total  += price
        today_cash   += cash_part
        today_online += paid
        today_rows.append({'appointment': appt, 'price': price, 'paid_online': paid, 'cash_part': cash_part})

    # غير مسوّاة
    unsettled_list = list(
        Appointment.objects
        .filter(doctor__in=all_doctors, status='Attended', is_settled=False)
        .select_related('doctor__clinic', 'payment_details')
        .order_by('-date', '-time')
    )
    total_collected  = Decimal('0.00')
    total_commission = Decimal('0.00')
    commission_rows  = []

    for appt in unsettled_list:
        price           = appt.doctor.price
        commission_rate = appt.doctor.clinic.commission_percentage / Decimal('100')
        commission_amt  = round(price * commission_rate, 2)
        paid            = _get_amount_paid_online(appt)
        total_collected  += paid
        total_commission += commission_amt
        commission_rows.append({
            'appointment':    appt,
            'price':          price,
            'commission_pct': appt.doctor.clinic.commission_percentage,
            'commission_amt': commission_amt,
            'net_to_owner':   round(price - commission_amt, 2),
        })

    net_settleable = total_collected - total_commission

    # مسوّاة سابقاً (آخر 30)
    settled_qs = (
        Appointment.objects
        .filter(doctor__in=all_doctors, status='Attended', is_settled=True)
        .select_related('doctor__clinic', 'payment_details')
        .order_by('-date')[:30]
    )
    past_total      = Decimal('0.00')
    past_commission = Decimal('0.00')
    for appt in settled_qs:
        rate             = appt.doctor.clinic.commission_percentage / Decimal('100')
        past_commission += round(appt.doctor.price * rate, 2)
        past_total      += _get_amount_paid_online(appt)

    return render(request, 'owner/earnings.html', {
        'today':            today,
        'owner':            owner,
        'clinics':          clinics,
        'is_superuser':     request.user.is_superuser,
        'today_total':      today_total,
        'today_cash':       today_cash,
        'today_online':     today_online,
        'today_rows':       today_rows,
        'today_count':      len(today_rows),
        'total_collected':  total_collected,
        'total_commission': total_commission,
        'net_settleable':   net_settleable,
        'unsettled_count':  len(unsettled_list),
        'commission_rows':  commission_rows,
        'settled_qs':       settled_qs,
        'past_total':       past_total,
        'past_commission':  past_commission,
        'past_net':         past_total - past_commission,
    })


# ═══════════════════════════════════════════════════════
# تسوية الحساب (Superuser فقط)
# ═══════════════════════════════════════════════════════

@login_required
def settle_account(request):
    if not request.user.is_superuser:
        messages.error(request, "⛔ هذا الإجراء متاح للمشرفين فقط.")
        return redirect('owner_earnings')

    if request.method == 'POST':
        owner_id = request.POST.get('owner_id')
        try:
            owner       = User.objects.get(id=int(owner_id))
            all_doctors = Doctor.objects.filter(clinic__owner=owner)
            count       = Appointment.objects.filter(
                doctor__in=all_doctors, status='Attended', is_settled=False
            ).update(is_settled=True, settled_at=tz.now())
            messages.success(request, f"✅ تمت تسوية {count} موعد لـ {owner.get_full_name() or owner.username}")
        except (User.DoesNotExist, ValueError, TypeError):
            messages.error(request, "⛔ بيانات غير صحيحة.")

    owner_id     = request.POST.get('owner_id') if request.method == 'POST' else None
    redirect_url = f"/owner/earnings/?owner_id={owner_id}" if owner_id else "/owner/earnings/"
    return redirect(redirect_url)


# ═══════════════════════════════════════════════════════
# تصدير CSV
# ═══════════════════════════════════════════════════════

@login_required
def owner_earnings_export_csv(request):
    owner       = _resolve_owner(request)
    all_doctors = Doctor.objects.filter(clinic__owner=owner)

    unsettled = (
        Appointment.objects
        .filter(doctor__in=all_doctors, status='Attended', is_settled=False)
        .select_related('doctor__clinic', 'payment_details')
        .order_by('-date', '-time')
    )

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="clinic_earnings.csv"'
    writer = csv.writer(response)
    writer.writerow(['التاريخ', 'الوقت', 'كود الموعد', 'الدكتور', 'العيادة',
                     'سعر الكشف', 'المدفوع أونلاين', 'نسبة العمولة', 'مبلغ العمولة', 'الصافي'])

    for appt in unsettled:
        price           = appt.doctor.price
        paid            = _get_amount_paid_online(appt)
        commission_rate = appt.doctor.clinic.commission_percentage / Decimal('100')
        commission_amt  = round(price * commission_rate, 2)
        writer.writerow([
            appt.date.strftime('%Y-%m-%d'), appt.time, appt.booking_code,
            appt.doctor.full_name, appt.doctor.clinic.name,
            price, paid, appt.doctor.clinic.commission_percentage,
            commission_amt, round(paid - commission_amt, 2),
        ])

    return response