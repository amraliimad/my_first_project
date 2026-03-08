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
from .forms import ExtendedSignupForm 
from .forms import PaymentForm, ExtendedSignupForm, UserProfileUpdateForm
from .models import Pitch, Booking, Payment, Review, PitchPricing, UserProfile
import csv
from decimal import Decimal
from django.http import HttpResponse
from django.contrib.auth.models import User
from .google_sheets import add_booking_to_sheet


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
@login_required(login_url='login')
def user_profile(request):
    user = request.user
    
    # 1. التأكد إن المستخدم له بروفايل (عشان نتجنب أي خطأ للحسابات القديمة)
    if hasattr(user, 'profile'):
        profile = user.profile
    else:
        profile = UserProfile.objects.create(user=user)

    # 2. معالجة فورم تعديل البيانات
    if request.method == 'POST':
        form = UserProfileUpdateForm(request.POST)
        if form.is_valid():
            # حفظ بيانات جدول User
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.save()
            
            # حفظ بيانات جدول UserProfile
            profile.middle_name = form.cleaned_data['middle_name']
            profile.phone_number = form.cleaned_data['phone_number']
            profile.save()
            
            messages.success(request, "تم تحديث بياناتك بنجاح! 💾")
            return redirect('user_profile')
    else:
        # تعبئة الفورم ببيانات المستخدم الحالية وقت فتح الصفحة
        form = UserProfileUpdateForm(initial={
            'first_name': user.first_name,
            'middle_name': profile.middle_name,
            'last_name': user.last_name,
            'phone_number': profile.phone_number,
        })

    # 3. جلب الحجوزات بنفس طريقتك القديمة الممتازة
    today    = timezone.now().date()
    upcoming = Booking.objects.filter(user=user, date__gte=today).order_by('date', 'time')
    past     = Booking.objects.filter(user=user, date__lt=today).order_by('-date', '-time')
    
    return render(request, 'user_profile.html', {
        'upcoming_bookings': upcoming,
        'past_bookings':     past,
        'user':              user,
        'form':              form,  # ضفنا الفورم هنا عشان تتبعت للـ HTML
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
        # التعديل هنا: استخدمنا الفورم الجديدة
        form = ExtendedSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "تم إنشاء الحساب بنجاح !")
            return redirect('home')
    else:
        # التعديل هنا كمان
        form = ExtendedSignupForm()
        
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

            # 🛠️ الدالة المنقذة: بتحول الـ Boolean لحروف صغيرة زي ما Paymob عايز بالظبط
            def bool_to_str(val):
                if isinstance(val, bool):
                    return str(val).lower()
                return str(val)

            # تجميع البيانات بنفس الترتيب الأبجدي الصارم لـ Paymob
            hmac_string = (
                bool_to_str(obj.get('amount_cents', '')) +
                bool_to_str(obj.get('created_at', '')) +
                bool_to_str(obj.get('currency', '')) +
                bool_to_str(obj.get('error_occured', '')) +
                bool_to_str(obj.get('has_parent_transaction', '')) +
                bool_to_str(obj.get('id', '')) +
                bool_to_str(obj.get('integration_id', '')) +
                bool_to_str(obj.get('is_3d_secure', '')) +
                bool_to_str(obj.get('is_auth', '')) +
                bool_to_str(obj.get('is_capture', '')) +
                bool_to_str(obj.get('is_refunded', '')) +
                bool_to_str(obj.get('is_standalone_payment', '')) +
                bool_to_str(obj.get('is_voided', '')) +
                bool_to_str(obj.get('order', {}).get('id', '')) +
                bool_to_str(obj.get('owner', '')) +
                bool_to_str(obj.get('pending', '')) +
                bool_to_str(obj.get('source_data', {}).get('pan', '')) +
                bool_to_str(obj.get('source_data', {}).get('sub_type', '')) +
                bool_to_str(obj.get('source_data', {}).get('type', '')) +
                bool_to_str(obj.get('success', ''))
            )

            # التشفير
            calculated_hmac = hmac.new(
                settings.PAYMOB_HMAC_SECRET.encode('utf-8'),
                hmac_string.encode('utf-8'),
                hashlib.sha512
            ).hexdigest()

            # التحقق النهائي
            if calculated_hmac == hmac_received and success:
                payment = Payment.objects.filter(paymob_order_id=order_id).first()
                if payment:
                    payment.is_verified = True
                    payment.transaction_id = str(obj.get('id', ''))
                    payment.save()
                    
                    # الفلوس دخلت الحساب بجد، نأكد الحجز
                    payment.booking.status = 'Confirmed'
                    payment.booking.save()
                                        # إرسال البيانات لجوجل شيت
                    add_booking_to_sheet(payment.booking)
            return HttpResponse(status=200)

        except Exception as e:
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
                                # إرسال البيانات لجوجل شيت
                new_booking = Booking.objects.get(pitch=pitch, date=selected_date, time=time_str)
                add_booking_to_sheet(new_booking)

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
# ═══════════════════════════════════════════════════════════════════════════
#  SECTION: داشبورد الأرباح المالية لصاحب الملعب
#  يُستبدل به كل دوال owner_earnings الموجودة في views.py
# ═══════════════════════════════════════════════════════════════════════════

def _get_amount_paid_online(booking):
    """
    دالة مساعدة: تحسب المبلغ المدفوع أونلاين لحجز معين.
    تعتمد على سجل الدفع (Payment) المرتبط بالحجز.
    """
    try:
        payment = booking.payment_details
        if payment.is_verified and payment.amount_cents > 0:
            return Decimal(payment.amount_cents) / Decimal('100')
    except Exception:
        pass
    return Decimal('0.00')


def _resolve_owner(request):
    """
    دالة مساعدة: تحدد صاحب الملعب المقصود.
    - لو المستخدم الحالي superuser وبعت owner_id → نستخدم ذلك الـ owner
    - غير كده → نستخدم request.user نفسه
    """
    if request.user.is_superuser:
        owner_id = request.GET.get('owner_id') or request.POST.get('owner_id')
        if owner_id:
            try:
                return User.objects.get(id=int(owner_id))
            except (User.DoesNotExist, ValueError):
                pass
    return request.user


@login_required
def owner_earnings(request):
    """
    داشبورد الأرباح المالية - 3 أقسام:
      A) وردية اليوم (Cash Drawer Focus)
      B) الرصيد المتراكم (Unsettled Ledger)
      C) تفاصيل العمولة (Commission Breakdown - accordion)
    """
    owner  = _resolve_owner(request)
    pitches = Pitch.objects.filter(owner=owner)

    if not pitches.exists():
        messages.error(request, "ليس لديك ملاعب مسجلة في حسابك.")
        return redirect('home')

    today = timezone.localtime().date()

    # ─────────────────────────────────────────────────────────
    # SECTION A ➜ وردية اليوم
    # ─────────────────────────────────────────────────────────
    today_bookings = (
        Booking.objects
        .filter(pitch__in=pitches, date=today)
        .exclude(status__in=['Cancelled', 'No-Show'])
        .select_related('pitch', 'payment_details')
        .order_by('time')
    )

    today_total_sales    = Decimal('0.00')
    today_cash_drawer    = Decimal('0.00')
    today_online_holding = Decimal('0.00')

    today_booking_rows = []
    for booking in today_bookings:
        full_price       = booking.pitch.price_per_hour
        paid_online      = _get_amount_paid_online(booking)
        cash_portion     = full_price - paid_online

        today_total_sales    += full_price
        today_cash_drawer    += cash_portion
        today_online_holding += paid_online

        today_booking_rows.append({
            'booking':    booking,
            'full_price': full_price,
            'paid_online': paid_online,
            'cash_portion': cash_portion,
        })

    # ─────────────────────────────────────────────────────────
    # SECTION B ➜ الرصيد المتراكم (Unsettled Ledger)
    #   فقط: status='Played' AND is_settled=False
    # ─────────────────────────────────────────────────────────
    unsettled_qs = (
        Booking.objects
        .filter(pitch__in=pitches, status='Played', is_settled=False)
        .select_related('pitch', 'payment_details')
        .order_by('-date', '-time')
    )

    total_online_collected = Decimal('0.00')
    total_commission       = Decimal('0.00')

    for booking in unsettled_qs:
        full_price       = booking.pitch.price_per_hour
        commission_rate  = booking.pitch.commission_percentage / Decimal('100')
        commission_amt   = round(full_price * commission_rate, 2)

        total_commission        += commission_amt
        total_online_collected  += _get_amount_paid_online(booking)

    net_settleable = total_online_collected - total_commission

    # أرشيف التسويات السابقة (is_settled=True)
    settled_qs = (
        Booking.objects
        .filter(pitch__in=pitches, status='Played', is_settled=True)
        .select_related('pitch', 'payment_details')
        .order_by('-date')
    )

    past_settled_total   = Decimal('0.00')
    past_settled_commission = Decimal('0.00')
    for booking in settled_qs:
        full_price      = booking.pitch.price_per_hour
        commission_rate = booking.pitch.commission_percentage / Decimal('100')
        past_settled_commission += round(full_price * commission_rate, 2)
        past_settled_total      += _get_amount_paid_online(booking)

    past_settled_net = past_settled_total - past_settled_commission

    # ─────────────────────────────────────────────────────────
    # SECTION C ➜ تفاصيل العمولة (Commission Breakdown)
    # ─────────────────────────────────────────────────────────
    commission_rows = []
    for booking in unsettled_qs:
        full_price      = booking.pitch.price_per_hour
        commission_rate = booking.pitch.commission_percentage / Decimal('100')
        commission_amt  = round(full_price * commission_rate, 2)

        commission_rows.append({
            'booking':        booking,
            'full_price':     full_price,
            'commission_pct': booking.pitch.commission_percentage,
            'commission_amt': commission_amt,
            'net_to_owner':   round(full_price - commission_amt, 2),
        })

    return render(request, 'owner/earnings.html', {
        # meta
        'today':          today,
        'owner':          owner,
        'pitches':        pitches,
        'is_superuser':   request.user.is_superuser,

        # Section A
        'today_total_sales':    today_total_sales,
        'today_cash_drawer':    today_cash_drawer,
        'today_online_holding': today_online_holding,
        'today_booking_rows':   today_booking_rows,
        'today_count':          len(today_booking_rows),

        # Section B
        'total_online_collected':  total_online_collected,
        'total_commission':        total_commission,
        'net_settleable':          net_settleable,
        'unsettled_count':         unsettled_qs.count(),
        'settled_qs':              settled_qs[:30],        # آخر 30 حجز مُسوَّى
        'past_settled_total':      past_settled_total,
        'past_settled_commission': past_settled_commission,
        'past_settled_net':        past_settled_net,

        # Section C
        'commission_rows': commission_rows,
    })


# ─────────────────────────────────────────────────────────────────────────
# تسوية الحساب (Admin Only)
# ─────────────────────────────────────────────────────────────────────────
@login_required
def settle_account(request):
    """
    POST only. متاح للـ superuser فقط (RBAC).
    يُحوِّل كل حجوزات status='Played' + is_settled=False
    إلى is_settled=True للملاعب المملوكة لـ owner_id.
    """
    if not request.user.is_superuser:
        messages.error(request, "⛔ هذا الإجراء متاح للمشرفين فقط.")
        return redirect('owner_earnings')

    if request.method == 'POST':
        owner_id = request.POST.get('owner_id')
        try:
            owner   = User.objects.get(id=int(owner_id))
            pitches = Pitch.objects.filter(owner=owner)
            count   = Booking.objects.filter(
                pitch__in=pitches,
                status='Played',
                is_settled=False
            ).update(is_settled=True)

            messages.success(
                request,
                f"✅ تمت تسوية {count} حجز بنجاح لصاحب الملعب: {owner.get_full_name() or owner.username}"
            )
        except (User.DoesNotExist, ValueError, TypeError):
            messages.error(request, "⛔ بيانات غير صحيحة - لم تتم التسوية.")

    return redirect(f"{request.build_absolute_uri('/')[:-1]}{'/owner/earnings/'}?owner_id={owner_id}")


# ─────────────────────────────────────────────────────────────────────────
# تصدير CSV لتفاصيل العمولة
# ─────────────────────────────────────────────────────────────────────────
@login_required
def owner_earnings_export_csv(request):
    """
    يُصدِّر تفاصيل العمولة للحجوزات غير المسوَّاة (Played + is_settled=False)
    كملف CSV جاهز للفتح في Excel.
    """
    owner   = _resolve_owner(request)
    pitches = Pitch.objects.filter(owner=owner)

    if not pitches.exists():
        messages.error(request, "ليس لديك ملاعب مسجلة.")
        return redirect('owner_earnings')

    unsettled_qs = (
        Booking.objects
        .filter(pitch__in=pitches, status='Played', is_settled=False)
        .select_related('pitch', 'payment_details')
        .order_by('-date', '-time')
    )

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="commission_details.csv"'

    writer = csv.writer(response)
    # الترويسة
    writer.writerow([
        'التاريخ', 'الوقت', 'كود الحجز', 'الملعب',
        'السعر الكامل (ج.م)', 'نسبة العمولة (%)',
        'مبلغ العمولة (ج.م)', 'الصافي لصاحب الملعب (ج.م)'
    ])

    for booking in unsettled_qs:
        full_price      = booking.pitch.price_per_hour
        commission_rate = booking.pitch.commission_percentage / Decimal('100')
        commission_amt  = round(full_price * commission_rate, 2)
        net_to_owner    = round(full_price - commission_amt, 2)

        writer.writerow([
            booking.date.strftime('%Y-%m-%d'),
            booking.time,
            booking.booking_code,
            booking.pitch.name,
            full_price,
            booking.pitch.commission_percentage,
            commission_amt,
            net_to_owner,
        ])

    return response
# ---------------------------------------------------------
# الدالة الجديدة: تأكيد اللعب أو عدم الحضور من صاحب الملعب
# ---------------------------------------------------------
@login_required
def owner_update_booking_status(request, booking_id):
    # التأكد أن الحجز يخص ملعب يملكه هذا المستخدم
    booking = get_object_or_404(Booking, id=booking_id, pitch__owner=request.user)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in ['Played', 'No-Show']:
            booking.status = new_status
            booking.save()
            
            if new_status == 'Played':
                messages.success(request, f"تم تأكيد استلام المبلغ ولعب المباراة بنجاح ✅")
            else:
                messages.warning(request, f"تم تسجيل (عدم حضور) للعميل وتفريغ الملعب ❌")
                
    # العودة لنفس يوم الجدول
    selected_date = booking.date.strftime('%Y-%m-%d')
    return redirect(f'/owner/pitch/{booking.pitch.id}/schedule/?date={selected_date}')


# ───────────────────────────────────────────
# 5. ملخص الأرباح (Earnings) - مُعدلة لتشمل العمولة المتغيرة
# ───────────────────────────────────────────
@login_required
def owner_earnings(request):
    from decimal import Decimal # تأكد من وجودها
    
    pitches = Pitch.objects.filter(owner=request.user)

    if not pitches.exists():
        messages.error(request, "ليس لديك ملاعب مسجلة.")
        return redirect('home')

    today = timezone.localtime().date() # تم إصلاح التوقيت

    periods = {
        'today': today,
        'this_week': today - timedelta(days=7),
        'this_month': today - timedelta(days=30),
    }

    earnings = {}
    for period_name, start_date in periods.items():
        # نأتي بالمدفوعات الأونلاين للحجوزات المؤكدة أو التي تم لعبها
        verified_payments = Payment.objects.filter(
            booking__pitch__in=pitches,
            booking__status__in=['Confirmed', 'Played'], 
            booking__date__gte=start_date,
            is_verified=True
        )
        
        total_net_for_owner = Decimal('0.00')
        
        for payment in verified_payments:
            amount_paid_online = Decimal(payment.amount_cents) / Decimal('100')
            
            # حساب عمولة المنصة بناءً على نسبة هذا الملعب (مثلاً 5%)
            commission_rate = payment.booking.pitch.commission_percentage / Decimal('100')
            platform_fee = amount_paid_online * commission_rate
            
            # الصافي لصاحب الملعب من المدفوعات الأونلاين
            owner_net = amount_paid_online - platform_fee
            total_net_for_owner += owner_net

        earnings[period_name] = {
            'amount': round(total_net_for_owner, 2),
            'count': verified_payments.count(),
        }

    # تفصيل لكل ملعب
    pitch_earnings = []
    for pitch in pitches:
        pitch_payments = Payment.objects.filter(
            booking__pitch=pitch,
            booking__status__in=['Confirmed', 'Played'],
            is_verified=True,
            booking__date__gte=today - timedelta(days=30),
        )
        
        pitch_net_total = Decimal('0.00')
        commission_rate = pitch.commission_percentage / Decimal('100')
        
        for payment in pitch_payments:
            amount = Decimal(payment.amount_cents) / Decimal('100')
            fee = amount * commission_rate
            pitch_net_total += (amount - fee)

        pitch_earnings.append({
            'pitch': pitch,
            'monthly_earnings': round(pitch_net_total, 2),
            'booking_count': pitch_payments.count(),
        })

    return render(request, 'owner/earnings.html', {
        'earnings': earnings,
        'pitch_earnings': pitch_earnings,
         'owner': request.user,
    })
