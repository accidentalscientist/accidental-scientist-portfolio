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
    # Honeypot — invisible to humans (hidden off-screen via CSS), bots fill it.
    # If it arrives non-empty, the view silently discards the submission.
    website = forms.CharField(
        required=False,
        label='Website',
        widget=forms.TextInput(attrs={
            'autocomplete': 'off',
            'tabindex': '-1',
            'class': 'hp-field',
        })
    )
