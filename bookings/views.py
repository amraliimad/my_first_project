from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib import messages
from django.db.models import Avg, Q
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt 
from .models import Pitch, Booking, Payment, Review, PitchPricing
from .forms import PaymentForm

# ---------------------------------------------------------
# دالة مساعدة لحساب المسافة (Haversine Formula)
# ---------------------------------------------------------
def haversine(lon1, lat1, lon2, lat2):
    """
    تحسب المسافة بين نقطتين جغرافيتين بالكيلومتر
    """
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 # نصف قطر الأرض بالكيلومتر
    return c * r

# ---------------------------------------------------------
# الصفحة الرئيسية (بحث + مسافة + تنظيف تلقائي للحجوزات)
# ---------------------------------------------------------
def home(request):
    # 1. تنظيف الحجوزات المعلقة القديمة
    # أي حجز لسه "Pending" وعدى عليه 30 دقيقة بيتلغي أوتوماتيك
    time_threshold = timezone.now() - timedelta(minutes=30)
    Booking.objects.filter(status='Pending', created_at__lt=time_threshold).update(status='Cancelled')

    # 2. جلب قائمة الملاعب
    pitches_list = Pitch.objects.all()

    # 3. منطق البحث عن "أقرب ملعب لي"
    user_lat = request.GET.get('lat')
    user_lng = request.GET.get('lng')

    if user_lat and user_lng:
        try:
            user_lat = float(user_lat)
            user_lng = float(user_lng)
            pitches_with_distance = []
            for pitch in pitches_list:
                if pitch.latitude and pitch.longitude:
                    dist = haversine(user_lng, user_lat, pitch.longitude, pitch.latitude)
                    pitch.distance = round(dist, 1)
                else:
                    pitch.distance = 99999 # الملاعب اللي ملهاش موقع تظهر في الآخر
                pitches_with_distance.append(pitch)
            # ترتيب الملاعب من الأقرب للأبعد
            pitches_list = sorted(pitches_with_distance, key=lambda x: x.distance)
        except ValueError:
            pass
    else:
        # الترتيب الافتراضي: الأحدث أولاً
        pitches_list = pitches_list.order_by('-id')

    # 4. تطبيق الفلاتر (منطقة - حجم - أرضية - سعر)
    location_query = request.GET.get('location')
    size_query = request.GET.get('size')
    floor_query = request.GET.get('floor_type')
    max_price = request.GET.get('price')

    # ملاحظة: لو الترتيب حولها لقائمة (List)، الفلترة بتختلف عن الـ QuerySet
    if isinstance(pitches_list, list):
        if location_query and location_query != 'all':
            pitches_list = [p for p in pitches_list if p.location == location_query]
        if size_query and size_query != 'all':
            pitches_list = [p for p in pitches_list if p.size == size_query]
        if floor_query and floor_query != 'all':
            pitches_list = [p for p in pitches_list if p.floor_type == floor_query]
        if max_price:
            pitches_list = [p for p in pitches_list if p.price_per_hour <= float(max_price)]
    else:
        if location_query and location_query != 'all': pitches_list = pitches_list.filter(location=location_query)
        if size_query and size_query != 'all': pitches_list = pitches_list.filter(size=size_query)
        if floor_query and floor_query != 'all': pitches_list = pitches_list.filter(floor_type=floor_query)
        if max_price: pitches_list = pitches_list.filter(price_per_hour__lte=max_price)

    # 5. تقسيم الصفحات (Pagination)
    locations = Pitch.objects.values_list('location', flat=True).distinct()
    paginator = Paginator(pitches_list, 6) # 6 ملاعب في الصفحة
    page_number = request.GET.get('page')
    pitches = paginator.get_page(page_number)

    return render(request, 'home.html', {
        'pitches': pitches,
        'locations': locations,
        'selected_location': location_query,
        'selected_size': size_query,
        'selected_floor': floor_query,
        'selected_price': max_price,
        'is_nearest_search': bool(user_lat),
    })


# ---------------------------------------------------------
# تفاصيل الملعب (مع الأسعار الديناميكية والجدول)
# ---------------------------------------------------------
def pitch_detail(request, pitch_id):
    pitch = get_object_or_404(Pitch, id=pitch_id)
    
    # 1. إضافة تقييم
    if request.method == 'POST' and 'rating' in request.POST:
        if request.user.is_authenticated:
            if not Review.objects.filter(pitch=pitch, user=request.user).exists():
                Review.objects.create(
                    pitch=pitch, user=request.user,
                    rating=request.POST.get('rating'),
                    comment=request.POST.get('comment')
                )
                messages.success(request, "تم نشر تقييمك!")
            else:
                messages.warning(request, "لقد قمت بتقييم هذا الملعب مسبقاً.")
            return redirect('pitch_detail', pitch_id=pitch.id)
        else:
            messages.error(request, "يجب تسجيل الدخول للتقييم.")

    # 2. الإحصائيات
    average_rating = pitch.reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    reviews = pitch.reviews.all()

    # 3. الجدول الزمني (المنطق المعدل)
    date_str = request.GET.get('date')
    try: selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except: selected_date = datetime.now().date()

    # جلب الحجوزات النشطة (المؤكدة والمعلقة)
    active_bookings = Booking.objects.filter(
        pitch=pitch, date=selected_date
    ).exclude(status='Cancelled')
    
    # عمل خريطة للساعات وحالتها: {18: 'Confirmed', 19: 'Pending'}
    hours_status_map = {int(b.time.split(':')[0]): b.status for b in active_bookings}

    hours_schedule = []
    current_hour = datetime.now().hour
    is_today = (selected_date == datetime.now().date())

    for i in range(24): 
        # بنشوف هل الساعة دي موجودة في الخريطة ولا لأ
        status = hours_status_map.get(i) # هترجع 'Confirmed' أو 'Pending' أو None
        
        is_past = is_today and i <= current_hour
        
        # سعر الساعة
        hour_price = pitch.price_per_hour
        special_price = PitchPricing.objects.filter(
            pitch=pitch, start_hour__lte=i, end_hour__gt=i
        ).filter(Q(specific_date=selected_date) | Q(specific_date__isnull=True)).order_by('price').first()
        if special_price: hour_price = special_price.price

        hours_schedule.append({
            'hour_display': f"{i:02d}:00",
            'hour_value': i,
            'status': status,      # هنا التغيير المهم: بنبعت الحالة نفسها
            'is_past': is_past,
            'price': hour_price
        })

    days_list = [{'full_date': (datetime.now().date() + timedelta(days=i)).strftime('%Y-%m-%d'), 
                  'day_name': (datetime.now().date() + timedelta(days=i)).strftime('%A'), 
                  'display': (datetime.now().date() + timedelta(days=i)).strftime('%d/%m')} for i in range(14)]

    related_pitches = Pitch.objects.filter(location=pitch.location).exclude(id=pitch.id)[:3]

    return render(request, 'pitch_detail.html', {
        'pitch': pitch, 'days_list': days_list, 'selected_date': selected_date.strftime('%Y-%m-%d'),
        'hours_schedule': hours_schedule, 'reviews': reviews, 'average_rating': round(average_rating, 1),
        'review_count': reviews.count(), 'related_pitches': related_pitches
    })


    # 4. شريط الأيام
    days_list = [{'full_date': (datetime.now().date() + timedelta(days=i)).strftime('%Y-%m-%d'), 
                  'day_name': (datetime.now().date() + timedelta(days=i)).strftime('%A'), 
                  'display': (datetime.now().date() + timedelta(days=i)).strftime('%d/%m')} for i in range(14)]

    # 5. ملاعب مقترحة (في نفس المنطقة)
    related_pitches = Pitch.objects.filter(location=pitch.location).exclude(id=pitch.id)[:3]

    return render(request, 'pitch_detail.html', {
        'pitch': pitch, 'days_list': days_list, 'selected_date': selected_date.strftime('%Y-%m-%d'),
        'hours_schedule': hours_schedule, 'reviews': reviews, 'average_rating': round(average_rating, 1),
        'review_count': reviews.count(), 'related_pitches': related_pitches
    })


# ---------------------------------------------------------
# تأكيد الحجز (VIP - حد يومي - أسعار متغيرة - عربون)
# ---------------------------------------------------------
# ---------------------------------------------------------
# تأكيد الحجز (VIP - حد يومي - أسعار متغيرة - عربون)
# ---------------------------------------------------------
@login_required(login_url='login')
def booking_confirm(request, pitch_id, hour):
    pitch = get_object_or_404(Pitch, id=pitch_id)
    
    # 1. إعداد التاريخ والوقت
    date_str = request.GET.get('date')
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        selected_date = datetime.now().date()
    
    hour_int = int(hour)
    time_str = f"{hour_int:02d}:00"

    # 2. حماية من الحجز المكرر (Race Condition) - فحص مبدئي
    is_taken = Booking.objects.filter(
        pitch=pitch, date=selected_date, time=time_str, status__in=['Confirmed', 'Pending']
    ).exists()

    if is_taken:
        messages.error(request, "عذراً، هذا الموعد تم حجزه للتو من قبل شخص آخر!")
        return redirect('pitch_detail', pitch_id=pitch.id)

    # 3. التحقق من الحد الأقصى للحجوزات اليومية (4 مرات) - فحص عند الدخول للصفحة
    today_bookings_count = Booking.objects.filter(
        user=request.user, 
        date=selected_date
    ).exclude(status='Cancelled').count()

    if today_bookings_count >= 4:
        messages.error(request, "عذراً، لقد وصلت للحد الأقصى (4 ساعات) في اليوم.")
        return redirect('pitch_detail', pitch_id=pitch.id)

    # 4. حساب السعر النهائي للساعة دي
    final_price = pitch.price_per_hour
    special_price = PitchPricing.objects.filter(
        pitch=pitch, start_hour__lte=hour_int, end_hour__gt=hour_int
    ).filter(Q(specific_date=selected_date) | Q(specific_date__isnull=True)).order_by('price').first()
    
    if special_price: final_price = special_price.price

    # 5. التحقق هل المستخدم VIP؟ (أكتر من 10 حجوزات مؤكدة)
    is_vip = Booking.objects.filter(user=request.user, status='Confirmed').count() >= 10

    # 6. معالجة الطلب (POST)
    if request.method == 'POST':
        # --- !!! الحماية القصوى (Double Check) !!! ---
        # نتحقق مرة أخرى في اللحظة دي بالذات قبل الحفظ مباشرة
        # ده بيمنع التحايل لو المستخدم فاتح كذا تاب
        real_time_count = Booking.objects.filter(
            user=request.user, 
            date=selected_date
        ).exclude(status='Cancelled').count()

        if real_time_count >= 4:
            messages.error(request, "تنبيه: لا يمكن إتمام العملية، لديك 4 حجوزات بالفعل لهذا اليوم.")
            return redirect('pitch_detail', pitch_id=pitch.id)
        # ---------------------------------------------

        form = PaymentForm(request.POST)
        payment_type_choice = request.POST.get('payment_type', 'Full')

        # حماية: الدفع في الملعب للـ VIP فقط
        if payment_type_choice == 'PayAtPitch' and not is_vip:
            messages.error(request, "خيار الدفع في الملعب متاح فقط للعملاء المميزين.")
            return redirect(request.path)

        if form.is_valid():
            # إنشاء الحجز
            booking = Booking.objects.create(
                pitch=pitch,
                user=request.user, 
                date=selected_date,
                time=time_str,
                status='Pending', # لازم مراجعة
                payment_type=payment_type_choice
            )
            
            # حفظ بيانات الدفع
            payment = form.save(commit=False)
            payment.booking = booking
            # تخزين طريقة الدفع (فودافون/انستا)
            method_from_post = request.POST.get('pay', 'Cash')
            method_map = {'voda': 'Vodafone', 'insta': 'Instapay', 'cash': 'Cash', 'fawry': 'Fawry'}
            payment.payment_method = method_map.get(method_from_post, 'Cash')
            payment.save()

            # حفظ الكود في الجلسة
            request.session['last_booking_code'] = booking.booking_code
            messages.success(request, "تم تسجيل الطلب! سيتم الإلغاء تلقائياً إذا لم يؤكد خلال 30 دقيقة.")
            return redirect('booking_success')
    else:
        form = PaymentForm()

    return render(request, 'booking_confirm.html', {
        'pitch': pitch,
        'hour': time_str,
        'date': selected_date,
        'form': form,
        'price': final_price, # السعر للعرض
        'is_vip': is_vip      # حالة الـ VIP
    })



# ---------------------------------------------------------
# نجاح الحجز
# ---------------------------------------------------------
@login_required
def booking_success(request):
    booking_code = request.session.get('last_booking_code')
    booking = None
    if booking_code:
        booking = Booking.objects.filter(booking_code=booking_code).first()
    return render(request, 'booking_success.html', {'booking_code': booking_code, 'booking': booking})


# ---------------------------------------------------------
# الملف الشخصي (مقسم) وإلغاء الحجز
# ---------------------------------------------------------
@login_required
def user_profile(request):
    today = datetime.now().date()
    # تقسيم الحجوزات
    upcoming = Booking.objects.filter(user=request.user, date__gte=today).order_by('date', 'time')
    past = Booking.objects.filter(user=request.user, date__lt=today).order_by('-date', '-time')
    return render(request, 'user_profile.html', {'upcoming_bookings': upcoming, 'past_bookings': past})

@login_required
def cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    # لا يمكن إلغاء حجز قديم أو ملغي
    if booking.status != 'Cancelled':
        booking.status = 'Cancelled'
        booking.save()
        messages.success(request, "تم إلغاء الحجز بنجاح.")
    return redirect('user_profile')


# ---------------------------------------------------------
# تسجيل الدخول وإنشاء الحساب
# ---------------------------------------------------------
def signup(request):
    if request.user.is_authenticated: return redirect('home')
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "تم إنشاء الحساب!")
            return redirect('home')
    else: form = UserCreationForm()
    return render(request, "registration/signup.html", {'form': form})
