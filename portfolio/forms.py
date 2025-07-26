from django import forms

class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        label='Your Name',
        widget=forms.TextInput(attrs={'placeholder': 'Rick Sanchez'})
    )
    email = forms.EmailField(
        label='Your Email',
        widget=forms.EmailInput(attrs={'placeholder': 'rick.sanchez@gmail.com'})
    )
    message = forms.CharField(
        label='Message',
        widget=forms.Textarea(attrs={'placeholder': 'Dear BirdPerson...'})
    )
