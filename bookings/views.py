from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Pitch, Booking, Payment
from .forms import PaymentForm
from datetime import datetime, timedelta
from django.contrib import messages # ضيف ده فوق

def home(request):
    pitches = Pitch.objects.all()
    return render(request, 'home.html', {'pitches': pitches})

def pitch_detail(request, pitch_id):
    pitch = get_object_or_404(Pitch, id=pitch_id)
    
    # 1. الحصول على التاريخ المختار (أو تاريخ اليوم كافتراضي)
    date_str = request.GET.get('date')
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = datetime.now().date()
    else:
        selected_date = datetime.now().date()

    # 2. جلب الحجوزات الموجودة لهذا الملعب في هذا التاريخ بالتحديد
    # بنجيب فقط الساعات المحجوزة ونحولها لقائمة أرقام (مثلاً: [10, 14, 20])
    booked_hours = Booking.objects.filter(
        pitch=pitch, 
        date=selected_date, 
        status__in=['Confirmed', 'Pending'] # بنعتبر المعلق محجوز برضه للأمان
    ).values_list('time', flat=True)
    
    # تحويل وقت الداتابيز (08:00:00) لرقم (8) ليسهل مقارنته في الجدول
    booked_hours_list = [int(t.split(':')[0]) for t in booked_hours]

    # 3. توليد 14 يوم للمواعيد (كما هي في كودك الأصلي)
    days_list = []
    for i in range(14):
        day = datetime.now().date() + timedelta(days=i)
        days_list.append({
            'full_date': day.strftime('%Y-%m-%d'),
            'day_name': day.strftime('%A'), 
            'display': day.strftime('%d/%m')
        })

    # 4. توليد الساعات وربطها بحالة الحجز الحقيقية
    hours_schedule = []
    for i in range(24):
        hours_schedule.append({
            'hour_display': f"{i:02d}:00",
            'hour_value': i,
            'is_booked': i in booked_hours_list # هنا الربط الحقيقي بالداتابيز
        })

    return render(request, 'pitch_detail.html', {
        'pitch': pitch,
        'days_list': days_list,
        'selected_date': selected_date.strftime('%Y-%m-%d'), # نبعته نص لسهولة الاستخدام
        'hours_schedule': hours_schedule
    })

@login_required
@login_required # بيحل مشكلة AnonymousUser اللي ظهرتلك
def booking_confirm(request, pitch_id, hour):
    pitch = get_object_or_404(Pitch, id=pitch_id)
    selected_date_raw = request.GET.get('date')
    
    # حل مشكلة "invalid date format" اللي في الصورة التانية
    try:
        # بنحاول نحول التاريخ من شكل (Feb. 12, 2026) لشكل يفهمه الـ Database
        selected_date = datetime.strptime(selected_date_raw, '%b. %d, %Y').date()
    except (ValueError, TypeError):
        # لو فشل التحويل أو التاريخ مش موجود، بنستخدم تاريخ النهاردة كحماية
        selected_date = datetime.now().date()
    
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            # إنشاء الحجز وربطه بالمستخدم المسجل حالياً
            booking = Booking.objects.create(
                pitch=pitch,
                user=request.user, 
                date=selected_date,
                time=f"{int(hour):02d}:00", # تأكدنا إن الساعة رقم
                status='Pending'
            )
            
            payment = form.save(commit=False)
            payment.booking = booking
            payment.save()
            return redirect('booking_success')
    else:
        form = PaymentForm()

    return render(request, 'booking_confirm.html', {
        'pitch': pitch,
        'hour': hour,
        'date': selected_date,
        'form': form
    })

def booking_success(request):
    return render(request, 'booking_success.html')
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login


def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "تم إنشاء الحساب بنجاح!")
            return redirect('home') # تأكد إن الاسم 'home' موجود في urls.py
        else:
            # لو فيه خطأ في البيانات (مثلاً الباسورد ضعيفة) هيطبع الخطأ في الـ Terminal
            print(form.errors) 
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})