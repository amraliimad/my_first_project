from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
import re # لإستخدام التعبيرات القياسية (Regex) في التحقق من رقم الهاتف
from .models import Payment

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["transaction_id"]
        labels = {
            "transaction_id": "رقم العملية (اختياري في حالة الدفع اليدوي)",
        }
        widgets = {
            "transaction_id": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "مثال: رقم تحويل فودافون كاش (اختياري)",
                }
            ),
        }
    
    # 🆕 جعل الحقل اختياري لتفادي أخطاء الحفظ لو اختار "دفع في الملعب"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['transaction_id'].required = False

class ExtendedSignupForm(UserCreationForm):
    username = forms.EmailField(
        label="البريد الإلكتروني", 
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'example@gmail.com', 'class': 'form-control'})
    )
    
    first_name = forms.CharField(label="الاسم الأول", required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    middle_name = forms.CharField(label="الاسم الثاني", required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(label="الاسم الأخير", required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    
    phone_number = forms.CharField(
        label="رقم الموبايل (واتساب)", 
        required=True, 
        widget=forms.TextInput(attrs={'placeholder': 'مثال: 01012345678', 'class': 'form-control'})
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name') 

    field_order = ['username', 'first_name', 'middle_name', 'last_name', 'phone_number']

    def clean_username(self):
        email = self.cleaned_data.get('username')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("هذا البريد الإلكتروني مسجل بالفعل، يرجى تسجيل الدخول.")
        return email

    # 🆕 التحقق من صحة رقم الهاتف المصري (أهمية قصوى لـ Paymob)
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if not re.match(r'^01[0125][0-9]{8}$', phone):
            raise forms.ValidationError("يرجى إدخال رقم موبايل مصري صحيح مكون من 11 رقم (مثال: 010...).")
        return phone

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['username']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            user.profile.middle_name = self.cleaned_data.get('middle_name')
            user.profile.phone_number = self.cleaned_data.get('phone_number')
            user.profile.save()
        return user


class UserProfileUpdateForm(forms.Form):
    first_name = forms.CharField(label="الاسم الأول", required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    middle_name = forms.CharField(label="الاسم الثاني", required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(label="الاسم الأخير", required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    phone_number = forms.CharField(
        label="رقم الموبايل (واتساب)", 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    # 🆕 التحقق من صحة رقم الهاتف عند تعديل البروفايل أيضاً
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone and not re.match(r'^01[0125][0-9]{8}$', phone):
            raise forms.ValidationError("يرجى إدخال رقم موبايل مصري صحيح مكون من 11 رقم.")
        return phone
