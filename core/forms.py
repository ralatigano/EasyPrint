from django import forms
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm
from .models import Usuario

# Formulario para registrar usuarios.


class RegistroUsuarioForm(UserCreationForm):
    first_name = forms.CharField(
        label='Nombre', max_length=150, required=True)
    last_name = forms.CharField(
        label='Apellido', max_length=150, required=True)
    email = forms.EmailField(
        label='Correo electrónico', required=False)
    grupos = forms.ModelChoiceField(
        queryset=Group.objects.all(), required=False, label='Grupo', empty_label='---------')

    class Meta:
        model = User
        # password1 y password2 los provee UserCreationForm automáticamente
        fields = ['username', 'first_name', 'last_name',
                  'email', 'password1', 'password2', 'grupos']

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            grupos = self.cleaned_data.get('grupos')
            if grupos:
                user.groups.add(grupos)
        return user
