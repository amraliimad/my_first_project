from django import forms
from .models import Payment
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["transaction_id"]
        labels = {
            "transaction_id": "رقم عملية تحويل فودافون كاش",
        }
        widgets = {
            "transaction_id": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "أدخل رقم العملية هنا...",
                }
            ),
        }

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class ExtendedSignupForm(UserCreationForm):
    # 1. تحويل حقل اسم المستخدم ليكون "البريد الإلكتروني"
    username = forms.EmailField(
        label="البريد الإلكتروني", 
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'example@gmail.com', 'class': 'form-control'})
    )
    
    # 2. إضافة حقول الاسم (الأول، الثاني، الأخير)
    first_name = forms.CharField(label="الاسم الأول", required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    middle_name = forms.CharField(label="الاسم الثاني", required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(label="الاسم الأخير", required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    
    # 3. رقم الموبايل
    phone_number = forms.CharField(label="رقم الموبايل (واتساب)", required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta(UserCreationForm.Meta):
        model = User
        # الحقول المرتبطة بجدول User الأساسي فقط
        fields = ('username', 'first_name', 'last_name') 

    # ترتيب ظهور الحقول في صفحة التسجيل
    field_order = ['username', 'first_name', 'middle_name', 'last_name', 'phone_number']

    def clean_username(self):
        # التأكد إن الإيميل مش مسجل قبل كده في الموقع
        email = self.cleaned_data.get('username')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("هذا البريد الإلكتروني مسجل بالفعل، يرجى تسجيل الدخول.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        # نسخ الإيميل لحقل الـ email في الداتابيز عشان نقدر نراسله بعدين
        user.email = self.cleaned_data['username']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            # حفظ الاسم الثاني والموبايل في جدول البروفايل
            user.profile.middle_name = self.cleaned_data.get('middle_name')
            user.profile.phone_number = self.cleaned_data.get('phone_number')
            user.profile.save()
        return user
class UserProfileUpdateForm(forms.Form):
    first_name = forms.CharField(label="الاسم الأول", required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    middle_name = forms.CharField(label="الاسم الثاني", required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(label="الاسم الأخير", required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    phone_number = forms.CharField(label="رقم الموبايل (واتساب)", required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
