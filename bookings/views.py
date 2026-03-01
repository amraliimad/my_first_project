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
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371
    return c * r


# ---------------------------------------------------------
# الصفحة الرئيسية
# ---------------------------------------------------------
def home(request):
    # تنظيف الحجوزات المعلقة القديمة
    time_threshold = timezone.now() - timedelta(minutes=30)
    Booking.objects.filter(status='Pending', created_at__lt=time_threshold).update(status='Cancelled')

    pitches_list  = Pitch.objects.all()
    pitches_count = Pitch.objects.count()

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
                    pitch.distance = 99999
                pitches_with_distance.append(pitch)
            pitches_list = sorted(pitches_with_distance, key=lambda x: x.distance)
        except ValueError:
            pass
    else:
        pitches_list = pitches_list.order_by('-id')

    location_query = request.GET.get('location')
    size_query     = request.GET.get('size')
    floor_query    = request.GET.get('floor_type')
    max_price      = request.GET.get('price')

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
        if location_query and location_query != 'all':
            pitches_list = pitches_list.filter(location=location_query)
        if size_query and size_query != 'all':
            pitches_list = pitches_list.filter(size=size_query)
        if floor_query and floor_query != 'all':
            pitches_list = pitches_list.filter(floor_type=floor_query)
        if max_price:
            pitches_list = pitches_list.filter(price_per_hour__lte=max_price)

    paginator   = Paginator(pitches_list, 6)
    page_number = request.GET.get('page')
    pitches     = paginator.get_page(page_number)

    return render(request, 'home.html', {
        'pitches_count': Pitch.objects.count(),  # ← أضف السطر ده
        'pitches':           pitches,
        'pitches_count':     pitches_count,
        'selected_location': location_query,
        'selected_size':     size_query,
        'selected_floor':    floor_query,
        'selected_price':    max_price,
        'is_nearest_search': bool(user_lat),
    })


# ---------------------------------------------------------
# تفاصيل الملعب
# ---------------------------------------------------------
def pitch_detail(request, pitch_id):
    pitch = get_object_or_404(Pitch, id=pitch_id)

    if request.method == 'POST' and 'rating' in request.POST:
        if request.user.is_authenticated:
            # التأكد أن المستخدم لعب بالفعل في هذا الملعب (حجز مؤكد وتاريخ مضى)
            has_played = Booking.objects.filter(
                user=request.user, 
                pitch=pitch, 
                status='Confirmed', 
                date__lte=datetime.now().date()
            ).exists()

            if not has_played:
                messages.error(request, "لا يمكنك تقييم الملعب إلا بعد اللعب فيه!")
            elif not Review.objects.filter(pitch=pitch, user=request.user).exists():
                Review.objects.create(...)
                messages.success(request, "تم نشر تقييمك!")
            else:
                messages.warning(request, "لقد قمت بتقييم هذا الملعب مسبقاً.")
            return redirect('pitch_detail', pitch_id=pitch.id)

    average_rating = pitch.reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    reviews        = pitch.reviews.all()

    date_str = request.GET.get('date')
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        selected_date = datetime.now().date()

    active_bookings  = Booking.objects.filter(pitch=pitch, date=selected_date).exclude(status='Cancelled')
    hours_status_map = {int(b.time.split(':')[0]): b.status for b in active_bookings}

    pricing_rules      = PitchPricing.objects.filter(pitch=pitch).filter(
        Q(specific_date=selected_date) | Q(specific_date__isnull=True)
    ).order_by('price')
    pricing_rules_list = list(pricing_rules)

    hours_schedule = []
    current_hour   = datetime.now().hour
    is_today       = (selected_date == datetime.now().date())

    for i in range(24):
        # ----------------------------------------------------
        # 1. إضافة جديدة: التحقق من مواعيد الفتح والغلق
        # ----------------------------------------------------
        is_open = False
        if pitch.opening_hour < pitch.closing_hour:
            # الوضع الطبيعي (مثلاً بيفتح 8 الصبح ويقفل 11 بالليل)
            if pitch.opening_hour <= i < pitch.closing_hour:
                is_open = True
        elif pitch.opening_hour > pitch.closing_hour:
            # لو الملعب بيطبق لليوم التاني (مثلاً يفتح 6 مساءً ويقفل 3 الفجر)
            if i >= pitch.opening_hour or i < pitch.closing_hour:
                is_open = True
        else:
            # لو ساعة الفتح تساوي ساعة الغلق، هنعتبره فاتح 24 ساعة
            is_open = True

        # لو الساعة دي برة مواعيد العمل، تجاهلها وماتعرضهاش
        if not is_open:
            continue
        # ----------------------------------------------------

        # 2. جلب حالة الحجز (هل هو محجوز ولا متاح)
        status  = hours_status_map.get(i)
        
        # 3. التحقق إذا كان الوقت ده عدى خلاص في يومنا الحالي
        is_past = is_today and i <= current_hour

        # 4. تنسيق الوقت بالعربي
        if i == 0:      formatted_time = "12:00 ص"
        elif i < 12:    formatted_time = f"{i}:00 ص"
        elif i == 12:   formatted_time = "12:00 م"
        else:           formatted_time = f"{i-12}:00 م"

        # 5. حساب السعر المتغير (Dynamic Pricing)
        hour_price = pitch.price_per_hour
        for rule in pricing_rules_list:
            if rule.start_hour <= i < rule.end_hour:
                hour_price = rule.price
                break

        # 6. إضافة الساعة للقائمة اللي هتتبعت للـ Template
        hours_schedule.append({
            'hour_display': formatted_time,
            'hour_value':   i,
            'status':       status,
            'is_past':      is_past,
            'price':        hour_price,
        })

    # ----------------------------------------------------
    # باقي كود الدالة كما هو بدون أي تغيير
    # ----------------------------------------------------
    days_list = []
    today     = datetime.now().date()

    for i in range(14):
        day_date = today + timedelta(days=i)
        days_list.append({
            'full_date': day_date.strftime('%Y-%m-%d'),
            'day_name':  day_date.strftime('%A'),
            'display':   day_date.strftime('%d/%m'),
        })

    related_pitches = Pitch.objects.filter(location=pitch.location).exclude(id=pitch.id)[:3]

    return render(request, 'pitch_detail.html', {
        'pitch':           pitch,
        'days_list':       days_list,
        'selected_date':   selected_date.strftime('%Y-%m-%d'),
        'hours_schedule':  hours_schedule,
        'reviews':         reviews,
        'average_rating':  round(average_rating, 1),
        'review_count':    reviews.count(),
        'related_pitches': related_pitches,
    })


# ---------------------------------------------------------
# تأكيد الحجز
# ---------------------------------------------------------
@login_required(login_url='login')
def booking_confirm(request, pitch_id, hour):
    pitch    = get_object_or_404(Pitch, id=pitch_id)
    hour_int = int(hour)

    # ----------------------------------------------------
    # 1. الحماية الإضافية: التأكد أن الملعب فاتح في هذا الوقت
    # ----------------------------------------------------
    is_open = False
    if pitch.opening_hour < pitch.closing_hour:
        if pitch.opening_hour <= hour_int < pitch.closing_hour:
            is_open = True
    elif pitch.opening_hour > pitch.closing_hour:
        if hour_int >= pitch.opening_hour or hour_int < pitch.closing_hour:
            is_open = True
    else:
        is_open = True # إذا كانت ساعات الفتح والغلق متساوية (يُعتبر 24 ساعة)

    if not is_open:
        messages.error(request, "عذراً، الملعب مغلق في هذا الوقت ولا يمكن الحجز.")
        return redirect('pitch_detail', pitch_id=pitch.id)
    # ----------------------------------------------------

    date_str = request.GET.get('date')
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        selected_date = datetime.now().date()

    time_str = f"{hour_int:02d}:00"

    is_taken = Booking.objects.filter(
        pitch=pitch, date=selected_date,
        time=time_str, status__in=['Confirmed', 'Pending']
    ).exists()

    if is_taken:
        messages.error(request, "عذراً، هذا الموعد تم حجزه للتو!")
        return redirect('pitch_detail', pitch_id=pitch.id)

    today_bookings_count = Booking.objects.filter(
        user=request.user, date=selected_date
    ).exclude(status='Cancelled').count()

    if today_bookings_count >= 4:
        messages.error(request, "عذراً، لقد وصلت للحد الأقصى (4 ساعات) في اليوم.")
        return redirect('pitch_detail', pitch_id=pitch.id)

    final_price   = pitch.price_per_hour
    special_price = PitchPricing.objects.filter(
        pitch=pitch, start_hour__lte=hour_int, end_hour__gt=hour_int
    ).filter(Q(specific_date=selected_date) | Q(specific_date__isnull=True)).order_by('price').first()

    if special_price:
        final_price = special_price.price

    is_vip = Booking.objects.filter(user=request.user, status='Confirmed').count() >= 10

    if request.method == 'POST':
        real_time_count = Booking.objects.filter(
            user=request.user, date=selected_date
        ).exclude(status='Cancelled').count()

        if real_time_count >= 4:
            messages.error(request, "تنبيه: لديك 4 حجوزات بالفعل لهذا اليوم.")
            return redirect('pitch_detail', pitch_id=pitch.id)

        payment_type_choice = request.POST.get('payment_type', 'Full')

        if payment_type_choice == 'PayAtPitch' and not is_vip:
            messages.error(request, "خيار الدفع في الملعب متاح فقط للعملاء المميزين.")
            return redirect(request.path)

        form = PaymentForm(request.POST)
        if form.is_valid():
            booking = Booking.objects.create(
                pitch=pitch, user=request.user,
                date=selected_date, time=time_str,
                status='Pending', payment_type=payment_type_choice
            )
            payment                = form.save(commit=False)
            payment.booking        = booking
            method_from_post       = request.POST.get('pay', 'Cash')
            method_map             = {'voda': 'Vodafone', 'insta': 'Instapay', 'cash': 'Cash', 'fawry': 'Fawry'}
            payment.payment_method = method_map.get(method_from_post, 'Cash')
            payment.save()

            request.session['last_booking_code'] = booking.booking_code
            messages.success(request, "تم تسجيل الطلب! سيتم الإلغاء تلقائياً إذا لم يؤكد خلال 30 دقيقة.")
            return redirect('booking_success')
    else:
        form = PaymentForm()

    return render(request, 'booking_confirm.html', {
        'pitch':  pitch,
        'hour':   time_str,
        'date':   selected_date,
        'form':   form,
        'price':  final_price,
        'is_vip': is_vip,
    })

# ---------------------------------------------------------
# نجاح الحجز
# ---------------------------------------------------------
@login_required
def booking_success(request):
    booking_code = request.session.get('last_booking_code')
    booking      = None
    if booking_code:
        booking = Booking.objects.filter(booking_code=booking_code).first()
    return render(request, 'booking_success.html', {
        'booking_code': booking_code,
        'booking':      booking,
    })


# ---------------------------------------------------------
# الملف الشخصي
# ---------------------------------------------------------
@login_required
def user_profile(request):
    today    = timezone.now().date()
    upcoming = Booking.objects.filter(user=request.user, date__gte=today).order_by('date', 'time')
    past     = Booking.objects.filter(user=request.user, date__lt=today).order_by('-date', '-time')

    return render(request, 'user_profile.html', {
        'upcoming_bookings': upcoming,
        'past_bookings':     past,
        'user':              request.user,
    })


# ---------------------------------------------------------
# إلغاء الحجز
# ---------------------------------------------------------
@login_required
def cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    if booking.status != 'Cancelled':
        booking.status = 'Cancelled'
        booking.save()
        messages.success(request, "تم إلغاء الحجز بنجاح.")
    return redirect('user_profile')


# ---------------------------------------------------------
# تسجيل حساب جديد
# ---------------------------------------------------------
def signup(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "تم إنشاء الحساب!")
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})


# ---------------------------------------------------------
# من نحن
# ---------------------------------------------------------
def about_us(request):
    return render(request, 'about_us.html')