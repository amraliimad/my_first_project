from django import forms
from .models import Payment


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

