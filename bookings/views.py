from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib import messages
from .models import Pitch, Booking, Payment
from .forms import PaymentForm
from datetime import datetime, timedelta
# ---------------------------------------------------------
# الصفحة الرئيسية
# ---------------------------------------------------------
def home(request):
    pitches = Pitch.objects.all()
    return render(request, 'home.html', {'pitches': pitches})


# ---------------------------------------------------------
# تفاصيل الملعب وجدول المواعيد
# ---------------------------------------------------------
def pitch_detail(request, pitch_id):
    pitch = get_object_or_404(Pitch, id=pitch_id)
    
    # 1. استلام التاريخ من الرابط أو استخدام تاريخ اليوم
    date_str = request.GET.get('date')
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = datetime.now().date()
    else:
        selected_date = datetime.now().date()

    # 2. جلب الساعات المحجوزة مسبقاً (المؤكدة والمعلقة)
    booked_hours_qs = Booking.objects.filter(
        pitch=pitch, 
        date=selected_date, 
        status__in=['Confirmed', 'Pending']
    ).values_list('time', flat=True)
    
    # تحويل الأوقات من نص "18:00" إلى رقم صحيح 18 للمقارنة
    booked_hours_list = []
    for t in booked_hours_qs:
        try:
            # نأخذ الجزء الأول قبل النقطتين ونحوله لرقم
            booked_hours_list.append(int(t.split(':')[0]))
        except (ValueError, IndexError):
            continue

    # 3. توليد قائمة الأيام الـ 14 القادمة للتنقل
    days_list = []
    for i in range(14):
        day = datetime.now().date() + timedelta(days=i)
        days_list.append({
            'full_date': day.strftime('%Y-%m-%d'), # الصيغة القياسية للرابط
            'day_name': day.strftime('%A'),       # اسم اليوم (Monday)
            'display': day.strftime('%d/%m')      # العرض المختصر (12/02)
        })

    # 4. توليد جدول الساعات (من 09:00 صباحاً حتى 03:00 فجراً مثلاً، أو 24 ساعة)
    # هنا سأجعلها 24 ساعة لتبسيط الكود
    hours_schedule = []
    current_hour = datetime.now().hour
    is_today = (selected_date == datetime.now().date())

    for i in range(24):
        # التحقق: هل الساعة محجوزة؟
        is_booked = i in booked_hours_list
        
        # التحقق: هل الساعة مضت بالفعل؟ (لا يمكن حجز الماضي في نفس اليوم)
        is_past = is_today and i <= current_hour

        hours_schedule.append({
            'hour_display': f"{i:02d}:00", # الشكل الظاهري
            'hour_value': i,               # القيمة للرابط
            'is_booked': is_booked,
            'is_past': is_past,            # لنمنع الضغط عليها في الـ HTML
            'available': not (is_booked or is_past) # ملخص الحالة
        })

    return render(request, 'pitch_detail.html', {
        'pitch': pitch,
        'days_list': days_list,
        'selected_date': selected_date.strftime('%Y-%m-%d'),
        'hours_schedule': hours_schedule
    })


# ---------------------------------------------------------
# تأكيد الحجز والدفع
# ---------------------------------------------------------
@login_required(login_url='login') # تحويل المستخدم لصفحة الدخول إذا لم يكن مسجلاً
def booking_confirm(request, pitch_id, hour):
    pitch = get_object_or_404(Pitch, id=pitch_id)
    
    # استقبال التاريخ ومعالجته
    date_str = request.GET.get('date')
    try:
        # نحاول قراءة التاريخ بصيغة قياسية
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        selected_date = datetime.now().date()
    
    # تجهيز صيغة الوقت للحفظ (مثلاً "14:00")
    time_str = f"{int(hour):02d}:00"

    # !! حماية هامة !!: التأكد أن الموعد لم يحجز فجأة من شخص آخر
    is_taken = Booking.objects.filter(
        pitch=pitch, date=selected_date, time=time_str, status__in=['Confirmed', 'Pending']
    ).exists()

    if is_taken:
        messages.error(request, "عذراً، هذا الموعد تم حجزه للتو من قبل شخص آخر!")
        return redirect('pitch_detail', pitch_id=pitch.id)

    # معالجة طلب الحجز (عند ضغط الزر)
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            # 1. إنشاء الحجز
            booking = Booking.objects.create(
                pitch=pitch,
                user=request.user, 
                date=selected_date,
                time=time_str,
                status='Pending'
            )
            
            # 2. حفظ بيانات الدفع وربطها بالحجز
            payment = form.save(commit=False)
            payment.booking = booking
            
            # تحديد طريقة الدفع بناء على اختيار المستخدم (Radio Button)
            payment_method = request.POST.get('pay', 'Cash') # الافتراضي كاش
            # نحول القيم المختصرة من الـ HTML إلى القيم الموجودة في الموديل
            method_map = {'voda': 'Vodafone', 'insta': 'Instapay', 'cash': 'Cash', 'fawry': 'Fawry'}
            payment.payment_method = method_map.get(payment_method, 'Cash')
            
            payment.save()

            # 3. حفظ كود الحجز في الجلسة (Session) لعرضه في الصفحة التالية
            request.session['last_booking_code'] = booking.booking_code
            
            messages.success(request, "تم تسجيل طلبك بنجاح!")
            return redirect('booking_success')
    else:
        form = PaymentForm()

    return render(request, 'booking_confirm.html', {
        'pitch': pitch,
        'hour': time_str,
        'date': selected_date,
        'form': form
    })


# ---------------------------------------------------------
# صفحة نجاح الحجز
# ---------------------------------------------------------
@login_required
def booking_success(request):
    # استرجاع كود الحجز من الجلسة
    booking_code = request.session.get('last_booking_code')
    
    # محاولة جلب تفاصيل الحجز لعرضها (اختياري)
    booking = None
    if booking_code:
        booking = Booking.objects.filter(booking_code=booking_code).first()

    return render(request, 'booking_success.html', {
        'booking_code': booking_code,
        'booking': booking
    })


# ---------------------------------------------------------
# تسجيل حساب جديد
# ---------------------------------------------------------
def signup(request):
    if request.user.is_authenticated:
        return redirect('home') # إذا كان مسجلاً بالفعل، حوله للرئيسية

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "تم إنشاء الحساب وتسجيل الدخول بنجاح!")
            return redirect('home')
        else:
            messages.error(request, "هناك خطأ في البيانات، يرجى التأكد من كلمة المرور.")
    else:
        form = UserCreationForm()
        
    return render(request, "registration/signup.html", {'form': form})