from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib import messages
from django.db.models import Avg, Q, Sum
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt
from .models import Pitch, Booking, Payment, Review, PitchPricing
from .forms import PaymentForm
import hmac
import hashlib
import json
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from .paymob import paymob_auth, create_order, create_payment_key, pay_with_wallet
from django.conf import settings
from django.http import JsonResponse
from decimal import Decimal
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

    # ✅ الجديد (مرة واحدة بس):
    return render(request, 'home.html', {
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
            # ✅ الكود الجديد:
            elif not Review.objects.filter(pitch=pitch, user=request.user).exists():
                rating = int(request.POST.get('rating', 5))
                comment = request.POST.get('comment', '')
                
                # التأكد إن التقييم بين 1 و 5
                if rating < 1:
                    rating = 1
                elif rating > 5:
                    rating = 5
                
                Review.objects.create(
                    pitch=pitch,
                    user=request.user,
                    rating=rating,
                    comment=comment,
                )
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

            method_from_post = request.POST.get('pay', 'Cash')

            # لو اختار محفظة إلكترونية → روح Paymob
            if method_from_post == 'wallet':
                phone = request.POST.get('wallet_phone', '')
                if not phone:
                    messages.error(request, "يرجى إدخال رقم المحفظة!")
                    booking.delete()
                    return redirect(request.path + f'?date={selected_date}')

                # حساب المبلغ بالقروش
                if payment_type_choice == 'Deposit':
                    amount = 5000  # 50 جنيه
                else:
                    amount = int(final_price * 100)

                try:
                    from .paymob import paymob_auth, create_order, create_payment_key, pay_with_wallet

                    auth_token = paymob_auth()
                    order_id = create_order(auth_token, amount, booking.booking_code)
                    payment_key = create_payment_key(auth_token, order_id, amount, request.user, phone)
                    redirect_url = pay_with_wallet(payment_key, phone)

                    # حفظ بيانات الدفع
                    Payment.objects.create(
                        booking=booking,
                        paymob_order_id=str(order_id),
                        amount_cents=amount,
                        payment_method='Vodafone',
                    )

                    if redirect_url:
                        # حفظ كود الحجز في الجلسة
                        request.session['last_booking_code'] = booking.booking_code
                        # وجّه العميل لصفحة الانتظار بدل Paymob مباشرة
                        return redirect('payment_pending', booking_code=booking.booking_code)
                    else:
                        messages.error(request, "حدث خطأ في بوابة الدفع. حاول تاني.")
                        booking.delete()
                        return redirect('pitch_detail', pitch_id=pitch.id)

                except Exception as e:
                    messages.error(request, f"خطأ في الدفع: {str(e)}")
                    booking.delete()
                    return redirect('pitch_detail', pitch_id=pitch.id)

            # لو اختار طريقة دفع تانية (يدوي زي ما كان)
            else:
                payment = form.save(commit=False)
                payment.booking = booking
                method_map = {'voda': 'Vodafone', 'insta': 'Instapay', 'cash': 'Cash', 'fawry': 'Fawry'}
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
    booking = None
    payment = None
    if booking_code:
        booking = Booking.objects.filter(booking_code=booking_code).first()
        if booking:
            payment = Payment.objects.filter(booking=booking).first()

    return render(request, 'booking_success.html', {
        'booking_code': booking_code,
        'booking': booking,
        'payment': payment,
    })
# ---------------------------------------------------------
# صفحة انتظار الدفع
# ---------------------------------------------------------
@login_required
def payment_pending(request, booking_code):
    booking = get_object_or_404(Booking, booking_code=booking_code, user=request.user)
    payment = Payment.objects.filter(booking=booking).first()

    return render(request, 'payment_pending.html', {
        'booking': booking,
        'payment': payment,
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

# ---------------------------------------------------------
# Paymob: بدء عملية الدفع بالمحفظة
# ---------------------------------------------------------
@login_required
def paymob_wallet_pay(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    phone = request.POST.get('wallet_phone', '')

    if not phone:
        messages.error(request, "يرجى إدخال رقم المحفظة!")
        return redirect('booking_confirm', pitch_id=booking.pitch.id, hour=int(booking.time.split(':')[0]))

    # حساب المبلغ بالقروش
    if booking.payment_type == 'Deposit':
        amount = 5000  # 50 جنيه = 5000 قرش
    else:
        amount = int(booking.pitch.price_per_hour * 100)

    # خطوات Paymob
    try:
        auth_token = paymob_auth()
        order_id = create_order(auth_token, amount, booking.booking_code)
        payment_key = create_payment_key(auth_token, order_id, amount, request.user, phone)
        redirect_url = pay_with_wallet(payment_key, phone)

        # حفظ بيانات الدفع
        payment, created = Payment.objects.get_or_create(booking=booking)
        payment.paymob_order_id = str(order_id)
        payment.amount_cents = amount
        payment.payment_method = 'Vodafone'
        payment.save()

        if redirect_url:
            return redirect(redirect_url)
        else:
            messages.error(request, "حدث خطأ في بوابة الدفع. حاول تاني.")
            return redirect('pitch_detail', pitch_id=booking.pitch.id)

    except Exception as e:
        messages.error(request, f"خطأ في الدفع: {str(e)}")
        return redirect('pitch_detail', pitch_id=booking.pitch.id)


# ---------------------------------------------------------
# Paymob: Callback بعد الدفع (Paymob يبعت النتيجة هنا)
# ---------------------------------------------------------
@csrf_exempt
def paymob_callback(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            obj = data.get('obj', {})
            order_id = str(obj.get('order', {}).get('id', ''))
            success = obj.get('success', False)
            hmac_received = request.GET.get('hmac', '')

            # التحقق من HMAC
            hmac_string = (
                str(obj.get('amount_cents', '')) +
                str(obj.get('created_at', '')) +
                str(obj.get('currency', '')) +
                str(obj.get('error_occured', '')) +
                str(obj.get('has_parent_transaction', '')) +
                str(obj.get('id', '')) +
                str(obj.get('integration_id', '')) +
                str(obj.get('is_3d_secure', '')) +
                str(obj.get('is_auth', '')) +
                str(obj.get('is_capture', '')) +
                str(obj.get('is_refunded', '')) +
                str(obj.get('is_standalone_payment', '')) +
                str(obj.get('is_voided', '')) +
                str(obj.get('order', {}).get('id', '')) +
                str(obj.get('owner', '')) +
                str(obj.get('pending', '')) +
                str(obj.get('source_data', {}).get('pan', '')) +
                str(obj.get('source_data', {}).get('sub_type', '')) +
                str(obj.get('source_data', {}).get('type', '')) +
                str(obj.get('success', ''))
            )

            calculated_hmac = hmac.new(
                settings.PAYMOB_HMAC_SECRET.encode('utf-8'),
                hmac_string.encode('utf-8'),
                hashlib.sha512
            ).hexdigest()

            if calculated_hmac == hmac_received and success:
                # الدفع نجح! حدّث حالة الحجز
                payment = Payment.objects.filter(paymob_order_id=order_id).first()
                if payment:
                    payment.is_verified = True
                    payment.transaction_id = str(obj.get('id', ''))
                    payment.save()
                    payment.booking.status = 'Confirmed'
                    payment.booking.save()

            return HttpResponse(status=200)

        except Exception:
            return HttpResponse(status=500)

    return HttpResponse(status=405)


# ---------------------------------------------------------
# Paymob: صفحة بعد الدفع (المستخدم يرجع هنا)
# ---------------------------------------------------------
def paymob_response(request):
    success = request.GET.get('success', 'false')
    order_id = request.GET.get('order', '')

    if success == 'true':
        payment = Payment.objects.filter(paymob_order_id=order_id).first()
        if payment:
            request.session['last_booking_code'] = payment.booking.booking_code
            return redirect('booking_success')

    messages.error(request, "الدفع لم يتم بنجاح. حاول تاني أو اختر طريقة دفع تانية.")
    return redirect('home')
# ---------------------------------------------------------
# API: التحقق من حالة الدفع (للصفحة المنتظرة)
# ---------------------------------------------------------

@login_required
def check_payment_status(request, booking_code):
    booking = Booking.objects.filter(
        booking_code=booking_code,
        user=request.user
    ).first()

    if booking:
        return JsonResponse({
            'status': booking.status,
            'booking_code': booking.booking_code,
        })
    return JsonResponse({'status': 'not_found'}, status=404)

# ═══════════════════════════════════════════════════════
# داشبورد صاحب الملعب
# ═══════════════════════════════════════════════════════

@login_required
def owner_dashboard(request):
    """الصفحة الرئيسية لصاحب الملعب"""
    pitches = Pitch.objects.filter(owner=request.user)

    if not pitches.exists():
        messages.error(request, "ليس لديك ملاعب مسجلة في حسابك.")
        return redirect('home')

    today = timezone.now().date()

    stats = {
        'total_pitches': pitches.count(),
        'today_bookings': Booking.objects.filter(
            pitch__in=pitches, date=today
        ).exclude(status='Cancelled').count(),
        'pending_bookings': Booking.objects.filter(
            pitch__in=pitches, status='Pending'
        ).count(),
        'confirmed_bookings': Booking.objects.filter(
            pitch__in=pitches, status='Confirmed',
            date__gte=today
        ).count(),
    }

    # حساب أرباح الأسبوع
    weekly_payments = Payment.objects.filter(
        booking__pitch__in=pitches,
        booking__status='Confirmed',
        booking__date__gte=today - timedelta(days=7),
        is_verified=True
    )
    total_cents = weekly_payments.aggregate(total=Sum('amount_cents'))['total'] or 0
    stats['weekly_earnings'] = Decimal(total_cents) / 100

    # حجوزات اليوم لكل ملعب
    today_schedule = []
    for pitch in pitches:
        pitch_bookings = Booking.objects.filter(
            pitch=pitch, date=today
        ).exclude(status='Cancelled').order_by('time')
        today_schedule.append({
            'pitch': pitch,
            'bookings': pitch_bookings,
            'count': pitch_bookings.count(),
        })

    return render(request, 'owner/dashboard.html', {
        'pitches': pitches,
        'stats': stats,
        'today': today,
        'today_schedule': today_schedule,
    })


# ───────────────────────────────────────────
# 1. جدول الحجوزات (مين جاي النهاردة؟)
# ───────────────────────────────────────────
@login_required
def owner_schedule(request, pitch_id):
    pitch = get_object_or_404(Pitch, id=pitch_id, owner=request.user)

    date_str = request.GET.get('date')
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        selected_date = datetime.now().date()

    bookings = Booking.objects.filter(
        pitch=pitch, date=selected_date
    ).exclude(status='Cancelled').order_by('time')

    # تفاصيل الدفع لكل حجز
    bookings_with_details = []
    for booking in bookings:
        payment = Payment.objects.filter(booking=booking).first()

        if booking.payment_type == 'Deposit':
            paid_online = Decimal('50.00')
            remaining = pitch.price_per_hour - paid_online
        elif booking.payment_type == 'Full':
            paid_online = pitch.price_per_hour
            remaining = Decimal('0.00')
        else:
            paid_online = Decimal('0.00')
            remaining = pitch.price_per_hour

        bookings_with_details.append({
            'booking': booking,
            'payment': payment,
            'paid_online': paid_online,
            'remaining': remaining,
            'is_verified': payment.is_verified if payment else False,
        })

    # ساعات العمل مع حالة كل ساعة
    booked_hours = {int(b.time.split(':')[0]): b for b in bookings}
    hours_schedule = []

    for i in range(24):
        # التحقق من مواعيد العمل
        is_open = False
        if pitch.opening_hour < pitch.closing_hour:
            if pitch.opening_hour <= i < pitch.closing_hour:
                is_open = True
        elif pitch.opening_hour > pitch.closing_hour:
            if i >= pitch.opening_hour or i < pitch.closing_hour:
                is_open = True
        else:
            is_open = True

        if not is_open:
            continue

        # تنسيق الوقت
        if i == 0:
            formatted_time = "12:00 ص"
        elif i < 12:
            formatted_time = f"{i}:00 ص"
        elif i == 12:
            formatted_time = "12:00 م"
        else:
            formatted_time = f"{i - 12}:00 م"

        booking_obj = booked_hours.get(i)
        hours_schedule.append({
            'hour_value': i,
            'hour_display': formatted_time,
            'booking': booking_obj,
            'is_booked': booking_obj is not None,
            'is_manual': booking_obj.is_manual if booking_obj else False,
        })

    # أيام للتنقل
    days_list = []
    today = datetime.now().date()
    for i in range(14):
        day_date = today + timedelta(days=i)
        days_list.append({
            'full_date': day_date.strftime('%Y-%m-%d'),
            'day_name': day_date.strftime('%A'),
            'display': day_date.strftime('%d/%m'),
        })

    return render(request, 'owner/schedule.html', {
        'pitch': pitch,
        'bookings_with_details': bookings_with_details,
        'hours_schedule': hours_schedule,
        'selected_date': selected_date.strftime('%Y-%m-%d'),
        'days_list': days_list,
    })


# ───────────────────────────────────────────
# 3. إغلاق ميعاد يدوياً (Manual Block)
# ───────────────────────────────────────────
@login_required
def owner_block_hour(request, pitch_id):
    pitch = get_object_or_404(Pitch, id=pitch_id, owner=request.user)

    if request.method == 'POST':
        date_str = request.POST.get('date')
        hour = request.POST.get('hour')
        customer_name = request.POST.get('customer_name', '')
        customer_phone = request.POST.get('customer_phone', '')

        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            hour_int = int(hour)
            time_str = f"{hour_int:02d}:00"

            exists = Booking.objects.filter(
                pitch=pitch, date=selected_date, time=time_str
            ).exclude(status='Cancelled').exists()

            if exists:
                messages.error(request, "الميعاد ده محجوز بالفعل!")
            else:
                Booking.objects.create(
                    pitch=pitch,
                    user=request.user,
                    date=selected_date,
                    time=time_str,
                    status='Confirmed',
                    payment_type='PayAtPitch',
                    is_manual=True,
                    customer_name=customer_name,
                    customer_phone=customer_phone,
                )
                messages.success(request, f"تم حجز الساعة {time_str} يدوياً ✅")

        except (ValueError, TypeError):
            messages.error(request, "بيانات غير صحيحة!")

    return redirect(f'/owner/pitch/{pitch.id}/schedule/?date={date_str}')


# ───────────────────────────────────────────
# 4. فتح ميعاد يدوي (Unblock)
# ───────────────────────────────────────────
@login_required
def owner_unblock_hour(request, booking_id):
    booking = get_object_or_404(
        Booking, id=booking_id,
        pitch__owner=request.user,
        is_manual=True
    )

    if request.method == 'POST':
        selected_date = booking.date.strftime('%Y-%m-%d')
        pitch_id = booking.pitch.id
        booking.status = 'Cancelled'
        booking.save()
        messages.success(request, "تم فتح الميعاد ✅")
        return redirect(f'/owner/pitch/{pitch_id}/schedule/?date={selected_date}')

    return redirect('owner_dashboard')


# ─────────────────────────��─────────────────
# 5. ملخص الأرباح (Earnings)
# ───────────────────────────────────────────
@login_required
def owner_earnings(request):
    pitches = Pitch.objects.filter(owner=request.user)

    if not pitches.exists():
        messages.error(request, "ليس لديك ملاعب مسجلة.")
        return redirect('home')

    today = timezone.now().date()

    # أرباح لكل فترة
    periods = {
        'today': today,
        'this_week': today - timedelta(days=7),
        'this_month': today - timedelta(days=30),
    }

    earnings = {}
    for period_name, start_date in periods.items():
        verified = Payment.objects.filter(
            booking__pitch__in=pitches,
            booking__status='Confirmed',
            booking__date__gte=start_date,
            is_verified=True
        )
        total_cents = verified.aggregate(total=Sum('amount_cents'))['total'] or 0
        earnings[period_name] = {
            'amount': Decimal(total_cents) / 100,
            'count': verified.count(),
        }

    # تفصيل لكل ملعب
    pitch_earnings = []
    for pitch in pitches:
        pitch_payments = Payment.objects.filter(
            booking__pitch=pitch,
            booking__status='Confirmed',
            is_verified=True,
            booking__date__gte=today - timedelta(days=30),
        )
        total = pitch_payments.aggregate(total=Sum('amount_cents'))['total'] or 0
        pitch_earnings.append({
            'pitch': pitch,
            'monthly_earnings': Decimal(total) / 100,
            'booking_count': pitch_payments.count(),
        })

    return render(request, 'owner/earnings.html', {
        'earnings': earnings,
        'pitch_earnings': pitch_earnings,
    })